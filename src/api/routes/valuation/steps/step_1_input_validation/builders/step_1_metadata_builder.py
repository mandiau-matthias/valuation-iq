"""
Step 1 Metadata Builder

Builds metadata dictionary for Step 1.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal


class Step1MetadataBuilder:
    """Builds metadata dictionary for Step 1."""

    def __init__(self):
        """Initialize the metadata builder."""
        pass

    def build_metadata_dict(
        self,
        revenue: Decimal,
        ebitda: Optional[Decimal],
        using_weighted: bool,
        weighting_method: str,
    ) -> Dict[str, Any]:
        """
        Build metadata dictionary.

        Args:
            revenue: Revenue value
            ebitda: EBITDA value (can be None)
            using_weighted: Whether weighted metrics were used
            weighting_method: Weighting method description

        Returns:
            Metadata dictionary
        """
        return {
            "validation_passed": revenue > 0,  # Mark validation status
            "normalized_fields": ["revenue", "ebitda"],
            "weighted_metrics_applied": using_weighted,
            "weighting_method": weighting_method,
            "revenue_positive": revenue > 0,
            "ebitda_provided": ebitda is not None,
        }
