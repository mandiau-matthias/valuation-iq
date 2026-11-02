from src.utils.exceptions import DCFCalculationError, MultiplesCalculationError

"""
Selection Strategies

This module contains various methodology selection strategies and algorithms
for the intelligent methodology selector.
"""

from typing import Dict, List, Optional, Any, Tuple
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .selector_types import (
    MethodologyType,
    BusinessContext,
    FinancialScore,
    OwnerScore,
    MarketScore,
    MethodologySelection,
    SelectionCriteria
)

logger = get_logger(__name__)


class SelectionStrategies:
    """Contains various methodology selection strategies"""

    def __init__(self):
        """Initialize the selection strategies"""
        self.logger = logger
        self.strategy_weights = self._build_strategy_weights()
        self.methodology_preferences = self._build_methodology_preferences()

    def select_by_business_characteristics(
        self,
        business_context: BusinessContext,
        criteria: SelectionCriteria
    ) -> MethodologyType:
        """
        Select methodology based on business characteristics

        Args:
            business_context: Business context information
            criteria: Selection criteria

        Returns:
            Selected methodology type
        """
        try:
            self.logger.info("Selecting methodology by business characteristics",
                           industry=business_context.industry,
                           business_type=business_context.business_type)

            # High growth businesses prefer DCF
            if business_context.growth_rate > 0.2:  # 20%+ growth
                if business_context.technology_dependency == "high":
                    return MethodologyType.DCF
                elif business_context.asset_intensity == "low":
                    return MethodologyType.DCF

            # High asset intensity businesses prefer asset-based
            if business_context.asset_intensity == "high":
                if business_context.capital_intensity == "high":
                    return MethodologyType.ASSET_BASED
                else:
                    return MethodologyType.MULTIPLES

            # Mature businesses prefer multiples
            if business_context.market_maturity == "mature":
                if business_context.revenue > 1000000:  # > 1M revenue
                    return MethodologyType.MULTIPLES
                else:
                    return MethodologyType.DCF

            # Technology businesses prefer DCF or ARR multiples
            if business_context.technology_dependency == "high":
                if business_context.business_type in ["saas", "software", "platform"]:
                    return MethodologyType.MULTIPLES  # ARR multiples
                else:
                    return MethodologyType.DCF

            # High regulatory businesses prefer DCF
            if business_context.regulatory_environment == "high":
                return MethodologyType.DCF

            # Default to multiples for established businesses
            if business_context.revenue > 500000:  # > 500k revenue
                return MethodologyType.MULTIPLES
            else:
                return MethodologyType.DCF

        except DCFCalculationError as e:
            self.logger.error(f"Error selecting by business characteristics: {e}")
            return MethodologyType.MULTIPLES

    def select_by_financial_health(
        self,
        financial_score: FinancialScore,
        criteria: SelectionCriteria
    ) -> MethodologyType:
        """
        Select methodology based on financial health

        Args:
            financial_score: Financial health score
            criteria: Selection criteria

        Returns:
            Selected methodology type
        """
        try:
            self.logger.info("Selecting methodology by financial health",
                           overall_score=financial_score.overall_score)

            # High financial health businesses can handle DCF
            if financial_score.overall_score > 0.8:
                if financial_score.growth_potential > 0.7:
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Medium financial health businesses
            elif financial_score.overall_score > 0.6:
                if financial_score.revenue_stability > 0.7:
                    return MethodologyType.MULTIPLES
                else:
                    return MethodologyType.DCF

            # Low financial health businesses
            else:
                if financial_score.asset_quality > 0.6:
                    return MethodologyType.ASSET_BASED
                else:
                    return MethodologyType.MULTIPLES

        except DCFCalculationError as e:
            self.logger.error(f"Error selecting by financial health: {e}")
            return MethodologyType.MULTIPLES

    def select_by_owner_dependency(
        self,
        owner_score: OwnerScore,
        criteria: SelectionCriteria
    ) -> MethodologyType:
        """
        Select methodology based on owner dependency

        Args:
            owner_score: Owner dependency score
            criteria: Selection criteria

        Returns:
            Selected methodology type
        """
        try:
            self.logger.info("Selecting methodology by owner dependency",
                           dependency_level=owner_score.dependency_level)

            # High owner dependency businesses need simpler methods
            if owner_score.dependency_level > 0.8:
                if owner_score.delegation_capability < 0.3:
                    return MethodologyType.MULTIPLES
                else:
                    return MethodologyType.DCF

            # Medium owner dependency businesses
            elif owner_score.dependency_level > 0.5:
                if owner_score.succession_planning > 0.6:
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Low owner dependency businesses
            else:
                if owner_score.expertise_level > 0.7:
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

        except DCFCalculationError as e:
            self.logger.error(f"Error selecting by owner dependency: {e}")
            return MethodologyType.MULTIPLES

    def select_by_market_context(
        self,
        market_score: MarketScore,
        criteria: SelectionCriteria
    ) -> MethodologyType:
        """
        Select methodology based on market context

        Args:
            market_score: Market context score
            criteria: Selection criteria

        Returns:
            Selected methodology type
        """
        try:
            self.logger.info("Selecting methodology by market context",
                           overall_score=market_score.overall_score)

            # High market potential businesses prefer DCF
            if market_score.overall_score > 0.8:
                if market_score.market_growth > 0.7:
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Medium market potential businesses
            elif market_score.overall_score > 0.6:
                if market_score.competition_level < 0.4:  # Low competition
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Low market potential businesses
            else:
                if market_score.barriers_to_entry > 0.6:
                    return MethodologyType.ASSET_BASED
                else:
                    return MethodologyType.MULTIPLES

        except MultiplesCalculationError as e:
            self.logger.error(f"Error selecting by market context: {e}")
            return MethodologyType.MULTIPLES

    def select_by_industry_rules(
        self,
        business_context: BusinessContext,
        industry_rules: Dict[str, Any]
    ) -> MethodologyType:
        """
        Select methodology based on industry rules

        Args:
            business_context: Business context information
            industry_rules: Industry-specific rules

        Returns:
            Selected methodology type
        """
        try:
            self.logger.info("Selecting methodology by industry rules",
                           industry=business_context.industry)

            industry = business_context.industry.lower()

            # Get industry preferences
            preferences = industry_rules.get("industry_preferences", {})
            if industry in preferences:
                return MethodologyType(preferences[industry])

            # Technology industry rules
            if industry in ["technology", "software", "saas"]:
                if business_context.business_type in ["saas", "platform"]:
                    return MethodologyType.MULTIPLES  # ARR multiples
                else:
                    return MethodologyType.DCF

            # Manufacturing industry rules
            elif industry in ["manufacturing", "industrial"]:
                if business_context.asset_intensity == "high":
                    return MethodologyType.ASSET_BASED
                else:
                    return MethodologyType.MULTIPLES

            # Retail industry rules
            elif industry in ["retail", "ecommerce"]:
                if business_context.revenue > 1000000:
                    return MethodologyType.MULTIPLES
                else:
                    return MethodologyType.DCF

            # Services industry rules
            elif industry in ["services", "consulting"]:
                if business_context.customer_concentration == "high":
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Healthcare industry rules
            elif industry in ["healthcare", "pharmaceutical"]:
                if business_context.regulatory_environment == "high":
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Finance industry rules
            elif industry in ["finance", "banking"]:
                if business_context.regulatory_environment == "high":
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Default to multiples
            return MethodologyType.MULTIPLES

        except DCFCalculationError as e:
            self.logger.error(f"Error selecting by industry rules: {e}")
            return MethodologyType.MULTIPLES

    def select_by_revenue_size(
        self,
        business_context: BusinessContext,
        criteria: SelectionCriteria
    ) -> MethodologyType:
        """
        Select methodology based on revenue size

        Args:
            business_context: Business context information
            criteria: Selection criteria

        Returns:
            Selected methodology type
        """
        try:
            self.logger.info("Selecting methodology by revenue size",
                           revenue=business_context.revenue)

            revenue = business_context.revenue

            # Small businesses (< 100k)
            if revenue < 100000:
                if business_context.asset_intensity == "high":
                    return MethodologyType.ASSET_BASED
                else:
                    return MethodologyType.MULTIPLES

            # Medium businesses (100k - 1M)
            elif revenue < 1000000:
                if business_context.growth_rate > 0.15:  # 15%+ growth
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Large businesses (1M - 10M)
            elif revenue < 10000000:
                if business_context.technology_dependency == "high":
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Very large businesses (> 10M)
            else:
                if business_context.market_maturity == "mature":
                    return MethodologyType.MULTIPLES
                else:
                    return MethodologyType.DCF

        except DCFCalculationError as e:
            self.logger.error(f"Error selecting by revenue size: {e}")
            return MethodologyType.MULTIPLES

    def select_by_growth_stage(
        self,
        business_context: BusinessContext,
        criteria: SelectionCriteria
    ) -> MethodologyType:
        """
        Select methodology based on growth stage

        Args:
            business_context: Business context information
            criteria: Selection criteria

        Returns:
            Selected methodology type
        """
        try:
            self.logger.info("Selecting methodology by growth stage",
                           growth_rate=business_context.growth_rate,
                           market_maturity=business_context.market_maturity)

            # Startup stage
            if business_context.market_maturity == "emerging":
                if business_context.technology_dependency == "high":
                    return MethodologyType.MULTIPLES  # ARR multiples for tech startups
                else:
                    return MethodologyType.DCF

            # Growth stage
            elif business_context.growth_rate > 0.2:  # 20%+ growth
                if business_context.technology_dependency == "high":
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Mature stage
            elif business_context.market_maturity == "mature":
                if business_context.asset_intensity == "high":
                    return MethodologyType.ASSET_BASED
                else:
                    return MethodologyType.MULTIPLES

            # Decline stage
            else:
                if business_context.asset_intensity == "high":
                    return MethodologyType.ASSET_BASED
                else:
                    return MethodologyType.MULTIPLES

        except MultiplesCalculationError as e:
            self.logger.error(f"Error selecting by growth stage: {e}")
            return MethodologyType.MULTIPLES

    def select_by_asset_intensity(
        self,
        business_context: BusinessContext,
        criteria: SelectionCriteria
    ) -> MethodologyType:
        """
        Select methodology based on asset intensity

        Args:
            business_context: Business context information
            criteria: Selection criteria

        Returns:
            Selected methodology type
        """
        try:
            self.logger.info("Selecting methodology by asset intensity",
                           asset_intensity=business_context.asset_intensity)

            # High asset intensity
            if business_context.asset_intensity == "high":
                if business_context.capital_intensity == "high":
                    return MethodologyType.ASSET_BASED
                else:
                    return MethodologyType.MULTIPLES

            # Medium asset intensity
            elif business_context.asset_intensity == "medium":
                if business_context.growth_rate > 0.15:  # 15%+ growth
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Low asset intensity
            else:
                if business_context.technology_dependency == "high":
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

        except DCFCalculationError as e:
            self.logger.error(f"Error selecting by asset intensity: {e}")
            return MethodologyType.MULTIPLES

    def select_by_regulatory_environment(
        self,
        business_context: BusinessContext,
        criteria: SelectionCriteria
    ) -> MethodologyType:
        """
        Select methodology based on regulatory environment

        Args:
            business_context: Business context information
            criteria: Selection criteria

        Returns:
            Selected methodology type
        """
        try:
            self.logger.info("Selecting methodology by regulatory environment",
                           regulatory_environment=business_context.regulatory_environment)

            # High regulatory environment
            if business_context.regulatory_environment == "high":
                if business_context.industry in ["healthcare", "pharmaceutical", "finance"]:
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Medium regulatory environment
            elif business_context.regulatory_environment == "medium":
                if business_context.growth_rate > 0.15:  # 15%+ growth
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

            # Low regulatory environment
            else:
                if business_context.technology_dependency == "high":
                    return MethodologyType.DCF
                else:
                    return MethodologyType.MULTIPLES

        except DCFCalculationError as e:
            self.logger.error(f"Error selecting by regulatory environment: {e}")
            return MethodologyType.MULTIPLES

    def _build_strategy_weights(self) -> Dict[str, Decimal]:
        """Build strategy weights for methodology selection"""
        return {
            "business_characteristics": 0.25,
            "financial_health": 0.20,
            "owner_dependency": 0.15,
            "market_context": 0.15,
            "industry_rules": 0.15,
            "revenue_size": 0.05,
            "growth_stage": 0.05
        }

    def _build_methodology_preferences(self) -> Dict[str, List[MethodologyType]]:
        """Build methodology preferences by strategy"""
        return {
            "business_characteristics": [MethodologyType.DCF, MethodologyType.MULTIPLES],
            "financial_health": [MethodologyType.DCF, MethodologyType.MULTIPLES],
            "owner_dependency": [MethodologyType.MULTIPLES, MethodologyType.DCF],
            "market_context": [MethodologyType.DCF, MethodologyType.MULTIPLES],
            "industry_rules": [MethodologyType.MULTIPLES, MethodologyType.DCF],
            "revenue_size": [MethodologyType.MULTIPLES, MethodologyType.DCF],
            "growth_stage": [MethodologyType.DCF, MethodologyType.MULTIPLES]
        }