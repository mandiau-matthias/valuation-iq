"""
Pattern Analysis Types and Data Structures

This module defines all data structures, enums, and configuration classes
for the Pattern Analyzer refactoring.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class InsightType(str, Enum):
    """Types of pattern insights"""
    BUSINESS_TYPE = "business_type"
    INDUSTRY = "industry"
    FINANCIAL = "financial"
    VALUATION_METHOD = "valuation_method"
    TEMPORAL = "temporal"
    CLUSTERING = "clustering"
    MARKET_TREND = "market_trend"
    RISK = "risk"
    OPPORTUNITY = "opportunity"


class ConfidenceLevel(str, Enum):
    """Confidence levels for insights"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class PatternType(str, Enum):
    """Types of patterns"""
    TREND = "trend"
    SEASONAL = "seasonal"
    CYCLICAL = "cyclical"
    ANOMALY = "anomaly"
    CORRELATION = "correlation"
    CLUSTER = "cluster"
    OUTLIER = "outlier"


class AnalysisScope(str, Enum):
    """Scope of analysis"""
    INDIVIDUAL = "individual"
    INDUSTRY = "industry"
    MARKET = "market"
    GLOBAL = "global"


@dataclass
class ValuationData:
    """Valuation data structure"""
    company_id: str
    company_name: str
    business_type: str
    industry: str
    revenue: Decimal
    ebitda: Decimal
    equity_value: Decimal
    valuation_date: datetime
    valuation_method: str
    confidence_score: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternInsight:
    """Pattern insight result"""
    insight_id: str
    insight_type: InsightType
    pattern_type: PatternType
    description: str
    confidence: ConfidenceLevel
    significance_score: Decimal
    affected_companies: List[str]
    timeframe: Tuple[datetime, datetime]
    supporting_data: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MarketTrend:
    """Market trend analysis"""
    trend_id: str
    trend_type: str
    direction: str  # increasing, decreasing, stable
    magnitude: Decimal
    confidence: ConfidenceLevel
    timeframe: Tuple[datetime, datetime]
    affected_industries: List[str]
    key_indicators: List[str]
    description: str
    impact_assessment: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class IndustryAnalysis:
    """Industry analysis result"""
    industry: str
    analysis_id: str
    performance_score: Decimal
    growth_rate: Decimal
    market_size: Decimal
    competitive_intensity: Decimal
    key_metrics: Dict[str, Decimal]
    benchmark_comparison: Dict[str, Any]
    trends: List[str]
    opportunities: List[str]
    risks: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RiskAssessment:
    """Risk assessment result"""
    risk_id: str
    risk_type: str
    severity: str  # low, medium, high, critical
    probability: Decimal
    impact: Decimal
    affected_companies: List[str]
    description: str
    mitigation_strategies: List[str]
    monitoring_indicators: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Opportunity:
    """Business opportunity identification"""
    opportunity_id: str
    opportunity_type: str
    potential_value: Decimal
    probability: Decimal
    timeframe: Tuple[datetime, datetime]
    affected_companies: List[str]
    description: str
    requirements: List[str]
    success_factors: List[str]
    risks: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StrategicRecommendation:
    """Strategic recommendation"""
    recommendation_id: str
    priority: str  # low, medium, high, critical
    category: str
    title: str
    description: str
    rationale: str
    expected_impact: str
    implementation_steps: List[str]
    success_metrics: List[str]
    timeline: str
    resources_required: List[str]
    risks: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MCPInsight:
    """MCP insight result"""
    insight_id: str
    insight_type: InsightType
    title: str
    description: str
    confidence: ConfidenceLevel
    data_sources: List[str]
    analysis_method: str
    key_findings: List[str]
    implications: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PatternAnalysisConfig:
    """Pattern analysis configuration"""
    enable_clustering: bool = True
    enable_temporal_analysis: bool = True
    enable_risk_assessment: bool = True
    enable_opportunity_identification: bool = True
    clustering_algorithm: str = "kmeans"  # kmeans, dbscan, hierarchical
    min_cluster_size: int = 3
    max_clusters: int = 10
    confidence_threshold: Decimal = Decimal('0.7')
    significance_threshold: Decimal = Decimal('0.05')
    temporal_window_days: int = 365
    market_data_integration: bool = True
    industry_benchmarking: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClusteringResult:
    """Clustering analysis result"""
    algorithm: str
    n_clusters: int
    silhouette_score: Decimal
    cluster_labels: List[int]
    cluster_centers: List[List[Decimal]]
    cluster_sizes: List[int]
    cluster_characteristics: Dict[int, Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StatisticalAnalysis:
    """Statistical analysis result"""
    analysis_type: str
    sample_size: int
    mean: Decimal
    median: Decimal
    std_dev: Decimal
    variance: Decimal
    skewness: Decimal
    kurtosis: Decimal
    correlation_matrix: Dict[str, Dict[str, Decimal]]
    significance_tests: Dict[str, Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TemporalPattern:
    """Temporal pattern analysis"""
    pattern_id: str
    pattern_type: PatternType
    start_date: datetime
    end_date: datetime
    frequency: str
    amplitude: Decimal
    phase: Decimal
    trend_direction: str
    seasonality_strength: Decimal
    cyclicity_strength: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)


# Default configuration
DEFAULT_PATTERN_ANALYSIS_CONFIG = PatternAnalysisConfig(
    enable_clustering=True,
    enable_temporal_analysis=True,
    enable_risk_assessment=True,
    enable_opportunity_identification=True,
    clustering_algorithm="kmeans",
    min_cluster_size=3,
    max_clusters=10,
    confidence_threshold=Decimal('0.7'),
    significance_threshold=Decimal('0.05'),
    temporal_window_days=365,
    market_data_integration=True,
    industry_benchmarking=True
)

# Pattern analysis thresholds
PATTERN_THRESHOLDS = {
    "correlation_strong": Decimal('0.7'),
    "correlation_moderate": Decimal('0.5'),
    "correlation_weak": Decimal('0.3'),
    "significance_level": Decimal('0.05'),
    "confidence_high": Decimal('0.8'),
    "confidence_medium": Decimal('0.6'),
    "confidence_low": Decimal('0.4'),
    "outlier_threshold": Decimal('2.0'),  # Standard deviations
    "trend_strength_strong": Decimal('0.7'),
    "trend_strength_moderate": Decimal('0.5'),
    "trend_strength_weak": Decimal('0.3')
}

# Industry benchmark categories
INDUSTRY_CATEGORIES = {
    "technology": ["software", "hardware", "telecommunications", "internet"],
    "healthcare": ["pharmaceuticals", "medical_devices", "healthcare_services"],
    "finance": ["banking", "insurance", "investment", "fintech"],
    "manufacturing": ["automotive", "aerospace", "electronics", "machinery"],
    "retail": ["ecommerce", "brick_mortar", "fashion", "consumer_goods"],
    "energy": ["oil_gas", "renewable_energy", "utilities", "mining"],
    "real_estate": ["development", "management", "investment", "construction"]
}

# Risk categories
RISK_CATEGORIES = {
    "market": ["volatility", "liquidity", "interest_rate", "currency"],
    "industry": ["disruption", "regulation", "competition", "technology"],
    "financial": ["credit", "operational", "liquidity", "concentration"],
    "operational": ["management", "key_personnel", "supply_chain", "cybersecurity"],
    "strategic": ["market_position", "competitive_advantage", "innovation", "scalability"]
}

# Opportunity categories
OPPORTUNITY_CATEGORIES = {
    "market": ["expansion", "new_segments", "geographic", "demographic"],
    "technology": ["digital_transformation", "automation", "ai_ml", "blockchain"],
    "operational": ["efficiency", "cost_reduction", "process_improvement", "outsourcing"],
    "strategic": ["acquisition", "partnership", "diversification", "vertical_integration"],
    "financial": ["funding", "investment", "capital_structure", "working_capital"]
}
