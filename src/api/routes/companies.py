from src.utils.exceptions import APIError

"""
Company Lookup API Routes

Handles company search in public registries.
"""

from typing import Optional
import os

from fastapi import APIRouter, Query, HTTPException, status
from src.utils.logging import get_logger

from src.services.market.company_lookup import CompanyLookupService

logger = get_logger(__name__)

router = APIRouter()

# Initialize company lookup service
companies_house_api_key = os.getenv("COMPANIES_HOUSE_API_KEY")
crunchbase_api_key = os.getenv("CRUNCHBASE_API_KEY")

company_lookup = CompanyLookupService(
    companies_house_api_key=companies_house_api_key,
    crunchbase_api_key=crunchbase_api_key,
)


@router.get(
    "/lookup",
    summary="Search for companies",
    description="Search public company registries to auto-fill company information.",
    status_code=status.HTTP_200_OK,
)
async def lookup_company(
    name: str = Query(..., description="Company name to search", min_length=2),
    country: Optional[str] = Query(
        None, description="2-letter country code (DE, UK, FR, etc.)", max_length=2
    ),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=50),
):
    """
    Search for companies in public registries.

    Data sources:
    - UK: Companies House (requires API key)
    - Germany: Handelsregister (placeholder - requires integration)
    - Global: Crunchbase (requires API key)

    Returns:
        - results: List of matching companies
        - total_results: Total number of matches
        - search_time_ms: Search duration
    """
    logger.info("Received company lookup request", name=name, country=country)

    if not name or len(name.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company name must be at least 2 characters",
        )

    try:
        result = await company_lookup.lookup(
            company_name=name, country=country, limit=limit
        )
        logger.info(
            "Company lookup complete",
            name=name,
            results_count=result["total_results"],
        )
        return result

    except APIError as e:
        logger.error("Company lookup failed", error=str(e), name=name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Company lookup failed. Please try again.",
        )


@router.get(
    "/data-sources",
    summary="Get available data sources",
    description="Returns list of available company data sources and their status.",
)
async def get_data_sources():
    """
    Get information about available company data sources.
    """
    return {
        "companies_house": {
            "available": companies_house_api_key is not None,
            "country": "UK",
            "description": "Official UK company registry",
        },
        "crunchbase": {
            "available": crunchbase_api_key is not None,
            "country": "Global",
            "description": "Startup and funding data",
        },
        "handelsregister": {
            "available": False,
            "country": "DE",
            "description": "German commercial registry (integration pending)",
        },
    }
