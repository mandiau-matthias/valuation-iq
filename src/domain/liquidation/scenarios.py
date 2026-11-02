"""Scenario computation — the orchestration above ``AssetBasedEngine``.

Wraps the dormant ``calculate_liquidation_value(orderly=True/False)``
branches into a single pure function that returns both scenarios as
typed payloads. No I/O, no logging — pure transformation so the omni
wrapper (and tests) can call it without standing up Pydantic models
or the engine logger.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Mapping, Optional

from src.domain.asset_based_engine import AssetBasedEngine, AssetBasedResult
from src.domain.asset_based_support import (
    derive_total_liabilities,
    normalize_business_model,
    to_decimal_or_none,
)
from src.domain.models import FinancialData, YearData
from src.utils.fiscal_year import get_current_filing_year

from .asset_schedule import AssetSchedule, build_asset_schedule
from .distress_probability import DistressAssessment, assess_distress_probability
from .factors import LIQUIDATION_SOURCES
from .payloads import LiquidationScenario, LiquidationScenarios
from .premise import PremiseDecision, PremiseOfValue, select_premise
from .scenario_artifacts import (
    compute_reduction_artifacts,
    compute_reporting_artifacts,
    compute_risk_artifacts,
    compute_waterfall_artifacts,
)


@dataclass(frozen=True)
class _ScenarioInputBundle:
    multiplier: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    financial_data: FinancialData


@dataclass(frozen=True)
class _PremiseArtifacts:
    distress: DistressAssessment
    asset_schedule: AssetSchedule
    premise: PremiseDecision
    going_concern_value: Optional[Decimal]
    expected_equity_value: Optional[Decimal]


def _scenario_from_result(
    result: AssetBasedResult, *, ownership_multiplier: Decimal
) -> LiquidationScenario:
    """Translate an ``AssetBasedResult`` into our typed scenario payload.

    Recovers ``would_be_insolvent`` from pre-clamp adjusted assets vs.
    adjusted liabilities — the engine clamps the displayed equity at 0,
    so this flag is what surfaces the downside signal even when the
    rendered number is also 0.
    """
    equity = (result.net_asset_value * ownership_multiplier).quantize(Decimal("0.01"))
    unclamped = (result.total_assets_adjusted - result.total_liabilities_adjusted).quantize(
        Decimal("0.01")
    )
    return LiquidationScenario(
        method=result.method.value,
        equity_value=equity,
        total_assets_book=result.total_assets_book,
        total_assets_adjusted=result.total_assets_adjusted,
        total_liabilities_book=result.total_liabilities_book,
        total_liabilities_adjusted=result.total_liabilities_adjusted,
        net_asset_value_unclamped=unclamped,
        value_low=(result.value_low * ownership_multiplier).quantize(Decimal("0.01")),
        value_high=(result.value_high * ownership_multiplier).quantize(Decimal("0.01")),
        asset_adjustments=[a.to_dict() for a in result.asset_adjustments],
        would_be_insolvent=result.total_liabilities_adjusted > result.total_assets_adjusted,
        warnings=list(result.warnings),
        rationale=result.rationale,
    )


def _distress_observation(value: object) -> Decimal | None:
    """Keep a supplied invalid observation distinct from an absent one."""
    if value is None:
        return None
    parsed = to_decimal_or_none(value)
    return parsed if parsed is not None else Decimal("NaN")


def _resolve_distress(
    *,
    balance_sheet: Mapping[str, object],
    total_assets: Decimal,
    total_liabilities: Decimal,
    ebit: Optional[object],
    revenue: Optional[object],
    ebitda: Optional[object],
) -> DistressAssessment:
    """Use reported EBIT, or EBITDA less explicitly observed D&A.

    Missing D&A is unknown, even when one of the components is supplied.
    Never treat EBITDA as EBIT by silently assuming zero non-cash expense.
    """
    ebit_decimal = _distress_observation(ebit)
    if ebit is None:
        ebitda_decimal = _distress_observation(ebitda)
        depreciation = _distress_observation(balance_sheet.get("depreciation"))
        amortization = _distress_observation(balance_sheet.get("amortization"))
        if (
            ebitda_decimal is not None
            and depreciation is not None
            and depreciation.is_finite()
            and depreciation >= 0
            and amortization is not None
            and amortization.is_finite()
            and amortization >= 0
        ):
            ebit_decimal = ebitda_decimal - depreciation - amortization

    return assess_distress_probability(
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        current_assets=_distress_observation(balance_sheet.get("current_assets")),
        current_liabilities=_distress_observation(balance_sheet.get("current_liabilities")),
        retained_earnings=_distress_observation(balance_sheet.get("retained_earnings")),
        ebit=ebit_decimal,
        total_equity=_distress_observation(balance_sheet.get("total_equity")),
    )


def _build_input_bundle(
    *,
    company_name: str,
    industry: str,
    business_model: str,
    founding_year: Optional[int],
    reporting_year: Optional[int],
    revenue: object,
    ebitda: object,
    ownership_multiplier: Decimal,
    country_code: str,
    balance_sheet: dict[str, object],
) -> _ScenarioInputBundle:
    multiplier = ownership_multiplier if ownership_multiplier > 0 else Decimal("1")
    reporting = reporting_year if reporting_year is not None else get_current_filing_year()

    total_assets = to_decimal_or_none(balance_sheet.get("total_assets"))
    if total_assets is None:
        raise ValueError("compute_liquidation_scenarios: total_assets must be > 0")
    if total_assets <= 0:
        raise ValueError("compute_liquidation_scenarios: total_assets must be > 0")

    total_liabilities = derive_total_liabilities(balance_sheet, total_assets)
    if total_liabilities is None:
        raise ValueError("compute_liquidation_scenarios: total_liabilities unresolvable")

    current_year = YearData(
        year=reporting,
        revenue=_decimal_or_zero(revenue),
        ebitda=_decimal_or_zero(ebitda),
        total_assets=total_assets,
        current_assets=to_decimal_or_none(balance_sheet.get("current_assets")),
        cash=to_decimal_or_none(balance_sheet.get("cash")),
        accounts_receivable=to_decimal_or_none(balance_sheet.get("accounts_receivable")),
        inventory=to_decimal_or_none(balance_sheet.get("inventory")),
        total_liabilities=total_liabilities,
        current_liabilities=to_decimal_or_none(balance_sheet.get("current_liabilities")),
        total_debt=to_decimal_or_none(balance_sheet.get("total_debt")),
        total_equity=to_decimal_or_none(balance_sheet.get("total_equity")),
    )

    financial_data = FinancialData(
        company_id=f"liquidation-{_default_text(company_name, 'company')}",
        company_name=_default_text(company_name, "Unknown Company"),
        country_code=country_code,
        industry=_default_text(industry, "other"),
        business_model=normalize_business_model(business_model),
        founding_year=founding_year if founding_year is not None else current_year.year,
        historical_years=[current_year],
        current_year=current_year,
        number_of_owners=1,
        has_complete_financials=True,
    )

    return _ScenarioInputBundle(
        multiplier=multiplier,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        financial_data=financial_data,
    )


def _compute_engine_scenarios(
    *,
    financial_data: FinancialData,
    country_code: str,
    industry: str,
    multiplier: Decimal,
) -> tuple[LiquidationScenario, LiquidationScenario]:
    scenario_industry = _default_text(industry, "other")
    engine = AssetBasedEngine(financial_data, country_code=country_code)
    orderly_result = engine.calculate_liquidation_value(
        orderly=True,
        industry=scenario_industry,
    )
    forced_result = engine.calculate_liquidation_value(
        orderly=False,
        industry=scenario_industry,
    )
    return (
        _scenario_from_result(orderly_result, ownership_multiplier=multiplier),
        _scenario_from_result(forced_result, ownership_multiplier=multiplier),
    )


def _compute_premise_artifacts(
    *,
    balance_sheet: dict[str, object],
    total_assets: Decimal,
    total_liabilities: Decimal,
    revenue: object,
    ebitda: object,
    orderly_scenario: LiquidationScenario,
    asset_overrides: Optional[Mapping[str, Mapping[str, object]]],
    owner_premise_override: Optional[PremiseOfValue],
    going_concern_value_override: Optional[Decimal],
    multiplier: Decimal,
) -> _PremiseArtifacts:
    distress = _resolve_distress(
        balance_sheet=balance_sheet,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        ebit=balance_sheet.get("ebit"),
        revenue=revenue,
        ebitda=ebitda,
    )
    asset_schedule = build_asset_schedule(
        balance_sheet=balance_sheet,
        asset_overrides=asset_overrides,
    )
    premise = select_premise(
        distress=distress,
        is_insolvent=orderly_scenario.would_be_insolvent,
        owner_override=owner_premise_override,
    )
    going_concern_value = _resolve_going_concern_value(
        override=going_concern_value_override,
    )

    return _PremiseArtifacts(
        distress=distress,
        asset_schedule=asset_schedule,
        premise=premise,
        going_concern_value=going_concern_value,
        expected_equity_value=None,
    )


def _resolve_going_concern_value(
    *,
    override: Optional[Decimal],
) -> Optional[Decimal]:
    # Caller-supplied comparison must already be equity for the same interest.
    # There is no evidence supporting the former 5x EBITDA minus all liabilities proxy.
    value = to_decimal_or_none(override)
    if value is None or value < 0 or value > Decimal("1e15"):
        return None
    return value


def _decimal_or_zero(value: object) -> Decimal:
    parsed = to_decimal_or_none(value)
    return parsed if parsed is not None else Decimal("0")


def _default_text(value: Optional[str], default: str) -> str:
    return value if value else default


def compute_liquidation_scenarios(
    *,
    company_name: str,
    industry: str,
    business_model: str,
    founding_year: Optional[int],
    reporting_year: Optional[int],
    revenue: object,
    ebitda: object,
    ownership_multiplier: Decimal,
    country_code: str,
    balance_sheet: dict[str, object],
    asset_overrides: Optional[Mapping[str, Mapping[str, object]]] = None,
    owner_premise_override: Optional[PremiseOfValue] = None,
    going_concern_value_override: Optional[Decimal] = None,
    # ----- Phase 2 inputs -----------------------------------------
    liability_buckets: Optional[Mapping[str, object]] = None,
    paid_up_capital: Optional[object] = None,
    tax_context: Optional[Mapping[str, object]] = None,
    taxable_reserves: Optional[object] = None,
    realised_capital_gains: Optional[object] = None,
    deferred_tax_liabilities: Optional[object] = None,
    headcount: int = 0,
    monthly_rent: Optional[object] = None,
    runway_months_orderly: Optional[int] = None,
    runway_months_forced: Optional[int] = None,
    wind_down_overrides: Optional[Mapping[str, object]] = None,
    # ----- Phase 3 inputs -----------------------------------------
    distress_wacc_orderly: Optional[object] = None,
    distress_wacc_forced: Optional[object] = None,
    enable_sensitivity: bool = True,
    sensitivity_sample_count: int = 256,
    nace_code: Optional[str] = None,
    multiples_value_override: Optional[Decimal] = None,
    adjusted_nav_override: Optional[Decimal] = None,
    # ----- Phase 4 inputs -----------------------------------------
    enable_disclosure: bool = True,
    extra_disclosure_assumptions: Optional[List[str]] = None,
    # ----- Replacement-cost (M&A buyer ceiling) ------------------
    enable_replacement_cost: bool = True,
    identifiable_intangibles_uplift_pct: Optional[Decimal] = None,
    # ----- Statement of Affairs (Section 0) ----------------------
    enable_statement_of_affairs: bool = True,
    # ----- Audit trail (digitalised M&A reproducibility) ---------
    enable_audit_trail: bool = True,
    effective_date: Optional[str] = None,  # ISO YYYY-MM-DD as-of date
    audit_run_id_override: Optional[str] = None,  # for deterministic tests
    audit_computed_at_override: Optional[str] = None,
    # ----- Phase 5: lawyer/accountant-grade reductions ------------
    enable_sufficiency_memo: bool = True,
    enable_creditor_letters: bool = True,
    enable_strategic_buyer_scenarios: bool = True,
) -> LiquidationScenarios:
    """Compute orderly + forced scenarios + premise + distress + schedule.

    The caller is responsible for input validation (balance-sheet
    presence, total_assets > 0, resolvable total_liabilities).

    Phase 1 additions over the prior contract:
    - ``asset_overrides``: per-asset-class manual override dict from
      Venus (book/adjusted/factor/disposal-month per class).
    - ``owner_premise_override``: explicit premise pinned by owner or
      advisor — disclosed as a scenario assumption requiring review.
    - ``going_concern_value_override``: optional caller-supplied equity
      comparison for the same ownership interest, date and currency.
      No automatic earnings proxy or probability-weighted value is produced.
      A bare comparison amount does not establish valuation provenance.
    """
    # Bind policy admission and audit metadata to one valuation date.
    effective_date = date.today().isoformat() if effective_date is None else effective_date
    inputs = _build_input_bundle(
        company_name=company_name,
        industry=industry,
        business_model=business_model,
        founding_year=founding_year,
        reporting_year=reporting_year,
        revenue=revenue,
        ebitda=ebitda,
        ownership_multiplier=ownership_multiplier,
        country_code=country_code,
        balance_sheet=balance_sheet,
    )
    orderly_scenario, forced_scenario = _compute_engine_scenarios(
        financial_data=inputs.financial_data,
        country_code=country_code,
        industry=industry,
        multiplier=inputs.multiplier,
    )
    premise_artifacts = _compute_premise_artifacts(
        balance_sheet=balance_sheet,
        total_assets=inputs.total_assets,
        total_liabilities=inputs.total_liabilities,
        revenue=revenue,
        ebitda=ebitda,
        orderly_scenario=orderly_scenario,
        asset_overrides=asset_overrides,
        owner_premise_override=owner_premise_override,
        going_concern_value_override=going_concern_value_override,
        multiplier=inputs.multiplier,
    )

    waterfall = compute_waterfall_artifacts(
        country_code=country_code,
        ownership_multiplier=inputs.multiplier,
        effective_date=effective_date,
        orderly_scenario=orderly_scenario,
        forced_scenario=forced_scenario,
        total_liabilities=inputs.total_liabilities,
        liability_buckets=liability_buckets,
        paid_up_capital=paid_up_capital,
        tax_context=tax_context,
        taxable_reserves=taxable_reserves,
        realised_capital_gains=realised_capital_gains,
        deferred_tax_liabilities=deferred_tax_liabilities,
        headcount=headcount,
        monthly_rent=monthly_rent,
        runway_months_orderly=runway_months_orderly,
        runway_months_forced=runway_months_forced,
        wind_down_overrides=wind_down_overrides,
    )

    risk = compute_risk_artifacts(
        asset_schedule=premise_artifacts.asset_schedule,
        orderly_scenario=orderly_scenario,
        total_liabilities=inputs.total_liabilities,
        waterfall=waterfall,
        distress_wacc_orderly=distress_wacc_orderly,
        distress_wacc_forced=distress_wacc_forced,
        enable_sensitivity=enable_sensitivity,
        sensitivity_sample_count=sensitivity_sample_count,
        adjusted_nav_override=adjusted_nav_override,
        going_concern_value_override=premise_artifacts.going_concern_value,
        multiples_value_override=multiples_value_override,
    )

    reporting = compute_reporting_artifacts(
        enable_disclosure=enable_disclosure,
        premise=premise_artifacts.premise,
        extra_disclosure_assumptions=extra_disclosure_assumptions,
        enable_replacement_cost=enable_replacement_cost,
        asset_schedule=premise_artifacts.asset_schedule,
        identifiable_intangibles_uplift_pct=identifiable_intangibles_uplift_pct,
        enable_statement_of_affairs=enable_statement_of_affairs,
        total_assets=inputs.total_assets,
        total_liabilities=inputs.total_liabilities,
        orderly_scenario=orderly_scenario,
        forced_scenario=forced_scenario,
        waterfall=waterfall,
        going_concern_value=premise_artifacts.going_concern_value,
        enable_audit_trail=enable_audit_trail,
        audit_payload=_build_audit_payload(
            revenue=revenue,
            ebitda=ebitda,
            effective_date=effective_date,
            company_name=company_name,
            industry=industry,
            business_model=business_model,
            founding_year=founding_year,
            reporting_year=inputs.financial_data.current_year.year,
            country_code=country_code,
            ownership_multiplier=ownership_multiplier,
            balance_sheet=balance_sheet,
            asset_overrides=asset_overrides,
            owner_premise_override=owner_premise_override,
            going_concern_value_override=going_concern_value_override,
            liability_buckets=liability_buckets,
            paid_up_capital=paid_up_capital,
            tax_context=tax_context,
            taxable_reserves=taxable_reserves,
            realised_capital_gains=realised_capital_gains,
            deferred_tax_liabilities=deferred_tax_liabilities,
            headcount=headcount,
            monthly_rent=monthly_rent,
            runway_months_orderly=runway_months_orderly,
            runway_months_forced=runway_months_forced,
            wind_down_overrides=wind_down_overrides,
            distress_wacc_orderly=distress_wacc_orderly,
            distress_wacc_forced=distress_wacc_forced,
            nace_code=nace_code,
            multiples_value_override=multiples_value_override,
            adjusted_nav_override=adjusted_nav_override,
            identifiable_intangibles_uplift_pct=identifiable_intangibles_uplift_pct,
        ),
        effective_date=effective_date,
        audit_run_id_override=audit_run_id_override,
        audit_computed_at_override=audit_computed_at_override,
    )

    reductions = compute_reduction_artifacts(
        enable_sufficiency_memo=enable_sufficiency_memo,
        enable_creditor_letters=enable_creditor_letters,
        enable_strategic_buyer_scenarios=enable_strategic_buyer_scenarios,
        waterfall=waterfall,
        going_concern_value=premise_artifacts.going_concern_value,
        replacement_cost=reporting.replacement_cost,
    )

    return LiquidationScenarios(
        orderly=orderly_scenario,
        forced=forced_scenario,
        book_equity=(inputs.total_assets - inputs.total_liabilities).quantize(Decimal("0.01")),
        ownership_multiplier=inputs.multiplier,
        sources=LIQUIDATION_SOURCES,
        premise=premise_artifacts.premise,
        distress=premise_artifacts.distress,
        asset_schedule=premise_artifacts.asset_schedule,
        expected_equity_value=premise_artifacts.expected_equity_value,
        going_concern_proxy_equity=premise_artifacts.going_concern_value,
        # Phase 2
        priority_cascade_orderly=waterfall.cascade_orderly,
        priority_cascade_forced=waterfall.cascade_forced,
        tax_leakage_orderly=waterfall.tax_orderly,
        tax_leakage_forced=waterfall.tax_forced,
        wind_down_orderly=waterfall.wind_down_orderly,
        wind_down_forced=waterfall.wind_down_forced,
        # Phase 3
        disposal_schedule_pv_orderly=risk.disposal_schedule_pv_orderly,
        disposal_schedule_pv_forced=risk.disposal_schedule_pv_forced,
        sensitivity=risk.sensitivity,
        premise_reconciliation=risk.premise_reconciliation,
        # Phase 4
        disclosure=reporting.disclosure,
        net_equity_to_shareholders_orderly=waterfall.net_orderly,
        net_equity_to_shareholders_forced=waterfall.net_forced,
        # Phase 4+ — M&A buyer ceiling, EY-cover, audit trail
        replacement_cost=reporting.replacement_cost,
        statement_of_affairs=reporting.statement_of_affairs,
        audit_trail=reporting.audit_trail,
        # Phase 5 — Lawyer / accountant grade reductions
        sufficiency_memo_orderly=reductions.sufficiency_orderly,
        sufficiency_memo_forced=reductions.sufficiency_forced,
        creditor_letters_orderly=reductions.creditor_letters_orderly,
        creditor_letters_forced=reductions.creditor_letters_forced,
        strategic_buyer_scenarios=reductions.strategic_buyer_scenarios,
    )


def _build_audit_payload(
    *,
    revenue: object,
    ebitda: object,
    effective_date: str,
    company_name: str,
    industry: str,
    business_model: str,
    founding_year: Optional[int],
    reporting_year: Optional[int],
    country_code: str,
    ownership_multiplier: Decimal,
    balance_sheet: dict[str, object],
    asset_overrides: Optional[Mapping[str, Mapping[str, object]]],
    owner_premise_override: Optional[PremiseOfValue],
    going_concern_value_override: Optional[Decimal],
    liability_buckets: Optional[Mapping[str, object]],
    paid_up_capital: Optional[object],
    tax_context: Optional[Mapping[str, object]],
    taxable_reserves: Optional[object],
    realised_capital_gains: Optional[object],
    deferred_tax_liabilities: Optional[object],
    headcount: int,
    monthly_rent: Optional[object],
    runway_months_orderly: Optional[int],
    runway_months_forced: Optional[int],
    wind_down_overrides: Optional[Mapping[str, object]],
    distress_wacc_orderly: Optional[object],
    distress_wacc_forced: Optional[object],
    nace_code: Optional[str],
    multiples_value_override: Optional[Decimal],
    adjusted_nav_override: Optional[Decimal],
    identifiable_intangibles_uplift_pct: Optional[Decimal],
) -> dict[str, object]:
    """Canonical audit-trail payload hashed by ``build_audit_trail``."""

    return {
        "revenue": revenue,
        "ebitda": ebitda,
        "effective_date": effective_date,
        "company_name": company_name,
        "industry": industry,
        "business_model": business_model,
        "founding_year": founding_year,
        "reporting_year": reporting_year,
        "country_code": country_code,
        "ownership_multiplier": ownership_multiplier,
        "balance_sheet": balance_sheet,
        "asset_overrides": dict(asset_overrides) if asset_overrides else None,
        "owner_premise_override": (
            owner_premise_override.value if owner_premise_override is not None else None
        ),
        "going_concern_value_override": going_concern_value_override,
        "liability_buckets": dict(liability_buckets) if liability_buckets else None,
        "paid_up_capital": paid_up_capital,
        "tax_context": dict(tax_context) if isinstance(tax_context, Mapping) else tax_context,
        "taxable_reserves": taxable_reserves,
        "realised_capital_gains": realised_capital_gains,
        "deferred_tax_liabilities": deferred_tax_liabilities,
        "headcount": headcount,
        "monthly_rent": monthly_rent,
        "runway_months_orderly": runway_months_orderly,
        "runway_months_forced": runway_months_forced,
        "wind_down_overrides": (dict(wind_down_overrides) if wind_down_overrides else None),
        "distress_wacc_orderly": distress_wacc_orderly,
        "distress_wacc_forced": distress_wacc_forced,
        "nace_code": nace_code,
        "multiples_value_override": multiples_value_override,
        "adjusted_nav_override": adjusted_nav_override,
        "identifiable_intangibles_uplift_pct": identifiable_intangibles_uplift_pct,
    }
