"""Bind market pricing inputs to the metric and company supported by evidence.

Provenance and content hashes alone do not bind a separate calibration payload.
Compare decimal values before any company-specific multiple adjustments. An
omitted calibration percentile remains unavailable; it is never invented here.
"""

import re
from collections.abc import Mapping
from decimal import Decimal

from src.domain.financial_arithmetic import decimal_number
from src.services.reports.weighted_benchmark_binding import (
    weighted_benchmark_metric_issues,
)

_QUANTILES = ("p10", "p25", "median", "p75", "p90")
_ALIASES = {
    "ev/ebitda": "ev_ebitda",
    "ev_ebitda_multiple": "ev_ebitda",
    "ebitda_multiple": "ev_ebitda",
    "ev/revenue": "ev_revenue",
    "ev_revenue_multiple": "ev_revenue",
    "revenue_multiple": "ev_revenue",
}


def _metric_name(value: object) -> str:
    name = str(value or "").strip().lower()
    return _ALIASES.get(name, name)


def _number(value: object) -> Decimal | None:
    if isinstance(value, str) and not re.fullmatch(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value.strip()
    ):
        return None
    try:
        parsed = decimal_number(value)
    except ValueError:
        return None
    return parsed


def _positive(value: object) -> Decimal | None:
    parsed = _number(value)
    return parsed if parsed is not None and parsed > 0 else None


def _metric_rows(contract: Mapping[str, object], name: str) -> list[Mapping[str, object]]:
    if "benchmark_resolution.v1" in (
        contract.get("schema_version"),
        contract.get("contract_version"),
    ):
        rows = contract.get("resolutions")
        return (
            [
                row
                for row in rows
                if isinstance(row, dict) and _metric_name(row.get("metric_name")) == name
            ]
            if isinstance(rows, list)
            else []
        )
    metrics = contract.get("metrics")
    return (
        [row for key, row in metrics.items() if _metric_name(key) == name and isinstance(row, dict)]
        if isinstance(metrics, dict)
        else []
    )


def _mix_weights(value: object) -> dict[str, Decimal] | None:
    if not isinstance(value, list) or not value:
        return None
    weights: dict[str, Decimal] = {}
    for row in value:
        if not isinstance(row, dict):
            return None
        identity = row.get("business_type_id")
        weight = _positive(row.get("weight"))
        if not isinstance(identity, str) or not identity or identity in weights or weight is None:
            return None
        weights[identity] = weight
    total = sum(weights.values(), Decimal(0))
    return {key: (weight / total * 100).quantize(Decimal(".01")) for key, weight in weights.items()}


def _target_issues(
    contract: Mapping[str, object],
    business_type_id: str,
    country_code: str,
    mix: object,
) -> list[str]:
    issues: list[str] = []
    country = str(contract.get("country_code") or contract.get("countryCode") or "").upper()
    aliases = {"UK": "GB"}
    if aliases.get(country, country) != aliases.get(country_code.upper(), country_code.upper()):
        issues.append("country_code.target_mismatch")
    target = contract.get("business_type_id") or contract.get("businessTypeId")
    # Older native contracts put their explicit target in each metric row.
    # Borrowed cohorts still require a separate target identity on the envelope.
    if target is None and contract.get("is_borrowed") is False:
        metrics = contract.get("metrics")
        rows = list(metrics.values()) if isinstance(metrics, Mapping) else metrics
        if (
            isinstance(rows, list)
            and rows
            and all(
                isinstance(row, Mapping)
                and isinstance(row.get("business_type_id"), str)
                and row.get("business_type_id")
                for row in rows
            )
        ):
            targets = {row.get("business_type_id") for row in rows}
            if len(targets) == 1:
                target = next(iter(targets))
    requested_mix = _mix_weights(mix)
    if mix is not None and requested_mix is None:
        issues.append("business_type_mix.invalid_weights")
    if requested_mix and len(requested_mix) > 1:
        source_mix = contract.get("source_mix")
        source_mix = source_mix if isinstance(source_mix, dict) else {}
        source_weights = _mix_weights(source_mix.get("segments"))
        if (
            source_mix.get("strategy") != "weighted_business_type_mix"
            or source_weights != requested_mix
            or business_type_id not in requested_mix
            or not isinstance(target, str)
            or not target.startswith("business-type-mix:")
            or set(target.removeprefix("business-type-mix:").split("+")) != set(requested_mix)
        ):
            issues.append("business_type_mix.target_mismatch")
    elif target != business_type_id or (
        requested_mix is not None and business_type_id not in requested_mix
    ):
        issues.append("business_type_id.target_mismatch")
    return issues


def benchmark_pricing_binding_issues(
    contract: Mapping[str, object],
    *,
    calibration: Mapping[str, object],
    required_attributes: set[str],
    business_type_id: str,
    country_code: str,
    business_type_mix: object = None,
) -> list[str]:
    """Return actionable mismatches for metrics that can enter this price only."""
    if not required_attributes:
        return []
    issues = _target_issues(contract, business_type_id, country_code, business_type_mix)
    for attribute in sorted(required_attributes):
        metric = attribute.removesuffix("_median")
        if _positive(calibration.get(attribute)) is None:
            continue  # zero is the existing unavailable-metric sentinel
        rows = _metric_rows(contract, metric)
        if len(rows) != 1:
            issues.append(f"{metric}.{'ambiguous_metric' if rows else 'missing_metric_values'}")
            continue
        row = rows[0]
        issues.extend(weighted_benchmark_metric_issues(contract, row, metric))
        sample = _positive(row.get("sample_size", row.get("sampleSize")))
        if sample is None or sample != sample.to_integral_value():
            issues.append(f"{metric}.invalid_sample_size")
        previous: Decimal | None = None
        for quantile in _QUANTILES:
            raw = row.get(quantile)
            value = _number(raw)
            valid = value is not None and (value > 0 if quantile == "median" else value >= 0)
            if (raw is not None or quantile == "median") and not valid:
                issues.append(f"{metric}.{quantile}.invalid_value")
            if value is not None:
                if previous is not None and value < previous:
                    issues.append(f"{metric}.{quantile}.unordered_distribution")
                previous = value
            supplied = calibration.get(f"{metric}_{quantile}")
            if supplied is not None and (not valid or _number(supplied) != value):
                issues.append(f"{metric}.{quantile}.calibration_mismatch")
    return issues
