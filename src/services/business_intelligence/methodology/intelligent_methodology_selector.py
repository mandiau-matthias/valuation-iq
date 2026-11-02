
from src.errors.error_types import DomainError
from src.utils.exceptions import (
    CalculationError,
    DCFCalculationError,
    DataValidationError,
    MethodologyError
)

"""
Intelligent Methodology Selector - Refactored

Main orchestrator for intelligent methodology selection, integrating all
modular components for comprehensive valuation approach determination.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from ..integration.selector_types import (
    BusinessContext, MethodologySelection, SelectionRequest, SelectionResponse,
    ConfidenceLevel, SelectionStatus
)
from .methodology_analyzer import MethodologyAnalyzer
from ..integration.selection_engine import SelectionEngine

# Academic provenance tracking
try:
    from src.services.academic.decorators import track_academic_provenance
    ACADEMIC_TRACKING_AVAILABLE = True
except ImportError:
    ACADEMIC_TRACKING_AVAILABLE = False
    # Create no-op decorator if import fails
    def track_academic_provenance(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

logger = get_logger(__name__)


class IntelligentMethodologySelectorRefactored:
    """
    Refactored intelligent methodology selector with modular architecture
    """

    def __init__(self):
        """Initialize the refactored methodology selector"""
        self.analyzer = MethodologyAnalyzer()
        self.selection_engine = SelectionEngine()

        logger.info("✅ IntelligentMethodologySelectorRefactored initialized")

    async def select_optimal_methodology(
        self,
        business_context: BusinessContext,
        financial_data: Dict[str, Any],
        owner_profile: Optional[Dict[str, Any]] = None,
        market_context: Optional[Dict[str, Any]] = None
    ) -> MethodologySelection:
        """
        Select optimal valuation methodology based on comprehensive analysis
        """

        start_time = datetime.now()

        try:
            logger.info(f"🔍 Analyzing methodology selection for {business_context.industry} business")

            # Step 1: Analyze business characteristics
            business_score = self.analyzer.analyze_business_characteristics(business_context)

            # Step 2: Analyze financial health
            financial_score = self.analyzer.analyze_financial_health(financial_data)

            # Step 3: Analyze owner dependency
            owner_score = self.analyzer.analyze_owner_dependency(owner_profile) if owner_profile else None

            # Step 4: Analyze market context
            market_score = self.analyzer.analyze_market_context(market_context) if market_context else None

            # Step 5: Apply industry-specific rules
            industry_score = self.analyzer.apply_industry_rules(business_context.industry, financial_data)

            # Step 6: Calculate methodology weights
            dcf_weight, multiples_weight = self.selection_engine.calculate_methodology_weights(
                business_score, financial_score, owner_score, market_score, industry_score
            )

            # Step 7: Generate recommendations
            recommendations = self.selection_engine.generate_recommendations(
                dcf_weight, multiples_weight, business_context, financial_data
            )

            # Step 8: Generate reasoning
            reasoning = self.selection_engine.generate_reasoning(
                dcf_weight, multiples_weight, business_score, financial_score, owner_score, market_score
            )

            # Step 9: Generate next questions
            next_questions = self.selection_engine.generate_next_questions(
                dcf_weight, multiples_weight, business_context, financial_data
            )

            # Step 10: Generate methodology notes
            methodology_notes = self.selection_engine.generate_methodology_notes(
                dcf_weight, multiples_weight, business_context, financial_data
            )

            # Calculate confidence score
            confidence_score = self.selection_engine.calculate_confidence_score(dcf_weight, multiples_weight)

            processing_time = (datetime.now() - start_time).total_seconds()

            logger.info(f"✅ Methodology selection complete: DCF={dcf_weight:.2f}, Multiples={multiples_weight:.2f} ({processing_time:.2f}s)")

            return MethodologySelection(
                dcf_weight=dcf_weight,
                multiples_weight=multiples_weight,
                confidence_score=confidence_score,
                reasoning=reasoning,
                recommendations=recommendations,
                next_questions=next_questions,
                methodology_notes=methodology_notes
            )

        except DCFCalculationError as e:
            logger.error(f"❌ Methodology selection failed: {str(e)}")
            # Return default methodology selection
            return MethodologySelection(
                dcf_weight=0.5,
                multiples_weight=0.5,
                confidence_score=0.5,
                reasoning="Default methodology selection due to analysis error",
                recommendations=["Use both DCF and Multiples for validation"],
                next_questions=[],
                methodology_notes="Default methodology selection"
            )

    async def process_selection_request(self, request: SelectionRequest) -> SelectionResponse:
        """Process a complete methodology selection request"""

        start_time = datetime.now()

        try:
            logger.info(f"Processing methodology selection request for {request.business_context.industry}")

            # Perform methodology selection
            selection = await self.select_optimal_methodology(
                request.business_context,
                request.financial_data,
                request.owner_profile,
                request.market_context
            )

            # Get analysis scores
            business_score = self.analyzer.analyze_business_characteristics(request.business_context)
            financial_score = self.analyzer.analyze_financial_health(request.financial_data)
            owner_score = self.analyzer.analyze_owner_dependency(request.owner_profile) if request.owner_profile else None
            market_score = self.analyzer.analyze_market_context(request.market_context) if request.market_context else None
            industry_score = self.analyzer.apply_industry_rules(request.business_context.industry, request.financial_data)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            # Determine confidence level
            confidence_level = self.selection_engine.determine_confidence_level(selection.confidence_score)

            return SelectionResponse(
                selection=selection,
                business_score=business_score,
                financial_score=financial_score,
                owner_score=owner_score,
                market_score=market_score,
                industry_score=industry_score,
                processing_time=processing_time,
                confidence_level=confidence_level.value
            )

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(f"Validation error in selection request processing: {e}", extra={'error_type': type(e).__name__})
            raise ValidationError(f"Invalid input for methodology selection: {e}") from e
        except DataValidationError as e:
            logger.error(f"Selection request processing failed: {e}", extra={'error_type': type(e).__name__})
            raise DomainError(
                f"Failed to process methodology selection request: {e}",
                context={'error_type': type(e).__name__}
            ) from e

    @track_academic_provenance(
        calculation_id="methodology_selection",
        section_name="Methodology Selection",
        extract_inputs=lambda args, kwargs: {
            'industry': kwargs.get('business_context').industry if kwargs.get('business_context') and hasattr(kwargs.get('business_context'), 'industry') else None,
            'revenue': kwargs.get('financial_data', {}).get('revenue'),
            'ebitda': kwargs.get('financial_data', {}).get('ebitda'),
            'business_type': kwargs.get('business_context').business_type if kwargs.get('business_context') and hasattr(kwargs.get('business_context'), 'business_type') else None
        },
        extract_outputs=lambda result: {
            'preferred_methodology': result.get('preferred_methodology'),
            'dcf_weight': result.get('dcf_weight'),
            'multiples_weight': result.get('multiples_weight'),
            'confidence_score': result.get('confidence_score')
        }
    )
    def get_methodology_preference(
        self,
        business_context: BusinessContext,
        financial_data: Dict[str, Any],
        owner_profile: Optional[Dict[str, Any]] = None,
        market_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get methodology preference during conversation"""

        try:
            logger.info("Getting methodology preference")

            # Perform quick analysis
            business_score = self.analyzer.analyze_business_characteristics(business_context)
            financial_score = self.analyzer.analyze_financial_health(financial_data)
            owner_score = self.analyzer.analyze_owner_dependency(owner_profile) if owner_profile else None
            market_score = self.analyzer.analyze_market_context(market_context) if market_context else None
            industry_score = self.analyzer.apply_industry_rules(business_context.industry, financial_data)

            # Calculate weights
            dcf_weight, multiples_weight = self.selection_engine.calculate_methodology_weights(
                business_score, financial_score, owner_score, market_score, industry_score
            )

            # Determine preferred methodology
            if dcf_weight > multiples_weight:
                preferred_methodology = "DCF"
                confidence_score = dcf_weight
            else:
                preferred_methodology = "Multiples"
                confidence_score = multiples_weight

            # Generate quick reasoning
            reasoning = self.selection_engine.generate_reasoning(
                dcf_weight, multiples_weight, business_score, financial_score, owner_score, market_score
            )

            # Generate quick recommendations
            recommendations = self.selection_engine.generate_recommendations(
                dcf_weight, multiples_weight, business_context, financial_data
            )

            # Generate quick questions
            next_questions = self.selection_engine.generate_next_questions(
                dcf_weight, multiples_weight, business_context, financial_data
            )

            return {
                "preferred_methodology": preferred_methodology,
                "confidence_score": confidence_score,
                "reasoning": reasoning,
                "recommendations": recommendations,
                "next_questions": next_questions,
                "dcf_weight": dcf_weight,
                "multiples_weight": multiples_weight
            }

        except DCFCalculationError as e:
            logger.error(f"Methodology preference failed: {e}")
            return {
                "preferred_methodology": "DCF",
                "confidence_score": 0.5,
                "reasoning": "Default methodology selection",
                "recommendations": ["Use both methodologies for validation"],
                "next_questions": [],
                "dcf_weight": 0.5,
                "multiples_weight": 0.5
            }

    def get_industry_specific_questions(self, industry: str) -> List[str]:
        """Get industry-specific questions for methodology selection"""

        try:
            logger.info(f"Getting industry-specific questions for {industry}")

            # Create mock business context for question generation
            business_context = BusinessContext(
                industry=industry,
                business_type="unknown",
                revenue=0,
                ebitda=0,
                growth_rate=0,
                business_age=0,
                employee_count=0,
                market_position="unknown",
                competitive_advantage="unknown"
            )

            # Generate questions using selection engine
            questions = self.selection_engine._generate_industry_questions(business_context)

            logger.info(f"Generated {len(questions)} industry-specific questions")

            return questions

        except MethodologyError as e:
            logger.error(f"Industry-specific questions failed: {e}")
            return []

    def get_methodology_guidance(self, methodology: str, industry: str) -> Dict[str, Any]:
        """Get methodology-specific guidance"""

        try:
            logger.info(f"Getting methodology guidance for {methodology} in {industry}")

            guidance = {
                "methodology": methodology,
                "industry": industry,
                "key_factors": [],
                "data_requirements": [],
                "best_practices": [],
                "common_pitfalls": []
            }

            # DCF guidance
            if methodology.lower() == "dcf":
                guidance["key_factors"] = [
                    "Revenue growth projections",
                    "EBITDA margin trends",
                    "Capital expenditure requirements",
                    "Working capital needs",
                    "Discount rate determination"
                ]
                guidance["data_requirements"] = [
                    "Historical financial statements (3-5 years)",
                    "Projected financial statements (5-10 years)",
                    "Capital expenditure plans",
                    "Working capital analysis",
                    "Market risk assessment"
                ]
                guidance["best_practices"] = [
                    "Use conservative growth assumptions",
                    "Consider multiple scenarios",
                    "Validate assumptions with market data",
                    "Regularly update projections"
                ]
                guidance["common_pitfalls"] = [
                    "Overly optimistic growth assumptions",
                    "Incorrect discount rate calculation",
                    "Ignoring terminal value sensitivity",
                    "Inadequate working capital modeling"
                ]

            # Multiples guidance
            elif methodology.lower() == "multiples":
                guidance["key_factors"] = [
                    "Comparable company selection",
                    "Multiple selection (P/E, EV/EBITDA, etc.)",
                    "Market data quality",
                    "Business comparability",
                    "Market timing"
                ]
                guidance["data_requirements"] = [
                    "Comparable company financials",
                    "Market transaction data",
                    "Industry benchmarks",
                    "Market multiples data",
                    "Business characteristics data"
                ]
                guidance["best_practices"] = [
                    "Select truly comparable companies",
                    "Use multiple valuation multiples",
                    "Consider market conditions",
                    "Adjust for differences"
                ]
                guidance["common_pitfalls"] = [
                    "Using inappropriate comparables",
                    "Ignoring market conditions",
                    "Over-relying on single multiple",
                    "Not adjusting for differences"
                ]

            # Industry-specific guidance
            if industry == "technology":
                guidance["industry_specific"] = {
                    "dcf_focus": "Recurring revenue, customer acquisition costs, churn rates",
                    "multiples_focus": "SaaS metrics, technology multiples, growth rates"
                }
            elif industry == "retail":
                guidance["industry_specific"] = {
                    "dcf_focus": "Location value, foot traffic, inventory turnover",
                    "multiples_focus": "Location-based multiples, retail comparables"
                }
            elif industry == "manufacturing":
                guidance["industry_specific"] = {
                    "dcf_focus": "Production capacity, equipment value, supply chain",
                    "multiples_focus": "Equipment multiples, manufacturing comparables"
                }
            elif industry == "services":
                guidance["industry_specific"] = {
                    "dcf_focus": "Hourly rates, client retention, capacity utilization",
                    "multiples_focus": "Service multiples, professional services comparables"
                }

            logger.info(f"Generated methodology guidance for {methodology}")

            return guidance

        except DCFCalculationError as e:
            logger.error(f"Methodology guidance failed: {e}")
            return {
                "methodology": methodology,
                "industry": industry,
                "key_factors": [],
                "data_requirements": [],
                "best_practices": [],
                "common_pitfalls": []
            }

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and metrics"""

        try:
            return {
                "status": "operational",
                "components": {
                    "analyzer": "operational",
                    "selection_engine": "operational"
                },
                "capabilities": [
                    "Business characteristics analysis",
                    "Financial health assessment",
                    "Owner dependency analysis",
                    "Market context analysis",
                    "Industry-specific rules",
                    "Methodology weight calculation",
                    "Confidence scoring",
                    "Recommendation generation"
                ],
                "supported_industries": [
                    "technology", "retail", "manufacturing", "services",
                    "healthcare", "food_beverage", "real_estate", "education",
                    "transportation", "entertainment", "agriculture", "energy",
                    "financial", "other"
                ],
                "supported_methodologies": [
                    "DCF", "Multiples", "Asset-Based", "Synthesized"
                ],
                "timestamp": datetime.now().isoformat()
            }

        except DCFCalculationError as e:
            logger.error(f"Failed to get system status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }