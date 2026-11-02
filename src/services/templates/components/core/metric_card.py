"""
Metric Card Component

Reusable metric card component for displaying financial metrics with trends.
"""

from typing import Dict, Any
from ..base import ComponentBase, ComponentConfig
from ..registry import register_component


@register_component("metric_card", {
    "description": "Financial metric card with trend indicators",
    "version": "1.0.0",
    "author": "Upswitch Team"
})
class MetricCardComponent(ComponentBase):
    """Reusable metric card component for financial metrics"""

    async def render(self, data: Dict[str, Any]) -> str:
        """Render metric card component"""
        # Extract data with defaults
        title = self.get_safe_value(data, "title", "Metric")
        value = self.get_safe_value(data, "value", "N/A")
        change = self.get_safe_value(data, "change", 0)
        unit = self.get_safe_value(data, "unit", "")
        description = self.get_safe_value(data, "description", "")
        size = self.get_safe_value(data, "size", "normal")  # small, normal, large
        color = self.get_safe_value(data, "color", "primary")  # primary, success, warning, danger

        # Handle different value types
        if isinstance(value, (int, float)):
            if unit == "currency":
                formatted_value = self.format_currency(value)
            elif unit == "percentage":
                formatted_value = self.format_percentage(value)
            else:
                formatted_value = self.format_number(value)
        else:
            formatted_value = str(value)

        # Get trend information
        trend_class = self.get_trend_class(change)
        trend_icon = self.get_trend_icon(change)
        trend_color = self.get_trend_color(change)

        # Size classes
        size_classes = {
            "small": "text-lg",
            "normal": "text-2xl", 
            "large": "text-3xl"
        }
        value_size_class = size_classes.get(size, "text-2xl")

        # Color classes
        color_classes = {
            "primary": "border-primary-600",
            "success": "border-green-600", 
            "warning": "border-yellow-600",
            "danger": "border-red-600"
        }
        border_class = color_classes.get(color, "border-primary-600")

        # Build description HTML if provided
        description_html = ""
        if description:
            description_html = f"""
            <p class="text-xs text-gray-500 mt-1">{self.escape_html(description)}</p>
            """

        return f"""
        <div class="metric-card bg-white rounded-lg shadow-sm p-6 border-l-4 {border_class} hover:shadow-md transition-shadow">
            <div class="flex items-center justify-between mb-2">
                <h3 class="text-sm font-medium text-gray-600 uppercase tracking-wide">
                    {self.escape_html(title)}
                </h3>
                {f'<span class="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">{self.escape_html(unit)}</span>' if unit else ''}
            </div>

            <div class="flex items-baseline justify-between">
                <div class="{value_size_class} font-bold text-gray-900">
                    {formatted_value}
                </div>
                {f'''
                <div class="flex items-center {trend_class} text-sm font-medium">
                    <span class="mr-1">{trend_icon}</span>
                    <span>{abs(change):.1f}%</span>
                </div>
                ''' if change != 0 else ''}
            </div>
            {description_html}
        </div>
        """
