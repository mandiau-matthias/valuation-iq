"""Shared helpers for report readiness context builders."""

from typing import TypeVar

_T = TypeVar("_T")
JsonMap = dict[str, object]


def as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def as_dict(value: object) -> JsonMap:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return as_dict(dumped)
    return {}


def first_present(*values: _T | None) -> _T | None:
    for value in values:
        if value is not None:
            return value
    return None


def safe_int(value: object) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0
