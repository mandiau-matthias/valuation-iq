"""Final payload assembly for startup report context."""

from dataclasses import dataclass
from typing import Optional

from src.services.reports.startup_report_context_helpers import (
    JsonMap,
    JsonRows,
    pin_float_band,
    safe_float,
    safe_get,
)
from src.services.reports.startup_report_context_sections import (
    build_founder_floor_advisory,
    ordered_weights,
    startup_input_float,
)
from src.services.reports.startup_report_translations import STARTUP_REPORT_TRANSLATIONS


@dataclass(frozen=True)
class StartupReportContextParts:
    loc: str
    details: JsonMap
    startup_inputs: object
    stage_display: str
    sector: object
    cleaned_advisor_cta_url: Optional[str]
    founder_pitch: object
    exit_multiple_rationale: object
    headline_mid: float
    canonical_low: float
    canonical_high: float
    canonical_basis: object
    weights: object
    founder_view: object
    outlier_policy: object
    defensibility_score: object
    sector_consistency: object
    berkus: object
    scorecard: object
    vc: object
    saas_forward: object
    defensibility: object
    regional: object
    sector_comparables: object
    cap_table: JsonMap
    pre_money_target_f: Optional[float]
    option_pool_pct: float
    safe_notes: object
    safe_total: float
    estimated_post_money: float
    founder_dilution_pct: float
    cap_table_simulator: Optional[JsonMap]
    share_distribution_segments: JsonRows
    dilution_scenarios: object
    inception_lens_advisory: object
    vc_oversubscribed: object
    vc_sensitivity: object
    vc_multiple_source: object
    risks_register: object


def build_startup_translation_table(loc: str) -> dict[str, str]:
    return {
        key: (entry.get(loc) or entry.get("nl") or f"[{key}]")
        for key, entry in STARTUP_REPORT_TRANSLATIONS.items()
    }


def assemble_startup_report_context(parts: StartupReportContextParts) -> JsonMap:
    headline_low, headline_mid, headline_high = _headline_values(parts)
    context = _base_context(
        parts=parts,
        headline_low=headline_low,
        headline_mid=headline_mid,
        headline_high=headline_high,
    )
    context.update(_method_context(parts))
    context.update(_cap_table_context(parts))
    context.update(_risk_and_sensitivity_context(parts))
    context["traction"] = _traction_context(parts.startup_inputs)
    return context


def _base_context(
    *,
    parts: StartupReportContextParts,
    headline_low: float,
    headline_mid: float,
    headline_high: float,
) -> JsonMap:
    t_table = build_startup_translation_table(parts.loc)
    return {
        "locale": parts.loc,
        "t": t_table,
        "stage": parts.details.get("stage"),
        "stage_display": parts.stage_display,
        "country_code": parts.details.get("country_code"),
        "sector": parts.sector,
        "advisor_cta_url": parts.cleaned_advisor_cta_url,
        "narrative": parts.details.get("narrative"),
        "founder_pitch": parts.founder_pitch,
        "exit_multiple_rationale": parts.exit_multiple_rationale,
        "equity_value_low": headline_low,
        "equity_value_mid": headline_mid,
        "equity_value_high": headline_high,
        "advisor_view": _advisor_view(parts),
        "weights": ordered_weights(parts.weights),
        "contributors": list(parts.details.get("contributors") or []),
        "founder_view": parts.founder_view,
    }


def _method_context(parts: StartupReportContextParts) -> JsonMap:
    return {
        "canonical": {
            "pre_money_mid": parts.headline_mid,
            "pre_money_low": parts.canonical_low,
            "pre_money_high": parts.canonical_high,
            "basis": parts.canonical_basis,
        },
        "outlier_policy": parts.outlier_policy,
        "defensibility_score": parts.defensibility_score,
        "sector_consistency": parts.sector_consistency,
        "berkus": parts.berkus,
        "scorecard": parts.scorecard,
        "vc": parts.vc,
        "saas_forward": parts.saas_forward,
        "defensibility": parts.defensibility,
        "regional_reference": parts.regional,
        "sector_comparables": parts.sector_comparables,
    }


def _cap_table_context(parts: StartupReportContextParts) -> JsonMap:
    return {
        "cap_table": {
            "pre_money_target": parts.pre_money_target_f,
            "option_pool_pct": parts.option_pool_pct,
            "safe_notes": parts.safe_notes,
            "safe_notes_total": parts.safe_total,
            "last_round_amount": safe_float(parts.cap_table.get("last_round_amount")),
            "last_round_post_money": safe_float(parts.cap_table.get("last_round_post_money")),
            "last_round_date": parts.cap_table.get("last_round_date"),
        },
        "dilution_scenario": {
            "post_money": parts.estimated_post_money,
            "founder_dilution_pct": parts.founder_dilution_pct,
            "option_pool_pct": parts.option_pool_pct,
            "safe_dilution_amount": parts.safe_total,
        },
        "cap_table_simulator": parts.cap_table_simulator,
        "share_distribution_segments": parts.share_distribution_segments,
        "dilution_scenarios": parts.dilution_scenarios,
        "founder_floor_advisory": build_founder_floor_advisory(
            parts.cap_table_simulator,
            parts.safe_notes,
        ),
    }


def _risk_and_sensitivity_context(parts: StartupReportContextParts) -> JsonMap:
    return {
        "inception_lens_advisory": parts.inception_lens_advisory,
        "vc_oversubscribed": parts.vc_oversubscribed,
        "vc_sensitivity": parts.vc_sensitivity,
        "vc_multiple_source": parts.vc_multiple_source,
        "pre_money_distribution": _pre_money_distribution(parts),
        "risks_register": parts.risks_register,
    }


def _headline_values(parts: StartupReportContextParts) -> tuple[float, float, float]:
    low = parts.canonical_low or float(parts.details.get("equity_value_low") or 0)
    high = parts.canonical_high or float(parts.details.get("equity_value_high") or 0)
    return pin_float_band(low, parts.headline_mid, high)


def _advisor_view(parts: StartupReportContextParts) -> JsonMap:
    low, mid, high = pin_float_band(
        float(parts.details.get("equity_value_low") or 0),
        float(parts.details.get("equity_value_mid") or 0),
        float(parts.details.get("equity_value_high") or 0),
    )
    return {
        "equity_value_mid": mid,
        "equity_value_low": low,
        "equity_value_high": high,
        "weights": ordered_weights(parts.weights),
        "contributors": list(parts.details.get("contributors") or []),
    }


def _pre_money_distribution(parts: StartupReportContextParts) -> JsonMap:
    low = parts.canonical_low or float(parts.details.get("equity_value_low") or 0)
    high = parts.canonical_high or float(parts.details.get("equity_value_high") or 0)
    return {
        "p10": low,
        "p50": parts.headline_mid,
        "p90": high,
        "spread_ratio": (high / low) if low and high else None,
    }


def _traction_context(startup_inputs: object) -> JsonMap:
    return {
        "mrr": startup_input_float(startup_inputs, "mrr"),
        "arr": startup_input_float(startup_inputs, "arr"),
        "mrr_growth_rate_pct": startup_input_float(startup_inputs, "mrr_growth_rate_pct"),
        "monthly_churn_pct": startup_input_float(startup_inputs, "monthly_churn_pct"),
        "cac": startup_input_float(startup_inputs, "cac"),
        "ltv": startup_input_float(startup_inputs, "ltv"),
        "burn_rate_monthly": startup_input_float(startup_inputs, "burn_rate_monthly"),
        "runway_months": startup_input_float(startup_inputs, "runway_months"),
        "team_size": safe_get(startup_inputs, "team_size"),
    }
