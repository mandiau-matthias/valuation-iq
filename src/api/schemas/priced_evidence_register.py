"""Run-bound report projections for priced evidence and value adjustments.

These contracts are deliberately report-only.  They do not authorize evidence,
change a valuation, or become a second calculation authority.  Every field is a
deterministic projection of an already sealed ``ValuationRunV2``.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import List, Literal, Optional

import rfc8785
from pydantic import BaseModel, Field, model_validator

from src.api.schemas.valuation_contracts import Sha256Hex


def _projection_hash(value: object) -> str:
    return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


class PricedEvidenceEntry(BaseModel):
    """One source or snapshot that supported a priced calculation input."""

    entry_id: str = Field(..., min_length=1)
    method_key: str = Field(..., min_length=1)
    use: str = Field(..., min_length=1)
    source_kind: str = Field(..., min_length=1)
    source_label: Optional[str] = None
    provider: Optional[str] = None
    source_id: Optional[str] = None
    benchmark_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    snapshot_hash: Optional[Sha256Hex] = None
    dataset_version_id: Optional[str] = None
    content_hash: Optional[str] = None
    locator: Optional[str] = None
    url: Optional[str] = None
    observed_at: Optional[str] = None
    published_at: Optional[str] = None
    sample_size: Optional[int] = Field(None, ge=0)
    sample_size_disclosure: Literal["reported", "not_disclosed", "not_applicable"]
    freshness_status: str = "not_assessed"
    review_status: str = "not_assessed"
    source_completeness: Literal["complete", "incomplete"]
    missing_committed_fields: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def bind_source_completeness(self) -> "PricedEvidenceEntry":
        expected = "incomplete" if self.missing_committed_fields else "complete"
        if self.source_completeness != expected:
            raise ValueError("priced evidence completeness does not match missing fields")
        return self


class PricedEvidenceRegister(BaseModel):
    """Immutable-view register derived from one sealed valuation run."""

    schema_version: Literal["priced_evidence_register.v1"] = "priced_evidence_register.v1"
    valuation_run_id: str
    valuation_run_hash: Sha256Hex
    entries: List[PricedEvidenceEntry] = Field(default_factory=list)
    register_hash: Sha256Hex

    @model_validator(mode="after")
    def verify_register_hash(self) -> "PricedEvidenceRegister":
        material = self.model_dump(mode="json", exclude={"register_hash"})
        if _projection_hash(material) != self.register_hash:
            raise ValueError("priced evidence register hash mismatch")
        return self


class ActionableAdjustmentLine(BaseModel):
    """One precomputed line in the owner value waterfall.

    ``signed_amount`` is monetary when the sealed ledger supplies an exact
    amount.  ``signed_percentage_points`` is used for factor-only method
    calibration rows.  A renderer must never derive one from the other.
    """

    line_id: str = Field(..., min_length=1)
    category: Literal[
        "operating_normalization",
        "enterprise_to_equity",
        "structural_shareholder_transaction",
    ]
    label: str = Field(..., min_length=1)
    signed_amount: Optional[Decimal] = None
    signed_percentage_points: Optional[Decimal] = None
    amount_basis: str = Field(..., min_length=1)
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    priced_state: Literal["priced", "scenario_only"]
    status: str = Field(..., min_length=1)
    evidence_reference_ids: List[str] = Field(default_factory=list)
    evidence_status: str = Field(..., min_length=1)
    evidence_date: Optional[str] = None
    source: Optional[str] = None
    source_path: str = Field(..., min_length=1)
    fiscal_year: Optional[int] = Field(None, ge=1900, le=2100)
    effective_date: Optional[str] = None
    recoverability: Literal["recoverable", "partly_recoverable", "structural", "not_assessed"] = (
        "not_assessed"
    )
    action: Optional[str] = None
    proof_required: Optional[str] = None
    missing_committed_fields: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_an_impact(self) -> "ActionableAdjustmentLine":
        if self.signed_amount is None and self.signed_percentage_points is None:
            if self.priced_state == "priced":
                raise ValueError("priced adjustment line requires a sealed impact")
        return self


class ActionableAdjustmentProjection(BaseModel):
    """Ordered adjustment lines bound to the same immutable valuation run."""

    schema_version: Literal["actionable_adjustment_projection.v1"] = (
        "actionable_adjustment_projection.v1"
    )
    valuation_run_id: str
    valuation_run_hash: Sha256Hex
    lines: List[ActionableAdjustmentLine] = Field(default_factory=list)
    projection_hash: Sha256Hex

    @model_validator(mode="after")
    def verify_projection_hash(self) -> "ActionableAdjustmentProjection":
        material = self.model_dump(mode="json", exclude={"projection_hash"})
        if _projection_hash(material) != self.projection_hash:
            raise ValueError("actionable adjustment projection hash mismatch")
        return self


def priced_evidence_register_hash(material: object) -> str:
    """Public constructor helper; kept here beside hash verification."""

    return _projection_hash(material)


def actionable_adjustment_projection_hash(material: object) -> str:
    """Public constructor helper; kept here beside hash verification."""

    return _projection_hash(material)
