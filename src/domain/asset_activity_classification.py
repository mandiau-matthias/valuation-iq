"""
Activity-code and industry-tag classification for asset-heavy entities.

These predicates intentionally stay separate from adjusted-NAV calculation so
methodology routing can use the same canonical activity rules without importing
the full NAV support module.
"""

from typing import Optional


def is_holding_company_activity(activity_code: str) -> bool:
    """UNAMBIGUOUS financial-holding NACE activities, valued via balance-sheet NAV:
    64.2x = activities of holding companies. A pure financial holding holds
    participations and has no operating P&L of its own, so NAV is always the right
    primary anchor.

    NACE 70.10 ('activities of head offices') is deliberately NOT matched here.
    70.10 is ambiguous between a pure holding and an operating management/service
    company that bills genuine fees (BE bestuursvennootschap, NL SBI 70102
    'concerndiensten'); routing it on the code alone would value a fee-earning
    operator on its thin net assets (audit 2026-06-11, reversing F36's over-route).
    70.10 is handled by `is_ambiguous_head_office_activity` + the financials in the
    methodology determiner, never as a hard NACE gate."""
    if not activity_code:
        return False
    normalized_digits = activity_code.replace(".", "")
    return activity_code.startswith("64.2") or normalized_digits.startswith("642")


# Industry-tag aliases that UNAMBIGUOUSLY mark an entity as patrimonium /
# real-estate asset-holding — value flows from the balance sheet, so these route
# to NAV / income-capitalisation regardless of the request methodology.
#
# Bare "holding"/"holding_company" are deliberately EXCLUDED (audit 2026-06-11,
# reversing F35): the label alone is ambiguous between a pure holding (NAV) and an
# operating management/service company that bills real management fees (BE
# bestuursvennootschap, NL SBI 70102), which must be valued on its earnings.
# A bare holding tag is routed by `is_ambiguous_head_office_activity` + the
# financials in the methodology determiner, not hard-gated here. Pure FINANCIAL
# holdings are captured by NACE 64.2x (`is_holding_company_activity`) once
# enrichment has run.
#
# NACE 68.31/68.32 (real-estate agencies, property management) are operating
# businesses and intentionally excluded — they route via regular multiples.
_ASSET_HEAVY_INDUSTRY_TAGS: frozenset[str] = frozenset(
    {
        "real_estate_holding",
        "patrimony",
        "patrimonium",
        "vastgoed",
    }
)


def _normalize_industry_tag(industry: Optional[str]) -> str:
    if not industry:
        return ""
    return industry.strip().lower().replace("-", "_").replace(" ", "_")


def is_real_estate_holding_activity(activity_code: str) -> bool:
    """NACE 68.10 (buying/selling own real estate) and 68.20 (renting/operating own
    or leased real estate) are real-estate asset-holding activities — value flows
    from balance-sheet NAV, not P&L multiples. NACE 68.31/68.32 (agencies / property
    management) are operating businesses and excluded."""
    if not activity_code:
        return False
    normalized_digits = activity_code.replace(".", "").replace(" ", "")
    return normalized_digits.startswith("6810") or normalized_digits.startswith("6820")


def is_asset_heavy_holding_activity(
    activity_code: Optional[str] = None,
    industry: Optional[str] = None,
) -> bool:
    """Detect financial-holding and real-estate-asset-holding entities that should
    be valued primarily via balance-sheet NAV rather than P&L multiples.

    True when ANY of:
      - NACE 64.2x (financial holding companies)
      - NACE 68.10 or 68.20 (real-estate ownership / operation)
      - `industry` is one of: real_estate_holding, patrimony, patrimonium,
        vastgoed, holding_company, holding (after hyphen/space normalisation)

    The industry-tag fallback exists for cases where NACE has not yet been
    enriched on the request (manual Mercury entry, advisor connector flow
    that skipped registry lookup). Once Hermes / KBO / KVK enrichment runs
    the NACE branch becomes the canonical signal."""
    if is_holding_company_activity(activity_code or ""):
        return True
    if is_real_estate_holding_activity(activity_code or ""):
        return True
    normalized_industry = _normalize_industry_tag(industry)
    if normalized_industry and normalized_industry in _ASSET_HEAVY_INDUSTRY_TAGS:
        return True
    return False


def is_ambiguous_head_office_activity(
    activity_code: Optional[str] = None,
    industry: Optional[str] = None,
) -> bool:
    """NACE 70.10 ('activities of head offices') and a bare 'holding' /
    'holding_company' industry tag are AMBIGUOUS: the same code/label covers both
    a pure holding (value = NAV of its participations) and an operating
    management/service company — the Belgian bestuursvennootschap, or NL SBI 70102
    'concerndiensten binnen eigen concern' — that bills genuine management fees and
    must be valued on its earnings. The code alone cannot tell them apart; only the
    financials can.

    The methodology determiner uses this predicate to route the class to NAV ONLY
    when the balance sheet confirms net assets dominate the earnings stream
    (`is_net_asset_dominant`), and to operating multiples otherwise. It is
    intentionally NOT folded into `is_asset_heavy_holding_activity`, so the Delphi
    benchmark-contract preflight still requires a trusted contract for these
    requests — the engine may legitimately value them on multiples."""
    normalized_digits = (activity_code or "").replace(".", "").replace(" ", "")
    if normalized_digits.startswith("7010"):
        return True
    return _normalize_industry_tag(industry) in ("holding", "holding_company")
