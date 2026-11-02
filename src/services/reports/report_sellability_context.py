"""Sellability report-section context builder.

Keeps the sellability section's state machine and localization maps out of
``MainReportDataAggregator`` while preserving the exact template context shape.
"""

from collections.abc import Mapping
from typing import Protocol

from src.services.reports.report_map_coercion import ReportMap, as_report_map, mapping_rows


class SellabilityTranslations(Protocol):
    sellability_band_significant_label: str
    sellability_band_significant_advice: str
    sellability_band_foundations_label: str
    sellability_band_foundations_advice: str
    sellability_band_sale_ready_in_most_label: str
    sellability_band_sale_ready_in_most_advice: str
    sellability_band_sale_ready_today_label: str
    sellability_band_sale_ready_today_advice: str
    sellability_confidence_high: str
    sellability_confidence_med: str
    sellability_confidence_low: str
    sellability_factor_owner_dependence: str
    sellability_factor_customer_concentration: str
    sellability_factor_revenue_quality: str
    sellability_factor_financial_cleanliness: str
    sellability_factor_growth_trend: str
    sellability_factor_transferability: str
    sellability_factor_owner_dependence_explanation: str
    sellability_factor_customer_concentration_explanation: str
    sellability_factor_revenue_quality_explanation: str
    sellability_factor_financial_cleanliness_explanation: str
    sellability_factor_growth_trend_explanation: str
    sellability_factor_transferability_explanation: str
    sellability_provenance_native: str
    sellability_provenance_aggregate_clone: str
    sellability_provenance_aggregate: str
    sellability_low_confidence_heading: str
    sellability_low_confidence_body: str
    sellability_sale_ready_empty_heading: str
    sellability_sale_ready_empty_body: str
    sellability_top_lifts_heading: str
    sellability_top_lifts_subheading: str
    sellability_tertiary_lifts_heading: str
    sellability_tertiary_lifts_subheading: str
    sellability_factor_breakdown_heading: str
    sellability_factor_breakdown_subheading: str
    sellability_close_caregiver: str
    sellability_invite_accountant_heading: str
    sellability_invite_accountant_body: str
    sellability_invite_accountant_cta: str


def _empty_sellability_context() -> ReportMap:
    return {
        "show_sellability_section": False,
        "sellability": None,
    }


def _sellability_assessment_map(response: object) -> ReportMap | None:
    sa = getattr(response, "sellability_assessment", None)
    if sa is None:
        return None
    return as_report_map(sa)


def _sellability_state(
    *,
    band: object,
    confidence: object,
    top_three_lifts: list[ReportMap],
) -> str:
    if band == "sale_ready_today" and not top_three_lifts:
        return "sale_ready"
    if confidence == "low" and not top_three_lifts:
        return "low_confidence"
    return "normal"


def _band_label_map(t: SellabilityTranslations) -> dict[str, tuple[str, str]]:
    return {
        "significant_work_to_do": (
            t.sellability_band_significant_label,
            t.sellability_band_significant_advice,
        ),
        "foundations_in_place": (
            t.sellability_band_foundations_label,
            t.sellability_band_foundations_advice,
        ),
        "sale_ready_in_most_ways": (
            t.sellability_band_sale_ready_in_most_label,
            t.sellability_band_sale_ready_in_most_advice,
        ),
        "sale_ready_today": (
            t.sellability_band_sale_ready_today_label,
            t.sellability_band_sale_ready_today_advice,
        ),
    }


def _confidence_label_map(t: SellabilityTranslations) -> dict[str, str]:
    return {
        "high": t.sellability_confidence_high,
        "med": t.sellability_confidence_med,
        "low": t.sellability_confidence_low,
    }


def _factor_label_map(t: SellabilityTranslations) -> dict[str, str]:
    return {
        "owner_dependence": t.sellability_factor_owner_dependence,
        "customer_concentration": t.sellability_factor_customer_concentration,
        "revenue_quality": t.sellability_factor_revenue_quality,
        "financial_cleanliness": t.sellability_factor_financial_cleanliness,
        "growth_trend": t.sellability_factor_growth_trend,
        "transferability": t.sellability_factor_transferability,
    }


def _factor_explanation_map(t: SellabilityTranslations) -> dict[str, str]:
    return {
        "owner_dependence": t.sellability_factor_owner_dependence_explanation,
        "customer_concentration": t.sellability_factor_customer_concentration_explanation,
        "revenue_quality": t.sellability_factor_revenue_quality_explanation,
        "financial_cleanliness": t.sellability_factor_financial_cleanliness_explanation,
        "growth_trend": t.sellability_factor_growth_trend_explanation,
        "transferability": t.sellability_factor_transferability_explanation,
    }


def _value_pct(value: object) -> float:
    try:
        pct = float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        pct = 0.0
    return max(0.0, min(100.0, pct))


def _decorated_factors(
    factors: object,
    *,
    factor_label_map: dict[str, str],
    factor_explanation_map: dict[str, str],
) -> list[ReportMap]:
    decorated_factors: list[ReportMap] = []
    for factor in mapping_rows(factors):
        key = factor.get("key")
        pct = _value_pct(factor.get("value"))
        decorated_factors.append(
            {
                **factor,
                "label": factor_label_map.get(key, key),
                "explanation": factor_explanation_map.get(key, ""),
                "value_pct": pct,
                "value_int": int(round(pct)),
            }
        )
    return decorated_factors


def _decorated_lifts(
    lifts: list[ReportMap],
    *,
    factor_label_map: dict[str, str],
) -> list[ReportMap]:
    return [
        {
            **lift,
            "factor_label": factor_label_map.get(lift.get("factor"), lift.get("factor")),
        }
        for lift in lifts
    ]


def _provenance_label(
    sa_dict: ReportMap,
    t: SellabilityTranslations,
) -> str | None:
    engine_signals = as_report_map(sa_dict.get("engine_signals")) or {}
    country_basis = engine_signals.get("delphi_country_basis")
    if not country_basis:
        return None
    return {
        "native": t.sellability_provenance_native,
        "aggregate_clone": t.sellability_provenance_aggregate_clone,
        "aggregate": t.sellability_provenance_aggregate,
    }.get(country_basis)


def _invite_accountant_url(request: object | None) -> str | None:
    if request is None:
        return None
    try:
        metadata = getattr(request, "metadata", None)
        if isinstance(metadata, Mapping):
            raw = metadata.get("invite_accountant_cta_url")
            if raw is not None:
                rendered = str(raw).strip()
                if rendered:
                    return rendered
    except Exception:
        return None
    return None


def _sellability_chrome(t: SellabilityTranslations) -> ReportMap:
    return {
        "low_confidence_heading": t.sellability_low_confidence_heading,
        "low_confidence_body": t.sellability_low_confidence_body,
        "sale_ready_empty_heading": t.sellability_sale_ready_empty_heading,
        "sale_ready_empty_body": t.sellability_sale_ready_empty_body,
        "top_lifts_heading": t.sellability_top_lifts_heading,
        "top_lifts_subheading": t.sellability_top_lifts_subheading,
        "tertiary_lifts_heading": t.sellability_tertiary_lifts_heading,
        "tertiary_lifts_subheading": t.sellability_tertiary_lifts_subheading,
        "factor_breakdown_heading": t.sellability_factor_breakdown_heading,
        "factor_breakdown_subheading": t.sellability_factor_breakdown_subheading,
        "close_caregiver": t.sellability_close_caregiver,
        "invite_accountant_heading": t.sellability_invite_accountant_heading,
        "invite_accountant_body": t.sellability_invite_accountant_body,
        "invite_accountant_cta": t.sellability_invite_accountant_cta,
    }


def build_sellability_section_context(
    response: object | None,
    t: SellabilityTranslations,
    *,
    is_owner_dep_methodology: bool = True,
    request: object | None = None,
) -> ReportMap:
    """Build the Sellability section context (BET-204 / chunk 6).

    Returns ``show_sellability_section: bool`` plus a flat ``sellability``
    dict ready for the Jinja partial. Four states:

    - **suppressed**: pure DCF / ASSET methodology.
    - **suppressed (no attachment)**: owner-dep methodology without
      ``sellability_assessment``.
    - **sale_ready**: top band and no actionable lifts.
    - **normal**: score, 6-factor breakdown, lifts, and benchmark provenance.

    Number formatting stays in the template so the same context drives HTML
    and PDF without duplicating format logic here.
    """
    if response is None:
        return _empty_sellability_context()

    if not is_owner_dep_methodology:
        return _empty_sellability_context()

    sa_dict = _sellability_assessment_map(response)
    if sa_dict is None:
        return _empty_sellability_context()

    score = int(sa_dict.get("score") or 0)
    band = sa_dict.get("band") or "significant_work_to_do"
    confidence = sa_dict.get("confidence") or "low"
    top_three_lifts = mapping_rows(sa_dict.get("top_three_lifts"))
    tertiary_lifts = mapping_rows(sa_dict.get("tertiary_lifts"))
    state = _sellability_state(
        band=band,
        confidence=confidence,
        top_three_lifts=top_three_lifts,
    )
    band_label_map = _band_label_map(t)
    band_label, band_advice = band_label_map.get(band, band_label_map["significant_work_to_do"])
    confidence_label = _confidence_label_map(t).get(confidence, t.sellability_confidence_low)
    factor_label_map = _factor_label_map(t)
    decorated_top_lifts = _decorated_lifts(top_three_lifts, factor_label_map=factor_label_map)
    decorated_tertiary_lifts = _decorated_lifts(
        tertiary_lifts,
        factor_label_map=factor_label_map,
    )

    return {
        "show_sellability_section": True,
        "sellability": {
            "state": state,
            "score": max(0, min(100, score)),
            "band": band,
            "band_label": band_label,
            "band_advice": band_advice,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "factors": _decorated_factors(
                sa_dict.get("factors"),
                factor_label_map=factor_label_map,
                factor_explanation_map=_factor_explanation_map(t),
            ),
            "top_three_lifts": decorated_top_lifts,
            "tertiary_lifts": decorated_tertiary_lifts,
            "provenance_label": _provenance_label(sa_dict, t),
            **_sellability_chrome(t),
            "invite_accountant_url": _invite_accountant_url(request),
        },
    }
