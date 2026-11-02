"""Accountant-view transformation helpers for the report transformer facade."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from src.services.infrastructure.exceptions import DataTransformationError, MissingDataError
from src.services.infrastructure.report_confidence import (
    confidence_score_fraction,
    confidence_score_percent,
)
from src.services.infrastructure.step_data_builder import (
    build_12_step_calculation_journey,
    get_step_output,
)
from src.services.infrastructure.translations import get_translations, normalize_report_locale
from src.services.infrastructure.waterfall_builder import build_valuation_waterfall
from src.utils.decimal_helpers import pin_band_monotone, to_decimal
from src.utils.exceptions import APIError
from src.utils.logging import get_logger

from .accountant_view_business import (
    build_business_type_characteristics,
    build_business_type_context,
)

if TYPE_CHECKING:
    from src.services.interfaces.request_response_protocol import (
        ValuationRequestProtocol,
        ValuationResponseProtocol,
    )


logger = get_logger(__name__)

TemplateData = dict[str, object]
Sections = dict[str, object]

REQUIRED_SECTION_KEYS = (
    "description_of_assignment",
    "information_sources",
    "executive_summary",
    "company_overview",
    "financial_analysis",
    "valuation_methodologies",
    "valuation_conclusion",
    "appendices",
)

_SECTION_ALIASES = {
    "description_of_assignment": "description",
    "information_sources": "information_sources",
    "executive_summary": "executive_summary",
    "company_overview": "company_overview",
    "financial_analysis": "financial_analysis",
    "valuation_methodologies": "valuation_methodology",
    "valuation_conclusion": "valuation_conclusion",
    "appendices": "appendices",
}


@dataclass(frozen=True)
class ReportTranslationContext:
    locale: str
    translations: object


def validate_transform_inputs(
    response: ValuationResponseProtocol | None,
    request: ValuationRequestProtocol | None,
) -> None:
    """Validate the public report transformation contract."""
    missing_fields = []
    if not response:
        missing_fields.append("response")
    if not request:
        missing_fields.append("request")
    if missing_fields:
        raise MissingDataError(
            "Both response and request are required",
            missing_fields=missing_fields,
        )

    if not getattr(response, "company_name", None):
        raise MissingDataError(
            "ValuationResponse missing required field: company_name",
            missing_fields=["company_name"],
        )


def build_translation_context(request: ValuationRequestProtocol) -> ReportTranslationContext:
    locale = normalize_report_locale(getattr(request, "locale", None) or "nl")
    country_code = str(getattr(request, "country_code", None) or "BE").strip().upper() or "BE"
    return ReportTranslationContext(
        locale=locale,
        translations=get_translations(locale, country_code=country_code),
    )


def transform_report_sections(
    transformers: Mapping[str, object],
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    translation_context: ReportTranslationContext,
) -> Sections:
    sections: Sections = {}
    for section_name, transformer in transformers.items():
        sections[section_name] = _transform_section(
            section_name=section_name,
            transformer=transformer,
            response=response,
            request=request,
            translation_context=translation_context,
        )
    return sections


def log_transform_start(response: ValuationResponseProtocol) -> None:
    logger.info(
        "Transforming valuation response for Accountant View report",
        extra={
            "company_name": getattr(response, "company_name", None),
            "valuation_id": getattr(response, "valuation_id", None),
            "valuation_date": getattr(response, "valuation_date", None),
            "equity_value_mid": getattr(response, "equity_value_mid", None),
            "confidence_score": getattr(response, "confidence_score", None),
        },
    )


def log_transform_complete(
    response: ValuationResponseProtocol,
    duration_seconds: float,
    transformed_sections: Sections,
    template_data: TemplateData,
    missing_sections: list[str],
) -> None:
    logger.info(
        "Valuation response transformation complete",
        extra={
            "company_name": getattr(response, "company_name", None),
            "valuation_id": getattr(response, "valuation_id", None),
            "duration_seconds": round(duration_seconds, 3),
            "sections_transformed": len(transformed_sections),
            "missing_sections": missing_sections if missing_sections else None,
            "top_level_keys": len(template_data),
            "has_executive_summary": "executive_summary" in template_data,
            "has_financial_analysis": "financial_analysis" in template_data,
            "has_valuation_conclusion": "valuation_conclusion" in template_data,
        },
    )


def _transform_section(
    section_name: str,
    transformer: object,
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    translation_context: ReportTranslationContext,
) -> TemplateData:
    try:
        transform = getattr(transformer, "transform")
        section_data = transform(
            response,
            request,
            **_section_translation_kwargs(transform, translation_context),
        )
        return _coerce_section_data(section_name, section_data, response)
    except DataTransformationError as exc:
        logger.error("Failed to transform %s section: %s", section_name, exc, exc_info=True)
        raise
    except APIError as exc:
        logger.error(
            "Unexpected error transforming %s section: %s", section_name, exc, exc_info=True
        )
        raise DataTransformationError(
            f"Unexpected error transforming {section_name} section: {exc}",
            company_name=getattr(response, "company_name", None),
        ) from exc
    except Exception as exc:
        logger.error(
            "Unexpected error transforming %s section: %s",
            section_name,
            exc,
            extra={
                "company_name": getattr(response, "company_name", None),
                "section_name": section_name,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise DataTransformationError(
            f"Unexpected error transforming {section_name} section: {exc}",
            company_name=getattr(response, "company_name", None),
        ) from exc


def _section_translation_kwargs(
    transform: object,
    translation_context: ReportTranslationContext,
) -> TemplateData:
    parameters = inspect.signature(transform).parameters
    kwargs: TemplateData = {}
    if "t" in parameters:
        kwargs["t"] = translation_context.translations
    if "locale" in parameters:
        kwargs["locale"] = translation_context.locale
    return kwargs


def _coerce_section_data(
    section_name: str,
    section_data: object,
    response: ValuationResponseProtocol,
) -> TemplateData:
    if section_data is None:
        logger.warning(
            "Section transformer returned None for %s",
            section_name,
            extra={
                "company_name": getattr(response, "company_name", None),
                "section_name": section_name,
            },
        )
        return {}

    if isinstance(section_data, dict):
        return section_data

    logger.warning(
        "Section transformer returned non-dict for %s, converting",
        section_name,
        extra={
            "company_name": getattr(response, "company_name", None),
            "section_name": section_name,
            "section_data_type": type(section_data).__name__,
        },
    )
    if hasattr(section_data, "__dict__"):
        return vars(section_data)
    return {}


def build_base_template_data(
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    transformed_sections: Sections,
    basic_builder: object,
    translation_context: ReportTranslationContext,
) -> TemplateData:
    years_of_data = len(request.historical_years_data) if request.historical_years_data else 0
    confidence_score_pct = confidence_score_percent(response.confidence_score)
    business_context = build_business_type_context(request, response)
    business_type_characteristics = build_business_type_characteristics(
        business_context.get("business_type_id"),
        getattr(response, "company_name", None),
    )
    pinned_low, pinned_mid, pinned_high = pin_band_monotone(
        response.equity_value_low,
        response.equity_value_mid,
        response.equity_value_high,
    )

    template_data = _build_identity_and_value_data(
        response=response,
        request=request,
        translation_context=translation_context,
        confidence_score_pct=confidence_score_pct,
        pinned_values=(pinned_low, pinned_mid, pinned_high),
    )
    template_data.update(_build_section_aliases(transformed_sections))
    template_data.update(
        _build_report_quality_data(
            request=request,
            years_of_data=years_of_data,
            confidence_score_pct=confidence_score_pct,
        )
    )
    template_data.update(_build_business_template_data(response, business_context, basic_builder))
    template_data["business_type_characteristics"] = business_type_characteristics
    template_data.update(_build_financial_template_data(request, response))
    template_data.update(_build_methodology_selection_data(response))
    template_data["calculation_steps"] = []
    return template_data


def _build_identity_and_value_data(
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    translation_context: ReportTranslationContext,
    confidence_score_pct: Decimal | None,
    pinned_values: tuple[object, object, object],
) -> TemplateData:
    pinned_low, pinned_mid, pinned_high = pinned_values
    return {
        "company_name": response.company_name,
        "valuation_date": getattr(response, "valuation_date", None),
        "valuation_id": getattr(response, "valuation_id", None),
        "industry": extract_industry(request),
        "valuation_range": {
            "low": pinned_low,
            "mid": pinned_mid,
            "high": pinned_high,
            "confidence": confidence_score_fraction(response.confidence_score),
        },
        "equity_value_low": pinned_low,
        "equity_value_mid": pinned_mid,
        "equity_value_high": pinned_high,
        "recommended_asking_price": getattr(response, "recommended_asking_price", None),
        "methodology": resolve_report_methodology(response, translation_context),
        "confidence_score": confidence_score_pct,
        "confidence_level": _confidence_level(response),
        "report_classification": "Business Valuation Report",
        "multiple_pipeline": getattr(response, "multiple_pipeline", None),
        "range_methodology": getattr(response, "range_methodology", None),
        "valuation_range_chart": None,
        "historical_performance_chart": None,
        "step_2_result": get_step_output(response, 2),
        "current_year_data": getattr(request, "current_year_data", None),
        "multiples_valuation": getattr(response, "multiples_valuation", None),
    }


def _build_section_aliases(transformed_sections: Sections) -> TemplateData:
    return {
        alias: transformed_sections.get(section_key) or {}
        for alias, section_key in _SECTION_ALIASES.items()
    }


def _build_report_quality_data(
    request: ValuationRequestProtocol,
    years_of_data: int,
    confidence_score_pct: Decimal | None,
) -> TemplateData:
    return {
        "years_of_data": years_of_data,
        "data_limitation_disclosure": build_data_limitation_disclosure(
            years_of_data,
            confidence_score_pct,
        ),
        "negative_ebitda_strategy": determine_negative_ebitda_strategy(request),
    }


def _build_business_template_data(
    response: ValuationResponseProtocol,
    business_context: TemplateData,
    basic_builder: object,
) -> TemplateData:
    return {
        **business_context,
        "business_type_benchmarks": basic_builder.extract_business_type_benchmarks(response),
        "step_2_source": basic_builder.extract_step_source_metadata(response, 2),
        "step_3_source": basic_builder.extract_step_source_metadata(response, 3),
        "step_5_source": basic_builder.extract_step_source_metadata(response, 5),
        "step_6_source": basic_builder.extract_step_source_metadata(response, 6),
        "step_2_7_source": basic_builder.extract_step_source_metadata(response, 2.7),
    }


def _build_financial_template_data(
    request: ValuationRequestProtocol,
    response: ValuationResponseProtocol,
) -> TemplateData:
    return {
        "revenue": extract_revenue(request),
        "step_1_inputs": extract_step_1_inputs(request),
        "ebitda": extract_ebitda_for_template(response, request),
    }


def _build_methodology_selection_data(response: ValuationResponseProtocol) -> TemplateData:
    methodology_selection = getattr(response, "methodology_selection", None)
    return {
        "methodology_selection": {
            "dcf_weight": getattr(response, "dcf_weight", None) or 0.0,
            "multiples_weight": getattr(response, "multiples_weight", None) or 1.0,
            "methodology_rationale": (
                getattr(
                    methodology_selection,
                    "methodology_rationale",
                    None,
                )
                if methodology_selection
                else None
            ),
        }
    }


def build_data_limitation_disclosure(
    years_of_data: int,
    confidence_score_pct: Decimal | None,
) -> TemplateData | None:
    if years_of_data >= 3:
        return None
    return {
        "message": (
            f"Only {years_of_data} year(s) of historical data available. "
            "This limits trend analysis and normalization capabilities."
        ),
        "impacts": [
            "Limited ability to identify historical trends",
            "Reduced confidence in normalized metrics",
            "Greater reliance on industry benchmarks",
        ],
        "confidence_cap": (
            min(confidence_score_pct, Decimal("75")) if confidence_score_pct is not None else None
        ),
        "confidence_cap_reason": "Limited historical data constrains confidence score",
    }


def determine_negative_ebitda_strategy(request: ValuationRequestProtocol) -> str | None:
    current_year_data = getattr(request, "current_year_data", None)
    if not current_year_data:
        return None

    ebitda = _decimal_or_none(getattr(current_year_data, "ebitda", None))
    revenue = _decimal_or_none(getattr(current_year_data, "revenue", None))
    if ebitda is None or ebitda >= 0:
        return None
    if revenue is not None and revenue > 0:
        return "revenue_multiples"
    return "high_risk"


def resolve_report_methodology(
    response: ValuationResponseProtocol,
    translation_context: ReportTranslationContext,
) -> object:
    if getattr(response, "methodology", None):
        return response.methodology

    dcf_weight = getattr(response, "dcf_weight", 0.0)
    multiples_weight = getattr(response, "multiples_weight", 1.0)
    if dcf_weight > 0.5:
        return getattr(translation_context.translations, "transformer_method_label_dcf")
    if multiples_weight > 0.5:
        return getattr(
            translation_context.translations, "transformer_method_label_market_multiples"
        )
    return getattr(translation_context.translations, "transformer_method_label_hybrid")


def extract_industry(request: ValuationRequestProtocol) -> str | None:
    industry = getattr(request, "industry", None)
    if not industry:
        return None
    if hasattr(industry, "value"):
        return industry.value
    return str(industry)


def extract_revenue(request: ValuationRequestProtocol) -> object:
    current_year_data = getattr(request, "current_year_data", None)
    revenue = getattr(current_year_data, "revenue", None) if current_year_data else None
    if revenue is None:
        revenue = getattr(request, "revenue", None)
    return revenue


def extract_step_1_inputs(request: ValuationRequestProtocol) -> TemplateData | None:
    current_year_data = getattr(request, "current_year_data", None)
    if current_year_data:
        return {
            "revenue": getattr(current_year_data, "revenue", 0),
            "ebitda": getattr(current_year_data, "ebitda", 0),
        }

    financials = getattr(request, "financials", None)
    if financials:
        return {
            "revenue": getattr(financials, "revenue", 0),
            "ebitda": getattr(financials, "ebitda", 0),
        }
    return None


def populate_calculation_steps(
    template_data: TemplateData,
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
) -> None:
    try:
        calculation_steps = build_12_step_calculation_journey(response, request)
        if calculation_steps and len(calculation_steps) == 12:
            template_data["calculation_steps"] = calculation_steps
            return
        logger.warning(
            "Calculation steps not available for appendices, using empty list",
            extra={"company_name": getattr(response, "company_name", None)},
        )
    except Exception as exc:
        logger.warning(
            "Failed to build calculation steps for appendices",
            extra={"company_name": getattr(response, "company_name", None), "error": str(exc)},
        )
    template_data["calculation_steps"] = []


def populate_valuation_waterfall(
    template_data: TemplateData,
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
) -> None:
    try:
        if getattr(response, "multiples_valuation", None):
            waterfall_data = build_valuation_waterfall(response, request)
            template_data["valuation_waterfall"] = waterfall_data
            logger.debug(
                "Valuation waterfall built for accountant view",
                extra={
                    "company_name": getattr(response, "company_name", None),
                    "has_waterfall": waterfall_data is not None,
                    "steps_count": (
                        len(waterfall_data.get("steps", []))
                        if isinstance(waterfall_data, dict)
                        else 0
                    ),
                },
            )
            return
        logger.warning(
            "No multiples_valuation available, valuation waterfall set to None",
            extra={"company_name": getattr(response, "company_name", None)},
        )
    except Exception as exc:
        logger.warning(
            "Failed to build valuation waterfall for accountant view",
            extra={"company_name": getattr(response, "company_name", None), "error": str(exc)},
        )
    template_data["valuation_waterfall"] = None


def extract_ebitda_for_template(
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
) -> object:
    current_year_data = getattr(request, "current_year_data", None)
    if current_year_data and hasattr(current_year_data, "ebitda"):
        return current_year_data.ebitda

    multiples_valuation = getattr(response, "multiples_valuation", None)
    if multiples_valuation and hasattr(multiples_valuation, "adjusted_ebitda"):
        return multiples_valuation.adjusted_ebitda
    return None


def ensure_required_sections(template_data: TemplateData, company_name: object) -> list[str]:
    missing_sections = []
    for section_key in REQUIRED_SECTION_KEYS:
        if section_key not in template_data or template_data[section_key] is None:
            missing_sections.append(section_key)
            template_data[section_key] = {}

    if missing_sections:
        logger.warning(
            "Some required sections missing from template data, using empty fallbacks",
            extra={"company_name": company_name, "missing_sections": missing_sections},
        )
    else:
        logger.debug(
            "All required sections present in template data",
            extra={"company_name": company_name, "sections_count": len(REQUIRED_SECTION_KEYS)},
        )
    return missing_sections


def _confidence_level(response: ValuationResponseProtocol) -> str:
    confidence = getattr(response, "overall_confidence", None)
    return str(confidence.value if hasattr(confidence, "value") else confidence)


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return to_decimal(value)
    except (TypeError, ValueError):
        return None
