"""Helpers for normalizing Titan weighted business-type mix payloads."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Dict, List, Mapping, Optional, Tuple

JsonObject = Dict[str, object]
RawSegment = Mapping[str, object]


def _clean_business_type_id(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_title(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned[:255] if cleaned else None


def _parse_weight(value: object) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        weight = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("business_type_mix weights must be numeric") from exc
    if weight < 0:
        raise ValueError("business_type_mix weights cannot be negative")
    return weight


def _has_explicit_weight(value: object) -> bool:
    return value is not None and value != ""


def _weight_to_number(value: Decimal) -> float | int:
    normalized = value.quantize(Decimal("0.01"))
    if normalized == normalized.to_integral_value():
        return int(normalized)
    return float(normalized)


def _raw_mix_segments(business_type_mix: object) -> List[RawSegment]:
    segments: List[RawSegment] = []
    if not isinstance(business_type_mix, list) or not business_type_mix:
        return segments

    for item in business_type_mix:
        if not isinstance(item, Mapping):
            raise ValueError("business_type_mix entries must be objects")
        segments.append(item)
    return segments


def _raw_sotp_segments(business_type_segments: object) -> List[JsonObject]:
    segments: List[JsonObject] = []
    if not isinstance(business_type_segments, list) or not business_type_segments:
        return segments

    for item in business_type_segments:
        if not isinstance(item, Mapping):
            raise ValueError("business_type_segments entries must be objects")
        segments.append(
            {
                "business_type_id": item.get("business_type_id"),
                "business_type_title": item.get("business_type_title") or item.get("title"),
                "weight": item.get("weight"),
            }
        )
    return segments


def _raw_weight_segments(business_type_weights: object) -> List[JsonObject]:
    if not isinstance(business_type_weights, Mapping) or not business_type_weights:
        return []
    return [
        {"business_type_id": str(key), "weight": value}
        for key, value in business_type_weights.items()
    ]


def _raw_primary_segment(business_type_id: object) -> List[JsonObject]:
    primary_id = _clean_business_type_id(business_type_id)
    if not primary_id:
        return []
    return [{"business_type_id": primary_id, "weight": 100}]


def _raw_segments_from_sources(
    *,
    business_type_mix: object,
    business_type_segments: object,
    business_type_weights: object,
    business_type_id: object,
) -> List[RawSegment]:
    mix_segments = _raw_mix_segments(business_type_mix)
    if mix_segments:
        return mix_segments

    sotp_segments = _raw_sotp_segments(business_type_segments)
    if sotp_segments:
        return sotp_segments

    weight_segments = _raw_weight_segments(business_type_weights)
    if weight_segments:
        return weight_segments

    return _raw_primary_segment(business_type_id)


def _merge_business_type_title(target: JsonObject, raw: RawSegment) -> None:
    if "business_type_title" in target:
        return
    title = _clean_title(raw.get("business_type_title"))
    if title:
        target["business_type_title"] = title


def _compact_segments(
    raw_segments: List[RawSegment],
) -> Tuple[Dict[str, JsonObject], Dict[str, Optional[Decimal]], Dict[str, bool]]:
    compact: Dict[str, JsonObject] = {}
    weight_by_id: Dict[str, Optional[Decimal]] = {}
    has_explicit_weight_by_id: Dict[str, bool] = {}

    for raw in raw_segments:
        segment_id = _clean_business_type_id(raw.get("business_type_id"))
        if not segment_id:
            raise ValueError("Each business_type_mix segment must include business_type_id")

        weight = _parse_weight(raw.get("weight"))
        has_weight = _has_explicit_weight(raw.get("weight"))
        if segment_id in compact:
            current_weight = weight_by_id.get(segment_id)
            weight_by_id[segment_id] = (current_weight or Decimal("0")) + (weight or Decimal("0"))
            has_explicit_weight_by_id[segment_id] = (
                has_explicit_weight_by_id[segment_id] or has_weight
            )
            _merge_business_type_title(compact[segment_id], raw)
            continue

        compact[segment_id] = {"business_type_id": segment_id}
        _merge_business_type_title(compact[segment_id], raw)
        weight_by_id[segment_id] = weight
        has_explicit_weight_by_id[segment_id] = has_weight

    return compact, weight_by_id, has_explicit_weight_by_id


def _explicit_weight_total(weight_by_id: Mapping[str, Optional[Decimal]]) -> Decimal:
    return sum((weight or Decimal("0") for weight in weight_by_id.values()), Decimal("0"))


def _normalized_share(
    *,
    segment_id: str,
    compact_size: int,
    has_explicit_weights: bool,
    explicit_total: Decimal,
    weight_by_id: Mapping[str, Optional[Decimal]],
) -> Decimal:
    if has_explicit_weights:
        return (weight_by_id[segment_id] or Decimal("0")) / explicit_total
    return Decimal("1") / Decimal(compact_size)


def _normalized_segments(
    *,
    compact: Dict[str, JsonObject],
    weight_by_id: Mapping[str, Optional[Decimal]],
    has_explicit_weight_by_id: Mapping[str, bool],
) -> List[JsonObject]:
    explicit_total = _explicit_weight_total(weight_by_id)
    has_explicit_weights = any(has_explicit_weight_by_id.values())
    if has_explicit_weights and explicit_total <= 0:
        raise ValueError("business_type_mix must contain at least one positive-weight segment")

    normalized_segments: List[JsonObject] = []
    for segment_id, segment in compact.items():
        share = _normalized_share(
            segment_id=segment_id,
            compact_size=len(compact),
            has_explicit_weights=has_explicit_weights,
            explicit_total=explicit_total,
            weight_by_id=weight_by_id,
        )
        normalized_weight = _weight_to_number(share * Decimal("100"))
        if normalized_weight != 0:
            normalized_segments.append({**segment, "weight": normalized_weight})

    if not normalized_segments:
        raise ValueError("business_type_mix must contain at least one positive-weight segment")

    normalized_segments.sort(key=lambda item: Decimal(str(item["weight"])), reverse=True)
    return normalized_segments


def _normalized_weights(normalized_segments: List[JsonObject]) -> JsonObject:
    return {str(segment["business_type_id"]): segment["weight"] for segment in normalized_segments}


def normalize_business_type_mix_fields(
    *,
    business_type_mix: object,
    business_type_segments: object = None,
    business_type_weights: object = None,
    business_type_id: object = None,
) -> Tuple[Optional[str], Optional[List[JsonObject]], Optional[JsonObject]]:
    """Normalize list/map/singular business-type input into a weighted mix.

    Returns ``(primary_business_type_id, normalized_mix, normalized_weights)``.
    The primary is always the highest-weight segment when a mix can be derived.
    """
    explicit_empty_mix = isinstance(business_type_mix, list) and len(business_type_mix) == 0
    if explicit_empty_mix:
        raise ValueError("business_type_mix must contain at least one segment")

    raw_segments = _raw_segments_from_sources(
        business_type_mix=business_type_mix,
        business_type_segments=business_type_segments,
        business_type_weights=business_type_weights,
        business_type_id=business_type_id,
    )
    if not raw_segments:
        return None, None, None

    compact, weight_by_id, has_explicit_weight_by_id = _compact_segments(raw_segments)
    normalized_segments = _normalized_segments(
        compact=compact,
        weight_by_id=weight_by_id,
        has_explicit_weight_by_id=has_explicit_weight_by_id,
    )
    primary = str(normalized_segments[0]["business_type_id"])
    return primary, normalized_segments, _normalized_weights(normalized_segments)
