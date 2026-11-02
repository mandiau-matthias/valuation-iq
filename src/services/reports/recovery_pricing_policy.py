"""Automatic recovery scenarios remain indicative unless sources are verified."""

from pydantic import ValidationError

from src.api.schemas.stateless_api import CalculateRequest
from src.api.schemas.valuation_contracts import ValuationCase


def recovery_pricing_allowed(request: CalculateRequest, *, source_verified: bool) -> bool:
    if source_verified:
        return True
    if request.recovery_inputs is None:
        return False
    case = request.valuation_case
    if case is None or case.schema_version != "valuation_case.v2" or case.case_attestation is None:
        return False
    # Supplied verification cannot be downgraded to bypass a schedule mismatch.
    if case is not None and case.forecast_evidence is not None:
        return False
    if case is not None and case.case_attestation is not None:
        try:
            ValuationCase.model_validate(case.model_dump(mode="json"))
        except (ValidationError, ValueError):
            return False
    return True
