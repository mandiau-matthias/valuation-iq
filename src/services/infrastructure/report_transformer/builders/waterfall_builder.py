"""
Waterfall Builder

WHAT: Builds waterfall, journey, and analysis structures for reports
WHY: Separates waterfall building logic from orchestration (SRP compliance)
HOW: Delegates to existing builders, organizes waterfall-specific data

SINGLE RESPONSIBILITY: Waterfall and journey building ONLY
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)

logger = get_logger(__name__)


class WaterfallBuilder:
    """
    Builds waterfall, journey, and analysis structures.
    
    SINGLE RESPONSIBILITY: Waterfall and journey building ONLY
    
    This service builds:
    - Valuation waterfall (step-by-step value breakdown)
    - Multiple journey (multiple selection path)
    - Owner concentration analysis
    - Adjustments summary
    
    NO extraction, NO enrichment, NO validation - pure building only.
    """
    
    def __init__(self):
        """Initialize waterfall builder."""
        self.logger = logger
    
    def build_valuation_waterfall(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> List[Dict[str, Any]]:
        """
        Build valuation waterfall (step-by-step breakdown).
        
        WHAT: Creates waterfall showing value adjustments
        WHY: Templates need visual breakdown of valuation steps
        HOW: Extracts waterfall steps from response
        
        Args:
            response: ValuationResponse
            request: ValuationRequest
        
        Returns:
            List of waterfall steps with:
            - step_name: Name of the step
            - value: Value at this step
            - adjustment: Adjustment made
            - percentage: Percentage impact
        
        Example:
            >>> builder = WaterfallBuilder()
            >>> waterfall = builder.build_valuation_waterfall(response, request)
            >>> print(waterfall[0])
            # {'step_name': 'Base Enterprise Value', 'value': 1000000, ...}
        """
        waterfall_steps = []
        
        try:
            # Extract waterfall from response if available
            if hasattr(response, 'valuation_waterfall') and response.valuation_waterfall:
                waterfall_steps = self._convert_waterfall_to_dict(response.valuation_waterfall)
            else:
                # Build waterfall from response fields
                waterfall_steps = self._build_waterfall_from_response(response)
            
            self.logger.debug(
                "Valuation waterfall built",
                extra={
                    'company_name': response.company_name,
                    'waterfall_steps': len(waterfall_steps)
                }
            )
        
        except Exception as e:
            self.logger.warning(
                "Failed to build valuation waterfall",
                extra={
                    'company_name': response.company_name,
                    'error': str(e)
                }
            )
            waterfall_steps = []
        
        return waterfall_steps
    
    def build_multiple_journey(self, response: ValuationResponseProtocol) -> Dict[str, Any]:
        """
        Build multiple journey (how multiple was selected).
        
        WHAT: Shows the path from industry multiples to selected multiple
        WHY: Templates need to explain multiple selection methodology
        HOW: Extracts multiple_journey or multiple_pipeline from response
        
        Args:
            response: ValuationResponse
        
        Returns:
            Dict with multiple journey data:
            - industry_multiples: Industry average multiples
            - selected_multiple: Final selected multiple
            - adjustments: Adjustments made
            - rationale: Selection rationale
        """
        journey = {}
        
        try:
            # Check for multiple_journey in response
            if hasattr(response, 'multiple_journey') and response.multiple_journey:
                journey = self._convert_to_dict(response.multiple_journey)
            
            # Fallback to multiple_pipeline
            elif hasattr(response, 'multiple_pipeline') and response.multiple_pipeline:
                journey = {
                    'pipeline': self._convert_to_dict(response.multiple_pipeline),
                    'selected_multiple': getattr(response, 'selected_multiple', None),
                    'multiple_type': getattr(response, 'multiple_type', None),
                }
            
            self.logger.debug(
                "Multiple journey built",
                extra={
                    'company_name': response.company_name,
                    'has_journey': bool(journey)
                }
            )
        
        except Exception as e:
            self.logger.warning(
                "Failed to build multiple journey",
                extra={
                    'company_name': response.company_name,
                    'error': str(e)
                }
            )
        
        return journey
    
    def build_owner_concentration_analysis(
        self,
        response: ValuationResponseProtocol
    ) -> Optional[Dict[str, Any]]:
        """
        Build owner concentration analysis.
        
        WHAT: Analyzes impact of owner concentration on valuation
        WHY: Templates show owner dependency risk
        HOW: Extracts owner concentration data from response
        
        Args:
            response: ValuationResponse
        
        Returns:
            Owner concentration analysis dict or None:
            - concentration_level: Level of concentration
            - discount_applied: Discount percentage
            - rationale: Explanation
        """
        analysis = None
        
        try:
            # Check for owner concentration adjustment in response
            if hasattr(response, 'owner_concentration_adjustment'):
                adjustment = response.owner_concentration_adjustment
                
                if adjustment:
                    analysis = {
                        'concentration_level': getattr(adjustment, 'concentration_level', None),
                        'discount_applied': getattr(adjustment, 'discount_percentage', 0),
                        'impact_on_value': getattr(adjustment, 'impact_on_value', 0),
                        'rationale': getattr(adjustment, 'rationale', None),
                    }
            
            # Fallback: check for number_of_owners in response
            elif hasattr(response, 'number_of_owners'):
                num_owners = response.number_of_owners
                if num_owners:
                    analysis = {
                        'concentration_level': 'High' if num_owners == 1 else 'Medium' if num_owners <= 3 else 'Low',
                        'number_of_owners': num_owners,
                    }
            
            if analysis:
                self.logger.debug(
                    "Owner concentration analysis built",
                    extra={
                        'company_name': response.company_name,
                        'has_analysis': True
                    }
                )
        
        except Exception as e:
            self.logger.warning(
                "Failed to build owner concentration analysis",
                extra={
                    'company_name': response.company_name,
                    'error': str(e)
                }
            )
        
        return analysis
    
    def build_adjustments_summary(self, response: ValuationResponseProtocol) -> List[Dict[str, Any]]:
        """
        Build adjustments summary.
        
        WHAT: Summarizes all valuation adjustments
        WHY: Templates need comprehensive adjustment list
        HOW: Collects all adjustments from response
        
        Args:
            response: ValuationResponse
        
        Returns:
            List of adjustments with:
            - adjustment_type: Type of adjustment
            - percentage: Percentage impact
            - value_impact: Dollar impact
            - rationale: Explanation
        """
        adjustments = []
        
        try:
            # Collect adjustments from response
            adjustment_fields = [
                'owner_concentration_adjustment',
                'size_discount',
                'liquidity_discount',
                'control_premium',
                'minority_discount',
            ]
            
            for field in adjustment_fields:
                if hasattr(response, field):
                    adjustment = getattr(response, field)
                    if adjustment:
                        adjustments.append(self._convert_adjustment_to_dict(field, adjustment))
            
            self.logger.debug(
                "Adjustments summary built",
                extra={
                    'company_name': response.company_name,
                    'adjustments_count': len(adjustments)
                }
            )
        
        except Exception as e:
            self.logger.warning(
                "Failed to build adjustments summary",
                extra={
                    'company_name': response.company_name,
                    'error': str(e)
                }
            )
        
        return adjustments
    
    def _convert_waterfall_to_dict(self, waterfall) -> List[Dict[str, Any]]:
        """Convert waterfall object/list to dict list."""
        if isinstance(waterfall, list):
            return [self._convert_to_dict(step) for step in waterfall]
        elif hasattr(waterfall, '__dict__'):
            return [waterfall.__dict__]
        else:
            return []
    
    def _build_waterfall_from_response(self, response: ValuationResponseProtocol) -> List[Dict[str, Any]]:
        """Build waterfall steps from response fields."""
        steps = []
        
        # Base enterprise value
        if hasattr(response, 'enterprise_value_mid'):
            steps.append({
                'step_name': 'Base Enterprise Value',
                'value': response.enterprise_value_mid,
                'adjustment': None,
                'percentage': None,
            })
        
        # Adjustments
        if hasattr(response, 'equity_value_mid'):
            steps.append({
                'step_name': 'Equity Value',
                'value': response.equity_value_mid,
                'adjustment': response.equity_value_mid - response.enterprise_value_mid if hasattr(response, 'enterprise_value_mid') else None,
                'percentage': None,
            })
        
        return steps
    
    def _convert_to_dict(self, obj) -> Dict[str, Any]:
        """Convert object to dict."""
        if isinstance(obj, dict):
            return obj
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        elif hasattr(obj, 'dict'):
            return obj.dict()
        else:
            return {}
    
    def _convert_adjustment_to_dict(self, field_name: str, adjustment) -> Dict[str, Any]:
        """Convert adjustment to dict."""
        adjustment_dict = {
            'adjustment_type': field_name.replace('_', ' ').title(),
        }
        
        if isinstance(adjustment, dict):
            adjustment_dict.update(adjustment)
        elif hasattr(adjustment, '__dict__'):
            adjustment_dict.update(adjustment.__dict__)
        
        return adjustment_dict
