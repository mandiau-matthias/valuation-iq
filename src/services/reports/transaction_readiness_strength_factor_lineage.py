"""Strength-factor lineage for transaction-readiness evidence rows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.services.reports.transaction_readiness_labels import text as _text

JsonMap = dict[str, object]

_OWNER_STRENGTH_FACTOR_HINTS = (
    "owner_dependency",
    "owner_dependence",
    "owner_hours_dependency",
)


def _as_dict(value: object) -> JsonMap:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return _as_dict(dumped)
    return {}


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _text_value(value: object) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _text_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [text for item in value if (text := _text_value(item))]


def _dedupe_text(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _lineage_rows_from_mapping(row: JsonMap) -> list[JsonMap]:
    rows: list[JsonMap] = []
    for key in ("strength_factor_evidence", "strength_factor_discount_evidence"):
        value = row.get(key)
        if isinstance(value, Mapping):
            rows.append(_as_dict(value))
        else:
            rows.extend(_as_dict(item) for item in _as_list(value) if isinstance(item, Mapping))
    if _is_strength_factor_lineage_row(row):
        rows.append(row)
    return rows


def _is_strength_factor_lineage_row(row: JsonMap) -> bool:
    return any(
        row.get(key)
        for key in (
            "factor_key",
            "factorKey",
            "multiple_discount_key",
            "multipleDiscountKey",
            "data_point_ids",
            "dataPointIds",
            "dataPoints",
        )
    )


def _lineage_source_rows(context: JsonMap) -> list[JsonMap]:
    rows: list[JsonMap] = []
    for key in (
        "multiple_waterfall_steps",
        "valuation_waterfall_steps",
        "discount_waterfall",
        "multiple_pipeline",
    ):
        rows.extend(
            _as_dict(item) for item in _as_list(context.get(key)) if isinstance(item, Mapping)
        )

    for key in ("advisor_multiple_transparency", "multiple_build_up", "discount_build_up"):
        container = _as_dict(context.get(key))
        for row_key in ("discount_rows", "rows", "waterfall", "discount_waterfall"):
            rows.extend(
                _as_dict(item)
                for item in _as_list(container.get(row_key))
                if isinstance(item, Mapping)
            )
        discounts = _as_dict(container.get("discounts"))
        for row_key in ("rows", "discount_rows"):
            rows.extend(
                _as_dict(item)
                for item in _as_list(discounts.get(row_key))
                if isinstance(item, Mapping)
            )
    return rows


def _lineage_factor_keys(row: JsonMap) -> list[str]:
    keys = [
        _text_value(row.get("factor_key")),
        _text_value(row.get("factorKey")),
    ]
    keys.extend(_text_list(row.get("strength_factor_keys")))
    keys.extend(_text_list(row.get("strengthFactorKeys")))
    return _dedupe_text(keys)


def _lineage_discount_key(row: JsonMap) -> str:
    linkage = _as_dict(row.get("valuation_linkage") or row.get("valuationLinkage"))
    for source in (row, linkage):
        for key in (
            "multiple_discount_key",
            "multipleDiscountKey",
            "strength_factor_discount_key",
            "strengthFactorDiscountKey",
            "discount_key",
            "discountKey",
        ):
            value = _text_value(source.get(key))
            if value:
                return value
    keys = _text_list(row.get("strength_factor_multiple_discount_keys"))
    return keys[0] if keys else ""


def _lineage_data_point_ids(row: JsonMap) -> list[str]:
    direct = [
        *_text_list(row.get("data_point_ids")),
        *_text_list(row.get("dataPointIds")),
        *_text_list(row.get("strength_factor_data_point_ids")),
    ]
    if direct:
        return _dedupe_text(direct)

    points = row.get("dataPoints")
    ids: list[str] = []
    for point in _as_list(points):
        point_map = _as_dict(point)
        for key in ("dataPointId", "data_point_id", "questionId", "question_id"):
            value = _text_value(point_map.get(key))
            if value:
                ids.append(value)
                break
    return _dedupe_text(ids)


def _is_owner_strength_factor_row(row: JsonMap) -> bool:
    searchable = " ".join(
        [
            *_lineage_factor_keys(row),
            _lineage_discount_key(row),
            *_lineage_data_point_ids(row),
        ]
    ).lower()
    return any(hint in searchable for hint in _OWNER_STRENGTH_FACTOR_HINTS)


def owner_strength_factor_lineage(context: JsonMap, locale: str) -> JsonMap:
    factor_keys: list[str] = []
    data_point_ids: list[str] = []
    discount_keys: list[str] = []
    for source_row in _lineage_source_rows(context):
        for row in _lineage_rows_from_mapping(source_row):
            if not _is_owner_strength_factor_row(row):
                continue
            factor_keys.extend(_lineage_factor_keys(row))
            data_point_ids.extend(_lineage_data_point_ids(row))
            discount_key = _lineage_discount_key(row)
            if discount_key:
                discount_keys.append(discount_key)

    factor_keys = _dedupe_text(factor_keys)
    data_point_ids = _dedupe_text(data_point_ids)
    discount_keys = _dedupe_text(discount_keys)
    if not (factor_keys or data_point_ids or discount_keys):
        return {}

    discount_display = ", ".join(discount_keys[:2])
    data_point_display = ", ".join(data_point_ids[:4])
    source_parts = []
    if discount_display:
        source_parts.append(
            f"{_text(locale, 'Multiplekorting', 'Multiple discount', 'Décote de multiple')}: {discount_display}"
        )
    if data_point_display:
        source_parts.append(
            f"{_text(locale, 'Datapunten', 'Data points', 'Points de données')}: {data_point_display}"
        )

    rebuttal = (
        f"{_text(locale, 'Versterk en hertest', 'Strengthen and retest', 'Renforcer et retester')}"
        f" {discount_display or _text(locale, 'eigenaarsafhankelijkheid', 'owner dependency', 'la dépendance au dirigeant')}"
    )
    if data_point_display:
        rebuttal = (
            f"{rebuttal} {_text(locale, 'met bewijs voor', 'with evidence for', 'avec preuves pour')}"
            f" {data_point_display}"
        )

    return {
        "multiple_discount_key": discount_keys[0] if discount_keys else None,
        "strength_factor_keys": factor_keys,
        "strength_factor_data_point_ids": data_point_ids,
        "source": "; ".join(source_parts),
        "rebuttal_evidence_needed": rebuttal,
    }
