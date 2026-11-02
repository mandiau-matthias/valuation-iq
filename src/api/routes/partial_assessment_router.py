"""Shared authenticated partial calculation and immutable report transport.

This router can be loaded independently of the complete earnings engine. The
full stateless and numeric profiles include these same handlers.
"""

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from src.api.schemas.partial_report import GeneratePartialReportRequest, PartialReportResponse
from src.api.schemas.partial_valuation import PartialValuationRequest, PartialValuationResponse
from src.middleware.auth import require_service_auth
from src.services.reports.partial_valuation import (
    PartialCalculationInputError,
    calculate_partial_valuation,
)

calculation_router = APIRouter(dependencies=[Depends(require_service_auth)])
report_router = APIRouter(dependencies=[Depends(require_service_auth)])


@calculation_router.post("/calculate-partial", response_model=PartialValuationResponse)
async def calculate_partial(request: PartialValuationRequest) -> PartialValuationResponse:
    """Price available evidence without inventing missing earnings or bridges."""
    try:
        return PartialValuationResponse.model_validate(
            await run_in_threadpool(calculate_partial_valuation, request)
        )
    except PartialCalculationInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@report_router.post("/generate-partial-report", response_model=PartialReportResponse)
async def partial_report(request: GeneratePartialReportRequest) -> PartialReportResponse:
    """Project the supplied immutable assessment without advisor acceptance."""
    from src.services.reports.partial_report import generate_partial_report

    return await generate_partial_report(request)
