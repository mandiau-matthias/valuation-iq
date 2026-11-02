"""Sufficiency, creditor-letter, buyer-scenario, and independence copy."""

from __future__ import annotations

from typing import Dict


def build_creditor_buyer_translations() -> Dict[str, Dict[str, str]]:
    """Return sufficiency, creditor-letter, buyer-scenario, and independence copy."""
    return {
        # ---------------------------------------------------------------
        # Phase 5 — Sufficiency Memo (Section 05a)
        # ---------------------------------------------------------------
        "sufficiency_section_title": {
            "nl": "Sufficiency Memo — kan de boedel elke tranche dekken?",
            "en": "Sufficiency Memo — can the estate cover each tier?",
        },
        "sufficiency_section_subtitle": {
            "nl": "Lawyer's first question — yes/no per tranche, EY/KPMG-format",
            "en": "Lawyer's first question — yes/no per tier, EY/KPMG format",
        },
        "sufficiency_col_tier": {"nl": "Rang", "en": "Tier"},
        "sufficiency_col_anchor": {"nl": "Wettelijke basis", "en": "Statutory anchor"},
        "sufficiency_col_claim": {"nl": "Vordering", "en": "Claim"},
        "sufficiency_col_recovery": {"nl": "Uitgekeerd", "en": "Recovered"},
        "sufficiency_col_coverage": {"nl": "Dekking", "en": "Coverage"},
        "sufficiency_col_verdict": {"nl": "Verdict", "en": "Verdict"},
        "sufficiency_verdict_paid_in_full": {
            "nl": "Volledig voldaan",
            "en": "Paid in full",
        },
        "sufficiency_verdict_partial": {
            "nl": "Gedeeltelijk",
            "en": "Partial",
        },
        "sufficiency_verdict_uncovered": {
            "nl": "Niet gedekt",
            "en": "Uncovered",
        },
        "sufficiency_headline_coverage": {
            "nl": "Headline dekking (totaal uitgekeerd / totaal vorderingen)",
            "en": "Headline coverage (total recovered / total claims)",
        },
        "sufficiency_deepest_paid": {
            "nl": "Diepste volledig voldane tranche",
            "en": "Deepest tier paid in full",
        },
        "sufficiency_estate_exhausted_at": {
            "nl": "Boedel uitgeput vanaf",
            "en": "Estate exhausted at",
        },
        # ---------------------------------------------------------------
        # Phase 5 — Creditor Letters (Section 11)
        # ---------------------------------------------------------------
        "creditor_letters_section_title": {
            "nl": "Concept-notificatiebrieven schuldeisers",
            "en": "Auto-drafted creditor notification letters",
        },
        "creditor_letters_section_subtitle": {
            "nl": "Boek XX WER §XX.39 (BE) / Faillissementswet Art. 38 (NL) format",
            "en": "Boek XX WER §XX.39 (BE) / Faillissementswet Art. 38 (NL) format",
        },
        "creditor_letters_cover_label": {
            "nl": "Toelichting voor de curator/advocaat",
            "en": "Note for curator/counsel",
        },
        "creditor_letters_subject": {"nl": "Onderwerp", "en": "Subject"},
        "creditor_letters_urgency_urgent": {
            "nl": "Urgent — volledige uitkering verwacht",
            "en": "Urgent — full payment expected",
        },
        "creditor_letters_urgency_standard": {
            "nl": "Standaard — gedeeltelijke uitkering",
            "en": "Standard — partial payment",
        },
        "creditor_letters_urgency_hardship": {
            "nl": "Hardship — geen uitkering verwacht",
            "en": "Hardship — no payment expected",
        },
        "creditor_letters_expected_dividend": {
            "nl": "Verwachte uitkering",
            "en": "Expected dividend",
        },
        # ---------------------------------------------------------------
        # Phase 5 — Strategic Buyer Scenarios (Section 00c)
        # ---------------------------------------------------------------
        "buyer_scenarios_section_title": {
            "nl": "Bid-band per koperprofiel — M&A onderhandelingsanker",
            "en": "Bid band by buyer profile — M&A negotiation anchor",
        },
        "buyer_scenarios_section_subtitle": {
            "nl": "McKinsey Ch. 18 + Damodaran Ch. 24 — financieel / strategisch / MBO",
            "en": "McKinsey Ch. 18 + Damodaran Ch. 24 — financial / strategic / MBO",
        },
        "buyer_scenarios_floor": {"nl": "Bod-vloer", "en": "Bid floor"},
        "buyer_scenarios_anchor": {"nl": "Anker (mid-point)", "en": "Anchor (mid-point)"},
        "buyer_scenarios_ceiling": {"nl": "Bod-plafond", "en": "Bid ceiling"},
        "buyer_scenarios_lv_multiplier": {
            "nl": "× liquidatie-vloer",
            "en": "× liquidation floor",
        },
        # ---------------------------------------------------------------
        # Phase 5 — Independence + Conflicts Disclosure (extends Section 10)
        # ---------------------------------------------------------------
        "disclosure_independence_title": {
            "nl": "Onafhankelijkheidsverklaring",
            "en": "Independence Statement",
        },
        "disclosure_conflicts_title": {
            "nl": "Belangenconflict-verklaring",
            "en": "Conflicts Disclosure",
        },
    }
