"""Canonical typed multiple build-up — the single provenance object (BET-520).

ONE structured, typed object that the PDF, the UI, and the live comparison all
read. It is the serialized "show your work" for a multiples valuation:

    earnings basis (+ add-back ledger)
      -> per-segment provenance (multiple, tier, band, as-of, override, EV)
      -> the discount stack (parameter -> magnitude -> EUR impact -> rationale)
      -> the EV->equity bridge (EV -> net debt -> NWC -> surplus -> equity)
      -> the final reconciliation with its honesty band.

The models are intentionally serialization-friendly (Decimal throughout, no
engine coupling) so the assembler can be a pure function and the same object
can be emitted on the stateless `/calculate` response and re-read by the report
renderer without divergent math. This is the source of truth — provenance is
assembled once, here, not recomputed in N places.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

JsonObject = Dict[str, object]

EarningsBasis = Literal["SDE", "EBITDA", "EBIT", "Revenue", "Unknown"]


class AddBackLine(BaseModel):
    """A single reported-earnings -> adjusted-earnings adjustment (BET-533)."""

    label: str
    category: str = "other"
    amount: Decimal = Decimal("0")
    type: str = Field("add", description="'add' | 'subtract'")
    signed_amount: Decimal = Decimal("0")
    rationale: Optional[str] = None
    source: Optional[str] = None
    status: str = "applied"
    applied: bool = True
    # v2 ledger projection: signed_amount is the contribution to the selected
    # earnings basis. The original annual decision and its weight remain exact.
    fiscal_year: Optional[int] = None
    annual_signed_amount: Optional[Decimal] = None
    weight: Optional[Decimal] = None
    decision_id: Optional[str] = None
    evidence_id: Optional[str] = None
    rule_version: Optional[str] = None
    currency: Optional[str] = None
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None


class EarningsBasisBuildUp(BaseModel):
    """Earnings basis (BET-532) + the adjusted/maintainable ledger (BET-533)."""

    projection_version: Literal["earnings_basis_build_up.v1", "earnings_basis_build_up.v2"] = (
        "earnings_basis_build_up.v1"
    )
    basis: EarningsBasis = "EBITDA"
    rationale: Optional[str] = Field(
        None, description="One-line rationale, e.g. 'SDE used: owner-operated, revenue < EUR 5M'."
    )
    reported_earnings: Optional[Decimal] = None
    adjusted_earnings: Optional[Decimal] = None
    total_adjustments: Decimal = Decimal("0")
    add_backs: List[AddBackLine] = Field(default_factory=list)
    is_adjusted: bool = False
    applied_adjustment_count: int = 0
    pending_adjustment_count: int = 0
    source: Optional[str] = None


class SegmentProvenance(BaseModel):
    """Per-segment SOTP provenance (BET-526) with full comp-set disclosure (BET-520)."""

    index: int = 0
    business_type_id: Optional[str] = None
    business_type_title: Optional[str] = None
    nace_code: Optional[str] = None
    basis: EarningsBasis = "EBITDA"
    earnings: Optional[Decimal] = None
    multiple: Optional[Decimal] = None
    enterprise_value: Optional[Decimal] = None
    weight: Optional[Decimal] = Field(
        None, description="Derived from segment EV share (display only), not a free input."
    )
    # Comp-set provenance — never a lone median.
    source_tier: Optional[str] = Field(
        None, description="proprietary obs -> seed -> academic -> fallback"
    )
    observation_count: Optional[int] = None
    multiple_p25: Optional[Decimal] = None
    multiple_median: Optional[Decimal] = None
    multiple_p75: Optional[Decimal] = None
    as_of: Optional[str] = None
    confidence: Optional[str] = None
    is_advisor_override: bool = False


class DiscountLine(BaseModel):
    """One discount/adjustment: parameter -> magnitude -> EUR impact -> rationale+source."""

    key: str
    label: str
    parameter: Decimal = Field(Decimal("0"), description="Model adjustment, e.g. -0.22 = 22% off.")
    advisor_weight: Decimal = Decimal("1")
    magnitude: Decimal = Field(
        Decimal("0"), description="Effective adjustment after advisor weight."
    )
    euro_impact: Optional[Decimal] = None
    factor_before: Optional[Decimal] = None
    factor_after: Optional[Decimal] = None
    rationale: Optional[str] = None
    source: Optional[str] = None
    multiple_discount_key: Optional[str] = Field(
        None,
        description="Canonical strength-factor discount key, e.g. revenue_quality_discount.",
    )
    strength_factor_multiple_discount_keys: List[str] = Field(default_factory=list)
    strength_factor_keys: List[str] = Field(default_factory=list)
    strength_factor_mapped_inputs: List[str] = Field(default_factory=list)
    strength_factor_valuation_effects: List[str] = Field(default_factory=list)
    strength_factor_captured_input_ids: List[str] = Field(default_factory=list)
    strength_factor_data_point_ids: List[str] = Field(default_factory=list)
    strength_factor_evidence_count: int = 0
    enabled: bool = True


class DiscountStack(BaseModel):
    """The multiplicative, floored discount stack (BET-523/524)."""

    enabled: bool = True
    composition: str = "multiplicative"
    floor_factor: Decimal = Decimal("0.45")
    pre_floor_factor: Optional[Decimal] = None
    floor_applied: bool = False
    total_adjustment_factor: Decimal = Decimal("1")
    total_adjustment: Decimal = Decimal("0")
    rows: List[DiscountLine] = Field(default_factory=list)
    owner_concentration_policy: Optional[str] = None
    owner_concentration_policy_reason: Optional[str] = None
    strength_factor_policy: Optional[str] = None
    strength_factor_evidence: List[dict] = Field(default_factory=list)


class EquityBridgeLine(BaseModel):
    """One itemized leg of the EV->equity bridge (BET-534)."""

    key: str
    label: str
    amount: Decimal = Decimal("0")
    operator: str = Field("-", description="'-' subtracts, '+' adds to running EV.")
    kind: str = Field(
        "adjustment", description="ev | debt | cash | net_debt | nwc | surplus | equity"
    )
    detail: Optional[str] = None


class EquityBridge(BaseModel):
    """EV -> net debt -> NWC normalization -> surplus assets -> equity (BET-534)."""

    enterprise_value: Optional[Decimal] = None
    lines: List[EquityBridgeLine] = Field(default_factory=list)
    equity_value: Optional[Decimal] = None
    net_debt: Optional[Decimal] = None
    equity_status: Optional[Literal["available", "unavailable_incomplete_bridge"]] = None
    unresolved_fields: List[str] = Field(default_factory=list)
    nwc_status: str = Field("not_assessed", description="assessed | not_assessed")
    nwc_note: Optional[str] = None
    is_phantom_suppressed: bool = False
    notes: List[str] = Field(default_factory=list)


class AdvisorOverride(BaseModel):
    """An advisor multiple override captured as ADVISOR_OVERRIDE (BET-522/524)."""

    kind: str = Field(
        "none", description="effective_multiple | per_type_multiple | multiple_calibration | none"
    )
    model_value: Optional[Decimal] = None
    advisor_value: Optional[Decimal] = None
    delta: Optional[Decimal] = None
    note: Optional[str] = None
    out_of_band: bool = False
    index_protected: bool = True
    # Audit trail — who/when (BET-524).
    advisor_id: Optional[str] = None
    timestamp: Optional[str] = None


class MultipleTypeBlendRow(BaseModel):
    """One EV/EBITDA vs EV/Revenue vs P/E component of the blend (BET-535)."""

    key: str
    label: str
    enterprise_value: Decimal = Decimal("0")
    weight: Decimal = Decimal("0")
    model_weight: Decimal = Decimal("0")
    advisor_delta: Decimal = Decimal("0")
    contribution: Decimal = Decimal("0")
    included: bool = True


class MultipleTypeBlend(BaseModel):
    """The advisor-controllable multiple-type blend block (BET-535)."""

    source: str = "sector_aware_default"
    model_source: str = "sector_aware_default"
    weighted_enterprise_value: Decimal = Decimal("0")
    rows: List[MultipleTypeBlendRow] = Field(default_factory=list)


class MultipleBuildUp(BaseModel):
    """The canonical, typed "show your work" object for a multiples valuation.

    Emitted once by the engine and re-read by the PDF + UI + live comparison.
    """

    version: str = "multiple_build_up_v2"
    tier: str = Field("firm", description="firm | free — full build-up is firm-tier only.")

    earnings_basis: EarningsBasisBuildUp = Field(default_factory=EarningsBasisBuildUp)

    segments: List[SegmentProvenance] = Field(default_factory=list)
    is_multi_segment: bool = False
    segment_mode: Optional[str] = Field(
        None, description="true_sotp | weighted_blend_fallback | single_segment"
    )

    multiple_type_blend: Optional[MultipleTypeBlend] = None

    discounts: DiscountStack = Field(default_factory=DiscountStack)
    advisor_override: Optional[AdvisorOverride] = None

    risk_analysis_enabled: bool = True
    risk_analysis_reference_only: bool = Field(
        False,
        description=(
            "True when risk analysis is OFF: the headline EV/equity here is the "
            "pre-adjustment comparable reference (a different standard of value), "
            "NOT the recommended value."
        ),
    )

    equity_bridge: EquityBridge = Field(default_factory=EquityBridge)

    # Final reconciliation: adjusted earnings x effective multiple -> EV -> bridge -> equity.
    adjusted_earnings: Optional[Decimal] = None
    effective_multiple: Optional[Decimal] = None
    enterprise_value: Optional[Decimal] = None
    equity_value: Optional[Decimal] = None
    band_low: Optional[Decimal] = None
    band_high: Optional[Decimal] = None
