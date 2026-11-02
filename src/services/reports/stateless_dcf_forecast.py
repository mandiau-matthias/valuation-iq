"""Forecast adaptation and historical diagnostics; pricing requires forecast evidence."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional
from src.api.schemas.stateless_api import CalculateRequest, YearDataStateless
from src.domain.asset_based_support import normalize_business_model
from src.services.reports.stateless_calculation_helpers import is_usable_actual_year
from src.services.reports.stateless_earnings_basis import with_normalized_actual_earnings
from src.services.reports.public_adaptive_profile import public_modeled_dcf_is_authorized
from src.utils.adaptive_input_helpers import get_business_context, get_business_context_percent, get_dcf_da_pct_override, get_percent_override
from src.utils.dcf_forecast_nwc import repair_legacy_full_revenue_nwc_change
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class _StatelessForecastOverrides:
    revenue_growth: Decimal | None
    revenue_growth_schedule: tuple[Decimal, ...]
    ebitda_margin: Decimal | None
    d_and_a_ratio: Decimal | None
    capex_ratio: Decimal | None
    nwc_ratio: Decimal | None

    @property
    def has_any(self) -> bool:
        return any(
            value is not None
            for value in (
                self.revenue_growth,
                *self.revenue_growth_schedule,
                self.ebitda_margin,
                self.d_and_a_ratio,
                self.capex_ratio,
                self.nwc_ratio,
            )
        )

@dataclass(frozen=True)
class _StatelessForecastAssumptions:
    growth_rate: Decimal
    growth_schedule: tuple[Decimal, ...]
    target_margin: Decimal | None
    target_d_and_a_ratio: Decimal | None
    target_capex_ratio: Decimal | None
    target_nwc_ratio: Decimal | None

def _economic_snapshot_commits_risk_free_rate(economic_context: dict[str, object]) -> bool:
    """Whether the typed context carries a complete canonical snapshot claim.

    Hash verification and jurisdiction binding happen again in the market
    adapter.  This narrow check only decides whether the stateless shim should
    forward the committed rate as its explicit bond-yield input.
    """

    return bool(
        economic_context.get("schema_version") == "economic_snapshot.v1"
        and economic_context.get("snapshot_id")
        and economic_context.get("snapshot_hash")
        and economic_context.get("snapshot_issuer")
        and economic_context.get("risk_free_rate_observed_at")
        and economic_context.get("equity_risk_premium_observed_at")
        and economic_context.get("growth_rates_observed_at")
        and economic_context.get("source_references")
    )

def _extract_stateless_has_audit(request: CalculateRequest) -> Optional[bool]:
    for attr in ("has_audit", "audited_financials", "is_audited"):
        value = getattr(request, attr, None)
        if isinstance(value, bool):
            return value
    business_context = get_business_context(request)
    for key in ("has_audit", "audited_financials", "is_audited"):
        value = business_context.get(key)
        if isinstance(value, bool):
            return value
    return None

def _split_stateless_forecast_years(
    request: CalculateRequest,
) -> tuple[list[YearDataStateless], list[YearDataStateless]]:
    historical_years: list[YearDataStateless] = []
    forecast_years: list[YearDataStateless] = []

    for year_data in request.historical_years:
        if getattr(year_data, "is_forecast", False):
            forecast_years.append(year_data)
        elif is_usable_actual_year(year_data):
            historical_years.append(year_data)

    historical_years.sort(key=lambda year: year.year)
    forecast_years.sort(key=lambda year: year.year)
    dropped_count = len(request.historical_years) - len(historical_years) - len(forecast_years)
    if dropped_count > 0:
        logger.info(
            "Dropped unusable stateless DCF historical rows",
            extra={
                "valuation_id": request.valuation_id,
                "company_name": request.company_name,
                "dropped_count": dropped_count,
                "remaining_count": len(historical_years),
            },
        )
    return historical_years, forecast_years

def _stateless_forecast_overrides(request: CalculateRequest) -> _StatelessForecastOverrides:
    context = get_business_context(request)
    raw_schedule = context.get("dcf_revenue_growth_schedule_pct")
    growth_schedule: list[Decimal] = []
    if isinstance(raw_schedule, (list, tuple)):
        for raw_index, _raw_value in enumerate(raw_schedule):
            value = get_business_context_percent(
                {"value": _raw_value},
                "value",
            )
            if value is None or value <= Decimal("-1") or value > Decimal("1"):
                raise ValueError(
                    "dcf_revenue_growth_schedule_pct contains an invalid percentage "
                    f"at index {raw_index}"
                )
            growth_schedule.append(value)
    return _StatelessForecastOverrides(
        revenue_growth=get_percent_override(request, "dcf_revenue_growth_pct"),
        revenue_growth_schedule=tuple(growth_schedule),
        ebitda_margin=get_percent_override(request, "dcf_ebitda_margin_pct"),
        d_and_a_ratio=get_dcf_da_pct_override(request),
        capex_ratio=get_percent_override(request, "dcf_capex_pct"),
        nwc_ratio=get_percent_override(request, "dcf_nwc_pct"),
    )

def _ratio_to_revenue(value: object, revenue: Decimal) -> Decimal | None:
    if value is None or revenue <= 0:
        return None
    return to_decimal(value) / revenue

def _current_capex_ratio(base_year: YearDataStateless, revenue: Decimal) -> Decimal | None:
    capex_ratio = _ratio_to_revenue(getattr(base_year, "capex", None), revenue)
    if capex_ratio is not None:
        return capex_ratio
    return _ratio_to_revenue(getattr(base_year, "depreciation", None), revenue)

def _stateless_forecast_assumptions(
    *,
    overrides: _StatelessForecastOverrides,
    base_year: YearDataStateless,
    revenue: Decimal,
    base_ebitda: Decimal,
) -> _StatelessForecastAssumptions:
    current_margin = (base_ebitda / revenue) if revenue > 0 else Decimal("0")
    return _StatelessForecastAssumptions(
        growth_rate=overrides.revenue_growth or Decimal("0"),
        growth_schedule=overrides.revenue_growth_schedule,
        target_margin=(
            overrides.ebitda_margin if overrides.ebitda_margin is not None else current_margin
        ),
        target_d_and_a_ratio=overrides.d_and_a_ratio,
        target_capex_ratio=(
            overrides.capex_ratio
            if overrides.capex_ratio is not None
            else _current_capex_ratio(base_year, revenue)
        ),
        target_nwc_ratio=(
            overrides.nwc_ratio
            if overrides.nwc_ratio is not None
            else _ratio_to_revenue(getattr(base_year, "nwc_change", None), revenue)
        ),
    )

def _project_stateless_forecast_year(
    *,
    base_year: YearDataStateless,
    offset: int,
    projected_revenue: Decimal,
    previous_revenue: Decimal,
    previous_ebitda: Decimal,
    assumptions: _StatelessForecastAssumptions,
) -> YearDataStateless:
    projected_ebitda = (
        projected_revenue * assumptions.target_margin
        if assumptions.target_margin is not None
        else previous_ebitda
    )
    projected_d_and_a = (
        projected_revenue * assumptions.target_d_and_a_ratio
        if assumptions.target_d_and_a_ratio is not None
        else None
    )
    projected_capex = (
        projected_revenue * assumptions.target_capex_ratio
        if assumptions.target_capex_ratio is not None
        else None
    )
    projected_nwc_change = (
        (projected_revenue - previous_revenue) * assumptions.target_nwc_ratio
        if assumptions.target_nwc_ratio is not None
        else None
    )
    return YearDataStateless(
        year=base_year.year + offset,
        revenue=projected_revenue,
        ebitda=projected_ebitda,
        ebit=(projected_ebitda - projected_d_and_a if projected_d_and_a is not None else None),
        depreciation=projected_d_and_a,
        capex=projected_capex,
        nwc_change=projected_nwc_change,
        is_forecast=True,
    )

def _generate_stateless_dcf_forecast_years(
    request: CalculateRequest,
    *,
    base_year: YearDataStateless,
    projection_years: int,
) -> list[YearDataStateless]:
    overrides = _stateless_forecast_overrides(request)
    if not overrides.has_any:
        return []

    revenue = to_decimal(base_year.revenue or 0)
    base_ebitda = to_decimal(base_year.ebitda or 0)
    assumptions = _stateless_forecast_assumptions(
        overrides=overrides,
        base_year=base_year,
        revenue=revenue,
        base_ebitda=base_ebitda,
    )

    forecasts: list[YearDataStateless] = []
    projected_revenue = revenue
    projected_ebitda = base_ebitda
    previous_revenue = revenue

    for offset in range(1, projection_years + 1):
        growth_rate = (
            assumptions.growth_schedule[offset - 1]
            if offset <= len(assumptions.growth_schedule)
            else assumptions.growth_rate
        )
        projected_revenue = projected_revenue * (Decimal("1") + growth_rate)
        forecast_year = _project_stateless_forecast_year(
            base_year=base_year,
            offset=offset,
            projected_revenue=projected_revenue,
            previous_revenue=previous_revenue,
            previous_ebitda=projected_ebitda,
            assumptions=assumptions,
        )
        forecasts.append(forecast_year)
        projected_ebitda = to_decimal(forecast_year.ebitda or 0)
        previous_revenue = projected_revenue

    return forecasts

def _repair_stateless_legacy_forecast_nwc_changes(
    request: CalculateRequest,
    *,
    base_year: YearDataStateless,
    forecast_years: list[YearDataStateless],
) -> list[YearDataStateless]:
    """Repair explicit forecast rows that persisted the old full-revenue ΔNWC formula."""
    nwc_ratio = get_percent_override(request, "dcf_nwc_pct")
    if nwc_ratio is None:
        return forecast_years

    previous_revenue = to_decimal(base_year.revenue or 0)
    repaired_count = 0
    repaired_years: list[YearDataStateless] = []
    for forecast_year in sorted(forecast_years, key=lambda y: y.year):
        revenue = to_decimal(forecast_year.revenue or 0)
        repaired_nwc_change = repair_legacy_full_revenue_nwc_change(
            supplied_nwc_change=forecast_year.nwc_change,
            revenue=revenue,
            previous_revenue=previous_revenue,
            nwc_ratio=nwc_ratio,
        )
        if repaired_nwc_change is not None:
            forecast_year.nwc_change = repaired_nwc_change
            repaired_count += 1
        repaired_years.append(forecast_year)
        if revenue > 0:
            previous_revenue = revenue

    if repaired_count:
        logger.info(
            "Repaired legacy stateless DCF forecast ΔNWC rows from full-revenue percent "
            "to growth-based NWC ratio",
            extra={
                "valuation_id": getattr(request, "valuation_id", None),
                "company": getattr(request, "company_name", None),
                "rows": repaired_count,
            },
        )
    return repaired_years

def stateless_dcf_forecast_years_for_timeline(
    request: CalculateRequest,
) -> list[YearDataStateless]:
    """Return the forecast rows the DCF engine can value as timeline points.

    Explicit request forecasts are already folded into ``request.historical_years``
    by Titan. When they are absent, the stateless DCF adapter may synthesize
    forecast rows from DCF percentage overrides; expose that same forecast grid to
    the timeline builder so DCF prognosis years can be rendered as graph
    projections without inventing rows from raw FCFF-only engine output.
    """
    _historical_years, forecast_years = _split_stateless_forecast_years(request)
    if forecast_years:
        return _repair_stateless_legacy_forecast_nwc_changes(
            request,
            base_year=request.current_year,
            forecast_years=forecast_years,
        )
    return _generate_stateless_dcf_forecast_years(
        request,
        base_year=request.current_year,
        projection_years=request.projection_years,
    )

def _coalesce_stateless_sme_calibration(
    request: CalculateRequest,
) -> Optional[dict[str, object]]:
    raw = getattr(request, "sme_calibration", None)
    if isinstance(raw, dict) and raw:
        return dict(raw)
    return None

def _build_stateless_dcf_request(request: CalculateRequest) -> SimpleNamespace:
    request = with_normalized_actual_earnings(request)
    economic_context = (
        request.economic_context.model_dump()
        if hasattr(request.economic_context, "model_dump")
        else dict(request.economic_context)
    )
    has_audit = _extract_stateless_has_audit(request)
    business_context = get_business_context(request)
    historical_years, forecast_years = _split_stateless_forecast_years(request)
    if getattr(request, "dcf_input_mode", None) == "fcff_only":
        missing_years = [row.year for row in forecast_years if row.free_cash_flow is None]
        if not forecast_years or missing_years:
            raise ValueError(
                "FCFF-only DCF requires explicit free_cash_flow on every "
                f"forecast row; missing years: {missing_years}"
            )
    if forecast_years:
        forecast_years = _repair_stateless_legacy_forecast_nwc_changes(
            request,
            base_year=request.current_year,
            forecast_years=forecast_years,
        )
    if not forecast_years:
        forecast_years = _generate_stateless_dcf_forecast_years(
            request,
            base_year=request.current_year,
            projection_years=request.projection_years,
        )
    equity_risk_premium = (
        economic_context.get("equity_risk_premium")
        if economic_context.get("equity_risk_premium") is not None
        else (
            economic_context.get("market_risk_premium")
            if economic_context.get("market_risk_premium") is not None
            else economic_context.get("erp")
        )
    )
    modeled_public_dcf_authorized = public_modeled_dcf_is_authorized(request)

    return SimpleNamespace(
        company_name=request.company_name,
        country_code=request.country_code,
        registration_number=getattr(request, "registration_number", None),
        kbo_number=getattr(request, "kbo_number", None),
        kvk_number=getattr(request, "kvk_number", None),
        vat_number=getattr(request, "vat_number", None),
        legal_form=getattr(request, "legal_form", None),
        postal_code=getattr(request, "postal_code", None),
        city=getattr(request, "city", None),
        industry=request.industry,
        business_model=normalize_business_model(request.business_model),
        founding_year=request.founding_year,
        business_type_id=getattr(request.business_type_calibration, "business_type_id", None),
        sme_calibration=_coalesce_stateless_sme_calibration(request),
        current_year_data=request.current_year,
        historical_years_data=historical_years,
        forecast_years_data=forecast_years,
        dcf_input_mode=getattr(request, "dcf_input_mode", None),
        number_of_employees=request.number_of_employees,
        recurring_revenue_percentage=request.recurring_revenue_percentage,
        rev_recurring_pct=getattr(request, "rev_recurring_pct", None),
        rev_recurring_amount=getattr(request, "rev_recurring_amount", None),
        rev_top_client_concentration_pct=getattr(request, "rev_top_client_concentration_pct", None),
        rev_top_client_amount=getattr(request, "rev_top_client_amount", None),
        rev_contract_backlog=getattr(request, "rev_contract_backlog", None),
        government_bond_yield=(
            economic_context.get("risk_free_rate")
            if bool(economic_context.get("risk_free_rate_is_override"))
            or _economic_snapshot_commits_risk_free_rate(economic_context)
            or modeled_public_dcf_authorized
            else None
        ),
        long_term_gdp_growth=(
            economic_context.get("gdp_growth_rate")
            if economic_context.get("gdp_growth_rate") is not None
            else economic_context.get("terminal_growth_rate")
        ),
        equity_risk_premium=equity_risk_premium,
        economic_context=economic_context,
        # This is derived inside ValuationIQ after the signed Public Adaptive
        # resolution verifies.  It is deliberately not part of the public API
        # schema, so callers cannot spoof ValuationIQ-owned market provenance.
        public_modeled_dcf_authorized=modeled_public_dcf_authorized,
        # The market-context adapter needs the governed mode to distinguish an
        # all-in observed WACC (whose CAPM components are intentionally null)
        # from a component-built discount rate.  The public CalculateRequest
        # has already verified this contract against signed valuation_case.v2.
        wacc_evidence_contract=getattr(request, "wacc_evidence_contract", None),
        business_context=business_context,
        has_audit=has_audit,
        audited_financials=has_audit,
        is_audited=has_audit,
        owner_dependency=request.owner_dependency,
    )
