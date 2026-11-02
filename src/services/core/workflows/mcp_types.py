"""
MCP Service Types

This module defines shared data structures and enums for the Valuation MCP Service refactoring.
"""

from dataclasses import InitVar, dataclass
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class MCPStatus(Enum):
    """MCP service status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PROCESSING = "processing"


class DataQualityLevel(Enum):
    """Data quality levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ValuationCategory(Enum):
    """Valuation size categories"""
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class GrowthCategory(Enum):
    """Growth rate categories"""
    DECLINING = "declining"
    STABLE = "stable"
    GROWING = "growing"
    HIGH_GROWTH = "high_growth"


class TrendDirection(Enum):
    """Trend direction indicators"""
    STRONGLY_INCREASING = "strongly_increasing"
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    STRONGLY_DECREASING = "strongly_decreasing"


class InsightType(Enum):
    """Insight type indicators"""
    PATTERN = "pattern"
    TREND = "trend"
    RISK = "risk"
    OPPORTUNITY = "opportunity"
    RECOMMENDATION = "recommendation"


class ConfidenceLevel(Enum):
    """Confidence level indicators"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass
class ValuationRecord:
    """Individual valuation record"""
    id: str
    company_name: str
    industry: str
    country_code: str
    revenue: Decimal
    ebitda: Decimal
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    confidence_score: Decimal
    total_assets: Optional[Decimal] = None
    total_debt: Optional[Decimal] = None
    cash: Optional[Decimal] = None
    employees: Optional[int] = None
    valuation_method: str = "synthesized"
    created_at: Optional[datetime] = None
    revenue_growth_rate: Optional[Decimal] = None


@dataclass
class ProcessedValuationRecord(ValuationRecord):
    """Valuation record with processed features"""
    revenue_multiple: Optional[Decimal] = None
    ebitda_multiple: Optional[Decimal] = None
    ebitda_margin: Optional[Decimal] = None
    debt_to_equity: Optional[Decimal] = None
    valuation_category: Optional[ValuationCategory] = None
    growth_category: Optional[GrowthCategory] = None
    data_quality_score: int = 0
    is_premium_exit: bool = False
    industry_performance_rank: Optional[Decimal] = None
    year: Optional[int] = None
    quarter: Optional[int] = None
    month: Optional[int] = None


@dataclass
class IndustryPattern:
    """Industry-specific valuation patterns"""
    industry: str
    median_revenue_multiple: Decimal
    mean_revenue_multiple: Decimal
    std_revenue_multiple: Decimal
    sample_size: int
    median_ebitda_multiple: Decimal
    median_ebitda_margin: Decimal
    premium_exits: int


@dataclass
class SeasonalPattern:
    """Seasonal valuation patterns"""
    quarter: str
    avg_multiple: Decimal
    premium_vs_annual: Decimal
    avg_confidence: Decimal


@dataclass
class ValuationBenchmark:
    """Valuation benchmarks by size category"""
    category: str
    median_revenue_multiple: Decimal
    median_ebitda_multiple: Decimal
    avg_confidence: Decimal
    sample_size: int


@dataclass
class QualityInsight:
    """Data quality insights"""
    high_quality_count: int
    medium_quality_count: int
    low_quality_count: int
    avg_confidence: Decimal
    completeness_score: Decimal


@dataclass
class MCPInsights:
    """Complete MCP analysis insights"""
    data_summary: Dict[str, Any]
    industry_patterns: Dict[str, IndustryPattern]
    seasonal_patterns: Dict[str, SeasonalPattern]
    valuation_benchmarks: Dict[str, ValuationBenchmark]
    quality_insights: QualityInsight
    trend_analysis: Dict[str, Any]


@dataclass
class AIContext:
    """Legacy context shape for deterministic analysis."""
    data_summary: Dict[str, Any]
    current_valuation: Optional[Dict[str, Any]]
    industry_patterns: Dict[str, Any]
    seasonal_patterns: Dict[str, Any]
    formatted_context: str


@dataclass
class MCPResult:
    """Complete MCP pipeline result"""
    status: MCPStatus
    execution_time_seconds: Decimal
    records_analyzed: int
    patterns: MCPInsights
    timestamp: datetime
    market_insights: str = ""
    ai_insights: InitVar[Optional[str]] = None
    error_message: Optional[str] = None

    def __post_init__(self, ai_insights: Optional[str]) -> None:
        if ai_insights is not None:
            self.market_insights = ai_insights

    @property
    def ai_insights(self) -> str:
        """Legacy alias for deterministic market notes."""
        return self.market_insights


@dataclass
class MCPConfiguration:
    """MCP service configuration"""
    enable_mcp: bool = True
    cache_ttl: int = 3600 * 24  # 24 hours
    max_records: int = 1000
    min_confidence_score: Decimal = Decimal('50.0')
    ai_model: str = "titan-owned"
    max_tokens: int = 1500
    temperature: Decimal = Decimal('0.3')


# Default configuration
DEFAULT_MCP_CONFIG = MCPConfiguration()

# Sample data configuration
SAMPLE_INDUSTRIES = ['saas', 'ecommerce', 'hospitality', 'manufacturing', 'consulting']
SAMPLE_COUNTRIES = ['BE', 'NL', 'DE', 'FR', 'LU']

# Industry-specific characteristics for sample data
INDUSTRY_CHARACTERISTICS = {
    'saas': {
        'base_multiple': Decimal('5.0'),
        'margin': Decimal('0.75'),
        'growth_rate_range': (Decimal('0.1'), Decimal('0.8'))
    },
    'ecommerce': {
        'base_multiple': Decimal('2.5'),
        'margin': Decimal('0.15'),
        'growth_rate_range': (Decimal('0.0'), Decimal('0.4'))
    },
    'hospitality': {
        'base_multiple': Decimal('2.0'),
        'margin': Decimal('0.25'),
        'growth_rate_range': (-Decimal('0.1'), Decimal('0.3'))
    },
    'manufacturing': {
        'base_multiple': Decimal('3.5'),
        'margin': Decimal('0.30'),
        'growth_rate_range': (Decimal('0.0'), Decimal('0.2'))
    },
    'consulting': {
        'base_multiple': Decimal('3.0'),
        'margin': Decimal('0.40'),
        'growth_rate_range': (Decimal('0.0'), Decimal('0.3'))
    }
}

# Valuation size thresholds
VALUATION_THRESHOLDS = {
    'micro': 500000,
    'small': 2000000,
    'medium': 10000000,
    'large': Decimal('Infinity')  # Use Decimal('Infinity') instead of to_decimal('inf')
}

# Growth rate thresholds
GROWTH_THRESHOLDS = {
    'declining': Decimal('-Infinity'),  # Use Decimal('-Infinity') instead of -to_decimal('inf')
    'stable': Decimal('0.0'),
    'growing': Decimal('0.1'),
    'high_growth': Decimal('0.3')
}

# Quality scoring weights
QUALITY_WEIGHTS = {
    'confidence_high': 30,  # >= 80%
    'confidence_medium': 20,  # >= 70%
    'assets_available': 20,
    'employees_available': 10,
    'financial_completeness': 20
}

# Additional types for compatibility
@dataclass
class ValuationData:
    """Valuation data structure for compatibility"""
    id: str
    company_name: str
    industry: str
    country_code: str
    revenue: Decimal
    ebitda: Decimal
    equity_value_mid: Decimal
    confidence_score: Decimal
    created_at: datetime


@dataclass
class DataSource:
    """Data source information"""
    name: str
    url: str
    type: str
    status: str


class ProcessingStatus(Enum):
    """Processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DataIngestionConfig:
    """Data ingestion configuration"""
    max_records: int = 1000
    min_confidence_score: Decimal = Decimal('50.0')
    cache_ttl: int = 3600
    timeout_seconds: int = 30


# Default configuration
DEFAULT_DATA_INGESTION_CONFIG = DataIngestionConfig()

# Additional types for feature engineering
@dataclass
class FeatureEngineeringConfig:
    """Feature engineering configuration"""
    enable_ratios: bool = True
    enable_categories: bool = True
    enable_time_features: bool = True
    enable_quality_scoring: bool = True


@dataclass
class FeatureEngineeringResult:
    """Feature engineering result"""
    processed_data: Any
    features_added: List[str]
    processing_time: Decimal
    status: str


# Default feature engineering configuration
DEFAULT_FEATURE_ENGINEERING_CONFIG = FeatureEngineeringConfig()

# Additional types for pattern analysis
@dataclass
class PatternInsight:
    """Pattern insight result"""
    pattern_type: str
    confidence: Decimal
    description: str
    impact: str


@dataclass
class PatternAnalysisResult:
    """Pattern analysis result"""
    insights: List[PatternInsight]
    patterns_found: int
    analysis_time: Decimal
    status: str


# Default pattern analysis configuration
DEFAULT_PATTERN_ANALYSIS_CONFIG = {
    "min_confidence": Decimal('0.7'),
    "max_patterns": 100,
    "timeout_seconds": 30
}

# Additional types for market analysis
@dataclass
class MarketTrend:
    """Market trend information"""
    trend_type: str
    direction: str
    strength: Decimal
    duration: str
    impact: str


@dataclass
class IndustryAnalysis:
    """Industry analysis result"""
    industry: str
    growth_rate: Decimal
    market_size: Decimal
    competition_level: str
    trends: List[MarketTrend]


@dataclass
class RiskAssessment:
    """Risk assessment result"""
    risk_level: str
    risk_factors: List[str]
    mitigation_strategies: List[str]
    confidence: Decimal


@dataclass
class Opportunity:
    """Business opportunity"""
    opportunity_type: str
    description: str
    potential_value: Decimal
    probability: Decimal
    timeline: str


@dataclass
class StrategicRecommendation:
    """Strategic recommendation"""
    recommendation_type: str
    description: str
    priority: str
    expected_impact: str
    implementation_steps: List[str]


@dataclass
class MCPInsight:
    """MCP insight result"""
    insight_type: str
    confidence: Decimal
    description: str
    impact: str
    recommendations: List[str]


@dataclass
class PatternAnalysisConfig:
    """Pattern analysis configuration"""
    min_confidence: Decimal = Decimal('0.7')
    max_patterns: int = 100
    timeout_seconds: int = 30
    enable_trend_analysis: bool = True
    enable_risk_assessment: bool = True


@dataclass
class AIEnhancementConfig:
    """Legacy narrative configuration; Titan owns AI provider settings."""
    model: str = "titan-owned"
    max_tokens: int = 1500
    temperature: Decimal = Decimal('0.3')
    timeout_seconds: int = 30
    enable_fallback: bool = True


# Default legacy narrative configuration
DEFAULT_AI_ENHANCEMENT_CONFIG = AIEnhancementConfig()


@dataclass
class ProcessingMetrics:
    """Processing metrics"""
    total_records: int
    processed_records: int
    failed_records: int
    processing_time: Decimal
    success_rate: Decimal
    error_rate: Decimal
