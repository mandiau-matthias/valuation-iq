"""
Step 1 Company Extractor

Extracts company information from request.
"""

from typing import Dict


class Step1CompanyExtractor:
    """Extracts company information."""

    def __init__(self) -> None:
        """Initialize the company extractor."""
        pass

    def extract_company_info(self, request: object) -> Dict[str, object]:
        """
        Extract company information from request.

        Args:
            request: Valuation request

        Returns:
            Dictionary with company information
        """
        return {
            "company_name": getattr(request, "company_name", None),
            "industry": getattr(request, "industry", None),
            "country": getattr(request, "country_code", None),
            "founded_year": getattr(request, "founded_year", None),
            "num_employees": getattr(request, "num_employees", None),
        }
