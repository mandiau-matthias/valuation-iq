"""ValuationIQ service re-exports.

Keep this package initializer side-effect-light. Importing a leaf module such
as ``src.services.reports.report_hash_lock`` must not eagerly initialize core,
market, database, AI, or template services.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    # Core services
    "ValuationMCPService": ("src.services.core", "ValuationMCPService"),
    "get_mcp_service": ("src.services.core", "get_mcp_service"),
    "ValuationQualityScorer": ("src.services.core", "ValuationQualityScorer"),
    "get_quality_scorer": ("src.services.core", "get_quality_scorer"),
    "ValuationReportService": ("src.services.core", "ValuationReportService"),
    # Triage services
    "GapAnalysisService": ("src.services.triage", "GapAnalysisService"),
    # Business intelligence services
    "BusinessIntelligenceService": (
        "src.services.business_intelligence",
        "BusinessIntelligenceService",
    ),
    "BusinessTypeIntegrationEngine": (
        "src.services.business_intelligence",
        "BusinessTypeIntegrationEngine",
    ),
    "IntelligentMethodologySelector": (
        "src.services.business_intelligence",
        "IntelligentMethodologySelector",
    ),
    # Market services
    "MarketDataCacheService": ("src.services.market", "MarketDataCacheService"),
    "CacheDataType": ("src.services.market", "CacheDataType"),
    "MarketDataIntegrationService": ("src.services.market", "MarketDataIntegrationService"),
    "CompanyLookupService": ("src.services.market", "CompanyLookupService"),
    # Infrastructure services
    "get_ai_service": ("src.services.infrastructure", "get_ai_service"),
    "IndustryInference": ("src.services.infrastructure", "IndustryInference"),
    "get_template_service": ("src.services.infrastructure", "get_template_service"),
    "DocumentParser": ("src.services.infrastructure", "DocumentParser"),
    # Monitoring services
    "CostMonitor": ("src.services.monitoring", "CostMonitor"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
