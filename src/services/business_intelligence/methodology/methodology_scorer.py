
"""
Methodology Scorer

This module handles scoring and ranking of valuation methodologies
based on business characteristics, financial health, and market context.
"""

from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from src.utils.logging import get_logger
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


class MethodologyScorer:
    """Scores and ranks valuation methodologies based on business characteristics"""

    def __init__(self):
        """Initialize the methodology scorer"""
        self.logger = logger
        self.scoring_weights = self._build_scoring_weights()
        self.methodology_scores = self._build_methodology_scores()
        self.industry_preferences = self._build_industry_preferences()

    def score_methodology(
        self,
        methodology: MethodologyType,
        criteria: SelectionCriteria
    ) -> Decimal:
        """
        Score a methodology based on selection criteria

        Args:
            methodology: The methodology to score
            criteria: Selection criteria

        Returns:
            Score between 0 and 1
        """
        try:
            self.logger.info("Scoring methodology",
                           methodology=methodology.value,
                           industry=criteria.business_characteristics.industry)

            # Calculate component scores
            business_score = self._score_by_business_characteristics(
                methodology, criteria.business_characteristics
            )
            financial_score = self._score_by_financial_health(
                methodology, criteria.financial_health
            )
            owner_score = self._score_by_owner_dependency(
                methodology, criteria.owner_dependency
            )
            market_score = self._score_by_market_context(
                methodology, criteria.market_context
            )
            industry_score = self._score_by_industry_rules(
                methodology, criteria.business_characteristics, criteria.industry_rules
            )

            # Calculate weighted final score
            final_score = self._calculate_weighted_score(
                business_score, financial_score, owner_score, market_score, industry_score
            )

            # Apply confidence adjustments
            final_score = self._apply_confidence_adjustments(final_score, criteria)

            self.logger.info("Methodology scored",
                           methodology=methodology.value,
                           final_score=from_decimal(final_score))

            return final_score

        except Exception as e:
            self.logger.error(f"Error scoring methodology: {e}")
            return Decimal('0.5')  # Default neutral score

    def rank_methodologies(
        self,
        methodologies: List[MethodologyType],
        criteria: SelectionCriteria
    ) -> List[Tuple[MethodologyType, float]]:
        """
        Rank methodologies by score

        Args:
            methodologies: List of methodologies to rank
            criteria: Selection criteria

        Returns:
            List of (methodology, score) tuples sorted by score
        """
        try:
            self.logger.info("Ranking methodologies",
                           count=len(methodologies),
                           industry=criteria.business_characteristics.industry)

            scored_methodologies = []

            for methodology in methodologies:
                score = self.score_methodology(methodology, criteria)
                scored_methodologies.append((methodology, score))

            # Sort by score (descending)
            ranked_methodologies = sorted(
                scored_methodologies,
                key=lambda x: x[1],
                reverse=True
            )

            self.logger.info("Methodologies ranked",
                           top_methodology=ranked_methodologies[0][0].value if ranked_methodologies else None,
                           top_score=from_decimal(ranked_methodologies[0][1]) if ranked_methodologies else 0.0)

            return ranked_methodologies

        except Exception as e:
            self.logger.error(f"Error ranking methodologies: {e}")
            return []

    def _score_by_business_characteristics(
        self,
        methodology: MethodologyType,
        business_context: BusinessContext
    ) -> Decimal:
        """Score methodology based on business characteristics"""
        try:
            score_decimal = Decimal('0.5')  # Base score
            growth_rate_decimal = to_decimal(business_context.growth_rate) if hasattr(business_context, 'growth_rate') else Decimal('0')
            revenue_decimal = to_decimal(business_context.revenue) if hasattr(business_context, 'revenue') else Decimal('0')

            # DCF scoring
            if methodology == MethodologyType.DCF:
                if growth_rate_decimal > Decimal('0.15'):  # 15%+ growth
                    score_decimal += Decimal('0.3')
                if business_context.technology_dependency == "high":
                    score_decimal += Decimal('0.2')
                if business_context.asset_intensity == "low":
                    score_decimal += Decimal('0.1')
                if business_context.market_maturity == "emerging":
                    score_decimal += Decimal('0.2')
                if business_context.regulatory_environment == "high":
                    score_decimal += Decimal('0.1')

            # Multiples scoring
            elif methodology == MethodologyType.MULTIPLES:
                if business_context.market_maturity == "mature":
                    score_decimal += Decimal('0.3')
                if revenue_decimal > Decimal('1000000'):  # > 1M revenue
                    score_decimal += Decimal('0.2')
                if business_context.asset_intensity == "medium":
                    score_decimal += Decimal('0.1')
                if business_context.regulatory_environment == "low":
                    score_decimal += Decimal('0.1')
                if business_context.customer_concentration == "low":
                    score_decimal += Decimal('0.1')

            # Asset-based scoring
            elif methodology == MethodologyType.ASSET_BASED:
                if business_context.asset_intensity == "high":
                    score_decimal += Decimal('0.4')
                if business_context.capital_intensity == "high":
                    score_decimal += Decimal('0.2')
                if business_context.market_maturity == "mature":
                    score_decimal += Decimal('0.1')
                if growth_rate_decimal < Decimal('0.05'):  # < 5% growth
                    score_decimal += Decimal('0.1')

            # Synthesized scoring
            elif methodology == MethodologyType.SYNTHESIZED:
                if revenue_decimal > Decimal('5000000'):  # > 5M revenue
                    score_decimal += Decimal('0.3')
                if business_context.market_maturity == "mature":
                    score_decimal += Decimal('0.2')
                if business_context.regulatory_environment == "high":
                    score_decimal += Decimal('0.1')
                if business_context.technology_dependency == "high":
                    score_decimal += Decimal('0.1')

            return max(Decimal('0.0'), min(Decimal('1.0'), score_decimal))

        except Exception as e:
            self.logger.error(f"Error scoring by business characteristics: {e}")
            return Decimal('0.5')

    def _score_by_financial_health(
        self,
        methodology: MethodologyType,
        financial_score: FinancialScore
    ) -> Decimal:
        """Score methodology based on financial health"""
        try:
            score_decimal = Decimal('0.5')  # Base score
            growth_potential_decimal = to_decimal(financial_score.growth_potential) if hasattr(financial_score, 'growth_potential') else Decimal('0')
            cash_flow_quality_decimal = to_decimal(financial_score.cash_flow_quality) if hasattr(financial_score, 'cash_flow_quality') else Decimal('0')
            revenue_stability_decimal = to_decimal(financial_score.revenue_stability) if hasattr(financial_score, 'revenue_stability') else Decimal('0')
            profitability_decimal = to_decimal(financial_score.profitability) if hasattr(financial_score, 'profitability') else Decimal('0')
            overall_score_decimal = to_decimal(financial_score.overall_score) if hasattr(financial_score, 'overall_score') else Decimal('0')
            asset_quality_decimal = to_decimal(financial_score.asset_quality) if hasattr(financial_score, 'asset_quality') else Decimal('0')
            debt_level_decimal = to_decimal(financial_score.debt_level) if hasattr(financial_score, 'debt_level') else Decimal('0')

            # DCF scoring
            if methodology == MethodologyType.DCF:
                if growth_potential_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.3')
                if cash_flow_quality_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.2')
                if revenue_stability_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.1')
                if profitability_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.1')

            # Multiples scoring
            elif methodology == MethodologyType.MULTIPLES:
                if revenue_stability_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.3')
                if profitability_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.2')
                if overall_score_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.1')
                if cash_flow_quality_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.1')

            # Asset-based scoring
            elif methodology == MethodologyType.ASSET_BASED:
                if asset_quality_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.4')
                if debt_level_decimal > Decimal('0.6'):  # Lower debt is better
                    score_decimal += Decimal('0.2')
                if overall_score_decimal < Decimal('0.5'):  # Lower overall score
                    score_decimal += Decimal('0.1')

            # Synthesized scoring
            elif methodology == MethodologyType.SYNTHESIZED:
                if overall_score_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.3')
                if revenue_stability_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.2')
                if profitability_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.1')

            return max(Decimal('0.0'), min(Decimal('1.0'), score_decimal))

        except Exception as e:
            self.logger.error(f"Error scoring by financial health: {e}")
            return Decimal('0.5')

    def _score_by_owner_dependency(
        self,
        methodology: MethodologyType,
        owner_score: OwnerScore
    ) -> Decimal:
        """Score methodology based on owner dependency"""
        try:
            score_decimal = Decimal('0.5')  # Base score
            dependency_level_decimal = to_decimal(owner_score.dependency_level) if hasattr(owner_score, 'dependency_level') else Decimal('0')
            delegation_capability_decimal = to_decimal(owner_score.delegation_capability) if hasattr(owner_score, 'delegation_capability') else Decimal('0')
            succession_planning_decimal = to_decimal(owner_score.succession_planning) if hasattr(owner_score, 'succession_planning') else Decimal('0')
            expertise_level_decimal = to_decimal(owner_score.expertise_level) if hasattr(owner_score, 'expertise_level') else Decimal('0')
            time_commitment_decimal = to_decimal(owner_score.time_commitment) if hasattr(owner_score, 'time_commitment') else Decimal('0')

            # DCF scoring
            if methodology == MethodologyType.DCF:
                if dependency_level_decimal < Decimal('0.5'):  # Lower dependency
                    score_decimal += Decimal('0.3')
                if delegation_capability_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.2')
                if succession_planning_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.1')
                if expertise_level_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.1')

            # Multiples scoring
            elif methodology == MethodologyType.MULTIPLES:
                if dependency_level_decimal > Decimal('0.6'):  # Higher dependency
                    score_decimal += Decimal('0.3')
                if delegation_capability_decimal < Decimal('0.4'):
                    score_decimal += Decimal('0.2')
                if succession_planning_decimal < Decimal('0.4'):
                    score_decimal += Decimal('0.1')
                if time_commitment_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.1')

            # Asset-based scoring
            elif methodology == MethodologyType.ASSET_BASED:
                if dependency_level_decimal > Decimal('0.7'):  # High dependency
                    score_decimal += Decimal('0.2')
                if delegation_capability_decimal < Decimal('0.3'):
                    score_decimal += Decimal('0.2')
                if succession_planning_decimal < Decimal('0.3'):
                    score_decimal += Decimal('0.1')

            # Synthesized scoring
            elif methodology == MethodologyType.SYNTHESIZED:
                if dependency_level_decimal < Decimal('0.4'):  # Low dependency
                    score_decimal += Decimal('0.3')
                if delegation_capability_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.2')
                if expertise_level_decimal > Decimal('0.8'):
                    score_decimal += Decimal('0.1')

            return max(Decimal('0.0'), min(Decimal('1.0'), score_decimal))

        except Exception as e:
            self.logger.error(f"Error scoring by owner dependency: {e}")
            return Decimal('0.5')

    def _score_by_market_context(
        self,
        methodology: MethodologyType,
        market_score: MarketScore
    ) -> Decimal:
        """Score methodology based on market context"""
        try:
            score_decimal = Decimal('0.5')  # Base score
            market_growth_decimal = to_decimal(market_score.market_growth) if hasattr(market_score, 'market_growth') else Decimal('0')
            market_size_decimal = to_decimal(market_score.market_size) if hasattr(market_score, 'market_size') else Decimal('0')
            competition_level_decimal = to_decimal(market_score.competition_level) if hasattr(market_score, 'competition_level') else Decimal('0')
            barriers_to_entry_decimal = to_decimal(market_score.barriers_to_entry) if hasattr(market_score, 'barriers_to_entry') else Decimal('0')
            customer_demand_decimal = to_decimal(market_score.customer_demand) if hasattr(market_score, 'customer_demand') else Decimal('0')
            overall_score_decimal = to_decimal(market_score.overall_score) if hasattr(market_score, 'overall_score') else Decimal('0')

            # DCF scoring
            if methodology == MethodologyType.DCF:
                if market_growth_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.3')
                if market_size_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.2')
                if competition_level_decimal < Decimal('0.4'):  # Low competition
                    score_decimal += Decimal('0.1')
                if barriers_to_entry_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.1')

            # Multiples scoring
            elif methodology == MethodologyType.MULTIPLES:
                if competition_level_decimal > Decimal('0.6'):  # High competition
                    score_decimal += Decimal('0.3')
                if market_size_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.2')
                if customer_demand_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.1')
                if barriers_to_entry_decimal < Decimal('0.4'):  # Low barriers
                    score_decimal += Decimal('0.1')

            # Asset-based scoring
            elif methodology == MethodologyType.ASSET_BASED:
                if barriers_to_entry_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.3')
                if competition_level_decimal < Decimal('0.3'):  # Very low competition
                    score_decimal += Decimal('0.2')
                if market_size_decimal < Decimal('0.4'):  # Small market
                    score_decimal += Decimal('0.1')

            # Synthesized scoring
            elif methodology == MethodologyType.SYNTHESIZED:
                if overall_score_decimal > Decimal('0.7'):
                    score_decimal += Decimal('0.3')
                if market_size_decimal > Decimal('0.6'):
                    score_decimal += Decimal('0.2')
                if competition_level_decimal > Decimal('0.5'):
                    score_decimal += Decimal('0.1')

            return max(Decimal('0.0'), min(Decimal('1.0'), score_decimal))

        except Exception as e:
            self.logger.error(f"Error scoring by market context: {e}")
            return Decimal('0.5')

    def _score_by_industry_rules(
        self,
        methodology: MethodologyType,
        business_context: BusinessContext,
        industry_rules: Dict[str, Any]
    ) -> Decimal:
        """Score methodology based on industry rules"""
        try:
            score_decimal = Decimal('0.5')  # Base score

            industry = business_context.industry.lower()

            # Get industry preferences
            preferences = industry_rules.get("industry_preferences", {})
            if industry in preferences:
                preferred_methodology = preferences[industry]
                if methodology.value == preferred_methodology:
                    score_decimal += Decimal('0.3')
                else:
                    score_decimal -= Decimal('0.1')

            # Technology industry scoring
            if industry in ["technology", "software", "saas"]:
                if methodology == MethodologyType.DCF:
                    score_decimal += Decimal('0.2')
                elif methodology == MethodologyType.MULTIPLES:
                    score_decimal += Decimal('0.1')

            # Manufacturing industry scoring
            elif industry in ["manufacturing", "industrial"]:
                if methodology == MethodologyType.ASSET_BASED:
                    score_decimal += Decimal('0.3')
                elif methodology == MethodologyType.MULTIPLES:
                    score_decimal += Decimal('0.2')
                elif methodology == MethodologyType.DCF:
                    score_decimal += Decimal('0.1')

            # Retail industry scoring
            elif industry in ["retail", "ecommerce"]:
                if methodology == MethodologyType.MULTIPLES:
                    score_decimal += Decimal('0.3')
                elif methodology == MethodologyType.DCF:
                    score_decimal += Decimal('0.1')

            # Services industry scoring
            elif industry in ["services", "consulting"]:
                if methodology == MethodologyType.MULTIPLES:
                    score_decimal += Decimal('0.2')
                elif methodology == MethodologyType.DCF:
                    score_decimal += Decimal('0.1')

            # Healthcare industry scoring
            elif industry in ["healthcare", "pharmaceutical"]:
                if methodology == MethodologyType.DCF:
                    score_decimal += Decimal('0.3')
                elif methodology == MethodologyType.MULTIPLES:
                    score_decimal += Decimal('0.1')

            # Finance industry scoring
            elif industry in ["finance", "banking"]:
                if methodology == MethodologyType.DCF:
                    score_decimal += Decimal('0.2')
                elif methodology == MethodologyType.MULTIPLES:
                    score_decimal += Decimal('0.1')

            return max(Decimal('0.0'), min(Decimal('1.0'), score_decimal))

        except Exception as e:
            self.logger.error(f"Error scoring by industry rules: {e}")
            return Decimal('0.5')

    def _calculate_weighted_score(
        self,
        business_score: Decimal,
        financial_score: Decimal,
        owner_score: Decimal,
        market_score: Decimal,
        industry_score: Decimal
    ) -> Decimal:
        """Calculate weighted final score"""
        try:
            # Weight factors
            business_weight_decimal = Decimal('0.25')
            financial_weight_decimal = Decimal('0.20')
            owner_weight_decimal = Decimal('0.15')
            market_weight_decimal = Decimal('0.15')
            industry_weight_decimal = Decimal('0.25')

            # Convert scores to Decimal if needed
            business_score_decimal = to_decimal(business_score) if not isinstance(business_score, Decimal) else business_score
            financial_score_decimal = to_decimal(financial_score) if not isinstance(financial_score, Decimal) else financial_score
            owner_score_decimal = to_decimal(owner_score) if not isinstance(owner_score, Decimal) else owner_score
            market_score_decimal = to_decimal(market_score) if not isinstance(market_score, Decimal) else market_score
            industry_score_decimal = to_decimal(industry_score) if not isinstance(industry_score, Decimal) else industry_score

            # Calculate weighted score
            weighted_score_decimal = (
                business_score_decimal * business_weight_decimal +
                financial_score_decimal * financial_weight_decimal +
                owner_score_decimal * owner_weight_decimal +
                market_score_decimal * market_weight_decimal +
                industry_score_decimal * industry_weight_decimal
            )

            return max(Decimal('0.0'), min(Decimal('1.0'), weighted_score_decimal))

        except Exception as e:
            self.logger.error(f"Error calculating weighted score: {e}")
            return Decimal('0.5')

    def _apply_confidence_adjustments(
        self,
        score: Decimal,
        criteria: SelectionCriteria
    ) -> Decimal:
        """Apply confidence-based adjustments to score"""
        try:
            adjusted_score_decimal = to_decimal(score) if not isinstance(score, Decimal) else score

            # High regulatory complexity reduces confidence
            if criteria.business_characteristics.regulatory_environment == "high":
                adjusted_score_decimal *= Decimal('0.9')

            # High technology dependency increases confidence for tech methodologies
            if criteria.business_characteristics.technology_dependency == "high":
                adjusted_score_decimal *= Decimal('1.05')

            # High asset intensity increases confidence for asset-based methodologies
            if criteria.business_characteristics.asset_intensity == "high":
                adjusted_score_decimal *= Decimal('1.05')

            # High growth potential increases confidence for DCF
            growth_potential_decimal = to_decimal(criteria.financial_health.growth_potential) if hasattr(criteria.financial_health, 'growth_potential') else Decimal('0')
            if growth_potential_decimal > Decimal('0.7'):
                adjusted_score_decimal *= Decimal('1.05')

            # High owner dependency reduces confidence
            dependency_level_decimal = to_decimal(criteria.owner_dependency.dependency_level) if hasattr(criteria.owner_dependency, 'dependency_level') else Decimal('0')
            if dependency_level_decimal > Decimal('0.8'):
                adjusted_score_decimal *= Decimal('0.9')

            # High market potential increases confidence
            market_overall_decimal = to_decimal(criteria.market_context.overall_score) if hasattr(criteria.market_context, 'overall_score') else Decimal('0')
            if market_overall_decimal > Decimal('0.8'):
                adjusted_score_decimal *= Decimal('1.05')

            return max(Decimal('0.0'), min(Decimal('1.0'), adjusted_score_decimal))

        except Exception as e:
            self.logger.error(f"Error applying confidence adjustments: {e}")
            return to_decimal(score) if not isinstance(score, Decimal) else score

    def _build_scoring_weights(self) -> Dict[str, Decimal]:
        """Build scoring weights for methodology selection"""
        return {
            "business_characteristics": 0.25,
            "financial_health": 0.20,
            "owner_dependency": 0.15,
            "market_context": 0.15,
            "industry_rules": 0.25
        }

    def _build_methodology_scores(self) -> Dict[str, Dict[str, Decimal]]:
        """Build methodology scoring rules"""
        return {
            "dcf": {
                "base_score": 0.8,
                "growth_weight": 0.3,
                "complexity_weight": 0.2,
                "accuracy_weight": 0.3
            },
            "multiples": {
                "base_score": 0.7,
                "simplicity_weight": 0.4,
                "market_weight": 0.3,
                "speed_weight": 0.3
            },
            "asset_based": {
                "base_score": 0.6,
                "asset_weight": 0.5,
                "liquidity_weight": 0.3,
                "stability_weight": 0.2
            },
            "synthesized": {
                "base_score": 0.9,
                "comprehensive_weight": 0.4,
                "accuracy_weight": 0.3,
                "complexity_weight": 0.3
            }
        }

    def _build_industry_preferences(self) -> Dict[str, Dict[str, Decimal]]:
        """Build industry-specific preferences"""
        return {
            "technology": {
                "dcf": 0.8,
                "multiples": 0.7,
                "asset_based": 0.3,
                "synthesized": 0.9
            },
            "manufacturing": {
                "dcf": 0.6,
                "multiples": 0.8,
                "asset_based": 0.9,
                "synthesized": 0.7
            },
            "retail": {
                "dcf": 0.5,
                "multiples": 0.9,
                "asset_based": 0.4,
                "synthesized": 0.6
            },
            "services": {
                "dcf": 0.7,
                "multiples": 0.8,
                "asset_based": 0.3,
                "synthesized": 0.8
            },
            "healthcare": {
                "dcf": 0.9,
                "multiples": 0.6,
                "asset_based": 0.5,
                "synthesized": 0.8
            },
            "finance": {
                "dcf": 0.8,
                "multiples": 0.7,
                "asset_based": 0.4,
                "synthesized": 0.9
            }
        }