"""
Technical Assessment

This module handles technical requirements analysis for the enhanced
owner profiling system.

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
This module performs ASSESSMENT and returns FLAGS/REQUIREMENTS.
Question generation has been deprecated - Titan handles all user interactions.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from .profiling_types import (
    TechnicalRequirement,
    OwnerQuestion,
    OwnerQuestionSet
)

logger = get_logger(__name__)


class TechnicalAssessment:
    """Assesses technical requirements and skills for business operations"""

    def __init__(self):
        """Initialize the technical assessment"""
        self.logger = logger
        self.technical_requirements = self._load_technical_requirements()
        self.skill_categories = self._build_skill_categories()
        self.assessment_questions = self._build_assessment_questions()

    def assess_technical_requirements(
        self,
        business_type: str,
        industry: str,
        business_context: Dict[str, Any]
    ) -> List[TechnicalRequirement]:
        """
        Assess technical requirements for a business

        Args:
            business_type: Type of business
            industry: Industry category
            business_context: Additional business context

        Returns:
            List of technical requirements
        """
        try:
            self.logger.info("Assessing technical requirements",
                           business_type=business_type,
                           industry=industry)

            # Get base requirements for business type
            base_requirements = self._get_base_requirements(business_type, industry)

            # Add industry-specific requirements
            industry_requirements = self._get_industry_requirements(industry)

            # Add business-specific requirements
            business_requirements = self._get_business_requirements(business_context)

            # Combine all requirements
            all_requirements = base_requirements + industry_requirements + business_requirements

            # Remove duplicates and prioritize
            unique_requirements = self._deduplicate_requirements(all_requirements)
            prioritized_requirements = self._prioritize_requirements(unique_requirements)

            self.logger.info("Technical requirements assessed",
                           total_requirements=len(prioritized_requirements),
                           critical_requirements=len([r for r in prioritized_requirements if r.importance_level >= 8]))

            return prioritized_requirements

        except Exception as e:
            self.logger.error(f"Error assessing technical requirements: {e}")
            return []

    def generate_technical_questions(
        self,
        technical_requirements: List[TechnicalRequirement],
        owner_profile: Dict[str, Any]
    ) -> List[OwnerQuestion]:
        """
        DEPRECATED: Question generation moved to Titan (The Brain).
        
        BRAIN & MUSCLE ARCHITECTURE:
        ValuationIQ returns assessment flags/requirements, not questions.
        Titan's TriageService generates questions via Claude.
        
        This method returns an empty list for backward compatibility.
        Use assess_technical_requirements() for the actual assessment.
        """
        self.logger.debug("generate_technical_questions called - DEPRECATED, returning empty list")
        return []
    
    def _generate_technical_questions_legacy(
        self,
        technical_requirements: List[TechnicalRequirement],
        owner_profile: Dict[str, Any]
    ) -> List[OwnerQuestion]:
        """LEGACY: Kept for reference only, not called."""
        try:
            self.logger.info("Generating technical assessment questions",
                           requirements_count=len(technical_requirements))

            questions = []

            for requirement in technical_requirements:
                # Generate question for each requirement
                question = self._create_requirement_question(requirement, owner_profile)
                if question:
                    questions.append(question)

            # Add general technical questions
            general_questions = self._get_general_technical_questions()
            questions.extend(general_questions)

            # Prioritize questions by importance
            prioritized_questions = self._prioritize_questions(questions)

            self.logger.info("Technical assessment questions generated",
                           total_questions=len(prioritized_questions))

            return prioritized_questions

        except Exception as e:
            self.logger.error(f"Error generating technical questions: {e}")
            return []

    def analyze_technical_gaps(
        self,
        owner_skills: List[str],
        technical_requirements: List[TechnicalRequirement]
    ) -> Dict[str, Any]:
        """
        Analyze technical skill gaps

        Args:
            owner_skills: Owner's technical skills
            technical_requirements: Required technical skills

        Returns:
            Technical gap analysis
        """
        try:
            self.logger.info("Analyzing technical skill gaps",
                           owner_skills_count=len(owner_skills),
                           requirements_count=len(technical_requirements))

            gaps = []
            covered_requirements = []
            critical_gaps = []

            for requirement in technical_requirements:
                # Check if owner has this skill
                has_skill = self._check_skill_match(owner_skills, requirement)

                if has_skill:
                    covered_requirements.append(requirement)
                else:
                    gaps.append(requirement)

                    # Check if it's critical
                    if requirement.importance_level >= 8:
                        critical_gaps.append(requirement)

            # Calculate coverage metrics
            total_requirements = len(technical_requirements)
            covered_count = len(covered_requirements)
            coverage_percentage = (covered_count / total_requirements * 100) if total_requirements > 0 else 0

            # Calculate risk score
            risk_score = self._calculate_technical_risk_score(gaps, critical_gaps)

            # Generate recommendations
            recommendations = self._generate_technical_recommendations(gaps, critical_gaps)

            gap_analysis = {
                "total_requirements": total_requirements,
                "covered_requirements": covered_count,
                "coverage_percentage": coverage_percentage,
                "gaps": gaps,
                "critical_gaps": critical_gaps,
                "risk_score": risk_score,
                "recommendations": recommendations,
                "covered_requirements_list": covered_requirements
            }

            self.logger.info("Technical gap analysis completed",
                           coverage_percentage=coverage_percentage,
                           critical_gaps=len(critical_gaps),
                           risk_score=risk_score)

            return gap_analysis

        except Exception as e:
            self.logger.error(f"Error analyzing technical gaps: {e}")
            return {}

    def _get_base_requirements(self, business_type: str, industry: str) -> List[TechnicalRequirement]:
        """Get base technical requirements for business type"""
        try:
            requirements = []

            # Technology businesses
            if business_type.lower() in ["saas", "software", "technology"]:
                requirements.extend([
                    TechnicalRequirement(
                        skill_name="Software Development",
                        importance_level=9,
                        rarity_score=6,
                        certification_required=False,
                        years_experience_required=3,
                        alternative_skills=["System Administration", "DevOps"],
                        training_time_estimate="6 months",
                        market_availability="high",
                        cost_estimate="$50k"
                    ),
                    TechnicalRequirement(
                        skill_name="Cloud Architecture",
                        importance_level=8,
                        rarity_score=7,
                        certification_required=True,
                        years_experience_required=2,
                        alternative_skills=["System Administration"],
                        training_time_estimate="3 months",
                        market_availability="medium",
                        cost_estimate="$30k"
                    )
                ])

            # Manufacturing businesses
            elif business_type.lower() in ["manufacturing", "production"]:
                requirements.extend([
                    TechnicalRequirement(
                        skill_name="Production Management",
                        importance_level=9,
                        rarity_score=5,
                        certification_required=False,
                        years_experience_required=5,
                        alternative_skills=["Operations Management"],
                        training_time_estimate="1 year",
                        market_availability="medium",
                        cost_estimate="$40k"
                    ),
                    TechnicalRequirement(
                        skill_name="Quality Control",
                        importance_level=8,
                        rarity_score=4,
                        certification_required=True,
                        years_experience_required=3,
                        alternative_skills=["Process Engineering"],
                        training_time_estimate="6 months",
                        market_availability="high",
                        cost_estimate="$25k"
                    )
                ])

            # Retail businesses
            elif business_type.lower() in ["retail", "ecommerce"]:
                requirements.extend([
                    TechnicalRequirement(
                        skill_name="Inventory Management",
                        importance_level=8,
                        rarity_score=3,
                        certification_required=False,
                        years_experience_required=2,
                        alternative_skills=["Supply Chain Management"],
                        training_time_estimate="3 months",
                        market_availability="high",
                        cost_estimate="$15k"
                    ),
                    TechnicalRequirement(
                        skill_name="Customer Service",
                        importance_level=7,
                        rarity_score=2,
                        certification_required=False,
                        years_experience_required=1,
                        alternative_skills=["Sales Management"],
                        training_time_estimate="1 month",
                        market_availability="high",
                        cost_estimate="$5k"
                    )
                ])

            # Services businesses
            elif business_type.lower() in ["consulting", "services"]:
                requirements.extend([
                    TechnicalRequirement(
                        skill_name="Project Management",
                        importance_level=9,
                        rarity_score=4,
                        certification_required=True,
                        years_experience_required=3,
                        alternative_skills=["Operations Management"],
                        training_time_estimate="6 months",
                        market_availability="medium",
                        cost_estimate="$30k"
                    ),
                    TechnicalRequirement(
                        skill_name="Client Relationship Management",
                        importance_level=8,
                        rarity_score=3,
                        certification_required=False,
                        years_experience_required=2,
                        alternative_skills=["Sales Management"],
                        training_time_estimate="3 months",
                        market_availability="high",
                        cost_estimate="$20k"
                    )
                ])

            return requirements

        except Exception as e:
            self.logger.error(f"Error getting base requirements: {e}")
            return []

    def _get_industry_requirements(self, industry: str) -> List[TechnicalRequirement]:
        """Get industry-specific technical requirements"""
        try:
            requirements = []

            # Healthcare industry
            if industry.lower() in ["healthcare", "medical"]:
                requirements.extend([
                    TechnicalRequirement(
                        skill_name="Medical Knowledge",
                        importance_level=9,
                        rarity_score=8,
                        certification_required=True,
                        years_experience_required=5,
                        alternative_skills=["Healthcare Administration"],
                        training_time_estimate="2 years",
                        market_availability="low",
                        cost_estimate="$100k+"
                    ),
                    TechnicalRequirement(
                        skill_name="Regulatory Compliance",
                        importance_level=8,
                        rarity_score=6,
                        certification_required=True,
                        years_experience_required=3,
                        alternative_skills=["Legal Knowledge"],
                        training_time_estimate="1 year",
                        market_availability="medium",
                        cost_estimate="$50k"
                    )
                ])

            # Finance industry
            elif industry.lower() in ["finance", "banking"]:
                requirements.extend([
                    TechnicalRequirement(
                        skill_name="Financial Analysis",
                        importance_level=9,
                        rarity_score=5,
                        certification_required=True,
                        years_experience_required=3,
                        alternative_skills=["Accounting"],
                        training_time_estimate="6 months",
                        market_availability="medium",
                        cost_estimate="$30k"
                    ),
                    TechnicalRequirement(
                        skill_name="Risk Management",
                        importance_level=8,
                        rarity_score=6,
                        certification_required=True,
                        years_experience_required=2,
                        alternative_skills=["Compliance"],
                        training_time_estimate="3 months",
                        market_availability="medium",
                        cost_estimate="$25k"
                    )
                ])

            return requirements

        except Exception as e:
            self.logger.error(f"Error getting industry requirements: {e}")
            return []

    def _get_business_requirements(self, business_context: Dict[str, Any]) -> List[TechnicalRequirement]:
        """Get business-specific technical requirements"""
        try:
            requirements = []

            # Add requirements based on business context
            if business_context.get("has_website", False):
                requirements.append(TechnicalRequirement(
                    skill_name="Web Development",
                    importance_level=6,
                    rarity_score=4,
                    certification_required=False,
                    years_experience_required=2,
                    alternative_skills=["Web Design"],
                    training_time_estimate="6 months",
                    market_availability="high",
                    cost_estimate="$20k"
                ))

            if business_context.get("has_inventory", False):
                requirements.append(TechnicalRequirement(
                    skill_name="Inventory Management",
                    importance_level=7,
                    rarity_score=3,
                    certification_required=False,
                    years_experience_required=2,
                    alternative_skills=["Supply Chain Management"],
                    training_time_estimate="3 months",
                    market_availability="high",
                    cost_estimate="$15k"
                ))

            return requirements

        except Exception as e:
            self.logger.error(f"Error getting business requirements: {e}")
            return []

    def _deduplicate_requirements(self, requirements: List[TechnicalRequirement]) -> List[TechnicalRequirement]:
        """Remove duplicate requirements"""
        try:
            unique_requirements = []
            seen_skills = set()

            for requirement in requirements:
                if requirement.skill_name.lower() not in seen_skills:
                    unique_requirements.append(requirement)
                    seen_skills.add(requirement.skill_name.lower())

            return unique_requirements

        except Exception as e:
            self.logger.error(f"Error deduplicating requirements: {e}")
            return requirements

    def _prioritize_requirements(self, requirements: List[TechnicalRequirement]) -> List[TechnicalRequirement]:
        """Prioritize requirements by importance and rarity"""
        try:
            # Sort by importance level (descending) then by rarity score (descending)
            return sorted(requirements, key=lambda x: (x.importance_level, x.rarity_score), reverse=True)
        except Exception as e:
            self.logger.error(f"Error prioritizing requirements: {e}")
            return requirements

    def _create_requirement_question(
        self,
        requirement: TechnicalRequirement,
        owner_profile: Dict[str, Any]
    ) -> Optional[OwnerQuestion]:
        """Create a question for a technical requirement"""
        try:
            question_text = f"Do you have experience with {requirement.skill_name}?"

            if requirement.certification_required:
                question_text += f" (Certification required: {requirement.skill_name})"

            question = OwnerQuestion(
                question_id=f"tech_{requirement.skill_name.lower().replace(' ', '_')}",
                question_text=question_text,
                question_type="technical",
                importance=requirement.importance_level,
                follow_up_questions=[
                    f"How many years of experience do you have with {requirement.skill_name}?",
                    f"Are you certified in {requirement.skill_name}?",
                    f"Can you delegate {requirement.skill_name} tasks to others?"
                ],
                expected_response_type="boolean",
                response_options=["Yes", "No"],
                validation_rules={"required": True}
            )

            return question

        except Exception as e:
            self.logger.error(f"Error creating requirement question: {e}")
            return None

    def _get_general_technical_questions(self) -> List[OwnerQuestion]:
        """Get general technical assessment questions"""
        try:
            return [
                OwnerQuestion(
                    question_id="tech_general_experience",
                    question_text="What is your overall technical experience level?",
                    question_type="technical",
                    importance=8,
                    follow_up_questions=[
                        "How do you stay updated with technical changes?",
                        "Do you have a technical mentor or advisor?"
                    ],
                    expected_response_type="multiple_choice",
                    response_options=["Beginner", "Intermediate", "Advanced", "Expert"],
                    validation_rules={"required": True}
                ),
                OwnerQuestion(
                    question_id="tech_delegation",
                    question_text="Can you delegate technical tasks to others?",
                    question_type="technical",
                    importance=7,
                    follow_up_questions=[
                        "Who would handle technical tasks if you're unavailable?",
                        "How do you ensure technical quality when delegating?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                ),
                OwnerQuestion(
                    question_id="tech_training",
                    question_text="Are you willing to invest in technical training?",
                    question_type="technical",
                    importance=6,
                    follow_up_questions=[
                        "What technical training have you completed recently?",
                        "What technical skills would you like to develop?"
                    ],
                    expected_response_type="boolean",
                    response_options=["Yes", "No"],
                    validation_rules={"required": True}
                )
            ]
        except Exception as e:
            self.logger.error(f"Error getting general technical questions: {e}")
            return []

    def _prioritize_questions(self, questions: List[OwnerQuestion]) -> List[OwnerQuestion]:
        """Prioritize questions by importance"""
        try:
            return sorted(questions, key=lambda x: x.importance, reverse=True)
        except Exception as e:
            self.logger.error(f"Error prioritizing questions: {e}")
            return questions

    def _check_skill_match(self, owner_skills: List[str], requirement: TechnicalRequirement) -> bool:
        """Check if owner has the required skill"""
        try:
            skill_name_lower = requirement.skill_name.lower()

            # Check direct match
            for skill in owner_skills:
                if skill_name_lower in skill.lower():
                    return True

            # Check alternative skills
            for alt_skill in requirement.alternative_skills:
                for skill in owner_skills:
                    if alt_skill.lower() in skill.lower():
                        return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking skill match: {e}")
            return False

    def _calculate_technical_risk_score(
        self,
        gaps: List[TechnicalRequirement],
        critical_gaps: List[TechnicalRequirement]
    ) -> Decimal:
        """Calculate technical risk score using Decimal"""
        try:
            if not gaps:
                return Decimal('0.1')  # Very low risk

            # Base risk from gaps using Decimal
            gaps_count_decimal = Decimal(str(len(gaps)))
            base_risk_decimal = gaps_count_decimal / Decimal('10.0')  # Normalize to 0-1

            # Increase risk for critical gaps using Decimal
            critical_count_decimal = Decimal(str(len(critical_gaps)))
            critical_risk_decimal = critical_count_decimal / Decimal('5.0')  # Normalize to 0-1

            # Combine risks using Decimal
            total_risk_decimal = (base_risk_decimal + critical_risk_decimal) / Decimal('2')

            # Clamp to 0-1 range
            clamped_risk = max(Decimal('0.0'), min(Decimal('1.0'), total_risk_decimal))
            
            return from_decimal(clamped_risk)

        except Exception as e:
            self.logger.error(f"Error calculating technical risk score: {e}")
            return Decimal('0.5')

    def _generate_technical_recommendations(
        self,
        gaps: List[TechnicalRequirement],
        critical_gaps: List[TechnicalRequirement]
    ) -> List[str]:
        """Generate technical recommendations"""
        try:
            recommendations = []

            if critical_gaps:
                recommendations.append("Address critical technical skill gaps immediately")
                for gap in critical_gaps:
                    recommendations.append(f"Develop {gap.skill_name} expertise")

            if gaps:
                recommendations.append("Create technical skill development plan")
                recommendations.append("Consider hiring technical specialists")
                recommendations.append("Implement knowledge transfer program")

            if not gaps:
                recommendations.append("Maintain current technical skill level")
                recommendations.append("Stay updated with industry changes")

            return recommendations

        except Exception as e:
            self.logger.error(f"Error generating technical recommendations: {e}")
            return []

    def _load_technical_requirements(self) -> Dict[str, List[TechnicalRequirement]]:
        """Load technical requirements database"""
        return {
            "technology": [],
            "manufacturing": [],
            "retail": [],
            "services": [],
            "healthcare": [],
            "finance": []
        }

    def _build_skill_categories(self) -> Dict[str, List[str]]:
        """Build skill categories"""
        return {
            "technical": ["Programming", "System Administration", "Database Management"],
            "management": ["Project Management", "Team Leadership", "Strategic Planning"],
            "business": ["Sales", "Marketing", "Customer Service"],
            "industry": ["Industry Knowledge", "Regulatory Compliance", "Market Analysis"]
        }

    def _build_assessment_questions(self) -> List[OwnerQuestion]:
        """Build assessment questions"""
        return [
            OwnerQuestion(
                question_id="tech_overall",
                question_text="What is your overall technical experience?",
                question_type="technical",
                importance=9,
                follow_up_questions=[],
                expected_response_type="multiple_choice",
                response_options=["Beginner", "Intermediate", "Advanced", "Expert"]
            )
        ]