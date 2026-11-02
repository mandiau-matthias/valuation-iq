from src.utils.exceptions import MethodologyError

"""
Scoring Engine

Handles scoring calculations and methodology confidence assessment.
Provides quantitative analysis for methodology selection decisions.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from .mapper_types import ValuationMethodology, MethodologyDecision

logger = get_logger(__name__)


class ScoringEngine:
    """Handles scoring calculations and confidence assessment"""

    def __init__(self):
        self.scoring_weights = self._build_scoring_weights()
        self.confidence_factors = self._build_confidence_factors()

    def _build_scoring_weights(self) -> Dict[str, Decimal]:
        """Build weights for different scoring factors"""
        return {
            'business_type_match': Decimal('0.3'),
            'industry_alignment': Decimal('0.25'),
            'revenue_size_fit': Decimal('0.2'),
            'business_maturity': Decimal('0.15'),
            'data_availability': Decimal('0.1')
        }

    def _build_confidence_factors(self) -> Dict[str, Dict[str, Decimal]]:
        """Build confidence factors for different scenarios"""
        return {
            'high_confidence': {
                'business_type_match': Decimal('0.9'),
                'industry_alignment': Decimal('0.8'),
                'revenue_size_fit': Decimal('0.8'),
                'business_maturity': Decimal('0.7'),
                'data_availability': Decimal('0.8')
            },
            'medium_confidence': {
                'business_type_match': Decimal('0.7'),
                'industry_alignment': Decimal('0.6'),
                'revenue_size_fit': Decimal('0.6'),
                'business_maturity': Decimal('0.5'),
                'data_availability': Decimal('0.6')
            },
            'low_confidence': {
                'business_type_match': Decimal('0.5'),
                'industry_alignment': Decimal('0.4'),
                'revenue_size_fit': Decimal('0.4'),
                'business_maturity': Decimal('0.3'),
                'data_availability': Decimal('0.4')
            }
        }

    def calculate_methodology_score(
        self,
        methodology: ValuationMethodology,
        business_type: str,
        industry: Optional[str] = None,
        revenue: Optional[Decimal] = None,
        years_in_operation: Optional[int] = None,
        data_quality: str = "medium"
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive score for a methodology choice

        Returns:
            Dictionary with score breakdown and recommendations
        """
        try:
            # Calculate individual factor scores
            business_type_score = self._calculate_business_type_score(methodology, business_type)
            industry_score = self._calculate_industry_score(methodology, industry)
            revenue_score = self._calculate_revenue_score(methodology, revenue)
            maturity_score = self._calculate_maturity_score(methodology, years_in_operation)
            data_score = self._calculate_data_score(methodology, data_quality)

            # Calculate weighted overall score
            scores = {
                'business_type_match': business_type_score,
                'industry_alignment': industry_score,
                'revenue_size_fit': revenue_score,
                'business_maturity': maturity_score,
                'data_availability': data_score
            }

            overall_score = self._calculate_weighted_score(scores)

            # Determine confidence level
            confidence_level = self._determine_confidence_level(overall_score)

            # Generate recommendations
            recommendations = self._generate_recommendations(scores, methodology)

            return {
                'methodology': methodology.value,
                'overall_score': overall_score,
                'confidence_level': confidence_level,
                'factor_scores': scores,
                'recommendations': recommendations,
                'is_recommended': overall_score >= Decimal('0.7')
            }

        except MethodologyError as e:
            logger.error(f"Error calculating methodology score: {e}")
            return {
                'methodology': methodology.value,
                'overall_score': Decimal('0.5'),
                'confidence_level': 'medium',
                'factor_scores': {},
                'recommendations': ['Unable to calculate detailed score'],
                'is_recommended': False
            }

    def _calculate_business_type_score(
        self, 
        methodology: ValuationMethodology, 
        business_type: str
    ) -> Decimal:
        """Calculate score based on business type compatibility"""

        # Business type to methodology compatibility matrix
        compatibility_matrix = {
            'saas': {
                ValuationMethodology.DCF: Decimal('0.9'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.95'),
                ValuationMethodology.MULTIPLES: Decimal('0.7'),
                ValuationMethodology.ASSET_BASED: Decimal('0.2')
            },
            'restaurant': {
                ValuationMethodology.MULTIPLES: Decimal('0.9'),
                ValuationMethodology.DCF: Decimal('0.7'),
                ValuationMethodology.ASSET_BASED: Decimal('0.6'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.3')
            },
            'manufacturing': {
                ValuationMethodology.ASSET_BASED: Decimal('0.9'),
                ValuationMethodology.MULTIPLES: Decimal('0.8'),
                ValuationMethodology.DCF: Decimal('0.6'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.2')
            },
            'consulting': {
                ValuationMethodology.MULTIPLES: Decimal('0.9'),
                ValuationMethodology.DCF: Decimal('0.7'),
                ValuationMethodology.ASSET_BASED: Decimal('0.3'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.2')
            },
            'retail': {
                ValuationMethodology.MULTIPLES: Decimal('0.8'),
                ValuationMethodology.ASSET_BASED: Decimal('0.7'),
                ValuationMethodology.DCF: Decimal('0.6'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.3')
            }
        }

        business_type_lower = business_type.lower()
        if business_type_lower in compatibility_matrix:
            return compatibility_matrix[business_type_lower].get(methodology, Decimal('0.5'))

        # Default scoring for unknown business types
        default_scores = {
            ValuationMethodology.MULTIPLES: Decimal('0.7'),
            ValuationMethodology.DCF: Decimal('0.6'),
            ValuationMethodology.ASSET_BASED: Decimal('0.5'),
            ValuationMethodology.ARR_MULTIPLES: Decimal('0.4')
        }

        return default_scores.get(methodology, Decimal('0.5'))

    def _calculate_industry_score(
        self, 
        methodology: ValuationMethodology, 
        industry: Optional[str]
    ) -> Decimal:
        """Calculate score based on industry alignment"""

        if not industry:
            return Decimal('0.5')  # Neutral score for unknown industry

        # Industry to methodology alignment
        industry_alignment = {
            'technology': {
                ValuationMethodology.DCF: Decimal('0.9'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.8'),
                ValuationMethodology.MULTIPLES: Decimal('0.6'),
                ValuationMethodology.ASSET_BASED: Decimal('0.3')
            },
            'manufacturing': {
                ValuationMethodology.ASSET_BASED: Decimal('0.9'),
                ValuationMethodology.MULTIPLES: Decimal('0.8'),
                ValuationMethodology.DCF: Decimal('0.6'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.2')
            },
            'services': {
                ValuationMethodology.MULTIPLES: Decimal('0.9'),
                ValuationMethodology.DCF: Decimal('0.7'),
                ValuationMethodology.ASSET_BASED: Decimal('0.3'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.2')
            },
            'retail': {
                ValuationMethodology.MULTIPLES: Decimal('0.8'),
                ValuationMethodology.ASSET_BASED: Decimal('0.7'),
                ValuationMethodology.DCF: Decimal('0.6'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.3')
            },
            'healthcare': {
                ValuationMethodology.DCF: Decimal('0.8'),
                ValuationMethodology.MULTIPLES: Decimal('0.7'),
                ValuationMethodology.ASSET_BASED: Decimal('0.5'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.3')
            }
        }

        industry_lower = industry.lower()
        for industry_key, scores in industry_alignment.items():
            if industry_key in industry_lower:
                return scores.get(methodology, Decimal('0.5'))

        return Decimal('0.5')  # Default score for unknown industry

    def _calculate_revenue_score(
        self, 
        methodology: ValuationMethodology, 
        revenue: Optional[Decimal]
    ) -> Decimal:
        """Calculate score based on revenue size appropriateness"""

        if revenue is None:
            return Decimal('0.5')  # Neutral score for unknown revenue

        # Revenue size to methodology appropriateness
        if revenue < 100000:  # < €100K
            scores = {
                ValuationMethodology.MULTIPLES: Decimal('0.8'),
                ValuationMethodology.ASSET_BASED: Decimal('0.7'),
                ValuationMethodology.DCF: Decimal('0.4'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.3')
            }
        elif revenue < 1000000:  # < €1M
            scores = {
                ValuationMethodology.MULTIPLES: Decimal('0.9'),
                ValuationMethodology.ASSET_BASED: Decimal('0.8'),
                ValuationMethodology.DCF: Decimal('0.6'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.5')
            }
        elif revenue < 10000000:  # < €10M
            scores = {
                ValuationMethodology.DCF: Decimal('0.9'),
                ValuationMethodology.MULTIPLES: Decimal('0.8'),
                ValuationMethodology.ASSET_BASED: Decimal('0.6'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.7')
            }
        else:  # > €10M
            scores = {
                ValuationMethodology.DCF: Decimal('0.9'),
                ValuationMethodology.MULTIPLES: Decimal('0.7'),
                ValuationMethodology.ASSET_BASED: Decimal('0.5'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.8')
            }

        return scores.get(methodology, Decimal('0.5'))

    def _calculate_maturity_score(
        self, 
        methodology: ValuationMethodology, 
        years_in_operation: Optional[int]
    ) -> Decimal:
        """Calculate score based on business maturity"""

        if not years_in_operation:
            return Decimal('0.5')  # Neutral score for unknown maturity

        # Business maturity to methodology appropriateness
        if years_in_operation < 2:  # Early stage
            scores = {
                ValuationMethodology.DCF: Decimal('0.8'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.7'),
                ValuationMethodology.MULTIPLES: Decimal('0.5'),
                ValuationMethodology.ASSET_BASED: Decimal('0.4')
            }
        elif years_in_operation < 5:  # Growth stage
            scores = {
                ValuationMethodology.DCF: Decimal('0.9'),
                ValuationMethodology.MULTIPLES: Decimal('0.8'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.7'),
                ValuationMethodology.ASSET_BASED: Decimal('0.5')
            }
        elif years_in_operation < 10:  # Established
            scores = {
                ValuationMethodology.MULTIPLES: Decimal('0.9'),
                ValuationMethodology.DCF: Decimal('0.8'),
                ValuationMethodology.ASSET_BASED: Decimal('0.7'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.6')
            }
        else:  # Mature
            scores = {
                ValuationMethodology.MULTIPLES: Decimal('0.9'),
                ValuationMethodology.ASSET_BASED: Decimal('0.8'),
                ValuationMethodology.DCF: Decimal('0.7'),
                ValuationMethodology.ARR_MULTIPLES: Decimal('0.5')
            }

        return scores.get(methodology, Decimal('0.5'))

    def _calculate_data_score(
        self, 
        methodology: ValuationMethodology, 
        data_quality: str
    ) -> Decimal:
        """Calculate score based on data quality requirements"""

        # Data quality requirements for different methodologies
        data_requirements = {
            ValuationMethodology.DCF: {'high': Decimal('0.9'), 'medium': Decimal('0.6'), 'low': 0.3},
            ValuationMethodology.ARR_MULTIPLES: {'high': Decimal('0.8'), 'medium': Decimal('0.7'), 'low': 0.4},
            ValuationMethodology.MULTIPLES: {'high': Decimal('0.8'), 'medium': Decimal('0.7'), 'low': 0.5},
            ValuationMethodology.ASSET_BASED: {'high': Decimal('0.9'), 'medium': Decimal('0.8'), 'low': 0.6}
        }

        methodology_requirements = data_requirements.get(methodology, {
            'high': Decimal('0.7'), 'medium': Decimal('0.6'), 'low': Decimal('0.4')
        })

        return methodology_requirements.get(data_quality, Decimal('0.5'))

    def _calculate_weighted_score(self, scores: Dict[str, Decimal]) -> Decimal:
        """Calculate weighted overall score using Decimal"""
        weighted_sum_decimal = Decimal('0.0')
        total_weight_decimal = Decimal('0.0')

        for factor, score in scores.items():
            weight_decimal = to_decimal(self.scoring_weights.get(factor, Decimal('0.1')))
            score_decimal = to_decimal(score)
            weighted_sum_decimal += score_decimal * weight_decimal
            total_weight_decimal += weight_decimal

        if total_weight_decimal > Decimal('0'):
            result_decimal = weighted_sum_decimal / total_weight_decimal
            return from_decimal(result_decimal)
        else:
            return Decimal('0.5')

    def _determine_confidence_level(self, score: Decimal) -> str:
        """Determine confidence level based on score"""
        if score >= 0.8:
            return 'high'
        elif score >= 0.6:
            return 'medium'
        else:
            return 'low'

    def _generate_recommendations(
        self, 
        scores: Dict[str, Decimal], 
        methodology: ValuationMethodology
    ) -> List[str]:
        """Generate recommendations based on score analysis"""
        recommendations = []

        # Check for low scores and provide recommendations
        for factor, score in scores.items():
            if score < 0.5:
                if factor == 'business_type_match':
                    recommendations.append(f"Consider alternative methodologies for this business type")
                elif factor == 'industry_alignment':
                    recommendations.append(f"Verify methodology alignment with industry standards")
                elif factor == 'revenue_size_fit':
                    recommendations.append(f"Assess if methodology is appropriate for business size")
                elif factor == 'business_maturity':
                    recommendations.append(f"Consider business stage when selecting methodology")
                elif factor == 'data_availability':
                    recommendations.append(f"Ensure sufficient data quality for {methodology.value} analysis")

        # Add positive recommendations for high scores
        high_score_factors = [factor for factor, score in scores.items() if score >= Decimal('0.8')]
        if high_score_factors:
            recommendations.append(f"Strong alignment in: {', '.join(high_score_factors)}")

        return recommendations

    def compare_methodologies(
        self,
        methodologies: List[ValuationMethodology],
        business_type: str,
        industry: Optional[str] = None,
        revenue: Optional[Decimal] = None,
        years_in_operation: Optional[int] = None,
        data_quality: str = "medium"
    ) -> List[Dict[str, Any]]:
        """Compare multiple methodologies and rank them"""

        comparison_results = []

        for methodology in methodologies:
            score_result = self.calculate_methodology_score(
                methodology, business_type, industry, revenue, years_in_operation, data_quality
            )
            comparison_results.append(score_result)

        # Sort by overall score (descending)
        comparison_results.sort(key=lambda x: x['overall_score'], reverse=True)

        return comparison_results

    def get_methodology_ranking(
        self,
        business_type: str,
        industry: Optional[str] = None,
        revenue: Optional[Decimal] = None,
        years_in_operation: Optional[int] = None,
        data_quality: str = "medium"
    ) -> List[Tuple[ValuationMethodology, float]]:
        """Get ranked list of methodologies for a business"""

        all_methodologies = [
            ValuationMethodology.DCF,
            ValuationMethodology.MULTIPLES,
            ValuationMethodology.ASSET_BASED,
            ValuationMethodology.ARR_MULTIPLES
        ]

        comparison_results = self.compare_methodologies(
            all_methodologies, business_type, industry, revenue, years_in_operation, data_quality
        )

        return [
            (ValuationMethodology(result['methodology']), result['overall_score'])
            for result in comparison_results
        ]