"""Stateless acquisition economics; requires signed service authentication at the router."""

from fastapi import APIRouter, Depends
from src.services.acquisition.scenarios import AcquisitionScenarioInput, calculate
from src.middleware.auth import require_service_auth

router = APIRouter(dependencies=[Depends(require_service_auth)])


@router.post("/acquisition/scenarios")
def acquisition_scenarios(request: AcquisitionScenarioInput) -> dict:
    return calculate(request)
