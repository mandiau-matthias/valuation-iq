"""
Financial Chart Service
----------------------
Domain service for generating financial visualizations using Plotly.
Designed to support both interactive HTML reports and static PDF generation.

ARCHITECTURE:
- Uses Plotly Graph Objects for precise control
- Exports to HTML div for web views (interactive)
- Exports to static image bytes for PDF generation
- Follows UpSwitch "Caregiver" design archetype (clean, trustworthy, clear)

AUTHOR: Senior CTO & World-Class Product Designer
DATE: December 2025
"""

import math
from typing import Any, Dict, Optional, List, Union
import plotly.graph_objects as go
import plotly.io as pio
from src.utils.logging import get_logger

logger = get_logger(__name__)


# UPSWITCH BRAND COLORS
# Defined to match the frontend design system and "Caregiver" archetype
class UpSwitchColors:
    NAVY = "#0F172A"  # Primary text, strong headers
    BLUE = "#3B82F6"  # Trust, primary action, mid-point
    GREEN = "#10B981"  # Growth, success, positive adjustments
    RED = "#EF4444"  # Warning, negative adjustments, expenses
    ORANGE = "#F59E0B"  # Caution, secondary metrics
    GRAY_LIGHT = "#F1F5F9"  # Backgrounds
    GRAY_MED = "#94A3B8"  # Secondary text, axis lines
    WHITE = "#FFFFFF"

    # Chart specific
    REVENUE_BAR = "#3B82F6"  # Blue for revenue (trust)
    EBITDA_LINE = "#10B981"  # Green for profit (growth)
    RANGE_FILL = "#E0F2FE"  # Light blue for range background


class FinancialChartService:
    """
    Service for generating financial charts for reports.

    DESIGN PRINCIPLES:
    1. Clarity: Remove chartjunk, focus on data.
    2. Trust: Use consistent, professional colors.
    3. Accessibility: High contrast, clear labels.
    4. Robustness: Fail gracefully if data is missing.
    """

    def __init__(self):
        self.logger = logger
        # Set default template to "plotly_white" for clean, professional look
        pio.templates.default = "plotly_white"

    @staticmethod
    def _to_finite_float(value: Any, default: float = 0.0) -> float:
        """Coerce report payload numbers without leaking NaN/inf into Plotly."""
        try:
            out = float(value)
        except (TypeError, ValueError):
            return default
        return out if math.isfinite(out) else default

    @staticmethod
    def _first_present(step: dict[str, Any], keys: list[str]) -> Any:
        for key in keys:
            if key in step and step.get(key) is not None:
                return step.get(key)
        return None

    @staticmethod
    def _year_sort_key(row: dict[str, Any]) -> tuple[int, str]:
        raw_year = row.get("year", "")
        try:
            year = int(float(str(raw_year).strip()))
        except (TypeError, ValueError):
            return (10**9, str(raw_year))
        return (year, str(raw_year))

    def _apply_upswitch_theme(self, fig: go.Figure, height: int = 400) -> go.Figure:
        """Apply UpSwitch standard styling to a figure."""
        fig.update_layout(
            font=dict(family="Inter, sans-serif", size=12, color=UpSwitchColors.NAVY),
            paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
            plot_bgcolor="rgba(0,0,0,0)",  # Transparent plot area
            margin=dict(l=40, r=40, t=40, b=40),
            height=height,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(
                showgrid=False,
                showline=True,
                linecolor=UpSwitchColors.GRAY_MED,
                tickfont=dict(color=UpSwitchColors.NAVY),
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor=UpSwitchColors.GRAY_LIGHT,
                showline=False,
                zeroline=False,
                tickformat=",.0f",  # Simple number format
            ),
        )
        return fig

    def create_historical_performance_chart(
        self, historical_data: List[Dict[str, Any]], as_image: bool = False
    ) -> Optional[Union[str, bytes]]:
        """
        Create a dual-axis chart: Revenue (Bar) and EBITDA (Line).

        Args:
            historical_data: List of dicts with 'year', 'revenue', 'ebitda'
            as_image: If True, returns image bytes (for PDF). If False, returns HTML div.

        Returns:
            HTML string or image bytes, or None if generation fails.
        """
        try:
            if not historical_data:
                self.logger.warning("Insufficient data for historical chart")
                return None

            # Sort by numeric year where possible: lexical sorting puts "20210"
            # before "2022", which makes the historical trend lie.
            data = sorted(historical_data, key=self._year_sort_key)
            years = [str(d.get("year", "—")) for d in data]
            revenue = [self._to_finite_float(d.get("revenue")) for d in data]
            ebitda = [self._to_finite_float(d.get("ebitda")) for d in data]

            fig = go.Figure()

            # Revenue Bars
            fig.add_trace(
                go.Bar(
                    x=years,
                    y=revenue,
                    name="Revenue",
                    marker_color=UpSwitchColors.REVENUE_BAR,
                    opacity=0.8,
                    hovertemplate="Revenue: %{y:,.0f}<extra></extra>",
                )
            )

            # EBITDA Line
            fig.add_trace(
                go.Scatter(
                    x=years,
                    y=ebitda,
                    name="EBITDA",
                    yaxis="y2",
                    line=dict(color=UpSwitchColors.EBITDA_LINE, width=3),
                    mode="lines+markers",
                    marker=dict(
                        size=8,
                        color=UpSwitchColors.WHITE,
                        line=dict(width=2, color=UpSwitchColors.EBITDA_LINE),
                    ),
                    hovertemplate="EBITDA: %{y:,.0f}<extra></extra>",
                )
            )

            # Layout with dual axis
            fig = self._apply_upswitch_theme(fig)
            fig.update_layout(
                title=dict(
                    text="Historical Financial Performance", font=dict(size=16, weight="bold")
                ),
                yaxis=dict(title="Revenue", side="left", showgrid=True),
                yaxis2=dict(
                    title="EBITDA", side="right", overlaying="y", showgrid=False, zeroline=False
                ),
                legend=dict(x=0, y=1.1, xanchor="left"),  # Adjust legend for title
            )

            fig.update_yaxes(tickprefix="€")

            if as_image:
                return pio.to_image(fig, format="png", width=800, height=400, scale=2)
            else:
                return pio.to_html(
                    fig, full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False}
                )

        except Exception as e:
            self.logger.error(f"Error generating historical chart: {e}", exc_info=True)
            return None

    def create_valuation_waterfall_chart(
        self, steps: List[Dict[str, Any]], as_image: bool = False
    ) -> Optional[Union[str, bytes]]:
        """
        Create a waterfall chart showing the valuation bridge.

        Args:
            steps: List of waterfall steps (name, value, type='absolute'|'relative')
            as_image: Return bytes for PDF or HTML string.
        """
        try:
            if not steps:
                return None

            measures = []
            y_values = []
            text_values = []

            for i, step in enumerate(steps):
                label = self._first_present(step, ["step_name", "label", "short_label", "name"])
                end_value = self._first_present(
                    step, ["end_value", "ev_after", "after_value", "value", "amount"]
                )
                start_value = self._first_present(
                    step, ["start_value", "ev_before", "before_value"]
                )
                delta_value = self._first_present(
                    step, ["delta_value", "adjustment_amount", "impact", "change"]
                )

                if end_value is None and delta_value is not None:
                    previous_end = (
                        self._first_present(steps[i - 1], ["end_value", "ev_after", "after_value"])
                        if i > 0
                        else 0
                    )
                    end = self._to_finite_float(previous_end) + self._to_finite_float(delta_value)
                else:
                    end = self._to_finite_float(end_value)

                if delta_value is None and i > 0:
                    if start_value is None:
                        previous_end = self._first_present(
                            steps[i - 1], ["end_value", "ev_after", "after_value", "value"]
                        )
                        start = self._to_finite_float(previous_end)
                    else:
                        start = self._to_finite_float(start_value)
                    delta = end - start
                else:
                    delta = self._to_finite_float(delta_value, end)

                kind = str(step.get("kind") or "").lower()
                is_start = i == 0 or kind == "base"
                is_total = i == len(steps) - 1 or kind in {"total", "subtotal"}

                if is_start:
                    measures.append("absolute")
                    y_values.append(end)
                    text_values.append(f"{end:,.0f}")
                elif is_total:
                    measures.append("total")
                    y_values.append(0)
                    text_values.append(f"{end:,.0f}")
                else:
                    measures.append("relative")
                    y_values.append(delta)
                    text_values.append(f"{delta:+,.0f}")

            names = [
                str(
                    self._first_present(step, ["step_name", "label", "short_label", "name"])
                    or f"Step {i + 1}"
                )
                for i, step in enumerate(steps)
            ]

            fig = go.Figure(
                go.Waterfall(
                    name="Valuation Bridge",
                    orientation="v",
                    measure=measures,
                    x=names,
                    textposition="outside",
                    text=text_values,
                    y=y_values,
                    connector={"line": {"color": UpSwitchColors.GRAY_MED}},
                    decreasing={"marker": {"color": UpSwitchColors.RED}},
                    increasing={"marker": {"color": UpSwitchColors.GREEN}},
                    totals={"marker": {"color": UpSwitchColors.NAVY}},
                )
            )

            fig = self._apply_upswitch_theme(fig)
            fig.update_layout(
                title=dict(text="Valuation Value Bridge", font=dict(size=16, weight="bold")),
                xaxis=dict(title=""),
                yaxis=dict(title="Enterprise/Equity Value"),
                showlegend=False,
            )

            if as_image:
                return pio.to_image(fig, format="png", width=800, height=450, scale=2)
            else:
                return pio.to_html(
                    fig, full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False}
                )

        except Exception as e:
            self.logger.error(f"Error generating waterfall chart: {e}", exc_info=True)
            return None

    def create_valuation_range_chart(
        self, low: float, mid: float, high: float, as_image: bool = False
    ) -> Optional[Union[str, bytes]]:
        """
        Create a horizontal range bar chart (Football field style).
        """
        try:
            low = self._to_finite_float(low)
            mid = self._to_finite_float(mid)
            high = self._to_finite_float(high)
            low, high = sorted((low, high))
            mid = min(max(mid, low), high) if high > low else low

            fig = go.Figure()

            # Base invisible bar to push the range to the right start
            fig.add_trace(
                go.Bar(
                    y=["Fair Market Value"],
                    x=[low],
                    orientation="h",
                    marker=dict(color="rgba(0,0,0,0)"),  # Invisible
                    hoverinfo="none",
                    showlegend=False,
                )
            )

            # The Range Bar (Low to High)
            fig.add_trace(
                go.Bar(
                    y=["Fair Market Value"],
                    x=[high - low],  # Width of the range
                    orientation="h",
                    marker=dict(
                        color=UpSwitchColors.BLUE,
                        opacity=0.2,
                        line=dict(color=UpSwitchColors.BLUE, width=2),
                    ),
                    name="Valuation Range",
                    hoverinfo="x",
                )
            )

            # Midpoint Marker
            fig.add_trace(
                go.Scatter(
                    x=[mid],
                    y=["Fair Market Value"],
                    mode="markers+text",
                    marker=dict(color=UpSwitchColors.NAVY, size=12, symbol="diamond"),
                    text=[f"Mid: {mid:,.0f}"],
                    textposition="top center",
                    name="Mid-Point",
                )
            )

            # Labels for Low and High
            fig.add_trace(
                go.Scatter(
                    x=[low, high],
                    y=["Fair Market Value", "Fair Market Value"],
                    mode="text",
                    text=[f"Low: {low:,.0f}", f"High: {high:,.0f}"],
                    textposition=["bottom left", "bottom right"],
                    showlegend=False,
                )
            )

            fig = self._apply_upswitch_theme(fig, height=200)
            fig.update_layout(
                barmode="stack",
                title=dict(text="Estimated Valuation Range", font=dict(size=16, weight="bold")),
                yaxis=dict(
                    showticklabels=False
                ),  # Hide the Y label "Fair Market Value" as it's redundant
                xaxis=dict(title="Equity Value"),
            )

            if as_image:
                return pio.to_image(fig, format="png", width=800, height=200, scale=2)
            else:
                return pio.to_html(
                    fig, full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False}
                )

        except Exception as e:
            self.logger.error(f"Error generating range chart: {e}", exc_info=True)
            return None
