"""
Equity Value Converter

Converts Enterprise Value to Equity Value by adjusting for net debt, following
McKinsey/Bain/Big 4 methodology with comprehensive validation and edge case handling.

RESEARCH FOUNDATION:
- Damodaran (2012): "Investment Valuation: Tools and Techniques" - EV to Equity conversion
- McKinsey & Company (2015): "Valuation: Measuring and Managing the Value of Companies" - Chapter 2
- Brealey, Myers & Allen (2020): "Principles of Corporate Finance" - Enterprise Value and Equity Value
- Koller, Goedhart & Wessels (2020): "Valuation: Measuring and Managing the Value of Companies" - Net Debt calculation

METHODOLOGY:
Enterprise Value represents the total value of the business (debt + equity).
Equity Value is what shareholders own after accounting for debt obligations.

Formula: Equity Value = Enterprise Value - Net Debt
Where: Net Debt = Total Debt - Cash and Cash Equivalents

OPERATING CASH VS EXCESS CASH (Small Company Exemption):
For small companies (<€25M revenue), not all cash is distributable. Operating cash is needed
for day-to-day operations, working capital, and operational reserves. Only excess cash
(beyond operational needs) should be added back to equity value.

Size Tiers (Operating Cash as % of Revenue):
- <€1M revenue: 15% (micro-cap, highest volatility)
- €1M-€5M revenue: 12% (small-cap, high volatility)
- €5M-€25M revenue: 8% (lower mid-market, moderate volatility)
- ≥€25M revenue: 0% (no exemption, all cash is excess)

Business-Type Multipliers:
- Manufacturing: 1.3x (high inventory, equipment needs)
- Retail/Food: 1.2x (inventory-driven working capital)
- Professional Services: 0.8x (low capital requirements)
- SaaS/Software: 0.7x (minimal working capital, negative WC common)
- Default: 1.0x (standard treatment)

Academic References:
- McKinsey & Company (2015): Operating cash typically Decimal('0.5')-2% for large firms, 2-5% for small firms
- Damodaran (2012): Small companies require higher cash buffers due to limited access to capital markets
- Minton & Schrand (1999): Small firms have 40-60% cash flow volatility vs 15-20% for large firms

VALIDATION:
- Balance sheet data validation (negative values, unrealistic ratios)
- Equity range validation (low < mid < high)
- Edge case handling (negative equity, high debt, cash-rich scenarios)
- Comprehensive metadata for transparency
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.errors.error_types import DatabaseError, DataQualityError
from src.utils.decimal_helpers import bank_round, from_decimal, safe_decimal, to_decimal
from src.utils.logging import get_logger

# Import BusinessTypeCategory for operating cash calculations
from src.domain.interfaces.business_type_protocol import BusinessTypeCategory

logger = get_logger(__name__)


class EquityValueConverter:
    """
    Convert Enterprise Value to Equity Value with comprehensive validation.

    CONVERSION FORMULA:
    - Equity Value = Enterprise Value - Net Debt
    - Net Debt = Total Debt - Cash and Cash Equivalents

    OPERATING CASH EXEMPTION (Small Companies):
    For companies <€25M revenue, operating cash (needed for operations) is excluded
    from net debt calculation. Only excess cash (beyond operational needs) is added back.

    Size Tiers:
    - <€1M: 15% of revenue (micro-cap)
    - €1M-€5M: 12% of revenue (small-cap)
    - €5M-€25M: 8% of revenue (lower mid-market)
    - ≥€25M: 0% (no exemption, all cash is excess)

    Business-Type Multipliers:
    - Manufacturing: 1.3x
    - Retail/Food: 1.2x
    - Professional Services: 0.8x
    - SaaS/Software: 0.7x
    - Default: 1.0x

    VALIDATION RULES:
    - Negative debt/cash: Flagged as invalid
    - High debt-to-EV ratio (>Decimal('2.0')): Flagged as unrealistic
    - High cash-to-EV ratio (>Decimal('1.5')): Flagged as unusual
    - Negative equity: Explained and floored at 0

    EDGE CASES:
    - Negative equity (debt > EV): Over-leveraged company
    - Cash > EV: Excess cash reserves
    - Net debt < 0: Cash-rich company
    - High debt-to-EV ratio: Financial distress indicator
    """

    # Validation thresholds
    HIGH_DEBT_RATIO_THRESHOLD = Decimal("2.0")  # Total debt / EV > Decimal('2.0') is unrealistic
    HIGH_CASH_RATIO_THRESHOLD = Decimal("1.5")  # Cash / EV > Decimal('1.5') is unusual

    # Business-type multipliers for operating cash calculation (Phase 2.4: Expanded to all 11 categories)
    # Based on McKinsey/Bain research: capital-intensive industries need more operating cash
    # Using string keys to avoid circular import
    BUSINESS_TYPE_MULTIPLIERS = {
        "manufacturing": to_decimal("1.3"),  # High inventory, equipment needs
        "retail_food": to_decimal("1.2"),  # Inventory-driven working capital
        "professional_services": to_decimal("0.8"),  # Low capital requirements
        "saas_software": to_decimal("0.7"),  # Minimal working capital, negative WC common
        "ecommerce": to_decimal("0.9"),  # Inventory-driven, moderate capital needs
        "construction": to_decimal("1.4"),  # Equipment-heavy, high capital needs
        "healthcare": to_decimal("1.1"),  # Equipment, moderate capital needs
        "financial_services": to_decimal("0.9"),  # Low capital, high cash reserves
        "real_estate": to_decimal("1.5"),  # Asset-heavy, very high capital needs
        "transportation": to_decimal("1.2"),  # Vehicle/equipment, high capital needs
        "other": to_decimal("1.0"),  # Default
    }

    DEFAULT_MULTIPLIER = to_decimal("1.0")  # Standard treatment

    def __init__(self):
        """Initialize Equity Value Converter."""
        logger.debug("Equity Value Converter initialized")

    def extract_balance_sheet_data(self, request) -> Dict[str, Decimal]:
        """
        Extract balance sheet data (debt and cash) from request.

        Checks multiple attribute names for backward compatibility.

        Args:
            request: Valuation request with current_year_data

        Returns:
            Dictionary with 'total_debt' and 'cash' as Decimal values
        """
        total_debt = to_decimal("0")
        cash = to_decimal("0")
        balance_sheet_available = False

        if hasattr(request, "current_year_data") and request.current_year_data:
            # Try multiple attribute names for debt
            debt_attrs = ["total_debt", "debt", "total_debt_amount"]
            for attr in debt_attrs:
                if hasattr(request.current_year_data, attr):
                    debt_val = getattr(request.current_year_data, attr)
                    if debt_val is not None:
                        try:
                            total_debt = safe_decimal(debt_val, to_decimal("0"))
                            balance_sheet_available = True
                            break
                        except (ValueError, TypeError):
                            continue

            # Try multiple attribute names for cash
            cash_attrs = ["cash", "cash_and_equivalents", "cash_amount"]
            for attr in cash_attrs:
                if hasattr(request.current_year_data, attr):
                    cash_val = getattr(request.current_year_data, attr)
                    if cash_val is not None:
                        try:
                            cash = safe_decimal(cash_val, to_decimal("0"))
                            balance_sheet_available = True
                            break
                        except (ValueError, TypeError):
                            continue

        return {
            "total_debt": total_debt,
            "cash": cash,
            "balance_sheet_available": balance_sheet_available,
        }

    def validate_balance_sheet_data(
        self, total_debt: Decimal, cash: Decimal, ev_mid: Decimal
    ) -> Dict[str, Any]:
        """
        Validate balance sheet data and return warnings.

        Args:
            total_debt: Total debt amount
            cash: Cash and cash equivalents
            ev_mid: Mid-point enterprise value

        Returns:
            Dictionary with validation results and warnings
        """
        validations = {
            "negative_debt": total_debt < 0,
            "negative_cash": cash < 0,
            "high_debt_ratio": False,
            "high_cash_ratio": False,
            "warnings": [],
            "notes": [],
        }

        # Calculate ratios if EV is valid - use Decimal for calculations, convert for display
        if ev_mid > 0:
            debt_ratio_decimal = total_debt / ev_mid
            cash_ratio_decimal = cash / ev_mid
            net_debt_ratio_decimal = (total_debt - cash) / ev_mid

            debt_ratio = from_decimal(debt_ratio_decimal, precision=4)
            cash_ratio = from_decimal(cash_ratio_decimal, precision=4)

            validations["debt_to_ev_ratio"] = debt_ratio
            validations["cash_to_ev_ratio"] = cash_ratio
            validations["net_debt_to_ev_ratio"] = from_decimal(net_debt_ratio_decimal, precision=4)

            if debt_ratio_decimal > to_decimal(str(self.HIGH_DEBT_RATIO_THRESHOLD)):
                validations["high_debt_ratio"] = True
                validations["warnings"].append(
                    f"High debt-to-EV ratio ({debt_ratio:.2f}x). "
                    f"Company has debt exceeding {self.HIGH_DEBT_RATIO_THRESHOLD}x enterprise value. "
                    "This may indicate financial distress."
                )

            if cash_ratio_decimal > to_decimal(str(self.HIGH_CASH_RATIO_THRESHOLD)):
                validations["high_cash_ratio"] = True
                validations["notes"].append(
                    f"High cash-to-EV ratio ({cash_ratio:.2f}x). "
                    f"Company has significant cash reserves relative to enterprise value. "
                    "This may indicate excess cash that could be distributed to shareholders."
                )
        else:
            validations["debt_to_ev_ratio"] = None
            validations["cash_to_ev_ratio"] = None
            validations["net_debt_to_ev_ratio"] = None

        if validations["negative_debt"]:
            validations["warnings"].append(
                "Negative debt value detected. This is unusual and may indicate data error."
            )

        if validations["negative_cash"]:
            validations["warnings"].append(
                "Negative cash value detected. This is unusual and may indicate data error."
            )

        return validations

    def calculate_operating_cash(
        self,
        revenue: Decimal,
        business_category: Optional[Any] = None,
        business_type_id: Optional[str] = None,
        key_metrics: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Calculate operating cash threshold based on size and business type.

        Operating cash is the minimum cash required for day-to-day operations,
        working capital, and operational reserves. Only cash beyond this threshold
        (excess cash) should be added back to equity value.

        Size Tiers (Operating Cash as % of Revenue):
        - <€1M: 15% (micro-cap, highest volatility)
        - €1M-€5M: 12% (small-cap, high volatility)
        - €5M-€25M: 8% (lower mid-market, moderate volatility)
        - ≥€25M: 0% (no exemption, all cash is excess)

        Business-Type Multipliers:
        - Manufacturing: 1.3x (high inventory, equipment needs)
        - Retail/Food: 1.2x (inventory-driven working capital)
        - Professional Services: 0.8x (low capital requirements)
        - SaaS/Software: 0.7x (minimal working capital, negative WC common)
        - Default: 1.0x (standard treatment)

        Args:
            revenue: Annual revenue
            business_category: BusinessTypeCategory enum (optional)
            business_type_id: Optional business type ID for database lookup (Phase Decimal('2.4'))

        Returns:
            Dictionary with:
            - operating_cash: Operating cash threshold (Decimal)
            - operating_cash_pct: Operating cash as % of revenue (float)
            - base_pct: Base percentage from size tier (float)
            - multiplier: Business-type multiplier applied (float)
            - size_tier: Size tier description (str)
            - exemption_applied: Whether exemption applies (bool)
            - rationale: Explanation of calculation (str)
        """
        # Determine size tier and base percentage
        if revenue < to_decimal("1000000"):
            base_pct = to_decimal("0.15")  # 15%
            size_tier = "Micro-cap (<€1M)"
            exemption_applied = True
        elif revenue < to_decimal("5000000"):
            base_pct = to_decimal("0.12")  # 12%
            size_tier = "Small-cap (€1M-€5M)"
            exemption_applied = True
        elif revenue < to_decimal("25000000"):
            base_pct = to_decimal("0.08")  # 8%
            size_tier = "Lower mid-market (€5M-€25M)"
            exemption_applied = True
        else:
            # No exemption for large companies (≥€25M)
            return {
                "operating_cash": to_decimal("0"),
                "operating_cash_pct": Decimal("0.0"),
                "base_pct": Decimal("0.0"),
                "multiplier": Decimal("1.0"),
                "size_tier": "Mid-market (≥€25M)",
                "exemption_applied": False,
                "rationale": "Large companies (≥€25M revenue) have predictable cash flows and access to capital markets. All cash is considered excess and distributable.",
            }

        # Apply business-type multiplier if business_category is provided
        # Phase 2.4: Enhanced with database-driven fallback using key_metrics
        multiplier = self.DEFAULT_MULTIPLIER
        multiplier_float = Decimal("1.0")
        business_type_note = ""
        database_calculated = False

        if business_category:
            # Handle both enum and string values
            category_key = business_category.value if hasattr(business_category, 'value') else str(business_category)
            if category_key in self.BUSINESS_TYPE_MULTIPLIERS:
                multiplier = self.BUSINESS_TYPE_MULTIPLIERS[category_key]
                multiplier_float = to_decimal(multiplier)
                business_type_note = (
                    f" {category_key} multiplier ({multiplier_float:.1f}x) applied."
                )
            else:
                # Use Titan-enriched key_metrics from request, or fall back to service defaults
                resolved_key_metrics = None
                if key_metrics and isinstance(key_metrics, (list, dict)):
                    resolved_key_metrics = list(key_metrics.keys()) if isinstance(key_metrics, dict) else key_metrics
                elif business_type_id:
                    try:
                        from src.services.business_type_metadata_service import (
                            get_business_type_metadata_service,
                        )
                        metadata_service = get_business_type_metadata_service()
                        if metadata_service:
                            resolved_key_metrics = metadata_service.get_key_metrics(None)
                    except (ImportError, AttributeError, TypeError, ValueError) as e:
                        logger.debug(
                            "Failed to load business type key_metrics: %s", e,
                        )

                if resolved_key_metrics:
                    key_metrics_lower = [str(m).lower() for m in resolved_key_metrics]

                    if any(
                        x in key_metrics_lower
                        for x in ["inventory", "equipment", "machinery", "assets"]
                    ):
                        multiplier = to_decimal("1.2")
                        multiplier_float = Decimal("1.2")
                        business_type_note = " Key metrics indicate capital-intensive business (multiplier 1.2x)."
                        database_calculated = True
                    elif any(
                        x in key_metrics_lower
                        for x in ["recurring_revenue", "subscription", "mrr", "arr"]
                    ):
                        multiplier = to_decimal("0.8")
                        multiplier_float = Decimal("0.8")
                        business_type_note = " Key metrics indicate recurring revenue model (multiplier 0.8x)."
                        database_calculated = True
                    else:
                        multiplier = self.DEFAULT_MULTIPLIER
                        multiplier_float = Decimal("1.0")
                        category_key = business_category.value if hasattr(business_category, 'value') else str(business_category)
                        business_type_note = (
                            f" Default multiplier (1.0x) for {category_key}."
                        )
                else:
                    # No business_type_id provided, use default
                    multiplier = self.DEFAULT_MULTIPLIER
                    multiplier_float = Decimal("1.0")
                    business_type_note = (
                        f" Default multiplier (1.0x) for {business_category.value}."
                    )

        # Calculate operating cash
        operating_cash_pct = base_pct * multiplier
        operating_cash = revenue * operating_cash_pct

        # Build rationale - use from_decimal for display values
        base_pct_float = from_decimal(base_pct * to_decimal("100"), precision=1)
        operating_cash_pct_float = from_decimal(operating_cash_pct * to_decimal("100"), precision=1)
        operating_cash_float = from_decimal(operating_cash, precision=0)
        rationale = (
            f"Operating cash threshold: {base_pct_float:.1f}% of revenue (base for {size_tier})"
            f"{business_type_note} "
            f"Final operating cash: {operating_cash_pct_float:.1f}% of revenue = €{operating_cash_float:,.0f}. "
            f"Only cash beyond this threshold (excess cash) is added back to equity value."
        )

        return {
            "operating_cash": operating_cash,
            "operating_cash_pct": operating_cash_pct_float,
            "base_pct": base_pct_float,
            "multiplier": multiplier_float,
            "size_tier": size_tier,
            "exemption_applied": exemption_applied,
            "rationale": rationale,
        }

    def calculate_excess_cash(self, total_cash: Decimal, operating_cash: Decimal) -> Decimal:
        """
        Calculate excess cash (cash beyond operational needs).

        Excess cash is the portion of total cash that exceeds operating cash requirements.
        Only excess cash should be added back to equity value.

        Formula: Excess Cash = max(0, Total Cash - Operating Cash)

        Args:
            total_cash: Total cash and cash equivalents
            operating_cash: Operating cash threshold (from calculate_operating_cash)

        Returns:
            Excess cash (cannot be negative)
        """
        excess_cash = max(to_decimal("0"), total_cash - operating_cash)
        return excess_cash

    def calculate_net_debt(
        self, total_debt: Decimal, cash: Decimal, excess_cash: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate net debt.

        Formula: Net Debt = Total Debt - Cash and Cash Equivalents

        For small companies with operating cash exemption:
        Formula: Net Debt = Total Debt - Excess Cash
        Where: Excess Cash = Total Cash - Operating Cash

        Net debt can be negative if cash exceeds debt (cash-rich company).

        Args:
            total_debt: Total debt amount
            cash: Cash and cash equivalents (total cash)
            excess_cash: Excess cash (optional, if provided uses this instead of total cash)

        Returns:
            Net debt (can be negative)
        """
        # Use excess cash if provided (for small company exemption), otherwise use total cash
        cash_to_use = excess_cash if excess_cash is not None else cash
        net_debt = total_debt - cash_to_use
        return net_debt

    def convert_to_equity(
        self, ev_low: Decimal, ev_mid: Decimal, ev_high: Decimal, net_debt: Decimal
    ) -> Dict[str, Decimal]:
        """
        Convert Enterprise Value to Equity Value.

        Formula: Equity Value = Enterprise Value - Net Debt

        Args:
            ev_low: Low estimate of enterprise value
            ev_mid: Mid-point estimate of enterprise value
            ev_high: High estimate of enterprise value
            net_debt: Net debt (Total Debt - Cash)

        Returns:
            Dictionary with equity_low, equity_mid, equity_high
        """
        equity_low = ev_low - net_debt
        equity_mid = ev_mid - net_debt
        equity_high = ev_high - net_debt

        return {"equity_low": equity_low, "equity_mid": equity_mid, "equity_high": equity_high}

    def validate_equity_range(
        self, equity_low: Decimal, equity_mid: Decimal, equity_high: Decimal
    ) -> Dict[str, Any]:
        """
        Validate equity value range and return corrected values if needed.

        Ensures: equity_low < equity_mid < equity_high

        Args:
            equity_low: Low estimate of equity value
            equity_mid: Mid-point estimate of equity value
            equity_high: High estimate of equity value

        Returns:
            Dictionary with validated/corrected values and validation status
        """
        original_values = {
            "equity_low": equity_low,
            "equity_mid": equity_mid,
            "equity_high": equity_high,
        }

        # Check if range is valid
        is_valid = equity_low < equity_mid < equity_high

        if not is_valid:
            logger.warning(
                "Invalid equity range detected, auto-correcting",
                extra={
                    "equity_low": from_decimal(equity_low, precision=2),
                    "equity_mid": from_decimal(equity_mid, precision=2),
                    "equity_high": from_decimal(equity_high, precision=2),
                },
            )

            # Auto-correct: ensure proper ordering
            equity_values = [equity_low, equity_mid, equity_high]
            equity_low = min(equity_values)
            equity_high = max(equity_values)

            # Recalculate mid as average of low and high if ordering was invalid
            if equity_low >= equity_mid or equity_mid >= equity_high:
                equity_mid = (equity_low + equity_high) / to_decimal("2")
                logger.info(
                    "Auto-corrected equity range",
                    extra={
                        "equity_low": from_decimal(equity_low, precision=2),
                        "equity_mid": from_decimal(equity_mid, precision=2),
                        "equity_high": from_decimal(equity_high, precision=2),
                    },
                )

        return {
            "equity_low": equity_low,
            "equity_mid": equity_mid,
            "equity_high": equity_high,
            "range_validated": True,
            "range_corrected": not is_valid,
            "original_values": original_values,
        }

    def get_edge_case_notes(
        self,
        equity_mid: Decimal,
        total_debt: Decimal,
        cash: Decimal,
        ev_mid: Decimal,
        net_debt: Decimal,
    ) -> list[str]:
        """
        Get explanatory notes for edge cases.

        Args:
            equity_mid: Mid-point equity value
            total_debt: Total debt
            cash: Cash and cash equivalents
            ev_mid: Mid-point enterprise value
            net_debt: Net debt

        Returns:
            List of explanatory notes for edge cases
        """
        notes = []

        # Negative equity (debt > EV)
        if equity_mid < 0:
            notes.append(
                "Equity value is negative because total debt exceeds enterprise value. "
                "This indicates the company is over-leveraged. "
                "Equity value is displayed as €0 for valuation purposes."
            )

        # Cash > EV
        if ev_mid > 0 and cash > ev_mid:
            notes.append(
                "Company has significant cash reserves relative to enterprise value. "
                "This may indicate excess cash that could be distributed to shareholders."
            )

        # Net debt < 0 (cash > debt)
        if net_debt < 0:
            notes.append(
                "Company has negative net debt (cash exceeds debt). "
                "This increases equity value as cash can be distributed to shareholders."
            )

        # High debt-to-EV ratio
        if ev_mid > 0:
            debt_ratio_decimal = total_debt / ev_mid
            debt_ratio = from_decimal(debt_ratio_decimal, precision=2)
            if debt_ratio_decimal > to_decimal("1.5"):
                notes.append(
                    f"Company has high debt relative to enterprise value (debt-to-EV ratio: {debt_ratio:.2f}x). "
                    "This significantly reduces equity value and may indicate financial distress."
                )

        return notes

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
        Get detailed breakdown for metadata.

        Args:
            ev_low, ev_mid, ev_high: Enterprise values
            total_debt, cash, net_debt: Balance sheet components
            equity_low, equity_mid, equity_high: Equity values

        Returns:
            Dictionary with complete breakdown for metadata
        """
        # Calculate ratios using Decimal, convert to float for JSON serialization
        debt_to_ev_ratio_decimal = total_debt / ev_mid if ev_mid > 0 else None
        cash_to_ev_ratio_decimal = cash / ev_mid if ev_mid > 0 else None
        net_debt_to_ev_ratio_decimal = net_debt / ev_mid if ev_mid > 0 else None

        debt_to_ev_ratio = (
            from_decimal(debt_to_ev_ratio_decimal, precision=4)
            if debt_to_ev_ratio_decimal is not None
            else None
        )
        cash_to_ev_ratio = (
            from_decimal(cash_to_ev_ratio_decimal, precision=4)
            if cash_to_ev_ratio_decimal is not None
            else None
        )
        net_debt_to_ev_ratio = (
            from_decimal(net_debt_to_ev_ratio_decimal, precision=4)
            if net_debt_to_ev_ratio_decimal is not None
            else None
        )

        return {
            "ev_low": from_decimal(ev_low, precision=2),
            "ev_mid": from_decimal(ev_mid, precision=2),
            "ev_high": from_decimal(ev_high, precision=2),
            "total_debt": from_decimal(total_debt, precision=2),
            "cash": from_decimal(cash, precision=2),
            "net_debt": from_decimal(net_debt, precision=2),
            "equity_low": from_decimal(equity_low, precision=2),
            "equity_mid": from_decimal(equity_mid, precision=2),
            "equity_high": from_decimal(equity_high, precision=2),
            "debt_to_ev_ratio": debt_to_ev_ratio,
            "cash_to_ev_ratio": cash_to_ev_ratio,
            "net_debt_to_ev_ratio": net_debt_to_ev_ratio,
            "calculation_low": f"{from_decimal(ev_low, precision=0):,.0f} - {from_decimal(net_debt, precision=0):,.0f} = {from_decimal(equity_low, precision=0):,.0f}",
            "calculation_mid": f"{from_decimal(ev_mid, precision=0):,.0f} - {from_decimal(net_debt, precision=0):,.0f} = {from_decimal(equity_mid, precision=0):,.0f}",
            "calculation_high": f"{from_decimal(ev_high, precision=0):,.0f} - {from_decimal(net_debt, precision=0):,.0f} = {from_decimal(equity_high, precision=0):,.0f}",
        }

    def convert_ev_to_equity(
        self,
        ev_mid: Decimal,
        total_debt: Decimal,
        cash: Decimal,
        ev_low: Optional[Decimal] = None,
        ev_high: Optional[Decimal] = None,
        revenue: Optional[Decimal] = None,
        business_category: Optional[Any] = None,
        business_type_id: Optional[str] = None,
        key_metrics: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Convenience method to convert EV to equity with automatic net debt calculation.
        
        This method handles the full conversion flow:
        1. Calculate operating cash (if revenue provided for small companies)
        2. Calculate excess cash
        3. Calculate net debt
        4. Convert EV to equity
        
        Args:
            ev_mid: Mid-point enterprise value
            total_debt: Total debt
            cash: Total cash and cash equivalents
            ev_low: Optional low estimate of enterprise value
            ev_high: Optional high estimate of enterprise value
            revenue: Optional revenue (for operating cash calculation)
            business_category: Optional business category (for operating cash multiplier)
            business_type_id: Optional business type ID (for operating cash multiplier)
            
        Returns:
            Dictionary with equity values and conversion details
        """
        # Calculate operating cash if revenue provided (small company exemption)
        operating_cash_result = None
        operating_cash = to_decimal("0")
        excess_cash = cash
        
        if revenue is not None and revenue > 0:
            operating_cash_result = self.calculate_operating_cash(
                revenue=revenue,
                business_category=business_category,
                business_type_id=business_type_id,
                key_metrics=key_metrics,
            )
            operating_cash = operating_cash_result["operating_cash"]
            excess_cash = self.calculate_excess_cash(cash, operating_cash)
        
        # Calculate net debt
        net_debt = self.calculate_net_debt(total_debt, cash, excess_cash)
        
        # Set default EV range if not provided
        if ev_low is None:
            ev_low = ev_mid * to_decimal("0.9")  # Default: 10% below mid
        if ev_high is None:
            ev_high = ev_mid * to_decimal("1.1")  # Default: 10% above mid
        
        # Convert to equity
        equity_result = self.convert_to_equity(ev_low, ev_mid, ev_high, net_debt)
        
        # Build comprehensive result
        result = {
            "equity_value_low": equity_result["equity_low"],
            "equity_value_mid": equity_result["equity_mid"],
            "equity_value_high": equity_result["equity_high"],
            "net_debt": net_debt,
            "total_debt": total_debt,
            "cash": cash,
            "excess_cash": excess_cash,
        }
        
        # Add operating cash details if calculated
        if operating_cash_result:
            result["operating_cash"] = operating_cash
            result["operating_cash_pct"] = operating_cash_result.get("operating_cash_pct", 0)
            result["size_tier"] = operating_cash_result.get("size_tier", "")
            result["exemption_applied"] = operating_cash_result.get("exemption_applied", False)
        
        return result
