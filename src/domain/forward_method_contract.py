"""Shared forward-method contract types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ForwardRole(str, Enum):
    """How a method may participate in a forward value cone."""

    PRIMARY_METHOD = "primary_method"
    STATIC_ANCHOR = "static_anchor"
    AGGREGATOR = "aggregator"
    DOWNSIDE_ONLY = "downside_only"


class ForecastFamily(str, Enum):
    """Mathematical family used by the forward adapter."""

    DISCOUNTED_CASH_FLOW = "discounted_cash_flow"
    MARKET_MULTIPLE = "market_multiple"
    OWNER_EARNINGS = "owner_earnings"
    ASSET_ROLL_FORWARD = "asset_roll_forward"
    PROPERTY_INCOME = "property_income"
    MILESTONE_STATE_TRANSITION = "milestone_state_transition"
    METHOD_BLEND = "method_blend"
    STATIC_REFERENCE = "static_reference"
    LIQUIDATION_PREMISE = "liquidation_premise"


class ForwardValueBasis(str, Enum):
    """Value object emitted by a method before the common equity bridge."""

    ENTERPRISE_VALUE = "enterprise_value"
    EQUITY_VALUE = "equity_value"


@dataclass(frozen=True)
class ForwardMethodSpec:
    """Method-specific forwardability requirements."""

    method_key: str
    family: ForecastFamily
    role: ForwardRole
    forecast_metric: str | None
    horizon_cap_years: int | None
    minimum_forward_evidence: str
    uncertainty_family: str
    correlation_bucket: str
    value_basis: ForwardValueBasis
    required_driver_groups: tuple[str, ...]
    pricing_inputs: tuple[str, ...]
    uncertainty_drivers: tuple[str, ...]
    exclusion_rules: tuple[str, ...]
    output_distribution: tuple[str, ...] = ("p10", "p50", "p90")

    @property
    def is_directly_forwardable(self) -> bool:
        return self.role == ForwardRole.PRIMARY_METHOD

    @property
    def requires_equity_bridge(self) -> bool:
        return self.value_basis == ForwardValueBasis.ENTERPRISE_VALUE
