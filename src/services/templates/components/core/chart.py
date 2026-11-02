"""
Chart Component

Reusable chart component for displaying data visualizations.
"""

from typing import Dict, Any, List
import json
from ..base import ComponentBase, ComponentConfig
from ..registry import register_component


@register_component("chart", {
    "description": "Data visualization chart component",
    "version": "1.0.0",
    "author": "Upswitch Team"
})
class ChartComponent(ComponentBase):
    """Reusable chart component for data visualizations"""

    async def render(self, data: Dict[str, Any]) -> str:
        """Render chart component"""
        # Extract data with defaults
        chart_type = self.get_safe_value(data, "type", "line")
        title = self.get_safe_value(data, "title", "")
        subtitle = self.get_safe_value(data, "subtitle", "")
        chart_data = self.get_safe_value(data, "data", [])
        width = self.get_safe_value(data, "width", "100%")
        height = self.get_safe_value(data, "height", "400px")
        responsive = self.get_safe_value(data, "responsive", True)
        show_legend = self.get_safe_value(data, "show_legend", True)
        show_grid = self.get_safe_value(data, "show_grid", True)

        # Generate unique chart ID
        import uuid
        chart_id = f"chart_{uuid.uuid4().hex[:8]}"

        # Build title HTML if provided
        title_html = ""
        if title:
            title_html = f"""
            <div class="mb-4">
                <h3 class="text-lg font-medium text-gray-900">{self.escape_html(title)}</h3>
                {f'<p class="text-sm text-gray-600 mt-1">{self.escape_html(subtitle)}</p>' if subtitle else ''}
            </div>
            """

        # Convert data to JSON for JavaScript
        chart_data_json = json.dumps(chart_data, default=str)

        # Build chart container
        container_classes = ["chart-container", "bg-white", "rounded-lg", "p-6", "shadow-sm"]
        if responsive:
            container_classes.append("overflow-hidden")

        return f"""
        <div class="chart-component">
            {title_html}
            <div class="{' '.join(container_classes)}">
                <canvas id="{chart_id}" width="{width}" height="{height}"></canvas>
            </div>

            <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    const ctx = document.getElementById('{chart_id}').getContext('2d');
                    const chartData = {chart_data_json};

                    new Chart(ctx, {{
                        type: '{chart_type}',
                        data: chartData,
                        options: {{
                            responsive: {str(responsive).lower()},
                            maintainAspectRatio: false,
                            plugins: {{
                                legend: {{
                                    display: {str(show_legend).lower()}
                                }}
                            }},
                            scales: {{
                                x: {{
                                    grid: {{
                                        display: {str(show_grid).lower()}
                                    }}
                                }},
                                y: {{
                                    grid: {{
                                        display: {str(show_grid).lower()}
                                    }}
                                }}
                            }}
                        }}
                    }});
                }});
            </script>
        </div>
        """
