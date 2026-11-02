"""
Orchestrator Types and Data Structures — DEPRECATED / LEGACY

.. deprecated::
    These types belong to the legacy ``services/core/orchestration/``
    stack.  The production pipeline's types live in
    ``src.domain.hybrid_types`` (weights), ``src.api.schemas.stateless_api``
    (method results), and ``src.domain.valuation_contract`` (canonical
    contract).  Do NOT add new types here.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import InitVar, dataclass, field
from enum import Enum
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class ValuationMethodology(str, Enum):
    """Valuation methodology types"""
    DCF = "dcf"
    MULTIPLES = "multiples"
    ASSET_BASED = "asset_based"
    HYBRID = "hybrid"
    QUICK_MULTIPLES = "quick_multiples"


class ProcessingStatus(str, Enum):
    """Processing status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PrivacyMode(str, Enum):
    """Privacy protection modes"""
    STRICT = "strict"
    BALANCED = "balanced"
    PERMISSIVE = "permissive"


@dataclass
class ValuationConfig:
    """Configuration for valuation processing"""
    enable_dcf: bool = True
    enable_multiples: bool = True
    enable_market_context: bool = True
    enable_ai_insights: InitVar[Optional[bool]] = None
    enable_owner_profiling: bool = True
    enable_business_intelligence: bool = True
    privacy_mode: PrivacyMode = PrivacyMode.STRICT
    data_quality_threshold: Decimal = Decimal('0.7')
    confidence_threshold: Decimal = Decimal('0.8')
    parallel_processing: bool = True
    timeout_seconds: int = 300

    def __post_init__(self, enable_ai_insights: Optional[bool]) -> None:
        if enable_ai_insights is not None:
            self.enable_market_context = True

    @property
    def enable_ai_insights(self) -> bool:
        """Legacy flag retained for callers; direct AI orchestration is retired."""
        return False

    @enable_ai_insights.setter
    def enable_ai_insights(self, _value: bool) -> None:
        """Ignore legacy attempts to enable direct AI orchestration."""
        self.enable_market_context = True


@dataclass
class ValuationContext:
    """Context for valuation processing"""
    request_id: str
    company_name: str
    industry: str
    country_code: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingMetrics:
    """Metrics for valuation processing"""
    start_time: datetime
    end_time: Optional[datetime] = None
    processing_time: Decimal = Decimal('0.0')
    data_preparation_time: Decimal = Decimal('0.0')
    valuation_calculation_time: Decimal = Decimal('0.0')
    market_context_time: Decimal = Decimal('0.0')
    ai_insights_time: InitVar[Optional[Decimal]] = None
    synthesis_time: Decimal = Decimal('0.0')
    total_api_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    def __post_init__(self, ai_insights_time: Optional[Decimal]) -> None:
        if ai_insights_time is not None:
            self.market_context_time = ai_insights_time

    def calculate_processing_time(self):
        """Calculate total processing time"""
        if self.end_time and self.start_time:
            self.processing_time = (self.end_time - self.start_time).total_seconds()

    @property
    def ai_insights_time(self) -> Decimal:
        """Legacy alias for deterministic market context timing."""
        return self.market_context_time

    @ai_insights_time.setter
    def ai_insights_time(self, value: Decimal) -> None:
        self.market_context_time = value


@dataclass
class ValuationResult:
    """Complete valuation result"""
    equity_value: Decimal
    enterprise_value: Decimal
    valuation_methodology: str
    confidence_score: Decimal
    value_drivers: List[str]
    risk_factors: List[str]
    sensitivity_analysis: Dict[str, Any]
    market_comparables: List[Dict[str, Any]]
    financial_metrics: Dict[str, Any]
    market_context: Optional[Dict[str, Any]] = None
    ai_insights: InitVar[Optional[Dict[str, Any]]] = None
    owner_profile: Optional[Dict[str, Any]] = None
    business_intelligence: Optional[Dict[str, Any]] = None
    processing_metrics: Optional[ProcessingMetrics] = None
    audit_trail: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self, ai_insights: Optional[Dict[str, Any]]) -> None:
        if ai_insights is not None:
            self.market_context = ai_insights

    @property
    def ai_insights(self) -> Optional[Dict[str, Any]]:
        """Legacy alias for deterministic market context."""
        return self.market_context

    @ai_insights.setter
    def ai_insights(self, value: Optional[Dict[str, Any]]) -> None:
        self.market_context = value


@dataclass
class MarketData:
    """Market data for valuation"""
    risk_free_rate: Decimal
    market_risk_premium: Decimal
    gdp_growth: Decimal
    inflation_rate: Decimal
    industry_multiples: Dict[str, Decimal]
    comparable_companies: List[Dict[str, Any]] = field(default_factory=list)
    market_conditions: str = "normal"


@dataclass
class SecurityContext:
    """Security context for valuation processing"""
    user_id: str
    permissions: List[str]
    access_level: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class AuditTrail:
    """Audit trail for valuation processing"""
    request_id: str
    timestamp: datetime
    user_id: Optional[str]
    action: str
    result: str
    processing_time: Decimal
    data_sources: List[str]
    methodologies_used: List[str]
    confidence_score: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceDependency:
    """Service dependency definition"""
    service_name: str
    required: bool
    timeout_seconds: int
    retry_count: int = 3
    fallback_available: bool = False


@dataclass
class WorkflowStep:
    """Workflow step definition"""
    step_id: str
    step_name: str
    dependencies: List[str]
    timeout_seconds: int
    retryable: bool = True
    critical: bool = True
    status: ProcessingStatus = ProcessingStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class AggregationWeights:
    """Weights for result aggregation"""
    dcf_weight: Decimal = Decimal('0.6')
    multiples_weight: Decimal = Decimal('0.4')
    confidence_adjustment: Decimal = Decimal('1.0')
    quality_threshold: Decimal = Decimal('0.7')


@dataclass
class ValuationInsights:
    """Insights from valuation analysis"""
    key_findings: List[str]
    recommendations: List[str]
    market_position: str
    growth_potential: str
    risk_assessment: str
    confidence_factors: List[str]
    data_quality_score: Decimal


# Default configurations
DEFAULT_VALUATION_CONFIG = ValuationConfig(
    enable_dcf=True,
    enable_multiples=True,
    enable_market_context=True,
    enable_owner_profiling=True,
    enable_business_intelligence=True,
    privacy_mode=PrivacyMode.STRICT,
    data_quality_threshold=Decimal('0.7'),
    confidence_threshold=Decimal('0.8'),
    parallel_processing=True,
    timeout_seconds=300
)

DEFAULT_AGGREGATION_WEIGHTS = AggregationWeights(
    dcf_weight=Decimal('0.6'),
    multiples_weight=Decimal('0.4'),
    confidence_adjustment=Decimal('1.0'),
    quality_threshold=Decimal('0.7')
)

# Service dependencies
SERVICE_DEPENDENCIES = [
    ServiceDependency(
        service_name="privacy_guard",
        required=True,
        timeout_seconds=30,
        retry_count=2,
        fallback_available=False
    ),
    ServiceDependency(
        service_name="market_context",
        required=False,
        timeout_seconds=60,
        retry_count=3,
        fallback_available=True
    ),
    ServiceDependency(
        service_name="mcp_service",
        required=False,
        timeout_seconds=45,
        retry_count=2,
        fallback_available=True
    ),
    ServiceDependency(
        service_name="owner_profiling",
        required=False,
        timeout_seconds=30,
        retry_count=2,
        fallback_available=True
    ),
    ServiceDependency(
        service_name="business_intelligence",
        required=False,
        timeout_seconds=30,
        retry_count=2,
        fallback_available=True
    )
]
