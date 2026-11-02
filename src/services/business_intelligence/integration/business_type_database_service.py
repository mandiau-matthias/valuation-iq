"""
Business Type Database Service - Stateless Implementation

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
Business type data comes from Titan via the CalculateRequest payload.

This service provides:
- Validation of business type calibration data
- Default values when calibration is not provided
- NO database queries (all data comes from request payload)

For business type lookups, use Titan's /business-types/* endpoints.

@author UpSwitch CTO Team
@version 2.0.0 - Brain & Muscle Stateless
"""

from threading import Lock
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from decimal import Decimal

from src.utils.decimal_helpers import to_decimal, optional_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BusinessTypeConfig:
    """Business type configuration from request payload."""
    id: Optional[str] = None
    category: str = "services"
    industry: str = "services"
    dcf_preference: Decimal = Decimal('0.5')
    multiples_preference: Decimal = Decimal('0.5')
    key_metrics: List[str] = None
    owner_dependency_impact: Decimal = Decimal('0.5')
    description: str = ""
    keywords: List[str] = None
    ev_revenue_multiple: Optional[Decimal] = None
    ev_ebitda_multiple: Optional[Decimal] = None
    typical_ebitda_margin_min: Optional[Decimal] = None
    typical_ebitda_margin_max: Optional[Decimal] = None
    
    def __post_init__(self):
        if self.key_metrics is None:
            self.key_metrics = []
        if self.keywords is None:
            self.keywords = []
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "BusinessTypeConfig":
        """Create from dictionary payload."""
        if not data:
            return cls()
        
        safe_decimal = optional_decimal
        
        return cls(
            id=data.get("id") or data.get("business_type_id"),
            category=data.get("category", "services"),
            industry=data.get("industry") or data.get("industry_mapping", "services"),
            dcf_preference=safe_decimal(data.get("dcf_preference")) if data.get("dcf_preference") is not None else Decimal('0.5'),
            multiples_preference=safe_decimal(data.get("multiples_preference")) if data.get("multiples_preference") is not None else Decimal('0.5'),
            key_metrics=data.get("key_metrics") or [],
            owner_dependency_impact=safe_decimal(data.get("owner_dependency_impact")) if data.get("owner_dependency_impact") is not None else Decimal('0.5'),
            description=data.get("description", ""),
            keywords=data.get("keywords") or [],
            ev_revenue_multiple=safe_decimal(data.get("ev_revenue_multiple")),
            ev_ebitda_multiple=safe_decimal(data.get("ev_ebitda_multiple")),
            typical_ebitda_margin_min=safe_decimal(data.get("typical_ebitda_margin_min")),
            typical_ebitda_margin_max=safe_decimal(data.get("typical_ebitda_margin_max")),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "category": self.category,
            "industry": self.industry,
            "dcf_preference": float(self.dcf_preference),
            "multiples_preference": float(self.multiples_preference),
            "key_metrics": self.key_metrics,
            "owner_dependency_impact": float(self.owner_dependency_impact),
            "description": self.description,
            "keywords": self.keywords,
            "ev_revenue_multiple": float(self.ev_revenue_multiple) if self.ev_revenue_multiple is not None else None,
            "ev_ebitda_multiple": float(self.ev_ebitda_multiple) if self.ev_ebitda_multiple is not None else None,
            "typical_ebitda_margin_min": float(self.typical_ebitda_margin_min) if self.typical_ebitda_margin_min is not None else None,
            "typical_ebitda_margin_max": float(self.typical_ebitda_margin_max) if self.typical_ebitda_margin_max is not None else None,
        }


@dataclass
class MethodologySelection:
    """Methodology selection result."""
    dcf_weight: Decimal
    multiples_weight: Decimal
    confidence_score: Decimal
    business_characteristics_impact: Decimal
    owner_dependency_impact: Decimal
    market_context_impact: Decimal


class BusinessTypeDatabaseService:
    """
    Stateless Business Type Service.
    
    BRAIN & MUSCLE ARCHITECTURE:
    - All business type data comes from the request payload
    - No database queries
    - Provides validation and default fallbacks
    
    For business type lookups, use Titan's endpoints.
    """

    def __init__(self):
        """Initialize stateless service."""
        self.logger = logger
        self.logger.debug("BusinessTypeDatabaseService initialized (stateless mode)")

    def get_business_type(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> BusinessTypeConfig:
        """
        Get business type configuration from payload.
        
        Args:
            calibration_data: Business type calibration from request
            
        Returns:
            BusinessTypeConfig instance
        """
        return BusinessTypeConfig.from_dict(calibration_data)

    def select_methodology(
        self,
        calibration_data: Optional[Dict[str, Any]] = None,
        owner_dependency_score: Optional[Decimal] = None,
        market_volatility: Optional[Decimal] = None
    ) -> MethodologySelection:
        """
        Select valuation methodology based on calibration.
        
        Args:
            calibration_data: Business type calibration from request
            owner_dependency_score: Owner dependency score (0-1)
            market_volatility: Market volatility factor
            
        Returns:
            MethodologySelection with weights
        """
        config = self.get_business_type(calibration_data)
        
        # Start with base preferences
        dcf_weight = config.dcf_preference
        multiples_weight = config.multiples_preference
        
        # Adjust for owner dependency (high dependency -> prefer multiples)
        owner_impact = Decimal('0')
        if owner_dependency_score and owner_dependency_score > Decimal('0.5'):
            owner_impact = (owner_dependency_score - Decimal('0.5')) * Decimal('0.2')
            dcf_weight -= owner_impact
            multiples_weight += owner_impact
        
        # Normalize weights
        total = dcf_weight + multiples_weight
        if total > Decimal('0'):
            dcf_weight = dcf_weight / total
            multiples_weight = multiples_weight / total
        
        # Calculate confidence
        confidence = Decimal('0.75')  # Base confidence
        if calibration_data:
            confidence += Decimal('0.15')  # Higher if we have specific calibration
        
        return MethodologySelection(
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            confidence_score=confidence,
            business_characteristics_impact=config.owner_dependency_impact,
            owner_dependency_impact=owner_impact,
            market_context_impact=Decimal('0')  # TODO: Market volatility
        )

    def get_benchmarks(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get benchmarks from calibration data.
        
        Args:
            calibration_data: Business type calibration from request
            
        Returns:
            Dictionary of benchmark values
        """
        config = self.get_business_type(calibration_data)
        
        return {
            "ev_revenue_multiple": float(config.ev_revenue_multiple) if config.ev_revenue_multiple else None,
            "ev_ebitda_multiple": float(config.ev_ebitda_multiple) if config.ev_ebitda_multiple else None,
            "typical_ebitda_margin_min": float(config.typical_ebitda_margin_min) if config.typical_ebitda_margin_min else None,
            "typical_ebitda_margin_max": float(config.typical_ebitda_margin_max) if config.typical_ebitda_margin_max else None,
        }


# Default industry benchmarks (fallback when no calibration).
# EV/EBITDA multiples aligned with Step 2 IndustryBenchmarkCollector
# and BELGIAN_SME_MULTIPLES_BY_TYPE (Brookz, BDO Belgium, Vlerick).
INDUSTRY_DEFAULTS = {
    "technology": {
        "dcf_preference": Decimal("0.6"),
        "multiples_preference": Decimal("0.4"),
        "owner_dependency_impact": Decimal("0.4"),
        "ev_ebitda_multiple": Decimal("7.0"),
    },
    "hospitality": {
        "dcf_preference": Decimal("0.3"),
        "multiples_preference": Decimal("0.7"),
        "owner_dependency_impact": Decimal("0.7"),
        "ev_ebitda_multiple": Decimal("4.5"),
    },
    "retail": {
        "dcf_preference": Decimal("0.35"),
        "multiples_preference": Decimal("0.65"),
        "owner_dependency_impact": Decimal("0.5"),
        "ev_ebitda_multiple": Decimal("4.0"),
    },
    "services": {
        "dcf_preference": Decimal("0.5"),
        "multiples_preference": Decimal("0.5"),
        "owner_dependency_impact": Decimal("0.6"),
        "ev_ebitda_multiple": Decimal("5.0"),
    },
    "manufacturing": {
        "dcf_preference": Decimal("0.5"),
        "multiples_preference": Decimal("0.5"),
        "owner_dependency_impact": Decimal("0.4"),
        "ev_ebitda_multiple": Decimal("4.5"),
    },
}


def get_industry_defaults(industry: str) -> Dict[str, Any]:
    """Get default values for an industry."""
    return INDUSTRY_DEFAULTS.get(industry, INDUSTRY_DEFAULTS["services"])


_business_type_db_lock = Lock()
_business_type_database_service: Optional[BusinessTypeDatabaseService] = None


def get_business_type_database_service() -> BusinessTypeDatabaseService:
    """Factory function to get a BusinessTypeDatabaseService instance.

    Uses double-checked locking consistent with other ValuationIQ singletons
    (``MainReportDataAggregator``, ``TemplateService``).
    """
    global _business_type_database_service
    if _business_type_database_service is None:
        with _business_type_db_lock:
            if _business_type_database_service is None:
                _business_type_database_service = BusinessTypeDatabaseService()
    return _business_type_database_service
