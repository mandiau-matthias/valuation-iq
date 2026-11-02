"""Versioned, sealed method decisions; independent from pricing computations."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MethodEligibilityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    eligible: bool
    value_basis: Literal["equity_value", "enterprise_value"] | None
    reason: str | None


class MethodEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["method-eligibility.v1"] = "method-eligibility.v1"
    policy_version: Literal["source-evidence-required.v1", "legacy-evidence-admission.v1"]
    methods: dict[str, MethodEligibilityDecision]
    equity_status: Literal["available", "unavailable_incomplete_bridge"]
    resolved_weights: list[dict[str, object]] = Field(default_factory=list)
