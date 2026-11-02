"""Owner Risk Ledger — single auditable record for M&A dossiers.

PURPOSE
-------
The owner-related discount in our reports flows through TWO independent
mechanisms by design:

1. STRUCTURAL (multiple-side, Step 4) — `OwnerConcentrationAdjuster`.
   Heuristic from owner / FTE ratio + business-type calibration. Reduces
   the EV/EBITDA multiple. Big 4 standard for SME valuations.

2. BEHAVIORAL (equity-side, post-Step 4) — `OwnerDependencyEngine` /
   `OwnerDependencyProcessor`. Damodaran 12-factor / SBVS transferability
   assessment driven by the 9-question owner profile. Reduces equity
   value (capped at MVP_OWNER_ADJUSTMENT_FLOOR..CEILING).

The two are complementary, not duplicative — see the comment in
`owner_concentration_adjuster.py`. But to a reader of the final report
they look like two separate "key person" rows in different sections,
which is exactly the confusion that causes M&A defensibility failures.

This ledger is the single auditable record that reconciles them:

  • One list of entries, side-tagged ("multiple" vs "equity").
  • Each entry carries its academic citation + methodology marker.
  • A combined monetary impact line lets the M&A reader read the full
    owner-related haircut at a glance.
  • An `audit_quality` flag tells the reader whether the assessment is
    backed by the 9-question profile (DEFENSIBLE) or by the structural
    heuristic alone (HEURISTIC_ONLY).
  • An explicit `cross_reference_note` documents the no-double-count
    invariant so an auditor doesn't have to re-derive it from code.

THE LEDGER IS PURE METADATA. It does not change any number that flows
into EV / equity / asking price. It is built AFTER the synthesis math
completes and consumes the existing pipeline_stage_4 + owner_dependency
result. Every value already exists in the response tree; this object is
the M&A-grade *presentation* of those values.

ACADEMIC FOUNDATION
-------------------
- Structural side: McKinsey Valuation Handbook (Koller, Goedhart &
  Wessels 2020, Ch. 11); Damodaran (2012) "Key Person Discounts"
  (p. 112-135); PwC Private Company Valuation Guide (2023, §5.3).
- Behavioral side: Damodaran (2012, Ch. 12) 12-factor framework;
  Pratt & Niculita (2008) "Valuing a Business" (5th ed., Ch. 14
  Transferability of Earnings); SBVS Key Person Risk frameworks;
  IVS 2022 (International Valuation Standards Council).
- Reconciliation principle: Mercer & Harms (2007) "Business Valuation:
  An Integrated Theory" — risk decomposition by mechanism (multiple
  vs. equity) is the IVS-aligned standard for SME M&A reports.
"""

from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.domain.owner_concentration_adjuster import OwnerConcentrationAdjuster
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Ledger schema version. Bump when the entry shape changes so renderers
# can branch on the version field rather than guessing at field presence.
LEDGER_VERSION = "1.0.0"


# Citation registry for the ledger. Each ledger entry references one or
# more keys here so the renderer (PDF / HTML / Mercury) does not have to
# re-quote sources. Adding a citation here is the only correct way to
# extend the registry — drift between the entry and a free-text citation
# string would defeat the audit trail.
CITATIONS: Dict[str, Dict[str, str]] = {
    "damodaran_2012_ch4": {
        "author": "Damodaran, A.",
        "year": "2012",
        "title": "Investment Valuation: Tools and Techniques for Determining the Value of Any Asset",
        "page_reference": "Ch. 4 — Key Person Discounts (p. 112-135)",
    },
    "damodaran_2012_ch12": {
        "author": "Damodaran, A.",
        "year": "2012",
        "title": "Investment Valuation",
        "page_reference": "Ch. 12 — 12-Factor Owner Dependency Framework",
    },
    "koller_2020_ch11": {
        "author": "Koller, T., Goedhart, M. & Wessels, D.",
        "year": "2020",
        "title": "Valuation: Measuring and Managing the Value of Companies (7th ed.)",
        "page_reference": "Ch. 11 — Valuing SMEs, p. 356",
    },
    "pwc_2023_53": {
        "author": "PwC",
        "year": "2023",
        "title": "Private Company Valuation Guide",
        "page_reference": "§5.3 Owner Concentration Risk",
    },
    "pratt_2008_ch14": {
        "author": "Pratt, S. & Niculita, A.",
        "year": "2008",
        "title": "Valuing a Business (5th ed.)",
        "page_reference": "Ch. 14 — Transferability of Earnings",
    },
    "ivs_2022": {
        "author": "International Valuation Standards Council",
        "year": "2022",
        "title": "International Valuation Standards (IVS)",
        "page_reference": "IVS 105 — Valuation Approaches and Methods",
    },
    "mercer_2007": {
        "author": "Mercer, Z. C. & Harms, T. W.",
        "year": "2007",
        "title": "Business Valuation: An Integrated Theory (2nd ed.)",
        "page_reference": "Risk decomposition by mechanism — multiple vs. equity",
    },
}


class OwnerRiskLedgerEntry(BaseModel):
    """One row in the reconciliation ledger.

    `side` distinguishes which mechanism applied the discount:
      • "multiple" — reduces the EV/EBITDA multiple, shows in the
        Step-4 waterfall (page 4 of the M&A dossier).
      • "equity"   — reduces equity value post-EV-to-equity bridge,
        shows in the Owner Profile section (page 5).
    """

    label: str = Field(description="Display label for the row.")
    side: Literal["multiple", "equity"] = Field(
        description="Which mechanism applied the discount: multiple or equity."
    )
    adjustment_pct: Decimal = Field(
        description=(
            "Discount as a signed percentage point on the value of its side. "
            "E.g. -20.0 means a 20% reduction. Equity-side entries express "
            "the discount as applied to equity_value_mid; multiple-side "
            "entries express it as applied to the EV/EBITDA multiple."
        )
    )
    monetary_impact: Decimal = Field(
        description=(
            "Signed € impact of this row on its side's denominator. Negative "
            "for a discount. Sums across sides at `total_monetary_impact`."
        )
    )
    risk_level: str = Field(description="Risk-level label, e.g. CRITICAL/HIGH/MEDIUM/LOW.")
    methodology: str = Field(
        description="Short methodology marker, e.g. 'FTE-ratio heuristic' or 'Damodaran 12-factor'."
    )
    citation_keys: List[str] = Field(
        default_factory=list,
        description="Keys into the module-level CITATIONS registry.",
    )
    is_heuristic: bool = Field(
        description=(
            "True if the row is structural / heuristic (no owner profile "
            "behind it). False if the row is profile-derived. Renderers "
            "use this to pick the right caveat language."
        )
    )
    evidence_grade: Literal["CORROBORATED", "UNCORROBORATED"] = Field(
        default="CORROBORATED",
        description=(
            "CORROBORATED = the inputs behind this row were confirmed by a "
            "human (Owner Profile completed, or headcount explicitly "
            "confirmed). UNCORROBORATED = derived from an unvalidated "
            "registry field; the row is capped and disclosed as a band. "
            "Orthogonal to `is_heuristic`, which says which MECHANISM "
            "produced the row, not whether its inputs were verified."
        ),
    )
    input_basis: Optional[str] = Field(
        default=None,
        description=(
            "Human-readable statement of the literal inputs behind the row "
            "(counts + where they came from). Rendered next to the label so "
            "the basis is visible on the page, not buried in a rationale."
        ),
    )

    model_config = ConfigDict(populate_by_name=True)


class OwnerRiskLedger(BaseModel):
    """Single auditable record of all owner-related discounts.

    Built once per valuation, after both the multiple waterfall and the
    OD haircut have run. Renderers (PDF / HTML / Mercury) consume this
    object verbatim — they MUST NOT re-derive any of these fields from
    upstream pipeline data, since that is precisely how the original
    label/value desync bug got into shipped reports.
    """

    version: str = Field(default=LEDGER_VERSION, description="Ledger schema version.")
    entries: List[OwnerRiskLedgerEntry] = Field(default_factory=list)

    total_monetary_impact: Decimal = Field(
        description=(
            "Sum of all entries' monetary impacts. Different sides — "
            "multiple-side reduces EV, equity-side reduces equity — but "
            "sum is meaningful as the total € the seller forgoes due to "
            "owner-related risk on a kas- en schuldvrije basis."
        )
    )

    profile_completed: bool = Field(
        description="True iff the 9-question Owner Profile assessment was filled in."
    )

    audit_quality: Literal["DEFENSIBLE", "HEURISTIC_ONLY"] = Field(
        description=(
            "DEFENSIBLE = behavioral profile available, both mechanisms "
            "active, the discount is decomposable. HEURISTIC_ONLY = only "
            "the structural FTE-based row is available; an M&A buyer's "
            "diligence team will likely re-derive the behavioral component."
        )
    )

    cross_reference_note: str = Field(
        description=(
            "Plain-language statement of the no-double-count invariant: "
            "structural (multiple-side) and behavioral (equity-side) "
            "discounts are complementary, not stacked. Renderable as-is."
        )
    )

    methodology_summary: str = Field(
        description=(
            "One-paragraph summary of the methodology applied, suitable "
            "for the report's 'Methodology' section."
        )
    )

    next_action: Optional[str] = Field(
        default=None,
        description=(
            "Concrete advisor-facing next action when the profile is not "
            "yet completed. None when audit_quality is DEFENSIBLE."
        ),
    )

    model_config = ConfigDict(populate_by_name=True)


def _format_input_basis(basis: Any, number_of_owners: Optional[int]) -> Optional[str]:
    """Human-readable basis line for the structural entry, printed on the report.

    Degrades to silence, never to the word "None". The earlier version
    interpolated `basis.get(...)` directly, so a pipeline_stage assembled without
    `number_of_owners` or with a differently-named source key rendered
    "None owner(s) / 2 employee(s) (source: unknown)" straight onto an advisor
    deliverable. Step 4 populates both today; this makes that a requirement of
    the FORMATTER rather than an assumption about every future caller.
    """
    if not isinstance(basis, dict) or not basis:
        return None

    owners = basis.get("number_of_owners")
    if owners is None:
        owners = number_of_owners
    employees = basis.get("number_of_employees")
    # Accept either key: Step 4 emits `headcount_source`; be tolerant of `source`.
    source = basis.get("headcount_source") or basis.get("source")

    parts: list[str] = []
    if owners is not None:
        parts.append(f"{owners} owner(s)")
    if employees is not None:
        parts.append(f"{employees} employee(s)")
    if not parts:
        return None

    line = " / ".join(parts)
    return f"{line} (source: {source})" if source else line

def _structural_entry(
    *,
    pipeline_stage: Dict[str, Any],
    ev_before: Decimal,
    ev_after: Decimal,
    number_of_owners: Optional[int],
) -> OwnerRiskLedgerEntry:
    """Build the multiple-side entry from the Step-4 pipeline stage."""

    # NOTE: this string is printed on the advisor's report, so it must degrade
    # to silence rather than to the word "None". See _format_input_basis.

    # Use the canonical inverse so the label here cannot drift from the
    # numeric impact even if the upstream pipeline_stage was assembled
    # with a stale risk_level (the METANOUS bug class).
    adjustment_pct = to_decimal(pipeline_stage.get("discount_percentage") or 0)
    risk_level = OwnerConcentrationAdjuster.risk_level_for_adjustment(
        adjustment_pct / Decimal("100"),
        number_of_owners=number_of_owners,
    )

    monetary_impact = to_decimal(ev_after) - to_decimal(ev_before)

    # A tier name asserts a *measured* concentration. When Step 4 could not
    # corroborate the headcount it stamps evidence_grade=UNCORROBORATED and caps
    # its own adjustment; the inverse lookup above would otherwise re-promote
    # that capped number to a tier name (a -5% row reads MEDIUM), re-asserting
    # off an unvalidated registry field exactly what the cap was meant to avoid.
    evidence_grade = str(pipeline_stage.get("evidence_grade") or "CORROBORATED").upper()
    corroborated = evidence_grade != "UNCORROBORATED"
    if not corroborated:
        risk_level = OwnerConcentrationAdjuster.UNCORROBORATED_RISK_LABEL

    basis = pipeline_stage.get("input_basis") or {}
    input_basis = _format_input_basis(basis, number_of_owners)

    return OwnerRiskLedgerEntry(
        label=(
            f"Structural Owner Concentration ({risk_level})"
            if corroborated
            else "Structural Owner Concentration (INDICATIVE — headcount not confirmed)"
        ),
        side="multiple",
        adjustment_pct=adjustment_pct,
        monetary_impact=monetary_impact,
        risk_level=risk_level,
        methodology=(
            "Owner / FTE ratio (Big 4 tier)"
            if corroborated
            else "Owner / FTE ratio — capped, headcount unverified"
        ),
        citation_keys=["damodaran_2012_ch4", "koller_2020_ch11", "pwc_2023_53"],
        is_heuristic=True,
        evidence_grade="CORROBORATED" if corroborated else "UNCORROBORATED",
        input_basis=input_basis,
    )


def _behavioral_entry(
    *,
    owner_dependency_result: Any,
    owner_dependency_adjustment: Decimal,
    equity_value_mid_after: Decimal,
) -> OwnerRiskLedgerEntry:
    """Build the equity-side entry from the OD result.

    `owner_dependency_adjustment` is the post-MVP-cap value (i.e. what
    actually shipped to the seller). The OD result also carries the
    pre-cap `raw_adjustment`; we keep the cap-applied value here because
    the ledger is the *applied* record, not the engine's wish list.
    """
    od_adjustment = to_decimal(owner_dependency_adjustment)
    od_pct = od_adjustment * Decimal("100")
    risk_level = getattr(owner_dependency_result, "risk_level", "UNKNOWN") or "UNKNOWN"

    # Equity-side impact: equity_after - equity_before. Since the
    # synthesizer scales equity by (1 + adjustment), a negative adjustment
    # produces a negative impact: equity_after = equity_before * (1+adj),
    # so impact = equity_before * adj = equity_after / (1+adj) * adj.
    if od_adjustment != Decimal("0") and od_adjustment != Decimal("-1"):
        equity_before = to_decimal(equity_value_mid_after) / (Decimal("1") + od_adjustment)
        monetary_impact = to_decimal(equity_value_mid_after) - equity_before
    else:
        monetary_impact = Decimal("0")

    return OwnerRiskLedgerEntry(
        label=f"Behavioral Owner Dependency ({risk_level})",
        side="equity",
        adjustment_pct=od_pct,
        monetary_impact=monetary_impact,
        risk_level=risk_level,
        methodology="Damodaran 12-factor / Pratt transferability",
        citation_keys=["damodaran_2012_ch12", "pratt_2008_ch14", "ivs_2022"],
        is_heuristic=False,
    )


_NO_DOUBLE_COUNT_NOTE = (
    "Structural (FTE-based) and behavioral (12-factor) owner-risk discounts "
    "are applied through different mechanisms — the multiple and the equity "
    "value respectively — and measure complementary aspects of the same risk "
    "(management depth vs. owner-role transferability). They are not stacked: "
    "the structural row reflects the management-depth heuristic, the behavioral "
    "row reflects the buyer's transferability discount post-bridge. This "
    "decomposition follows IVS 105 and Mercer & Harms (2007)."
)


_HEURISTIC_ONLY_SUMMARY = (
    "Owner-related risk in this dossier is captured solely by the structural "
    "Owner / FTE ratio heuristic on the EV/EBITDA multiple (Step 4). The "
    "behavioral 12-factor assessment (page 5) was not completed, so a buyer's "
    "diligence team will most likely re-derive an additional transferability "
    "discount on the equity-side bridge. Completing the 9-question Owner "
    "Profile lets us pre-empt that and gives the row defensible attribution "
    "per Damodaran (2012, Ch. 12) and Pratt & Niculita (2008, Ch. 14)."
)


_DEFENSIBLE_SUMMARY = (
    "Owner-related risk is decomposed into a structural component on the "
    "EV/EBITDA multiple (Big 4 FTE-ratio heuristic, Step 4) and a behavioral "
    "component on the equity bridge (Damodaran 12-factor / Pratt "
    "transferability, post-Step 7). Both are sourced and capped per the MVP "
    "underclaim band; the combined € impact is the dossier's full owner-risk "
    "haircut, with no double-count between mechanisms."
)


def build_owner_risk_ledger(
    *,
    pipeline_stage_4: Optional[Dict[str, Any]],
    structural_ev_before: Decimal,
    structural_ev_after: Decimal,
    owner_dependency_result: Optional[Any],
    owner_dependency_adjustment: Any,
    equity_value_mid_after: Decimal,
    number_of_owners: Optional[int] = None,
) -> Optional[OwnerRiskLedger]:
    """Assemble the reconciliation ledger.

    Returns None when there is genuinely nothing to report — i.e. no
    structural row AND no behavioral row. In every other case the
    ledger object is built and the renderer can decide how to surface
    it. We deliberately do NOT raise on partial input: the ledger is a
    presentation layer and must be at least as robust as the underlying
    pipeline.
    """
    od_adjustment = to_decimal(owner_dependency_adjustment) if owner_dependency_adjustment is not None else Decimal("0")
    profile_completed = owner_dependency_result is not None and od_adjustment != Decimal("0")

    entries: List[OwnerRiskLedgerEntry] = []

    structural_present = (
        pipeline_stage_4 is not None
        and to_decimal(pipeline_stage_4.get("discount_percentage") or 0) != Decimal("0")
    )
    if structural_present:
        try:
            entries.append(
                _structural_entry(
                    pipeline_stage=pipeline_stage_4,
                    ev_before=to_decimal(structural_ev_before),
                    ev_after=to_decimal(structural_ev_after),
                    number_of_owners=number_of_owners,
                )
            )
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(
                "Owner risk ledger: failed to build structural entry; skipping",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

    if profile_completed:
        try:
            entries.append(
                _behavioral_entry(
                    owner_dependency_result=owner_dependency_result,
                    owner_dependency_adjustment=od_adjustment,
                    equity_value_mid_after=to_decimal(equity_value_mid_after),
                )
            )
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(
                "Owner risk ledger: failed to build behavioral entry; skipping",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

    if not entries:
        return None

    total_impact = sum((entry.monetary_impact for entry in entries), Decimal("0"))
    audit_quality: Literal["DEFENSIBLE", "HEURISTIC_ONLY"] = (
        "DEFENSIBLE" if profile_completed else "HEURISTIC_ONLY"
    )

    return OwnerRiskLedger(
        entries=entries,
        total_monetary_impact=total_impact,
        profile_completed=profile_completed,
        audit_quality=audit_quality,
        cross_reference_note=_NO_DOUBLE_COUNT_NOTE,
        methodology_summary=(
            _DEFENSIBLE_SUMMARY if profile_completed else _HEURISTIC_ONLY_SUMMARY
        ),
        next_action=(
            None
            if profile_completed
            else "Send the 9-question Owner Profile questionnaire to unlock behavioral attribution."
        ),
    )
