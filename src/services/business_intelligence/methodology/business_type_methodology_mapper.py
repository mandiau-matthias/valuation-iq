from src.utils.exceptions import ConfigurationError, DataValidationError

"""
Business Type Methodology Mapper - Refactored

Main orchestrator for business type to methodology mapping system.
Integrates all modular components for comprehensive methodology selection.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ..analysis.business_type_analyzer import BusinessTypeAnalyzer
from ..classification.industry_rules import IndustryRules
from ..integration.mapper_types import (
    BUSINESS_TYPE_VARIATIONS,
    BusinessCharacteristics,
    MethodologyDecision,
    RefinementFactors,
    ValuationMethodology,
)
from ..integration.scoring_engine import ScoringEngine
from .methodology_selector import MethodologySelector
from .time_estimates import methodology_time_estimate

logger = get_logger(__name__)


class BusinessTypeMethodologyMapperRefactored:
    """Refactored main orchestrator for business type to methodology mapping"""

    def __init__(self):
        self.business_analyzer = BusinessTypeAnalyzer()
        self.methodology_selector = MethodologySelector()
        self.industry_rules = IndustryRules()
        self.scoring_engine = ScoringEngine()

        logger.info("BusinessTypeMethodologyMapperRefactored initialized successfully")

    def get_optimal_methodology(
        self,
        business_type: str,
        industry: Optional[str] = None,
        revenue: Optional[Decimal] = None,
        years_in_operation: Optional[int] = None,
        country_code: str = "BE",
    ) -> MethodologyDecision:
        """
        Get optimal valuation methodology for a business type

        Args:
            business_type: Business type from frontend (current catalog)
            industry: Industry category
            revenue: Annual revenue (for refinement)
            years_in_operation: Years in business
            country_code: Country code for regional factors

        Returns:
            MethodologyDecision with optimal methodology and reasoning
        """
        try:
            logger.info(
                f"Selecting methodology for business_type={business_type}, industry={industry}"
            )

            # Step 1: Get business type characteristics
            business_characteristics = self.business_analyzer.get_business_type_characteristics(
                business_type
            )

            # Step 2: Get base methodology configuration
            base_config = self.business_analyzer.get_business_type_config(business_type)

            if not base_config:
                # Fallback to industry-based methodology
                return self.methodology_selector._get_industry_fallback_methodology(
                    industry, revenue, years_in_operation
                )

            # Step 3: Apply industry rules
            refined_methodology, confidence_adjustment, reasoning_changes = (
                self.industry_rules.apply_industry_rules(
                    business_type,
                    industry,
                    revenue,
                    years_in_operation,
                    ValuationMethodology(base_config["primary"]),
                )
            )

            # Step 4: Calculate comprehensive score
            score_result = self.scoring_engine.calculate_methodology_score(
                refined_methodology, business_type, industry, revenue, years_in_operation
            )

            # Step 5: Build final decision
            decision = self._build_methodology_decision(
                base_config,
                refined_methodology,
                confidence_adjustment,
                reasoning_changes,
                score_result,
                business_type,
                industry,
                revenue,
                years_in_operation,
            )

            logger.info(
                f"Selected methodology: {decision.primary_methodology.value} "
                f"(confidence: {decision.confidence_score:.2f})"
            )

            return decision

        except ConfigurationError as e:
            logger.error(f"Error selecting methodology for {business_type}: {e}")
            return self.methodology_selector._get_conservative_fallback()

    def _build_methodology_decision(
        self,
        base_config: Dict[str, Any],
        refined_methodology: ValuationMethodology,
        confidence_adjustment: Decimal,
        reasoning_changes: List[str],
        score_result: Dict[str, Any],
        business_type: str,
        industry: Optional[str],
        revenue: Optional[Decimal],
        years_in_operation: Optional[int],
    ) -> MethodologyDecision:
        """Build final methodology decision with all refinements"""

        # Start with base confidence
        confidence = Decimal("0.8") + confidence_adjustment

        # Adjust based on score
        if score_result["confidence_level"] == "high":
            confidence += Decimal("0.1")
        elif score_result["confidence_level"] == "low":
            confidence -= Decimal("0.1")

        # Build comprehensive reasoning
        reasoning = base_config["reasoning"]
        if reasoning_changes:
            reasoning += " " + " ".join(reasoning_changes)

        # Add score-based insights
        if score_result["overall_score"] >= 0.8:
            reasoning += (
                " High confidence in methodology selection based on comprehensive analysis."
            )
        elif score_result["overall_score"] < 0.6:
            reasoning += " Consider alternative methodologies based on business characteristics."

        # Add maturity and size considerations
        if years_in_operation and years_in_operation < 2:
            reasoning += " Early-stage businesses benefit from growth-focused analysis."
        elif years_in_operation and years_in_operation > 10:
            reasoning += " Mature businesses with stable operations are well-suited for market-based valuation."

        if revenue and revenue < 100000:
            reasoning += " Small businesses typically use simpler valuation methods."
        elif revenue and revenue > 10000000:
            reasoning += " Large businesses require sophisticated analysis for accurate valuation."

        return MethodologyDecision(
            primary_methodology=refined_methodology,
            secondary_methodology=(
                ValuationMethodology(base_config["secondary"])
                if base_config.get("secondary")
                else None
            ),
            confidence_score=min(confidence, Decimal("1.0")),
            reasoning=reasoning,
            key_factors=base_config["key_factors"],
            special_considerations=base_config["special_considerations"],
            expected_accuracy=score_result["overall_score"],
            time_estimate=methodology_time_estimate(refined_methodology, revenue),
            multiple_types=base_config["multiple_types"],
            growth_weighted=base_config.get("growth_weighted", False),
            asset_intensity=base_config.get("asset_intensity", "medium"),
        )

    def get_business_type_characteristics(self, business_type: str) -> BusinessCharacteristics:
        """Get detailed characteristics for a business type"""
        return self.business_analyzer.get_business_type_characteristics(business_type)

    def get_methodology_recommendations(
        self, business_type: str, industry: Optional[str] = None
    ) -> List[MethodologyDecision]:
        """Get multiple methodology recommendations with different approaches"""
        return self.methodology_selector.get_methodology_recommendations(business_type, industry)

    def compare_methodologies(
        self,
        business_type: str,
        industry: Optional[str] = None,
        revenue: Optional[Decimal] = None,
        years_in_operation: Optional[int] = None,
        data_quality: str = "medium",
    ) -> List[Dict[str, Any]]:
        """Compare multiple methodologies and rank them"""
        methodologies = [
            ValuationMethodology.DCF,
            ValuationMethodology.MULTIPLES,
            ValuationMethodology.ASSET_BASED,
            ValuationMethodology.ARR_MULTIPLES,
        ]

        return self.scoring_engine.compare_methodologies(
            methodologies, business_type, industry, revenue, years_in_operation, data_quality
        )

    def get_methodology_ranking(
        self,
        business_type: str,
        industry: Optional[str] = None,
        revenue: Optional[Decimal] = None,
        years_in_operation: Optional[int] = None,
        data_quality: str = "medium",
    ) -> List[tuple]:
        """Get ranked list of methodologies for a business"""
        return self.scoring_engine.get_methodology_ranking(
            business_type, industry, revenue, years_in_operation, data_quality
        )

    def validate_methodology_choice(
        self,
        methodology: ValuationMethodology,
        business_type: str,
        industry: Optional[str] = None,
        revenue: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Validate if a methodology choice is appropriate for the business"""
        return self.methodology_selector.validate_methodology_choice(
            methodology, business_type, revenue
        )

    def get_industry_characteristics(self, industry: str) -> Dict[str, Any]:
        """Get detailed characteristics for an industry"""
        return self.industry_rules.get_industry_characteristics(industry)

    def list_supported_business_types(self) -> List[str]:
        """Get list of all supported business types"""
        return self.business_analyzer.list_business_types()

    def get_business_types_by_category(self, category: str) -> List[str]:
        """Get business types for a specific category"""
        return self.business_analyzer.get_business_types_by_category(category)

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and health metrics"""
        try:
            # Test basic functionality
            test_result = self.get_optimal_methodology("restaurant")

            return {
                "status": "healthy",
                "components": {
                    "business_analyzer": "operational",
                    "methodology_selector": "operational",
                    "industry_rules": "operational",
                    "scoring_engine": "operational",
                },
                "supported_business_types": len(self.list_supported_business_types()),
                "last_test_result": test_result.primary_methodology.value,
                "version": "2.0.0",
            }
        except DataValidationError as e:
            logger.error(f"System status check failed: {e}")
            return {
                "status": "degraded",
                "error": str(e),
                "components": {
                    "business_analyzer": "unknown",
                    "methodology_selector": "unknown",
                    "industry_rules": "unknown",
                    "scoring_engine": "unknown",
                },
            }


# Global instance for backward compatibility
business_type_mapper = BusinessTypeMethodologyMapperRefactored()
