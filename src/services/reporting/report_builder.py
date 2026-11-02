from src.errors.error_types import TemplateRenderError

"""
Report Builder for Conversation Report Generator

This module handles HTML report construction, template rendering,
metric formatting, and CSS styling application.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

import re
from typing import Dict, Any, List, Optional
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.reporting.report_types import (
    ValuationReport, ValuationInsight, REPORT_TEMPLATES, DEFAULT_CSS_STYLES as CSS_STYLES
)

logger = get_logger(__name__)


class ReportBuilder:
    """
    Handles HTML report construction and template rendering
    """

    def __init__(self):
        """Initialize the report builder"""
        self.templates = REPORT_TEMPLATES
        self.css_styles = CSS_STYLES
        logger.info("✅ ReportBuilder initialized")

    def generate_html_report(self, report: ValuationReport) -> str:
        """
        Generate HTML report from ValuationReport object
        """
        try:
            logger.info(f"🔨 Building HTML report for {report.company_name}")

            # Generate insights HTML
            insights_html = self._generate_insights_html(report.insights)

            # Generate recommendations HTML
            recommendations_html = self._generate_recommendations_html(report.recommendations)

            # Generate metrics HTML
            metrics_html = self._generate_metrics_html(report.key_metrics)

            # Generate full HTML report
            html_content = self.templates["full_report"].format(
                company_name=report.company_name,
                generated_date=report.generated_at.strftime("%B %d, %Y"),
                executive_summary=self._generate_executive_summary_html(report),
                key_metrics=self.templates["key_metrics"].format(
                    metrics_html=metrics_html
                ),
                insights=self.templates["insights"].format(
                    insights_html=insights_html
                ),
                recommendations=self.templates["recommendations"].format(
                    recommendations_html=recommendations_html
                ),
                css_styles=self.css_styles
            )

            logger.info(f"✅ HTML report generated successfully for {report.company_name}")
            return html_content

        except TemplateRenderError as e:
            logger.error(f"❌ Failed to generate HTML report: {str(e)}")
            raise

    def _generate_executive_summary_html(self, report: ValuationReport) -> str:
        """Generate executive summary HTML section"""
        return self.templates["executive_summary"].format(
            company_name=report.company_name,
            estimated_value=report.estimated_value["most_likely"],
            min_value=report.estimated_value["min"],
            max_value=report.estimated_value["max"],
            confidence_score=report.confidence_score,
            methodology=report.methodology,
            executive_summary=report.executive_summary
        )

    def _generate_insights_html(self, insights: List[ValuationInsight]) -> str:
        """Generate insights HTML section"""
        insights_html = ""
        for insight in insights:
            impact_class = f"insight-{insight.impact}"
            insights_html += f"""
            <div class="insight {impact_class}">
                <h4>{insight.title}</h4>
                <p>{insight.description}</p>
                <span class="confidence">Confidence: {insight.confidence:.0%}</span>
            </div>
            """
        return insights_html

    def _generate_recommendations_html(self, recommendations: List[str]) -> str:
        """Generate recommendations HTML section"""
        recommendations_html = ""
        for recommendation in recommendations:
            recommendations_html += f"<li>{recommendation}</li>"
        return recommendations_html

    def _generate_metrics_html(self, key_metrics: Dict[str, Any]) -> str:
        """Generate metrics HTML section"""
        metrics_html = ""
        for key, value in key_metrics.items():
            if value is not None:
                formatted_value = self._format_metric_value(key, value)
                metrics_html += f"""
                <div class="metric">
                    <span class="metric-label">{key.replace('_', ' ').title()}</span>
                    <span class="metric-value">{formatted_value}</span>
                </div>
                """
        return metrics_html

    def _format_metric_value(self, key: str, value: Any) -> str:
        """Format metric value for display"""
        if value is None:
            return "Not provided"

        if key in ["revenue", "ebitda", "total_assets", "total_debt"]:
            return f"€{value:,.0f}"
        elif key == "founded_year":
            return str(value)
        else:
            return str(value)

    def parse_financial_value(self, value: Any) -> Optional[Decimal]:
        """Parse financial value from various formats"""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return to_decimal(value)

        if isinstance(value, str):
            # Remove currency symbols and commas
            clean_value = re.sub(r'[€$£¥,\s]', '', value)
            try:
                return to_decimal(clean_value)
            except ValueError:
                return None

        return None

    def extract_key_metrics(self, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format key business metrics"""
        return {
            "revenue": collected_data.get("revenue"),
            "ebitda": collected_data.get("ebitda"),
            "total_assets": collected_data.get("total_assets"),
            "total_debt": collected_data.get("total_debt"),
            "employee_count": collected_data.get("employee_count"),
            "founded_year": collected_data.get("founded_year"),
            "industry": collected_data.get("industry"),
            "business_type": collected_data.get("business_type")
        }

    def summarize_conversation(self, conversation_data: Dict[str, Any]) -> str:
        """Summarize conversation for context"""
        messages = conversation_data.get("conversation_history", [])
        if not messages:
            return "No conversation history available"

        # Simple summary of conversation length and topics
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        return f"Conversation with {len(user_messages)} user inputs covering business valuation topics."
