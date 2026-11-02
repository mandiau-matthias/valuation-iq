"""
Step 1 Margin Calculator

Calculates EBITDA margin with error handling.
"""

from decimal import Decimal
from typing import Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step1MarginCalculator:
    """Calculates EBITDA margin."""

    def __init__(self):
        """Initialize the margin calculator."""
        pass

    def calculate_ebitda_margin(self, revenue: Decimal, ebitda: Optional[Decimal]) -> Decimal:
        """
        Calculate EBITDA margin with error handling.

        Args:
            revenue: Revenue value
            ebitda: EBITDA value (can be None)

        Returns:
            EBITDA margin as percentage (Decimal('0.0') if calculation fails or data unavailable)
        """
        logger.debug(
            "🧮 Calculating EBITDA margin",
            extra={
                "step_number": 1,
                "revenue": revenue,
                "ebitda": ebitda,
                "ebitda_provided": ebitda is not None and ebitda is not False,
            },
        )

        if revenue is not None and revenue > 0 and ebitda is not None and ebitda is not False:
            try:
                ebitda_margin = to_decimal(ebitda) / to_decimal(revenue) * 100
                logger.debug(
                    "✅ EBITDA margin calculated",
                    extra={
                        "step_number": 1,
                        "formula": f"EBITDA Margin = (EBITDA {to_decimal(ebitda):,.0f} / Revenue {to_decimal(revenue):,.0f}) × 100",
                        "ebitda_margin": round(ebitda_margin, 2),
                    },
                )
                return ebitda_margin
            except (ValueError, TypeError, ZeroDivisionError) as e:
                logger.warning(
                    "⚠️  EBITDA margin calculation failed, defaulting to 0%",
                    extra={"step_number": 1, "error": str(e), "revenue": revenue, "ebitda": ebitda},
                )
                return Decimal("0.0")
        else:
            logger.debug(
                "ℹ️  EBITDA not provided, margin set to 0%",
                extra={"step_number": 1, "ebitda": ebitda, "revenue": revenue},
            )
            return Decimal("0.0")
