"""Template-context merge helpers for report aggregation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class ReportMergeLogger(Protocol):
    def warning(self, message: str, *args: object, **kwargs: object) -> None:
        """Log an unexpected context overwrite."""


def safe_merge(
    context: dict[str, object],
    overlay: Mapping[str, object],
    source: str,
    *,
    logger: ReportMergeLogger,
    allowed_overwrites: frozenset[str] = frozenset(),
) -> None:
    """Merge overlay into context while warning on unexpected overwrites."""
    for key, value in overlay.items():
        if key in context and key not in allowed_overwrites:
            old = context[key]
            if old != value:
                logger.warning(
                    "[AGGREGATOR] Context key overwritten by %s",
                    source,
                    extra={
                        "key": key,
                        "old_type": type(old).__name__,
                        "new_type": type(value).__name__,
                    },
                )
        context[key] = value
