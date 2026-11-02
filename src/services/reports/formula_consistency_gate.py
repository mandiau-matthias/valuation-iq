"""Formula consistency gate — defensibility output check.

Runs after every report context is built and validates that the displayed
metric × multiple equals the displayed enterprise value within tolerance.
This is the structural check that prevents the class of bug where the
headline shows ``€137K × 1.50× = €347K`` (mathematically impossible).

Scope by method:

  *  EBITDA / Revenue / SDE / ARR / Fiscal-4×: gate validates
     ``displayed_basis × displayed_multiple ≈ enterprise_value`` within
     the configured tolerance (default 1 %). On failure the gate marks
     the context as ``defensibility_block_reason`` so the caller can
     either render an explicit error notice or short-circuit to a 422.

  *  DCF: gate is bypassed because EV is derived from PV of cashflows,
     not from a metric × multiple identity.

  *  Adjusted NAV / Adaptive / Startup: gate validates that the headline
     equity equals the engine's reported equity (no fantom-debt drift
     introduced by the rendering layer).

The gate is *strict by default* but can be downgraded to a warning via the
``soft`` flag during a rollout window.

Pure business logic — deterministic, fully testable, no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TOLERANCE = Decimal("0.01")  # 1 %
ABSOLUTE_TOLERANCE = Decimal("1")  # round-down floor in EUR


@dataclass
class FormulaCheck:
    name: str
    expected: float
    actual: float
    delta_pct: float
    passed: bool
    reason: str = ""


@dataclass
class FormulaGateResult:
    passed: bool
    method_key: str
    checks: list[FormulaCheck] = field(default_factory=list)
    block_reason: str | None = None

    def to_context_dict(self) -> dict[str, object]:
        return {
            "defensibility_gate_passed": self.passed,
            "defensibility_block_reason": self.block_reason,
            "defensibility_checks": [
                {
                    "name": c.name,
                    "expected": c.expected,
                    "actual": c.actual,
                    "delta_pct": c.delta_pct,
                    "passed": c.passed,
                    "reason": c.reason,
                }
                for c in self.checks
            ],
        }


@dataclass(frozen=True)
class FormulaMethodProfile:
    method_key: str
    metric_type: str
    is_dcf: bool
    is_asset: bool
    is_sde: bool
    has_weighted_synthesis: bool
    is_holding_sotp: bool


@dataclass(frozen=True)
class FormulaGateValues:
    enterprise_value: Decimal
    equity_value: Decimal
    net_debt: Decimal
    nwc_adjustment: Decimal
    tax_latency_net_impact: Decimal


def _safe_decimal(v: object) -> Decimal:
    if v is None:
        return Decimal("0")
    try:
        return Decimal(str(v))
    except Exception:  # noqa: BLE001 — context-construction must not crash here
        return Decimal("0")


def _first_present(context: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        if key in context and context[key] is not None:
            return context[key]
    return None


def _check_metric_multiple_ev(
    *,
    name: str,
    basis: Decimal,
    multiple: Decimal,
    enterprise_value: Decimal,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> FormulaCheck:
    """Validate ``basis × multiple ≈ enterprise_value`` within *tolerance*."""
    expected = basis * multiple
    if expected <= 0:
        return FormulaCheck(
            name=name,
            expected=float(expected),
            actual=float(enterprise_value),
            delta_pct=0.0,
            passed=basis <= 0 or multiple <= 0,
            reason="basis or multiple is non-positive — gate skipped",
        )

    delta = abs(enterprise_value - expected)
    delta_pct = (delta / expected) if expected > 0 else Decimal("0")
    passed = delta <= ABSOLUTE_TOLERANCE or delta_pct <= tolerance

    return FormulaCheck(
        name=name,
        expected=float(expected),
        actual=float(enterprise_value),
        delta_pct=float(delta_pct),
        passed=passed,
        reason=(
            "ok"
            if passed
            else (
                f"{name} mismatch: {float(basis):.2f} × {float(multiple):.4f} = "
                f"{float(expected):.2f}, but enterprise_value = {float(enterprise_value):.2f} "
                f"(Δ {float(delta_pct) * 100:.2f}%)"
            )
        ),
    )


def _check_equity_consistency(
    *,
    enterprise_value: Decimal,
    net_debt: Decimal,
    equity_value: Decimal,
    nwc_adjustment: Decimal = Decimal("0"),
    tax_latency_net_impact: Decimal = Decimal("0"),
) -> FormulaCheck:
    """Validate ``EV − net_debt + nwc + tax_lat ≈ equity`` within tolerance."""
    expected = enterprise_value - net_debt + nwc_adjustment + tax_latency_net_impact
    delta = abs(equity_value - expected)
    base = max(abs(expected), Decimal("1"))
    delta_pct = delta / base
    passed = delta <= ABSOLUTE_TOLERANCE or delta_pct <= DEFAULT_TOLERANCE
    return FormulaCheck(
        name="equity_bridge",
        expected=float(expected),
        actual=float(equity_value),
        delta_pct=float(delta_pct),
        passed=passed,
        reason=(
            "ok"
            if passed
            else (
                f"Equity bridge mismatch: EV {float(enterprise_value):.2f} "
                f"− net_debt {float(net_debt):.2f} + nwc {float(nwc_adjustment):.2f} "
                f"+ tax_latency {float(tax_latency_net_impact):.2f} = "
                f"{float(expected):.2f}, but equity = {float(equity_value):.2f} "
                f"(Δ {float(delta_pct) * 100:.2f}%)"
            )
        ),
    )


def _resolve_method_key(context: Mapping[str, object], method_key: str | None) -> str:
    resolved_method = (
        method_key
        or context.get("primary_method_key")
        or context.get("methodology")
        or context.get("method_override_selected_method")
        or context.get("recommended_methodology")
        or ""
    )
    return str(resolved_method or "").strip().lower()


def _build_method_profile(
    context: Mapping[str, object],
    method_key: str | None,
) -> FormulaMethodProfile:
    resolved_method = _resolve_method_key(context, method_key)
    return FormulaMethodProfile(
        method_key=resolved_method,
        metric_type=str(context.get("multiple_metric_type") or "").upper(),
        is_dcf="dcf" in resolved_method or bool(context.get("is_dcf_only_methodology")),
        is_asset=bool(context.get("is_asset_methodology")),
        is_sde=bool(context.get("is_sde_methodology")) or "sde" in resolved_method,
        has_weighted_synthesis=bool(context.get("has_weighted_synthesis")),
        is_holding_sotp=(
            "holding_sotp" in resolved_method or bool(context.get("is_holding_sotp_report"))
        ),
    )


def _extract_gate_values(context: Mapping[str, object]) -> FormulaGateValues:
    return FormulaGateValues(
        enterprise_value=_safe_decimal(
            _first_present(context, "enterprise_value_mid", "valuation")
        ),
        equity_value=_safe_decimal(_first_present(context, "equity_value", "equity_value_mid")),
        net_debt=_safe_decimal(context.get("net_debt")),
        nwc_adjustment=_safe_decimal(
            _first_present(context, "nwc_surplus_deficit", "nwc_adjustment")
        ),
        tax_latency_net_impact=_safe_decimal(context.get("tax_latency_net_impact")),
    )


def _check_equity_bridge(values: FormulaGateValues) -> FormulaCheck:
    return _check_equity_consistency(
        enterprise_value=values.enterprise_value,
        net_debt=values.net_debt,
        equity_value=values.equity_value,
        nwc_adjustment=values.nwc_adjustment,
        tax_latency_net_impact=values.tax_latency_net_impact,
    )


def _check_equity_premise(context: Mapping[str, object], values: FormulaGateValues) -> FormulaCheck:
    """Validate that an equity-premise method did not fabricate an EV.

    NAV, startup, fiscal and liquidation conclusions can begin and end at
    shareholder equity.  Applying an EV-minus-debt identity to those methods
    is a category error; the defensibility invariant is that EV remains N/A
    while a finite, non-negative equity conclusion is present.
    """

    enterprise_value = _first_present(context, "enterprise_value_mid", "enterprise_value")
    passed = enterprise_value is None and values.equity_value >= 0
    return FormulaCheck(
        name="equity_premise_ev_not_applicable",
        expected=0.0,
        actual=float(_safe_decimal(enterprise_value)),
        delta_pct=0.0 if passed else 1.0,
        passed=passed,
        reason=(
            "ok — equity-premise method retains EV as N/A"
            if passed
            else "Equity-premise method must not fabricate or relabel an enterprise value."
        ),
    )


def _check_dcf_no_balance_alignment(values: FormulaGateValues) -> FormulaCheck:
    delta = abs(values.enterprise_value - values.equity_value)
    return FormulaCheck(
        name="dcf_no_balance_equity_alignment",
        expected=float(values.enterprise_value),
        actual=float(values.equity_value),
        delta_pct=float(delta / max(abs(values.enterprise_value), Decimal("1"))),
        passed=delta <= ABSOLUTE_TOLERANCE,
        reason=(
            "DCF without balance inputs: equity must equal EV; "
            "any gap is a phantom-debt rendering bug."
        ),
    )


def _check_dcf_channel(
    context: Mapping[str, object],
    values: FormulaGateValues,
) -> list[FormulaCheck]:
    if bool(context.get("has_balance_data")):
        return [_check_equity_bridge(values)]

    return [_check_dcf_no_balance_alignment(values)]


def _check_sotp_value(
    *,
    name: str,
    expected: Decimal,
    actual: Decimal,
) -> FormulaCheck:
    delta = abs(actual - expected)
    base = max(abs(expected), Decimal("1"))
    delta_pct = delta / base
    passed = delta <= ABSOLUTE_TOLERANCE
    return FormulaCheck(
        name=name,
        expected=float(expected),
        actual=float(actual),
        delta_pct=float(delta_pct),
        passed=passed,
        reason=(
            "ok"
            if passed
            else (
                f"{name} mismatch: committed SOTP {float(expected):.2f}, "
                f"report {float(actual):.2f} (delta {float(delta_pct) * 100:.2f}%)"
            )
        ),
    )


def _check_holding_sotp_channel(
    context: Mapping[str, object],
    values: FormulaGateValues,
) -> list[FormulaCheck]:
    sotp = context.get("holding_sotp")
    if not isinstance(sotp, Mapping) or sotp.get("available") is not True:
        return [
            FormulaCheck(
                name="holding_sotp_schedule",
                expected=1.0,
                actual=0.0,
                delta_pct=1.0,
                passed=False,
                reason="Holding SOTP headline has no available committed entity schedule.",
            )
        ]
    return [
        _check_sotp_value(
            name="holding_sotp_enterprise_mid",
            expected=_safe_decimal(sotp.get("enterprise_value_mid")),
            actual=values.enterprise_value,
        ),
        _check_sotp_value(
            name="holding_sotp_equity_mid",
            expected=_safe_decimal(sotp.get("equity_value_mid")),
            actual=values.equity_value,
        ),
    ]


def _metric_basis_and_multiple(
    context: Mapping[str, object],
    profile: FormulaMethodProfile,
) -> tuple[str, Decimal, Decimal]:
    applied_multiple = _safe_decimal(context.get("applied_multiple"))

    if profile.is_sde:
        sde_multiple = _safe_decimal(context.get("sde_multiple")) or applied_multiple
        return "sde × sde_multiple = EV", _safe_decimal(context.get("sde_value")), sde_multiple

    if profile.metric_type == "REVENUE":
        basis = _safe_decimal(_first_present(context, "revenue", "valuation_basis_value"))
        return "revenue × revenue_multiple = EV", basis, applied_multiple

    if profile.metric_type == "ARR":
        return (
            "arr × arr_multiple = EV",
            _safe_decimal(context.get("valuation_basis_value")),
            applied_multiple,
        )

    # A sealed run can price weighted earnings while the annual statements
    # show current-year EBITDA. Validate the committed pricing denominator.
    basis = _safe_decimal(_first_present(context, "valuation_basis_value", "sustainable_ebitda"))
    return "ebitda × ebitda_multiple = EV", basis, applied_multiple


def _check_multiples_channel(
    context: Mapping[str, object],
    profile: FormulaMethodProfile,
    values: FormulaGateValues,
    tolerance: Decimal,
) -> list[FormulaCheck]:
    basis_name, basis, multiple = _metric_basis_and_multiple(context, profile)
    return [
        _check_metric_multiple_ev(
            name=basis_name,
            basis=basis,
            multiple=multiple,
            enterprise_value=values.enterprise_value,
            tolerance=tolerance,
        ),
        _check_equity_bridge(values),
    ]


def _check_cover_body_synthesis(
    context: Mapping[str, object],
    values: FormulaGateValues,
    tolerance: Decimal,
) -> FormulaCheck | None:
    if not context.get("has_weighted_synthesis"):
        return None

    synthesis_blended = _safe_decimal(context.get("synthesis_blended_value"))
    synthesis_basis = (
        str(
            context.get("synthesis_value_basis")
            or context.get("headline_value_basis")
            or context.get("value_basis")
            or "equity_value"
        )
        .strip()
        .lower()
    )
    is_enterprise_value = synthesis_basis == "enterprise_value"
    body_value = (
        values.enterprise_value
        if is_enterprise_value
        else values.equity_value if values.equity_value > 0 else values.enterprise_value
    )
    body_label = "enterprise value" if is_enterprise_value else "equity"
    if synthesis_blended <= 0 or body_value <= 0:
        return None

    delta = abs(synthesis_blended - body_value)
    delta_pct = delta / body_value
    cover_ok = delta <= ABSOLUTE_TOLERANCE or delta_pct <= tolerance
    return FormulaCheck(
        name=f"cover synthesis = body {body_label}",
        expected=float(body_value),
        actual=float(synthesis_blended),
        delta_pct=float(delta_pct),
        passed=cover_ok,
        reason=(
            "ok"
            if cover_ok
            else (
                f"cover synthesis {float(synthesis_blended):.2f} ≠ body {body_label} "
                f"{float(body_value):.2f} (Δ {float(delta_pct) * 100:.2f}%) — "
                "two-brain split: the weighted cover must equal the body."
            )
        ),
    )


def _build_formula_checks(
    context: Mapping[str, object],
    profile: FormulaMethodProfile,
    values: FormulaGateValues,
    tolerance: Decimal,
) -> list[FormulaCheck]:
    if profile.is_holding_sotp:
        checks = _check_holding_sotp_channel(context, values)
    elif profile.is_dcf:
        checks = _check_dcf_channel(context, values)
    elif context.get("enterprise_value_applicability") == "not_applicable":
        checks = [_check_equity_premise(context, values)]
    elif profile.has_weighted_synthesis or profile.is_asset:
        # Weighted synthesis and asset methods are not single metric × multiple identities.
        checks = [_check_equity_bridge(values)]
    else:
        checks = _check_multiples_channel(context, profile, values, tolerance)

    # An EV-only conclusion has no equity bridge to reconcile. Keep its
    # method arithmetic checks, while retaining bridge checks for known zero
    # equity and for every report that publishes an equity conclusion.
    if (
        context.get("headline_value_basis") == "enterprise_value"
        and all(
            context.get(key) is None
            for key in ("equity_value", "equity_value_mid", "equity_value_low", "equity_value_high")
        )
        and _first_present(context, "enterprise_value_mid", "valuation") is not None
    ):
        checks = [check for check in checks if check.name != "equity_bridge"]

    # Cover == body. When a user-weighted synthesis drives the cover headline, it
    # MUST equal the body's authoritative equity. A gap is the VAL-2026 "two-brain"
    # regression (the cover blended a GROSS multiples leg → €582K while the body
    # showed €554K). This gate guards reconcile_synthesis_multiples_legs so the
    # split can never silently return — independent of method type.
    synthesis_check = _check_cover_body_synthesis(context, values, tolerance)
    if synthesis_check is not None:
        checks.append(synthesis_check)

    return checks


def _result_from_checks(
    *,
    method_key: str,
    checks: list[FormulaCheck],
    soft: bool,
) -> FormulaGateResult:
    failed = [c for c in checks if not c.passed]
    if not failed:
        return FormulaGateResult(passed=True, method_key=method_key, checks=checks)

    block_reason = " | ".join(c.reason for c in failed)
    result = FormulaGateResult(
        passed=False,
        method_key=method_key,
        checks=checks,
        block_reason=block_reason,
    )
    if soft:
        logger.warning(
            "Formula gate failed (soft mode — render proceeds)",
            extra={"method_key": method_key, "block_reason": block_reason},
        )
        result.passed = True  # soft mode does not block
    else:
        logger.error(
            "Formula gate BLOCKED rendering",
            extra={"method_key": method_key, "block_reason": block_reason},
        )
    return result


def run_formula_gate(
    context: Mapping[str, object],
    *,
    method_key: str | None = None,
    soft: bool = False,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> FormulaGateResult:
    """Run the defensibility gate against *context*.

    The function is read-only on *context* — call ``apply_gate_to_context``
    if you want to merge the result into the context dict.
    """
    profile = _build_method_profile(context, method_key)
    values = _extract_gate_values(context)
    checks = _build_formula_checks(context, profile, values, tolerance)
    return _result_from_checks(method_key=profile.method_key, checks=checks, soft=soft)


def apply_gate_to_context(
    context: dict[str, object],
    *,
    method_key: str | None = None,
    soft: bool = False,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> FormulaGateResult:
    """Run the gate and stamp the result onto *context*.

    Sets:
      *  ``defensibility_gate_passed``     — bool
      *  ``defensibility_block_reason``    — str | None
      *  ``defensibility_checks``          — list of dicts (template diagnostic)
    """
    result = run_formula_gate(context, method_key=method_key, soft=soft, tolerance=tolerance)
    context.update(result.to_context_dict())
    return result
