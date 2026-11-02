from src.utils.exceptions import APIError

"""
Step 7 Equity Calculator

Calculates equity values from enterprise values using net debt.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
from src.domain.equity_value_converter import EquityValueConverter
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step7EquityCalculator:
    """Calculates equity values for Step 7."""

    def __init__(self):
        """Initialize the equity calculator."""
        self.equity_converter = EquityValueConverter()
        self.business_type_triage = BusinessTypeTriageEngine()

    def find_ev_source_step(
        self, previous_results: Dict[int, Any]
    ) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """
        Find the latest step with EV values (priority: Step 6 > 5 > 4 > 3).

        Args:
            previous_results: Dictionary of previous step results

        Returns:
            Tuple of (ev_source_step, ev_data)
        """
        from ...base_step import StepStatus

        ev_source_step = None
        ev_data = None

        for candidate_step in [6, 5, 4, 3]:
            candidate_step_output = previous_results.get(candidate_step)
            if candidate_step_output and candidate_step_output.status == StepStatus.COMPLETED:
                candidate_result = candidate_step_output.result
                if candidate_result and "enterprise_value_mid" in candidate_result:
                    ev_source_step = candidate_step
                    ev_data = candidate_result
                    logger.debug(
                        f"✅ Found EV in Step {candidate_step}",
                        extra={
                            "step_number": 7,
                            "ev_source_step": candidate_step,
                            "ev_mid": candidate_result.get("enterprise_value_mid"),
                        },
                    )
                    break
                else:
                    logger.debug(
                        f"⏭️ Step {candidate_step} completed but no EV found",
                        extra={
                            "step_number": 7,
                            "candidate_step": candidate_step,
                            "result_keys": (
                                list(candidate_result.keys()) if candidate_result else []
                            ),
                        },
                    )

        return ev_source_step, ev_data

    def extract_revenue(self, request: object, previous_results: Dict[int, Any]) -> Decimal:
        """
        Extract revenue from Step 1 or request fallback.

        Args:
            request: Valuation request
            previous_results: Dictionary of previous step results

        Returns:
            Revenue as Decimal
        """
        from ...base_step import StepStatus

        step1_result = previous_results.get(1)
        step1_available = (
            step1_result is not None
            and step1_result.status == StepStatus.COMPLETED
            and step1_result.result is not None
        )

        if step1_available:
            revenue_val = step1_result.result.get("revenue", 0)
            if revenue_val is not None:
                return to_decimal(str(revenue_val))
            else:
                return to_decimal("0")
        else:
            # Fallback to request data if Step 1 unavailable
            revenue = to_decimal("0")
            if hasattr(request, "current_year_data") and request.current_year_data:
                if hasattr(request.current_year_data, "revenue"):
                    revenue_val = request.current_year_data.revenue
                    if revenue_val is not None:
                        revenue = to_decimal(str(revenue_val))
            logger.warning(
                "⚠️  Step 1 revenue not available, using request data as fallback",
                extra={"revenue": to_decimal(revenue)},
            )
            return revenue

    def calculate_operating_cash_and_excess(
        self, revenue: Decimal, request: object
    ) -> Dict[str, Any]:
        """
        Calculate operating cash and excess cash.

        Args:
            revenue: Revenue value
            request: Valuation request

        Returns:
            Dictionary with operating_cash, operating_cash_pct, exemption_applied, rationale, excess_cash
        """
        # Get business category for operating cash multiplier
        business_category = None
        try:
            # BANK-GRADE: Extract individual parameters from request for get_business_type_category()
            business_type_id = getattr(request, "business_type_id", None)
            business_model = getattr(request, "business_model", None)
            industry = getattr(request, "industry", None)
            category_id = getattr(request, "category_id", None)
            business_category_enum = self.business_type_triage.get_business_type_category(
                business_type_id=business_type_id,
                business_model=business_model,
                industry=industry,
                category_id=category_id,
            )
            # Extract value from enum if it's an enum, otherwise use as-is
            business_category = (
                business_category_enum.value
                if hasattr(business_category_enum, "value")
                else business_category_enum
            )
        except (APIError, AttributeError, ValueError, TypeError) as e:
            logger.debug(
                "Could not determine business category",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "business_type_id": getattr(request, "business_type_id", None),
                },
            )

        # Calculate operating cash and excess cash (for small company exemption)
        business_type_id = getattr(request, "business_type_id", None)
        request_key_metrics = getattr(request, "key_metrics", None)
        operating_cash_result = self.equity_converter.calculate_operating_cash(
            revenue, business_category, business_type_id, key_metrics=request_key_metrics
        )
        operating_cash = operating_cash_result["operating_cash"]
        operating_cash_pct = operating_cash_result["operating_cash_pct"]
        exemption_applied = operating_cash_result["exemption_applied"]
        exemption_rationale = operating_cash_result["rationale"]

        return {
            "operating_cash": operating_cash,
            "operating_cash_pct": operating_cash_pct,
            "exemption_applied": exemption_applied,
            "exemption_rationale": exemption_rationale,
            "business_category": business_category,
            "size_tier": operating_cash_result.get("size_tier", "N/A"),
        }

    def extract_balance_sheet_data(self, request: object) -> Dict[str, Any]:
        """
        Extract balance sheet data using domain class.

        Args:
            request: Valuation request

        Returns:
            Dictionary with total_debt, cash, balance_sheet_available
        """
        balance_sheet_data = self.equity_converter.extract_balance_sheet_data(request)
        return balance_sheet_data

    def calculate_net_debt(
        self,
        total_debt: Decimal,
        cash: Decimal,
        excess_cash: Optional[Decimal],
        exemption_applied: bool,
    ) -> Decimal:
        """
        Calculate net debt using excess cash (if exemption applied) or total cash (standard).

        Args:
            total_debt: Total debt
            cash: Total cash
            excess_cash: Excess cash (if exemption applied)
            exemption_applied: Whether exemption is applied

        Returns:
            Net debt
        """
        return self.equity_converter.calculate_net_debt(
            total_debt, cash, excess_cash if exemption_applied else None
        )

    def convert_to_equity(
        self, ev_low: Decimal, ev_mid: Decimal, ev_high: Decimal, net_debt: Decimal
    ) -> Dict[str, Decimal]:
        """
        Convert enterprise values to equity values.

        Args:
            ev_low: EV low value
            ev_mid: EV mid value
            ev_high: EV high value
            net_debt: Net debt

        Returns:
            Dictionary with equity_low, equity_mid, equity_high
        """
        return self.equity_converter.convert_to_equity(ev_low, ev_mid, ev_high, net_debt)

    def validate_equity_range(
        self, equity_low: Decimal, equity_mid: Decimal, equity_high: Decimal
    ) -> Dict[str, Any]:
        """
        Validate equity range using domain class.

        Args:
            equity_low: Equity low value
            equity_mid: Equity mid value
            equity_high: Equity high value

        Returns:
            Dictionary with validated equity values and validation info
        """
        return self.equity_converter.validate_equity_range(equity_low, equity_mid, equity_high)

    def validate_balance_sheet_data(
        self, total_debt: Decimal, cash: Decimal, ev_mid: Decimal
    ) -> Dict[str, Any]:
        """
        Validate balance sheet data using domain class.

        Args:
            total_debt: Total debt
            cash: Cash
            ev_mid: EV mid value

        Returns:
            Dictionary with validation results
        """
        return self.equity_converter.validate_balance_sheet_data(total_debt, cash, ev_mid)

    def get_edge_case_notes(
        self,
        calculated_equity_mid: Decimal,
        total_debt: Decimal,
        cash: Decimal,
        ev_mid: Decimal,
        net_debt: Decimal,
    ) -> list:
        """
        Get edge case notes using domain class.

        Args:
            calculated_equity_mid: Calculated equity mid value
            total_debt: Total debt
            cash: Cash
            ev_mid: EV mid value
            net_debt: Net debt

        Returns:
            List of edge case notes
        """
        return self.equity_converter.get_edge_case_notes(
            calculated_equity_mid, total_debt, cash, ev_mid, net_debt
        )

    def get_conversion_breakdown(
        self,
        ev_low: Decimal,
        ev_mid: Decimal,
        ev_high: Decimal,
        total_debt: Decimal,
        cash: Decimal,
        net_debt: Decimal,
        equity_low: Decimal,
        equity_mid: Decimal,
        equity_high: Decimal,
    ) -> Dict[str, Any]:
        """
        Get conversion breakdown using domain class.

        Args:
            ev_low: EV low value
            ev_mid: EV mid value
            ev_high: EV high value
            total_debt: Total debt
            cash: Cash
            net_debt: Net debt
            equity_low: Equity low value
            equity_mid: Equity mid value
            equity_high: Equity high value

        Returns:
            Dictionary with conversion breakdown
        """
        return self.equity_converter.get_conversion_breakdown(
            ev_low, ev_mid, ev_high, total_debt, cash, net_debt, equity_low, equity_mid, equity_high
        )
