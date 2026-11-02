"""Canonical negative-EBITDA recovery policy and calculation boundary."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping, Protocol

import rfc8785

from src.api.schemas.negative_ebitda_recovery import (
    NegativeEbitdaResolution,
    OperatingTrajectory,
    PublicNegativeEbitdaRecoveryProjection,
    RecoveryInputs,
    RecoveryScenario,
    RecoveryScenarioResult,
)
from src.api.schemas.stateless_api import CalculateRequest
from src.api.schemas.stateless_response_schemas import (
    CalculateResponse,
    MethodResult,
    TriageFlag,
    ValuationTimelinePoint,
)
from src.domain.revenue_growth import revenue_growth as calculate_revenue_growth
from src.services.reports.public_valuation_audit import build_public_valuation_audit
from src.utils.decimal_helpers import safe_decimal_or_zero, safe_float
from src.utils.logging import get_logger

AUDIT_TRAIL_VERSION = "negative_ebitda_resolution.v1"
MODEL_VERSION = "negative_ebitda_recovery.v1"

logger = get_logger(__name__)


class _InputContext(Protocol):
    request: CalculateRequest
    triage_flags: list[TriageFlag]
    normalized_business_model: str
    calibration: object
    benchmark_contract: Mapping[str, object] | None
    revenue: float
    ebitda: float
    revenue_growth: Decimal
    balance_sheet: dict[str, object]
    ownership_multiplier: Decimal
    primary_business_type_id: str
    earnings_basis: dict[str, object]
    trial_balance_anomalies: dict[str, object] | None
    holdings_consolidation: dict[str, object] | None


@dataclass(frozen=True)
class RecoveryOutcome:
    resolution: NegativeEbitdaResolution
    valuation_results: dict[str, MethodResult]
    equity_low: Decimal | None
    equity_mid: Decimal | None
    equity_high: Decimal | None
    enterprise_low: Decimal | None
    enterprise_mid: Decimal | None
    enterprise_high: Decimal | None


def _env_enabled(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _recovery_producer_default_enabled() -> bool:
    """Keep local/test flows smooth while deployed producers roll out fail-closed."""

    environment = os.getenv("ENVIRONMENT", "").strip().lower()
    if environment in {"production", "staging"}:
        return False
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME"):
        return False
    return True


def recovery_feature_enabled() -> bool:
    return _env_enabled(
        "NEGATIVE_EBITDA_RECOVERY_VALUATION_ENABLED",
        _recovery_producer_default_enabled(),
    )


def public_recovery_benchmark_enabled() -> bool:
    # Filed turnover/ARR benchmarks and governed NAV floors can safely publish
    # a bounded public curve. Public DCF remains prohibited regardless of this
    # flag because filed accounts do not contain a verified recovery schedule.
    return _env_enabled(
        "PUBLIC_RECOVERY_BENCHMARK_ENABLED",
        _recovery_producer_default_enabled(),
    )


def _ebitda_band(value: Decimal) -> str:
    """Return a coarse, non-identifying analytics band."""
    magnitude = abs(value)
    if magnitude < Decimal("100000"):
        return "negative_under_100k"
    if magnitude < Decimal("500000"):
        return "negative_100k_to_500k"
    if magnitude < Decimal("2000000"):
        return "negative_500k_to_2m"
    return "negative_over_2m"


def _canonical_hash(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")

    def json_wire(item: object) -> object:
        if isinstance(item, Decimal):
            return format(item, "f")
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, Mapping):
            return {str(key): json_wire(nested) for key, nested in item.items()}
        if isinstance(item, (list, tuple)):
            return [json_wire(nested) for nested in item]
        return item

    return hashlib.sha256(rfc8785.dumps(json_wire(value))).hexdigest()


def reported_ebitda(request: CalculateRequest) -> Decimal:
    current = request.current_year
    return current.reported_ebitda if current.reported_ebitda is not None else current.ebitda


def normalized_positive(
    request: CalculateRequest,
    earnings_basis: Mapping[str, object] | None = None,
) -> bool:
    """Return whether signed canonical normalization crossed zero.

    Top-level normalization rows and ``current_year.normalized_ebitda`` are
    caller-controlled compatibility transports. They never determine routing.
    ``earnings_basis`` is produced from Titan's signed valuation-case decisions
    by ``resolve_stateless_earnings_basis``.
    """

    if not isinstance(earnings_basis, Mapping):
        return False
    current_reported = safe_decimal_or_zero(earnings_basis.get("current_reported_ebitda"))
    current_normalized = safe_decimal_or_zero(earnings_basis.get("current_normalized_ebitda"))
    return bool(reported_ebitda(request) < 0 and current_reported < 0 and current_normalized > 0)


def requires_private_recovery_path(
    request: CalculateRequest,
    earnings_basis: Mapping[str, object] | None = None,
) -> bool:
    metadata = request.metadata if isinstance(request.metadata, Mapping) else {}
    return bool(
        recovery_feature_enabled()
        and metadata.get("public_adaptive_profile_v2") is not True
        and metadata.get("public_adaptive_profile_v1") is not True
        and reported_ebitda(request) < 0
        and not normalized_positive(request, earnings_basis)
    )


def requires_public_recovery_path(
    request: CalculateRequest,
    earnings_basis: Mapping[str, object] | None = None,
) -> bool:
    metadata = request.metadata if isinstance(request.metadata, Mapping) else {}
    return bool(
        (
            metadata.get("public_adaptive_profile_v2") is True
            or metadata.get("public_adaptive_profile_v1") is True
        )
        and reported_ebitda(request) < 0
        and not normalized_positive(request, earnings_basis)
    )


def _ratio(value: Decimal | None, revenue: Decimal) -> Decimal | None:
    if value is None:
        return None
    if abs(value) <= Decimal("1"):
        return value
    if revenue <= 0:
        return None
    return value / revenue


def _cash_flow(row: object) -> Decimal | None:
    for name in ("free_cash_flow", "operating_cash_flow"):
        value = getattr(row, name, None)
        if value is not None:
            return Decimal(str(value))
    return None


def _working_capital(row: object) -> Decimal | None:
    receivables = getattr(row, "accounts_receivable", None)
    payables = getattr(row, "accounts_payable", None)
    inventory = getattr(row, "inventory", None)
    if any(value is not None for value in (receivables, payables, inventory)):
        return (
            safe_decimal_or_zero(receivables)
            + safe_decimal_or_zero(inventory)
            - safe_decimal_or_zero(payables)
        )
    current_assets = getattr(row, "current_assets", None)
    current_liabilities = getattr(row, "current_liabilities", None)
    if current_assets is not None and current_liabilities is not None:
        return Decimal(str(current_assets)) - Decimal(str(current_liabilities))
    return None


def _canonical_trajectory_ebitda(
    earnings_basis: Mapping[str, object] | None,
    year: int,
) -> Decimal | None:
    if not isinstance(earnings_basis, Mapping):
        return None
    rows = earnings_basis.get("rows")
    if not isinstance(rows, list):
        return None
    for raw in rows:
        if not isinstance(raw, Mapping) or raw.get("year") != year:
            continue
        value = raw.get("normalized_ebitda")
        if value is not None:
            return safe_decimal_or_zero(value)
    return None


def _trajectory_ebitda(
    request: CalculateRequest,
    row: object,
    earnings_basis: Mapping[str, object] | None = None,
) -> Decimal:
    canonical = _canonical_trajectory_ebitda(
        earnings_basis,
        int(getattr(row, "year")),
    )
    if canonical is not None:
        return canonical
    reported = getattr(row, "reported_ebitda", None)
    if reported is not None:
        return Decimal(str(reported))
    return Decimal(str(getattr(row, "ebitda")))


def build_operating_trajectory(
    request: CalculateRequest,
    earnings_basis: Mapping[str, object] | None = None,
) -> OperatingTrajectory:
    rows_by_year = {
        row.year: row for row in request.historical_years if row.is_forecast is not True
    }
    rows_by_year[request.current_year.year] = request.current_year
    rows = [rows_by_year[year] for year in sorted(rows_by_year)]
    warnings: list[str] = []
    conflicts: list[str] = []
    periods = len(rows)

    if periods < 2:
        return OperatingTrajectory(
            direction="unknown",
            ebitda_direction="unknown",
            confidence="low",
            comparable_periods=periods,
            warnings=["insufficient_history_for_direction"],
        )

    previous, latest = rows[-2], rows[-1]
    previous_duration = (
        (previous.period_end - previous.period_start).days + 1
        if previous.period_start is not None and previous.period_end is not None
        else None
    )
    latest_duration = (
        (latest.period_end - latest.period_start).days + 1
        if latest.period_start is not None and latest.period_end is not None
        else None
    )
    period_duration_changed = bool(
        previous_duration
        and latest_duration
        and abs(latest_duration - previous_duration) > max(7, previous_duration * 0.05)
    )
    if period_duration_changed:
        conflicts.append("accounting_period_duration_changed")
        warnings.append("periods_must_be_annualized_before_trajectory_comparison")
    elif previous_duration is None or latest_duration is None:
        warnings.append("period_duration_evidence_incomplete")

    previous_source_currency = str(previous.source_currency or "").strip().upper()
    latest_source_currency = str(latest.source_currency or "").strip().upper()
    previous_currency_basis = str(previous.currency_basis or "").strip().lower()
    latest_currency_basis = str(latest.currency_basis or "").strip().lower()
    currency_lineage_changed = bool(
        previous_source_currency
        and latest_source_currency
        and previous_source_currency != latest_source_currency
    ) or bool(
        previous_currency_basis
        and latest_currency_basis
        and previous_currency_basis != latest_currency_basis
    )
    if currency_lineage_changed:
        conflicts.append("currency_lineage_changed")
        warnings.append("currency_conversion_lineage_requires_reconciliation")
    elif not (
        previous_source_currency
        and latest_source_currency
        and previous_currency_basis
        and latest_currency_basis
    ):
        warnings.append("currency_lineage_incomplete")
    previous_basis = str(getattr(previous, "ebitda_basis", "") or "").strip().lower()
    latest_basis = str(getattr(latest, "ebitda_basis", "") or "").strip().lower()
    accounting_basis_changed = bool(
        previous_basis and latest_basis and previous_basis != latest_basis
    )
    if accounting_basis_changed:
        conflicts.append("accounting_ebitda_basis_changed")
        warnings.append("accounting_reclassification_requires_review")

    previous_revenue_source = str(getattr(previous, "revenue_source", "") or "").strip().lower()
    latest_revenue_source = str(getattr(latest, "revenue_source", "") or "").strip().lower()
    revenue_semantics_changed = bool(
        previous_revenue_source
        and latest_revenue_source
        and previous_revenue_source != latest_revenue_source
    )
    if revenue_semantics_changed:
        conflicts.append("revenue_semantics_changed")
        warnings.append("accounting_periods_not_fully_comparable")
    previous_revenue = Decimal(str(previous.revenue))
    latest_revenue = Decimal(str(latest.revenue))
    growth_evidence = calculate_revenue_growth(latest, [previous])
    revenue_growth = growth_evidence.rate
    if growth_evidence.reason:
        warnings.append(f"revenue_growth_unavailable_{growth_evidence.reason}")
    elif growth_evidence.elapsed_years and growth_evidence.elapsed_years > 1:
        warnings.append("revenue_growth_annualized_over_fiscal_gap")
    previous_ebitda = _trajectory_ebitda(request, previous, earnings_basis)
    latest_ebitda = _trajectory_ebitda(request, latest, earnings_basis)
    previous_ebitda_margin = previous_ebitda / previous_revenue if previous_revenue > 0 else None
    latest_ebitda_margin = latest_ebitda / latest_revenue if latest_revenue > 0 else None
    ebitda_margin_change = (
        latest_ebitda_margin - previous_ebitda_margin
        if latest_ebitda_margin is not None and previous_ebitda_margin is not None
        else None
    )

    latest_gross_margin = _ratio(getattr(latest, "gross_margin", None), latest_revenue)
    previous_gross_margin = _ratio(getattr(previous, "gross_margin", None), previous_revenue)
    gross_margin_change = (
        latest_gross_margin - previous_gross_margin
        if latest_gross_margin is not None and previous_gross_margin is not None
        else None
    )

    latest_cash_flow = _cash_flow(latest)
    previous_cash_flow = _cash_flow(previous)
    cash_burn_change = (
        max(-latest_cash_flow, Decimal("0")) - max(-previous_cash_flow, Decimal("0"))
        if latest_cash_flow is not None and previous_cash_flow is not None
        else None
    )
    latest_wc = _working_capital(latest)
    previous_wc = _working_capital(previous)
    working_capital_change = (
        latest_wc - previous_wc if latest_wc is not None and previous_wc is not None else None
    )

    comparability_blocked = (
        accounting_basis_changed
        or period_duration_changed
        or currency_lineage_changed
        or revenue_semantics_changed
    )
    if comparability_blocked:
        ebitda_direction = "unknown"
    elif ebitda_margin_change is None:
        ebitda_direction = "unknown"
    elif ebitda_margin_change > Decimal("0.02"):
        ebitda_direction = "improving"
    elif ebitda_margin_change < Decimal("-0.02"):
        ebitda_direction = "deteriorating"
    else:
        ebitda_direction = "stable"

    revenue_direction = "stable"
    if revenue_growth is not None and revenue_growth > Decimal("0.05"):
        revenue_direction = "improving"
    elif revenue_growth is not None and revenue_growth < Decimal("-0.05"):
        revenue_direction = "deteriorating"
        conflicts.append("revenue_contraction")
    if cash_burn_change is not None and cash_burn_change > 0:
        conflicts.append("worsening_cash_conversion")
    if working_capital_change is not None and working_capital_change > 0:
        conflicts.append("working_capital_absorption")
    if (
        getattr(latest, "capex", None) is not None
        and getattr(previous, "capex", None) is not None
        and safe_decimal_or_zero(latest.capex) < safe_decimal_or_zero(previous.capex)
        and revenue_direction != "improving"
    ):
        conflicts.append("reduced_product_investment")

    if comparability_blocked:
        direction = "unknown"
    elif ebitda_direction == revenue_direction:
        direction = ebitda_direction
    elif ebitda_direction == "stable" and revenue_direction == "stable":
        direction = "stable"
    else:
        direction = "mixed"

    if comparability_blocked:
        confidence = "low"
    elif periods == 2:
        confidence = "low"
        warnings.append("insufficient_history_for_durable_trend")
    elif periods == 3:
        confidence = "medium"
    else:
        pair_directions: list[str] = []
        for older, newer in zip(rows, rows[1:]):
            old_revenue = Decimal(str(older.revenue))
            new_revenue = Decimal(str(newer.revenue))
            if old_revenue <= 0 or new_revenue <= 0:
                continue
            delta = (
                _trajectory_ebitda(request, newer, earnings_basis) / new_revenue
                - _trajectory_ebitda(request, older, earnings_basis) / old_revenue
            )
            pair_directions.append(
                "improving"
                if delta > Decimal("0.02")
                else "deteriorating" if delta < Decimal("-0.02") else "stable"
            )
        confidence = "high" if pair_directions and len(set(pair_directions)) == 1 else "medium"
        if confidence == "medium":
            warnings.append("inconsistent_historical_direction")

    if not isinstance(earnings_basis, Mapping) and any(
        getattr(row, "ebitda_normalized", False) for row in rows
    ):
        warnings.append("unverified_normalization_reclassification_preserved_reported")

    return OperatingTrajectory(
        direction=direction,
        ebitda_direction=ebitda_direction,
        confidence=confidence,
        comparable_periods=periods,
        latest_revenue_growth=revenue_growth,
        latest_gross_margin_change=gross_margin_change,
        latest_ebitda_margin_change=ebitda_margin_change,
        latest_cash_burn_change=cash_burn_change,
        latest_working_capital_change=working_capital_change,
        warnings=warnings,
        conflicts=list(dict.fromkeys(conflicts)),
    )


def _method_band(result: MethodResult | None) -> tuple[Decimal, Decimal, Decimal] | None:
    if result is None or result.available is not True or result.value is None:
        return None
    mid = Decimal(str(result.value))
    low = Decimal(str(result.value_low if result.value_low is not None else mid))
    high = Decimal(str(result.value_high if result.value_high is not None else mid))
    if not all(value.is_finite() for value in (low, mid, high)) or not low <= mid <= high:
        raise ValueError("Recovery method range must be finite and ordered")
    if mid <= 0:
        return None
    return low, mid, high


def _candidate_methods(
    request: CalculateRequest, context: _InputContext
) -> dict[str, MethodResult]:
    # Core recovery policy/tests must not initialize the full report/method
    # graph merely by importing this module. Load Omni only when candidates are
    # actually calculated.
    from src.domain.omni_calc_coordinator import calculate_all_methods

    calibration = context.calibration
    ev_multiple = safe_float(getattr(calibration, "ev_ebitda_median", None))
    p25_raw = getattr(calibration, "ev_ebitda_p25", None)
    p25 = safe_float(ev_multiple if p25_raw is None else p25_raw)
    p75_raw = getattr(calibration, "ev_ebitda_p75", None)
    p75 = safe_float(ev_multiple if p75_raw is None else p75_raw)
    debt = safe_float(request.current_year.total_debt)
    cash = safe_float(request.current_year.cash)
    liquidation_inputs = {
        "enable_sensitivity": False,
        **(request.liquidation_inputs or {}),
    }
    return calculate_all_methods(
        ebitda=context.ebitda,
        revenue=context.revenue,
        ev_ebitda_multiple=ev_multiple,
        p25_multiple=p25,
        p75_multiple=p75,
        total_adjustment=0.0,
        total_debt=debt,
        cash=cash,
        equity_value_mid=Decimal("0"),
        dcf_results=None,
        dcf_exclusion_reason="Recovery DCF is resolved by negative_ebitda_recovery.v1.",
        calibration=calibration,
        revenue_growth=safe_float(context.revenue_growth),
        owner_dependency=None,
        industry=request.industry,
        recurring_revenue_percentage=request.recurring_revenue_percentage,
        ownership_multiplier=context.ownership_multiplier,
        country_code=request.country_code,
        company_name=request.company_name,
        business_model=context.normalized_business_model,
        founding_year=request.founding_year,
        reporting_year=request.current_year.year,
        balance_sheet=context.balance_sheet,
        business_context=request.business_context,
        business_type_id=context.primary_business_type_id,
        primary_basis="hybrid",
        liquidation_inputs=liquidation_inputs,
        real_estate_yield_evidence=request.real_estate_yield_evidence_contract,
    )


def _funding_state(
    recovery: RecoveryInputs,
    scenario: RecoveryScenario,
    fcff_by_year: list[tuple[int, Decimal]],
    *,
    authoritative_opening_cash: Decimal,
) -> tuple[Decimal, Decimal]:
    cash_without_funding = authoritative_opening_cash
    gross_need = Decimal("0")
    for _, fcff in fcff_by_year:
        cash_without_funding += fcff
        gross_need = max(
            gross_need,
            recovery.funding_plan.minimum_cash - cash_without_funding,
        )

    cash_with_funding = authoritative_opening_cash
    unresolved = Decimal("0")
    commitments = recovery.funding_plan.commitments
    for year, fcff in fcff_by_year:
        cash_with_funding += sum(
            (item.amount for item in commitments if item.available_year == year),
            Decimal("0"),
        )
        cash_with_funding += fcff
        unresolved = max(
            unresolved,
            recovery.funding_plan.minimum_cash - cash_with_funding,
        )
    return max(gross_need, Decimal("0")), max(unresolved, Decimal("0"))


def _scenario_dcf(
    *,
    request: CalculateRequest,
    recovery: RecoveryInputs,
    scenario: RecoveryScenario,
    allow_value: bool,
    floor_band: tuple[Decimal, Decimal, Decimal] | None,
    trajectory: OperatingTrajectory,
) -> RecoveryScenarioResult:
    blockers: list[str] = []
    warnings: list[str] = []
    derived_schedule: list[dict[str, object]] = []
    nol_carry = Decimal("0")
    fcff_by_year: list[tuple[int, Decimal]] = []
    break_even_year: int | None = None

    for index, row in enumerate(scenario.forecast_years):
        ebitda = row.revenue - row.operating_expenses_excluding_da
        ebit = ebitda - row.depreciation_and_amortization
        # Only the first forecast-year opening NOL is an external input. Every
        # later opening balance is derived from the prior closing carryforward;
        # this prevents the same loss shield from being reintroduced annually.
        input_nol_opening = row.nol_opening
        nol_available = input_nol_opening if index == 0 else nol_carry
        if index > 0 and input_nol_opening != nol_available:
            warnings.append("nol_opening_rederived_from_prior_year")
        taxable_before_nol = max(ebit, Decimal("0"))
        nol_used = min(nol_available, taxable_before_nol)
        taxable_income = taxable_before_nol - nol_used
        cash_taxes = taxable_income * row.tax_rate
        nol_carry = nol_available - nol_used + max(-ebit, Decimal("0"))
        fcff = ebit - cash_taxes + row.depreciation_and_amortization - row.capex - row.delta_nwc
        if break_even_year is None and ebitda > 0 and fcff > 0:
            break_even_year = row.year
        fcff_by_year.append((row.year, fcff))
        derived_schedule.append(
            {
                "year": row.year,
                "revenue": row.revenue,
                "ebitda": ebitda,
                "ebit": ebit,
                "input_nol_opening": input_nol_opening,
                "nol_opening": nol_available,
                "nol_used": nol_used,
                "nol_closing": nol_carry,
                "cash_taxes": cash_taxes,
                "fcff": fcff,
            }
        )

    reported_cash = request.current_year.cash
    authoritative_opening_cash = (
        safe_decimal_or_zero(reported_cash)
        if reported_cash is not None
        else recovery.funding_plan.opening_cash
    )
    if authoritative_opening_cash != recovery.funding_plan.opening_cash:
        warnings.append("funding_opening_cash_reconciled_to_current_accounts")
    funding_gap, unresolved_funding = _funding_state(
        recovery,
        scenario,
        fcff_by_year,
        authoritative_opening_cash=authoritative_opening_cash,
    )
    if not allow_value:
        blockers.append("unsigned_or_unreconciled_recovery_case")
    if unresolved_funding > 0:
        blockers.append("unresolved_funding")
    if "worsening_cash_conversion" in trajectory.conflicts:
        blockers.append("worsening_cash_conversion_requires_reconciliation")
    last_two = derived_schedule[-2:]
    if len(last_two) < 2 or any(
        safe_decimal_or_zero(row["ebitda"]) <= 0 or safe_decimal_or_zero(row["fcff"]) <= 0
        for row in last_two
    ):
        blockers.append("terminal_positive_ebitda_and_fcff_not_demonstrated")
    if break_even_year is None:
        blockers.append("positive_ebitda_and_fcff_not_reached")

    wacc = scenario.wacc_override or recovery.governed_assumptions.wacc
    growth = (
        scenario.terminal_growth_override
        if scenario.terminal_growth_override is not None
        else recovery.governed_assumptions.terminal_growth_rate
    )
    if growth >= wacc:
        blockers.append("terminal_growth_not_below_wacc")
    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    if blockers:
        if (
            floor_band is not None
            and allow_value
            and blockers != ["unsigned_or_unreconciled_recovery_case"]
        ):
            low, mid, high = floor_band
            return RecoveryScenarioResult(
                key=scenario.key,
                probability_percent=scenario.probability_percent,
                status="floor_substituted",
                equity_value_low=low,
                equity_value_mid=mid,
                equity_value_high=high,
                break_even_year=break_even_year,
                funding_gap=funding_gap,
                blockers=blockers,
                warnings=warnings,
                derived_schedule=derived_schedule,
            )
        return RecoveryScenarioResult(
            key=scenario.key,
            probability_percent=scenario.probability_percent,
            status="blocked",
            break_even_year=break_even_year,
            funding_gap=funding_gap,
            blockers=blockers,
            warnings=warnings,
            derived_schedule=derived_schedule,
        )

    def value_at(rate: Decimal, terminal_growth: Decimal) -> tuple[Decimal, Decimal]:
        present_explicit = sum(
            (
                fcff / ((Decimal("1") + rate) ** index)
                for index, (_, fcff) in enumerate(fcff_by_year, 1)
            ),
            Decimal("0"),
        )
        terminal_fcff = fcff_by_year[-1][1] * (Decimal("1") + terminal_growth)
        terminal_value = terminal_fcff / (rate - terminal_growth)
        present_terminal = terminal_value / ((Decimal("1") + rate) ** len(fcff_by_year))
        return present_explicit + present_terminal, present_terminal

    low_wacc = min(Decimal("0.95"), wacc + Decimal("0.01"))
    low_growth = max(Decimal("-0.1"), growth - Decimal("0.005"))
    high_wacc = max(growth + Decimal("0.0051"), wacc - Decimal("0.01"))
    high_growth = min(high_wacc - Decimal("0.0001"), growth + Decimal("0.005"))
    ev_low, _ = value_at(low_wacc, low_growth)
    ev_mid, terminal_pv = value_at(wacc, growth)
    ev_high, _ = value_at(high_wacc, high_growth)
    ev_low, ev_high = min(ev_low, ev_high), max(ev_low, ev_high)
    debt = safe_decimal_or_zero(request.current_year.total_debt)
    # Minimum operating cash is required to execute the plan and is not excess
    # cash distributable to current shareholders at the valuation date.
    cash = authoritative_opening_cash
    excess_cash = max(cash - recovery.funding_plan.minimum_cash, Decimal("0"))
    ownership = Decimal(
        str(request.shares_for_sale if request.shares_for_sale is not None else 100)
    ) / Decimal("100")
    shareholder_bridge_complete = (
        request.current_year.cash is not None
        and request.current_year.total_debt is not None
        and len(recovery.funding_plan.commitments) == 0
    )
    equities = (
        tuple((value + excess_cash - debt) * ownership for value in (ev_low, ev_mid, ev_high))
        if shareholder_bridge_complete
        else None
    )
    if min(ev_low, ev_mid, ev_high) <= 0:
        if floor_band is not None:
            low, mid, high = floor_band
            return RecoveryScenarioResult(
                key=scenario.key,
                probability_percent=scenario.probability_percent,
                status="floor_substituted",
                equity_value_low=low,
                equity_value_mid=mid,
                equity_value_high=high,
                break_even_year=break_even_year,
                funding_gap=funding_gap,
                blockers=["dcf_value_not_positive_after_equity_bridge"],
                warnings=warnings,
                derived_schedule=derived_schedule,
            )
        return RecoveryScenarioResult(
            key=scenario.key,
            probability_percent=scenario.probability_percent,
            status="blocked",
            break_even_year=break_even_year,
            funding_gap=funding_gap,
            blockers=["dcf_value_not_positive_after_equity_bridge"],
            warnings=warnings,
            derived_schedule=derived_schedule,
        )
    if equities is not None and min(equities) < 0:
        warnings.append("debt_overhang_before_shareholder_floor")
    terminal_share = terminal_pv / ev_mid if ev_mid > 0 else None
    if equities is None:
        warnings.append("current_shareholder_equity_conditional_on_financing_terms")
    return RecoveryScenarioResult(
        key=scenario.key,
        probability_percent=scenario.probability_percent,
        status="eligible",
        enterprise_value_low=ev_low.quantize(Decimal("0.01")),
        enterprise_value_mid=ev_mid.quantize(Decimal("0.01")),
        enterprise_value_high=ev_high.quantize(Decimal("0.01")),
        equity_value_low=(equities[0].quantize(Decimal("0.01")) if equities else None),
        equity_value_mid=(equities[1].quantize(Decimal("0.01")) if equities else None),
        equity_value_high=(equities[2].quantize(Decimal("0.01")) if equities else None),
        break_even_year=break_even_year,
        funding_gap=funding_gap.quantize(Decimal("0.01")),
        terminal_value_share=(
            terminal_share.quantize(Decimal("0.0001")) if terminal_share is not None else None
        ),
        warnings=warnings,
        derived_schedule=derived_schedule,
    )


def _verified_recovery_inputs(request: CalculateRequest) -> bool:
    from .recovery_source_admission import recovery_forecasts_are_source_verified

    if not recovery_forecasts_are_source_verified(request):
        return False
    recovery = request.recovery_inputs
    if recovery is None:
        return False
    case = request.valuation_case
    if case is None or case.schema_version != "valuation_case.v2" or case.case_attestation is None:
        return False
    review = case.recovery_automated_review
    if not isinstance(review, Mapping):
        return False
    checks = review.get("checks")
    if (
        review.get("schema_version") != "recovery_automated_review.v1"
        or not isinstance(checks, Mapping)
        or any(
            checks.get(key) is not True
            for key in (
                "scenario_set_complete",
                "forecast_rows_evidence_backed",
                "operating_drivers_reconciled",
                "reinvestment_inputs_present",
                "funding_state_evidence_backed",
                "governed_assumptions_evidence_backed",
            )
        )
    ):
        return False
    committed_snapshot = dict(case.recovery_inputs_snapshot or {})
    committed_snapshot.pop("verification_receipt", None)
    expected_hash = _canonical_hash(committed_snapshot)
    # No human role or receipt gates DCF. Titan's signed, schedule-bound
    # automated review plus ValuationIQ's own FCFF/runway/terminal controls do.
    return review.get("recovery_inputs_hash") == expected_hash


def _candidate_audit(
    *,
    methods: Mapping[str, MethodResult],
    benchmark_governed: bool,
    revenue_reliable: bool,
    revenue_quality: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    audit: dict[str, dict[str, object]] = {}
    for key in (
        "ebitda_multiple",
        "sde_multiple",
        "dcf",
        "arr_multiple",
        "omzet_multiple",
        "adjusted_nav",
        "liquidation_analysis",
    ):
        result = methods.get(key)
        accepted = bool(result and result.available and _method_band(result) is not None)
        reason = None if accepted else getattr(result, "unavailable_reason", None)
        if key in {"arr_multiple", "omzet_multiple"} and not benchmark_governed:
            accepted = False
            reason = "governed_matching_benchmark_required"
        if key == "omzet_multiple" and not revenue_reliable:
            accepted = False
            reason = "reliable_revenue_evidence_required"
        if key == "arr_multiple" and revenue_quality.get("arr_qualified") is not True:
            accepted = False
            reason = "recurring_revenue_quality_threshold_not_met"
        if key in {"ebitda_multiple", "sde_multiple"}:
            accepted = False
            reason = "positive_multiple_cannot_be_applied_to_negative_ebitda"
        audit[key] = {"accepted": accepted, "reason": reason}
        if key in {"arr_multiple", "omzet_multiple"}:
            audit[key].update(
                {
                    "quality_evidence_complete": revenue_quality.get("quality_evidence_complete"),
                    "quality_evidence": revenue_quality.get("quality_evidence"),
                    "missing_quality_evidence": revenue_quality.get("missing_quality_evidence"),
                    "confidence_cap": revenue_quality.get("confidence_cap"),
                }
            )
    return audit


def _revenue_quality_assessment(request: CalculateRequest) -> dict[str, object]:
    """Grade revenue-method evidence without turning absence into fake precision.

    A governed benchmark and a reliable positive revenue basis remain the
    numeric eligibility gates. Quality evidence controls confidence and the
    follow-up evidence list so filed-turnover cases can still produce a
    conservative public curve while richer private evidence can earn medium
    confidence. No advisor review is involved.
    """

    current = request.current_year
    source = str(current.revenue_source or "management_accounts").strip().lower()
    evidence: list[str] = []
    if source == "turnover":
        evidence.append("filed_turnover")
    if current.gross_margin is not None:
        evidence.append("gross_margin_profile")
    if (
        request.rev_top_client_concentration_pct is not None
        or request.rev_top_client_amount is not None
    ):
        evidence.append("customer_concentration")
    if request.rev_contract_backlog is not None:
        evidence.append("contracted_backlog")
    if request.owner_dependency_factors is not None:
        evidence.append("owner_transferability")
    if (
        request.recurring_revenue_percentage > 0
        or request.rev_recurring_pct is not None
        or request.rev_recurring_amount is not None
    ):
        evidence.append("recurring_revenue")

    required_dimensions = {
        "gross_margin_profile",
        "customer_concentration",
        "contracted_backlog_or_duration",
        "owner_transferability",
    }
    satisfied_dimensions = {item for item in evidence if item in required_dimensions}
    if "contracted_backlog" in evidence:
        satisfied_dimensions.add("contracted_backlog_or_duration")
    missing = sorted(required_dimensions - satisfied_dimensions)
    # Two independent quality dimensions are enough for a medium-confidence
    # benchmark indication. A filed turnover source establishes the amount,
    # but is not itself treated as evidence of margin or transferability.
    quality_complete = len(satisfied_dimensions) >= 2
    return {
        "revenue_basis": source,
        "quality_evidence": evidence,
        "missing_quality_evidence": missing,
        "quality_evidence_complete": quality_complete,
        "confidence_cap": "medium" if quality_complete else "low",
        "arr_qualified": request.recurring_revenue_percentage >= Decimal("0.70"),
    }


def resolve_negative_ebitda(
    request: CalculateRequest,
    context: _InputContext,
    *,
    evaluated_at: datetime | None = None,
) -> RecoveryOutcome:
    evaluated_at = evaluated_at or datetime.now(timezone.utc)
    analytics_dimensions = {
        "business_type": context.primary_business_type_id,
        "ebitda_band": _ebitda_band(reported_ebitda(request)),
        "conversion_stage": "calculation",
    }
    logger.info("negative_ebitda_case_detected", extra=analytics_dimensions)
    trajectory = build_operating_trajectory(request, context.earnings_basis)
    methods = _candidate_methods(request, context)
    benchmark_governed = context.benchmark_contract is not None
    revenue_reliable = bool(
        request.current_year.revenue > 0
        and str(request.current_year.revenue_source or "").strip().lower()
        not in {"gross_margin", "gross_profit", "unresolved"}
    )
    revenue_quality = _revenue_quality_assessment(request)
    audit = _candidate_audit(
        methods=methods,
        benchmark_governed=benchmark_governed,
        revenue_reliable=revenue_reliable,
        revenue_quality=revenue_quality,
    )

    selected_method = str(request.selected_method or "").strip().lower()
    floor_order = (
        ("liquidation_analysis", "adjusted_nav")
        if selected_method in {"liquidation", "liquidation_analysis"}
        else ("adjusted_nav", "liquidation_analysis")
    )
    floor_key = next(
        (key for key in floor_order if audit[key]["accepted"] is True),
        None,
    )
    floor_band = _method_band(methods.get(floor_key)) if floor_key is not None else None
    recovery = request.recovery_inputs
    verified = _verified_recovery_inputs(request)
    from .recovery_pricing_policy import recovery_pricing_allowed

    pricing_allowed = recovery_pricing_allowed(request, source_verified=verified)
    scenario_results: list[RecoveryScenarioResult] = []
    weighted_equity: tuple[Decimal, Decimal, Decimal] | None = None
    weighted_enterprise: tuple[Decimal, Decimal, Decimal] | None = None

    if recovery is not None:
        logger.info(
            "recovery_dcf_started",
            extra={
                **analytics_dimensions,
                "evidence_complete": verified,
                "advisor_review": bool(
                    recovery.verification_receipt
                    and recovery.verification_receipt.actor_role == "advisor"
                ),
            },
        )
        scenario_results = [
            _scenario_dcf(
                request=request,
                recovery=recovery,
                scenario=scenario,
                allow_value=pricing_allowed,
                floor_band=floor_band,
                trajectory=trajectory,
            )
            for scenario in recovery.scenarios
        ]
        if pricing_allowed and not verified:
            scenario_results = [
                result.model_copy(
                    update={
                        "warnings": [*result.warnings, "disclosed_assumptions_not_source_verified"]
                    }
                )
                for result in scenario_results
            ]
        dcf_eligible_count = sum(result.status == "eligible" for result in scenario_results)
        all_probability_covered = all(result.status != "blocked" for result in scenario_results)
        dcf_rejection_reasons = list(
            dict.fromkeys(blocker for result in scenario_results for blocker in result.blockers)
        )
        audit["dcf"] = {
            "accepted": bool(
                pricing_allowed and dcf_eligible_count > 0 and all_probability_covered
            ),
            "reason": (
                None
                if pricing_allowed and dcf_eligible_count > 0 and all_probability_covered
                else (
                    "unsigned_or_unreconciled_recovery_case"
                    if not verified
                    else (
                        "all_scenarios_resolved_to_asset_floor"
                        if dcf_eligible_count == 0 and all_probability_covered
                        else ",".join(dcf_rejection_reasons) or "recovery_dcf_not_eligible"
                    )
                )
            ),
            "source_verified": verified,
            "pricing_basis": "source_verified" if verified else "disclosed_assumptions",
            "eligible_scenarios": dcf_eligible_count,
            "covered_scenarios": sum(result.status != "blocked" for result in scenario_results),
        }
        logger.info(
            (
                "recovery_dcf_completed"
                if audit["dcf"]["accepted"] is True
                else "recovery_dcf_blocked"
            ),
            extra={
                **analytics_dimensions,
                "evidence_complete": verified,
                "eligible_scenarios": dcf_eligible_count,
                "covered_scenarios": sum(result.status != "blocked" for result in scenario_results),
            },
        )
        if pricing_allowed and dcf_eligible_count > 0 and all_probability_covered:
            weighted_equity_values = [Decimal("0"), Decimal("0"), Decimal("0")]
            weighted_enterprise_values = [Decimal("0"), Decimal("0"), Decimal("0")]
            enterprise_complete = True
            equity_complete = True
            for result in scenario_results:
                probability = result.probability_percent / Decimal("100")
                equity_values = (
                    result.equity_value_low,
                    result.equity_value_mid,
                    result.equity_value_high,
                )
                if any(value is None for value in equity_values):
                    equity_complete = False
                else:
                    for index, value in enumerate(equity_values):
                        weighted_equity_values[index] += safe_decimal_or_zero(value) * probability
                enterprise_values = (
                    result.enterprise_value_low,
                    result.enterprise_value_mid,
                    result.enterprise_value_high,
                )
                if any(value is None for value in enterprise_values):
                    enterprise_complete = False
                else:
                    for index, value in enumerate(enterprise_values):
                        weighted_enterprise_values[index] += (
                            safe_decimal_or_zero(value) * probability
                        )
            if equity_complete:
                weighted_equity = tuple(
                    value.quantize(Decimal("0.01")) for value in weighted_equity_values
                )
            if enterprise_complete:
                weighted_enterprise = tuple(
                    value.quantize(Decimal("0.01")) for value in weighted_enterprise_values
                )

    blockers: list[str] = []
    required_evidence: list[str] = []
    actions: list[str] = []
    primary_method: str | None = None
    status = "no_going_concern_range"
    cross_checks: list[str] = []
    confidence = "low"
    headline_equity = weighted_equity
    headline_enterprise = weighted_enterprise

    if weighted_enterprise is not None:
        status = "recovery_eligible"
        primary_method = "recovery_dcf"
        if weighted_equity is None:
            blockers.append("current_shareholder_equity_conditional")
            required_evidence.append("evidence_backed_financing_allocation_terms")
        cross_checks = [
            method
            for key, method in (
                ("arr_multiple", "arr_multiple"),
                ("omzet_multiple", "revenue_multiple"),
                ("adjusted_nav", "adjusted_nav"),
                ("liquidation_analysis", "orderly_liquidation"),
            )
            if audit[key]["accepted"] is True
        ]
        confidence = "medium" if verified else "low"
        max_terminal_share = max(
            (
                result.terminal_value_share
                for result in scenario_results
                if result.terminal_value_share is not None
            ),
            default=None,
        )
        if max_terminal_share is not None and max_terminal_share > Decimal("0.85"):
            blockers.append("terminal_value_share_above_85_percent")
            confidence = "medium" if verified else "low"
        elif max_terminal_share is not None and max_terminal_share > Decimal("0.75"):
            blockers.append("terminal_value_share_above_75_percent")
            if confidence == "high":
                confidence = "medium"
    else:
        arr_band = _method_band(methods.get("arr_multiple"))
        revenue_band = _method_band(methods.get("omzet_multiple"))
        recurring = request.recurring_revenue_percentage >= Decimal("0.7")
        if recurring and audit["arr_multiple"]["accepted"] is True and arr_band is not None:
            status = "revenue_benchmark_eligible"
            primary_method = "arr_multiple"
            headline_equity = arr_band
            confidence = str(revenue_quality["confidence_cap"])
            if audit["omzet_multiple"]["accepted"] is True:
                cross_checks.append("revenue_multiple")
        elif audit["omzet_multiple"]["accepted"] is True and revenue_band is not None:
            status = "revenue_benchmark_eligible"
            primary_method = "revenue_multiple"
            headline_equity = revenue_band
            confidence = str(revenue_quality["confidence_cap"])
            if audit["arr_multiple"]["accepted"] is True:
                cross_checks.append("arr_multiple")
        elif floor_band is not None and floor_key is not None:
            status = "asset_floor_only"
            primary_method = (
                "adjusted_nav" if floor_key == "adjusted_nav" else "orderly_liquidation"
            )
            headline_equity = floor_band
            confidence = "medium"
            # A scenario table may still be present for recovery planning, but
            # if every scenario resolved to the same governed floor it must not
            # be mislabeled or probability-weighted as Recovery DCF.
            if scenario_results and all(
                result.status == "floor_substituted" for result in scenario_results
            ):
                blockers.extend(
                    blocker for result in scenario_results for blocker in result.blockers
                )
        else:
            blockers.extend(
                [
                    "negative_normalized_ebitda",
                    "no_defensible_going_concern_or_asset_floor",
                ]
            )
            if recovery is None:
                blockers.append("recovery_scenarios_missing")
                required_evidence.extend(
                    [
                        "three_probability_weighted_recovery_schedules",
                        "funding_plan_with_committed_sources",
                        "governed_wacc_and_terminal_assumptions",
                        "titan_signed_case_with_reconciled_recovery_inputs",
                    ]
                )
            elif not verified:
                blockers.append("unsigned_or_unreconciled_recovery_case")
                required_evidence.append("titan_signed_recovery_case")
            for result in scenario_results:
                blockers.extend(result.blockers)
            if not benchmark_governed:
                required_evidence.append("governed_matching_revenue_or_arr_benchmark")
            if not revenue_reliable:
                required_evidence.append("reliable_revenue_or_arr_evidence")
            required_evidence.append("evidence_backed_adjusted_nav_or_orderly_liquidation_inputs")
            actions.extend(
                [
                    "Reconcile the operating drivers to an explicit break-even plan.",
                    "Secure committed funding through the minimum-cash point.",
                    "Document recurring revenue quality or an evidence-backed asset floor.",
                ]
            )
        if (
            primary_method in {"arr_multiple", "revenue_multiple"}
            and not revenue_quality["quality_evidence_complete"]
        ):
            required_evidence.extend(
                str(item) for item in revenue_quality["missing_quality_evidence"]
            )
            actions.append(
                "Add revenue-quality evidence to raise this benchmark indication above low confidence."
            )

    blockers = list(dict.fromkeys(blockers))
    required_evidence = list(dict.fromkeys(required_evidence))
    break_even = min(
        (result.break_even_year for result in scenario_results if result.break_even_year),
        default=None,
    )
    funding_gap = max(
        (result.funding_gap for result in scenario_results),
        default=None,
    )
    terminal_share = max(
        (
            result.terminal_value_share
            for result in scenario_results
            if result.terminal_value_share is not None
        ),
        default=None,
    )
    canonical_reported = (
        safe_decimal_or_zero(context.earnings_basis.get("current_reported_ebitda"))
        if "current_reported_ebitda" in context.earnings_basis
        else reported_ebitda(request)
    )
    canonical_normalized = (
        safe_decimal_or_zero(context.earnings_basis.get("current_normalized_ebitda"))
        if "current_normalized_ebitda" in context.earnings_basis
        else canonical_reported
    )
    normalization_bridge = {
        "reported_ebitda": canonical_reported,
        "accepted_adjustments": canonical_normalized - canonical_reported,
        "normalized_ebitda": canonical_normalized,
        "basis": "signed_valuation_case_decisions",
    }
    base_result = next(
        (result for result in scenario_results if result.key == "base"),
        None,
    )
    break_even_row = None
    if base_result is not None and base_result.break_even_year is not None:
        break_even_row = next(
            (
                row
                for row in base_result.derived_schedule
                if row.get("year") == base_result.break_even_year
            ),
            None,
        )
    break_even_bridge = (
        {
            "scenario": "base",
            "year": base_result.break_even_year,
            "revenue": break_even_row.get("revenue"),
            "ebitda": break_even_row.get("ebitda"),
            "fcff": break_even_row.get("fcff"),
        }
        if base_result is not None and break_even_row is not None
        else None
    )
    minimum_cash = recovery.funding_plan.minimum_cash if recovery is not None else Decimal("0")
    current_cash = safe_decimal_or_zero(request.current_year.cash)
    current_debt = safe_decimal_or_zero(request.current_year.total_debt)
    equity_bridge = (
        {
            "enterprise_value": headline_enterprise[1] if headline_enterprise is not None else None,
            "current_cash": current_cash,
            "minimum_operating_cash": minimum_cash,
            "excess_cash": max(current_cash - minimum_cash, Decimal("0")),
            "current_debt": current_debt,
            "funding_need": funding_gap,
            "current_equity_value": headline_equity[1] if headline_equity is not None else None,
            "ownership_percentage": Decimal(str(request.shares_for_sale or 100)),
            "funding_deducted_from_enterprise_value": False,
            "basis": (
                "pre_financing_current_shareholder_indication"
                if headline_equity is not None
                else "conditional_shareholder_value"
            ),
            "shareholder_equity_status": (
                "available" if headline_equity is not None else "conditional"
            ),
            "qualification": (
                "current_cash_debt_bridge_complete"
                if headline_equity is not None
                else "future_financing_allocation_depends_on_instrument_terms"
            ),
        }
        if headline_enterprise is not None
        else None
    )
    cause_codes = list(
        dict.fromkeys(
            [
                *trajectory.conflicts,
                *(
                    ["evidence_backed_normalization_bridge"]
                    if canonical_normalized != canonical_reported
                    else []
                ),
                "operating_loss_under_recovery",
            ]
        )
    )
    method_family = {
        "normalized_ebitda": "normalized_earnings",
        "sde": "normalized_earnings",
        "recovery_dcf": "recovery_dcf",
        "arr_multiple": "revenue_or_arr",
        "revenue_multiple": "revenue_or_arr",
        "adjusted_nav": "asset_floor",
        "orderly_liquidation": "distress_or_liquidation",
    }.get(primary_method, "insufficient_recovery_evidence")
    earnings_basis_text = str(context.earnings_basis).lower()
    if "owner" in earnings_basis_text and canonical_normalized != canonical_reported:
        primary_cause = "owner_compensation_distortion"
    elif "restructur" in earnings_basis_text or "one_off" in earnings_basis_text:
        primary_cause = "one_off_restructuring"
    elif "revenue_contraction" in trajectory.conflicts:
        primary_cause = "recent_customer_loss"
    elif "reduced_product_investment" in trajectory.conflicts:
        primary_cause = "product_development_investment"
    else:
        primary_cause = "insufficient_evidence"
    if canonical_normalized != canonical_reported:
        logger.info(
            "normalization_bridge_completed",
            extra={**analytics_dimensions, "evidence_complete": True},
        )
    input_material = (
        recovery
        if recovery is not None
        else {
            "current_year": request.current_year.model_dump(mode="json"),
            "historical_years": [row.model_dump(mode="json") for row in request.historical_years],
        }
    )
    resolution = NegativeEbitdaResolution(
        status=status,
        reported_ebitda=canonical_reported,
        normalized_ebitda=canonical_normalized,
        operating_trajectory=trajectory,
        primary_method=primary_method,
        method_family=method_family,
        primary_cause=primary_cause,
        cross_check_methods=cross_checks,
        break_even_year=break_even,
        funding_gap=funding_gap,
        terminal_value_share=terminal_share,
        headline_equity_value_low=headline_equity[0] if headline_equity else None,
        headline_equity_value_mid=headline_equity[1] if headline_equity else None,
        headline_equity_value_high=headline_equity[2] if headline_equity else None,
        headline_enterprise_value_low=(headline_enterprise[0] if headline_enterprise else None),
        headline_enterprise_value_mid=(headline_enterprise[1] if headline_enterprise else None),
        headline_enterprise_value_high=(headline_enterprise[2] if headline_enterprise else None),
        confidence=confidence,
        cause_codes=cause_codes,
        normalization_bridge=normalization_bridge,
        break_even_bridge=break_even_bridge,
        equity_bridge=equity_bridge,
        blockers=blockers,
        required_evidence=required_evidence,
        value_building_actions=actions,
        scenario_results=scenario_results,
        candidate_method_audit=audit,
        evaluated_at=evaluated_at,
        input_snapshot_hash=_canonical_hash(input_material),
        resolution_snapshot_hash="0" * 64,
    )
    resolution = resolution.model_copy(
        update={
            "resolution_snapshot_hash": _canonical_hash(
                resolution.model_dump(mode="json", exclude={"resolution_snapshot_hash"})
            )
        }
    )
    logger.info(
        "negative_ebitda_method_resolved",
        extra={
            "business_type": context.primary_business_type_id,
            "ebitda_band": _ebitda_band(reported_ebitda(request)),
            "chosen_method": resolution.primary_method,
            "resolution_status": resolution.status,
            "trajectory": resolution.operating_trajectory.ebitda_direction,
            "evidence_complete": (
                verified
                if resolution.primary_method == "recovery_dcf"
                else (
                    bool(revenue_quality["quality_evidence_complete"])
                    if resolution.primary_method in {"arr_multiple", "revenue_multiple"}
                    else resolution.primary_method is not None
                )
            ),
            "conversion_stage": "calculation",
            "advisor_review": bool(
                recovery
                and recovery.verification_receipt
                and recovery.verification_receipt.actor_role == "advisor"
            ),
            "candidate_methods": resolution.candidate_method_audit,
        },
    )
    if resolution.primary_method == "recovery_dcf":
        from .recovery_method_snapshot import recovery_dcf_method_snapshot

        methods["dcf"] = recovery_dcf_method_snapshot(resolution)
    return RecoveryOutcome(
        resolution=resolution,
        valuation_results=methods,
        equity_low=headline_equity[0] if headline_equity else None,
        equity_mid=headline_equity[1] if headline_equity else None,
        equity_high=headline_equity[2] if headline_equity else None,
        enterprise_low=headline_enterprise[0] if headline_enterprise else None,
        enterprise_mid=headline_enterprise[1] if headline_enterprise else None,
        enterprise_high=headline_enterprise[2] if headline_enterprise else None,
    )


def _confidence_score(level: str) -> int:
    return {"low": 35, "medium": 60, "high": 80}.get(level, 35)


def build_negative_ebitda_response(
    request: CalculateRequest,
    context: _InputContext,
    *,
    verified_titan_request_wire_commitment: Mapping[str, str] | None = None,
) -> CalculateResponse:
    outcome = resolve_negative_ebitda(request, context)
    resolution = outcome.resolution
    flags = list(context.triage_flags)
    flags.extend(
        TriageFlag(
            field="negative_ebitda_resolution",
            issue=code,
            severity="warning",
        )
        for code in resolution.blockers
    )
    methodologies = {
        "recovery_dcf": "RECOVERY_DCF",
        "arr_multiple": "ARR_MULTIPLE",
        "revenue_multiple": "OMZET_MULTIPLE",
        "adjusted_nav": "ADJUSTED_NAV",
        "orderly_liquidation": "LIQUIDATION_ANALYSIS",
    }
    method_labels = {
        "recovery_dcf": "Recovery DCF",
        "arr_multiple": "ARR benchmark",
        "revenue_multiple": "Revenue benchmark",
        "adjusted_nav": "Adjusted NAV floor",
        "orderly_liquidation": "Orderly liquidation floor",
    }
    methodology = methodologies.get(resolution.primary_method or "", "RECOVERY_ASSESSMENT")
    method_label = method_labels.get(resolution.primary_method or "", "Recovery assessment")
    confidence_score = _confidence_score(resolution.confidence)
    valuation_summary = (
        "No defensible range established yet. The recovery assessment identifies the "
        "break-even, funding and evidence requirements for a future valuation."
        if resolution.primary_method is None
        else f"Negative-EBITDA assessment resolved using {method_label}."
    )
    reported = reported_ebitda(request)
    normalized = (
        resolution.normalized_ebitda
        if resolution.normalized_ebitda is not None
        else resolution.reported_ebitda
    )
    dcf_results = None
    if resolution.primary_method == "recovery_dcf" and outcome.enterprise_mid is not None:
        dcf_results = {
            "model_version": MODEL_VERSION,
            "enterprise_value": outcome.enterprise_mid,
            "enterprise_value_low": outcome.enterprise_low,
            "enterprise_value_high": outcome.enterprise_high,
            "equity_value": outcome.equity_mid,
            "terminal_value_share": resolution.terminal_value_share,
            "funding_need_shown_separately": True,
            "funding_deducted_from_enterprise_value": False,
            "scenario_results": [
                result.model_dump(mode="json") for result in resolution.scenario_results
            ],
        }
    financial_metrics = {
        "revenue": request.current_year.revenue,
        "reported_ebitda": reported,
        "normalized_ebitda": normalized,
        "ebitda_margin": (
            reported / request.current_year.revenue if request.current_year.revenue > 0 else None
        ),
    }
    data_quality = {
        "recovery_input_complete": request.recovery_inputs is not None,
        "authenticated_verification": _verified_recovery_inputs(request),
        "trajectory_confidence": resolution.operating_trajectory.confidence,
    }
    data_tier = "defensible" if resolution.confidence != "low" else "indicative"
    report_readiness_state = (
        "automated_recovery_ready"
        if resolution.primary_method is not None
        else "recovery_assessment_complete_no_range"
    )
    defensibility_review_state = (
        "automated_evidence_reviewed"
        if resolution.primary_method == "recovery_dcf" and _verified_recovery_inputs(request)
        else "evidence_governed" if resolution.primary_method is not None else "evidence_requested"
    )
    valuation_disclaimer = (
        "Recovery scenarios are conditional and are not a guarantee of funding or performance."
    )
    if resolution.primary_method == "recovery_dcf" and not _verified_recovery_inputs(request):
        data_tier = "indicative"
        defensibility_review_state = "indicative_assumptions"
        valuation_disclaimer += (
            " This indicative estimate uses disclosed scenario assumptions; "
            "the company forecast has not been source-verified."
        )
    valuation_run = None
    driver_ledger: dict[str, object] | None = None
    if (
        resolution.primary_method is not None
        and outcome.equity_low is not None
        and outcome.equity_mid is not None
        and outcome.equity_high is not None
    ):
        from src.services.reports.stateless_valuation_run import (
            build_stateless_valuation_run,
            build_value_driver_ledger,
        )

        driver_ledger = build_value_driver_ledger(
            earnings_basis_ledger=context.earnings_basis,
            multiple_build_up={},
            equity_bridge_adjustments={
                "funding_gap": resolution.funding_gap,
                "funding_need_shown_separately": True,
                "funding_deducted_from_enterprise_value": False,
            },
            holdings_consolidation=context.holdings_consolidation,
            owner_dependency_result=None,
            owner_dependency_adjustment=Decimal("0"),
            ownership_percentage=Decimal("1"),
            equity_before_owner_dependency=outcome.equity_mid,
            equity_after_owner_dependency=outcome.equity_mid,
            canonical_enterprise_value=outcome.enterprise_mid,
            methodology_used=methodology,
        )
        valuation_run = build_stateless_valuation_run(
            request=request,
            verified_titan_request_wire_commitment=verified_titan_request_wire_commitment,
            calculation_timestamp=resolution.evaluated_at.isoformat(),
            equity_values={
                "low": outcome.equity_low,
                "mid": outcome.equity_mid,
                "high": outcome.equity_high,
            },
            enterprise_values=(
                {
                    "low": outcome.enterprise_low,
                    "mid": outcome.enterprise_mid,
                    "high": outcome.enterprise_high,
                }
                if outcome.enterprise_low is not None
                and outcome.enterprise_mid is not None
                and outcome.enterprise_high is not None
                else None
            ),
            methodology_used=methodology,
            dcf_weight=(
                Decimal("1") if resolution.primary_method == "recovery_dcf" else Decimal("0")
            ),
            multiples_weight=(
                Decimal("1")
                if resolution.primary_method in {"arr_multiple", "revenue_multiple"}
                else Decimal("0")
            ),
            valuation_results=outcome.valuation_results,
            benchmark_contract=context.benchmark_contract,
            triage_flags=flags,
            driver_ledger=driver_ledger,
            public_valuation_audit=None,
            valuation_timeline=None,
            forward_value_cone=None,
            weighted_valuation=None,
            financial_metrics=financial_metrics,
            dcf_results=dcf_results,
            multiples_results=None,
            response_snapshot={
                "recommended_asking_price": outcome.equity_mid,
                "recommended_multiple": None,
                "methodology_selection_reason": (
                    "Exclusive negative-EBITDA method ladder from " "negative_ebitda_resolution.v1."
                ),
                "dcf_exclusion_reason": (
                    None
                    if resolution.primary_method == "recovery_dcf"
                    else "Recovery DCF eligibility gates were not satisfied."
                ),
                "confidence_level": resolution.confidence.upper(),
                "confidence_score": confidence_score,
                "earnings_basis": (
                    "Revenue"
                    if resolution.primary_method in {"arr_multiple", "revenue_multiple"}
                    else None
                ),
                "earnings_basis_rationale": (
                    "A positive earnings multiple was not applied to negative EBITDA."
                ),
                "earnings_basis_ledger": context.earnings_basis,
                "holdings_consolidation": context.holdings_consolidation,
                "size_discount": Decimal("0"),
                "liquidity_discount": Decimal("0"),
                "owner_dependency_adjustment": Decimal("0"),
                "country_adjustment": Decimal("0"),
                "total_adjustment": Decimal("0"),
                "valuation_summary": valuation_summary,
                "key_value_drivers": [
                    "Operating break-even",
                    "Committed funding",
                    "Revenue quality",
                ],
                "risk_factors": resolution.blockers[:10],
                "data_quality": data_quality,
                "data_tier": data_tier,
                "data_tier_rationale": "Recovery confidence is bounded by evidence and verification.",
                "publication_allowed": False,
                "publication_blocked": True,
                "report_readiness_state": report_readiness_state,
                "defensibility_review_state": defensibility_review_state,
                "valuation_method_label": method_label,
                "confidence_label": f"{resolution.confidence.title()} recovery confidence",
                "present_point_estimate": False,
                "valuation_disclaimer": valuation_disclaimer,
                # Preserve Decimal/datetime values until the valuation-run
                # transport stabilizer serializes the complete response.  A
                # field-local JSON dump can normalize nested values differently
                # from the typed outer CalculateResponse and make an otherwise
                # valid run fail its own immutable snapshot check.
                "negative_ebitda_resolution": resolution.model_dump(mode="python"),
            },
        )

    return CalculateResponse(
        status="WARNINGS",
        valuation_id=request.valuation_id,
        calculation_timestamp=resolution.evaluated_at.isoformat(),
        valuation_run=valuation_run,
        equity_value_low=outcome.equity_low,
        equity_value_mid=outcome.equity_mid,
        equity_value_high=outcome.equity_high,
        enterprise_value_low=outcome.enterprise_low,
        enterprise_value_mid=outcome.enterprise_mid,
        enterprise_value_high=outcome.enterprise_high,
        recommended_asking_price=outcome.equity_mid,
        recommended_multiple=None,
        triage_flags=flags,
        artifacts=None,
        methodology_used=methodology,
        dcf_weight=Decimal("1") if resolution.primary_method == "recovery_dcf" else Decimal("0"),
        multiples_weight=(
            Decimal("1")
            if resolution.primary_method in {"arr_multiple", "revenue_multiple"}
            else Decimal("0")
        ),
        methodology_selection_reason=(
            "Exclusive negative-EBITDA method ladder from negative_ebitda_resolution.v1."
        ),
        dcf_exclusion_reason=(
            None
            if resolution.primary_method == "recovery_dcf"
            else "Recovery DCF eligibility gates were not satisfied."
        ),
        confidence_level=resolution.confidence.upper(),
        confidence_score=confidence_score,
        financial_metrics=financial_metrics,
        dcf_results=dcf_results,
        multiples_results=None,
        earnings_basis=(
            "Revenue" if resolution.primary_method in {"arr_multiple", "revenue_multiple"} else None
        ),
        earnings_basis_rationale=(
            "A positive earnings multiple was not applied to negative EBITDA."
        ),
        earnings_basis_ledger=context.earnings_basis,
        value_driver_ledger=driver_ledger,
        holdings_consolidation=context.holdings_consolidation,
        valuation_summary=valuation_summary,
        key_value_drivers=[
            "Operating break-even",
            "Committed funding",
            "Revenue quality",
        ],
        risk_factors=resolution.blockers[:10],
        valuation_results=outcome.valuation_results,
        data_quality=data_quality,
        data_tier=data_tier,
        data_tier_rationale="Recovery confidence is bounded by evidence and verification.",
        publication_allowed=False,
        publication_blocked=True,
        report_readiness_state=report_readiness_state,
        defensibility_review_state=defensibility_review_state,
        valuation_method_label=method_label,
        confidence_label=f"{resolution.confidence.title()} recovery confidence",
        present_point_estimate=False,
        valuation_disclaimer=valuation_disclaimer,
        negative_ebitda_resolution=resolution,
        valuation_timeline=None,
        forward_value_cone=None,
    )


def _public_audit_enterprise_band(
    audit: Mapping[str, object] | None,
) -> tuple[Decimal, Decimal, Decimal] | None:
    if not isinstance(audit, Mapping):
        return None
    bridge = audit.get("value_bridge")
    if not isinstance(bridge, Mapping):
        return None
    band = bridge.get("enterprise_value")
    if not isinstance(band, Mapping):
        return None
    low = safe_decimal_or_zero(band.get("low"))
    mid = safe_decimal_or_zero(band.get("mid"))
    high = safe_decimal_or_zero(band.get("high"))
    if low <= 0 or low > mid or mid > high:
        return None
    return low, mid, high


def build_public_negative_ebitda_response(
    request: CalculateRequest,
    context: _InputContext,
    *,
    verified_titan_request_wire_commitment: Mapping[str, str] | None = None,
) -> CalculateResponse:
    """Resolve a public negative-EBITDA case without ever entering Recovery DCF.

    The private resolver is reused only for its governed revenue/asset method
    selection. Public requests carry no recovery schedules, and this wrapper
    strips every private-only output before returning a publication result.
    """

    base = build_negative_ebitda_response(
        request,
        context,
        verified_titan_request_wire_commitment=verified_titan_request_wire_commitment,
    )
    resolution = base.negative_ebitda_resolution
    assert resolution is not None
    input_fingerprint = _canonical_hash(
        {
            "schema_version": "public_negative_ebitda_input.v1",
            "entity": {
                "country_code": request.country_code,
                "registration_number": request.registration_number,
                "business_type_id": context.primary_business_type_id,
            },
            "current_year": request.current_year.model_dump(mode="json"),
            "historical_years": [
                row.model_dump(mode="json")
                for row in request.historical_years
                if row.is_forecast is not True
            ],
            "benchmark_contract": context.benchmark_contract,
        }
    )
    public_method = resolution.primary_method
    numeric_method_enabled = bool(
        public_recovery_benchmark_enabled()
        and public_method
        in {
            "arr_multiple",
            "revenue_multiple",
            "adjusted_nav",
            "orderly_liquidation",
        }
        and base.equity_value_low is not None
        and base.equity_value_mid is not None
        and base.equity_value_high is not None
    )
    if public_method in {"adjusted_nav", "orderly_liquidation"}:
        numeric_method_enabled = bool(
            numeric_method_enabled
            and request.current_year.total_assets is not None
            and request.current_year.total_liabilities is not None
            and request.current_year.total_debt is not None
            and request.current_year.total_equity is not None
        )

    audit: dict[str, object] | None = None
    enterprise_band: tuple[Decimal, Decimal, Decimal] | None = None
    if numeric_method_enabled:
        is_asset = public_method in {"adjusted_nav", "orderly_liquidation"}
        audit_failures: list[str] = []
        audit_failure_diagnostics: list[dict[str, object]] = []
        audit = build_public_valuation_audit(
            request=request,
            calculation_timestamp=base.calculation_timestamp,
            equity_value_low=base.equity_value_low,
            equity_value_mid=base.equity_value_mid,
            equity_value_high=base.equity_value_high,
            enterprise_value_low=None,
            enterprise_value_mid=None,
            enterprise_value_high=None,
            methodology_used="ASSET_BASED" if is_asset else "MULTIPLES",
            dcf_weight=Decimal("0"),
            multiples_weight=Decimal("0") if is_asset else Decimal("1"),
            dcf_exclusion_reason="public_negative_ebitda_recovery_dcf_forbidden",
            earnings_basis=None if is_asset else "REVENUE",
            recommended_multiple=None,
            multiple_build_up=(
                {} if is_asset else {"adjusted_earnings": request.current_year.revenue}
            ),
            confidence_level=base.confidence_level or "LOW",
            size_discount=Decimal("0"),
            liquidity_discount=Decimal("0"),
            country_adjustment=Decimal("0"),
            failure_reasons=audit_failures,
            failure_diagnostics=audit_failure_diagnostics,
        )
        if audit is None:
            numeric_method_enabled = False
            logger.warning(
                "public negative-EBITDA numeric audit failed closed",
                extra={
                    "valuation_id": request.valuation_id,
                    "failed_controls": sorted(set(audit_failures)),
                    "control_diagnostics": audit_failure_diagnostics,
                },
            )
        elif not is_asset:
            enterprise_band = _public_audit_enterprise_band(audit)
            if enterprise_band is None:
                numeric_method_enabled = False

    public_status = resolution.status if numeric_method_enabled else "no_going_concern_range"
    public_primary_method = public_method if numeric_method_enabled else None
    result_fingerprint = _canonical_hash(
        {
            "input_fingerprint": input_fingerprint,
            "status": public_status,
            "primary_method": public_primary_method,
            "equity": (
                [base.equity_value_low, base.equity_value_mid, base.equity_value_high]
                if numeric_method_enabled
                else None
            ),
            "enterprise": enterprise_band,
            "audit": audit if numeric_method_enabled else None,
        }
    )
    projection_resolution = resolution.model_copy(
        update={
            "status": public_status,
            "primary_method": public_primary_method,
            "method_family": (
                resolution.method_family
                if numeric_method_enabled
                else "insufficient_recovery_evidence"
            ),
        }
    )
    projection = build_public_recovery_projection(
        request,
        status=public_status,
        evaluated_at=resolution.evaluated_at,
        resolution=projection_resolution,
        input_fingerprint=input_fingerprint,
        result_fingerprint=result_fingerprint,
    )
    outcome = {
        "schema_version": "public_negative_ebitda_outcome.v1",
        "status": "available" if numeric_method_enabled else "blocked",
        "model_version": MODEL_VERSION,
        "input_fingerprint": input_fingerprint,
        "result_fingerprint": result_fingerprint,
        "latest_fiscal_year": request.current_year.year,
        "resolved_method": public_primary_method,
        "value_basis": audit.get("value_basis") if audit is not None else None,
        "negative_ebitda_recovery": projection.model_dump(mode="json"),
    }

    if not numeric_method_enabled:
        return base.model_copy(
            update={
                "valuation_run": None,
                "negative_ebitda_resolution": projection_resolution,
                "equity_value_low": None,
                "equity_value_mid": None,
                "equity_value_high": None,
                "enterprise_value_low": None,
                "enterprise_value_mid": None,
                "enterprise_value_high": None,
                "recommended_asking_price": None,
                "recommended_multiple": None,
                "methodology_used": "RECOVERY_ASSESSMENT",
                "dcf_weight": Decimal("0"),
                "multiples_weight": Decimal("0"),
                "publication_allowed": False,
                "publication_blocked": True,
                "public_valuation_audit": None,
                "public_method_resolution": outcome,
                "public_negative_ebitda_recovery": projection,
                "valuation_timeline": None,
                "forward_value_cone": None,
            }
        )

    enterprise_low = enterprise_band[0] if enterprise_band is not None else None
    enterprise_mid = enterprise_band[1] if enterprise_band is not None else None
    enterprise_high = enterprise_band[2] if enterprise_band is not None else None
    valuation_timeline = None
    if getattr(request, "include_valuation_timeline", False):
        # The public recovery contract deliberately carries only the latest
        # source-bound actual checkpoint. Re-entering the generic timeline
        # builder could synthesize modeled DCF checkpoints for earlier years.
        valuation_timeline = [
            ValuationTimelinePoint(
                fiscal_year=request.current_year.year,
                equity_low=base.equity_value_low,
                equity_mid=base.equity_value_mid,
                equity_high=base.equity_value_high,
                enterprise_value_low=enterprise_low,
                enterprise_value_mid=enterprise_mid,
                enterprise_value_high=enterprise_high,
                value_basis=("enterprise_value" if enterprise_band is not None else "equity_value"),
                currency=request.currency,
                methodology_used=base.methodology_used,
                confidence_level=base.confidence_level,
                confidence_score=base.confidence_score,
                audit_snapshot=audit,
                is_forecast=False,
            )
        ]
    return base.model_copy(
        update={
            "negative_ebitda_resolution": projection_resolution,
            "enterprise_value_low": enterprise_low,
            "enterprise_value_mid": enterprise_mid,
            "enterprise_value_high": enterprise_high,
            "publication_allowed": True,
            "publication_blocked": False,
            "public_valuation_audit": audit,
            "public_method_resolution": outcome,
            "public_negative_ebitda_recovery": projection,
            "valuation_timeline": valuation_timeline,
            "forward_value_cone": None,
        }
    )


def build_public_recovery_projection(
    request: CalculateRequest,
    *,
    status: str = "no_going_concern_range",
    evaluated_at: datetime | None = None,
    resolution: NegativeEbitdaResolution | None = None,
    input_fingerprint: str | None = None,
    result_fingerprint: str | None = None,
) -> PublicNegativeEbitdaRecoveryProjection:
    trajectory = (
        resolution.operating_trajectory
        if resolution is not None
        else build_operating_trajectory(request)
    )
    blockers = ["public_accounts_cannot_support_recovery_dcf"]
    required = [
        "private_operating_driver_schedules",
        "funding_plan",
        "titan_signed_case_with_reconciled_recovery_inputs",
    ]
    floor_methods: list[str] = []
    if (
        request.current_year.total_assets is not None
        and request.current_year.total_liabilities is not None
    ):
        floor_methods.append("adjusted_nav")
    return PublicNegativeEbitdaRecoveryProjection(
        status=status,
        entity_key=(
            f"{request.country_code.upper()}:{request.registration_number}"
            if request.registration_number
            else None
        ),
        latest_fiscal_year=request.current_year.year,
        input_fingerprint=input_fingerprint,
        result_fingerprint=result_fingerprint,
        operating_trajectory=trajectory,
        primary_method=resolution.primary_method if resolution is not None else None,
        eligible_floor_methods=(
            [
                method
                for method in ("adjusted_nav", "orderly_liquidation")
                if method == resolution.primary_method or method in resolution.cross_check_methods
            ]
            if resolution is not None
            else floor_methods
        ),
        blockers=(resolution.blockers if resolution is not None else blockers),
        required_evidence=(resolution.required_evidence if resolution is not None else required),
        evaluated_at=evaluated_at or datetime.now(timezone.utc),
    )


def build_normalized_positive_resolution(
    request: CalculateRequest,
    *,
    earnings_basis: Mapping[str, object],
    primary_method: str,
    cross_check_methods: list[str],
    valuation_results: Mapping[str, object],
    headline_equity: tuple[Decimal, Decimal, Decimal],
    headline_enterprise: tuple[Decimal, Decimal, Decimal] | None,
    evaluated_at: datetime,
) -> NegativeEbitdaResolution:
    canonical_reported = safe_decimal_or_zero(earnings_basis.get("current_reported_ebitda"))
    canonical_normalized = safe_decimal_or_zero(earnings_basis.get("current_normalized_ebitda"))
    raw_rows = earnings_basis.get("rows")
    rows = (
        [dict(row) for row in raw_rows if isinstance(row, Mapping)]
        if isinstance(raw_rows, list)
        else []
    )
    applied_rows = [
        dict(adjustment)
        for row in rows
        for adjustment in (
            row.get("applied_adjustments")
            if isinstance(row.get("applied_adjustments"), list)
            else []
        )
        if isinstance(adjustment, Mapping)
    ]
    adjustment_text = " ".join(
        str(value).lower()
        for row in applied_rows
        for value in (row.get("category"), row.get("field"), row.get("label"))
        if value is not None
    )
    if "owner" in adjustment_text or "management_compensation" in adjustment_text:
        primary_cause = "owner_compensation_distortion"
    elif any(token in adjustment_text for token in ("restructur", "one_off", "one-off")):
        primary_cause = "one_off_restructuring"
    elif any(token in adjustment_text for token in ("product", "development", "r&d")):
        primary_cause = "product_development_investment"
    elif any(token in adjustment_text for token in ("investment", "growth")):
        primary_cause = "temporary_investment"
    else:
        primary_cause = "insufficient_evidence"

    candidate_method_audit: dict[str, dict[str, object]] = {}
    for method_key, method in valuation_results.items():
        if method is None:
            continue
        available = bool(getattr(method, "available", False))
        candidate_method_audit[str(method_key)] = {
            "available": available,
            "selected": str(method_key)
            == ("sde_multiple" if primary_method == "sde" else "ebitda_multiple"),
            "value_basis": getattr(method, "value_basis", "equity_value"),
            "equity_value_low": getattr(method, "equity_value_low", None)
            or getattr(method, "value_low", None),
            "equity_value_mid": getattr(method, "equity_value", None)
            or getattr(method, "value", None),
            "equity_value_high": getattr(method, "equity_value_high", None)
            or getattr(method, "value_high", None),
            "enterprise_value_low": getattr(method, "enterprise_value_low", None),
            "enterprise_value_mid": getattr(method, "enterprise_value", None),
            "enterprise_value_high": getattr(method, "enterprise_value_high", None),
            "unavailable_reason": getattr(method, "unavailable_reason", None),
        }

    current_cash = request.current_year.cash
    current_debt = request.current_year.total_debt
    equity_bridge = {
        "enterprise_value": headline_enterprise[1] if headline_enterprise else None,
        "current_cash": current_cash,
        "current_debt": current_debt,
        "current_equity_value": headline_equity[1],
        "ownership_percentage": Decimal(str(request.shares_for_sale or 100)),
        "funding_deducted_from_enterprise_value": False,
        "basis": "normalized_earnings_current_shareholder_indication",
        "shareholder_equity_status": "available",
        "qualification": (
            "current_cash_debt_bridge_complete"
            if current_cash is not None and current_debt is not None
            else "method_result_equity_basis"
        ),
    }
    resolution = NegativeEbitdaResolution(
        status="normalized_positive",
        reported_ebitda=canonical_reported,
        normalized_ebitda=canonical_normalized,
        operating_trajectory=build_operating_trajectory(request, earnings_basis),
        primary_method="sde" if primary_method == "sde" else "normalized_ebitda",
        method_family="normalized_earnings",
        primary_cause=primary_cause,
        cross_check_methods=cross_check_methods,
        headline_equity_value_low=headline_equity[0],
        headline_equity_value_mid=headline_equity[1],
        headline_equity_value_high=headline_equity[2],
        headline_enterprise_value_low=(headline_enterprise[0] if headline_enterprise else None),
        headline_enterprise_value_mid=(headline_enterprise[1] if headline_enterprise else None),
        headline_enterprise_value_high=(headline_enterprise[2] if headline_enterprise else None),
        confidence="medium",
        cause_codes=[
            "reported_negative_normalized_positive",
            "evidence_backed_normalization_bridge",
        ],
        normalization_bridge={
            "reported_ebitda": canonical_reported,
            "accepted_adjustments": canonical_normalized - canonical_reported,
            "normalized_ebitda": canonical_normalized,
            "basis": "signed_valuation_case_decisions",
            "rows": rows,
            "applied_adjustments": applied_rows,
        },
        break_even_bridge={
            "state": "already_positive_after_accepted_normalization",
            "reported_ebitda": canonical_reported,
            "accepted_adjustments": canonical_normalized - canonical_reported,
            "normalized_ebitda": canonical_normalized,
        },
        equity_bridge=equity_bridge,
        blockers=[],
        required_evidence=[],
        value_building_actions=[],
        scenario_results=[],
        candidate_method_audit=candidate_method_audit,
        evaluated_at=evaluated_at,
        input_snapshot_hash=_canonical_hash(
            {
                "current_year": request.current_year.model_dump(mode="json"),
                "historical_years": [
                    row.model_dump(mode="json") for row in request.historical_years
                ],
                "earnings_basis": dict(earnings_basis),
            }
        ),
        resolution_snapshot_hash="0" * 64,
    )
    return resolution.model_copy(
        update={
            "resolution_snapshot_hash": _canonical_hash(
                resolution.model_dump(mode="json", exclude={"resolution_snapshot_hash"})
            )
        }
    )
