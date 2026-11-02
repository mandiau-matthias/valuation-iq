"""
Reports Services

This module contains services for generating reports from conversations
and business data.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from .conversation_report_generator import ConversationReportGenerator, ConversationReportGeneratorRefactored
from .report_builder import ReportBuilder
from .insights_generator import InsightsGenerator
from .report_types import (
    ValuationInsight, ValuationReport, REPORT_TEMPLATES, 
    VALUATION_METHODOLOGIES, DEFAULT_CSS_STYLES as CSS_STYLES
)

__all__ = [
    "ConversationReportGenerator",
    # Refactored modules
    "ConversationReportGeneratorRefactored",
    "ReportBuilder",
    "InsightsGenerator",
    "ValuationInsight",
    "ValuationReport",
    "REPORT_TEMPLATES",
    "VALUATION_METHODOLOGIES",
    "CSS_STYLES"
]
