"""
Step 1 Result Builder

Builds result dictionary for Step 1.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal


class Step1ResultBuilder:
    """Builds result dictionary for Step 1."""

    def __init__(self):
        """Initialize the result builder."""
        pass

    def build_result_dict(
        self,
        revenue: Decimal,
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
        company_info: Dict[str, Any],
        using_weighted: bool,
        weighting_method: str,
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.

        CRITICAL: Ensure revenue and ebitda are always included in result, even if 0 or None.
        This ensures downstream steps can access the data and handle it appropriately.

        Args:
            revenue: Revenue value
            ebitda: EBITDA value (can be None)
            ebitda_margin: EBITDA margin percentage
            company_info: Company information dictionary
            using_weighted: Whether weighted metrics were used
            weighting_method: Weighting method description

        Returns:
            Result dictionary
        """
        return {
            "revenue": to_decimal(revenue) if revenue is not None else Decimal("0.0"),
            "ebitda": to_decimal(ebitda) if ebitda is not None else None,
            "ebitda_margin": (
                to_decimal(ebitda_margin) if ebitda_margin is not None else Decimal("0.0")
            ),
            "company_info": company_info,
            "using_weighted_metrics": using_weighted,
            "weighting_method": weighting_method,
        }
