"""Liquidation Analysis method wrapper — thin omni-calc adapter.

All math + factors live in ``src.domain.liquidation``. This module's only
job is the contract translation: validate inputs, dispatch to the
liquidation subpackage, package the result as a ``MethodResult`` for
``omni_calc_coordinator``.

Semantics
---------
- ``MethodResult.value`` returns the orderly liquidation equity (the
  realistic wind-down number). Forced liquidation lives in
  ``details.forced``.
- This is a downside lens, not a going-concern equity estimate.
  ``calculate_weighted_average`` only blends user-weighted methods, so
  liquidation never auto-pollutes the headline blend.
"""

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Optional

from src.api.schemas.method_details import build_liquidation_analysis_details
from src.api.schemas.stateless_api import MethodResult
from src.domain.asset_based_support import derive_total_liabilities, to_decimal_or_none
from src.domain.financial_arithmetic import decimal_number, money
from src.domain.liquidation import (
    LIQUIDATION_LABEL,
    LiquidationUnavailableReason,
    PremiseOfValue,
    compute_liquidation_scenarios,
)

from .adjusted_nav import _reconciled_asset_components


def _unavailable(
    *,
    reason: str,
    code: LiquidationUnavailableReason,
    missing_fields: Optional[list[str]] = None,
    remediation: Optional[str] = None,
) -> MethodResult:
    return MethodResult(
        value=None,
        method_key="liquidation_analysis",
        label=LIQUIDATION_LABEL,
        available=False,
        unavailable_reason=reason,
        details={
            "unavailable_code": code.value,
            "missing_fields": list(missing_fields or []),
            "remediation": remediation,
        },
    )


def calculate_liquidation_result(
    *,
    company_name: str,
    industry: str,
    business_model: str,
    founding_year: Optional[int],
    reporting_year: Optional[int],
    revenue: float,
    ebitda: float,
    ownership_multiplier: Decimal,
    country_code: str,
    balance_sheet: Optional[Mapping[str, object]],
    # ----- Phase 1 ------------------------------------------------
    asset_overrides: Optional[Mapping[str, Mapping[str, object]]] = None,
    owner_premise_override: Optional[PremiseOfValue] = None,
    going_concern_value_override: Optional[Decimal] = None,
    # ----- Phase 2 ------------------------------------------------
    liability_buckets: Optional[Mapping[str, object]] = None,
    paid_up_capital: object | None = None,
    tax_context: Mapping[str, object] | None = None,
    taxable_reserves: object | None = None,
    realised_capital_gains: object | None = None,
    deferred_tax_liabilities: object | None = None,
    headcount: int = 0,
    monthly_rent: object | None = None,
    runway_months_orderly: Optional[int] = None,
    runway_months_forced: Optional[int] = None,
    wind_down_overrides: Optional[Mapping[str, object]] = None,
    # ----- Phase 3 ------------------------------------------------
    distress_wacc_orderly: object | None = None,
    distress_wacc_forced: object | None = None,
    enable_sensitivity: bool = True,
    sensitivity_sample_count: int = 256,
    nace_code: Optional[str] = None,
    multiples_value_override: Optional[Decimal] = None,
    adjusted_nav_override: Optional[Decimal] = None,
    # ----- Phase 4 ------------------------------------------------
    enable_disclosure: bool = True,
    extra_disclosure_assumptions: Optional[Sequence[str]] = None,
    # ----- Replacement cost / SOA / audit trail (M&A artifact) ----
    enable_replacement_cost: bool = True,
    identifiable_intangibles_uplift_pct: Optional[Decimal] = None,
    enable_statement_of_affairs: bool = True,
    enable_audit_trail: bool = True,
    effective_date: Optional[str] = None,
    audit_run_id_override: Optional[str] = None,
    audit_computed_at_override: Optional[str] = None,
    # ----- Phase 5 lawyer/accountant outputs ----------------------
    enable_sufficiency_memo: bool = True,
    enable_creditor_letters: bool = True,
    enable_strategic_buyer_scenarios: bool = True,
) -> MethodResult:
    """Compute orderly + forced liquidation values as a MethodResult.

    Input contract mirrors ``calculate_adjusted_nav_result`` — both
    methods need the same balance-sheet shape.

    Phase 1 (all optional, backwards-compatible):
    - ``asset_overrides`` / ``owner_premise_override`` /
      ``going_concern_value_override``.

    Phase 2 — insolvency cascade + conditional tax + wind-down:
    - ``liability_buckets`` per-tier explicit allocation;
      ``tax_context`` for dated advisor-input cash-tax scenarios, plus
      BE fiscal ``paid_up_capital``. Legacy gains/DTL/reserves alone
      do not establish cash tax or an exemption; ``headcount`` /
      ``monthly_rent`` / ``runway_months_*`` / ``wind_down_overrides``
      for the bottom-up wind-down build-up.

    Phase 3 — PV-discount + sensitivity + premise reconciliation:
    - ``distress_wacc_orderly`` / ``distress_wacc_forced`` override
      the default Damodaran SME range (15% / 25%).
    - ``enable_sensitivity`` / ``sensitivity_sample_count`` control
      the Latin-hypercube tornado.
    - ``nace_code`` — feeds the Delphi NACE recovery-factor cohort.
    - ``multiples_value_override`` / ``adjusted_nav_override`` give
      the premise reconciliation real going-concern figures.

    Phase 4 — Disclosure block:
    - ``enable_disclosure`` toggles the IVS 104 / USPAP / IFRS 13
      structured Section 10.
    - ``extra_disclosure_assumptions`` lets the appraiser append
      engagement-specific assumptions to the standard set.
    """
    try:
        ownership = decimal_number(ownership_multiplier, "ownership multiplier")
        if not Decimal(0) <= ownership <= Decimal(1):
            raise ValueError("Ownership multiplier must fall between zero and one.")
        asset_assumptions: list[dict[str, object]] = []
        if balance_sheet is not None:
            balance_sheet, asset_assumptions = _reconciled_asset_components(balance_sheet)
            for field in ("total_assets", "total_liabilities", "total_equity", "total_debt"):
                if balance_sheet.get(field) is not None:
                    decimal_number(balance_sheet[field], field)
    except ValueError as exc:
        return MethodResult(
            value=None,
            method_key="liquidation_analysis",
            label=LIQUIDATION_LABEL,
            available=False,
            unavailable_reason=str(exc),
        )

    if not balance_sheet:
        return _unavailable(
            reason="Balansgegevens vereist — totale activa ontbreken.",
            code=LiquidationUnavailableReason.BALANCE_SHEET_MISSING,
            missing_fields=[
                "current_year_data.total_assets",
                "current_year_data.total_liabilities",
            ],
            remediation=(
                "Vul minstens totale activa en passiva in vanuit de "
                "recentste balans om de liquidatiewaarde te berekenen."
            ),
        )

    balance_sheet_payload = dict(balance_sheet)

    total_assets = to_decimal_or_none(balance_sheet_payload.get("total_assets"))
    if total_assets is None or total_assets <= 0:
        return _unavailable(
            reason="Balansgegevens vereist — totale activa moeten positief zijn.",
            code=LiquidationUnavailableReason.TOTAL_ASSETS_NON_POSITIVE,
            missing_fields=["current_year_data.total_assets"],
            remediation="Corrigeer totale activa naar een positief bedrag uit de balans.",
        )

    if derive_total_liabilities(balance_sheet_payload, total_assets) is None:
        return _unavailable(
            reason="Balansgegevens vereist — totale verplichtingen of eigen vermogen ontbreekt.",
            code=LiquidationUnavailableReason.TOTAL_LIABILITIES_UNRESOLVABLE,
            missing_fields=["current_year_data.total_liabilities|current_year_data.total_equity"],
            remediation=(
                "Vul totale verplichtingen of volledig eigen vermogen in zodat "
                "totale passiva kan worden afgeleid."
            ),
        )

    with localcontext() as context:
        context.rounding = ROUND_HALF_EVEN
        scenarios = compute_liquidation_scenarios(
            company_name=company_name,
            industry=industry,
            business_model=business_model,
            founding_year=founding_year,
            reporting_year=reporting_year,
            revenue=revenue,
            ebitda=ebitda,
            ownership_multiplier=ownership if ownership != 0 else Decimal(1),
            country_code=country_code,
            balance_sheet=balance_sheet_payload,
            # Phase 1
            asset_overrides=asset_overrides,
            owner_premise_override=owner_premise_override,
            going_concern_value_override=going_concern_value_override,
            # Phase 2
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
            # Phase 3
            distress_wacc_orderly=distress_wacc_orderly,
            distress_wacc_forced=distress_wacc_forced,
            enable_sensitivity=enable_sensitivity,
            sensitivity_sample_count=sensitivity_sample_count,
            nace_code=nace_code,
            multiples_value_override=multiples_value_override,
            adjusted_nav_override=adjusted_nav_override,
            # Phase 4
            enable_disclosure=enable_disclosure,
            extra_disclosure_assumptions=(
                list(extra_disclosure_assumptions)
                if extra_disclosure_assumptions is not None
                else None
            ),
            # Phase 4+ — M&A artifact
            enable_replacement_cost=enable_replacement_cost,
            identifiable_intangibles_uplift_pct=identifiable_intangibles_uplift_pct,
            enable_statement_of_affairs=enable_statement_of_affairs,
            enable_audit_trail=enable_audit_trail,
            effective_date=effective_date,
            audit_run_id_override=audit_run_id_override,
            audit_computed_at_override=audit_computed_at_override,
            # Phase 5 — lawyer/accountant magic
            enable_sufficiency_memo=enable_sufficiency_memo,
            enable_creditor_letters=enable_creditor_letters,
            enable_strategic_buyer_scenarios=enable_strategic_buyer_scenarios,
        )

    details = dict(build_liquidation_analysis_details(scenarios=scenarios))
    details["modeled_asset_components"] = asset_assumptions
    details["value_basis"] = "equity_value"
    details["range_basis"] = {
        "schema_version": "valuation_range_basis.v1",
        "kind": "assumed_liquidation_spread",
        "assumed_spread": Decimal("0.15"),
        "empirical_percentiles": False,
        "statistical_coverage": None,
    }
    details["headline_basis"] = (
        "recovered_assets_less_liabilities_before_additional_wind_down_and_tax"
    )
    details["exact_scenario_ledger"] = {
        key: {
            "full_company_assets_recovered": scenario.total_assets_adjusted,
            "full_company_liabilities": scenario.total_liabilities_adjusted,
            "full_company_equity_before_floor": scenario.net_asset_value_unclamped,
            "selected_equity_after_floor": (
                Decimal("0.00") if ownership == 0 else scenario.equity_value
            ),
        }
        for key, scenario in (("orderly", scenarios.orderly), ("forced", scenarios.forced))
    }
    # The legacy engine defaults zero ownership to 100%. Its asset/cascade
    # artifacts remain full-company evidence; project the explicitly selected
    # zero stake at this boundary instead of silently repricing it as 100%.
    if ownership == 0:
        details["ownership_multiplier"] = ownership
        details["supplementary_artifact_basis"] = "full_company_before_selected_ownership"
        for key in ("orderly", "forced"):
            scenario_details = dict(details[key])
            for field in ("equity_value", "value_low", "value_high"):
                scenario_details[field] = Decimal("0.00")
            details[key] = scenario_details
    value = Decimal("0.00") if ownership == 0 else money(scenarios.headline_equity())
    low = Decimal("0.00") if ownership == 0 else money(scenarios.orderly.value_low)
    high = Decimal("0.00") if ownership == 0 else money(scenarios.orderly.value_high)
    return MethodResult(
        value=value,
        value_low=low,
        value_high=high,
        equity_value=value,
        equity_value_low=low,
        equity_value_high=high,
        value_basis="equity_value",
        method_key="liquidation_analysis",
        label=LIQUIDATION_LABEL,
        available=True,
        details=details,
    )
