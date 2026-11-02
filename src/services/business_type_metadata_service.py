"""
Business Type Metadata Service - Stateless Implementation

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
Business type metadata comes from Titan via the CalculateRequest payload.

This service provides:
- Parsing and validation of metadata from request payloads
- Default values based on industry when metadata is not provided
- NO database queries (all data comes from request payload)

For business type lookups, use Titan's /business-types/* endpoints.

@author UpSwitch CTO Team
@version 2.0.0 - Brain & Muscle Stateless
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from decimal import Decimal
from threading import Lock

from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, optional_decimal

logger = get_logger(__name__)


@dataclass
class BusinessTypeMetadata:
    """Business type metadata from request payload."""
    id: Optional[str] = None
    title: str = "General Business"
    short_title: Optional[str] = None
    description: str = ""
    sector: str = "services"
    industry: str = "services"
    sub_industry: Optional[str] = None
    primary_model: str = "standard"
    secondary_models: List[str] = None
    revenue_streams: List[str] = None
    typical_revenue_min: Optional[Decimal] = None
    typical_revenue_max: Optional[Decimal] = None
    typical_revenue_median: Optional[Decimal] = None
    typical_ebitda_margin_min: Optional[Decimal] = None
    typical_ebitda_margin_max: Optional[Decimal] = None
    typical_ebitda_margin_median: Optional[Decimal] = None
    dcf_preference: Decimal = Decimal('0.5')
    multiples_preference: Decimal = Decimal('0.5')
    preferred_multiples: List[str] = None
    owner_dependency_impact: Decimal = Decimal('0.5')
    risk_factors: List[str] = None
    key_metrics: List[str] = None
    market_context_matrix: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.secondary_models is None:
            self.secondary_models = []
        if self.revenue_streams is None:
            self.revenue_streams = []
        if self.preferred_multiples is None:
            self.preferred_multiples = ["EV/EBITDA"]
        if self.risk_factors is None:
            self.risk_factors = []
        if self.key_metrics is None:
            self.key_metrics = []
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "BusinessTypeMetadata":
        """Create from dictionary payload."""
        if not data:
            return cls()
        
        safe_decimal = optional_decimal
        
        return cls(
            id=data.get("id") or data.get("business_type_id"),
            title=data.get("title", "General Business"),
            short_title=data.get("short_title"),
            description=data.get("description", ""),
            sector=data.get("sector", "services"),
            industry=data.get("industry") or data.get("industry_mapping", "services"),
            sub_industry=data.get("sub_industry"),
            primary_model=data.get("primary_model", "standard"),
            secondary_models=data.get("secondary_models") or [],
            revenue_streams=data.get("revenue_streams") or [],
            typical_revenue_min=safe_decimal(data.get("typical_revenue_min")),
            typical_revenue_max=safe_decimal(data.get("typical_revenue_max")),
            typical_revenue_median=safe_decimal(data.get("typical_revenue_median")),
            typical_ebitda_margin_min=safe_decimal(data.get("typical_ebitda_margin_min")),
            typical_ebitda_margin_max=safe_decimal(data.get("typical_ebitda_margin_max")),
            typical_ebitda_margin_median=safe_decimal(data.get("typical_ebitda_margin_median")),
            dcf_preference=safe_decimal(data.get("dcf_preference")) if data.get("dcf_preference") is not None else Decimal('0.5'),
            multiples_preference=safe_decimal(data.get("multiples_preference")) if data.get("multiples_preference") is not None else Decimal('0.5'),
            preferred_multiples=data.get("preferred_multiples") or ["EV/EBITDA"],
            owner_dependency_impact=safe_decimal(data.get("owner_dependency_impact")) if data.get("owner_dependency_impact") is not None else Decimal('0.5'),
            risk_factors=data.get("risk_factors") or [],
            key_metrics=data.get("key_metrics") or [],
            market_context_matrix=data.get("market_context_matrix") or None,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "short_title": self.short_title,
            "description": self.description,
            "sector": self.sector,
            "industry": self.industry,
            "sub_industry": self.sub_industry,
            "primary_model": self.primary_model,
            "secondary_models": self.secondary_models,
            "revenue_streams": self.revenue_streams,
            "typical_revenue_min": float(self.typical_revenue_min) if self.typical_revenue_min else None,
            "typical_revenue_max": float(self.typical_revenue_max) if self.typical_revenue_max else None,
            "typical_revenue_median": float(self.typical_revenue_median) if self.typical_revenue_median else None,
            "typical_ebitda_margin_min": float(self.typical_ebitda_margin_min) if self.typical_ebitda_margin_min is not None else None,
            "typical_ebitda_margin_max": float(self.typical_ebitda_margin_max) if self.typical_ebitda_margin_max is not None else None,
            "typical_ebitda_margin_median": float(self.typical_ebitda_margin_median) if self.typical_ebitda_margin_median is not None else None,
            "dcf_preference": float(self.dcf_preference),
            "multiples_preference": float(self.multiples_preference),
            "preferred_multiples": self.preferred_multiples,
            "owner_dependency_impact": float(self.owner_dependency_impact),
            "risk_factors": self.risk_factors,
            "key_metrics": self.key_metrics,
            "market_context_matrix": self.market_context_matrix,
        }


class BusinessTypeMetadataService:
    """
    Stateless Business Type Metadata Service.
    
    BRAIN & MUSCLE ARCHITECTURE:
    - All metadata comes from the request payload
    - No database queries
    - Provides validation and default fallbacks
    
    For business type lookups, use Titan's endpoints.
    """

    def __init__(self):
        """Initialize stateless service."""
        self.logger = logger
        self.logger.debug("BusinessTypeMetadataService initialized (stateless mode)")

    def get_metadata(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> BusinessTypeMetadata:
        """
        Get metadata from request payload.

        Args:
            calibration_data: Business type calibration from request.
                If a non-dict (e.g. legacy business_type_id string) is passed,
                returns default metadata (stateless mode has no ID lookup).

        Returns:
            BusinessTypeMetadata instance
        """
        if not isinstance(calibration_data, dict):
            return BusinessTypeMetadata.from_dict(None)
        return BusinessTypeMetadata.from_dict(calibration_data)

    def get_dcf_preference(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> Decimal:
        """Get DCF methodology preference (0-1)."""
        metadata = self.get_metadata(calibration_data)
        return metadata.dcf_preference

    def get_multiples_preference(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> Decimal:
        """Get multiples methodology preference (0-1)."""
        metadata = self.get_metadata(calibration_data)
        return metadata.multiples_preference

    def get_owner_dependency_impact(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> Decimal:
        """Get owner dependency impact factor (0-1)."""
        metadata = self.get_metadata(calibration_data)
        return metadata.owner_dependency_impact

    def get_ebitda_margin_benchmarks(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Optional[float]]:
        """Get EBITDA margin benchmarks for the business type."""
        metadata = self.get_metadata(calibration_data)
        return {
            "min": float(metadata.typical_ebitda_margin_min) if metadata.typical_ebitda_margin_min else None,
            "max": float(metadata.typical_ebitda_margin_max) if metadata.typical_ebitda_margin_max else None,
            "median": float(metadata.typical_ebitda_margin_median) if metadata.typical_ebitda_margin_median else None,
        }

    def get_key_metrics(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Get key metrics for the business type."""
        metadata = self.get_metadata(calibration_data)
        return metadata.key_metrics or []

    def get_preferred_multiples(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Get preferred valuation multiples for the business type."""
        metadata = self.get_metadata(calibration_data)
        return metadata.preferred_multiples or ["EV/EBITDA"]

    def get_risk_factors(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Get risk factors for the business type."""
        metadata = self.get_metadata(calibration_data)
        return metadata.risk_factors or []

    def get_business_type_metadata(
        self,
        calibration_data: Optional[Dict[str, Any]] = None
    ) -> Optional[BusinessTypeMetadata]:
        """
        Get full BusinessTypeMetadata object.

        Accepts a calibration dict (from request payload) or a bare
        business_type_id string (legacy callers). Non-dict values
        return default metadata.
        """
        return self.get_metadata(calibration_data)


# Industry default metadata (fallback when no calibration)
INDUSTRY_DEFAULT_METADATA = {
    "technology": BusinessTypeMetadata(
        industry="technology",
        sector="technology",
        dcf_preference=Decimal("0.6"),
        multiples_preference=Decimal("0.4"),
        owner_dependency_impact=Decimal("0.4"),
        preferred_multiples=["EV/Revenue", "EV/EBITDA"],
        typical_ebitda_margin_min=Decimal("0.15"),
        typical_ebitda_margin_max=Decimal("0.35"),
    ),
    "hospitality": BusinessTypeMetadata(
        industry="hospitality",
        sector="hospitality",
        dcf_preference=Decimal("0.3"),
        multiples_preference=Decimal("0.7"),
        owner_dependency_impact=Decimal("0.7"),
        preferred_multiples=["EV/EBITDA"],
        typical_ebitda_margin_min=Decimal("0.10"),
        typical_ebitda_margin_max=Decimal("0.20"),
    ),
    "retail": BusinessTypeMetadata(
        industry="retail",
        sector="retail",
        dcf_preference=Decimal("0.35"),
        multiples_preference=Decimal("0.65"),
        owner_dependency_impact=Decimal("0.5"),
        preferred_multiples=["EV/EBITDA", "P/E"],
        typical_ebitda_margin_min=Decimal("0.05"),
        typical_ebitda_margin_max=Decimal("0.15"),
    ),
    "services": BusinessTypeMetadata(
        industry="services",
        sector="services",
        dcf_preference=Decimal("0.5"),
        multiples_preference=Decimal("0.5"),
        owner_dependency_impact=Decimal("0.6"),
        preferred_multiples=["EV/EBITDA"],
        typical_ebitda_margin_min=Decimal("0.10"),
        typical_ebitda_margin_max=Decimal("0.25"),
    ),
}


def get_industry_default_metadata(industry: str) -> BusinessTypeMetadata:
    """Get default metadata for an industry."""
    return INDUSTRY_DEFAULT_METADATA.get(industry, INDUSTRY_DEFAULT_METADATA["services"])


_business_type_metadata_service: Optional[BusinessTypeMetadataService] = None
_business_type_metadata_service_lock = Lock()


def get_business_type_metadata_service() -> BusinessTypeMetadataService:
    """Return the process-wide stateless BusinessTypeMetadataService."""
    global _business_type_metadata_service
    if _business_type_metadata_service is None:
        with _business_type_metadata_service_lock:
            if _business_type_metadata_service is None:
                _business_type_metadata_service = BusinessTypeMetadataService()
    return _business_type_metadata_service
