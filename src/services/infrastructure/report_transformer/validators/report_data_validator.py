"""
Report Data Validator

WHAT: Validates all report data structures comprehensively
WHY: Separates validation logic from orchestration (SRP compliance)
HOW: Validates inputs, outputs, steps, pipeline stages

SINGLE RESPONSIBILITY: Report data validation ONLY
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from src.utils.logging import get_logger
from src.services.infrastructure.exceptions import DataValidationError, MissingDataError

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest
    from src.services.infrastructure.translations import ReportTranslations

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)

logger = get_logger(__name__)


class ReportDataValidator:
    """
    Validates all report data structures.
    
    SINGLE RESPONSIBILITY: Report data validation ONLY
    
    This service validates:
    - Input validation (response and request)
    - Step output validation
    - Pipeline stage validation
    - Waterfall step validation
    
    NO extraction, NO transformation, NO enrichment - pure validation only.
    """
    
    def __init__(self):
        """Initialize report data validator."""
        self.logger = logger
    
    def validate_inputs(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ):
        """
        Validate critical inputs for report generation.
        
        WHAT: Checks if required fields are present
        WHY: Prevent errors during report generation
        HOW: Validates response and request have required fields
        
        Args:
            response: ValuationResponse
            request: ValuationRequest
        
        Raises:
            MissingDataError: If required fields are missing
            DataValidationError: If data is invalid
        
        Business Rules:
        - response.company_name is required
        - response.equity_value_mid is required
        - request must be provided
        """
        # Validate response
        if not response:
            raise MissingDataError(
                "ValuationResponse is required",
                missing_fields=['response']
            )
        
        if not hasattr(response, 'company_name') or not response.company_name:
            raise MissingDataError(
                "ValuationResponse missing required field: company_name",
                missing_fields=['company_name']
            )
        
        if not hasattr(response, 'equity_value_mid'):
            raise MissingDataError(
                "ValuationResponse missing required field: equity_value_mid",
                missing_fields=['equity_value_mid']
            )
        
        # Validate request
        if not request:
            raise MissingDataError(
                "ValuationRequest is required",
                missing_fields=['request']
            )
        
        self.logger.debug(
            "Inputs validated successfully",
            extra={
                'company_name': response.company_name,
                'has_request': request is not None
            }
        )
    
    def validate_step_outputs(self, calculation_steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate and fix step outputs.
        
        WHAT: Ensures all steps have valid output structures
        WHY: Templates expect consistent step output format
        HOW: Checks each step's outputs dict, adds defaults if missing
        
        Args:
            calculation_steps: List of calculation steps
        
        Returns:
            Validated/fixed calculation steps
        
        Business Rules:
        - Each step must have 'outputs' dict
        - outputs must be a dict (not None, not list)
        - Missing outputs are set to empty dict
        """
        if not calculation_steps:
            self.logger.warning("No calculation steps to validate")
            return calculation_steps
        
        fixed_count = 0
        
        for i, step in enumerate(calculation_steps):
            if not isinstance(step, dict):
                self.logger.warning(
                    "Step is not a dict, skipping validation",
                    extra={'step_index': i, 'step_type': type(step).__name__}
                )
                continue
            
            # Ensure 'outputs' exists and is a dict
            if 'outputs' not in step or not isinstance(step.get('outputs'), dict):
                step['outputs'] = {}
                fixed_count += 1
                
                self.logger.debug(
                    "Fixed missing or invalid outputs for step",
                    extra={
                        'step_index': i,
                        'step_number': step.get('step_number'),
                        'step_name': step.get('step_name', 'Unknown')
                    }
                )
        
        if fixed_count > 0:
            self.logger.info(
                "Fixed step outputs",
                extra={
                    'total_steps': len(calculation_steps),
                    'fixed_count': fixed_count
                }
            )
        
        return calculation_steps
    
    def validate_pipeline_stages(self, info_tab_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate pipeline stages in info tab data.
        
        WHAT: Ensures multiple_pipeline has valid structure
        WHY: Templates expect specific pipeline format
        HOW: Validates pipeline dict structure
        
        Args:
            info_tab_data: Info tab data dict
        
        Returns:
            Validated info tab data
        
        Business Rules:
        - multiple_pipeline should be a dict
        - If invalid, set to empty dict
        """
        if 'multiple_pipeline' in info_tab_data:
            pipeline = info_tab_data['multiple_pipeline']
            
            if not isinstance(pipeline, dict):
                self.logger.warning(
                    "Invalid multiple_pipeline type, setting to empty dict",
                    extra={'pipeline_type': type(pipeline).__name__}
                )
                info_tab_data['multiple_pipeline'] = {}
        
        return info_tab_data
    
    def validate_waterfall_steps(self, info_tab_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate waterfall steps in info tab data.
        
        WHAT: Ensures waterfall steps have valid structure
        WHY: Templates expect list of waterfall steps
        HOW: Validates waterfall is a list
        
        Args:
            info_tab_data: Info tab data dict
        
        Returns:
            Validated info tab data
        
        Business Rules:
        - valuation_waterfall should be a list
        - If invalid, set to empty list
        """
        if 'valuation_waterfall' in info_tab_data:
            waterfall = info_tab_data['valuation_waterfall']
            
            if not isinstance(waterfall, list):
                self.logger.warning(
                    "Invalid valuation_waterfall type, setting to empty list",
                    extra={'waterfall_type': type(waterfall).__name__}
                )
                info_tab_data['valuation_waterfall'] = []
        
        return info_tab_data
    
    def validate_business_type_characteristics(
        self,
        calculation_steps: List[Dict[str, Any]]
    ) -> bool:
        """
        Validate that business_type_characteristics exist in step outputs.
        
        WHAT: Checks if business_type_characteristics are present
        WHY: Templates require these characteristics
        HOW: Checks first step's outputs
        
        Args:
            calculation_steps: List of calculation steps
        
        Returns:
            True if characteristics present, False otherwise
        """
        if not calculation_steps or len(calculation_steps) == 0:
            return False
        
        first_step = calculation_steps[0]
        if not isinstance(first_step, dict):
            return False
        
        outputs = first_step.get('outputs', {})
        if not isinstance(outputs, dict):
            return False
        
        has_characteristics = 'business_type_characteristics' in outputs
        
        self.logger.debug(
            "Business type characteristics validation",
            extra={'has_characteristics': has_characteristics}
        )
        
        return has_characteristics
    
    def validate_and_enrich_template_data(
        self,
        template_data: Dict[str, Any],
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
        country_code: str = "BE",
    ) -> Dict[str, Any]:
        """
        Validate and enrich template data with defaults.

        WHAT: Ensures template data has all required fields
        WHY: Prevent template rendering errors
        HOW: Adds default values for missing fields

        Args:
            template_data: Template data dict
            t: Optional pre-built ReportTranslations snapshot
            locale: Fallback locale when ``t`` is not provided

        Returns:
            Validated and enriched template data

        Business Rules:
        - Add default empty values for optional fields
        - Ensure numeric fields are numeric (not None)
        """
        from src.services.infrastructure.translations import get_translations, normalize_report_locale
        _cc = str(country_code or "BE").strip().upper() or "BE"
        _t = t or get_translations(
            normalize_report_locale(locale),
            country_code=_cc,
        )

        # Ensure core fields exist
        if 'company_name' not in template_data:
            template_data['company_name'] = 'Unknown Company'

        # Ensure valuation range exists
        if 'valuation_range' not in template_data or not template_data['valuation_range']:
            template_data['valuation_range'] = {
                'low': 0,
                'mid': 0,
                'high': 0,
                'confidence': 0
            }

        # Ensure methodology exists
        if 'methodology' not in template_data:
            template_data['methodology'] = _t.transformer_method_label_market_multiples
        
        # Ensure calculation_steps exists
        if 'calculation_steps' not in template_data:
            template_data['calculation_steps'] = []
        
        self.logger.debug(
            "Template data validated and enriched",
            extra={
                'company_name': template_data.get('company_name'),
                'has_valuation_range': 'valuation_range' in template_data,
                'has_calculation_steps': 'calculation_steps' in template_data
            }
        )
        
        return template_data
