"""Working-Capital Peg — F5 Part A (BET-245).

Pure math that computes the working-capital target a buyer should
leave behind at closing. SME advisors regularly skip this calculation
and lose 5-10% of EV in post-closing adjustments. We compute it
defensibly, with provenance.

Calculation (per Damodaran "Investment Valuation" Ch. 25 + standard
SME M&A practice):

    WC_peg = 12-month mean of operating NWC

    operating_NWC = (receivables + inventory + prepaid_expenses)
                  − (payables + accrued_expenses + deferred_revenue)

We deliberately EXCLUDE cash + shareholder loans + interest-bearing
debt from both sides — those are deal-financing items, not working
capital. The peg is a working-capital number, not a cash/debt number.

Confidence ladder:
    'high'   — ≥12 monthly NWC points present, recent (last point
               within 90 days of `as_of`)
    'medium' — 6-11 monthly points present, OR 12+ months with last
               point >90 days stale, OR derived from quarterly
    'low'    — only annual data; we average 3-year annual NWC

Output is a dataclass `WCPegResult`:
    target_eur          — single peg number
    band_low_eur        — target × 0.9
    band_high_eur       — target × 1.1
    monthly_series      — input series passed through (for seasonality chart)
    derived_from        — 'monthly_ledger_signals' | 'annual_fallback'
    confidence          — 'high' | 'medium' | 'low'
    one_liner           — caregiver-tone advisor-facing narrative
    provenance_notes    — list[str] for audit footnote

Pure: same inputs → same outputs. No I/O. No global state. No
`datetime.now()` — callers pass `as_of` for determinism.

Anti-scope (per BET-247):
    - No advisor judgement (override is Mercury/Titan layer)
    - No SPA wording (Legora territory)
    - No tax treatment (covered by tax_latency.py sibling)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Literal, Optional

# ---------------------------------------------------------------------
# Configuration constants — locked for v1
# ---------------------------------------------------------------------

#: ±10% band per F5 spec — buyer/seller negotiate within this range.
PEG_BAND_PCT: float = 0.10

#: Months of monthly data needed for 'high' confidence.
HIGH_CONFIDENCE_MONTHS: int = 12

#: Months of monthly data needed for 'medium' confidence.
MEDIUM_CONFIDENCE_MIN_MONTHS: int = 6

#: Max staleness for 'high' confidence — most recent monthly point
#: must be within this many days of `as_of`.
HIGH_CONFIDENCE_FRESHNESS_DAYS: int = 90

#: Years of annual NWC needed for annual fallback.
ANNUAL_FALLBACK_MIN_YEARS: int = 3


# ---------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class MonthlyNWCPoint:
    """One month-end snapshot of operating NWC components.

    Components are in EUR. Cash + shareholder loans + interest-bearing
    debt are explicitly NOT here — caller filters them upstream.
    """

    month: str  # ISO yyyy-MM
    receivables: float
    inventory: float
    prepaid_expenses: float
    payables: float
    accrued_expenses: float
    deferred_revenue: float

    @property
    def nwc(self) -> float:
        operating_assets = self.receivables + self.inventory + self.prepaid_expenses
        operating_liabilities = self.payables + self.accrued_expenses + self.deferred_revenue
        return operating_assets - operating_liabilities


@dataclass(frozen=True)
class AnnualNWCPoint:
    """Year-end NWC snapshot for the annual fallback path.

    Same exclusion rules as `MonthlyNWCPoint`. Used when only annual
    accounts are available (no Hermes monthly feed).
    """

    year: int
    nwc: float


# ---------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------


WCPegDerivedFrom = Literal["monthly_ledger_signals", "annual_fallback"]
WCPegConfidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class WCPegResult:
    """Output of `compute_wc_peg`. Drives the F1 `WCPegRender` payload."""

    target_eur: int
    band_low_eur: int
    band_high_eur: int
    monthly_series: List[MonthlyNWCPoint]
    derived_from: WCPegDerivedFrom
    confidence: WCPegConfidence
    one_liner: str
    provenance_notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# Confidence assessment
# ---------------------------------------------------------------------


def _months_between(earlier_iso: str, later_iso: str) -> int:
    """Inclusive month count between two yyyy-MM ISO strings.

    Used to detect gaps in monthly series. Not a calendar library —
    just a defensible approximation.
    """
    e_year, e_month = (int(p) for p in earlier_iso.split("-")[:2])
    l_year, l_month = (int(p) for p in later_iso.split("-")[:2])
    return (l_year - e_year) * 12 + (l_month - e_month) + 1


def _is_fresh(latest_month_iso: str, as_of: datetime, max_days: int) -> bool:
    """Returns True if the latest monthly point is within `max_days` of `as_of`.

    Approximation: we treat the month as ending on the 28th to avoid
    short-month off-by-one. Defensible because confidence buckets are
    coarse-grained.
    """
    year, month = (int(p) for p in latest_month_iso.split("-")[:2])
    month_end = datetime(year=year, month=month, day=28)
    return (as_of - month_end).days <= max_days


def _assess_confidence_monthly(
    monthly_series: List[MonthlyNWCPoint],
    as_of: datetime,
) -> WCPegConfidence:
    """Confidence based on monthly-series quality."""
    n = len(monthly_series)
    if n == 0:
        # Caller should have routed to annual fallback; defensive.
        return "low"
    sorted_months = sorted(p.month for p in monthly_series)
    latest = sorted_months[-1]
    fresh = _is_fresh(latest, as_of, HIGH_CONFIDENCE_FRESHNESS_DAYS)
    if n >= HIGH_CONFIDENCE_MONTHS and fresh:
        return "high"
    if n >= MEDIUM_CONFIDENCE_MIN_MONTHS:
        return "medium"
    return "low"


# ---------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------


def _mean_nwc_monthly(monthly_series: List[MonthlyNWCPoint]) -> float:
    if not monthly_series:
        raise ValueError("Cannot compute monthly mean from empty series.")
    total = sum(p.nwc for p in monthly_series)
    return total / len(monthly_series)


def _mean_nwc_annual(annual_series: List[AnnualNWCPoint]) -> float:
    if not annual_series:
        raise ValueError("Cannot compute annual mean from empty series.")
    return sum(p.nwc for p in annual_series) / len(annual_series)


def _build_one_liner(
    target_eur: int,
    confidence: WCPegConfidence,
    derived_from: WCPegDerivedFrom,
) -> str:
    """Caregiver-tone narrative for the IM. Per F1/A0 voice baseline.

    No superlatives. No "best/only/leading". Explains what the number
    means in M&A-practical terms.
    """
    formatted = f"€{target_eur:,.0f}"
    base = (
        f"Working capital peg target: {formatted}. "
        "Below this and the buyer claws back from the purchase price; "
        "above this and the seller leaves cash on the table."
    )
    if confidence == "low" or derived_from == "annual_fallback":
        return f"{base} Based on annual averages — advisor review recommended before legal handoff."
    if confidence == "medium":
        return f"{base} Confidence: medium (partial monthly history)."
    return base


def compute_wc_peg(
    monthly_series: Optional[List[MonthlyNWCPoint]],
    annual_series: Optional[List[AnnualNWCPoint]],
    as_of: datetime,
) -> Optional[WCPegResult]:
    """Compute the working-capital peg.

    Routing:
        1. If `monthly_series` has ≥6 points → use monthly mean (high or
           medium confidence based on series quality).
        2. Else if `annual_series` has ≥3 points → annual-fallback path
           (low confidence — advisor narrative recommended).
        3. Else returns `None` — caller renders an empty-state in the IM.

    Args:
        monthly_series: month-end NWC points. May be `None` or empty.
        annual_series: year-end NWC points (fallback). May be `None` or empty.
        as_of: reference date for staleness check. Caller-supplied for
            test determinism.

    Returns:
        `WCPegResult` or `None` if data is insufficient.
    """
    monthly = monthly_series or []
    annual = annual_series or []
    provenance_notes: List[str] = []

    # Path 1: monthly signals
    if len(monthly) >= MEDIUM_CONFIDENCE_MIN_MONTHS:
        # Sort by month-iso so the seasonality chart renders in order.
        monthly_sorted = sorted(monthly, key=lambda p: p.month)
        confidence = _assess_confidence_monthly(monthly_sorted, as_of)
        target = _mean_nwc_monthly(monthly_sorted)
        provenance_notes.append(
            f"Computed from {len(monthly_sorted)}-month NWC mean; "
            f"window {monthly_sorted[0].month}…{monthly_sorted[-1].month}."
        )
        derived_from: WCPegDerivedFrom = "monthly_ledger_signals"
    elif len(annual) >= ANNUAL_FALLBACK_MIN_YEARS:
        confidence = "low"
        target = _mean_nwc_annual(annual)
        provenance_notes.append(
            f"Computed from {len(annual)}-year annual NWC mean (no monthly feed). "
            "Confidence: low — recommend collecting monthly data before legal handoff."
        )
        derived_from = "annual_fallback"
        monthly_sorted = []
    else:
        # Neither path satisfies the minimum data threshold.
        return None

    target_int = int(round(target))
    band_low = int(round(target * (1.0 - PEG_BAND_PCT)))
    band_high = int(round(target * (1.0 + PEG_BAND_PCT)))

    return WCPegResult(
        target_eur=target_int,
        band_low_eur=band_low,
        band_high_eur=band_high,
        monthly_series=monthly_sorted,
        derived_from=derived_from,
        confidence=confidence,
        one_liner=_build_one_liner(target_int, confidence, derived_from),
        provenance_notes=provenance_notes,
    )


__all__ = [
    "ANNUAL_FALLBACK_MIN_YEARS",
    "AnnualNWCPoint",
    "HIGH_CONFIDENCE_FRESHNESS_DAYS",
    "HIGH_CONFIDENCE_MONTHS",
    "MEDIUM_CONFIDENCE_MIN_MONTHS",
    "MonthlyNWCPoint",
    "PEG_BAND_PCT",
    "WCPegConfidence",
    "WCPegDerivedFrom",
    "WCPegResult",
    "compute_wc_peg",
]
