
"""
Selection Engine

Handles methodology weight calculations, confidence scoring, and
intelligent selection logic for valuation methodology determination.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from .selector_types import (
    MethodologySelection, BusinessContext, FinancialScore, OwnerScore, MarketScore,
    ConfidenceLevel, METHODOLOGY_WEIGHTS, CONFIDENCE_THRESHOLDS
)

logger = get_logger(__name__)


class SelectionEngine:
    """Handles methodology selection logic and weight calculations"""

    def __init__(self):
        self.methodology_weights = METHODOLOGY_WEIGHTS
        self.confidence_thresholds = CONFIDENCE_THRESHOLDS

    def calculate_methodology_weights(
        self,
        business_score: Dict[str, Decimal],
        financial_score: FinancialScore,
        owner_score: Optional[OwnerScore],
        market_score: Optional[MarketScore],
        industry_score: Dict[str, Decimal]
    ) -> Tuple[float, float]:
        """Calculate final methodology weights"""

        try:
            logger.info("Calculating methodology weights")

            # Calculate DCF weight
            dcf_weight = self._calculate_dcf_weight(
                business_score, financial_score, owner_score, market_score, industry_score
            )

            # Calculate Multiples weight
            multiples_weight = self._calculate_multiples_weight(
                business_score, financial_score, owner_score, market_score, industry_score
            )

            # Normalize weights to sum to 1.0
            dcf_weight, multiples_weight = self._normalize_weights(dcf_weight, multiples_weight)

            logger.info(f"Methodology weights calculated: DCF={dcf_weight:.2f}, Multiples={multiples_weight:.2f}")

            return dcf_weight, multiples_weight

        except Exception as e:
            logger.error(f"Methodology weight calculation failed: {e}")
            return Decimal('0.5'), Decimal('0.5')

    def generate_recommendations(
        self,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        business_context: BusinessContext,
        financial_data: Dict[str, Any]
    ) -> List[str]:
        """Generate methodology recommendations"""

        try:
            logger.info("Generating methodology recommendations")

            recommendations = []

            # DCF recommendations
            if dcf_weight > 0.7:
                recommendations.append("DCF is the primary methodology due to strong financial fundamentals and growth potential")
            elif dcf_weight > 0.5:
                recommendations.append("DCF provides good valuation insights alongside other methodologies")
            else:
                recommendations.append("DCF has limited applicability due to business characteristics")

            # Multiples recommendations
            if multiples_weight > 0.7:
                recommendations.append("Multiples is the primary methodology due to strong market comparables and business stability")
            elif multiples_weight > 0.5:
                recommendations.append("Multiples provides good valuation insights alongside other methodologies")
            else:
                recommendations.append("Multiples has limited applicability due to lack of market comparables")

            # Industry-specific recommendations
            industry_recommendations = self._generate_industry_recommendations(
                business_context, dcf_weight, multiples_weight
            )
            recommendations.extend(industry_recommendations)

            logger.info(f"Generated {len(recommendations)} recommendations")

            return recommendations

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return ["Use both DCF and Multiples for validation"]

    def generate_reasoning(
        self,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        business_score: Dict[str, Decimal],
        financial_score: FinancialScore,
        owner_score: Optional[OwnerScore],
        market_score: Optional[MarketScore]
    ) -> str:
        """Generate reasoning for methodology selection"""

        try:
            logger.info("Generating methodology selection reasoning")

            reasoning_parts = []

            # DCF reasoning
            if dcf_weight > 0.6:
                reasoning_parts.append(f"DCF is preferred (weight: {dcf_weight:.1%}) due to:")
                if business_score.get("dcf_revenue", 0) > 0.7:
                    reasoning_parts.append("- Strong revenue base")
                if business_score.get("dcf_growth", 0) > 0.7:
                    reasoning_parts.append("- High growth potential")
                if financial_score.dcf_score > 0.7:
                    reasoning_parts.append("- Strong financial fundamentals")
                if owner_score and owner_score.dcf_impact > 0.8:
                    reasoning_parts.append("- Low owner dependency")

            # Multiples reasoning
            if multiples_weight > 0.6:
                reasoning_parts.append(f"Multiples is preferred (weight: {multiples_weight:.1%}) due to:")
                if business_score.get("multiples_market", 0) > 0.7:
                    reasoning_parts.append("- Strong market position")
                if financial_score.multiples_score > 0.7:
                    reasoning_parts.append("- Financial stability")
                if market_score and market_score.multiples_score > 0.7:
                    reasoning_parts.append("- Good market comparables")
                if owner_score and owner_score.multiples_impact > 1.0:
                    reasoning_parts.append("- High owner dependency")

            reasoning = " ".join(reasoning_parts)

            if not reasoning:
                reasoning = "Balanced methodology selection based on available data"

            logger.info("Methodology reasoning generated")

            return reasoning

        except Exception as e:
            logger.error(f"Reasoning generation failed: {e}")
            return "Default methodology selection"

    def generate_next_questions(
        self,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        business_context: BusinessContext,
        financial_data: Dict[str, Any]
    ) -> List[str]:
        """
        DEPRECATED: Question generation moved to Titan (The Brain).
        
        BRAIN & MUSCLE ARCHITECTURE:
        ValuationIQ (The Muscle) returns methodology weights and flags.
        Question generation is handled by Titan's TriageService via Claude.
        
        This method is kept for backward compatibility but returns empty list.
        """
        logger.debug("generate_next_questions called - DEPRECATED, returning empty list")
        return []

    def generate_methodology_notes(
        self,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        business_context: BusinessContext,
        financial_data: Dict[str, Any]
    ) -> str:
        """Generate methodology notes"""

        try:
            logger.info("Generating methodology notes")

            notes = []

            # DCF notes
            if dcf_weight > 0.7:
                notes.append("DCF is the primary methodology due to strong financial fundamentals and growth potential.")
            elif dcf_weight > 0.5:
                notes.append("DCF provides valuable insights alongside other methodologies.")
            else:
                notes.append("DCF has limited applicability due to business characteristics.")

            # Multiples notes
            if multiples_weight > 0.7:
                notes.append("Multiples is the primary methodology due to strong market comparables and business stability.")
            elif multiples_weight > 0.5:
                notes.append("Multiples provides valuable insights alongside other methodologies.")
            else:
                notes.append("Multiples has limited applicability due to lack of market comparables.")

            # Industry-specific notes
            industry_notes = self._generate_industry_notes(business_context, dcf_weight, multiples_weight)
            notes.extend(industry_notes)

            methodology_notes = " ".join(notes)

            logger.info("Methodology notes generated")

            return methodology_notes

        except Exception as e:
            logger.error(f"Notes generation failed: {e}")
            return "Default methodology selection"

    def calculate_confidence_score(self, dcf_weight: Decimal, multiples_weight: Decimal) -> Decimal:
        """Calculate confidence score for methodology selection using Decimal"""

        try:
            # Higher confidence when one methodology is clearly preferred
            dcf_weight_decimal = to_decimal(dcf_weight) if dcf_weight is not None else Decimal("0")
            multiples_weight_decimal = to_decimal(multiples_weight) if multiples_weight is not None else Decimal("1")
            
            max_weight_decimal = max(dcf_weight_decimal, multiples_weight_decimal)
            min_weight_decimal = min(dcf_weight_decimal, multiples_weight_decimal)

            # Calculate confidence based on weight difference
            weight_difference_decimal = max_weight_decimal - min_weight_decimal

            if max_weight_decimal > Decimal('0.8'):
                return Decimal('0.9')  # High confidence
            elif max_weight_decimal > Decimal('0.6'):
                return Decimal('0.7')  # Medium confidence
            elif max_weight_decimal > Decimal('0.4'):
                return Decimal('0.5')  # Low confidence
            else:
                return Decimal('0.3')  # Very low confidence

        except Exception as e:
            logger.error(f"Confidence score calculation failed: {e}")
            return Decimal('0.5')

    def determine_confidence_level(self, confidence_score: Decimal) -> ConfidenceLevel:
        """Determine confidence level from score"""

        if confidence_score >= self.confidence_thresholds["high"]:
            return ConfidenceLevel.HIGH
        elif confidence_score >= self.confidence_thresholds["medium"]:
            return ConfidenceLevel.MEDIUM
        elif confidence_score >= self.confidence_thresholds["low"]:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def _calculate_dcf_weight(
        self,
        business_score: Dict[str, Decimal],
        financial_score: FinancialScore,
        owner_score: Optional[OwnerScore],
        market_score: Optional[MarketScore],
        industry_score: Dict[str, Decimal]
    ) -> Decimal:
        """Calculate DCF weight"""

        dcf_weight = Decimal('0.0')

        # Business characteristics (30% weight)
        dcf_weight += (business_score.get("dcf_revenue", Decimal('0.5')) * self.methodology_weights["business_characteristics"] * Decimal('0.33'))
        dcf_weight += (business_score.get("dcf_ebitda", Decimal('0.5')) * self.methodology_weights["business_characteristics"] * Decimal('0.33'))
        dcf_weight += (business_score.get("dcf_growth", Decimal('0.5')) * self.methodology_weights["business_characteristics"] * Decimal('0.17'))
        dcf_weight += (business_score.get("dcf_age", Decimal('0.5')) * self.methodology_weights["business_characteristics"] * Decimal('0.17'))

        # Financial health (40% weight)
        dcf_weight += (financial_score.dcf_score * self.methodology_weights["financial_health"])

        # Owner dependency (20% weight)
        if owner_score:
            dcf_weight += (owner_score.dcf_impact * self.methodology_weights["owner_dependency"])
        else:
            dcf_weight += self.methodology_weights["owner_dependency"]  # Default weight

        # Market context (5% weight)
        if market_score:
            dcf_weight += (market_score.dcf_score * self.methodology_weights["market_context"])
        else:
            dcf_weight += self.methodology_weights["market_context"]  # Default weight

        # Industry rules (5% weight)
        dcf_weight += (industry_score.get("dcf_industry", Decimal('0.5')) * self.methodology_weights["industry_rules"])

        return dcf_weight

    def _calculate_multiples_weight(
        self,
        business_score: Dict[str, Decimal],
        financial_score: FinancialScore,
        owner_score: Optional[OwnerScore],
        market_score: Optional[MarketScore],
        industry_score: Dict[str, Decimal]
    ) -> Decimal:
        """Calculate Multiples weight"""

        multiples_weight = Decimal('0.0')

        # Business characteristics (30% weight)
        multiples_weight += (business_score.get("multiples_market", Decimal('0.5')) * self.methodology_weights["business_characteristics"])

        # Financial health (40% weight)
        multiples_weight += (financial_score.multiples_score * self.methodology_weights["financial_health"])

        # Owner dependency (20% weight)
        if owner_score:
            multiples_weight += (owner_score.multiples_impact * self.methodology_weights["owner_dependency"])
        else:
            multiples_weight += self.methodology_weights["owner_dependency"]  # Default weight

        # Market context (5% weight)
        if market_score:
            multiples_weight += (market_score.multiples_score * self.methodology_weights["market_context"])
        else:
            multiples_weight += self.methodology_weights["market_context"]  # Default weight

        # Industry rules (5% weight)
        multiples_weight += (industry_score.get("multiples_industry", Decimal('0.5')) * self.methodology_weights["industry_rules"])

        return multiples_weight

    def _normalize_weights(self, dcf_weight: Decimal, multiples_weight: Decimal) -> Tuple[float, float]:
        """Normalize weights to sum to 1.0"""

        total_weight = dcf_weight + multiples_weight

        if total_weight > 0:
            dcf_weight = dcf_weight / total_weight
            multiples_weight = multiples_weight / total_weight
        else:
            dcf_weight = Decimal('0.5')
            multiples_weight = Decimal('0.5')

        return dcf_weight, multiples_weight

    def _generate_industry_recommendations(
        self,
        business_context: BusinessContext,
        dcf_weight: Decimal,
        multiples_weight: Decimal
    ) -> List[str]:
        """Generate industry-specific recommendations"""

        recommendations = []

        # Technology industry recommendations
        if business_context.industry == "technology":
            recommendations.append("Focus on recurring revenue metrics and customer acquisition costs")
            if dcf_weight > 0.6:
                recommendations.append("Consider SaaS-specific DCF models for recurring revenue businesses")

        # Retail industry recommendations
        elif business_context.industry == "retail":
            recommendations.append("Focus on location value and foot traffic metrics")
            if multiples_weight > 0.6:
                recommendations.append("Use location-based multiples for retail businesses")

        # Manufacturing industry recommendations
        elif business_context.industry == "manufacturing":
            recommendations.append("Focus on production capacity and equipment value")
            if dcf_weight > 0.6:
                recommendations.append("Consider equipment depreciation in DCF models")

        # Services industry recommendations
        elif business_context.industry == "services":
            recommendations.append("Focus on hourly rates and client retention metrics")
            if multiples_weight > 0.6:
                recommendations.append("Use service-based multiples for professional services")

        return recommendations

    def _generate_industry_questions(self, business_context: BusinessContext) -> List[str]:
        """
        DEPRECATED: Question generation moved to Titan (The Brain).
        
        BRAIN & MUSCLE ARCHITECTURE:
        Industry-specific questions are generated by Titan's TriageService via Claude.
        
        Returns empty list for backward compatibility.
        """
        return []

    def _generate_industry_notes(
        self,
        business_context: BusinessContext,
        dcf_weight: Decimal,
        multiples_weight: Decimal
    ) -> List[str]:
        """Generate industry-specific notes"""

        notes = []

        # Technology industry notes
        if business_context.industry == "technology":
            if dcf_weight > 0.6:
                notes.append("Technology businesses with recurring revenue are well-suited for DCF analysis.")
            if multiples_weight > 0.6:
                notes.append("SaaS metrics and technology multiples provide good valuation benchmarks.")

        # Retail industry notes
        elif business_context.industry == "retail":
            if multiples_weight > 0.6:
                notes.append("Retail businesses benefit from location-based multiples and market comparables.")
            if dcf_weight > 0.6:
                notes.append("DCF analysis should consider location value and foot traffic patterns.")

        # Manufacturing industry notes
        elif business_context.industry == "manufacturing":
            if dcf_weight > 0.6:
                notes.append("Manufacturing businesses require careful consideration of equipment depreciation and capacity utilization.")
            if multiples_weight > 0.6:
                notes.append("Equipment value and production metrics are important for multiples analysis.")

        # Services industry notes
        elif business_context.industry == "services":
            if multiples_weight > 0.6:
                notes.append("Professional services businesses benefit from hourly rate multiples and client metrics.")
            if dcf_weight > 0.6:
                notes.append("DCF analysis should consider client retention and service capacity utilization.")

        return notes
