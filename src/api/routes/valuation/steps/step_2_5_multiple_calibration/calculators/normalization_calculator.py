"""
EBITDA Normalization Calculator

Calculates normalized EBITDA by applying adjustments for:
1. Owner compensation
2. One-time expenses (estimated from margin volatility)
3. Personal expenses (when data available)

Academic Source: Trugman (2017, p. 287), Pratt & Niculita (2008), Hitchner (2017)
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.domain.report_integrity import build_owner_compensation_estimated_warning
from src.utils.decimal_helpers import to_decimal, from_decimal, bank_round
from src.utils.fiscal_year import get_current_filing_year
from src.utils.logging import get_logger

from ..analyzers.margin_volatility_analyzer import MarginVolatilityAnalyzer
from ..modules.owner_compensation_adjuster import OwnerCompensationAdjuster

logger = get_logger(__name__)


class NormalizationCalculator:
    """
    Multiple Calibration Calculator (formerly EBITDA normalization).
    
    MULTIPLE-FIRST METHODOLOGY:
    Analyzes quality factors (margin volatility, owner compensation) and calculates
    adjustment to the MULTIPLE, not the EBITDA metric.
    
    This prevents double-counting where both EBITDA is increased AND multiple is decreased.
    Big 4 standard: All adjustments applied to the multiple.
    """
    
    def __init__(self) -> None:
        """Initialize calculator with sub-modules."""
        self.owner_comp_adjuster = OwnerCompensationAdjuster()
        self.margin_analyzer = MarginVolatilityAnalyzer()
    
    def calculate_quality_multiple_adjustment(
        self,
        reported_ebitda: Decimal,
        revenue: Decimal,
        historical_data: List[Any],
        base_multiple: Optional[Decimal] = None,
        owner_compensation: Optional[Decimal] = None,
        business_category: Optional[str] = None,
        location: str = "Belgium",
        business_type_id: Optional[str] = None,
        current_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calculate quality-based adjustment to base multiple (MULTIPLE-FIRST METHODOLOGY).
        
        Instead of normalizing EBITDA upward, we discount the multiple downward.
        This prevents double-counting when Steps 4-6 also discount the multiple.
        
        Quality Factors Analyzed:
        1. Margin Volatility → Lower multiple if volatile earnings
        2. Owner Compensation Risk → Lower multiple if above market
        3. Earnings Consistency → Lower multiple if inconsistent
        
        Args:
            reported_ebitda: Reported EBITDA from financial statements
            revenue: Current year revenue
            historical_data: Historical year data for margin analysis
            base_multiple: Base multiple from comparables (for reference)
            owner_compensation: Owner compensation (optional, will estimate if not provided)
            business_category: Business category for market rate lookup
            location: Geographic location
            business_type_id: Business type ID for context
            current_year: Explicit reporting year for metadata labeling
            
        Returns:
            Dictionary with quality_multiple_adjustment and analysis details
        """
        logger.debug(
            "🔍 Starting quality-based multiple calibration (MULTIPLE-FIRST)",
            extra={
                "reported_ebitda": from_decimal(reported_ebitda),
                "revenue": from_decimal(revenue),
                "historical_years": len(historical_data),
                "base_multiple": from_decimal(base_multiple) if base_multiple else None,
                "methodology": "Multiple-first approach (Big 4 standard)",
            }
        )
        
        quality_factors = []
        multiple_adjustment = Decimal("0")  # Negative = discount, Positive = premium
        
        # 1. Owner Compensation Risk Analysis
        owner_comp_adj, owner_comp_explanation, owner_comp_meta = \
            self.owner_comp_adjuster.calculate_adjustment(
                owner_compensation,
                revenue,
                business_category,
                location
            )
        
        # Convert owner comp excess to multiple discount
        # Logic: If owner taking €10K more than market rate, that's a quality issue
        # We discount the multiple slightly (not add to EBITDA)
        if abs(owner_comp_adj) > Decimal("1000"):  # Material threshold €1k
            # Rule: €10K excess = -0.05x discount on multiple
            owner_comp_multiple_impact = (owner_comp_adj / Decimal("10000")) * Decimal("-0.05")
            owner_comp_multiple_impact = max(owner_comp_multiple_impact, Decimal("-0.15"))  # Cap at -0.15x
            
            quality_factors.append({
                "category": "owner_compensation_risk",
                "name": "Owner Compensation Risk",
                "impact": from_decimal(owner_comp_multiple_impact),
                "description": f"Owner compensation {abs(from_decimal(owner_comp_adj)):,.0f}€ {'above' if owner_comp_adj > 0 else 'below'} market rate",
                "severity": owner_comp_meta.get("severity", "low"),
            })
            multiple_adjustment += owner_comp_multiple_impact
        
        # 2. Margin Volatility Analysis → Multiple Discount
        margin_analysis = self.margin_analyzer.analyze_margin_pattern(
            reported_ebitda,
            revenue,
            historical_data
        )
        
        volatility_level = margin_analysis.get("volatility_level", "LOW")
        
        # Convert volatility to multiple discount
        # Big 4 standard: Higher volatility = Lower quality = Lower multiple
        volatility_multiple_impact = Decimal("0")
        if volatility_level == "HIGH":
            volatility_multiple_impact = Decimal("-0.3")  # Severe quality concern
            severity = "high"
        elif volatility_level == "MEDIUM":
            volatility_multiple_impact = Decimal("-0.2")  # Moderate quality concern
            severity = "medium"
        elif volatility_level == "LOW":
            volatility_multiple_impact = Decimal("0")  # No discount for stable margins
            severity = "low"
        
        if volatility_multiple_impact != Decimal("0"):
            margin_stdev = margin_analysis.get("margin_stdev", 0)
            explanation = (
                f"{volatility_level} margin volatility detected (±{from_decimal(margin_stdev):.1f}pp). "
                f"Volatile earnings indicate lower quality of earnings. "
                f"Multiple discounted by {abs(from_decimal(volatility_multiple_impact))}x to reflect earnings risk."
            )
            
            quality_factors.append({
                "category": "margin_volatility",
                "name": "Margin Volatility Discount",
                "impact": from_decimal(volatility_multiple_impact),
                "description": explanation,
                "severity": severity,
            })
            multiple_adjustment += volatility_multiple_impact
        
        # Total multiple adjustment (negative = discount, positive = premium)
        # This will be applied to base multiple in Step 3
        quality_multiple_adjustment = multiple_adjustment
        
        # Calculate normalized EBITDA (for transparency/bridge, even if multiple-first)
        # Big 4 standard: Even if multiple-first, we still show the bridge
        ebitda_adjustments = []
        if abs(owner_comp_adj) > Decimal("1000"):
            ebitda_adjustments.append({
                "name": "Owner Compensation Adjustment",
                "amount": from_decimal(owner_comp_adj),
                "rationale": owner_comp_explanation
            })
        
        normalized_ebitda = reported_ebitda + owner_comp_adj
        
        # Determine confidence level
        confidence_score = self._calculate_quality_confidence(
            margin_analysis,
            len(quality_factors),
            owner_comp_meta.get("data_quality", "estimated")
        )
        
        # Calculate earnings quality score (0-100)
        earnings_quality_score = 100 - int(abs(from_decimal(quality_multiple_adjustment)) * 50)
        earnings_quality_score = max(0, min(100, earnings_quality_score))  # Clamp to 0-100
        
        result = {
            # MULTIPLE-FIRST: Output quality adjustment to multiple, NOT normalized EBITDA
            "quality_multiple_adjustment": from_decimal(quality_multiple_adjustment),

            # EBITDA BRIDGE: Added for report transparency (requested by SME persona)
            "reported_ebitda": from_decimal(reported_ebitda),
            "normalized_ebitda": from_decimal(normalized_ebitda),
            "ebitda_adjustments": ebitda_adjustments,

            # POST-DEAL LENS: surfaces actual + market-rate so the response
            # builder can compute the SDE-driven Post-Deal equity swap.
            # These are consumed by `builders/post_deal_swap.py` and emitted
            # on `ValuationResponse.owner_compensation_swap`. The amounts
            # are also retained inside `owner_compensation_metadata` so a
            # future report renderer can show the full swap waterfall.
            "owner_compensation_metadata": owner_comp_meta,
            
            # PHASE 3: Base multiple for waterfall tracking
            "base_multiple": from_decimal(base_multiple) if base_multiple else None,
            
            # Quality analysis details
            "quality_analysis": {
                "margin_volatility_level": volatility_level,
                "earnings_quality_score": earnings_quality_score,
                "factors_analyzed": [f["category"] for f in quality_factors],
                "num_quality_factors": len(quality_factors),
            },
            
            # Detailed quality factors
            "quality_factors": quality_factors,
            
            # Margin analysis (for reference/display)
            "margin_analysis": {
                "current_margin": from_decimal(margin_analysis["current_margin"]),
                "average_margin": from_decimal(margin_analysis["average_margin"]),
                "margin_stdev": from_decimal(margin_analysis["margin_stdev"]),
                "volatility_level": margin_analysis["volatility_level"],
                "quality_of_earnings_flag": margin_analysis["quality_of_earnings_flag"],
                "normalized_margin": from_decimal(margin_analysis["normalized_margin"]),
            },
            
            # ACADEMIC SOURCES: SME-specific research backing quality calibration
            "academic_sources": [
                {
                    "source_id": "trugman_2017",
                    "author": "Trugman, G.R.",
                    "year": 2017,
                    "title": "Understanding Business Valuation: A Practical Guide to Valuing Small to Medium-Sized Businesses",
                    "publisher": "AICPA",
                    "pages": "Chapter 8: Quality of Earnings Analysis",
                    "relevance": "AICPA standard for SME earnings quality assessment and multiple calibration"
                },
                {
                    "source_id": "hitchner_2017",
                    "author": "Hitchner, J.R.",
                    "year": 2017,
                    "title": "Financial Valuation: Applications and Models",
                    "publisher": "Wiley",
                    "pages": "Chapter 11: Adjustments to the Multiple",
                    "relevance": "Multiple-first methodology - adjusting multiples for company-specific risk factors"
                },
                {
                    "source_id": "pratt_niculita_2008",
                    "author": "Pratt, S.P. & Niculita, A.V.",
                    "year": 2008,
                    "title": "Valuing a Business: The Analysis and Appraisal of Closely Held Companies",
                    "publisher": "McGraw-Hill",
                    "pages": "Chapter 14: Normalization Adjustments",
                    "relevance": "Private company normalization methodology"
                }
            ],
            
            # Academic foundation for methodology
            "methodology_foundation": {
                "approach": "Multiple-First Quality Calibration",
                "principle": "All quality adjustments applied to valuation multiple, not EBITDA metric",
                "academic_basis": [
                    "Damodaran (2012): 'The multiple is the primary vehicle for risk adjustment in comparables analysis'",
                    "Hitchner (2017): 'Company-specific risk factors should adjust the multiple, creating a calibrated multiple'",
                    "Trugman (2017): 'Quality of earnings analysis informs multiple selection for SME valuations'"
                ]
            },
            
            # Metadata
            "confidence_score": confidence_score,
            "year": current_year or get_current_filing_year(),
            "rationale": self._build_quality_rationale(quality_factors, margin_analysis),
        }

        # Pass-8 integrity disclosure: when owner compensation was not
        # provided and the engine had to auto-estimate it, surface a
        # high-severity warning. For owner-led SMEs this is typically the
        # largest normalization item and an estimate is materially less
        # defensible than a real input.
        if owner_comp_meta.get("data_quality") == "estimated":
            integrity = build_owner_compensation_estimated_warning(
                estimated_compensation=float(owner_comp_meta.get("owner_compensation", 0) or 0),
                estimation_method="10% of revenue, min €50k, max €200k",
            )
            existing = result.get("data_quality_warnings")
            if isinstance(existing, list):
                existing.append(integrity)
            else:
                result["data_quality_warnings"] = [integrity]

        logger.debug(
            "✅ Quality-based multiple calibration complete (MULTIPLE-FIRST)",
            extra={
                "quality_multiple_adjustment": from_decimal(quality_multiple_adjustment),
                "num_quality_factors": len(quality_factors),
                "volatility_level": volatility_level,
                "earnings_quality_score": earnings_quality_score,
                "confidence": confidence_score,
                "methodology": "Multiple-first approach - no double-counting"
            }
        )
        
        return result
    
    def _calculate_quality_confidence(
        self,
        margin_analysis: Dict,
        num_quality_factors: int,
        data_quality: str
    ) -> str:
        """
        Calculate confidence in quality assessment.
        
        Factors:
        - Margin volatility
        - Number of quality factors detected
        - Data quality (provided vs estimated)
        """
        volatility_level = margin_analysis.get("volatility_level", "LOW")
        
        if data_quality == "provided" and volatility_level == "LOW":
            return "High"
        elif volatility_level == "HIGH" or num_quality_factors >= 2:
            return "Medium"
        else:
            return "Medium"
    
    def _build_quality_rationale(
        self,
        quality_factors: List[Dict],
        margin_analysis: Dict
    ) -> str:
        """Build human-readable rationale for quality-based multiple calibration."""
        if not quality_factors:
            return (
                "Quality analysis indicates stable earnings and normal operating conditions. "
                "No quality-based adjustment to the base multiple is required. "
                "The comparable company multiple can be applied without modification for quality factors."
            )
        
        rationale_parts = [
            "Quality-based multiple calibration (MULTIPLE-FIRST METHODOLOGY): "
            "Quality and risk factors are reflected through adjustments to the valuation multiple, "
            "not through EBITDA normalization. This prevents double-counting and aligns with Big 4 standards."
        ]
        
        for factor in quality_factors:
            impact_direction = "discount" if factor["impact"] < 0 else "premium"
            rationale_parts.append(
                f"\n• {factor['description']} → {abs(factor['impact']):.2f}x {impact_direction}"
            )
        
        if margin_analysis.get("quality_of_earnings_flag"):
            volatility = margin_analysis.get("margin_stdev", 0)
            rationale_parts.append(
                f"\n\nNote: Margin volatility analysis shows ±{volatility:.1f} percentage point variation. "
                "This earnings volatility is reflected in the multiple adjustment, ensuring the "
                "valuation appropriately discounts for quality of earnings risk."
            )
        
        return " ".join(rationale_parts)

