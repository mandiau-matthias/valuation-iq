"""Typed result contract for liquidation scenarios.

Mirrors the pattern of ``startup_valuation/payloads.py``: dataclasses
that downstream consumers (omni-calc wrapper, report templates, test
suites) can depend on without reaching into the engine internals.

The single Dutch label lives here so anything UI-facing
(MethodReadinessPanel, PDF, omni labels test) reads the same string.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from .asset_schedule import AssetSchedule
from .audit_trail import AuditTrail
from .creditor_letters import CreditorLetterPack
from .disclosure import DisclosureBlock
from .disposal_schedule_pv import DisposalSchedulePV
from .distress_probability import DistressAssessment
from .premise import PremiseDecision
from .premise_reconciliation import PremiseReconciliation
from .priority_cascade import PriorityCascade
from .replacement_cost import ReplacementCostEstimate
from .sensitivity import SensitivityResult
from .statement_of_affairs import StatementOfAffairs
from .strategic_buyer_scenarios import StrategicBuyerScenarios
from .sufficiency_memo import SufficiencyMemo
from .tax_leakage import TaxLeakageBridge
from .wind_down_costs import WindDownCostEstimate

LIQUIDATION_LABEL = "Liquidatiewaarde (Geordende & Gedwongen)"


class LiquidationUnavailableReason(str, Enum):
    """Stable reason codes surfaced when liquidation cannot be computed.

    Mercury / Venus consume these via ``MethodResult.details`` to drive
    targeted unlock nudges. Codes are part of the cross-app contract;
    add new variants here, never inline strings.
    """

    BALANCE_SHEET_MISSING = "LIQUIDATION_BALANCE_SHEET_MISSING"
    TOTAL_ASSETS_NON_POSITIVE = "LIQUIDATION_TOTAL_ASSETS_NON_POSITIVE"
    TOTAL_LIABILITIES_UNRESOLVABLE = "LIQUIDATION_TOTAL_LIABILITIES_UNRESOLVABLE"


@dataclass
class LiquidationScenario:
    """A single (orderly|forced) scenario result.

    Equity figures are post-ownership-multiplier and post-clamp at 0.
    ``net_asset_value_unclamped`` preserves the pre-clamp number so the
    UI can flag insolvent scenarios even when the displayed equity is 0
    (this is the whole point of the downside lens).
    """

    method: str  # "orderly_liquidation" | "forced_liquidation"
    equity_value: Decimal
    total_assets_book: Decimal
    total_assets_adjusted: Decimal
    total_liabilities_book: Decimal
    total_liabilities_adjusted: Decimal
    net_asset_value_unclamped: Decimal
    value_low: Decimal
    value_high: Decimal
    asset_adjustments: List[Dict[str, object]] = field(default_factory=list)
    would_be_insolvent: bool = False
    warnings: List[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> Dict[str, object]:
        """Serialize for the ``MethodResult.details`` payload.

        Decimals are stringified→floated to match the rest of the omni
        details contract (no Decimal across the JSON boundary).
        """
        return {
            "method": self.method,
            "equity_value": float(self.equity_value),
            "total_assets_book": float(self.total_assets_book),
            "total_assets_adjusted": float(self.total_assets_adjusted),
            "total_liabilities_book": float(self.total_liabilities_book),
            "total_liabilities_adjusted": float(self.total_liabilities_adjusted),
            "net_asset_value_unclamped": float(self.net_asset_value_unclamped),
            "value_low": float(self.value_low),
            "value_high": float(self.value_high),
            "asset_adjustments": list(self.asset_adjustments),
            "would_be_insolvent": self.would_be_insolvent,
            "warnings": list(self.warnings),
            "rationale": self.rationale,
        }


@dataclass
class LiquidationScenarios:
    """Container for both scenarios + book-equity reference.

    ``orderly`` is the realistic figure for the headline; ``forced`` is
    the distress floor. ``book_equity`` is the raw assets - liabilities
    figure (signed) for the UI to show "your books say €X, liquidation
    says €Y" without re-deriving.

    The financial score is a complete-input screen, not a fitted probability.
    Premise labels identify comparison scenarios requiring advisor review.
    Neither field establishes viability or automatically weights valuation.
    """

    orderly: LiquidationScenario
    forced: LiquidationScenario
    book_equity: Decimal
    ownership_multiplier: Decimal
    sources: tuple[str, ...]
    premise: Optional[PremiseDecision] = None
    distress: Optional[DistressAssessment] = None
    asset_schedule: Optional[AssetSchedule] = None
    # Legacy slots: expected value is withheld without calibrated probability.
    # The proxy slot can hold only a caller-supplied equity comparison.
    expected_equity_value: Optional[Decimal] = None
    going_concern_proxy_equity: Optional[Decimal] = None
    # Phase 2 — insolvency cascade + tax + wind-down (per scenario).
    priority_cascade_orderly: Optional[PriorityCascade] = None
    priority_cascade_forced: Optional[PriorityCascade] = None
    tax_leakage_orderly: Optional[TaxLeakageBridge] = None
    tax_leakage_forced: Optional[TaxLeakageBridge] = None
    wind_down_orderly: Optional[WindDownCostEstimate] = None
    wind_down_forced: Optional[WindDownCostEstimate] = None
    # Phase 3 — PV-discount + sensitivity + premise reconciliation.
    disposal_schedule_pv_orderly: Optional[DisposalSchedulePV] = None
    disposal_schedule_pv_forced: Optional[DisposalSchedulePV] = None
    sensitivity: Optional[SensitivityResult] = None
    premise_reconciliation: Optional[PremiseReconciliation] = None
    # Phase 4 — disclosure block.
    disclosure: Optional[DisclosureBlock] = None
    # Net-to-shareholder figures (post cascade + tax + wind-down). These
    # are conditional advisor-input scenarios, absent when tax facts are missing.
    net_equity_to_shareholders_orderly: Optional[Decimal] = None
    net_equity_to_shareholders_forced: Optional[Decimal] = None
    # Phase 4+ — replacement cost (M&A buyer ceiling per IVS 105 §60-90),
    # Statement of Affairs (EY-format M&A cover), audit-trail metadata
    # (run_id + payload SHA + engine version for digitalised M&A
    # journey reproducibility per AICPA SSVS No. 1 §57(d)).
    replacement_cost: Optional[ReplacementCostEstimate] = None
    statement_of_affairs: Optional[StatementOfAffairs] = None
    audit_trail: Optional[AuditTrail] = None
    # Phase 5 — Lawyer- and accountant-grade outputs (the "M&A magic"):
    # Sufficiency Memo (per-tier yes/no recovery — lawyer's first
    # question), Creditor Letter Pack (auto-drafted §XX.39 / Art. 38
    # notification letters), Strategic Buyer Scenarios (financial /
    # strategic / MBO bid bands per McKinsey Ch. 18 + Damodaran Ch. 24).
    sufficiency_memo_orderly: Optional[SufficiencyMemo] = None
    sufficiency_memo_forced: Optional[SufficiencyMemo] = None
    creditor_letters_orderly: Optional[CreditorLetterPack] = None
    creditor_letters_forced: Optional[CreditorLetterPack] = None
    strategic_buyer_scenarios: Optional[StrategicBuyerScenarios] = None

    def headline_equity(self) -> Decimal:
        """The orderly figure — what ``MethodResult.value`` should expose."""
        return self.orderly.equity_value

    def to_details_dict(self) -> Dict[str, object]:
        """Serialize for ``MethodResult.details``.

        Includes the ``scope_note`` that pins Phase 1 boundary
        (insolvency priority waterfall = Phase 2; tax leakage = Phase 2;
        sensitivity = Phase 3; NACE calibration = Phase 4) so report
        consumers don't accidentally treat this as a legal-grade output.
        """
        details: Dict[str, object] = {
            "orderly": self.orderly.to_dict(),
            "forced": self.forced.to_dict(),
            "book_equity": float(self.book_equity),
            "ownership_multiplier": float(self.ownership_multiplier),
            "tax_assessment_status": {
                "orderly": (
                    "advisor_input_scenario"
                    if self.tax_leakage_orderly is not None
                    else "not_assessed"
                ),
                "forced": (
                    "advisor_input_scenario"
                    if self.tax_leakage_forced is not None
                    else "not_assessed"
                ),
            },
            "expected_value_status": "not_assessed_uncalibrated_probability",
            "going_concern_comparison_status": (
                "caller_supplied_equity_requires_review"
                if self.going_concern_proxy_equity is not None
                else "not_assessed"
            ),
            "buyer_scenarios_status": "not_assessed_unreconciled_bases_and_premiums",
            "sources": list(self.sources),
            "scope_note": (
                "Company equity and conditional after-tax owner proceeds are separate "
                "estimates. Tax is not assessed without complete dated advisor inputs. "
                "Buyer bid ranges are withheld because value bases and preset premiums "
                "have not been substantiated. Recovery assumptions and sensitivity "
                "quantiles require independent validation; they are not calibrated "
                "prediction intervals."
            ),
        }
        _add_optional_to_dict(
            details,
            [
                ("premise", self.premise),
                ("distress", self.distress),
                ("asset_schedule", self.asset_schedule),
            ],
        )
        _add_optional_decimals(
            details,
            [
                ("expected_equity_value", self.expected_equity_value),
                ("going_concern_proxy_equity", self.going_concern_proxy_equity),
            ],
        )
        # Phase 2-4 surfacing.
        _add_optional_to_dict(
            details,
            [
                ("priority_cascade_orderly", self.priority_cascade_orderly),
                ("priority_cascade_forced", self.priority_cascade_forced),
                ("tax_leakage_orderly", self.tax_leakage_orderly),
                ("tax_leakage_forced", self.tax_leakage_forced),
                ("wind_down_orderly", self.wind_down_orderly),
                ("wind_down_forced", self.wind_down_forced),
                ("disposal_schedule_pv_orderly", self.disposal_schedule_pv_orderly),
                ("disposal_schedule_pv_forced", self.disposal_schedule_pv_forced),
                ("sensitivity", self.sensitivity),
                ("premise_reconciliation", self.premise_reconciliation),
                ("disclosure", self.disclosure),
            ],
        )
        _add_optional_decimals(
            details,
            [
                (
                    "net_equity_to_shareholders_orderly",
                    self.net_equity_to_shareholders_orderly,
                ),
                (
                    "net_equity_to_shareholders_forced",
                    self.net_equity_to_shareholders_forced,
                ),
            ],
        )
        _add_optional_to_dict(
            details,
            [
                ("replacement_cost", self.replacement_cost),
                ("statement_of_affairs", self.statement_of_affairs),
                ("audit_trail", self.audit_trail),
            ],
        )
        # Phase 5 — Lawyer/accountant-grade outputs.
        _add_optional_to_dict(
            details,
            [
                ("sufficiency_memo_orderly", self.sufficiency_memo_orderly),
                ("sufficiency_memo_forced", self.sufficiency_memo_forced),
                ("creditor_letters_orderly", self.creditor_letters_orderly),
                ("creditor_letters_forced", self.creditor_letters_forced),
                ("strategic_buyer_scenarios", self.strategic_buyer_scenarios),
            ],
        )
        return details


def _add_optional_to_dict(
    details: Dict[str, object],
    entries: List[tuple[str, object]],
) -> None:
    for key, value in entries:
        if value is not None:
            details[key] = value.to_dict()


def _add_optional_decimals(
    details: Dict[str, object],
    entries: List[tuple[str, Optional[Decimal]]],
) -> None:
    for key, value in entries:
        if value is not None:
            details[key] = float(value)
