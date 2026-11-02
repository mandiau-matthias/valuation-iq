"""Canonical stateless calculation transport for ValuationIQ.

This router is isolated from report/PDF and legacy API imports so the local
Public Adaptive migration profile can start only the numeric engine. The full
stateless router includes this exact router, preserving one request handler and
one calculation implementation across runtime profiles.
"""

from fastapi import APIRouter, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool

from src.api.routes.partial_assessment_router import calculate_partial, calculation_router
from src.api.schemas.stateless_api import CalculateRequest, CalculateResponse
from src.api.schemas.titan_request_wire_security import (
    TitanRequestWireCommitmentError,
    verify_titan_request_wire_commitment,
)
from src.services.reports.stateless_calculation import calculate_stateless_response

router = APIRouter()
router.include_router(calculation_router)


@router.post(
    "/calculate",
    response_model=CalculateResponse,
    summary="Calculate valuation (stateless)",
    description=(
        "Perform full valuation calculation. Titan sends all data, no DB access. "
        "`shares_for_sale` supports partial-stake valuations by scaling equity outputs."
    ),
)
async def calculate(
    request: CalculateRequest,
    raw_request: Request = None,
) -> CalculateResponse:
    """Calculate one valuation from Titan's complete, authenticated input."""
    verified_wire_commitment = None
    if raw_request is not None:
        try:
            verified_wire_commitment = verify_titan_request_wire_commitment(
                await raw_request.body()
            )
        except TitanRequestWireCommitmentError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "TITAN_REQUEST_WIRE_COMMITMENT_INVALID",
                    "message": str(exc),
                },
            ) from exc
    elif (
        request.metadata is not None
        and request.metadata.get("titan_request_wire_commitment") is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "TITAN_REQUEST_WIRE_COMMITMENT_UNVERIFIED",
                "message": "A Titan wire commitment requires the authenticated HTTP body.",
            },
        )
    # The canonical engine is synchronous and CPU-heavy. Running it on the event
    # loop prevents health/readiness traffic from being served during a batch and
    # can make a healthy multi-worker process look dead to its supervisor.
    return await run_in_threadpool(
        calculate_stateless_response,
        request,
        verified_titan_request_wire_commitment=verified_wire_commitment,
    )


__all__ = ["calculate", "calculate_partial", "router"]
