"""Shared mapping coercion helpers for report context builders."""

from collections.abc import Mapping
from typing import Protocol, TypeAlias, runtime_checkable

ReportMap: TypeAlias = dict[str, object]


@runtime_checkable
class ModelDumpLike(Protocol):
    def model_dump(self) -> object: ...


def as_report_map(value: object) -> ReportMap | None:
    """Return a plain report map for dict wrappers, pydantic-style models, or mappings."""
    underlying = getattr(value, "_data", None)
    if isinstance(underlying, dict):
        return dict(underlying)
    if isinstance(value, ModelDumpLike):
        dumped = value.model_dump()
        return dict(dumped) if isinstance(dumped, Mapping) else None
    if isinstance(value, Mapping):
        return dict(value)
    return None


def mapping_rows(value: object) -> list[ReportMap]:
    """Coerce a list of report payload rows, dropping non-mapping entries."""
    rows = value if isinstance(value, list) else []
    return [row_map for row in rows if (row_map := as_report_map(row)) is not None]
