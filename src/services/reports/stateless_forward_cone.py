"""Forward cone for explicit or ValuationIQ-modeled FY+1..FY+5 points."""

from __future__ import annotations

from decimal import Decimal

from src.api.schemas.stateless_api import CalculateRequest
from src.api.schemas.stateless_response_schemas import (
    ForwardConeAssumptionEvidence,
    ForwardConeMethodContribution,
    ForwardScenarioPath,
    ForwardValueCone,
    ForwardValueConePoint,
    ValuationTimelinePoint,
)
from src.services.reports.public_adaptive_profile import (
    PUBLIC_MODELED_DCF_POLICY_VERSION,
    public_modeled_dcf_is_authorized,
)


def build_explicit_forecast_forward_cone(
    *,
    request: CalculateRequest,
    timeline: list[ValuationTimelinePoint] | None,
) -> ForwardValueCone | None:
    """Project explicit or ValuationIQ-modeled forecast valuations."""
    if not timeline:
        return None
    modeled_public = public_modeled_dcf_is_authorized(request)
    modeled_public_policy_version = (
        _modeled_public_dcf_policy_version(request) if modeled_public else None
    )
    explicit_years = {
        row.year
        for row in request.historical_years
        if row.is_forecast and row.year > request.current_year.year
    }
    forecast_points = [
        point
        for point in timeline
        if point.is_forecast
        and (modeled_public or point.fiscal_year in explicit_years)
    ][:5]
    if not forecast_points:
        return None

    response_points = [
        _forward_point(
            request=request,
            point=point,
            modeled_public=modeled_public,
            modeled_public_policy_version=modeled_public_policy_version,
        )
        for point in forecast_points
    ]
    confidence = _path_confidence(response_points)
    return ForwardValueCone(
        points=response_points,
        scenario_paths={
            "base": ForwardScenarioPath(
                key="base",
                label=(
                    "ValuationIQ modeled Adaptive base case"
                    if modeled_public
                    else "Explicit forecast base case"
                ),
                action_status="base",
                points=response_points,
                confidence=confidence,
                gate_status=(
                    "emitted"
                    if all(point.gate_status == "emitted" for point in response_points)
                    else "degraded"
                ),
                provenance=[
                    (
                        "valuation_iq_modeled_public_dcf_defaults"
                        if modeled_public
                        else "advisor_entered_or_integration_observed_forecast_rows"
                    ),
                    "valuation_iq_current_market_lens_recalculation",
                ],
                warnings=[],
                audit_events=["No action heuristic changed the canonical forecast path."],
            )
        },
    )


def _modeled_public_dcf_policy_version(request: CalculateRequest) -> str:
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    profile = metadata.get("public_adaptive_resolution")
    resolution = profile.get("modeled_dcf_resolution") if isinstance(profile, dict) else None
    policy_version = resolution.get("policy_version") if isinstance(resolution, dict) else None
    return (
        policy_version
        if isinstance(policy_version, str) and policy_version.strip()
        else PUBLIC_MODELED_DCF_POLICY_VERSION
    )


def _forward_point(
    *,
    request: CalculateRequest,
    point: ValuationTimelinePoint,
    modeled_public: bool = False,
    modeled_public_policy_version: str | None = None,
) -> ForwardValueConePoint:
    method_key = _method_key(point.methodology_used)
    confidence = _confidence(point.confidence_level)
    assumptions = [
        ForwardConeAssumptionEvidence(
            field_key=(
                f"modeled_forecast_financials.{point.fiscal_year}"
                if modeled_public
                else f"forecast_financials.{point.fiscal_year}"
            ),
            source_kind="sector_default" if modeled_public else "advisor_entered",
            use_kind="forward_driver_input",
            confidence=confidence,
            source=(
                modeled_public_policy_version or PUBLIC_MODELED_DCF_POLICY_VERSION
                if modeled_public
                else f"historical_years[{point.fiscal_year}].is_forecast"
            ),
            responsible_surface=("valuation_iq" if modeled_public else "titan_valuation_case"),
            transformation=(
                "valuation_iq_modeled_driver_projection_and_full_adaptive_recalculation"
                if modeled_public
                else "full_valuation_recalculation_on_current_market_lens"
            ),
            fallback=False,
            warnings=[],
        ),
        ForwardConeAssumptionEvidence(
            field_key="current_market_lens",
            source_kind="integration_observed",
            use_kind="current_report_input",
            confidence=confidence,
            source="valuation_run.benchmark_snapshot",
            responsible_surface="valuation_iq",
            transformation="forecast_year_revalued_with_current_benchmark_contract",
            fallback=False,
            warnings=[],
        ),
    ]
    degraded = request.currency is None or point.confidence_level is None
    warnings = []
    if request.currency is None:
        warnings.append("currency_unresolved")
    if point.confidence_level is None:
        warnings.append("forecast_evidence_confidence_unresolved")
    return ForwardValueConePoint(
        fiscal_year=point.fiscal_year,
        horizon_years=point.fiscal_year - request.current_year.year,
        equity_low=point.equity_low,
        equity_mid=point.equity_mid,
        equity_high=point.equity_high,
        valuation_date_convention="fiscal_year_end_current_market_lens_restatement",
        method_mix=[
            ForwardConeMethodContribution(
                method_key=method_key,
                weight=Decimal("1"),
                equity_low=point.equity_low,
                equity_mid=point.equity_mid,
                equity_high=point.equity_high,
                uncertainty_family="forecast_and_market_lens",
                correlation_bucket="canonical_valuation_run",
                assumptions=assumptions,
                warnings=warnings,
            )
        ],
        uncertainty_provenance=(
            [
                "valuation_range_from_full_forecast_year_recalculation",
                "evidence_confidence_is_separate_from_range_width",
            ]
            + (["modeled_forward_assumptions_not_actuals"] if modeled_public else [])
        ),
        assumptions=assumptions,
        gate_status="degraded" if degraded else "emitted",
        excluded_methods=[],
        audit_events=[
            (
                "ValuationIQ-modeled forecast point valued independently; it is not a filed actual and cannot raise maturity."
                if modeled_public
                else "Explicit forecast row valued independently; no historical averaging leaked into the point."
            )
        ],
        confidence_level=point.confidence_level,
        warnings=warnings,
    )


def _method_key(methodology: str | None) -> str:
    normalized = str(methodology or "adaptive").strip().lower()
    return {
        "hybrid": "upswitch_adaptive",
        "weighted_synthesis": "upswitch_adaptive",
        "multiples": "ebitda_multiple",
        "dcf": "dcf",
        "asset_based": "adjusted_nav",
        "holding_sotp": "holding_sotp",
    }.get(normalized, normalized or "upswitch_adaptive")


def _confidence(value: str | None) -> str:
    normalized = str(value or "low").strip().lower()
    return normalized if normalized in {"low", "medium", "high"} else "low"


def _path_confidence(points: list[ForwardValueConePoint]) -> str:
    levels = {_confidence(point.confidence_level) for point in points}
    if "low" in levels:
        return "low"
    if "medium" in levels:
        return "medium"
    return "high"
