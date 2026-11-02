"""Sellability render-input models (BET-204 / chunk 6).

These models describe the **render-time payload** that Titan attaches to
`ValuationResponse.sellability_assessment` when invoking the report
renderer. They mirror the locked output schema from A1 spec §9 — but
note this is the WIRE shape, NOT the Prisma row. Titan owns the
projection from `sellability_assessment` (Prisma) → these Pydantic
models when building the render request.

Why Pydantic and not a plain dict (like the `legacy_schemas` deprecated
`owner_profiling: Optional[Dict[str, Any]]`):
    - Wire-shape drift between Titan and ValuationIQ is a real risk;
      Pydantic enforces it at parse time.
    - The aggregator can branch on typed fields (`band`, `confidence`)
      without `dict.get()` ceremony.
    - JSON-schema generation gives us a defensible contract artefact.

Architectural pin (per founder constraint, 2026-05-02):
    The Sellability section is rendered as a SECTION inside the existing
    main valuation report. It does NOT have a separate PDF endpoint or
    email pipeline. This module describes only the render payload — the
    rendering itself is composed via Jinja partials at
    `templates/main_report/pages/sellability.html` and the PDF twin
    at `templates/main_report_pdf/pages/sellability.html`.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


SellabilityBand = Literal[
    "significant_work_to_do",
    "foundations_in_place",
    "sale_ready_in_most_ways",
    "sale_ready_today",
]

SellabilityConfidence = Literal["high", "med", "low"]

SellabilityFactorKey = Literal[
    "owner_dependence",
    "customer_concentration",
    "revenue_quality",
    "financial_cleanliness",
    "growth_trend",
    "transferability",
]

SellabilityWeightsSource = Literal[
    "global_default",
    "delphi_country_sector",
    "delphi_sector",
]

SellabilityCountryBasis = Literal[
    "native",
    "aggregate_clone",
    "aggregate",
]


class SellabilityFactorBreakdownRender(BaseModel):
    """One factor row from the score breakdown — render-time shape."""

    key: SellabilityFactorKey
    value: float = Field(..., ge=0, le=100)
    weight: float = Field(..., ge=0, le=1)
    contribution: float
    data_available: bool


class SellabilityLiftRender(BaseModel):
    """One lift entry — top-3 or tertiary."""

    factor: SellabilityFactorKey
    action: str
    eur_impact: Optional[int] = None
    confidence: SellabilityConfidence
    uplift_pct: float


class SellabilityWeightsRender(BaseModel):
    """The 6 factor weights actually used (post-resolution)."""

    owner_dependence: float
    customer_concentration: float
    revenue_quality: float
    financial_cleanliness: float
    growth_trend: float
    transferability: float


class SellabilityEngineSignalsRender(BaseModel):
    """Engineering metadata + Delphi provenance footer payload."""

    transferability_index_reused: bool
    owner_dependence_reused: bool
    years_of_financials: int
    cap_breach_count: int
    factors_with_missing_data: int
    delphi_benchmark_id: Optional[str] = None
    delphi_country_basis: Optional[SellabilityCountryBasis] = None
    delphi_multiple_used: Optional[float] = None


class SellabilityAssessmentRender(BaseModel):
    """Render-time payload for the Sellability section.

    Attached to `ValuationResponse.sellability_assessment` by Titan when
    the user has a recent score AND the report is being rendered for an
    owner-dep-eligible methodology. Absence of this field (None) drives
    the "skipped" state in the rendered section.
    """

    assessment_id: str
    score: int = Field(..., ge=0, le=100)
    band: SellabilityBand
    confidence: SellabilityConfidence
    factors: List[SellabilityFactorBreakdownRender]
    top_three_lifts: List[SellabilityLiftRender] = Field(default_factory=list)
    tertiary_lifts: List[SellabilityLiftRender] = Field(default_factory=list)
    weights_used: SellabilityWeightsRender
    weights_source: SellabilityWeightsSource
    engine_signals: SellabilityEngineSignalsRender
    created_at: str  # ISO-8601


__all__ = [
    "SellabilityAssessmentRender",
    "SellabilityBand",
    "SellabilityConfidence",
    "SellabilityCountryBasis",
    "SellabilityEngineSignalsRender",
    "SellabilityFactorBreakdownRender",
    "SellabilityFactorKey",
    "SellabilityLiftRender",
    "SellabilityWeightsRender",
    "SellabilityWeightsSource",
]
