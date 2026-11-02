"""
Summary Component

Reusable summary component for executive summaries and key insights.
"""

from typing import Dict, Any, List
from ..base import ComponentBase, ComponentConfig
from ..registry import register_component


@register_component("summary", {
    "description": "Executive summary with key insights and highlights",
    "version": "1.0.0",
    "author": "Upswitch Team"
})
class SummaryComponent(ComponentBase):
    """Reusable summary component for key insights"""

    async def render(self, data: Dict[str, Any]) -> str:
        """Render summary component"""
        # Extract data with defaults
        title = self.get_safe_value(data, "title", "Executive Summary")
        subtitle = self.get_safe_value(data, "subtitle", "")
        highlights = self.get_safe_value(data, "highlights", [])
        key_metrics = self.get_safe_value(data, "key_metrics", [])
        insights = self.get_safe_value(data, "insights", [])
        recommendations = self.get_safe_value(data, "recommendations", [])
        style = self.get_safe_value(data, "style", "default")  # default, compact, detailed

        # Build title HTML
        title_html = f"""
        <div class="mb-6">
            <h2 class="text-2xl font-bold text-gray-900 mb-2">{self.escape_html(title)}</h2>
            {f'<p class="text-gray-600">{self.escape_html(subtitle)}</p>' if subtitle else ''}
        </div>
        """

        # Build highlights section
        highlights_html = ""
        if highlights:
            highlight_items = []
            for highlight in highlights:
                if isinstance(highlight, dict):
                    text = highlight.get("text", "")
                    icon = highlight.get("icon", "✓")
                    color = highlight.get("color", "green")
                else:
                    text = str(highlight)
                    icon = "✓"
                    color = "green"

                color_classes = {
                    "green": "text-green-600 bg-green-50",
                    "blue": "text-blue-600 bg-blue-50", 
                    "yellow": "text-yellow-600 bg-yellow-50",
                    "red": "text-red-600 bg-red-50"
                }
                color_class = color_classes.get(color, "text-green-600 bg-green-50")

                highlight_items.append(f"""
                <li class="flex items-start">
                    <span class="flex-shrink-0 w-5 h-5 {color_class} rounded-full flex items-center justify-center text-xs font-bold mr-3 mt-0.5">
                        {icon}
                    </span>
                    <span class="text-gray-700">{self.escape_html(text)}</span>
                </li>
                """)

            highlights_html = f"""
            <div class="mb-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-3">Key Highlights</h3>
                <ul class="space-y-2">
                    {''.join(highlight_items)}
                </ul>
            </div>
            """

        # Build key metrics section
        metrics_html = ""
        if key_metrics:
            metric_items = []
            for metric in key_metrics:
                if isinstance(metric, dict):
                    label = metric.get("label", "")
                    value = metric.get("value", "")
                    change = metric.get("change", 0)
                else:
                    label = str(metric)
                    value = ""
                    change = 0

                trend_html = ""
                if change != 0:
                    trend_class = self.get_trend_class(change)
                    trend_icon = self.get_trend_icon(change)
                    trend_html = f"""
                    <span class="ml-2 {trend_class} text-sm">
                        {trend_icon} {abs(change):.1f}%
                    </span>
                    """

                metric_items.append(f"""
                <div class="bg-gray-50 rounded-lg p-4">
                    <div class="text-sm font-medium text-gray-600">{self.escape_html(label)}</div>
                    <div class="text-xl font-bold text-gray-900 mt-1">
                        {self.escape_html(str(value))}{trend_html}
                    </div>
                </div>
                """)

            metrics_html = f"""
            <div class="mb-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-3">Key Metrics</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {''.join(metric_items)}
                </div>
            </div>
            """

        # Build insights section
        insights_html = ""
        if insights:
            insight_items = []
            for insight in insights:
                if isinstance(insight, dict):
                    text = insight.get("text", "")
                    category = insight.get("category", "general")
                else:
                    text = str(insight)
                    category = "general"

                category_colors = {
                    "positive": "border-green-200 bg-green-50",
                    "negative": "border-red-200 bg-red-50",
                    "neutral": "border-gray-200 bg-gray-50",
                    "general": "border-blue-200 bg-blue-50"
                }
                category_class = category_colors.get(category, "border-blue-200 bg-blue-50")

                insight_items.append(f"""
                <div class="border-l-4 {category_class} p-4">
                    <p class="text-gray-700">{self.escape_html(text)}</p>
                </div>
                """)

            insights_html = f"""
            <div class="mb-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-3">Key Insights</h3>
                <div class="space-y-3">
                    {''.join(insight_items)}
                </div>
            </div>
            """

        # Build recommendations section
        recommendations_html = ""
        if recommendations:
            rec_items = []
            for i, rec in enumerate(recommendations, 1):
                if isinstance(rec, dict):
                    text = rec.get("text", "")
                    priority = rec.get("priority", "medium")
                else:
                    text = str(rec)
                    priority = "medium"

                priority_colors = {
                    "high": "text-red-600",
                    "medium": "text-yellow-600", 
                    "low": "text-green-600"
                }
                priority_class = priority_colors.get(priority, "text-yellow-600")

                rec_items.append(f"""
                <li class="flex items-start">
                    <span class="flex-shrink-0 w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center text-xs font-bold text-gray-600 mr-3 mt-0.5">
                        {i}
                    </span>
                    <span class="text-gray-700">{self.escape_html(text)}</span>
                    <span class="ml-2 {priority_class} text-xs font-medium">({priority})</span>
                </li>
                """)

            recommendations_html = f"""
            <div class="mb-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-3">Recommendations</h3>
                <ol class="space-y-2">
                    {''.join(rec_items)}
                </ol>
            </div>
            """

        # Combine all sections
        content_html = f"""
        {highlights_html}
        {metrics_html}
        {insights_html}
        {recommendations_html}
        """

        return f"""
        <div class="summary-component bg-white rounded-lg shadow-sm p-6">
            {title_html}
            {content_html}
        </div>
        """
