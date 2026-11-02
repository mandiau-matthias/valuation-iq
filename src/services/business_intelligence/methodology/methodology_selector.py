"""
Methodology Selector

Handles the selection and refinement of valuation methodologies based on
business characteristics and additional factors.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import ConfigurationError
from src.utils.logging import get_logger

from ..integration.mapper_types import MethodologyDecision, RefinementFactors, ValuationMethodology
from .time_estimates import methodology_time_estimate

logger = get_logger(__name__)


def _configured_methodologies(
    base_config: Dict[str, Any],
) -> tuple[ValuationMethodology, Optional[ValuationMethodology]]:
    primary = ValuationMethodology(base_config["primary"])
    secondary = (
        ValuationMethodology(base_config["secondary"]) if base_config.get("secondary") else None
    )
    return primary, secondary


def _initial_refinement_confidence(
    *,
    industry: Optional[str],
    revenue: Optional[Decimal],
    years_in_operation: Optional[int],
) -> Decimal:
    confidence = Decimal("0.8")
    if revenue and years_in_operation:
        confidence += Decimal("0.1")
    if industry:
        confidence += Decimal("0.05")
    return confidence


def _apply_maturity_refinement(
    primary: ValuationMethodology,
    confidence: Decimal,
    years_in_operation: Optional[int],
) -> tuple[ValuationMethodology, Decimal]:
    if not years_in_operation:
        return primary, confidence
    if years_in_operation < 2 and primary == ValuationMethodology.MULTIPLES:
        return ValuationMethodology.DCF, confidence - Decimal("0.1")
    if years_in_operation > 10 and primary == ValuationMethodology.DCF:
        return ValuationMethodology.MULTIPLES, confidence + Decimal("0.05")
    return primary, confidence


def _apply_revenue_refinement(
    primary: ValuationMethodology,
    confidence: Decimal,
    revenue: Optional[Decimal],
) -> tuple[ValuationMethodology, Decimal]:
    if not revenue:
        return primary, confidence
    if revenue < 100000 and primary in [
        ValuationMethodology.DCF,
        ValuationMethodology.ARR_MULTIPLES,
    ]:
        return ValuationMethodology.MULTIPLES, confidence - Decimal("0.1")
    if revenue > 10000000 and primary == ValuationMethodology.MULTIPLES:
        return ValuationMethodology.DCF, confidence + Decimal("0.05")
    return primary, confidence


def _refinement_reasoning(
    base_reasoning: str,
    *,
    revenue: Optional[Decimal],
    years_in_operation: Optional[int],
) -> str:
    reasoning = base_reasoning
    if years_in_operation and years_in_operation < 2:
        reasoning += " Early-stage businesses benefit from growth-focused DCF analysis."
    elif years_in_operation and years_in_operation > 10:
        reasoning += (
            " Mature businesses with stable operations are well-suited for market multiples."
        )

    if revenue and revenue < 100000:
        reasoning += " Small businesses typically use simpler valuation methods."
    elif revenue and revenue > 10000000:
        reasoning += " Large businesses require sophisticated DCF analysis for accurate valuation."
    return reasoning


class MethodologySelector:
    """Selects and refines valuation methodologies"""

    def __init__(self):
        self.industry_factors = self._build_industry_factors()

    def _build_industry_factors(self) -> Dict[str, Dict[str, Any]]:
        """Build industry-specific factors that influence methodology selection"""
        return {
            "technology": {
                "growth_potential": "high",
                "asset_intensity": "low",
                "revenue_predictability": "medium",
                "key_metrics": ["growth_rate", "retention", "unit_economics"],
            },
            "manufacturing": {
                "growth_potential": "medium",
                "asset_intensity": "high",
                "revenue_predictability": "high",
                "key_metrics": ["capacity_utilization", "efficiency", "supply_chain"],
            },
            "services": {
                "growth_potential": "medium",
                "asset_intensity": "low",
                "revenue_predictability": "high",
                "key_metrics": ["client_retention", "utilization", "pricing_power"],
            },
            "retail": {
                "growth_potential": "low",
                "asset_intensity": "medium",
                "revenue_predictability": "medium",
                "key_metrics": ["same_store_sales", "inventory_turnover", "margins"],
            },
            "healthcare": {
                "growth_potential": "medium",
                "asset_intensity": "medium",
                "revenue_predictability": "high",
                "key_metrics": ["patient_volume", "reimbursement", "quality_metrics"],
            },
        }

    def select_optimal_methodology(
        self,
        business_type: str,
        industry: Optional[str] = None,
        revenue: Optional[Decimal] = None,
        years_in_operation: Optional[int] = None,
        country_code: str = "BE",
    ) -> MethodologyDecision:
        """
        Select optimal valuation methodology for a business type

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
            # Get base methodology from business type mapping
            base_config = self._get_base_methodology_config(business_type)

            if not base_config:
                # Fallback to industry-based methodology
                return self._get_industry_fallback_methodology(
                    industry, revenue, years_in_operation
                )

            # Refine methodology based on additional factors
            refined_decision = self._refine_methodology_decision(
                base_config, industry, revenue, years_in_operation, country_code
            )

            logger.info(
                f"Selected methodology for {business_type}: {refined_decision.primary_methodology.value}"
            )

            return refined_decision

        except ConfigurationError as e:
            logger.error(f"Error selecting methodology for {business_type}: {e}")
            # Return conservative fallback
            return self._get_conservative_fallback()

    def _get_base_methodology_config(self, business_type: str) -> Optional[Dict[str, Any]]:
        """Get base methodology configuration for business type"""
        # This would be populated by the business type analyzer
        # For now, return None to trigger fallback
        return None

    def _refine_methodology_decision(
        self,
        base_config: Dict[str, Any],
        industry: Optional[str],
        revenue: Optional[Decimal],
        years_in_operation: Optional[int],
        country_code: str,
    ) -> MethodologyDecision:
        """Refine methodology decision based on additional factors"""

        primary, secondary = _configured_methodologies(base_config)
        confidence = _initial_refinement_confidence(
            industry=industry,
            revenue=revenue,
            years_in_operation=years_in_operation,
        )
        primary, confidence = _apply_maturity_refinement(
            primary,
            confidence,
            years_in_operation,
        )
        primary, confidence = _apply_revenue_refinement(primary, confidence, revenue)
        reasoning = _refinement_reasoning(
            base_config["reasoning"],
            revenue=revenue,
            years_in_operation=years_in_operation,
        )

        return MethodologyDecision(
            primary_methodology=primary,
            secondary_methodology=secondary,
            confidence_score=min(confidence, 1.0),
            reasoning=reasoning,
            key_factors=base_config["key_factors"],
            special_considerations=base_config["special_considerations"],
            expected_accuracy=0.85 if confidence > 0.8 else 0.75,
            time_estimate=methodology_time_estimate(primary, revenue),
            multiple_types=base_config["multiple_types"],
            growth_weighted=base_config.get("growth_weighted", False),
            asset_intensity=base_config.get("asset_intensity", "medium"),
        )

    def _get_industry_fallback_methodology(
        self, industry: Optional[str], revenue: Optional[Decimal], years_in_operation: Optional[int]
    ) -> MethodologyDecision:
        """Fallback methodology selection based on industry"""

        if not industry:
            return self._get_conservative_fallback()

        industry_lower = industry.lower()

        # Technology/Software
        if any(term in industry_lower for term in ["technology", "software", "tech", "digital"]):
            return MethodologyDecision(
                primary_methodology=ValuationMethodology.DCF,
                secondary_methodology=ValuationMethodology.MULTIPLES,
                confidence_score=0.7,
                reasoning="Technology businesses typically have high growth potential, making DCF analysis most appropriate",
                key_factors=["growth_rate", "market_size", "competitive_advantage"],
                special_considerations=["technology_risk", "market_adoption", "scalability"],
                expected_accuracy=0.75,
                time_estimate="2-3 hours",
                multiple_types=["revenue", "ebitda"],
                growth_weighted=True,
                asset_intensity="low",
            )

        # Manufacturing/Industrial
        elif any(term in industry_lower for term in ["manufacturing", "industrial", "production"]):
            return MethodologyDecision(
                primary_methodology=ValuationMethodology.ASSET_BASED,
                secondary_methodology=ValuationMethodology.MULTIPLES,
                confidence_score=0.7,
                reasoning="Manufacturing businesses are asset-intensive, making asset-based valuation most appropriate",
                key_factors=["equipment", "inventory", "facilities", "supply_chain"],
                special_considerations=["equipment_age", "maintenance_costs", "raw_material_costs"],
                expected_accuracy=0.75,
                time_estimate="1-2 hours",
                multiple_types=["revenue", "ebitda"],
                growth_weighted=False,
                asset_intensity="high",
            )

        # Services
        elif any(term in industry_lower for term in ["services", "consulting", "professional"]):
            return MethodologyDecision(
                primary_methodology=ValuationMethodology.MULTIPLES,
                secondary_methodology=ValuationMethodology.DCF,
                confidence_score=0.7,
                reasoning="Service businesses are people-based with predictable revenue streams, suitable for market multiples",
                key_factors=["client_base", "expertise", "reputation", "talent"],
                special_considerations=["key_person_risk", "client_retention", "talent_retention"],
                expected_accuracy=0.75,
                time_estimate="1-2 hours",
                multiple_types=["revenue", "ebitda"],
                growth_weighted=False,
                asset_intensity="low",
            )

        # Default fallback
        else:
            return self._get_conservative_fallback()

    def _get_conservative_fallback(self) -> MethodologyDecision:
        """Conservative fallback methodology"""
        return MethodologyDecision(
            primary_methodology=ValuationMethodology.MULTIPLES,
            secondary_methodology=ValuationMethodology.ASSET_BASED,
            confidence_score=0.6,
            reasoning="Using conservative market multiples approach for general business valuation",
            key_factors=["revenue", "profitability", "market_position"],
            special_considerations=["market_conditions", "industry_trends", "competitive_position"],
            expected_accuracy=0.7,
            time_estimate="1-2 hours",
            multiple_types=["revenue", "ebitda"],
            growth_weighted=False,
            asset_intensity="medium",
        )

    def get_methodology_recommendations(
        self, business_type: str, industry: Optional[str] = None
    ) -> List[MethodologyDecision]:
        """Get multiple methodology recommendations with different approaches"""
        recommendations = []

        # Primary recommendation
        primary = self.select_optimal_methodology(business_type, industry)
        recommendations.append(primary)

        # Alternative approaches
        if primary.primary_methodology == ValuationMethodology.DCF:
            # Add multiples alternative
            alternative = MethodologyDecision(
                primary_methodology=ValuationMethodology.MULTIPLES,
                secondary_methodology=ValuationMethodology.DCF,
                confidence_score=0.7,
                reasoning="Market multiples provide a quick validation of DCF assumptions",
                key_factors=primary.key_factors,
                special_considerations=primary.special_considerations,
                expected_accuracy=0.75,
                time_estimate="1-2 hours",
                multiple_types=primary.multiple_types,
                growth_weighted=False,
                asset_intensity=primary.asset_intensity,
            )
            recommendations.append(alternative)

        return recommendations

    def validate_methodology_choice(
        self,
        methodology: ValuationMethodology,
        business_type: str,
        revenue: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Validate if a methodology choice is appropriate for the business"""
        validation_result = {
            "is_appropriate": True,
            "confidence": 0.8,
            "warnings": [],
            "recommendations": [],
        }

        # Check methodology appropriateness based on business characteristics
        if methodology == ValuationMethodology.DCF:
            if revenue and revenue < 100000:
                validation_result["warnings"].append(
                    "DCF may be overly complex for small businesses"
                )
                validation_result["recommendations"].append(
                    "Consider using market multiples instead"
                )
                validation_result["confidence"] -= 0.2

        elif methodology == ValuationMethodology.MULTIPLES:
            if business_type in ["saas", "mobile_app", "fintech"]:
                validation_result["warnings"].append("Multiples may not capture growth potential")
                validation_result["recommendations"].append(
                    "Consider using DCF for growth-focused valuation"
                )
                validation_result["confidence"] -= 0.1

        elif methodology == ValuationMethodology.ASSET_BASED:
            if business_type in ["saas", "consulting", "legal"]:
                validation_result["warnings"].append(
                    "Asset-based valuation may undervalue service businesses"
                )
                validation_result["recommendations"].append(
                    "Consider using market multiples or DCF"
                )
                validation_result["confidence"] -= 0.3

        validation_result["confidence"] = max(0.0, min(1.0, validation_result["confidence"]))

        return validation_result
