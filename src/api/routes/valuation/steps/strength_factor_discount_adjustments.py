"""Apply priced strength-factor evidence to modular multiple-discount steps."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from src.domain.multiples.strength_factor_discount_evidence import (
    strength_factor_discount_adjustments_from_business_context,
)

JsonMap = dict[str, object]

STRENGTH_FACTOR_DISCOUNT_LINEAGE_KEYS = (
    "strength_factor_discount_key",
    "strength_factor_discount_adjustment",
    "strength_factor_discount_before",
    "strength_factor_discount_after",
    "strength_factor_discount_evidence",
    "strength_factor_policy",
)


def strength_factor_discount_adjustment_for_request(
    request: object,
    discount_key: str,
) -> tuple[Decimal, list[JsonMap]]:
    evidence_rows = strength_factor_discount_adjustments_from_business_context(
        getattr(request, "business_context", None),
        revenue=_request_revenue(request),
        team_size=_request_team_size(request),
    )

    matching_rows: list[JsonMap] = []
    total_adjustment = Decimal("0")
    for row in evidence_rows:
        if row.get("discount_key") != discount_key:
            continue
        adjustment = row.get("adjustment")
        if not isinstance(adjustment, Decimal):
            continue
        total_adjustment += adjustment
        matching_rows.append(dict(row))

    return total_adjustment, matching_rows


def _request_revenue(request: object) -> object:
    for attr in ("revenue", "annual_revenue", "current_revenue", "latest_revenue"):
        value = getattr(request, attr, None)
        if value is not None and value != "":
            return value

    current_year_data = getattr(request, "current_year_data", None)
    if isinstance(current_year_data, Mapping):
        for key in ("revenue", "annual_revenue", "turnover", "sales"):
            value = current_year_data.get(key)
            if value is not None and value != "":
                return value
    return None


def _request_team_size(request: object) -> object:
    for attr in ("number_of_employees", "employee_count", "team_size", "fte_count"):
        value = getattr(request, attr, None)
        if value is not None and value != "":
            return value

    current_year_data = getattr(request, "current_year_data", None)
    if isinstance(current_year_data, Mapping):
        for key in ("number_of_employees", "employee_count", "team_size", "fte_count"):
            value = current_year_data.get(key)
            if value is not None and value != "":
                return value
    return None


def apply_priced_strength_factor_adjustment(
    base_discount: Decimal,
    strength_factor_adjustment: Decimal,
    *,
    floor: Decimal,
    ceiling: Decimal = Decimal("0"),
) -> Decimal:
    if strength_factor_adjustment == 0:
        return base_discount

    return max(floor, min(ceiling, base_discount + strength_factor_adjustment))


def annotate_strength_factor_discount_result(
    result_dict: JsonMap,
    metadata_dict: JsonMap,
    *,
    discount_key: str,
    evidence_rows: list[JsonMap],
    adjustment: Decimal,
    discount_before: Decimal,
    discount_after: Decimal,
) -> None:
    if not evidence_rows:
        return

    payload: JsonMap = {
        "strength_factor_discount_key": discount_key,
        "strength_factor_discount_adjustment": adjustment,
        "strength_factor_discount_before": discount_before,
        "strength_factor_discount_after": discount_after,
        "strength_factor_discount_evidence": evidence_rows,
        "strength_factor_policy": _strength_factor_policy_name(evidence_rows),
    }
    result_dict.update(payload)
    metadata_dict.update(payload)

    pipeline_stage = result_dict.get("pipeline_stage")
    if isinstance(pipeline_stage, dict):
        pipeline_stage.update(payload)

    discount_breakdown = (
        pipeline_stage.get("discount_breakdown") if isinstance(pipeline_stage, Mapping) else None
    )
    if isinstance(discount_breakdown, dict):
        discount_breakdown.update(payload)


def strength_factor_discount_lineage_payload(source: Mapping[str, object]) -> JsonMap:
    payload: JsonMap = {}
    for key in STRENGTH_FACTOR_DISCOUNT_LINEAGE_KEYS:
        value = source.get(key)
        if value is not None:
            payload[key] = value

    evidence = payload.get("strength_factor_discount_evidence")
    if evidence is not None and "strength_factor_evidence" not in source:
        payload["strength_factor_evidence"] = evidence

    return payload


def _strength_factor_policy_name(evidence_rows: list[JsonMap]) -> str:
    if any(row.get("source") == "business_growth_maturity_policy" for row in evidence_rows):
        return "business_context_and_growth_maturity_policy"
    return "explicit_business_context_adjustments_only"
