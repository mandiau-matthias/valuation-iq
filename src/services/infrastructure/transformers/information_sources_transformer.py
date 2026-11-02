"""
Information Sources Transformer

Builds the information sources section of the valuation report.
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
from src.services.infrastructure.report_confidence import (
    confidence_score_display,
    confidence_score_percent,
)
from src.api.routes.valuation.steps.step_2_benchmarking.utils.data_source_formatter import DataSourceFormatter


class InformationSourcesTransformer(BaseTransformer):
    """Transformer for information sources section."""

    def _build_data_sources(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        t: "ReportTranslations",
    ) -> list:
        """Build data sources list."""
        data_sources = []
        confidence_score_pct = confidence_score_percent(response.confidence_score)

        # Financial data source
        if request.current_year_data:
            data_sources.append({
                'type': 'Financial Statements',
                'description': t.transformer_info_source_financial_desc.format(
                    company=response.company_name
                ),
                'date_collected': response.valuation_date,
                'reliability': 'High' if confidence_score_pct is not None and confidence_score_pct >= 75 else 'Medium'
            })

        # Historical financial data
        if request.historical_years_data and len(request.historical_years_data) > 0:
            years_count = len(request.historical_years_data)
            data_sources.append({
                'type': 'Historical Financial Data',
                'description': f"{years_count} year(s) of historical financial statements and performance data",
                'date_collected': response.valuation_date,
                'reliability': 'High' if years_count >= 3 else 'Medium'
            })

        # Market multiples data source
        if response.multiples_valuation:
            multiples = response.multiples_valuation
            data_source_type = multiples.data_source if hasattr(multiples, 'data_source') and multiples.data_source else 'Industry Database'
            multiples_source = getattr(multiples, 'multiples_source', None) or data_source_type

            source_display = DataSourceFormatter.format_data_source_display(multiples_source)
            source_description = f"Market multiples data from {source_display}"

            # Add academic citations if available
            citations = DataSourceFormatter.format_academic_citations(multiples_source)
            if citations:
                source_description += f" ({citations})"

            if hasattr(multiples, 'comparables_count') and multiples.comparables_count:
                source_description += f" based on {multiples.comparables_count} comparable companies"

            data_sources.append({
                'type': t.transformer_method_label_market_multiples,
                'description': source_description,
                'date_collected': response.valuation_date,
                'reliability': 'High' if multiples.comparables_count and multiples.comparables_count >= 5 else 'Medium'
            })

        # DCF data source (if applicable)
        if response.dcf_valuation and response.dcf_weight and response.dcf_weight > 0:
            data_sources.append({
                'type': 'Discounted Cash Flow Analysis',
                'description': "Projected cash flow analysis and terminal value calculations",
                'date_collected': response.valuation_date,
                'reliability': 'High' if confidence_score_pct is not None and confidence_score_pct >= 75 else 'Medium'
            })

        return data_sources

    def _build_financial_statements(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        t: "ReportTranslations",
    ) -> list:
        """Build financial statements list."""
        financial_statements = []
        if request.historical_years_data:
            for year_data in request.historical_years_data:
                if hasattr(year_data, 'year') and year_data.year:
                    financial_statements.append(f"Financial statements for year {year_data.year}")
        if request.current_year_data:
            financial_statements.append(
                t.transformer_info_source_current_year_statements.format(
                    date=response.valuation_date
                )
            )

        return financial_statements if financial_statements else None
    
    def _build_market_data(self, response: ValuationResponseProtocol) -> list:
        """Build market data list."""
        market_data = []
        if response.multiples_valuation:
            multiples = response.multiples_valuation
            if hasattr(multiples, 'data_source') and multiples.data_source:
                source_display = DataSourceFormatter.format_data_source_display(multiples.data_source)
                citations = DataSourceFormatter.format_academic_citations(multiples.data_source)
                description = f"Market multiples from {source_display}"
                if citations:
                    description += f" ({citations})"
                market_data.append(description)
            if hasattr(multiples, 'comparables_count') and multiples.comparables_count:
                market_data.append(f"Comparable company analysis ({multiples.comparables_count} companies)")
            if hasattr(multiples, 'ebitda_multiple') and multiples.ebitda_multiple:
                market_data.append(f"EBITDA multiple: {multiples.ebitda_multiple:.2f}x")
            if hasattr(multiples, 'revenue_multiple') and multiples.revenue_multiple:
                market_data.append(f"Revenue multiple: {multiples.revenue_multiple:.2f}x")
        
        return market_data if market_data else None
    
    def _build_reliability_assessment(self, response: ValuationResponseProtocol) -> str:
        """Build reliability assessment text."""
        reliability_assessment = (
            f"The data sources used in this valuation have been assessed for reliability based on "
            f"the quality and completeness of the information provided. "
        )
        confidence_score_pct = confidence_score_percent(response.confidence_score)
        
        if confidence_score_pct is not None:
            score_display = confidence_score_display(confidence_score_pct)
            if confidence_score_pct >= 80:
                reliability_assessment += (
                    f"The overall confidence score of {score_display}% indicates high reliability "
                    f"of the valuation inputs and methodology."
                )
            elif confidence_score_pct >= 60:
                reliability_assessment += (
                    f"The overall confidence score of {score_display}% indicates moderate reliability. "
                    f"Some limitations in data quality or market comparability may affect the precision of the valuation."
                )
            else:
                reliability_assessment += (
                    f"The overall confidence score of {score_display}% indicates lower reliability. "
                    f"Significant limitations in data quality, market comparability, or other factors may affect the valuation conclusion."
                )
        else:
            reliability_assessment += (
                "The reliability of the valuation is based on the quality and completeness of the financial data "
                "and market information available at the valuation date."
            )
        
        return reliability_assessment
    
    def _build_limitations(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> str:
        """Build limitations text."""
        limitation_parts = []
        
        # Data quality limitations
        if request.historical_years_data and len(request.historical_years_data) < 3:
            limitation_parts.append(
                f"Limited historical data ({len(request.historical_years_data)} year(s)) may constrain trend analysis "
                "and normalization capabilities."
            )
        
        # Comparables limitations
        if response.multiples_valuation:
            multiples = response.multiples_valuation
            if hasattr(multiples, 'comparables_count') and multiples.comparables_count and multiples.comparables_count < 5:
                limitation_parts.append(
                    f"Limited comparable company data ({multiples.comparables_count} companies) may affect the precision "
                    "of market multiple selection."
                )
        
        # Confidence-based limitations
        confidence_score_pct = confidence_score_percent(response.confidence_score)
        if confidence_score_pct is not None and confidence_score_pct < 70:
            limitation_parts.append(
                f"The confidence score of {confidence_score_display(confidence_score_pct)}% reflects uncertainty in the valuation inputs "
                "or methodology, which should be considered when interpreting the valuation conclusion."
            )
        
        return " ".join(limitation_parts) if limitation_parts else None
    
    def transform(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
    ) -> Dict[str, Any]:
        """
        Build information sources section.

        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            t: Optional pre-built ReportTranslations snapshot
            locale: Fallback locale when ``t`` is not provided

        Returns:
            Dictionary with information sources data for template rendering

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
            "Building information sources section",
            extra={
                'company_name': response.company_name,
                'valuation_id': response.valuation_id
            }
        )

        # Build all components using helper methods
        data_sources = self._build_data_sources(response, request, _t)
        financial_statements = self._build_financial_statements(response, request, _t)
        market_data = self._build_market_data(response)
        reliability_assessment = self._build_reliability_assessment(response)
        limitations = self._build_limitations(response, request)
        
        try:
            result = {
                'data_sources': data_sources,
                'financial_statements': financial_statements,
                'market_data': market_data,
                'interviews': None,  # Optional - not typically available from automated valuation
                'documents_reviewed': None,  # Optional - not typically available from automated valuation
                'reliability_assessment': reliability_assessment,
                'limitations': limitations
            }
            
            self.logger.debug(
                "Information sources section built successfully",
                extra={
                    'company_name': response.company_name,
                    'data_sources_count': len(data_sources),
                    'has_limitations': bool(limitations)
                }
            )
            
            return result
        except (AttributeError, TypeError, KeyError) as e:
            self.logger.error(
                "Error building information sources section",
                extra={
                    'company_name': getattr(response, 'company_name', 'Unknown'),
                    'error_type': type(e).__name__,
                    'error': str(e)
                },
                exc_info=True
            )
            raise DataTransformationError(
                f"Failed to build information sources: {e}",
                company_name=getattr(response, 'company_name', None)
            ) from e
