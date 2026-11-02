from src.utils.exceptions import APIError, DataValidationError, DatabaseError
from src.database.connection import is_stateless_mode, StatelessModeError
from src.config import get_settings
from src.registry.titan_kbo_client import TitanKBOClient, TitanRegistryUnavailable

"""
Registry API Routes - Refactored

BRAIN & MUSCLE ARCHITECTURE:
KBO Registry access is now handled by Titan (The Brain).
These routes continue to work for backward compatibility but
Titan has direct database access for faster lookups.

In stateless mode (STATELESS_MODE=true), these routes cannot access the database.
Registry operations should be handled by Titan (The Brain).

This is the main orchestrator for the refactored registry API routes.
It provides a clean interface to the modular registry components.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Path
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .registry_types import (
    RegistrySearchRequest, RegistrySearchResponse, RegistryFetchRequest, RegistryFetchResponse
)

logger = get_logger(__name__)

# Create FastAPI router
# Note: No prefix here since it's mounted with prefix="/api/v1/registry" in main.py
router = APIRouter(tags=["Registry"])

# Lazy initialization to avoid circular imports
_endpoint_manager = None

def get_endpoint_manager():
    """Get or create endpoint manager instance (lazy initialization)"""
    global _endpoint_manager
    if _endpoint_manager is None:
        from ..service_registry import ServiceRegistry
        from ..endpoint_manager import EndpointManager
        service_registry = ServiceRegistry()
        _endpoint_manager = EndpointManager(service_registry)
    return _endpoint_manager


def get_titan_kbo_client() -> TitanKBOClient:
    return TitanKBOClient(get_settings().titan_api_url)


def is_belgian_registry(country_code: Optional[str]) -> bool:
    return (country_code or "BE").upper() == "BE"


@router.post("/search", response_model=RegistrySearchResponse)
async def search_companies(
    request: RegistrySearchRequest
) -> RegistrySearchResponse:
    """
    Search for companies in business registries

    This endpoint searches for companies across multiple business registries
    and returns matching results with company details.
    """
    # Default registry searches are Belgian; route them directly so a failed
    # Titan request cannot be transformed into a successful empty response by
    # the generic endpoint manager.
    if is_belgian_registry(request.country_code):
        try:
            return RegistrySearchResponse(
                **(await get_titan_kbo_client().search_payload(request.company_name, request.limit))
            )
        except (TitanRegistryUnavailable, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Titan KBO registry is unavailable") from exc

    try:
        logger.info("Company search request", extra={
                       "company_name": request.company_name,
                       "country_code": request.country_code,
                       "limit": request.limit
                   })

        # Use endpoint manager to handle the search
        endpoint_manager = get_endpoint_manager()

        search_results = await endpoint_manager.search_companies(
            company_name=request.company_name,
            country_code=request.country_code,
            limit=request.limit
        )

        # Ensure search_results has required fields and handle None values
        results = search_results.get("results", [])
        if not isinstance(results, list):
            logger.warning("Invalid results type, converting to list", extra={
                "results_type": type(results).__name__
            })
            results = []
        
        # Filter out None values and ensure all items are dicts
        # Also convert Decimal values to float for JSON serialization
        filtered_results = []
        for result in results:
            if result is None:
                continue
            if not isinstance(result, dict):
                logger.warning("Skipping non-dict result", extra={
                    "result_type": type(result).__name__
                })
                continue
            
            # Convert Decimal values to float for JSON serialization
            converted_result = {}
            for key, value in result.items():
                if isinstance(value, Decimal):
                    converted_result[key] = float(value)
                else:
                    converted_result[key] = value
            filtered_results.append(converted_result)
        
        # Convert to response model (results are now properly formatted dicts)
        response = RegistrySearchResponse(
            results=filtered_results,
            total_results=int(search_results.get("total_results", 0)),
            search_time_ms=int(search_results.get("search_time_ms", 0)),
            registry_name=str(search_results.get("registry_name", "Multi-Registry Search")),
            registry_url=search_results.get("registry_url") or None
        )

        logger.info("Company search completed",
                   extra={
                       "results_count": len(response.results),
                       "search_time_ms": search_results.get("search_time_ms", 0)
                   })

        return response

    except HTTPException:
        # Re-raise HTTP exceptions (they're already properly formatted)
        raise
    except ValueError as e:
        # Handle Pydantic validation errors
        logger.error(f"Company search response validation failed: {e}", exc_info=True, extra={
            "company_name": request.company_name,
            "country_code": request.country_code
        })
        raise HTTPException(status_code=500, detail="Company search failed due to a data validation issue.")
    except DatabaseError as e:
        logger.error(f"Company search failed (DatabaseError): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Company search failed. Please try again.")
    except Exception as e:
        logger.error(
            f"Company search failed (unexpected error): {e}",
            exc_info=True,
            extra={
                "error_type": type(e).__name__,
                "company_name": request.company_name,
                "country_code": request.country_code,
                "limit": request.limit,
            }
        )
        raise HTTPException(
            status_code=500,
            detail="Company search failed. Please try again."
        )


@router.get("/company/{company_id}", response_model=RegistryFetchResponse)
async def get_company_details(
    company_id: str = Path(..., description="Company identifier"),
    country_code: str = Query(..., description="Country code (e.g., BE, NL, DE)")
) -> RegistryFetchResponse:
    """
    Get detailed company information from business registry

    This endpoint retrieves comprehensive company details including
    registration information, legal status, and contact details.
    """
    if is_belgian_registry(country_code):
        try:
            company_data = await get_titan_kbo_client().get_company_details(company_id)
        except TitanRegistryUnavailable as exc:
            raise HTTPException(status_code=503, detail="Titan KBO registry is unavailable") from exc
        if not company_data:
            raise HTTPException(status_code=404, detail=f"Company {company_id} not found in BE registry")
        return RegistryFetchResponse(
            company_id=company_data["company_id"],
            company_name=company_data["company_name"],
            registration_number=company_data["registration_number"],
            country_code=company_data["country_code"],
            legal_form=company_data["legal_form"],
            filing_history=[],
            founding_year=company_data["founding_year"],
            industry_code=company_data["industry_code"],
            industry_description=company_data["industry_description"],
            employees=None,
            website=None,
            data_source="Titan KBO",
            source_url=None,
            last_updated=company_data["last_updated"],
            completeness_score=company_data["completeness_score"],
        )
    
    try:
        logger.info("Company details request", extra={
            "company_id": company_id,
            "country_code": country_code
        })

        # Use endpoint manager to get company details
        endpoint_manager = get_endpoint_manager()
        company_data = await endpoint_manager.get_company_details(
            company_id=company_id,
            country_code=country_code
        )

        if not company_data:
            raise HTTPException(
                status_code=404,
                detail=f"Company {company_id} not found in {country_code} registry"
            )

        # Convert to response model (flatten to match RegistryFetchResponse structure)
        response = RegistryFetchResponse(
            company_id=company_data.get("company_id", ""),
            company_name=company_data.get("company_name", ""),
            registration_number=company_data.get("registration_number", ""),
            country_code=company_data.get("country_code", ""),
            legal_form=company_data.get("legal_form", ""),
            filing_history=company_data.get("filing_history", []),
            founding_year=company_data.get("founding_year", 0),
            industry_code=company_data.get("industry_code", ""),
            industry_description=company_data.get("industry_description", ""),
            employees=company_data.get("employees", 0),
            website=company_data.get("website", ""),
            data_source=company_data.get("data_source", ""),
            source_url=company_data.get("source_url", ""),
            last_updated=company_data.get("last_updated", ""),
            completeness_score=company_data.get("completeness_score", Decimal('0.0'))
        )

        logger.info("Company details retrieved", extra={
            "company_name": response.company_name
        })

        return response

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Company details retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Company details retrieval failed. Please try again.")


@router.get("/company/{company_id}/financials", response_model=RegistryFetchResponse)
async def get_company_financials(
    company_id: str = Path(..., description="Company identifier"),
    country_code: str = Query(..., description="Country code (e.g., BE, NL, DE)"),
    years: Optional[int] = Query(None, description="Number of years of financial history")
) -> RegistryFetchResponse:
    """
    Get company financial data from business registry

    This endpoint retrieves historical financial data including
    revenue, profit, assets, and other key financial metrics.
    """
    # BRAIN & MUSCLE: Enforce statelessness
    if is_stateless_mode():
        raise StatelessModeError(
            "Registry financials requires database access. "
            "In stateless mode, registry operations should be handled by Titan (The Brain)."
        )
    
    try:
        logger.info("Company financials request", extra={
            "company_id": company_id,
            "country_code": country_code,
            "years": years
        })

        # Use endpoint manager to get financial data
        endpoint_manager = get_endpoint_manager()
        financial_data = await endpoint_manager.get_company_financials(
            company_id=company_id,
            country_code=country_code,
            years=years
        )

        # If no financial data, try to get company details and return empty financials
        if not financial_data:
            logger.info("No financial data found, fetching company details", extra={
                "company_id": company_id,
                "country_code": country_code
            })
            
            # Try to get company details to at least return company info
            company_details = await endpoint_manager.get_company_details(
                company_id=company_id,
                country_code=country_code
            )
            
            if not company_details:
                raise HTTPException(
                    status_code=404,
                    detail=f"Company {company_id} not found in {country_code}"
                )
            
            # Return company info with empty financials (common for Belgian companies)
            financial_data = {
                "company_id": company_id,
                "company_name": company_details.get("company_name", ""),
                "registration_number": company_details.get("registration_number", company_id),
                "country_code": country_code,
                "legal_form": company_details.get("legal_form", ""),
                "filing_history": [],  # No financial data available
                "founding_year": company_details.get("founding_year", 0),
                "industry_code": company_details.get("industry_code", ""),
                "industry_description": company_details.get("industry_description", ""),
                "employees": company_details.get("employees", 0),
                "website": company_details.get("website", ""),
                "data_source": company_details.get("data_source", "KBO/BCE"),
                "source_url": company_details.get("source_url", ""),
                "last_updated": company_details.get("last_updated", datetime.now(timezone.utc).isoformat()),
                "completeness_score": Decimal('0.1')  # Low score due to no financials
            }
            
            logger.info("Returning company info with empty financials", extra={
                "company_name": financial_data.get("company_name"),
                "note": "Financial data not publicly available for Belgian companies"
            })

        # Convert to response model (flatten to match RegistryFetchResponse structure)
        response = RegistryFetchResponse(
            company_id=financial_data.get("company_id", ""),
            company_name=financial_data.get("company_name", ""),
            registration_number=financial_data.get("registration_number", ""),
            country_code=financial_data.get("country_code", ""),
            legal_form=financial_data.get("legal_form", ""),
            filing_history=financial_data.get("filing_history", []),
            founding_year=financial_data.get("founding_year", 0),
            industry_code=financial_data.get("industry_code", ""),
            industry_description=financial_data.get("industry_description", ""),
            employees=financial_data.get("employees", 0),
            website=financial_data.get("website", ""),
            data_source=financial_data.get("data_source", ""),
            source_url=financial_data.get("source_url", ""),
            last_updated=financial_data.get("last_updated", ""),
            completeness_score=financial_data.get("completeness_score", Decimal('0.0'))
        )

        logger.info("Company financials retrieved", extra={
            "company_name": response.company_name,
            "history_years": len(response.filing_history)
        })

        return response

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Financial data retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Financial data retrieval failed. Please try again.")


@router.get("/lookup-and-value")
async def lookup_and_value_company(
    company_name: str = Query(..., description="Company name to search for"),
    country_code: Optional[str] = Query(None, description="Country code filter"),
    limit: int = Query(10, description="Maximum number of results")
) -> Dict[str, Any]:
    """
    Combined lookup and valuation endpoint

    This endpoint searches for companies and provides basic valuation
    estimates based on available financial data.
    """
    try:
        logger.info("Lookup and value request", extra={
            "company_name": company_name,
            "country_code": country_code,
            "limit": limit
        })

        # Search for companies
        endpoint_manager = get_endpoint_manager()
        search_results = await endpoint_manager.search_companies(
            company_name=company_name,
            country_code=country_code,
            limit=limit
        )

        # Add basic valuation estimates to results
        enhanced_results = []
        for result in search_results.get("results", []):
            # Add basic valuation estimate (placeholder)
            result["estimated_value"] = {
                "value_range": "€100K - €500K",
                "confidence": "Low",
                "methodology": "Basic estimation",
                "data_quality": "Limited"
            }
            enhanced_results.append(result)

        response = {
            "search_results": enhanced_results,
            "total_results": search_results.get("total_results", 0),
            "search_time_ms": search_results.get("search_time_ms", 0),
            "valuation_note": "Basic estimates only - comprehensive valuation requires detailed financial data"
        }

        logger.info("Lookup and value completed", extra={
            "results_count": len(enhanced_results)
        })

        return response

    except APIError as e:
        logger.error(f"Lookup and value failed: {e}")
        raise HTTPException(status_code=500, detail="Company lookup failed. Please try again.")


@router.get("/status")
async def get_registry_status() -> Dict[str, Any]:
    """Get registry service status and metrics"""
    try:
        # Get endpoint manager
        endpoint_manager = get_endpoint_manager()
        
        # Get endpoint status
        endpoint_status = endpoint_manager.get_endpoint_status()

        # Get service registry status
        from ..service_registry import ServiceRegistry
        service_registry = ServiceRegistry()
        service_status = service_registry.get_registry_status()

        # Get performance metrics
        performance_metrics = endpoint_manager.get_performance_metrics()

        return {
            "endpoint_status": endpoint_status,
            "service_registry": service_status,
            "performance_metrics": performance_metrics,
            "last_updated": "2024-01-01T00:00:00Z"
        }

    except DataValidationError as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail="Registry status check failed.")


# Health check endpoint
@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy", "service": "registry-api"}
