from decimal import Decimal

"""
Step 7 Error Handler

Handles error scenarios and fallback logic for Step 7.
"""

from typing import Optional

from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step7ErrorHandler:
    """Handles error scenarios and fallback logic."""

    def __init__(self, step_name: str):
        """
        Initialize the error handler.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def handle_no_ev_source(
        self, available_steps: list, step_statuses: dict, request: object
    ) -> StepOutput:
        """
        Handle case where no valid EV source found.

        Args:
            available_steps: List of available step numbers
            step_statuses: Dictionary of step statuses
            request: Valuation request

        Returns:
            StepOutput with fallback calculation or FAILED status
        """
        logger.error(
            "❌ Step 7 failed: No valid EV source found",
            extra={
                "step_number": 7,
                "available_steps": available_steps,
                "required_step": 3,
                "step_statuses": step_statuses,
            },
        )

        # Try fallback calculation if we have revenue
        revenue = None
        ebitda = None
        if hasattr(request, "current_year_data") and request.current_year_data:
            revenue = getattr(request.current_year_data, "revenue", None)
            ebitda = getattr(request.current_year_data, "ebitda", None)

        if revenue and revenue > 0:
            # Use conservative revenue multiple as fallback
            estimated_ev = revenue * Decimal("0.5")  # Conservative 0.5x revenue multiple
            estimated_equity = estimated_ev  # Assume no debt for fallback

            logger.warning(
                "⚠️ Step 7: Using fallback calculation from revenue",
                extra={
                    "step_number": 7,
                    "fallback_revenue": revenue,
                    "estimated_ev": estimated_ev,
                    "estimated_equity": estimated_equity,
                    "fallback_reason": "No valid EV source found from steps 3-6",
                },
            )

            return StepOutput(
                step_number=7,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,  # Mark as completed with fallback
                result={
                    "equity_value_low": to_decimal(estimated_equity * Decimal("0.8")),
                    "equity_value_mid": to_decimal(estimated_equity),
                    "equity_value_high": to_decimal(estimated_equity * Decimal("1.2")),
                    "enterprise_value_low": to_decimal(estimated_ev * Decimal("0.8")),
                    "enterprise_value_mid": to_decimal(estimated_ev),
                    "enterprise_value_high": to_decimal(estimated_ev * Decimal("1.2")),
                    "net_debt": Decimal("0.0"),
                    "calculation_method": "fallback_revenue_multiple",
                    "fallback_reason": "No valid EV source found from steps 3-6",
                    "warning": "Equity value calculated using fallback method due to missing Step 3 data",
                },
                metadata={
                    "fallback_used": True,
                    "fallback_method": "revenue_multiple",
                    "fallback_multiple": Decimal("0.5"),
                },
            )
        else:
            # No fallback possible - return failed status
            return StepOutput(
                step_number=7,
                step_name=self.step_name,
                status=StepStatus.FAILED,
                result={},
                error="No valid EV source found from steps 3-6. Step 3 (base EV) is required. No revenue data available for fallback calculation.",
            )

    def handle_invalid_ev_values(
        self,
        ev_low: Decimal,
        ev_mid: Decimal,
        ev_high: Decimal,
        ev_source_step: int,
        ev_data_keys: list,
        request: object,
    ) -> StepOutput:
        """
        Handle case where EV values are invalid.

        Args:
            ev_low: EV low value
            ev_mid: EV mid value
            ev_high: EV high value
            ev_source_step: Source step number
            ev_data_keys: Keys in EV data dictionary
            request: Valuation request

        Returns:
            StepOutput with fallback calculation or FAILED status
        """
        error_details = {
            "ev_low": ev_low,
            "ev_mid": ev_mid,
            "ev_high": ev_high,
            "ev_source_step": ev_source_step,
            "ev_data_keys": ev_data_keys,
        }

        logger.error(
            f"❌ Step 7 failed: Invalid EV values from Step {ev_source_step}",
            extra={"step_number": 7, **error_details},
        )

        # Try fallback calculation if we have revenue
        revenue = None
        if hasattr(request, "current_year_data") and request.current_year_data:
            revenue = getattr(request.current_year_data, "revenue", None)

        if revenue and revenue > 0:
            estimated_ev = revenue * Decimal("0.5")
            estimated_equity = estimated_ev

            logger.warning(
                "⚠️ Step 7: Using fallback calculation due to invalid EV values",
                extra={
                    "step_number": 7,
                    "fallback_revenue": revenue,
                    "estimated_equity": estimated_equity,
                    "original_ev_mid": ev_mid,
                },
            )

            return StepOutput(
                step_number=7,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,  # Mark as completed with fallback
                result={
                    "equity_value_low": to_decimal(estimated_equity * Decimal("0.8")),
                    "equity_value_mid": to_decimal(estimated_equity),
                    "equity_value_high": to_decimal(estimated_equity * Decimal("1.2")),
                    "enterprise_value_low": to_decimal(estimated_ev * Decimal("0.8")),
                    "enterprise_value_mid": to_decimal(estimated_ev),
                    "enterprise_value_high": to_decimal(estimated_ev * Decimal("1.2")),
                    "net_debt": Decimal("0.0"),
                    "calculation_method": "fallback_revenue_multiple",
                    "fallback_reason": f"Invalid EV from Step {ev_source_step}",
                    "warning": "Equity value calculated using fallback method due to invalid EV values",
                },
                metadata={
                    "fallback_used": True,
                    "fallback_method": "revenue_multiple",
                    "fallback_multiple": Decimal("0.5"),
                    "original_ev_error": error_details,
                },
            )
        else:
            return StepOutput(
                step_number=7,
                step_name=self.step_name,
                status=StepStatus.FAILED,
                result={},
                error=f"Invalid EV from Step {ev_source_step}: mid={ev_mid}, low={ev_low}, high={ev_high}. No revenue data available for fallback.",
            )

    def handle_conflicting_tax_latency_inputs(self) -> StepOutput:
        """
        Both legacy tax_latencies and BSA rows with category tax_latency were sent.
        Applying both would double-count the equity bridge adjustment.
        """
        msg = (
            "Step 7: Conflicting tax latency inputs. Use either request.tax_latencies "
            "(import path) or balance_sheet_adjustments with category tax_latency "
            "(manual/Venus path), not both."
        )
        logger.error(
            "Step 7 failed: conflicting tax latency sources",
            extra={"step_number": 7, "error": msg},
        )
        return StepOutput(
            step_number=7,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=msg,
        )
