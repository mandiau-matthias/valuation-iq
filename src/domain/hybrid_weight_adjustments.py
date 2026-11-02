"""Adjustment and guardrail helpers for hybrid DCF/multiples weights."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Tuple

from src.domain.dcf_policy import user_explicitly_configured_dcf
from src.domain.historical_years import oldest_historical_year
from src.domain.hybrid_revenue_enforcement import (
    build_revenue_enforcement_decision,
    is_high_growth_revenue_profile,
)
from src.domain.hybrid_types import MethodologyDecision
from src.domain.interfaces.request_protocol import ValuationRequestProtocol
from src.utils.decimal_helpers import from_decimal, to_decimal


class HybridWeightAdjustmentService:
    """Apply growth, revenue guardrail, and normalization adjustments."""

    def __init__(self, logger_instance):
        self.logger = logger_instance

    def apply_growth_adjustments(
        self,
        request: ValuationRequestProtocol,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        weight_source: str,
        min_weight: Decimal,
        max_weight: Decimal,
    ) -> Tuple[Decimal, Decimal, list]:
        """
        Apply growth profile adjustments.

        High growth → favor multiples (captures current market)
        Declining → favor DCF (fundamental analysis)

        Returns:
            Tuple of (dcf_weight, multiples_weight, adjustments_list)
        """
        adjustments = []
        historical = [
            year
            for year in (request.historical_years_data or [])
            if not getattr(year, "is_forecast", False)
        ]

        if not historical or len(historical) == 0:
            return dcf_weight, multiples_weight, adjustments

        oldest_year = oldest_historical_year(historical)
        first_revenue = to_decimal(getattr(oldest_year, "revenue", 0) or 0)
        current_revenue = to_decimal(request.current_year_data.revenue or 0)

        if first_revenue <= 0:
            return dcf_weight, multiples_weight, adjustments

        # Determine adjustment strength based on weight source
        has_business_weights = weight_source in [
            "business_context",
            "repository",
            "hardcoded_dict",
            "titan_enrichment",
        ]

        # High growth (>20% total growth)
        if current_revenue > first_revenue * Decimal("1.2"):
            # Favor multiples for high-growth companies
            adjustment = Decimal("0.05") if has_business_weights else Decimal("0.08")
            dcf_weight = max(min_weight, dcf_weight - adjustment)
            multiples_weight = min(max_weight, multiples_weight + adjustment)
            adjustments.append(f"high_growth_+{from_decimal(adjustment):.0%}_multiples")
            self.logger.info(
                "📈 High growth detected, favoring multiples",
                extra={
                    "first_revenue": from_decimal(first_revenue),
                    "current_revenue": from_decimal(current_revenue),
                    "adjustment": from_decimal(adjustment),
                },
            )

        # Declining (<5% decline)
        elif current_revenue < first_revenue * Decimal("0.95"):
            # Favor DCF for declining companies (fundamental analysis)
            adjustment = Decimal("0.03") if has_business_weights else Decimal("0.05")
            dcf_weight = min(max_weight, dcf_weight + adjustment)
            multiples_weight = max(min_weight, multiples_weight - adjustment)
            adjustments.append(f"declining_revenue_+{from_decimal(adjustment):.0%}_dcf")
            self.logger.info(
                "📉 Declining revenue detected, favoring DCF",
                extra={
                    "first_revenue": from_decimal(first_revenue),
                    "current_revenue": from_decimal(current_revenue),
                    "adjustment": from_decimal(adjustment),
                },
            )

        return dcf_weight, multiples_weight, adjustments

    def apply_revenue_enforcement(
        self,
        request: ValuationRequestProtocol,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        methodology_decision: MethodologyDecision,
    ) -> Tuple[Decimal, Decimal, Optional[str]]:
        """
        Apply revenue-based DCF weight guardrails (White Paper standards).

        Per Upswitch Valuation Metrics White Paper:
        - Revenue <€2.5M: DCF weight = 0% (forced, Multiples only)
        - Revenue €2.5-5M: DCF weight ≤ 10% (capped)
        - Revenue €5-10M: DCF weight ≤ 40% (capped)
        - Revenue >€10M: DCF weight ≤ 60% (soft cap)

        These are FINAL overrides after all other adjustments.
        Guardrails ensure risk management for smaller companies.

        Academic rationale:
        - McKinsey Valuation (2015): Small Firm Effect
        - Damodaran (2012): DCF unsuitable for volatile cash flows
        - PwC Valuation Guidelines: Revenue-based methodology selection

        Returns:
            Tuple of (dcf_weight, multiples_weight, enforcement_reason)
        """
        revenue = to_decimal(request.current_year_data.revenue or 0)
        original_dcf = dcf_weight

        # Only enforce guardrails if DCF is allowed by methodology decision
        if methodology_decision == MethodologyDecision.MULTIPLES_ONLY:
            return dcf_weight, multiples_weight, None

        # Advisor-explicit weighting overrides the revenue guardrail (honored +
        # disclosed, never silently zeroed). When the advisor deliberately
        # configured DCF — custom Waarderingssynthese weights, selected_method
        # ``dcf``, direct-FCFF mode, or a business_context DCF schedule — we keep
        # their weighting and record a disclosure marker instead of forcing DCF
        # to 0%. The methodology *determiner* already honors this intent
        # ("suitability score bypassed per user intent"); the weight enforcement
        # must agree, otherwise the cover (which renders the advisor's weighted
        # synthesis) and the engine output diverge into two different valuations
        # in one report (VAL-2026 two-brain regression: €582K cover vs €407K
        # body). The guardrail stays the default for engine-chosen weights.
        if user_explicitly_configured_dcf(request):
            self.logger.info(
                "🧭 Advisor-explicit weighting honored — White Paper revenue "
                "guardrail bypassed and disclosed (not silently overriding DCF)",
                extra={
                    "revenue": from_decimal(to_decimal(request.current_year_data.revenue or 0)),
                    "dcf_weight": from_decimal(dcf_weight),
                    "multiples_weight": from_decimal(multiples_weight),
                },
            )
            return dcf_weight, multiples_weight, "advisor_override_dcf_guardrail_disclosed"

        # Detect high-growth profile for guardrail relaxation
        # Per Damodaran (2012): high-growth companies benefit from DCF even at smaller scale
        decision = build_revenue_enforcement_decision(
            revenue,
            dcf_weight,
            multiples_weight,
            is_high_growth_revenue_profile(request),
        )

        if decision.reason and decision.log_message:
            extra = {
                "revenue": from_decimal(revenue),
                "original_dcf": from_decimal(original_dcf),
                "enforced_dcf": from_decimal(decision.dcf_weight),
            }
            if decision.is_high_growth:
                extra["is_high_growth"] = True
            self.logger.info(decision.log_message, extra=extra)

        return decision.dcf_weight, decision.multiples_weight, decision.reason

    def normalize_weights(
        self, dcf_weight: Decimal, multiples_weight: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """
        Normalize weights to ensure they sum to 1.0.

        Returns:
            Tuple of (dcf_weight, multiples_weight)
        """
        total = dcf_weight + multiples_weight

        if total <= 0:
            self.logger.warning("Both weights are zero or negative, defaulting to 100% multiples")
            return Decimal("0.0"), Decimal("1.0")

        if abs(total - Decimal("1.0")) > Decimal("0.0001"):
            self.logger.debug(
                "Normalizing weights",
                extra={
                    "before_total": from_decimal(total),
                    "before_dcf": from_decimal(dcf_weight),
                    "before_multiples": from_decimal(multiples_weight),
                },
            )
            dcf_weight = dcf_weight / total
            multiples_weight = multiples_weight / total

        return dcf_weight, multiples_weight

    def build_rationale(
        self,
        weight_source: str,
        base_dcf: Decimal,
        final_dcf: Decimal,
        final_multiples: Decimal,
        adjustments: list,
    ) -> str:
        """Build human-readable rationale for weight decision."""

        source_explanations = {
            "titan_enrichment": "Upswitch Index benchmark contract and business-type policy (via Titan)",
            "business_context": "Frontend user preferences",
            "repository": "Synced business-type cache weights for this business type",
            "hardcoded_dict": "Business type-specific weights",
            "profitability_default": "Profitability-based default weights",
            "methodology_decision": "Methodology eligibility decision",
        }

        rationale = f"Base: {source_explanations.get(weight_source, weight_source)}"

        # Add adjustment summary if weights changed
        if abs(base_dcf - final_dcf) > 0.01:
            adjustment_count = len(
                [
                    a
                    for a in adjustments
                    if a not in ["normalized", "constraints_20%-80%", "constraints_40%-60%"]
                ]
            )
            if adjustment_count > 0:
                rationale += f" with {adjustment_count} adjustment(s)"

        rationale += f" → DCF: {final_dcf:.0%}, Multiples: {final_multiples:.0%}"

        return rationale
