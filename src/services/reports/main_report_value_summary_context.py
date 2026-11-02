"""Value-summary context builders for main report aggregation."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol

from src.services.reports.advisor_multiple_transparency_context import (
    build_advisor_multiple_transparency_context,
)
from src.services.reports.report_reference_context import ReportReferenceContext
from src.utils.decimal_helpers import safe_decimal_or_zero as _canonical_safe_decimal
from src.utils.decimal_helpers import safe_float as _canonical_safe_float

JsonMap = dict[str, object]

to_float = _canonical_safe_float
safe_decimal = _canonical_safe_decimal


class ReportCompanyNameTranslations(Protocol):
    report_company_name_unknown: str


def build_main_report_headline_context(
    *,
    response: object,
    report_reference: ReportReferenceContext,
    translations: ReportCompanyNameTranslations,
    latest_year: object,
    enterprise_value_low: Decimal,
    enterprise_value_mid: Decimal,
    enterprise_value_high: Decimal,
    equity_value_low: Decimal | None,
    equity_value: Decimal | None,
    equity_value_high: Decimal | None,
    dcf_ineligible_scenario: object,
    ev_band_is_meaningful: bool,
    equity_band_is_meaningful: bool,
    thin_benchmark_force_range: bool,
    method_divergence_caveat: object | None,
    step_data: Mapping[str, object],
    engine_synthesis_equity_anchored: bool,
    aligned_recommended_asking_price: Decimal | None,
    asking_price_realigned: bool,
) -> JsonMap:
    """Build the report identity and headline valuation fields."""

    ev_band_source = step_data.get("_ev_band_source")
    return {
        "report_id": report_reference.report_id,
        "report_id_display": report_reference.report_id_display,
        "discussion_signoff_line": report_reference.discussion_signoff_line,
        "company_name": getattr(response, "company_name", None)
        or translations.report_company_name_unknown,
        "valuation_date": report_reference.valuation_date,
        "valuation_expiry_date": report_reference.valuation_expiry_date,
        "current_year": latest_year,
        "latest_year": latest_year,
        "valuation": to_float(enterprise_value_mid),
        "valuation_low": to_float(enterprise_value_low),
        "valuation_high": to_float(enterprise_value_high),
        "dcf_ineligible_scenario": dcf_ineligible_scenario,
        "equity_value": to_float(equity_value) if equity_value is not None else None,
        "equity_value_low": to_float(equity_value_low) if equity_value_low is not None else None,
        "equity_value_high": to_float(equity_value_high) if equity_value_high is not None else None,
        "valuation_band_is_meaningful": ev_band_is_meaningful,
        "equity_value_band_is_meaningful": equity_band_is_meaningful,
        "thin_benchmark_force_range": thin_benchmark_force_range,
        "method_divergence_caveat": method_divergence_caveat,
        "ev_band_source": ev_band_source,
        "ev_sourced_from_engine_equity": (
            ev_band_source == "engine_equity_band" or engine_synthesis_equity_anchored
        ),
        "recommended_asking_price": (
            to_float(aligned_recommended_asking_price)
            if aligned_recommended_asking_price is not None
            else None
        ),
        "recommended_asking_price_realigned": asking_price_realigned,
        "recommended_asking_multiple": to_float(
            safe_decimal(getattr(response, "recommended_asking_multiple", None))
        ),
    }


def build_main_report_multiple_context(
    *,
    response: object,
    multiple_context: Mapping[str, object],
    implied_ebitda_multiple_context: Mapping[str, object],
    formula_metric_value: Decimal,
    display_multiple: Decimal,
    pre_synthesis_multiple: Decimal,
    applied_multiple_rail: str,
    base_multiple: Decimal,
    multiple_low: Decimal,
    multiple_high: Decimal,
    total_discount: Decimal,
    has_benchmark_reference_multiple: bool,
    show_benchmark_reference_without_table: bool,
    show_size_discount_skipped_note: bool,
    locale: str = "nl",
) -> JsonMap:
    """Build multiple-method fields used by report templates."""

    metric_type = multiple_context["metric_type"]
    return {
        "applied_multiple": to_float(display_multiple),
        # Which rail applied_multiple / multiple_low / multiple_high sit on.
        # The alignment guard keeps all three on ONE rail; this key tells the
        # renderers whether that rail is before or after the Step 4/5/6
        # discounts, so a pre-discount multiple can never print unlabelled.
        "applied_multiple_rail": applied_multiple_rail,
        "multiple_is_pre_discount": applied_multiple_rail == "pre_discount_market_ev",
        "pre_synthesis_multiple": to_float(pre_synthesis_multiple),
        "base_multiple": to_float(base_multiple),
        "multiple_low": to_float(multiple_low),
        "multiple_high": to_float(multiple_high),
        "total_discount": to_float(total_discount),
        "multiple_metric_type": metric_type,
        "is_revenue_multiple_method": metric_type == "REVENUE",
        **implied_ebitda_multiple_context,
        "valuation_basis_value": to_float(formula_metric_value),
        "multiple_display_label": multiple_context["multiple_display_label"],
        "benchmark_multiple_label": multiple_context["benchmark_multiple_label"],
        "benchmark_multiple_mid": to_float(multiple_context["benchmark_multiple_mid"]),
        "benchmark_multiple_low": to_float(multiple_context["benchmark_multiple_low"]),
        "benchmark_multiple_high": to_float(multiple_context["benchmark_multiple_high"]),
        "multiple_source": multiple_context["multiple_source"],
        "is_hybrid_component_multiple": multiple_context["is_hybrid_component_multiple"],
        "has_benchmark_reference_multiple": has_benchmark_reference_multiple,
        "show_benchmark_reference_without_table": show_benchmark_reference_without_table,
        "show_size_discount_skipped_note": show_size_discount_skipped_note,
        **build_advisor_multiple_transparency_context(response, locale=locale),
    }
