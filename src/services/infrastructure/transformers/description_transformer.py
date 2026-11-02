"""
Description of Assignment Transformer

Builds the description of assignment section of the valuation report.
"""

from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.infrastructure.exceptions import DataTransformationError
from .base_transformer import BaseTransformer
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.infrastructure.report_confidence import (
    confidence_score_display,
    confidence_score_percent,
)


class DescriptionTransformer(BaseTransformer):
    """Transformer for description of assignment section."""
    
    def transform(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> Dict[str, Any]:
        """
        Build description of assignment section.
        
        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            
        Returns:
            Dictionary with description of assignment data for template rendering
            
        Raises:
            MissingDataError: If required data is missing
            DataTransformationError: If transformation fails
        """
        # Validate inputs
        self._validate_inputs(response, request)
        
        self.logger.debug(
            "Building description of assignment section",
            extra={
                'company_name': response.company_name,
                'valuation_id': response.valuation_id,
                'valuation_date': str(response.valuation_date)
            }
        )
        # Purpose of valuation
        purpose = (
            f"This valuation report provides an independent assessment of the fair market value "
            f"of {response.company_name} as of {response.valuation_date}. "
            f"The valuation is prepared for general business purposes, including potential "
            f"transaction planning, strategic decision-making, and financial reporting."
        )
        
        # Scope of work
        scope = (
            f"The valuation analysis includes a comprehensive review of the company's financial "
            f"performance, market position, and industry comparables. The analysis incorporates "
            f"market multiples methodology to determine the enterprise value and equity value "
            f"of the business. The valuation considers historical financial data, current market "
            f"conditions, and industry-specific factors relevant to {response.company_name}."
        )
        
        # Standard of value
        standard_of_value = "Fair Market Value"
        standard_of_value_description = (
            "Fair Market Value is defined as the price at which property would change hands "
            "between a willing buyer and a willing seller, neither being under any compulsion "
            "to buy or sell and both having reasonable knowledge of relevant facts. This standard "
            "assumes a hypothetical transaction in the most appropriate market for the subject interest."
        )
        
        # Premise of value
        premise_of_value = "Going Concern"
        premise_of_value_description = (
            "The valuation assumes the business will continue to operate as a going concern, "
            "generating future cash flows and maintaining its current business operations. "
            "This premise reflects the expectation that the business will continue operating "
            "in the ordinary course of business rather than being liquidated."
        )
        
        # Valuation date note
        valuation_date_note = (
            f"The valuation is based on information available as of {response.valuation_date}. "
            f"Subsequent events or changes in market conditions may affect the valuation conclusion. "
            f"The analysis reflects the company's financial position and market conditions as of this date."
        )
        
        # Intended users
        intended_users = (
            "This report is intended for use by the company's management, shareholders, "
            "potential investors, and other parties with a legitimate interest in understanding "
            "the company's valuation. The report may be used for transaction planning, strategic "
            "decision-making, financial reporting, or other business purposes."
        )
        
        # Other considerations (optional)
        other_considerations = None
        confidence_score_pct = confidence_score_percent(response.confidence_score)
        if confidence_score_pct is not None and confidence_score_pct < 70:
            other_considerations = (
                f"Note: The valuation confidence score of {confidence_score_display(confidence_score_pct)}% indicates "
                f"moderate uncertainty in the valuation conclusion. This may be due to limited "
                f"historical data, market volatility, or other factors affecting the reliability "
                f"of the valuation inputs."
            )
        
        try:
            result = {
                'purpose': purpose,
                'scope': scope,
                'standard_of_value': standard_of_value,
                'standard_of_value_description': standard_of_value_description,
                'premise_of_value': premise_of_value,
                'premise_of_value_description': premise_of_value_description,
                'valuation_date_note': valuation_date_note,
                'intended_users': intended_users,
                'other_considerations': other_considerations
            }
            
            self.logger.debug(
                "Description of assignment section built successfully",
                extra={
                    'company_name': response.company_name,
                    'has_other_considerations': other_considerations is not None
                }
            )
            
            return result
        except (AttributeError, TypeError, KeyError) as e:
            self.logger.error(
                "Error building description of assignment section",
                extra={
                    'company_name': getattr(response, 'company_name', 'Unknown'),
                    'error_type': type(e).__name__,
                    'error': str(e)
                },
                exc_info=True
            )
            raise DataTransformationError(
                f"Failed to build description of assignment: {e}",
                company_name=getattr(response, 'company_name', None)
            ) from e
