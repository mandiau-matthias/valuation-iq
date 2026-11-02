from src.utils.exceptions import APIError, InvalidDiscountError

"""
PDF Report Generation Endpoints
Adapted from Ilara Artemis Template Pattern

Generates professional PDF valuation reports
"""

import asyncio
import io
import os
import time
import uuid
from datetime import datetime

# Import the valuation calculation logic
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from src.api.dependencies.cache_service import get_optional_cache_service
from src.api.routes.valuation.benchmark_contract_utils import (
    extract_request_resolved_benchmark_contract,
    request_allows_untrusted_multiples_fallback,
)

# Import orchestrator for comprehensive valuation
from src.api.routes.valuation.valuation_orchestrator import get_valuation_orchestrator
from src.api.routes.valuation_routes_types import (
    convert_request_to_domain,
    get_industry_benchmarks,
    get_market_context,
)
from src.api.schemas import ErrorResponse, ValuationRequest, ValuationResponse
from src.domain.financial_metrics import FinancialMetricsCalculator
from src.domain.synthesizer import ValuationSynthesizer
from src.middleware.auth import require_service_auth
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_service_auth)])


def _industry_benchmarks_for_request(request: ValuationRequest) -> Any:
    benchmark_contract = extract_request_resolved_benchmark_contract(request)
    allow_untrusted_fallback = request_allows_untrusted_multiples_fallback(request)
    if request.use_multiples and benchmark_contract is None and not allow_untrusted_fallback:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "BENCHMARK_CONTRACT_REQUIRED",
                "message": (
                    "PDF/HTML valuation reports will not use generic industry multiples. "
                    "Provide a resolved benchmark contract, disable use_multiples, "
                    "or explicitly opt into a disclosed untrusted fallback."
                ),
            },
        )

    industry_benchmarks = get_industry_benchmarks(
        request.industry.value,
        request.country_code,
    )
    if benchmark_contract:
        metrics = benchmark_contract.get("metrics", {})
        ev_ebitda = metrics.get("ev_ebitda", {}) if isinstance(metrics, dict) else {}
        ev_revenue = metrics.get("ev_revenue", {}) if isinstance(metrics, dict) else {}
        pe_ratio = metrics.get("pe_ratio", {}) if isinstance(metrics, dict) else {}
        if ev_ebitda.get("median") is not None:
            industry_benchmarks.median_ev_ebitda = to_decimal(ev_ebitda["median"])
        if ev_revenue.get("median") is not None:
            industry_benchmarks.median_ev_revenue = to_decimal(ev_revenue["median"])
        if pe_ratio.get("median") is not None:
            industry_benchmarks.median_pe = to_decimal(pe_ratio["median"])
    return industry_benchmarks


def _format_market_value(value: Any) -> str:
    if value is None:
        return "not available"
    if isinstance(value, Decimal):
        return str(from_decimal(value))
    return str(value)


def _build_public_market_insights(
    request: ValuationRequest,
    market_context: Any,
    industry_benchmarks: Any,
) -> str:
    """Render deterministic market context; Titan owns any AI-generated narrative."""
    industry = request.industry.value
    country = request.country_code
    benchmark_parts = [
        f"EV/revenue median {_format_market_value(industry_benchmarks.median_ev_revenue)}",
        f"EV/EBITDA median {_format_market_value(industry_benchmarks.median_ev_ebitda)}",
        f"P/E median {_format_market_value(industry_benchmarks.median_pe)}",
    ]
    market_parts = [
        "risk-free rate "
        f"{_format_market_value(getattr(market_context, 'government_bond_yield', None))}",
        "equity risk premium "
        f"{_format_market_value(getattr(market_context, 'equity_risk_premium', None))}",
        "long-term GDP growth "
        f"{_format_market_value(getattr(market_context, 'long_term_gdp_growth', None))}",
    ]
    return (
        f"Market analysis for {industry} in {country} is based on public market data, "
        f"resolved benchmark inputs ({'; '.join(benchmark_parts)}), and market assumptions "
        f"({'; '.join(market_parts)}). Consider advisor review for current market dynamics "
        "and company-specific positioning."
    )


@router.post(
    "/pdf",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Generate PDF valuation report",
    description="""
    Generate a professional PDF valuation report with:
    - Executive summary
    - Detailed financial analysis
    - Deterministic public market context
    - Valuation calculations
    - Risk assessment

    **Privacy Guarantee**: Private financial data never leaves the valuation engine.
    """,
    responses={
        200: {
            "description": "PDF report generated successfully",
            "content": {"application/pdf": {}},
        },
        400: {"model": ErrorResponse, "description": "Invalid request data"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def generate_valuation_pdf(request: ValuationRequest, http_request: Request) -> Response:
    """
    Generate comprehensive PDF valuation report.

    This endpoint:
    1. Calculates complete valuation (same as /calculate)
    2. Renders deterministic public market context
    3. Renders professional PDF report
    4. Returns downloadable PDF file
    """
    try:
        logger.info(
            "PDF report request received",
            company=request.company_name,
            industry=request.industry.value,
        )

        # Step 1: Calculate valuation (same as /calculate endpoint)
        financial_data = convert_request_to_domain(request)

        # Get cache service for performance optimization
        cache_service = await get_optional_cache_service(http_request)

        market_context = await get_market_context(
            request.country_code,
            request.government_bond_yield,
            request.long_term_gdp_growth,
            request.equity_risk_premium,
            cache_service=cache_service,
            economic_context=request.economic_context,
        )

        industry_benchmarks = _industry_benchmarks_for_request(request)

        synthesizer = ValuationSynthesizer(
            financial_data=financial_data,
            market_context=market_context,
            industry_benchmarks=industry_benchmarks,
            comparables=request.comparables,
        )

        result = synthesizer.synthesize_valuation(
            use_dcf=request.use_dcf,
            use_multiples=request.use_multiples,
            projection_years=request.projection_years,
            owner_profile_roster=request.owner_profile_roster,
        )

        metrics_calculator = FinancialMetricsCalculator(financial_data)
        health_description = metrics_calculator.get_financial_health_description(
            result.financial_metrics.financial_health_score
        )

        # Step 2: Render deterministic market context. Titan owns AI-generated narrative.
        market_insights_text = _build_public_market_insights(
            request=request,
            market_context=market_context,
            industry_benchmarks=industry_benchmarks,
        )

        # Step 3: Prepare data for template
        from src.services.infrastructure.translations import (
            get_translations,
            normalize_report_locale,
        )

        _pdf_locale = getattr(request, "locale", None) or "nl"
        _pdf_cc = str(getattr(request, "country_code", None) or "BE").strip().upper() or "BE"
        _pdf_t = get_translations(
            normalize_report_locale(_pdf_locale),
            country_code=_pdf_cc,
        )
        template_data = {
            "company_name": result.company_name,
            "industry": request.industry.value,
            "business_model": getattr(request, "business_model", "Standard"),
            "country_code": request.country_code,
            "report_date": datetime.now(),
            "valuation_id": str(uuid.uuid4()),
            # Valuation range
            "valuation_range_min": result.equity_value_low,
            "valuation_range_max": result.equity_value_high,
            "confidence_level": result.overall_confidence.value,
            # Key metrics with context
            "revenue_multiple": industry_benchmarks.median_ev_revenue,
            "ebitda_multiple": industry_benchmarks.median_ev_ebitda,
            "industry_average": industry_benchmarks.median_pe,
            # Multiples transparency data
            "multiples_source": "industry_benchmarks",  # or 'comparables' if available
            "comparables_count": getattr(result, "comparables_count", 0),
            "multiples_confidence": getattr(result, "multiples_confidence", "medium"),
            "current_revenue": request.revenue,
            "current_ebitda": request.ebitda,
            "size_discount": getattr(result, "size_discount", 0),
            "liquidity_discount": getattr(result, "liquidity_discount", 0),
            "country_adjustment": getattr(result, "country_adjustment", 0),
            # Valuation methods
            "valuation_methods": [
                {
                    "name": _pdf_t.transformer_method_label_dcf,
                    "weight": result.dcf_weight,
                    "value": result.equity_value_mid if request.use_dcf else 0,
                },
                {
                    "name": _pdf_t.transformer_method_label_market_multiples,
                    "weight": result.multiples_weight,
                    "value": result.equity_value_mid if request.use_multiples else 0,
                },
            ],
            # Insights and risks
            "market_insights": market_insights_text,
            "risk_factors": result.risk_factors,
        }

        # Step 4: Generate PDF
        from src.services.infrastructure.template_service import get_template_service

        template_service = get_template_service()

        pdf_bytes = template_service.generate_pdf(
            valuation_data=template_data, template_name="valuation_report.html"
        )

        # Step 5: Return PDF as downloadable file
        filename = f"valuation_report_{request.company_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/pdf",
            },
        )

    except APIError as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF generation failed. Please try again or contact support.",
        )


@router.post(
    "/html",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Generate HTML valuation report preview",
    description="""
    Generate an instant HTML preview of the valuation report.

    **Performance Benefits:**
    - Instant preview (no PDF generation overhead)
    - 3-5s faster than PDF generation
    - Mobile-friendly responsive design
    - Print-to-PDF available via browser

    **Use Cases:**
    - Quick preview before downloading PDF
    - Mobile/tablet viewing
    - Embedding in web applications

    **Privacy Guarantee**: Private financial data never leaves the valuation engine.
    """,
    responses={
        200: {"description": "HTML report generated successfully", "content": {"text/html": {}}},
        400: {"model": ErrorResponse, "description": "Invalid request data"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def generate_valuation_html(request: ValuationRequest, http_request: Request) -> Response:
    """
    Generate HTML valuation report preview.

    This endpoint:
    1. Calculates complete valuation (same as /calculate)
    2. Renders deterministic public market context
    3. Renders professional HTML report
    4. Returns HTML for instant preview

    **Aphrodite Caching**: Market data cached for <100ms response times
    """
    try:
        logger.info(
            "HTML report request received",
            company=request.company_name,
            industry=request.industry.value,
        )

        # Step 1: Calculate valuation (same as PDF endpoint)
        financial_data = convert_request_to_domain(request)

        # Get cache service for performance optimization
        cache_service = await get_optional_cache_service(http_request)

        market_context = await get_market_context(
            request.country_code,
            request.government_bond_yield,
            request.long_term_gdp_growth,
            request.equity_risk_premium,
            cache_service=cache_service,
            economic_context=request.economic_context,
        )

        industry_benchmarks = _industry_benchmarks_for_request(request)

        synthesizer = ValuationSynthesizer(
            financial_data=financial_data,
            market_context=market_context,
            industry_benchmarks=industry_benchmarks,
            comparables=request.comparables,
        )

        result = synthesizer.synthesize_valuation(
            use_dcf=request.use_dcf,
            use_multiples=request.use_multiples,
            projection_years=request.projection_years,
            owner_profile_roster=request.owner_profile_roster,
        )

        metrics_calculator = FinancialMetricsCalculator(financial_data)
        health_description = metrics_calculator.get_financial_health_description(
            result.financial_metrics.financial_health_score
        )

        # Step 2: Render deterministic market context. Titan owns AI-generated narrative.
        market_insights_text = _build_public_market_insights(
            request=request,
            market_context=market_context,
            industry_benchmarks=industry_benchmarks,
        )

        # Step 3: Prepare template data (same as PDF)
        from src.services.infrastructure.translations import (
            get_translations,
            normalize_report_locale,
        )

        _html_locale = getattr(request, "locale", None) or "nl"
        _html_cc = str(getattr(request, "country_code", None) or "BE").strip().upper() or "BE"
        _html_t = get_translations(
            normalize_report_locale(_html_locale),
            country_code=_html_cc,
        )
        template_data = {
            "valuation_id": str(uuid.uuid4()),
            "report_date": datetime.now(),
            "company_name": request.company_name,
            "industry": request.industry.value,
            "country": request.country_code,
            # Executive summary
            "valuation_range_min": result.valuation_range_lower,
            "valuation_range_max": result.valuation_range_upper,
            "confidence_level": result.confidence_level,
            # Valuation details
            "dcf_valuation": result.dcf_valuation,
            "multiples_valuation": result.multiples_valuation,
            "synthesized_valuation": result.synthesized_valuation,
            # Financial metrics
            "revenue": financial_data.current_year_data.revenue,
            "ebitda": financial_data.current_year_data.ebitda,
            "revenue_multiple": result.financial_metrics.revenue_multiple,
            "ebitda_multiple": result.financial_metrics.ebitda_multiple,
            "industry_average": industry_benchmarks.median_ev_ebitda,
            "financial_health_score": result.financial_metrics.financial_health_score,
            "health_description": health_description,
            # Valuation methods
            "valuation_methods": [
                {
                    "name": _html_t.transformer_method_label_dcf,
                    "weight": result.weights.get("dcf_weight", Decimal("0.0")),
                    "value": result.dcf_valuation,
                },
                {
                    "name": _html_t.transformer_method_label_market_multiples,
                    "weight": result.weights.get("multiples_weight", Decimal("0.0")),
                    "value": result.multiples_valuation,
                },
            ],
            # Insights and risks
            "market_insights": market_insights_text,
            "risk_factors": result.risk_factors,
        }

        # Prepare owner concentration data for template (if available)
        owner_concentration_data = None
        if result.multiples_valuation and hasattr(
            result.multiples_valuation, "owner_concentration"
        ):
            owner_conc = result.multiples_valuation.owner_concentration
            if owner_conc and owner_conc.get("ratio"):
                # Calculate unadjusted multiples for display
                adjusted_ebitda = (
                    result.multiples_valuation.ebitda_multiple
                    if hasattr(result.multiples_valuation, "ebitda_multiple")
                    else 0
                )
                adjusted_revenue = (
                    result.multiples_valuation.revenue_multiple
                    if hasattr(result.multiples_valuation, "revenue_multiple")
                    else 0
                )
                adjustment_factor = owner_conc["adjustment_factor"]

                unadjusted_ebitda = (
                    adjusted_ebitda / (1 + adjustment_factor)
                    if adjustment_factor != -1
                    else adjusted_ebitda
                )
                unadjusted_revenue = (
                    adjusted_revenue / (1 + adjustment_factor)
                    if adjustment_factor != -1
                    else adjusted_revenue
                )

                # Use the canonical helper so the threshold table can never drift
                # from the adjuster's tier table (the prior inline derivation here
                # mis-classified -0.30 / partnership -0.15 boundaries).
                from src.domain.owner_concentration_adjuster import OwnerConcentrationAdjuster

                risk_level = OwnerConcentrationAdjuster.risk_level_for_adjustment(adjustment_factor)

                owner_concentration_data = {
                    "ratio": owner_conc["ratio"],
                    "adjustment_factor": owner_conc["adjustment_factor"],
                    "number_of_owners": owner_conc["number_of_owners"],
                    "number_of_employees": owner_conc["number_of_employees"],
                    "risk_level": risk_level,
                    "unadjusted_ebitda_multiple": unadjusted_ebitda,
                    "unadjusted_revenue_multiple": unadjusted_revenue,
                    "adjusted_ebitda_multiple": adjusted_ebitda,
                    "adjusted_revenue_multiple": adjusted_revenue,
                    "calibration": owner_conc.get("calibration"),  # If available
                }

        # Add owner concentration to template data
        template_data["owner_concentration"] = owner_concentration_data

        # Step 4: Render HTML (SKIP PDF generation for instant preview)
        from src.services.infrastructure.template_service import get_template_service

        template_service = get_template_service()

        html_content = template_service.render_valuation_report(
            valuation_data=template_data, template_name="valuation_report.html"
        )

        # Step 5: Return HTML for instant preview
        return Response(
            content=html_content,
            media_type="text/html",
            headers={
                "Cache-Control": "no-cache",  # Fresh data every time
                "Content-Type": "text/html; charset=utf-8",
            },
        )

    except InvalidDiscountError as e:
        logger.error(f"HTML generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HTML report generation failed. Please try again or contact support.",
        )


@router.post(
    "/accountant-view",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Generate Accountant View PDF report",
    description="""
    Generate a professional Accountant View PDF report with:
    - Cover page
    - Table of contents
    - Executive summary
    - Company and market overview
    - Financial analysis (including EBITDA normalization)
    - Valuation methodologies (detailed breakdown)
    - Valuation conclusion
    - Appendices (including academic references)

    **Format**: Word-document-style, minimalistic design, professional appearance

    **Privacy Guarantee**: Private financial data never leaves the valuation engine.
    """,
    responses={
        200: {
            "description": "PDF report generated successfully",
            "content": {"application/pdf": {}},
        },
        400: {"model": ErrorResponse, "description": "Invalid request data"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def generate_accountant_view_pdf(request: ValuationRequest) -> Response:
    """
    Generate comprehensive Accountant View PDF report.

    This endpoint:
    1. Calculates complete valuation (same as /calculate)
    2. Transforms ValuationResponse to template-friendly format
    3. Renders professional Accountant View PDF report
    4. Returns downloadable PDF file
    """
    correlation_id = str(uuid.uuid4())
    try:
        logger.info(
            "🔍 [PDF-GEN] Accountant View PDF report request received",
            extra={
                "company": request.company_name,
                "industry": str(request.industry) if request.industry else None,
                "correlation_id": correlation_id,
            },
        )

        # Step 1: Calculate valuation using orchestrator (same as /calculate endpoint)
        logger.info(
            "🔍 [PDF-GEN] Step 1: Starting valuation calculation",
            extra={"correlation_id": correlation_id, "company": request.company_name},
        )
        orchestrator = get_valuation_orchestrator()
        valuation_response = await orchestrator.process_comprehensive_valuation(
            request, context={"correlation_id": correlation_id}
        )

        if not valuation_response:
            logger.error(
                "❌ [PDF-GEN] Step 1 failed: Valuation calculation returned None",
                extra={"correlation_id": correlation_id, "company": request.company_name},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Valuation calculation failed - no response received",
            )

        logger.info(
            "✅ [PDF-GEN] Step 1 completed: Valuation calculation successful",
            extra={
                "correlation_id": correlation_id,
                "company": request.company_name,
                "valuation_id": getattr(valuation_response, "valuation_id", None),
                "equity_value_mid": getattr(valuation_response, "equity_value_mid", None),
            },
        )

        # Step 2: Build accountant-view report context
        logger.info(
            "🔍 [PDF-GEN] Step 2: Building accountant-view report context",
            extra={"correlation_id": correlation_id, "company": request.company_name},
        )
        from src.services.infrastructure.main_report_data_aggregator import (
            get_main_report_aggregator,
        )
        from src.services.infrastructure.template_service import get_template_service

        locale = getattr(request, "locale", None) or "nl"
        aggregator = get_main_report_aggregator()
        context = aggregator.aggregate(valuation_response, request, locale=locale)
        template_service = get_template_service()

        logger.info(
            "🔍 [PDF-GEN] Step 3: Rendering accountant-view PDF bytes",
            extra={"correlation_id": correlation_id, "company": request.company_name},
        )
        try:
            pdf_start_time = time.time()
            pdf_bytes = await asyncio.to_thread(
                template_service.generate_accountant_view_pdf, context
            )
            pdf_generation_duration = time.time() - pdf_start_time
            pdf_size_bytes = len(pdf_bytes) if pdf_bytes else 0
            pdf_size_mb = pdf_size_bytes / (1024 * 1024)

            logger.info(
                "✅ [PDF-GEN] Step 3b completed: PDF generation successful",
                extra={
                    "correlation_id": correlation_id,
                    "company": request.company_name,
                    "pdf_size_bytes": pdf_size_bytes,
                    "pdf_size_mb": round(pdf_size_mb, 2),
                    "pdf_generation_time_seconds": round(pdf_generation_duration, 3),
                    "pdf_is_bytes": isinstance(pdf_bytes, bytes),
                    "performance_target_met": pdf_generation_duration < Decimal("3.0")
                    and pdf_size_mb < Decimal("5.0"),
                },
            )

            # Warn if performance targets not met
            if pdf_generation_duration >= 3.0:
                logger.warning(
                    f"⚠️ [PDF-GEN] PDF generation time ({pdf_generation_duration:.2f}s) exceeds target (<3s)",
                    extra={
                        "correlation_id": correlation_id,
                        "company": request.company_name,
                        "generation_time_seconds": round(pdf_generation_duration, 3),
                        "target_seconds": Decimal("3.0"),
                    },
                )
            if pdf_size_mb >= 5.0:
                logger.warning(
                    f"⚠️ [PDF-GEN] PDF file size ({pdf_size_mb:.2f}MB) exceeds target (<5MB)",
                    extra={
                        "correlation_id": correlation_id,
                        "company": request.company_name,
                        "pdf_size_mb": round(pdf_size_mb, 2),
                        "target_mb": Decimal("5.0"),
                    },
                )
        except APIError as pdf_error:
            logger.error(
                "❌ [PDF-GEN] Step 3b failed: PDF generation error",
                extra={
                    "correlation_id": correlation_id,
                    "company": request.company_name,
                    "error_type": type(pdf_error).__name__,
                    "error_message": str(pdf_error),
                    "error_args": pdf_error.args if hasattr(pdf_error, "args") else None,
                },
                exc_info=True,
            )
            raise

        # Step 4: Return PDF as downloadable file
        if not pdf_bytes or len(pdf_bytes) == 0:
            logger.error(
                "❌ [PDF-GEN] Step 4 failed: PDF bytes are empty",
                extra={"correlation_id": correlation_id, "company": request.company_name},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PDF generation failed - empty PDF bytes",
            )

        filename = f"valuation_report_accountant_{request.company_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"

        logger.info(
            "✅ [PDF-GEN] Step 4: Returning PDF response",
            extra={
                "correlation_id": correlation_id,
                "company": request.company_name,
                "filename": filename,
                "pdf_size_bytes": len(pdf_bytes),
            },
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/pdf",
            },
        )

    except HTTPException:
        raise
    except APIError as e:
        logger.error(
            f"❌ [PDF-GEN] Accountant View PDF generation failed: {e}",
            extra={
                "correlation_id": correlation_id,
                "company": request.company_name if request else None,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "error_args": e.args if hasattr(e, "args") else None,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Accountant view PDF generation failed. Please try again or contact support.",
        )
