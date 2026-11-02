"""Final response-policy helpers for stateless valuation calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping, Protocol

from src.api.schemas.stateless_api import MethodResult, TriageFlag
from src.api.schemas.weighted_valuation import WeightedValuationResult
from src.domain.omni_calc_coordinator import calculate_weighted_average
from src.domain.valuation_contract import METHOD_KEY_ALIASES


class LoggerLike(Protocol):
    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class StatelessHeadlineState:
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    enterprise_value_low: Decimal | None
    enterprise_value_mid: Decimal | None
    enterprise_value_high: Decimal | None
    recommended_asking: Decimal
    recommended_multiple: Decimal | None
    multiples_results: dict[str, object] | None
    methodology_used: str
    methodology_selection_reason: str | None
    resolved_method_key: str | None = None


PURE_EQUITY_METHOD_KEYS = frozenset(
    {
        "startup_valuation",
        "fiscal_4x",
        "liquidation_analysis",
        "adjusted_nav",
    }
)


def promote_saas_validation_flags(
    *,
    valuation_results: Mapping[str, MethodResult],
    triage_flags: list[TriageFlag],
    logger: LoggerLike,
) -> None:
    """Promote ARR method validation flags to stateless triage flags."""
    for validation_flag in _arr_validation_flags(valuation_results):
        try:
            triage_flags.append(_saas_triage_flag(validation_flag))
        except Exception as exc:
            logger.warning(
                "Could not promote SaaS validation flag to TriageFlag",
                extra={"flag": validation_flag, "error": str(exc)},
            )


def _arr_validation_flags(valuation_results: Mapping[str, MethodResult]) -> list[object]:
    arr_method_result = valuation_results.get("arr_multiple")
    if arr_method_result is None or arr_method_result.details is None:
        return []

    validation_flags = arr_method_result.details.get("validation_flags") or []
    if not isinstance(validation_flags, list):
        return []
    return validation_flags


def _saas_triage_flag(validation_flag: object) -> TriageFlag:
    if not isinstance(validation_flag, dict):
        raise TypeError("validation flag must be a mapping")
    return TriageFlag(
        field=str(validation_flag.get("field") or "saas"),
        issue=str(validation_flag.get("issue") or "saas_validation"),
        severity=str(validation_flag.get("severity") or "warning"),
        value=validation_flag.get("value"),
        benchmark=validation_flag.get("benchmark"),
    )


def apply_startup_headline_override(
    *,
    selected_method: object,
    valuation_results: Mapping[str, MethodResult],
    headline_state: StatelessHeadlineState,
) -> StatelessHeadlineState:
    """Override the response headline with the standalone startup valuation when selected."""
    if selected_method != "startup_valuation":
        return headline_state

    startup_method = valuation_results.get("startup_valuation")
    if not startup_method or not startup_method.available or startup_method.value is None:
        return headline_state

    details = startup_method.details or {}
    canonical = details.get("canonical") if isinstance(details.get("canonical"), dict) else {}
    startup_low = _decimal_or_none(
        canonical.get("pre_money_low")
        if canonical.get("pre_money_low") is not None
        else details.get("equity_value_low")
    )
    startup_high = _decimal_or_none(
        canonical.get("pre_money_high")
        if canonical.get("pre_money_high") is not None
        else details.get("equity_value_high")
    )
    equity_value_mid = startup_method.value
    if startup_low is not None and startup_high is not None and startup_low > 0:
        equity_value_low = startup_low
        equity_value_high = startup_high
    else:
        equity_value_low = equity_value_mid
        equity_value_high = equity_value_mid

    return StatelessHeadlineState(
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
        # Startup is a pre-money equity premise. There is no independently
        # calculated enterprise-value band, so preserve explicit non-applicability.
        enterprise_value_low=None,
        enterprise_value_mid=None,
        enterprise_value_high=None,
        recommended_asking=equity_value_mid,
        recommended_multiple=None,
        multiples_results=None,
        methodology_used="STARTUP_VALUATION",
        methodology_selection_reason=(
            str(details.get("narrative"))
            if details.get("narrative")
            else headline_state.methodology_selection_reason
        ),
        resolved_method_key="startup_valuation",
    )


_MARKET_METHOD_KEYS = {
    "upswitch_adaptive",
    "ebitda_multiple",
    "omzet_multiple",
    "sde_multiple",
    "arr_multiple",
}

_METHODOLOGY_BY_METHOD_KEY = {
    "upswitch_adaptive": "UPSWITCH_ADAPTIVE",
    "ebitda_multiple": "EBITDA_MULTIPLE",
    "omzet_multiple": "OMZET_MULTIPLE",
    "sde_multiple": "SDE_MULTIPLE",
    "arr_multiple": "ARR_MULTIPLE",
    "dcf": "DCF",
    "adjusted_nav": "ADJUSTED_NAV",
    "real_estate_yield": "REAL_ESTATE_YIELD",
    "fiscal_4x": "FISCAL_4X",
    "liquidation_analysis": "LIQUIDATION_ANALYSIS",
    "startup_valuation": "STARTUP_VALUATION",
}


def apply_selected_method_headline_override(
    *,
    selected_method: object,
    user_weights: object,
    valuation_results: Mapping[str, MethodResult],
    headline_state: StatelessHeadlineState,
    triage_flags: list[TriageFlag],
) -> StatelessHeadlineState:
    """Promote one eligible canonical method, with an explicit fallback.

    ``user_weights`` is the more specific advisor instruction and therefore
    deliberately supersedes ``selected_method``. An unavailable selection is
    never silently ignored: it emits a qualification and promotes the first
    eligible supporting method already calculated from the same evidence.
    """
    selected = str(selected_method or "").strip()
    if not selected or user_weights:
        return headline_state

    method = valuation_results.get(selected)
    if method is not None and method.available and method.value is not None:
        return _promote_method_result(
            method_key=selected,
            method=method,
            headline_state=headline_state,
            selection_reason=f"Selected eligible {selected} method is the canonical headline.",
        )

    unavailable_reason = (
        method.unavailable_reason
        if method is not None and method.unavailable_reason
        else "method was not calculated with the available evidence"
    )
    triage_flags.append(
        TriageFlag(
            field="selected_method",
            issue="selected_method_unavailable",
            severity="warning",
            value={"method_key": selected, "reason": unavailable_reason},
        )
    )
    fallback_key = _first_eligible_fallback_method(
        selected_method=selected,
        valuation_results=valuation_results,
        headline_state=headline_state,
    )
    if fallback_key is None:
        return headline_state

    fallback = valuation_results[fallback_key]
    triage_flags.append(
        TriageFlag(
            field="selected_method",
            issue="selected_method_fallback_applied",
            severity="warning",
            value={
                "requested_method_key": selected,
                "resolved_method_key": fallback_key,
                "reason": unavailable_reason,
            },
        )
    )
    return _promote_method_result(
        method_key=fallback_key,
        method=fallback,
        headline_state=headline_state,
        selection_reason=(
            f"Selected {selected} was unavailable ({unavailable_reason}); "
            f"eligible {fallback_key} was applied as the best-effort fallback."
        ),
    )


def _first_eligible_fallback_method(
    *,
    selected_method: str,
    valuation_results: Mapping[str, MethodResult],
    headline_state: StatelessHeadlineState,
) -> str | None:
    preferred: list[str] = []
    methodology = headline_state.methodology_used.upper()
    if methodology == "DCF":
        preferred.append("dcf")
    elif methodology in {"ASSET_BASED", "ADJUSTED_NAV"}:
        preferred.append("adjusted_nav")
    preferred.extend(
        [
            "upswitch_adaptive",
            "ebitda_multiple",
            "omzet_multiple",
            "dcf",
            "adjusted_nav",
            "real_estate_yield",
            "fiscal_4x",
            "liquidation_analysis",
        ]
    )
    for method_key in dict.fromkeys(preferred):
        if method_key == selected_method:
            continue
        method = valuation_results.get(method_key)
        if method is not None and method.available and method.value is not None:
            return method_key
    return None


def _promote_method_result(
    *,
    method_key: str,
    method: MethodResult,
    headline_state: StatelessHeadlineState,
    selection_reason: str,
) -> StatelessHeadlineState:
    if (
        method_key == "dcf"
        and method.value_low is None
        and method.value_high is None
        and headline_state.methodology_used.upper() == "DCF"
    ):
        # The DCF MethodResult carries the reconciled midpoint; its sensitivity
        # range is emitted by the canonical DCF headline synthesis. With a
        # selected 100% DCF route that range belongs to the same method and is
        # preferable to manufacturing a point band.
        equity_low, equity_mid, equity_high = (
            headline_state.equity_value_low,
            _coalesce_decimal(_decimal_or_none(method.value), headline_state.equity_value_mid),
            headline_state.equity_value_high,
        )
    else:
        equity_low, equity_mid, equity_high = _method_equity_range(method_key, method)
    enterprise_low, enterprise_mid, enterprise_high = _method_enterprise_range(
        method_key,
        method,
        headline_state=headline_state,
    )
    return StatelessHeadlineState(
        equity_value_low=equity_low,
        equity_value_mid=equity_mid,
        equity_value_high=equity_high,
        enterprise_value_low=enterprise_low,
        enterprise_value_mid=enterprise_mid,
        enterprise_value_high=enterprise_high,
        recommended_asking=equity_mid,
        recommended_multiple=method.multiple_used,
        multiples_results=(
            headline_state.multiples_results if method_key in _MARKET_METHOD_KEYS else None
        ),
        methodology_used=_METHODOLOGY_BY_METHOD_KEY[method_key],
        methodology_selection_reason=selection_reason,
        resolved_method_key=method_key,
    )


def _method_equity_range(
    method_key: str,
    method: MethodResult,
) -> tuple[Decimal, Decimal, Decimal]:
    mid = _coalesce_decimal(_decimal_or_none(method.value), Decimal("0"))
    details = method.details if isinstance(method.details, Mapping) else {}
    low = _decimal_or_none(method.value_low)
    high = _decimal_or_none(method.value_high)

    if method_key == "startup_valuation":
        canonical = details.get("canonical")
        canonical = canonical if isinstance(canonical, Mapping) else {}
        low = _coalesce_decimal(_decimal_or_none(canonical.get("pre_money_low")), low)
        high = _coalesce_decimal(_decimal_or_none(canonical.get("pre_money_high")), high)
    elif method_key == "liquidation_analysis":
        orderly = details.get("orderly")
        orderly = orderly if isinstance(orderly, Mapping) else {}
        low = _coalesce_decimal(_decimal_or_none(orderly.get("value_low")), low)
        high = _coalesce_decimal(_decimal_or_none(orderly.get("value_high")), high)

    low = _coalesce_decimal(low, _decimal_or_none(details.get("equity_range_low")), mid)
    high = _coalesce_decimal(high, _decimal_or_none(details.get("equity_range_high")), mid)
    low = max(Decimal("0"), min(low, mid, high))
    high = max(low, mid, high)
    return low, max(Decimal("0"), mid), high


def _method_enterprise_range(
    method_key: str,
    method: MethodResult,
    *,
    headline_state: StatelessHeadlineState,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    # These methods begin and end on shareholder equity. Even if a legacy
    # method-details payload contains a compatibility EV-looking scalar, it is
    # not an independently calculated enterprise value and must not be surfaced.
    if method_key in PURE_EQUITY_METHOD_KEYS:
        return None, None, None

    if method_key in {"dcf", "upswitch_adaptive"} and all(
        value is not None
        for value in (
            headline_state.enterprise_value_low,
            headline_state.enterprise_value_mid,
            headline_state.enterprise_value_high,
        )
    ):
        return (
            headline_state.enterprise_value_low,
            headline_state.enterprise_value_mid,
            headline_state.enterprise_value_high,
        )

    details = method.details if isinstance(method.details, Mapping) else {}
    mid = _coalesce_decimal(
        _decimal_or_none(details.get("enterprise_value_mid")),
        _decimal_or_none(details.get("enterprise_value")),
    )
    if mid is None:
        return None, None, None
    low = _decimal_or_none(details.get("enterprise_value_low"))
    high = _decimal_or_none(details.get("enterprise_value_high"))
    if low is None or high is None:
        # A disclosed EV point is still authoritative even where the method's
        # uncertainty engine only emitted an equity range (notably NAV/ARR).
        point = max(Decimal("0"), mid)
        return point, point, point
    low = max(Decimal("0"), min(low, mid, high))
    high = max(low, mid, high)
    return low, max(Decimal("0"), mid), high


def _coalesce_decimal(*values: Decimal | None) -> Decimal | None:
    return next((value for value in values if value is not None), None)


def build_fiscal_4x_anchor(*, ebitda: float, country_code: object) -> Decimal | None:
    """Build the Belgian fiscal 4x EBITDA reference anchor."""
    if ebitda > 0 and country_code == "BE":
        return Decimal(str(round(ebitda * 4, 2)))
    return None


def build_weighted_valuation_result(
    *,
    valuation_results: dict[str, MethodResult],
    user_weights: object,
    user_weight_justification: object,
    triage_flags: list[TriageFlag],
    logger: LoggerLike,
    value_basis: str = "equity_value",
    strict_user_weights: bool = False,
    renormalize_unavailable_weights: bool = False,
    require_positive_values: bool = False,
) -> WeightedValuationResult | None:
    """Calculate advisor-configured weighted valuation and surface failures as flags."""
    if not user_weights or not isinstance(user_weights, dict) or len(user_weights) == 0:
        return None
    try:
        canonical_weights: dict[str, float] = {}
        for raw_key, raw_weight in user_weights.items():
            canonical_key = METHOD_KEY_ALIASES.get(str(raw_key), str(raw_key))
            canonical_weights[canonical_key] = canonical_weights.get(canonical_key, 0.0) + float(
                raw_weight
            )

        # Validate the advisor's original instruction before best-effort
        # eligibility filtering. Filtering must never make malformed weights
        # appear valid.
        original_total = sum(canonical_weights.values())
        if abs(original_total - 1.0) > 0.02:
            raise ValueError(
                f"Gewichten moeten optellen tot 100% (huidige som: {original_total * 100:.1f}%)."
            )

        eligible_weights: dict[str, float] = {}
        excluded: list[dict[str, object]] = []
        for method_key, weight in canonical_weights.items():
            if weight <= 0:
                continue
            method = valuation_results.get(method_key)
            selected_value = (
                method.enterprise_value
                if method is not None and value_basis == "enterprise_value"
                else method.value if method is not None else None
            )
            selected_value_is_eligible = selected_value is not None and (
                not require_positive_values or selected_value > 0
            )
            if method is not None and method.available and selected_value_is_eligible:
                eligible_weights[method_key] = weight
                continue
            excluded.append(
                {
                    "method_key": method_key,
                    "original_weight": weight,
                    "reason": (
                        method.unavailable_reason
                        if method is not None and method.unavailable_reason
                        else "method was not calculated with the available evidence"
                    ),
                }
            )

        eligible_total = sum(eligible_weights.values())
        if strict_user_weights and excluded and not renormalize_unavailable_weights:
            triage_flags.append(
                TriageFlag(
                    field="user_weights",
                    issue="strict_weighted_method_unavailable",
                    severity="error",
                    value={"excluded_methods": excluded},
                )
            )
            return None
        if eligible_total <= 0:
            triage_flags.append(
                TriageFlag(
                    field="user_weights",
                    issue="no_eligible_methods_for_weighted_synthesis",
                    severity="warning",
                    value={"excluded_methods": excluded},
                )
            )
            return None

        normalized_weights = {
            method_key: weight / eligible_total
            for method_key, weight in eligible_weights.items()
        }
        excluded_weight = Decimal(str(sum(float(row["original_weight"]) for row in excluded)))
        result = calculate_weighted_average(
            methods=valuation_results,
            weights=normalized_weights,
            justification=(
                str(user_weight_justification) if user_weight_justification is not None else None
            ),
            value_basis=value_basis,
        )
        if excluded:
            inflation = min(
                Decimal("2"),
                Decimal("1") / max(Decimal("0.01"), Decimal(str(eligible_total))),
            )
            triage_flags.append(
                TriageFlag(
                    field="user_weights",
                    issue="ineligible_methods_excluded_weights_renormalized",
                    severity="warning",
                    value={
                        "excluded_methods": excluded,
                        "resolved_weights": normalized_weights,
                        "uncertainty_inflation_factor": str(inflation),
                        "policy_version": "eligible_method_renormalization.v1",
                    },
                )
            )
            return result.model_copy(
                update={
                    "weights_renormalized": True,
                    "excluded_methods": excluded,
                    "excluded_original_weight": excluded_weight,
                    "uncertainty_inflation_factor": inflation,
                }
            )
        return result
    except ValueError as exc:
        logger.warning("Weighted average failed in stateless route: %s", exc)
        triage_flags.append(
            TriageFlag(
                field="user_weights",
                issue="synthesis_failed",
                severity="warning",
                value=str(exc),
            )
        )
        return None


def calculate_stateless_status(triage_flags: list[TriageFlag]) -> str:
    """Derive the stateless calculation status from triage severity."""
    if any(flag.severity == "error" for flag in triage_flags):
        return "ERROR"
    if any(flag.severity == "warning" for flag in triage_flags):
        return "WARNINGS"
    return "SUCCESS"


def build_financial_metrics(
    *,
    current_year,
    ebitda_margin: float,
    revenue_growth: float,
    ownership_percentage: Decimal,
    ownership_multiplier: Decimal,
    confidence_score: int,
    confidence_level: str,
    reported_ebitda: Decimal,
    normalized_ebitda: Decimal,
    valuation_basis_ebitda: Decimal,
    valuation_basis_mode: str,
    revenue_growth_evidence: dict[str, object] | None = None,
    revenue_cagr_3y_evidence: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build the response financial metrics block from canonical calculated values."""
    metrics: dict[str, object] = {
        "revenue": float(current_year.revenue),
        "revenue_source": current_year.revenue_source,
        "ebitda": float(valuation_basis_ebitda),
        "reported_ebitda": float(reported_ebitda),
        "normalized_ebitda": float(normalized_ebitda),
        "valuation_basis_ebitda": float(valuation_basis_ebitda),
        "valuation_basis_mode": valuation_basis_mode,
        "ebitda_margin": ebitda_margin,
        "revenue_growth": float(revenue_growth),
        "shares_for_sale": float(ownership_percentage),
        "ownership_multiplier": float(ownership_multiplier),
        "financial_health_score": confidence_score,
        "financial_health_description": f"Financial health is {confidence_level.lower()}",
    }
    if revenue_growth_evidence is not None:
        metrics["revenue_growth"] = revenue_growth_evidence.get("rate")
        metrics["revenue_growth_evidence"] = revenue_growth_evidence
    if revenue_cagr_3y_evidence is not None:
        metrics["revenue_cagr_3y"] = revenue_cagr_3y_evidence.get("rate")
        metrics["revenue_cagr_3y_evidence"] = revenue_cagr_3y_evidence
    # Report generation is a separate stateless call. Preserve supplied balance
    # fields here so `/generate-report` can distinguish a real EV→equity bridge
    # from an apparent missing-balance phantom without inventing zeroes.
    for key in (
        "ebit",
        "depreciation",
        "cash",
        "inventory",
        "total_debt",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "current_assets",
        "current_liabilities",
        "accounts_receivable",
        "accounts_payable",
    ):
        value = getattr(current_year, key, None)
        if value is not None:
            metrics[key] = float(value)
    if "total_equity" in metrics:
        metrics["equity"] = metrics["total_equity"]
    return metrics


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
