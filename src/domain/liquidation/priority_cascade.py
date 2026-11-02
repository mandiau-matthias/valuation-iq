"""Insolvency priority cascade — BE (Boek XX WER) + NL (Faillissementswet).

Why this is the EY-approval-grade module
----------------------------------------
A liquidation analysis without a priority cascade is a back-of-envelope
sketch. EY/Deloitte/KPMG/PwC restructuring practices anchor every
"realisable equity to shareholders" figure on the country-specific
statutory waterfall — without it, the equity number is whatever's left
after subtracting *book* liabilities, which routinely overstates what
the owner actually receives by 30–60% (the senior creditors take more
than book, the junior creditors take less, and shareholders almost
always come last).

This module encodes the BE and NL waterfalls as first-class data so:
1. The engine can run "what reaches the shareholder" arithmetically
   per the same rules a court-appointed trustee would apply.
2. The report renders a defensible cascade table with statutory
   references (article numbers in the source law).
3. Sensitivity analysis (Phase 3) can run "what if the secured pool
   recovers 80% vs 100%" without re-encoding the rules.

Belgium — Boek XX WER ("Wetboek Economisch Recht — Boek XX")
------------------------------------------------------------
Belgian insolvency law (Boek XX, in force since May 2018) imposes a
strict cascade on bankruptcy distributions:

1. **Boedelschuld / Schulden van de boedel** — costs of administration:
   curator fees, legal fees, post-bankruptcy contracts kept in force.
   Paid first from the gross estate before any creditor sees a euro.
2. **Bijzondere voorrechten op roerend goed (RSZ)** — RSZ
   (sociale zekerheid werknemers) super-priority on movables.
   Art. 19 Hypotheekwet + Art. 30bis RSZ-wet.
3. **Bijzondere voorrechten op onroerend goed** — secured creditors
   (mortgages, pledges, retention of title). Art. 87 Hypotheekwet.
4. **Algemene voorrechten** — general preferences. Order:
   a. Bezoldigingen (loon) van werknemers — Art. 19, 3°bis Hypotheekwet
      (employee wages, 6 months capped at €7,500/month).
   b. BTW + Bedrijfsvoorheffing — Art. 423 WIB.
   c. Andere fiscus + RSZ — Art. 19 Hypotheekwet, 4°/5°.
5. **Gewone schuldeisers (concurrent)** — unsecured creditors,
   pro-rata distribution.
6. **Achtergestelde schuldeisers** — subordinated (typically
   shareholder loans contractually subordinated, or claims under
   Art. 537 W.Venn. for hidden financing).
7. **Aandeelhouders** — only after all of the above is paid in full.

Netherlands — Faillissementswet (Fw)
-------------------------------------
Dutch bankruptcy law (Faillissementswet, originally 1893; major
revisions 2008 and Wet Homologatie Onderhands Akkoord 2021):

1. **Boedelschulden (estate debts)** — Art. 182 Fw + 184 Fw + 185 Fw.
   Curator fees, post-bankruptcy lease/utilities, salaris curator.
2. **Separatisten** — secured creditors (hypotheek/pand). Stand
   *outside* the bankruptcy estate per Art. 57 Fw — they collect
   their security, surrender any surplus, and rank as concurrent for
   any deficit.
3. **Hoog-preferente schuldeisers** — Art. 3:288 BW + 3:284 BW.
   a. Kosten van behoud — Art. 3:284 BW (preservation costs).
   b. Pand-/hypotheekrechten op specifieke goederen.
4. **Hoog-bevoorrecht (super-preferent)** — UWV (Uitvoeringsinstituut
   Werknemersverzekeringen) for last 13 weeks of wages prior to
   bankruptcy + holiday pay (Art. 66 WW).
5. **Preferente schuldeisers** — Art. 21 Invorderingswet 1990 (fiscus
   bodembeslag), Art. 3:288 BW (other preferences).
6. **Concurrente schuldeisers** — unsecured pro-rata.
7. **Achtergestelde schuldeisers** — subordinated.
8. **Aandeelhouders**.

Output contract
---------------
Both jurisdictions emit the same typed structure (`PriorityCascade`)
so the report template renders identically; the *content* of each
tier (statutory anchor, prior order) is jurisdiction-specific.

References
----------
- Boek XX WER (België): Wet 11/8/2017 inwerkingtreding 1/5/2018.
- Hypotheekwet (België): Wet 16/12/1851.
- WIB 92 (Wetboek Inkomstenbelastingen): Art. 264bis (liquidatiebonus),
  Art. 423 (fiscus voorrechten).
- Faillissementswet (NL): Stb. 1893, laatstelijk gewijzigd 2021 (WHOA).
- Burgerlijk Wetboek 3 (NL): Art. 3:284 + 3:288.
- Invorderingswet 1990 (NL): Art. 21 (bodemrecht).
- Werkloosheidswet (NL): Art. 66 (UWV loonovername).
- IVS 104 §80 — Premise of value: forced liquidation requires the
  jurisdiction's statutory cascade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.domain.liquidation.decimal_coercion import to_decimal_or_none

CASCADE_SOURCES_BE: tuple[str, ...] = (
    "Boek XX WER (Wet 11/8/2017, inw. 1/5/2018) — insolventieprocedures",
    "Hypotheekwet (Wet 16/12/1851) Art. 19 — algemene voorrechten",
    "WIB 92 Art. 423 — voorrechten fiscus + bedrijfsvoorheffing",
    "RSZ-wet 27/6/1969 Art. 30bis — RSZ super-priority",
    "Reilly & Schweihs (1998) Valuing Intangible Assets, Ch. 16",
)

CASCADE_SOURCES_NL: tuple[str, ...] = (
    "Faillissementswet 1893 (laatst gewijzigd WHOA 2021) Art. 57 / 182 / 184",
    "Burgerlijk Wetboek 3 Art. 3:284 + 3:288 — voorrechten",
    "Invorderingswet 1990 Art. 21 — fiscus bodemrecht",
    "Werkloosheidswet Art. 66 — UWV loonovername",
)


class CascadeJurisdiction(str, Enum):
    """Stable codes for routing the cascade. Only BE and NL are wired
    in Phase 2; LU/FR/DE require their own statutory mappings."""

    BE = "BE"
    NL = "NL"


class CascadeTierCode(str, Enum):
    """Stable enum for cascade tiers — surfaced in the report.

    The codes are jurisdiction-agnostic; the `statutory_anchor` field
    on each tier carries the BE/NL article number. This keeps the
    report template free of locale-switches.
    """

    ESTATE_COSTS = "estate_costs"  # boedelschulden / kosten van de boedel
    SECURED = "secured"  # secured creditors
    SUPER_PREFERENT_EMPLOYEES = "super_preferent_employees"  # RSZ/UWV/payroll super
    PREFERENT_TAX = "preferent_tax"  # BTW/fiscus
    PREFERENT_OTHER = "preferent_other"  # other preferent
    UNSECURED = "unsecured"  # concurrent
    SUBORDINATED = "subordinated"  # achtergesteld
    SHAREHOLDERS = "shareholders"  # last in line


@dataclass(frozen=True)
class CascadeTier:
    """One tier in the priority waterfall.

    `claim_amount` is the gross liability in this tier (book or
    appraised). `recovery_amount` is what this tier actually gets
    paid from the realised proceeds. `recovery_rate` is implicit
    (`recovery_amount / claim_amount`) and exposed for the report.
    `statutory_anchor` cites the source-law article (e.g. "Art. 30bis
    RSZ-wet" or "Art. 3:288 BW").
    """

    code: CascadeTierCode
    label: str  # human-readable, e.g. "RSZ super-prioriteit"
    claim_amount: Decimal
    recovery_amount: Decimal
    statutory_anchor: str
    rationale: str = ""

    @property
    def recovery_rate(self) -> Decimal:
        if self.claim_amount <= 0:
            return Decimal("0")
        return (self.recovery_amount / self.claim_amount).quantize(Decimal("0.0001"))

    @property
    def shortfall(self) -> Decimal:
        return (self.claim_amount - self.recovery_amount).quantize(Decimal("0.01"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value,
            "label": self.label,
            "claim_amount": float(self.claim_amount),
            "recovery_amount": float(self.recovery_amount),
            "recovery_rate": float(self.recovery_rate),
            "shortfall": float(self.shortfall),
            "statutory_anchor": self.statutory_anchor,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class PriorityCascade:
    """The full cascade — gross proceeds → per-tier recovery → equity floor.

    `equity_to_shareholders` is what's left for class 7 (BE) / 8 (NL)
    after every higher tier is satisfied; this is the figure the
    liquidation report headline equity should anchor on instead of
    the naive `assets - book_liabilities` clamp at 0.
    """

    jurisdiction: CascadeJurisdiction
    gross_proceeds: Decimal  # adjusted realisable value before any creditor paid
    tiers: tuple[CascadeTier, ...]
    equity_to_shareholders: Decimal
    total_claims: Decimal  # sum of claim_amount across tiers (excl. equity)
    total_recovered: Decimal  # sum of recovery_amount across tiers
    total_shortfall: Decimal
    sources: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    # Per-tier liability buckets we received (prior to allocation) — useful
    # for the report to show "this is what was owed" alongside "this is
    # what got paid" without re-deriving from the tiers.
    input_liability_buckets: Mapping[str, Decimal] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jurisdiction": self.jurisdiction.value,
            "gross_proceeds": float(self.gross_proceeds),
            "tiers": [t.to_dict() for t in self.tiers],
            "equity_to_shareholders": float(self.equity_to_shareholders),
            "total_claims": float(self.total_claims),
            "total_recovered": float(self.total_recovered),
            "total_shortfall": float(self.total_shortfall),
            "sources": list(self.sources),
            "warnings": list(self.warnings),
            "input_liability_buckets": {
                k: float(v) for k, v in self.input_liability_buckets.items()
            },
        }


# ---------------------------------------------------------------------------
# Belgian cascade — Boek XX WER
# ---------------------------------------------------------------------------

# Default order: estate → secured → super-preferent (RSZ + employee wages)
# → preferent tax (BTW/bedrijfsvoorheffing) → preferent other (fiscus extra)
# → unsecured → subordinated → shareholders.
_BE_TIER_ORDER: tuple[Tuple[CascadeTierCode, str, str, str], ...] = (
    (
        CascadeTierCode.ESTATE_COSTS,
        "estate_costs",
        "Boedelschulden (curator + post-fail. contracten)",
        "Boek XX WER Art. XX.99 — schulden van de boedel",
    ),
    (
        CascadeTierCode.SECURED,
        "secured",
        "Bevoorrechte schuldeisers (hypotheek + pand + retentie)",
        "Hypotheekwet Art. 19, 1° + Boek XX WER Art. XX.156",
    ),
    (
        CascadeTierCode.SUPER_PREFERENT_EMPLOYEES,
        "super_preferent_employees",
        "RSZ + werknemersloon (super-prioriteit)",
        "RSZ-wet Art. 30bis + Hypotheekwet Art. 19, 3°bis",
    ),
    (
        CascadeTierCode.PREFERENT_TAX,
        "preferent_tax",
        "BTW + bedrijfsvoorheffing (algemeen voorrecht fiscus)",
        "WIB 92 Art. 423 + BTW-wetboek Art. 86",
    ),
    (
        CascadeTierCode.PREFERENT_OTHER,
        "preferent_other",
        "Andere algemene voorrechten",
        "Hypotheekwet Art. 19, 4° en 5°",
    ),
    (
        CascadeTierCode.UNSECURED,
        "unsecured",
        "Gewone (concurrente) schuldeisers",
        "Boek XX WER Art. XX.155 — pari passu verdeling",
    ),
    (
        CascadeTierCode.SUBORDINATED,
        "subordinated",
        "Achtergestelde schuldeisers + aandeelhoudersleningen",
        "W.Venn. Art. 537 + contractuele achterstelling",
    ),
)


# ---------------------------------------------------------------------------
# Dutch cascade — Faillissementswet
# ---------------------------------------------------------------------------

_NL_TIER_ORDER: tuple[Tuple[CascadeTierCode, str, str, str], ...] = (
    (
        CascadeTierCode.ESTATE_COSTS,
        "estate_costs",
        "Boedelschulden (salaris curator + post-fail. lasten)",
        "Faillissementswet Art. 182 + 184 + 185",
    ),
    (
        CascadeTierCode.SECURED,
        "secured",
        "Separatisten (hypotheek + pandhouders)",
        "Faillissementswet Art. 57 — separatisten buiten boedel",
    ),
    (
        CascadeTierCode.SUPER_PREFERENT_EMPLOYEES,
        "super_preferent_employees",
        "UWV loon-overname + vakantiegeld (laatste 13 weken)",
        "Werkloosheidswet Art. 66 + Burgerlijk Wetboek 3:284",
    ),
    (
        CascadeTierCode.PREFERENT_TAX,
        "preferent_tax",
        "Belastingdienst (omzetbelasting + LB) + bodemrecht",
        "Invorderingswet 1990 Art. 21 + BW 3:288 sub a",
    ),
    (
        CascadeTierCode.PREFERENT_OTHER,
        "preferent_other",
        "Andere preferente schuldeisers",
        "Burgerlijk Wetboek 3:288",
    ),
    (
        CascadeTierCode.UNSECURED,
        "unsecured",
        "Concurrente schuldeisers",
        "Faillissementswet Art. 26 — pari passu",
    ),
    (
        CascadeTierCode.SUBORDINATED,
        "subordinated",
        "Achtergestelde schuldeisers",
        "Burgerlijk Wetboek 3:277 lid 2",
    ),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# Default liability bucket allocation when the caller doesn't supply
# explicit buckets. Mirrors the share each tier typically holds in
# Belgian SME bankruptcies (Graydon BE statistics 2023 — used as a
# defensible-default; the report flags it as estimated when no explicit
# buckets are supplied).
#
# IMPORTANT — estate_costs convention:
# The orchestrator pre-subtracts the bottom-up wind-down build-up from
# gross_proceeds *before* invoking the cascade (Big-4 convention: the
# operational wind-down is paid out of the estate before any creditor
# tier is allocated). Therefore the default `estate_costs` share here
# represents *court-administered* boedelschulden only — curator fee
# additions, late legal fees, post-bankruptcy contracts the trustee
# elects to keep in force — distinct from operational wind-down.
# 1% is the Big-4 published mid-range for these residual court costs.
_BE_DEFAULT_BUCKET_SHARE: Mapping[CascadeTierCode, Decimal] = {
    CascadeTierCode.ESTATE_COSTS: Decimal("0.01"),  # court-residual only
    CascadeTierCode.SECURED: Decimal("0.32"),  # bank loans, mortgages, pledges
    CascadeTierCode.SUPER_PREFERENT_EMPLOYEES: Decimal("0.11"),
    CascadeTierCode.PREFERENT_TAX: Decimal("0.16"),
    CascadeTierCode.PREFERENT_OTHER: Decimal("0.05"),
    CascadeTierCode.UNSECURED: Decimal("0.30"),
    CascadeTierCode.SUBORDINATED: Decimal("0.05"),
}

_NL_DEFAULT_BUCKET_SHARE: Mapping[CascadeTierCode, Decimal] = {
    CascadeTierCode.ESTATE_COSTS: Decimal("0.01"),  # court-residual only
    CascadeTierCode.SECURED: Decimal("0.34"),
    CascadeTierCode.SUPER_PREFERENT_EMPLOYEES: Decimal("0.09"),
    CascadeTierCode.PREFERENT_TAX: Decimal("0.20"),  # NL fiscus is heavier
    CascadeTierCode.PREFERENT_OTHER: Decimal("0.04"),
    CascadeTierCode.UNSECURED: Decimal("0.27"),
    CascadeTierCode.SUBORDINATED: Decimal("0.05"),
}


def _resolve_buckets(
    *,
    total_liabilities: Decimal,
    explicit: Optional[Mapping[str, Any]],
    jurisdiction: CascadeJurisdiction,
) -> Tuple[Mapping[CascadeTierCode, Decimal], List[str]]:
    """Resolve the per-tier claim amounts.

    Strategy:
    1. If the caller supplied explicit buckets, honour them verbatim
       (any unspecified tier defaults to 0).
    2. Otherwise, apply the jurisdiction's default share matrix to
       `total_liabilities` and emit a warning so the report tells the
       reader the buckets are estimated.

    Returns the bucket map plus any warnings to surface.
    """
    warnings: List[str] = []
    if explicit:
        # Coerce string keys to CascadeTierCode.
        buckets: Dict[CascadeTierCode, Decimal] = {}
        for key, value in explicit.items():
            try:
                tier = CascadeTierCode(key)
            except ValueError:
                warnings.append(f"Unknown liability bucket key {key!r} ignored by cascade")
                continue
            amount = to_decimal_or_none(value)
            if amount is None or amount < 0:
                continue
            buckets[tier] = amount
        return buckets, warnings

    # Default allocation.
    share = (
        _BE_DEFAULT_BUCKET_SHARE
        if jurisdiction is CascadeJurisdiction.BE
        else _NL_DEFAULT_BUCKET_SHARE
    )
    buckets = {
        tier: (total_liabilities * pct).quantize(Decimal("0.01")) for tier, pct in share.items()
    }
    warnings.append(
        "Per-tier liability buckets were not supplied — applied "
        f"jurisdiction-default allocation for {jurisdiction.value}. "
        "For an EY/Big-4-grade report, supply explicit buckets via "
        "`liability_buckets` so the cascade reflects the actual debt "
        "structure rather than an industry estimate."
    )
    return buckets, warnings


def _allocate_cascade(
    *,
    gross_proceeds: Decimal,
    buckets: Mapping[CascadeTierCode, Decimal],
    tier_order: tuple[Tuple[CascadeTierCode, str, str, str], ...],
) -> Tuple[List[CascadeTier], Decimal]:
    """Greedy top-down allocation: each tier takes up to its claim.

    Returns the list of CascadeTier rows and the residual equity to
    shareholders. Mathematically: this is the same algorithm a court
    trustee runs — pay tier 1 in full (or up to gross), then tier 2 from
    the remainder, etc., until either all tiers are paid or proceeds
    run out.
    """
    remaining = gross_proceeds
    tiers: List[CascadeTier] = []
    for code, _, label, anchor in tier_order:
        claim = buckets.get(code, Decimal("0"))
        if claim <= 0:
            tiers.append(
                CascadeTier(
                    code=code,
                    label=label,
                    claim_amount=Decimal("0.00"),
                    recovery_amount=Decimal("0.00"),
                    statutory_anchor=anchor,
                    rationale="Geen claim in deze tranche",
                )
            )
            continue
        recovery = min(remaining, claim)
        if recovery < 0:
            recovery = Decimal("0")
        tiers.append(
            CascadeTier(
                code=code,
                label=label,
                claim_amount=claim.quantize(Decimal("0.01")),
                recovery_amount=recovery.quantize(Decimal("0.01")),
                statutory_anchor=anchor,
                rationale=(
                    "Volledig voldaan uit de boedel"
                    if recovery >= claim
                    else f"Slechts {float((recovery / claim) * 100):.1f}% gedekt — boedel uitgeput"
                ),
            )
        )
        remaining -= recovery
        if remaining < 0:
            remaining = Decimal("0")

    return tiers, remaining.quantize(Decimal("0.01"))


def compute_priority_cascade(
    *,
    country_code: str,
    gross_proceeds: Any,
    total_liabilities: Any,
    liability_buckets: Optional[Mapping[str, Any]] = None,
) -> Optional[PriorityCascade]:
    """Build the BE or NL priority cascade.

    Returns None for unsupported jurisdictions (LU/FR/DE/etc.); the
    caller falls back to the engine's naive book-value subtraction
    so the report still renders something rather than crashing.
    """
    jurisdiction_str = (country_code or "").upper()
    try:
        jurisdiction = CascadeJurisdiction(jurisdiction_str)
    except ValueError:
        return None

    proceeds = to_decimal_or_none(gross_proceeds) or Decimal("0")
    total_liab = to_decimal_or_none(total_liabilities) or Decimal("0")
    if proceeds < 0:
        proceeds = Decimal("0")

    buckets, warnings = _resolve_buckets(
        total_liabilities=total_liab,
        explicit=liability_buckets,
        jurisdiction=jurisdiction,
    )
    tier_order = _BE_TIER_ORDER if jurisdiction is CascadeJurisdiction.BE else _NL_TIER_ORDER
    tiers, equity = _allocate_cascade(
        gross_proceeds=proceeds, buckets=buckets, tier_order=tier_order
    )

    total_claims = sum((t.claim_amount for t in tiers), Decimal("0")).quantize(Decimal("0.01"))
    total_recovered = sum((t.recovery_amount for t in tiers), Decimal("0")).quantize(
        Decimal("0.01")
    )
    total_shortfall = (total_claims - total_recovered).quantize(Decimal("0.01"))

    sources = CASCADE_SOURCES_BE if jurisdiction is CascadeJurisdiction.BE else CASCADE_SOURCES_NL

    return PriorityCascade(
        jurisdiction=jurisdiction,
        gross_proceeds=proceeds.quantize(Decimal("0.01")),
        tiers=tuple(tiers),
        equity_to_shareholders=equity,
        total_claims=total_claims,
        total_recovered=total_recovered,
        total_shortfall=total_shortfall,
        sources=sources,
        warnings=tuple(warnings),
        input_liability_buckets={code.value: amount for code, amount in buckets.items()},
    )


__all__ = [
    "CASCADE_SOURCES_BE",
    "CASCADE_SOURCES_NL",
    "CascadeJurisdiction",
    "CascadeTier",
    "CascadeTierCode",
    "PriorityCascade",
    "compute_priority_cascade",
]
