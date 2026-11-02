from src.utils.exceptions import APIError, ExternalServiceError

"""
Company Lookup Service

Searches public company registries and databases to auto-fill company information.
"""

from typing import List, Dict, Any, Optional
import re

from src.utils.logging import get_logger
import httpx
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class CompanyLookupService:
    """
    Service for looking up companies in public registries.
    """

    def __init__(
        self,
        companies_house_api_key: Optional[str] = None,
        crunchbase_api_key: Optional[str] = None,
    ):
        """Initialize with optional API keys."""
        self.companies_house_api_key = companies_house_api_key
        self.crunchbase_api_key = crunchbase_api_key
        self.timeout = Decimal('10.0')

    async def lookup(
        self, company_name: str, country: Optional[str] = None, limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for companies across multiple data sources.

        Args:
            company_name: Company name to search
            country: Optional 2-letter country code (DE, UK, FR, etc.)
            limit: Maximum number of results

        Returns:
            Dict with results, total_results, search_time_ms
        """
        logger.info(
            "Starting company lookup", company_name=company_name, country=country
        )

        results = []

        # 1. Search based on country
        if country == "UK" and self.companies_house_api_key:
            uk_results = await self._search_companies_house(company_name)
            results.extend(uk_results)
        elif country == "DE":
            de_results = await self._search_german_registry(company_name)
            results.extend(de_results)
        else:
            # Search all available sources
            if self.companies_house_api_key:
                uk_results = await self._search_companies_house(company_name)
                results.extend(uk_results)

        # 2. Enrich with Crunchbase if available
        if self.crunchbase_api_key:
            cb_results = await self._search_crunchbase(company_name)
            results = self._merge_results(results, cb_results)

        # 3. Deduplicate and rank
        unique_results = self._deduplicate(results)
        ranked = self._rank_by_relevance(unique_results, company_name)

        return {
            "results": ranked[:limit],
            "total_results": len(ranked),
            "search_time_ms": 0,  # TODO: Add timing
        }

    async def _search_companies_house(self, company_name: str) -> List[Dict[str, Any]]:
        """
        Search UK Companies House API.

        Official API: https://developer.company-information.service.gov.uk/
        """
        if not self.companies_house_api_key:
            return []

        try:
            url = "https://api.company-information.service.gov.uk/search/companies"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params={"q": company_name, "items_per_page": 20},
                    auth=(self.companies_house_api_key, ""),
                )

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for item in data.get("items", []):
                        results.append(
                            {
                                "name": item.get("title"),
                                "legal_name": item.get("title"),
                                "country": "UK",
                                "city": item.get("address", {}).get("locality"),
                                "industry": self._infer_industry(
                                    item.get("description", "")
                                ),
                                "registry_id": item.get("company_number"),
                                "status": item.get("company_status"),
                                "data_sources": ["companies_house"],
                                "confidence": Decimal('0.9'),
                            }
                        )

                    logger.info(
                        "Companies House search complete", results_count=len(results)
                    )
                    return results

        except APIError as e:
            logger.error("Companies House search failed", error=str(e))

        return []

    async def _search_german_registry(self, company_name: str) -> List[Dict[str, Any]]:
        """
        Search German Handelsregister (Commercial Registry).

        Note: No official API - would require web scraping or paid service.
        This is a placeholder implementation.
        """
        logger.info("German registry search - placeholder implementation")

        # Placeholder: In production, integrate with:
        # - Handelsregister API (paid service)
        # - North Data API (https://www.northdata.com/)
        # - Web scraping (not recommended)

        # Return mock result for now
        if "gmbh" in company_name.lower():
            return [
                {
                    "name": company_name,
                    "country": "DE",
                    "industry": "other",
                    "data_sources": ["placeholder"],
                    "confidence": Decimal('0.5'),
                }
            ]

        return []

    async def _search_crunchbase(self, company_name: str) -> List[Dict[str, Any]]:
        """
        Search Crunchbase for company information.

        API: https://data.crunchbase.com/docs
        Cost: $99/month for basic access
        """
        if not self.crunchbase_api_key:
            return []

        try:
            url = "https://api.crunchbase.com/api/v4/autocompletes"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params={"query": company_name, "collection_ids": "organizations"},
                    headers={"X-cb-user-key": self.crunchbase_api_key},
                )

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for entity in data.get("entities", []):
                        results.append(
                            {
                                "name": entity.get("identifier", {}).get("value"),
                                "description": entity.get("short_description"),
                                "country": entity.get("location_identifiers", [{}])[0]
                                .get("value", "")
                                .split(",")[-1]
                                .strip(),
                                "employees": entity.get("num_employees"),
                                "founding_year": entity.get("founded_on", {}).get(
                                    "year"
                                ),
                                "data_sources": ["crunchbase"],
                                "confidence": Decimal('0.85'),
                            }
                        )

                    logger.info(
                        "Crunchbase search complete", results_count=len(results)
                    )
                    return results

        except ExternalServiceError as e:
            logger.error("Crunchbase search failed", error=str(e))

        return []

    def _infer_industry(self, description: str) -> str:
        """
        Infer industry from company description.
        """
        description_lower = description.lower()

        if any(
            keyword in description_lower
            for keyword in ["software", "tech", "saas", "digital", "it"]
        ):
            return "technology"
        elif any(
            keyword in description_lower
            for keyword in ["retail", "shop", "store", "ecommerce"]
        ):
            return "retail"
        elif any(
            keyword in description_lower
            for keyword in ["manufacturing", "production", "factory"]
        ):
            return "manufacturing"
        elif any(
            keyword in description_lower
            for keyword in ["consulting", "advisory", "services"]
        ):
            return "services"
        elif any(
            keyword in description_lower
            for keyword in ["healthcare", "medical", "hospital", "clinic"]
        ):
            return "healthcare"
        else:
            return "other"

    def _merge_results(
        self, results1: List[Dict[str, Any]], results2: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge and enrich results from multiple sources.
        """
        merged = {}

        for result in results1 + results2:
            name = result.get("name", "").lower()
            if name in merged:
                # Merge data sources
                existing = merged[name]
                existing["data_sources"] = list(
                    set(existing.get("data_sources", []) + result.get("data_sources", []))
                )
                # Update with non-null values
                for key, value in result.items():
                    if value and not existing.get(key):
                        existing[key] = value
            else:
                merged[name] = result

        return list(merged.values())

    def _deduplicate(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate companies based on name similarity.
        """
        unique = {}

        for result in results:
            name = result.get("name", "").lower().strip()
            # Simple deduplication - in production, use fuzzy matching
            key = re.sub(r"[^a-z0-9]", "", name)

            if key not in unique:
                unique[key] = result

        return list(unique.values())

    def _rank_by_relevance(
        self, results: List[Dict[str, Any]], query: str
    ) -> List[Dict[str, Any]]:
        """
        Rank results by relevance to search query.
        """

        def relevance_score(result: Dict[str, Any]) -> Decimal:
            name = result.get("name", "").lower()
            query_lower = query.lower()

            # Exact match
            if name == query_lower:
                return Decimal('1.0')

            # Starts with query
            if name.startswith(query_lower):
                return Decimal('0.9')

            # Contains query
            if query_lower in name:
                return Decimal('0.7')

            # Default
            return result.get("confidence", Decimal('0.5'))

        # Sort by relevance score (descending)
        sorted_results = sorted(
            results, key=lambda x: relevance_score(x), reverse=True
        )

        return sorted_results
