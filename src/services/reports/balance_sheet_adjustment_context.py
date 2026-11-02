"""Balance-sheet adjustment and tax-latency report context helpers."""

from collections.abc import Mapping, Sequence
from decimal import Decimal

from src.services.reports.protocol_adapter import DictWrapper, _attr, _unwrap
from src.utils.decimal_helpers import safe_decimal_or_zero, safe_float

JsonMap = dict[str, object]


def _unwrap_if_needed(value: object) -> object:
    return _unwrap(value) if isinstance(value, DictWrapper) else value


def _as_json_map(value: object) -> JsonMap | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def _text(value: object) -> str:
    return str(value or "").strip()


def _balance_sheet_adjustments_payload(request: object | None) -> object | None:
    if not request:
        return None
    if isinstance(request, Mapping):
        return request.get("balance_sheet_adjustments")
    if hasattr(request, "balance_sheet_adjustments"):
        return getattr(request, "balance_sheet_adjustments")
    getter = getattr(request, "get", None)
    if callable(getter):
        return getter("balance_sheet_adjustments")
    return None


def tax_latency_rows_from_balance_sheet_adjustments(
    raw_adjustments: Sequence[object],
) -> list[JsonMap]:
    """Build PDF tax-latency rows from balance-sheet adjustment payloads."""
    rows: list[JsonMap] = []
    for adjustment in raw_adjustments:
        fields = _tax_latency_adjustment_fields(adjustment)
        if fields is not None:
            rows.append(_tax_latency_adjustment_row(fields))
    return rows


def _tax_latency_adjustment_fields(adjustment: object) -> JsonMap | None:
    adjustment_d = _unwrap_if_needed(adjustment)
    adjustment_map = _as_json_map(adjustment_d)
    if adjustment_map is not None:
        return _tax_latency_mapping_fields(adjustment_map)
    return _tax_latency_object_fields(adjustment_d)


def _tax_latency_mapping_fields(adjustment: JsonMap) -> JsonMap | None:
    if adjustment.get("category", "other") != "tax_latency":
        return None
    label = adjustment.get("label") or ""
    return {
        "description": _text(adjustment.get("description") or label),
        "temporary_difference": adjustment.get("temporary_difference"),
        "tax_rate": adjustment.get("tax_rate"),
        "tax_latency_type": adjustment.get("tax_latency_type"),
        "amount": adjustment.get("amount", 0),
        "type": adjustment.get("type", "subtract"),
        "account_code": adjustment.get("account_code"),
    }


def _tax_latency_object_fields(adjustment: object) -> JsonMap | None:
    if _attr(adjustment, "category", "other") != "tax_latency":
        return None
    label = _attr(adjustment, "label", "")
    return {
        "description": _text(_attr(adjustment, "description", None) or label),
        "temporary_difference": _attr(adjustment, "temporary_difference", None),
        "tax_rate": _attr(adjustment, "tax_rate", None),
        "tax_latency_type": _attr(adjustment, "tax_latency_type", None),
        "amount": _attr(adjustment, "amount", 0),
        "type": _attr(adjustment, "type", "subtract"),
        "account_code": _attr(adjustment, "account_code", None),
    }


def _tax_latency_adjustment_row(fields: JsonMap) -> JsonMap:
    temporary_difference = fields.get("temporary_difference")
    tax_rate = fields.get("tax_rate")
    amount_abs = safe_decimal_or_zero(fields.get("amount", 0))
    adjustment_type = fields.get("type", "subtract")
    latency_type = fields.get("tax_latency_type") or (
        "active" if adjustment_type == "add" else "passive"
    )
    difference_decimal = (
        safe_decimal_or_zero(temporary_difference)
        if temporary_difference is not None
        else abs(amount_abs)
    )
    rate_decimal = safe_decimal_or_zero(tax_rate) if tax_rate is not None else Decimal("25")
    row: JsonMap = {
        "type": latency_type,
        "description": fields.get("description"),
        "temporary_difference": safe_float(difference_decimal),
        "tax_rate": safe_float(rate_decimal),
        "amount": _tax_latency_amount(
            amount_abs=amount_abs,
            adjustment_type=adjustment_type,
            latency_type=latency_type,
            difference_decimal=difference_decimal,
            rate_decimal=rate_decimal,
            has_tax_formula=temporary_difference is not None and tax_rate is not None,
        ),
    }
    account_code = fields.get("account_code")
    if account_code:
        row["account_code"] = account_code
    return row


def _tax_latency_amount(
    *,
    amount_abs: Decimal,
    adjustment_type: object,
    latency_type: object,
    difference_decimal: Decimal,
    rate_decimal: Decimal,
    has_tax_formula: bool,
) -> float:
    signed_amount = amount_abs if adjustment_type == "add" else -amount_abs
    if not has_tax_formula:
        return safe_float(signed_amount)
    core_amount = difference_decimal * (rate_decimal / Decimal("100"))
    if latency_type == "passive":
        core_amount = -core_amount
    return safe_float(core_amount)


def extract_tax_latencies(
    *,
    request: object | None,
    step_data: Mapping[str, object],
) -> list[JsonMap]:
    """Extract report tax latencies from Step 7, request payload, or BSA fallback."""
    latencies = _json_rows_from_list(step_data.get("tax_latencies", []))
    if latencies:
        return latencies

    step_adjustments = step_data.get("balance_sheet_adjustments")
    if isinstance(step_adjustments, list):
        rows = tax_latency_rows_from_balance_sheet_adjustments(step_adjustments)
        if rows:
            return rows

    raw_latencies = _tax_latencies_payload(request)
    if raw_latencies:
        return _tax_latency_rows_from_payload(raw_latencies)

    raw_adjustments = _balance_sheet_adjustments_payload(request)
    if raw_adjustments and isinstance(raw_adjustments, list):
        rows = tax_latency_rows_from_balance_sheet_adjustments(raw_adjustments)
        if rows:
            return rows

    return []


def _json_rows_from_list(rows: object) -> list[JsonMap]:
    if not isinstance(rows, list):
        return []
    return [row for row in (_as_json_map(item) for item in rows) if row is not None]


def _tax_latencies_payload(request: object | None) -> object | None:
    if isinstance(request, Mapping) and request.get("tax_latencies"):
        return request.get("tax_latencies")
    if request and hasattr(request, "tax_latencies") and getattr(request, "tax_latencies"):
        return getattr(request, "tax_latencies")
    return None


def _tax_latency_rows_from_payload(raw_latencies: object) -> list[JsonMap]:
    raw_latencies = _unwrap_if_needed(raw_latencies)
    if not isinstance(raw_latencies, list):
        return []

    result: list[JsonMap] = []
    for latency in raw_latencies:
        row = _tax_latency_row_from_payload(latency)
        if row is not None:
            result.append(row)
    return result


def _tax_latency_row_from_payload(latency: object) -> JsonMap | None:
    latency_d = _unwrap_if_needed(latency)
    latency_map = _as_json_map(latency_d)
    if latency_map is not None:
        diff = safe_decimal_or_zero(latency_map.get("temporary_difference", 0))
        raw_rate = latency_map.get("tax_rate", 25)
        latency_type = latency_map.get("type", "passive")
        description = latency_map.get("description", "")
        account_code = latency_map.get("account_code")
    elif latency_d is not None:
        diff = safe_decimal_or_zero(_attr(latency_d, "temporary_difference", 0))
        raw_rate = _attr(latency_d, "tax_rate", 25)
        latency_type = _attr(latency_d, "type", "passive")
        description = _attr(latency_d, "description", "")
        account_code = _attr(latency_d, "account_code", None)
    else:
        return None

    rate = safe_decimal_or_zero(raw_rate) / Decimal("100")
    amount = diff * rate
    if latency_type == "passive":
        amount = -amount
    row: JsonMap = {
        "type": latency_type,
        "description": description,
        "temporary_difference": safe_float(diff),
        "tax_rate": safe_float(safe_decimal_or_zero(raw_rate)),
        "amount": safe_float(amount),
    }
    if account_code:
        row["account_code"] = account_code
    return row


def extract_balance_sheet_adjustments(
    *,
    request: object | None,
    step_data: Mapping[str, object],
) -> list[JsonMap]:
    """Extract report balance-sheet adjustments from Step 7 or request payload."""
    raw_step_adjustments = step_data.get("balance_sheet_adjustments", [])
    adjustments = (
        [_as_json_map(row) for row in raw_step_adjustments]
        if isinstance(raw_step_adjustments, list)
        else []
    )
    adjustments = [row for row in adjustments if row is not None]
    if adjustments:
        return adjustments

    raw_adjustments = _balance_sheet_adjustments_payload(request)
    if not (raw_adjustments and isinstance(raw_adjustments, list)):
        return []

    result: list[JsonMap] = []
    for adjustment in raw_adjustments:
        adjustment_d = _unwrap_if_needed(adjustment)
        adjustment_map = _as_json_map(adjustment_d)
        if adjustment_map is not None:
            row: JsonMap = {
                "id": adjustment_map.get("id", ""),
                "label": adjustment_map.get("label", ""),
                "amount": safe_float(safe_decimal_or_zero(adjustment_map.get("amount", 0))),
                "type": adjustment_map.get("type", "subtract"),
                "category": adjustment_map.get("category", "other"),
                "description": adjustment_map.get("description"),
                "account_code": adjustment_map.get("account_code"),
            }
            temporary_difference = adjustment_map.get("temporary_difference")
            tax_rate = adjustment_map.get("tax_rate")
            tax_latency_type = adjustment_map.get("tax_latency_type")
        elif hasattr(adjustment_d, "label"):
            row = {
                "id": _attr(adjustment_d, "id", ""),
                "label": _attr(adjustment_d, "label", ""),
                "amount": safe_float(safe_decimal_or_zero(_attr(adjustment_d, "amount", 0))),
                "type": _attr(adjustment_d, "type", "subtract"),
                "category": _attr(adjustment_d, "category", "other"),
                "description": _attr(adjustment_d, "description", None),
                "account_code": _attr(adjustment_d, "account_code", None),
            }
            temporary_difference = _attr(adjustment_d, "temporary_difference", None)
            tax_rate = _attr(adjustment_d, "tax_rate", None)
            tax_latency_type = _attr(adjustment_d, "tax_latency_type", None)
        else:
            continue

        if temporary_difference is not None:
            row["temporary_difference"] = safe_float(safe_decimal_or_zero(temporary_difference))
        if tax_rate is not None:
            row["tax_rate"] = safe_float(safe_decimal_or_zero(tax_rate))
        if tax_latency_type is not None:
            row["tax_latency_type"] = tax_latency_type
        result.append(row)

    return result
