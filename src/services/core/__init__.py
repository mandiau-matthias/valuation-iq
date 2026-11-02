"""
Core Valuation Services — LEGACY RE-EXPORTS

.. deprecated::
    The ``ValuationOrchestrator`` and ``ValuationProcessor`` re-exported
    here are from the legacy ``orchestration/`` sub-package.  The
    production HTTP pipeline uses ``src.api.routes.valuation`` instead.
    Imports are kept for ``ProgressiveValuationService`` and debug/MCP
    compatibility.  Prefer ``src.api.routes.valuation`` for new work.
"""

from .orchestration.valuation_mcp_service import ValuationMCPServiceRefactored as ValuationMCPService, get_mcp_service
from .monitoring.valuation_quality_scorer import ValuationQualityScorer, get_quality_scorer
from .orchestration.valuation_report_service import ValuationReportService

# Orchestration Service Components
from .orchestration.valuation_orchestrator import ValuationOrchestrator
from .orchestration.valuation_processor import ValuationProcessor

# MCP Types
from .workflows.mcp_types import (
    ValuationData, MCPInsight, MCPResult, MCPConfiguration,
    PatternInsight, MarketTrend, IndustryAnalysis, RiskAssessment,
    Opportunity, StrategicRecommendation, ProcessingMetrics,
    DataSource, ProcessingStatus, InsightType, ConfidenceLevel,
    DataIngestionConfig, FeatureEngineeringConfig, PatternAnalysisConfig,
    AIEnhancementConfig, DEFAULT_MCP_CONFIG, DEFAULT_DATA_INGESTION_CONFIG,
    DEFAULT_FEATURE_ENGINEERING_CONFIG, DEFAULT_PATTERN_ANALYSIS_CONFIG,
    DEFAULT_AI_ENHANCEMENT_CONFIG
)

__all__ = [
    # Original services
    "ValuationMCPService",
    "get_mcp_service",
    "ValuationQualityScorer", 
    "get_quality_scorer",
    "ValuationReportService",

    # Orchestration Services
    "ValuationOrchestrator",
    "ValuationProcessor",

    # MCP Types
    "ValuationData",
    "MCPInsight",
    "MCPResult",
    "MCPConfiguration",
    "PatternInsight",
    "MarketTrend",
    "IndustryAnalysis",
    "RiskAssessment",
    "Opportunity",
    "StrategicRecommendation",
    "ProcessingMetrics",
    "DataSource",
    "ProcessingStatus",
    "InsightType",
    "ConfidenceLevel",
    "DataIngestionConfig",
    "FeatureEngineeringConfig",
    "PatternAnalysisConfig",
    "AIEnhancementConfig",
    "DEFAULT_MCP_CONFIG",
    "DEFAULT_DATA_INGESTION_CONFIG",
    "DEFAULT_FEATURE_ENGINEERING_CONFIG",
    "DEFAULT_PATTERN_ANALYSIS_CONFIG",
    "DEFAULT_AI_ENHANCEMENT_CONFIG"
]
