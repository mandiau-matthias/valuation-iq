"""Per-year valuation timeline — the value-over-fiscal-years curve.

Values EACH fiscal year present in the request (historical actuals + the current
year + forecast/projection years) and returns one :class:`ValuationTimelinePoint`
per year. Together they form a real valuation curve for the company.

Design (locked product decisions):
  * CONSTANT CURRENT LENS — every year is valued on *today's* resolved benchmark
    multiples / calibration / macro (carried over from the main request). Only
    that year's financials vary. Each point is a "restated" value, not a true
    historical mark (we have no reliable historical-benchmark time series). The
    advisor's multiple / discount overrides ARE the lens, so they are kept; only
    per-year-unsafe inputs (user blend weights, startup override, year-keyed
    EBITDA weights, …) are neutralized so each year is a clean adaptive run.
  * FULL ADAPTIVE METHODOLOGY per year — each year reuses the entire engine via a
    recursive :func:`calculate_stateless_response` call, so methodology selection
    (DCF / multiples / asset) adapts to that year's data. NO lookahead: a year is
    valued using only the financial data strictly before it. Company-level
    classification policy is part of the constant current lens and is bound once
    from the complete filed dossier before recursive calculation.
  * The latest-actual-year point is taken directly from the just-computed headline
    so the curve's anchor reconciles to the headline exactly (and we save a call).

Best-effort: a single failing year is dropped (logged), never fatal — mirrors
``_build_safe_stateless_market_context``.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
import json
from typing import Optional

from src.api.schemas.stateless_api import CalculateRequest
from src.api.schemas.stateless_common import YearDataStateless
from src.api.schemas.stateless_response_schemas import ValuationTimelinePoint
from src.services.reports.stateless_dcf import stateless_dcf_forecast_years_for_timeline
from src.services.reports.stateless_evidence_dates import evidence_source_as_of
from src.services.reports.stateless_owner_salary import (
    public_owner_operated_classification,
)
from src.utils.adaptive_input_helpers import get_business_context

# Public company history and forward prognosis are separate graph products.
# Keep the current filing plus up to nine historical filed observations (the
# public request contract) without
# letting five newer forecast years evict the oldest filed evidence from the
# same transport array.
MAX_ACTUAL_TIMELINE_YEARS = 10
MAX_FORECAST_TIMELINE_YEARS = 5
MAX_TIMELINE_YEARS = MAX_ACTUAL_TIMELINE_YEARS + MAX_FORECAST_TIMELINE_YEARS

# Per-year-unsafe fields cleared on each sub-request. The lens (benchmark
# contract, calibration, macro, country, owner dependency, and the advisor's
# multiple / discount overrides) is deliberately carried over unchanged so the
# whole curve is valued on one constant current lens.
# Public Adaptive weights are also cleared here on purpose: every recursive
# checkpoint re-enters ``apply_public_adaptive_profile`` and then binds the
# verified capability set to that year's final readiness/evidence weights.
# This lets Adaptive weights change across actual years without letting an
# outer-year blend leak into or override the canonical per-year decision.
_PER_YEAR_NEUTRALIZED: dict[str, object] = {
    "include_valuation_timeline": False,  # recursion guard — sub-calls never recurse
    "user_weights": None,
    "user_weight_justification": None,
    "selected_method": None,
    "startup_inputs": None,
    "holdings_consolidation": None,
    "use_monte_carlo": False,
    # Each current-lens checkpoint must be struck on that target fiscal year's
    # own earnings, not a rolling blend that changes as more history accrues.
    "historical_ebitda_weighting_mode": "current_year",
    "historical_ebitda_weights": None,
}


def _per_year_neutralized_fields(request: CalculateRequest) -> dict[str, object]:
    """Resolve dossier-scoped timeline behavior without changing legacy defaults."""
    fields = dict(_PER_YEAR_NEUTRALIZED)
    context = get_business_context(request)
    if context.get("valuation_timeline_preserve_user_weights") is True:
        fields.pop("user_weights", None)
        fields.pop("user_weight_justification", None)
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    if (
        metadata.get("public_adaptive_profile_v2") is True
        or metadata.get("public_adaptive_profile_v1") is True
    ) and request.selected_method in {"upswitch_adaptive", "ebitda_multiple"}:
        # A machine-governed public request binds its selected method in the
        # producer envelope. Clearing it would make historical checkpoints use
        # a different method from the headline while retaining the outer
        # calibration. Preserve the attested selection so each recursive
        # subrun re-applies and re-verifies the same public profile contract.
        fields.pop("selected_method", None)
    return fields


_UNSCOPED_MEASUREMENT_DATE_FIELDS: dict[str, object] = {
    "tax_latencies": None,
    "balance_sheet_adjustments": None,
    "real_estate_treatment": "none",
    "real_estate_market_value": None,
    "real_estate_book_value": None,
    "estimated_market_rent": None,
}
_UNSCOPED_MEASUREMENT_DATE_QUALIFICATION = (
    "Unscoped measurement-date tax, balance-sheet and real-estate bridge inputs "
    "were excluded from this non-anchor current-lens restatement."
)


# Codes that mean "we decided not to publish this year", as opposed to "this
# year crashed". Both used to be swallowed by the same blanket handler and
# logged identically, which made a deliberate withholding indistinguishable
# from a defect — and invisible to anyone reading a short public curve.
_WITHHELD_BY_POLICY_CODES = frozenset(
    {
        "NEGATIVE_EBITDA_RECOVERY_EVIDENCE_REQUIRED",
        "NO_ELIGIBLE_VALUATION_METHOD",
        "REAL_ESTATE_YIELD_UNAVAILABLE",
    }
)


def _coerce_failure_detail(detail: object) -> Mapping[str, object] | None:
    """Return a detail mapping, parsing the JSON-string form FastAPI can carry."""
    if isinstance(detail, Mapping):
        return detail
    if isinstance(detail, str):
        text = detail.strip()
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
            except ValueError:
                return None
            if isinstance(parsed, Mapping):
                return parsed
    return None


def _safe_timeline_failure_diagnostics(error: Exception) -> dict[str, object]:
    """Return bounded, non-financial diagnostics for a skipped checkpoint."""
    detail = _coerce_failure_detail(getattr(error, "detail", None))
    if detail is None:
        return {"failure_type": type(error).__name__, "withheld_by_policy": False}
    code = detail.get("code") or detail.get("reason_code")
    failed_controls = detail.get("failed_controls")
    controls = (
        [str(value)[:80] for value in failed_controls[:12]]
        if isinstance(failed_controls, list)
        else []
    )
    normalized = str(code).strip().upper() if code is not None else ""
    return {
        "failure_type": type(error).__name__,
        "failure_code": str(code)[:120] if code is not None else None,
        "failed_controls": controls,
        "withheld_by_policy": normalized in _WITHHELD_BY_POLICY_CODES,
    }


def _has_unscoped_measurement_date_inputs(request: CalculateRequest) -> bool:
    return bool(
        request.tax_latencies
        or request.balance_sheet_adjustments
        or request.real_estate_treatment not in (None, "none")
        or request.real_estate_market_value is not None
        or request.real_estate_book_value is not None
        or request.estimated_market_rent is not None
    )


def _confidence_score_int(value: object) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _point_value_basis(
    requested_basis: str,
    enterprise_low: object | None,
    enterprise_mid: object | None,
    enterprise_high: object | None,
) -> str:
    """Declare EV only when this exact point carries a complete EV range."""
    if requested_basis == "enterprise_value" and all(
        value is not None for value in (enterprise_low, enterprise_mid, enterprise_high)
    ):
        return "enterprise_value"
    return "equity_value"


def _build_year_subrequest(
    request: CalculateRequest,
    target: YearDataStateless,
    prior_years: list[YearDataStateless],
) -> CalculateRequest:
    """A copy of the main request restated for ``target`` year.

    Uses ``model_copy(update=...)`` — Pydantic v2 does NOT re-run validators on a
    copy, which is REQUIRED: a forecast year sitting in ``current_year`` would
    otherwise be rejected by ``validate_current_year_not_in_future``.
    """
    metadata = dict(request.metadata or {})
    # The calculation layer may build a timeline internally to derive a forward
    # cone even when ``include_valuation_timeline`` is false. Mark recursive
    # checkpoints explicitly so that secondary fallback cannot recurse forever.
    metadata["valuation_timeline_subrequest"] = True
    metadata["valuation_timeline_parent_valuation_id"] = request.valuation_id
    metadata["valuation_timeline_target_fiscal_year"] = target.year
    # This commitment authenticates the exact outer HTTP wire. An in-process
    # per-year subrequest is derived after that boundary and must not claim it
    # was independently received and verified. The parent run still seals the
    # original commitment and the timeline projection in its own lineage.
    metadata.pop("titan_request_wire_commitment", None)
    if metadata.get("public_valuation_audit") is True:
        by_year = metadata.get("public_financial_inputs_by_year")
        raw_inputs = by_year.get(str(target.year)) if isinstance(by_year, Mapping) else None
        # A sub-year must never inherit the headline year's financial audit
        # inputs. Missing lineage deliberately yields no per-year public audit.
        metadata["public_financial_inputs"] = (
            [dict(row) for row in raw_inputs if isinstance(row, Mapping)]
            if isinstance(raw_inputs, list)
            else []
        )
        # Historical filed points are intentionally valued today. Their
        # freshness is proven by immutable deposit/parser lineage rather than
        # by pretending the fiscal year itself is recent. Forecast/current
        # points must keep the normal headline freshness policy.
        metadata["public_valuation_historical_point"] = (
            target.year < request.current_year.year and target.is_forecast is not True
        )
        if target.is_forecast is True:
            # A ValuationIQ-generated forward point is a modeled projection,
            # not a filed fiscal observation. It remains inside the signed
            # parent result/authority envelope, but must not impersonate a
            # source-bound public audit or count toward T2/T3 actual years.
            metadata["public_valuation_audit"] = False
            metadata["public_adaptive_modeled_forecast_point"] = True
    # Legacy unscoped Venus normalizations belong only to the original
    # headline/current year. Once a historical or forecast row becomes the
    # subrequest's `current_year`, carrying those rows would rewrite every graph
    # checkpoint. Explicitly year-scoped decisions remain eligible.
    target_normalizations = [
        adjustment for adjustment in request.normalizations if adjustment.fiscal_year == target.year
    ]
    subrequest_current = target
    subrequest_years = prior_years
    valuation_case = request.valuation_case
    if (
        request.dcf_input_mode == "fcff_only"
        and target.is_forecast is True
        and target.free_cash_flow is not None
    ):
        # A future DCF mark is valued at that future date from the remaining
        # explicit FCFF horizon—not from forecasts that are already in the
        # past relative to the mark. The final explicit year receives one
        # terminal-growth continuation row so its value does not silently fall
        # back to an earnings multiple.
        subrequest_current = target.model_copy(update={"is_forecast": False})
        actual_history = [row for row in prior_years if row.is_forecast is not True]
        remaining_fcff = [
            row
            for row in request.historical_years
            if row.is_forecast is True and row.year > target.year and row.free_cash_flow is not None
        ]
        if not remaining_fcff:
            terminal_growth = request.economic_context.terminal_growth_rate
            remaining_fcff = [
                YearDataStateless(
                    year=target.year + 1,
                    revenue=0,
                    ebitda=0,
                    free_cash_flow=(target.free_cash_flow * (Decimal("1") + terminal_growth)),
                    is_forecast=True,
                )
            ]
        subrequest_years = [*actual_history, *remaining_fcff]
        if valuation_case is not None and valuation_case.accounting_evidence_attachment == "priced":
            # A Titan signature covers the exact case, including attachment
            # status. Rebinding that signed reported-evidence package to an
            # advisor forecast would both invalidate the attestation and make
            # reported facts appear to authenticate forecast money. Until a
            # projection-specific signed evidence contract exists, omit this
            # best-effort forecast point instead of mutating the case.
            raise ValueError(
                "signed priced accounting evidence cannot be rebound to a forecast timeline point"
            )

    return request.model_copy(
        update={
            **_per_year_neutralized_fields(request),
            **_UNSCOPED_MEASUREMENT_DATE_FIELDS,
            "current_year": subrequest_current,
            "historical_years": subrequest_years,
            "normalizations": target_normalizations,
            "valuation_id": f"{request.valuation_id}_ty{target.year}",
            "metadata": metadata,
            "valuation_case": valuation_case,
        }
    )


def build_valuation_timeline(
    *,
    request: CalculateRequest,
    headline_equity_low: object,
    headline_equity_mid: object,
    headline_equity_high: object,
    headline_methodology_used: Optional[str],
    headline_confidence_level: Optional[str],
    headline_confidence_score: object,
    logger: object,
    headline_audit_snapshot: Optional[dict[str, object]] = None,
    headline_enterprise_value_low: object | None = None,
    headline_enterprise_value_mid: object | None = None,
    headline_enterprise_value_high: object | None = None,
) -> list[ValuationTimelinePoint]:
    """Build one valuation point per fiscal year. Best-effort; never raises."""
    # Lazy import: stateless_calculation imports THIS module, so importing it at
    # module load time would be a circular import.
    from src.services.reports.stateless_calculation import calculate_stateless_response

    current = request.current_year
    metadata = request.metadata if isinstance(request.metadata, Mapping) else {}
    public_v2 = metadata.get("public_adaptive_profile_v2") is True
    parent_owner_classification = (
        public_owner_operated_classification(request) if public_v2 else None
    )
    reconciled_modeled_dcf = bool(
        isinstance(headline_audit_snapshot, Mapping)
        and isinstance(headline_audit_snapshot.get("modeled_dcf"), Mapping)
    )

    # All input years, deduped by fiscal year. The current year wins ties.
    by_year: dict[int, YearDataStateless] = {}
    for year_data in request.historical_years:
        by_year[year_data.year] = year_data
    by_year[current.year] = current
    include_forecasts = (
        get_business_context(request).get("valuation_timeline_include_forecasts", True) is not False
    )
    if include_forecasts and (not public_v2 or reconciled_modeled_dcf):
        for forecast_year in stateless_dcf_forecast_years_for_timeline(request):
            if forecast_year.year == current.year:
                continue
            by_year[forecast_year.year] = forecast_year
    else:
        # Explicit forecast rows share ``historical_years`` with filed rows in
        # the transport contract. Merely skipping generated forecasts would
        # therefore still leak supplied 2026–2030 rows into an actual-only
        # private curve. Apply the dossier gate to both sources. Public
        # Adaptive also enters this branch when DCF was authorized but did not
        # contribute a reconciled method leg: authorization alone must never
        # manufacture a public forward cone.
        by_year = {year: row for year, row in by_year.items() if row.is_forecast is not True}

    all_years = sorted(by_year.keys())
    actual_years = [year for year in all_years if by_year[year].is_forecast is not True]
    forecast_years = [year for year in all_years if by_year[year].is_forecast is True]
    # The headline/current filing is authoritative and must survive even if a
    # malformed caller supplies more than the supported number of actual rows.
    actual_others = [year for year in actual_years if year != current.year]
    kept_actuals = actual_others[-(MAX_ACTUAL_TIMELINE_YEARS - 1) :]
    if current.year in actual_years:
        kept_actuals.append(current.year)
    # Forecasts are a forward outlook, so keep the nearest horizons first.
    target_years = sorted(
        {
            *kept_actuals,
            *forecast_years[:MAX_FORECAST_TIMELINE_YEARS],
        }
    )

    points: list[ValuationTimelinePoint] = []
    for year in target_years:
        if year == current.year:
            # Reconcile the anchor to the headline (and skip a redundant call).
            points.append(
                ValuationTimelinePoint(
                    fiscal_year=year,
                    equity_low=headline_equity_low,
                    equity_mid=headline_equity_mid,
                    equity_high=headline_equity_high,
                    enterprise_value_low=headline_enterprise_value_low,
                    enterprise_value_mid=headline_enterprise_value_mid,
                    enterprise_value_high=headline_enterprise_value_high,
                    value_basis=_point_value_basis(
                        request.headline_value_basis,
                        headline_enterprise_value_low,
                        headline_enterprise_value_mid,
                        headline_enterprise_value_high,
                    ),
                    currency=getattr(request, "currency", None),
                    methodology_used=headline_methodology_used,
                    confidence_level=headline_confidence_level,
                    confidence_score=_confidence_score_int(headline_confidence_score),
                    audit_snapshot=headline_audit_snapshot,
                    is_forecast=False,
                    source_as_of=evidence_source_as_of(request, year),
                )
            )
            continue

        target_row = by_year[year]
        # No lookahead: value this year using only data strictly before it.
        prior_years = [by_year[y] for y in all_years if y < year]
        try:
            calculation_kwargs = (
                {"parent_public_owner_operated_classification": (parent_owner_classification)}
                if parent_owner_classification is not None
                else {}
            )
            sub_response = calculate_stateless_response(
                _build_year_subrequest(request, target_row, prior_years),
                **calculation_kwargs,
            )
            points.append(
                ValuationTimelinePoint(
                    fiscal_year=year,
                    equity_low=sub_response.equity_value_low,
                    equity_mid=sub_response.equity_value_mid,
                    equity_high=sub_response.equity_value_high,
                    enterprise_value_low=getattr(sub_response, "enterprise_value_low", None),
                    enterprise_value_mid=getattr(sub_response, "enterprise_value_mid", None),
                    enterprise_value_high=getattr(sub_response, "enterprise_value_high", None),
                    value_basis=_point_value_basis(
                        request.headline_value_basis,
                        getattr(sub_response, "enterprise_value_low", None),
                        getattr(sub_response, "enterprise_value_mid", None),
                        getattr(sub_response, "enterprise_value_high", None),
                    ),
                    currency=getattr(request, "currency", None),
                    methodology_used=sub_response.methodology_used,
                    confidence_level=sub_response.confidence_level,
                    confidence_score=_confidence_score_int(sub_response.confidence_score),
                    audit_snapshot=getattr(sub_response, "public_valuation_audit", None),
                    is_forecast=bool(getattr(target_row, "is_forecast", False)),
                    source_as_of=evidence_source_as_of(request, year),
                    qualifications=(
                        [_UNSCOPED_MEASUREMENT_DATE_QUALIFICATION]
                        if _has_unscoped_measurement_date_inputs(request)
                        else []
                    ),
                )
            )
        except Exception as error:
            diagnostics = _safe_timeline_failure_diagnostics(error)
            # A year we declined to publish is a product decision with a reason
            # code; a year that crashed is a defect. Logging both as "calc
            # failed" hid the first behind the second.
            logger.warning(  # type: ignore[attr-defined]
                (
                    "valuation_timeline: year withheld by policy (omitted from curve)"
                    if diagnostics.get("withheld_by_policy")
                    else "valuation_timeline: per-year calc failed (skipping year)"
                ),
                extra={"fiscal_year": year, **diagnostics},
            )

    points.sort(key=lambda point: point.fiscal_year)
    return points
