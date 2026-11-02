"""Liquidation-method disclosures with professional-framework references.

Why a structured disclosure block is the EY-approval signature
--------------------------------------------------------------
Big-4 valuation reports close with a disclosure block that names:

1. **Bases of value applied** (IVS 104 §10) — Fair Market Value /
   Liquidation Value / Investment Value / Equitable Value, with the
   authoritative anchor cited.
2. **Premise of value** (IVS 104 §60–80) — going concern vs orderly /
   forced liquidation, with the trigger that selected it.
3. **Approach used** (IVS 105) — market / income / cost approach.
4. **Methodology references and limitations** — frameworks consulted,
   without treating model output as a conforming professional engagement.
5. **Fair-value hierarchy** (IFRS 13 §72-90) — Level 1/2/3 inputs.
6. **Limitations & assumptions** — explicit list.
7. **Out-of-scope items** — explicit list.
8. **Preparer block** — model identity and calculation date; a human
   signatory is supplied only by the commissioning advisor.

This module emits a structured analytical payload for report templates.
It does not create a valuation opinion, professional independence
statement, IVS compliance, USPAP compliance, or an audit engagement.

References
----------
- IVS 104 (2022 ed.) §10 — Bases of Value definitions.
- IVS 104 §60-80 — Premise of value.
- IVS 105 (2022 ed.) — Valuation approaches and methods.
- USPAP STANDARD 9 (Appraisal Foundation, 2024-2025 ed.).
- IFRS 13 §72-90 — Fair value hierarchy.
- IAS 36 §6 — Recoverable amount = max(FVLCD, value in use).
- AICPA SSVS No. 1 (Statement on Standards for Valuation Services).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Mapping, Optional

DISCLOSURE_SOURCES: tuple[str, ...] = (
    "IVS 104 (2022) §10 — Bases of Value",
    "IVS 104 §60–80 — Premise of Value",
    "IVS 105 (2022) — Valuation Approaches and Methods",
    "USPAP STANDARD 9 (2024-2025) — Business Valuation",
    "IFRS 13 §72-90 — Fair Value Hierarchy",
    "IAS 36 §6 — Recoverable Amount",
    "AICPA SSVS No. 1 — Statement on Standards for Valuation Services",
)


class FairValueLevel(str, Enum):
    """IFRS 13 §72 fair-value hierarchy levels."""

    LEVEL_1 = "level_1"  # quoted prices in active markets
    LEVEL_2 = "level_2"  # observable inputs other than quoted prices
    LEVEL_3 = "level_3"  # unobservable inputs


@dataclass(frozen=True)
class FairValueHierarchyEntry:
    """One asset / liability classification entry per IFRS 13.

    ``code`` is a stable key (e.g. ``fv_cash``, ``fv_machinery``) that
    the report context uses to overlay localized ``item_label`` /
    ``rationale``.  The dataclass defaults remain English so direct dict
    consumers and engine-level tests get a useful payload without
    running the report-context resolution step; the locale layer kicks
    in only on the way to the templates.
    """

    item_label: str
    level: FairValueLevel
    rationale: str
    code: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "item_label": self.item_label,
            "level": self.level.value,
            "rationale": self.rationale,
            "code": self.code,
        }


@dataclass(frozen=True)
class DisclosureBlock:
    """Structured disclosure payload — populates the report's Section 10."""

    bases_of_value: tuple[str, ...]  # e.g. ("Liquidation Value (orderly)",)
    premise_of_value: str  # selected premise + trigger code
    approaches_used: tuple[str, ...]  # ("Market Approach", "Cost Approach")
    methodology_compliance: (
        str  # retained field name; content is reference/limitation copy
    )
    fair_value_hierarchy: tuple[FairValueHierarchyEntry, ...]
    limitations: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    assumptions: tuple[str, ...]
    sources: tuple[str, ...]
    signatory: Mapping[str, str]  # {"name": ..., "qualification": ..., "date": ...}
    independence_statement: str  # USPAP STANDARD 9-3 — independence + conflicts
    conflicts_disclosure: str  # any conflicts of interest

    def to_dict(self) -> Dict[str, object]:
        return {
            "bases_of_value": list(self.bases_of_value),
            "premise_of_value": self.premise_of_value,
            "approaches_used": list(self.approaches_used),
            "methodology_compliance": self.methodology_compliance,
            "fair_value_hierarchy": [e.to_dict() for e in self.fair_value_hierarchy],
            "limitations": list(self.limitations),
            "out_of_scope": list(self.out_of_scope),
            "assumptions": list(self.assumptions),
            "sources": list(self.sources),
            "signatory": dict(self.signatory),
            "independence_statement": self.independence_statement,
            "conflicts_disclosure": self.conflicts_disclosure,
        }


# ---------------------------------------------------------------------------
# Default disclosure assembled from the engine outputs.
# Assets/liabilities are typically classified as Level 3 in a liquidation
# context (no quoted prices, factors derived from cohort data + appraiser
# judgement) per IFRS 13 §86-90.
# ---------------------------------------------------------------------------

_DEFAULT_FV_HIERARCHY: tuple[FairValueHierarchyEntry, ...] = (
    FairValueHierarchyEntry(
        code="fv_cash",
        item_label="Cash & cash equivalents",
        level=FairValueLevel.LEVEL_1,
        rationale="Quoted prices in active markets; par value at all dates.",
    ),
    FairValueHierarchyEntry(
        code="fv_trade_receivables",
        item_label="Trade receivables",
        level=FairValueLevel.LEVEL_2,
        rationale=(
            "Observable counterparty data + aging schedule; recovery "
            "rate derived from observable collection histories."
        ),
    ),
    FairValueHierarchyEntry(
        code="fv_inventory",
        item_label="Inventory",
        level=FairValueLevel.LEVEL_3,
        rationale=(
            "No active market for SME-grade work-in-progress or "
            "specialised finished goods at distress sale; recovery "
            "factor sourced from Pratt&Niculita / EY academic data."
        ),
    ),
    FairValueHierarchyEntry(
        code="fv_real_estate",
        item_label="Real estate (land + buildings)",
        level=FairValueLevel.LEVEL_2,
        rationale=(
            "Observable comparable sales in the local commercial real-"
            "estate market; appraisal applies a haircut for distressed "
            "wind-down timeline."
        ),
    ),
    FairValueHierarchyEntry(
        code="fv_machinery",
        item_label="Machinery & equipment",
        level=FairValueLevel.LEVEL_3,
        rationale=(
            "Specialised SME machinery; no active market. Recovery "
            "factor sourced from cohort data (Delphi NACE × class) "
            "with academic fallback."
        ),
    ),
    FairValueHierarchyEntry(
        code="fv_intangibles",
        item_label="Intangible assets",
        level=FairValueLevel.LEVEL_3,
        rationale=(
            "No active market for SME goodwill / trademarks at "
            "liquidation; valuer applies highly-discounted recovery "
            "factor (typically 5-20%)."
        ),
    ),
)

_DEFAULT_LIMITATIONS: tuple[str, ...] = (
    "Recovery factors above the cohort floor are applied where Delphi "
    "has insufficient k-anon-protected sample; report flags those "
    "lines explicitly.",
    "Insolvency priority cascade percentages reflect statutory "
    "default allocations (Boek XX WER / Faillissementswet) absent "
    "explicit per-tier liability buckets supplied by the appraiser.",
    "Wind-down cost estimates use jurisdiction-default assumptions "
    "(severance multiplier, professional-fees percentage, lease "
    "termination). Material deviation requires explicit override.",
    "PV-discount applies a distress WACC of 15% orderly / 25% forced "
    "(Damodaran 2012 Ch. 23 SME range). Custom WACC may be supplied "
    "where the cap-stack supports it.",
)

_DEFAULT_OUT_OF_SCOPE: tuple[str, ...] = (
    "Litigation reserve and contingent legal liabilities — these "
    "must be quantified by the entity's outside counsel; the report "
    "does NOT estimate exposure.",
    "Environmental remediation — site-specific, requires Phase II "
    "environmental assessment by qualified consultant.",
    "Pension underfunding — requires actuarial valuation per IAS 19; "
    "the report assumes the supplied DTL bucket already captures it.",
    "Cross-border tax planning — international structuring is outside "
    "the scope of a single-country liquidation analysis.",
)

_DEFAULT_ASSUMPTIONS: tuple[str, ...] = (
    "Effective date of valuation = balance-sheet reporting date supplied.",
    "Currency of presentation = EUR; no FX translation applied.",
    "Going-concern premise applies unless distress signal triggers "
    "liquidation per IVS 104 §80 decision tree.",
    "All figures are pre-DLOM; lack-of-marketability discount is a "
    "separate adjustment outside this engine.",
)


_DEFAULT_BASES_OF_VALUE: tuple[str, ...] = (
    "Liquidation Value — orderly (IVS 104 §10)",
    "Liquidation Value — forced (IVS 104 §10)",
    "Adjusted Net Asset Value — going-concern reference (IVS 104 §10)",
)

_DEFAULT_APPROACHES_USED: tuple[str, ...] = (
    "Cost Approach — Adjusted Net Asset Value (IVS 105 §60)",
    "Income Approach — Probability-weighted expected value (IVS 105 §40)",
    "Market Approach — Recovery-factor calibration (IVS 105 §20)",
)

_DEFAULT_SIGNATORY: Mapping[str, str] = {
    "name": "Upswitch ValuationIQ — automated model output",
    "qualification": (
        "Not a professional signatory or certification. The identified advisor "
        "must review the sealed evidence, assumptions, method and PDF before approval."
    ),
    "date": "Computed at run-time by the engine",
}


_DEFAULT_INDEPENDENCE_STATEMENT: str = (
    "The software is not a valuer and cannot make a professional independence "
    "declaration. The approving advisor must document personal and firm-level "
    "relationships, fees, conflicts and any economic interest for this engagement."
)

_DEFAULT_CONFLICTS_DISCLOSURE: str = (
    "No material conflicts of interest identified at the engine level. "
    "When a human appraiser counter-signs the engine output for "
    "court-grade work product, that appraiser must add their own "
    "AICPA SSVS No. 1 §52 conflicts disclosure covering personal and "
    "firm-level relationships with the subject, its creditors, and "
    "any prospective bidders."
)


def build_disclosure_block(
    *,
    bases_of_value: Optional[List[str]] = None,
    premise_of_value: str = "going_concern",
    premise_trigger: str = "default_going_concern",
    approaches_used: Optional[List[str]] = None,
    fair_value_hierarchy: Optional[List[FairValueHierarchyEntry]] = None,
    extra_limitations: Optional[List[str]] = None,
    extra_out_of_scope: Optional[List[str]] = None,
    extra_assumptions: Optional[List[str]] = None,
    signatory: Optional[Mapping[str, str]] = None,
    independence_statement_override: Optional[str] = None,
    conflicts_disclosure_override: Optional[str] = None,
) -> DisclosureBlock:
    """Build the structured disclosure block.

    Defaults are populated from the academic and statutory sources
    cited in the module docstring; callers override per-engagement.
    """
    bases = _tuple_or_default(bases_of_value, _DEFAULT_BASES_OF_VALUE)
    premise_str = f"{premise_of_value} (trigger: {premise_trigger})"
    approaches = _tuple_or_default(approaches_used, _DEFAULT_APPROACHES_USED)
    methodology_compliance = (
        "The method presentation draws on concepts found in IVS, USPAP and "
        "AICPA valuation guidance. Those references do not make this automated "
        "output a conforming engagement or professional valuation opinion. "
        "Conformity may be stated only after an appropriately scoped engagement "
        "and documented professional review of all applicable requirements."
    )

    fv_hierarchy = _tuple_or_default(fair_value_hierarchy, _DEFAULT_FV_HIERARCHY)
    limitations = _extend_defaults(_DEFAULT_LIMITATIONS, extra_limitations)
    out_of_scope = _extend_defaults(_DEFAULT_OUT_OF_SCOPE, extra_out_of_scope)
    assumptions = _extend_defaults(_DEFAULT_ASSUMPTIONS, extra_assumptions)
    sig = _signatory_or_default(signatory)

    return DisclosureBlock(
        bases_of_value=bases,
        premise_of_value=premise_str,
        approaches_used=approaches,
        methodology_compliance=methodology_compliance,
        fair_value_hierarchy=fv_hierarchy,
        limitations=limitations,
        out_of_scope=out_of_scope,
        assumptions=assumptions,
        sources=DISCLOSURE_SOURCES,
        signatory=sig,
        independence_statement=_override_or_default(
            independence_statement_override,
            _DEFAULT_INDEPENDENCE_STATEMENT,
        ),
        conflicts_disclosure=_override_or_default(
            conflicts_disclosure_override,
            _DEFAULT_CONFLICTS_DISCLOSURE,
        ),
    )


def _tuple_or_default(
    values: Optional[List[object]],
    default: tuple[object, ...],
) -> tuple[object, ...]:
    if values is None:
        return default
    return tuple(values)


def _extend_defaults(
    defaults: tuple[str, ...],
    extra_values: Optional[List[str]],
) -> tuple[str, ...]:
    if extra_values is None:
        return defaults
    return defaults + tuple(extra_values)


def _signatory_or_default(signatory: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    if signatory is None:
        return dict(_DEFAULT_SIGNATORY)
    return dict(signatory)


def _override_or_default(override: Optional[str], default: str) -> str:
    if override is None:
        return default
    return override


__all__ = [
    "DISCLOSURE_SOURCES",
    "DisclosureBlock",
    "FairValueHierarchyEntry",
    "FairValueLevel",
    "build_disclosure_block",
]
