"""
Business Intelligence Services

This module contains services for business type intelligence,
methodology selection, and business analysis.
"""

# Import from existing modules
from .integration.business_intelligence_service import BusinessTypeIntelligenceService as BusinessIntelligenceService, BusinessTypeIntelligenceService as BusinessTypeIntelligenceServiceRefactored
from .integration.business_type_integration_engine import BusinessTypeIntegrationEngineRefactored as BusinessTypeIntegrationEngine
from .methodology.intelligent_methodology_selector import IntelligentMethodologySelectorRefactored as IntelligentMethodologySelector
from .analysis.business_analyzer import BusinessAnalyzer
from .analysis.business_type_analyzer import BusinessTypeAnalyzer
from .methodology.methodology_selector import MethodologySelector
from .classification.industry_rules import IndustryRules
from .integration.scoring_engine import ScoringEngine
from .analysis.intelligence_processor import IntelligenceProcessor
from .analysis.data_integrator import DataIntegrator
from .methodology.methodology_analyzer import MethodologyAnalyzer
from .integration.selection_engine import SelectionEngine

# Types
from .integration.mapper_types import (
    ValuationMethodology, MethodologyDecision, BusinessCharacteristics,
    BusinessCategory, AssetIntensity, GrowthPotential, RevenuePredictability,
    RefinementFactors, BusinessTypeConfig, IndustryFactors
)

# Intelligence types
from .analysis.intelligence_types import (
    LearningType, BusinessTypeAnalysis, MethodologyWeights, LearnedAdjustments,
    BusinessTypeStatistics, HistoricalAnalysis, BusinessAdjustments,
    MarketAdjustments, OwnerAdjustments, LearningModel, BusinessTypeConfig,
    AnalysisRequest, AnalysisResponse, ConfidenceLevel, AnalysisStatus,
    ProcessingMetrics, BUSINESS_TYPE_CATEGORIES, DEFAULT_BUSINESS_CONFIG,
    ML_MODEL_CONFIG
)

# Selector types
from .integration.selector_types import (
    MethodologyType, BusinessContext, FinancialScore, OwnerScore, MarketScore,
    MethodologySelection, MethodologyPreference, SelectionRequest, SelectionResponse,
    ConfidenceLevel, SelectionStatus, BusinessRules, IndustryRules, FinancialRules,
    OwnerRules, MarketRules, DEFAULT_BUSINESS_RULES, DEFAULT_INDUSTRY_RULES,
    DEFAULT_FINANCIAL_RULES, DEFAULT_OWNER_RULES, DEFAULT_MARKET_RULES,
    INDUSTRY_CATEGORIES, MARKET_POSITION_LEVELS, COMPETITIVE_ADVANTAGE_LEVELS,
    METHODOLOGY_WEIGHTS, CONFIDENCE_THRESHOLDS
)

__all__ = [
    "BusinessIntelligenceService",
    "BusinessTypeIntegrationEngine", 
    "IntelligentMethodologySelector",
    "BusinessAnalyzer",
    "BusinessTypeAnalyzer",
    "MethodologySelector",
    "IndustryRules",
    "ScoringEngine",
    "IntelligenceProcessor",
    "DataIntegrator",
    "MethodologyAnalyzer",
    "SelectionEngine",
    # Types
    "ValuationMethodology",
    "MethodologyDecision",
    "BusinessCharacteristics",
    "BusinessCategory",
    "AssetIntensity",
    "GrowthPotential",
    "RevenuePredictability",
    "RefinementFactors",
    "BusinessTypeConfig",
    "IndustryFactors",
    # New intelligence types
    "LearningType",
    "BusinessTypeAnalysis",
    "MethodologyWeights",
    "LearnedAdjustments",
    "BusinessTypeStatistics",
    "HistoricalAnalysis",
    "BusinessAdjustments",
    "MarketAdjustments",
    "OwnerAdjustments",
    "LearningModel",
    "AnalysisRequest",
    "AnalysisResponse",
    "ConfidenceLevel",
    "AnalysisStatus",
    "ProcessingMetrics",
    "BUSINESS_TYPE_CATEGORIES",
    "DEFAULT_BUSINESS_CONFIG",
    "ML_MODEL_CONFIG",
    # New selector types
    "MethodologyType",
    "BusinessContext",
    "FinancialScore",
    "OwnerScore",
    "MarketScore",
    "MethodologySelection",
    "MethodologyPreference",
    "SelectionRequest",
    "SelectionResponse",
    "ConfidenceLevel",
    "SelectionStatus",
    "BusinessRules",
    "IndustryRules",
    "FinancialRules",
    "OwnerRules",
    "MarketRules",
    "DEFAULT_BUSINESS_RULES",
    "DEFAULT_INDUSTRY_RULES",
    "DEFAULT_FINANCIAL_RULES",
    "DEFAULT_OWNER_RULES",
    "DEFAULT_MARKET_RULES",
    "INDUSTRY_CATEGORIES",
    "MARKET_POSITION_LEVELS",
    "COMPETITIVE_ADVANTAGE_LEVELS",
    "METHODOLOGY_WEIGHTS",
    "CONFIDENCE_THRESHOLDS"
]
