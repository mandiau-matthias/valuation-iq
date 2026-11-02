
"""
Enhanced Template Service

Component-based template rendering with caching, minification, and composition.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from jinja2 import Environment, FileSystemLoader
import time

from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .components import (
    ComponentRegistry, 
    TemplateCacheService, 
    MinificationService,
    get_component,
    get_registry
)
from .components.core import *  # Import all core components to register them

logger = logging.getLogger(__name__)


class EnhancedValuationTemplateService:
    """Enhanced template service with component-based rendering"""

    def __init__(self, template_dir: str = "templates/valuation", redis_client=None):
        self.template_dir = template_dir
        self.component_registry = get_registry()
        self.cache_service = TemplateCacheService(redis_client)
        self.minification_service = MinificationService()

        # Initialize Jinja2 environment (existing)
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True,
            enable_async=True,
        )

        # Add custom filters
        self.env.filters['format_currency'] = self._format_currency
        self.env.filters['format_percentage'] = self._format_percentage
        self.env.filters['format_date'] = self._format_date

        # Statistics
        self.stats = {
            "components_rendered": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "minification_savings": 0
        }

        logger.info(f"Enhanced template service initialized with {len(self.component_registry.list_components())} components")

    async def render_component(
        self,
        component_name: str,
        data: Dict[str, Any],
        use_cache: bool = True,
        minify: bool = True
    ) -> str:
        """Render individual component"""
        try:
            component_class = get_component(component_name)
            component = component_class()

            # Override component config if needed
            if not minify:
                component.config.minify = False

            if use_cache:
                html = await component.render_cached(data, self.cache_service)
            else:
                html = await component.render(data)

            # Apply minification if enabled
            if minify and component.config.minify:
                original_size = len(html)
                html = self.minification_service.minify_html(html)
                self.stats["minification_savings"] += original_size - len(html)

            self.stats["components_rendered"] += 1
            logger.debug(f"Rendered component: {component_name}")

            return html

        except Exception as e:
            logger.error(f"Component render failed for {component_name}: {e}")
            return self._render_error_component(component_name, str(e))

    async def render_section_with_components(
        self,
        section_id: str,
        components: List[Tuple[str, Dict[str, Any]]],
        layout: str = "vertical",
        use_cache: bool = True,
        minify: bool = True
    ) -> str:
        """Render section composed of multiple components"""
        try:
            rendered_components = []

            for component_name, component_data in components:
                html = await self.render_component(component_name, component_data, use_cache, minify)
                rendered_components.append(html)

            # Assemble components based on layout
            if layout == "vertical":
                section_html = "\n".join(rendered_components)
            elif layout == "grid":
                components_joined = "\n".join(rendered_components)
                section_html = f"""
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {components_joined}
                </div>
                """
            elif layout == "horizontal":
                components_joined = "\n".join(rendered_components)
                section_html = f"""
                <div class="flex flex-wrap gap-4">
                    {components_joined}
                </div>
                """
            else:
                section_html = "\n".join(rendered_components)

            logger.debug(f"Rendered section {section_id} with {len(components)} components")
            return section_html

        except Exception as e:
            logger.error(f"Section render failed for {section_id}: {e}")
            return self._render_error_section(section_id, str(e))

    async def render_complete_report(
        self,
        report_data: Dict[str, Any],
        template_name: str = "base/full_report.html",
        use_components: bool = True,
        use_cache: bool = True,
        minify: bool = True
    ) -> str:
        """Render complete valuation report"""
        try:
            if use_components:
                # Use component-based rendering
                return await self._render_component_based_report(report_data, use_cache, minify)
            else:
                # Use traditional Jinja2 rendering
                return await self._render_traditional_report(report_data, template_name)

        except Exception as e:
            logger.error(f"Complete report render failed: {e}")
            return self._render_error_report(str(e))

    async def _render_component_based_report(
        self,
        report_data: Dict[str, Any],
        use_cache: bool = True,
        minify: bool = True
    ) -> str:
        """Render report using components"""
        sections = []

        # Header section
        if "company_name" in report_data:
            header_data = {
                "company_name": report_data.get("company_name"),
                "industry": report_data.get("industry"),
                "report_date": report_data.get("report_date"),
                "valuation_id": report_data.get("valuation_id"),
                "report_type": "Business Valuation Report"
            }
            header_html = await self.render_component("header", header_data, use_cache, minify)
            sections.append(header_html)

        # Executive Summary section
        if "executive_summary" in report_data:
            summary_data = {
                "title": "Executive Summary",
                "highlights": report_data.get("executive_summary", {}).get("highlights", []),
                "key_metrics": report_data.get("executive_summary", {}).get("key_metrics", []),
                "insights": report_data.get("executive_summary", {}).get("insights", [])
            }
            summary_html = await self.render_component("summary", summary_data, use_cache, minify)
            sections.append(summary_html)

        # Key Metrics section
        if "key_metrics" in report_data:
            metrics_data = report_data.get("key_metrics", [])
            metrics_components = []
            for metric in metrics_data:
                metrics_components.append(("metric_card", metric))

            metrics_html = await self.render_section_with_components(
                "key_metrics", 
                metrics_components, 
                "grid", 
                use_cache, 
                minify
            )
            sections.append(f"""
            <div class="section mb-8">
                <h2 class="text-xl font-bold text-gray-900 mb-4">Key Metrics</h2>
                {metrics_html}
            </div>
            """)

        # Valuation Methods table
        if "valuation_methods" in report_data:
            table_data = {
                "title": "Valuation Methodology",
                "headers": [
                    {"text": "Method", "align": "left"},
                    {"text": "Weight", "align": "center", "unit": "percentage"},
                    {"text": "Estimated Value", "align": "right", "unit": "currency"}
                ],
                "rows": report_data.get("valuation_methods", [])
            }
            table_html = await self.render_component("table", table_data, use_cache, minify)
            sections.append(f"""
            <div class="section mb-8">
                {table_html}
            </div>
            """)

        # Footer section
        footer_data = {
            "generated_by": "Upswitch Valuation Engine",
            "generation_timestamp": report_data.get("generation_timestamp", time.strftime("%Y-%m-%d %H:%M:%S")),
            "version": "2.0.0"
        }
        footer_html = await self.render_component("footer", footer_data, use_cache, minify)
        sections.append(footer_html)

        # Combine all sections
        sections_joined = "\n".join(sections)
        company_name = report_data.get('company_name', 'Company')
        report_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Valuation Report - {company_name}</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                .primary-600 {{ color: #14B8A6; }}
                .border-primary-600 {{ border-color: #14B8A6; }}
                .bg-primary-600 {{ background-color: #14B8A6; }}
                .text-primary-600 {{ color: #14B8A6; }}
                .from-primary-600 {{ --tw-gradient-from: #14B8A6; }}
            </style>
        </head>
        <body class="bg-gray-50">
            <div class="max-w-6xl mx-auto p-6">
                {sections_joined}
            </div>
        </body>
        </html>
        """

        return report_html

    async def _render_traditional_report(
        self,
        report_data: Dict[str, Any],
        template_name: str
    ) -> str:
        """Render report using traditional Jinja2 templates"""
        try:
            template = self.env.get_template(template_name)

            # Add generation timestamp
            report_data['generation_timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")

            html = await template.render_async(**report_data)
            logger.info(f"Rendered traditional template: {template_name}")
            return html

        except Exception as e:
            logger.error(f"Traditional template render failed: {e}")
            return self._render_error_report(str(e))

    def _render_error_component(self, component_name: str, error: str) -> str:
        """Render error component"""
        return f"""
        <div class="bg-red-50 border border-red-200 rounded-lg p-4">
            <div class="flex items-center">
                <svg class="h-5 w-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                </svg>
                <span class="text-red-700">Component '{component_name}' failed to render: {error}</span>
            </div>
        </div>
        """

    def _render_error_section(self, section_id: str, error: str) -> str:
        """Render error section"""
        return f"""
        <div class="bg-red-50 border border-red-200 rounded-lg p-4">
            <div class="flex items-center">
                <svg class="h-5 w-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                </svg>
                <span class="text-red-700">Section '{section_id}' failed to render: {error}</span>
            </div>
        </div>
        """

    def _render_error_report(self, error: str) -> str:
        """Render error report"""
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Report Generation Error</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-50">
            <div class="max-w-4xl mx-auto p-6">
                <div class="bg-red-50 border border-red-200 rounded-lg p-6">
                    <h1 class="text-xl font-bold text-red-800 mb-2">Report Generation Failed</h1>
                    <p class="text-red-700">{error}</p>
                </div>
            </div>
        </body>
        </html>
        """

    def get_available_components(self) -> List[str]:
        """Get list of available components"""
        return self.component_registry.list_components()

    def get_component_metadata(self, component_name: str) -> Dict[str, Any]:
        """Get component metadata"""
        return self.component_registry.get_metadata(component_name)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache_service.get_stats()

    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            **self.stats,
            "cache_stats": self.get_cache_stats(),
            "available_components": len(self.get_available_components())
        }

    async def clear_cache(self):
        """Clear all cache"""
        await self.cache_service.clear_all()
        logger.info("Cleared all template cache")

    # Custom filter functions
    def _format_currency(self, value: Decimal, currency: str = "USD") -> str:
        """Format currency value"""
        if currency == "USD":
            return f"${value:,.2f}"
        elif currency == "EUR":
            return f"\u20AC{value:,.2f}"
        else:
            return f"{value:,.2f} {currency}"

    def _format_percentage(self, value: Decimal, decimals: int = 1) -> str:
        """Format percentage value"""
        return f"{value:.{decimals}f}%"

    def _format_date(self, date_value) -> str:
        """Format date value"""
        if hasattr(date_value, 'strftime'):
            return date_value.strftime("%B %d, %Y")
        else:
            return str(date_value)
