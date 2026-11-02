"""Strength-factor evidence adapter for ValuationIQ multiple discounts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

from src.domain.business_growth_maturity_discounts import (
    build_business_growth_maturity_discount_adjustments,
)

JsonMap = dict[str, object]

STRENGTH_FACTOR_DISCOUNT_CONTEXT_KEYS = (
    "strength_factor_discount_adjustments",
    "strength_factor_discount_evidence",
    "strength_factor_multiple_adjustments",
)

STRENGTH_FACTOR_DISCOUNT_KEYS = frozenset(
    {
        "size_discount",
        "liquidity_discount",
        "country_adjustment",
        "growth_premium",
        "revenue_trend",
    }
)

STRENGTH_FACTOR_DISCOUNT_ALIASES: dict[str, str] = {
    "size": "size_discount",
    "liquidity": "liquidity_discount",
    "country": "country_adjustment",
    "growth": "growth_premium",
    "growth_trend": "growth_premium",
    "growth_trend_discount": "growth_premium",
    "revenue_quality": "liquidity_discount",
    "revenue_quality_discount": "liquidity_discount",
    "financial_cleanliness": "liquidity_discount",
    "financial_cleanliness_discount": "liquidity_discount",
    "customer_concentration": "liquidity_discount",
    "customer_concentration_discount": "liquidity_discount",
    "management_depth": "liquidity_discount",
    "management_depth_discount": "liquidity_discount",
    "moat_differentiation": "liquidity_discount",
    "moat_differentiation_discount": "liquidity_discount",
    "margin_context": "liquidity_discount",
    "margin_quality": "liquidity_discount",
    "margin_quality_discount": "liquidity_discount",
    "operating_quality": "liquidity_discount",
    "operating_quality_discount": "liquidity_discount",
    "owner_hours_dependency": "liquidity_discount",
    "key_dependencies": "liquidity_discount",
    "growth_narrative": "growth_premium",
    "transferability": "liquidity_discount",
    "transferability_risk_band": "liquidity_discount",
    "lease_transferability_risk": "liquidity_discount",
    "food_safety_risk": "liquidity_discount",
    "security_compliance_risk": "liquidity_discount",
    "regulatory_standing_risk": "liquidity_discount",
    "supplier_dependency_risk": "liquidity_discount",
    "dependency_risk_band": "liquidity_discount",
    "compliance_risk_band": "liquidity_discount",
    "platform_dependency": "liquidity_discount",
    "platform_dependency_discount": "liquidity_discount",
    "working_capital": "liquidity_discount",
    "working_capital_discount": "liquidity_discount",
    "owner_dependence": "liquidity_discount",
    "owner_dependence_discount": "liquidity_discount",
    "owner_dependency": "liquidity_discount",
}

STRENGTH_FACTOR_EVIDENCE_FIELD_ALIASES: dict[str, str] = {
    "factorKey": "factor_key",
    "factorLabel": "factor_label",
    "discountKey": "discount_key",
    "multipleDiscountKey": "multiple_discount_key",
    "mappedSubjectiveInput": "mapped_subjective_input",
    "valuationEffect": "valuation_effect",
    "engineDriver": "engine_driver",
    "capturedInputId": "captured_input_id",
    "dataPointIds": "data_point_ids",
}

STRENGTH_FACTOR_LINKAGE_FIELD_ALIASES: dict[str, str] = {
    "discount_key": "discount_key",
    "discountKey": "discount_key",
    "multiple_discount_key": "multiple_discount_key",
    "multipleDiscountKey": "multiple_discount_key",
    "sellability_factor": "sellability_factor",
    "sellabilityFactor": "sellability_factor",
    "engine_driver": "engine_driver",
    "engineDriver": "engine_driver",
    "maps_to_subjective_input": "maps_to_subjective_input",
    "mapsToSubjectiveInput": "maps_to_subjective_input",
    "mapped_subjective_input": "mapped_subjective_input",
    "mappedSubjectiveInput": "mapped_subjective_input",
    "valuation_effect": "valuation_effect",
    "valuationEffect": "valuation_effect",
    "effect": "valuation_effect",
}

MAX_STRENGTH_FACTOR_DISCOUNT_ADJUSTMENT = Decimal("0.15")


def _decimal(value: object, default: Decimal = Decimal("0")) -> Decimal:
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _percent_or_ratio(value: Decimal) -> Decimal:
    if abs(value) > Decimal("1.5"):
        return value / Decimal("100")
    return value


def _canonical_strength_factor_discount_key(raw: object) -> str | None:
    token = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    candidates = [token]
    for suffix in ("_multiple_discount", "_discount"):
        if token.endswith(suffix):
            candidates.append(token[: -len(suffix)])

    for candidate in candidates:
        if candidate in STRENGTH_FACTOR_DISCOUNT_KEYS:
            return candidate
        alias = STRENGTH_FACTOR_DISCOUNT_ALIASES.get(candidate)
        if alias in STRENGTH_FACTOR_DISCOUNT_KEYS:
            return alias
    return None


def _bounded_strength_factor_adjustment(value: Decimal) -> Decimal:
    return min(
        MAX_STRENGTH_FACTOR_DISCOUNT_ADJUSTMENT,
        max(-MAX_STRENGTH_FACTOR_DISCOUNT_ADJUSTMENT, value),
    )


def _strength_factor_adjustment_from_row(row: Mapping[str, object]) -> Decimal | None:
    for key in (
        "adjustment",
        "model_adjustment",
        "multiple_adjustment",
        "discount_adjustment",
        "value",
    ):
        if key in row:
            return _bounded_strength_factor_adjustment(_percent_or_ratio(_decimal(row.get(key))))
    for key in ("discount_pct", "discount_percent"):
        if key in row:
            return _bounded_strength_factor_adjustment(
                -abs(_percent_or_ratio(_decimal(row.get(key))))
            )
    for key in ("premium_pct", "premium_percent"):
        if key in row:
            return _bounded_strength_factor_adjustment(
                abs(_percent_or_ratio(_decimal(row.get(key))))
            )
    return None


def _strength_factor_discount_key_from_row(row: Mapping[str, object]) -> str | None:
    linkage = _strength_factor_valuation_linkage(row)
    for key in (
        "discount_key",
        "discountKey",
        "multiple_discount_key",
        "multipleDiscountKey",
        "sellability_factor",
        "sellabilityFactor",
        "engine_driver",
        "engineDriver",
        "maps_to_subjective_input",
        "mapsToSubjectiveInput",
        "mapped_subjective_input",
        "mappedSubjectiveInput",
    ):
        for source in (row, linkage):
            resolved = _canonical_strength_factor_discount_key(source.get(key))
            if resolved:
                return resolved
    return None


def _strength_factor_valuation_linkage(row: Mapping[str, object]) -> Mapping[str, object]:
    for key in ("valuation_linkage", "valuationLinkage"):
        value = row.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _text_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _strength_factor_data_point_ids(row: Mapping[str, object]) -> list[str]:
    direct = [
        *_text_list(row.get("data_point_ids")),
        *_text_list(row.get("dataPointIds")),
    ]
    if direct:
        return list(dict.fromkeys(direct))[:8]

    points = row.get("dataPoints")
    if not isinstance(points, Sequence) or isinstance(points, (str, bytes, bytearray)):
        return []

    ids: list[str] = []
    for point in points:
        if not isinstance(point, Mapping):
            continue
        for key in ("dataPointId", "data_point_id", "questionId", "question_id"):
            value = point.get(key)
            if isinstance(value, str) and value.strip():
                ids.append(value.strip())
                break
    return list(dict.fromkeys(ids))[:8]


def _normalize_strength_factor_evidence_fields(row: Mapping[str, object]) -> JsonMap:
    normalized: JsonMap = dict(row)
    for source_key, target_key in STRENGTH_FACTOR_EVIDENCE_FIELD_ALIASES.items():
        if target_key in normalized:
            continue
        value = row.get(source_key)
        if value is not None and value != "":
            normalized[target_key] = value
    linkage = _strength_factor_valuation_linkage(row)
    for source_key, target_key in STRENGTH_FACTOR_LINKAGE_FIELD_ALIASES.items():
        if target_key in normalized:
            continue
        value = linkage.get(source_key)
        if value is not None and value != "":
            normalized[target_key] = value
    if "data_point_ids" not in normalized:
        data_point_ids = _strength_factor_data_point_ids(row)
        if data_point_ids:
            normalized["data_point_ids"] = data_point_ids
    return normalized


def normalize_strength_factor_discount_adjustments(raw: object) -> list[JsonMap]:
    """Normalize explicit strength-factor evidence into discount adjustments."""
    if raw is None:
        return []

    if isinstance(raw, Mapping):
        discount_key = _strength_factor_discount_key_from_row(raw)
        adjustment = _strength_factor_adjustment_from_row(raw)
        if discount_key and adjustment is not None and adjustment != 0:
            value_row = _normalize_strength_factor_evidence_fields(raw)
            return [
                {
                    **value_row,
                    "discount_key": discount_key,
                    "adjustment": adjustment,
                    "source": value_row.get("source") or "business_type_strength_factor",
                }
            ]

        nested = raw.get("rows") or raw.get("adjustments") or raw.get("evidence")
        if nested is not None:
            return normalize_strength_factor_discount_adjustments(nested)
        items: list[JsonMap] = []
        for raw_key, raw_value in raw.items():
            discount_key = _canonical_strength_factor_discount_key(raw_key)
            if not discount_key:
                continue
            value_row = (
                _normalize_strength_factor_evidence_fields(raw_value)
                if isinstance(raw_value, Mapping)
                else {}
            )
            adjustment = (
                _strength_factor_adjustment_from_row(value_row)
                if value_row
                else _bounded_strength_factor_adjustment(_percent_or_ratio(_decimal(raw_value)))
            )
            if adjustment is None or adjustment == 0:
                continue
            items.append(
                {
                    **value_row,
                    "discount_key": discount_key,
                    "adjustment": adjustment,
                    "source": value_row.get("source") or "business_type_strength_factor",
                }
            )
        return items

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        items = []
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            discount_key = _strength_factor_discount_key_from_row(entry)
            adjustment = _strength_factor_adjustment_from_row(entry)
            if not discount_key or adjustment is None or adjustment == 0:
                continue
            value_row = _normalize_strength_factor_evidence_fields(entry)
            items.append(
                {
                    **value_row,
                    "discount_key": discount_key,
                    "adjustment": adjustment,
                    "source": value_row.get("source") or "business_type_strength_factor",
                }
            )
        return items

    return []


def strength_factor_discount_adjustments_from_business_context(
    business_context: Mapping[str, object] | None,
    *,
    revenue: object = None,
    team_size: object = None,
) -> list[JsonMap]:
    """Read the non-breaking business_context bridge used by Titan -> ValuationIQ."""
    context = business_context if isinstance(business_context, Mapping) else {}

    adjustments: list[JsonMap] = []
    for key in STRENGTH_FACTOR_DISCOUNT_CONTEXT_KEYS:
        adjustments.extend(normalize_strength_factor_discount_adjustments(context.get(key)))

    maturity_context = context.get("business_growth_maturity") or context.get("growth_maturity")
    adjustments.extend(
        normalize_strength_factor_discount_adjustments(
            build_business_growth_maturity_discount_adjustments(
                maturity_context if isinstance(maturity_context, Mapping) else None,
                revenue=(
                    revenue if revenue is not None else _first_context_value(context, _REVENUE_KEYS)
                ),
                team_size=(
                    team_size
                    if team_size is not None
                    else _first_context_value(context, _TEAM_SIZE_KEYS)
                ),
            )
        )
    )
    return adjustments


_REVENUE_KEYS = (
    "revenue",
    "annual_revenue",
    "current_revenue",
    "latest_revenue",
)
_TEAM_SIZE_KEYS = (
    "team_size",
    "number_of_employees",
    "employee_count",
    "employees",
    "fte_count",
    "total_employees",
)


def _first_context_value(context: Mapping[str, object], keys: Sequence[str]) -> object:
    for key in keys:
        value = context.get(key)
        if value is not None and value != "":
            return value
    return None


def apply_strength_factor_discount_adjustments(
    adjustments: Mapping[str, object],
    strength_factor_discount_adjustments: object,
) -> tuple[dict[str, object], list[JsonMap]]:
    """Merge explicit strength-factor evidence into the multiple discount inputs."""
    normalized = normalize_strength_factor_discount_adjustments(
        strength_factor_discount_adjustments
    )
    if not normalized:
        return dict(adjustments), []

    merged: dict[str, object] = dict(adjustments)
    applied: list[JsonMap] = []
    for row in normalized:
        discount_key = row.get("discount_key")
        adjustment = row.get("adjustment")
        if not isinstance(discount_key, str) or not isinstance(adjustment, Decimal):
            continue
        before = _decimal(merged.get(discount_key))
        after = before + adjustment
        merged[discount_key] = after
        applied.append(
            {
                **row,
                "base_adjustment_before": before,
                "base_adjustment_after": after,
            }
        )
    return merged, applied


def annotate_discount_stack_with_strength_factor_evidence(
    stack: JsonMap,
    strength_factor_evidence: Sequence[Mapping[str, object]],
) -> JsonMap:
    """Attach strength-factor provenance to discount rows and the raw stack."""
    if not strength_factor_evidence:
        return stack

    by_key: dict[str, list[Mapping[str, object]]] = {}
    for evidence in strength_factor_evidence:
        key = evidence.get("discount_key")
        if isinstance(key, str):
            by_key.setdefault(key, []).append(evidence)

    for row in stack.get("rows", []):
        if not isinstance(row, dict):
            continue
        evidence_rows = by_key.get(str(row.get("key") or ""))
        if not evidence_rows:
            continue
        factor_labels = [
            str(item.get("factor_label") or item.get("factor_key") or "strength factor")
            for item in evidence_rows[:3]
        ]
        multiple_discount_key = _first_evidence_text(
            evidence_rows,
            ("multiple_discount_key", "multipleDiscountKey", "discount_key", "discountKey"),
        ) or str(row.get("key") or "")
        row_evidence = []
        for item in evidence_rows:
            evidence_item = dict(item)
            if multiple_discount_key:
                evidence_item.setdefault("multiple_discount_key", multiple_discount_key)
            row_evidence.append(evidence_item)
        row["source"] = "strength_factor_evidence"
        if multiple_discount_key:
            row["multiple_discount_key"] = multiple_discount_key
        row["rationale"] = (
            "Adjusted from captured business-type strength-factor evidence: "
            + ", ".join(factor_labels)
        )
        row["strength_factor_evidence"] = row_evidence
        row["strength_factor_evidence_count"] = len(evidence_rows)

    stack["strength_factor_evidence"] = [dict(item) for item in strength_factor_evidence]
    stack["strength_factor_policy"] = _strength_factor_policy_name(strength_factor_evidence)
    return stack


def _first_evidence_text(
    evidence_rows: Sequence[Mapping[str, object]],
    keys: Sequence[str],
) -> str | None:
    for evidence in evidence_rows:
        for key in keys:
            value = evidence.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _strength_factor_policy_name(
    strength_factor_evidence: Sequence[Mapping[str, object]],
) -> str:
    if any(
        evidence.get("source") == "business_growth_maturity_policy"
        for evidence in strength_factor_evidence
    ):
        return "business_context_and_growth_maturity_policy"
    return "explicit_business_context_adjustments_only"
