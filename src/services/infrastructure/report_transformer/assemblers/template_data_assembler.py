"""
Template Data Assembler

WHAT: Assembles final template data dictionaries
WHY: Separates data assembly logic (SRP compliance)
HOW: Combines extracted, enriched, and transformed data into template format

SINGLE RESPONSIBILITY: Template data assembly ONLY
"""

from typing import Dict, Any, TYPE_CHECKING
from src.utils.logging import get_logger
from src.utils.decimal_helpers import pin_band_monotone
from src.services.infrastructure.report_confidence import (
    confidence_score_fraction,
    confidence_score_percent,
)

if TYPE_CHECKING:
    from src.api.schemas import ValuationRequest, ValuationResponse

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)

logger = get_logger(__name__)


class TemplateDataAssembler:
    """
    Assembles final template data dictionaries.
    
    SINGLE RESPONSIBILITY: Template data assembly ONLY
    
    NO extraction, NO enrichment, NO transformation - pure assembly only.
    """
    
    def __init__(self):
        """Initialize template data assembler."""
        self.logger = logger
    
    def assemble_accountant_view_data(
        self,
        response: ValuationResponseProtocol,
        transformed_sections: Dict[str, Any],
        methodology: str,
        enriched_business_data: Dict[str, Any],
        data_quality_analysis: Dict[str, Any],
        **additional_data
    ) -> Dict[str, Any]:
        """
        Assemble complete Accountant View template data.
        
        Args:
            response: ValuationResponse
            transformed_sections: Transformed section data
            methodology: Determined methodology
            enriched_business_data: Enriched business type data
            data_quality_analysis: Data quality analysis results
            **additional_data: Any additional data to include
        
        Returns:
            Complete template data dict
        """
        # Pin the band ``low ≤ mid ≤ high`` so a downstream engine regression
        # (Step 11 collapse, omni override drift, etc.) can never surface an
        # inverted range like the METANOUS €1.7M / €1.34M / €1.7M case in the
        # accountant-view roadmap headline. The pin is a no-op when the band
        # is already monotone — see ``utils.decimal_helpers.pin_band_monotone``.
        _pinned_low, _pinned_mid, _pinned_high = pin_band_monotone(
            response.equity_value_low,
            response.equity_value_mid,
            response.equity_value_high,
        )
        template_data = {
            'company_name': response.company_name,
            'valuation_date': response.valuation_date,
            'valuation_id': response.valuation_id,
            'industry': enriched_business_data.get('industry'),
            'valuation_range': {
                'low': _pinned_low,
                'mid': _pinned_mid,
                'high': _pinned_high,
                'confidence': confidence_score_fraction(response.confidence_score)
            },
            'methodology': methodology,
            'confidence_score': confidence_score_percent(response.confidence_score),
            'confidence_level': str(response.overall_confidence.value if hasattr(response.overall_confidence, 'value') else response.overall_confidence),
            **transformed_sections,
            **data_quality_analysis,
            **enriched_business_data,
            **additional_data,
        }
        
        self.logger.info(
            "Accountant View template data assembled",
            extra={
                'company_name': response.company_name,
                'top_level_keys': len(template_data)
            }
        )
        
        return template_data
    
    def assemble_info_tab_data(
        self,
        basic_data: Dict[str, Any],
        calculation_steps: list,
        enriched_business_data: Dict[str, Any],
        **additional_data
    ) -> Dict[str, Any]:
        """
        Assemble complete Info Tab template data.
        
        Args:
            basic_data: Basic response data
            calculation_steps: 12-step calculation journey
            enriched_business_data: Enriched business type data
            **additional_data: Any additional data
        
        Returns:
            Complete info tab data dict
        """
        info_tab_data = {
            **basic_data,
            'calculation_steps': calculation_steps,
            **enriched_business_data,
            **additional_data,
        }
        
        self.logger.info(
            "Info Tab template data assembled",
            extra={
                'company_name': basic_data.get('company_name'),
                'calculation_steps_count': len(calculation_steps) if calculation_steps else 0
            }
        )
        
        return info_tab_data
