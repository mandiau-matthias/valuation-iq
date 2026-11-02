"""Business-type enrichment helpers for accountant-view report data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.services.interfaces.request_response_protocol import (
        ValuationRequestProtocol,
        ValuationResponseProtocol,
    )


logger = get_logger(__name__)

TemplateData = dict[str, object]


def build_business_type_context(
    request: ValuationRequestProtocol,
    response: ValuationResponseProtocol,
) -> TemplateData:
    business_type = getattr(request, "business_type", None)
    business_type_id = getattr(request, "business_type_id", None)
    business_context: TemplateData = {
        "business_type": business_type,
        "business_type_id": business_type_id,
        "business_type_icon": "🏢",
    }

    if not business_type_id:
        return business_context

    return _enrich_business_type_context(
        business_context=business_context,
        valuation_preferences=getattr(request, "valuation_preferences", None),
        company_name=getattr(response, "company_name", None),
    )


def _enrich_business_type_context(
    business_context: TemplateData,
    valuation_preferences: object,
    company_name: object,
) -> TemplateData:
    business_type_id = business_context.get("business_type_id")
    try:
        from src.services.business_type_metadata_service import get_business_type_metadata_service

        metadata_service = get_business_type_metadata_service()
        calibration_data = (
            valuation_preferences if isinstance(valuation_preferences, dict) else None
        )
        metadata = metadata_service.get_business_type_metadata(calibration_data)
        if metadata and metadata.id:
            if metadata.title:
                business_context["business_type"] = metadata.title
            if getattr(metadata, "icon", None):
                business_context["business_type_icon"] = metadata.icon
        if not business_context.get("business_type"):
            business_context["business_type"] = _business_type_fallback_title(business_type_id)
    except Exception as exc:
        if not business_context.get("business_type"):
            business_context["business_type"] = _business_type_fallback_title(business_type_id)
        logger.warning(
            "Error looking up business type metadata, using fallback",
            extra={
                "business_type_id": business_type_id,
                "fallback_display_name": business_context.get("business_type"),
                "error": str(exc),
                "company_name": company_name,
            },
        )
    return business_context


def build_business_type_characteristics(
    business_type_id: object,
    company_name: object = None,
) -> TemplateData:
    if not business_type_id:
        return _default_business_type_characteristics()

    try:
        from src.services.business_intelligence.analysis.business_type_analyzer import (
            BusinessTypeAnalyzer,
        )

        analyzer = BusinessTypeAnalyzer()
        characteristics = analyzer.get_business_type_characteristics(str(business_type_id))
        return {
            "multiples_preference": _multiples_preference(characteristics),
            "owner_dependency_impact": _owner_dependency_impact(str(business_type_id)),
            "typical_ebitda_margin_median": _typical_ebitda_margin(str(business_type_id)),
            "business_type": getattr(characteristics, "business_type", business_type_id),
            "category": getattr(characteristics, "category", None),
            "optimal_methodology": str(
                getattr(characteristics, "optimal_methodology", "MULTIPLES")
            ),
        }
    except Exception as exc:
        logger.warning(
            "Failed to get business_type_characteristics, using defaults",
            extra={
                "business_type_id": business_type_id,
                "error": str(exc),
                "company_name": company_name,
            },
        )
        return _default_business_type_characteristics()


def _multiples_preference(characteristics: object) -> float:
    optimal_method = str(getattr(characteristics, "optimal_methodology", "")).lower()
    if "multiple" in optimal_method or "market" in optimal_method:
        return 0.90
    if "dcf" in optimal_method or "cash" in optimal_method:
        return 0.60
    if "hybrid" in optimal_method:
        return 0.75
    return 0.85


def _owner_dependency_impact(business_type_id: str) -> float:
    if business_type_id in {"restaurant", "cafe", "coffee_shop", "brewery"}:
        return 0.65
    if business_type_id in {"saas", "software", "ecommerce"}:
        return 0.35
    return 0.5


def _typical_ebitda_margin(business_type_id: str) -> float:
    if business_type_id == "restaurant":
        return 0.10
    if business_type_id in {"saas", "software"}:
        return 0.25
    return 0.15


def _default_business_type_characteristics() -> TemplateData:
    return {
        "multiples_preference": 0.85,
        "owner_dependency_impact": 0.5,
        "typical_ebitda_margin_median": 0.15,
    }


def _business_type_fallback_title(business_type_id: object) -> str | None:
    if business_type_id is None:
        return None
    return str(business_type_id).replace("_", " ").title()
