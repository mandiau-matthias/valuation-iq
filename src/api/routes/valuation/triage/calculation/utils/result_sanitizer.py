"""
Result Sanitizer Utility

Provides reusable sanitization methods for request/result data for logging.
"""

from typing import Any, Dict

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from src.api.schemas import ValuationRequest


class ResultSanitizer:
    """
    Utility class for sanitizing data for logging.

    Responsibilities:
    - Sanitize input data for logging
    - Sanitize request data
    - Sanitize output data
    - Summarize previous results
    """

    def __init__(self):
        """Initialize ResultSanitizer."""
        pass

    def sanitize_input_for_logging(
        self, request: ValuationRequest, previous_results: Dict[int, StepOutput]
    ) -> Dict[str, Any]:
        """
        Create sanitized input summary for logging.

        Removes sensitive data and creates summary of inputs.

        Args:
            request: The valuation request
            previous_results: Results from previous steps

        Returns:
            Sanitized input summary dictionary
        """
        summary = {
            "company_name": getattr(request, "company_name", "N/A"),
            "industry": getattr(request, "industry", "N/A"),
            "business_type_id": getattr(request, "business_type_id", "N/A"),
            "has_current_year_data": hasattr(request, "current_year_data")
            and request.current_year_data is not None,
            "has_historical_data": bool(getattr(request, "historical_years_data", None)),
            "historical_years_count": (
                len(getattr(request, "historical_years_data", []))
                if getattr(request, "historical_years_data", None)
                else 0
            ),
            "previous_steps_completed": [
                k for k, v in previous_results.items() if v.status == StepStatus.COMPLETED
            ],
            "previous_steps_skipped": [
                k for k, v in previous_results.items() if v.status == StepStatus.SKIPPED
            ],
        }

        # Add revenue/EBITDA if available (not sensitive, but useful for debugging)
        if hasattr(request, "current_year_data") and request.current_year_data:
            summary["revenue"] = getattr(request.current_year_data, "revenue", None)
            summary["ebitda"] = getattr(request.current_year_data, "ebitda", None)

        return summary

    def sanitize_request_data(self, request: ValuationRequest) -> Dict[str, Any]:
        """
        Sanitize request data for logging (remove sensitive fields).

        Args:
            request: The valuation request

        Returns:
            Sanitized request data dictionary
        """
        return {
            "company_name": getattr(request, "company_name", "N/A"),
            "industry": getattr(request, "industry", "N/A"),
            "business_type_id": getattr(request, "business_type_id", "N/A"),
            "country_code": getattr(request, "country_code", "N/A"),
            "founding_year": getattr(request, "founding_year", None),
            "revenue": (
                getattr(request.current_year_data, "revenue", None)
                if hasattr(request, "current_year_data") and request.current_year_data
                else None
            ),
            "ebitda": (
                getattr(request.current_year_data, "ebitda", None)
                if hasattr(request, "current_year_data") and request.current_year_data
                else None
            ),
            "number_of_owners": getattr(request, "number_of_owners", None),
            "number_of_employees": getattr(request, "number_of_employees", None),
        }

    def summarize_previous_results(self, previous_results: Dict[int, StepOutput]) -> Dict[str, Any]:
        """
        Create summary of previous step results for logging.

        Args:
            previous_results: Results from previous steps

        Returns:
            Summary dictionary of previous results
        """
        summary = {}
        for step_num, step_output in previous_results.items():
            summary[f"step_{step_num}"] = {
                "status": step_output.status.value,
                "has_ev": "enterprise_value_mid" in step_output.result,
                "has_equity": "equity_value_mid" in step_output.result,
                "execution_time_ms": step_output.execution_time_ms,
            }
            if "enterprise_value_mid" in step_output.result:
                summary[f"step_{step_num}"]["ev_mid"] = step_output.result.get(
                    "enterprise_value_mid"
                )
            if "equity_value_mid" in step_output.result:
                summary[f"step_{step_num}"]["equity_mid"] = step_output.result.get(
                    "equity_value_mid"
                )
        return summary

    def sanitize_output_data(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize output data for logging.

        Args:
            result: Output result dictionary

        Returns:
            Sanitized output data (valuation results are not sensitive, so returns as-is)
        """
        # Return all output data (valuation results are not sensitive)
        return result
