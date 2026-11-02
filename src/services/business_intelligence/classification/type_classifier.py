
"""
Business Type Classifier for Business Type Intelligence Service

This module provides business type classification capabilities including
business type detection, category classification, and industry mapping.
"""

from typing import Dict, Any, List, Optional, Tuple
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .intelligence_types import (
    BusinessTypeInsights,
    AnalysisRequest,
    AnalysisStatus,
    ConfidenceLevel
)

logger = get_logger(__name__)


class BusinessTypeClassifier:
    """
    Classifies business types and provides categorization.

    Provides business type classification including:
    - Business type detection from descriptions
    - Category classification
    - Industry mapping
    - Business model identification
    """

    def __init__(self):
        """Initialize the business type classifier"""
        self.logger = logger

        # Business type classification rules
        self.classification_rules = self._initialize_classification_rules()

        # Industry mapping
        self.industry_mapping = self._initialize_industry_mapping()

        # Business model patterns
        self.business_model_patterns = self._initialize_business_model_patterns()

    def classify_business_type(
        self, 
        description: str,
        industry: Optional[str] = None,
        business_model: Optional[str] = None
    ) -> Tuple[str, str, float]:
        """
        Classify business type from description

        Args:
            description: Business description
            industry: Optional industry hint
            business_model: Optional business model hint

        Returns:
            Tuple of (business_type, category, confidence)
        """
        try:
            # Normalize description
            normalized_description = self._normalize_description(description)

            # Extract keywords
            keywords = self._extract_keywords(normalized_description)

            # Classify based on keywords
            classification_result = self._classify_by_keywords(keywords)

            # Apply industry hints if available
            if industry:
                classification_result = self._apply_industry_hints(classification_result, industry)

            # Apply business model hints if available
            if business_model:
                classification_result = self._apply_business_model_hints(classification_result, business_model)

            # Calculate confidence
            confidence = self._calculate_classification_confidence(classification_result, keywords)

            business_type = classification_result['business_type']
            category = classification_result['category']

            self.logger.info(f"Classified business type: {business_type} (confidence: {confidence:.2f})")
            return business_type, category, confidence

        except Exception as e:
            self.logger.error(f"Error classifying business type: {e}")
            return 'other', 'other', Decimal('0.5')

    def get_business_insights(
        self, 
        business_type: str,
        category: str
    ) -> BusinessTypeInsights:
        """
        Get comprehensive insights for a business type

        Args:
            business_type: Classified business type
            category: Business category

        Returns:
            BusinessTypeInsights with comprehensive information
        """
        try:
            # Get business type specific insights
            insights = self._get_business_type_insights(business_type)

            # Get category specific insights
            category_insights = self._get_category_insights(category)

            # Merge insights
            merged_insights = self._merge_insights(insights, category_insights)

            # Determine analysis status and confidence
            analysis_status = self._determine_analysis_status(business_type)
            confidence_level = self._determine_confidence_level(merged_insights)

            return BusinessTypeInsights(
                business_type=business_type,
                analysis_status=analysis_status,
                confidence_level=confidence_level,
                key_insights=merged_insights.get('key_insights', []),
                recommendations=merged_insights.get('recommendations', []),
                risk_factors=merged_insights.get('risk_factors', []),
                growth_opportunities=merged_insights.get('growth_opportunities', []),
                market_positioning=merged_insights.get('market_positioning', 'Unknown'),
                competitive_advantages=merged_insights.get('competitive_advantages', []),
                valuation_considerations=merged_insights.get('valuation_considerations', [])
            )

        except Exception as e:
            self.logger.error(f"Error getting business insights: {e}")
            return self._get_default_insights(business_type)

    def _initialize_classification_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize business type classification rules"""
        return {
            'technology': {
                'keywords': ['software', 'app', 'saas', 'tech', 'digital', 'platform', 'api', 'cloud', 'ai', 'data'],
                'business_models': ['saas', 'mobile_app', 'ecommerce', 'web_development'],
                'category': 'technology'
            },
            'healthcare': {
                'keywords': ['medical', 'health', 'clinic', 'doctor', 'patient', 'hospital', 'pharmacy', 'dental'],
                'business_models': ['medical_practice', 'dental_practice', 'pharmacy', 'telemedicine'],
                'category': 'healthcare'
            },
            'manufacturing': {
                'keywords': ['manufacturing', 'production', 'factory', 'equipment', 'machinery', 'assembly'],
                'business_models': ['manufacturing', 'automotive', 'electronics', 'textiles'],
                'category': 'industrial'
            },
            'services': {
                'keywords': ['consulting', 'service', 'advisory', 'support', 'management', 'professional'],
                'business_models': ['consulting', 'legal', 'accounting', 'marketing'],
                'category': 'services'
            },
            'retail': {
                'keywords': ['retail', 'store', 'shop', 'sales', 'merchandise', 'customer', 'product'],
                'business_models': ['retail', 'fashion', 'electronics_retail', 'specialty_store'],
                'category': 'retail'
            },
            'food_beverage': {
                'keywords': ['restaurant', 'food', 'catering', 'coffee', 'brewery', 'bakery', 'dining'],
                'business_models': ['restaurant', 'catering', 'coffee_shop', 'food_truck'],
                'category': 'food_beverage'
            },
            'real_estate': {
                'keywords': ['real estate', 'property', 'construction', 'development', 'rental', 'commercial'],
                'business_models': ['real_estate', 'property_development', 'construction'],
                'category': 'real_estate'
            }
        }

    def _initialize_industry_mapping(self) -> Dict[str, str]:
        """Initialize industry to category mapping"""
        return {
            'technology': 'technology',
            'software': 'technology',
            'healthcare': 'healthcare',
            'medical': 'healthcare',
            'manufacturing': 'industrial',
            'automotive': 'industrial',
            'services': 'services',
            'consulting': 'services',
            'retail': 'retail',
            'fashion': 'retail',
            'food': 'food_beverage',
            'restaurant': 'food_beverage',
            'real estate': 'real_estate',
            'construction': 'real_estate'
        }

    def _initialize_business_model_patterns(self) -> Dict[str, List[str]]:
        """Initialize business model patterns"""
        return {
            'b2b': ['business to business', 'b2b', 'enterprise', 'corporate'],
            'b2c': ['business to consumer', 'b2c', 'consumer', 'retail'],
            'saas': ['software as a service', 'saas', 'subscription', 'recurring'],
            'marketplace': ['marketplace', 'platform', 'two-sided', 'multi-sided'],
            'ecommerce': ['ecommerce', 'online store', 'digital retail', 'online sales'],
            'consulting': ['consulting', 'advisory', 'professional services', 'expertise'],
            'manufacturing': ['manufacturing', 'production', 'assembly', 'factory'],
            'retail': ['retail', 'store', 'shop', 'merchandise']
        }

    def _normalize_description(self, description: str) -> str:
        """Normalize business description for analysis"""
        try:
            # Convert to lowercase
            normalized = description.lower()

            # Remove special characters
            import re
            normalized = re.sub(r'[^\w\s]', ' ', normalized)

            # Remove extra whitespace
            normalized = ' '.join(normalized.split())

            return normalized

        except Exception as e:
            self.logger.error(f"Error normalizing description: {e}")
            return description.lower()

    def _extract_keywords(self, description: str) -> List[str]:
        """Extract keywords from business description"""
        try:
            # Split into words
            words = description.split()

            # Filter out common words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'}

            # Extract meaningful keywords
            keywords = [word for word in words if word not in stop_words and len(word) > 2]

            return keywords

        except Exception as e:
            self.logger.error(f"Error extracting keywords: {e}")
            return []

    def _classify_by_keywords(self, keywords: List[str]) -> Dict[str, Any]:
        """Classify business type based on keywords"""
        try:
            best_match = {
                'business_type': 'other',
                'category': 'other',
                'confidence': Decimal('0.0'),
                'matched_keywords': []
            }

            # Check each classification rule
            for business_type, rules in self.classification_rules.items():
                matched_keywords = []
                for keyword in keywords:
                    if keyword in rules['keywords']:
                        matched_keywords.append(keyword)

                # Calculate confidence based on matched keywords
                if matched_keywords:
                    confidence = len(matched_keywords) / len(rules['keywords'])
                    if confidence > best_match['confidence']:
                        best_match = {
                            'business_type': business_type,
                            'category': rules['category'],
                            'confidence': confidence,
                            'matched_keywords': matched_keywords
                        }

            return best_match

        except Exception as e:
            self.logger.error(f"Error classifying by keywords: {e}")
            return {'business_type': 'other', 'category': 'other', 'confidence': Decimal('0.0'), 'matched_keywords': []}

    def _apply_industry_hints(self, classification_result: Dict[str, Any], industry: str) -> Dict[str, Any]:
        """Apply industry hints to classification"""
        try:
            # Map industry to category
            category = self.industry_mapping.get(industry.lower(), 'other')

            # If industry hint matches classification, boost confidence
            if category == classification_result['category']:
                classification_result['confidence'] = min(Decimal('1.0'), classification_result['confidence'] + Decimal('0.2'))

            return classification_result

        except Exception as e:
            self.logger.error(f"Error applying industry hints: {e}")
            return classification_result

    def _apply_business_model_hints(self, classification_result: Dict[str, Any], business_model: str) -> Dict[str, Any]:
        """Apply business model hints to classification"""
        try:
            # Check if business model matches classification
            business_type = classification_result['business_type']
            if business_type in self.classification_rules:
                business_models = self.classification_rules[business_type]['business_models']
                if business_model.lower() in [bm.lower() for bm in business_models]:
                    classification_result['confidence'] = min(Decimal('1.0'), classification_result['confidence'] + Decimal('0.1'))

            return classification_result

        except Exception as e:
            self.logger.error(f"Error applying business model hints: {e}")
            return classification_result

    def _calculate_classification_confidence(self, classification_result: Dict[str, Any], keywords: List[str]) -> Decimal:
        """Calculate classification confidence"""
        try:
            base_confidence = classification_result['confidence']

            # Boost confidence for more keywords
            keyword_boost = min(Decimal('0.2'), len(keywords) * Decimal('0.02'))

            # Boost confidence for specific business types
            business_type = classification_result['business_type']
            if business_type in ['technology', 'healthcare', 'manufacturing']:
                business_type_boost = Decimal('0.1')
            else:
                business_type_boost = Decimal('0.0')

            total_confidence = base_confidence + keyword_boost + business_type_boost

            return min(Decimal('1.0'), max(Decimal('0.0'), total_confidence))

        except Exception as e:
            self.logger.error(f"Error calculating classification confidence: {e}")
            return Decimal('0.5')

    def _get_business_type_insights(self, business_type: str) -> Dict[str, Any]:
        """Get insights for specific business type"""
        try:
            insights_map = {
                'technology': {
                    'key_insights': ['High growth potential', 'Technology-driven', 'Scalable business model'],
                    'recommendations': ['Focus on innovation', 'Build strong technical team', 'Invest in R&D'],
                    'risk_factors': ['Technology disruption', 'Competition', 'Regulatory changes'],
                    'growth_opportunities': ['Market expansion', 'Product development', 'Partnerships'],
                    'market_positioning': 'Innovation leader',
                    'competitive_advantages': ['Technical expertise', 'First-mover advantage', 'Network effects'],
                    'valuation_considerations': ['Growth rate', 'Market size', 'Competitive position']
                },
                'healthcare': {
                    'key_insights': ['Regulated industry', 'High barriers to entry', 'Stable demand'],
                    'recommendations': ['Ensure compliance', 'Build reputation', 'Focus on quality'],
                    'risk_factors': ['Regulatory compliance', 'Medical liability', 'Cost pressures'],
                    'growth_opportunities': ['Service expansion', 'Technology adoption', 'Market growth'],
                    'market_positioning': 'Quality healthcare provider',
                    'competitive_advantages': ['Medical expertise', 'Patient relationships', 'Regulatory compliance'],
                    'valuation_considerations': ['Regulatory environment', 'Patient base', 'Service quality']
                },
                'manufacturing': {
                    'key_insights': ['Asset-intensive', 'Operational efficiency', 'Supply chain dependent'],
                    'recommendations': ['Optimize operations', 'Manage supply chain', 'Invest in equipment'],
                    'risk_factors': ['Supply chain disruption', 'Equipment maintenance', 'Labor costs'],
                    'growth_opportunities': ['Process improvement', 'Product innovation', 'Market expansion'],
                    'market_positioning': 'Efficient manufacturer',
                    'competitive_advantages': ['Operational efficiency', 'Quality control', 'Cost management'],
                    'valuation_considerations': ['Asset value', 'Operational efficiency', 'Market demand']
                }
            }

            return insights_map.get(business_type, {
                'key_insights': ['General business insights'],
                'recommendations': ['Focus on core business'],
                'risk_factors': ['Market competition'],
                'growth_opportunities': ['Market expansion'],
                'market_positioning': 'Market participant',
                'competitive_advantages': ['Business expertise'],
                'valuation_considerations': ['Financial performance']
            })

        except Exception as e:
            self.logger.error(f"Error getting business type insights: {e}")
            return {}

    def _get_category_insights(self, category: str) -> Dict[str, Any]:
        """Get insights for business category"""
        try:
            category_insights = {
                'technology': {
                    'key_insights': ['Innovation-driven', 'High growth potential', 'Technology adoption'],
                    'recommendations': ['Invest in technology', 'Build technical team', 'Focus on innovation'],
                    'risk_factors': ['Technology disruption', 'Competition', 'Market volatility'],
                    'growth_opportunities': ['Market expansion', 'Product development', 'Technology adoption'],
                    'market_positioning': 'Technology leader',
                    'competitive_advantages': ['Technical expertise', 'Innovation', 'Market knowledge'],
                    'valuation_considerations': ['Growth potential', 'Market size', 'Competitive position']
                },
                'healthcare': {
                    'key_insights': ['Regulated industry', 'Stable demand', 'Quality focus'],
                    'recommendations': ['Ensure compliance', 'Focus on quality', 'Build reputation'],
                    'risk_factors': ['Regulatory compliance', 'Medical liability', 'Cost pressures'],
                    'growth_opportunities': ['Service expansion', 'Technology adoption', 'Market growth'],
                    'market_positioning': 'Quality healthcare provider',
                    'competitive_advantages': ['Medical expertise', 'Patient relationships', 'Regulatory compliance'],
                    'valuation_considerations': ['Regulatory environment', 'Patient base', 'Service quality']
                }
            }

            return category_insights.get(category, {
                'key_insights': ['Industry-specific insights'],
                'recommendations': ['Industry best practices'],
                'risk_factors': ['Industry risks'],
                'growth_opportunities': ['Industry opportunities'],
                'market_positioning': 'Industry participant',
                'competitive_advantages': ['Industry expertise'],
                'valuation_considerations': ['Industry factors']
            })

        except Exception as e:
            self.logger.error(f"Error getting category insights: {e}")
            return {}

    def _merge_insights(self, business_insights: Dict[str, Any], category_insights: Dict[str, Any]) -> Dict[str, Any]:
        """Merge business type and category insights"""
        try:
            merged = {}

            # Merge each insight category
            for key in ['key_insights', 'recommendations', 'risk_factors', 'growth_opportunities', 'competitive_advantages', 'valuation_considerations']:
                business_items = business_insights.get(key, [])
                category_items = category_insights.get(key, [])

                # Combine and deduplicate
                combined_items = list(set(business_items + category_items))
                merged[key] = combined_items

            # Use business type insights for market positioning
            merged['market_positioning'] = business_insights.get('market_positioning', category_insights.get('market_positioning', 'Unknown'))

            return merged

        except Exception as e:
            self.logger.error(f"Error merging insights: {e}")
            return business_insights

    def _determine_analysis_status(self, business_type: str) -> AnalysisStatus:
        """Determine analysis status based on business type"""
        try:
            # Well-known business types have completed analysis
            known_types = ['technology', 'healthcare', 'manufacturing', 'services', 'retail', 'food_beverage']

            if business_type in known_types:
                return AnalysisStatus.COMPLETED
            else:
                return AnalysisStatus.PENDING

        except Exception as e:
            self.logger.error(f"Error determining analysis status: {e}")
            return AnalysisStatus.PENDING

    def _determine_confidence_level(self, insights: Dict[str, Any]) -> ConfidenceLevel:
        """Determine confidence level based on insights"""
        try:
            # Count insights to determine confidence
            total_insights = sum(len(insights.get(key, [])) for key in ['key_insights', 'recommendations', 'risk_factors', 'growth_opportunities'])

            if total_insights >= 20:
                return ConfidenceLevel.VERY_HIGH
            elif total_insights >= 15:
                return ConfidenceLevel.HIGH
            elif total_insights >= 10:
                return ConfidenceLevel.MEDIUM
            else:
                return ConfidenceLevel.LOW

        except Exception as e:
            self.logger.error(f"Error determining confidence level: {e}")
            return ConfidenceLevel.LOW

    def _get_default_insights(self, business_type: str) -> BusinessTypeInsights:
        """Get default insights when analysis fails"""
        return BusinessTypeInsights(
            business_type=business_type,
            analysis_status=AnalysisStatus.PENDING,
            confidence_level=ConfidenceLevel.LOW,
            key_insights=['Insufficient data for analysis'],
            recommendations=['Gather more business information'],
            risk_factors=['Unknown risks'],
            growth_opportunities=['Market expansion'],
            market_positioning='Unknown',
            competitive_advantages=['Business expertise'],
            valuation_considerations=['Financial performance']
        )
