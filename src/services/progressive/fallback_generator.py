"""
Fallback Valuation Generator

Generates explicitly disclosed fallback previews when the caller opts into
untrusted fallback multiples. Without that consent, this generator fails closed
with zero-value blocked outputs.
"""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal

logger = logging.getLogger(__name__)


def _country_from_progressive_context(context: Dict[str, Any]) -> str:
    raw = context.get("country_code") or context.get("country")
    if not raw:
        return "BE"
    return str(raw).strip().upper() or "BE"


@dataclass
class FallbackValuationPreview:
    """Fallback valuation preview with industry-based estimates"""

    value_low: Decimal
    value_mid: Decimal
    value_high: Decimal
    confidence_score: Decimal
    confidence_level: str
    methodology: str
    multiple_low: Decimal
    multiple_high: Decimal
    industry: str
    data_completeness: Decimal
    timestamp: str
    is_fallback: bool = True
    fallback_reason: str = "Full calculation unavailable"


class FallbackValuationGenerator:
    """Generate disclosed fallback outputs only when explicitly authorized."""

    INDUSTRY_MULTIPLES = {
        "technology": {"revenue": Decimal("3.5"), "ebitda": 12.0},
        "retail": {"revenue": Decimal("0.8"), "ebitda": 6.0},
        "services": {"revenue": Decimal("1.5"), "ebitda": 8.0},
        "manufacturing": {"revenue": Decimal("1.2"), "ebitda": 7.0},
        "healthcare": {"revenue": Decimal("2.5"), "ebitda": 10.0},
        "finance": {"revenue": Decimal("2.0"), "ebitda": 9.0},
        "real_estate": {"revenue": Decimal("1.0"), "ebitda": 5.0},
        "education": {"revenue": Decimal("1.8"), "ebitda": 7.5},
        "default": {"revenue": Decimal("2.0"), "ebitda": 8.0},
    }

    def __init__(self):
        logger.info("[FALLBACK] FallbackValuationGenerator initialized")

    def _allows_untrusted_fallback(self, context: Dict[str, Any]) -> bool:
        if context.get("allow_untrusted_multiples_fallback") is True:
            return True
        for key in ("metadata", "business_context", "multiples_metadata"):
            nested = context.get(key)
            if (
                isinstance(nested, dict)
                and nested.get("allow_untrusted_multiples_fallback") is True
            ):
                return True
        return False

    def _blocked_preview(
        self,
        context: Dict[str, Any],
        error: Optional[str],
    ) -> FallbackValuationPreview:
        return FallbackValuationPreview(
            value_low=Decimal("0"),
            value_mid=Decimal("0"),
            value_high=Decimal("0"),
            confidence_score=Decimal("0"),
            confidence_level="blocked",
            methodology="Resolved benchmark contract required",
            multiple_low=Decimal("0"),
            multiple_high=Decimal("0"),
            industry=self._extract_industry(context),
            data_completeness=Decimal("0"),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            is_fallback=True,
            fallback_reason=error or "Fallback multiples require explicit consent",
        )

    def _blocked_dict(
        self,
        context: Dict[str, Any],
        error: Optional[str],
        *,
        confidence_level: str = "blocked",
    ) -> Dict[str, Any]:
        return {
            "value_low": Decimal("0"),
            "value_mid": Decimal("0"),
            "value_high": Decimal("0"),
            "confidence_score": Decimal("0"),
            "confidence_level": confidence_level,
            "methodology": "Resolved benchmark contract required",
            "industry": self._extract_industry(context),
            "data_completeness": Decimal("0"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_fallback": True,
            "fallback_reason": error or "Fallback multiples require explicit consent",
            "blocked": True,
            "requires_benchmark_contract": True,
            "publication_allowed": False,
        }

    def generate_fallback_preview(
        self, context: Dict[str, Any], error: Optional[str] = None
    ) -> FallbackValuationPreview:
        """Generate simple multiple-based estimate using industry heuristics"""
        logger.info(f"[FALLBACK] Generating fallback preview | context_keys={list(context.keys())}")

        if not self._allows_untrusted_fallback(context):
            return self._blocked_preview(context, error)

        revenue = self._extract_revenue(context)
        industry = self._extract_industry(context)

        # Get industry-specific multiples
        industry_data = self.INDUSTRY_MULTIPLES.get(industry, self.INDUSTRY_MULTIPLES["default"])
        revenue_multiple = industry_data["revenue"]

        # Calculate base estimate
        if revenue and revenue > 0:
            estimated_value = revenue * revenue_multiple
            confidence_score = Decimal("0.3")
            confidence_level = "Low (industry averages)"
            methodology = f"Simplified {industry} industry multiple ({revenue_multiple}x revenue)"
        else:
            # Default estimate for unknown revenue
            estimated_value = 1000000  # €1M default
            confidence_score = Decimal("0.1")
            confidence_level = "Very Low (no revenue data)"
            methodology = "Default industry estimate"

        # Apply variance for low/high estimates
        variance = Decimal("0.3")
        value_low = estimated_value * (1 - variance)
        value_high = estimated_value * (1 + variance)

        logger.info(
            f"[FALLBACK] Generated fallback estimate | value={estimated_value:,.0f} | industry={industry} | revenue={revenue}"
        )

        return FallbackValuationPreview(
            value_low=value_low,
            value_mid=estimated_value,
            value_high=value_high,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            methodology=methodology,
            multiple_low=revenue_multiple * Decimal("0.7"),
            multiple_high=revenue_multiple * Decimal("1.3"),
            industry=industry,
            data_completeness=Decimal("0.3"),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            is_fallback=True,
            fallback_reason=error or "Full calculation unavailable",
        )

    def generate_fallback_intermediate(
        self,
        context: Dict[str, Any],
        error: Optional[str] = None,
        locale: str = "nl",
    ) -> Dict[str, Any]:
        """Generate fallback intermediate valuation"""
        logger.info(
            f"[FALLBACK] Generating fallback intermediate | context_keys={list(context.keys())}"
        )

        if not self._allows_untrusted_fallback(context):
            return self._blocked_dict(context, error)

        from src.services.infrastructure.translations import (
            get_translations,
            normalize_report_locale,
        )

        _cc = _country_from_progressive_context(context)
        _t = get_translations(
            normalize_report_locale(locale),
            country_code=_cc,
        )

        revenue = self._extract_revenue(context)
        ebitda = self._extract_ebitda(context)
        industry = self._extract_industry(context)

        # Use EBITDA multiple if available, otherwise revenue multiple
        industry_data = self.INDUSTRY_MULTIPLES.get(industry, self.INDUSTRY_MULTIPLES["default"])

        if ebitda and ebitda > 0:
            ebitda_multiple = industry_data["ebitda"]
            estimated_value = ebitda * ebitda_multiple
            methodology = f"EBITDA multiple ({ebitda_multiple}x EBITDA)"
        elif revenue and revenue > 0:
            revenue_multiple = industry_data["revenue"]
            estimated_value = revenue * revenue_multiple
            methodology = f"Revenue multiple ({revenue_multiple}x revenue)"
        else:
            estimated_value = 1000000
            methodology = "Default industry estimate"

        return {
            "value_low": estimated_value * Decimal("0.7"),
            "value_mid": estimated_value,
            "value_high": estimated_value * Decimal("1.3"),
            "confidence_score": Decimal("0.4"),
            "confidence_level": _t.transformer_confidence_low_industry,
            "methodology": methodology,
            "industry": industry,
            "data_completeness": Decimal("0.4"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_fallback": True,
            "fallback_reason": error or "Full calculation unavailable",
        }

    def generate_fallback_advanced(
        self,
        context: Dict[str, Any],
        error: Optional[str] = None,
        locale: str = "nl",
    ) -> Dict[str, Any]:
        """Generate fallback advanced valuation"""
        logger.info(
            f"[FALLBACK] Generating fallback advanced | context_keys={list(context.keys())}"
        )

        if not self._allows_untrusted_fallback(context):
            return self._blocked_dict(context, error)

        from src.services.infrastructure.translations import (
            get_translations,
            normalize_report_locale,
        )

        _cc = _country_from_progressive_context(context)
        _t = get_translations(
            normalize_report_locale(locale),
            country_code=_cc,
        )

        # Use more sophisticated heuristics for advanced fallback
        revenue = self._extract_revenue(context)
        ebitda = self._extract_ebitda(context)
        industry = self._extract_industry(context)

        # Try multiple approaches and take the average
        estimates = []

        if revenue and revenue > 0:
            industry_data = self.INDUSTRY_MULTIPLES.get(
                industry, self.INDUSTRY_MULTIPLES["default"]
            )
            revenue_estimate = revenue * industry_data["revenue"]
            estimates.append(revenue_estimate)

        if ebitda and ebitda > 0:
            industry_data = self.INDUSTRY_MULTIPLES.get(
                industry, self.INDUSTRY_MULTIPLES["default"]
            )
            ebitda_estimate = ebitda * industry_data["ebitda"]
            estimates.append(ebitda_estimate)

        if not estimates:
            estimated_value = 1000000
        else:
            estimated_value = sum(estimates) / len(estimates)

        return {
            "value_low": estimated_value * Decimal("0.6"),
            "value_mid": estimated_value,
            "value_high": estimated_value * Decimal("1.4"),
            "confidence_score": Decimal("0.5"),
            "confidence_level": _t.transformer_confidence_medium_industry,
            "methodology": "Multi-factor industry analysis",
            "industry": industry,
            "data_completeness": Decimal("0.5"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_fallback": True,
            "fallback_reason": error or "Full calculation unavailable",
        }

    def generate_fallback_complete(
        self,
        context: Dict[str, Any],
        error: Optional[str] = None,
        locale: str = "nl",
    ) -> Dict[str, Any]:
        """Generate fallback complete valuation"""
        logger.info(
            f"[FALLBACK] Generating fallback complete | context_keys={list(context.keys())}"
        )

        if not self._allows_untrusted_fallback(context):
            return self._blocked_dict(context, error)

        from src.services.infrastructure.translations import (
            get_translations,
            normalize_report_locale,
        )

        _cc = _country_from_progressive_context(context)
        _t = get_translations(
            normalize_report_locale(locale),
            country_code=_cc,
        )

        # Use the most comprehensive fallback approach
        revenue = self._extract_revenue(context)
        ebitda = self._extract_ebitda(context)
        industry = self._extract_industry(context)

        # Weighted average of multiple approaches
        estimates = []
        weights = []

        if revenue and revenue > 0:
            industry_data = self.INDUSTRY_MULTIPLES.get(
                industry, self.INDUSTRY_MULTIPLES["default"]
            )
            revenue_estimate = revenue * industry_data["revenue"]
            estimates.append(revenue_estimate)
            weights.append(Decimal("0.4"))

        if ebitda and ebitda > 0:
            industry_data = self.INDUSTRY_MULTIPLES.get(
                industry, self.INDUSTRY_MULTIPLES["default"]
            )
            ebitda_estimate = ebitda * industry_data["ebitda"]
            estimates.append(ebitda_estimate)
            weights.append(Decimal("0.6"))

        if not estimates:
            estimated_value = 1000000
        else:
            # Weighted average
            total_weight = sum(weights)
            estimated_value = (
                sum(est * weight for est, weight in zip(estimates, weights)) / total_weight
            )

        return {
            "value_low": estimated_value * Decimal("0.5"),
            "value_mid": estimated_value,
            "value_high": estimated_value * Decimal("1.5"),
            "confidence_score": Decimal("0.6"),
            "confidence_level": _t.transformer_confidence_medium_high_industry,
            "methodology": "Weighted industry multiple analysis",
            "industry": industry,
            "data_completeness": Decimal("0.6"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_fallback": True,
            "fallback_reason": error or "Full calculation unavailable",
        }

    def _extract_revenue(self, context: Dict[str, Any]) -> Optional[Decimal]:
        """Extract revenue from context with error handling"""
        try:
            revenue = context.get("revenue")
            if revenue:
                return to_decimal(revenue)
        except (ValueError, TypeError):
            logger.warning(f"[FALLBACK] Could not parse revenue: {context.get('revenue')}")
        return None

    def _extract_ebitda(self, context: Dict[str, Any]) -> Optional[Decimal]:
        """Extract EBITDA from context with error handling"""
        try:
            ebitda = context.get("ebitda")
            if ebitda:
                return to_decimal(ebitda)
        except (ValueError, TypeError):
            logger.warning(f"[FALLBACK] Could not parse EBITDA: {context.get('ebitda')}")
        return None

    def _extract_industry(self, context: Dict[str, Any]) -> str:
        """Extract industry from context with fallback"""
        industry = context.get("industry", "").lower().strip()

        # Map common industry names to our categories
        industry_mapping = {
            "tech": "technology",
            "software": "technology",
            "saas": "technology",
            "ecommerce": "retail",
            "online retail": "retail",
            "b2b services": "services",
            "consulting": "services",
            "health": "healthcare",
            "medical": "healthcare",
            "banking": "finance",
            "fintech": "finance",
            "property": "real_estate",
            "school": "education",
            "university": "education",
        }

        return industry_mapping.get(industry, industry or "default")

    def _get_industry_multiple(self, industry: str) -> Decimal:
        """Get revenue multiple for industry"""
        industry_data = self.INDUSTRY_MULTIPLES.get(industry, self.INDUSTRY_MULTIPLES["default"])
        return industry_data["revenue"]
