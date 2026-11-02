"""Weighted valuation synthesis schemas.

Kept separate from the large stateless API request/response schema so APV
bridge metadata can evolve without growing the already-large API contract file.
"""

from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from src.domain.method_keys import MethodKey


class WeightedMethodContribution(BaseModel):
    """One row in the blended-valuation synthesis table."""

    method_key: MethodKey = Field(
        ...,
        description=("Engine method key, typed against src.domain.method_keys.MethodKey."),
    )
    label: str = Field(..., description="Human-readable method name")
    equity_value: Decimal = Field(..., description="Unblended equity value")
    equity_value_low: Optional[Decimal] = None
    equity_value_high: Optional[Decimal] = None
    enterprise_value: Optional[Decimal] = Field(
        None, description="Unblended method enterprise value when independently calculated."
    )
    enterprise_value_low: Optional[Decimal] = None
    enterprise_value_high: Optional[Decimal] = None
    weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="User-assigned weight; all weights sum to 1.0",
    )
    weight_decimal: Optional[Decimal] = Field(
        None,
        ge=0,
        le=1,
        description="Exact normalized weight used for financial synthesis; weight is the legacy display alias.",
    )
    weighted_contribution: Decimal = Field(
        ...,
        description="Selected value-basis amount multiplied by weight.",
    )
    weighted_contribution_unrounded: Optional[Decimal] = Field(
        None,
        description="Exact Decimal contribution used in synthesis before display rounding.",
    )
    value_basis: Optional[str] = Field(
        None,
        description="Optional valuation-basis tag, e.g. 'apv' or 'net_engine'.",
    )
    value_before_bridge: Optional[Decimal] = Field(
        None,
        description="Method equity value before explicit bridge adjustment.",
    )
    bridge_adjustment: Optional[Decimal] = Field(
        None,
        description="Explicit bridge adjustment included in method equity value.",
    )
    bridge_adjustment_pct_of_total: Optional[Decimal] = Field(
        None,
        description="Bridge adjustment percentage of bridged method value.",
    )
    discounting_convention: Optional[str] = Field(
        None,
        description="Cash-flow timing convention for the bridge adjustment.",
    )
    bridge_provenance: Optional[Dict[str, object]] = Field(
        None,
        description=(
            "Structured bridge provenance, e.g. APV tax-shield source and customer-template "
            "reconciliation status."
        ),
    )
    benchmark_reconciliation: Optional[Dict[str, object]] = Field(
        None,
        description="Optional customer-template benchmark reconciliation for the bridged method.",
    )


class WeightedValuationResult(BaseModel):
    """Result of a user-configured blended valuation across multiple methods."""

    blended_equity_value: Decimal = Field(
        ...,
        description="Sum of all weighted contributions",
    )
    pre_common_bridge_blended_equity_value: Optional[Decimal] = Field(
        None,
        description="Method-weighted equity before a shared top-level bridge correction.",
    )
    common_bridge_adjustment: Decimal = Field(
        Decimal("0"),
        description="Shared equity-side bridge applied after method weighting.",
    )
    pre_shareholder_transaction_blended_equity_value: Optional[Decimal] = Field(
        None,
        description=(
            "Blended equity after the common bridge but before structural, "
            "shareholder or transaction adjustments."
        ),
    )
    shareholder_transaction_adjustment: Decimal = Field(
        Decimal("0"),
        description=(
            "Signed structural/shareholder/transaction adjustment applied after "
            "method weighting and the common EV-to-equity bridge."
        ),
    )
    synthesis_policy_version: str = "eligible_method_renormalization.v1"
    weights_renormalized: bool = False
    excluded_methods: List[Dict[str, object]] = Field(default_factory=list)
    excluded_original_weight: Decimal = Decimal("0")
    uncertainty_inflation_factor: Decimal = Decimal("1")
    valuation_range_low: Optional[Decimal] = None
    valuation_range_high: Optional[Decimal] = None
    enterprise_value_low: Optional[Decimal] = None
    enterprise_value_mid: Optional[Decimal] = None
    enterprise_value_high: Optional[Decimal] = None
    raw_equity_value_low: Optional[Decimal] = None
    raw_equity_value_mid: Optional[Decimal] = None
    raw_equity_value_high: Optional[Decimal] = None
    debt_overhang: Decimal = Decimal("0")
    value_basis: str = "equity_value"
    contributions: List[WeightedMethodContribution] = Field(
        ...,
        description="Per-method breakdown",
    )
    user_justification: Optional[str] = Field(
        None,
        description="Accountant's textual motivation for the chosen weighting",
    )
