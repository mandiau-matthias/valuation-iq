"""Sellability MVP — €-impact computation (BET-204 / A2 chunk 3).

Pure-functional, stateless helpers. No I/O, no DB, no HTTP.

Architecture (Brain & Muscle):
    Titan (Brain) reads Delphi multiples via Prisma and the Sellability score
    via `compute_sellability_score()` in `key-man-score.util.ts`'s sibling
    `sellability-score.util.ts`. Titan then calls into this module via the
    existing PythonEngineService HTTP path, passing the multiple, current
    EBITDA, and the score factor breakdown as parameters.

This module owns the MATH (per-factor uplift, EV delta, top-3 / tertiary
selection rule from spec §7.1 / §7.2) but never sources its own data.
"""

from .eur_impact import (
    FACTOR_UPLIFTS,
    SellabilityFactorInput,
    SellabilityImpactResult,
    SellabilityLift,
    compute_sellability_eur_impact,
)

__all__ = [
    "FACTOR_UPLIFTS",
    "SellabilityFactorInput",
    "SellabilityImpactResult",
    "SellabilityLift",
    "compute_sellability_eur_impact",
]
