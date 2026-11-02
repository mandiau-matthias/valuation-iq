"""Shared historical EBITDA weight normalization for API request schemas."""

from decimal import Decimal
from typing import Optional

from src.domain.financial_arithmetic import decimal_number


def _historical_weight_items(value: object) -> dict[object, object]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, list):
        raise ValueError("historical_ebitda_weights must be a year-to-weight map or list")
    return _historical_weight_items_from_rows(value)


def _historical_weight_items_from_rows(rows: list[object]) -> dict[object, object]:
    raw_items: dict[object, object] = {}
    for entry in rows:
        item = _historical_weight_item_from_row(entry)
        if item is not None:
            year, weight = item
            year_key = int(str(year))
            if year_key in raw_items:
                raise ValueError("historical_ebitda_weights cannot contain duplicate fiscal years")
            raw_items[year_key] = weight
    return raw_items


def _historical_weight_item_from_row(entry: object) -> tuple[object, object] | None:
    if isinstance(entry, dict):
        return _historical_weight_item_from_mapping(entry)
    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        return entry[0], entry[1]
    return None


def _historical_weight_item_from_mapping(
    entry: dict[object, object],
) -> tuple[object, object] | None:
    year = entry.get("year") or entry.get("fiscal_year") or entry.get("fiscalYear")
    weight = entry.get("weight")
    if weight is None:
        weight = entry.get("percentage")
        if weight is None:
            weight = entry.get("pct")
    if year is None or weight is None:
        return None
    return year, weight


def normalize_historical_ebitda_weights(value: object) -> Optional[dict[int, Decimal]]:
    """Normalize historical EBITDA weights from a year map or row list."""
    if value is None or value == "" or value == []:
        return None

    normalized: dict[int, Decimal] = {}
    for year, weight in _historical_weight_items(value).items():
        year_int = int(str(year))
        weight_dec = decimal_number(weight, "historical EBITDA weight")
        if year_int in normalized:
            raise ValueError("historical_ebitda_weights cannot contain duplicate fiscal years")
        if weight_dec < 0:
            raise ValueError("historical_ebitda_weights cannot contain negative weights")
        normalized[year_int] = weight_dec
    return normalized or None
