from src.utils.exceptions import DataValidationError, DCFCalculationError

"""
Business Rules for Methodology Selection

This module contains the business rules and logic for selecting
optimal valuation methodologies based on business characteristics.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from .methodology_types import (
    AssetIntensity,
    BusinessCategory,
    BusinessTypeConfig,
    GrowthPotential,
    MethodologyDecision,
    RevenuePredictability,
    ValuationMethodology,
)
from .time_estimates import methodology_time_estimate

logger = get_logger(__name__)


class MethodologyRules:
    """
    Business rules for methodology selection.

    Contains the logic for determining optimal valuation methodologies
    based on business type, industry, and characteristics.
    """

    def __init__(self):
        """Initialize methodology rules"""
        self.logger = logger

        # Base rules for methodology selection
        self.methodology_rules = self._initialize_methodology_rules()

        # Industry-specific rules
        self.industry_rules = self._initialize_industry_rules()

    def select_methodology(
        self,
        business_type: str,
        revenue: Optional[Decimal] = None,
        asset_intensity: Optional[str] = None,
        growth_potential: Optional[str] = None,
    ) -> MethodologyDecision:
        """
        Select optimal methodology based on business characteristics

        Args:
            business_type: Type of business
            revenue: Annual revenue (optional)
            asset_intensity: Asset intensity level (optional)
            growth_potential: Growth potential level (optional)

        Returns:
            MethodologyDecision with selected methodology
        """
        try:
            # Normalize business type
            normalized_type = self._normalize_business_type(business_type)

            # Get base configuration
            config = self._get_business_type_config(normalized_type)

            if not config:
                return self._get_conservative_fallback()

            # Apply business rules
            decision = self._apply_business_rules(
                config, revenue, asset_intensity, growth_potential
            )

            self.logger.info(
                f"Selected methodology for {business_type}: {decision.primary_methodology.value}"
            )
            return decision

        except DCFCalculationError as e:
            self.logger.error(f"Error selecting methodology: {e}")
            return self._get_conservative_fallback()

    def _initialize_methodology_rules(self) -> Dict[str, Any]:
        """Initialize base methodology selection rules"""
        return {
            # High asset intensity -> DCF or Asset-based
            "high_asset_intensity": {
                "condition": "asset_intensity == 'high'",
                "primary": ValuationMethodology.DCF,
                "secondary": ValuationMethodology.ASSET_BASED,
                "reasoning": "High asset intensity businesses require detailed cash flow analysis",
            },
            # Low asset intensity -> Multiples
            "low_asset_intensity": {
                "condition": "asset_intensity == 'low'",
                "primary": ValuationMethodology.MULTIPLES,
                "secondary": ValuationMethodology.DCF,
                "reasoning": "Low asset intensity businesses are well-suited for market multiples",
            },
            # High growth potential -> DCF or ARR multiples
            "high_growth": {
                "condition": "growth_potential == 'high'",
                "primary": ValuationMethodology.DCF,
                "secondary": ValuationMethodology.ARR_MULTIPLES,
                "reasoning": "High growth businesses require forward-looking valuation methods",
            },
            # SaaS/Technology -> ARR multiples
            "saas_technology": {
                "condition": "business_type in ['saas', 'software', 'mobile_app', 'ecommerce']",
                "primary": ValuationMethodology.ARR_MULTIPLES,
                "secondary": ValuationMethodology.DCF,
                "reasoning": "Technology businesses are best valued using ARR/MRR multiples",
            },
            # Asset-heavy businesses -> Asset-based
            "asset_heavy": {
                "condition": "asset_intensity == 'high' and business_type in ['manufacturing', 'construction', 'real_estate']",
                "primary": ValuationMethodology.ASSET_BASED,
                "secondary": ValuationMethodology.DCF,
                "reasoning": "Asset-heavy businesses should be valued based on their asset base",
            },
            # Service businesses -> Multiples
            "service_businesses": {
                "condition": "business_type in ['consulting', 'legal', 'accounting', 'marketing']",
                "primary": ValuationMethodology.MULTIPLES,
                "secondary": ValuationMethodology.DCF,
                "reasoning": "Service businesses are well-suited for market multiples",
            },
        }

    def _initialize_industry_rules(self) -> Dict[str, Any]:
        """Initialize industry-specific rules"""
        return {
            "food_beverage": {
                "preferred_methodology": ValuationMethodology.MULTIPLES,
                "key_factors": ["location", "reputation", "operational_efficiency"],
                "multiple_types": ["revenue", "ebitda"],
                "special_considerations": ["seasonality", "local_competition"],
            },
            "technology": {
                "preferred_methodology": ValuationMethodology.ARR_MULTIPLES,
                "key_factors": ["user_base", "recurring_revenue", "growth_rate"],
                "multiple_types": ["arr", "revenue"],
                "special_considerations": ["market_penetration", "competitive_advantage"],
            },
            "healthcare": {
                "preferred_methodology": ValuationMethodology.DCF,
                "key_factors": ["patient_base", "specialization", "regulatory_compliance"],
                "multiple_types": ["revenue", "ebitda"],
                "special_considerations": ["regulatory_risks", "patient_retention"],
            },
            "manufacturing": {
                "preferred_methodology": ValuationMethodology.DCF,
                "key_factors": ["production_capacity", "equipment_value", "supply_chain"],
                "multiple_types": ["revenue", "ebitda"],
                "special_considerations": ["equipment_depreciation", "supply_chain_risks"],
            },
            "services": {
                "preferred_methodology": ValuationMethodology.MULTIPLES,
                "key_factors": ["client_base", "reputation", "talent"],
                "multiple_types": ["revenue", "ebitda"],
                "special_considerations": ["key_person_risk", "client_retention"],
            },
        }

    def _get_business_type_config(self, business_type: str) -> Optional[BusinessTypeConfig]:
        """Get configuration for a business type"""
        # This would contain the actual business type mappings
        # For now, return a simplified configuration
        return BusinessTypeConfig(
            primary=ValuationMethodology.MULTIPLES,
            secondary=ValuationMethodology.DCF,
            multiple_types=["revenue", "ebitda"],
            asset_intensity="medium",
            key_factors=["revenue", "profitability", "market_position"],
            special_considerations=["market_conditions", "competitive_position"],
            growth_weighted=False,
            reasoning="Standard business valuation approach",
        )

    def _apply_business_rules(
        self,
        config: BusinessTypeConfig,
        revenue: Optional[Decimal],
        asset_intensity: Optional[str],
        growth_potential: Optional[str],
    ) -> MethodologyDecision:
        """Apply business rules to determine methodology"""
        try:
            # Start with base configuration
            primary = config.primary
            secondary = config.secondary
            confidence = Decimal("0.7")  # Bank-grade: Decimal confidence
            reasoning = config.reasoning

            # Apply revenue-based rules - Bank-grade: Decimal arithmetic
            if revenue:
                if revenue > 10000000:  # > €10M
                    if primary == ValuationMethodology.MULTIPLES:
                        primary = ValuationMethodology.DCF
                        confidence += Decimal("0.1")  # Bank-grade: Decimal increment
                        reasoning += " Large business requires detailed DCF analysis."
                elif revenue < 1000000:  # < €1M
                    if primary == ValuationMethodology.DCF:
                        primary = ValuationMethodology.MULTIPLES
                        confidence += Decimal("0.1")  # Bank-grade: Decimal increment
                        reasoning += " Small business suitable for multiples approach."

            # Apply asset intensity rules - Bank-grade: Decimal arithmetic
            if asset_intensity:
                if asset_intensity == "high":
                    if primary != ValuationMethodology.DCF:
                        primary = ValuationMethodology.DCF
                        confidence += Decimal("0.1")  # Bank-grade: Decimal increment
                        reasoning += " High asset intensity requires DCF analysis."
                elif asset_intensity == "low":
                    if primary != ValuationMethodology.MULTIPLES:
                        primary = ValuationMethodology.MULTIPLES
                        confidence += Decimal("0.1")  # Bank-grade: Decimal increment
                        reasoning += " Low asset intensity suitable for multiples."

            # Apply growth potential rules - Bank-grade: Decimal arithmetic
            if growth_potential:
                if growth_potential == "high":
                    if primary == ValuationMethodology.MULTIPLES:
                        primary = ValuationMethodology.DCF
                        confidence += Decimal("0.1")  # Bank-grade: Decimal increment
                        reasoning += " High growth potential requires forward-looking DCF."
                elif growth_potential == "low":
                    if primary == ValuationMethodology.DCF:
                        primary = ValuationMethodology.MULTIPLES
                        confidence += Decimal("0.1")  # Bank-grade: Decimal increment
                        reasoning += " Stable business suitable for multiples."

            # Ensure confidence is within bounds - Bank-grade: Decimal comparison
            confidence = min(confidence, Decimal("1.0"))  # Bank-grade: Decimal max bound

            return MethodologyDecision(
                primary_methodology=primary,
                secondary_methodology=secondary,
                confidence_score=confidence,
                reasoning=reasoning,
                key_factors=config.key_factors,
                special_considerations=config.special_considerations,
                expected_accuracy=Decimal("0.8"),  # Bank-grade: Decimal expected accuracy
                time_estimate=methodology_time_estimate(primary, revenue),
                multiple_types=config.multiple_types,
                growth_weighted=config.growth_weighted,
                asset_intensity=config.asset_intensity,
            )

        except DCFCalculationError as e:
            self.logger.error(f"Error applying business rules: {e}")
            return self._get_conservative_fallback()

    def _get_conservative_fallback(self) -> MethodologyDecision:
        """Conservative fallback methodology"""
        return MethodologyDecision(
            primary_methodology=ValuationMethodology.MULTIPLES,
            secondary_methodology=ValuationMethodology.ASSET_BASED,
            confidence_score=Decimal("0.6"),  # Bank-grade: Decimal confidence
            reasoning="Using conservative market multiples approach for general business valuation",
            key_factors=["revenue", "profitability", "market_position"],
            special_considerations=["market_conditions", "industry_trends", "competitive_position"],
            expected_accuracy=Decimal("0.7"),  # Bank-grade: Decimal expected accuracy
            time_estimate="1-2 hours",
            multiple_types=["revenue", "ebitda"],
            growth_weighted=False,
            asset_intensity="medium",
        )

    def _normalize_business_type(self, business_type: str) -> str:
        """Normalize business type string"""
        return business_type.lower().replace(" ", "_").replace("-", "_")

    def get_industry_factors(self, industry: str) -> Dict[str, Any]:
        """Get industry-specific factors"""
        return self.industry_rules.get(
            industry,
            {
                "preferred_methodology": ValuationMethodology.MULTIPLES,
                "key_factors": ["revenue", "profitability"],
                "multiple_types": ["revenue", "ebitda"],
                "special_considerations": ["market_conditions"],
            },
        )

    def validate_methodology_choice(
        self, business_type: str, methodology: ValuationMethodology
    ) -> bool:
        """Validate if a methodology choice is appropriate for a business type"""
        try:
            # Get recommended methodology
            decision = self.select_methodology(business_type)

            # Check if chosen methodology is primary or secondary
            return (
                methodology == decision.primary_methodology
                or methodology == decision.secondary_methodology
            )

        except DataValidationError as e:
            self.logger.error(f"Error validating methodology choice: {e}")
            return False
