"""
Step 7 Result Builder

Builds result dictionaries and metadata for Step 7.
"""

from decimal import Decimal
from typing import Any, Dict

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger
from src.utils.core.data_extraction_helpers import extract_enum_value

logger = get_logger(__name__)


class Step7ResultBuilder:
    """Builds result dictionaries and metadata for Step 7."""

    def __init__(self, step_name: str):
        """
        Initialize the result builder.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def build_result_dict(
        self,
        equity_low_float: Decimal,
        equity_mid_float: Decimal,
        equity_high_float: Decimal,
        total_debt_float: Decimal,
        cash_float: Decimal,
        operating_cash: Decimal,
        excess_cash: Decimal,
        net_debt_float: Decimal,
        balance_sheet_available: bool,
        ev_source_step: int,
        calculated_equity_mid_float: Decimal,
        range_validated: bool,
        range_corrected: bool,
        exemption_applied: bool,
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.

        Args:
            equity_low_float: Equity low value
            equity_mid_float: Equity mid value
            equity_high_float: Equity high value
            total_debt_float: Total debt
            cash_float: Cash
            operating_cash: Operating cash
            excess_cash: Excess cash
            net_debt_float: Net debt
            balance_sheet_available: Whether balance sheet data is available
            ev_source_step: Source step number
            calculated_equity_mid_float: Calculated equity mid (may be negative)
            range_validated: Whether range was validated
            range_corrected: Whether range was corrected
            exemption_applied: Whether exemption was applied

        Returns:
            Result dictionary
        """
        return {
            "equity_value_low": equity_low_float,
            "equity_value_mid": equity_mid_float,
            "equity_value_high": equity_high_float,
            "total_debt": total_debt_float,
            "cash": cash_float,
            "operating_cash": to_decimal(operating_cash),
            "excess_cash": to_decimal(excess_cash),
            "net_debt": net_debt_float,
            "balance_sheet_available": balance_sheet_available,
            "ev_source_step": ev_source_step,
            "calculated_equity_mid": calculated_equity_mid_float,  # May be negative
            "range_validated": range_validated,
            "range_corrected": range_corrected,
            "exemption_applied": exemption_applied,
        }

    def build_metadata_dict(
        self,
        ev_low_float: Decimal,
        ev_mid_float: Decimal,
        ev_high_float: Decimal,
        total_debt_float: Decimal,
        cash_float: Decimal,
        operating_cash: Decimal,
        excess_cash: Decimal,
        operating_cash_pct: Decimal,
        net_debt_float: Decimal,
        equity_low_float: Decimal,
        equity_mid_float: Decimal,
        equity_high_float: Decimal,
        ev_source_step: int,
        exemption_applied: bool,
        exemption_rationale: str,
        size_tier: str,
        business_category: Any,
        range_validated: bool,
        range_corrected: bool,
        balance_sheet_validation: Dict[str, Any],
        edge_case_notes: list,
        calculated_equity_mid_float: Decimal,
        conversion_breakdown: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build metadata dictionary.

        Args:
            ev_low_float: EV low value
            ev_mid_float: EV mid value
            ev_high_float: EV high value
            total_debt_float: Total debt
            cash_float: Cash
            operating_cash: Operating cash
            excess_cash: Excess cash
            operating_cash_pct: Operating cash percentage
            net_debt_float: Net debt
            equity_low_float: Equity low value
            equity_mid_float: Equity mid value
            equity_high_float: Equity high value
            ev_source_step: Source step number
            exemption_applied: Whether exemption was applied
            exemption_rationale: Exemption rationale
            size_tier: Size tier
            business_category: Business category
            range_validated: Whether range was validated
            range_corrected: Whether range was corrected
            balance_sheet_validation: Balance sheet validation results
            edge_case_notes: Edge case notes
            calculated_equity_mid_float: Calculated equity mid (may be negative)
            conversion_breakdown: Conversion breakdown dictionary

        Returns:
            Metadata dictionary
        """
        return {
            "formula": "Equity Value = Enterprise Value - Net Debt",
            "net_debt_formula": (
                "Net Debt = Total Debt - Excess Cash"
                if exemption_applied
                else "Net Debt = Total Debt - Cash"
            ),
            "ev_source_step": ev_source_step,
            "calculation_low": conversion_breakdown["calculation_low"],
            "calculation_mid": conversion_breakdown["calculation_mid"],
            "calculation_high": conversion_breakdown["calculation_high"],
            "ev_low": conversion_breakdown["ev_low"],
            "ev_mid": conversion_breakdown["ev_mid"],
            "ev_high": conversion_breakdown["ev_high"],
            "equity_low": conversion_breakdown["equity_low"],
            "equity_mid": conversion_breakdown["equity_mid"],
            "equity_high": conversion_breakdown["equity_high"],
            "total_debt": conversion_breakdown["total_debt"],
            "cash": conversion_breakdown["cash"],
            "operating_cash": to_decimal(operating_cash),
            "excess_cash": to_decimal(excess_cash),
            "operating_cash_pct": operating_cash_pct,
            "net_debt": conversion_breakdown["net_debt"],
            "debt_to_ev_ratio": conversion_breakdown["debt_to_ev_ratio"],
            "cash_to_ev_ratio": conversion_breakdown["cash_to_ev_ratio"],
            "net_debt_to_ev_ratio": conversion_breakdown["net_debt_to_ev_ratio"],
            "exemption_applied": exemption_applied,
            "exemption_rationale": exemption_rationale,
            "size_tier": size_tier,
            "business_category": extract_enum_value(business_category),
            "range_validated": range_validated,
            "range_corrected": range_corrected,
            "balance_sheet_validation": {
                "warnings": balance_sheet_validation.get("warnings", []),
                "notes": balance_sheet_validation.get("notes", []),
                "negative_debt": balance_sheet_validation.get("negative_debt", False),
                "negative_cash": balance_sheet_validation.get("negative_cash", False),
                "high_debt_ratio": balance_sheet_validation.get("high_debt_ratio", False),
                "high_cash_ratio": balance_sheet_validation.get("high_cash_ratio", False),
            },
            "edge_case_notes": edge_case_notes,
            "calculated_equity_mid": calculated_equity_mid_float,  # May be negative
            "note": "Assumes net debt = 0 if balance sheet unavailable. "
            "Equity values are floored at 0 for display purposes (negative equity indicates over-leverage). "
            f'{"Operating cash exemption applied for small company." if exemption_applied else "Standard treatment (all cash is excess)."}',
            "source": "Damodaran (2012), Koller/Goedhart/Wessels (2020), Brealey/Myers/Allen (2020)",
            "precision": "Decimal (bank-grade)",
            "rounding": "ROUND_HALF_EVEN (banker's rounding)",
        }
