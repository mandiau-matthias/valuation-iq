"""Replay a Titan activity-weighted envelope from every component metric.

These are derived component values, not pooled-sample quantiles or a SOTP.
The sample count is the weakest component count, never a sum of unknown overlap.
"""

import re
from collections.abc import Mapping
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

from src.domain.financial_arithmetic import decimal_number

_QUANTILES = ("p10", "p25", "median", "p75", "p90")


def _number(value: object) -> Decimal | None:
    if isinstance(value, str) and not re.fullmatch(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value.strip()
    ):
        return None
    try:
        parsed = decimal_number(value)
        return parsed if parsed.is_zero() or -323 <= parsed.adjusted() <= 308 else None
    except ValueError:
        return None


def _country(value: object) -> str:
    code = str(value or "").strip().upper()
    return "GB" if code == "UK" else code


def weighted_benchmark_metric_issues(
    contract: Mapping[str, object], row: Mapping[str, object], metric: str
) -> list[str]:
    """Reject incomplete components or a composite that cannot be reproduced."""
    mix = contract.get("source_mix")
    if not isinstance(mix, dict) or mix.get("strategy") != "weighted_business_type_mix":
        return []
    prefix = f"{metric}.business_type_mix"
    segments = mix.get("segments")
    if (
        contract.get("methodology_version") != "titan-business-type-mix-v2"
        or not isinstance(segments, list)
        or not 2 <= len(segments) <= 20
        or mix.get("sample_size_basis") != "minimum_component_sample_not_unique_transactions"
        or mix.get("rounding") != "decimal_half_up_4_places"
        or row.get("source_mix") != mix
    ):
        return [f"{prefix}.component_evidence_required"]
    issues: list[str] = []
    weights: list[Decimal] = []
    rows: list[dict[str, object]] = []
    samples: list[Decimal] = []
    confidences: list[Decimal] = []
    dates: list[datetime] = []
    identities: set[str] = set()
    for segment in segments:
        if not isinstance(segment, dict):
            return [f"{prefix}.invalid_component"]
        identity = segment.get("business_type_id")
        weight = _number(segment.get("weight"))
        metrics = segment.get("metrics")
        component = metrics.get(metric) if isinstance(metrics, dict) else None
        if (
            not isinstance(identity, str)
            or identity in identities
            or weight is None
            or weight < Decimal(".01")
            or weight > 100
            or weight != weight.quantize(Decimal(".01"))
            or not isinstance(component, dict)
        ):
            return [f"{prefix}.invalid_component"]
        identities.add(identity)
        if (
            component.get("business_type_id") != identity
            or component.get("metric_name") != metric
            or _country(component.get("country_code")) != _country(contract.get("country_code"))
            or not all(
                component.get(key)
                for key in ("benchmark_id", "dataset_version_id", "methodology_version")
            )
        ):
            issues.append(f"{prefix}.component_target_mismatch")
        sample = _number(component.get("sample_size"))
        if (
            sample is None
            or not 0 < sample <= 9007199254740991
            or sample != sample.to_integral_value()
        ):
            return [f"{prefix}.invalid_component_sample"]
        score = _number(component.get("confidence_score"))
        if score is None or not 0 <= score <= 1:
            return [f"{prefix}.invalid_component_confidence"]
        try:
            date = datetime.fromisoformat(str(component.get("published_at")).replace("Z", "+00:00"))
            if date.tzinfo is None:
                return [f"{prefix}.invalid_component_date"]
        except ValueError:
            return [f"{prefix}.invalid_component_date"]
        previous: Decimal | None = None
        for quantile in _QUANTILES:
            raw = component.get(quantile)
            if raw is None and quantile != "median":
                continue
            value = _number(raw)
            if (
                value is None
                or value < 0
                or (quantile == "median" and value == 0)
                or (previous is not None and value < previous)
            ):
                return [f"{prefix}.invalid_component_distribution"]
            previous = value
        blockers = component.get("release_blockers")
        output_blockers = row.get("release_blockers")
        if (
            not isinstance(blockers, list)
            or not isinstance(output_blockers, list)
            or any(blocker not in output_blockers for blocker in blockers)
        ):
            issues.append(f"{prefix}.component_release_mismatch")
        if (
            row.get("standalone_conclusion_eligible") is True
            and component.get("standalone_conclusion_eligible") is not True
        ):
            issues.append(f"{prefix}.component_release_mismatch")
        weights.append(weight)
        rows.append(component)
        samples.append(sample)
        confidences.append(score)
        dates.append(date)
    if sum(weights, Decimal(0)) != 100:
        issues.append(f"{prefix}.invalid_weight_partition")
    for quantile in _QUANTILES:
        values = [_number(component.get(quantile)) for component in rows]
        if any(value is None for value in values):
            if row.get(quantile) is not None:
                issues.append(f"{prefix}.{quantile}.incomplete_components")
            continue
        with localcontext() as context:
            context.prec = 400
            expected = sum(
                (
                    weight * value / 100
                    for weight, value in zip(weights, values)
                    if value is not None
                ),
                Decimal(0),
            ).quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)
        if _number(row.get(quantile)) != expected:
            issues.append(f"{prefix}.{quantile}.aggregation_mismatch")
    if _number(row.get("sample_size")) != min(samples):
        issues.append(f"{prefix}.sample_size_mismatch")
    if _number(row.get("confidence_score")) != min(confidences):
        issues.append(f"{prefix}.confidence_score_mismatch")
    try:
        actual_date = datetime.fromisoformat(str(row.get("published_at")).replace("Z", "+00:00"))
        if actual_date != min(dates):
            issues.append(f"{prefix}.publication_date_mismatch")
    except ValueError:
        issues.append(f"{prefix}.publication_date_mismatch")
    return list(dict.fromkeys(issues))
