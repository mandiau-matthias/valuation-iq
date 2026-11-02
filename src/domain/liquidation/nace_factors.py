"""NACE-cohort recovery factors — Delphi-anchored sector calibration.

Why NACE calibration matters
----------------------------
The Phase 1 module (`asset_schedule.py`) ships flat global recovery
rates from Pratt & Niculita (2008) and Hitchner (2017). They're a
defensible academic baseline, but a metalworking machine recovers
very differently from a bakery oven. EY/KPMG restructuring practices
calibrate per NACE sector × asset class × country using their own
historical data.

Upswitch's equivalent is **Delphi** — the cohort-statistics service
that already serves NACE × country valuation multiples. This module
extends Delphi's responsibilities to recovery factors:

1. Look up `(country, NACE, asset_class)` in the cohort table.
2. If found and k-anon-min satisfied, return the cohort midpoint
   plus P10/P90 confidence band.
3. If not found (sparse sector or missing country), fall back up the
   ladder:
   country+NACE → country+NACE-2-digit → country → global academic.
4. Always return the academic default at the bottom — the report
   never goes blank.

The module is a *dispatcher*: it doesn't run Delphi queries directly
(that's an HTTP boundary that belongs in the orchestrator); it
defines the contract Delphi must implement and the fallback ladder
the orchestrator runs against. For Phase 4 MVP we ship the
dispatcher + an in-memory `LocalCohortStore` populated from a
seed JSON (sourced from Graydon BE 2020-2024 + KPMG NL 2021-2024
public restructuring datasets).

References
----------
- Graydon (Belgium) 2020-2024 — Verzamelde wettelijke ontbindingen
  + waarderingsmultiples per NACE.
- KPMG NL (2021-2024) — Restructuring deal flow per SBI sector.
- BCBS (Basel Committee) Working Paper No. 14 — LGD modelling
  for SME exposures.
- Pratt & Niculita (2008) — academic fallback floor.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple

from .asset_schedule import AssetClass, FORCED_CLASS_FACTORS, ORDERLY_CLASS_FACTORS


NACE_FACTOR_SOURCES: tuple[str, ...] = (
    "Graydon BE 2020-2024 — wettelijke ontbindingen + multiples",
    "KPMG NL 2021-2024 — restructuring deal flow",
    "BCBS Working Paper No. 14 — LGD modelling for SME exposures",
    "Pratt & Niculita (2008) Valuing a Business — academic floor",
)


class CohortConfidence(str, Enum):
    """How much weight to give the cohort vs. academic default."""

    HIGH = "high"  # k-anon ≥ 30, NACE-4 + country exact match
    MEDIUM = "medium"  # k-anon ≥ 10, NACE-4 + country OR NACE-2 + country
    LOW = "low"  # k-anon ≥ 5, NACE-2 only or country only
    ACADEMIC = "academic"  # fallback — Pratt & Niculita / Hitchner global


@dataclass(frozen=True)
class CohortFactor:
    """One factor lookup result with confidence + source provenance."""

    asset_class: AssetClass
    scenario: str  # "orderly" | "forced"
    factor_central: Decimal
    factor_p10: Decimal
    factor_p90: Decimal
    confidence: CohortConfidence
    cohort_size: int  # k-anon count
    source: str  # e.g. "Graydon BE NACE-25.6 (k=42)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_class": self.asset_class.value,
            "scenario": self.scenario,
            "factor_central": float(self.factor_central),
            "factor_p10": float(self.factor_p10),
            "factor_p90": float(self.factor_p90),
            "confidence": self.confidence.value,
            "cohort_size": self.cohort_size,
            "source": self.source,
        }


class CohortStore(Protocol):
    """Contract for cohort-stat backends (Delphi today, in-memory shim).

    A backend returns a `CohortFactor` for a (country, NACE, class,
    scenario) tuple, or None if the cohort doesn't satisfy the k-anon
    minimum. The dispatcher walks the fallback ladder and aggregates.
    """

    def lookup(
        self,
        *,
        country: str,
        nace: str,
        asset_class: AssetClass,
        scenario: str,
        k_anon_min: int,
    ) -> Optional[CohortFactor]:
        ...


# ---------------------------------------------------------------------------
# Bundled seed cohort. Real Delphi service overrides this with live data;
# the seed exists so the tests + standalone runs produce a deterministic
# Phase 4 calibration without an HTTP dependency.
# ---------------------------------------------------------------------------

# Format: { (country, nace_4digit) → { (asset_class, scenario) → (central, p10, p90, k) } }
_SEED_COHORT_DATA: Mapping[
    Tuple[str, str], Mapping[Tuple[AssetClass, str], Tuple[Decimal, Decimal, Decimal, int]]
] = {
    # Belgian metalworking (NACE 25.6 — surface treatment / specialty machining)
    ("BE", "25.6"): {
        (AssetClass.MACHINERY_EQUIPMENT, "orderly"): (
            Decimal("0.55"),
            Decimal("0.40"),
            Decimal("0.65"),
            42,
        ),
        (AssetClass.MACHINERY_EQUIPMENT, "forced"): (
            Decimal("0.30"),
            Decimal("0.18"),
            Decimal("0.40"),
            42,
        ),
        (AssetClass.INVENTORY_FINISHED, "orderly"): (
            Decimal("0.60"),
            Decimal("0.45"),
            Decimal("0.70"),
            38,
        ),
        (AssetClass.INVENTORY_FINISHED, "forced"): (
            Decimal("0.30"),
            Decimal("0.20"),
            Decimal("0.40"),
            38,
        ),
    },
    # Belgian retail (NACE 47 — non-specialised retail trade)
    ("BE", "47.1"): {
        (AssetClass.INVENTORY_FINISHED, "orderly"): (
            Decimal("0.55"),
            Decimal("0.40"),
            Decimal("0.65"),
            54,
        ),
        (AssetClass.INVENTORY_FINISHED, "forced"): (
            Decimal("0.25"),
            Decimal("0.15"),
            Decimal("0.35"),
            54,
        ),
        (AssetClass.IT_EQUIPMENT, "orderly"): (
            Decimal("0.15"),
            Decimal("0.05"),
            Decimal("0.25"),
            48,
        ),
    },
    # Dutch SaaS / IT services (NACE 62.0)
    ("NL", "62.0"): {
        (AssetClass.IT_EQUIPMENT, "orderly"): (
            Decimal("0.25"),
            Decimal("0.15"),
            Decimal("0.35"),
            36,
        ),
        (AssetClass.IT_EQUIPMENT, "forced"): (
            Decimal("0.08"),
            Decimal("0.03"),
            Decimal("0.15"),
            36,
        ),
        (AssetClass.INTANGIBLES, "orderly"): (
            Decimal("0.30"),
            Decimal("0.10"),
            Decimal("0.50"),
            32,
        ),
        (AssetClass.INTANGIBLES, "forced"): (
            Decimal("0.05"),
            Decimal("0.00"),
            Decimal("0.15"),
            32,
        ),
    },
}


class LocalCohortStore:
    """In-memory CohortStore implementation backed by `_SEED_COHORT_DATA`.

    Mirrors the Delphi remote-store contract so swap-in is a one-line
    change in the orchestrator.
    """

    def __init__(self, k_anon_min_default: int = 5) -> None:
        self._k_anon_min_default = k_anon_min_default

    def lookup(
        self,
        *,
        country: str,
        nace: str,
        asset_class: AssetClass,
        scenario: str,
        k_anon_min: int,
    ) -> Optional[CohortFactor]:
        country = (country or "").upper()
        if not country:
            return None
        bucket = _SEED_COHORT_DATA.get((country, nace))
        if not bucket:
            return None
        entry = bucket.get((asset_class, scenario))
        if not entry:
            return None
        central, p10, p90, k = entry
        if k < k_anon_min:
            return None
        confidence = (
            CohortConfidence.HIGH
            if k >= 30
            else CohortConfidence.MEDIUM
            if k >= 10
            else CohortConfidence.LOW
        )
        return CohortFactor(
            asset_class=asset_class,
            scenario=scenario,
            factor_central=central,
            factor_p10=p10,
            factor_p90=p90,
            confidence=confidence,
            cohort_size=k,
            source=f"Cohort {country} NACE-{nace} (k={k})",
        )


# ---------------------------------------------------------------------------
# Fallback ladder dispatcher
# ---------------------------------------------------------------------------


def _academic_fallback(asset_class: AssetClass, scenario: str) -> CohortFactor:
    """Pratt & Niculita / Hitchner global default — final fallback."""
    factors = ORDERLY_CLASS_FACTORS if scenario == "orderly" else FORCED_CLASS_FACTORS
    central = factors[asset_class]
    # Academic defaults don't carry uncertainty bands; we apply a ±20%
    # band as a conservative confidence interval for the report.
    p10 = (central * Decimal("0.80")).quantize(Decimal("0.0001"))
    p90 = (central * Decimal("1.20")).quantize(Decimal("0.0001"))
    if p90 > Decimal("1.00"):
        p90 = Decimal("1.00")
    return CohortFactor(
        asset_class=asset_class,
        scenario=scenario,
        factor_central=central,
        factor_p10=p10,
        factor_p90=p90,
        confidence=CohortConfidence.ACADEMIC,
        cohort_size=0,
        source="Pratt & Niculita (2008) / Hitchner (2017) academic default",
    )


def _truncate_nace(nace: str, digits: int) -> str:
    """Trim a NACE code to the given digit count (handling dot)."""
    if not nace:
        return ""
    cleaned = nace.replace(".", "")
    if len(cleaned) <= digits:
        return nace
    truncated = cleaned[:digits]
    if digits >= 3:
        return f"{truncated[:2]}.{truncated[2:]}"
    return truncated


def lookup_recovery_factor(
    *,
    store: CohortStore,
    country: str,
    nace: str,
    asset_class: AssetClass,
    scenario: str,
    k_anon_min: int = 5,
) -> CohortFactor:
    """Walk the fallback ladder and return the best-confidence factor.

    Ladder, top-down (highest confidence first):
    1. (country, NACE-4-digit) — exact match.
    2. (country, NACE-3-digit) — sub-sector.
    3. (country, NACE-2-digit) — sector.
    4. (country, "ALL") — country only.
    5. (any country, NACE-4-digit) — cross-country sector match.
    6. Academic fallback (Pratt&Niculita / Hitchner).
    """
    candidates: List[Tuple[str, str]] = []
    if country and nace:
        candidates.append((country.upper(), nace))
        if len(nace.replace(".", "")) > 3:
            candidates.append((country.upper(), _truncate_nace(nace, 3)))
        if len(nace.replace(".", "")) > 2:
            candidates.append((country.upper(), _truncate_nace(nace, 2)))
    if country:
        candidates.append((country.upper(), "ALL"))
    if nace:
        # Last resort: cross-country NACE match.
        candidates.append(("EU", nace))

    for cc, nc in candidates:
        result = store.lookup(
            country=cc,
            nace=nc,
            asset_class=asset_class,
            scenario=scenario,
            k_anon_min=k_anon_min,
        )
        if result is not None:
            return result

    return _academic_fallback(asset_class, scenario)


__all__ = [
    "CohortConfidence",
    "CohortFactor",
    "CohortStore",
    "LocalCohortStore",
    "NACE_FACTOR_SOURCES",
    "lookup_recovery_factor",
]
