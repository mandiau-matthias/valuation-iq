"""
Methodology Selector Service

BANK-GRADE SRP-COMPLIANT: Valuation methodology selection ONLY

WHAT: Selects optimal valuation methodology based on business characteristics
WHY: Single responsibility - methodology decision logic
HOW: Analyzes business characteristics, market data, and historical patterns

VALUATION METHODOLOGIES SUPPORTED:
1. DCF (Discounted Cash Flow) - Best for stable, predictable businesses
2. Market Multiples (EV/EBITDA, EV/Revenue) - Best for mid-market with comparables
3. SDE (Seller's Discretionary Earnings) - Best for owner-operated small businesses
4. Asset-Based - Best for asset-heavy or distressed businesses
5. Entry Cost - Provides ceiling/floor for acquisitions

METHODOLOGY SELECTION MATRIX:
| Revenue       | EBITDA  | Assets | Owner-Op | Primary Method | Secondary     |
|---------------|---------|--------|----------|----------------|---------------|
| < EUR 500K    | Any     | Low    | Yes      | SDE            | Asset-Based   |
| 500K-2M       | Positive| Low    | Yes      | SDE            | Multiples     |
| 500K-2M       | Negative| High   | Any      | Asset-Based    | Entry Cost    |
| 2M-10M        | Positive| Low    | Any      | Multiples      | DCF           |
| 2M-10M        | Positive| High   | Any      | Multiples      | Asset-Based   |
| > 10M         | Positive| Any    | No       | DCF            | Multiples     |
| Any           | Negative| High   | Any      | Asset-Based    | Liquidation   |

ACADEMIC SOURCES:
- Trugman (2017): "Understanding Business Valuation" - SDE methodology
- Hitchner (2017): "Financial Valuation" - Asset-based approach
- Pratt & Niculita (2008): "Valuing a Business" - Methodology selection
- Damodaran (2012): "Investment Valuation" - DCF and comparables

EXTRACTED FROM: BusinessTypeIntelligenceService (780 lines)
COMPLIANCE: Bank-Grade Excellence Framework - SRP Phase 1
"""

from typing import Dict, Any, Optional, List
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from ..analysis.intelligence_processor import IntelligenceProcessor
from ..analysis.intelligence_types import MethodologyWeights

logger = get_logger(__name__)


class ValuationMethodology(str, Enum):
    """Available valuation methodologies."""
    DCF = "dcf"
    MULTIPLES = "multiples"
    SDE = "sde"
    ASSET_BASED = "asset_based"
    ENTRY_COST = "entry_cost"
    HYBRID = "hybrid"


@dataclass
class MethodologyRecommendation:
    """Complete methodology recommendation with weights and reasoning."""
    primary_method: ValuationMethodology
    secondary_method: Optional[ValuationMethodology]
    
    # Weights (should sum to 1.0)
    dcf_weight: Decimal = Decimal("0.0")
    multiples_weight: Decimal = Decimal("0.0")
    sde_weight: Decimal = Decimal("0.0")
    asset_based_weight: Decimal = Decimal("0.0")
    entry_cost_weight: Decimal = Decimal("0.0")
    
    # Suitability scores (0-1)
    dcf_suitability: Decimal = Decimal("0.0")
    multiples_suitability: Decimal = Decimal("0.0")
    sde_suitability: Decimal = Decimal("0.0")
    asset_based_suitability: Decimal = Decimal("0.0")
    entry_cost_suitability: Decimal = Decimal("0.0")
    
    confidence: Decimal = Decimal("0.5")
    reasoning: str = ""
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_method": self.primary_method.value,
            "secondary_method": self.secondary_method.value if self.secondary_method else None,
            "weights": {
                "dcf": from_decimal(self.dcf_weight),
                "multiples": from_decimal(self.multiples_weight),
                "sde": from_decimal(self.sde_weight),
                "asset_based": from_decimal(self.asset_based_weight),
                "entry_cost": from_decimal(self.entry_cost_weight),
            },
            "suitability_scores": {
                "dcf": from_decimal(self.dcf_suitability),
                "multiples": from_decimal(self.multiples_suitability),
                "sde": from_decimal(self.sde_suitability),
                "asset_based": from_decimal(self.asset_based_suitability),
                "entry_cost": from_decimal(self.entry_cost_suitability),
            },
            "confidence": from_decimal(self.confidence),
            "reasoning": self.reasoning,
            "warnings": self.warnings,
        }


class MethodologySelector:
    """
    BANK-GRADE SRP-COMPLIANT: Valuation methodology selection.
    
    SINGLE RESPONSIBILITY: Select optimal valuation methodology ONLY.
    
    This service focuses solely on determining which valuation methodology
    (DCF, Multiples, or Hybrid) is most appropriate based on business
    characteristics, market data, and historical patterns.
    
    Design Pattern: Strategy Pattern
    - Different methodologies are different strategies
    - Selection logic separated from methodology implementation
    - Enables independent testing and optimization
    
    Responsibilities:
    - DCF suitability assessment
    - Multiples suitability assessment
    - Methodology recommendation
    - Confidence scoring
    """
    
    def __init__(self):
        """
        Initialize methodology selector.
        
        SRP: Focused on methodology selection only
        """
        self.intelligence_processor = IntelligenceProcessor()
        self.logger = logger
        
        # Methodology thresholds (configurable)
        self.dcf_threshold = Decimal('0.6')
        self.multiples_threshold = Decimal('0.6')
        self.high_confidence_threshold = Decimal('0.7')
        
        self.logger.info("✅ [METHODOLOGY-SELECTOR] MethodologySelector initialized (SRP-compliant)")
    
    async def select_methodology(
        self,
        business_analysis: Dict[str, Any],
        market_adjustments: Optional[Dict[str, Any]] = None,
        owner_adjustments: Optional[Dict[str, Any]] = None,
        historical_analysis: Optional[Any] = None
    ) -> MethodologyWeights:
        """
        Select optimal valuation methodology.
        
        SRP: Only selects methodology, doesn't perform valuation or analysis.
        
        Args:
            business_analysis: Business characteristics and adjustments
            market_adjustments: Market context adjustments (optional)
            owner_adjustments: Owner dependency adjustments (optional)
            historical_analysis: Historical data analysis (optional)
            
        Returns:
            MethodologyWeights containing:
            - dcf_weight: DCF methodology weight (0-1)
            - multiples_weight: Multiples methodology weight (0-1)
            - confidence_score: Confidence in recommendation (0-1)
            - reasoning: Explanation for selection
        """
        self.logger.info(
            "🔍 [METHODOLOGY-SELECTOR] Selecting methodology",
            extra={
                'business_type': business_analysis.get('config', {}).get('business_type', 'unknown'),
                'has_market_data': market_adjustments is not None,
                'has_owner_data': owner_adjustments is not None
            }
        )
        
        # Calculate methodology weights
        methodology_weights = self.intelligence_processor.calculate_methodology_weights(
            business_analysis.get("adjustments", {}),
            market_adjustments,
            owner_adjustments,
            historical_analysis
        )
        
        self.logger.info(
            f"✅ [METHODOLOGY-SELECTOR] Methodology selected",
            extra={
                'dcf_weight': float(methodology_weights.dcf_weight),
                'multiples_weight': float(methodology_weights.multiples_weight),
                'confidence': float(methodology_weights.confidence_score)
            }
        )
        
        return methodology_weights
    
    def calculate_dcf_suitability(
        self,
        business_characteristics: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate DCF methodology suitability score.
        
        SRP: Only calculates DCF suitability, doesn't make final decision.
        
        DCF is more suitable when:
        - Predictable cash flows
        - Stable revenue growth
        - Low owner dependency
        - Mature business stage
        
        Args:
            business_characteristics: Business characteristics including
                revenue_level, growth_stage, complexity, etc.
            
        Returns:
            DCF suitability score (0-1)
        """
        self.logger.info(
            "🔍 [METHODOLOGY-SELECTOR] Calculating DCF suitability",
            extra={'characteristics': business_characteristics}
        )
        
        score = Decimal('0.5')  # Base score
        
        # Revenue stability favors DCF
        revenue_level = business_characteristics.get('revenue_level', 'Medium')
        if revenue_level == 'High':
            score += Decimal('0.2')
        elif revenue_level == 'Medium':
            score += Decimal('0.1')
        
        # Mature businesses favor DCF
        growth_stage = business_characteristics.get('growth_stage', 'Growth')
        if growth_stage == 'Mature':
            score += Decimal('0.15')
        elif growth_stage == 'Growth':
            score += Decimal('0.05')
        
        # Higher complexity favors DCF
        complexity = business_characteristics.get('complexity', 'Medium')
        if complexity == 'High':
            score += Decimal('0.1')
        elif complexity == 'Medium':
            score += Decimal('0.05')
        
        # Cap at 1.0
        score = min(score, Decimal('1.0'))
        
        self.logger.info(
            f"✅ [METHODOLOGY-SELECTOR] DCF suitability: {float(score):.2f}",
            extra={'score': float(score)}
        )
        
        return score
    
    def calculate_multiples_suitability(
        self,
        business_characteristics: Dict[str, Any],
        market_data_quality: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate Multiples methodology suitability score.
        
        SRP: Only calculates Multiples suitability, doesn't make final decision.
        
        Multiples is more suitable when:
        - Good comparable companies available
        - High market data quality
        - Standard business type
        - Lower complexity
        
        Args:
            business_characteristics: Business characteristics
            market_data_quality: Quality of market data (0-1)
            
        Returns:
            Multiples suitability score (0-1)
        """
        self.logger.info(
            "🔍 [METHODOLOGY-SELECTOR] Calculating Multiples suitability",
            extra={
                'characteristics': business_characteristics,
                'market_quality': float(market_data_quality) if market_data_quality else None
            }
        )
        
        score = Decimal('0.5')  # Base score
        
        # Market data quality is critical for multiples
        if market_data_quality:
            if market_data_quality > Decimal('0.8'):
                score += Decimal('0.25')
            elif market_data_quality > Decimal('0.6'):
                score += Decimal('0.15')
            elif market_data_quality > Decimal('0.4'):
                score += Decimal('0.05')
        
        # Lower complexity favors multiples (easier to find comparables)
        complexity = business_characteristics.get('complexity', 'Medium')
        if complexity == 'Low':
            score += Decimal('0.15')
        elif complexity == 'Medium':
            score += Decimal('0.05')
        
        # Growth stage impact
        growth_stage = business_characteristics.get('growth_stage', 'Growth')
        if growth_stage in ['Growth', 'Startup']:
            score += Decimal('0.1')  # Easier to find comparables
        
        # Cap at 1.0
        score = min(score, Decimal('1.0'))
        
        self.logger.info(
            f"✅ [METHODOLOGY-SELECTOR] Multiples suitability: {float(score):.2f}",
            extra={'score': float(score)}
        )
        
        return score
    
    def determine_confidence(
        self,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        data_quality: Optional[Decimal] = None
    ) -> Decimal:
        """
        Determine confidence in methodology recommendation.
        
        SRP: Only calculates confidence, doesn't make decisions.
        
        High confidence when:
        - Clear winner (large weight difference)
        - High data quality
        - Both weights are reasonable
        
        Args:
            dcf_weight: DCF methodology weight
            multiples_weight: Multiples methodology weight
            data_quality: Overall data quality (0-1)
            
        Returns:
            Confidence score (0-1)
        """
        self.logger.info(
            "🔍 [METHODOLOGY-SELECTOR] Determining confidence",
            extra={
                'dcf_weight': float(dcf_weight),
                'multiples_weight': float(multiples_weight)
            }
        )
        
        # Base confidence from weight difference
        weight_diff = abs(dcf_weight - multiples_weight)
        
        if weight_diff > Decimal('0.4'):
            base_confidence = Decimal('0.9')
        elif weight_diff > Decimal('0.2'):
            base_confidence = Decimal('0.7')
        else:
            base_confidence = Decimal('0.5')
        
        # Adjust for data quality
        if data_quality:
            confidence = base_confidence * (Decimal('0.7') + (data_quality * Decimal('0.3')))
        else:
            confidence = base_confidence * Decimal('0.8')  # Slight penalty for no data quality info
        
        # Cap at 1.0
        confidence = min(confidence, Decimal('1.0'))
        
        self.logger.info(
            f"✅ [METHODOLOGY-SELECTOR] Confidence determined: {float(confidence):.2f}",
            extra={'confidence': float(confidence)}
        )
        
        return confidence
    
    def get_methodology_recommendation(
        self,
        dcf_weight: Decimal,
        multiples_weight: Decimal
    ) -> str:
        """
        Get methodology recommendation text.
        
        SRP: Only formats recommendation, doesn't make decision.
        
        Args:
            dcf_weight: DCF methodology weight
            multiples_weight: Multiples methodology weight
            
        Returns:
            Recommendation string ('DCF', 'Multiples', or 'Hybrid')
        """
        if dcf_weight > self.dcf_threshold and dcf_weight > multiples_weight:
            return 'DCF'
        elif multiples_weight > self.multiples_threshold and multiples_weight > dcf_weight:
            return 'Multiples'
        else:
            return 'Hybrid'
    
    # =========================================================================
    # ENHANCED METHODOLOGY SELECTION (SDE, Asset-Based, Entry Cost)
    # =========================================================================
    
    def calculate_sde_suitability(
        self,
        business_characteristics: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate SDE methodology suitability score.
        
        SDE (Seller's Discretionary Earnings) is most suitable when:
        - Owner-operated business (1-3 owners actively involved)
        - Revenue under EUR 2M (ideal under EUR 500K)
        - Service business with low assets
        - Sole proprietorship or small partnership
        
        Academic Source: Trugman (2017, p. 287)
        
        Args:
            business_characteristics: Business characteristics including
                revenue, owner_operated, asset_intensity, etc.
            
        Returns:
            SDE suitability score (0-1)
        """
        self.logger.info(
            "🔍 [METHODOLOGY-SELECTOR] Calculating SDE suitability",
            extra={'characteristics': business_characteristics}
        )
        
        score = Decimal('0.0')  # Start at 0, add based on criteria
        
        # Revenue level is critical for SDE
        revenue = to_decimal(business_characteristics.get('revenue', 0))
        if revenue < Decimal('500000'):
            score += Decimal('0.40')  # Strong preference for micro businesses
        elif revenue < Decimal('2000000'):
            score += Decimal('0.25')  # Moderate preference for small businesses
        elif revenue < Decimal('5000000'):
            score += Decimal('0.10')  # Some applicability for lower mid-market
        else:
            score += Decimal('0.0')   # Not suitable for larger businesses
        
        # Owner-operated is key for SDE
        is_owner_operated = business_characteristics.get('is_owner_operated', True)
        owner_count = business_characteristics.get('owner_count', 1)
        if is_owner_operated and owner_count <= 2:
            score += Decimal('0.30')  # Strong SDE signal
        elif is_owner_operated:
            score += Decimal('0.15')
        
        # Low asset intensity favors SDE
        asset_intensity = business_characteristics.get('asset_intensity', 'low')
        if asset_intensity == 'low':
            score += Decimal('0.15')
        elif asset_intensity == 'medium':
            score += Decimal('0.05')
        
        # Service businesses are ideal for SDE
        business_type = business_characteristics.get('business_type', '').lower()
        if any(t in business_type for t in ['service', 'consulting', 'professional']):
            score += Decimal('0.15')
        elif any(t in business_type for t in ['retail', 'restaurant', 'trade']):
            score += Decimal('0.10')
        
        # Cap at 1.0
        score = min(score, Decimal('1.0'))
        
        self.logger.info(
            f"✅ [METHODOLOGY-SELECTOR] SDE suitability: {float(score):.2f}",
            extra={'score': float(score)}
        )
        
        return score
    
    def calculate_asset_based_suitability(
        self,
        business_characteristics: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate Asset-Based methodology suitability score.
        
        Asset-based valuation is most suitable when:
        - High asset intensity (manufacturing, construction, real estate)
        - Negative or low EBITDA (going concern doubt)
        - Holding companies
        - Distressed businesses or liquidation scenarios
        
        Academic Source: Hitchner (2017, Ch. 8), Pratt & Niculita (2008)
        
        Args:
            business_characteristics: Business characteristics including
                total_assets, ebitda, asset_intensity, etc.
            
        Returns:
            Asset-based suitability score (0-1)
        """
        self.logger.info(
            "🔍 [METHODOLOGY-SELECTOR] Calculating Asset-Based suitability",
            extra={'characteristics': business_characteristics}
        )
        
        score = Decimal('0.0')
        
        # Negative EBITDA strongly favors asset-based
        ebitda = to_decimal(business_characteristics.get('ebitda', 0))
        if ebitda <= Decimal('0'):
            score += Decimal('0.40')  # Strong signal for asset-based
        elif ebitda < to_decimal(business_characteristics.get('revenue', 1)) * Decimal('0.05'):
            score += Decimal('0.20')  # Low profitability
        
        # High asset intensity
        asset_intensity = business_characteristics.get('asset_intensity', 'low')
        if asset_intensity == 'high':
            score += Decimal('0.30')
        elif asset_intensity == 'medium':
            score += Decimal('0.15')
        
        # Asset-heavy industries
        business_type = business_characteristics.get('business_type', '').lower()
        if any(t in business_type for t in ['manufacturing', 'construction', 'real estate', 'logistics']):
            score += Decimal('0.20')
        elif any(t in business_type for t in ['retail', 'distribution']):
            score += Decimal('0.10')
        
        # Assets relative to revenue (high = asset-based more appropriate)
        total_assets = to_decimal(business_characteristics.get('total_assets', 0))
        revenue = to_decimal(business_characteristics.get('revenue', 1))
        if revenue > 0:
            asset_to_revenue = total_assets / revenue
            if asset_to_revenue > Decimal('1.5'):
                score += Decimal('0.10')  # Asset-heavy
        
        # Cap at 1.0
        score = min(score, Decimal('1.0'))
        
        self.logger.info(
            f"✅ [METHODOLOGY-SELECTOR] Asset-Based suitability: {float(score):.2f}",
            extra={'score': float(score)}
        )
        
        return score
    
    def calculate_entry_cost_suitability(
        self,
        business_characteristics: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate Entry Cost methodology suitability score.
        
        Entry cost provides a ceiling/floor for acquisitions:
        - Useful as sanity check for any acquisition
        - Primary method when barriers to entry are low
        - Important for new/young businesses
        - Validates income approach values
        
        Academic Source: Porter (1980), Damodaran (2012)
        
        Args:
            business_characteristics: Business characteristics
            
        Returns:
            Entry cost suitability score (0-1)
        """
        self.logger.info(
            "🔍 [METHODOLOGY-SELECTOR] Calculating Entry Cost suitability",
            extra={'characteristics': business_characteristics}
        )
        
        score = Decimal('0.3')  # Base score - always useful as secondary
        
        # Young businesses favor entry cost
        business_age = business_characteristics.get('business_age_years', 10)
        if business_age < 3:
            score += Decimal('0.30')  # Young business
        elif business_age < 5:
            score += Decimal('0.15')
        
        # Low barriers to entry favor entry cost as primary
        barriers_to_entry = business_characteristics.get('barriers_to_entry', 'medium')
        if barriers_to_entry == 'low':
            score += Decimal('0.20')
        elif barriers_to_entry == 'medium':
            score += Decimal('0.10')
        
        # Highly competitive markets
        market_competition = business_characteristics.get('market_competition', 'medium')
        if market_competition == 'high':
            score += Decimal('0.10')
        
        # Cap at 1.0
        score = min(score, Decimal('1.0'))
        
        self.logger.info(
            f"✅ [METHODOLOGY-SELECTOR] Entry Cost suitability: {float(score):.2f}",
            extra={'score': float(score)}
        )
        
        return score
    
    def select_comprehensive_methodology(
        self,
        business_characteristics: Dict[str, Any],
        market_data_quality: Optional[Decimal] = None,
    ) -> MethodologyRecommendation:
        """
        Select optimal valuation methodology from all available methods.
        
        This enhanced method considers ALL valuation approaches:
        - DCF (for stable, predictable businesses)
        - Multiples (for mid-market with comparables)
        - SDE (for owner-operated small businesses)
        - Asset-Based (for asset-heavy or distressed)
        - Entry Cost (as ceiling/sanity check)
        
        Args:
            business_characteristics: Complete business profile
            market_data_quality: Quality of market data (0-1)
            
        Returns:
            MethodologyRecommendation with primary, secondary, and weights
        """
        self.logger.info(
            "🔍 [METHODOLOGY-SELECTOR] Selecting comprehensive methodology",
            extra={'characteristics': business_characteristics}
        )
        
        warnings = []
        
        # Calculate all suitability scores
        dcf_suit = self.calculate_dcf_suitability(business_characteristics)
        mult_suit = self.calculate_multiples_suitability(business_characteristics, market_data_quality)
        sde_suit = self.calculate_sde_suitability(business_characteristics)
        asset_suit = self.calculate_asset_based_suitability(business_characteristics)
        entry_suit = self.calculate_entry_cost_suitability(business_characteristics)
        
        # Find primary and secondary methods
        scores = [
            (ValuationMethodology.DCF, dcf_suit),
            (ValuationMethodology.MULTIPLES, mult_suit),
            (ValuationMethodology.SDE, sde_suit),
            (ValuationMethodology.ASSET_BASED, asset_suit),
            (ValuationMethodology.ENTRY_COST, entry_suit),
        ]
        
        # Sort by suitability descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        primary = scores[0][0]
        secondary = scores[1][0] if scores[1][1] > Decimal('0.3') else None
        
        # Calculate weights based on suitability
        total_suit = sum(s[1] for s in scores)
        if total_suit > Decimal('0'):
            dcf_weight = dcf_suit / total_suit
            mult_weight = mult_suit / total_suit
            sde_weight = sde_suit / total_suit
            asset_weight = asset_suit / total_suit
            entry_weight = entry_suit / total_suit
        else:
            # Default to equal weights
            dcf_weight = mult_weight = sde_weight = asset_weight = entry_weight = Decimal('0.2')
        
        # Generate reasoning
        reasoning_parts = []
        revenue = to_decimal(business_characteristics.get('revenue', 0))
        
        if primary == ValuationMethodology.SDE:
            reasoning_parts.append(
                f"SDE is recommended as primary method for this owner-operated business "
                f"with €{from_decimal(revenue):,.0f} revenue."
            )
        elif primary == ValuationMethodology.ASSET_BASED:
            reasoning_parts.append(
                "Asset-Based valuation is recommended due to high asset intensity "
                "and/or low profitability."
            )
        elif primary == ValuationMethodology.MULTIPLES:
            reasoning_parts.append(
                "Market Multiples approach is recommended based on revenue size "
                "and availability of comparable transactions."
            )
        elif primary == ValuationMethodology.DCF:
            reasoning_parts.append(
                "DCF is recommended for this mature business with predictable cash flows."
            )
        
        if secondary:
            reasoning_parts.append(f"{secondary.value.upper()} is recommended as secondary method.")
        
        # Add warnings
        ebitda = to_decimal(business_characteristics.get('ebitda', 0))
        if ebitda <= Decimal('0'):
            warnings.append("Negative EBITDA detected - income approaches may be unreliable")
        if revenue < Decimal('500000') and primary in [ValuationMethodology.DCF, ValuationMethodology.MULTIPLES]:
            warnings.append("Revenue under €500K - consider SDE as alternative methodology")
        
        # Calculate confidence
        confidence = self.determine_confidence(
            scores[0][1],  # Primary suitability
            scores[1][1],  # Secondary suitability
            market_data_quality
        )
        
        recommendation = MethodologyRecommendation(
            primary_method=primary,
            secondary_method=secondary,
            dcf_weight=dcf_weight,
            multiples_weight=mult_weight,
            sde_weight=sde_weight,
            asset_based_weight=asset_weight,
            entry_cost_weight=entry_weight,
            dcf_suitability=dcf_suit,
            multiples_suitability=mult_suit,
            sde_suitability=sde_suit,
            asset_based_suitability=asset_suit,
            entry_cost_suitability=entry_suit,
            confidence=confidence,
            reasoning=" ".join(reasoning_parts),
            warnings=warnings,
        )
        
        self.logger.info(
            f"✅ [METHODOLOGY-SELECTOR] Comprehensive methodology selected",
            extra={
                'primary': primary.value,
                'secondary': secondary.value if secondary else None,
                'confidence': float(confidence),
            }
        )
        
        return recommendation
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.
        
        Returns:
            Dict containing:
            - service_name: Name of this service
            - responsibility: Single responsibility description
            - thresholds: Configuration thresholds
            - supported_methodologies: List of available methodologies
            - status: Operational status
        """
        return {
            'service_name': 'MethodologySelector',
            'responsibility': 'Valuation methodology selection (enhanced with SDE/Asset-Based)',
            'thresholds': {
                'dcf_threshold': float(self.dcf_threshold),
                'multiples_threshold': float(self.multiples_threshold),
                'high_confidence_threshold': float(self.high_confidence_threshold)
            },
            'supported_methodologies': [m.value for m in ValuationMethodology],
            'methodology_matrix': {
                'micro_business_owner_operated': 'SDE primary, Asset-Based secondary',
                'small_business_profitable': 'SDE or Multiples, based on comparables',
                'small_business_distressed': 'Asset-Based primary, Entry Cost secondary',
                'mid_market_profitable': 'Multiples primary, DCF secondary',
                'mid_market_asset_heavy': 'Multiples primary, Asset-Based secondary',
                'large_business': 'DCF primary, Multiples secondary',
            },
            'academic_sources': [
                'Trugman (2017): SDE methodology',
                'Hitchner (2017): Asset-based approach',
                'Pratt & Niculita (2008): Methodology selection',
                'Damodaran (2012): DCF and comparables',
            ],
            'status': 'operational',
            'srp_compliant': True
        }
