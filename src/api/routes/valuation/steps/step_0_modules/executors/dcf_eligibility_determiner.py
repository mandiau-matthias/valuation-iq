"""DCF Eligibility Determiner for Step 0 Data Quality."""

from typing import Dict, Optional, Tuple

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
from src.domain.dcf_policy import user_explicitly_configured_dcf
from src.domain.valuation_contract import method_key_matches
from src.utils.logging import get_logger

from .dcf_eligibility_rules import (
    current_revenue,
    eligibility_criteria_summary,
    historical_actual_years,
    historical_data_failure_reason,
    is_sole_trader_request,
    quality_threshold_failure_reason,
    resolve_revenue_threshold,
    revenue_failure_reason,
)

logger = get_logger(__name__)


class DCFEligibilityDeterminer:
    """Determines DCF methodology eligibility."""

    def __init__(self, business_type_triage: BusinessTypeTriageEngine):
        """
        Initialize the DCF eligibility determiner.

        Args:
            business_type_triage: The business type triage engine
        """
        self.business_type_triage = business_type_triage

    def is_dcf_eligible(
        self,
        request,
        quality_score: int,
        step_number: int = 0,
        user_selected_method: Optional[str] = None,
        sub_calculations: Optional[Dict[str, Dict[str, object]]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if DCF methodology is viable.

        McKinsey Criteria (base):
        1. Data quality score >= 60%
        2. Revenue >= €5,000,000 (or lower for high-growth SaaS)
        3. Historical data >= 3 years (2 years minimum with higher quality)

        When ``user_selected_method`` is ``"dcf"`` the revenue threshold is
        bypassed (advisor explicitly chose DCF). Sole-trader exclusion, data
        quality, and historical-years checks still apply.

        Business-Type Adjustments:
        - SaaS/Software: Lower revenue threshold (€1M) if high growth
        - Professional Services: Standard threshold
        - Retail/Food: Standard threshold

        Sole Trader Exclusion:
        - Sole traders are almost always excluded from DCF
        - Revenue <€5M + owner-dependent = DCF not suitable
        - Auto-exclude for sole traders regardless of other criteria

        Args:
            request: The valuation request object
            quality_score: The quality score (0-100)
            step_number: The step number (default: 0)
            user_selected_method: If ``"dcf"``, bypass revenue threshold
                (advisor explicitly selected DCF upfront)

        Returns:
            Tuple of (is_eligible, exclusion_reason):
            - is_eligible: True if DCF is eligible, False otherwise
            - exclusion_reason: Reason for exclusion if not eligible, None if eligible
        """
        user_forced_dcf = method_key_matches(user_selected_method, "dcf")
        user_explicit_dcf_intent = user_explicitly_configured_dcf(request)
        dcf_revenue_bypass = user_forced_dcf or user_explicit_dcf_intent

        logger.debug(
            "🔍 Checking sole trader status",
            extra={
                "step_number": step_number,
                "business_type": getattr(request, "business_type", None),
                "number_of_owners": getattr(request, "number_of_owners", None),
                "number_of_employees": getattr(request, "number_of_employees", None),
            },
        )

        if is_sole_trader_request(request):
            logger.info(
                "❌ DCF not eligible: sole trader excluded",
                extra={
                    "step_number": step_number,
                    "reason": "Sole traders are owner-dependent and typically too small for DCF",
                    "revenue": current_revenue(request),
                    "criteria_failed": "Sole trader exclusion (McKinsey/Bain standard)",
                },
            )
            return (
                False,
                "Sole trader excluded (owner-dependent, typically too small for DCF per academic valuation standards - Trugman 2017, Pratt & Niculita 2008)",
            )

        logger.debug(
            "✅ Not a sole trader, continuing DCF eligibility check",
            extra={"step_number": step_number},
        )

        logger.debug(
            "🔍 Checking data quality threshold",
            extra={
                "step_number": step_number,
                "quality_score": quality_score,
                "threshold": 60,
                "threshold_met": quality_score >= 60,
            },
        )

        quality_failure = quality_threshold_failure_reason(quality_score)
        if quality_failure is not None:
            logger.info(
                "❌ DCF not eligible: data quality too low",
                extra={
                    "step_number": step_number,
                    "quality_score": quality_score,
                    "threshold": 60,
                    "criteria_failed": f"Data quality {quality_score}% < 60% threshold",
                },
            )
            return False, quality_failure

        logger.debug(
            "✅ Data quality threshold met",
            extra={"step_number": step_number, "quality_score": quality_score},
        )

        business_category = self.business_type_triage.get_business_type_category(
            getattr(request, "business_type_id", None),
            getattr(request, "business_model", None),
            getattr(request, "industry", None),
            category_id=getattr(request, "category_id", None),
        )
        business_category_value = business_category.value
        revenue = current_revenue(request)
        historical_years = historical_actual_years(request)
        logger.debug(
            "🔍 Determining revenue threshold (business-type aware)",
            extra={
                "step_number": step_number,
                "business_category": business_category_value,
                "default_threshold": 5_000_000,
                "revenue": revenue,
            },
        )

        threshold_decision = resolve_revenue_threshold(
            request=request,
            business_category_value=business_category_value,
            revenue=revenue,
            historical_years=historical_years,
            sub_calculations=sub_calculations,
            step_number=step_number,
        )
        revenue_threshold = threshold_decision.threshold

        logger.debug(
            "🔍 Checking revenue threshold",
            extra={
                "step_number": step_number,
                "revenue": revenue,
                "threshold": revenue_threshold,
                "threshold_source": threshold_decision.source,
                "threshold_met": revenue >= revenue_threshold,
                "formula": f"Revenue {revenue} >= Threshold {revenue_threshold}",
            },
        )

        if revenue < revenue_threshold:
            if dcf_revenue_bypass:
                logger.info(
                    "⚡ DCF revenue threshold bypassed: explicit DCF intent detected",
                    extra={
                        "step_number": step_number,
                        "revenue": revenue,
                        "threshold": revenue_threshold,
                        "business_category": business_category_value,
                        "user_forced": user_forced_dcf,
                        "user_explicit_dcf_intent": user_explicit_dcf_intent,
                    },
                )
            else:
                logger.info(
                    "❌ DCF not eligible: revenue below threshold",
                    extra={
                        "step_number": step_number,
                        "revenue": revenue,
                        "threshold": revenue_threshold,
                        "business_category": business_category_value,
                        "criteria_failed": f"Revenue {revenue} < Threshold {revenue_threshold}",
                        "shortfall": revenue_threshold - revenue,
                    },
                )
                return False, revenue_failure_reason(revenue, revenue_threshold)

        logger.debug(
            "✅ Revenue threshold met",
            extra={"step_number": step_number, "revenue": revenue, "threshold": revenue_threshold},
        )

        historical_count = len(historical_years) if isinstance(historical_years, list) else 0

        logger.debug(
            "🔍 Checking historical data requirement",
            extra={
                "step_number": step_number,
                "historical_years_count": historical_count,
                "minimum_required": 2,
                "preferred": 3,
                "requirement_met": historical_count >= 2,
            },
        )

        historical_failure = historical_data_failure_reason(
            historical_count=historical_count,
            quality_score=quality_score,
        )
        if historical_failure is not None and historical_count < 2:
            logger.info(
                "❌ DCF not eligible: insufficient historical data",
                extra={
                    "step_number": step_number,
                    "years": historical_count,
                    "required": 2,
                    "criteria_failed": f"Historical years {historical_count} < 2 minimum",
                },
            )
            return False, historical_failure

        if historical_count == 2:
            logger.debug(
                "🔍 Only 2 years of data: checking enhanced quality requirement",
                extra={
                    "step_number": step_number,
                    "historical_years": historical_count,
                    "quality_score": quality_score,
                    "required_quality": 70,
                    "enhanced_requirement_met": quality_score >= 70,
                },
            )

            if historical_failure is not None:
                logger.info(
                    "❌ DCF not eligible: only 2 years of data and quality score below 70%",
                    extra={
                        "step_number": step_number,
                        "years": historical_count,
                        "quality_score": quality_score,
                        "required_quality": 70,
                        "criteria_failed": f"With only 2 years, quality score {quality_score}% < 70% threshold",
                    },
                )
                return False, historical_failure

        logger.info(
            "✅ DCF eligible: all criteria met",
            extra={
                "step_number": step_number,
                "revenue": revenue,
                "revenue_threshold": revenue_threshold,
                "business_category": business_category_value,
                "quality_score": quality_score,
                "historical_years": historical_count,
                "user_forced_dcf": user_forced_dcf,
                "user_explicit_dcf_intent": user_explicit_dcf_intent,
                "criteria_summary": eligibility_criteria_summary(
                    quality_score=quality_score,
                    revenue=revenue,
                    revenue_threshold=revenue_threshold,
                    dcf_revenue_bypass=dcf_revenue_bypass,
                    historical_count=historical_count,
                ),
            },
        )
        return True, None
