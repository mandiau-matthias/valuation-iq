"""
Owner Concentration Processor

Extracted from synthesizer.py to reduce complexity.
Handles owner concentration risk factor processing.
"""

from decimal import Decimal
from typing import Any, List, Optional

from src.domain.models import MultiplesResult
from src.utils.exceptions import CalculationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OwnerConcentrationProcessor:
    """Processes owner concentration risk factors."""

    def process_owner_concentration_risk(
        self, multiples_result: Optional[MultiplesResult], risk_factors: List[str]
    ) -> List[str]:
        """
        Process owner concentration risk factor from multiples result.

        Args:
            multiples_result: Multiples valuation result
            risk_factors: Current list of risk factors

        Returns:
            Updated list of risk factors with owner concentration added if applicable
        """
        if not multiples_result:
            return risk_factors

        try:
            owner_conc = self._extract_owner_concentration(multiples_result)

            if owner_conc and isinstance(owner_conc, dict):
                if self._is_significant_owner_concentration(owner_conc):
                    risk_desc = self._generate_risk_description(owner_conc)
                    if risk_desc:
                        risk_factors.insert(0, risk_desc)

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(
                "Error processing owner concentration",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "multiples_result_type": (
                        type(multiples_result).__name__ if multiples_result else None
                    ),
                },
                exc_info=True,
            )
        except CalculationError as e:
            logger.error(
                "Unexpected error processing owner concentration",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "multiples_result_type": (
                        type(multiples_result).__name__ if multiples_result else None
                    ),
                },
                exc_info=True,
            )

        return risk_factors

    def _extract_owner_concentration(
        self, multiples_result: MultiplesResult
    ) -> Optional[dict]:
        """Extract owner concentration data from multiples result."""
        logger.debug(
            "Processing owner concentration",
            multiples_result_type=type(multiples_result).__name__,
            has_owner_conc_attr=(
                hasattr(multiples_result, "owner_concentration")
                if not isinstance(multiples_result, dict)
                else False
            ),
            is_dict=isinstance(multiples_result, dict),
        )

        try:
            if isinstance(multiples_result, dict):
                return multiples_result.get("owner_concentration")
            elif hasattr(multiples_result, "owner_concentration"):
                return getattr(multiples_result, "owner_concentration", None)
            return None
        except (AttributeError, KeyError, TypeError) as e:
            logger.warning(
                "Failed to access owner_concentration from multiples_result",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "multiples_result_type": type(multiples_result).__name__,
                },
                exc_info=True,
            )
            return None

    def _is_significant_owner_concentration(self, owner_conc: dict) -> bool:
        """Check if owner concentration is significant enough to add as risk factor."""
        ratio = owner_conc.get("ratio")
        number_of_owners = owner_conc.get("number_of_owners")
        number_of_employees = owner_conc.get("number_of_employees")
        adjustment_factor = owner_conc.get("adjustment_factor")

        return (
            ratio is not None
            and ratio > Decimal("0.25")
            and number_of_owners is not None
            and number_of_employees is not None
            and adjustment_factor is not None
        )

    def _generate_risk_description(self, owner_conc: dict) -> Optional[str]:
        """Generate risk description for owner concentration."""
        try:
            from src.domain.owner_concentration_adjuster import OwnerConcentrationAdjuster

            adjuster = OwnerConcentrationAdjuster()
            return adjuster.generate_risk_description(
                owner_conc.get("ratio"),
                owner_conc.get("number_of_owners"),
                owner_conc.get("number_of_employees"),
                owner_conc.get("adjustment_factor"),
            )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.warning(
                "Failed to generate owner concentration risk description",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return None
        except CalculationError as e:
            logger.warning(
                "Unexpected error generating owner concentration risk description",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return None

