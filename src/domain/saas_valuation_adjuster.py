from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.domain.saas_eligibility import (
    EligibilityThresholds,
    SaasEligibilityVerdict,
    evaluate_saas_eligibility,
)
from src.domain.saas_input_validation import SaasValidationReport, validate_saas_inputs
from src.utils.adaptive_input_helpers import (
    get_business_context_decimal,
    get_business_context_percent,
)
from src.utils.decimal_helpers import float_or_none


def _clamp(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return max(lower, min(upper, value))


_to_float = float_or_none


def _nrr_expansion_spread_points(
    nrr: Optional[Decimal], revenue_churn: Optional[Decimal]
) -> Optional[Decimal]:
    """NRR% − (100 − gross revenue churn %), in percentage points — same as Venus `computeNrrExpansionSpreadPct`."""
    if nrr is None or revenue_churn is None:
        return None
    return nrr * Decimal("100") - (Decimal("100") - revenue_churn * Decimal("100"))


@dataclass(frozen=True)
class _SaasAdjustmentDelta:
    factor: str
    change: Decimal
    note: str
    i18n_key: str


@dataclass(frozen=True)
class _SaasThresholdAdjustment:
    factor: str
    operator: str
    threshold: Decimal
    change: Decimal
    note: str
    i18n_key: str

    def matches(self, value: Decimal) -> bool:
        if self.operator == "gt":
            return value > self.threshold
        if self.operator == "gte":
            return value >= self.threshold
        return value < self.threshold

    def to_delta(self) -> _SaasAdjustmentDelta:
        return _SaasAdjustmentDelta(
            factor=self.factor,
            change=self.change,
            note=self.note,
            i18n_key=self.i18n_key,
        )


@dataclass(frozen=True)
class _SaasMetricInputs:
    arr_growth: Optional[Decimal]
    nrr: Optional[Decimal]
    revenue_churn: Optional[Decimal]
    customer_churn: Optional[Decimal]
    gross_margin: Optional[Decimal]
    customer_concentration: Optional[Decimal]
    expansion_revenue: Optional[Decimal]
    cac: Optional[Decimal]
    sm_spend: Optional[Decimal]
    rule_of_40: Optional[Decimal]
    ltv_cac: Optional[Decimal]
    cac_payback_months: Optional[Decimal]
    magic_number: Optional[Decimal]
    nrr_expansion_spread: Optional[Decimal]


_BENELUX_EU_COUNTRIES = frozenset({"BE", "NL", "LU", "FR", "DE"})
_BASE_ARR_MULTIPLE = Decimal("5.0")

_NRR_RULES = (
    _SaasThresholdAdjustment(
        "nrr",
        "gte",
        Decimal("1.20"),
        Decimal("2.0"),
        "NRR above 120% unlocks premium ARR multiples.",
        "saas_nrr_120",
    ),
    _SaasThresholdAdjustment(
        "nrr",
        "gte",
        Decimal("1.10"),
        Decimal("1.0"),
        "NRR above 110% supports a premium multiple.",
        "saas_nrr_110",
    ),
    _SaasThresholdAdjustment(
        "nrr",
        "gte",
        Decimal("1.00"),
        Decimal("0.5"),
        "NRR at or above 100% shows healthy retention.",
        "saas_nrr_100",
    ),
    _SaasThresholdAdjustment(
        "nrr",
        "lt",
        Decimal("0.90"),
        Decimal("-1.0"),
        "NRR below 90% pressures the valuation multiple.",
        "saas_nrr_90",
    ),
)

_REVENUE_CHURN_RULES = (
    _SaasThresholdAdjustment(
        "gross_revenue_churn",
        "gt",
        Decimal("0.15"),
        Decimal("-1.5"),
        "High revenue churn is a strong multiple drag.",
        "saas_churn_15",
    ),
    _SaasThresholdAdjustment(
        "gross_revenue_churn",
        "gt",
        Decimal("0.10"),
        Decimal("-1.0"),
        "Revenue churn above 10% reduces multiple confidence.",
        "saas_churn_10",
    ),
    _SaasThresholdAdjustment(
        "gross_revenue_churn",
        "gt",
        Decimal("0.05"),
        Decimal("-0.5"),
        "Revenue churn between 5–10% is moderate for SME SaaS.",
        "saas_churn_5",
    ),
)

_RULE_OF_40_RULES = (
    _SaasThresholdAdjustment(
        "rule_of_40",
        "gt",
        Decimal("60"),
        Decimal("1.5"),
        "Rule of 40 above 60 is elite for SME SaaS.",
        "saas_ro40_60",
    ),
    _SaasThresholdAdjustment(
        "rule_of_40",
        "gte",
        Decimal("40"),
        Decimal("1.0"),
        "Rule of 40 at or above 40 supports a premium multiple.",
        "saas_ro40_40",
    ),
    _SaasThresholdAdjustment(
        "rule_of_40",
        "lt",
        Decimal("20"),
        Decimal("-1.0"),
        "Rule of 40 below 20 signals weaker SaaS efficiency.",
        "saas_ro40_20",
    ),
)

_ARR_GROWTH_RULES = (
    _SaasThresholdAdjustment(
        "arr_growth",
        "gt",
        Decimal("0.50"),
        Decimal("2.0"),
        "ARR growth above 50% warrants the strongest premium.",
        "saas_ag_50",
    ),
    _SaasThresholdAdjustment(
        "arr_growth",
        "gt",
        Decimal("0.30"),
        Decimal("1.0"),
        "ARR growth above 30% supports a premium.",
        "saas_ag_30",
    ),
    _SaasThresholdAdjustment(
        "arr_growth",
        "gte",
        Decimal("0.10"),
        Decimal("0.5"),
        "ARR growth between 10–30% shows steady momentum.",
        "saas_ag_10_30",
    ),
    _SaasThresholdAdjustment(
        "arr_growth",
        "lt",
        Decimal("0.10"),
        Decimal("-0.5"),
        "Low ARR growth narrows the valuation range.",
        "saas_ag_10",
    ),
)

_CUSTOMER_CONCENTRATION_RULES = (
    _SaasThresholdAdjustment(
        "customer_concentration",
        "gt",
        Decimal("0.70"),
        Decimal("-1.5"),
        "Heavy customer concentration increases retention risk.",
        "saas_cc_70",
    ),
    _SaasThresholdAdjustment(
        "customer_concentration",
        "gt",
        Decimal("0.50"),
        Decimal("-1.0"),
        "Top-customer concentration above 50% reduces quality.",
        "saas_cc_50",
    ),
    _SaasThresholdAdjustment(
        "customer_concentration",
        "gt",
        Decimal("0.30"),
        Decimal("-0.5"),
        "Customer concentration between 30–50% is a moderate risk signal.",
        "saas_cc_30",
    ),
)

_GROSS_MARGIN_RULES = (
    _SaasThresholdAdjustment(
        "gross_margin",
        "gte",
        Decimal("0.80"),
        Decimal("0.5"),
        "Gross margin above 80% supports SaaS quality.",
        "saas_gm_80",
    ),
    _SaasThresholdAdjustment(
        "gross_margin",
        "lt",
        Decimal("0.60"),
        Decimal("-0.5"),
        "Gross margin below 60% weakens SaaS quality.",
        "saas_gm_60",
    ),
)

_EXPANSION_REVENUE_RULES = (
    _SaasThresholdAdjustment(
        "expansion_revenue",
        "gte",
        Decimal("0.20"),
        Decimal("0.5"),
        "Expansion revenue above 20% improves compounding quality.",
        "saas_exp_20",
    ),
    _SaasThresholdAdjustment(
        "expansion_revenue",
        "gte",
        Decimal("0.10"),
        Decimal("0.25"),
        "Expansion revenue between 10–20% shows healthy upsell motion.",
        "saas_exp_10",
    ),
    _SaasThresholdAdjustment(
        "expansion_revenue",
        "lt",
        Decimal("0.05"),
        Decimal("-0.25"),
        "Expansion revenue below 5% signals limited upsell capability.",
        "saas_exp_low",
    ),
)


def _percentage_points(value: Optional[Decimal]) -> Optional[float]:
    return _to_float(value * Decimal("100")) if value is not None else None


def _rule_of_40(
    arr_growth: Optional[Decimal], gross_margin: Optional[Decimal]
) -> Optional[Decimal]:
    if arr_growth is None or gross_margin is None:
        return None
    return (arr_growth + gross_margin) * Decimal("100")


def _ltv_cac(
    *,
    arr: Decimal,
    gross_margin: Optional[Decimal],
    customer_churn: Optional[Decimal],
    cac: Optional[Decimal],
) -> Optional[Decimal]:
    if arr <= 0:
        return None
    if gross_margin is None or customer_churn is None or customer_churn <= 0:
        return None
    if cac is None or cac <= 0:
        return None
    return ((arr * gross_margin) / customer_churn) / cac


def _monthly_recurring_revenue(context: Mapping[str, object], arr: Decimal) -> Decimal:
    mrr_explicit = get_business_context_decimal(context, "saas_mrr")
    if mrr_explicit is not None and mrr_explicit > 0:
        return mrr_explicit
    return arr / Decimal("12")


def _cac_payback_months(
    *,
    cac: Optional[Decimal],
    monthly_recurring: Decimal,
    gross_margin: Optional[Decimal],
) -> Optional[Decimal]:
    if cac is None or cac <= 0:
        return None
    if monthly_recurring <= 0 or gross_margin is None or gross_margin <= 0:
        return None
    return cac / (monthly_recurring * gross_margin)


def _magic_number(
    *,
    arr: Decimal,
    arr_growth: Optional[Decimal],
    sm_spend: Optional[Decimal],
) -> Optional[Decimal]:
    if arr <= 0 or arr_growth is None:
        return None
    if sm_spend is None or sm_spend <= 0:
        return None
    return ((arr * arr_growth) / sm_spend) * Decimal("4")


def _extract_saas_metric_inputs(
    *,
    context: Mapping[str, object],
    arr: Decimal,
) -> _SaasMetricInputs:
    arr_growth = get_business_context_percent(context, "saas_arr_growth_pct")
    nrr = get_business_context_percent(context, "saas_nrr_pct")
    revenue_churn = get_business_context_percent(context, "saas_churn_pct")
    customer_churn = get_business_context_percent(context, "saas_customer_churn_pct")
    gross_margin = get_business_context_percent(context, "saas_gross_margin_pct")
    customer_concentration = get_business_context_percent(
        context, "saas_customer_concentration_pct"
    )
    expansion_revenue = get_business_context_percent(context, "saas_expansion_revenue_pct")
    cac = get_business_context_decimal(context, "saas_cac")
    sm_spend = get_business_context_decimal(context, "saas_sm_spend")
    monthly_recurring = _monthly_recurring_revenue(context, arr)
    rule_of_40 = _rule_of_40(arr_growth, gross_margin)
    return _SaasMetricInputs(
        arr_growth=arr_growth,
        nrr=nrr,
        revenue_churn=revenue_churn,
        customer_churn=customer_churn,
        gross_margin=gross_margin,
        customer_concentration=customer_concentration,
        expansion_revenue=expansion_revenue,
        cac=cac,
        sm_spend=sm_spend,
        rule_of_40=rule_of_40,
        ltv_cac=_ltv_cac(
            arr=arr,
            gross_margin=gross_margin,
            customer_churn=customer_churn,
            cac=cac,
        ),
        cac_payback_months=_cac_payback_months(
            cac=cac,
            monthly_recurring=monthly_recurring,
            gross_margin=gross_margin,
        ),
        magic_number=_magic_number(
            arr=arr,
            arr_growth=arr_growth,
            sm_spend=sm_spend,
        ),
        nrr_expansion_spread=_nrr_expansion_spread_points(nrr, revenue_churn),
    )


def _matching_adjustment_delta(
    value: Optional[Decimal], rules: tuple[_SaasThresholdAdjustment, ...]
) -> Optional[_SaasAdjustmentDelta]:
    if value is None:
        return None
    for rule in rules:
        if rule.matches(value):
            return rule.to_delta()
    return None


def _saas_adjustment_deltas(metrics: _SaasMetricInputs) -> list[_SaasAdjustmentDelta]:
    candidates = (
        (metrics.nrr, _NRR_RULES),
        (metrics.revenue_churn, _REVENUE_CHURN_RULES),
        (metrics.rule_of_40, _RULE_OF_40_RULES),
        (metrics.arr_growth, _ARR_GROWTH_RULES),
        (metrics.customer_concentration, _CUSTOMER_CONCENTRATION_RULES),
        (metrics.gross_margin, _GROSS_MARGIN_RULES),
        (metrics.expansion_revenue, _EXPANSION_REVENUE_RULES),
    )
    return [
        delta
        for value, rules in candidates
        if (delta := _matching_adjustment_delta(value, rules)) is not None
    ]


def _breakdown_step(delta: _SaasAdjustmentDelta) -> dict[str, object]:
    return {
        "factor": delta.factor,
        "change": _to_float(delta.change),
        "note": delta.note,
        "i18n_key": delta.i18n_key,
    }


def _apply_adjustment_deltas(
    *,
    multiple: Decimal,
    breakdown: list[dict[str, object]],
    deltas: list[_SaasAdjustmentDelta],
) -> Decimal:
    adjusted = multiple
    for delta in deltas:
        if delta.change == 0:
            continue
        adjusted += delta.change
        breakdown.append(_breakdown_step(delta))
    return adjusted


def _regional_discount(country_code: str) -> Decimal:
    return Decimal("0.85") if country_code.upper() in _BENELUX_EU_COUNTRIES else Decimal("1.0")


def _initial_adjustment_breakdown(
    *,
    base_multiple: Decimal,
    regional_discount: Decimal,
) -> list[dict[str, object]]:
    return [
        {
            "factor": "regional_belgian_eu_private_discount",
            "change": _to_float((base_multiple * regional_discount) - base_multiple),
            "note": "Private Benelux / EU SaaS SMEs trade below US public cloud benchmark levels.",
            "i18n_key": "saas_regional",
        }
    ]


def _build_computed_metrics(
    *,
    arr: Decimal,
    metrics: _SaasMetricInputs,
    regional_discount: Decimal,
    base_multiple: Decimal,
    quality_score: Optional[float],
) -> dict[str, object]:
    return {
        "arr": _to_float(arr),
        "arr_growth_pct": _percentage_points(metrics.arr_growth),
        "nrr_pct": _percentage_points(metrics.nrr),
        "gross_revenue_churn_pct": _percentage_points(metrics.revenue_churn),
        "customer_churn_pct": _percentage_points(metrics.customer_churn),
        "gross_margin_pct": _percentage_points(metrics.gross_margin),
        "customer_concentration_pct": _percentage_points(metrics.customer_concentration),
        "expansion_revenue_pct": _percentage_points(metrics.expansion_revenue),
        "rule_of_40": _to_float(metrics.rule_of_40),
        "ltv_cac": _to_float(metrics.ltv_cac),
        "cac_payback_months": _to_float(metrics.cac_payback_months),
        "magic_number": _to_float(metrics.magic_number),
        "nrr_expansion_spread": _to_float(metrics.nrr_expansion_spread),
        "regional_discount_factor": _to_float(regional_discount),
        # Surface the base multiple so the report waterfall can render the
        # correct anchor instead of hardcoding 5.0x in the template.
        "base_multiple": _to_float(base_multiple),
        "saas_quality_score": quality_score,
        "saas_quality_label": _quality_label(quality_score),
    }


@dataclass
class SaasAdjustmentResult:
    is_saas: bool
    arr: Optional[Decimal]
    arr_multiple: Optional[Decimal]
    ebitda_adjustment_factor: Decimal
    computed_metrics: dict[str, object] = field(default_factory=dict)
    adjustment_breakdown: list[dict[str, object]] = field(default_factory=list)
    eligibility: Optional[SaasEligibilityVerdict] = None
    validation: Optional[SaasValidationReport] = None

    @property
    def is_eligible(self) -> bool:
        """ARR-multiple-as-primary-method eligibility — the load-bearing flag.

        ``is_saas`` only signals that ARR could be derived; ``is_eligible``
        means the ARR multiple is defensible as the headline lens (recurring
        share above threshold, no validation errors, growth/retention
        signals present).
        """
        if not self.is_saas or self.eligibility is None:
            return False
        return self.eligibility.eligible


def _derive_arr(
    *,
    revenue: Decimal,
    recurring_revenue_percentage: Optional[Decimal],
    context: Mapping[str, object],
) -> Optional[Decimal]:
    explicit_arr = get_business_context_decimal(context, "saas_arr")
    if explicit_arr is not None and explicit_arr > 0:
        return explicit_arr

    mrr = get_business_context_decimal(context, "saas_mrr")
    if mrr is not None and mrr > 0:
        return mrr * Decimal("12")

    if (
        recurring_revenue_percentage is not None
        and recurring_revenue_percentage > 0
        and revenue > 0
    ):
        return revenue * recurring_revenue_percentage

    if recurring_revenue_percentage is not None and recurring_revenue_percentage <= 0:
        return None

    return revenue if revenue > 0 else None


def _compute_saas_quality_score(
    *,
    rule_of_40: Optional[Decimal],
    nrr: Optional[Decimal],
    ltv_cac: Optional[Decimal],
    revenue_churn: Optional[Decimal],
    gross_margin: Optional[Decimal],
) -> Optional[float]:
    """0–100 composite quality score across key SaaS health metrics."""
    scores = []
    if rule_of_40 is not None:
        ro40 = float(rule_of_40)
        scores.append(min(100.0, max(0.0, (ro40 / 60.0) * 100.0)))
    if nrr is not None:
        nrr_f = float(nrr) * 100
        scores.append(min(100.0, max(0.0, ((nrr_f - 80) / 40) * 100)))
    if ltv_cac is not None:
        scores.append(min(100.0, max(0.0, (float(ltv_cac) / 5.0) * 100.0)))
    if revenue_churn is not None:
        churn_f = float(revenue_churn) * 100
        scores.append(min(100.0, max(0.0, ((15 - churn_f) / 15) * 100)))
    if gross_margin is not None:
        gm_f = float(gross_margin) * 100
        scores.append(min(100.0, max(0.0, ((gm_f - 50) / 40) * 100)))
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def _quality_label(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    if score >= 75:
        return "strong"
    if score >= 50:
        return "healthy"
    if score >= 25:
        return "developing"
    return "at_risk"


def compute_saas_adjustment(
    *,
    revenue: Decimal,
    recurring_revenue_percentage: Optional[Decimal],
    business_context: Optional[Mapping[str, object]],
    country_code: str = "BE",
    eligibility_thresholds: Optional[EligibilityThresholds] = None,
    business_type_id: Optional[str] = None,
) -> SaasAdjustmentResult:
    """Compute SaaS-conditioned valuation inputs (ARR multiple, EBITDA
    adjustment factor, computed health metrics).

    The function ALWAYS returns a ``SaasAdjustmentResult`` carrying
    ``validation`` and ``eligibility`` payloads — even when ARR is
    missing or ineligible. Callers needing a strict gate read
    ``result.is_eligible``; callers that only want metrics for the
    report read ``result.computed_metrics`` regardless.
    """
    context = dict(business_context or {})

    # Resolve thresholds: explicit override > per-business-type lookup >
    # module defaults. Keeps per-type tuning out of every caller's hands
    # and makes the gate deterministic for any registered business type.
    resolved_thresholds = (
        eligibility_thresholds
        if eligibility_thresholds is not None
        else EligibilityThresholds.for_business_type(business_type_id)
    )

    # Run validation FIRST so the eligibility verdict can inspect errors
    # before any other branch decides we are or are not "SaaS".
    validation_report = validate_saas_inputs(
        business_context=context,
        revenue=revenue if revenue is not None and revenue > 0 else None,
    )

    arr = _derive_arr(
        revenue=revenue,
        recurring_revenue_percentage=recurring_revenue_percentage,
        context=context,
    )

    eligibility_verdict = evaluate_saas_eligibility(
        revenue=revenue if revenue is not None and revenue > 0 else None,
        business_context=context,
        recurring_revenue_percentage=recurring_revenue_percentage,
        validation_report=validation_report,
        thresholds=resolved_thresholds,
    )

    if arr is None or arr <= 0:
        return SaasAdjustmentResult(
            is_saas=False,
            arr=None,
            arr_multiple=None,
            ebitda_adjustment_factor=Decimal("1"),
            eligibility=eligibility_verdict,
            validation=validation_report,
        )

    # Hard-block: validation errors collapse the SaaS path. Diagnostics
    # are still carried on the result so callers can surface them
    # (no silent rejection).
    if validation_report.has_errors:
        return SaasAdjustmentResult(
            is_saas=False,
            arr=arr,
            arr_multiple=None,
            ebitda_adjustment_factor=Decimal("1"),
            eligibility=eligibility_verdict,
            validation=validation_report,
        )

    metrics = _extract_saas_metric_inputs(context=context, arr=arr)
    base_multiple = _BASE_ARR_MULTIPLE
    regional_discount = _regional_discount(country_code)
    multiple = base_multiple * regional_discount
    breakdown = _initial_adjustment_breakdown(
        base_multiple=base_multiple,
        regional_discount=regional_discount,
    )
    multiple = _apply_adjustment_deltas(
        multiple=multiple,
        breakdown=breakdown,
        deltas=_saas_adjustment_deltas(metrics),
    )

    arr_multiple = _clamp(multiple, Decimal("2.5"), Decimal("12.0"))
    ebitda_adjustment_factor = _clamp(
        arr_multiple / base_multiple, Decimal("0.75"), Decimal("1.35")
    )

    saas_quality_score = _compute_saas_quality_score(
        rule_of_40=metrics.rule_of_40,
        nrr=metrics.nrr,
        ltv_cac=metrics.ltv_cac,
        revenue_churn=metrics.revenue_churn,
        gross_margin=metrics.gross_margin,
    )

    computed_metrics = _build_computed_metrics(
        arr=arr,
        metrics=metrics,
        regional_discount=regional_discount,
        base_multiple=base_multiple,
        quality_score=saas_quality_score,
    )

    # CRITICAL: when SaaS lens is INELIGIBLE (e.g. recurring share too low,
    # missing growth/retention signals), the EBITDA multiple must NOT be
    # perturbed by SaaS-flavoured math. We keep ARR multiple + computed
    # metrics for reporting, but neutralise the cross-method ebitda factor
    # so an ineligible SaaS profile cannot silently discount the EBITDA
    # valuation of a non-SaaS business (the Three Towers Capital scenario).
    eligible_ebitda_factor = (
        ebitda_adjustment_factor if eligibility_verdict.eligible else Decimal("1")
    )

    return SaasAdjustmentResult(
        is_saas=True,
        arr=arr,
        arr_multiple=arr_multiple,
        ebitda_adjustment_factor=eligible_ebitda_factor,
        computed_metrics=computed_metrics,
        adjustment_breakdown=breakdown,
        eligibility=eligibility_verdict,
        validation=validation_report,
    )
