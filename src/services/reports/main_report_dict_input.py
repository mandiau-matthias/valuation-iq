"""Dict-input adapter for main report aggregation."""

from __future__ import annotations

from collections.abc import Callable

from src.services.reports.main_report_contracts import MainReportContext
from src.services.reports.protocol_adapter import DictWrapper

JsonMap = dict[str, object]


def aggregate_main_report_from_valuation_data(
    *,
    valuation_data: JsonMap,
    locale: str,
    aggregate: Callable[..., MainReportContext],
    logger: object,
) -> MainReportContext:
    """Wrap Titan's dict payload for Protocol-compatible report aggregation."""
    if not valuation_data or not isinstance(valuation_data, dict):
        raise ValueError(
            f"aggregate_from_valuation_data: expected dict, got {type(valuation_data).__name__}"
        )

    skipped_keys = {"html_report", "pdf_html_report"}
    flattened = {key: value for key, value in valuation_data.items() if key not in skipped_keys}

    details = flattened.pop("details", None)
    if isinstance(details, dict):
        for key, value in details.items():
            if key not in flattened and key not in skipped_keys:
                flattened[key] = value

    wrapped = DictWrapper(flattened)
    context = aggregate(
        response=wrapped,
        request=wrapped,
        locale=locale,
    )
    logger.debug(
        "aggregate_from_valuation_data: context built successfully",
        extra={
            "company_name": context.get("company_name"),
            "valuation": context.get("valuation"),
            "context_keys_count": len(context),
        },
    )
    return context
