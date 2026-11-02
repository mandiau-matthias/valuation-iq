
"""
Report Formatter

This module handles HTML report formatting and template rendering
for professional valuation reports with customizable styling.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .report_types import (
    ValuationReport, ValuationInsight, ReportConfiguration,
    DEFAULT_REPORT_CONFIG, REPORT_TEMPLATES, DEFAULT_CSS_STYLES
)

logger = get_logger(__name__)


class ReportFormatter:
    """
    Report formatting service for HTML report generation

    Handles:
    - Load and manage report templates
    - Generate HTML sections
    - Format metrics and values
    - Apply CSS styles
    - Render complete HTML reports
    """

    def __init__(self, config: Optional[ReportConfiguration] = None):
        """Initialize the report formatter"""
        self.logger = logger
        self.config = config or DEFAULT_REPORT_CONFIG

        # Load templates
        self.templates = self._load_report_templates()
        self.css_styles = self._get_css_styles()

        self.logger.info("ReportFormatter initialized")

    def generate_html_report(self, report: ValuationReport) -> str:
        """
        Generate complete HTML report from ValuationReport object

        Args:
            report: Complete valuation report

        Returns:
            Formatted HTML report string
        """
        try:
            self.logger.info("Generating HTML report", company=report.company_name)

            # Generate individual sections
            executive_summary_html = self._format_executive_summary(report)
            key_metrics_html = self._format_key_metrics(report)
            insights_html = self._format_insights_section(report)
            recommendations_html = self._format_recommendations_section(report)

            # Generate complete HTML report
            html_content = self.templates["full_report"].format(
                company_name=report.company_name,
                generated_date=report.generated_at.strftime("%B %d, %Y"),
                executive_summary=executive_summary_html,
                key_metrics=key_metrics_html,
                insights=insights_html,
                recommendations=recommendations_html,
                css_styles=self.css_styles
            )

            self.logger.info("HTML report generated successfully", company=report.company_name)
            return html_content

        except Exception as e:
            self.logger.error(f"HTML report generation failed: {e}")
            raise

    def _format_executive_summary(self, report: ValuationReport) -> str:
        """Format executive summary section"""
        try:
            return self.templates["executive_summary"].format(
                company_name=report.company_name,
                estimated_value=report.estimated_value["most_likely"],
                min_value=report.estimated_value["min"],
                max_value=report.estimated_value["max"],
                confidence_score=report.confidence_score,
                methodology=report.methodology,
                executive_summary=report.executive_summary
            )

        except Exception as e:
            self.logger.error(f"Executive summary formatting failed: {e}")
            return f"<div class='error'>Executive summary formatting failed: {e}</div>"

    def _format_key_metrics(self, report: ValuationReport) -> str:
        """Format key metrics section"""
        try:
            if not self.config.include_key_metrics:
                return ""

            metrics_html = ""
            for key, value in report.key_metrics.items():
                if value is not None:
                    formatted_value = self._format_metric_value(key, value)
                    metrics_html += f"""
                    <div class="metric">
                        <span class="metric-label">{self._format_metric_label(key)}</span>
                        <span class="metric-value">{formatted_value}</span>
                    </div>
                    """

            return self.templates["key_metrics"].format(metrics_html=metrics_html)

        except Exception as e:
            self.logger.error(f"Key metrics formatting failed: {e}")
            return f"<div class='error'>Key metrics formatting failed: {e}</div>"

    def _format_insights_section(self, report: ValuationReport) -> str:
        """Format insights section"""
        try:
            if not self.config.include_insights:
                return ""

            insights_html = ""
            for insight in report.insights[:self.config.max_insights]:
                impact_class = f"insight-{insight.impact}"
                insights_html += f"""
                <div class="insight {impact_class}">
                    <h4>{insight.title}</h4>
                    <p>{insight.description}</p>
                    <div class="insight-meta">
                        <span class="category">{insight.category.title()}</span>
                        <span class="confidence">Confidence: {insight.confidence:.0%}</span>
                    </div>
                </div>
                """

            return self.templates["insights"].format(insights_html=insights_html)

        except Exception as e:
            self.logger.error(f"Insights section formatting failed: {e}")
            return f"<div class='error'>Insights section formatting failed: {e}</div>"

    def _format_recommendations_section(self, report: ValuationReport) -> str:
        """Format recommendations section"""
        try:
            if not self.config.include_recommendations:
                return ""

            recommendations_html = ""
            for recommendation in report.recommendations[:self.config.max_recommendations]:
                recommendations_html += f"<li>{recommendation}</li>"

            return self.templates["recommendations"].format(recommendations_html=recommendations_html)

        except Exception as e:
            self.logger.error(f"Recommendations section formatting failed: {e}")
            return f"<div class='error'>Recommendations section formatting failed: {e}</div>"

    def _format_metric_value(self, key: str, value: Any) -> str:
        """Format metric value for display"""
        try:
            if isinstance(value, (int, float)):
                if key in ["revenue", "ebitda", "estimated_value"]:
                    return f"€{value:,.0f}"
                elif key in ["profit_margin", "revenue_growth"]:
                    return f"{value:.1f}%"
                else:
                    return f"{value:,.0f}"
            elif isinstance(value, str):
                return value
            else:
                return str(value)

        except Exception as e:
            self.logger.warning(f"Failed to format metric value for {key}: {e}")
            return str(value)

    def _format_metric_label(self, key: str) -> str:
        """Format metric label for display"""
        # Convert snake_case to Title Case
        return key.replace('_', ' ').title()

    def _load_report_templates(self) -> Dict[str, str]:
        """Load HTML report templates"""
        return REPORT_TEMPLATES.copy()

    def _get_css_styles(self) -> str:
        """Get CSS styles for the report"""
        base_styles = DEFAULT_CSS_STYLES

        # Add template-specific styles
        if self.config.template_style == "minimal":
            base_styles += self._get_minimal_styles()
        elif self.config.template_style == "detailed":
            base_styles += self._get_detailed_styles()
        else:  # professional
            base_styles += self._get_professional_styles()

        return base_styles

    def _get_minimal_styles(self) -> str:
        """Get minimal template styles"""
        return """
        .report-container {
            padding: 20px;
        }

        .insight {
            margin: 10px 0;
            padding: 10px;
        }

        .metric {
            padding: 10px;
        }
        """

    def _get_detailed_styles(self) -> str:
        """Get detailed template styles"""
        return """
        .insight {
            margin: 20px 0;
            padding: 20px;
            border-radius: 8px;
        }

        .insight-meta {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
            font-size: 0.9em;
            color: #666;
        }

        .metric {
            padding: 20px;
            border-radius: 8px;
            margin: 10px 0;
        }

        .recommendations-list {
            padding-left: 20px;
        }

        .recommendations-list li {
            margin: 10px 0;
            line-height: 1.6;
        }
        """

    def _get_professional_styles(self) -> str:
        """Get professional template styles"""
        return """
        .report-container {
            font-family: 'Georgia', serif;
            line-height: 1.8;
        }

        .report-header {
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            padding: 40px;
            border-radius: 8px 8px 0 0;
        }

        .insight {
            border-left: 5px solid #007bff;
            background: linear-gradient(90deg, #f8f9fa, #ffffff);
            margin: 20px 0;
            padding: 25px;
            border-radius: 0 8px 8px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .insight-high {
            border-left-color: #dc3545;
            background: linear-gradient(90deg, #fff5f5, #ffffff);
        }

        .insight-medium {
            border-left-color: #ffc107;
            background: linear-gradient(90deg, #fffbf0, #ffffff);
        }

        .insight-low {
            border-left-color: #28a745;
            background: linear-gradient(90deg, #f0fff4, #ffffff);
        }

        .metric {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            transition: transform 0.2s ease;
        }

        .metric:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }

        .valuation-range {
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            margin: 20px 0;
        }

        .estimated-value {
            font-size: 2.5em;
            font-weight: bold;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        """

    def generate_section_html(
        self,
        section_type: str,
        content: Dict[str, Any]
    ) -> str:
        """
        Generate HTML for a specific report section

        Args:
            section_type: Type of section to generate
            content: Content data for the section

        Returns:
            Formatted HTML for the section
        """
        try:
            if section_type == "executive_summary":
                return self._format_executive_summary_from_data(content)
            elif section_type == "key_metrics":
                return self._format_key_metrics_from_data(content)
            elif section_type == "insights":
                return self._format_insights_from_data(content)
            elif section_type == "recommendations":
                return self._format_recommendations_from_data(content)
            else:
                return f"<div class='error'>Unknown section type: {section_type}</div>"

        except Exception as e:
            self.logger.error(f"Section HTML generation failed for {section_type}: {e}")
            return f"<div class='error'>Section generation failed: {e}</div>"

    def _format_executive_summary_from_data(self, content: Dict[str, Any]) -> str:
        """Format executive summary from data"""
        return self.templates["executive_summary"].format(**content)

    def _format_key_metrics_from_data(self, content: Dict[str, Any]) -> str:
        """Format key metrics from data"""
        metrics_html = content.get("metrics_html", "")
        return self.templates["key_metrics"].format(metrics_html=metrics_html)

    def _format_insights_from_data(self, content: Dict[str, Any]) -> str:
        """Format insights from data"""
        insights_html = content.get("insights_html", "")
        return self.templates["insights"].format(insights_html=insights_html)

    def _format_recommendations_from_data(self, content: Dict[str, Any]) -> str:
        """Format recommendations from data"""
        recommendations_html = content.get("recommendations_html", "")
        return self.templates["recommendations"].format(recommendations_html=recommendations_html)

    def update_template(self, template_name: str, template_content: str) -> bool:
        """
        Update a report template

        Args:
            template_name: Name of the template to update
            template_content: New template content

        Returns:
            True if successful, False otherwise
        """
        try:
            if template_name in self.templates:
                self.templates[template_name] = template_content
                self.logger.info(f"Template updated: {template_name}")
                return True
            else:
                self.logger.warning(f"Unknown template: {template_name}")
                return False

        except Exception as e:
            self.logger.error(f"Template update failed: {e}")
            return False

    def get_template_names(self) -> List[str]:
        """Get list of available template names"""
        return list(self.templates.keys())

    def validate_html(self, html_content: str) -> bool:
        """
        Basic HTML validation

        Args:
            html_content: HTML content to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Basic validation - check for required tags
            required_tags = ["<html>", "<head>", "<body>"]
            return all(tag in html_content for tag in required_tags)

        except Exception as e:
            self.logger.error(f"HTML validation failed: {e}")
            return False
