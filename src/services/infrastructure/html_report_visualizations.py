"""Optional chart enrichment for HTML report template data."""

from __future__ import annotations

import asyncio
import base64

TemplateData = dict[str, object]


async def add_visualizations_to_template_data(
    *,
    template_data: TemplateData,
    chart_service: object,
) -> None:
    """Add optional image charts when source data is present."""
    historical_data = _extract_historical_data(template_data)
    if historical_data:
        chart_img = await asyncio.to_thread(
            chart_service.create_historical_performance_chart,
            historical_data,
            as_image=True,
        )
        if chart_img and isinstance(chart_img, bytes):
            template_data["historical_performance_chart"] = _img_tag(
                chart_img,
                alt="Historical Financial Performance",
            )

    waterfall_steps = _extract_waterfall_steps(template_data)
    if waterfall_steps:
        chart_img = await asyncio.to_thread(
            chart_service.create_valuation_waterfall_chart,
            waterfall_steps,
            as_image=True,
        )
        if chart_img and isinstance(chart_img, bytes):
            template_data["valuation_bridge_chart"] = _img_tag(
                chart_img,
                alt="Valuation Bridge",
            )

    valuation_range = template_data.get("valuation_range")
    if isinstance(valuation_range, dict):
        low = valuation_range.get("low")
        mid = valuation_range.get("mid")
        high = valuation_range.get("high")
        if low is not None and mid is not None and high is not None:
            chart_img = await asyncio.to_thread(
                chart_service.create_valuation_range_chart,
                float(low),
                float(mid),
                float(high),
                as_image=True,
            )
            if chart_img and isinstance(chart_img, bytes):
                template_data["valuation_range_chart"] = _img_tag(
                    chart_img,
                    alt="Valuation Range",
                )


def _extract_historical_data(template_data: TemplateData) -> object | None:
    financial_analysis = template_data.get("financial_analysis")
    if isinstance(financial_analysis, dict) and financial_analysis.get("historical_performance"):
        return financial_analysis["historical_performance"]

    calculation_steps = template_data.get("calculation_steps")
    if isinstance(calculation_steps, list):
        for step in calculation_steps:
            if not isinstance(step, dict):
                continue
            inputs = step.get("inputs")
            if (
                step.get("step_number") == 0
                and isinstance(inputs, dict)
                and inputs.get("historical_years_data")
            ):
                return inputs["historical_years_data"]
    return None


def _extract_waterfall_steps(template_data: TemplateData) -> object | None:
    valuation_conclusion = template_data.get("valuation_conclusion")
    if not isinstance(valuation_conclusion, dict):
        return None
    waterfall_summary = valuation_conclusion.get("waterfall_summary")
    if not isinstance(waterfall_summary, dict):
        return None
    return waterfall_summary.get("steps")


def _img_tag(image_bytes: bytes, *, alt: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return (
        f'<img src="data:image/png;base64,{encoded}" '
        f'style="width:100%;max-width:800px;height:auto;" '
        f'alt="{alt}" />'
    )
