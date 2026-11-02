from src.utils.exceptions import DCFCalculationError, MethodologyError, MultiplesCalculationError

"""
Decision Tree

This module contains decision tree logic for methodology selection
based on business characteristics and rules.
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


class DecisionTree:
    """Decision tree for methodology selection"""

    def __init__(self):
        """Initialize the decision tree"""
        self.logger = logger
        self.decision_rules = self._build_decision_rules()
        self.industry_trees = self._build_industry_trees()
        self.financial_trees = self._build_financial_trees()
        self.owner_trees = self._build_owner_trees()
        self.market_trees = self._build_market_trees()

    def make_decision(
        self,
        criteria: SelectionCriteria
    ) -> MethodologySelection:
        """
        Make methodology selection decision using decision tree

        Args:
            criteria: Selection criteria

        Returns:
            Methodology selection decision
        """
        try:
            self.logger.info("Making methodology selection decision",
                           industry=criteria.business_characteristics.industry,
                           business_type=criteria.business_characteristics.business_type)

            # Start with root decision
            decision = self._evaluate_root_decision(criteria)

            # Apply industry-specific decisions
            decision = self._apply_industry_decisions(decision, criteria)

            # Apply financial health decisions
            decision = self._apply_financial_decisions(decision, criteria)

            # Apply owner dependency decisions
            decision = self._apply_owner_decisions(decision, criteria)

            # Apply market context decisions
            decision = self._apply_market_decisions(decision, criteria)

            # Final decision refinement
            decision = self._refine_final_decision(decision, criteria)

            self.logger.info("Methodology selection decision completed",
                           primary_methodology=decision.primary_methodology.value,
                           confidence_score=decision.confidence_score)

            return decision

        except MethodologyError as e:
            self.logger.error(f"Error making methodology selection decision: {e}")
            return self._get_default_decision()

    def _evaluate_root_decision(
        self,
        criteria: SelectionCriteria
    ) -> MethodologySelection:
        """Evaluate root decision based on business characteristics"""
        try:
            business_context = criteria.business_characteristics

            # High growth businesses
            if business_context.growth_rate > 0.2:  # 20%+ growth
                if business_context.technology_dependency == "high":
                    return self._create_decision(
                        MethodologyType.DCF,
                        None,
                        Decimal('0.9'),
                        "High growth technology business requires DCF analysis",
                        ["growth_rate", "technology_dependency"],
                        ["Market expansion potential", "Technology advantage sustainability"]
                    )
                else:
                    return self._create_decision(
                        MethodologyType.DCF,
                        MethodologyType.MULTIPLES,
                        Decimal('0.8'),
                        "High growth business requires DCF analysis",
                        ["growth_rate"],
                        ["Growth sustainability", "Market expansion"]
                    )

            # High asset intensity businesses
            elif business_context.asset_intensity == "high":
                if business_context.capital_intensity == "high":
                    return self._create_decision(
                        MethodologyType.ASSET_BASED,
                        MethodologyType.MULTIPLES,
                        Decimal('0.8'),
                        "High asset intensity business requires asset-based valuation",
                        ["asset_intensity", "capital_intensity"],
                        ["Asset utilization efficiency", "Asset maintenance requirements"]
                    )
                else:
                    return self._create_decision(
                        MethodologyType.MULTIPLES,
                        MethodologyType.ASSET_BASED,
                        Decimal('0.7'),
                        "Asset-intensive business suitable for multiples valuation",
                        ["asset_intensity"],
                        ["Asset efficiency", "Market comparables"]
                    )

            # Mature businesses
            elif business_context.market_maturity == "mature":
                if business_context.revenue > 1000000:  # > 1M revenue
                    return self._create_decision(
                        MethodologyType.MULTIPLES,
                        MethodologyType.DCF,
                        Decimal('0.8'),
                        "Mature business with established revenue suitable for multiples",
                        ["market_maturity", "revenue"],
                        ["Market comparables", "Historical performance"]
                    )
                else:
                    return self._create_decision(
                        MethodologyType.MULTIPLES,
                        None,
                        Decimal('0.7'),
                        "Mature business suitable for multiples valuation",
                        ["market_maturity"],
                        ["Market comparables"]
                    )

            # Technology businesses
            elif business_context.technology_dependency == "high":
                if business_context.business_type in ["saas", "software", "platform"]:
                    return self._create_decision(
                        MethodologyType.MULTIPLES,
                        MethodologyType.DCF,
                        Decimal('0.9'),
                        "Technology business suitable for ARR multiples",
                        ["technology_dependency", "business_type"],
                        ["Recurring revenue stability", "Customer lifetime value"]
                    )
                else:
                    return self._create_decision(
                        MethodologyType.DCF,
                        MethodologyType.MULTIPLES,
                        Decimal('0.8'),
                        "Technology business requires DCF analysis",
                        ["technology_dependency"],
                        ["Technology advantage", "Market expansion potential"]
                    )

            # High regulatory businesses
            elif business_context.regulatory_environment == "high":
                return self._create_decision(
                    MethodologyType.DCF,
                    MethodologyType.MULTIPLES,
                    Decimal('0.8'),
                    "High regulatory environment requires DCF analysis",
                    ["regulatory_environment"],
                    ["Regulatory compliance", "Risk assessment"]
                )

            # Default decision
            else:
                if business_context.revenue > 500000:  # > 500k revenue
                    return self._create_decision(
                        MethodologyType.MULTIPLES,
                        MethodologyType.DCF,
                        Decimal('0.7'),
                        "Established business suitable for multiples valuation",
                        ["revenue"],
                        ["Market comparables"]
                    )
                else:
                    return self._create_decision(
                        MethodologyType.DCF,
                        MethodologyType.MULTIPLES,
                        Decimal('0.6'),
                        "Growing business requires DCF analysis",
                        ["growth_rate"],
                        ["Growth potential", "Market expansion"]
                    )

        except DCFCalculationError as e:
            self.logger.error(f"Error evaluating root decision: {e}")
            return self._get_default_decision()

    def _apply_industry_decisions(
        self,
        decision: MethodologySelection,
        criteria: SelectionCriteria
    ) -> MethodologySelection:
        """Apply industry-specific decisions"""
        try:
            industry = criteria.business_characteristics.industry.lower()

            # Technology industry decisions
            if industry in ["technology", "software", "saas"]:
                if criteria.business_characteristics.business_type in ["saas", "platform"]:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Technology industry prefers ARR multiples for SaaS businesses."
                    decision.key_factors.append("industry_preference")
                else:
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " Technology industry requires DCF for growth potential."
                    decision.key_factors.append("industry_preference")

            # Manufacturing industry decisions
            elif industry in ["manufacturing", "industrial"]:
                if criteria.business_characteristics.asset_intensity == "high":
                    decision.primary_methodology = MethodologyType.ASSET_BASED
                    decision.reasoning += " Manufacturing industry with high asset intensity requires asset-based valuation."
                    decision.key_factors.append("industry_preference")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Manufacturing industry suitable for multiples valuation."
                    decision.key_factors.append("industry_preference")

            # Retail industry decisions
            elif industry in ["retail", "ecommerce"]:
                if criteria.business_characteristics.revenue > 1000000:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Retail industry with established revenue suitable for multiples."
                    decision.key_factors.append("industry_preference")
                else:
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " Retail industry requires DCF for growth analysis."
                    decision.key_factors.append("industry_preference")

            # Services industry decisions
            elif industry in ["services", "consulting"]:
                if criteria.business_characteristics.customer_concentration == "high":
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " Services industry with high customer concentration requires DCF analysis."
                    decision.key_factors.append("industry_preference")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Services industry suitable for multiples valuation."
                    decision.key_factors.append("industry_preference")

            # Healthcare industry decisions
            elif industry in ["healthcare", "pharmaceutical"]:
                if criteria.business_characteristics.regulatory_environment == "high":
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " Healthcare industry with high regulatory environment requires DCF analysis."
                    decision.key_factors.append("industry_preference")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Healthcare industry suitable for multiples valuation."
                    decision.key_factors.append("industry_preference")

            # Finance industry decisions
            elif industry in ["finance", "banking"]:
                if criteria.business_characteristics.regulatory_environment == "high":
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " Finance industry with high regulatory environment requires DCF analysis."
                    decision.key_factors.append("industry_preference")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Finance industry suitable for multiples valuation."
                    decision.key_factors.append("industry_preference")

            return decision

        except DCFCalculationError as e:
            self.logger.error(f"Error applying industry decisions: {e}")
            return decision

    def _apply_financial_decisions(
        self,
        decision: MethodologySelection,
        criteria: SelectionCriteria
    ) -> MethodologySelection:
        """Apply financial health decisions"""
        try:
            financial_score = criteria.financial_health

            # High financial health
            if financial_score.overall_score > 0.8:
                if financial_score.growth_potential > 0.7:
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " High financial health with strong growth potential requires DCF analysis."
                    decision.key_factors.append("financial_health")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " High financial health suitable for multiples valuation."
                    decision.key_factors.append("financial_health")

            # Medium financial health
            elif financial_score.overall_score > 0.6:
                if financial_score.revenue_stability > 0.7:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Medium financial health with stable revenue suitable for multiples."
                    decision.key_factors.append("financial_health")
                else:
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " Medium financial health requires DCF analysis."
                    decision.key_factors.append("financial_health")

            # Low financial health
            else:
                if financial_score.asset_quality > 0.6:
                    decision.primary_methodology = MethodologyType.ASSET_BASED
                    decision.reasoning += " Low financial health with good asset quality requires asset-based valuation."
                    decision.key_factors.append("financial_health")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Low financial health suitable for multiples valuation."
                    decision.key_factors.append("financial_health")

            return decision

        except MultiplesCalculationError as e:
            self.logger.error(f"Error applying financial decisions: {e}")
            return decision

    def _apply_owner_decisions(
        self,
        decision: MethodologySelection,
        criteria: SelectionCriteria
    ) -> MethodologySelection:
        """Apply owner dependency decisions"""
        try:
            owner_score = criteria.owner_dependency

            # High owner dependency
            if owner_score.dependency_level > 0.8:
                if owner_score.delegation_capability < 0.3:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " High owner dependency with low delegation requires simple multiples valuation."
                    decision.key_factors.append("owner_dependency")
                else:
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " High owner dependency with good delegation requires DCF analysis."
                    decision.key_factors.append("owner_dependency")

            # Medium owner dependency
            elif owner_score.dependency_level > 0.5:
                if owner_score.succession_planning > 0.6:
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " Medium owner dependency with good succession planning requires DCF analysis."
                    decision.key_factors.append("owner_dependency")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Medium owner dependency suitable for multiples valuation."
                    decision.key_factors.append("owner_dependency")

            # Low owner dependency
            else:
                if owner_score.expertise_level > 0.7:
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " Low owner dependency with high expertise requires DCF analysis."
                    decision.key_factors.append("owner_dependency")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Low owner dependency suitable for multiples valuation."
                    decision.key_factors.append("owner_dependency")

            return decision

        except DCFCalculationError as e:
            self.logger.error(f"Error applying owner decisions: {e}")
            return decision

    def _apply_market_decisions(
        self,
        decision: MethodologySelection,
        criteria: SelectionCriteria
    ) -> MethodologySelection:
        """Apply market context decisions"""
        try:
            market_score = criteria.market_context

            # High market potential
            if market_score.overall_score > 0.8:
                if market_score.market_growth > 0.7:
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " High market potential with strong growth requires DCF analysis."
                    decision.key_factors.append("market_context")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " High market potential suitable for multiples valuation."
                    decision.key_factors.append("market_context")

            # Medium market potential
            elif market_score.overall_score > 0.6:
                if market_score.competition_level < 0.4:  # Low competition
                    decision.primary_methodology = MethodologyType.DCF
                    decision.reasoning += " Medium market potential with low competition requires DCF analysis."
                    decision.key_factors.append("market_context")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Medium market potential suitable for multiples valuation."
                    decision.key_factors.append("market_context")

            # Low market potential
            else:
                if market_score.barriers_to_entry > 0.6:
                    decision.primary_methodology = MethodologyType.ASSET_BASED
                    decision.reasoning += " Low market potential with high barriers requires asset-based valuation."
                    decision.key_factors.append("market_context")
                else:
                    decision.primary_methodology = MethodologyType.MULTIPLES
                    decision.reasoning += " Low market potential suitable for multiples valuation."
                    decision.key_factors.append("market_context")

            return decision

        except MultiplesCalculationError as e:
            self.logger.error(f"Error applying market decisions: {e}")
            return decision

    def _refine_final_decision(
        self,
        decision: MethodologySelection,
        criteria: SelectionCriteria
    ) -> MethodologySelection:
        """Refine final decision based on all factors"""
        try:
            # Calculate confidence score based on all factors
            confidence_factors = []

            # Business characteristics confidence
            if criteria.business_characteristics.growth_rate > 0.15:
                confidence_factors.append(Decimal('0.1'))
            if criteria.business_characteristics.technology_dependency == "high":
                confidence_factors.append(Decimal('0.1'))
            if criteria.business_characteristics.asset_intensity == "high":
                confidence_factors.append(Decimal('0.1'))

            # Financial health confidence
            if criteria.financial_health.overall_score > 0.7:
                confidence_factors.append(Decimal('0.1'))
            if criteria.financial_health.growth_potential > 0.7:
                confidence_factors.append(Decimal('0.1'))

            # Owner dependency confidence
            if criteria.owner_dependency.dependency_level < 0.5:
                confidence_factors.append(Decimal('0.1'))
            if criteria.owner_dependency.delegation_capability > 0.6:
                confidence_factors.append(Decimal('0.1'))

            # Market context confidence
            if criteria.market_context.overall_score > 0.7:
                confidence_factors.append(Decimal('0.1'))
            if criteria.market_context.market_growth > 0.7:
                confidence_factors.append(Decimal('0.1'))

            # Calculate final confidence
            base_confidence = Decimal('0.7')
            confidence_adjustment = sum(confidence_factors)
            decision.confidence_score = min(Decimal('1.0'), base_confidence + confidence_adjustment)

            # Set expected accuracy based on confidence
            decision.expected_accuracy = decision.confidence_score * Decimal('0.9')

            # Set time estimate based on methodology
            time_estimates = {
                MethodologyType.DCF: "3-4 weeks",
                MethodologyType.MULTIPLES: "1-2 weeks",
                MethodologyType.ASSET_BASED: "2-3 weeks",
                MethodologyType.SYNTHESIZED: "4-6 weeks"
            }
            decision.time_estimate = time_estimates.get(decision.primary_methodology, "2-3 weeks")

            return decision

        except DCFCalculationError as e:
            self.logger.error(f"Error refining final decision: {e}")
            return decision

    def _create_decision(
        self,
        primary_methodology: MethodologyType,
        secondary_methodology: Optional[MethodologyType],
        confidence_score: Decimal,
        reasoning: str,
        key_factors: List[str],
        special_considerations: List[str]
    ) -> MethodologySelection:
        """Create methodology selection decision"""
        return MethodologySelection(
            primary_methodology=primary_methodology,
            secondary_methodology=secondary_methodology,
            confidence_score=confidence_score,
            reasoning=reasoning,
            key_factors=key_factors,
            special_considerations=special_considerations,
            expected_accuracy=confidence_score * Decimal('0.9'),
            time_estimate="2-3 weeks",
            methodology_weights={},
            business_score=Decimal('0.0'),
            financial_score=Decimal('0.0'),
            owner_score=Decimal('0.0'),
            market_score=Decimal('0.0')
        )

    def _get_default_decision(self) -> MethodologySelection:
        """Get default methodology selection decision"""
        return self._create_decision(
            MethodologyType.MULTIPLES,
            MethodologyType.DCF,
            Decimal('0.6'),
            "Default methodology selection",
            ["revenue", "industry"],
            ["Requires manual review"]
        )

    def _build_decision_rules(self) -> Dict[str, Any]:
        """Build decision rules for methodology selection"""
        return {
            "growth_threshold": Decimal('0.2'),
            "asset_intensity_threshold": Decimal('0.7'),
            "revenue_threshold": 1000000,
            "financial_health_threshold": Decimal('0.7'),
            "owner_dependency_threshold": Decimal('0.8'),
            "market_potential_threshold": Decimal('0.8')
        }

    def _build_industry_trees(self) -> Dict[str, Dict[str, Any]]:
        """Build industry-specific decision trees"""
        return {
            "technology": {
                "saas": MethodologyType.MULTIPLES,
                "software": MethodologyType.DCF,
                "platform": MethodologyType.MULTIPLES,
                "default": MethodologyType.DCF
            },
            "manufacturing": {
                "high_asset": MethodologyType.ASSET_BASED,
                "medium_asset": MethodologyType.MULTIPLES,
                "low_asset": MethodologyType.DCF,
                "default": MethodologyType.MULTIPLES
            },
            "retail": {
                "high_revenue": MethodologyType.MULTIPLES,
                "medium_revenue": MethodologyType.DCF,
                "low_revenue": MethodologyType.DCF,
                "default": MethodologyType.MULTIPLES
            }
        }

    def _build_financial_trees(self) -> Dict[str, Dict[str, Any]]:
        """Build financial health decision trees"""
        return {
            "high_health": {
                "high_growth": MethodologyType.DCF,
                "medium_growth": MethodologyType.MULTIPLES,
                "low_growth": MethodologyType.MULTIPLES
            },
            "medium_health": {
                "stable_revenue": MethodologyType.MULTIPLES,
                "unstable_revenue": MethodologyType.DCF
            },
            "low_health": {
                "good_assets": MethodologyType.ASSET_BASED,
                "poor_assets": MethodologyType.MULTIPLES
            }
        }

    def _build_owner_trees(self) -> Dict[str, Dict[str, Any]]:
        """Build owner dependency decision trees"""
        return {
            "high_dependency": {
                "low_delegation": MethodologyType.MULTIPLES,
                "high_delegation": MethodologyType.DCF
            },
            "medium_dependency": {
                "good_succession": MethodologyType.DCF,
                "poor_succession": MethodologyType.MULTIPLES
            },
            "low_dependency": {
                "high_expertise": MethodologyType.DCF,
                "low_expertise": MethodologyType.MULTIPLES
            }
        }

    def _build_market_trees(self) -> Dict[str, Dict[str, Any]]:
        """Build market context decision trees"""
        return {
            "high_potential": {
                "high_growth": MethodologyType.DCF,
                "medium_growth": MethodologyType.MULTIPLES
            },
            "medium_potential": {
                "low_competition": MethodologyType.DCF,
                "high_competition": MethodologyType.MULTIPLES
            },
            "low_potential": {
                "high_barriers": MethodologyType.ASSET_BASED,
                "low_barriers": MethodologyType.MULTIPLES
            }
        }