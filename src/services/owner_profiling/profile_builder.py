"""
Profile Builder for Enhanced Owner Profiling

This module handles profile construction logic, including question generation,
technical requirements analysis, and report building.

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) provides profile analysis.
Titan (The Brain) manages conversation context and state.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, Any, List, Optional, Protocol
from datetime import datetime
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.owner_profiling.profiling_types import (
    OwnerRiskAssessmentReport, OWNER_QUESTIONS, TECHNICAL_REQUIREMENTS
)
from src.services.owner_profiling.owner_profiling_engine import OwnerProfile
from enum import Enum


# Type definitions (context comes from Titan's payload)
class BusinessType(str, Enum):
    """Business type enum for owner profiling"""
    SOLE_PROPRIETOR = "sole_proprietor"
    PARTNERSHIP = "partnership"
    LLC = "llc"
    CORPORATION = "corporation"


class IndustryCategory(str, Enum):
    """Industry category enum for owner profiling"""
    CONSTRUCTION = "construction"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    SERVICES = "services"
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    OTHER = "other"


class ConversationContext(Protocol):
    """Protocol for conversation context (actual implementation in Titan)"""
    business_type: BusinessType


logger = get_logger(__name__)


class ProfileBuilder:
    """
    Handles profile construction and question generation
    """

    def __init__(self):
        """Initialize the profile builder"""
        self.owner_questions = OWNER_QUESTIONS
        self.technical_requirements = TECHNICAL_REQUIREMENTS
        logger.info("✅ ProfileBuilder initialized")

    def determine_owner_questions(
        self, 
        context: ConversationContext,
        industry: IndustryCategory
    ) -> List[Dict]:
        """
        DEPRECATED: Question generation moved to Titan (The Brain).
        
        BRAIN & MUSCLE ARCHITECTURE:
        ValuationIQ returns analysis flags/profiles, not questions.
        Titan's TriageService generates questions via Claude.
        
        This method returns an empty list for backward compatibility.
        Use build_owner_profile() for the actual profiling analysis.
        """
        logger.debug("determine_owner_questions called - DEPRECATED, returning empty list")
        return []
    
    def _determine_owner_questions_legacy(
        self, 
        context: ConversationContext,
        industry: IndustryCategory
    ) -> List[Dict]:
        """LEGACY: Kept for reference only, not called."""
        questions = []

        # Always ask core owner questions
        questions.extend(self.owner_questions["time_commitment"])
        questions.extend(self.owner_questions["delegation_capability"])
        questions.extend(self.owner_questions["succession_planning"])
        questions.extend(self.owner_questions["customer_relationships"])
        questions.extend(self.owner_questions["supplier_relationships"])

        # Add industry-specific technical questions
        if industry.value in self.technical_requirements:
            technical_reqs = self.technical_requirements[industry.value]
            questions.extend([
                {
                    "question": f"What {industry.value} technical skills are required?",
                    "field": "technical_skills_required",
                    "type": "multi_select",
                    "options": technical_reqs["technical_skills"],
                    "risk_weight": 0.5,
                    "follow_up": f"How difficult would it be to find someone with these {industry.value} skills?"
                },
                {
                    "question": f"Do you have {industry.value} certifications?",
                    "field": "owner_certifications",
                    "type": "multi_select",
                    "options": technical_reqs["certifications"],
                    "risk_weight": 0.3,
                    "follow_up": "Are these certifications required to operate the business?"
                },
                {
                    "question": f"What {industry.value} equipment do you personally operate?",
                    "field": "equipment_operation",
                    "type": "multi_select",
                    "options": technical_reqs["equipment_knowledge"],
                    "risk_weight": 0.4,
                    "follow_up": "How much training would someone need to operate this equipment?"
                }
            ])

        # Add business type specific questions
        if context.business_type == BusinessType.SOLE_PROPRIETOR:
            questions.extend([
                {
                    "question": "Do you have any family members involved in the business?",
                    "field": "family_involvement",
                    "type": "boolean",
                    "risk_weight": 0.2,
                    "follow_up": "What role do they play in the business?"
                },
                {
                    "question": "What happens to the business if you're unavailable?",
                    "field": "business_continuity",
                    "type": "text",
                    "risk_weight": 0.3,
                    "follow_up": "How long could the business operate without you?"
                }
            ])

        return questions

    def build_owner_risk_report(
        self,
        owner_profile: OwnerProfile,
        industry: IndustryCategory,
        business_context: Dict[str, Any],
        risk_assessment: 'OwnerRiskAssessment'
    ) -> OwnerRiskAssessmentReport:
        """Build comprehensive owner risk assessment report"""

        # Generate immediate actions
        immediate_actions = self._generate_immediate_actions(owner_profile, risk_assessment)

        # Generate long-term improvements
        long_term_improvements = self._generate_long_term_improvements(owner_profile, risk_assessment)

        # Generate valuation adjustments
        valuation_adjustments = self._generate_valuation_adjustments(risk_assessment)

        return OwnerRiskAssessmentReport(
            owner_name=f"Owner-{owner_profile.id}",
            business_name=f"Business-{owner_profile.business_id}",
            assessment_date=datetime.now(),
            overall_risk_score=risk_assessment.overall_risk_score,
            risk_level=risk_assessment.risk_level.value,
            time_commitment_risk=risk_assessment.time_commitment_risk,
            technical_requirements_risk=risk_assessment.technical_requirements_risk,
            delegation_capability_risk=risk_assessment.delegation_capability_risk,
            succession_planning_risk=risk_assessment.succession_planning_risk,
            hours_per_week=owner_profile.hours_per_week,
            delegation_capability=owner_profile.delegation_capability,
            succession_plan=owner_profile.succession_plan,
            technical_skills=owner_profile.primary_tasks,
            certifications=[],  # Not available in current OwnerProfile
            risk_factors=risk_assessment.risk_factors,
            mitigation_recommendations=risk_assessment.mitigation_recommendations,
            due_diligence_notes=risk_assessment.due_diligence_notes,
            valuation_impact=risk_assessment.valuation_impact,
            transferability_assessment=risk_assessment.transferability_assessment,
            immediate_actions=immediate_actions,
            long_term_improvements=long_term_improvements,
            valuation_adjustments=valuation_adjustments
        )

    def _generate_immediate_actions(
        self,
        owner_profile: OwnerProfile,
        risk_assessment: 'OwnerRiskAssessment'
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

    def _generate_long_term_improvements(
        self,
        owner_profile: OwnerProfile,
        risk_assessment: 'OwnerRiskAssessment'
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

    def _generate_valuation_adjustments(self, risk_assessment: 'OwnerRiskAssessment') -> List[str]:
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
