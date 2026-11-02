"""
OmniCalcCoordinator - Calculate all valuation methods simultaneously.

Runs every supported method against the same normalized inputs and returns
a Dict[str, MethodResult] that the frontend can switch between instantly.

Methods that cannot compute (e.g. DCF with negative EBITDA, SDE for large
firms) return available=False with a reason string.

Three distinct weighting concepts exist across the ValuationIQ codebase — they
are isolated from each other but share the word "weights", so beware of
conflating them:

1. **User synthesis weights** — ``calculate_weighted_average()`` in this file.
   Accountant-configured blend of the 8 SME method equities for the PDF
   synthesis page.  Weights must sum to 100 %.  The 9th method
   (``startup_valuation``) is a standalone engine that triangulates four
   startup-native methods internally and is *not* blendable with SME methods
   here — it produces its own dedicated report flow.

2. **Hybrid methodology weights** — ``HybridWeightCalculator`` /
   ``extract_methodology_weights()`` in the pipeline.  DCF vs multiples split
   (e.g. 60/40) used to compute the ``upswitch_adaptive`` headline value.
   Not user-facing.

3. **Multiples engine EV composition** — ``ValuationCalculationCoordinator``.
   Fixed 60/30/10 blend of EV/EBITDA, EV/Revenue, P/E within the multiples
   domain.  Internal to the pipeline.
"""

import math
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Callable, Dict, List, Literal, Optional

from src.api.schemas.stateless_api import (
    MethodResult,
    WeightedMethodContribution,
    WeightedValuationResult,
)
from src.api.schemas.stateless_common import RealEstateYieldEvidenceContract
from src.domain.asset_based_support import normalize_business_model
from src.domain.financial_arithmetic import decimal_number, money
from src.domain.methods import (
    calculate_adaptive_result,
    calculate_adjusted_nav_result,
    calculate_arr_result,
    calculate_dcf_result,
    calculate_ebitda_result,
    calculate_fiscal_4x_result,
    calculate_liquidation_result,
    calculate_real_estate_yield_result,
    calculate_revenue_result,
    calculate_sde_result,
    calculate_startup_result,
)
from src.domain.methods._shared import finite_float as _finite_float
from src.domain.methods._shared import (
    saas_adjustment_from_artifact as _saas_adjustment_from_artifact,
)
from src.domain.saas_valuation_adjuster import SaasAdjustmentResult, compute_saas_adjustment
from src.domain.startup_valuation import (
    LifecycleStageTriage,
    StartupInputs,
    apply_startup_methodology_gate,
    resolve_startup_methodology_override_provenance,
)
from src.domain.startup_valuation.schemas import CapTableSummary
from src.domain.valuation_contract import METHOD_KEY_ALIASES
from src.utils.adaptive_input_helpers import is_saas_context
from src.utils.decimal_helpers import optional_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _safe_method(
    fn: Callable[[], MethodResult],
    *,
    label: str,
    fallback_reason: str,
) -> MethodResult:
    """Run *fn* and return its ``MethodResult``.  On any exception, log a
    warning and return ``MethodResult(available=False)`` so a single method
    failure never crashes the entire multi-method calculation.
    """
    try:
        return fn()
    except Exception as exc:
        logger.error(
            "%s calculation failed unexpectedly: %s",
            label,
            exc,
            exc_info=True,
            extra={"method_label": label, "error_type": type(exc).__name__},
        )
        return MethodResult(
            value=None,
            label=label,
            available=False,
            unavailable_reason=f"{fallback_reason} ({type(exc).__name__})",
        )


def _finite_optional_float(value: Optional[float]) -> Optional[float]:
    return _finite_float(value) if value is not None else None


def _saas_adjustment_has_diagnostics(saas_adjustment: SaasAdjustmentResult) -> bool:
    return saas_adjustment.eligibility is not None or bool(
        saas_adjustment.validation and saas_adjustment.validation.flags
    )


def _resolve_saas_adjustment(
    *,
    revenue: float,
    recurring_revenue_percentage: Optional[Decimal],
    business_context: Optional[Mapping[str, object]],
    country_code: str,
    business_type_id: Optional[str],
    business_model: str,
    industry: str,
    saas_analysis: Optional[Mapping[str, object]],
) -> Optional[SaasAdjustmentResult]:
    saas_adjustment = _saas_adjustment_from_artifact(saas_analysis)
    if saas_adjustment is not None:
        return saas_adjustment

    if not is_saas_context(
        business_context=business_context,
        business_type_id=business_type_id,
        business_model=business_model,
        industry=industry,
    ):
        return None

    revenue_dec = optional_decimal(revenue)
    computed_adjustment = compute_saas_adjustment(
        revenue=revenue_dec if revenue_dec is not None else Decimal("0"),
        recurring_revenue_percentage=recurring_revenue_percentage,
        business_context=business_context,
        country_code=country_code,
        business_type_id=business_type_id,
    )
    if not computed_adjustment.is_saas and not _saas_adjustment_has_diagnostics(
        computed_adjustment
    ):
        return None
    return computed_adjustment


def _is_arr_method_eligible(saas_adjustment: Optional[SaasAdjustmentResult]) -> bool:
    return bool(
        saas_adjustment is not None
        and saas_adjustment.is_eligible
        and saas_adjustment.arr_multiple is not None
        and saas_adjustment.arr is not None
        and saas_adjustment.arr > 0
    )


def _arr_value_or_zero(saas_adjustment: Optional[SaasAdjustmentResult]) -> float:
    if not saas_adjustment or not saas_adjustment.arr:
        return 0.0
    return float(saas_adjustment.arr)


def _arr_multiple_or_zero(saas_adjustment: Optional[SaasAdjustmentResult]) -> float:
    if not saas_adjustment or not saas_adjustment.arr_multiple:
        return 0.0
    return float(saas_adjustment.arr_multiple)


def _calculate_arr_method_result(
    *,
    saas_adjustment: Optional[SaasAdjustmentResult],
    total_adjustment: float,
    total_debt: float,
    cash: float,
    ownership_multiplier: float,
    nwc_adjustment: float,
    cap_table: Optional[CapTableSummary],
    investment_amount_sought: Optional[Decimal],
) -> MethodResult:
    if _is_arr_method_eligible(saas_adjustment):
        return _safe_method(
            lambda: calculate_arr_result(
                arr=saas_adjustment.arr,
                arr_multiple=saas_adjustment.arr_multiple,
                total_adjustment=total_adjustment,
                total_debt=total_debt,
                cash=cash,
                ownership_multiplier=ownership_multiplier,
                saas_adjustment=saas_adjustment,
                nwc_adjustment=nwc_adjustment,
                cap_table=cap_table,
                investment_amount_sought=investment_amount_sought,
            ),
            label="ARR multiple",
            fallback_reason="ARR multiple-berekening mislukt.",
        )

    # Even when ineligible we still call calculate_arr_result to get
    # a fully-populated MethodResult with eligibility + validation
    # diagnostics in `details`. No silent string fallback.
    # No cap-table simulator on the ineligible branch — the method
    # short-circuits before computing equity, so there's no
    # pre-money anchor to dilute against.
    return _safe_method(
        lambda: calculate_arr_result(
            arr=_arr_value_or_zero(saas_adjustment),
            arr_multiple=_arr_multiple_or_zero(saas_adjustment),
            total_adjustment=total_adjustment,
            total_debt=total_debt,
            cash=cash,
            ownership_multiplier=ownership_multiplier,
            saas_adjustment=saas_adjustment,
            nwc_adjustment=nwc_adjustment,
        ),
        label="ARR multiple",
        fallback_reason="ARR multiple-berekening mislukt.",
    )


def _sde_owner_context(business_context: Optional[Mapping[str, object]]) -> tuple[int, str]:
    context = business_context or {}
    return int(context.get("number_of_owners") or 1), str(context.get("owner_role") or "working")


def calculate_all_methods(
    *,
    ebitda: float,
    revenue: float,
    ev_ebitda_multiple: float,
    adaptive_multiple_used: Optional[float] = None,
    p25_multiple: float,
    p75_multiple: float,
    total_adjustment: float,
    total_debt: float,
    cash: float,
    equity_value_mid: Decimal,
    dcf_results: Optional[Dict[str, Any]],
    dcf_exclusion_reason: Optional[str],
    calibration: Any,
    revenue_growth: float,
    owner_dependency: Any,
    industry: str,
    recurring_revenue_percentage: Optional[Decimal] = None,
    equity_value_low: Optional[Decimal] = None,
    equity_value_high: Optional[Decimal] = None,
    ownership_multiplier: Decimal = Decimal("1"),
    country_code: str = "BE",
    company_name: str = "Unknown Company",
    business_model: str = "other",
    founding_year: Optional[int] = None,
    reporting_year: Optional[int] = None,
    balance_sheet: Optional[Dict[str, Any]] = None,
    business_context: Optional[Dict[str, Any]] = None,
    business_type_id: Optional[str] = None,
    primary_basis: Literal["hybrid", "asset_based"] = "hybrid",
    saas_analysis: Optional[Dict[str, Any]] = None,
    owner_salary_addback: Optional[float] = None,
    sde_ebitda: Optional[float] = None,
    sde_revenue: Optional[float] = None,
    nwc_adjustment: float = 0.0,
    methodology_justification: Optional[str] = None,
    fiscal_ebitda: Optional[float] = None,
    startup_inputs: Optional[StartupInputs] = None,
    lifecycle_stage_triage: Optional[LifecycleStageTriage] = None,
    cap_table: Optional[CapTableSummary] = None,
    investment_amount_sought: Optional[Decimal] = None,
    # Liquidation Phase 2-4 advisor inputs. A single dict-shaped passthrough
    # so the orchestrator surface stays narrow; the keys map 1:1 onto the
    # optional kwargs of `calculate_liquidation_result`. None means "engine
    # uses jurisdiction defaults" — the report flags estimated buckets.
    # See `apps/valuation-iq/src/domain/liquidation/scenarios.py` for the
    # full key contract (liability_buckets, paid_up_capital, headcount, …).
    liquidation_inputs: Optional[Dict[str, Any]] = None,
    real_estate_yield_evidence: Optional[RealEstateYieldEvidenceContract] = None,
    revenue_multiple_input: Decimal | None = None,
    require_revenue_basis: bool = False,
    revenue_basis: str | None = None,
    cohort_revenue_basis: str | None = None,
    enterprise_value_mid: Decimal | None = None,
    enterprise_value_low: Decimal | None = None,
    enterprise_value_high: Decimal | None = None,
) -> Dict[str, MethodResult]:
    """Return MethodResult for every supported valuation method.

    Thin dispatcher — each method's logic lives in its own module under
    ``src.domain.methods``.  Fault isolation via ``_safe_method`` ensures
    one failure never crashes another.
    """
    # Monetary values and observed zero bounds reach each method unchanged.
    # A malformed bridge is an invalid request, never a zero-valued estimate.
    for field, value in (
        ("risk adjustment", total_adjustment),
        ("financial debt", total_debt),
        ("cash", cash),
        ("NWC adjustment", nwc_adjustment),
    ):
        decimal_number(value, field)
    revenue_growth = _finite_float(revenue_growth)
    adaptive_multiple_used = _finite_optional_float(adaptive_multiple_used)

    results: Dict[str, MethodResult] = {}
    normalized_business_model = normalize_business_model(business_model).value

    saas_adjustment = _resolve_saas_adjustment(
        revenue=revenue,
        recurring_revenue_percentage=recurring_revenue_percentage,
        business_context=business_context,
        country_code=country_code,
        business_type_id=business_type_id,
        business_model=normalized_business_model,
        industry=industry,
        saas_analysis=saas_analysis,
    )

    om = decimal_number(ownership_multiplier, "ownership")

    # 1. Adaptive
    results["upswitch_adaptive"] = _safe_method(
        lambda: calculate_adaptive_result(
            primary_basis=primary_basis,
            equity_value_mid=equity_value_mid,
            enterprise_value_mid=enterprise_value_mid,
            enterprise_value_low=enterprise_value_low,
            enterprise_value_high=enterprise_value_high,
            adaptive_multiple_used=adaptive_multiple_used,
            ev_ebitda_multiple=ev_ebitda_multiple,
            equity_value_low=equity_value_low,
            equity_value_high=equity_value_high,
            saas_adjustment=saas_adjustment,
            methodology_justification=methodology_justification,
        ),
        label="UpSwitch Adaptive",
        fallback_reason="Berekening UpSwitch Adaptive mislukt.",
    )

    # 2. EBITDA multiple
    results["ebitda_multiple"] = _safe_method(
        lambda: calculate_ebitda_result(
            ebitda=ebitda,
            ev_ebitda_multiple=ev_ebitda_multiple,
            p25_multiple=p25_multiple,
            p75_multiple=p75_multiple,
            total_adjustment=total_adjustment,
            total_debt=total_debt,
            cash=cash,
            ownership_multiplier=om,
            nwc_adjustment=nwc_adjustment,
            saas_adjustment=saas_adjustment,
        ),
        label="EBITDA-multiple",
        fallback_reason="Berekening EBITDA-multiple mislukt.",
    )

    # 3. DCF
    results["dcf"] = _safe_method(
        lambda: calculate_dcf_result(
            dcf_results=dcf_results,
            dcf_exclusion_reason=dcf_exclusion_reason,
            total_debt=total_debt,
            cash=cash,
            ownership_multiplier=om,
            nwc_adjustment=nwc_adjustment,
        ),
        label="Discounted Cash Flow (DCF)",
        fallback_reason="DCF-berekening mislukt.",
    )

    # 4. SDE (industry-specific multiples from BizBuySell/Pepperdine)
    sde_num_owners, sde_owner_role = _sde_owner_context(business_context)
    results["sde_multiple"] = _safe_method(
        lambda: calculate_sde_result(
            ebitda=ebitda if sde_ebitda is None else sde_ebitda,
            revenue=revenue if sde_revenue is None else sde_revenue,
            total_adjustment=total_adjustment,
            total_debt=total_debt,
            cash=cash,
            owner_dependency=owner_dependency,
            ownership_multiplier=om,
            owner_salary_addback=owner_salary_addback,
            nwc_adjustment=nwc_adjustment,
            business_type_id=business_type_id,
            industry=industry,
            country_code=country_code,
            num_owners=sde_num_owners,
            owner_role=sde_owner_role,
        ),
        label="SDE-multiple",
        fallback_reason="SDE-berekening mislukt.",
    )

    # 5. Revenue (Omzet) multiple
    results["omzet_multiple"] = _safe_method(
        lambda: calculate_revenue_result(
            revenue=revenue_multiple_input if revenue_multiple_input is not None else revenue,
            require_revenue_basis=require_revenue_basis,
            revenue_basis=revenue_basis,
            cohort_revenue_basis=cohort_revenue_basis,
            total_adjustment=total_adjustment,
            total_debt=total_debt,
            cash=cash,
            calibration=calibration,
            ownership_multiplier=om,
            nwc_adjustment=nwc_adjustment,
        ),
        label="Omzetmultiple",
        fallback_reason="Omzetmultiple-berekening mislukt.",
    )

    # 6. ARR (SaaS only)
    results["arr_multiple"] = _calculate_arr_method_result(
        saas_adjustment=saas_adjustment,
        total_adjustment=total_adjustment,
        total_debt=total_debt,
        cash=cash,
        ownership_multiplier=om,
        nwc_adjustment=nwc_adjustment,
        cap_table=cap_table,
        investment_amount_sought=investment_amount_sought,
    )

    # 7. Adjusted NAV
    results["adjusted_nav"] = _safe_method(
        lambda: calculate_adjusted_nav_result(
            company_name=company_name,
            industry=industry,
            business_model=normalized_business_model,
            founding_year=founding_year,
            reporting_year=reporting_year,
            revenue=revenue,
            ebitda=ebitda,
            ownership_multiplier=ownership_multiplier,
            country_code=country_code,
            balance_sheet=balance_sheet,
            business_context=business_context,
        ),
        label="Gecorrigeerde NAV (Intrinsieke Waarde)",
        fallback_reason="Adjusted NAV-berekening mislukt.",
    )

    # 8. Canonical property income capitalisation.  This deliberately receives
    # only the signed evidence contract; legacy property-type cap-rate defaults
    # and inferred NOI never cross this boundary.
    results["real_estate_yield"] = _safe_method(
        lambda: calculate_real_estate_yield_result(
            evidence=real_estate_yield_evidence,
            ownership_multiplier=ownership_multiplier,
        ),
        label="Real-estate yield (income capitalisation)",
        fallback_reason="Canonical real-estate yield calculation failed.",
    )

    # 9. Fiscal 4x EBITDA (Belgium only)
    _fiscal_ebitda = fiscal_ebitda if fiscal_ebitda is not None else ebitda
    results["fiscal_4x"] = _safe_method(
        lambda: calculate_fiscal_4x_result(
            country_code=country_code,
            ebitda=_fiscal_ebitda,
            balance_sheet=balance_sheet,
            ownership_multiplier=ownership_multiplier,
        ),
        label="Fiscale Vuistregel (4× EBITDA)",
        fallback_reason="Berekening Fiscale Vuistregel mislukt.",
    )

    # 10. Startup Valuation (qualitative + venture, non-combinable)
    results["startup_valuation"] = _safe_method(
        lambda: calculate_startup_result(startup_inputs=startup_inputs),
        label="Startup Valuation",
        fallback_reason="Berekening Startup Valuation mislukt.",
    )

    # 11. Liquidation Analysis (downside lens, orderly + forced).
    # Surfaces the AssetBasedEngine orderly+forced branches plus the
    # full Phase 1-4 depth (IVS 104 premise, Altman Z'' distress,
    # 12-class realisation schedule, BE/NL insolvency cascade, tax
    # leakage, bottom-up wind-down, PV-discount, sensitivity, premise
    # reconciliation, IVS+USPAP+IFRS-13 disclosure). Not blended with
    # going-concern methods — separate premise of value (IVS 104 §80).
    # Advisor-grade inputs flow in via `liquidation_inputs`; keys map
    # 1:1 to the wrapper's optional kwargs (None → engine defaults).
    _liquidation_kwargs: Dict[str, Any] = dict(liquidation_inputs or {})
    results["liquidation_analysis"] = _safe_method(
        lambda: calculate_liquidation_result(
            company_name=company_name,
            industry=industry,
            business_model=normalized_business_model,
            founding_year=founding_year,
            reporting_year=reporting_year,
            revenue=revenue,
            ebitda=ebitda,
            ownership_multiplier=ownership_multiplier,
            country_code=country_code,
            balance_sheet=balance_sheet,
            **_liquidation_kwargs,
        ),
        label="Liquidatiewaarde (Geordende & Gedwongen)",
        fallback_reason="Berekening liquidatiewaarde mislukt.",
    )

    return apply_startup_methodology_gate(
        results,
        startup_inputs=startup_inputs,
        lifecycle_stage_triage=lifecycle_stage_triage,
        override_provenance=resolve_startup_methodology_override_provenance(business_context),
    )


def calculate_weighted_average(
    methods: Dict[str, MethodResult],
    weights: Dict[str, float],
    justification: Optional[str] = None,
    value_basis: str = "equity_value",
) -> WeightedValuationResult:
    """Blend multiple valuation methods using user-configured weights.

    Validates that every weighted method is available and that weights sum to 1.0.
    Returns a ``WeightedValuationResult`` with the blended equity value and
    per-method breakdown suitable for the PDF synthesis page.

    Raises ``ValueError`` with a Dutch-language message when a weight is
    assigned to a method that could not be computed.
    """

    WEIGHT_SUM_TOLERANCE = Decimal(".02")  # ±2 integer percent = 2/100, aligned with frontend

    normalized_weights: dict[str, Decimal] = {}
    for key, raw_weight in weights.items():
        canonical = METHOD_KEY_ALIASES.get(key, key)
        if canonical in normalized_weights:
            raise ValueError(f"duplicate method alias in synthesis weights: {canonical}")
        normalized_weights[canonical] = decimal_number(raw_weight, f"weight for {key}")
    normalized = normalized_weights

    for k, v in normalized.items():
        if not math.isfinite(v) or v < 0.0 or v > 1.0:
            raise ValueError(f"Gewicht voor '{k}' moet tussen 0% en 100% liggen (ontvangen: {v}).")

    weight_sum = sum(normalized.values())
    if abs(weight_sum - Decimal(1)) > WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            f"Gewichten moeten optellen tot 100% (huidige som: {weight_sum * 100:.1f}%)."
        )

    if weight_sum != 1.0 and weight_sum > 0:
        norm_factor = Decimal(1) / weight_sum
        normalized = {k: v * norm_factor for k, v in normalized.items()}

    if value_basis not in {"equity_value", "enterprise_value"}:
        raise ValueError("value_basis must be 'equity_value' or 'enterprise_value'.")

    contributions: List[WeightedMethodContribution] = []
    blended = Decimal("0")
    blended_equity = Decimal("0")
    blended_low = Decimal("0")
    blended_high = Decimal("0")

    for method_key, weight in normalized.items():
        if weight <= 0:
            continue

        method = methods.get(method_key)
        if method is None:
            raise ValueError(
                f"Kan geen gewicht toekennen aan '{method_key}': methode niet berekend."
            )
        equity_value = (
            method.equity_value
            if method.equity_value is not None
            else (method.value if method.value_basis == "equity_value" else None)
        )
        selected_value = (
            method.enterprise_value if value_basis == "enterprise_value" else equity_value
        )
        if not method.available or selected_value is None or equity_value is None:
            reason = method.unavailable_reason or "ontbrekende invoergegevens"
            raise ValueError(f"Kan geen gewicht toekennen aan {method.label}: {reason}")

        weight_dec = Decimal(str(weight))
        contribution = Decimal(str(selected_value)) * weight_dec
        blended += contribution
        blended_equity += Decimal(str(equity_value)) * weight_dec

        if value_basis == "enterprise_value":
            selected_low = (
                method.enterprise_value_low
                if method.enterprise_value_low is not None
                else method.enterprise_value
            )
            selected_high = (
                method.enterprise_value_high
                if method.enterprise_value_high is not None
                else method.enterprise_value
            )
        else:
            selected_low = next(
                (
                    v
                    for v in (method.equity_value_low, method.value_low, equity_value)
                    if v is not None
                )
            )
            selected_high = next(
                (
                    v
                    for v in (method.equity_value_high, method.value_high, equity_value)
                    if v is not None
                )
            )
        if (
            not decimal_number(selected_low)
            <= decimal_number(selected_value)
            <= decimal_number(selected_high)
        ):
            raise ValueError(
                f"Invalid valuation band for {method_key}: low <= base <= high is required"
            )
        blended_low += Decimal(str(selected_low)) * weight_dec
        blended_high += Decimal(str(selected_high)) * weight_dec

        contribution_payload: Dict[str, Any] = {
            "method_key": method_key,
            "label": method.label,
            "equity_value": equity_value,
            "equity_value_low": (
                method.equity_value_low if method.equity_value_low is not None else method.value_low
            ),
            "equity_value_high": (
                method.equity_value_high
                if method.equity_value_high is not None
                else method.value_high
            ),
            "enterprise_value": method.enterprise_value,
            "enterprise_value_low": method.enterprise_value_low,
            "enterprise_value_high": method.enterprise_value_high,
            "weight": weight,
            "weight_decimal": weight_dec,
            "weighted_contribution": money(contribution),
            "weighted_contribution_unrounded": contribution,
            "value_basis": value_basis,
        }
        bridge_payload = _method_bridge_provenance(method_key, method)
        if value_basis == "enterprise_value":
            bridge_payload.pop("value_basis", None)
        contribution_payload.update(bridge_payload)

        contributions.append(
            WeightedMethodContribution(
                **contribution_payload,
            )
        )

    blended = money(blended)
    blended_equity = money(blended_equity)
    blended_low = money(blended_low)
    blended_high = money(blended_high)

    logger.info(
        "Weighted average calculated",
        extra={
            "value_basis": value_basis,
            "num_methods": len(contributions),
            "weighted_method_count": len(normalized),
        },
    )

    return WeightedValuationResult(
        blended_equity_value=(blended if value_basis == "equity_value" else blended_equity),
        valuation_range_low=(blended_low if value_basis == "equity_value" else None),
        valuation_range_high=(blended_high if value_basis == "equity_value" else None),
        enterprise_value_low=(blended_low if value_basis == "enterprise_value" else None),
        enterprise_value_mid=(blended if value_basis == "enterprise_value" else None),
        enterprise_value_high=(blended_high if value_basis == "enterprise_value" else None),
        value_basis=value_basis,
        contributions=contributions,
        user_justification=justification,
    )


def _decimal_or_none(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _method_bridge_provenance(method_key: str, method: MethodResult) -> Dict[str, Any]:
    """Expose audited method-level bridges in weighted synthesis rows.

    APV tax shields are not a separate valuation method; they are a bridge
    inside the DCF leg. Carrying the fields here lets the report and Venus
    show why the weighted DCF value equals the customer-template APV result
    without creating a second DCF-like row that could be double-counted.
    """

    if method_key != "dcf" or not isinstance(method.details, dict):
        if isinstance(method.details, dict):
            value_basis = method.details.get("weighted_synthesis_value_basis")
            if value_basis == "net_engine":
                # BET-460: tag the row as net-basis so the report can render its
                # methodology label, but do NOT emit the gross→net reconciliation
                # magnitudes (value_before_bridge, and benchmark_reconciliation's
                # gross_method_value + net_engine_value). Together those disclose
                # the implied gross→net discount in the customer-facing
                # weighted_valuation payload. The reconciliation is already baked
                # into this row's equity_value, so nothing downstream needs the
                # raw gross figure — the synthesis page never renders it and the
                # cover/body cap is enforced by the reconciled equity value.
                return {"value_basis": "net_engine"}
        return {}

    tax_shield = _decimal_or_none(method.details.get("apv_tax_shield_value"))
    if tax_shield is None or tax_shield == 0:
        return {}

    payload: Dict[str, Any] = {
        "value_basis": "apv",
        "bridge_adjustment": tax_shield,
    }

    value_before_bridge = _decimal_or_none(method.details.get("dcf_equity_value_before_apv"))
    if value_before_bridge is not None:
        payload["value_before_bridge"] = value_before_bridge

    pct = _decimal_or_none(method.details.get("apv_tax_shield_pct_of_total"))
    if pct is not None:
        payload["bridge_adjustment_pct_of_total"] = pct

    convention = method.details.get("apv_discounting_convention")
    if isinstance(convention, str) and convention.strip():
        payload["discounting_convention"] = convention.strip()

    bridge_provenance = method.details.get("apv_bridge_provenance")
    if isinstance(bridge_provenance, dict):
        payload["bridge_provenance"] = dict(bridge_provenance)
    elif payload.get("discounting_convention") == "year_end":
        payload["bridge_provenance"] = {
            "basis": "explicit_tax_shield_schedule",
            "benchmark_style": "customer_template_apv",
            "customer_template_reconciliation": True,
            "discounting_convention": "year_end",
            "included_in_dcf_value": True,
            "separate_weighting_method": False,
            "double_counting_guard": (
                "APV tax shields are already included inside the DCF method value; "
                "do not add or weight APV as a separate valuation method."
            ),
        }

    benchmark_reconciliation = method.details.get("apv_benchmark_reconciliation")
    if isinstance(benchmark_reconciliation, dict):
        payload["benchmark_reconciliation"] = dict(benchmark_reconciliation)

    return payload
