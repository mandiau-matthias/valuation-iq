"""
Footer Component

Reusable footer component for report footers with disclaimers and metadata.
"""

from typing import Dict, Any
from datetime import datetime
from ..base import ComponentBase, ComponentConfig
from ..registry import register_component


@register_component("footer", {
    "description": "Report footer with disclaimers and metadata",
    "version": "1.0.0",
    "author": "Upswitch Team"
})
class FooterComponent(ComponentBase):
    """Reusable footer component for report footers"""

    async def render(self, data: Dict[str, Any]) -> str:
        """Render footer component"""
        # Extract data with defaults
        disclaimer = self.get_safe_value(data, "disclaimer", 
            "This valuation report is provided for informational purposes only and should not be considered as financial advice. "
            "Valuations are estimates based on available data and market conditions at the time of analysis.")
        generated_by = self.get_safe_value(data, "generated_by", "Upswitch Valuation Engine")
        generation_timestamp = self.get_safe_value(data, "generation_timestamp", datetime.now().isoformat())
        version = self.get_safe_value(data, "version", "1.0.0")
        contact_info = self.get_safe_value(data, "contact_info", {})
        legal_links = self.get_safe_value(data, "legal_links", [])
        show_timestamp = self.get_safe_value(data, "show_timestamp", True)
        show_version = self.get_safe_value(data, "show_version", True)

        # Format generation timestamp
        try:
            if isinstance(generation_timestamp, str):
                parsed_time = datetime.fromisoformat(generation_timestamp.replace('Z', '+00:00'))
                formatted_time = parsed_time.strftime("%B %d, %Y at %I:%M %p UTC")
            else:
                formatted_time = generation_timestamp.strftime("%B %d, %Y at %I:%M %p UTC")
        except (ValueError, TypeError, AttributeError):
            formatted_time = str(generation_timestamp)

        # Build contact info HTML
        contact_html = ""
        if contact_info:
            contact_items = []
            if contact_info.get("email"):
                contact_items.append(f"""
                <div class="flex items-center text-sm text-gray-600">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                    </svg>
                    <a href="mailto:{self.escape_html(contact_info['email'])}" class="hover:text-primary-600">
                        {self.escape_html(contact_info['email'])}
                    </a>
                </div>
                """)

            if contact_info.get("phone"):
                contact_items.append(f"""
                <div class="flex items-center text-sm text-gray-600">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                    </svg>
                    <a href="tel:{self.escape_html(contact_info['phone'])}" class="hover:text-primary-600">
                        {self.escape_html(contact_info['phone'])}
                    </a>
                </div>
                """)

            if contact_info.get("website"):
                contact_items.append(f"""
                <div class="flex items-center text-sm text-gray-600">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9v-9m0-9v9"></path>
                    </svg>
                    <a href="{self.escape_html(contact_info['website'])}" class="hover:text-primary-600" target="_blank" rel="noopener">
                        {self.escape_html(contact_info['website'])}
                    </a>
                </div>
                """)

            if contact_items:
                contact_html = f"""
                <div class="mb-4">
                    <h4 class="text-sm font-medium text-gray-900 mb-2">Contact Information</h4>
                    <div class="space-y-1">
                        {''.join(contact_items)}
                    </div>
                </div>
                """

        # Build legal links HTML
        legal_html = ""
        if legal_links:
            legal_items = []
            for link in legal_links:
                if isinstance(link, dict):
                    text = link.get("text", "")
                    url = link.get("url", "#")
                else:
                    text = str(link)
                    url = "#"

                legal_items.append(f"""
                <a href="{self.escape_html(url)}" class="text-sm text-gray-600 hover:text-primary-600 mr-4">
                    {self.escape_html(text)}
                </a>
                """)

            legal_html = f"""
            <div class="mb-4">
                <div class="flex flex-wrap">
                    {''.join(legal_items)}
                </div>
            </div>
            """

        # Build metadata HTML
        metadata_items = []
        if show_timestamp:
            metadata_items.append(f"""
            <div class="text-xs text-gray-500">
                <strong>Generated:</strong> {formatted_time}
            </div>
            """)

        if show_version:
            metadata_items.append(f"""
            <div class="text-xs text-gray-500">
                <strong>Version:</strong> {self.escape_html(version)}
            </div>
            """)

        metadata_html = ""
        if metadata_items:
            metadata_html = f"""
            <div class="flex flex-wrap gap-4 mb-4">
                {''.join(metadata_items)}
            </div>
            """

        return f"""
        <div class="footer-component mt-12 pt-6 border-t border-gray-200">
            <div class="max-w-4xl mx-auto">
                {contact_html}
                {legal_html}
                {metadata_html}

                <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
                    <div class="flex">
                        <svg class="w-5 h-5 text-yellow-600 mr-2 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                        </svg>
                        <div>
                            <h4 class="text-sm font-medium text-yellow-800 mb-1">Disclaimer</h4>
                            <p class="text-sm text-yellow-700">{self.escape_html(disclaimer)}</p>
                        </div>
                    </div>
                </div>

                <div class="text-center text-xs text-gray-500">
                    <p>Generated by <strong>{self.escape_html(generated_by)}</strong></p>
                </div>
            </div>
        </div>
        """
