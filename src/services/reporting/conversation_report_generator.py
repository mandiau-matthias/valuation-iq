
"""
Conversation Report Generator - Refactored

This is the main report generator orchestrator that coordinates all report services
for deterministic valuation report generation from conversation data.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.utils.logging import get_logger

# Import refactored components
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .report_types import (
    ValuationReport, ReportConfiguration, DEFAULT_REPORT_CONFIG
)
from .data_aggregator import DataAggregator
from .report_formatter import ReportFormatter
from .insight_generator import InsightGenerator

# Import external services
from src.validation.data_quality.data_lineage_tracker import DataLineageTracker
from src.services.monitoring.analytics.conversation_metrics import ConversationMetricsCollector

logger = get_logger(__name__)


class ConversationReportGeneratorRefactored:
    """
    Refactored Conversation Report Generator with modular architecture

Coordinates:
- Data extraction and aggregation
- Deterministic insight generation
- HTML report formatting
- External service integration
- Error handling and logging
    """

    def __init__(self, config: Optional[ReportConfiguration] = None):
        """Initialize the refactored report generator"""
        self.logger = logger
        self.config = config or DEFAULT_REPORT_CONFIG

        # Initialize refactored components
        self.data_aggregator = DataAggregator(self.config)
        self.report_formatter = ReportFormatter(self.config)
        self.insight_generator = InsightGenerator()

        # Initialize external services
        self.data_lineage_tracker = DataLineageTracker()
        self.metrics_collector = ConversationMetricsCollector()

        self.logger.info(
            "ConversationReportGeneratorRefactored initialized",
            template_style=self.config.template_style,
            max_insights=self.config.max_insights
        )

    async def generate_report_from_conversation(
        self,
        session_id: str,
        conversation_data: Dict[str, Any],
        collected_data: Dict[str, Any]
    ) -> ValuationReport:
        """
        Generate a complete valuation report from conversation data

        Args:
            session_id: Session identifier
            conversation_data: Raw conversation data
            collected_data: Collected data from conversation

        Returns:
            Complete valuation report
        """
        try:
            self.logger.info("Generating valuation report from conversation", session_id=session_id)

            # Step 1: Extract and aggregate data
            extraction_result = self.data_aggregator.extract_key_information(
                conversation_data, collected_data
            )

            # Step 2: Calculate valuation
            valuation_result = await self.insight_generator.calculate_valuation(
                revenue=extraction_result.revenue,
                ebitda=extraction_result.ebitda,
                industry=extraction_result.industry,
                business_type=extraction_result.business_type,
                employee_count=extraction_result.employee_count
            )

            # Step 3: Generate insights
            insights = await self.insight_generator.generate_insights(
                collected_data=collected_data,
                valuation_result=valuation_result,
                conversation_data=conversation_data
            )

            # Step 4: Generate executive summary
            executive_summary = await self.insight_generator.generate_executive_summary(
                company_name=extraction_result.company_name,
                collected_data=collected_data,
                valuation_result=valuation_result,
                insights=insights
            )

            # Step 5: Generate recommendations
            recommendations = await self.insight_generator.generate_recommendations(
                collected_data=collected_data,
                insights=insights
            )

            # Step 6: Create complete report
            report = ValuationReport(
                company_name=extraction_result.company_name,
                estimated_value=valuation_result.estimated_value,
                methodology=valuation_result.methodology,
                confidence_score=valuation_result.confidence_score,
                executive_summary=executive_summary,
                key_metrics=extraction_result.key_metrics,
                insights=insights,
                recommendations=recommendations,
                assumptions=valuation_result.assumptions,
                limitations=valuation_result.limitations,
                generated_at=datetime.now(),
                session_id=session_id,
                conversation_summary=self.data_aggregator.summarize_conversation(conversation_data),
                metadata={
                    "extraction_confidence": extraction_result.confidence,
                    "completeness_score": extraction_result.completeness_score,
                    "missing_fields": extraction_result.missing_fields
                }
            )

            # Step 7: Track report generation
            await self._track_report_generation(session_id, report)

            self.logger.info(
                "Valuation report generated successfully",
                session_id=session_id,
                company_name=report.company_name,
                estimated_value=report.estimated_value["most_likely"],
                confidence=report.confidence_score
            )

            return report

        except Exception as e:
            self.logger.error(
                "Failed to generate valuation report",
                error=str(e),
                session_id=session_id
            )
            raise

    async def generate_html_report(self, report: ValuationReport) -> str:
        """
        Generate HTML report from ValuationReport object

        Args:
            report: Complete valuation report

        Returns:
            Formatted HTML report string
        """
        try:
            self.logger.info("Generating HTML report", company=report.company_name)

            html_content = self.report_formatter.generate_html_report(report)

            # Validate HTML
            if not self.report_formatter.validate_html(html_content):
                self.logger.warning("Generated HTML failed validation")

            self.logger.info("HTML report generated successfully", company=report.company_name)
            return html_content

        except Exception as e:
            self.logger.error(f"HTML report generation failed: {e}")
            raise

    async def generate_report_section(
        self,
        section_type: str,
        report: ValuationReport
    ) -> str:
        """
        Generate a specific report section

        Args:
            section_type: Type of section to generate
            report: Complete valuation report

        Returns:
            Formatted HTML for the section
        """
        try:
            self.logger.info(f"Generating report section: {section_type}")

            if section_type == "executive_summary":
                return self.report_formatter._format_executive_summary(report)
            elif section_type == "key_metrics":
                return self.report_formatter._format_key_metrics(report)
            elif section_type == "insights":
                return self.report_formatter._format_insights_section(report)
            elif section_type == "recommendations":
                return self.report_formatter._format_recommendations_section(report)
            else:
                raise ValueError(f"Unknown section type: {section_type}")

        except Exception as e:
            self.logger.error(f"Report section generation failed for {section_type}: {e}")
            raise

    async def _track_report_generation(self, session_id: str, report: ValuationReport):
        """Track report generation for analytics and lineage"""
        try:
            # Track data lineage
            self.data_lineage_tracker.track_data_point(
                field_name="valuation_report",
                value=f"Report generated for {report.company_name}",
                source="ml_inference",
                session_id=session_id,
                confidence=report.confidence_score
            )

            # Track metrics
            self.metrics_collector.record_report_generation(
                session_id=session_id,
                company_name=report.company_name,
                estimated_value=report.estimated_value["most_likely"],
                confidence_score=report.confidence_score,
                methodology=report.methodology,
                insights_count=len(report.insights),
                recommendations_count=len(report.recommendations)
            )

        except Exception as e:
            self.logger.warning(f"Report tracking failed: {e}")

    def get_report_configuration(self) -> ReportConfiguration:
        """Get current report configuration"""
        return self.config

    def update_report_configuration(self, new_config: ReportConfiguration) -> bool:
        """
        Update report configuration

        Args:
            new_config: New configuration

        Returns:
            True if successful, False otherwise
        """
        try:
            self.config = new_config

            # Update component configurations
            self.data_aggregator.config = new_config
            self.report_formatter.config = new_config

            self.logger.info("Report configuration updated")
            return True

        except Exception as e:
            self.logger.error(f"Configuration update failed: {e}")
            return False

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and component health"""
        return {
            "status": "operational",
            "components": {
                "data_aggregator": "active",
                "report_formatter": "active",
                "insight_generator": "active",
                "data_lineage_tracker": "active",
                "metrics_collector": "active"
            },
            "configuration": {
                "template_style": self.config.template_style,
                "max_insights": self.config.max_insights,
                "max_recommendations": self.config.max_recommendations,
                "confidence_threshold": self.config.confidence_threshold
            },
            "templates_available": self.report_formatter.get_template_names(),
            "timestamp": datetime.now().isoformat()
        }

    async def validate_report_data(
        self,
        conversation_data: Dict[str, Any],
        collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate report data before generation

        Args:
            conversation_data: Raw conversation data
            collected_data: Collected data

        Returns:
            Validation results
        """
        try:
            # Extract data
            extraction_result = self.data_aggregator.extract_key_information(
                conversation_data, collected_data
            )

            # Validate completeness
            is_complete, missing_critical = self.data_aggregator.validate_data_completeness(
                extraction_result
            )

            return {
                "is_valid": is_complete,
                "completeness_score": extraction_result.completeness_score,
                "confidence": extraction_result.confidence,
                "missing_critical_fields": missing_critical,
                "missing_fields": extraction_result.missing_fields,
                "extracted_data": {
                    "company_name": extraction_result.company_name,
                    "revenue": extraction_result.revenue,
                    "ebitda": extraction_result.ebitda,
                    "industry": extraction_result.industry,
                    "business_type": extraction_result.business_type
                }
            }

        except Exception as e:
            self.logger.error(f"Report data validation failed: {e}")
            return {
                "is_valid": False,
                "error": str(e)
            }


ConversationReportGenerator = ConversationReportGeneratorRefactored
