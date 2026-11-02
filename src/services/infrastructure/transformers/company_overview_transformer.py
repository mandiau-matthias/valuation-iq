"""
Company Overview Transformer

Builds the company overview section of the valuation report.
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


class CompanyOverviewTransformer(BaseTransformer):
    """Transformer for company overview section."""
    
    def transform(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> Dict[str, Any]:
        """
        Build company overview section.
        
        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            
        Returns:
            Dictionary with company overview data for template rendering
            
        Raises:
            MissingDataError: If required data is missing
            DataTransformationError: If transformation fails
        """
        # Validate inputs
        self._validate_inputs(response, request)
        
        self.logger.debug(
            "Building company overview section",
            extra={
                'company_name': response.company_name,
                'valuation_id': response.valuation_id,
                'industry': request.industry
            }
        )
        company_description = f"{response.company_name} is a {request.industry if request.industry else 'business'} company"
        if request.founding_year:
            company_description += f" founded in {request.founding_year}"
        if request.number_of_employees:
            company_description += f" with approximately {request.number_of_employees} employees"
        company_description += "."
        
        market_position = f"Operating in the {request.industry if request.industry else 'market'} sector"
        if request.country_code:
            market_position += f" in {request.country_code}"
        market_position += "."
        
        # Industry benchmarking
        industry_benchmarking = {}
        if response.multiples_valuation:
            multiples = response.multiples_valuation
            
            # Add revenue
            if request.current_year_data and request.current_year_data.revenue:
                industry_benchmarking['revenue'] = request.current_year_data.revenue
            
            ebitda_value = self.get_ebitda_value(response, request)
            if ebitda_value is not None:
                industry_benchmarking['ebitda'] = ebitda_value
            ebitda_margin = self.get_ebitda_margin(response, request)
            if ebitda_margin is not None:
                industry_benchmarking['ebitda_margin'] = ebitda_margin
            if hasattr(multiples, 'comparables_count') and multiples.comparables_count:
                industry_benchmarking['comparables_count'] = multiples.comparables_count
                industry_benchmarking['industry'] = request.industry if request.industry else 'N/A'
        
        # Industry analysis
        industry_analysis = f"The {request.industry if request.industry else 'industry'} sector"
        if response.multiples_valuation and hasattr(response.multiples_valuation, 'industry_trends'):
            industry_analysis += " shows strong market dynamics"
        industry_analysis += "."
        
        # Growth prospects
        growth_prospects = "The company demonstrates growth potential"
        if request.current_year_data and request.current_year_data.revenue:
            growth_prospects += f" with current revenue of \u20AC{request.current_year_data.revenue:,.0f}"
        growth_prospects += "."
        
        # Business strategy
        business_strategy = f"{response.company_name} focuses on"
        if request.business_model:
            business_model_value = request.business_model.value if hasattr(request.business_model, 'value') else str(request.business_model)
            business_strategy += f" {business_model_value} business model"
        business_strategy += "."
        
        try:
            result = {
                'company_description': company_description,
                'business_model': [],  # Can be enhanced
                'key_milestones': [],  # Can be enhanced
                'market_position': market_position,
                'competitive_advantages': [],  # Can be enhanced
                'industry_analysis': industry_analysis,
                'industry_benchmarking': industry_benchmarking if industry_benchmarking else None,
                'competitive_comparison': None,  # Can be enhanced with comparables data
                'industry_trends': [],  # Can be enhanced
                'growth_prospects': growth_prospects,
                'growth_opportunities': [],  # Can be enhanced
                'business_strategy': business_strategy,
                'strategic_initiatives': []  # Can be enhanced
            }
            
            self.logger.debug(
                "Company overview section built successfully",
                extra={
                    'company_name': response.company_name,
                    'has_industry_benchmarking': industry_benchmarking is not None
                }
            )
            
            return result
        except (AttributeError, TypeError, KeyError) as e:
            self.logger.error(
                "Error building company overview section",
                extra={
                    'company_name': getattr(response, 'company_name', 'Unknown'),
                    'error_type': type(e).__name__,
                    'error': str(e)
                },
                exc_info=True
            )
            raise DataTransformationError(
                f"Failed to build company overview: {e}",
                company_name=getattr(response, 'company_name', None)
            ) from e

