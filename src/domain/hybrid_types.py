"""
Hybrid Methodology Type Definitions

Defines data classes and enums for the hybrid valuation methodology system.
These types support intelligent DCF vs Multiples decision-making with growth awareness.

@author UpSwitch CTO Team
@version 1.0.0
@date November 2025
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class MethodologyDecision(Enum):
    """
    Methodology decision options for hybrid valuation.

    Based on growth-aware decision matrix:
    - MULTIPLES_ONLY: DCF not suitable (score < 40)
    - HYBRID_MULTIPLES_PRIMARY: Multiples favored (score 40-69, weights ~70/30)
    - HYBRID_DCF_PRIMARY: DCF favored (score ≥70, weights ~30/70)
    """

    MULTIPLES_ONLY = "multiples_only"
    HYBRID_MULTIPLES_PRIMARY = "hybrid_multiples_primary"
    HYBRID_DCF_PRIMARY = "hybrid_dcf_primary"


@dataclass
class DCFSuitabilityScore:
    """
    Detailed scoring breakdown for DCF methodology suitability.

    Total score 0-100 determines methodology decision:
    - < 40: Multiples only
    - 40-69: Hybrid (Multiples primary)
    - ≥ 70: Hybrid (DCF primary)
    """

    # Individual component scores
    revenue_size_score: int = 0  # 0-25 points
    data_quality_score: int = 0  # 0-25 points
    growth_score: int = 0  # 0-20 points (NEW - cofounder feedback)
    business_model_score: int = 0  # 0-15 points (NEW - SaaS bonus)
    recurring_revenue_score: int = 0  # 0-10 points (NEW)
    historical_data_score: int = 0  # 0-5 points

    # Total
    total_score: int = 0  # Sum of all components (0-100)

    # Explanation
    breakdown: Dict[str, Any] = field(default_factory=dict)
    exclusion_reason: Optional[str] = None


@dataclass
class WeightResult:
    """
    Result of hybrid weight calculation.

    Represents the final DCF/Multiples weights after:
    1. Base weight lookup (database or default)
    2. Growth adjustments
    3. Constraint application
    4. Revenue enforcement
    5. Normalization
    """

    dcf_weight: Decimal
    multiples_weight: Decimal

    # Metadata
    source: str  # "business_context", "database", "hardcoded", "default"
    adjustments_applied: List[str] = field(default_factory=list)
    rationale: str = ""

    # Original base weights (before adjustments)
    base_dcf_weight: Optional[Decimal] = None
    base_multiples_weight: Optional[Decimal] = None

    def __post_init__(self):
        """Validate weights sum to 1.0 using Decimal arithmetic (bank-grade precision)"""
        total = self.dcf_weight + self.multiples_weight
        if abs(total - Decimal('1.0')) > Decimal('0.01'):
            raise ValueError(
                f"Weights must sum to 1.0, got {float(total):.3f} "
                f"(DCF: {self.dcf_weight}, Multiples: {self.multiples_weight})"
            )


@dataclass
class AggregatedValuation:
    """
    Result of aggregating DCF and Multiples valuations.

    Combines results from both methodologies using calculated weights.
    """

    # Core valuation values
    equity_value: Decimal
    equity_value_low: Optional[Decimal] = None
    equity_value_high: Optional[Decimal] = None
    enterprise_value: Decimal = 0.0
    enterprise_value_low: Optional[Decimal] = None
    enterprise_value_high: Optional[Decimal] = None

    # Methodology information
    methodology: str = (
        "hybrid"  # "multiples_only", "hybrid_multiples_primary", "hybrid_dcf_primary"
    )
    weights: Optional[WeightResult] = None

    # Component results (for transparency)
    component_results: Dict[str, Any] = field(default_factory=dict)

    # Confidence and ranges
    confidence_score: Optional[Decimal] = None
    range_methodology: Optional[str] = None  # "dispersion", "confidence"

    # Metadata
    calculation_timestamp: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class MethodologyEligibilityResult:
    """
    Complete result of methodology eligibility decision.

    Includes the decision, scoring breakdown, and explanation.
    """

    decision: MethodologyDecision
    suitability_score: DCFSuitabilityScore
    should_calculate_dcf: bool
    explanation: str

    # Recommendations
    recommended_dcf_weight: Decimal = 0.5
    recommended_multiples_weight: Decimal = 0.5


# ============================================================================
# CONSTANTS
# ============================================================================

# Score thresholds for methodology decision
SCORE_THRESHOLD_MULTIPLES_ONLY = 40
SCORE_THRESHOLD_HYBRID_DCF_PRIMARY = 70

# Revenue size tiers (in EUR)
REVENUE_MICRO = 100_000  # Below this: exclude DCF
REVENUE_VERY_SMALL = 1_000_000  # €100K-€1M: conditional DCF
REVENUE_SMALL = 5_000_000  # €1M-€5M: Hybrid (Multiples primary)
REVENUE_MEDIUM = 10_000_000  # €5M-€10M: Hybrid (balanced)
# ≥€10M: Hybrid (DCF primary) or DCF primary

# Growth rate thresholds (CAGR)
GROWTH_HIGH = 0.25  # ≥25% CAGR = high growth
GROWTH_MODERATE = 0.15  # 15-25% CAGR = moderate growth
GROWTH_LOW = 0.05  # 5-15% CAGR = low growth
# <5% CAGR = stagnant/declining

# Data quality thresholds (0-100)
DATA_QUALITY_EXCELLENT = 80
DATA_QUALITY_GOOD = 60
DATA_QUALITY_FAIR = 40
# <40 = poor data quality

# Business model types with DCF bonus
BUSINESS_MODELS_DCF_FRIENDLY = {
    "saas",
    "software",
    "subscription",
    "recurring",
    "manufacturing",
    "real-estate",
    "logistics",
}

# Historical data requirements (years)
HISTORICAL_DATA_MINIMUM = 2
HISTORICAL_DATA_PREFERRED = 3

# ============================================================================
# WHITE PAPER REVENUE THRESHOLDS (Governance Guardrails)
# ============================================================================
# Per Upswitch Valuation Metrics White Paper:
# Revenue-based DCF weight caps for risk management

REVENUE_THRESHOLD_MICRO = 2_500_000  # <€2.5M: DCF weight = 0% (forced)
REVENUE_THRESHOLD_SMALL = 5_000_000  # €2.5-5M: DCF weight ≤ 10% (capped)
REVENUE_THRESHOLD_MID = 10_000_000  # €5-10M: DCF weight ≤ 40% (capped)
# >€10M: DCF weight ≤ 60% (soft cap, can exceed with justification)

# Corresponding DCF weight caps
DCF_WEIGHT_CAP_MICRO = 0.00  # 0% for <€2.5M
DCF_WEIGHT_CAP_SMALL = 0.10  # 10% for €2.5-5M
DCF_WEIGHT_CAP_MID = 0.40  # 40% for €5-10M
DCF_WEIGHT_CAP_LARGE = 0.60  # 60% for >€10M (soft cap)
