"""
Business Recommendation Engine Service

BANK-GRADE SRP-COMPLIANT: Business recommendations generation ONLY

WHAT: Generates strategic business recommendations
WHY: Single responsibility - recommendation generation
HOW: Analyzes business data and generates actionable insights

SINGLE RESPONSIBILITY: Recommendation generation
- Strategic recommendations
- Action prioritization
- Growth opportunities identification
- Risk mitigation advice

EXTRACTED FROM: BusinessTypeIntelligenceService (780 lines)
COMPLIANCE: Bank-Grade Excellence Framework - SRP Phase 1

=============================================================================
QUALITY ASSURANCE FLAG - AI RECOMMENDATIONS DISABLED
=============================================================================

As of January 2026, AI-generated recommendations are DISABLED in production
reports to ensure accuracy and prevent generic advice that could be incorrect
for specific businesses.

RATIONALE:
- Generic recommendations appeared for ALL businesses regardless of context
- Recommendations like "Transition to recurring revenue" could be wrong
- "Less is more" principle: calculated values only, no speculative advice
- Academic compliance: USPAP Standard 9, IVS 105

TO RE-ENABLE:
Set ENABLE_AI_RECOMMENDATIONS = True (requires QA approval)
=============================================================================
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal
from ..analysis.intelligence_types import BusinessTypeAnalysis

logger = get_logger(__name__)


# =============================================================================
# FEATURE FLAG: AI Recommendations Control
# =============================================================================
# Set to False to disable AI-generated recommendations in reports
# This prevents generic advice that could be factually incorrect for
# specific businesses. Reports will show only calculated values.
#
# Academic compliance: USPAP Standard 9, IVS 105
# Principle: "Less is more" - accuracy over comprehensiveness
# =============================================================================
ENABLE_AI_RECOMMENDATIONS = False


class Recommendation:
    """Single business recommendation"""
    def __init__(
        self,
        category: str,
        priority: str,
        title: str,
        description: str,
        impact: str,
        effort: str
    ):
        self.category = category
        self.priority = priority
        self.title = title
        self.description = description
        self.impact = impact
        self.effort = effort


class BusinessRecommendationEngine:
    """
    BANK-GRADE SRP-COMPLIANT: Business recommendations generation.
    
    SINGLE RESPONSIBILITY: Generate business recommendations ONLY.
    
    This service focuses solely on creating strategic, actionable recommendations
    based on business analysis, methodology selection, and risk assessment.
    
    Design Pattern: Service Pattern
    - Separates recommendation logic from analysis
    - Enables independent testing and customization
    - Allows extending with new recommendation types
    
    Responsibilities:
    - Strategic recommendation generation
    - Action item prioritization
    - Growth opportunity identification
    - Risk mitigation advice
    """
    
    def __init__(self):
        """
        Initialize business recommendation engine.
        
        SRP: Focused on recommendation generation only
        """
        self.logger = logger
        
        # Recommendation thresholds (configurable)
        self.high_growth_threshold = Decimal('0.7')
        self.high_dependency_threshold = Decimal('0.7')
        self.high_risk_threshold = Decimal('0.6')
        self.strong_methodology_threshold = Decimal('0.7')
        
        self.logger.info("✅ [RECOMMENDATION-ENGINE] BusinessRecommendationEngine initialized (SRP-compliant)")
    
    async def generate_recommendations(
        self,
        business_analysis: BusinessTypeAnalysis,
        methodology_weights: Any,
        market_context: Optional[Dict[str, Any]] = None,
        owner_dependency: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Generate comprehensive business recommendations.
        
        SRP: Only generates recommendations, doesn't implement or analyze.
        
        NOTE: When ENABLE_AI_RECOMMENDATIONS is False, this method returns
        an empty list to prevent generic advice from appearing in reports.
        
        Args:
            business_analysis: Business type analysis results
            methodology_weights: Methodology selection weights
            market_context: Market context data (optional)
            owner_dependency: Owner dependency analysis (optional)
            
        Returns:
            List of recommendation strings (empty if AI recommendations disabled)
        """
        # =================================================================
        # QUALITY ASSURANCE: Check feature flag before generating
        # =================================================================
        if not ENABLE_AI_RECOMMENDATIONS:
            self.logger.info(
                "⚠️ [RECOMMENDATION-ENGINE] AI recommendations DISABLED for quality assurance",
                extra={
                    'feature_flag': 'ENABLE_AI_RECOMMENDATIONS',
                    'status': 'disabled',
                    'reason': 'Prevents generic advice that could be incorrect',
                    'academic_compliance': 'USPAP Standard 9, IVS 105',
                }
            )
            return []
        
        self.logger.info(
            f"🔍 [RECOMMENDATION-ENGINE] Generating recommendations",
            extra={
                'business_type': business_analysis.business_type,
                'recommended_methodology': business_analysis.recommended_methodology
            }
        )
        
        recommendations = []
        
        # Methodology recommendations
        recommendations.extend(
            self._generate_methodology_recommendations(
                business_analysis.recommended_methodology,
                methodology_weights
            )
        )
        
        # Risk recommendations
        recommendations.extend(
            self._generate_risk_recommendations(business_analysis)
        )
        
        # Growth recommendations
        recommendations.extend(
            self._generate_growth_recommendations(business_analysis)
        )
        
        # Owner dependency recommendations
        if owner_dependency:
            recommendations.extend(
                self._generate_owner_dependency_recommendations(owner_dependency)
            )
        
        # Market context recommendations
        if market_context:
            recommendations.extend(
                self._generate_market_recommendations(market_context)
            )
        
        self.logger.info(
            f"✅ [RECOMMENDATION-ENGINE] Generated {len(recommendations)} recommendations",
            extra={'count': len(recommendations)}
        )
        
        return recommendations
    
    def prioritize_actions(
        self,
        recommendations: List[Recommendation]
    ) -> List[Recommendation]:
        """
        Prioritize recommendations by impact and urgency.
        
        SRP: Only prioritizes, doesn't generate or implement.
        
        Args:
            recommendations: List of Recommendation objects
            
        Returns:
            Sorted list of recommendations (highest priority first)
        """
        self.logger.info(
            f"🔍 [RECOMMENDATION-ENGINE] Prioritizing {len(recommendations)} actions",
            extra={'count': len(recommendations)}
        )
        
        # Priority order mapping
        priority_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
        
        # Sort by priority, then by impact
        impact_order = {'High': 0, 'Medium': 1, 'Low': 2}
        
        sorted_recommendations = sorted(
            recommendations,
            key=lambda r: (
                priority_order.get(r.priority, 999),
                impact_order.get(r.impact, 999)
            )
        )
        
        self.logger.info(
            f"✅ [RECOMMENDATION-ENGINE] Actions prioritized",
            extra={'top_priority': sorted_recommendations[0].priority if sorted_recommendations else None}
        )
        
        return sorted_recommendations
    
    def identify_growth_opportunities(
        self,
        business_analysis: BusinessTypeAnalysis,
        market_context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Identify growth opportunities for the business.
        
        SRP: Only identifies opportunities, doesn't implement or analyze.
        
        NOTE: When ENABLE_AI_RECOMMENDATIONS is False, this method returns
        an empty list to prevent generic advice from appearing in reports.
        
        Args:
            business_analysis: Business type analysis
            market_context: Market context data (optional)
            
        Returns:
            List of growth opportunity descriptions (empty if disabled)
        """
        # =================================================================
        # QUALITY ASSURANCE: Check feature flag before generating
        # =================================================================
        if not ENABLE_AI_RECOMMENDATIONS:
            self.logger.info(
                "⚠️ [RECOMMENDATION-ENGINE] Growth opportunities DISABLED for quality assurance",
                extra={
                    'feature_flag': 'ENABLE_AI_RECOMMENDATIONS',
                    'status': 'disabled',
                    'reason': 'Prevents generic advice that could be incorrect',
                }
            )
            return []
        
        self.logger.info(
            f"🔍 [RECOMMENDATION-ENGINE] Identifying growth opportunities",
            extra={'business_type': business_analysis.business_type}
        )
        
        opportunities = []
        
        # High growth potential
        if business_analysis.growth_potential > self.high_growth_threshold:
            opportunities.extend([
                "Significant growth potential identified - consider expansion strategies",
                "Market conditions favor aggressive growth investments",
                "Consider raising capital for accelerated growth"
            ])
        
        # Market expansion
        if market_context:
            expected_growth = to_decimal(market_context.get('expected_growth_rate', 0))
            if expected_growth > Decimal('0.15'):
                opportunities.append("Strong market growth expected - expand market share")
        
        # Technology opportunities
        if business_analysis.business_type in ['saas', 'software', 'b2b_saas']:
            opportunities.extend([
                "Explore international market expansion",
                "Consider strategic partnerships for distribution",
                "Invest in product development for market leadership"
            ])
        
        # Service business opportunities
        elif business_analysis.business_type in ['consulting', 'legal', 'accounting']:
            opportunities.extend([
                "Productize services for scalability",
                "Build recurring revenue streams",
                "Develop team to reduce owner dependency"
            ])
        
        self.logger.info(
            f"✅ [RECOMMENDATION-ENGINE] Identified {len(opportunities)} opportunities",
            extra={'count': len(opportunities)}
        )
        
        return opportunities
    
    def _generate_methodology_recommendations(
        self,
        recommended_methodology: str,
        methodology_weights: Any
    ) -> List[str]:
        """Generate methodology-specific recommendations"""
        
        recommendations = []
        
        dcf_weight = methodology_weights.dcf_weight
        multiples_weight = methodology_weights.multiples_weight
        
        if recommended_methodology == 'DCF':
            if dcf_weight > self.strong_methodology_threshold:
                recommendations.append(
                    "Strong recommendation for DCF methodology based on financial characteristics"
                )
            else:
                recommendations.append(
                    "DCF methodology preferred, but consider Multiples validation"
                )
        
        elif recommended_methodology == 'Multiples':
            if multiples_weight > self.strong_methodology_threshold:
                recommendations.append(
                    "Strong recommendation for Multiples methodology based on market data"
                )
            else:
                recommendations.append(
                    "Multiples methodology preferred, but consider DCF validation"
                )
        
        else:  # Hybrid
            recommendations.append(
                "Consider using both methodologies for comprehensive valuation"
            )
            recommendations.append(
                "Weight final valuation based on methodology strengths"
            )
        
        return recommendations
    
    def _generate_risk_recommendations(
        self,
        business_analysis: BusinessTypeAnalysis
    ) -> List[str]:
        """Generate risk-related recommendations"""
        
        recommendations = []
        
        # Check risk assessment
        overall_risk = business_analysis.risk_assessment.get("overall_risk", "Medium")
        
        if overall_risk == "High":
            recommendations.extend([
                "Consider additional risk factors and sensitivity analysis",
                "Implement comprehensive risk mitigation strategies",
                "Conduct detailed due diligence before finalizing valuation"
            ])
        
        elif overall_risk == "Medium":
            recommendations.append(
                "Monitor key risk factors during valuation process"
            )
        
        # Market data quality
        if business_analysis.market_data_quality < Decimal('0.5'):
            recommendations.append(
                "Limited market data available - use conservative assumptions"
            )
        
        return recommendations
    
    def _generate_growth_recommendations(
        self,
        business_analysis: BusinessTypeAnalysis
    ) -> List[str]:
        """Generate growth-related recommendations"""
        
        recommendations = []
        
        if business_analysis.growth_potential > self.high_growth_threshold:
            recommendations.extend([
                "High growth potential - consider forward-looking metrics",
                "Focus on sustainable growth strategies",
                "Validate growth assumptions with market data"
            ])
        
        elif business_analysis.growth_potential < Decimal('0.3'):
            recommendations.append(
                "Limited growth potential - focus on stability and profitability"
            )
        
        return recommendations
    
    def _generate_owner_dependency_recommendations(
        self,
        owner_dependency: Dict[str, Any]
    ) -> List[str]:
        """Generate owner dependency recommendations"""
        
        recommendations = []
        
        dependency_score = to_decimal(owner_dependency.get('dependency_score', 0.5))
        
        if dependency_score > self.high_dependency_threshold:
            recommendations.extend([
                "High owner dependency - consider succession planning in valuation",
                "Develop transition plan to reduce business risk",
                "Document critical processes and knowledge"
            ])
        
        elif dependency_score > Decimal('0.4'):
            recommendations.append(
                "Moderate owner dependency - strengthen management team"
            )
        
        return recommendations
    
    def _generate_market_recommendations(
        self,
        market_context: Dict[str, Any]
    ) -> List[str]:
        """Generate market context recommendations"""
        
        recommendations = []
        
        # Market growth
        expected_growth = to_decimal(market_context.get('expected_growth_rate', 0))
        if expected_growth > Decimal('0.15'):
            recommendations.append(
                "Strong market growth - position for market expansion"
            )
        elif expected_growth < Decimal('0.05'):
            recommendations.append(
                "Slow market growth - focus on market share and efficiency"
            )
        
        # Market sentiment
        sentiment = market_context.get('market_sentiment', 'Neutral')
        if sentiment == 'Negative':
            recommendations.append(
                "Negative market sentiment - use conservative valuation assumptions"
            )
        elif sentiment == 'Positive':
            recommendations.append(
                "Positive market sentiment - favorable for growth investments"
            )
        
        return recommendations
    
    def create_detailed_recommendation(
        self,
        category: str,
        title: str,
        description: str,
        priority: str = 'Medium',
        impact: str = 'Medium',
        effort: str = 'Medium'
    ) -> Recommendation:
        """
        Create a detailed recommendation object.
        
        SRP: Only creates recommendation, doesn't analyze or implement.
        
        Args:
            category: Recommendation category (e.g., 'Growth', 'Risk', 'Operations')
            title: Short title
            description: Detailed description
            priority: Priority level (Critical/High/Medium/Low)
            impact: Expected impact (High/Medium/Low)
            effort: Required effort (High/Medium/Low)
            
        Returns:
            Recommendation object
        """
        return Recommendation(
            category=category,
            priority=priority,
            title=title,
            description=description,
            impact=impact,
            effort=effort
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.
        
        Returns:
            Dict containing:
            - service_name: Name of this service
            - responsibility: Single responsibility description
            - thresholds: Configuration thresholds
            - status: Operational status
        """
        return {
            'service_name': 'BusinessRecommendationEngine',
            'responsibility': 'Business recommendations generation',
            'thresholds': {
                'high_growth': float(self.high_growth_threshold),
                'high_dependency': float(self.high_dependency_threshold),
                'high_risk': float(self.high_risk_threshold),
                'strong_methodology': float(self.strong_methodology_threshold)
            },
            'status': 'operational',
            'srp_compliant': True
        }
