from src.utils.exceptions import MultiplesCalculationError

"""
Research-only Multiples Data API

Provides research-only access to public-market multiples. Valuation-grade
headline multiples must come from Titan as an Upswitch Index benchmark contract.

Endpoints:
- GET /multiples/industry/{industry} - Get industry multiples
- GET /multiples/business-model/{model} - Get business model multiples  
- GET /multiples/real-time - Get real-time multiples data
- GET /multiples/sources - Get available data sources
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.adapters.fmp_adapter import FMPAdapter
from src.config.countries import SUPPORTED_COUNTRY_CODES
from src.domain.transparency import DataSource
from src.services.privacy.compliance.transparency_tracker import TransparencyTracker
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/multiples", tags=["Multiples Data"])


class MultiplesResponse(BaseModel):
    """Research-only multiples data response"""

    # Basic info
    industry: str
    business_model: Optional[str] = None
    country_code: str
    data_source: str
    last_updated: datetime

    # Multiples data
    ev_ebitda_multiple: Optional[Decimal] = None
    ev_revenue_multiple: Optional[Decimal] = None
    pe_multiple: Optional[Decimal] = None

    # Context
    comparables_count: int = 0
    confidence_level: str = "medium"
    data_quality: str = "standard"

    # Transparency
    source_details: str
    raw_data_link: Optional[str] = None
    confidence_score: Decimal = Decimal("0.8")
    publication_allowed: bool = False
    benchmark_contract_required: bool = True
    fallback_disclosure: str = (
        "Research-only fallback. Not a resolved benchmark contract and "
        "not valid for headline valuation publication."
    )


class MultiplesSourceResponse(BaseModel):
    """Available multiples data sources"""

    sources: List[Dict[str, Any]]
    total_sources: int
    last_refresh: datetime


def _benchmark_contract_required_detail(
    *,
    industry: Optional[str] = None,
    business_model: Optional[str] = None,
    country: str = "BE",
) -> Dict[str, Any]:
    return {
        "code": "BENCHMARK_CONTRACT_REQUIRED",
        "message": (
            "Valuation-grade multiples must be resolved through the "
            "published Upswitch Index benchmark contract. This endpoint will not silently "
            "return FMP, generic, or hardcoded headline multiples."
        ),
        "industry": industry,
        "business_model": business_model,
        "country_code": country,
        "required_provenance": [
            "benchmark_id",
            "dataset_version_id",
            "country_code",
            "region_key",
            "tier",
            "walk_step",
            "sample_size",
            "confidence_band",
            "source_mix",
            "evidence_summary",
            "published_at",
            "methodology_version",
        ],
        "remediation": (
            "Resolve the metric through Titan's Upswitch Index contract flow or pass "
            "allow_untrusted_fallback=true for explicitly disclosed research-only data."
        ),
    }


def _explicitly_allows_fallback(value: Any) -> bool:
    """FastAPI Query defaults are truthy objects during direct unit calls."""
    return value is True


@router.get(
    "/industry/{industry}",
    response_model=MultiplesResponse,
    summary="Get industry multiples",
    description="Get real-time industry multiples for a specific sector",
)
async def get_industry_multiples(
    industry: str = Path(..., description="Industry sector"),
    country: str = Query("BE", description="Country code"),
    business_model: Optional[str] = Query(None, description="Business model type"),
    allow_untrusted_fallback: bool = Query(
        False,
        description=(
            "Explicitly allow research-only public-market fallback data. "
            "Never valid for headline valuation publication."
        ),
    ),
) -> MultiplesResponse:
    """
    Get research-only industry multiples data.

    Fails closed by default. Valuation-grade multiples must come from the
    resolved Upswitch Index benchmark contract via Titan.
    """
    try:
        logger.info("Fetching industry multiples", industry=industry, country=country)

        if not _explicitly_allows_fallback(allow_untrusted_fallback):
            raise HTTPException(
                status_code=422,
                detail=_benchmark_contract_required_detail(
                    industry=industry,
                    business_model=business_model,
                    country=country,
                ),
            )

        # Initialize services
        fmp_adapter = FMPAdapter()
        transparency_tracker = TransparencyTracker()

        try:
            cached_data = await fmp_adapter.get_industry_multiples(industry, country)
        except Exception as exc:
            logger.warning(
                "Disclosed public-market fallback unavailable",
                industry=industry,
                country=country,
                error=str(exc),
            )
            cached_data = None

        if cached_data:
            logger.info("Retrieved multiples from cache", industry=industry)

            # Track data provenance
            transparency_tracker.record_market_data(
                data_type="Industry Multiples",
                value=cached_data.get("ev_ebitda_median", 0),
                source_type=DataSource.FMP_API.value,
                source_details=(
                    f"Disclosed research-only FMP fallback - {industry} sector in {country}"
                ),
                comparables_count=cached_data.get("company_count", 0),
                percentile=50,
                source_confidence=Decimal("0.35"),
            )

            return MultiplesResponse(
                industry=industry,
                business_model=business_model,
                country_code=country,
                data_source="DISCLOSED_EXTERNAL_MARKET_FALLBACK",
                last_updated=datetime.now(timezone.utc),
                ev_ebitda_multiple=cached_data.get("ev_ebitda_median"),
                ev_revenue_multiple=cached_data.get("ev_revenue_median"),
                pe_multiple=cached_data.get("pe_median"),
                comparables_count=cached_data.get("company_count", 0),
                confidence_level="low",
                data_quality="research_only",
                source_details=(
                    "Disclosed FMP public-market fallback; not local SME evidence "
                    f"and not an Upswitch Index benchmark contract ({cached_data.get('company_count', 0)} public companies)."
                ),
                raw_data_link="https://financialmodelingprep.com/developer/docs",
                confidence_score=Decimal("0.35"),
            )

        raise HTTPException(
            status_code=422,
            detail={
                **_benchmark_contract_required_detail(
                    industry=industry,
                    business_model=business_model,
                    country=country,
                ),
                "code": "FALLBACK_DATA_UNAVAILABLE",
                "message": (
                    "No disclosed fallback data is available. The endpoint will "
                    "not manufacture generic industry benchmark multiples."
                ),
            },
        )

    except HTTPException:
        raise
    except MultiplesCalculationError as e:
        logger.error("Error fetching industry multiples", error=str(e), industry=industry)
        raise HTTPException(status_code=500, detail=f"Failed to fetch multiples for {industry}")


@router.get(
    "/business-model/{model}",
    response_model=MultiplesResponse,
    summary="Get business model multiples",
    description="Get real-time multiples for specific business models",
)
async def get_business_model_multiples(
    model: str = Path(..., description="Business model type"),
    industry: str = Query(..., description="Industry sector"),
    country: str = Query("BE", description="Country code"),
    allow_untrusted_fallback: bool = Query(
        False,
        description=(
            "Explicitly allow research-only hardcoded fallback data. "
            "Never valid for headline valuation publication."
        ),
    ),
) -> MultiplesResponse:
    """
    Get real-time multiples for specific business models.

    Fails closed by default. Business-model presets are research-only and only
    returned when the caller explicitly accepts the disclosed fallback.
    """
    try:
        logger.info("Fetching business model multiples", model=model, industry=industry)

        if not _explicitly_allows_fallback(allow_untrusted_fallback):
            raise HTTPException(
                status_code=422,
                detail=_benchmark_contract_required_detail(
                    industry=industry,
                    business_model=model,
                    country=country,
                ),
            )

        # Disclosed research-only presets. These are never publication-grade.
        model_adjustments = {
            "saas": {"ev_revenue_multiple": Decimal("8.0"), "ev_ebitda_multiple": Decimal("25.0")},
            "ecommerce": {
                "ev_revenue_multiple": Decimal("2.5"),
                "ev_ebitda_multiple": Decimal("12.0"),
            },
            "manufacturing": {
                "ev_revenue_multiple": Decimal("1.8"),
                "ev_ebitda_multiple": Decimal("8.0"),
            },
            "services": {
                "ev_revenue_multiple": Decimal("2.2"),
                "ev_ebitda_multiple": Decimal("10.0"),
            },
            "retail": {"ev_revenue_multiple": Decimal("1.5"), "ev_ebitda_multiple": Decimal("6.0")},
        }

        base_multiples = model_adjustments.get(
            model.lower(),
            {"ev_revenue_multiple": Decimal("2.0"), "ev_ebitda_multiple": Decimal("8.0")},
        )

        return MultiplesResponse(
            industry=industry,
            business_model=model,
            country_code=country,
            data_source="DISCLOSED_EXTERNAL_MARKET_FALLBACK",
            last_updated=datetime.now(timezone.utc),
            ev_ebitda_multiple=base_multiples["ev_ebitda_multiple"],
            ev_revenue_multiple=base_multiples["ev_revenue_multiple"],
            pe_multiple=base_multiples["ev_ebitda_multiple"] * Decimal("1.2"),  # Estimated P/E
            comparables_count=0,
            confidence_level="low",
            data_quality="research_only",
            source_details=(
                f"Explicit hardcoded research-only fallback for {model} in {industry}; "
                "not local evidence and not an Upswitch Index benchmark contract."
            ),
            confidence_score=Decimal("0.20"),
        )

    except HTTPException:
        raise
    except MultiplesCalculationError as e:
        logger.error("Error fetching business model multiples", error=str(e), model=model)
        raise HTTPException(status_code=500, detail=f"Failed to fetch multiples for {model}")


@router.get(
    "/real-time",
    response_model=List[MultiplesResponse],
    summary="Get real-time multiples data",
    description="Get comprehensive real-time multiples data for all industries",
)
async def get_real_time_multiples(
    industries: Optional[List[str]] = Query(None, description="Specific industries to fetch"),
    # Defaults to the 16 product-exposed countries (see `src/config/countries.py`).
    # Callers can narrow per-request; the explicit BE/NL/DE/FR-only default was
    # leaving a Spanish/Italian caller with no comparables when they didn't pass
    # `countries=` themselves.
    countries: Optional[List[str]] = Query(
        list(SUPPORTED_COUNTRY_CODES),
        description="Countries to include (defaults to the 16 product-exposed countries)",
    ),
    include_business_models: bool = Query(True, description="Include business model breakdowns"),
    allow_untrusted_fallback: bool = Query(
        False,
        description=(
            "Explicitly allow research-only fallback data. "
            "Never valid for headline valuation publication."
        ),
    ),
) -> List[MultiplesResponse]:
    """
    Get comprehensive real-time multiples data.

    Fails closed by default. Returns only explicitly disclosed research fallback
    data when allow_untrusted_fallback=true.
    """
    try:
        logger.info("Fetching real-time multiples data", industries=industries, countries=countries)

        if not _explicitly_allows_fallback(allow_untrusted_fallback):
            raise HTTPException(
                status_code=422,
                detail=_benchmark_contract_required_detail(country=",".join(countries or [])),
            )

        # Default industries if not specified
        if not industries:
            industries = [
                "technology",
                "manufacturing",
                "services",
                "retail",
                "healthcare",
                "finance",
                "real_estate",
            ]

        results = []

        for industry in industries:
            for country in countries:
                try:
                    # Get industry multiples
                    industry_data = await get_industry_multiples(
                        industry=industry,
                        country=country,
                        allow_untrusted_fallback=True,
                    )
                    results.append(industry_data)

                    # Add business model breakdowns if requested
                    if include_business_models:
                        business_models = ["saas", "ecommerce", "manufacturing", "services"]
                        for model in business_models:
                            model_data = await get_business_model_multiples(
                                model=model,
                                industry=industry,
                                country=country,
                                allow_untrusted_fallback=True,
                            )
                            results.append(model_data)

                except MultiplesCalculationError as e:
                    logger.warning(f"Failed to fetch multiples for {industry}/{country}: {e}")
                    continue
                except HTTPException as e:
                    logger.warning(
                        "Research fallback unavailable for multiples request",
                        industry=industry,
                        country=country,
                        status_code=e.status_code,
                    )
                    continue

        logger.info("Real-time multiples data fetched", count=len(results))
        return results

    except HTTPException:
        raise
    except MultiplesCalculationError as e:
        logger.error("Error fetching real-time multiples", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch real-time multiples data")


@router.get(
    "/sources",
    response_model=MultiplesSourceResponse,
    summary="Get available data sources",
    description="Get information about available multiples data sources",
)
async def get_multiples_sources() -> MultiplesSourceResponse:
    """
    Get information about available multiples data sources.

    Returns details about data sources, their reliability, and update frequencies.
    """
    try:
        sources = [
            {
                "name": "Upswitch Index Benchmark Contract",
                "type": "valuation_grade",
                "reliability": "very_high",
                "update_frequency": "published by deterministic gates and operator approval",
                "coverage": "native Benelux; beta/borrowed/global elsewhere",
                "description": ("Only publication-grade source for headline valuation multiples."),
            },
            {
                "name": "FMP API",
                "type": "research_fallback",
                "reliability": "low_for_private_sme_valuation",
                "update_frequency": "daily",
                "coverage": "global public companies",
                "description": (
                    "Public-market fallback only when explicitly disclosed; "
                    "not local SME evidence and not an Upswitch Index benchmark."
                ),
            },
            {
                "name": "OECD / macro context",
                "type": "context_only",
                "reliability": "not_a_multiple_source",
                "update_frequency": "quarterly",
                "coverage": "european",
                "description": "Economic context only; not a valuation multiple source.",
            },
            {
                "name": "Hardcoded business-model presets",
                "type": "research_fallback",
                "reliability": "low",
                "update_frequency": "manual",
                "coverage": "generic",
                "description": (
                    "Explicit fallback only; never local evidence and never " "publication-grade."
                ),
            },
            {
                "name": "Upswitch Index candidate collectors",
                "type": "proposal_only",
                "reliability": "proposal_only",
                "update_frequency": "continuous collection",
                "coverage": "depends on evidence depth",
                "description": (
                    "Collector and AI output remains proposal-only until "
                    "deterministic validation and operator approval publish a benchmark contract."
                ),
            },
        ]

        return MultiplesSourceResponse(
            sources=sources,
            total_sources=len(sources),
            last_refresh=datetime.now(timezone.utc),
        )

    except MultiplesCalculationError as e:
        logger.error("Error fetching multiples sources", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch data sources")


@router.get(
    "/health",
    summary="Multiples API health check",
    description="Check the health of the multiples data API",
)
async def health_check() -> Dict[str, Any]:
    """
    Health check for the multiples API.

    Returns the status of data sources and cache.
    """
    try:
        # Check FMP adapter
        fmp_adapter = FMPAdapter()
        fmp_status = "healthy" if fmp_adapter.api_key else "limited"

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {"fmp_api": fmp_status, "transparency_tracker": "healthy"},
            "data_sources": {
                "upswitch_index_contract_required": "enforced",
                # Legacy response key retained for older clients and monitors.
                "delphi_contract_required": "enforced",
                "research_fallback_fmp": fmp_status,
                "generic_fallback": "disabled_by_default",
            },
        }

    except MultiplesCalculationError as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }
