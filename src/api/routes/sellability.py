"""Sellability €-impact HTTP route (BET-204 / A2 chunk 4).

Thin FastAPI wrapper around the pure-functional `compute_sellability_eur_impact`
in `src/services/sellability/eur_impact.py`. Brain (Titan) calls this
endpoint after computing the Sellability score and resolving the Upswitch Index
multiple — the math itself stays stateless and lives in the muscle layer.

Auth: bearer JWT, validated by Titan's PythonEngineService when calling.
The shared JWT secret + path-level auth happens at app middleware level
(see `src/api/main.py`). This route adds no per-request auth.

Request shape: see `SellabilityEurImpactRequest`. The factor list is
expected to be the exact 6-factor breakdown produced by Titan's
`computeSellabilityScore()` — drift between the two ends is caught by
the Titan-side integration test that round-trips the JSON shape.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.services.sellability import (
    SellabilityFactorInput,
    compute_sellability_eur_impact,
)

router = APIRouter()


# ---------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------


class SellabilityFactorPayload(BaseModel):
    """One factor row from Titan's score breakdown."""

    key: str
    value: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    contribution: float
    data_available: bool


class SellabilityEurImpactRequest(BaseModel):
    """Locked contract with Titan. Adding fields is OK; renaming requires
    a coordinated change on both ends."""

    factors: list[SellabilityFactorPayload]
    delphi_multiple: Optional[float] = Field(default=None, gt=0)
    current_ebitda: Optional[float] = Field(default=None)
    country_basis: Optional[Literal["native", "aggregate_clone", "aggregate"]] = None
    has_owner_profile_data: bool = False
    has_recent_financials: bool = False


class SellabilityLiftPayload(BaseModel):
    factor: str
    action: str
    eur_impact: Optional[int]
    confidence: Literal["high", "med", "low"]
    uplift_pct: float


class SellabilityEurImpactResponse(BaseModel):
    top_three_lifts: list[SellabilityLiftPayload]
    tertiary_lifts: list[SellabilityLiftPayload]
    cold_cell: bool
    current_ev: Optional[float]


class SellabilityImpactScenariosV2Request(SellabilityEurImpactRequest):
    """Evidence-addressable inputs; copy and publication stay with Titan."""

    input_references: list[str] = Field(min_length=1, max_length=50)
    calibration_source_references: list[str] = Field(
        default_factory=lambda: ["src/services/sellability/eur_impact.py"],
        min_length=1,
        max_length=20,
    )


class ModeledMoneyBandV2(BaseModel):
    low: int
    high: int
    currency: Literal["EUR"] = "EUR"


class SellabilityImpactScenarioV2(BaseModel):
    factor: str
    confidence: Literal["high", "med", "low"]
    uplift_pct: float
    modeled_band: Optional[ModeledMoneyBandV2]


class SellabilityImpactScenariosV2Response(BaseModel):
    calculation_id: str
    methodology_version: Literal["sellability_impact_scenarios_v2"]
    calibration_source_references: list[str]
    input_references: list[str]
    scenarios: list[SellabilityImpactScenarioV2]
    cold_cell: bool
    current_ev: Optional[float]


# ---------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------


@router.post(
    "/sellability/eur-impact",
    response_model=SellabilityEurImpactResponse,
    summary="Compute Sellability €-impact lifts (BET-204)",
    description=(
        "Pure-functional wrapper. No I/O. Caller (Titan) is responsible for "
        "resolving the Upswitch Index multiple and the entity context. Returns the "
        "spec §7.1 / §7.2 split: top-3 hero lifts + tertiary panel."
    ),
)
def post_sellability_eur_impact(
    request: SellabilityEurImpactRequest,
) -> SellabilityEurImpactResponse:
    factor_inputs = [
        SellabilityFactorInput(
            key=f.key,
            value=f.value,
            weight=f.weight,
            contribution=f.contribution,
            data_available=f.data_available,
        )
        for f in request.factors
    ]

    result = compute_sellability_eur_impact(
        factors=factor_inputs,
        delphi_multiple=request.delphi_multiple,
        current_ebitda=request.current_ebitda,
        country_basis=request.country_basis,
        has_owner_profile_data=request.has_owner_profile_data,
        has_recent_financials=request.has_recent_financials,
    )

    return SellabilityEurImpactResponse(
        top_three_lifts=[
            SellabilityLiftPayload(
                factor=l.factor,
                action=l.action,
                eur_impact=l.eur_impact,
                confidence=l.confidence,
                uplift_pct=l.uplift_pct,
            )
            for l in result.top_three_lifts
        ],
        tertiary_lifts=[
            SellabilityLiftPayload(
                factor=l.factor,
                action=l.action,
                eur_impact=l.eur_impact,
                confidence=l.confidence,
                uplift_pct=l.uplift_pct,
            )
            for l in result.tertiary_lifts
        ],
        cold_cell=result.cold_cell,
        current_ev=result.current_ev,
    )


@router.post(
    "/sellability/impact-scenarios/v2",
    response_model=SellabilityImpactScenariosV2Response,
    summary="Compute versioned Sellability impact scenarios without recommendation copy",
)
def post_sellability_impact_scenarios_v2(
    request: SellabilityImpactScenariosV2Request,
) -> SellabilityImpactScenariosV2Response:
    factor_inputs = [
        SellabilityFactorInput(
            key=f.key,
            value=f.value,
            weight=f.weight,
            contribution=f.contribution,
            data_available=f.data_available,
        )
        for f in request.factors
    ]
    result = compute_sellability_eur_impact(
        factors=factor_inputs,
        delphi_multiple=request.delphi_multiple,
        current_ebitda=request.current_ebitda,
        country_basis=request.country_basis,
        has_owner_profile_data=request.has_owner_profile_data,
        has_recent_financials=request.has_recent_financials,
    )
    fingerprint_payload = {
        "methodology": "sellability_impact_scenarios_v2",
        "factors": [factor.model_dump(mode="json") for factor in request.factors],
        "delphi_multiple": request.delphi_multiple,
        "current_ebitda": request.current_ebitda,
        "country_basis": request.country_basis,
        "input_references": sorted(set(request.input_references)),
        "calibration_source_references": sorted(set(request.calibration_source_references)),
    }
    calculation_id = (
        "si2_"
        + hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:24]
    )
    lifts = [*result.top_three_lifts, *result.tertiary_lifts]
    return SellabilityImpactScenariosV2Response(
        calculation_id=calculation_id,
        methodology_version="sellability_impact_scenarios_v2",
        calibration_source_references=list(dict.fromkeys(request.calibration_source_references)),
        input_references=list(dict.fromkeys(request.input_references)),
        scenarios=[
            SellabilityImpactScenarioV2(
                factor=lift.factor,
                confidence=lift.confidence,
                uplift_pct=lift.uplift_pct,
                modeled_band=_modeled_band(lift.eur_impact, lift.confidence),
            )
            for lift in lifts
        ],
        cold_cell=result.cold_cell,
        current_ev=result.current_ev,
    )


def _modeled_band(
    amount: Optional[int], confidence: Literal["high", "med", "low"]
) -> Optional[ModeledMoneyBandV2]:
    if amount is None:
        return None
    spread = {"high": 0.15, "med": 0.25, "low": 0.35}[confidence]
    return ModeledMoneyBandV2(
        low=max(0, round(amount * (1 - spread))),
        high=max(0, round(amount * (1 + spread))),
    )
