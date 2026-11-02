from src.utils.exceptions import BusinessTypeError, CalculationError, DataValidationError, MultiplesCalculationError

"""
Time Commitment Analyzer

This module handles time commitment analysis for the enhanced
owner profiling system.

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
This analyzer performs ANALYSIS and returns FLAGS/METRICS.
Question generation has been deprecated - Titan handles all user interactions.
"""

from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from .profiling_types import (
    RiskLevel,
    TimeCommitmentAnalysis,
    OwnerQuestion,
    OwnerQuestionSet
)

logger = get_logger(__name__)


class TimeCommitmentAnalyzer:
    """Analyzes owner time commitment and dependency risks"""

    def __init__(self):
        """Initialize the time commitment analyzer"""
        self.logger = logger
        self.time_thresholds = self._build_time_thresholds()
        self.risk_factors = self._build_risk_factors()
        self.analysis_questions = self._build_analysis_questions()

    def analyze_time_commitment(
        self,
        owner_profile: Dict[str, Any],
        business_context: Dict[str, Any]
    ) -> TimeCommitmentAnalysis:
        """
        Analyze owner time commitment

        Args:
            owner_profile: Owner profile data
            business_context: Business context information

        Returns:
            Time commitment analysis
        """
        try:
            self.logger.info("Analyzing time commitment",
                           hours_per_week=owner_profile.get("hours_per_week", 0),
                           business_type=business_context.get("business_type", "unknown"))

            # Extract time commitment data
            hours_per_week = owner_profile.get("hours_per_week", 40)
            peak_periods = owner_profile.get("peak_periods", [])
            seasonal_variations = owner_profile.get("seasonal_variations", {})

            # Calculate risk score
            risk_score = self._calculate_time_commitment_risk(hours_per_week)
            risk_level = self._determine_risk_level(risk_score)

            # Analyze critical vs delegatable hours
            critical_hours = self._calculate_critical_hours(hours_per_week, business_context)
            delegatable_hours = self._calculate_delegatable_hours(hours_per_week, business_context)

            # Calculate delegation potential
            delegation_potential = self._calculate_delegation_potential(
                delegatable_hours, hours_per_week
            )

            # Calculate succession readiness
            succession_readiness = self._calculate_succession_readiness(
                owner_profile, business_context
            )

            analysis = TimeCommitmentAnalysis(
                hours_per_week=hours_per_week,
                risk_score=risk_score,
                risk_level=risk_level,
                critical_hours=critical_hours,
                delegatable_hours=delegatable_hours,
                peak_periods=peak_periods,
                seasonal_variations=seasonal_variations,
                delegation_potential=delegation_potential,
                succession_readiness=succession_readiness
            )

            self.logger.info("Time commitment analysis completed",
                           risk_score=from_decimal(risk_score),
                           risk_level=risk_level.value,
                           delegation_potential=from_decimal(delegation_potential))

            return analysis

        except Exception as e:
            self.logger.error(f"Error analyzing time commitment: {e}")
            return self._get_default_time_analysis()

    def generate_time_commitment_questions(
        self,
        business_context: Dict[str, Any],
        owner_profile: Dict[str, Any]
    ) -> List[OwnerQuestion]:
        """
        DEPRECATED: Question generation moved to Titan (The Brain).
        
        BRAIN & MUSCLE ARCHITECTURE:
        ValuationIQ returns analysis flags/metrics, not questions.
        Titan's TriageService generates questions via Claude.
        
        This method returns an empty list for backward compatibility.
        Use analyze_time_commitment() for the actual analysis.
        """
        self.logger.debug("generate_time_commitment_questions called - DEPRECATED, returning empty list")
        return []
    
    def _generate_time_commitment_questions_legacy(
        self,
        business_context: Dict[str, Any],
        owner_profile: Dict[str, Any]
    ) -> List[OwnerQuestion]:
        """LEGACY: Kept for reference only, not called."""
        try:
            self.logger.info("Generating time commitment questions",
                           business_type=business_context.get("business_type", "unknown"))

            questions = []

            # Core time commitment questions
            questions.extend(self._get_core_time_questions())

            # Business-specific questions
            business_type = business_context.get("business_type", "").lower()
            if business_type in ["retail", "ecommerce"]:
                questions.extend(self._get_retail_time_questions())
            elif business_type in ["manufacturing", "production"]:
                questions.extend(self._get_manufacturing_time_questions())
            elif business_type in ["services", "consulting"]:
                questions.extend(self._get_services_time_questions())

            # Peak period questions
            questions.extend(self._get_peak_period_questions())

            # Seasonal variation questions
            questions.extend(self._get_seasonal_questions())

            # Delegation questions
            questions.extend(self._get_delegation_questions())

            # Prioritize questions by importance
            prioritized_questions = self._prioritize_questions(questions)

            self.logger.info("Time commitment questions generated",
                           total_questions=len(prioritized_questions))

            return prioritized_questions

        except Exception as e:
            self.logger.error(f"Error generating time commitment questions: {e}")
            return []

    def _calculate_time_commitment_risk(self, hours_per_week: int) -> Decimal:
        """Calculate time commitment risk score"""
        try:
            # Risk increases with hours per week
            if hours_per_week >= 70:
                return Decimal('0.9')  # Very high risk
            elif hours_per_week >= 60:
                return Decimal('0.8')  # High risk
            elif hours_per_week >= 50:
                return Decimal('0.6')  # Medium-high risk
            elif hours_per_week >= 40:
                return Decimal('0.4')  # Medium risk
            elif hours_per_week >= 30:
                return Decimal('0.2')  # Low risk
            else:
                return Decimal('0.1')  # Very low risk
        except CalculationError as e:
            self.logger.error(f"Error calculating time commitment risk: {e}")
            return Decimal('0.5')

    def _determine_risk_level(self, risk_score: Decimal) -> RiskLevel:
        """Determine risk level based on score"""
        try:
            risk_score_decimal = to_decimal(risk_score) if not isinstance(risk_score, Decimal) else risk_score
            if risk_score_decimal >= Decimal('0.8'):
                return RiskLevel.VERY_HIGH
            elif risk_score_decimal >= Decimal('0.6'):
                return RiskLevel.HIGH
            elif risk_score_decimal >= Decimal('0.4'):
                return RiskLevel.MEDIUM
            else:
                return RiskLevel.LOW
        except Exception as e:
            self.logger.error(f"Error determining risk level: {e}")
            return RiskLevel.MEDIUM

    def _calculate_critical_hours(
        self,
        hours_per_week: int,
        business_context: Dict[str, Any]
    ) -> int:
        """Calculate critical hours that cannot be delegated"""
        try:
            business_type = business_context.get("business_type", "").lower()

            # Base critical hours (20% of total hours)
            base_critical = int(hours_per_week * 0.2)

            # Adjust based on business type
            if business_type in ["consulting", "services"]:
                # Services require more owner involvement
                base_critical = int(hours_per_week * 0.3)
            elif business_type in ["manufacturing", "production"]:
                # Manufacturing can be more automated
                base_critical = int(hours_per_week * 0.15)
            elif business_type in ["retail", "ecommerce"]:
                # Retail has more routine tasks
                base_critical = int(hours_per_week * 0.25)

            return max(5, base_critical)  # Minimum 5 hours

        except BusinessTypeError as e:
            self.logger.error(f"Error calculating critical hours: {e}")
            return int(hours_per_week * 0.2)

    def _calculate_delegatable_hours(
        self,
        hours_per_week: int,
        business_context: Dict[str, Any]
    ) -> int:
        """Calculate hours that can be delegated"""
        try:
            critical_hours = self._calculate_critical_hours(hours_per_week, business_context)
            delegatable_hours = hours_per_week - critical_hours

            return max(0, delegatable_hours)

        except CalculationError as e:
            self.logger.error(f"Error calculating delegatable hours: {e}")
            return int(hours_per_week * 0.5)

    def _calculate_delegation_potential(
        self,
        delegatable_hours: int,
        total_hours: int
    ) -> Decimal:
        """Calculate delegation potential score"""
        try:
            if total_hours == 0:
                return Decimal('0.0')

            delegatable_decimal = Decimal(str(delegatable_hours))
            total_decimal = Decimal(str(total_hours))
            potential = delegatable_decimal / total_decimal
            return max(Decimal('0.0'), min(Decimal('1.0'), potential))

        except CalculationError as e:
            self.logger.error(f"Error calculating delegation potential: {e}")
            return Decimal('0.5')

    def _calculate_succession_readiness(
        self,
        owner_profile: Dict[str, Any],
        business_context: Dict[str, Any]
    ) -> Decimal:
        """Calculate succession readiness score"""
        try:
            # Base score from delegation capability
            delegation_capability = owner_profile.get("delegation_capability", 5)
            delegation_decimal = Decimal(str(delegation_capability))
            base_score_decimal = delegation_decimal / Decimal('10.0')

            # Adjust based on business complexity
            business_type = business_context.get("business_type", "").lower()
            if business_type in ["consulting", "services"]:
                # Services are more dependent on owner expertise
                base_score_decimal *= Decimal('0.8')
            elif business_type in ["manufacturing", "production"]:
                # Manufacturing can be more systematized
                base_score_decimal *= Decimal('1.1')
            elif business_type in ["retail", "ecommerce"]:
                # Retail has more routine operations
                base_score_decimal *= Decimal('1.0')

            return max(Decimal('0.0'), min(Decimal('1.0'), base_score_decimal))

        except BusinessTypeError as e:
            self.logger.error(f"Error calculating succession readiness: {e}")
            return Decimal('0.5')

    def _get_core_time_questions(self) -> List[OwnerQuestion]:
        """Get core time commitment questions"""
        try:
            return [
                OwnerQuestion(
                    question_id="time_hours_per_week",
                    question_text="How many hours per week do you work in the business?",
                    question_type="time",
                    importance=10,
                    follow_up_questions=[
                        "Are these hours consistent throughout the year?",
                        "Do you work more hours during certain periods?"
                    ],
                    expected_response_type="number",
                    validation_rules={"min": 1, "max": 168, "required": True}
                ),
                OwnerQuestion(
                    question_id="time_work_schedule",
                    question_text="What is your typical work schedule?",
                    question_type="time",
                    importance=8,
                    follow_up_questions=[
                        "Do you work weekends?",
                        "Do you work evenings or nights?"
                    ],
                    expected_response_type="text",
                    validation_rules={"required": True}
                ),
                OwnerQuestion(
                    question_id="time_vacation",
                    question_text="How much vacation time do you take per year?",
                    question_type="time",
                    importance=7,
                    follow_up_questions=[
                        "Can you take vacation without affecting the business?",
                        "Who handles the business when you're away?"
                    ],
                    expected_response_type="number",
                    validation_rules={"min": 0, "max": 52, "required": True}
                )
            ]
        except DataValidationError as e:
            self.logger.error(f"Error getting core time questions: {e}")
            return []

    def _get_retail_time_questions(self) -> List[OwnerQuestion]:
        """Get retail-specific time questions"""
        try:
            return [
                OwnerQuestion(
                    question_id="time_retail_hours",
                    question_text="Do you work during store hours?",
                    question_type="time",
                    importance=8,
                    follow_up_questions=[
                        "Can you leave the store unattended?",
                        "Do you have staff to cover when you're not there?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                ),
                OwnerQuestion(
                    question_id="time_retail_seasons",
                    question_text="Do you work more hours during certain seasons?",
                    question_type="time",
                    importance=6,
                    follow_up_questions=[
                        "Which seasons are busiest?",
                        "How do you handle increased demand?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                )
            ]
        except MultiplesCalculationError as e:
            self.logger.error(f"Error getting retail time questions: {e}")
            return []

    def _get_manufacturing_time_questions(self) -> List[OwnerQuestion]:
        """Get manufacturing-specific time questions"""
        try:
            return [
                OwnerQuestion(
                    question_id="time_manufacturing_shifts",
                    question_text="Do you work multiple shifts?",
                    question_type="time",
                    importance=8,
                    follow_up_questions=[
                        "How many shifts do you work?",
                        "Do you have shift supervisors?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                ),
                OwnerQuestion(
                    question_id="time_manufacturing_production",
                    question_text="Are you involved in daily production decisions?",
                    question_type="time",
                    importance=7,
                    follow_up_questions=[
                        "Can production continue without you?",
                        "Do you have production managers?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                )
            ]
        except DataValidationError as e:
            self.logger.error(f"Error getting manufacturing time questions: {e}")
            return []

    def _get_services_time_questions(self) -> List[OwnerQuestion]:
        """Get services-specific time questions"""
        try:
            return [
                OwnerQuestion(
                    question_id="time_services_clients",
                    question_text="Do you work directly with clients?",
                    question_type="time",
                    importance=9,
                    follow_up_questions=[
                        "Can others handle client relationships?",
                        "Do you have client managers?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                ),
                OwnerQuestion(
                    question_id="time_services_projects",
                    question_text="Are you involved in all projects?",
                    question_type="time",
                    importance=8,
                    follow_up_questions=[
                        "Can projects continue without you?",
                        "Do you have project managers?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                )
            ]
        except DataValidationError as e:
            self.logger.error(f"Error getting services time questions: {e}")
            return []

    def _get_peak_period_questions(self) -> List[OwnerQuestion]:
        """Get peak period questions"""
        try:
            return [
                OwnerQuestion(
                    question_id="time_peak_periods",
                    question_text="Are there peak periods when you work more hours?",
                    question_type="time",
                    importance=7,
                    follow_up_questions=[
                        "Which periods are busiest?",
                        "How many more hours do you work during peak periods?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                ),
                OwnerQuestion(
                    question_id="time_peak_handling",
                    question_text="How do you handle increased demand during peak periods?",
                    question_type="time",
                    importance=6,
                    follow_up_questions=[
                        "Do you hire temporary staff?",
                        "Do you work longer hours yourself?"
                    ],
                    expected_response_type="multiple_choice",
                    response_options=["Work longer hours", "Hire temporary staff", "Delegate more", "Other"],
                    validation_rules={"required": True}
                )
            ]
        except MultiplesCalculationError as e:
            self.logger.error(f"Error getting peak period questions: {e}")
            return []

    def _get_seasonal_questions(self) -> List[OwnerQuestion]:
        """Get seasonal variation questions"""
        try:
            return [
                OwnerQuestion(
                    question_id="time_seasonal_variations",
                    question_text="Does your business have seasonal variations?",
                    question_type="time",
                    importance=6,
                    follow_up_questions=[
                        "Which seasons are busiest?",
                        "How do you handle seasonal changes?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                ),
                OwnerQuestion(
                    question_id="time_seasonal_planning",
                    question_text="How do you plan for seasonal variations?",
                    question_type="time",
                    importance=5,
                    follow_up_questions=[
                        "Do you adjust staffing levels?",
                        "Do you change your work schedule?"
                    ],
                    expected_response_type="text",
                    validation_rules={"required": True}
                )
            ]
        except DataValidationError as e:
            self.logger.error(f"Error getting seasonal questions: {e}")
            return []

    def _get_delegation_questions(self) -> List[OwnerQuestion]:
        """Get delegation questions"""
        try:
            return [
                OwnerQuestion(
                    question_id="time_delegation_capability",
                    question_text="Can you delegate tasks to others?",
                    question_type="time",
                    importance=9,
                    follow_up_questions=[
                        "What tasks can you delegate?",
                        "Who can handle delegated tasks?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                ),
                OwnerQuestion(
                    question_id="time_delegation_comfort",
                    question_text="How comfortable are you delegating tasks?",
                    question_type="time",
                    importance=8,
                    follow_up_questions=[
                        "What prevents you from delegating more?",
                        "How do you ensure quality when delegating?"
                    ],
                    expected_response_type="multiple_choice",
                    response_options=["Very comfortable", "Somewhat comfortable", "Not comfortable", "Never delegate"],
                    validation_rules={"required": True}
                )
            ]
        except MultiplesCalculationError as e:
            self.logger.error(f"Error getting delegation questions: {e}")
            return []

    def _prioritize_questions(self, questions: List[OwnerQuestion]) -> List[OwnerQuestion]:
        """Prioritize questions by importance"""
        try:
            return sorted(questions, key=lambda x: x.importance, reverse=True)
        except Exception as e:
            self.logger.error(f"Error prioritizing questions: {e}")
            return questions

    def _get_default_time_analysis(self) -> TimeCommitmentAnalysis:
        """Get default time commitment analysis"""
        return TimeCommitmentAnalysis(
            hours_per_week=40,
            risk_score=0.5,
            risk_level=RiskLevel.MEDIUM,
            critical_hours=8,
            delegatable_hours=32,
            peak_periods=[],
            seasonal_variations={},
            delegation_potential=0.5,
            succession_readiness=0.5
        )

    def _build_time_thresholds(self) -> Dict[str, int]:
        """Build time thresholds for analysis"""
        return {
            "very_high_risk": 70,
            "high_risk": 60,
            "medium_risk": 50,
            "low_risk": 40,
            "very_low_risk": 30
        }

    def _build_risk_factors(self) -> Dict[str, List[str]]:
        """Build risk factors for time commitment"""
        return {
            "high_hours": [
                "Working 60+ hours per week",
                "No vacation time",
                "Working weekends and holidays"
            ],
            "delegation_issues": [
                "Cannot delegate critical tasks",
                "No backup personnel",
                "Owner handles all decisions"
            ],
            "seasonal_dependency": [
                "High seasonal variations",
                "No planning for off-seasons",
                "Owner required during peak periods"
            ]
        }

    def _build_analysis_questions(self) -> List[OwnerQuestion]:
        """Build analysis questions"""
        return [
            OwnerQuestion(
                question_id="time_analysis_overall",
                question_text="How would you rate your overall time commitment to the business?",
                question_type="time",
                importance=10,
                follow_up_questions=[],
                expected_response_type="multiple_choice",
                response_options=["Very high", "High", "Medium", "Low", "Very low"]
            )
        ]