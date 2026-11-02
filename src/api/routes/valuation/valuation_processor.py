"""
Valuation Processor

This module handles the actual processing of valuation methodologies.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    DCFCalculationError,
    MarketDataError,
    MultiplesCalculationError,
    ValidationError,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from .valuation_types import (
    BusinessType,
    FinancialData,
    IndustryCategory,
    MarketData,
    ValuationMethod,
    ValuationRequest,
)

logger = get_logger(__name__)


class ValuationProcessor:
    """Handles actual valuation calculations"""

    def __init__(self):
        """Initialize the valuation processor"""
        self.logger = logger
        self.calculation_engines = self._load_calculation_engines()
        self.industry_data = self._load_industry_data()
        self.market_data = self._load_market_data()

    async def process_dcf_valuation(
        self, financial_data: FinancialData, market_data: MarketData, assumptions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process DCF valuation calculation

        Args:
            financial_data: Financial data for valuation
            market_data: Market data for valuation
            assumptions: Valuation assumptions

        Returns:
            DCF valuation results
        """
        try:
            self.logger.info(
                "Processing DCF valuation",
                revenue=financial_data.revenue,
                ebitda=financial_data.ebitda,
            )

            # Calculate WACC
            wacc = await self._calculate_wacc(financial_data, market_data)

            # Project cash flows
            cash_flows = await self._project_cash_flows(financial_data, assumptions)

            # Calculate present value of cash flows
            present_value = await self._calculate_present_value(cash_flows, wacc)

            # Calculate terminal value
            terminal_value = await self._calculate_terminal_value(
                cash_flows[-1], wacc, assumptions.get("terminal_growth_rate", Decimal("0.03"))
            )

            # Calculate enterprise value
            enterprise_value = present_value + terminal_value

            # Calculate equity value
            equity_value = enterprise_value - financial_data.total_debt + financial_data.cash

            # Perform sensitivity analysis
            sensitivity_analysis = await self._perform_dcf_sensitivity_analysis(
                financial_data, market_data, assumptions
            )

            result = {
                "methodology": "DCF",
                "present_value": present_value,
                "terminal_value": terminal_value,
                "enterprise_value": enterprise_value,
                "equity_value": equity_value,
                "wacc": wacc,
                "terminal_growth_rate": assumptions.get("terminal_growth_rate", Decimal("0.03")),
                "cash_flow_projections": cash_flows,
                "sensitivity_analysis": sensitivity_analysis,
            }

            self.logger.info(
                "DCF valuation processed successfully",
                enterprise_value=enterprise_value,
                equity_value=equity_value,
            )

            return result

        except (CalculationError, DataQualityError, MarketDataError, ValidationError) as e:
            self.logger.error(f"Error processing DCF valuation: {e}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(
                f"An unexpected error occurred during DCF valuation processing: {e}", exc_info=True
            )
            raise DCFCalculationError(
                f"Unexpected error in DCF valuation processing: {e}",
                step="dcf_valuation_processing",
                calculation_type="DCF Valuation Processing",
                context={"error_type": type(e).__name__},
            ) from e

    async def process_multiples_valuation(
        self,
        financial_data: FinancialData,
        market_data: MarketData,
        business_type: BusinessType,
        industry: IndustryCategory,
    ) -> Dict[str, Any]:
        """
        Process multiples valuation calculation

        Args:
            financial_data: Financial data for valuation
            market_data: Market data for valuation
            business_type: Business type
            industry: Industry category

        Returns:
            Multiples valuation results
        """
        try:
            self.logger.info(
                "Processing multiples valuation",
                business_type=business_type.value,
                industry=industry.value,
            )

            # Get industry multiples
            industry_multiples = await self._get_industry_multiples(industry)

            # Calculate valuations using different multiples
            pe_valuation = financial_data.net_income * market_data.pe_ratio
            ev_ebitda_valuation = financial_data.ebitda * market_data.ev_ebitda_ratio
            ps_valuation = financial_data.revenue * market_data.price_to_sales
            pb_valuation = financial_data.total_assets * market_data.price_to_book

            # Calculate weighted average
            weights = await self._calculate_multiples_weights(business_type, industry)
            weighted_valuation = (
                pe_valuation * weights["pe"]
                + ev_ebitda_valuation * weights["ev_ebitda"]
                + ps_valuation * weights["ps"]
                + pb_valuation * weights["pb"]
            )

            # Calculate equity value
            equity_value = weighted_valuation

            # Get comparable companies
            comparable_companies = await self._get_comparable_companies(industry, business_type)

            # Calculate valuation range
            valuation_range = await self._calculate_valuation_range(
                [pe_valuation, ev_ebitda_valuation, ps_valuation, pb_valuation]
            )

            result = {
                "methodology": "Multiples",
                "pe_multiple": market_data.pe_ratio,
                "ev_ebitda_multiple": market_data.ev_ebitda_ratio,
                "price_to_sales_multiple": market_data.price_to_sales,
                "price_to_book_multiple": market_data.price_to_book,
                "industry_averages": industry_multiples,
                "comparable_companies": comparable_companies,
                "valuation_range": valuation_range,
                "enterprise_value": weighted_valuation,
                "equity_value": equity_value,
            }

            self.logger.info(
                "Multiples valuation processed successfully",
                enterprise_value=weighted_valuation,
                equity_value=equity_value,
            )

            return result

        except (CalculationError, DataQualityError, MarketDataError, ValidationError) as e:
            self.logger.error(f"Error processing multiples valuation: {e}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(
                f"An unexpected error occurred during multiples valuation processing: {e}",
                exc_info=True,
            )
            raise MultiplesCalculationError(
                f"Unexpected error in multiples valuation processing: {e}",
                step="multiples_valuation_processing",
                calculation_type="Multiples Valuation Processing",
                context={"error_type": type(e).__name__},
            ) from e

    async def process_asset_based_valuation(
        self, financial_data: FinancialData, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """
        Process asset-based valuation calculation

        Args:
            financial_data: Financial data for valuation
            business_type: Business type
            industry: Industry category

        Returns:
            Asset-based valuation results
        """
        try:
            self.logger.info(
                "Processing asset-based valuation",
                total_assets=financial_data.total_assets,
                total_debt=financial_data.total_debt,
            )

            # Calculate book value
            book_value = financial_data.total_assets - financial_data.total_debt

            # Calculate adjusted book value
            adjustment_factors = await self._get_asset_adjustment_factors(business_type, industry)
            adjusted_book_value = book_value * adjustment_factors["book_value_factor"]

            # Calculate liquidation value
            liquidation_value = await self._calculate_liquidation_value(financial_data)

            # Calculate replacement cost
            replacement_cost = await self._calculate_replacement_cost(financial_data, industry)

            # Calculate intangible assets
            intangible_assets = await self._calculate_intangible_assets(
                financial_data, business_type
            )

            # Calculate goodwill
            goodwill = await self._calculate_goodwill(financial_data, business_type, industry)

            # Calculate final valuation
            enterprise_value = max(adjusted_book_value, liquidation_value, replacement_cost)
            equity_value = enterprise_value

            # Asset breakdown
            asset_breakdown = {
                "tangible_assets": financial_data.total_assets - intangible_assets,
                "intangible_assets": intangible_assets,
                "goodwill": goodwill,
                "total_assets": financial_data.total_assets,
            }

            result = {
                "methodology": "Asset-Based",
                "book_value": book_value,
                "adjusted_book_value": adjusted_book_value,
                "liquidation_value": liquidation_value,
                "replacement_cost": replacement_cost,
                "intangible_assets": intangible_assets,
                "goodwill": goodwill,
                "asset_breakdown": asset_breakdown,
                "enterprise_value": enterprise_value,
                "equity_value": equity_value,
            }

            self.logger.info(
                "Asset-based valuation processed successfully",
                enterprise_value=enterprise_value,
                equity_value=equity_value,
            )

            return result

        except (CalculationError, DataQualityError, MarketDataError, ValidationError) as e:
            self.logger.error(f"Error processing asset-based valuation: {e}", exc_info=True)
            raise
        except (AttributeError, KeyError, TypeError) as e:
            self.logger.error(
                f"Data access or type error during asset-based valuation processing: {e}",
                exc_info=True,
            )
            raise ValidationError(f"Invalid data provided for asset-based valuation: {e}") from e
        except Exception as e:
            self.logger.error(
                f"An unexpected error occurred during asset-based valuation processing: {e}",
                exc_info=True,
            )
            raise CalculationError(
                f"Unexpected error in asset-based valuation processing: {e}"
            ) from e

    async def _calculate_wacc(
        self, financial_data: FinancialData, market_data: MarketData
    ) -> Decimal:
        """Calculate Weighted Average Cost of Capital"""
        try:
            # Cost of equity using CAPM
            risk_free_rate = market_data.risk_free_rate
            market_risk_premium = market_data.market_risk_premium
            beta = market_data.beta

            cost_of_equity = risk_free_rate + (beta * market_risk_premium)

            # Cost of debt (simplified)
            cost_of_debt = risk_free_rate + Decimal("0.02")  # 2% spread over risk-free rate

            # Tax shield
            tax_shield = 1 - financial_data.tax_rate

            # Capital structure
            total_capital = financial_data.total_assets
            debt_ratio = financial_data.total_debt / total_capital if total_capital > 0 else 0
            equity_ratio = 1 - debt_ratio

            # WACC calculation
            wacc = (cost_of_equity * equity_ratio) + (cost_of_debt * debt_ratio * tax_shield)

            return wacc

        except Exception as e:
            self.logger.error(f"Error calculating WACC: {e}", exc_info=True)
            return Decimal("0.10")

    async def _project_cash_flows(
        self, financial_data: FinancialData, assumptions: Dict[str, Any]
    ) -> List[Dict[str, Decimal]]:
        """Project future cash flows"""
        try:
            time_horizon = assumptions.get("time_horizon", 5)
            growth_rate = financial_data.growth_rate
            terminal_growth_rate = assumptions.get("terminal_growth_rate", Decimal("0.03"))

            cash_flows = []
            current_revenue = financial_data.revenue
            current_ebitda = financial_data.ebitda

            for year in range(1, time_horizon + 1):
                # Project revenue
                projected_revenue = current_revenue * ((1 + growth_rate) ** year)

                # Project EBITDA (assuming constant margin)
                ebitda_margin = current_ebitda / current_revenue if current_revenue > 0 else 0
                projected_ebitda = projected_revenue * ebitda_margin

                # Project depreciation (simplified)
                depreciation = financial_data.depreciation * ((1 + growth_rate) ** year)

                # Project capex (simplified)
                capex = financial_data.capex * ((1 + growth_rate) ** year)

                # Calculate free cash flow
                free_cash_flow = projected_ebitda - depreciation - capex

                cash_flows.append(
                    {
                        "year": year,
                        "revenue": projected_revenue,
                        "ebitda": projected_ebitda,
                        "depreciation": depreciation,
                        "capex": capex,
                        "free_cash_flow": free_cash_flow,
                    }
                )

            return cash_flows

        except Exception as e:
            self.logger.error(f"Error projecting cash flows: {e}", exc_info=True)
            return []

    async def _calculate_present_value(
        self, cash_flows: List[Dict[str, Decimal]], wacc: Decimal
    ) -> Decimal:
        """Calculate present value of cash flows"""
        try:
            present_value = Decimal("0.0")

            for i, cash_flow in enumerate(cash_flows):
                year = i + 1
                fcf = cash_flow["free_cash_flow"]
                discount_factor = (1 + wacc) ** year
                pv = fcf / discount_factor
                present_value += pv

            return present_value

        except Exception as e:
            self.logger.error(f"Error calculating present value: {e}", exc_info=True)
            return Decimal("0.0")

    async def _calculate_terminal_value(
        self, last_cash_flow: Dict[str, Decimal], wacc: Decimal, terminal_growth_rate: Decimal
    ) -> Decimal:
        """Calculate terminal value"""
        try:
            last_fcf = last_cash_flow["free_cash_flow"]
            terminal_value = (last_fcf * (1 + terminal_growth_rate)) / (wacc - terminal_growth_rate)
            return terminal_value

        except Exception as e:
            self.logger.error(f"Error calculating terminal value: {e}", exc_info=True)
            return Decimal("0.0")

    async def _perform_dcf_sensitivity_analysis(
        self, financial_data: FinancialData, market_data: MarketData, assumptions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform DCF sensitivity analysis"""
        try:
            sensitivity = {}

            # Revenue sensitivity
            base_revenue = financial_data.revenue
            revenue_scenarios = [Decimal("0.9"), Decimal("1.0"), Decimal("1.1")]  # -10%, base, +10%
            revenue_sensitivity = {}

            for scenario in revenue_scenarios:
                adjusted_revenue = base_revenue * scenario
                # Simplified sensitivity calculation
                revenue_sensitivity[f"{int((scenario - 1) * 100)}%"] = adjusted_revenue * Decimal(
                    "2.5"
                )

            sensitivity["revenue_sensitivity"] = revenue_sensitivity

            # Growth rate sensitivity
            base_growth = financial_data.growth_rate
            growth_scenarios = [
                base_growth - Decimal("0.01"),
                base_growth,
                base_growth + Decimal("0.01"),
            ]
            growth_sensitivity = {}

            for scenario in growth_scenarios:
                growth_sensitivity[f"{int((scenario - base_growth) * 100)}%"] = (
                    financial_data.revenue * (Decimal("2.0") + scenario)
                )

            sensitivity["growth_rate_sensitivity"] = growth_sensitivity

            # Discount rate sensitivity
            base_wacc = await self._calculate_wacc(financial_data, market_data)
            wacc_scenarios = [base_wacc - Decimal("0.01"), base_wacc, base_wacc + Decimal("0.01")]
            wacc_sensitivity = {}

            for scenario in wacc_scenarios:
                wacc_sensitivity[f"{int((scenario - base_wacc) * 100)}%"] = (
                    financial_data.revenue * (Decimal("3.0") - scenario * 10)
                )

            sensitivity["discount_rate_sensitivity"] = wacc_sensitivity

            return sensitivity

        except Exception as e:
            self.logger.error(f"Error performing DCF sensitivity analysis: {e}", exc_info=True)
            return {}

    async def _get_industry_multiples(self, industry: IndustryCategory) -> Dict[str, Decimal]:
        """Get industry-specific multiples"""
        try:
            industry_multiples = self.industry_data.get(industry.value, {})
            return {
                "pe_ratio": industry_multiples.get("pe_ratio", Decimal("15.0")),
                "ev_ebitda_ratio": industry_multiples.get("ev_ebitda_ratio", Decimal("10.0")),
                "price_to_sales": industry_multiples.get("price_to_sales", Decimal("2.0")),
                "price_to_book": industry_multiples.get("price_to_book", Decimal("2.5")),
            }

        except Exception as e:
            self.logger.error(
                f"An unexpected error occurred getting industry multiples: {e}", exc_info=True
            )
            return {
                "pe_ratio": Decimal("15.0"),
                "ev_ebitda_ratio": Decimal("10.0"),
                "price_to_sales": Decimal("2.0"),
                "price_to_book": Decimal("2.5"),
            }

    async def _calculate_multiples_weights(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Decimal]:
        """Calculate weights for different multiples"""
        try:
            weights = {
                "pe": Decimal("0.3"),
                "ev_ebitda": Decimal("0.4"),
                "ps": Decimal("0.2"),
                "pb": Decimal("0.1"),
            }

            if business_type == BusinessType.STARTUP:
                weights = {
                    "pe": Decimal("0.1"),
                    "ev_ebitda": Decimal("0.3"),
                    "ps": Decimal("0.4"),
                    "pb": Decimal("0.2"),
                }
            elif business_type == BusinessType.ENTERPRISE:
                weights = {
                    "pe": Decimal("0.4"),
                    "ev_ebitda": Decimal("0.4"),
                    "ps": Decimal("0.1"),
                    "pb": Decimal("0.1"),
                }

            return weights

        except Exception as e:
            self.logger.error(
                f"Error calculating multiples weights: {e}", exc_info=True
            )
            return {
                "pe": Decimal("0.3"),
                "ev_ebitda": Decimal("0.4"),
                "ps": Decimal("0.2"),
                "pb": Decimal("0.1"),
            }

    async def _get_comparable_companies(
        self, industry: IndustryCategory, business_type: BusinessType
    ) -> List[Dict[str, Any]]:
        """Get comparable companies for multiples analysis"""
        try:
            # This would typically query a database of comparable companies
            # For now, return mock data
            return [
                {
                    "name": f"Company A ({industry.value})",
                    "pe_ratio": Decimal("15.0"),
                    "ev_ebitda_ratio": Decimal("10.0"),
                    "market_cap": 1000000000,
                },
                {
                    "name": f"Company B ({industry.value})",
                    "pe_ratio": Decimal("18.0"),
                    "ev_ebitda_ratio": Decimal("12.0"),
                    "market_cap": 1500000000,
                },
            ]

        except Exception as e:
            self.logger.error(f"Error getting comparable companies: {e}", exc_info=True)
            return []

    async def _calculate_valuation_range(self, valuations: List[Decimal]) -> Dict[str, Decimal]:
        """Calculate valuation range from multiple valuations"""
        try:
            if not valuations:
                return {"low": Decimal("0"), "high": Decimal("0"), "mid": Decimal("0")}

            valuations.sort()
            low = valuations[0]
            high = valuations[-1]
            mid = sum(valuations) / len(valuations)

            return {"low": low, "high": high, "mid": mid}

        except Exception as e:
            self.logger.error(f"Error calculating valuation range: {e}", exc_info=True)
            return {"low": Decimal("0"), "high": Decimal("0"), "mid": Decimal("0")}

    async def _get_asset_adjustment_factors(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Decimal]:
        """Get asset adjustment factors"""
        try:
            factors = {
                "book_value_factor": Decimal("1.0"),
                "liquidation_factor": Decimal("0.7"),
                "replacement_factor": Decimal("1.2"),
            }

            # Adjust based on business type
            if business_type == BusinessType.STARTUP:
                factors["book_value_factor"] = Decimal("0.8")
            elif business_type == BusinessType.ENTERPRISE:
                factors["book_value_factor"] = Decimal("1.1")

            return factors

        except Exception as e:
            self.logger.error(f"Error getting asset adjustment factors: {e}", exc_info=True)
            return {
                "book_value_factor": Decimal("1.0"),
                "liquidation_factor": Decimal("0.7"),
                "replacement_factor": Decimal("1.2"),
            }

    async def _calculate_liquidation_value(self, financial_data: FinancialData) -> Decimal:
        """Calculate liquidation value"""
        try:
            # Simplified liquidation value calculation
            liquidation_value = financial_data.total_assets * Decimal("0.7")  # 70% of book value
            return liquidation_value

        except Exception as e:
            self.logger.error(f"Error calculating liquidation value: {e}", exc_info=True)
            return financial_data.total_assets * Decimal("0.7")

    async def _calculate_replacement_cost(
        self, financial_data: FinancialData, industry: IndustryCategory
    ) -> Decimal:
        """Calculate replacement cost"""
        try:
            # Simplified replacement cost calculation
            replacement_cost = financial_data.total_assets * Decimal("1.2")  # 120% of book value
            return replacement_cost

        except Exception as e:
            self.logger.error(f"Error calculating replacement cost: {e}", exc_info=True)
            return financial_data.total_assets * Decimal("1.2")

    async def _calculate_intangible_assets(
        self, financial_data: FinancialData, business_type: BusinessType
    ) -> Decimal:
        """Calculate intangible assets value"""
        try:
            # Simplified intangible assets calculation
            if business_type == BusinessType.STARTUP:
                intangible_assets = financial_data.revenue * Decimal("0.5")  # 50% of revenue
            elif business_type == BusinessType.ENTERPRISE:
                intangible_assets = financial_data.revenue * Decimal("0.3")  # 30% of revenue
            else:
                intangible_assets = financial_data.revenue * Decimal("0.2")  # 20% of revenue

            return intangible_assets

        except Exception as e:
            self.logger.error(f"Error calculating intangible assets: {e}", exc_info=True)
            return financial_data.revenue * Decimal("0.2")

    async def _calculate_goodwill(
        self, financial_data: FinancialData, business_type: BusinessType, industry: IndustryCategory
    ) -> Decimal:
        """Calculate goodwill value"""
        try:
            # Simplified goodwill calculation
            goodwill = financial_data.revenue * Decimal("0.1")  # 10% of revenue
            return goodwill

        except Exception as e:
            self.logger.error(f"Error calculating goodwill: {e}", exc_info=True)
            return financial_data.revenue * Decimal("0.1")

    def _load_calculation_engines(self) -> Dict[str, Any]:
        """Load calculation engines configuration"""
        return {
            "dcf_engine": "dcf_calculator",
            "multiples_engine": "multiples_calculator",
            "asset_engine": "asset_calculator",
            "market_engine": "market_calculator",
        }

    def _load_industry_data(self) -> Dict[str, Any]:
        """Load industry-specific data"""
        return {
            "technology": {
                "pe_ratio": Decimal("20.0"),
                "ev_ebitda_ratio": Decimal("15.0"),
                "price_to_sales": Decimal("3.0"),
                "price_to_book": Decimal("4.0"),
            },
            "manufacturing": {
                "pe_ratio": Decimal("12.0"),
                "ev_ebitda_ratio": Decimal("8.0"),
                "price_to_sales": Decimal("1.5"),
                "price_to_book": Decimal("2.0"),
            },
            "retail": {
                "pe_ratio": Decimal("10.0"),
                "ev_ebitda_ratio": Decimal("6.0"),
                "price_to_sales": Decimal("1.0"),
                "price_to_book": Decimal("1.5"),
            },
            "services": {
                "pe_ratio": Decimal("15.0"),
                "ev_ebitda_ratio": Decimal("10.0"),
                "price_to_sales": Decimal("2.0"),
                "price_to_book": Decimal("2.5"),
            },
        }

    def _load_market_data(self) -> Dict[str, Any]:
        """Load market data configuration"""
        return {
            "risk_free_rate": Decimal("0.03"),
            "market_risk_premium": Decimal("0.06"),
            "default_beta": Decimal("1.0"),
        }
