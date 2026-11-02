"""Request-metadata access helpers for report context builders."""

from typing import TypeAlias, cast

from src.domain.report_contact.sanitize import sanitize_report_email, sanitize_report_phone
from src.services.reports.protocol_adapter import _attr, _unwrap

MetadataMap: TypeAlias = dict[str, object]


def get_request_metadata(request: object | None) -> MetadataMap | None:
    """Return request metadata only when it is a plain mapping."""
    if not request or not hasattr(request, "metadata"):
        return None
    metadata = _unwrap(getattr(request, "metadata", None))
    return cast(MetadataMap, metadata) if isinstance(metadata, dict) else None


def get_metadata_bool(request: object | None, key: str, default: bool = False) -> bool:
    """Get a boolean value from request metadata with an attribute fallback."""
    metadata = get_request_metadata(request)
    val = metadata.get(key) if metadata else _attr(request, key)
    if val is None:
        return default
    if isinstance(val, str):
        normalized = val.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return bool(val)


def get_metadata_str(request: object | None, key: str) -> str | None:
    """Get a stripped string value from request metadata with contact sanitization."""
    metadata = get_request_metadata(request)
    val = metadata.get(key) if metadata and metadata.get(key) is not None else _attr(request, key)
    if val is None:
        return None
    rendered = str(val).strip()
    if not rendered:
        return None
    if key == "accountant_email":
        return sanitize_report_email(rendered)
    if key == "accountant_phone":
        return sanitize_report_phone(rendered)
    return rendered


def get_metadata_float(request: object | None, key: str) -> float | None:
    """Get a float value from request metadata with an attribute fallback."""
    metadata = get_request_metadata(request)
    val = metadata.get(key) if metadata and metadata.get(key) is not None else _attr(request, key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def get_accountant_name(request: object | None) -> str | None:
    """Get accountant firm name from request metadata."""
    return get_metadata_str(request, "accountant_firm_name")


def get_accountant_logo(request: object | None) -> str | None:
    """Get accountant logo URL from request metadata."""
    return get_metadata_str(request, "accountant_logo_url")
