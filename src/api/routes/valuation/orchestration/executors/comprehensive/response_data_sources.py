"""Data-source provenance builder for comprehensive valuation responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Protocol

from src.api.routes.valuation.benchmark_contract_utils import (
    as_mapping,
    benchmark_contract_source_key,
    extract_resolved_benchmark_contract,
    is_resolved_benchmark_contract,
)
from src.api.schemas import ValuationRequest


class LoggerLike(Protocol):
    def debug(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class TitanProvenanceContext:
    ev_ebitda_multiple: object
    ev_revenue_multiple: object
    pe_ratio: object
    preferences: dict[str, object]
    benchmarks: dict[str, object]
    benchmark_contract: object
    benchmark_resolved: bool
    business_type_id: object
    industry: object
    official_financials: object
    official_verification_badge: object

    @property
    def has_multiples(self) -> bool:
        return bool(self.ev_ebitda_multiple or self.ev_revenue_multiple)

    @property
    def has_preferences(self) -> bool:
        return bool(self.preferences)

    @property
    def has_benchmarks(self) -> bool:
        return bool(self.benchmarks)


def _extract_titan_context(request: ValuationRequest) -> TitanProvenanceContext:
    titan_metadata = as_mapping(getattr(request, "multiples_metadata", None))
    benchmark_contract = extract_resolved_benchmark_contract(titan_metadata) or (
        titan_metadata.get("benchmark_contract") or titan_metadata.get("benchmarkContract")
    )
    return TitanProvenanceContext(
        ev_ebitda_multiple=getattr(request, "ev_ebitda_multiple", None),
        ev_revenue_multiple=getattr(request, "ev_revenue_multiple", None),
        pe_ratio=getattr(request, "pe_ratio", None),
        preferences=as_mapping(getattr(request, "valuation_preferences", None)),
        benchmarks=as_mapping(getattr(request, "industry_benchmarks", None)),
        benchmark_contract=benchmark_contract,
        benchmark_resolved=is_resolved_benchmark_contract(benchmark_contract),
        business_type_id=getattr(request, "business_type_id", None),
        industry=getattr(request, "industry", None),
        official_financials=getattr(request, "official_financials", None),
        official_verification_badge=getattr(request, "official_verification_badge", None),
    )


def _empty_data_sources() -> dict[str, object]:
    return {
        "summary": {
            "primary_source": "unknown",
            "timestamp": date.today().isoformat(),
        },
        "multiples": {},
        "weights": {},
        "benchmarks": {},
        "industry": {},
        "official_financials": {},
    }


def _multiples_source(
    context: TitanProvenanceContext,
    detailed_results: dict[str, object],
) -> dict[str, object]:
    if context.has_multiples:
        resolved_source = (
            benchmark_contract_source_key(context.benchmark_contract)
            if context.benchmark_resolved
            else "TITAN_MULTIPLES_WITHOUT_RESOLVED_CONTRACT"
        )
        return {
            "source": resolved_source,
            "description": (
                "Resolved benchmark contract via Titan"
                if context.benchmark_resolved
                else "Titan supplied multiples without a resolved benchmark contract; "
                "concrete business-type valuations should fail closed before publication"
            ),
            "benchmark_contract": (
                context.benchmark_contract if context.benchmark_resolved else None
            ),
            "ev_ebitda_provided": bool(context.ev_ebitda_multiple),
            "ev_revenue_provided": bool(context.ev_revenue_multiple),
            "pe_ratio_provided": bool(context.pe_ratio),
        }

    multiples_data = as_mapping(detailed_results.get("multiples_valuation"))
    return {
        "source": multiples_data.get("data_source", "DISCLOSED_EXTERNAL_MARKET_FALLBACK"),
        "description": (
            "Disclosed fallback or non-concrete multiple source; not a "
            "resolved benchmark contract"
        ),
    }


def _weights_source(
    context: TitanProvenanceContext,
    detailed_results: dict[str, object],
) -> dict[str, object]:
    if context.has_preferences:
        return {
            "source": "titan_enrichment",
            "description": "DCF/Multiples preferences from Titan business-type context",
            "dcf_preference_provided": context.preferences.get("dcf_preference") is not None,
            "multiples_preference_provided": (
                context.preferences.get("multiples_preference") is not None
            ),
        }
    return {
        "source": detailed_results.get("weight_source", "profitability_default"),
        "description": "Weights from deterministic methodology context",
    }


def _benchmarks_source(context: TitanProvenanceContext) -> dict[str, object]:
    if context.has_benchmarks:
        return {
            "source": "titan_enrichment",
            "description": "Industry context from Titan; valuation multiples use the Upswitch Index benchmark contract",
            "ebitda_margin_provided": "typical_ebitda_margin" in context.benchmarks,
            "revenue_range_provided": "typical_revenue" in context.benchmarks,
        }
    return {
        "source": "context_unavailable",
        "description": "No Titan industry benchmark context supplied",
    }


def _industry_source(context: TitanProvenanceContext) -> dict[str, object]:
    if context.has_multiples and context.business_type_id:
        return {
            "source": "titan_enrichment",
            "business_type_id": context.business_type_id,
            "industry": context.industry,
            "description": "Industry derived from business_types database",
        }
    return {
        "source": "frontend_provided",
        "industry": context.industry,
        "description": "Industry provided directly by frontend",
    }


def _official_financials_source(context: TitanProvenanceContext) -> dict[str, object]:
    if not context.official_financials:
        return {}

    official_financials = as_mapping(context.official_financials)
    filing_year = official_financials.get("filing_year") or official_financials.get("filingYear")
    source = official_financials.get("source") or "titan_official_filing"
    return {
        "source": source,
        "description": "Official filing enrichment provided by Titan from official filings",
        "filing_year": filing_year,
        "verification_badge": context.official_verification_badge,
    }


def _is_startup_valuation(request: ValuationRequest, detailed_results: dict[str, object]) -> bool:
    selected_method = str(getattr(request, "selected_method", "") or "").strip().lower()
    methodology = str(detailed_results.get("methodology") or "").strip().upper()
    return (
        selected_method == "startup_valuation"
        or methodology == "STARTUP"
        or bool(detailed_results.get("startup_valuation_native"))
        or isinstance(detailed_results.get("startup_valuation"), dict)
    )


def _startup_source(request: ValuationRequest, context: TitanProvenanceContext) -> dict[str, object]:
    startup_inputs = getattr(request, "startup_inputs", None)
    return {
        "source": "STARTUP_VALUATION_ENGINE",
        "description": (
            "Startup-native valuation using milestone, team, market, funding, "
            "and venture back-solve evidence instead of SME EBITDA/DCF inputs"
        ),
        "method_key": "startup_valuation",
        "stage": getattr(startup_inputs, "stage", None),
        "country_code": getattr(startup_inputs, "country_code", None)
        or getattr(request, "country_code", None),
        "industry": context.industry,
    }


def _apply_startup_data_sources(
    data_sources: dict[str, object],
    *,
    request: ValuationRequest,
    context: TitanProvenanceContext,
) -> None:
    data_sources["startup"] = _startup_source(request, context)
    data_sources["summary"]["primary_source"] = "STARTUP_VALUATION_ENGINE"
    data_sources["multiples"] = {
        "source": "not_applicable",
        "description": "Startup valuation does not use SME market multiples.",
    }
    data_sources["weights"] = {
        "source": "startup_native_method",
        "description": "Startup valuation selected explicitly; DCF and SME multiples weights are zero.",
        "dcf_preference_provided": False,
        "multiples_preference_provided": False,
    }
    data_sources["benchmarks"] = {
        "source": "startup_method_model",
        "description": "Startup-native model assumptions; no SME benchmark contract is used.",
    }
    data_sources["industry"] = {
        "source": "startup_inputs_or_frontend",
        "industry": context.industry,
        "description": "Startup sector context provided by the startup valuation request.",
    }


def build_response_data_sources(
    request: ValuationRequest,
    detailed_results: Dict[str, object],
    *,
    logger: LoggerLike | None = None,
) -> Dict[str, object]:
    """
    Build data sources tracking for audit trail.

    Tracks where each major valuation parameter came from:
    - resolved Upswitch Index/Titan benchmark contracts,
    - disclosed external market fallbacks,
    - deterministic weight sources,
    - industry and official-filing provenance.
    """
    context = _extract_titan_context(request)
    data_sources = _empty_data_sources()
    data_sources["multiples"] = _multiples_source(context, detailed_results)
    data_sources["summary"]["primary_source"] = data_sources["multiples"]["source"]
    data_sources["weights"] = _weights_source(context, detailed_results)
    data_sources["benchmarks"] = _benchmarks_source(context)
    data_sources["industry"] = _industry_source(context)
    data_sources["official_financials"] = _official_financials_source(context)
    if _is_startup_valuation(request, detailed_results):
        _apply_startup_data_sources(
            data_sources,
            request=request,
            context=context,
        )

    if logger:
        logger.debug(
            "📊 DATA SOURCES AUDIT",
            extra={
                "primary_source": data_sources["summary"]["primary_source"],
                "multiples_source": data_sources["multiples"].get("source"),
                "weights_source": data_sources["weights"].get("source"),
                "benchmarks_source": data_sources["benchmarks"].get("source"),
                "industry_source": data_sources["industry"].get("source"),
                "official_financials_source": data_sources["official_financials"].get("source"),
                "business_type_id": context.business_type_id,
            },
        )

    return data_sources
