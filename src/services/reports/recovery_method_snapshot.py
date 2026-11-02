"""Render the selected recovery method from its saved resolution, without repricing."""

from src.api.schemas.negative_ebitda_recovery import NegativeEbitdaResolution
from src.api.schemas.stateless_response_schemas import MethodResult


def recovery_dcf_method_snapshot(resolution: NegativeEbitdaResolution) -> MethodResult:
    equity_known = resolution.headline_equity_value_mid is not None
    return MethodResult(
        label="Recovery DCF",
        method_key="dcf",
        engine_version="negative_ebitda_recovery.v1",
        available=True,
        confidence=resolution.confidence,
        value_basis="equity_value" if equity_known else "enterprise_value",
        value=(
            resolution.headline_equity_value_mid
            if equity_known
            else resolution.headline_enterprise_value_mid
        ),
        value_low=(
            resolution.headline_equity_value_low
            if equity_known
            else resolution.headline_enterprise_value_low
        ),
        value_high=(
            resolution.headline_equity_value_high
            if equity_known
            else resolution.headline_enterprise_value_high
        ),
        enterprise_value=resolution.headline_enterprise_value_mid,
        enterprise_value_low=resolution.headline_enterprise_value_low,
        enterprise_value_high=resolution.headline_enterprise_value_high,
        equity_value=resolution.headline_equity_value_mid,
        equity_value_low=resolution.headline_equity_value_low,
        equity_value_high=resolution.headline_equity_value_high,
        details={
            "range_provenance": "probability_weighted_recovery_scenarios",
            "resolution_snapshot_hash": resolution.resolution_snapshot_hash,
            "equity_bridge": resolution.model_dump(mode="json")["equity_bridge"],
            "source_verified": resolution.candidate_method_audit["dcf"]["source_verified"],
            "scenario_results": [
                row.model_dump(mode="json") for row in resolution.scenario_results
            ],
        },
    )
