from src.utils.exceptions import MultiplesCalculationError, ValuationEngineError

"""
Registry Router

Routes company lookup requests to the appropriate country-specific registry client.
This is the main entry point for the registry-first architecture.

BRAIN & MUSCLE ARCHITECTURE:
In stateless mode, registry lookups should be done via Titan's
/api/v2/registry/* endpoints. This router checks the stateless_mode
setting and disables database access accordingly.
"""

import os
from typing import List, Optional, Dict, Any
import logging

from .base import RegistryClient, RegistrySearchResult, RegistryFinancialData
from .netherlands import NetherlandsRegistryClient
from .titan_kbo_client import TitanKBOClient, TitanRegistryUnavailable
from decimal import Decimal
from src.config import settings

logger = logging.getLogger(__name__)


class RegistryRouter:
    """
    Routes registry requests to appropriate country-specific clients.

    This is the main entry point for the registry-first architecture.
    It automatically selects the correct registry client based on country
    and keeps Belgian registry identity behind Titan's canonical contract.

    BRAIN & MUSCLE: In stateless mode, database access is disabled.
    Use Titan's /api/v2/registry/* endpoints instead.

    Belgium always uses Titan. Other country-specific providers keep their
    existing contracts.
    """

    def __init__(self) -> None:
        """
        Initialize registry clients.

        Titan is the only Belgian KBO owner. No direct KBO database client,
        ETL loader, scraper, or public-data fallback is constructed here.
        """
        kvk_api_key = settings.kvk_api_key or os.getenv("KVK_API_KEY")
        kvk_base_url = settings.kvk_api_base_url or os.getenv("KVK_API_BASE_URL")

        # Belgian identity is always resolved by Titan.
        self.clients: Dict[str, RegistryClient] = {
            "BE": TitanKBOClient(settings.titan_api_url),
            "NL": NetherlandsRegistryClient(
                api_key=kvk_api_key,
                base_url=kvk_base_url,
                timeout=30.0
            ),
            # Future clients will be added here:
            # "UK": UKHybridClient(),
            # "DE": GermanyHybridClient(),
            # "FR": FranceHybridClient(),
        }

        logger.debug(f"Registry router initialized with supported countries: {list(self.clients.keys())}")

    async def search_companies(
        self, 
        company_name: str, 
        country_code: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for companies across registries.

        Args:
            company_name: Company name to search for
            country_code: Optional 2-letter country code (BE, UK, etc.)
            limit: Maximum number of results

        Returns:
            Dict with results, total_results, search_time_ms, registry_name
        """
        logger.debug(
            f"Registry search | company_name: {company_name} | country_code: {country_code} | limit: {limit} | clients: {list(self.clients.keys())}"
        )

        if country_code and country_code in self.clients:
            # Search specific country
            client = self.clients[country_code]
            client_type = type(client).__name__
            logger.debug(f"Registry client found | country_code: {country_code} | client_type: {client_type}")

            try:
                results = await client.search_companies(company_name, limit)
            except TitanRegistryUnavailable:
                # A Belgian lookup must not look successful-but-empty when
                # Titan is unavailable. Route callers map this to a 503.
                raise
            except Exception as e:
                logger.error(
                    f"Registry client search failed: {e}",
                    exc_info=True,
                    extra={
                        "country_code": country_code,
                        "company_name": company_name,
                        "limit": limit,
                        "error_type": type(e).__name__,
                        "client_type": type(client).__name__
                    }
                )
                # Return empty results instead of crashing
                results = []
                registry_name = client.get_registry_name() if hasattr(client, 'get_registry_name') else "Error"
                return {
                    "results": [],
                    "total_results": 0,
                    "search_time_ms": 0,
                    "registry_name": registry_name,
                    "registry_url": None
                }

            logger.debug(
                f"Registry search returned | results_count: {len(results) if results else 0} | country_code: {country_code}"
            )
            registry_name = client.get_registry_name()
        else:
            # Search all available registries
            all_results = []
            registry_name = "Multiple Registries"

            for country, client in self.clients.items():
                try:
                    country_results = await client.search_companies(company_name, limit)
                    all_results.extend(country_results)
                except TitanRegistryUnavailable:
                    # The all-country helper includes Belgium. Preserve the
                    # failed Titan contract instead of silently omitting it.
                    raise
                except MultiplesCalculationError as e:
                    logger.warning(f"Registry search failed | country: {country} | error: {str(e)}")
                    continue
                except Exception as e:
                    logger.error(
                        f"Registry search failed (unexpected error) | country: {country} | error: {str(e)}",
                        exc_info=True,
                        extra={
                            "country": country,
                            "company_name": company_name,
                            "error_type": type(e).__name__
                        }
                    )
                    continue

            # Deduplicate and rank results
            results = self._deduplicate_results(all_results)
            results = self._rank_results(results, company_name)
            results = results[:limit]

        # Convert results to dict format (handle both RegistrySearchResult objects and dicts)
        def to_dict(result):
            from decimal import Decimal

            if isinstance(result, dict):
                # Convert Decimal values to float for JSON serialization
                converted = {}
                for key, value in result.items():
                    converted[key] = float(value) if isinstance(value, Decimal) else value
                return converted
            elif hasattr(result, 'model_dump'):
                # Use mode='json' to ensure proper serialization of Decimal fields
                try:
                    return result.model_dump(mode='json')
                except (TypeError, ValueError):
                    # Fallback if mode='json' not supported - manually convert Decimals
                    dumped = result.model_dump()
                    return {k: float(v) if isinstance(v, Decimal) else v for k, v in dumped.items()}
            elif hasattr(result, 'dict'):
                # For Pydantic v1, use dict() with json_encoders
                try:
                    return result.dict()
                except Exception:
                    # Fallback: convert manually
                    return {k: float(v) if isinstance(v, Decimal) else v 
                           for k, v in result.__dict__.items()}
            else:
                # Fallback: try to convert to dict
                if hasattr(result, '__dict__'):
                    return {k: float(v) if isinstance(v, Decimal) else v 
                           for k, v in result.__dict__.items()}
                return {}

        converted_results = [to_dict(result) for result in results]

        response = {
            "results": converted_results,
            "total_results": len(results),
            "search_time_ms": 0,  # TODO: Add timing
            "registry_name": registry_name,
            "registry_url": self._get_registry_url(country_code) if country_code else None
        }
        return response

    async def get_company_financials(
        self, 
        company_id: str, 
        country_code: str,
        years: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch financial data for a specific company.

        Args:
            company_id: Company identifier from search results
            country_code: 2-letter country code
            years: Number of years of history to fetch

        Returns:
            Company financial data or None if not found
        """
        logger.info(f"Registry financials requested | company_id: {company_id} | country_code: {country_code}")

        if country_code not in self.clients:
            logger.error(f"Unsupported country | country_code: {country_code}")
            return None

        try:
            client = self.clients[country_code]
            financial_data = await client.get_company_financials(company_id, years)

            if financial_data:
                return financial_data.model_dump() if hasattr(financial_data, 'model_dump') else financial_data.dict()
            else:
                logger.warning(f"No financial data found | company_id: {company_id}")
                return None

        except ValuationEngineError as e:
            logger.error(f"Error fetching company financials | error: {str(e)} | company_id: {company_id} | country_code: {country_code}")
            return None

    async def get_company_details(
        self, 
        company_id: str, 
        country_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch additional company details.

        Args:
            company_id: Company identifier
            country_code: 2-letter country code

        Returns:
            Company details or None if not found
        """
        if country_code not in self.clients:
            return None

        try:
            client = self.clients[country_code]
            details = await client.get_company_details(company_id)
            return details

        except ValuationEngineError as e:
            logger.error(f"Error fetching company details | error: {str(e)} | company_id: {company_id} | country_code: {country_code}")
            return None

    def _deduplicate_results(self, results: List[RegistrySearchResult]) -> List[RegistrySearchResult]:
        """
        Remove duplicate companies based on name similarity.
        
        Args:
            results: List of registry search results
            
        Returns:
            Deduplicated list of results, keeping highest confidence for duplicates
        """
        unique_results = {}

        for result in results:
            # Use company name as key for deduplication
            key = result.company_name.lower().strip()

            if key not in unique_results:
                unique_results[key] = result
            else:
                # Keep the result with higher confidence
                existing = unique_results[key]
                if result.confidence_score > existing.confidence_score:
                    unique_results[key] = result

        return list(unique_results.values())

    def _rank_results(
        self, 
        results: List[RegistrySearchResult], 
        search_term: str
    ) -> List[RegistrySearchResult]:
        """
        Rank results by relevance to search term.
        
        Args:
            results: List of registry search results
            search_term: Search term used for ranking
            
        Returns:
            Ranked list of results sorted by relevance
        """

        def relevance_score(result: RegistrySearchResult) -> Decimal:
            name_lower = result.company_name.lower()
            search_lower = search_term.lower()

            # Exact match
            if name_lower == search_lower:
                return 1.0

            # Starts with search term
            if name_lower.startswith(search_lower):
                return 0.9

            # Contains search term
            if search_lower in name_lower:
                return 0.8

            # Use confidence score from registry
            return result.confidence_score

        # Sort by relevance score (descending)
        return sorted(results, key=relevance_score, reverse=True)

    def _get_registry_url(self, country_code: Optional[str]) -> Optional[str]:
        """Get registry URL for country."""
        if country_code and country_code in self.clients:
            client = self.clients[country_code]
            return getattr(client, 'BASE_URL', None)
        return None

    async def close_all(self) -> None:
        """
        Close all registry clients.
        
        Cleans up connections for all registered registry clients.
        """
        for client in self.clients.values():
            if hasattr(client, 'close'):
                await client.close()

        logger.info("All registry clients closed")

    def get_supported_countries(self) -> List[str]:
        """Get list of supported country codes."""
        return list(self.clients.keys())

    def get_registry_info(self) -> Dict[str, Any]:
        """Get information about available registries."""
        info = {}

        for country_code, client in self.clients.items():
            info[country_code] = {
                "name": client.get_registry_name(),
                "country": client.get_country_code(),
                "available": True,
                "description": f"Official {client.get_country_code()} business registry"
            }

        return info
