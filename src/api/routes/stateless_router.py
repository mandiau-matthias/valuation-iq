"""
Stateless API Router - Brain & Muscle Architecture

THE MUSCLE: ValuationIQ as a stateless calculation engine.

This router provides stateless endpoints where Titan (The Brain) sends
ALL required data in each request. No database access, no session state,
no AI/LLM calls - just pure calculation.

ENDPOINTS:
- POST /api/v2/stateless/calculate - Full valuation calculation
- POST /api/v2/stateless/validate - Triage/validation check
- POST /api/v2/stateless/generate-report - PDF/HTML report generation

ARCHITECTURE:
- Every request is self-contained
- All data comes from Titan (the orchestrator)
- Enables testing without database setup
- Horizontal scaling with stateless workers

Author: Upswitch CTO Team
Date: January 2026
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.api.routes.partial_assessment_router import partial_report as partial_report
from src.api.routes.partial_assessment_router import report_router
from src.api.routes.stateless_calculation_router import router as calculation_router
from src.api.schemas.sealed_report_schemas import ReportRenderSnapshotV1, ReportRenderSnapshotV2
from src.api.schemas.stateless_api import (
    GenerateReportRequest,
    GenerateReportResponse,
    ValidateRequest,
    ValidateResponse,
)
from src.api.schemas.valuation_assessment import (
    AssessmentReportResponse,
    GenerateAssessmentReportRequest,
)
from src.api.schemas.valuation_contracts import ValuationInputCatalog
from src.middleware.auth import require_service_auth
from src.services.reports.assessment_report import generate_assessment_report
from src.services.reports.sealed_report_rendering import (
    SealedReportRenderError,
    render_sealed_report,
)
from src.services.reports.stateless_input_catalog import build_valuation_input_catalog
from src.services.reports.stateless_report_generation import generate_stateless_report_response
from src.services.reports.stateless_validation import validate_stateless_request
from src.utils.logging import get_logger

logger = get_logger(__name__)


router = APIRouter(
    prefix="/api/v2/stateless",
    tags=["stateless", "brain-muscle"],
    dependencies=[Depends(require_service_auth)],
)

# The full API and the local migration profile share this exact handler. The
# profile omits only unrelated report/PDF and legacy route registration.
router.include_router(calculation_router)
router.include_router(report_router)


@router.get(
    "/input-catalog",
    response_model=ValuationInputCatalog,
    summary="Get the versioned valuation input catalog",
)
async def input_catalog() -> ValuationInputCatalog:
    """Return every executable request field with evidence and value semantics."""
    return build_valuation_input_catalog()


# =============================================================================
# VALIDATE ENDPOINT
# =============================================================================


@router.post(
    "/validate",
    response_model=ValidateResponse,
    summary="Validate data (dry run)",
    description="Check data completeness and quality before calculation.",
)
async def validate(request: ValidateRequest) -> ValidateResponse:
    """
    Validate financial data and return warnings/suggestions.

    BRAIN & MUSCLE ARCHITECTURE:
    - Titan sends data before full calculation
    - ValuationIQ validates without database access
    - Returns warnings and suggestions for Titan to handle

    Enables "dry run" checks before final calculation.
    """
    logger.info(
        "Stateless validate request received",
        extra={
            "industry": request.industry,
            "has_calibration": request.business_type_calibration is not None,
        },
    )

    return validate_stateless_request(request)


# =============================================================================
# GENERATE-REPORT ENDPOINT
# =============================================================================


@router.post(
    "/generate-report",
    response_model=GenerateReportResponse,
    summary="Generate valuation report",
    description="Generate HTML and PDF report from valuation result.",
)
async def generate_report(request: GenerateReportRequest) -> GenerateReportResponse:
    """
    Generate valuation report from calculation result.

    BRAIN & MUSCLE ARCHITECTURE:
    - Titan sends complete valuation result
    - ValuationIQ generates HTML and PDF
    - Returns report content for Titan to store

    PDF generation uses WeasyPrint (if available).
    """
    return await generate_stateless_report_response(request)


@router.post(
    "/render-sealed-pdf",
    response_class=Response,
    summary="Render a sealed publishable valuation memorandum",
    description=(
        "Fail-closed binary PDF/A-2b rendering from one immutable "
        "ReportRenderSnapshotV1 or V2. No HTML, base64 or fallback artifact is returned."
    ),
)
async def render_sealed_pdf(
    snapshot: ReportRenderSnapshotV1 | ReportRenderSnapshotV2,
) -> Response:
    try:
        pdf_bytes, receipt, receipt_header = await render_sealed_report(snapshot)
    except SealedReportRenderError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": exc.code,
                "message": str(exc),
                "diagnostics": exc.diagnostics,
            },
        ) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "X-Content-Type-Options": "nosniff",
            "X-PDF-SHA256": receipt.pdf_sha256,
            "X-Render-Snapshot-SHA256": receipt.render_snapshot_hash,
            "X-Report-Render-Receipt": receipt_header,
        },
    )


@router.post(
    "/generate-assessment-report",
    response_model=AssessmentReportResponse,
    summary="Render an immutable nonnumeric financial assessment",
)
async def generate_assessment_report_endpoint(
    request: GenerateAssessmentReportRequest,
) -> AssessmentReportResponse:
    # The enclosing router requires service authentication. Dossier authorization
    # and current-revision admission remain Titan responsibilities.
    from starlette.concurrency import run_in_threadpool

    result: AssessmentReportResponse = await run_in_threadpool(generate_assessment_report, request)
    return result
