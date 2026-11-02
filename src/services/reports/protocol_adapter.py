"""Protocol adapters for dict-backed valuation payloads."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date, datetime
from typing import Any, cast


def _parse_date(value: object) -> date | None:
    """Parse date from string, datetime, or date."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value[:10]).date()
        except (ValueError, TypeError):
            return None
    return None


def _wrap_for_protocol(val: object) -> object:
    """Recursively wrap dicts for attribute access."""
    if val is None:
        return None
    if isinstance(val, dict):
        return DictWrapper(val)
    if isinstance(val, list):
        return [_wrap_for_protocol(v) for v in val]
    return val


def _unwrap(val: object) -> object:
    """Unwrap a DictWrapper back to a plain dict."""
    if isinstance(val, DictWrapper):
        return val._data
    return val


def coerce_json_object(candidate: object) -> dict[str, Any] | None:
    """Coerce a dict, DictWrapper, Mapping, or Pydantic model to a plain dict.

    Used anywhere a JSON-shaped response field must feed Jinja/report context
    without assuming a single carrier type.
    """
    if candidate is None:
        return None
    unwrapped = _unwrap(candidate)
    if isinstance(unwrapped, dict):
        return unwrapped
    if isinstance(unwrapped, Mapping):
        return dict(unwrapped)
    model_dump = getattr(unwrapped, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
            return dict(dumped) if isinstance(dumped, Mapping) else None
        except Exception:  # pragma: no cover — defensive against subclass quirks
            return None
    return None


def _sanitize_market_data_source_display(raw: object, managed_dataset_label: str) -> object:
    """Hide internal engine paths from report-visible provenance labels."""
    if raw is None:
        return None
    rendered = str(raw).strip()
    if not rendered:
        return None
    if "economic_context" in rendered.lower():
        return managed_dataset_label
    return raw


def _attr(obj: object, name: str, default: object = None) -> object:
    """Attribute access that applies default when DictWrapper returns None."""
    val = getattr(obj, name, default)
    if val is None:
        return default
    return val


class DictWrapper:
    """Expose a dict through attribute access for protocol compatibility."""

    __slots__ = ("_data",)

    def __init__(self, data: object):
        payload = cast(dict[str, object], data) if isinstance(data, dict) else {}
        object.__setattr__(self, "_data", payload)

    def __getattr__(self, name: str) -> object:
        if name.startswith("_"):
            raise AttributeError(name)
        val = self._data.get(name)
        return _wrap_for_protocol(val)

    def get(self, key: str, default: object = None) -> object:
        if key in self._data:
            return _wrap_for_protocol(self._data[key])
        return default

    def __getitem__(self, key: str) -> object:
        return _wrap_for_protocol(self._data[key])

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __bool__(self) -> bool:
        return bool(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __repr__(self) -> str:
        return f"DictWrapper(keys={list(self._data.keys())[:5]}...)"
