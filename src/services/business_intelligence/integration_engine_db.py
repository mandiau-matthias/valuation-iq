from src.utils.exceptions import DCFCalculationError, DatabaseError

"""
Business Type Integration Engine (Database Version)

Updated integration engine that uses the database service instead of hardcoded configurations.
Maintains backward compatibility while providing database-driven intelligence.

@author UpSwitch CTO Team
@version 1.0.0
"""

import asyncio
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import structlog

from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.business_intelligence.integration.business_type_database_service import (
    get_business_type_database_service,
    BusinessTypeDatabaseService,
    BusinessTypeConfig,
    MethodologySelection
)

# ============================================================================
# TYPES
# ============================================================================

class BusinessCategory:
    """Business category enum"""
    FOOD_BEVERAGE = "food-beverage"
    TECH_DIGITAL = "tech-digital"
    PROFESSIONAL_SERVICES = "professional-services"
    BEAUTY_WELLNESS = "beauty-wellness"
    RETAIL_ECOMMERCE = "retail-ecommerce"
    HOME_PROPERTY = "home-property"
    EDUCATION_TRAINING = "education-training"
    TRANSPORTATION_LOGISTICS = "transportation-logistics"
    EVENTS_ENTERTAINMENT = "events-entertainment"
    FINANCIAL_SERVICES = "financial-services"
    PET_SERVICES = "pet-services"
    AUTOMOTIVE = "automotive"
    HOSPITALITY_TOURISM = "hospitality-tourism"
    AGRICULTURE = "agriculture"
    ARTS_CRAFTS = "arts-crafts"
    REPAIR_MAINTENANCE = "repair-maintenance"
    SECURITY_SAFETY = "security-safety"
    ENVIRONMENTAL = "environmental"

@dataclass
class BusinessTypeAnalysis:
    """Business type analysis result"""
    business_type_id: str
    category: str
    industry: str
    dcf_preference: Decimal
    multiples_preference: Decimal
    owner_dependency_impact: Decimal
    key_metrics: List[str]
    methodology_selection: MethodologySelection
    confidence_score: Decimal
    recommendations: List[str]

# ============================================================================
# INTEGRATION ENGINE
# ============================================================================

class BusinessTypeIntegrationEngine:
    """
    Database-driven business type integration engine.
    Replaces hardcoded configurations with database-driven intelligence.
    """

    def __init__(self):
        self.database_service = get_business_type_database_service()
        self.logger = structlog.get_logger(__name__)
        self._initialized = False
        self._initialize_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the integration engine"""
        if self._initialized:
            return

        async with self._initialize_lock:
            if self._initialized:
                return

            try:
                self.logger.info("Initializing BusinessTypeIntegrationEngine...")

                # Initialize the database service
                self._initialized = True
                self.logger.info("BusinessTypeIntegrationEngine initialized (stateless mode)")

            except (DatabaseError, AttributeError) as e:
                self.logger.warning(f"BusinessTypeIntegrationEngine init degraded: {e}")
                self._initialized = True

    async def get_business_type_config(self, business_type_id: str) -> Optional[BusinessTypeConfig]:
        """Get business type configuration by ID"""
        if not self._initialized:
            await self.initialize()

        try:
            return self.database_service.get_business_type(business_type_id)
        except (AttributeError, TypeError):
            return None

    async def get_all_business_types(self) -> Dict[str, BusinessTypeConfig]:
        """Get all business type configurations"""
        if not self._initialized:
            await self.initialize()

        return await self.database_service.get_all_business_types()

    async def get_business_types_by_category(self, category: str) -> Dict[str, BusinessTypeConfig]:
        """Get business types by category"""
        if not self._initialized:
            await self.initialize()

        return await self.database_service.get_business_types_by_category(category)

    async def get_popular_business_types(self) -> Dict[str, BusinessTypeConfig]:
        """Get popular business types"""
        if not self._initialized:
            await self.initialize()

        return await self.database_service.get_popular_business_types()

    async def search_business_types(self, query: str, limit: int = 20) -> Dict[str, BusinessTypeConfig]:
        """Search business types"""
        if not self._initialized:
            await self.initialize()

        return await self.database_service.search_business_types(query, limit)

    async def analyze_business_type(self, business_type_id: str, business_characteristics: Dict[str, Any]) -> Optional[BusinessTypeAnalysis]:
        """Analyze a business type and provide methodology recommendations"""
        if not self._initialized:
            await self.initialize()

        try:
            # Get business type configuration
            config = await self.database_service.get_business_type_config(business_type_id)
            if not config:
                self.logger.warning(f"Business type {business_type_id} not found")
                return None

            # Select optimal methodology
            methodology_selection = await self.database_service.select_methodology(
                business_type_id, 
                business_characteristics
            )

            if not methodology_selection:
                self.logger.warning(f"Failed to select methodology for business type {business_type_id}")
                return None

            # Generate recommendations
            recommendations = await self._generate_recommendations(
                business_type_id, 
                config, 
                business_characteristics,
                methodology_selection
            )

            # Calculate confidence score
            confidence_score = await self._calculate_confidence_score(
                config, 
                business_characteristics, 
                methodology_selection
            )

            return BusinessTypeAnalysis(
                business_type_id=business_type_id,
                category=config.category,
                industry=config.industry,
                dcf_preference=config.dcf_preference,
                multiples_preference=config.multiples_preference,
                owner_dependency_impact=config.owner_dependency_impact,
                key_metrics=config.key_metrics,
                methodology_selection=methodology_selection,
                confidence_score=confidence_score,
                recommendations=recommendations
            )

        except DCFCalculationError as e:
            self.logger.error(f"Failed to analyze business type {business_type_id}: {e}")
            return None

    async def _generate_recommendations(
        self, 
        business_type_id: str, 
        config: BusinessTypeConfig, 
        business_characteristics: Dict[str, Any],
        methodology_selection: MethodologySelection
    ) -> List[str]:
        """Generate recommendations based on business type and characteristics"""
        recommendations = []

        # Methodology recommendations
        if methodology_selection.dcf_weight > 0.7:
            recommendations.append("DCF methodology is strongly recommended for this business type")
        elif methodology_selection.multiples_weight > 0.7:
            recommendations.append("Market multiples methodology is strongly recommended for this business type")
        else:
            recommendations.append("Hybrid methodology combining DCF and market multiples is recommended")

        # Owner dependency recommendations
        if config.owner_dependency_impact > 0.7:
            recommendations.append("High owner dependency detected - consider succession planning in valuation")
        elif config.owner_dependency_impact < 0.3:
            recommendations.append("Low owner dependency - business is well-systematized")

        # Key metrics recommendations
        if config.key_metrics:
            recommendations.append(f"Focus on these key metrics: {', '.join(config.key_metrics)}")

        # Business characteristics recommendations
        if business_characteristics.get('revenue_growth_rate', 0) > 0.2:
            recommendations.append("High growth rate - DCF methodology will capture future value")
        elif business_characteristics.get('revenue_growth_rate', 0) < 0.05:
            recommendations.append("Low growth rate - market multiples may be more appropriate")

        if business_characteristics.get('recurring_revenue_percentage', 0) > 0.8:
            recommendations.append("High recurring revenue - consider SaaS-specific valuation methods")

        return recommendations

    async def _calculate_confidence_score(
        self, 
        config: BusinessTypeConfig, 
        business_characteristics: Dict[str, Any],
        methodology_selection: MethodologySelection
    ) -> Decimal:
        """Calculate confidence score for the analysis"""
        base_confidence = Decimal('0.8')  # High confidence with database data

        # Adjust based on data completeness
        if config.dcf_preference and config.multiples_preference:
            base_confidence += Decimal('0.1')

        if config.key_metrics:
            base_confidence += Decimal('0.05')

        # Adjust based on business characteristics alignment
        if business_characteristics.get('revenue_growth_rate') is not None:
            base_confidence += Decimal('0.05')

        if business_characteristics.get('owner_dependency') is not None:
            base_confidence += Decimal('0.05')

        # Cap at 1.0
        return min(base_confidence, Decimal('1.0'))

    async def get_methodology_weights(self, business_type_id: str, business_characteristics: Dict[str, Any]) -> Optional[Tuple[float, float]]:
        """Get methodology weights for a business type"""
        if not self._initialized:
            await self.initialize()

        return await self.database_service.get_methodology_preferences(business_type_id)

    async def get_owner_dependency_impact(self, business_type_id: str) -> Optional[Decimal]:
        """Get owner dependency impact for a business type"""
        if not self._initialized:
            await self.initialize()

        return await self.database_service.get_owner_dependency_impact(business_type_id)

    async def get_key_metrics(self, business_type_id: str) -> List[str]:
        """Get key metrics for a business type"""
        if not self._initialized:
            await self.initialize()

        return await self.database_service.get_key_metrics(business_type_id)

    async def get_business_type_intelligence(self, business_type_id: str) -> Dict[str, Any]:
        """Get comprehensive business type intelligence"""
        if not self._initialized:
            await self.initialize()

        return await self.database_service.get_business_type_intelligence(business_type_id)

    async def refresh_data(self) -> None:
        """Refresh business types data from database"""
        if not self._initialized:
            await self.initialize()

        await self.database_service.refresh_cache()
        self.logger.info("Business types data refreshed from database")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get integration engine health status"""
        try:
            db_health = await self.database_service.get_health_status()

            return {
                "service": "BusinessTypeIntegrationEngine",
                "initialized": self._initialized,
                "database_service": db_health
            }
        except DatabaseError as e:
            return {
                "service": "BusinessTypeIntegrationEngine",
                "initialized": self._initialized,
                "error": str(e)
            }

# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_business_type_integration_engine: Optional[BusinessTypeIntegrationEngine] = None
_business_type_integration_engine_lock = threading.Lock()

def get_business_type_integration_engine() -> BusinessTypeIntegrationEngine:
    """Get thread-safe singleton business type integration engine instance."""
    global _business_type_integration_engine

    if _business_type_integration_engine is None:
        with _business_type_integration_engine_lock:
            if _business_type_integration_engine is None:
                _business_type_integration_engine = BusinessTypeIntegrationEngine()

    return _business_type_integration_engine
