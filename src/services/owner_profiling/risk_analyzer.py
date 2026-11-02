"""
Risk Analyzer for Enhanced Owner Profiling

This module handles all risk analysis logic for owner profiling,
including risk calculation, factor identification, and mitigation recommendations.

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) provides risk analysis.
Titan (The Brain) manages conversation context and state.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.owner_profiling.profiling_types import (
    RiskLevel, OwnerRiskAssessment, RISK_ASSESSMENT_RULES
)
from src.services.owner_profiling.owner_profiling_engine import OwnerProfile
from src.services.owner_profiling.profile_builder import IndustryCategory

logger = get_logger(__name__)


class RiskAnalyzer:
    """
    Handles comprehensive risk analysis for owner profiling
    """

    def __init__(self):
        """Initialize the risk analyzer"""
        self.risk_rules = RISK_ASSESSMENT_RULES
        logger.info("✅ RiskAnalyzer initialized")

    def calculate_time_commitment_risk(self, hours_per_week: int) -> Decimal:
        """Calculate time commitment risk score"""
        if hours_per_week > 50:
            return Decimal('0.9')  # Very high risk
        elif hours_per_week > 40:
            return Decimal('0.7')  # High risk
        elif hours_per_week > 30:
            return Decimal('0.5')  # Medium risk
        else:
            return Decimal('0.2')  # Low risk

    def calculate_technical_requirements_risk(
        self, 
        primary_tasks: List[str], 
        industry: IndustryCategory,
        technical_requirements: Dict[str, Dict]
    ) -> Decimal:
        """Calculate technical requirements risk score"""
        # Get industry-specific technical requirements
        industry_requirements = technical_requirements.get(industry.value, {})
        required_skills = industry_requirements.get("technical_skills", [])

        # Calculate skill coverage
        if not required_skills:
            return Decimal('0.5')  # Default risk if no industry requirements

        skill_coverage_decimal = Decimal(str(len(set(primary_tasks) & set(required_skills)))) / Decimal(str(len(required_skills)))

        # Higher risk if owner has many required skills (harder to replace)
        if skill_coverage_decimal > Decimal('0.8'):
            return Decimal('0.8')  # High risk
        elif skill_coverage_decimal > Decimal('0.6'):
            return Decimal('0.6')  # Medium risk
        elif skill_coverage_decimal > Decimal('0.4'):
            return Decimal('0.4')  # Low risk
        else:
            return Decimal('0.2')  # Very low risk

    def calculate_delegation_capability_risk(self, delegation_capability: int) -> Decimal:
        """Calculate delegation capability risk score"""
        if delegation_capability < 4:
            return Decimal('0.9')  # Very high risk
        elif delegation_capability < 6:
            return Decimal('0.7')  # High risk
        elif delegation_capability < 8:
            return Decimal('0.5')  # Medium risk
        else:
            return Decimal('0.2')  # Low risk

    def calculate_succession_planning_risk(self, succession_plan: bool) -> Decimal:
        """Calculate succession planning risk score"""
        if succession_plan:
            return Decimal('0.2')  # Low risk
        else:
            return Decimal('0.8')  # High risk

    def determine_risk_level(self, risk_score: Decimal) -> RiskLevel:
        """Determine risk level based on score"""
        risk_score_decimal = to_decimal(risk_score)
        if risk_score_decimal > Decimal('0.8'):
            return RiskLevel.VERY_HIGH
        elif risk_score_decimal > Decimal('0.6'):
            return RiskLevel.HIGH
        elif risk_score_decimal > Decimal('0.4'):
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def identify_risk_factors(
        self,
        owner_profile: OwnerProfile,
        time_commitment_risk: Decimal,
        technical_requirements_risk: Decimal,
        delegation_capability_risk: Decimal,
        succession_planning_risk: Decimal
    ) -> List[str]:
        """Identify specific risk factors"""
        risk_factors = []
        time_risk_decimal = to_decimal(time_commitment_risk) if not isinstance(time_commitment_risk, Decimal) else time_commitment_risk
        tech_risk_decimal = to_decimal(technical_requirements_risk) if not isinstance(technical_requirements_risk, Decimal) else technical_requirements_risk
        delegation_risk_decimal = to_decimal(delegation_capability_risk) if not isinstance(delegation_capability_risk, Decimal) else delegation_capability_risk
        succession_risk_decimal = to_decimal(succession_planning_risk) if not isinstance(succession_planning_risk, Decimal) else succession_planning_risk

        if time_risk_decimal > Decimal('0.7'):
            risk_factors.append(f"Owner works {owner_profile.hours_per_week} hours per week (high time commitment)")

        if tech_risk_decimal > Decimal('0.7'):
            risk_factors.append(f"Owner has {len(owner_profile.primary_tasks)} primary tasks (high technical dependency)")

        if delegation_risk_decimal > Decimal('0.7'):
            risk_factors.append(f"Owner delegation capability: {owner_profile.delegation_capability}/10 (poor delegation)")

        if succession_risk_decimal > Decimal('0.7'):
            risk_factors.append("No succession plan in place")

        if owner_profile.hours_per_week > 50:
            risk_factors.append("Owner works excessive hours (>50/week)")

        if owner_profile.delegation_capability < 5:
            risk_factors.append("Poor delegation capability (<5/10)")

        if not owner_profile.succession_plan:
            risk_factors.append("No succession plan documented")

        return risk_factors

    def generate_mitigation_recommendations(
        self,
        owner_profile: OwnerProfile,
        risk_factors: List[str]
    ) -> List[str]:
        """Generate risk mitigation recommendations"""
        recommendations = []

        if owner_profile.hours_per_week > 50:
            recommendations.append("Reduce owner hours through delegation and hiring")

        if owner_profile.delegation_capability < 5:
            recommendations.append("Develop management team and delegation skills")

        if not owner_profile.succession_plan:
            recommendations.append("Create succession plan and document key processes")

        if len(owner_profile.primary_tasks) > 5:
            recommendations.append("Document technical processes and train backup personnel")

        if owner_profile.hours_per_week > 40:
            recommendations.append("Implement cross-training for key roles")

        if owner_profile.delegation_capability < 6:
            recommendations.append("Invest in management development and training")

        return recommendations

    def generate_due_diligence_notes(self, owner_profile: OwnerProfile) -> str:
        """Generate due diligence notes"""
        notes = []

        notes.append(f"Owner works {owner_profile.hours_per_week} hours per week")
        notes.append(f"Delegation capability: {owner_profile.delegation_capability}/10")
        notes.append(f"Succession plan: {'Yes' if owner_profile.succession_plan else 'No'}")
        notes.append(f"Primary tasks: {len(owner_profile.primary_tasks)} areas")

        if owner_profile.hours_per_week > 50:
            notes.append("HIGH RISK: Owner works excessive hours")

        if owner_profile.delegation_capability < 5:
            notes.append("HIGH RISK: Poor delegation capability")

        if not owner_profile.succession_plan:
            notes.append("HIGH RISK: No succession plan")

        return "; ".join(notes)

    def generate_valuation_impact_assessment(self, risk_score: Decimal) -> str:
        """Generate valuation impact assessment"""
        if risk_score > 0.8:
            return "VERY HIGH IMPACT: 15-20% valuation reduction recommended due to high owner dependency"
        elif risk_score > 0.6:
            return "HIGH IMPACT: 10-15% valuation reduction recommended due to owner dependency"
        elif risk_score > 0.4:
            return "MEDIUM IMPACT: 5-10% valuation reduction recommended due to moderate owner dependency"
        else:
            return "LOW IMPACT: Minimal valuation impact due to low owner dependency"

    def generate_transferability_assessment(
        self,
        owner_profile: OwnerProfile,
        risk_score: Decimal
    ) -> str:
        """Generate transferability assessment"""
        if risk_score > 0.8:
            return "VERY HIGH TRANSFERABILITY RISK: Business highly dependent on owner, difficult to transfer"
        elif risk_score > 0.6:
            return "HIGH TRANSFERABILITY RISK: Business moderately dependent on owner, transferability concerns"
        elif risk_score > 0.4:
            return "MEDIUM TRANSFERABILITY RISK: Some owner dependency, manageable transferability"
        else:
            return "LOW TRANSFERABILITY RISK: Low owner dependency, good transferability"

    def generate_immediate_actions(
        self,
        owner_profile: OwnerProfile,
        risk_assessment: OwnerRiskAssessment
    ) -> List[str]:
        """Generate immediate actions for risk mitigation"""
        actions = []

        if risk_assessment.time_commitment_risk > 0.7:
            actions.append("Immediately reduce owner hours through delegation")

        if risk_assessment.delegation_capability_risk > 0.7:
            actions.append("Start management training and development program")

        if risk_assessment.succession_planning_risk > 0.7:
            actions.append("Begin succession planning process")

        if risk_assessment.technical_requirements_risk > 0.7:
            actions.append("Document critical technical processes")

        return actions

    def generate_long_term_improvements(
        self,
        owner_profile: OwnerProfile,
        risk_assessment: OwnerRiskAssessment
    ) -> List[str]:
        """Generate long-term improvement recommendations"""
        improvements = []

        improvements.append("Develop comprehensive management team")
        improvements.append("Implement cross-training programs")
        improvements.append("Create detailed succession plan")
        improvements.append("Document all critical business processes")
        improvements.append("Establish key performance indicators for delegation")
        improvements.append("Regular management development and training")

        return improvements

    def generate_valuation_adjustments(self, risk_assessment: OwnerRiskAssessment) -> List[str]:
        """Generate valuation adjustment recommendations"""
        adjustments = []

        if risk_assessment.overall_risk_score > 0.8:
            adjustments.append("Apply 15-20% valuation reduction for high owner dependency")
        elif risk_assessment.overall_risk_score > 0.6:
            adjustments.append("Apply 10-15% valuation reduction for owner dependency")
        elif risk_assessment.overall_risk_score > 0.4:
            adjustments.append("Apply 5-10% valuation reduction for moderate owner dependency")
        else:
            adjustments.append("Minimal valuation adjustment needed")

        return adjustments