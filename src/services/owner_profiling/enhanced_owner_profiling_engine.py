"""
Enhanced Owner Profiling Engine - Refactored

This is the main orchestrator for the enhanced owner profiling engine,
providing comprehensive owner risk analysis for due diligence purposes.

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) provides owner risk analysis.
Titan (The Brain) manages conversation context and state.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from decimal import Decimal

# Internal imports
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.utils.exceptions import BusinessTypeError, ValuationEngineError
from src.errors.error_types import TemplateRenderError
from src.services.owner_profiling.owner_profiling_engine import OwnerProfile
from src.services.owner_profiling.profiling_types import (
    RiskLevel, OwnerRiskAssessment, OwnerRiskAssessmentReport,
    OWNER_QUESTIONS, TECHNICAL_REQUIREMENTS, RISK_ASSESSMENT_RULES
)
from src.services.owner_profiling.risk_analyzer import RiskAnalyzer
from src.services.owner_profiling.profile_builder import ProfileBuilder, IndustryCategory, ConversationContext

logger = get_logger(__name__)


class EnhancedOwnerProfilingEngineRefactored:
    """
    Enhanced owner profiling engine with comprehensive risk analysis
    """

    def __init__(self):
        """Initialize the enhanced owner profiling engine"""
        self.risk_analyzer = RiskAnalyzer()
        self.profile_builder = ProfileBuilder()

        logger.info("✅ EnhancedOwnerProfilingEngineRefactored initialized")

    async def determine_owner_questions(
        self, 
        context: ConversationContext,
        industry: IndustryCategory
    ) -> List[Dict]:
        """
        DEPRECATED: Question generation moved to Titan (The Brain).
        
        BRAIN & MUSCLE ARCHITECTURE:
        ValuationIQ returns risk assessments and flags, not questions.
        Titan's TriageService generates questions via Claude.
        
        Returns empty list for backward compatibility.
        Use assess_owner_risk() for the actual risk analysis.
        """
        logger.debug(f"determine_owner_questions called - DEPRECATED, returning empty list")
        return []

    async def assess_owner_risk(
        self,
        owner_profile: OwnerProfile,
        industry: IndustryCategory,
        business_context: Dict[str, Any]
    ) -> OwnerRiskAssessment:
        """
        Assess comprehensive owner risk for due diligence
        """
        try:
            logger.info(f"🔍 Assessing owner risk for profile {owner_profile.id}")

            # Calculate individual risk scores using risk analyzer
            time_commitment_risk = self.risk_analyzer.calculate_time_commitment_risk(
                owner_profile.hours_per_week
            )
            technical_requirements_risk = self.risk_analyzer.calculate_technical_requirements_risk(
                owner_profile.primary_tasks, industry, TECHNICAL_REQUIREMENTS
            )
            delegation_capability_risk = self.risk_analyzer.calculate_delegation_capability_risk(
                owner_profile.delegation_capability
            )
            succession_planning_risk = self.risk_analyzer.calculate_succession_planning_risk(
                owner_profile.succession_plan
            )

            # Calculate overall risk score
            overall_risk_score = (
                time_commitment_risk * 0.4 +
                technical_requirements_risk * 0.3 +
                delegation_capability_risk * 0.2 +
                succession_planning_risk * 0.1
            )

            # Determine risk level
            risk_level = self.risk_analyzer.determine_risk_level(overall_risk_score)

            # Identify risk factors
            risk_factors = self.risk_analyzer.identify_risk_factors(
                owner_profile, time_commitment_risk, technical_requirements_risk,
                delegation_capability_risk, succession_planning_risk
            )

            # Generate mitigation recommendations
            mitigation_recommendations = self.risk_analyzer.generate_mitigation_recommendations(
                owner_profile, risk_factors
            )

            # Generate due diligence notes
            due_diligence_notes = self.risk_analyzer.generate_due_diligence_notes(owner_profile)
            valuation_impact = self.risk_analyzer.generate_valuation_impact_assessment(overall_risk_score)
            transferability_assessment = self.risk_analyzer.generate_transferability_assessment(
                owner_profile, overall_risk_score
            )

            logger.info(f"✅ Owner risk assessment complete: {risk_level.value} risk")

            return OwnerRiskAssessment(
                overall_risk_score=overall_risk_score,
                risk_level=risk_level,
                time_commitment_risk=time_commitment_risk,
                technical_requirements_risk=technical_requirements_risk,
                delegation_capability_risk=delegation_capability_risk,
                succession_planning_risk=succession_planning_risk,
                risk_factors=risk_factors,
                mitigation_recommendations=mitigation_recommendations,
                due_diligence_notes=due_diligence_notes,
                valuation_impact=valuation_impact,
                transferability_assessment=transferability_assessment
            )

        except ValuationEngineError as e:
            logger.error(f"❌ Owner risk assessment failed: {str(e)}")
            # Return default risk assessment
            return OwnerRiskAssessment(
                overall_risk_score=0.5,
                risk_level=RiskLevel.MEDIUM,
                time_commitment_risk=0.5,
                technical_requirements_risk=0.5,
                delegation_capability_risk=0.5,
                succession_planning_risk=0.5,
                risk_factors=["Assessment error"],
                mitigation_recommendations=["Contact support"],
                due_diligence_notes="Risk assessment incomplete",
                valuation_impact="Unknown impact",
                transferability_assessment="Unknown transferability"
            )

    async def generate_owner_risk_report(
        self,
        owner_profile: OwnerProfile,
        industry: IndustryCategory,
        business_context: Dict[str, Any]
    ) -> OwnerRiskAssessmentReport:
        """Generate comprehensive owner risk assessment report"""

        try:
            logger.info(f"📊 Generating owner risk report for profile {owner_profile.id}")

            # Assess owner risk
            risk_assessment = await self.assess_owner_risk(owner_profile, industry, business_context)

            # Build comprehensive report
            report = self.profile_builder.build_owner_risk_report(
                owner_profile, industry, business_context, risk_assessment
            )

            logger.info(f"✅ Owner risk report generated successfully")
            return report

        except TemplateRenderError as e:
            logger.error(f"❌ Failed to generate owner risk report: {str(e)}")
            # Return default report
            return OwnerRiskAssessmentReport(
                owner_name=f"Owner-{owner_profile.id}",
                business_name=f"Business-{owner_profile.business_id}",
                assessment_date=datetime.now(),
                overall_risk_score=0.5,
                risk_level="medium",
                time_commitment_risk=0.5,
                technical_requirements_risk=0.5,
                delegation_capability_risk=0.5,
                succession_planning_risk=0.5,
                hours_per_week=owner_profile.hours_per_week,
                delegation_capability=owner_profile.delegation_capability,
                succession_plan=owner_profile.succession_plan,
                technical_skills=owner_profile.primary_tasks,
                certifications=[],  # Not available in current OwnerProfile
                risk_factors=["Report generation error"],
                mitigation_recommendations=["Contact support"],
                due_diligence_notes="Report generation incomplete",
                valuation_impact="Unknown impact",
                transferability_assessment="Unknown transferability",
                immediate_actions=["Contact support"],
                long_term_improvements=["Contact support"],
                valuation_adjustments=["Contact support"]
            )

    def get_technical_requirements(self, industry: IndustryCategory) -> Dict[str, Any]:
        """Get technical requirements for specific industry"""
        return TECHNICAL_REQUIREMENTS.get(industry.value, {})

    def get_risk_assessment_rules(self) -> Dict[str, Any]:
        """Get risk assessment rules"""
        return RISK_ASSESSMENT_RULES

    def get_owner_questions(self) -> Dict[str, List[Dict]]:
        """Get owner questions templates"""
        return OWNER_QUESTIONS