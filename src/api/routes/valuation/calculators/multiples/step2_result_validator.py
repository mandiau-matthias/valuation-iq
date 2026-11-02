"""
Step 2 Result Validator

Responsibility: Validate Step 2 results.

Single Responsibility: Step 2 result validation only.
"""

from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


class Step2ResultValidator:
    """
    Validates Step 2 results.
    
    Single Responsibility: Step 2 result validation only.
    """

    def __init__(self):
        """Initialize validator"""
        self.logger = logger

    def validate_step_2_result(self, step_2: dict[str, object]) -> bool:
        """
        Validate that step_2 result has required fields.

        Args:
            step_2: Step 2 result dictionary

        Returns:
            True if all required fields are present
        """
        required_fields = [
            "ev_revenue_multiple",
            "ev_ebitda_multiple",
            "data_source",
            "primary_method",
        ]

        for field in required_fields:
            if field not in step_2:
                self.logger.warning(
                    f"⚠️ Step 2 result missing required field: {field}",
                    extra={"missing_field": field, "available_fields": list(step_2.keys())},
                )
                return False

        return True
