"""Business-type methodology scoring and selection policy."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from src.api.routes.valuation.triage.business_type_taxonomy import BusinessTypeCategory
from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValuationMethodology(Enum):
    """
    Primary valuation methodology for a business.

    Selection based on academic literature and market practice:
    - EBITDA_MULTIPLES: Standard for mid-market (EUR 2M-50M)
    - SDE_MULTIPLES: Standard for small business (< EUR 2M)
    - ASSET_BASED: For asset-heavy or distressed businesses
    - DCF: For growth companies or when cash flow projection is reliable
    - HYBRID: Weighted combination based on business characteristics
    """

    EBITDA_MULTIPLES = "ebitda_multiples"
    SDE_MULTIPLES = "sde_multiples"
    ASSET_BASED = "asset_based"
    DCF = "dcf"
    HYBRID = "hybrid"


REVENUE_THRESHOLD_MICRO = Decimal("500000")
REVENUE_THRESHOLD_SMALL = Decimal("2000000")
REVENUE_THRESHOLD_MEDIUM = Decimal("10000000")


@dataclass
class MethodologyDecision:
    """Output of methodology selection logic."""

    primary: ValuationMethodology
    secondary: Optional[ValuationMethodology] = None
    tertiary: Optional[ValuationMethodology] = None
    weights: Dict[str, Decimal] = field(default_factory=dict)
    confidence: Decimal = Decimal("0.7")
    reasoning: str = ""
    data_sources: List[str] = field(default_factory=list)
    sde_suitability: Decimal = Decimal("0")
    ebitda_suitability: Decimal = Decimal("0")
    asset_based_suitability: Decimal = Decimal("0")
    dcf_suitability: Decimal = Decimal("0")

    def to_dict(self) -> Dict[str, object]:
        return {
            "primary": self.primary.value,
            "secondary": self.secondary.value if self.secondary else None,
            "tertiary": self.tertiary.value if self.tertiary else None,
            "weights": {k: float(v) for k, v in self.weights.items()},
            "confidence": float(self.confidence),
            "reasoning": self.reasoning,
            "data_sources": self.data_sources,
            "suitability_scores": {
                "sde": float(self.sde_suitability),
                "ebitda": float(self.ebitda_suitability),
                "asset_based": float(self.asset_based_suitability),
                "dcf": float(self.dcf_suitability),
            },
        }


def _request_revenue(request: ValuationRequest) -> Decimal:
    if hasattr(request, "current_year_data") and request.current_year_data:
        return to_decimal(getattr(request.current_year_data, "revenue", 0) or 0)
    return Decimal("0")


def _request_owner_count(request: ValuationRequest) -> int:
    if hasattr(request, "number_of_owners") and request.number_of_owners:
        return request.number_of_owners
    if hasattr(request, "business_context"):
        business_context = request.business_context or {}
        return business_context.get("number_of_owners", 1)
    return 1


def _calculate_sde_suitability(
    revenue: Decimal,
    num_owners: int,
    category: BusinessTypeCategory,
) -> Decimal:
    """Calculate SDE methodology suitability score (0-1)."""
    score = Decimal("0")

    if revenue < REVENUE_THRESHOLD_MICRO:
        score += Decimal("0.50")
    elif revenue < REVENUE_THRESHOLD_SMALL:
        score += Decimal("0.40")
    elif revenue < REVENUE_THRESHOLD_MEDIUM:
        score += Decimal("0.20")
    else:
        score += Decimal("0.05")

    if num_owners == 1:
        score += Decimal("0.25")
    elif num_owners <= 3:
        score += Decimal("0.20")
    elif num_owners <= 5:
        score += Decimal("0.10")

    high_sde_categories = {
        BusinessTypeCategory.PROFESSIONAL_SERVICES,
        BusinessTypeCategory.HEALTHCARE,
        BusinessTypeCategory.RETAIL_FOOD,
    }
    if category in high_sde_categories:
        score += Decimal("0.25")
    elif category in (BusinessTypeCategory.ECOMMERCE, BusinessTypeCategory.CONSTRUCTION):
        score += Decimal("0.15")
    else:
        score += Decimal("0.10")

    return min(Decimal("1.0"), score)


def _calculate_ebitda_suitability(
    revenue: Decimal,
    num_owners: int,
    category: BusinessTypeCategory,
) -> Decimal:
    """Calculate EBITDA multiples methodology suitability score (0-1)."""
    score = Decimal("0")

    if revenue >= REVENUE_THRESHOLD_MEDIUM:
        score += Decimal("0.50")
    elif revenue >= REVENUE_THRESHOLD_SMALL:
        score += Decimal("0.40")
    elif revenue >= REVENUE_THRESHOLD_MICRO:
        score += Decimal("0.25")
    else:
        score += Decimal("0.15")

    if num_owners > 5:
        score += Decimal("0.25")
    elif num_owners > 3:
        score += Decimal("0.20")
    elif num_owners > 1:
        score += Decimal("0.15")
    else:
        score += Decimal("0.10")

    high_ebitda_categories = {
        BusinessTypeCategory.SAAS_SOFTWARE,
        BusinessTypeCategory.MANUFACTURING,
        BusinessTypeCategory.FINANCIAL_SERVICES,
    }
    if category in high_ebitda_categories:
        score += Decimal("0.25")
    else:
        score += Decimal("0.15")

    return min(Decimal("1.0"), score)


def _calculate_asset_based_suitability(
    category: BusinessTypeCategory,
    request: ValuationRequest,
) -> Decimal:
    """Calculate Asset-Based methodology suitability score (0-1)."""
    score = Decimal("0")

    asset_heavy_categories = {
        BusinessTypeCategory.MANUFACTURING: Decimal("0.60"),
        BusinessTypeCategory.CONSTRUCTION: Decimal("0.50"),
        BusinessTypeCategory.REAL_ESTATE: Decimal("0.55"),
        BusinessTypeCategory.TRANSPORTATION: Decimal("0.45"),
    }
    score += asset_heavy_categories.get(category, Decimal("0.15"))

    if hasattr(request, "asset_based_calibration"):
        asset_calibration = request.asset_based_calibration or {}
        preference = to_decimal(asset_calibration.get("asset_methodology_preference", 0))
        score += preference * Decimal("0.40")

    return min(Decimal("1.0"), score)


def _calculate_dcf_suitability(
    revenue: Decimal,
    category: BusinessTypeCategory,
    request: ValuationRequest,
) -> Decimal:
    """Calculate DCF methodology suitability score (0-1)."""
    score = Decimal("0")

    if revenue >= REVENUE_THRESHOLD_MEDIUM:
        score += Decimal("0.40")
    elif revenue >= REVENUE_THRESHOLD_SMALL:
        score += Decimal("0.20")
    else:
        score += Decimal("0.05")

    growth_categories = {
        BusinessTypeCategory.SAAS_SOFTWARE: Decimal("0.30"),
        BusinessTypeCategory.ECOMMERCE: Decimal("0.20"),
        BusinessTypeCategory.FINANCIAL_SERVICES: Decimal("0.15"),
    }
    score += growth_categories.get(category, Decimal("0.05"))

    if hasattr(request, "dcf_preference"):
        dcf_pref = to_decimal(getattr(request, "dcf_preference", 0) or 0)
        score += dcf_pref * Decimal("0.30")

    return min(Decimal("1.0"), score)


def select_business_type_methodology(
    *,
    request: ValuationRequest,
    category: BusinessTypeCategory,
) -> MethodologyDecision:
    """Select the optimal valuation methodology for a business category."""
    revenue = _request_revenue(request)
    num_owners = _request_owner_count(request)

    sde_suitability = _calculate_sde_suitability(revenue, num_owners, category)
    ebitda_suitability = _calculate_ebitda_suitability(revenue, num_owners, category)
    asset_based_suitability = _calculate_asset_based_suitability(category, request)
    dcf_suitability = _calculate_dcf_suitability(revenue, category, request)

    suitability_scores = [
        (ValuationMethodology.SDE_MULTIPLES, sde_suitability),
        (ValuationMethodology.EBITDA_MULTIPLES, ebitda_suitability),
        (ValuationMethodology.ASSET_BASED, asset_based_suitability),
        (ValuationMethodology.DCF, dcf_suitability),
    ]
    suitability_scores.sort(key=lambda x: x[1], reverse=True)

    primary = suitability_scores[0][0]
    secondary = suitability_scores[1][0] if len(suitability_scores) > 1 else None
    tertiary = suitability_scores[2][0] if len(suitability_scores) > 2 else None

    total_suitability = sum(s[1] for s in suitability_scores[:3])
    if total_suitability > 0:
        weights = {
            suitability_scores[0][0].value: suitability_scores[0][1] / total_suitability,
            suitability_scores[1][0].value: suitability_scores[1][1] / total_suitability,
            suitability_scores[2][0].value: suitability_scores[2][1] / total_suitability,
        }
    else:
        weights = {
            ValuationMethodology.EBITDA_MULTIPLES.value: Decimal("0.70"),
            ValuationMethodology.SDE_MULTIPLES.value: Decimal("0.20"),
            ValuationMethodology.ASSET_BASED.value: Decimal("0.10"),
        }

    reasoning = ". ".join(
        [
            f"Revenue: EUR {from_decimal(revenue):,.0f}",
            f"Owner count: {num_owners}",
            f"Category: {category.value}",
            f"SDE suitability: {from_decimal(sde_suitability * 100):.0f}%",
            f"EBITDA suitability: {from_decimal(ebitda_suitability * 100):.0f}%",
        ]
    )

    primary_score = suitability_scores[0][1]
    secondary_score = suitability_scores[1][1] if len(suitability_scores) > 1 else Decimal("0")
    confidence = min(
        Decimal("0.95"), max(Decimal("0.50"), primary_score - secondary_score + Decimal("0.5"))
    )

    decision = MethodologyDecision(
        primary=primary,
        secondary=secondary,
        tertiary=tertiary,
        weights=weights,
        confidence=confidence,
        reasoning=reasoning,
        data_sources=["Pepperdine (2024)", "BizBuySell (2024)", "Trugman (2017)"],
        sde_suitability=sde_suitability,
        ebitda_suitability=ebitda_suitability,
        asset_based_suitability=asset_based_suitability,
        dcf_suitability=dcf_suitability,
    )

    logger.info(
        "Methodology selected",
        extra={
            "primary": primary.value,
            "secondary": secondary.value if secondary else None,
            "confidence": from_decimal(confidence),
            "revenue": from_decimal(revenue),
            "category": category.value,
        },
    )
    return decision
