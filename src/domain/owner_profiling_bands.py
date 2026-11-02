"""Owner Profiling risk-band design tokens — Jinja side.

Canonical source for the band → HSL mapping used in
`main_report/pages/owner_profiling.html` and its PDF twin. The same
table lives in:

  - `apps/mercury/design-system/tokens/owner-profiling-bands.ts`
  - `apps/venus/src/design-system/owner-profiling-bands.ts`

Cross-app parity is pinned by:

  - `apps/mercury/tests/unit/design-system/op-bands-parity.test.ts`
    (Mercury ↔ Venus)
  - `apps/valuation-iq/src/tests/test_owner_profiling_bands.py`
    (Python ↔ JS values; loads the Mercury TS module as text and
    asserts the HSL strings match this dict)

Rationale: before this module each surface inlined its own HSL triple
(see the launch audit, 2026-05-01). A future palette tune would have
silently diverged across Mercury wizard / Venus chip / Jinja report.

Adding a new band: extend BOTH this dict AND the two TS mirrors in
the same PR. The parity tests will fail otherwise.
"""

from typing import Dict, Literal

OwnerProfilingBand = Literal["good", "caution", "warn", "neutral"]

# HSL triples (no `hsl(` wrapper) — consumers wrap as needed.
# Keep these in lockstep with the TS mirrors.
OP_BAND_HSL: Dict[str, str] = {
    "good": "143, 40%, 42%",
    "caution": "37, 65%, 55%",
    "warn": "6, 55%, 50%",
    "neutral": "224, 10%, 45%",
}


def op_band_color(band: str | None, alpha: float | None = None) -> str:
    """Emit `hsl(<triple>)` or `hsl(<triple> / <alpha>)` for a band.

    Unknown / None bands fall back to ``neutral`` so a malformed
    context never blows the report. Used as a Jinja global so
    templates can write ``{{ op_band_color(owner_profiling.risk_band) }}``
    instead of inlining HSL.
    """
    triple = OP_BAND_HSL.get((band or "neutral").lower(), OP_BAND_HSL["neutral"])
    if alpha is None:
        return f"hsl({triple})"
    return f"hsl({triple} / {alpha})"


# Severity ordering — same contract as the TS mirrors.
OP_BAND_SEVERITY_ORDER: tuple[str, ...] = ("good", "neutral", "caution", "warn")
