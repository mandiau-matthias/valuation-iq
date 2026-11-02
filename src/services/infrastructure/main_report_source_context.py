"""Source-fact preparation for main report aggregation."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Optional, Protocol

from src.services.infrastructure.translations import get_translations, normalize_report_locale
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.reports.company_registry_context import build_kbo_company_data
from src.services.reports.consolidation_report_context import build_consolidation_report_context
from src.services.reports.implied_multiple_context import build_implied_ebitda_multiple_context
from src.services.reports.official_financials_context import build_official_financials_context
from src.services.reports.protocol_adapter import coerce_json_object
from src.services.reports.report_benchmark_anchor_context import backfill_missing_benchmark_anchor
from src.services.reports.report_benchmark_context import build_industry_benchmarks
from src.services.reports.report_benchmark_context import (
    extract_calibration_data_from_request as resolve_calibration_data_from_request,
)
from src.services.reports.report_identity_context import (
    get_report_business_type_id,
    get_report_nace_code,
    get_report_registration_number,
)
from src.services.reports.report_value_admission import (
    admitted_optional_equity_band,
    admitted_point_or_band,
)

ValuationResponse = ValuationResponseProtocol
ValuationRequest = ValuationRequestProtocol

_MISSING = object()


def _first_present_attr(obj: object, *names: str) -> object | None:
    """Return the first non-None attribute, preserving explicit zeros."""
    for name in names:
        value = getattr(obj, name, _MISSING)
        if value is not _MISSING and value is not None:
            return value
    return None


class MainReportSourceAggregator(Protocol):
    logger: object

    def _country_code_from_request(self, request): ...

    def _extract_step_data(self, response, locale, translations, request): ...

    def _is_generic_sector_label(self, value): ...

    def _extract_ebitda(self, response, request, step_data): ...

    def _get_revenue(self, response, request): ...

    def _resolve_display_current_year(self, request, response): ...

    def _build_multi_year_data(self, request, locale, translations): ...

    def _get_latest_year_normalized_for_display(
        self, request, reported_ebitda, multi_year_data
    ): ...

    def _compute_explicit_total_adjustments(
        self, request, response, reported_ebitda, latest_year_normalized_ebitda
    ): ...

    def _summarize_proposed_adjustments(self, request, response): ...

    def _extract_multiple_context(
        self, *, response, step_data, industry_benchmarks, locale, t, request
    ): ...

    def _extract_enterprise_value_range(
        self, response, step_data, equity_value_low, equity_value, equity_value_high
    ): ...


@dataclass
class MainReportSourceContext:
    """Prepared upstream facts for main report aggregation."""

    report_locale: Literal["nl", "en", "fr"]
    report_country: Optional[str]
    translations: object
    step_data: dict[str, object]
    business_type_id: Optional[str]
    nace_code: Optional[str]
    industry_benchmarks: dict[str, object]
    registration_number: Optional[str]
    kbo_data: object
    official_financials: object
    sustainable_ebitda: Decimal
    reported_ebitda: Decimal
    revenue_value: Decimal
    equity_value_low: Decimal | None
    equity_value: Decimal | None
    equity_value_high: Decimal | None
    latest_year: object
    multi_year_data: list[dict[str, object]]
    consolidation_report_context: dict[str, object]
    latest_year_normalized_ebitda: Decimal
    total_adjustments: Decimal
    proposed_adjustments_total: Decimal
    proposed_adjustments_count: int
    multiple_context: dict[str, object]
    enterprise_value_low: Decimal
    enterprise_value_mid: Decimal
    enterprise_value_high: Decimal
    applied_multiple: object
    multiple_low: object
    multiple_high: object
    base_multiple: object
    implied_ebitda_multiple_context: dict[str, object]


def build_main_report_source_context(
    aggregator: MainReportSourceAggregator,
    response: ValuationResponse,
    request: Optional[ValuationRequest],
    locale: str,
) -> MainReportSourceContext:
    """Prepare source facts before valuation alignment and context assembly."""
    report_locale: Literal["nl", "en", "fr"] = normalize_report_locale(locale)
    report_country = aggregator._country_code_from_request(request)
    translations = get_translations(report_locale, country_code=report_country)

    step_data = aggregator._extract_step_data(response, locale, translations, request)
    business_type_id = get_report_business_type_id(response, request)
    nace_code = get_report_nace_code(response, request)
    calibration_data = resolve_calibration_data_from_request(request)
    canonical_run = getattr(response, "valuation_run", None)
    industry_benchmarks = build_industry_benchmarks(
        business_type_id=business_type_id,
        business_type_mix=getattr(request, "business_type_mix", None),
        nace_code=nace_code,
        response=response,
        calibration_data=calibration_data,
        is_generic_sector_label=aggregator._is_generic_sector_label,
        logger=aggregator.logger,
        country_code=report_country,
        allow_mutable_anchor_fallbacks=canonical_run is None,
    )

    registration_number = get_report_registration_number(response, request)
    kbo_data = build_kbo_company_data(
        registration_number=registration_number,
        response=response,
        request=request,
        logger=aggregator.logger,
    )
    official_financials = build_official_financials_context(response, request)

    sustainable_ebitda, reported_ebitda, _ = aggregator._extract_ebitda(
        response, request, step_data
    )
    revenue_value = aggregator._get_revenue(response, request)
    equity_values = (
        _first_present_attr(response, "equity_value_low", "valuation_min"),
        _first_present_attr(response, "equity_value_mid", "valuation_midpoint"),
        _first_present_attr(response, "equity_value_high", "valuation_max"),
    )
    equity_value_low, equity_value, equity_value_high = (
        admitted_optional_equity_band(*equity_values)
        if all(value is None for value in equity_values)
        else admitted_point_or_band(*equity_values)
    )

    latest_year = aggregator._resolve_display_current_year(request, response)
    multi_year_data = aggregator._build_multi_year_data(request, locale, translations)
    consolidation_report_context = build_consolidation_report_context(
        coerce_json_object(getattr(response, "holdings_consolidation", None)),
        locale=locale,
    )

    latest_year_normalized_ebitda = aggregator._get_latest_year_normalized_for_display(
        request, reported_ebitda, multi_year_data
    )
    total_adjustments = aggregator._compute_explicit_total_adjustments(
        request, response, reported_ebitda, latest_year_normalized_ebitda
    )
    proposed_adjustments_total, proposed_adjustments_count = (
        aggregator._summarize_proposed_adjustments(request, response)
    )

    multiple_context = aggregator._extract_multiple_context(
        response=response,
        step_data=step_data,
        industry_benchmarks=industry_benchmarks,
        locale=locale,
        t=translations,
        request=request,
    )
    if canonical_run is None:
        backfill_missing_benchmark_anchor(
            multiple_context,
            business_type_id=business_type_id,
            country_code=report_country or "BE",
        )
    enterprise_value_low, enterprise_value_mid, enterprise_value_high = (
        aggregator._extract_enterprise_value_range(
            response, step_data, equity_value_low, equity_value, equity_value_high
        )
    )

    applied_multiple = multiple_context["applied_multiple"]
    multiple_low = multiple_context["multiple_low"]
    multiple_high = multiple_context["multiple_high"]
    base_multiple = multiple_context["base_multiple"]
    implied_ebitda_multiple_context = build_implied_ebitda_multiple_context(
        metric_type=multiple_context["metric_type"],
        enterprise_value_mid=enterprise_value_mid,
        sustainable_ebitda=sustainable_ebitda,
        revenue_value=revenue_value,
    )

    return MainReportSourceContext(
        report_locale=report_locale,
        report_country=report_country,
        translations=translations,
        step_data=step_data,
        business_type_id=business_type_id,
        nace_code=nace_code,
        industry_benchmarks=industry_benchmarks,
        registration_number=registration_number,
        kbo_data=kbo_data,
        official_financials=official_financials,
        sustainable_ebitda=sustainable_ebitda,
        reported_ebitda=reported_ebitda,
        revenue_value=revenue_value,
        equity_value_low=equity_value_low,
        equity_value=equity_value,
        equity_value_high=equity_value_high,
        latest_year=latest_year,
        multi_year_data=multi_year_data,
        consolidation_report_context=consolidation_report_context,
        latest_year_normalized_ebitda=latest_year_normalized_ebitda,
        total_adjustments=total_adjustments,
        proposed_adjustments_total=proposed_adjustments_total,
        proposed_adjustments_count=proposed_adjustments_count,
        multiple_context=multiple_context,
        enterprise_value_low=enterprise_value_low,
        enterprise_value_mid=enterprise_value_mid,
        enterprise_value_high=enterprise_value_high,
        applied_multiple=applied_multiple,
        multiple_low=multiple_low,
        multiple_high=multiple_high,
        base_multiple=base_multiple,
        implied_ebitda_multiple_context=implied_ebitda_multiple_context,
    )
