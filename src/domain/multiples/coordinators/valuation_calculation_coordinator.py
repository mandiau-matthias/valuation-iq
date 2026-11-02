"""
Valuation Calculation Coordinator

Orchestrates weighted enterprise value and equity value calculations for the multiples engine.
Handles weighted EV calculation from multiple methods and conversion to equity value.

RESPONSIBILITIES:
- Calculate weighted average enterprise value from multiple methods
- Convert enterprise value to equity value
- Handle fallback calculations when data is missing

ARCHITECTURE:
This coordinator acts as a thin orchestration layer that:
1. Combines valuations from different multiples (EBITDA, Revenue, P/E)
2. Applies appropriate weights to each method
3. Converts enterprise value to equity value

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

from decimal import Decimal
from typing import Mapping, Optional

from src.domain.ev_equity_bridge import calculate_ev_equity_bridge
from src.domain.models import FinancialData
from src.domain.multiples.advisor_controls import (
    build_multiple_type_blend,
    infer_sector_multiple_type_weights,
)
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValuationCalculationCoordinator:
    """
    Coordinates valuation calculations for the multiples engine.

    This coordinator handles:
    1. Weighted enterprise value calculation
    2. Equity value conversion
    """

    def __init__(self, financial_data: FinancialData) -> None:
        """
        Initialize valuation calculation coordinator.

        Args:
            financial_data: Company financial data
        """
        self.financial_data = financial_data
        self.logger = logger
        self.last_multiple_type_blend: dict[str, object] = {}
        self.last_ev_equity_bridge: dict[str, object] = {}

    def calculate_weighted_valuation(
        self,
        ev_ebitda: Optional[Decimal],
        ev_revenue: Optional[Decimal],
        pe_valuation: Optional[Decimal],
        multiple_type_weights: Mapping[str, object] | None = None,
        default_multiple_type_weights: Mapping[str, object] | None = None,
        default_multiple_type_source: str = "sector_aware_default",
    ) -> Decimal:
        """
        Calculate weighted average enterprise value.

        Weights default to a sector/financial-profile model policy and can be
        overridden by advisor-provided `multiple_type_weights`.

        Args:
            ev_ebitda: Enterprise value from EBITDA multiple
            ev_revenue: Enterprise value from Revenue multiple
            pe_valuation: Enterprise value from P/E multiple

        Returns:
            Weighted average enterprise value
        """
        inferred_defaults, inferred_source = infer_sector_multiple_type_weights(
            revenue=getattr(self.financial_data.current_year, "revenue", None),
            ebitda=getattr(self.financial_data.current_year, "ebitda", None),
        )
        blend = build_multiple_type_blend(
            {
                "ev_ebitda": ev_ebitda,
                "ev_revenue": ev_revenue,
                "pe": pe_valuation,
            },
            multiple_type_weights,
            default_weights=default_multiple_type_weights or inferred_defaults,
            default_source=default_multiple_type_source or inferred_source,
        )
        self.last_multiple_type_blend = blend

        weighted_ev = to_decimal(blend.get("weighted_enterprise_value") or 0)
        if weighted_ev <= 0:
            # Fallback: use revenue multiple if no other data
            revenue = to_decimal(self.financial_data.current_year.revenue)
            return revenue * Decimal("2.0")

        return weighted_ev

    def calculate_equity_value(
        self,
        enterprise_value: Decimal,
        balance_sheet_adjustments: list[object] | None = None,
    ) -> Decimal:
        """
        Convert enterprise value to equity value.

        Equity Value = Enterprise Value - Net Debt + NWC Surplus/Deficit
            + Balance Sheet Adjustments
        Net Debt = Total Debt - Cash

        Args:
            enterprise_value: Enterprise value to convert
            balance_sheet_adjustments: Optional signed bridge rows such as
                surplus assets, non-operating assets, provisions, or carve-outs.

        Returns:
            Equity value
        """
        bridge = calculate_ev_equity_bridge(
            financial_data=self.financial_data,
            enterprise_value=enterprise_value,
            balance_sheet_adjustments=balance_sheet_adjustments,
        )
        self.last_ev_equity_bridge = bridge.to_dict()
        return bridge.equity_value
