"""Phase-level artifacts for liquidation scenario orchestration.

The public ``compute_liquidation_scenarios`` function owns the contract.
This module owns the optional phase reductions around that contract so
the scenario orchestrator stays readable and the legal/accounting
artifacts are isolated behind typed return values.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Mapping, Optional

from .asset_schedule import AssetSchedule
from .audit_trail import AuditTrail, build_audit_trail
from .creditor_letters import CreditorLetterPack, build_creditor_letter_pack
from .disclosure import DisclosureBlock, build_disclosure_block
from .disposal_schedule_pv import DisposalSchedulePV, compute_disposal_schedule_pv
from .payloads import LiquidationScenario
from .premise import PremiseDecision
from .premise_reconciliation import PremiseReconciliation, reconcile_premises
from .priority_cascade import PriorityCascade, compute_priority_cascade
from .replacement_cost import ReplacementCostEstimate, compute_replacement_cost
from .sensitivity import SensitivityResult, build_default_drivers, compute_sensitivity
from .statement_of_affairs import StatementOfAffairs, build_statement_of_affairs
from .strategic_buyer_scenarios import StrategicBuyerScenarios
from .sufficiency_memo import SufficiencyMemo, build_sufficiency_memo
from .tax_leakage import TaxLeakageBridge, compute_tax_leakage
from .tax_policy import tax_context_for_scenario
from .wind_down_costs import WindDownCostEstimate, compute_wind_down_costs


@dataclass(frozen=True)
class LiquidationWaterfallArtifacts:
    """Phase 2 creditor, tax, and wind-down reductions."""

    wind_down_orderly: WindDownCostEstimate
    wind_down_forced: WindDownCostEstimate
    cascade_orderly: Optional[PriorityCascade]
    cascade_forced: Optional[PriorityCascade]
    tax_orderly: Optional[TaxLeakageBridge]
    tax_forced: Optional[TaxLeakageBridge]
    net_orderly: Optional[Decimal]
    net_forced: Optional[Decimal]


@dataclass(frozen=True)
class LiquidationRiskArtifacts:
    """Phase 3 PV, sensitivity, and premise reconciliation output."""

    disposal_schedule_pv_orderly: DisposalSchedulePV
    disposal_schedule_pv_forced: DisposalSchedulePV
    sensitivity: Optional[SensitivityResult]
    premise_reconciliation: PremiseReconciliation


@dataclass(frozen=True)
class LiquidationReportingArtifacts:
    """Phase 4 and 4+ reporting artifacts."""

    disclosure: Optional[DisclosureBlock]
    replacement_cost: Optional[ReplacementCostEstimate]
    statement_of_affairs: Optional[StatementOfAffairs]
    audit_trail: Optional[AuditTrail]


@dataclass(frozen=True)
class LiquidationReductionArtifacts:
    """Phase 5 lawyer/accountant framing artifacts."""

    sufficiency_orderly: Optional[SufficiencyMemo]
    sufficiency_forced: Optional[SufficiencyMemo]
    creditor_letters_orderly: Optional[CreditorLetterPack]
    creditor_letters_forced: Optional[CreditorLetterPack]
    strategic_buyer_scenarios: Optional[StrategicBuyerScenarios]


def compute_waterfall_artifacts(
    *,
    country_code: str,
    ownership_multiplier: Decimal,
    effective_date: Optional[str],
    orderly_scenario: LiquidationScenario,
    forced_scenario: LiquidationScenario,
    total_liabilities: Decimal,
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
) -> LiquidationWaterfallArtifacts:
    """Compute wind-down, creditor cascade, tax leakage, and net proceeds."""

    wind_down_kwargs = dict(wind_down_overrides) if wind_down_overrides else {}
    wind_down_orderly = compute_wind_down_costs(
        scenario="orderly",
        country_code=country_code,
        gross_proceeds=orderly_scenario.total_assets_adjusted,
        headcount=headcount,
        monthly_rent=monthly_rent,
        runway_months=runway_months_orderly,
        **wind_down_kwargs,
    )
    wind_down_forced = compute_wind_down_costs(
        scenario="forced",
        country_code=country_code,
        gross_proceeds=forced_scenario.total_assets_adjusted,
        headcount=headcount,
        monthly_rent=monthly_rent,
        runway_months=runway_months_forced,
        **wind_down_kwargs,
    )

    cascade_orderly = compute_priority_cascade(
        country_code=country_code,
        gross_proceeds=_net_of_wind_down(
            orderly_scenario.total_assets_adjusted,
            wind_down_orderly.total,
        ),
        total_liabilities=total_liabilities,
        liability_buckets=liability_buckets,
    )
    cascade_forced = compute_priority_cascade(
        country_code=country_code,
        gross_proceeds=_net_of_wind_down(
            forced_scenario.total_assets_adjusted,
            wind_down_forced.total,
        ),
        total_liabilities=total_liabilities,
        liability_buckets=liability_buckets,
    )

    tax_orderly = compute_tax_leakage(
        country_code=country_code,
        gross_distribution=_gross_distribution(cascade_orderly),
        tax_context=tax_context_for_scenario(
            tax_context,
            "orderly",
            ownership_multiplier=ownership_multiplier,
            effective_date=effective_date,
        ),
        paid_up_capital=paid_up_capital,
        taxable_reserves=taxable_reserves,
        realised_capital_gains=realised_capital_gains,
        deferred_tax_liabilities=deferred_tax_liabilities,
    )
    tax_forced = compute_tax_leakage(
        country_code=country_code,
        gross_distribution=_gross_distribution(cascade_forced),
        tax_context=tax_context_for_scenario(
            tax_context,
            "forced",
            ownership_multiplier=ownership_multiplier,
            effective_date=effective_date,
        ),
        paid_up_capital=paid_up_capital,
        taxable_reserves=taxable_reserves,
        realised_capital_gains=realised_capital_gains,
        deferred_tax_liabilities=deferred_tax_liabilities,
    )

    return LiquidationWaterfallArtifacts(
        wind_down_orderly=wind_down_orderly,
        wind_down_forced=wind_down_forced,
        cascade_orderly=cascade_orderly,
        cascade_forced=cascade_forced,
        tax_orderly=tax_orderly,
        tax_forced=tax_forced,
        net_orderly=_net_to_shareholder(cascade_orderly, tax_orderly),
        net_forced=_net_to_shareholder(cascade_forced, tax_forced),
    )


def compute_risk_artifacts(
    *,
    asset_schedule: AssetSchedule,
    orderly_scenario: LiquidationScenario,
    total_liabilities: Decimal,
    waterfall: LiquidationWaterfallArtifacts,
    distress_wacc_orderly: Optional[object],
    distress_wacc_forced: Optional[object],
    enable_sensitivity: bool,
    sensitivity_sample_count: int,
    adjusted_nav_override: Optional[Decimal],
    going_concern_value_override: Optional[Decimal],
    multiples_value_override: Optional[Decimal],
) -> LiquidationRiskArtifacts:
    """Compute Phase 3 PV schedules, sensitivity, and premise reconciliation."""

    pv_orderly = compute_disposal_schedule_pv(
        schedule=asset_schedule,
        scenario="orderly",
        distress_wacc_annual=distress_wacc_orderly,
    )
    pv_forced = compute_disposal_schedule_pv(
        schedule=asset_schedule,
        scenario="forced",
        distress_wacc_annual=distress_wacc_forced,
    )

    sensitivity = _compute_sensitivity_if_enabled(
        enabled=enable_sensitivity,
        orderly_scenario=orderly_scenario,
        total_liabilities=total_liabilities,
        waterfall=waterfall,
        sample_count=sensitivity_sample_count,
    )
    reconciliation = reconcile_premises(
        liquidation_value=orderly_scenario.equity_value,
        adjusted_nav=adjusted_nav_override,
        dcf_value=going_concern_value_override,
        multiples_value=multiples_value_override,
    )

    return LiquidationRiskArtifacts(
        disposal_schedule_pv_orderly=pv_orderly,
        disposal_schedule_pv_forced=pv_forced,
        sensitivity=sensitivity,
        premise_reconciliation=reconciliation,
    )


def compute_reporting_artifacts(
    *,
    enable_disclosure: bool,
    premise: PremiseDecision,
    extra_disclosure_assumptions: Optional[List[str]],
    enable_replacement_cost: bool,
    asset_schedule: AssetSchedule,
    identifiable_intangibles_uplift_pct: Optional[Decimal],
    enable_statement_of_affairs: bool,
    total_assets: Decimal,
    total_liabilities: Decimal,
    orderly_scenario: LiquidationScenario,
    forced_scenario: LiquidationScenario,
    waterfall: LiquidationWaterfallArtifacts,
    going_concern_value: Optional[Decimal],
    enable_audit_trail: bool,
    audit_payload: dict[str, object],
    effective_date: Optional[str],
    audit_run_id_override: Optional[str],
    audit_computed_at_override: Optional[str],
) -> LiquidationReportingArtifacts:
    """Build optional report-grade artifacts without expanding the orchestrator."""

    disclosure = _build_disclosure_if_enabled(
        enabled=enable_disclosure,
        premise=premise,
        extra_assumptions=extra_disclosure_assumptions,
    )
    replacement_cost = _build_replacement_cost_if_enabled(
        enabled=enable_replacement_cost,
        asset_schedule=asset_schedule,
        identifiable_intangibles_uplift_pct=identifiable_intangibles_uplift_pct,
    )
    statement_of_affairs = _build_statement_of_affairs_if_enabled(
        enabled=enable_statement_of_affairs,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        orderly_scenario=orderly_scenario,
        forced_scenario=forced_scenario,
        waterfall=waterfall,
        going_concern_value=going_concern_value,
        replacement_cost=replacement_cost,
    )
    audit_trail = _build_audit_trail_if_enabled(
        enabled=enable_audit_trail,
        payload=audit_payload,
        effective_date=effective_date,
        run_id_override=audit_run_id_override,
        computed_at_override=audit_computed_at_override,
    )

    return LiquidationReportingArtifacts(
        disclosure=disclosure,
        replacement_cost=replacement_cost,
        statement_of_affairs=statement_of_affairs,
        audit_trail=audit_trail,
    )


def compute_reduction_artifacts(
    *,
    enable_sufficiency_memo: bool,
    enable_creditor_letters: bool,
    enable_strategic_buyer_scenarios: bool,
    waterfall: LiquidationWaterfallArtifacts,
    going_concern_value: Optional[Decimal],
    replacement_cost: Optional[ReplacementCostEstimate],
) -> LiquidationReductionArtifacts:
    """Build lawyer/accountant reductions from already-computed artifacts."""

    sufficiency_orderly = _build_sufficiency_memo_if_enabled(
        enabled=enable_sufficiency_memo,
        cascade=waterfall.cascade_orderly,
        scenario="orderly",
    )
    sufficiency_forced = _build_sufficiency_memo_if_enabled(
        enabled=enable_sufficiency_memo,
        cascade=waterfall.cascade_forced,
        scenario="forced",
    )
    creditor_letters_orderly = _build_creditor_letter_pack_if_enabled(
        enabled=enable_creditor_letters,
        cascade=waterfall.cascade_orderly,
        scenario="orderly",
    )
    creditor_letters_forced = _build_creditor_letter_pack_if_enabled(
        enabled=enable_creditor_letters,
        cascade=waterfall.cascade_forced,
        scenario="forced",
    )
    # Preset buyer premiums and mixed valuation bases do not substantiate bids.
    # Preserve the optional payload field, but withhold automatic bid pricing.
    buyer_scenarios = None

    return LiquidationReductionArtifacts(
        sufficiency_orderly=sufficiency_orderly,
        sufficiency_forced=sufficiency_forced,
        creditor_letters_orderly=creditor_letters_orderly,
        creditor_letters_forced=creditor_letters_forced,
        strategic_buyer_scenarios=buyer_scenarios,
    )


def _net_of_wind_down(scenario_assets: Decimal, wind_down_total: Decimal) -> Decimal:
    """Clamp post-wind-down gross proceeds before creditor allocation."""

    net = scenario_assets - wind_down_total
    return net if net > 0 else Decimal("0")


def _gross_distribution(cascade: Optional[PriorityCascade]) -> Optional[Decimal]:
    if cascade is None:
        return None
    return cascade.equity_to_shareholders


def _net_to_shareholder(
    cascade: Optional[PriorityCascade],
    tax: Optional[TaxLeakageBridge],
) -> Optional[Decimal]:
    if cascade is None or tax is None:
        return None
    net = cascade.equity_to_shareholders - tax.total_tax_leakage
    if net < 0:
        net = Decimal("0.00")
    return net.quantize(Decimal("0.01"))


def _compute_sensitivity_if_enabled(
    *,
    enabled: bool,
    orderly_scenario: LiquidationScenario,
    total_liabilities: Decimal,
    waterfall: LiquidationWaterfallArtifacts,
    sample_count: int,
) -> Optional[SensitivityResult]:
    if not enabled or orderly_scenario.equity_value <= 0 or waterfall.net_orderly is None:
        return None
    try:
        return _run_sensitivity(
            central_value=waterfall.net_orderly,
            orderly_assets_adjusted=orderly_scenario.total_assets_adjusted,
            total_liabilities=total_liabilities,
            wind_down_total=waterfall.wind_down_orderly.total,
            tax_total=(
                waterfall.tax_orderly.total_tax_leakage
                if waterfall.tax_orderly is not None
                else Decimal("0")
            ),
            sample_count=sample_count,
        )
    except Exception:
        return None


def _run_sensitivity(
    *,
    central_value: Decimal,
    orderly_assets_adjusted: Decimal,
    total_liabilities: Decimal,
    wind_down_total: Decimal,
    tax_total: Decimal,
    sample_count: int,
) -> SensitivityResult:
    """Run a four-driver sensitivity around central net-equity."""

    drivers = build_default_drivers(
        central_inputs={
            "asset_recovery_scalar": Decimal("1.00"),
            "liability_scalar": Decimal("1.00"),
            "wind_down_scalar": Decimal("1.00"),
            "tax_scalar": Decimal("1.00"),
        },
        stress_frac=Decimal("0.20"),
    )

    def _evaluate(inputs: dict[str, Decimal]) -> Decimal:
        equity = (
            orderly_assets_adjusted * inputs["asset_recovery_scalar"]
            - total_liabilities * inputs["liability_scalar"]
            - wind_down_total * inputs["wind_down_scalar"]
            - tax_total * inputs["tax_scalar"]
        )
        return equity if equity > 0 else Decimal("0")

    return compute_sensitivity(
        central_value=central_value,
        drivers=drivers,
        evaluator=_evaluate,
        sample_count=sample_count,
        seed=0,
    )


def _build_disclosure_if_enabled(
    *,
    enabled: bool,
    premise: PremiseDecision,
    extra_assumptions: Optional[List[str]],
) -> Optional[DisclosureBlock]:
    if not enabled:
        return None
    return build_disclosure_block(
        premise_of_value=premise.primary.value,
        premise_trigger=premise.trigger.value,
        extra_assumptions=extra_assumptions,
    )


def _build_replacement_cost_if_enabled(
    *,
    enabled: bool,
    asset_schedule: AssetSchedule,
    identifiable_intangibles_uplift_pct: Optional[Decimal],
) -> Optional[ReplacementCostEstimate]:
    if not enabled or not asset_schedule.lines:
        return None
    try:
        return compute_replacement_cost(
            schedule=asset_schedule,
            identifiable_intangibles_uplift_pct=identifiable_intangibles_uplift_pct,
        )
    except Exception:
        return None


def _build_statement_of_affairs_if_enabled(
    *,
    enabled: bool,
    total_assets: Decimal,
    total_liabilities: Decimal,
    orderly_scenario: LiquidationScenario,
    forced_scenario: LiquidationScenario,
    waterfall: LiquidationWaterfallArtifacts,
    going_concern_value: Optional[Decimal],
    replacement_cost: Optional[ReplacementCostEstimate],
) -> Optional[StatementOfAffairs]:
    if (
        not enabled
        or waterfall.cascade_orderly is None
        or waterfall.cascade_forced is None
        or waterfall.net_orderly is None
        or waterfall.net_forced is None
    ):
        return None
    try:
        return build_statement_of_affairs(
            book_equity=(total_assets - total_liabilities).quantize(Decimal("0.01")),
            orderly_assets_adjusted=orderly_scenario.total_assets_adjusted,
            forced_assets_adjusted=forced_scenario.total_assets_adjusted,
            wind_down_orderly_total=waterfall.wind_down_orderly.total,
            wind_down_forced_total=waterfall.wind_down_forced.total,
            cascade_orderly_tiers=waterfall.cascade_orderly.tiers,
            cascade_forced_tiers=waterfall.cascade_forced.tiers,
            tax_orderly_total=(
                waterfall.tax_orderly.total_tax_leakage
                if waterfall.tax_orderly is not None
                else Decimal("0")
            ),
            tax_forced_total=(
                waterfall.tax_forced.total_tax_leakage
                if waterfall.tax_forced is not None
                else Decimal("0")
            ),
            net_orderly=waterfall.net_orderly,
            net_forced=waterfall.net_forced,
            going_concern_value=going_concern_value,
            replacement_cost_value=(
                replacement_cost.total_replacement_cost if replacement_cost is not None else None
            ),
            cascade_jurisdiction=waterfall.cascade_orderly.jurisdiction.value,
        )
    except Exception:
        return None


def _build_audit_trail_if_enabled(
    *,
    enabled: bool,
    payload: dict[str, object],
    effective_date: Optional[str],
    run_id_override: Optional[str],
    computed_at_override: Optional[str],
) -> Optional[AuditTrail]:
    if not enabled:
        return None
    try:
        return build_audit_trail(
            payload=payload,
            effective_date=effective_date,
            run_id_override=run_id_override,
            computed_at_override=computed_at_override,
        )
    except Exception:
        return None


def _build_sufficiency_memo_if_enabled(
    *,
    enabled: bool,
    cascade: Optional[PriorityCascade],
    scenario: str,
) -> Optional[SufficiencyMemo]:
    if not enabled or cascade is None:
        return None
    try:
        return build_sufficiency_memo(cascade=cascade, scenario=scenario)
    except Exception:
        return None


def _build_creditor_letter_pack_if_enabled(
    *,
    enabled: bool,
    cascade: Optional[PriorityCascade],
    scenario: str,
) -> Optional[CreditorLetterPack]:
    if not enabled or cascade is None:
        return None
    try:
        return build_creditor_letter_pack(cascade=cascade, scenario=scenario)
    except Exception:
        return None
