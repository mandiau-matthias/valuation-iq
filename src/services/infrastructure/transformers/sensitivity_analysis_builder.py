"""
Sensitivity Analysis Builder

Builds sensitivity analysis data showing valuation impact of different EBITDA
bases and multiple ranges per AICPA BVS-VII and Hitchner (2017) standards.

Academic Compliance:
- Hitchner (2017): Financial Valuation, Chapter 12 - Scenario Analysis
- AICPA BVS-VII: Comprehensive valuations require sensitivity analysis
- McKinsey (2015): Scenario modeling for valuation uncertainty quantification
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SensitivityAnalysisBuilder:
    """Builds sensitivity analysis for valuation scenarios."""
    
    def build_sensitivity_analysis(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> Optional[Dict[str, Any]]:
        """
        Build sensitivity analysis showing valuation under different scenarios.
        
        Scenarios:
        1. EBITDA Basis Scenarios:
           - Conservative: 2024 EBITDA only
           - Base Case: Weighted/normalized EBITDA (current system)
           - Current Year: 2025 EBITDA only
           - 3-Year Average: Simple average of all years
        
        2. Multiple Range Scenarios:
           - P25 (Conservative)
           - P50 (Median) - Base case
           - P75 (Optimistic)
        
        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest with historical data
            
        Returns:
            Dictionary with sensitivity analysis data, or None if insufficient data
        """
        try:
            # Extract required data
            base_valuation = to_decimal(getattr(response, 'equity_value_mid', 0))
            if base_valuation <= 0:
                logger.warning("Cannot build sensitivity analysis: base_valuation is zero")
                return None
            
            # Extract base multiple (calibrated)
            base_multiple = self._extract_final_multiple(response)
            if not base_multiple or base_multiple <= 0:
                logger.warning("Cannot build sensitivity analysis: base_multiple not available")
                return None
            
            # Extract base EBITDA (what was used in calculation)
            base_ebitda = to_decimal(getattr(response, 'ebitda', 0))
            if base_ebitda is None or (base_ebitda == Decimal("0") and base_multiple > 0):
                base_ebitda = base_valuation / base_multiple if base_multiple > 0 else Decimal("0")
            
            # Extract historical EBITDA values
            current_year_ebitda = None
            historical_ebitdas = []
            
            if hasattr(request, 'current_year_data') and request.current_year_data:
                current_year_ebitda = to_decimal(getattr(request.current_year_data, 'ebitda', None))
            
            if hasattr(request, 'historical_years_data') and request.historical_years_data:
                for year_data in request.historical_years_data:
                    ebitda = to_decimal(getattr(year_data, 'ebitda', None))
                    if ebitda:
                        historical_ebitdas.append({
                            'year': getattr(year_data, 'year', None),
                            'ebitda': ebitda
                        })
            
            # Build EBITDA scenarios
            ebitda_scenarios = self._build_ebitda_scenarios(
                base_ebitda=base_ebitda,
                current_year_ebitda=current_year_ebitda,
                historical_ebitdas=historical_ebitdas,
                base_multiple=base_multiple,
                base_valuation=base_valuation
            )
            
            # Build multiple range scenarios
            multiple_range_scenarios = self._build_multiple_range_scenarios(
                base_ebitda=base_ebitda,
                base_multiple=base_multiple,
                response=response,
                base_valuation=base_valuation
            )
            
            # Calculate margin volatility note
            margin_volatility_note = self._calculate_margin_volatility_note(request)
            
            result = {
                'ebitda_scenarios': ebitda_scenarios,
                'multiple_range_scenarios': multiple_range_scenarios,
                'base_multiple': from_decimal(base_multiple),
                'base_ebitda': from_decimal(base_ebitda),
                'base_valuation': from_decimal(base_valuation),
                'margin_volatility_note': margin_volatility_note,
            }
            
            logger.info(
                "✅ Sensitivity analysis built successfully",
                extra={
                    'num_ebitda_scenarios': len(ebitda_scenarios),
                    'num_multiple_scenarios': len(multiple_range_scenarios),
                    'base_valuation': from_decimal(base_valuation),
                }
            )
            
            return result
            
        except (AttributeError, TypeError, ValueError, KeyError) as e:
            logger.warning(
                "Failed to build sensitivity analysis",
                extra={
                    'error_type': type(e).__name__,
                    'error': str(e),
                },
                exc_info=False
            )
            return None
    
    def _extract_final_multiple(self, response: ValuationResponseProtocol) -> Optional[Decimal]:
        """Extract final calibrated multiple from response."""
        try:
            # Try to get from multiples_valuation
            if hasattr(response, 'multiples_valuation') and response.multiples_valuation:
                final_multiple = getattr(response.multiples_valuation, 'final_ebitda_multiple', None)
                if final_multiple:
                    return to_decimal(final_multiple)
            
            # Fallback: Calculate from equity_value and ebitda
            equity_value = to_decimal(getattr(response, 'equity_value_mid', 0))
            ebitda = to_decimal(getattr(response, 'ebitda', 0))
            
            if equity_value > 0 and ebitda > 0:
                return equity_value / ebitda
            
            return None
            
        except (AttributeError, TypeError, ValueError, ZeroDivisionError):
            return None
    
    def _build_ebitda_scenarios(
        self,
        base_ebitda: Decimal,
        current_year_ebitda: Optional[Decimal],
        historical_ebitdas: List[Dict[str, Any]],
        base_multiple: Decimal,
        base_valuation: Decimal
    ) -> List[Dict[str, Any]]:
        """Build EBITDA basis scenarios."""
        scenarios = []
        safe_base = base_valuation if base_valuation and base_valuation > 0 else Decimal("1")

        # Scenario 1: Conservative (2024 only, if available)
        if historical_ebitdas and len(historical_ebitdas) >= 1:
            # Get most recent historical year (2024)
            most_recent_historical = sorted(historical_ebitdas, key=lambda x: x['year'], reverse=True)[0]
            conservative_ebitda = most_recent_historical['ebitda']
            conservative_valuation = conservative_ebitda * base_multiple
            
            scenarios.append({
                'name': f"Conservative ({most_recent_historical['year']} only)",
                'ebitda': from_decimal(conservative_ebitda),
                'multiple': from_decimal(base_multiple),
                'valuation': from_decimal(conservative_valuation),
                'variance_pct': from_decimal(((conservative_valuation - base_valuation) / safe_base * 100)),
                'is_base_case': False,
            })
        
        # Scenario 2: Base Case (Weighted/Normalized - current system)
        scenarios.append({
            'name': 'Base Case (Weighted)',
            'ebitda': from_decimal(base_ebitda),
            'multiple': from_decimal(base_multiple),
            'valuation': from_decimal(base_valuation),
            'variance_pct': 0.0,
            'is_base_case': True,
        })
        
        # Scenario 3: Current Year Only (if different from base)
        if current_year_ebitda and abs(current_year_ebitda - base_ebitda) > Decimal("1000"):
            current_year_valuation = current_year_ebitda * base_multiple
            scenarios.append({
                'name': 'Current Year (2025 only)',
                'ebitda': from_decimal(current_year_ebitda),
                'multiple': from_decimal(base_multiple),
                'valuation': from_decimal(current_year_valuation),
                'variance_pct': from_decimal(((current_year_valuation - base_valuation) / safe_base * 100)),
                'is_base_case': False,
            })
        
        # Scenario 4: 3-Year Simple Average (if 3+ years available)
        if current_year_ebitda and len(historical_ebitdas) >= 2:
            all_ebitdas = [h['ebitda'] for h in historical_ebitdas] + [current_year_ebitda]
            avg_ebitda = sum(all_ebitdas) / len(all_ebitdas)
            avg_valuation = avg_ebitda * base_multiple
            
            scenarios.append({
                'name': f'{len(all_ebitdas)}-Year Average',
                'ebitda': from_decimal(avg_ebitda),
                'multiple': from_decimal(base_multiple),
                'valuation': from_decimal(avg_valuation),
                'variance_pct': from_decimal(((avg_valuation - base_valuation) / safe_base * 100)),
                'is_base_case': False,
            })
        
        return scenarios
    
    def _build_multiple_range_scenarios(
        self,
        base_ebitda: Decimal,
        base_multiple: Decimal,
        response: ValuationResponseProtocol,
        base_valuation: Decimal
    ) -> List[Dict[str, Any]]:
        """Build multiple range scenarios (P25, P50, P75)."""
        scenarios = []
        safe_base = base_valuation if base_valuation and base_valuation > 0 else Decimal("1")

        # Extract market multiples from Step 2 if available
        p25_multiple = None
        p50_multiple = None
        p75_multiple = None
        
        if hasattr(response, 'detailed_results') and response.detailed_results:
            step_results = response.detailed_results.get('step_results', {})
            step2 = step_results.get(2)
            
            if step2 and hasattr(step2, 'result'):
                step2_result = step2.result
                _p25 = step2_result.get('ev_ebitda_p25')
                p25_multiple = to_decimal(_p25 if _p25 is not None else step2_result.get('multiples_p25'))
                _p50 = step2_result.get('ev_ebitda_p50')
                p50_multiple = to_decimal(_p50 if _p50 is not None else step2_result.get('multiples_p50'))
                _p75 = step2_result.get('ev_ebitda_p75')
                p75_multiple = to_decimal(_p75 if _p75 is not None else step2_result.get('multiples_p75'))
        
        # Fallback: Estimate from base multiple
        if not p50_multiple:
            p50_multiple = base_multiple
            p25_multiple = base_multiple * Decimal("0.8")
            p75_multiple = base_multiple * Decimal("1.2")
        elif not p25_multiple or not p75_multiple:
            p25_multiple = p50_multiple * Decimal("0.8")
            p75_multiple = p50_multiple * Decimal("1.2")
        
        # Calculate risk adjustments to get from market multiple to calibrated multiple
        # This preserves the company-specific adjustments (owner, size, liquidity)
        risk_adjustment_factor = base_multiple / p50_multiple if p50_multiple > 0 else Decimal("1.0")
        
        # Apply same risk adjustment factor to P25 and P75
        calibrated_p25 = p25_multiple * risk_adjustment_factor
        calibrated_p50 = p50_multiple * risk_adjustment_factor  # Should equal base_multiple
        calibrated_p75 = p75_multiple * risk_adjustment_factor
        
        # P25 Scenario (Conservative)
        p25_valuation = base_ebitda * calibrated_p25
        scenarios.append({
            'name': 'Conservative (P25)',
            'multiple': from_decimal(calibrated_p25),
            'valuation': from_decimal(p25_valuation),
            'variance_pct': from_decimal(((p25_valuation - base_valuation) / safe_base * 100)),
            'is_median': False,
        })
        
        # P50 Scenario (Median - Base Case)
        p50_valuation = base_ebitda * calibrated_p50
        scenarios.append({
            'name': 'Median (P50)',
            'multiple': from_decimal(calibrated_p50),
            'valuation': from_decimal(p50_valuation),
            'variance_pct': from_decimal(((p50_valuation - base_valuation) / safe_base * 100)),
            'is_median': True,
        })
        
        # P75 Scenario (Optimistic)
        p75_valuation = base_ebitda * calibrated_p75
        scenarios.append({
            'name': 'Optimistic (P75)',
            'multiple': from_decimal(calibrated_p75),
            'valuation': from_decimal(p75_valuation),
            'variance_pct': from_decimal(((p75_valuation - base_valuation) / safe_base * 100)),
            'is_median': False,
        })
        
        return scenarios
    
    def _calculate_margin_volatility_note(self, request: ValuationRequestProtocol) -> str:
        """Calculate margin volatility note for context."""
        try:
            margins = []
            
            if hasattr(request, 'current_year_data') and request.current_year_data:
                revenue = to_decimal(getattr(request.current_year_data, 'revenue', None))
                ebitda = to_decimal(getattr(request.current_year_data, 'ebitda', None))
                if revenue and ebitda and revenue > 0:
                    margin = (ebitda / revenue) * 100
                    margins.append(from_decimal(margin))
            
            if hasattr(request, 'historical_years_data') and request.historical_years_data:
                for year_data in request.historical_years_data:
                    revenue = to_decimal(getattr(year_data, 'revenue', None))
                    ebitda = to_decimal(getattr(year_data, 'ebitda', None))
                    if revenue and ebitda and revenue > 0:
                        margin = (ebitda / revenue) * 100
                        margins.append(from_decimal(margin))
            
            if len(margins) >= 2:
                min_margin = min(margins)
                max_margin = max(margins)
                margin_range = max_margin - min_margin
                return f"{min_margin:.1f}% - {max_margin:.1f}% (±{margin_range/2:.1f}pp variation)"
            elif len(margins) == 1:
                return f"{margins[0]:.1f}% (single year data)"
            else:
                return "Insufficient data for margin analysis"
                
        except (AttributeError, TypeError, ValueError, ZeroDivisionError) as e:
            logger.warning(f"Failed to calculate margin volatility note: {e}")
            return "Margin data unavailable"
