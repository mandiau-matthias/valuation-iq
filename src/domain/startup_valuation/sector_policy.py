"""Sector ↔ method consistency policy.

Two startup-valuation methods are sector-sensitive in a way the rest of
the engine deliberately abstracts away:

* **SaaS Forward Multiple** — produces a defensible number for
  *recurring-revenue* companies (B2B SaaS, subscription fintech,
  certain deeptech-AI products).  Applying it to a marketplace,
  consumer brand or hardware company produces a meaningless number
  because the underlying ARR construct doesn't apply.

* **VC Method exit multiple** — already sector-aware via
  :func:`get_sector_defaults` in :mod:`.regional_data`, so no extra
  policy is needed here; that module is the single source of truth.

This module owns the *yes/no* gate for the SaaS Forward leg.  Centralised
here so the synthesis blender + the report context builder + the future
methodology-recommendation engine all read from one place.

Calibration sources:
  * Atomico SoEU 2024, Dealroom Benelux 2024 — only the SaaS / Fintech /
    Deeptech-AI sectors show enough recurring-revenue exit data to
    support the SaaS Forward multiple at pre-seed scale.
  * Index Ventures, Point Nine, Seedcamp — concur that applying the
    forward multiple outside these sectors fits to noise.
"""

from __future__ import annotations

from typing import FrozenSet, Optional

from .schemas import StartupSector


#: Sectors for which the SaaS Forward multiple produces a defensible
#: pre-money number.  Empirically the only sectors where forward 12-mo
#: ARR × multiple survives partner-level scrutiny.  Marketplace is
#: deliberately excluded — marketplace revenue is take-rate × GMV and
#: trades on a fundamentally different multiple shape.
SAAS_FORWARD_COMPATIBLE_SECTORS: FrozenSet[StartupSector] = frozenset(
    # Vertical-AI workflow plays are recurring-revenue at their core —
    # Casetext / Harvey / AlphaSense all priced on forward ARR × multiple
    # at growth, so the SaaS Forward leg is the right lens for the
    # pre-seed/seed-band early-revenue case.
    {"saas", "fintech", "deeptech_ai", "vertical_ai"}
)


def is_saas_forward_compatible(sector: Optional[str]) -> bool:
    """Return ``True`` when the SaaS Forward leg applies to ``sector``.

    Lenient against missing input — when the sector is unknown we
    return ``False`` (the method opts out, the founder report explains
    why).  This matches the principle "no number is better than a
    wrong number" — silent fallback to "saas" would let a hardware
    company get a SaaS multiple.
    """
    if not sector:
        return False
    return sector in SAAS_FORWARD_COMPATIBLE_SECTORS


def saas_forward_skip_reason(sector: Optional[str]) -> str:
    """Localized (Dutch) one-liner for why the SaaS Forward leg was skipped.

    Surfaced in the report's defensibility section so the founder isn't
    left guessing.  Stays consistent with the "geen … opgegeven" /
    "niet van toepassing" convention used elsewhere in the engine.
    """
    if not sector:
        return (
            "SaaS Forward methode niet toegepast — sector niet bepaald "
            "(geef een sector op om deze leg te activeren)."
        )
    return (
        f"SaaS Forward methode niet toegepast — sector '{sector}' is geen "
        "recurring-revenue SaaS / Fintech / Deeptech-AI."
    )


__all__ = [
    "SAAS_FORWARD_COMPATIBLE_SECTORS",
    "is_saas_forward_compatible",
    "saas_forward_skip_reason",
]
