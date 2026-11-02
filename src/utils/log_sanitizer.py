"""Shared redaction helpers for structured logs and audit metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

REDACTED = "<REDACTED>"
TRUNCATED = "<TRUNCATED>"

SENSITIVE_KEY_MARKERS = (
    "authorization",
    "cookie",
    "credential",
    "csrf",
    "email",
    "jwt",
    "key",
    "password",
    "phone",
    "refresh",
    "secret",
    "session",
    "signature",
    "token",
)

BUSINESS_DATA_KEY_MARKERS = (
    "arr",
    "asset",
    "bank",
    "cash",
    "company",
    "customer",
    "debt",
    "ebit",
    "ebitda",
    "enterprise_value",
    "equity",
    "financial",
    "income",
    "liabilit",
    "margin",
    "owner",
    "payroll",
    "profit",
    "revenue",
    "social",
    "ssn",
    "valuation",
    "vat",
    "working_capital",
)

LOW_RISK_KEYS = {
    "client_host",
    "content_length",
    "content_type",
    "correlation_id",
    "duration_ms",
    "error_id",
    "error_type",
    "event_type",
    "method",
    "path",
    "request_id",
    "request_body_size",
    "request_body_type",
    "response_size",
    "status_code",
    "success",
    "timestamp",
    "user_agent",
}


def _normalized_key(key: object) -> str:
    return str(key).lower().replace("-", "_")


def is_sensitive_log_key(key: object) -> bool:
    normalized = _normalized_key(key)
    return any(marker in normalized for marker in SENSITIVE_KEY_MARKERS)


def is_business_data_log_key(key: object) -> bool:
    normalized = _normalized_key(key)
    return any(marker in normalized for marker in BUSINESS_DATA_KEY_MARKERS)


def should_redact_log_key(key: object) -> bool:
    normalized = _normalized_key(key)
    if normalized in LOW_RISK_KEYS:
        return False
    return is_sensitive_log_key(normalized) or is_business_data_log_key(normalized)


def sanitize_log_value(
    value: Any,
    *,
    key: object | None = None,
    max_depth: int = 6,
    max_items: int = 20,
) -> Any:
    """Return a JSON-friendly copy of ``value`` with sensitive fields redacted."""
    if key is not None and should_redact_log_key(key):
        return REDACTED

    if max_depth <= 0:
        return TRUNCATED

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for index, (item_key, item_value) in enumerate(value.items()):
            if index >= max_items:
                sanitized["..."] = f"{len(value) - max_items} more keys"
                break
            sanitized[str(item_key)] = sanitize_log_value(
                item_value,
                key=item_key,
                max_depth=max_depth - 1,
                max_items=max_items,
            )
        return sanitized

    if isinstance(value, bytes):
        return "<BINARY>"

    if isinstance(value, str):
        return value

    if isinstance(value, Sequence):
        sanitized_items = [
            sanitize_log_value(item, max_depth=max_depth - 1, max_items=max_items)
            for item in list(value)[:max_items]
        ]
        if len(value) > max_items:
            sanitized_items.append(f"... and {len(value) - max_items} more items")
        return sanitized_items

    return value


def sanitize_log_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], sanitize_log_value(mapping))
