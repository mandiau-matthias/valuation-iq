"""
Table Component

Reusable table component for displaying structured data with sorting and styling.
"""

from typing import Dict, Any, List
from ..base import ComponentBase, ComponentConfig
from ..registry import register_component


@register_component("table", {
    "description": "Data table with sorting and responsive design",
    "version": "1.0.0",
    "author": "Upswitch Team"
})
class TableComponent(ComponentBase):
    """Reusable table component for structured data"""

    async def render(self, data: Dict[str, Any]) -> str:
        """Render table component"""
        # Extract data with defaults
        headers = self.get_safe_value(data, "headers", [])
        rows = self.get_safe_value(data, "rows", [])
        title = self.get_safe_value(data, "title", "")
        caption = self.get_safe_value(data, "caption", "")
        striped = self.get_safe_value(data, "striped", True)
        hover = self.get_safe_value(data, "hover", True)
        sortable = self.get_safe_value(data, "sortable", False)
        responsive = self.get_safe_value(data, "responsive", True)

        # Build table classes
        table_classes = ["min-w-full", "divide-y", "divide-gray-200"]
        if striped:
            table_classes.append("bg-white")

        # Build row classes
        row_classes = []
        if hover:
            row_classes.append("hover:bg-gray-50")

        # Build header HTML
        header_html = ""
        if headers:
            header_cells = []
            for header in headers:
                if isinstance(header, dict):
                    header_text = header.get("text", "")
                    header_align = header.get("align", "left")
                    header_sortable = header.get("sortable", sortable)
                else:
                    header_text = str(header)
                    header_align = "left"
                    header_sortable = sortable

                sort_icon = ""
                if header_sortable:
                    sort_icon = """
                    <svg class="ml-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"></path>
                    </svg>
                    """

                header_cells.append(f"""
                <th class="px-6 py-3 text-{header_align} text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {self.escape_html(header_text)}{sort_icon}
                </th>
                """)

            header_html = f"""
            <thead class="bg-gray-50">
                <tr>
                    {''.join(header_cells)}
                </tr>
            </thead>
            """

        # Build rows HTML
        rows_html = ""
        if rows:
            row_cells = []
            for i, row in enumerate(rows):
                # Alternate row styling
                row_class = "bg-white" if not striped or i % 2 == 0 else "bg-gray-50"
                row_class += " " + " ".join(row_classes)

                cells = []
                for j, cell in enumerate(row):
                    # Get alignment from header if available
                    align = "left"
                    if j < len(headers) and isinstance(headers[j], dict):
                        align = headers[j].get("align", "left")

                    # Format cell value
                    if isinstance(cell, (int, float)):
                        if j < len(headers) and isinstance(headers[j], dict):
                            unit = headers[j].get("unit", "")
                            if unit == "currency":
                                cell_value = self.format_currency(cell)
                            elif unit == "percentage":
                                cell_value = self.format_percentage(cell)
                            else:
                                cell_value = self.format_number(cell)
                        else:
                            cell_value = self.format_number(cell)
                    else:
                        cell_value = self.escape_html(str(cell))

                    cells.append(f"""
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-{align} text-gray-900">
                        {cell_value}
                    </td>
                    """)

                row_cells.append(f"""
                <tr class="{row_class}">
                    {''.join(cells)}
                </tr>
                """)

            rows_html = f"""
            <tbody class="divide-y divide-gray-200">
                {''.join(row_cells)}
            </tbody>
            """

        # Build caption HTML if provided
        caption_html = ""
        if caption:
            caption_html = f"""
            <caption class="text-sm text-gray-500 text-center py-2">
                {self.escape_html(caption)}
            </caption>
            """

        # Build title HTML if provided
        title_html = ""
        if title:
            title_html = f"""
            <div class="mb-4">
                <h3 class="text-lg font-medium text-gray-900">{self.escape_html(title)}</h3>
            </div>
            """

        # Build responsive wrapper if needed
        table_html = f"""
        <table class="{' '.join(table_classes)}">
            {caption_html}
            {header_html}
            {rows_html}
        </table>
        """

        if responsive:
            table_html = f"""
            <div class="overflow-x-auto">
                {table_html}
            </div>
            """

        return f"""
        <div class="table-component">
            {title_html}
            {table_html}
        </div>
        """
