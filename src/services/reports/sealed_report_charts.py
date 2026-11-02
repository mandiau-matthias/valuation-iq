"""Calculation-free SVG geometry for sealed memorandum charts.

All economic values arrive as sealed fields.  This module converts those
already-calculated values into coordinates; Jinja receives only display text
and finished SVG attributes and therefore cannot perform valuation arithmetic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def method_chart_rows(method_page: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Select monetary sealed rows for a compact method-specific visual."""

    method_id = str(method_page.get("method_id") or "")
    allowed_fragments = {
        "market": ("metric_basis", "enterprise_value"),
        "dcf": ("pv_explicit", "pv_terminal", "enterprise_value"),
        "sde": (
            "earnings",
            "owner_remuneration",
            "replacement_cost",
            "enterprise_value",
        ),
        "revenue_startup": (".arr", ".mrr", ".metric", ".burn", "enterprise_value"),
        "adjusted_nav": ("book_equity", "revaluation_uplift", "corrected_value"),
        "holding_sotp": (
            ".entity.",
            "intercompany_eliminations",
            "non_operating_assets",
            "equity_value",
        ),
        "liquidation": ("orderly_value", "forced_value", "headline_equity"),
    }.get(method_id, ())
    rows = method_page.get("rows")
    source = (
        list(rows)
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes, bytearray))
        else []
    )
    return [
        row
        for row in source
        if isinstance(row, Mapping)
        and any(fragment in str(row.get("field_id") or "") for fragment in allowed_fragments)
    ][:6]


def bridge_chart_rows(rows: Sequence[Mapping[str, object]], locale: str) -> list[dict[str, object]]:
    labels = {
        "bridge.enterprise_value": {"nl": "OV", "fr": "VE", "en": "EV"},
        "bridge.debt": {"nl": "Schuld", "fr": "Dette", "en": "Debt"},
        "bridge.cash": {"nl": "Cash", "fr": "Trésorerie", "en": "Cash"},
        "bridge.nwc": {"nl": "WKK", "fr": "BFR", "en": "NWC"},
        "bridge.tax": {"nl": "Bel.", "fr": "Impôt", "en": "Tax"},
        "bridge.equity_value": {
            "nl": "Eigen verm.",
            "fr": "Cap. prop.",
            "en": "Equity",
        },
    }
    return [
        {
            **dict(row),
            "label": labels.get(str(row.get("field_id") or ""), {}).get(
                locale, str(row.get("label") or "")
            ),
        }
        for row in rows
    ]


def _indexed_values(values: list[Decimal | None]) -> list[Decimal | None]:
    """Return presentation-only index values using the first non-zero point.

    Revenue, EBITDA and margin have different units and orders of magnitude.
    Drawing them on one monetary axis made the EBITDA and margin series appear
    flat. Indexing is chart geometry only; the sealed table remains the
    authoritative source for every displayed economic value.
    """

    baseline = next((value for value in values if value not in (None, 0)), None)
    if baseline is None:
        return [None for _ in values]
    return [None if value is None else value / baseline * Decimal("100") for value in values]


def _indexed_points(values: list[Decimal | None], minimum: Decimal, maximum: Decimal) -> str:
    if not values or maximum <= minimum:
        return ""
    count = len(values)
    step = Decimal("420") / Decimal(max(count - 1, 1))
    output: list[str] = []
    for index, value in enumerate(values):
        if value is None:
            continue
        x = Decimal("50") + step * Decimal(index)
        y = Decimal("136") - (value - minimum) / (maximum - minimum) * Decimal("84")
        output.append(f"{x.quantize(Decimal('0.1'))},{y.quantize(Decimal('0.1'))}")
    return " ".join(output)


def financial_history_chart(
    rows: Sequence[Mapping[str, object]],
    *,
    series_labels: Mapping[str, str] | None = None,
) -> dict[str, object] | None:
    revenue: list[Decimal | None] = []
    ebitda: list[Decimal | None] = []
    margin: list[Decimal | None] = []
    year_labels: list[dict[str, str]] = []
    count = len(rows)
    if count < 2:
        return None
    step = Decimal("420") / Decimal(max(count - 1, 1))
    for index, row in enumerate(rows):
        cells = row.get("cells")
        cell_rows = list(cells) if isinstance(cells, Sequence) else []
        by_id = {
            str(cell.get("field_id") or "").rsplit(".", 1)[-1]: cell
            for cell in cell_rows
            if isinstance(cell, Mapping)
        }
        revenue.append(_decimal(by_id.get("revenue", {}).get("raw")))
        ebitda.append(_decimal(by_id.get("reported_ebitda", {}).get("raw")))
        margin.append(_decimal(by_id.get("ebitda_margin", {}).get("raw")))
        x = Decimal("50") + step * Decimal(index)
        year_labels.append({"x": str(x.quantize(Decimal("0.1"))), "label": str(row.get("year"))})
    indexed_revenue = _indexed_values(revenue)
    indexed_ebitda = _indexed_values(ebitda)
    indexed_margin = _indexed_values(margin)
    available = [
        value for value in [*indexed_revenue, *indexed_ebitda, *indexed_margin] if value is not None
    ]
    if not available:
        return None
    minimum = min(available)
    maximum = max(available)
    if minimum == maximum:
        minimum -= Decimal("5")
        maximum += Decimal("5")
    else:
        padding = max((maximum - minimum) * Decimal("0.12"), Decimal("2"))
        minimum -= padding
        maximum += padding
    resolved_labels = series_labels or {}
    return {
        "chart_id": "financial_history",
        "view_box": "0 0 520 176",
        "revenue_points": _indexed_points(indexed_revenue, minimum, maximum),
        "ebitda_points": _indexed_points(indexed_ebitda, minimum, maximum),
        "margin_points": _indexed_points(indexed_margin, minimum, maximum),
        "series_labels": {
            "revenue": str(
                resolved_labels.get("revenue") or resolved_labels.get("revenue_short") or "Revenue"
            ),
            "ebitda": str(
                resolved_labels.get("ebitda")
                or resolved_labels.get("reported_ebitda_short")
                or "EBITDA"
            ),
            "margin": str(
                resolved_labels.get("margin")
                or resolved_labels.get("ebitda_margin")
                or "EBITDA margin"
            ),
            "index": str(
                resolved_labels.get("index")
                or resolved_labels.get("financial_history_index")
                or "First year = 100"
            ),
        },
        "year_labels": year_labels,
    }


def three_value_bars(
    rows: Sequence[Mapping[str, object]], *, chart_id: str
) -> dict[str, object] | None:
    numeric_rows: list[tuple[Mapping[str, object], Decimal]] = []
    for row in rows:
        value = _decimal(row.get("raw"))
        if value is not None:
            numeric_rows.append((row, value))
    if len(numeric_rows) < 2:
        return None
    maximum = max(abs(value) for _, value in numeric_rows)
    if maximum <= 0:
        return None
    numeric_rows = numeric_rows[:6]
    chart_width = Decimal("520")
    plot_left = Decimal("28")
    plot_right = Decimal("492")
    slot = (plot_right - plot_left) / Decimal(len(numeric_rows))
    bar_width = min(Decimal("68"), slot * Decimal("0.58"))
    bars: list[dict[str, str]] = []
    for index, (row, value) in enumerate(numeric_rows):
        height = abs(value) / maximum * Decimal("78")
        x = plot_left + slot * Decimal(index) + (slot - bar_width) / Decimal("2")
        y = Decimal("112") - height
        bars.append(
            {
                "x": str(x.quantize(Decimal("0.1"))),
                "y": str(y.quantize(Decimal("0.1"))),
                "width": str(bar_width.quantize(Decimal("0.1"))),
                "height": str(max(height, Decimal("1")).quantize(Decimal("0.1"))),
                "label_x": str((x + bar_width / Decimal("2")).quantize(Decimal("0.1"))),
                "label": str(row.get("label") or ""),
                "display": str(row.get("display") or "—"),
                "field_id": str(row.get("field_id") or ""),
                "tone": "negative" if value < 0 else "positive",
            }
        )
    return {
        "chart_id": chart_id,
        "view_box": f"0 0 {chart_width} 155",
        "bars": bars,
    }


def bridge_direction_chart(
    rows: Sequence[Mapping[str, object]], *, chart_id: str = "ev_to_equity_bridge"
) -> dict[str, object] | None:
    """Build a directional bridge without recalculating the sealed conclusion.

    Operators are already part of the display projection.  This function only
    maps their direction to SVG coordinates; it never totals or reconciles the
    rows, so the canonical valuation run remains the sole arithmetic authority.
    """

    prepared: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        value = _decimal(row.get("raw"))
        if value is None:
            continue
        operator = str(row.get("operator") or "")
        direction = -1 if operator == "−" else 1
        if index in (0, len(rows) - 1):
            direction = 1
        prepared.append({**dict(row), "chart_value": abs(value), "direction": direction})
    if len(prepared) < 2:
        return None
    maximum = max(_decimal(row["chart_value"]) or Decimal("0") for row in prepared)
    if maximum <= 0:
        return None
    prepared = prepared[:6]
    plot_left = Decimal("28")
    slot = Decimal("464") / Decimal(len(prepared))
    bar_width = min(Decimal("58"), slot * Decimal("0.56"))
    baseline = Decimal("55")
    bars: list[dict[str, str]] = []
    for index, row in enumerate(prepared):
        value = _decimal(row["chart_value"]) or Decimal("0")
        height = max(value / maximum * Decimal("34"), Decimal("1"))
        direction = int(row["direction"])
        x = plot_left + slot * Decimal(index) + (slot - bar_width) / Decimal("2")
        y = baseline - height if direction > 0 else baseline
        bars.append(
            {
                "x": str(x.quantize(Decimal("0.1"))),
                "y": str(y.quantize(Decimal("0.1"))),
                "width": str(bar_width.quantize(Decimal("0.1"))),
                "height": str(height.quantize(Decimal("0.1"))),
                "label_x": str((x + bar_width / Decimal("2")).quantize(Decimal("0.1"))),
                "label": str(row.get("label") or ""),
                "display": str(row.get("display") or "—"),
                "field_id": str(row.get("field_id") or ""),
                "tone": "negative" if direction < 0 else "positive",
            }
        )
    return {
        "chart_id": chart_id,
        "view_box": "0 0 520 108",
        "baseline_y": "55",
        "bars": bars,
    }


def benchmark_distribution_chart(
    rows: Sequence[Mapping[str, object]], selected: Mapping[str, object] | None
) -> dict[str, object] | None:
    values: dict[str, Decimal] = {}
    displays: dict[str, str] = {}
    for row in rows:
        field_id = str(row.get("field_id") or "")
        if field_id.endswith(".p25"):
            key = "p25"
        elif field_id.endswith(".median"):
            key = "p50"
        elif field_id.endswith(".p75"):
            key = "p75"
        else:
            continue
        value = _decimal(row.get("raw"))
        if value is not None:
            values[key] = value
            displays[key] = str(row.get("display") or "—")
    if not all(key in values for key in ("p25", "p50", "p75")):
        return None
    low, mid, high = values["p25"], values["p50"], values["p75"]
    if low <= 0 or not low <= mid <= high or high == low:
        return None
    selected_value = _decimal(selected.get("raw")) if selected else None

    def x(value: Decimal) -> str:
        bounded = min(max(value, low), high)
        coordinate = Decimal("56") + (bounded - low) / (high - low) * Decimal("408")
        return str(coordinate.quantize(Decimal("0.1")))

    markers = [
        {"id": key, "x": x(values[key]), "display": displays[key]} for key in ("p25", "p50", "p75")
    ]
    return {
        "chart_id": "benchmark_distribution",
        "view_box": "0 0 520 105",
        "range_x": x(low),
        "range_width": str((Decimal(x(high)) - Decimal(x(low))).quantize(Decimal("0.1"))),
        "markers": markers,
        "selected": (
            {
                "x": x(selected_value),
                "display": str(selected.get("display") or "—"),
                "field_id": str(selected.get("field_id") or ""),
            }
            if selected_value is not None
            else None
        ),
    }
