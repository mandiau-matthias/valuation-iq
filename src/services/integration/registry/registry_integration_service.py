"""
Registry Integration Service

Service class that wraps the registry router functionality for use in other services.
This provides a clean interface for looking up companies and fetching their details.
"""

from typing import Any, Dict, List, Optional

from src.registry.router import RegistryRouter
from src.utils.exceptions import APIError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RegistryIntegrationService:
    """
    Service class that wraps registry router functionality.

    This service provides a clean interface for:
    - Looking up companies by name
    - Fetching company details by registration number
    - Handling errors gracefully
    """

    def __init__(self):
        """Initialize the registry integration service."""
        self.registry_router = RegistryRouter()
        logger.info("RegistryIntegrationService initialized")

    async def lookup_company(
        self,
        company_name: str,
        country_code: str = "BE",
    ) -> Optional[Dict[str, Any]]:
        """
        Look up a company by name.

        Args:
            company_name: Company name to search for
            country_code: 2-letter country code (defaults to BE)

        Returns:
            Company data if found, None otherwise
        """
        try:
            logger.info(
                "Looking up company",
                company_name=company_name,
                country_code=country_code,
            )

            search_result = await self.registry_router.search_companies(
                company_name=company_name,
                country_code=country_code,
                limit=1,
            )

            results = search_result.get("results", [])
            if results:
                real_companies = [
                    result for result in results if result.get("result_type") == "COMPANY"
                ]
                suggestions_count = len(
                    [result for result in results if result.get("result_type") == "SUGGESTION"]
                )

                if real_companies:
                    company_data = real_companies[0]
                    logger.info(
                        "Company found",
                        company_name=company_data.get("company_name"),
                        registration_number=company_data.get("registration_number"),
                        suggestions_filtered=suggestions_count,
                    )
                    return company_data

                logger.info(
                    "No real company found, only suggestions",
                    company_name=company_name,
                    suggestions_count=suggestions_count,
                )
                return None

            logger.warning("No company found", company_name=company_name)
            return None

        except APIError as e:
            logger.error(
                "Error looking up company",
                error=str(e),
                company_name=company_name,
            )
            return None

    async def fetch_company_details(
        self,
        enterprise_number: str,
        country_code: str = "BE",
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed company information by registration number.

        Args:
            enterprise_number: Company registration number
            country_code: 2-letter country code (defaults to BE)

        Returns:
            Company details if found, None otherwise
        """
        try:
            logger.info(
                "Fetching company details",
                enterprise_number=enterprise_number,
                country_code=country_code,
            )

            # Try to get financial data first
            financial_data = await self.registry_router.get_company_financials(
                company_id=enterprise_number, country_code=country_code
            )

            if financial_data:
                logger.info(
                    "Company details found",
                    company_name=financial_data.get("company_name"),
                    enterprise_number=enterprise_number,
                )
                return financial_data

            # If no financial data, try to get basic details
            basic_details = await self.registry_router.get_company_details(
                company_id=enterprise_number, country_code=country_code
            )

            if basic_details:
                logger.info(
                    "Basic company details found",
                    enterprise_number=enterprise_number,
                )
                return basic_details

            logger.warning(
                "No company details found",
                enterprise_number=enterprise_number,
            )
            return None

        except Exception as e:
            logger.error(
                "Error fetching company details",
                error=str(e),
                enterprise_number=enterprise_number,
            )
            return None

    async def search_companies(
        self,
        company_name: str,
        country_code: str = "BE",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for multiple companies by name.

        Args:
            company_name: Company name to search for
            country_code: 2-letter country code (defaults to BE)
            limit: Maximum number of results

        Returns:
            List of company search results
        """
        try:
            logger.info(
                "Searching companies",
                company_name=company_name,
                country_code=country_code,
                limit=limit,
            )

            search_result = await self.registry_router.search_companies(
                company_name=company_name, country_code=country_code, limit=limit
            )

            results = search_result.get("results", [])
            logger.info(
                "Company search completed",
                company_name=company_name,
                results_count=len(results),
            )

            return results

        except Exception as e:
            logger.error(
                "Error searching companies",
                error=str(e),
                company_name=company_name,
            )
            return []

    def get_supported_countries(self) -> List[str]:
        """
        Get list of supported country codes.

        Returns:
            List of supported country codes
        """
        return list(self.registry_router.clients.keys())

    def is_country_supported(self, country_code: str) -> bool:
        """
        Check if a country is supported.

        Args:
            country_code: 2-letter country code

        Returns:
            True if country is supported, False otherwise
        """
        return country_code in self.registry_router.clients
