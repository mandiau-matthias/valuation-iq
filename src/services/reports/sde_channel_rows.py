"""Row builders for SDE report-channel rendering contracts."""

from __future__ import annotations

from decimal import Decimal

ReportRow = dict[str, object]
ReportRows = list[ReportRow]
ReportContext = dict[str, object]


def row(**values: object) -> ReportRow:
    return values


def calibration_step(
    label: str,
    description: object,
    multiple: Decimal,
    impact: Decimal,
    kind: str,
) -> ReportRow:
    return row(
        label=label,
        description=description,
        multiple=float(multiple),
        impact=float(impact),
        kind=kind,
    )


def bridge_row(label: str, amount: float, running_total: float, kind: str) -> ReportRow:
    return row(label=label, amount=amount, running_total=running_total, kind=kind)


def calibration_to_waterfall_steps(cascade: ReportRows) -> ReportRows:
    """Convert SDE cascade rows into the waterfall-renderer schema."""
    if not cascade:
        return []

    out: ReportRows = []
    previous = 0.0
    for idx, row_data in enumerate(cascade):
        multiple = float(row_data.get("multiple") or 0)
        kind = row_data.get("kind") or "increase"
        impact = float(row_data.get("impact") or (multiple - previous))

        if idx == 0 or kind == "base":
            out.append(_base_waterfall_step(row_data, multiple))
        elif kind == "total":
            out.append(_total_waterfall_step(row_data, multiple))
        else:
            out.append(_adjustment_waterfall_step(row_data, previous, multiple, impact))
        previous = multiple
    return out


def _base_waterfall_step(row_data: ReportRow, multiple: float) -> ReportRow:
    return row(
        label=row_data.get("label") or "Base SDE multiple",
        short_label=_waterfall_short_label(row_data),
        kind="base",
        tone="neutral",
        start_value=0.0,
        end_value=multiple,
        delta_value=multiple,
        annotation=row_data.get("description"),
    )


def _total_waterfall_step(row_data: ReportRow, multiple: float) -> ReportRow:
    return row(
        label=row_data.get("label") or "Applied SDE multiple",
        short_label=_waterfall_short_label(row_data),
        kind="total",
        tone="brand",
        start_value=0.0,
        end_value=multiple,
        delta_value=multiple,
        annotation=row_data.get("description"),
    )


def _adjustment_waterfall_step(
    row_data: ReportRow,
    previous: float,
    multiple: float,
    impact: float,
) -> ReportRow:
    return row(
        label=row_data.get("label") or "Adjustment",
        short_label=_waterfall_short_label(row_data),
        kind="increase" if impact >= 0 else "decrease",
        tone="positive" if impact >= 0 else "negative",
        start_value=previous,
        end_value=multiple,
        delta_value=impact,
        annotation=row_data.get("description"),
    )


def _waterfall_short_label(row_data: ReportRow) -> object:
    return row_data.get("short_label") or _short_label(row_data.get("label"))


def _short_label(label: object) -> str:
    if not isinstance(label, str):
        return ""
    return label.split("(")[0].strip().split(":")[0].strip()
