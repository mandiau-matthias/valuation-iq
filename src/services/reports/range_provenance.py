"""Disclose how a sealed range was produced without inventing statistical coverage."""

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RangeProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["range-provenance.v1"] = "range-provenance.v1"
    kind: Literal["model_band", "benchmark_percentile_band", "simulation_interval"]
    calibration_status: Literal["unverified"] = "unverified"
    eligible_holdout_count: Literal[0] = 0
    empirical_coverage: None = None
    transaction_relative_error: None = None
    assumptions: list[str]
    source_vintages: list[dict[str, object]] = Field(default_factory=list)
    excluded_methods: dict[str, str] = Field(default_factory=dict)
    resolved_weights: list[dict[str, object]] = Field(default_factory=list)


def sealed_range_provenance(
    *,
    method_results: Mapping[str, object],
    source_vintages: Sequence[object],
    method_mix: list[dict[str, object]],
) -> dict[str, object]:
    excluded = {}
    for key, result in method_results.items():
        payload = result if isinstance(result, Mapping) else vars(result)
        if payload.get("available") is False:
            excluded[key] = str(
                payload.get("unavailable_reason") or "Required method evidence unavailable"
            )
    return RangeProvenance(
        # Blended and adjusted ranges are model bands even when a component
        # multiple originated from benchmark percentiles. They are not a
        # statistical confidence interval for a transaction price.
        kind="model_band",
        assumptions=[
            "Range endpoints are the sealed method/synthesis output.",
            "Model and benchmark assumptions determine the band; transaction-price coverage is unverified.",
            "Historical cash-flow and capex proxies are diagnostics, not verified forecasts.",
        ],
        source_vintages=[dict(item) for item in source_vintages if isinstance(item, Mapping)],
        excluded_methods=excluded,
        resolved_weights=method_mix,
    ).model_dump(mode="json")
