
from src.errors.error_types import ValidationError
from src.utils.exceptions import CalculationError, DCFCalculationError, MultiplesCalculationError

"""
Valuation Processor Service — DEPRECATED / LEGACY

.. deprecated::
    The production valuation pipeline uses
    ``src.api.routes.valuation.orchestration.executors`` (DCF, Multiples,
    Hybrid executors) and ``ComprehensiveValuationOrchestrator``.  This
    module is still imported by ``ProgressiveValuationService`` and
    ``src.services.core.__init__`` but should not receive new features.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal
import math

from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.domain.models import FinancialData, YearData
from src.domain.financial_metrics import FinancialMetricsCalculator

# Lazy import to avoid circular dependency
# ValuationMetrics and MarketData will be imported when needed

logger = get_logger(__name__)


@dataclass
class DCFParameters:
    """Parameters for DCF valuation"""
    discount_rate: Decimal
    terminal_growth_rate: Decimal
    projection_years: int = 5
    terminal_value_multiple: Decimal = Decimal('10.0')


@dataclass
class MultiplesParameters:
    """Parameters for multiples valuation"""
    revenue_multiple: Decimal
    ebitda_multiple: Decimal
    pe_ratio: Decimal
    pb_ratio: Decimal


class ValuationProcessor:
    """
    Core valuation processing service.

    Provides the main valuation calculation logic including:
    - DCF (Discounted Cash Flow) calculations
    - Multiples-based valuations
    - Financial metrics computation
    - Sensitivity analysis
    """

    def __init__(self, financial_data: Optional[FinancialData] = None):
        """Initialize the valuation processor"""
        self.logger = logger
        self.financial_metrics_calculator = FinancialMetricsCalculator(financial_data) if financial_data else None

        # Default parameters
        self.default_dcf_params = DCFParameters(
            discount_rate=Decimal('0.10'),
            terminal_growth_rate=Decimal('0.03'),
            projection_years=5,
            terminal_value_multiple=Decimal('10.0')
        )

        self.default_multiples_params = MultiplesParameters(
            revenue_multiple=Decimal('2.5'),
            ebitda_multiple=Decimal('8.0'),
            pe_ratio=Decimal('15.0'),
            pb_ratio=Decimal('2.0')
        )

    async     def calculate_dcf_valuation(
        self,
        financial_data: FinancialData,
        market_data: 'MarketData',
        dcf_params: Optional[DCFParameters] = None
    ) -> Dict[str, Any]:
        """
        Calculate DCF (Discounted Cash Flow) valuation.

        Args:
            financial_data: Financial data for the company
            market_data: Market data and rates
            dcf_params: DCF parameters (optional)

        Returns:
            DCF valuation result
        """
        try:
            params = dcf_params or self.default_dcf_params

            self.logger.info(
                "Starting DCF valuation calculation",
                company_name=financial_data.company_name,
                discount_rate=params.discount_rate,
                terminal_growth_rate=params.terminal_growth_rate
            )

            # Calculate free cash flows
            free_cash_flows = await self._calculate_free_cash_flows(
                financial_data, params
            )

            # Calculate terminal value
            terminal_value = await self._calculate_terminal_value(
                free_cash_flows[-1], params
            )

            # Discount cash flows to present value
            present_value_cash_flows = await self._discount_cash_flows(
                free_cash_flows, params.discount_rate
            )

            # Calculate enterprise value
            enterprise_value_decimal = sum(present_value_cash_flows) + terminal_value

            # Calculate equity value (assuming no debt for simplicity)
            equity_value_decimal = enterprise_value_decimal

            # Calculate sensitivity analysis
            sensitivity_analysis = await self._calculate_dcf_sensitivity(
                financial_data, market_data, params
            )

            result = {
                'methodology': 'dcf',
                'equity_value': from_decimal(equity_value_decimal),
                'enterprise_value': from_decimal(enterprise_value_decimal),
                'discount_rate': from_decimal(params.discount_rate),
                'terminal_growth_rate': from_decimal(params.terminal_growth_rate),
                'free_cash_flows': [from_decimal(fcf) for fcf in free_cash_flows],
                'terminal_value': from_decimal(terminal_value),
                'present_value_cash_flows': [from_decimal(pv) for pv in present_value_cash_flows],
                'sensitivity_analysis': sensitivity_analysis,
                'confidence_score': 0.8,
                'value_drivers': ['revenue_growth', 'profitability', 'discount_rate'],
                'risk_factors': ['projection_accuracy', 'terminal_value_assumptions']
            }

            self.logger.info(
                "DCF valuation calculation completed",
                company_name=financial_data.company_name,
                equity_value=from_decimal(equity_value_decimal),
                enterprise_value=from_decimal(enterprise_value_decimal)
            )

            return result

        except (DCFCalculationError, ValidationError) as e:
            # Re-raise specific errors
            raise
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            self.logger.error(f"Validation error calculating DCF valuation: {e}", extra={'error_type': type(e).__name__})
            raise ValidationError(f"Invalid input for DCF valuation: {e}") from e
        except DCFCalculationError as e:
            self.logger.error(f"Error calculating DCF valuation: {e}", extra={'error_type': type(e).__name__})
            raise DCFCalculationError(
                f"Failed to calculate DCF valuation: {e}",
                step="dcf_calculation",
                calculation_type="DCF Valuation",
                context={'error_type': type(e).__name__}
            ) from e

    async def calculate_multiples_valuation(
        self,
        financial_data: FinancialData,
        market_data: 'MarketData',
        multiples_params: Optional[MultiplesParameters] = None
    ) -> Dict[str, Any]:
        """
        Calculate multiples-based valuation.

        Args:
            financial_data: Financial data for the company
            market_data: Market data and benchmarks
            multiples_params: Multiples parameters (optional)

        Returns:
            Multiples valuation result
        """
        try:
            params = multiples_params or self.default_multiples_params

            self.logger.info(
                "Starting multiples valuation calculation",
                company_name=financial_data.company_name,
                revenue_multiple=params.revenue_multiple,
                ebitda_multiple=params.ebitda_multiple
            )

            # Calculate valuations using different multiples
            revenue_decimal = to_decimal(financial_data.revenue) if financial_data.revenue else Decimal('0')
            revenue_valuation_decimal = revenue_decimal * params.revenue_multiple
            
            ebitda_decimal = to_decimal(financial_data.ebitda) if financial_data.ebitda else Decimal('0')
            ebitda_valuation_decimal = ebitda_decimal * params.ebitda_multiple if financial_data.ebitda else Decimal('0')
            
            net_income_decimal = to_decimal(financial_data.net_income) if financial_data.net_income else Decimal('0')
            pe_valuation_decimal = net_income_decimal * params.pe_ratio if financial_data.net_income else Decimal('0')
            
            total_assets_decimal = to_decimal(financial_data.total_assets) if financial_data.total_assets else Decimal('0')
            pb_valuation_decimal = total_assets_decimal * params.pb_ratio if financial_data.total_assets else Decimal('0')

            # Weight the different valuations
            valuations = []
            weights = []

            if revenue_valuation_decimal > Decimal('0'):
                valuations.append(revenue_valuation_decimal)
                weights.append(Decimal('0.4'))  # 40% weight to revenue multiple

            if ebitda_valuation_decimal > Decimal('0'):
                valuations.append(ebitda_valuation_decimal)
                weights.append(Decimal('0.3'))  # 30% weight to EBITDA multiple

            if pe_valuation_decimal > Decimal('0'):
                valuations.append(pe_valuation_decimal)
                weights.append(Decimal('0.2'))  # 20% weight to P/E ratio

            if pb_valuation_decimal > Decimal('0'):
                valuations.append(pb_valuation_decimal)
                weights.append(Decimal('0.1'))  # 10% weight to P/B ratio

            # Calculate weighted average
            if valuations and weights:
                total_weight_decimal = sum(weights)
                weighted_sum_decimal = sum(v * w for v, w in zip(valuations, weights))
                weighted_valuation_decimal = weighted_sum_decimal / total_weight_decimal if total_weight_decimal > Decimal('0') else Decimal('0')
            else:
                weighted_valuation_decimal = revenue_valuation_decimal  # Fallback to revenue multiple

            # Calculate enterprise value (assuming no debt for simplicity)
            enterprise_value_decimal = weighted_valuation_decimal
            equity_value_decimal = enterprise_value_decimal

            # Calculate sensitivity analysis
            sensitivity_analysis = await self._calculate_multiples_sensitivity(
                financial_data, market_data, params
            )

            result = {
                'methodology': 'multiples',
                'equity_value': from_decimal(equity_value_decimal),
                'enterprise_value': from_decimal(enterprise_value_decimal),
                'revenue_valuation': from_decimal(revenue_valuation_decimal),
                'ebitda_valuation': from_decimal(ebitda_valuation_decimal),
                'pe_valuation': from_decimal(pe_valuation_decimal),
                'pb_valuation': from_decimal(pb_valuation_decimal),
                'weighted_valuation': from_decimal(weighted_valuation_decimal),
                'sensitivity_analysis': sensitivity_analysis,
                'confidence_score': 0.7,
                'value_drivers': ['industry_multiples', 'market_conditions'],
                'risk_factors': ['multiple_volatility', 'market_conditions']
            }

            self.logger.info(
                "Multiples valuation calculation completed",
                company_name=financial_data.company_name,
                equity_value=from_decimal(equity_value_decimal),
                enterprise_value=from_decimal(enterprise_value_decimal)
            )

            return result

        except (MultiplesCalculationError, ValidationError) as e:
            # Re-raise specific errors
            raise
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            self.logger.error(f"Validation error calculating multiples valuation: {e}", extra={'error_type': type(e).__name__})
            raise ValidationError(f"Invalid input for multiples valuation: {e}") from e
        except MultiplesCalculationError as e:
            self.logger.error(f"Error calculating multiples valuation: {e}", extra={'error_type': type(e).__name__})
            raise MultiplesCalculationError(
                f"Failed to calculate multiples valuation: {e}",
                step="multiples_calculation",
                calculation_type="Multiples Valuation",
                context={'error_type': type(e).__name__}
            ) from e

    async     def calculate_financial_metrics(
        self,
        financial_data: FinancialData
    ) -> 'ValuationMetrics':
        """
        Calculate comprehensive financial metrics.

        Args:
            financial_data: Financial data for the company

        Returns:
            Calculated financial metrics
        """
        try:
            self.logger.info(
                "Starting financial metrics calculation",
                company_name=financial_data.company_name
            )

            # Basic calculations - convert to Decimal
            revenue_decimal = to_decimal(financial_data.revenue or 0)
            ebitda_decimal = to_decimal(financial_data.ebitda or 0)
            net_income_decimal = to_decimal(financial_data.net_income or 0)
            total_assets_decimal = to_decimal(financial_data.total_assets or 0)
            total_debt_decimal = to_decimal(financial_data.total_debt or 0)
            cash_decimal = to_decimal(financial_data.cash or 0)
            equity_decimal = total_assets_decimal - total_debt_decimal

            # Profitability ratios
            gross_margin = from_decimal(ebitda_decimal / revenue_decimal) if revenue_decimal > Decimal('0') else 0.0
            operating_margin = from_decimal(ebitda_decimal / revenue_decimal) if revenue_decimal > Decimal('0') else 0.0
            net_margin = from_decimal(net_income_decimal / revenue_decimal) if revenue_decimal > Decimal('0') else 0.0

            # Efficiency ratios
            asset_turnover = from_decimal(revenue_decimal / total_assets_decimal) if total_assets_decimal > Decimal('0') else 0.0
            inventory_turnover = from_decimal(revenue_decimal / (total_assets_decimal * Decimal('0.3'))) if total_assets_decimal > Decimal('0') else 0.0  # Assume 30% inventory
            receivables_turnover = from_decimal(revenue_decimal / (total_assets_decimal * Decimal('0.2'))) if total_assets_decimal > Decimal('0') else 0.0  # Assume 20% receivables
            payables_turnover = from_decimal(revenue_decimal / (total_assets_decimal * Decimal('0.1'))) if total_assets_decimal > Decimal('0') else 0.0  # Assume 10% payables

            # Liquidity ratios
            current_ratio = from_decimal((cash_decimal + total_assets_decimal * Decimal('0.5')) / (total_debt_decimal * Decimal('0.3'))) if total_debt_decimal > Decimal('0') else 0.0  # Simplified
            quick_ratio = from_decimal(cash_decimal / (total_debt_decimal * Decimal('0.3'))) if total_debt_decimal > Decimal('0') else 0.0  # Simplified
            working_capital_ratio = from_decimal((cash_decimal + total_assets_decimal * Decimal('0.5') - total_debt_decimal * Decimal('0.3')) / revenue_decimal) if revenue_decimal > Decimal('0') else 0.0

            # Leverage ratios
            debt_to_equity = from_decimal(total_debt_decimal / equity_decimal) if equity_decimal > Decimal('0') else 0.0

            # Return ratios
            roe = from_decimal(net_income_decimal / equity_decimal) if equity_decimal > Decimal('0') else 0.0
            roa = from_decimal(net_income_decimal / total_assets_decimal) if total_assets_decimal > Decimal('0') else 0.0

            # Cash conversion cycle
            inventory_turnover_decimal = to_decimal(inventory_turnover)
            receivables_turnover_decimal = to_decimal(receivables_turnover)
            payables_turnover_decimal = to_decimal(payables_turnover)
            if inventory_turnover_decimal > Decimal('0') and receivables_turnover_decimal > Decimal('0') and payables_turnover_decimal > Decimal('0'):
                cash_conversion_cycle = from_decimal(
                    Decimal('365') / inventory_turnover_decimal + 
                    Decimal('365') / receivables_turnover_decimal - 
                    Decimal('365') / payables_turnover_decimal
                )
            else:
                cash_conversion_cycle = 0.0

            # Valuation multiples
            revenue_multiple_decimal = Decimal('2.5')  # Default
            ebitda_multiple_decimal = Decimal('8.0')  # Default
            pe_ratio_decimal = Decimal('15.0')  # Default
            pb_ratio_decimal = Decimal('2.0')  # Default

            # Calculate equity and enterprise values
            equity_value_decimal = revenue_decimal * revenue_multiple_decimal
            equity_value = from_decimal(equity_value_decimal)
            enterprise_value_decimal = equity_value_decimal + total_debt_decimal - cash_decimal
            enterprise_value = from_decimal(enterprise_value_decimal)

            # Lazy import to avoid circular dependency (acceptable adapter pattern)
            try:
                from src.api.routes.valuation.valuation_types import FinancialMetricsResponse as ValuationMetrics
            except ImportError:
                # Fallback: create a simple dict-based response
                logger.warning("FinancialMetricsResponse not available, using dict fallback")
                ValuationMetrics = None
            
            metrics_data = {
                'equity_value': equity_value,
                'enterprise_value': enterprise_value,
                'revenue_multiple': from_decimal(revenue_multiple_decimal),
                'ebitda_multiple': from_decimal(ebitda_multiple_decimal),
                'pe_ratio': from_decimal(pe_ratio_decimal),
                'pb_ratio': from_decimal(pb_ratio_decimal),
                'roe': roe,
                'roa': roa,
                'debt_to_equity': debt_to_equity,
                'current_ratio': current_ratio,
                'quick_ratio': quick_ratio,
                'gross_margin': gross_margin,
                'operating_margin': operating_margin,
                'net_margin': net_margin,
                'asset_turnover': asset_turnover,
                'inventory_turnover': inventory_turnover,
                'receivables_turnover': receivables_turnover,
                'payables_turnover': payables_turnover,
                'cash_conversion_cycle': cash_conversion_cycle,
                'working_capital_ratio': working_capital_ratio
            }
            
            if ValuationMetrics is not None:
                metrics = ValuationMetrics(**metrics_data)
            else:
                # Fallback to dict if API type not available
                metrics = metrics_data

            self.logger.info(
                "Financial metrics calculation completed",
                company_name=financial_data.company_name,
                equity_value=equity_value,
                roe=roe,
                roa=roa
            )

            return metrics

        except (ValidationError, CalculationError) as e:
            # Re-raise specific errors
            raise
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            self.logger.error(f"Validation error calculating financial metrics: {e}", extra={'error_type': type(e).__name__})
            raise ValidationError(f"Invalid input for financial metrics calculation: {e}") from e
        except Exception as e:
            self.logger.error(f"Error calculating financial metrics: {e}", extra={'error_type': type(e).__name__})
            raise CalculationError(
                f"Failed to calculate financial metrics: {e}",
                calculation_type="Financial Metrics",
                context={'error_type': type(e).__name__}
            ) from e

    async def _calculate_free_cash_flows(
        self,
        financial_data: FinancialData,
        params: DCFParameters
    ) -> List[Decimal]:
        """Calculate projected free cash flows"""
        try:
            # Start with current EBITDA
            current_ebitda_decimal = to_decimal(financial_data.ebitda) if financial_data.ebitda else Decimal('0')
            current_revenue_decimal = to_decimal(financial_data.revenue) if financial_data.revenue else Decimal('0')

            # Assume growth rates
            revenue_growth_rate_decimal = Decimal('0.05')  # 5% annual growth
            if current_revenue_decimal > Decimal('0'):
                ebitda_margin_decimal = current_ebitda_decimal / current_revenue_decimal
            else:
                ebitda_margin_decimal = Decimal('0.1')

            free_cash_flows = []

            for year in range(1, params.projection_years + 1):
                # Project revenue
                year_decimal = Decimal(str(year))
                growth_factor = (Decimal('1') + revenue_growth_rate_decimal) ** year_decimal
                projected_revenue_decimal = current_revenue_decimal * growth_factor

                # Project EBITDA
                projected_ebitda_decimal = projected_revenue_decimal * ebitda_margin_decimal

                # Assume capital expenditures and working capital changes
                capex_decimal = projected_revenue_decimal * Decimal('0.05')  # 5% of revenue
                working_capital_change_decimal = projected_revenue_decimal * Decimal('0.02')  # 2% of revenue

                # Calculate free cash flow
                free_cash_flow_decimal = projected_ebitda_decimal - capex_decimal - working_capital_change_decimal
                free_cash_flows.append(free_cash_flow_decimal)

            return free_cash_flows

        except DCFCalculationError as e:
            self.logger.error(f"Error calculating free cash flows: {e}")
            return []

    async def _calculate_terminal_value(
        self,
        final_cash_flow: Decimal,
        params: DCFParameters
    ) -> Decimal:
        """Calculate terminal value"""
        try:
            # Gordon Growth Model
            final_cash_flow_decimal = to_decimal(final_cash_flow) if not isinstance(final_cash_flow, Decimal) else final_cash_flow
            numerator = final_cash_flow_decimal * (Decimal('1') + params.terminal_growth_rate)
            denominator = params.discount_rate - params.terminal_growth_rate
            
            if denominator > Decimal('0'):
                terminal_value_decimal = numerator / denominator
            else:
                terminal_value_decimal = Decimal('0')

            return terminal_value_decimal

        except DCFCalculationError as e:
            self.logger.error(f"Error calculating terminal value: {e}")
            return Decimal('0')

    async def _discount_cash_flows(
        self,
        cash_flows: List[Decimal],
        discount_rate: Decimal
    ) -> List[Decimal]:
        """Discount cash flows to present value"""
        try:
            present_values = []

            for year, cash_flow in enumerate(cash_flows, 1):
                cash_flow_decimal = to_decimal(cash_flow) if not isinstance(cash_flow, Decimal) else cash_flow
                year_decimal = Decimal(str(year))
                discount_factor = (Decimal('1') + discount_rate) ** year_decimal
                present_value_decimal = cash_flow_decimal / discount_factor
                present_values.append(present_value_decimal)

            return present_values

        except DCFCalculationError as e:
            self.logger.error(f"Error discounting cash flows: {e}")
            return []

    async def _calculate_dcf_sensitivity(
        self,
        financial_data: FinancialData,
        market_data: 'MarketData',
        params: DCFParameters
    ) -> Dict[str, Any]:
        """Calculate DCF sensitivity analysis"""
        try:
            sensitivity = {}

            # Test different discount rates
            discount_rates = [params.discount_rate - 0.02, params.discount_rate, params.discount_rate + 0.02]
            for rate in discount_rates:
                # This would recalculate DCF with different rates
                sensitivity[f'discount_rate_{rate:.2f}'] = {
                    'equity_value': financial_data.revenue * (3.0 - rate * 10),  # Simplified
                    'impact': 'high' if abs(rate - params.discount_rate) > 0.01 else 'medium'
                }

            # Test different terminal growth rates
            growth_rates = [params.terminal_growth_rate - 0.01, params.terminal_growth_rate, params.terminal_growth_rate + 0.01]
            for rate in growth_rates:
                sensitivity[f'terminal_growth_{rate:.2f}'] = {
                    'equity_value': financial_data.revenue * (2.5 + rate * 20),  # Simplified
                    'impact': 'high' if abs(rate - params.terminal_growth_rate) > 0.005 else 'medium'
                }

            return sensitivity

        except DCFCalculationError as e:
            self.logger.error(f"Error calculating DCF sensitivity: {e}")
            return {}

    async def _calculate_multiples_sensitivity(
        self,
        financial_data: FinancialData,
        market_data: 'MarketData',
        params: MultiplesParameters
    ) -> Dict[str, Any]:
        """Calculate multiples sensitivity analysis"""
        try:
            sensitivity = {}

            # Test different revenue multiples
            revenue_multiples = [params.revenue_multiple - 0.5, params.revenue_multiple, params.revenue_multiple + 0.5]
            for multiple in revenue_multiples:
                sensitivity[f'revenue_multiple_{multiple:.1f}'] = {
                    'equity_value': financial_data.revenue * multiple,
                    'impact': 'high' if abs(multiple - params.revenue_multiple) > 0.25 else 'medium'
                }

            # Test different EBITDA multiples
            ebitda_multiples = [params.ebitda_multiple - 2.0, params.ebitda_multiple, params.ebitda_multiple + 2.0]
            for multiple in ebitda_multiples:
                if financial_data.ebitda:
                    sensitivity[f'ebitda_multiple_{multiple:.1f}'] = {
                        'equity_value': financial_data.ebitda * multiple,
                        'impact': 'high' if abs(multiple - params.ebitda_multiple) > 1.0 else 'medium'
                    }

            return sensitivity

        except MultiplesCalculationError as e:
            self.logger.error(f"Error calculating multiples sensitivity: {e}")
            return {}
