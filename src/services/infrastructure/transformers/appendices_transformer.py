"""
Appendices Transformer

Builds the appendices section of the valuation report.
"""

from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.infrastructure.step_data_builder import build_12_step_calculation_journey
from src.services.infrastructure.exceptions import DataTransformationError
from .base_transformer import BaseTransformer


class AppendicesTransformer(BaseTransformer):
    """Transformer for appendices section."""
    
    def transform(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> Dict[str, Any]:
        """
        Build appendices section.
        
        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            
        Returns:
            Dictionary with appendices data for template rendering
            
        Raises:
            MissingDataError: If required data is missing
            DataTransformationError: If transformation fails
        """
        # Validate inputs
        self._validate_inputs(response, request)
        
        self.logger.debug(
            "Building appendices section",
            extra={
                'company_name': response.company_name,
                'valuation_id': response.valuation_id,
                'has_historical_data': bool(request.historical_years_data)
            }
        )
        # Financial statements
        financial_statements = {'has_statements': False}
        if request.historical_years_data:
            income_statements = []
            for year_data in request.historical_years_data:
                income_statements.append({
                    'year': year_data.year,
                    'revenue': year_data.revenue,
                    'ebitda': year_data.ebitda,
                    'net_income': getattr(year_data, 'net_income', None)
                })
            if income_statements:
                financial_statements = {
                    'has_statements': True,
                    'income_statements': income_statements,
                    'balance_sheets': []  # Can be enhanced
                }
        
        try:
            # Calculation journey
            calculation_journey = build_12_step_calculation_journey(response, request)
            
            # BANK-GRADE: Ensure calculation_journey is always a list
            if not isinstance(calculation_journey, list):
                self.logger.warning(
                    "Calculation journey is not a list, converting",
                    extra={
                        'company_name': response.company_name,
                        'calculation_journey_type': type(calculation_journey).__name__
                    }
                )
                calculation_journey = []
            
            # BANK-GRADE: Validate calculation journey has expected structure
            if calculation_journey and len(calculation_journey) > 0:
                # Ensure each step has required fields for template rendering
                for i, step in enumerate(calculation_journey):
                    if isinstance(step, dict):
                        # Ensure required fields exist with defaults
                        if 'step_name' not in step:
                            step['step_name'] = f"Step {i+1}"
                        if 'status' not in step:
                            step['status'] = 'completed'
                        if 'rationale' not in step and 'explanation' not in step:
                            step['rationale'] = 'Calculation step executed'
                            step['explanation'] = 'Calculation step executed'
                    elif hasattr(step, '__dict__'):
                        # Convert object to dict if needed
                        step_dict = step.__dict__
                        if 'step_name' not in step_dict:
                            step_dict['step_name'] = f"Step {i+1}"
                        if 'status' not in step_dict:
                            step_dict['status'] = 'completed'
                        calculation_journey[i] = step_dict
            
            # BANK-GRADE: Build complete appendices structure with all required fields
            result = {
                'financial_statements': financial_statements,
                'calculation_journey': calculation_journey,
                'calculation_steps': calculation_journey,  # Alias for compatibility
                'ebitda_normalization_details': None,  # Can be enhanced
                # Academic references will be added by ReportRenderingCoordinator
                # but we ensure the structure exists
                'academic_references': None  # Placeholder - will be populated during rendering
            }
            
            # BANK-GRADE: Validate result structure
            if not isinstance(result, dict):
                raise ValueError(f"Appendices transformer returned non-dict: {type(result)}")
            
            # BANK-GRADE: Validate required fields are present
            required_fields = ['financial_statements', 'calculation_journey', 'calculation_steps']
            missing_fields = [field for field in required_fields if field not in result]
            if missing_fields:
                self.logger.warning(
                    "Missing required fields in appendices result, adding defaults",
                    extra={
                        'company_name': response.company_name,
                        'missing_fields': missing_fields
                    }
                )
                for field in missing_fields:
                    if field == 'financial_statements':
                        result[field] = {'has_statements': False}
                    elif field in ['calculation_journey', 'calculation_steps']:
                        result[field] = []
            
            self.logger.debug(
                "Appendices section built successfully",
                extra={
                    'company_name': response.company_name,
                    'has_financial_statements': financial_statements.get('has_statements', False),
                    'calculation_steps_count': len(calculation_journey) if isinstance(calculation_journey, list) else 0,
                    'has_academic_references_placeholder': 'academic_references' in result
                }
            )
            
            return result
        except (AttributeError, TypeError, KeyError, ValueError) as e:
            self.logger.error(
                "Error building appendices section",
                extra={
                    'company_name': getattr(response, 'company_name', 'Unknown'),
                    'error_type': type(e).__name__,
                    'error': str(e)
                },
                exc_info=True
            )
            raise DataTransformationError(
                f"Failed to build appendices: {e}",
                company_name=getattr(response, 'company_name', None)
            ) from e

