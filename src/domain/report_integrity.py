"""Report-integrity warning constructors — single source of truth.

Pass-8 launch-readiness:
This module is the *only* place where "must-disclose" warnings are
constructed. Engine code paths (orchestrators, calculators, validators)
import these factories and append their output to either:

  - a step's ``result["data_quality_warnings"]`` list, OR
  - a step's ``metadata["quality_warning"]`` field, OR
  - the ``detailed_results["data_quality_warnings"]`` rollup directly.

The response_builder's ``_aggregate_quality_warnings`` walks all three
paths, so any of them works. Whichever lives closest to the offending
code is preferred — keep the warning physically near its trigger so
future readers find the rationale without searching.

Each warning is a dict with at minimum:
  - ``type``       : machine-readable id; matches the aggregator catalog.
  - ``severity``   : "high" | "medium" | "low"; "high" promotes the
                     warning to the Page-1 callout. Integrity flags are
                     always "high" because they describe limitations the
                     reader must know to evaluate the report.
  - ``message``    : English copy (engine-side telemetry). Aggregator
                     swaps to localized copy via the catalog when rendering.
  - ``recommendation``: actionable next step for the user/advisor.
  - ``details``    : (optional) structured payload for debugging.

The integrity warnings are designed to be *idempotent* and *additive* —
they cannot break a valuation calculation, only annotate its output.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# ── public factories ─────────────────────────────────────────────────


def build_method_substitution_warning(
    *,
    requested_method: str,
    executed_method: str,
    reason: Optional[str] = None,
    extra_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Emitted when the executed method differs from what the user requested.

    Example: user picks ``adjusted_nav`` but balance-sheet inputs are missing,
    so the engine falls back to multiples. The reader of the PDF must be told.
    """
    details = {
        "requested_method": requested_method,
        "executed_method": executed_method,
        "engine_reason": reason,
    }
    if isinstance(extra_details, dict):
        details.update(extra_details)

    return {
        "type": "method_substitution",
        "severity": "high",
        "message": (
            f"Requested valuation method '{requested_method}' was substituted "
            f"with '{executed_method}'."
        ),
        "recommendation": (
            "Provide the inputs required by the requested method "
            "(typically balance-sheet data for NAV) and re-run, "
            "or explicitly confirm the substitute method is acceptable."
        ),
        "details": details,
    }


def build_net_debt_unavailable_warning() -> Dict[str, Any]:
    """Emitted when Step 7 had to assume net debt = 0 because no balance sheet
    data was provided. The EV→Equity bridge is then a proxy, not auditable.
    """
    return {
        "type": "net_debt_unavailable",
        "severity": "high",
        "message": (
            "No balance-sheet data was provided. Net debt was assumed to be "
            "zero and operating-cash exemption was applied via a revenue proxy."
        ),
        "recommendation": (
            "Add total debt and cash positions (or import the filed accounts) "
            "before sharing this report externally — the EV→Equity bridge is "
            "not audit-defensible without them."
        ),
        "details": {
            "step_number": 7,
        },
    }


def build_owner_compensation_estimated_warning(
    *,
    estimated_compensation: float,
    estimation_method: str,
) -> Dict[str, Any]:
    """Emitted when Step 2.5 had to auto-estimate owner compensation.

    For owner-led SMEs (≤2 owner-managers, ≤10 FTE) this is typically the
    largest normalization item, and an estimate is materially less defensible
    than a real input.
    """
    return {
        "type": "owner_compensation_estimated",
        "severity": "high",
        "message": (
            f"Owner compensation was not provided; the engine estimated "
            f"€{estimated_compensation:,.0f} using {estimation_method}."
        ),
        "recommendation": (
            "Enter the actual owner salary paid (or the market replacement "
            "cost) so normalized EBITDA is defensible."
        ),
        "details": {
            "estimated_compensation": estimated_compensation,
            "estimation_method": estimation_method,
            "step_number": 2.5,
        },
    }


def build_ebitda_benchmark_deviation_warning(
    *,
    actual_margin_pct: float,
    expected_margin_pct: float,
    direction: str,
    actual_margin_basis: Optional[str] = None,
) -> Dict[str, Any]:
    """Emitted when EBITDA margin diverges materially from a MEASURED sector median.

    ``direction`` is "lower" or "higher"; margins are fractions (0.10 = 10%).

    Step 2 builds this from the same measurement as its graded
    ``industry_margin_deviation`` warning, and only when the sector band is a
    measured distribution (``benchmark_margin_provenance``). A derived,
    curated or hand-set band is context, never grounds for a must-disclose
    flag. ``actual_margin_basis`` names the earnings basis of
    ``actual_margin_pct`` so it is provably the published margin.
    """
    delta_pp = abs(actual_margin_pct - expected_margin_pct)
    details: Dict[str, Any] = {
        "actual_margin_pct": actual_margin_pct,
        "expected_margin_pct": expected_margin_pct,
        "deviation_direction": direction,
        "deviation_pp": delta_pp,
        "benchmark_measured": True,
    }
    if actual_margin_basis:
        details["actual_margin_basis"] = actual_margin_basis
    return {
        "type": "ebitda_benchmark_deviation",
        "severity": "high",
        "message": (
            f"EBITDA margin {actual_margin_pct:.1%} is {direction} than the "
            f"sector median ({expected_margin_pct:.1%}); deviation "
            f"{delta_pp:.1%} percentage points."
        ),
        "recommendation": (
            "Document the reason for the deviation (owner salary, one-offs, "
            "structural difference) or add a normalization line."
        ),
        "details": details,
    }


def build_book_equity_unavailable_warning() -> Dict[str, Any]:
    """Emitted when the Belgian fiscal-reference page is requested but the
    book equity term is missing — the statutory formula cannot close.
    """
    return {
        "type": "book_equity_unavailable",
        "severity": "high",
        "message": (
            "Book equity not provided — the Belgian fiscal-reference value "
            "cannot be fully calculated. The EBITDA component is shown "
            "separately as a partial figure."
        ),
        "recommendation": (
            "Add total_equity (or total_assets and total_debt) from the "
            "latest filed accounts so the statutory formula renders fully."
        ),
        "details": {},
    }


def build_impossible_margin_warning(
    *,
    year: int,
    ebitda: float,
    revenue: float,
    margin_pct: float,
    is_weighted: bool,
) -> Dict[str, Any]:
    """Emitted when a year's normalized EBITDA margin is ≥ 100% of revenue.

    A margin ≥ 100% means normalized EBITDA ≥ revenue, which is mathematically
    impossible for an operating company. Common causes:
      - Reporting error (wrong column mapped to EBITDA)
      - Aggressive normalizations that over-correct
      - Operating company with property/IP that contributes income without
        being captured in revenue (in which case the right fix is a carve-out,
        not the displayed margin)

    ``is_weighted`` distinguishes years inside the McKinsey weighting window
    (top 3 most recent) from older years that don't currently feed the
    multiple — both are flagged, but the recommendation differs.
    """
    return {
        "type": "impossible_margin",
        "severity": "high",
        "message": (
            f"FY{year} normalized EBITDA margin {margin_pct:.1f}% "
            f"exceeds 100% (€{ebitda:,.0f} on €{revenue:,.0f} revenue) — "
            f"mathematically impossible for an operating company."
        ),
        "recommendation": (
            "Verify the EBITDA mapping for this year; check for "
            "over-aggressive normalizations or income classified outside "
            "revenue (rental, intercompany, property). If the year is "
            "weighted into the multiple, the headline cannot be defended "
            "until this is resolved."
        ),
        "details": {
            "year": year,
            "ebitda": ebitda,
            "revenue": revenue,
            "margin_pct": margin_pct,
            "is_weighted_year": is_weighted,
        },
    }


# ── private helpers ──────────────────────────────────────────────────


_INTEGRITY_TYPES = frozenset({
    "method_substitution",
    "net_debt_unavailable",
    "owner_compensation_estimated",
    "ebitda_benchmark_deviation",
    "book_equity_unavailable",
    "impossible_margin",
})


def is_integrity_warning(warning: Any) -> bool:
    """True if a warning dict represents a methodological-integrity flag.

    Used by the aggregator to force the Page-1 callout ON whenever any of
    these surface, regardless of the default ``show_quality_warnings_callout``
    state.
    """
    if not isinstance(warning, dict):
        return False
    return warning.get("type") in _INTEGRITY_TYPES
