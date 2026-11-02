"""
Valuation Report Generation Service — DEPRECATED / LEGACY

.. deprecated::
    Production report generation is handled by
    ``src.api.routes.reports._build_report_context`` and
    ``src.services.infrastructure.main_report_data_aggregator``.
    This module has no active HTTP-route consumers.
"""

from src.utils.logging import get_logger
from collections.abc import Mapping
from typing import Optional, List
from datetime import datetime
from enum import Enum
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

from src.utils.exceptions import (
    CalculationError,
    ValidationError,
    DataQualityError,
)
# Built-in exceptions (ValueError, TypeError, AttributeError) don't need to be imported from src.errors

logger = get_logger(__name__)


class ValuationMethodology(str, Enum):
    """Supported valuation methodologies"""
    DCF = "dcf"
    MULTIPLES = "multiples"
    ASSET_BASED = "asset_based"
    SYNTHESIZED = "synthesized"


class ValuationError(Exception):
    """Base exception for valuation errors"""
    pass


class DataValidationError(ValuationError):
    """Raised when input data validation fails"""
    pass


class CalculationError(ValuationError):
    """Raised when valuation calculations fail"""
    pass


class ValuationReportService:
    """
    Core valuation report generation service

    Architecture Pattern:
    Based on Ilara Artemis ReportService with CRITICAL privacy enhancements
    for handling financial data.

    Pipeline (6 Steps):
    1. Validate private financial data
    2. Fetch public market context (from cache)
    3. Calculate financial metrics (private data)
    4. Render deterministic public market context
    5. Perform valuation calculations
    6. Assemble and validate report

    Privacy Guarantee:
    - Private financial data never leaves ValuationIQ
    - Titan owns external AI orchestration and audit
    - Strict audit logging for compliance
    """

    def __init__(
        self,
        market_service,
        calculation_service,
        ai_service,
        template_service,
        validation_service,
        privacy_guard
    ):
        """
        Initialize with injected dependencies for better testability

        Args:
            market_service: Market data fetching service (uses cache)
            calculation_service: Financial calculations (DCF, multiples, metrics)
            ai_service: Legacy parameter ignored; Titan owns AI orchestration
            template_service: Report template generation
            validation_service: Data and output validation
            privacy_guard: Privacy enforcement middleware
        """
        self.market_service = market_service
        self.calculation_service = calculation_service
        self.ai_service = None
        if ai_service is not None:
            logger.warning(
                "Ignoring legacy ValuationReportService ai_service; Titan owns AI orchestration"
            )
        self.template_service = template_service
        self.validation_service = validation_service
        self.privacy_guard = privacy_guard

        logger.info("ValuationReportService initialized")

    async def generate_valuation_report(
        self,
        request: "ValuationRequest",
        methodologies: Optional[List[ValuationMethodology]] = None
    ) -> "ValuationReport":
        """
        Main report generation orchestrator

        Clean, focused responsibility with proper error handling and privacy enforcement.

        Args:
            request: Valuation request with company data and parameters
            methodologies: List of valuation methods to use (defaults to all)

        Returns:
            Complete valuation report with results and market context

        Raises:
            DataValidationError: If input data is invalid
            CalculationError: If valuation calculations fail
            ValuationError: For other valuation errors
        """
        request_id = request.request_id or f"val_{int(datetime.utcnow().timestamp())}"

        logger.info(
            "Starting valuation report generation",
            request_id=request_id,
            company=request.company_name,
            industry=request.industry,
            methodologies=methodologies
        )

        try:
            # Step 1: Validate private financial data
            logger.info(f"[{request_id}] Step 1/6: Validating financial data")
            await self._validate_request(request)

            # Step 2: Fetch public market context (CACHED - fast!)
            logger.info(f"[{request_id}] Step 2/6: Fetching market context")
            market_context = await self.market_service.get_market_context(
                industry=request.industry,
                country=request.country_code,
                sector=getattr(request, 'sector', None)
            )

            logger.info(
                "Market context fetched successfully",
                request_id=request_id,
                industry_multiples=bool(market_context.get('industry_multiples')),
                economic_indicators=bool(market_context.get('economic_indicators'))
            )

            # Step 3: Calculate financial metrics (PRIVATE DATA - not cached)
            logger.info(f"[{request_id}] Step 3/6: Calculating financial metrics")
            metrics = await self.calculation_service.calculate_metrics(
                financial_data=request.financial_data
            )

            logger.info(
                "Financial metrics calculated",
                request_id=request_id,
                profitability_score=metrics.profitability_score,
                liquidity_score=metrics.liquidity_score,
                efficiency_score=metrics.efficiency_score
            )

            # Step 4: Render deterministic market context. Titan owns AI narrative.
            logger.info(f"[{request_id}] Step 4/6: Rendering deterministic market context")
            market_insights = self._build_market_insights(
                request=request,
                market_context=market_context,
                metrics=metrics,
            )

            logger.info(
                "Market context rendered successfully",
                request_id=request_id,
                insights_keys=list(market_insights.keys()),
            )

            # Step 5: Perform valuation calculations
            logger.info(f"[{request_id}] Step 5/6: Performing valuation")

            # Determine which methodologies to use
            if methodologies is None:
                methodologies = [
                    ValuationMethodology.DCF if request.use_dcf else None,
                    ValuationMethodology.MULTIPLES if request.use_multiples else None,
                    ValuationMethodology.ASSET_BASED if getattr(request, 'use_asset_based', False) else None
                ]
                methodologies = [m for m in methodologies if m is not None]

            valuation_results = {}

            for methodology in methodologies:
                logger.info(
                    f"Calculating {methodology.value} valuation",
                    request_id=request_id
                )

                result = await self.calculation_service.calculate_valuation(
                    methodology=methodology,
                    financial_data=request.financial_data,
                    market_context=market_context,
                    projection_years=getattr(request, 'projection_years', 5),
                    terminal_growth_rate=getattr(request, 'terminal_growth_rate', None)
                )

                valuation_results[methodology.value] = result

                logger.info(
                    f"{methodology.value.upper()} valuation complete",
                    request_id=request_id,
                    value_range=f"\u20AC{result['min_value']:,.0f} - \u20AC{result['max_value']:,.0f}"
                )

            # Synthesize multiple valuations
            synthesized_result = await self.calculation_service.synthesize_valuations(
                valuation_results
            )

            logger.info(
                "Valuation synthesis complete",
                request_id=request_id,
                final_value=f"\u20AC{synthesized_result['value']:,.0f}",
                confidence=synthesized_result['confidence']
            )

            # Step 6: Assemble report
            logger.info(f"[{request_id}] Step 6/6: Assembling report")

            report = await self.template_service.generate_report(
                request_id=request_id,
                company_info={
                    'name': request.company_name,
                    'industry': request.industry,
                    'country': request.country_code,
                },
                valuation_results=valuation_results,
                synthesized_result=synthesized_result,
                metrics=metrics,
                market_insights=market_insights,
                market_context=market_context
            )

            # Validate output
            validated_report = await self.validation_service.validate_report(report)

            logger.info(
                "✅ Valuation report generated successfully",
                request_id=request_id,
                company=request.company_name,
                valuation_range=f"\u20AC{synthesized_result['min_value']:,.0f} - \u20AC{synthesized_result['max_value']:,.0f}",
                final_value=f"\u20AC{synthesized_result['value']:,.0f}",
                methodologies=[m.value for m in methodologies]
            )

            return validated_report

        except DataValidationError as e:
            logger.error(
                "❌ Data validation error",
                request_id=request_id,
                error=str(e)
            )
            raise

        except CalculationError as e:
            logger.error(
                "❌ Calculation error",
                request_id=request_id,
                error=str(e)
            )
            # Try to generate fallback report
            return await self._generate_fallback_report(request, str(e))

        except Exception as e:
            logger.error(
                "💥 Unexpected error during valuation",
                request_id=request_id,
                error=str(e),
                error_type=type(e).__name__
            )
            # Try to generate fallback report
            return await self._generate_fallback_report(request, str(e))

    async def _validate_request(self, request: "ValuationRequest") -> None:
        """
        Validate incoming valuation request

        Checks:
        - Required fields present
        - Financial data validity
        - Reasonable value ranges
        - Methodology compatibility

        Args:
            request: Valuation request to validate

        Raises:
            DataValidationError: If validation fails
        """
        # Required fields
        if not request.company_name or len(request.company_name.strip()) < 2:
            raise DataValidationError("Company name is required and must be at least 2 characters")

        if not request.industry:
            raise DataValidationError("Industry classification is required")

        if not request.country_code:
            raise DataValidationError("Country code is required")

        # Financial data validation
        financial_data = request.financial_data

        if not financial_data:
            raise DataValidationError("Financial data is required")

        # Revenue validation
        revenue = financial_data.get('revenue', 0)
        if revenue <= 0:
            raise DataValidationError("Revenue must be positive")

        if revenue > 1_000_000_000_000:  # 1 trillion
            raise DataValidationError("Revenue seems unrealistically high")

        # EBITDA validation (can be negative)
        ebitda = financial_data.get('ebitda')
        if ebitda is None:
            raise DataValidationError("EBITDA is required")

        # Check if EBITDA margin is reasonable
        if ebitda / revenue < -1.0 or ebitda / revenue > 1.0:
            raise DataValidationError("EBITDA/Revenue ratio is out of reasonable range")

        # Assets validation
        total_assets = financial_data.get('total_assets', 0)
        if total_assets < 0:
            raise DataValidationError("Total assets cannot be negative")

        # Debt validation
        total_debt = financial_data.get('total_debt', 0)
        if total_debt < 0:
            raise DataValidationError("Total debt cannot be negative")

        # Methodology validation
        if not request.use_dcf and not request.use_multiples:
            raise DataValidationError("At least one valuation methodology must be selected")

        # DCF-specific validation
        if request.use_dcf:
            projection_years = getattr(request, 'projection_years', 5)
            if projection_years < 1 or projection_years > 20:
                raise DataValidationError("Projection years must be between 1 and 20")

        logger.info("Request validation passed", company=request.company_name)

    def _build_market_insights(
        self,
        request: "ValuationRequest",
        market_context: Mapping[str, object],
        metrics: object,
    ) -> dict[str, object]:
        """Build deterministic report context without external model calls."""
        industry = getattr(request, "industry", "the selected industry")
        country = getattr(request, "country_code", "the selected market")
        size_category = getattr(metrics, "size_category", "unknown")
        growth_category = getattr(metrics, "growth_category", "unknown")
        profitability_category = getattr(metrics, "profitability_category", "unknown")

        return {
            "key_findings": (
                f"Market context for {industry} in {country} was assembled from "
                "provided benchmark and economic data. "
                f"Company profile categories: size={size_category}, "
                f"growth={growth_category}, profitability={profitability_category}."
            ),
            "recommendations": [
                "Review benchmark inputs before external distribution.",
                "Validate company-specific adjustments with an advisor.",
                "Use Titan-owned AI services for any generated narrative.",
            ],
            "source": "valuationiq_deterministic_market_context",
            "market_data_available": bool(market_context),
        }

    async def _generate_fallback_report(
        self,
        request: "ValuationRequest",
        error: str
    ) -> "ValuationReport":
        """
        Generate fallback report when primary processing fails

        This ensures the user always gets SOME output, even if full processing fails.
        Uses simple heuristics and market averages.

        Args:
            request: Original valuation request
            error: Error message that triggered fallback

        Returns:
            Simplified valuation report with fallback calculations
        """
        logger.info(
            "📝 Generating fallback valuation report",
            company=request.company_name,
            error=error
        )

        # Simple fallback calculation using industry averages
        revenue = request.financial_data.get('revenue', 0)
        ebitda = request.financial_data.get('ebitda', 0)

        # Conservative industry average multiples
        fallback_revenue_multiple = 1.5
        fallback_ebitda_multiple = 8.0

        fallback_value = (
            (revenue * fallback_revenue_multiple * 0.4) +
            (ebitda * fallback_ebitda_multiple * 0.6)
        )

        fallback_report = {
            'request_id': request.request_id,
            'company_name': request.company_name,
            'valuation_date': datetime.utcnow().isoformat(),
            'status': 'fallback',
            'error_message': error,
            'fallback_valuation': {
                'value': fallback_value,
                'min_value': fallback_value * 0.7,
                'max_value': fallback_value * 1.3,
                'methodology': 'simple_multiples',
                'confidence': 'low',
                'note': 'Fallback valuation using conservative industry averages'
            },
            'warnings': [
                'Full valuation processing failed',
                'Using simplified fallback methodology',
                'Results should be used for indicative purposes only',
                'Consider manual review'
            ]
        }

        logger.warning(
            "Fallback report generated",
            company=request.company_name,
            fallback_value=f"\u20AC{fallback_value:,.0f}"
        )

        return fallback_report

    async def generate_executive_summary(
        self,
        valuation_report: "ValuationReport"
    ) -> str:
        """
        Generate executive summary from full valuation report

        Similar to Artemis's summary generation but for financial valuations.

        Args:
            valuation_report: Complete valuation report

        Returns:
            Executive summary text (markdown format)
        """
        try:
            # Extract key information
            company = valuation_report.get('company_name')
            final_value = valuation_report.get('synthesized_result', {}).get('value', 0)
            confidence = valuation_report.get('synthesized_result', {}).get('confidence', 'medium')

            methodologies = list(valuation_report.get('valuation_results', {}).keys())

            summary = f"""
# Executive Summary: {company} Valuation

## Valuation Overview
- **Enterprise Value**: €{final_value:,.0f}
- **Confidence Level**: {confidence.capitalize()}
- **Methodologies Used**: {', '.join(m.upper() for m in methodologies)}
- **Valuation Date**: {valuation_report.get('valuation_date')}

## Key Findings
{valuation_report.get('market_insights', {}).get('key_findings', 'Analysis based on market data and financial metrics.')}

## Market Context
- Industry trends aligned with company performance
- Economic indicators considered in valuation
- Comparable companies analysis conducted

## Recommendations
Based on current market conditions and company performance, this valuation provides a comprehensive assessment suitable for strategic planning, M&A discussions, and investment decisions.

*Generated by Upswitch Valuation Engine*
"""

            return summary.strip()

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error generating executive summary", extra={'error': str(e), 'error_type': type(e).__name__}, exc_info=True)
            return f"Executive Summary for {valuation_report.get('company_name', 'Company')}"


# Helper functions for backward compatibility

async def generate_valuation_report(
    request: "ValuationRequest",
    services: Mapping[str, object]
) -> "ValuationReport":
    """
    Convenience function for generating valuation reports

    Args:
        request: Valuation request
        services: Dictionary of required services

    Returns:
        Valuation report
    """
    report_service = ValuationReportService(
        market_service=services['market_service'],
        calculation_service=services['calculation_service'],
        ai_service=services.get('ai_service'),
        template_service=services['template_service'],
        validation_service=services['validation_service'],
        privacy_guard=services['privacy_guard']
    )

    return await report_service.generate_valuation_report(request)
