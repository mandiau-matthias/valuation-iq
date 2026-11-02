"""
Executive Summary Transformer

Builds the executive summary section of the valuation report.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest
    from src.services.infrastructure.translations import ReportTranslations

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.infrastructure.exceptions import DataTransformationError
from .base_transformer import BaseTransformer
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class ExecutiveSummaryTransformer(BaseTransformer):
    """Transformer for executive summary section."""

    def transform(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
    ) -> Dict[str, Any]:
        """
        Build executive summary section.
        
        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            
        Returns:
            Dictionary with executive summary data for template rendering
            
        Raises:
            MissingDataError: If required data is missing
            DataTransformationError: If transformation fails
        """
        # Validate inputs
        self._validate_inputs(response, request)
        
        from .executive_summary_builders import (
            PrimaryMethodBuilder,
            MethodologyDescriptionBuilder,
            NoticeBuilder,
            BusinessOverviewBuilder,
            FinancialHighlightsBuilder,
        )
        _cc = str(getattr(request, "country_code", None) or "BE").strip().upper() or "BE"
        
        self.logger.debug(
            "Building executive summary section",
            extra={
                'company_name': response.company_name,
                'valuation_id': response.valuation_id,
                'multiples_weight': response.multiples_weight,
                'dcf_weight': response.dcf_weight
            }
        )
        
        # Build individual sections using builders (locale-aware)
        primary_method, primary_method_explanation = PrimaryMethodBuilder.build(
            response, request, self.get_ebitda_value, t=t, locale=locale, country_code=_cc,
        )

        methodology_description = MethodologyDescriptionBuilder.build(
            response, t=t, locale=locale, country_code=_cc,
        )

        dcf_exclusion_notice = NoticeBuilder.build_dcf_exclusion_notice(response)
        methodology_downgrade_notice = NoticeBuilder.build_methodology_downgrade_notice(response)
        sme_calibration_notice = NoticeBuilder.build_sme_calibration_notice(
            response, t=t, locale=locale, country_code=_cc,
        )
        range_methodology_explanation = NoticeBuilder.build_range_methodology_explanation(
            response, t=t, locale=locale, country_code=_cc,
        )

        business_overview = BusinessOverviewBuilder.build(
            response, request, t=t, locale=locale, country_code=_cc,
        )

        financial_highlights = FinancialHighlightsBuilder.build(
            response, request, self.get_ebitda_value, self.logger, t=t, locale=locale, country_code=_cc,
        )

        try:
            result = {
                'methodology_description': methodology_description,
                'primary_method': primary_method,
                'primary_method_explanation': primary_method_explanation,
                'dcf_exclusion_notice': dcf_exclusion_notice,
                'methodology_downgrade_notice': methodology_downgrade_notice,
                'sme_calibration_notice': sme_calibration_notice,
                'range_methodology_explanation': range_methodology_explanation,
                'confidence_score': getattr(response, 'confidence_score', None),
                'business_overview': business_overview,
                'financial_highlights': financial_highlights,
                'value_drivers': getattr(response, 'key_value_drivers', None) or [],
                'risk_factors': getattr(response, 'risk_factors', None) or [],
                'recommendations': []
            }
            
            self.logger.debug(
                "Executive summary section built successfully",
                extra={
                    'company_name': response.company_name,
                    'primary_method': primary_method,
                    'has_value_drivers': len(result['value_drivers']) > 0,
                    'has_risk_factors': len(result['risk_factors']) > 0
                }
            )
            
            return result
        except (AttributeError, TypeError, KeyError) as e:
            self.logger.error(
                "Error building executive summary section",
                extra={
                    'company_name': getattr(response, 'company_name', 'Unknown'),
                    'error_type': type(e).__name__,
                    'error': str(e)
                },
                exc_info=True
            )
            raise DataTransformationError(
                f"Failed to build executive summary: {e}",
                company_name=getattr(response, 'company_name', None)
            ) from e

