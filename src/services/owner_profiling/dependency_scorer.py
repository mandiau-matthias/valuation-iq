from src.utils.exceptions import DependencyError

"""
Owner Dependency Scoring Service

Calculates owner dependency scores and valuation adjustments based on
12-factor assessment of key person risk for SME valuations.

Author: Upswitch Engineering Team
Date: October 2025
Status: P0 Implementation
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
import logging
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = logging.getLogger(__name__)


class DependencyLevel(Enum):
    """Owner dependency levels"""
    LOW = "low"           # 0-30% dependency
    MEDIUM = "medium"     # 30-60% dependency  
    HIGH = "high"         # 60-80% dependency
    CRITICAL = "critical" # 80-100% dependency


@dataclass
class DependencyScore:
    """Owner dependency scoring result"""
    overall_score: Decimal  # 0.0 to 1.0
    dependency_level: DependencyLevel
    adjustment_factor: Decimal  # -0.4 to 0.0 (negative adjustment)
    factor_scores: Dict[str, Decimal]
    recommendations: List[str]
    risk_summary: str


class OwnerDependencyScorer:
    """
    Scores owner dependency and calculates valuation adjustments

    This service analyzes 12-factor owner dependency assessment results
    and provides valuation adjustments based on key person risk.
    """

    def __init__(self):
        """Initialize the dependency scorer"""
        self.logger = logger
        self.answer_weights = self._initialize_answer_weights()
        self.factor_weights = self._initialize_factor_weights()

    def _initialize_answer_weights(self) -> Dict[str, Dict[str, Decimal]]:
        """Initialize answer weights for each question"""
        return {
            "client_relationships": {
                "I manage all key relationships personally": Decimal('1.0'),
                "I manage most, team handles some": Decimal('0.7'),
                "Team manages most, I handle key ones": Decimal('0.4'),
                "Team manages all relationships": Decimal('0.1')
            },
            "operations_management": {
                "I handle all operations personally": Decimal('1.0'),
                "I handle most, team does routine tasks": Decimal('0.7'),
                "Team handles most, I oversee key areas": Decimal('0.4'),
                "Team handles all operations independently": Decimal('0.1')
            },
            "business_development": {
                "I generate all new business personally": Decimal('1.0'),
                "I generate most, team helps with some": Decimal('0.7'),
                "Team generates most, I handle key prospects": Decimal('0.4'),
                "Team generates all new business": Decimal('0.1')
            },
            "technical_expertise": {
                "I have all critical technical knowledge": Decimal('1.0'),
                "I have most, team has some specialized knowledge": Decimal('0.7'),
                "Team has most, I have key strategic knowledge": Decimal('0.4'),
                "Team has all technical knowledge": Decimal('0.1')
            },
            "team_strength": {
                "Very weak - business would struggle significantly": Decimal('1.0'),
                "Weak - would need major restructuring": Decimal('0.7'),
                "Moderate - could continue with some challenges": Decimal('0.4'),
                "Strong - could operate independently": Decimal('0.1')
            },
            "process_documentation": {
                "No documentation - everything is in my head": Decimal('1.0'),
                "Some documentation - key processes written down": Decimal('0.7'),
                "Good documentation - most processes documented": Decimal('0.4'),
                "Excellent documentation - everything is documented": Decimal('0.1')
            },
            "succession_planning": {
                "No succession plan": Decimal('1.0'),
                "Informal plan - identified potential successors": Decimal('0.7'),
                "Formal plan - documented succession process": Decimal('0.4'),
                "Complete plan - tested and ready to execute": Decimal('0.1')
            },
            "revenue_concentration": {
                "80-100% of revenue depends on me": Decimal('1.0'),
                "60-80% of revenue depends on me": Decimal('0.7'),
                "40-60% of revenue depends on me": Decimal('0.4'),
                "0-40% of revenue depends on me": Decimal('0.1')
            },
            "strategic_decisions": {
                "I make all strategic decisions alone": Decimal('1.0'),
                "I make most, team provides input": Decimal('0.7'),
                "Team makes most, I make key decisions": Decimal('0.4'),
                "Team makes all strategic decisions": Decimal('0.1')
            },
            "external_relationships": {
                "I manage all key relationships personally": Decimal('1.0'),
                "I manage most, team handles some": Decimal('0.7'),
                "Team manages most, I handle key ones": Decimal('0.4'),
                "Team manages all relationships": Decimal('0.1')
            },
            "brand_reputation": {
                "Yes - I am the brand, very personal": Decimal('1.0'),
                "Somewhat - brand is associated with me": Decimal('0.7'),
                "Partially - brand has some independence": Decimal('0.4'),
                "No - brand is independent of me": Decimal('0.1')
            },
            "transition_readiness": {
                "Very long - 2+ years with significant risk": Decimal('1.0'),
                "Long - 1-2 years with moderate risk": Decimal('0.7'),
                "Moderate - 6-12 months with some risk": Decimal('0.4'),
                "Quick - 3-6 months with minimal risk": Decimal('0.1')
            }
        }

    def _initialize_factor_weights(self) -> Dict[str, Decimal]:
        """Initialize factor weights for overall scoring"""
        return {
            "client_relationships": Decimal('0.20'),      # 20% - Most critical
            "operations_management": Decimal('0.15'),      # 15% - High impact
            "business_development": Decimal('0.15'),       # 15% - High impact
            "technical_expertise": Decimal('0.10'),       # 10% - Medium impact
            "team_strength": Decimal('0.10'),             # 10% - Medium impact
            "process_documentation": Decimal('0.08'),     # 8% - Medium impact
            "succession_planning": Decimal('0.08'),       # 8% - Medium impact
            "revenue_concentration": Decimal('0.07'),     # 7% - Medium impact
            "strategic_decisions": Decimal('0.05'),       # 5% - Lower impact
            "external_relationships": Decimal('0.05'),    # 5% - Lower impact
            "brand_reputation": Decimal('0.04'),          # 4% - Lower impact
            "transition_readiness": Decimal('0.03')       # 3% - Lower impact
        }

    def calculate_owner_dependency_score(self, answers: Dict[str, str]) -> DependencyScore:
        """
        Calculate owner dependency score from assessment answers

        Args:
            answers: Dictionary of question_id -> answer_text

        Returns:
            DependencyScore with overall score, level, and recommendations
        """
        try:
            self.logger.info("Calculating owner dependency score",
                           answers_count=len(answers))

            # Calculate factor scores
            factor_scores = {}
            weighted_sum_decimal = Decimal('0.0')
            total_weight_decimal = Decimal('0.0')

            for question_id, answer in answers.items():
                if question_id in self.answer_weights and answer in self.answer_weights[question_id]:
                    # Get answer weight (0.1 to 1.0)
                    answer_weight = self.answer_weights[question_id][answer]

                    # Get factor weight
                    factor_weight = self.factor_weights.get(question_id, Decimal('0.0'))

                    # Calculate weighted score
                    factor_score_decimal = answer_weight * factor_weight
                    factor_scores[question_id] = answer_weight

                    weighted_sum_decimal += factor_score_decimal
                    total_weight_decimal += factor_weight
                else:
                    self.logger.warning(f"Unknown question or answer: {question_id} = {answer}")

            # Calculate overall dependency score (0.0 to 1.0)
            if total_weight_decimal > Decimal('0'):
                overall_score = weighted_sum_decimal / total_weight_decimal
            else:
                overall_score = Decimal('0.0')

            # Determine dependency level
            dependency_level = self._determine_dependency_level(overall_score)

            # Calculate adjustment factor (-0.4 to 0.0)
            adjustment_factor = self._calculate_adjustment_factor(overall_score)

            # Generate recommendations
            recommendations = self._generate_recommendations(overall_score, factor_scores)

            # Generate risk summary
            risk_summary = self._generate_risk_summary(overall_score, dependency_level)

            result = DependencyScore(
                overall_score=overall_score,
                dependency_level=dependency_level,
                adjustment_factor=adjustment_factor,
                factor_scores=factor_scores,
                recommendations=recommendations,
                risk_summary=risk_summary
            )

            self.logger.info("Owner dependency score calculated",
                           overall_score=from_decimal(overall_score),
                           dependency_level=dependency_level.value,
                           adjustment_factor=from_decimal(adjustment_factor))

            return result

        except DependencyError as e:
            self.logger.error("Failed to calculate owner dependency score", error=str(e))
            raise

    def _determine_dependency_level(self, score: Decimal) -> DependencyLevel:
        """Determine dependency level from score"""
        score_decimal = to_decimal(score) if not isinstance(score, Decimal) else score
        if score_decimal >= Decimal('0.8'):
            return DependencyLevel.CRITICAL
        elif score_decimal >= Decimal('0.6'):
            return DependencyLevel.HIGH
        elif score_decimal >= Decimal('0.3'):
            return DependencyLevel.MEDIUM
        else:
            return DependencyLevel.LOW

    def _calculate_adjustment_factor(self, score: Decimal) -> Decimal:
        """Calculate valuation adjustment factor from dependency score"""
        # Linear mapping: 0.0 score = 0% adjustment, 1.0 score = -40% adjustment
        score_decimal = to_decimal(score) if not isinstance(score, Decimal) else score
        return Decimal('-0.4') * score_decimal

    def _generate_recommendations(self, score: Decimal, factor_scores: Dict[str, Decimal]) -> List[str]:
        """Generate recommendations based on dependency score and factor scores"""
        recommendations = []
        score_decimal = to_decimal(score) if not isinstance(score, Decimal) else score

        if score_decimal >= Decimal('0.8'):
            recommendations.extend([
                "URGENT: Document all business processes and procedures",
                "URGENT: Build a strong management team to reduce dependency",
                "URGENT: Diversify client relationships to reduce concentration risk",
                "URGENT: Create formal succession plans and test them",
                "URGENT: Reduce personal brand dependency"
            ])
        elif score_decimal >= Decimal('0.6'):
            recommendations.extend([
                "HIGH PRIORITY: Delegate more operational tasks to team members",
                "HIGH PRIORITY: Document key business processes",
                "HIGH PRIORITY: Build team capabilities and cross-training",
                "HIGH PRIORITY: Diversify revenue sources and client base",
                "HIGH PRIORITY: Develop formal succession plans"
            ])
        elif score_decimal >= Decimal('0.3'):
            recommendations.extend([
                "MEDIUM PRIORITY: Continue building team strength and capabilities",
                "MEDIUM PRIORITY: Document remaining undocumented processes",
                "MEDIUM PRIORITY: Develop and test succession plans",
                "MEDIUM PRIORITY: Reduce remaining personal dependencies",
                "MEDIUM PRIORITY: Build more independent revenue streams"
            ])
        else:
            recommendations.extend([
                "MAINTAIN: Continue current practices - you're doing well!",
                "OPTIMIZE: Fine-tune team processes for even better efficiency",
                "GROW: Focus on scaling and growth opportunities",
                "EXPLORE: Consider expansion or acquisition opportunities"
            ])

        # Add specific recommendations based on factor scores
        client_relationships_score = factor_scores.get("client_relationships", Decimal('0'))
        if not isinstance(client_relationships_score, Decimal):
            client_relationships_score = to_decimal(client_relationships_score)
        if client_relationships_score > Decimal('0.7'):
            recommendations.append("Focus on diversifying client relationships")

        process_doc_score = factor_scores.get("process_documentation", Decimal('0'))
        if not isinstance(process_doc_score, Decimal):
            process_doc_score = to_decimal(process_doc_score)
        if process_doc_score > Decimal('0.7'):
            recommendations.append("Prioritize documenting all business processes")

        team_strength_score = factor_scores.get("team_strength", Decimal('0'))
        if not isinstance(team_strength_score, Decimal):
            team_strength_score = to_decimal(team_strength_score)
        if team_strength_score > Decimal('0.7'):
            recommendations.append("Invest in team development and training")

        succession_score = factor_scores.get("succession_planning", Decimal('0'))
        if not isinstance(succession_score, Decimal):
            succession_score = to_decimal(succession_score)
        if succession_score > Decimal('0.7'):
            recommendations.append("Create and test formal succession plans")

        return recommendations

    def _generate_risk_summary(self, score: Decimal, level: DependencyLevel) -> str:
        """Generate risk summary based on dependency score"""
        score_decimal = to_decimal(score) if not isinstance(score, Decimal) else score
        score_pct = from_decimal(score_decimal * Decimal('100'), precision=0)
        if level == DependencyLevel.CRITICAL:
            return f"CRITICAL dependency risk ({score_pct:.0f}%). Business is highly dependent on owner. Significant valuation impact expected."
        elif level == DependencyLevel.HIGH:
            return f"HIGH dependency risk ({score_pct:.0f}%). Business has substantial owner dependency. Moderate valuation impact expected."
        elif level == DependencyLevel.MEDIUM:
            return f"MEDIUM dependency risk ({score_pct:.0f}%). Business has moderate owner dependency. Some valuation impact expected."
        else:
            return f"LOW dependency risk ({score_pct:.0f}%). Business has minimal owner dependency. Minimal valuation impact expected."

    def get_adjustment_explanation(self, adjustment_factor: Decimal) -> str:
        """Get human-readable explanation of valuation adjustment"""
        adjustment_decimal = to_decimal(adjustment_factor) if not isinstance(adjustment_factor, Decimal) else adjustment_factor
        percentage = from_decimal(abs(adjustment_decimal * Decimal('100')), precision=0)

        if adjustment_decimal <= Decimal('-0.3'):
            return f"High owner dependency reduces business value by {percentage:.0f}% due to key person risk and transferability concerns."
        elif adjustment_decimal <= Decimal('-0.2'):
            return f"Moderate owner dependency reduces business value by {percentage:.0f}% due to transferability risks."
        elif adjustment_decimal <= Decimal('-0.1'):
            return f"Some owner dependency reduces business value by {percentage:.0f}% due to minor transferability concerns."
        else:
            return "Minimal owner dependency has no significant impact on business value."

    def should_apply_adjustment(
        self,
        company_size: int,
        revenue: Decimal,
        industry: str,
        dependency_score: Decimal
    ) -> bool:
        """
        Determine if owner dependency adjustment should be applied

        Args:
            company_size: Number of employees
            revenue: Annual revenue
            industry: Industry type
            dependency_score: Calculated dependency score

        Returns:
            True if adjustment should be applied
        """
        dependency_score_decimal = to_decimal(dependency_score) if not isinstance(dependency_score, Decimal) else dependency_score
        revenue_decimal = to_decimal(revenue) if not isinstance(revenue, Decimal) else revenue
        
        # Always apply if dependency score is high
        if dependency_score_decimal >= Decimal('0.6'):
            return True

        # Apply for SMEs with moderate dependency
        if (company_size < 50 or revenue_decimal < Decimal('10000000')) and dependency_score_decimal >= Decimal('0.3'):
            return True

        # Apply for owner-dependent industries
        owner_dependent_industries = [
            "professional_services", "consulting", "agency", 
            "personal_services", "creative_services"
        ]
        if industry in owner_dependent_industries and dependency_score_decimal >= Decimal('0.2'):
            return True

        return False
