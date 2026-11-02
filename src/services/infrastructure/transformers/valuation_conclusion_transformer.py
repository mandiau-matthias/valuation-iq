"""
Valuation Conclusion Transformer

Builds the valuation conclusion section of the valuation report.
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest
    from src.services.infrastructure.translations import ReportTranslations

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.infrastructure.waterfall_builder import get_owner_concentration_adjustment
from src.services.infrastructure.exceptions import DataTransformationError
from src.utils.logging import get_logger
from .base_transformer import BaseTransformer
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.infrastructure.report_confidence import (
    confidence_score_display,
    confidence_score_percent,
)
from src.api.routes.valuation.steps.step_2_benchmarking.utils.data_source_formatter import DataSourceFormatter

logger = get_logger(__name__)


class ValuationConclusionTransformer(BaseTransformer):
    """Transformer for valuation conclusion section."""
    
    def _build_waterfall_summary(self, response: ValuationResponseProtocol) -> Dict[str, Any]:
        """
        Build waterfall summary from multiple_pipeline.
        
        Args:
            response: ValuationResponse with multiple_pipeline
            
        Returns:
            Dictionary with waterfall summary
        """
        waterfall_summary = {'has_waterfall': False, 'steps': []}
        
        if not response.multiple_pipeline or not response.multiple_pipeline.stages:
            return waterfall_summary
        
        waterfall_steps = []
        current_multiple = response.multiple_pipeline.initial_multiple
        current_ev = response.multiple_pipeline.initial_multiple * response.multiple_pipeline.metric_value
        
        for stage in response.multiple_pipeline.stages:
            # Safely access discount_percentage
            discount_percentage = None
            if isinstance(stage, dict):
                discount_percentage = stage.get('discount_percentage')
            else:
                discount_percentage = getattr(stage, 'discount_percentage', None)
            
            # Safely access other stage attributes
            step_number = stage.get('step_number') if isinstance(stage, dict) else getattr(stage, 'step_number', None)
            step_name = stage.get('step_name') if isinstance(stage, dict) else getattr(stage, 'step_name', 'Unknown')
            explanation = stage.get('explanation') if isinstance(stage, dict) else getattr(stage, 'explanation', None)
            multiple_after = stage.get('multiple_after') if isinstance(stage, dict) else getattr(stage, 'multiple_after', None)
            ev_after = stage.get('ev_after') if isinstance(stage, dict) else getattr(stage, 'ev_after', None)
            
            waterfall_steps.append({
                'step_number': step_number,
                'step_name': step_name,
                'description': explanation or f"{step_name} adjustment",
                'multiple_before': current_multiple,
                'multiple_after': multiple_after,
                'ev_before': current_ev,
                'ev_after': ev_after,
                'adjustment_percentage': discount_percentage
            })
            
            current_multiple = multiple_after if multiple_after is not None else current_multiple
            current_ev = ev_after if ev_after is not None else current_ev
        
        # Validate all waterfall_steps are dicts with adjustment_percentage
        for i, step in enumerate(waterfall_steps):
            if not isinstance(step, dict):
                logger.warning(
                    f"Waterfall step {i} in valuation_conclusion is not a dictionary, converting...",
                    extra={'step_type': type(step).__name__, 'step_index': i}
                )
                waterfall_steps[i] = dict(step) if hasattr(step, '__dict__') else {}
                step = waterfall_steps[i]
            
            if 'adjustment_percentage' not in step:
                discount_pct = step.get('discount_percentage')
                step['adjustment_percentage'] = discount_pct
        
        if waterfall_steps:
            waterfall_summary = {
                'has_waterfall': True,
                'steps': waterfall_steps
            }
        
        return waterfall_summary

    def _build_adjustment_rationales(self, response: ValuationResponseProtocol) -> Dict[str, Any]:
        """
        Build adjustment rationales from response.
        
        Args:
            response: ValuationResponse with adjustment data
            
        Returns:
            Dictionary with adjustment rationales
        """
        adjustment_rationales = {}
        
        if response.multiples_valuation:
            multiples = response.multiples_valuation
            owner_conc_adjustment = get_owner_concentration_adjustment(response)
            if owner_conc_adjustment is not None:
                adjustment_rationales['owner_concentration'] = {
                    'applied': True,
                    'rationale': f"Owner concentration adjustment of {owner_conc_adjustment:,.0f} applied due to key person dependency"
                }
            if multiples.size_discount:
                adjustment_rationales['size_discount'] = {
                    'rationale': f"Size discount of {multiples.size_discount:,.0f} applied to reflect company size relative to market comparables"
                }
            if multiples.liquidity_discount:
                adjustment_rationales['liquidity_discount'] = {
                    'applied': True,
                    'rationale': f"Liquidity discount of {multiples.liquidity_discount:,.0f} applied to reflect market liquidity constraints"
                }
        
        if response.owner_dependency_adjustment:
            adjustment_rationales['ownership_adjustment'] = {
                'applied': True,
                'rationale': f"Ownership adjustment of {response.owner_dependency_adjustment:,.0f} applied based on owner dependency analysis"
            }
        
        return adjustment_rationales

    def _build_range_methodology(self, response: ValuationResponseProtocol) -> Optional[Dict[str, Any]]:
        """
        Build range methodology information.
        
        Args:
            response: ValuationResponse with range_methodology
            
        Returns:
            Dictionary with range methodology info, or None
        """
        if not response.range_methodology:
            return None
        
        return {
            'is_multiple_dispersion': response.range_methodology == 'multiple_dispersion',
            'explanation': "Range based on P25/P50/P75 percentiles from comparables" if response.range_methodology == 'multiple_dispersion' else "Range based on confidence-adjusted spread"
        }

    def _build_recommendations(self, response: ValuationResponseProtocol, request: ValuationRequestProtocol) -> Dict[str, List[str]]:
        """
        Build recommendations for sale process, deal structure, and timing.
        
        Args:
            response: ValuationResponse
            request: ValuationRequest
            
        Returns:
            Dictionary with recommendations by category
        """
        recommendations = {
            'sale_process': [],
            'deal_structure': [],
            'timing': []
        }
        confidence_score_pct = confidence_score_percent(response.confidence_score)
        
        # Sale process recommendations
        if response.equity_value_mid:
            if response.equity_value_mid >= 1000000:
                recommendations['sale_process'].append("Consider engaging a professional M&A advisor to manage the sale process and maximize value")
                recommendations['sale_process'].append("Prepare comprehensive due diligence materials including financial statements, contracts, and operational documentation")
            else:
                recommendations['sale_process'].append("Consider a targeted approach to potential buyers in the same industry or strategic acquirers")
            recommendations['sale_process'].append("Ensure all financial records are current and audited to facilitate buyer due diligence")
        
        # Deal structure recommendations
        if confidence_score_pct is not None and confidence_score_pct < 75:
            recommendations['deal_structure'].append("Consider earnout structures to bridge valuation gaps and align buyer/seller interests")
        else:
            recommendations['deal_structure'].append("Cash consideration is recommended given the valuation confidence level")
        
        if response.multiples_valuation and hasattr(response.multiples_valuation, 'comparables_count') and response.multiples_valuation.comparables_count and response.multiples_valuation.comparables_count < 5:
            recommendations['deal_structure'].append("Given limited comparable data, consider structured payments tied to future performance")
        
        # Timing recommendations
        if request.current_year_data and request.current_year_data.revenue:
            revenue = request.current_year_data.revenue
            if revenue > 0:
                growth_rate = self._calculate_revenue_growth_rate(request)
                
                if growth_rate and growth_rate > 10:
                    recommendations['timing'].append("Current growth trajectory suggests optimal timing for sale within next 12-18 months")
                elif growth_rate and growth_rate < 0:
                    recommendations['timing'].append("Consider addressing declining revenue trends before initiating sale process")
                else:
                    recommendations['timing'].append("Stable performance suggests flexibility in sale timing; consider market conditions")
        
        if confidence_score_pct is not None and confidence_score_pct >= 80:
            recommendations['timing'].append("High confidence valuation supports immediate sale process initiation")
        
        return recommendations

    def _calculate_revenue_growth_rate(self, request: ValuationRequestProtocol) -> Optional[Decimal]:
        """
        Calculate revenue growth rate from historical data.
        
        Args:
            request: ValuationRequest with historical data
            
        Returns:
            Growth rate as percentage, or None
        """
        if not request.historical_years_data or len(request.historical_years_data) < 2:
            return None
        
        years = sorted([yd.year for yd in request.historical_years_data], reverse=True)
        if len(years) < 2:
            return None
        
        recent_revenue = next((yd.revenue for yd in request.historical_years_data if yd.year == years[0]), None)
        prior_revenue = next((yd.revenue for yd in request.historical_years_data if yd.year == years[1]), None)
        
        if recent_revenue is not None and prior_revenue is not None and prior_revenue > 0:
            growth_rate = self.safe_divide((recent_revenue - prior_revenue), prior_revenue, None)
            if growth_rate is not None:
                return growth_rate * 100
        
        return None

    def _build_assumptions(self, response: ValuationResponseProtocol, request: ValuationRequestProtocol, t: Optional["ReportTranslations"] = None) -> List[Dict[str, str]]:
        """
        Build valuation assumptions.
        
        Args:
            response: ValuationResponse
            request: ValuationRequest
            
        Returns:
            List of assumption dictionaries
        """
        assumptions = []
        
        # Revenue growth assumptions
        if request.historical_years_data and len(request.historical_years_data) > 0:
            assumptions.append({
                'category': 'Revenue Growth',
                'description': 'Assumed continuation of historical growth trends adjusted for market conditions',
                'impact': 'Moderate - Historical trends provide baseline but market conditions may vary'
            })
        else:
            assumptions.append({
                'category': 'Revenue Growth',
                'description': 'Assumed stable revenue based on current year performance',
                'impact': 'Moderate - Limited historical data constrains growth projections'
            })
        
        # EBITDA margin assumptions
        ebitda = self.get_ebitda_value(response, request)
        revenue = request.current_year_data.revenue if request.current_year_data else None
        if ebitda is not None and revenue is not None and revenue > 0:
            margin = self.safe_divide(ebitda, revenue, None)
            if margin is not None:
                margin = margin * 100
            else:
                margin = None
            assumptions.append({
                'category': 'EBITDA Margins',
                'description': f'Assumed maintenance of current normalized EBITDA margin of {margin:.1f}%',
                'impact': 'High - Margin sustainability directly affects valuation multiple'
            })
        
        # Market conditions assumptions
        assumptions.append({
            'category': 'Market Conditions',
            'description': 'Assumed stable market conditions consistent with valuation date',
            'impact': 'High - Market volatility can significantly affect valuation multiples'
        })
        
        # Multiples assumptions
        if response.multiples_valuation:
            multiples = response.multiples_valuation
            raw_source = getattr(multiples, 'data_source', 'Industry Database')
            data_source = DataSourceFormatter.format_data_source_display(raw_source)
            comparables_count = getattr(multiples, 'comparables_count', 0)
            _category_label = (
                t.transformer_method_label_market_multiples if t is not None else 'Market Multiples'
            )
            assumptions.append({
                'category': _category_label,
                'description': f'Based on {data_source} with {comparables_count} comparable companies, adjusted for size and risk differences',
                'impact': 'High - Multiple selection is primary driver of enterprise value'
            })
        
        # Discount rate assumptions (if DCF applicable)
        if response.dcf_valuation and response.dcf_weight and response.dcf_weight > 0:
            assumptions.append({
                'category': 'Discount Rates',
                'description': 'Based on industry benchmarks and company-specific risk factors',
                'impact': 'High - Discount rate directly affects present value calculations'
            })
        
        # Data quality assumptions
        confidence_score_pct = confidence_score_percent(response.confidence_score)
        if confidence_score_pct is not None and confidence_score_pct < 70:
            assumptions.append({
                'category': 'Data Quality',
                'description': f'Valuation confidence of {confidence_score_display(confidence_score_pct)}% reflects limitations in data quality or market comparability',
                'impact': 'High - Lower confidence indicates greater uncertainty in valuation conclusion'
            })
        
        return assumptions

    def _build_limitations(self, response: ValuationResponseProtocol) -> Dict[str, Any]:
        """
        Build valuation limitations.
        
        Args:
            response: ValuationResponse
            
        Returns:
            Dictionary with limitations description, items, and qualifications
        """
        limitations_items = []
        limitations_qualifications = []
        
        limitations_description = (
            "This valuation is subject to various limiting conditions that may affect its accuracy and applicability. "
            "The valuation is based on information available as of the valuation date and assumes normal market conditions."
        )
        
        # Build limitations items based on data quality and confidence
        confidence_score_pct = confidence_score_percent(response.confidence_score)
        if confidence_score_pct is not None and confidence_score_pct < 70:
            limitations_items.append("Lower confidence score indicates limitations in data quality or market comparability")
        
        if response.multiples_valuation:
            multiples = response.multiples_valuation
            comparables_count = getattr(multiples, 'comparables_count', 0)
            if comparables_count < 5:
                limitations_items.append(f"Limited comparable company data ({comparables_count} companies) may affect multiple accuracy")
            
            data_source = getattr(multiples, 'data_source', None)
            if data_source and 'fallback' in str(data_source).lower():
                limitations_items.append("Valuation based on fallback data sources with potentially reduced accuracy")
        
        # Add standard limitations
        limitations_items.append("This valuation is based on financial data and information provided by management")
        limitations_items.append("Projections and forecasts are estimates and actual results may vary")
        limitations_items.append("Market conditions may change, affecting the relevance of this valuation over time")
        
        if not limitations_items:
            limitations_items.append("Comparable transaction data may be limited in availability and relevance")
            limitations_items.append("The valuation does not account for potential synergies or strategic value to specific buyers")
            limitations_items.append("This valuation assumes normal market conditions and does not account for extraordinary events")
        
        # Build qualifications
        limitations_qualifications.append("This valuation has been prepared in accordance with professional valuation standards")
        limitations_qualifications.append(f"The valuation is based on information available as of {response.valuation_date}")
        limitations_qualifications.append("This valuation is subject to completion of due diligence")
        limitations_qualifications.append("The valuation does not constitute legal, tax, or investment advice")
        limitations_qualifications.append("Users should consult with appropriate professional advisors before making decisions based on this valuation")
        
        return {
            'description': limitations_description,
            'items': limitations_items,
            'qualifications': limitations_qualifications
        }
    
    def transform(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
    ) -> Dict[str, Any]:
        """
        Build valuation conclusion section.

        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            t: Optional pre-built ReportTranslations snapshot
            locale: Fallback locale when ``t`` is not provided

        Returns:
            Dictionary with valuation conclusion data for template rendering

        Raises:
            MissingDataError: If required data is missing
            DataTransformationError: If transformation fails
        """
        # Validate inputs
        self._validate_inputs(response, request)

        from src.services.infrastructure.translations import get_translations, normalize_report_locale
        _cc = str(getattr(request, "country_code", None) or "BE").strip().upper() or "BE"
        _t = t or get_translations(
            normalize_report_locale(locale),
            country_code=_cc,
        )

        self.logger.debug(
            "Building valuation conclusion section",
            extra={
                'company_name': response.company_name,
                'valuation_id': response.valuation_id,
                'equity_value_mid': response.equity_value_mid
            }
        )

        rationale = response.valuation_summary or f"Valuation of {response.company_name} based on market multiples methodology"

        # Build all sections
        waterfall_summary = self._build_waterfall_summary(response)
        adjustment_rationales = self._build_adjustment_rationales(response)
        range_methodology = self._build_range_methodology(response)
        recommendations = self._build_recommendations(response, request)
        assumptions = self._build_assumptions(response, request, _t)
        limitations = self._build_limitations(response)
        
        try:
            # BANK-GRADE: Build sensitivity analysis if possible
            sensitivity_analysis = None
            if response.equity_value_mid:
                try:
                    # Build basic sensitivity analysis based on multiple variations
                    sensitivity_items = []
                    
                    # Multiple sensitivity (±10%, ±20%)
                    if response.multiple_pipeline and response.multiple_pipeline.final_multiple:
                        base_multiple = response.multiple_pipeline.final_multiple
                        ebitda = self.get_ebitda_value(response, request)
                        
                        if ebitda and ebitda > 0:
                            # +10% multiple
                            high_multiple = base_multiple * 1.10
                            high_value = high_multiple * ebitda
                            sensitivity_items.append({
                                'assumption': f'Multiple +10% ({high_multiple:.2f}x)',
                                'impact': f"{high_value:,.0f}",
                                'scenario_type': 'upside'
                            })
                            
                            # -10% multiple
                            low_multiple = base_multiple * 0.90
                            low_value = low_multiple * ebitda
                            sensitivity_items.append({
                                'assumption': f'Multiple -10% ({low_multiple:.2f}x)',
                                'impact': f"{low_value:,.0f}",
                                'scenario_type': 'downside'
                            })
                    
                    if sensitivity_items:
                        sensitivity_analysis = sensitivity_items
                except Exception as e:
                    self.logger.warning(
                        "Failed to build sensitivity analysis, using None",
                        extra={
                            'company_name': response.company_name,
                            'error': str(e)
                        }
                    )
            
            # BANK-GRADE: Ensure all required fields are present with defaults
            result = {
                'rationale': rationale or f"Valuation of {response.company_name} based on market multiples methodology",
                'waterfall_summary': waterfall_summary if waterfall_summary else {'has_waterfall': False, 'steps': []},
                'value_drivers': getattr(response, 'key_value_drivers', None) or [],
                'risk_factors': getattr(response, 'risk_factors', None) or [],
                'adjustment_rationales': adjustment_rationales if adjustment_rationales else {},
                'range_methodology': range_methodology,
                'sensitivity_analysis': sensitivity_analysis,
                'recommendations': recommendations if recommendations else {
                    'sale_process': [],
                    'deal_structure': [],
                    'timing': []
                },
                'assumptions': assumptions if assumptions else [],
                'limitations': limitations if limitations else {
                    'description': 'This valuation is subject to various limiting conditions.',
                    'items': ['Valuation is valid only for the stated date.', 'No independent audit was performed.'],
                    'qualifications': []
                }
            }
            
            # BANK-GRADE: Validate result structure
            required_fields = [
                'rationale', 'waterfall_summary', 'value_drivers', 'risk_factors',
                'adjustment_rationales', 'range_methodology', 'sensitivity_analysis',
                'recommendations', 'assumptions', 'limitations'
            ]
            missing_fields = [field for field in required_fields if field not in result]
            if missing_fields:
                self.logger.warning(
                    "Missing required fields in valuation conclusion result",
                    extra={
                        'company_name': response.company_name,
                        'missing_fields': missing_fields
                    }
                )
            
            self.logger.debug(
                "Valuation conclusion section built successfully",
                extra={
                    'company_name': response.company_name,
                    'has_waterfall': waterfall_summary.get('has_waterfall', False) if waterfall_summary else False,
                    'assumptions_count': len(assumptions) if assumptions else 0,
                    'has_sensitivity_analysis': sensitivity_analysis is not None,
                    'recommendations_count': sum(len(v) if isinstance(v, list) else 0 for v in recommendations.values()) if recommendations else 0
                }
            )
            
            return result
        except (AttributeError, TypeError, KeyError, ValueError) as e:
            self.logger.error(
                "Error building valuation conclusion section",
                extra={
                    'company_name': getattr(response, 'company_name', 'Unknown'),
                    'error_type': type(e).__name__,
                    'error': str(e)
                },
                exc_info=True
            )
            raise DataTransformationError(
                f"Failed to build valuation conclusion: {e}",
                company_name=getattr(response, 'company_name', None)
            ) from e
