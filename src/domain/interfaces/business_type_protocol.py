"""
Business Type Triage Protocol

Protocol definition for business type triage functionality.
This allows domain layer to use business type categorization
without depending on API route implementations.
"""

from typing import Optional, Protocol

from src.domain.business_type_taxonomy import BusinessTypeCategory


class BusinessTypeTriageProtocol(Protocol):
    """Protocol for business type triage engine."""

    def get_business_type_category(
        self,
        business_type_id: Optional[str],
        business_model: Optional[str],
        industry: Optional[str],
        category_id: Optional[str] = None,
    ) -> BusinessTypeCategory:
        """
        Get business type category.

        Args:
            business_type_id: Business type ID
            business_model: Business model
            industry: Industry
            category_id: Category ID from Titan enrichment (database-sourced, highest priority)

        Returns:
            Business type category
        """
        ...


__all__ = ["BusinessTypeCategory", "BusinessTypeTriageProtocol"]
