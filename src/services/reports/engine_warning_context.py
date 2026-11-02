"""Shared report engine-warning helpers."""

from __future__ import annotations

from typing import TypeAlias, cast

ReportMap: TypeAlias = dict[str, object]


def append_engine_warning(
    step_data: ReportMap,
    *,
    key: str,
    severity: str,
    message: str,
    message_nl: str | None = None,
) -> None:
    record: dict[str, object] = {"key": key, "severity": severity, "message": message}
    if message_nl:
        record["message_nl"] = message_nl
    engine_warnings = cast(list[object], step_data.setdefault("_engine_warnings", []))
    engine_warnings.append(record)
