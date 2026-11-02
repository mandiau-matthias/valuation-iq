"""SDE channel — single source of truth for SDE rendering context.

This module exists to keep the SDE valuation channel cleanly isolated from
the EBITDA / Revenue / DCF / NAV / Fiscal / ARR / Adaptive / Startup
channels.  When the SDE method is the active selection, the report context
must be built coherently from SDE inputs only:

  *  basis = SDE  (NOT sustainable_ebitda)
  *  multiple = SDE multiple  (NOT EBITDA cascade output)
  *  multiple_metric_type = "SDE"  (drives label "EV/SDE")
  *  P25 / P75 = SDE percentiles  (NOT EBITDA percentiles)
  *  calibration cascade = base SDE × owner_concentration × size × DLOM × Belgian premium
  *  enterprise_value = SDE × applied_SDE_multiple  (no EBITDA cascade leak)

Every previous bug had the same root cause: the EBITDA cascade leaked into
the SDE rendering. By centralising the channel in one module that the
omni-calc override and the aggregator both consume, that whole class of
bug becomes structurally impossible — there is one place that knows what
"SDE active" means for the report.

Pure business logic — no FastAPI, no I/O, deterministic, fully testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.services.reports.adaptive_report_gates import refresh_adaptive_gates_on_context
from src.services.reports.sde_channel_rows import ReportContext, ReportRows
from src.services.reports.sde_channel_rows import bridge_row as _bridge_row
from src.services.reports.sde_channel_rows import calibration_step as _calibration_step
from src.services.reports.sde_channel_rows import (
    calibration_to_waterfall_steps as _calibration_to_waterfall_steps,
)
from src.services.reports.sde_channel_rows import row as _row
from src.utils.decimal_helpers import safe_decimal, safe_float
from src.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Tunable defaults
# ---------------------------------------------------------------------------

# Owner-concentration multiplicative discount on the SDE multiple, by tier.
# Empirical: BVR Pepperdine 2024 + Hitchner 2017 chapter on key-person risk.
# These are SDE-specific because SDE *already* embeds the owner; concentration
# captures the residual risk that the buyer's cashflow assumes a replacement
# operator can be found and retained.
SDE_OWNER_CONCENTRATION_DISCOUNT: dict[str, Decimal] = {
    "low": Decimal("0.0"),  # diversified team, multiple owners, documented succession
    "medium": Decimal("-0.08"),  # 2–3 owners, key-person dependency present but mitigated
    "high": Decimal("-0.18"),  # 1 owner, central relationship/sales role, no succession plan
}

# Size discount on the SDE multiple by revenue band. Lower than the EBITDA
# cascade because SDE multiples are already calibrated to micro/small.
SDE_SIZE_DISCOUNT: dict[str, Decimal] = {
    "micro": Decimal("-0.06"),  # < EUR 500K
    "small": Decimal("-0.04"),  # EUR 500K – 2M
    "lower_middle": Decimal("-0.02"),  # EUR 2M – 5M
}

# Belgium / Benelux DLOM (Discount for Lack of Marketability) for private
# SME shares, scaled for SDE-eligible micro/small caps. Empirical anchor:
# Stout Restricted Stock studies + FMV Opinions pre-IPO data.
SDE_DLOM_BY_COUNTRY_AND_SIZE: dict[str, dict[str, Decimal]] = {
    "BE": {
        "micro": Decimal("-0.30"),
        "small": Decimal("-0.25"),
        "lower_middle": Decimal("-0.20"),
    },
    "NL": {
        "micro": Decimal("-0.28"),
        "small": Decimal("-0.23"),
        "lower_middle": Decimal("-0.18"),
    },
    "DEFAULT": {
        "micro": Decimal("-0.25"),
        "small": Decimal("-0.20"),
        "lower_middle": Decimal("-0.15"),
    },
}

# Belgian market premium — small structural premium for BE-incorporated
# entities reflecting tighter buyer market and post-2026 fiscal regime
# clarity. Kept symmetric to the engine implementation in Step 2.7.
DEFAULT_BELGIAN_MARKET_PREMIUM = Decimal("0.05")


# ---------------------------------------------------------------------------
# Inputs / Outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SdeChannelInputs:
    """Minimum inputs required to render an SDE channel context.

    Every field has a deterministic default so the channel cannot crash if
    upstream omits something; missing values are surfaced via warnings,
    never via silent incorrect math.
    """

    sde_value: Decimal
    sde_base_multiple: Decimal
    revenue: Decimal
    total_debt: Decimal = Decimal("0")
    cash: Decimal = Decimal("0")
    nwc_adjustment: Decimal = Decimal("0")
    owner_salary_addback: Decimal = Decimal("0")
    owner_salary_estimate: Decimal = Decimal("0")
    owner_salary_source: str = "estimate"
    owner_role: str = "working"
    num_owners: int = 1
    business_size: str = "small"  # "micro" | "small" | "lower_middle"
    country_code: str = "BE"
    industry: str = ""
    business_type_id: str = ""
    # Optional engine-supplied benchmark range (P25 / P75 of SDE multiple).
    # When absent, the channel computes a symmetric ±15% band around base.
    sde_multiple_p25: Optional[Decimal] = None
    sde_multiple_p75: Optional[Decimal] = None
    # Optional override of the owner-concentration tier — when the engine has
    # qualitative info (succession plan, replacement hire executed, etc.) it
    # can downgrade the default HIGH tier.
    owner_concentration_tier_override: Optional[str] = None
    # Optional override of Belgian market premium.
    belgian_market_premium_override: Optional[Decimal] = None


@dataclass(frozen=True)
class SdeCalibrationAdjustments:
    owner_concentration_tier: str
    owner_concentration_adjustment: Decimal
    size_discount_adjustment: Decimal
    liquidity_discount_adjustment: Decimal
    belgian_market_premium: Decimal


@dataclass
class SdeChannelResult:
    """Coherent SDE channel state ready to drop into the report context."""

    sde_value: float
    sde_base_multiple: float
    sde_applied_multiple: float
    sde_multiple_p25: float
    sde_multiple_p75: float
    enterprise_value: float
    enterprise_value_low: float
    enterprise_value_high: float
    equity_value: float
    equity_value_low: float
    equity_value_high: float
    # Bridge components — exposed independently so the rendering layer
    # never has to back out net_debt from an EV/Equity gap (which leaks
    # NWC into net_debt).
    net_debt: float
    nwc_adjustment: float
    owner_concentration_tier: str
    owner_concentration_adjustment: float
    size_discount_adjustment: float
    liquidity_discount_adjustment: float
    belgian_market_premium: float
    owner_salary_addback: float
    owner_salary_estimate: float
    owner_salary_source: str
    owner_role: str
    calibration_steps: ReportRows = field(default_factory=list)
    sde_bridge: ReportRows = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Risk overrides
# ---------------------------------------------------------------------------


def resolve_owner_concentration_tier(
    *,
    num_owners: int,
    business_size: str,
    override: Optional[str] = None,
) -> str:
    """Default owner-concentration tier for SDE-eligible businesses.

    SDE businesses are by definition owner-operated, so the *default* posture
    is HIGH key-person risk. The engine or user input may downgrade this to
    MEDIUM (2–3 owners or documented succession) or LOW (≥4 owners with
    distributed customer relationships). The default is conservative, in
    keeping with the spirit of SDE multiples (BVR / IBBA 2024).
    """
    if override:
        normalized = str(override).strip().lower()
        if normalized in SDE_OWNER_CONCENTRATION_DISCOUNT:
            return normalized

    n = max(1, int(num_owners or 1))
    if n >= 4:
        return "low"
    if n >= 2:
        return "medium"
    # Single-owner micro/small: default HIGH per BVR / IBBA practice.
    return "high"


def resolve_dlom_adjustment(country_code: str, business_size: str) -> Decimal:
    """Liquidity discount calibrated to SDE-eligible micro/small SMEs."""
    cc = (country_code or "BE").upper()
    table = SDE_DLOM_BY_COUNTRY_AND_SIZE.get(cc) or SDE_DLOM_BY_COUNTRY_AND_SIZE["DEFAULT"]
    size_key = business_size if business_size in table else "small"
    return table.get(size_key, table["small"])


def _belgian_market_premium(inputs: SdeChannelInputs) -> Decimal:
    if inputs.belgian_market_premium_override is not None:
        return inputs.belgian_market_premium_override
    if inputs.country_code.upper() == "BE":
        return DEFAULT_BELGIAN_MARKET_PREMIUM
    return Decimal("0")


def _calibration_adjustments(inputs: SdeChannelInputs) -> SdeCalibrationAdjustments:
    owner_tier = resolve_owner_concentration_tier(
        num_owners=inputs.num_owners,
        business_size=inputs.business_size,
        override=inputs.owner_concentration_tier_override,
    )
    return SdeCalibrationAdjustments(
        owner_concentration_tier=owner_tier,
        owner_concentration_adjustment=SDE_OWNER_CONCENTRATION_DISCOUNT[owner_tier],
        size_discount_adjustment=SDE_SIZE_DISCOUNT.get(inputs.business_size, Decimal("0")),
        liquidity_discount_adjustment=resolve_dlom_adjustment(
            inputs.country_code,
            inputs.business_size,
        ),
        belgian_market_premium=_belgian_market_premium(inputs),
    )


def _float_or_zero(value: object) -> float:
    rendered = safe_float(value)
    if rendered is None:
        return 0.0
    return rendered


def _text_or_default(value: str, default: str) -> str:
    if value:
        return value
    return default


# ---------------------------------------------------------------------------
# Calibration cascade
# ---------------------------------------------------------------------------


def _apply_multiplicative(base: Decimal, factor: Decimal) -> Decimal:
    """Apply a signed factor (e.g. -0.18 for a 18% discount) to *base*.

    Returns base * (1 + factor), guarding against base <= 0.
    """
    if base <= 0:
        return Decimal("0")
    return (base * (Decimal("1") + factor)).quantize(Decimal("0.0001"))


def _owner_addback_label(owner_role: str) -> str:
    normalized_role = str(owner_role or "").lower()
    if normalized_role == "working":
        return "Working owner — market replacement compensation"
    if normalized_role == "passive":
        return "Passive investor compensation add-back (full)"
    return "Owner compensation add-back"


def build_calibration_cascade(
    inputs: SdeChannelInputs,
    *,
    adjustments: SdeCalibrationAdjustments | None = None,
) -> ReportRows:
    """Build the SDE-specific multiple calibration cascade.

    Output mirrors the structure expected by ``_build_multiple_waterfall_steps``
    in the aggregator so the same waterfall renderer can draw it.
    """
    base = safe_decimal(inputs.sde_base_multiple)
    if base <= 0:
        return []

    adjustments = adjustments or _calibration_adjustments(inputs)

    steps: ReportRows = []
    running = base

    steps.append(
        _calibration_step(
            "Base SDE multiple",
            f"Industry SDE median for {inputs.industry or 'sector'} "
            f"({inputs.business_size}) — BVR / Pepperdine 2024.",
            running,
            running,
            "base",
        )
    )

    if adjustments.owner_concentration_adjustment != 0:
        new_val = _apply_multiplicative(
            running,
            adjustments.owner_concentration_adjustment,
        )
        impact = new_val - running
        description = (
            f"{adjustments.owner_concentration_tier.upper()} key-person risk: "
            f"{int(inputs.num_owners)} owner(s); "
            "default for SDE-eligible micro/small unless succession is documented."
        )
        steps.append(
            _calibration_step(
                f"Owner concentration ({adjustments.owner_concentration_tier})",
                description,
                new_val,
                impact,
                "decrease" if impact < 0 else "increase",
            )
        )
        running = new_val

    if adjustments.size_discount_adjustment != 0:
        new_val = _apply_multiplicative(running, adjustments.size_discount_adjustment)
        impact = new_val - running
        steps.append(
            _calibration_step(
                f"Size discount ({inputs.business_size})",
                "Size adjustment for SDE-eligible micro/small caps.",
                new_val,
                impact,
                "decrease" if impact < 0 else "increase",
            )
        )
        running = new_val

    if adjustments.liquidity_discount_adjustment != 0:
        new_val = _apply_multiplicative(
            running,
            adjustments.liquidity_discount_adjustment,
        )
        impact = new_val - running
        description = (
            f"Private-company illiquidity discount calibrated for "
            f"{inputs.country_code.upper()} micro/small SMEs "
            "(Stout Restricted Stock 2024 / FMV pre-IPO studies)."
        )
        steps.append(
            _calibration_step(
                "Illiquidity discount (DLOM)",
                description,
                new_val,
                impact,
                "decrease" if impact < 0 else "increase",
            )
        )
        running = new_val

    if adjustments.belgian_market_premium != 0:
        new_val = _apply_multiplicative(running, adjustments.belgian_market_premium)
        impact = new_val - running
        steps.append(
            _calibration_step(
                "Belgian market premium",
                "Belgian SME M&A market premium (Vlerick / Moore 2024).",
                new_val,
                impact,
                "increase" if impact > 0 else "decrease",
            )
        )
        running = new_val

    steps.append(
        _calibration_step(
            "Applied SDE multiple",
            "Final SDE multiple after calibration adjustments.",
            running,
            running,
            "total",
        )
    )

    return steps


# ---------------------------------------------------------------------------
# Bridge (Reported EBITDA → SDE)
# ---------------------------------------------------------------------------


def build_sde_bridge(
    *,
    normalized_ebitda_basis: Decimal,
    sde_value: Decimal,
    owner_salary_addback: Decimal,
    owner_role: str,
) -> ReportRows:
    """Reported EBITDA → SDE bridge ladder with running totals.

    Always renders at least the anchor and total rows so the report never
    shows a blank "Aanpassingsoverzicht" when the user supplied an explicit
    owner_salary_addback through the wizard.
    """
    bridge: ReportRows = []
    running = float(normalized_ebitda_basis or 0)

    bridge.append(_bridge_row("Normalised EBITDA basis", running, running, "anchor"))

    add = float(owner_salary_addback or 0)
    if add != 0:
        running += add
        bridge.append(
            _bridge_row(
                f"+ {_owner_addback_label(owner_role)}",
                add,
                round(running, 2),
                "addback",
            )
        )

    # Reconciliation row — the engine total wins if there is rounding drift.
    bridge.append(
        _bridge_row(
            "= Seller's Discretionary Earnings (SDE)",
            float(sde_value or 0),
            float(sde_value or 0),
            "total",
        )
    )
    return bridge


def _calibrated_sde_percentile_band(
    *,
    inputs: SdeChannelInputs,
    base: Decimal,
    applied: Decimal,
    warnings: list[str],
) -> tuple[Decimal, Decimal]:
    """Return P25/P75 multiples in the same calibrated space as ``applied``.

    Titan/Upswitch Index benchmark percentiles describe the raw SDE multiple cell. The
    channel then applies owner concentration, size, liquidity, and Belgian
    market adjustments to the median. If the raw percentiles are used unchanged
    against the adjusted median, the low percentile can exceed the mid, which
    pushes Step 11 into after-the-fact band repair. Scale supplied percentiles
    by the same calibration ratio as the median so the whole band lives in one
    valuation basis.
    """
    raw_p25 = safe_decimal(inputs.sde_multiple_p25) if inputs.sde_multiple_p25 is not None else None
    raw_p75 = safe_decimal(inputs.sde_multiple_p75) if inputs.sde_multiple_p75 is not None else None

    if raw_p25 is None and raw_p75 is None:
        return applied * Decimal("0.85"), applied * Decimal("1.15")

    calibration_ratio = applied / base if base > 0 else Decimal("0")
    p25 = (raw_p25 * calibration_ratio) if raw_p25 is not None else applied * Decimal("0.85")
    p75 = (raw_p75 * calibration_ratio) if raw_p75 is not None else applied * Decimal("1.15")

    p25 = p25.quantize(Decimal("0.0001"))
    p75 = p75.quantize(Decimal("0.0001"))

    if p25 <= applied <= p75:
        return p25, p75

    original_p25 = p25
    original_p75 = p75
    p25 = min(original_p25, original_p75, applied)
    p75 = max(original_p25, original_p75, applied)
    warning = (
        "SDE percentile band normalized after calibration because supplied "
        "P25/P75 did not contain the applied SDE multiple."
    )
    warnings.append(warning)
    logger.warning(
        "SDE channel normalized calibrated percentile band",
        extra={
            "raw_p25": str(raw_p25),
            "raw_p75": str(raw_p75),
            "base_multiple": str(base),
            "applied_multiple": str(applied),
            "original_calibrated_p25": str(original_p25),
            "original_calibrated_p75": str(original_p75),
            "normalized_p25": str(p25),
            "normalized_p75": str(p75),
        },
    )
    return p25, p75


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def build_sde_channel(inputs: SdeChannelInputs) -> SdeChannelResult:
    """Compute a fully-coherent SDE channel state.

    Math is *deliberately* re-derived inside this module rather than reading
    EV / equity from upstream — this is a defensive boundary so the channel
    cannot inherit a wrong EV from the EBITDA cascade.
    """
    warnings: list[str] = []
    sde = safe_decimal(inputs.sde_value)
    base = safe_decimal(inputs.sde_base_multiple)

    if sde <= 0:
        warnings.append("sde_value is non-positive — channel cannot compute a defensible EV.")
    if base <= 0:
        warnings.append("sde_base_multiple is non-positive — channel cannot calibrate.")

    adjustments = _calibration_adjustments(inputs)
    cascade = build_calibration_cascade(inputs, adjustments=adjustments)
    applied = Decimal(str(cascade[-1]["multiple"])) if cascade else base

    # Percentile range — keep P25/P75 in the same calibrated multiple space as
    # the adjusted median. This prevents raw benchmark percentiles from sitting
    # above a post-risk adjusted SDE mid value.
    p25, p75 = _calibrated_sde_percentile_band(
        inputs=inputs,
        base=base,
        applied=applied,
        warnings=warnings,
    )

    ev_mid = (sde * applied).quantize(Decimal("0.01"))
    ev_low = (sde * p25).quantize(Decimal("0.01"))
    ev_high = (sde * p75).quantize(Decimal("0.01"))

    # EV → Equity bridge (cash, debt, NWC). Channel does NOT invent a net
    # debt from an EV/Equity gap — that fantom-debt anti-pattern is exactly
    # what the defensibility gate forbids.
    net_debt = safe_decimal(inputs.total_debt) - safe_decimal(inputs.cash)
    nwc = safe_decimal(inputs.nwc_adjustment)
    equity_mid = (ev_mid - net_debt + nwc).quantize(Decimal("0.01"))
    equity_low = (ev_low - net_debt + nwc).quantize(Decimal("0.01"))
    equity_high = (ev_high - net_debt + nwc).quantize(Decimal("0.01"))

    bridge = build_sde_bridge(
        normalized_ebitda_basis=safe_decimal(inputs.sde_value)
        - safe_decimal(inputs.owner_salary_addback),
        sde_value=sde,
        owner_salary_addback=safe_decimal(inputs.owner_salary_addback),
        owner_role=inputs.owner_role,
    )

    return SdeChannelResult(
        sde_value=_float_or_zero(sde),
        sde_base_multiple=_float_or_zero(base),
        sde_applied_multiple=_float_or_zero(applied),
        sde_multiple_p25=_float_or_zero(p25),
        sde_multiple_p75=_float_or_zero(p75),
        enterprise_value=_float_or_zero(ev_mid),
        enterprise_value_low=_float_or_zero(ev_low),
        enterprise_value_high=_float_or_zero(ev_high),
        equity_value=_float_or_zero(equity_mid),
        equity_value_low=_float_or_zero(equity_low),
        equity_value_high=_float_or_zero(equity_high),
        net_debt=_float_or_zero(net_debt),
        nwc_adjustment=_float_or_zero(nwc),
        owner_concentration_tier=adjustments.owner_concentration_tier,
        owner_concentration_adjustment=_float_or_zero(
            adjustments.owner_concentration_adjustment,
        ),
        size_discount_adjustment=_float_or_zero(adjustments.size_discount_adjustment),
        liquidity_discount_adjustment=_float_or_zero(
            adjustments.liquidity_discount_adjustment,
        ),
        belgian_market_premium=_float_or_zero(adjustments.belgian_market_premium),
        owner_salary_addback=_float_or_zero(inputs.owner_salary_addback),
        owner_salary_estimate=_float_or_zero(inputs.owner_salary_estimate),
        owner_salary_source=_text_or_default(inputs.owner_salary_source, "estimate"),
        owner_role=_text_or_default(inputs.owner_role, "working"),
        calibration_steps=cascade,
        sde_bridge=bridge,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Context wiring — the seam between the channel and the rendering layer
# ---------------------------------------------------------------------------


def apply_sde_channel_to_context(
    context: ReportContext,
    *,
    channel: SdeChannelResult,
    locale: str = "nl",
) -> ReportContext:
    """Atomically replace the EBITDA-cascade context fields with SDE channel state.

    This is the *only* function that should write SDE rendering fields onto
    the report context. omni_calc_overrides and main_report_data_aggregator
    both call this so the contract is single-sourced.

    Side-effects on *context* (returned for chaining):

      *  Replaces metric_type, multiple_metric_type, multiple_display_label,
         benchmark labels with SDE-aware variants.
      *  Replaces base_multiple, applied_multiple, P25/P75, EV / equity
         range with SDE channel values.
      *  Replaces multiple_waterfall_steps with the SDE calibration cascade.
      *  Sets sde_value, sde_multiple, sde_components, sde_bridge.
      *  Stamps multiple_metric_type='SDE' so the consistency gate validates
         against SDE × SDE multiple, not EBITDA × EBITDA multiple.
    """
    # ── basis figures ──
    context["sde_value"] = channel.sde_value
    context["sde_multiple"] = channel.sde_applied_multiple
    context["sde_base_multiple"] = channel.sde_base_multiple
    context["sde_multiple_p25"] = channel.sde_multiple_p25
    context["sde_multiple_p75"] = channel.sde_multiple_p75
    context["sde_owner_salary"] = channel.owner_salary_addback
    context["sde_owner_salary_source"] = channel.owner_salary_source
    context["sde_owner_role"] = channel.owner_role
    context["sde_owner_concentration_tier"] = channel.owner_concentration_tier
    context["valuation_basis_value"] = channel.sde_value

    # ── multiple display ──
    context["applied_multiple"] = channel.sde_applied_multiple
    context["base_multiple"] = channel.sde_base_multiple
    context["multiple_low"] = channel.sde_multiple_p25
    context["multiple_high"] = channel.sde_multiple_p75
    context["multiple_metric_type"] = "SDE"
    context["multiple_display_label"] = _sde_multiple_display_label(locale)
    context["benchmark_multiple_label"] = _sde_benchmark_label(locale)
    context["benchmark_multiple_mid"] = channel.sde_base_multiple
    context["benchmark_multiple_low"] = channel.sde_multiple_p25
    context["benchmark_multiple_high"] = channel.sde_multiple_p75

    # ── EV / equity ──
    context["valuation"] = channel.enterprise_value
    context["enterprise_value_mid"] = channel.enterprise_value
    context["enterprise_value_low"] = channel.enterprise_value_low
    context["enterprise_value_high"] = channel.enterprise_value_high
    context["valuation_low"] = channel.enterprise_value_low
    context["valuation_high"] = channel.enterprise_value_high
    context["equity_value"] = channel.equity_value
    context["equity_value_mid"] = channel.equity_value
    context["equity_value_low"] = channel.equity_value_low
    context["equity_value_high"] = channel.equity_value_high
    # SDE-specific EV alias — drives the dedicated SDE page's "= Enterprise
    # Value" row AND the `has_sde_page` aggregator gate fallback. Without
    # this alias the EV row silently disappears from the SDE summary card.
    context["ev_sde_enterprise_value"] = channel.enterprise_value

    # ── EV → equity bridge (channel is authoritative) ──
    # The channel exposes net_debt and nwc_adjustment as independent
    # fields so the rendering layer never has to back them out from the
    # EV/Equity gap. This guarantees the formula gate's identity
    # ``equity = EV − net_debt + nwc + tax_lat`` reconciles exactly.
    context["net_debt"] = round(channel.net_debt, 2)
    context["nwc_adjustment"] = round(channel.nwc_adjustment, 2)
    context["nwc_surplus_deficit"] = round(channel.nwc_adjustment, 2)
    bridge_delta = channel.enterprise_value - channel.equity_value
    if abs(bridge_delta) < 0.01:
        context["show_ev_equity_bridge"] = False
        context["has_net_debt_adjustment"] = False
        context["bridge_net_debt_amount"] = 0.0
        context["bridge_net_debt_operator"] = "−"
    else:
        context["show_ev_equity_bridge"] = True
        context["has_net_debt_adjustment"] = abs(channel.net_debt) > 0.01
        context["bridge_net_debt_amount"] = round(abs(channel.net_debt), 2)
        context["bridge_net_debt_operator"] = "−" if channel.net_debt > 0 else "+"

    # ── methodology flags ──
    context["has_sde"] = True
    context["is_sde_methodology"] = True
    context["is_asset_methodology"] = False
    context["is_dcf_only_methodology"] = False
    context["is_revenue_multiple_method"] = False
    context["supports_metric_to_ev_bridge"] = True

    # ── waterfall + bridge ──
    waterfall_steps = _calibration_to_waterfall_steps(channel.calibration_steps)
    context["multiple_waterfall_steps"] = waterfall_steps
    context["sde_calibration_steps"] = channel.calibration_steps
    context["sde_bridge"] = channel.sde_bridge

    # Populate the calibration ledger inputs with SDE-shaped rows so the
    # `_calibration_ledger.html` partial (which reads `calibration_steps`
    # / `discount_waterfall`) renders the SDE cascade instead of falling
    # back to a synthetic EBITDA-shaped reconstruction.
    ledger_rows: ReportRows = []
    sde_value_for_ev = channel.sde_value if channel.sde_value > 0 else 1.0
    for idx, step in enumerate(channel.calibration_steps):
        mult = float(step.get("multiple") or 0)
        impact = step.get("impact")
        if impact is None or step.get("kind") == "base":
            row_impact = None
        else:
            row_impact = float(impact)
        ledger_rows.append(
            _row(
                label=step.get("label"),
                multiple=mult,
                impact=row_impact,
                ev=float(sde_value_for_ev) * mult,
                ref="",
                description=step.get("description"),
            )
        )
    context["calibration_steps"] = ledger_rows
    context["discount_waterfall"] = ledger_rows
    # Clear EBITDA-shaped reconstruction inputs that the ledger would
    # otherwise use as fallback when calibration_steps is empty.
    context["owner_dependency_adjustment"] = 0
    context["size_discount_percentage"] = 0

    # ── adjustments table fallback (if EBITDA-normalization data is empty,
    # surface the SDE bridge so the report never shows €0 adjustments when
    # the user supplied an owner add-back). ──
    if channel.owner_salary_addback and not context.get("ebitda_adjustments"):
        context["ebitda_adjustments_sde_fallback"] = channel.sde_bridge
        context["total_adjustments"] = channel.owner_salary_addback

    # ── single-method override markers ──
    context["valuation_methodology"] = "SDE Multiples"
    context["valuation_methodology_display"] = _sde_methodology_display(locale)
    context["methodology"] = "sde_multiple"
    context["recommended_methodology"] = "SDE Multiples"
    context["primary_method_key"] = "sde_multiple"
    context["primary_method_label"] = _sde_methodology_display(locale)

    refresh_adaptive_gates_on_context(context)
    return context


def _sde_multiple_display_label(locale: str) -> str:
    return "SDE-multiple (EV/SDE)"


def _sde_benchmark_label(locale: str) -> str:
    if str(locale or "nl").lower().startswith("nl"):
        return "Marktmediaan (EV/SDE)"
    return "Market median (EV/SDE)"


def _sde_methodology_display(locale: str) -> str:
    if str(locale or "nl").lower().startswith("nl"):
        return "SDE-multiple"
    return "SDE Multiple"


# ---------------------------------------------------------------------------
# Public idempotent applicator
# ---------------------------------------------------------------------------


def ensure_sde_channel_applied(
    context: ReportContext,
    valuation_data: ReportContext,
    *,
    locale: str = "nl",
) -> bool:
    """Compatibility wrapper for callers that still import from sde_channel."""
    from src.services.reports.sde_channel_applicator import (
        ensure_sde_channel_applied as apply_sde_channel,
    )

    return apply_sde_channel(context, valuation_data, locale=locale)
