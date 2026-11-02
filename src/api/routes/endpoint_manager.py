from src.utils.exceptions import APIError, DataValidationError, MissingDataError, ValuationEngineError

"""
Endpoint Manager

This module handles endpoint management, request routing,
and response processing for the Registry API refactoring.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.utils.fiscal_year import get_current_filing_year
from src.utils.logging import get_logger
from .registry.registry_types import (
    CountryCode,
    INVALID_SEARCH_PATTERNS, COUNTRY_CONFIGURATIONS
)
from .service_registry import ServiceRegistry

logger = get_logger(__name__)


class EndpointManager:
    """
    Endpoint manager for registry API operations

    Handles:
    - Request routing and validation
    - Response processing and formatting
    - Error handling and fallbacks
    - Performance monitoring
    """

    def __init__(self, service_registry: ServiceRegistry) -> None:
        """
        Initialize the endpoint manager.
        
        Args:
            service_registry: Service registry instance for service discovery
        """
        self.logger = logger
        self.service_registry = service_registry
        self._registry_router = None  # Lazy initialization to avoid circular imports
        self.request_cache: Dict[str, Any] = {}
        self.performance_metrics: Dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": Decimal('0.0')
        }

        self.logger.info("EndpointManager initialized")
    
    @property
    def registry_router(self):
        """Lazy initialization of RegistryRouter to avoid circular imports"""
        if self._registry_router is None:
            from src.registry.router import RegistryRouter
            self._registry_router = RegistryRouter()
            self.logger.info("RegistryRouter initialized on first use")
        return self._registry_router

    async def search_companies(
        self,
        company_name: str,
        country_code: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for companies in registries

        Args:
            company_name: Company name to search for
            country_code: Optional country code filter
            limit: Maximum number of results

        Returns:
            Search results dictionary
        """
        try:
            start_time = datetime.now(timezone.utc)

            self.logger.info("Company search request",
                           extra={
                               "company_name": company_name,
                               "country_code": country_code,
                               "limit": limit
                           })

            # Validate search query
            if not self._validate_search_query(company_name):
                return self._create_empty_search_response("Invalid search query")

            # Determine target countries
            target_countries = self._get_target_countries(country_code)

            # Search in each country
            all_results = []
            total_results = 0
            search_time_ms = 0

            for country in target_countries:
                try:
                    country_results = await self._search_in_country(
                        company_name, country, limit
                    )
                    all_results.extend(country_results)
                    total_results += len(country_results)

                except ValuationEngineError as e:
                    self.logger.warning(f"Search failed for country {country}: {e}")
                    continue
                except Exception as e:
                    self.logger.error(
                        f"Unexpected error searching country {country}: {e}",
                        exc_info=True,
                        extra={
                            "country": country.value,
                            "company_name": company_name,
                            "error_type": type(e).__name__
                        }
                    )
                    continue

            # Calculate search time
            search_time_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            # Format results
            formatted_results = self._format_search_results(all_results)

            # Update metrics
            self._update_metrics(True, search_time_ms)

            response = {
                "results": formatted_results,
                "total_results": total_results,
                "search_time_ms": search_time_ms,
                "registry_name": "Multi-Registry Search",
                "registry_url": None
            }

            self.logger.info("Company search completed", extra={
                "results_count": total_results,
                "search_time_ms": search_time_ms
            })

            return response

        except MissingDataError as e:
            self.logger.error(f"Company search failed: {e}")
            self._update_metrics(False, 0)
            return self._create_empty_search_response(f"Search failed: {str(e)}")
        except Exception as e:
            # Catch all other exceptions to prevent unhandled errors
            self.logger.error(
                f"Company search failed (unexpected error): {e}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "company_name": company_name,
                    "country_code": country_code,
                    "limit": limit
                }
            )
            self._update_metrics(False, 0)
            return self._create_empty_search_response(f"Search failed: {str(e)}")

    async def get_company_details(
        self,
        company_id: str,
        country_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed company information

        Args:
            company_id: Company identifier
            country_code: Country code

        Returns:
            Company details dictionary or None
        """
        try:
            self.logger.info("Company details request", extra={
                "company_id": company_id,
                "country_code": country_code
            })

            # Use RegistryRouter to fetch company details (real implementation)
            company_details = await self.registry_router.get_company_details(
                company_id=company_id,
                country_code=country_code
            )

            if company_details:
                self.logger.info("Company details retrieved", extra={
                    "company_name": company_details.get("company_name")
                })

            return company_details

        except Exception as e:
            self.logger.error(f"Company details retrieval failed: {e}", extra={
                "company_id": company_id,
                "country_code": country_code,
                "error": str(e)
            })
            return None

    async def get_company_financials(
        self,
        company_id: str,
        country_code: str,
        years: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get company financial data

        Args:
            company_id: Company identifier
            country_code: Country code
            years: Number of years of history

        Returns:
            Financial data dictionary or None
        """
        try:
            self.logger.info("Company financials request", extra={
                "company_id": company_id,
                "country_code": country_code,
                "years": years
            })

            # Check if financial data is available for this country
            try:
                country_enum = CountryCode(country_code.upper())
                country_config = self.service_registry.get_country_configuration(country_enum)
                if not country_config.get("financial_data_available", False):
                    self.logger.info("Financial data not available for country", extra={
                        "country": country_code
                    })
                    return None
            except ValueError:
                self.logger.warning("Invalid country code", extra={"country_code": country_code})
                return None

            # Use RegistryRouter to fetch financial data (real implementation)
            financial_data = await self.registry_router.get_company_financials(
                company_id=company_id,
                country_code=country_code,
                years=years
            )

            if financial_data:
                self.logger.info("Financial data retrieved", extra={
                    "company_name": financial_data.get("company_name"),
                    "history_years": len(financial_data.get("filing_history", []))
                })
            else:
                self.logger.warning("No financial data found", extra={
                    "company_id": company_id,
                    "country_code": country_code
                })

            return financial_data

        except Exception as e:
            self.logger.error(f"Financial data retrieval failed: {e}", extra={
                "company_id": company_id,
                "country_code": country_code,
                "error": str(e)
            })
            return None

    def _validate_search_query(self, company_name: str) -> bool:
        """Validate search query"""
        try:
            company_name_lower = company_name.lower()

            # Check for invalid patterns
            for pattern in INVALID_SEARCH_PATTERNS:
                if pattern in company_name_lower:
                    self.logger.warning("Invalid search pattern detected", extra={
                        "pattern": pattern,
                        "query": company_name
                    })
                    return False

            # Check minimum length
            if len(company_name.strip()) < 2:
                return False

            return True

        except DataValidationError as e:
            self.logger.error(f"Search query validation failed: {e}")
            return False

    def _get_target_countries(self, country_code: Optional[str]) -> List[CountryCode]:
        """Get target countries for search"""
        if country_code:
            try:
                return [CountryCode(country_code.upper())]
            except ValueError:
                self.logger.warning("Invalid country code", extra={"country_code": country_code})
                return []
        else:
            # Return all supported countries
            return [CountryCode.BELGIUM]  # Only Belgium is currently active

    async def _search_in_country(
        self,
        company_name: str,
        country: CountryCode,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search for companies in a specific country using RegistryRouter"""
        try:
            # Use the real RegistryRouter to search companies
            result = await self.registry_router.search_companies(
                company_name=company_name,
                country_code=country.value,
                limit=limit
            )
            
            # Extract results from the response
            return result.get("results", [])

        except Exception as e:
            self.logger.error(f"Country search failed for {country.value}: {e}",
                            extra={"country": country.value, "error": str(e)})
            return []


    async def _fetch_company_from_registry(
        self,
        company_id: str,
        country_code: str,
        service: Any
    ) -> Optional[Dict[str, Any]]:
        """Fetch company details from registry"""
        # Simulate API call
        await asyncio.sleep(0.2)  # asyncio.sleep requires float

        # Return mock company details
        return {
            "company_id": company_id,
            "company_name": f"Company {company_id}",
            "registration_number": company_id,
            "country_code": country_code,
            "legal_form": "BVBA",
            "status": "Active",
            "founding_year": 2020,
            "industry_code": "62.01",
            "industry_description": "Computer programming activities",
            "employees": 25,
            "website": f"https://www.company{company_id}.com",
            "address": "123 Business Street, Brussels, Belgium",
            "filing_history": [],
            "data_source": service.name,
            "source_url": f"{service.url}/company/{company_id}",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "completeness_score": Decimal('0.7')
        }

    async def _fetch_financial_data_from_registry(
        self,
        company_id: str,
        country_code: str,
        service: Any,
        years: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """Fetch financial data from registry"""
        # Simulate API call
        await asyncio.sleep(0.3)  # asyncio.sleep requires float

        # Return mock financial data
        filing_history = []
        current_year = get_current_filing_year()

        for i in range(years or 3):
            year = current_year - i
            filing_history.append({
                "year": year,
                "revenue": 1000000 + i * 100000,
                "ebitda": 200000 + i * 20000,
                "net_income": 150000 + i * 15000,
                "total_assets": 2000000 + i * 200000,
                "total_liabilities": 800000 + i * 80000,
                "equity": 1200000 + i * 120000,
                "cash": 300000 + i * 30000,
                "debt": 500000 + i * 50000,
                "employees": 25 + i * 2,
                "currency": "EUR",
                "data_quality_score": Decimal('0.8') - i * Decimal('0.1')
            })

        return {
            "company_id": company_id,
            "company_name": f"Company {company_id}",
            "registration_number": company_id,
            "country_code": country_code,
            "legal_form": "BVBA",
            "filing_history": filing_history,
            "founding_year": 2020,
            "industry_code": "62.01",
            "industry_description": "Computer programming activities",
            "employees": 25,
            "website": f"https://www.company{company_id}.com",
            "data_source": service.name,
            "source_url": f"{service.url}/company/{company_id}",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "completeness_score": Decimal('0.8')
        }

    def _format_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format search results for API response"""
        if not isinstance(results, list):
            self.logger.warning("Invalid results type in _format_search_results", extra={
                "results_type": type(results).__name__
            })
            return []
        
        # Filter out None values and ensure all items are dicts
        valid_results = [r for r in results if isinstance(r, dict)]
        
        # Sort by confidence score (descending)
        valid_results.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)

        return valid_results

    def _create_empty_search_response(self, reason: str) -> Dict[str, Any]:
        """Create empty search response"""
        # Note: Don't include "error" field as it's not part of RegistrySearchResponse model
        # The error reason is logged but not returned in the response
        return {
            "results": [],
            "total_results": 0,
            "search_time_ms": 0,
            "registry_name": "Search Error",
            "registry_url": None
        }

    def _update_metrics(self, success: bool, response_time: Decimal):
        """Update performance metrics"""
        try:
            self.performance_metrics["total_requests"] += 1

            if success:
                self.performance_metrics["successful_requests"] += 1
            else:
                self.performance_metrics["failed_requests"] += 1

            # Update average response time
            total_time = self.performance_metrics["average_response_time"] * (self.performance_metrics["total_requests"] - 1)
            self.performance_metrics["average_response_time"] = (total_time + response_time) / self.performance_metrics["total_requests"]

        except APIError as e:
            self.logger.error(f"Metrics update failed: {e}")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return self.performance_metrics.copy()

    def get_endpoint_status(self) -> Dict[str, Any]:
        """Get endpoint status"""
        return {
            "status": "operational",
            "total_requests": self.performance_metrics["total_requests"],
            "success_rate": (
                self.performance_metrics["successful_requests"] / 
                max(1, self.performance_metrics["total_requests"])
            ),
            "average_response_time": self.performance_metrics["average_response_time"],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
