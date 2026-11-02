"""Methodology selection policy for stateless valuation calculations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Mapping

from src.api.schemas.stateless_api import BusinessTypeCalibration, CalculateRequest, TriageFlag
from src.domain.asset_based_support import (
    has_sufficient_asset_inputs,
    is_ambiguous_head_office_activity,
    is_asset_heavy_holding_activity,
    is_holding_company_activity,
    is_net_asset_dominant,
)
from src.config.country_packs import (
    dcf_country_configuration_blocker,
    dcf_economic_snapshot_blocker,
)
from src.services.reports.public_adaptive_profile import public_modeled_dcf_is_authorized
from src.utils.decimal_helpers import safe_decimal_or_zero

ADAPTIVE_WEIGHT_POLICY_VERSION = "business_archetype_readiness_evidence.v1"
_LIMITED_HISTORY_DCF_READINESS = Decimal("3") / Decimal("7")
_WEIGHT_QUANTUM = Decimal("0.000001")
_MARKET_SELECTED_METHODS = {
    "ebitda_multiple",
    "omzet_multiple",
    "sde_multiple",
    "arr_multiple",
}


@dataclass(frozen=True)
class StatelessMethodologySelection:
    dcf_weight: Decimal
    multiples_weight: Decimal
    methodology_used: str
    methodology_selection_reason: str
    dcf_exclusion_reason: str | None
    triage_flags: list[TriageFlag]


def has_explicit_fcff_forecast(request: CalculateRequest) -> bool:
    """Return whether every FCFF-only forecast row has explicit FCFF."""
    if getattr(request, "dcf_input_mode", None) != "fcff_only":
        return False
    forecast_rows = [
        year for year in request.historical_years if bool(getattr(year, "is_forecast", False))
    ]
    return bool(forecast_rows) and all(
        getattr(year, "free_cash_flow", None) is not None for year in forecast_rows
    )


def _effective_selected_method(request: CalculateRequest) -> str | None:
    """User weights intentionally supersede a single selected headline."""
    if getattr(request, "user_weights", None):
        return None
    return getattr(request, "selected_method", None)


def _automatic_asset_routing_is_authorized(request: CalculateRequest) -> bool:
    """Keep strict method weights as the executable method boundary.

    A strict weight map is emitted by an upstream governed profile (including
    Public Adaptive).  Auto-routing to adjusted NAV when that map does not
    contain ``adjusted_nav`` would execute an unauthorised method and can also
    change an enterprise-value request into a net-asset valuation.  Interactive
    requests without strict weights retain the existing automatic asset route.
    """
    if getattr(request, "strict_user_weights", False) is not True:
        return True
    weights = getattr(request, "user_weights", None)
    if not isinstance(weights, Mapping):
        return False
    return safe_decimal_or_zero(weights.get("adjusted_nav")) > 0


def _base_selection(request: CalculateRequest) -> StatelessMethodologySelection:
    return StatelessMethodologySelection(
        dcf_weight=Decimal("0.5"),
        multiples_weight=Decimal("0.5"),
        methodology_used=request.methodology,
        methodology_selection_reason=(
            f"Using {request.methodology} based on data availability and business type preferences"
        ),
        dcf_exclusion_reason=None,
        triage_flags=[],
    )


def _with_added_flags(
    selection: StatelessMethodologySelection,
    *flags: TriageFlag,
) -> StatelessMethodologySelection:
    return replace(selection, triage_flags=[*selection.triage_flags, *flags])


def _renormalized_method_weights(
    *,
    dcf_weight: Decimal,
    multiples_weight: Decimal,
) -> tuple[Decimal, Decimal]:
    dcf = max(Decimal("0"), dcf_weight)
    multiples = max(Decimal("0"), multiples_weight)
    total = dcf + multiples
    if total <= 0:
        return Decimal("0"), Decimal("0")
    normalized_dcf = (dcf / total).quantize(_WEIGHT_QUANTUM)
    return normalized_dcf, Decimal("1") - normalized_dcf


def _apply_dcf_viability_rules(
    selection: StatelessMethodologySelection,
    *,
    request: CalculateRequest,
    ebitda: float,
    historical_year_count: int,
) -> StatelessMethodologySelection:
    if (
        request.methodology not in {"HYBRID", "DCF"}
        and _effective_selected_method(request) != "dcf"
    ):
        return selection

    country_blocker = dcf_country_configuration_blocker(
        request.country_code,
        request.business_context,
    )
    if country_blocker:
        return _with_added_flags(
            replace(
                selection,
                dcf_exclusion_reason=country_blocker,
                dcf_weight=Decimal("0"),
                multiples_weight=(Decimal("1") if request.include_multiples else Decimal("0")),
                methodology_used=("MULTIPLES" if request.include_multiples else "DCF"),
            ),
            TriageFlag(
                field=(
                    "business_context.irish_tax_regime"
                    if request.country_code == "IE"
                    else "business_context.dcf_tax_rate_pct"
                ),
                issue="country_pack_tax_regime_unresolved",
                severity="warning",
                value=None,
            ),
        )

    economic_blocker = (
        None
        if public_modeled_dcf_is_authorized(request)
        else dcf_economic_snapshot_blocker(
            request.country_code,
            request.economic_context,
        )
    )
    if economic_blocker:
        return _with_added_flags(
            replace(
                selection,
                dcf_exclusion_reason=economic_blocker.reason,
                dcf_weight=Decimal("0"),
                multiples_weight=(Decimal("1") if request.include_multiples else Decimal("0")),
                methodology_used=("MULTIPLES" if request.include_multiples else "DCF"),
            ),
            TriageFlag(
                field=economic_blocker.field,
                issue=economic_blocker.issue,
                severity="warning",
                value=economic_blocker.value,
            ),
        )

    if getattr(request, "dcf_input_mode", None) == "fcff_only":
        if has_explicit_fcff_forecast(request):
            return selection
        missing_years = [
            year.year
            for year in request.historical_years
            if bool(getattr(year, "is_forecast", False))
            and getattr(year, "free_cash_flow", None) is None
        ]
        return _with_added_flags(
            replace(
                selection,
                dcf_exclusion_reason=(
                    "FCFF-only DCF requires free_cash_flow on every forecast row"
                ),
                dcf_weight=Decimal("0"),
                multiples_weight=Decimal("1"),
                methodology_used="MULTIPLES",
            ),
            TriageFlag(
                field="historical_years.free_cash_flow",
                issue="missing_fcff_forecast",
                severity="warning",
                value={"missing_fiscal_years": missing_years},
            ),
        )

    if ebitda <= 0:
        return _with_added_flags(
            replace(
                selection,
                dcf_exclusion_reason="EBITDA is negative - DCF requires positive cash flows",
                dcf_weight=Decimal("0"),
                multiples_weight=Decimal("1"),
                methodology_used="MULTIPLES",
            ),
            TriageFlag(
                field="ebitda",
                issue="negative_ebitda",
                severity="warning",
                value=ebitda,
            ),
        )

    if historical_year_count < 2:
        dcf_weight, multiples_weight = _renormalized_method_weights(
            dcf_weight=selection.dcf_weight * _LIMITED_HISTORY_DCF_READINESS,
            multiples_weight=selection.multiples_weight,
        )
        return _with_added_flags(
            replace(
                selection,
                # Limited history reduces readiness/evidence weight; it does
                # not make an otherwise successful FCFF calculation invalid.
                dcf_exclusion_reason=None,
                dcf_weight=dcf_weight,
                multiples_weight=multiples_weight,
                methodology_selection_reason=(
                    "Hybrid weighting reduced the DCF leg for limited historical "
                    "evidence; DCF remains eligible and the valuation range widens."
                ),
            ),
            TriageFlag(
                field="historical_years",
                issue="insufficient_history",
                severity="info",
                value=historical_year_count,
                benchmark=3,
            ),
        )

    return selection


def _asset_route_subject(activity_code: str, industry: str | None) -> str:
    if is_holding_company_activity(activity_code):
        return f"holding-company activity {activity_code}"
    if activity_code:
        return f"real-estate asset-holding activity {activity_code}"
    return f"asset-holding entity (industry: {industry})"


def _apply_asset_routing_rules(
    selection: StatelessMethodologySelection,
    *,
    request: CalculateRequest,
    revenue: float,
    balance_sheet: Mapping[str, object],
    activity_code: str,
) -> StatelessMethodologySelection:
    if is_asset_heavy_holding_activity(activity_code, industry=request.industry):
        reason_subject = _asset_route_subject(activity_code, request.industry)
        return replace(
            selection,
            dcf_weight=Decimal("0"),
            multiples_weight=Decimal("0"),
            methodology_used="ASSET_BASED",
            methodology_selection_reason=(
                f"Using Asset-Based methodology because {reason_subject} "
                "is primarily valued on underlying assets and liabilities."
            ),
            dcf_exclusion_reason="Asset-holding route selected for balance-sheet-led valuation.",
        )

    is_head_office_asset_route = is_ambiguous_head_office_activity(
        activity_code, industry=request.industry
    ) and (
        is_net_asset_dominant(balance_sheet, safe_decimal_or_zero(request.current_year.ebitda))
        or (revenue <= 0 and has_sufficient_asset_inputs(balance_sheet))
    )
    if not is_head_office_asset_route:
        return selection

    head_office_subject = activity_code or f"industry tag '{request.industry}'"
    return replace(
        selection,
        dcf_weight=Decimal("0"),
        multiples_weight=Decimal("0"),
        methodology_used="ASSET_BASED",
        methodology_selection_reason=(
            "Using Asset-Based methodology because head-office / holding activity "
            f"{head_office_subject} has net assets that dwarf its earnings stream — value is "
            "stored in the balance sheet, not a thin management-fee P&L."
        ),
        dcf_exclusion_reason="Net-asset-dominant holding: balance-sheet-led valuation.",
    )


def _apply_explicit_methodology_weights(
    selection: StatelessMethodologySelection,
    request: CalculateRequest,
) -> StatelessMethodologySelection:
    if request.methodology == "MULTIPLES":
        return replace(selection, dcf_weight=Decimal("0"), multiples_weight=Decimal("1"))

    if request.methodology == "DCF" and selection.dcf_exclusion_reason is None:
        return replace(selection, dcf_weight=Decimal("1"), multiples_weight=Decimal("0"))

    if str(request.methodology).upper() == "ASSET_BASED":
        return replace(
            selection,
            dcf_weight=Decimal("0"),
            multiples_weight=Decimal("0"),
            methodology_used="ASSET_BASED",
            methodology_selection_reason="Using explicit Asset-Based methodology request.",
        )

    return selection


def _apply_selected_method_preference(
    selection: StatelessMethodologySelection,
    request: CalculateRequest,
) -> StatelessMethodologySelection:
    selected = _effective_selected_method(request)
    if selected is None or selected == "upswitch_adaptive":
        return selection

    if selected == "dcf":
        if not request.include_dcf or selection.dcf_exclusion_reason is not None:
            return selection
        return replace(
            selection,
            dcf_weight=Decimal("1"),
            multiples_weight=Decimal("0"),
            methodology_used="DCF",
            methodology_selection_reason=(
                "Selected eligible DCF method is authoritative for the headline."
            ),
        )

    if selected in _MARKET_SELECTED_METHODS:
        if not request.include_multiples:
            return selection
        return replace(
            selection,
            dcf_weight=Decimal("0"),
            multiples_weight=Decimal("1"),
            methodology_used="MULTIPLES",
            methodology_selection_reason=(
                f"Selected eligible {selected} method is authoritative for the headline."
            ),
        )

    if selected == "adjusted_nav":
        return replace(
            selection,
            dcf_weight=Decimal("0"),
            multiples_weight=Decimal("0"),
            methodology_used="ASSET_BASED",
            methodology_selection_reason=(
                "Selected adjusted NAV method is authoritative for the headline."
            ),
            dcf_exclusion_reason="Selected adjusted NAV is a balance-sheet methodology.",
        )

    if selected == "real_estate_yield":
        return replace(
            selection,
            dcf_weight=Decimal("0"),
            multiples_weight=Decimal("0"),
            methodology_used="REAL_ESTATE_YIELD",
            methodology_selection_reason=(
                "Selected governed property income-capitalisation method is authoritative."
            ),
            dcf_exclusion_reason=(
                "Property NOI and a metric-matched cap-rate distribution are the selected basis."
            ),
        )

    # Fiscal, liquidation and startup methods are calculated by OmniCalc after
    # the support headline exists. Keep the viable support route alive until
    # their MethodResult can be eligibility-checked and promoted.
    return replace(
        selection,
        methodology_selection_reason=(
            f"Selected {selected} will become the headline if its required evidence is eligible."
        ),
    )


def _apply_method_inclusion_controls(
    selection: StatelessMethodologySelection,
    request: CalculateRequest,
) -> StatelessMethodologySelection:
    """Make Venus/Titan include flags authoritative eligibility controls."""
    if selection.methodology_used == "ASSET_BASED":
        return selection
    if not request.include_dcf:
        return _with_added_flags(
            replace(
                selection,
                dcf_weight=Decimal("0"),
                multiples_weight=Decimal("1"),
                methodology_used="MULTIPLES",
                dcf_exclusion_reason="DCF disabled by request include_dcf=false.",
                methodology_selection_reason=(
                    "DCF was explicitly excluded; the eligible market method carries 100%."
                ),
            ),
            TriageFlag(
                field="include_dcf",
                issue="dcf_excluded_by_request",
                severity="info",
                value=False,
            ),
        )
    if not request.include_multiples:
        if selection.dcf_exclusion_reason is not None or selection.dcf_weight <= 0:
            return _with_added_flags(
                replace(
                    selection,
                    dcf_weight=Decimal("0"),
                    multiples_weight=Decimal("0"),
                    methodology_used="NO_ELIGIBLE_METHOD",
                    methodology_selection_reason=(
                        "Market methods were explicitly excluded and DCF is not eligible."
                    ),
                ),
                TriageFlag(
                    field="include_multiples",
                    issue="no_eligible_method_after_request_exclusions",
                    severity="error",
                    value=False,
                ),
            )
        return _with_added_flags(
            replace(
                selection,
                dcf_weight=Decimal("1"),
                multiples_weight=Decimal("0"),
                methodology_used="DCF",
                methodology_selection_reason=(
                    "Market methods were explicitly excluded; eligible DCF carries 100%."
                ),
            ),
            TriageFlag(
                field="include_multiples",
                issue="multiples_excluded_by_request",
                severity="info",
                value=False,
            ),
        )
    return selection


def _apply_calibration_preferences(
    selection: StatelessMethodologySelection,
    calibration: BusinessTypeCalibration,
) -> StatelessMethodologySelection:
    if calibration.dcf_preference is None or calibration.multiples_preference is None:
        return selection
    dcf_weight, multiples_weight = _renormalized_method_weights(
        dcf_weight=calibration.dcf_preference,
        multiples_weight=calibration.multiples_preference,
    )
    if dcf_weight == 0 and multiples_weight == 0:
        return selection
    return replace(
        selection,
        dcf_weight=dcf_weight,
        multiples_weight=multiples_weight,
    )


def _apply_evidence_quality_weighting(
    selection: StatelessMethodologySelection,
    calibration: BusinessTypeCalibration,
) -> StatelessMethodologySelection:
    """Multiply archetype weights by observable method-evidence quality."""
    quality = calibration.calibration_quality_score
    if quality is None or selection.dcf_weight <= 0 or selection.multiples_weight <= 0:
        return selection
    dcf_weight, multiples_weight = _renormalized_method_weights(
        dcf_weight=selection.dcf_weight,
        multiples_weight=selection.multiples_weight * quality,
    )
    return replace(
        selection,
        dcf_weight=dcf_weight,
        multiples_weight=multiples_weight,
        methodology_selection_reason=(
            f"{selection.methodology_selection_reason}; adaptive weights resolved under "
            f"{ADAPTIVE_WEIGHT_POLICY_VERSION} using benchmark evidence quality {quality}."
        ),
    )


def _with_weight_provenance(
    selection: StatelessMethodologySelection,
    calibration: BusinessTypeCalibration,
) -> StatelessMethodologySelection:
    return _with_added_flags(
        selection,
        TriageFlag(
            field="methodology_weights",
            issue="adaptive_method_weights_resolved",
            severity="info",
            value={
                "policy_version": ADAPTIVE_WEIGHT_POLICY_VERSION,
                "business_archetype": calibration.business_type_id,
                "dcf_weight": str(selection.dcf_weight),
                "multiples_weight": str(selection.multiples_weight),
                "dcf_readiness": ("excluded" if selection.dcf_weight == 0 else "eligible"),
                "benchmark_evidence_quality": (
                    str(calibration.calibration_quality_score)
                    if calibration.calibration_quality_score is not None
                    else "not_supplied"
                ),
                "dcf_exclusion_reason": selection.dcf_exclusion_reason,
            },
        ),
    )


def _apply_margin_benchmark_triage(
    selection: StatelessMethodologySelection,
    *,
    calibration: BusinessTypeCalibration,
    ebitda_margin: float,
) -> StatelessMethodologySelection:
    if not calibration.typical_ebitda_margin:
        return selection

    typical_margin = float(calibration.typical_ebitda_margin)
    if typical_margin <= 0:
        return selection

    deviation = abs(ebitda_margin - typical_margin) / typical_margin
    if deviation <= 0.5:
        return selection

    return _with_added_flags(
        selection,
        TriageFlag(
            field="ebitda_margin",
            issue="deviation_from_sector_benchmark",
            severity="warning",
            value=round(ebitda_margin * 100, 1),
            benchmark=round(typical_margin * 100, 1),
            deviation_percent=Decimal(str(round(deviation * 100, 1))),
        ),
    )


def select_stateless_methodology(
    *,
    request: CalculateRequest,
    calibration: BusinessTypeCalibration,
    ebitda: float,
    revenue: float,
    ebitda_margin: float,
    historical_year_count: int,
    balance_sheet: Mapping[str, object],
    activity_code: str,
) -> StatelessMethodologySelection:
    """Select DCF, multiples, hybrid, or asset-based route and emit triage flags."""
    selection = _apply_calibration_preferences(_base_selection(request), calibration)
    selection = _apply_dcf_viability_rules(
        selection,
        request=request,
        ebitda=ebitda,
        historical_year_count=historical_year_count,
    )
    before_asset_routing = selection
    selected = _effective_selected_method(request)
    if (selected is None or selected == "upswitch_adaptive") and (
        _automatic_asset_routing_is_authorized(request)
    ):
        selection = _apply_asset_routing_rules(
            selection,
            request=request,
            revenue=revenue,
            balance_sheet=balance_sheet,
            activity_code=activity_code,
        )
    if selection is before_asset_routing:
        selection = _apply_evidence_quality_weighting(selection, calibration)
        selection = _apply_explicit_methodology_weights(selection, request)
        selection = _apply_method_inclusion_controls(selection, request)
        selection = _apply_selected_method_preference(selection, request)
    selection = _apply_margin_benchmark_triage(
        selection,
        calibration=calibration,
        ebitda_margin=ebitda_margin,
    )
    return _with_weight_provenance(selection, calibration)
