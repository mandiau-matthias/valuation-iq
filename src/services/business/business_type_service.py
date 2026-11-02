"""
Business Type Service - Stateless Implementation — DEPRECATED

.. deprecated::
    The production valuation pipeline uses
    ``src.services.business_intelligence.business_type_multiples_adapter``
    (DB-backed via ``BusinessTypesRepository``) for business-type
    calibration, not this stateless service.  The authoritative Pydantic
    schema is ``src.api.schemas.stateless_api.BusinessTypeCalibration``.

    This module has no production callers and is kept for backward
    compatibility only.  Do NOT add new features here.

Original description:
  ValuationIQ (The Muscle) is a stateless calculation engine.
  Business type data comes from Titan via the CalculateRequest payload.
"""

from typing import List, Optional, Dict, Any, Tuple
from functools import lru_cache
from decimal import Decimal

from src.utils.logging import get_logger

logger = get_logger(__name__)


class BusinessTypeCalibration:
    """
    Business type calibration data from Titan.
    
    All data is passed via the stateless API request payload.
    No database queries are performed.
    """
    
    def __init__(
        self,
        business_type_id: Optional[str] = None,
        title: Optional[str] = None,
        dcf_preference: Optional[Decimal] = None,
        multiples_preference: Optional[Decimal] = None,
        industry_mapping: Optional[str] = None,
        owner_dependency_impact: Optional[Decimal] = None,
        key_metrics: Optional[List[str]] = None,
        sector: Optional[str] = None,
        ev_revenue_multiple: Optional[Decimal] = None,
        ev_ebitda_multiple: Optional[Decimal] = None,
        typical_ebitda_margin_min: Optional[Decimal] = None,
        typical_ebitda_margin_max: Optional[Decimal] = None,
        revenue_growth_benchmark: Optional[Decimal] = None,
    ):
        self.id = business_type_id
        self.title = title or "General Business"
        self.dcf_preference = dcf_preference if dcf_preference is not None else Decimal('0.5')
        self.multiples_preference = multiples_preference if multiples_preference is not None else Decimal('0.5')
        self.industry_mapping = industry_mapping or "services"
        self.owner_dependency_impact = owner_dependency_impact if owner_dependency_impact is not None else Decimal('0.5')
        self.key_metrics = key_metrics or []
        self.sector = sector
        self.ev_revenue_multiple = ev_revenue_multiple
        self.ev_ebitda_multiple = ev_ebitda_multiple
        self.typical_ebitda_margin_min = typical_ebitda_margin_min
        self.typical_ebitda_margin_max = typical_ebitda_margin_max
        self.revenue_growth_benchmark = revenue_growth_benchmark
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "BusinessTypeCalibration":
        """
        Create BusinessTypeCalibration from dictionary payload.
        
        Args:
            data: Dictionary from request payload, or None for defaults
            
        Returns:
            BusinessTypeCalibration instance
        """
        if not data:
            logger.debug("No calibration data provided, using defaults")
            return cls()
        
        def to_decimal(value: Any) -> Optional[Decimal]:
            if value is None:
                return None
            try:
                return Decimal(str(value))
            except Exception:
                return None
        
        return cls(
            business_type_id=data.get("business_type_id") or data.get("id"),
            title=data.get("title"),
            dcf_preference=to_decimal(data.get("dcf_preference")),
            multiples_preference=to_decimal(data.get("multiples_preference")),
            industry_mapping=data.get("industry_mapping") or data.get("industry"),
            owner_dependency_impact=to_decimal(data.get("owner_dependency_impact")),
            key_metrics=data.get("key_metrics") or data.get("keyMetrics") or [],
            sector=data.get("sector"),
            ev_revenue_multiple=to_decimal(data.get("ev_revenue_multiple")),
            ev_ebitda_multiple=to_decimal(data.get("ev_ebitda_multiple")),
            typical_ebitda_margin_min=to_decimal(data.get("typical_ebitda_margin_min")),
            typical_ebitda_margin_max=to_decimal(data.get("typical_ebitda_margin_max")),
            revenue_growth_benchmark=to_decimal(data.get("revenue_growth_benchmark")),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "dcf_preference": float(self.dcf_preference),
            "multiples_preference": float(self.multiples_preference),
            "industry_mapping": self.industry_mapping,
            "owner_dependency_impact": float(self.owner_dependency_impact),
            "key_metrics": self.key_metrics,
            "sector": self.sector,
            "ev_revenue_multiple": float(self.ev_revenue_multiple) if self.ev_revenue_multiple is not None else None,
            "ev_ebitda_multiple": float(self.ev_ebitda_multiple) if self.ev_ebitda_multiple is not None else None,
            "typical_ebitda_margin_min": float(self.typical_ebitda_margin_min) if self.typical_ebitda_margin_min is not None else None,
            "typical_ebitda_margin_max": float(self.typical_ebitda_margin_max) if self.typical_ebitda_margin_max is not None else None,
            "revenue_growth_benchmark": float(self.revenue_growth_benchmark) if self.revenue_growth_benchmark else None,
        }


class BusinessTypeService:
    """
    Stateless Business Type Service.
    
    BRAIN & MUSCLE ARCHITECTURE:
    - All business type data comes from the request payload
    - No database queries
    - Provides validation and default fallbacks
    """
    
    def __init__(self):
        """Initialize stateless business type service."""
        logger.info("BusinessTypeService initialized (stateless mode)")
    
    def get_calibration(self, calibration_data: Optional[Dict[str, Any]]) -> BusinessTypeCalibration:
        """
        Get calibration from request payload or return defaults.
        
        Args:
            calibration_data: Business type calibration from request payload
            
        Returns:
            BusinessTypeCalibration instance
        """
        return BusinessTypeCalibration.from_dict(calibration_data)
    
    def validate_calibration(self, calibration: BusinessTypeCalibration) -> List[str]:
        """
        Validate calibration data and return any warnings.
        
        Args:
            calibration: BusinessTypeCalibration to validate
            
        Returns:
            List of warning messages (empty if valid)
        """
        warnings = []
        
        # Check for unusual preference values
        total_preference = calibration.dcf_preference + calibration.multiples_preference
        if abs(total_preference - Decimal('1.0')) > Decimal('0.01'):
            warnings.append(
                f"DCF + Multiples preference ({total_preference}) should sum to 1.0"
            )
        
        # Check owner dependency impact
        if calibration.owner_dependency_impact < Decimal('0') or calibration.owner_dependency_impact > Decimal('1'):
            warnings.append(
                f"Owner dependency impact ({calibration.owner_dependency_impact}) should be between 0 and 1"
            )
        
        return warnings
    
    def get_question_fields(self, calibration: BusinessTypeCalibration) -> List[str]:
        """
        Get question fields from calibration data.
        
        Args:
            calibration: BusinessTypeCalibration with key_metrics
            
        Returns:
            List of field names to collect
        """
        if calibration.key_metrics:
            return calibration.key_metrics
        
        # Fallback based on industry
        return get_fallback_fields(calibration.industry_mapping or "services")


@lru_cache(maxsize=50)
def get_fallback_fields(industry: str) -> Tuple[str, ...]:
    """Return default metric fields for *industry* as an immutable tuple.

    Cached via ``@lru_cache``; returning a tuple guarantees callers cannot
    corrupt the cache by mutating the result.
    """
    fallback_map = {
        "hospitality": ("daily_transactions", "average_ticket_size", "seating_capacity"),
        "technology": ("mrr", "arr", "churn_rate", "cac", "ltv"),
        "retail": ("inventory_turnover", "average_order_value", "foot_traffic"),
        "manufacturing": ("production_capacity", "equipment_age", "utilization_rate"),
        "professional_services": ("billable_hours", "hourly_rate", "client_retention"),
        "healthcare": ("patient_volume", "average_revenue_per_patient", "payer_mix"),
    }
    
    return fallback_map.get(industry, ("revenue", "ebitda", "employees"))


# Industry defaults for when no calibration is provided
DEFAULT_INDUSTRY_CALIBRATIONS = {
    "services": BusinessTypeCalibration(
        industry_mapping="services",
        dcf_preference=Decimal("0.4"),
        multiples_preference=Decimal("0.6"),
        owner_dependency_impact=Decimal("0.6"),
    ),
    "technology": BusinessTypeCalibration(
        industry_mapping="technology",
        dcf_preference=Decimal("0.6"),
        multiples_preference=Decimal("0.4"),
        owner_dependency_impact=Decimal("0.4"),
    ),
    "hospitality": BusinessTypeCalibration(
        industry_mapping="hospitality",
        dcf_preference=Decimal("0.3"),
        multiples_preference=Decimal("0.7"),
        owner_dependency_impact=Decimal("0.7"),
    ),
    "retail": BusinessTypeCalibration(
        industry_mapping="retail",
        dcf_preference=Decimal("0.35"),
        multiples_preference=Decimal("0.65"),
        owner_dependency_impact=Decimal("0.5"),
    ),
    "manufacturing": BusinessTypeCalibration(
        industry_mapping="manufacturing",
        dcf_preference=Decimal("0.5"),
        multiples_preference=Decimal("0.5"),
        owner_dependency_impact=Decimal("0.4"),
    ),
}


def get_industry_defaults(industry: str) -> BusinessTypeCalibration:
    """
    Get default calibration for an industry.
    
    Args:
        industry: Industry code
        
    Returns:
        Default BusinessTypeCalibration for the industry
    """
    return DEFAULT_INDUSTRY_CALIBRATIONS.get(
        industry,
        DEFAULT_INDUSTRY_CALIBRATIONS["services"]
    )
