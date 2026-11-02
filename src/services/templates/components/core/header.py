"""
Header Component

Reusable header component for valuation reports with branding and metadata.
"""

from typing import Dict, Any
from datetime import datetime
from ..base import ComponentBase, ComponentConfig
from ..registry import register_component


@register_component("header", {
    "description": "Report header with company branding and metadata",
    "version": "1.0.0",
    "author": "Upswitch Team"
})
class HeaderComponent(ComponentBase):
    """Reusable header component for valuation reports"""

    async def render(self, data: Dict[str, Any]) -> str:
        """Render header component"""
        # Extract data with defaults
        company_name = self.get_safe_value(data, "company_name", "Company")
        industry = self.get_safe_value(data, "industry", "Technology")
        report_date = self.get_safe_value(data, "report_date", datetime.now().strftime("%Y-%m-%d"))
        valuation_id = self.get_safe_value(data, "valuation_id", "N/A")
        report_type = self.get_safe_value(data, "report_type", "Business Valuation")
        logo_url = self.get_safe_value(data, "logo_url", "")

        # Format report date
        if isinstance(report_date, str):
            try:
                parsed_date = datetime.fromisoformat(report_date.replace('Z', '+00:00'))
                formatted_date = parsed_date.strftime("%B %d, %Y")
            except (ValueError, TypeError, AttributeError):
                formatted_date = report_date
        else:
            formatted_date = report_date.strftime("%B %d, %Y") if hasattr(report_date, 'strftime') else str(report_date)

        # Build logo HTML if provided
        logo_html = ""
        if logo_url:
            logo_html = f"""
            <div class="flex items-center mb-4">
                <img src="{self.escape_html(logo_url)}" alt="{self.escape_html(company_name)} Logo" 
                     class="h-12 w-auto mr-4">
            </div>
            """

        return f"""
        <div class="header bg-gradient-to-r from-primary-600 to-blue-600 text-white rounded-lg p-8 mb-8">
            {logo_html}
            <div class="flex flex-col md:flex-row md:items-center md:justify-between">
                <div class="mb-4 md:mb-0">
                    <h1 class="text-3xl font-bold mb-2">{self.escape_html(report_type)}</h1>
                    <h2 class="text-xl font-semibold text-primary-100">{self.escape_html(company_name)}</h2>
                    <p class="text-primary-200 mt-1">{self.escape_html(industry)}</p>
                </div>
                <div class="text-right">
                    <div class="text-sm text-primary-200">
                        <p><strong>Report Date:</strong> {formatted_date}</p>
                        <p><strong>Valuation ID:</strong> {self.escape_html(valuation_id)}</p>
                    </div>
                </div>
            </div>
        </div>
        """
