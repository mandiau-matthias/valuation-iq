"""
Step 2 Result Updater

Responsibility: Update Step 2 results if recovery was used.

Single Responsibility: Step 2 result update logic only.
"""

from decimal import Decimal
from src.utils.valuation_logger import ValuationLogger
from ...steps import StepStatus

logger = ValuationLogger(__name__)


class Step2ResultUpdater:
    """
    Updates Step 2 results if recovery was used.
    
    Single Responsibility: Step 2 result update logic only.
    """

    def __init__(self):
        """Initialize updater"""
        self.logger = logger

    def update_step_2_result_if_needed(
        self,
        step_results: dict[int, object],
        step_2: dict[str, object],
        revenue_multiple_raw: object,
        ebitda_multiple_raw: object,
        context: dict[str, object] | None,
    ) -> None:
        """
        Update Step 2's result in step_results if fallback recovery was used.

        Args:
            step_results: Dictionary mapping step numbers to StepOutput objects
            step_2: Extracted/recovered step_2 dictionary
            revenue_multiple_raw: Revenue multiple value
            ebitda_multiple_raw: EBITDA multiple value
            context: Optional calculation context
        """
        if 2 not in step_results or not step_2 or not isinstance(step_2, dict) or len(step_2) == 0:
            return

        step_2_output = step_results[2]
        step_2_has_empty_result = (
            not hasattr(step_2_output, "result")
            or not isinstance(step_2_output.result, dict)
            or len(step_2_output.result) == 0
        )
        step_2_from_fallback = (
            step_2.get("data_source", "").startswith("fallback")
            or step_2.get("warning", "").lower().find("fallback") >= 0
        )

        if step_2_has_empty_result or step_2_from_fallback:
            if hasattr(step_2_output, "result"):
                step_2_output.result.update(
                    {
                        "ev_revenue_multiple": step_2.get(
                            "ev_revenue_multiple", revenue_multiple_raw
                        ),
                        "ev_ebitda_multiple": step_2.get("ev_ebitda_multiple", ebitda_multiple_raw),
                        "data_source": step_2.get("data_source", "fallback_recovery_successful"),
                        "primary_method": step_2.get(
                            "primary_method", "EV/Revenue" if revenue_multiple_raw else "EV/EBITDA"
                        ),
                        "warning": step_2.get(
                            "warning", "Step 2 result recovered from fallback multiples"
                        ),
                    }
                )

                # Ensure percentile fields are present
                self._ensure_percentile_fields(step_2_output.result)

                # Update status to COMPLETED if it was FAILED
                if hasattr(step_2_output, "status"):
                    if step_2_output.status == StepStatus.FAILED:
                        step_2_output.status = StepStatus.COMPLETED
                        self.logger.info(
                            "✅ Updated Step 2 status from FAILED to COMPLETED after fallback recovery",
                            extra={
                                "step_number": 2,
                                "correlation_id": (
                                    context.get("correlation_id") if context else None
                                ),
                                "recovered_multiples": {
                                    "ev_revenue_multiple": step_2_output.result.get(
                                        "ev_revenue_multiple"
                                    ),
                                    "ev_ebitda_multiple": step_2_output.result.get(
                                        "ev_ebitda_multiple"
                                    ),
                                },
                            },
                        )

    def _ensure_percentile_fields(self, result: dict[str, object]) -> None:
        """
        Ensure percentile fields are present in result.
        
        Args:
            result: Step 2 result dictionary
        """
        if (
            "ev_revenue_p25" not in result
            and "ev_revenue_multiple" in result
        ):
            ev_rev = result["ev_revenue_multiple"]
            result.update(
                {
                    "ev_revenue_p25": ev_rev * Decimal("0.8"),
                    "ev_revenue_p50": ev_rev,
                    "ev_revenue_p75": ev_rev * Decimal("1.2"),
                }
            )
        if (
            "ev_ebitda_p25" not in result
            and "ev_ebitda_multiple" in result
        ):
            ev_ebitda = result["ev_ebitda_multiple"]
            result.update(
                {
                    "ev_ebitda_p25": ev_ebitda * Decimal("0.8"),
                    "ev_ebitda_p50": ev_ebitda,
                    "ev_ebitda_p75": ev_ebitda * Decimal("1.2"),
                }
            )
