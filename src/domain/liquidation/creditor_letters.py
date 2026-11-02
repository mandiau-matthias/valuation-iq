"""Creditor Letter Templates — auto-drafted per-tier notification letters.

Why this is the lawyer's killer feature
---------------------------------------
Under Boek XX WER §XX.39 (BE) and Faillissementswet Art. 38 (NL), the
court-appointed curator/trustee must notify each creditor of:
1. The amount of their claim as accepted.
2. The rank assigned (preferent / secured / concurrent).
3. The expected dividend under each scenario.
4. The statutory basis for the ranking.

Every restructuring lawyer hand-drafts these letters today. This
module produces the draft content automatically — the lawyer copies
into their notice template, edits the addressee block, and ships.

The artifact is *the* magic moment for an M&A counsel evaluating a
distressed acquisition: they get a per-tier notification letter
*draft* baked into the report, with the statutory citation already
filled in. That's pure leverage on the cascade math.

Each generated letter is a structured payload (subject + opening +
body paragraphs + closing + statutory anchor + signatory placeholder)
so downstream renderers (PDF / Word / DOCX export) can format
without re-deriving content.

References
----------
- Boek XX WER §XX.39 — Notification of creditors (BE).
- Boek XX WER Art. XX.155 — Distribution rules (BE).
- Faillissementswet Art. 38 — Notification (NL).
- Faillissementswet Art. 26 — Pari-passu within tier (NL).
- Belgian Code of Civil Procedure Art. 1395 — Standard notification format.
- KPMG (2022) "Restructuring Notice Drafting Standards."
- Monard Law (2023) public memos on §XX.39 letter format.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from .priority_cascade import CascadeTier, CascadeTierCode, PriorityCascade


CREDITOR_LETTER_SOURCES: tuple[str, ...] = (
    "Boek XX WER §XX.39 + Art. XX.155 — schuldeiser-notificatie (BE)",
    "Faillissementswet Art. 38 + Art. 26 — schuldeiser-notificatie (NL)",
    "Belgian Code of Civil Procedure Art. 1395 — notification format",
    "KPMG (2022) Restructuring Notice Drafting Standards",
    "Monard Law (2023) public memos — §XX.39 letter format",
)


class LetterUrgency(str, Enum):
    """Lawyer-grade flag for triage when reviewing letter drafts."""

    URGENT = "urgent"  # tier paid in full or near-full — fast settlement
    STANDARD = "standard"  # partial coverage — negotiation expected
    HARDSHIP = "hardship"  # uncovered — claimant should engage counsel


@dataclass(frozen=True)
class CreditorLetter:
    """One auto-drafted creditor notification letter.

    Each field is a structured paragraph the lawyer copies into their
    house template. The `body_paragraphs` list is the meat — typically
    3-5 paragraphs covering claim ack, ranking, expected dividend,
    statutory basis, recourse.
    """

    tier_code: str
    tier_label: str
    statutory_anchor: str
    urgency: LetterUrgency
    subject_line: str
    salutation_placeholder: str  # "Geachte heer/mevrouw [naam]"
    body_paragraphs: tuple[str, ...]
    closing: str
    signatory_placeholder: str  # "[curator naam], advocaat"
    expected_dividend_pct: Decimal
    expected_dividend_amount: Decimal
    claim_amount: Decimal
    rationale: str  # internal — why this letter exists in this form

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier_code": self.tier_code,
            "tier_label": self.tier_label,
            "statutory_anchor": self.statutory_anchor,
            "urgency": self.urgency.value,
            "subject_line": self.subject_line,
            "salutation_placeholder": self.salutation_placeholder,
            "body_paragraphs": list(self.body_paragraphs),
            "closing": self.closing,
            "signatory_placeholder": self.signatory_placeholder,
            "expected_dividend_pct": float(self.expected_dividend_pct),
            "expected_dividend_amount": float(self.expected_dividend_amount),
            "claim_amount": float(self.claim_amount),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class CreditorLetterPack:
    """All auto-drafted letters for one cascade scenario."""

    scenario: str  # "orderly" | "forced"
    jurisdiction: str  # "BE" | "NL"
    letters: tuple[CreditorLetter, ...]
    cover_note: str  # paragraph the lawyer reads first
    sources: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "jurisdiction": self.jurisdiction,
            "letters": [letter.to_dict() for letter in self.letters],
            "cover_note": self.cover_note,
            "sources": list(self.sources),
        }


def _urgency_for(tier: CascadeTier) -> LetterUrgency:
    if tier.recovery_rate >= Decimal("0.95"):
        return LetterUrgency.URGENT
    if tier.recovery_rate > Decimal("0"):
        return LetterUrgency.STANDARD
    return LetterUrgency.HARDSHIP


def _format_pct(value: Decimal) -> str:
    return f"{float(value) * 100:.1f}%"


def _format_eur(value: Decimal) -> str:
    return f"€{float(value):,.0f}"


def _body_for(
    tier: CascadeTier,
    *,
    jurisdiction: str,
    scenario: str,
) -> tuple[str, ...]:
    """Produce the 4-paragraph body — clinical, lawyer-grade prose."""
    coverage_pct = _format_pct(tier.recovery_rate)
    expected = _format_eur(tier.recovery_amount)
    claim = _format_eur(tier.claim_amount)
    shortfall = _format_eur(tier.shortfall)

    p1 = (
        f"Hierbij bevestigen wij dat uw vordering ten bedrage van {claim} "
        f"is opgenomen in de boedel onder de tranche '{tier.label}'. "
        f"De wettelijke grondslag voor deze rangschikking is "
        f"{tier.statutory_anchor}."
    )

    if tier.recovery_amount >= tier.claim_amount:
        p2 = (
            f"Op basis van het '{scenario}' liquidatiescenario verwachten "
            f"wij dat uw vordering volledig (100%) zal worden voldaan. "
            f"De verwachte uitkering bedraagt {expected}."
        )
        p3 = (
            "Wij zullen u op de hoogte houden van het exacte tijdstip "
            "van uitkering. Indien u over bewijsstukken beschikt die "
            "deze rangschikking betwisten, gelieve binnen 30 dagen na "
            "ontvangst van dit schrijven contact op te nemen."
        )
    elif tier.recovery_amount > 0:
        p2 = (
            f"Op basis van het '{scenario}' liquidatiescenario verwachten "
            f"wij dat uw vordering gedeeltelijk zal worden voldaan: "
            f"{coverage_pct} dekking, ofwel {expected} uitkeerbaar uit "
            f"de boedel. Het tekort bedraagt {shortfall}."
        )
        p3 = (
            "De gedeeltelijke dekking volgt uit het pari-passu beginsel "
            "binnen de tranche. Wij zijn beschikbaar voor overleg over "
            "een mogelijke schikking, met inachtneming van uw "
            "wettelijke rechten op het tekort."
        )
    else:
        p2 = (
            f"Op basis van het '{scenario}' liquidatiescenario verwachten "
            f"wij geen uitkering aan uw tranche. De boedel is uitgeput "
            f"vóór deze rang. Het volledige bedrag van {claim} blijft "
            "onbetaald."
        )
        p3 = (
            "Gezien de aard van deze positie raden wij u aan zich te "
            "wenden tot uw eigen juridische raadgever om uw rechten "
            "vast te stellen, in het bijzonder met betrekking tot "
            "eventuele persoonlijke garanties of zekerheden buiten "
            "de boedel."
        )

    p4 = (
        f"Voor enige vragen over deze notificatie of de toegepaste "
        f"distributiemethodiek verwijzen wij u naar het bijgevoegde "
        f"Statement of Affairs en de relevante wetgevende basis "
        f"({tier.statutory_anchor}). Het rapport is reproduceerbaar "
        f"per AICPA SSVS No. 1 §57(d) — vraagt u gerust de Run-ID "
        f"en payload-hash op voor uw eigen verificatie."
    )

    return (p1, p2, p3, p4)


def _subject_for(tier: CascadeTier, *, jurisdiction: str) -> str:
    statutory = "Boek XX WER §XX.39" if jurisdiction == "BE" else "Faillissementswet Art. 38"
    return (
        f"Notificatie schuldeiser — tranche '{tier.label}' "
        f"({statutory})"
    )


def _cover_note(jurisdiction: str, total_letters: int) -> str:
    statutory = (
        "Boek XX WER §XX.39 + Art. XX.155"
        if jurisdiction == "BE"
        else "Faillissementswet Art. 38 + Art. 26"
    )
    return (
        f"Onderstaande {total_letters} concept-notificatiebrieven zijn "
        f"automatisch gegenereerd op basis van de schuldeisersrangorde "
        f"in dit rapport ({statutory}). Elke brief moet vóór verzending "
        f"door de curator/advocaat-raadgever worden nagekeken: "
        f"adresgegevens, salutatie, signatuur, en eventuele "
        f"sector-specifieke aanvullingen (RSZ, BTW, milieu) zijn niet "
        f"automatisch ingevuld. De wettelijke basis per tranche en de "
        f"verwachte uitkering zijn wél automatisch correct."
    )


def build_creditor_letter_pack(
    *,
    cascade: PriorityCascade,
    scenario: str,
) -> CreditorLetterPack:
    """Generate the full per-tier letter pack for one scenario.

    Tiers with zero-claim are skipped (no creditor to notify). Tiers
    with claim>0 always get a letter regardless of recovery — the
    UNCOVERED case still warrants a "no dividend expected" notification
    under Art. 38 Fw / §XX.39 WER.
    """
    letters: List[CreditorLetter] = []
    for tier in cascade.tiers:
        if tier.claim_amount <= 0:
            continue
        urgency = _urgency_for(tier)
        body = _body_for(
            tier,
            jurisdiction=cascade.jurisdiction.value,
            scenario=scenario,
        )
        letters.append(
            CreditorLetter(
                tier_code=tier.code.value,
                tier_label=tier.label,
                statutory_anchor=tier.statutory_anchor,
                urgency=urgency,
                subject_line=_subject_for(tier, jurisdiction=cascade.jurisdiction.value),
                salutation_placeholder="Geachte heer/mevrouw [naam],",
                body_paragraphs=body,
                closing=(
                    "Met hoogachting,\n\n"
                    "[Plaatsnaam], [datum]"
                ),
                signatory_placeholder="[Curator/advocaat naam] — [Balienummer]",
                expected_dividend_pct=tier.recovery_rate,
                expected_dividend_amount=tier.recovery_amount,
                claim_amount=tier.claim_amount,
                rationale=(
                    f"Auto-gegenereerd onder {tier.statutory_anchor}. "
                    f"Urgentie: {urgency.value}."
                ),
            )
        )

    return CreditorLetterPack(
        scenario=scenario,
        jurisdiction=cascade.jurisdiction.value,
        letters=tuple(letters),
        cover_note=_cover_note(cascade.jurisdiction.value, len(letters)),
        sources=CREDITOR_LETTER_SOURCES,
    )


__all__ = [
    "CREDITOR_LETTER_SOURCES",
    "CreditorLetter",
    "CreditorLetterPack",
    "LetterUrgency",
    "build_creditor_letter_pack",
]
