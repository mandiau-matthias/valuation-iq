"""
Quick Valuation Calculator Module

Extracted from valuation_orchestrator.py as part of refactoring initiative.

RESPONSIBILITIES:
- Calculate quick valuations using multiples-based approach
- Apply business type adjustments
- Calculate value ranges and confidence scores
- Generate key factors and recommendations

REFACTORING NOTE:
This module extracts the quick valuation logic from the 1,272-line orchestrator
to improve maintainability and testability.
"""

from decimal import Decimal
from typing import Dict, List, Optional

from src.api.routes.valuation.benchmark_contract_utils import (
    benchmark_contract_data_source,
    is_resolved_benchmark_contract,
    normalize_benchmark_contract,
)
from src.api.schemas import QuickValuationRequest
from src.utils.country_code import normalize_iso3166_alpha2
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import MultiplesCalculationError
from src.utils.logging import get_logger

from ..valuation_types import BusinessType, ValuationMethod

logger = get_logger(__name__)


class QuickValuationCalculator:
    """
    Calculates quick business valuations using simplified multiples approach

    Features:
    - Revenue and EBITDA multiples
    - DB-driven business type intelligence
    - Industry-specific adjustments
    - Confidence scoring
    """

    def __init__(
        self, business_rules: Dict[str, object], multiples_adapter=None, business_types_repo=None
    ):
        """
        Initialize quick valuation calculator

        Args:
            business_rules: Business rules configuration
            multiples_adapter: Optional business type multiples adapter
            business_types_repo: Optional business types repository
        """
        self.logger = logger
        self.business_rules = business_rules
        self.multiples_adapter = multiples_adapter
        self.business_types_repo = business_types_repo

        self.logger.debug(
            "✅ QuickValuationCalculator initialized",
            extra={
                "has_multiples_adapter": multiples_adapter is not None,
                "has_business_types_repo": business_types_repo is not None,
            },
        )

    async def calculate(
        self,
        revenue: Decimal,
        ebitda: Decimal,
        industry: str,
        methodology: ValuationMethod,
        business_type_id: Optional[str] = None,
        country_code: Optional[str] = None,
        benchmark_contract: Optional[Dict[str, object]] = None,
        allow_untrusted_multiples_fallback: bool = False,
    ) -> Decimal:
        """
        Calculate quick valuation

        Args:
            revenue: Annual revenue
            ebitda: Annual EBITDA
            industry: Industry category
            methodology: Valuation methodology
            business_type_id: Optional business type ID for DB-driven multiples
            country_code: ISO country for DB multiples lookup (default BE)

        Returns:
            Base valuation amount
        """
        try:
            cc = normalize_iso3166_alpha2(country_code)
            self.logger.info(
                "💰 Starting quick valuation calculation",
                extra={
                    "revenue": revenue,
                    "ebitda": ebitda,
                    "industry": industry,
                    "methodology": (
                        methodology.value if hasattr(methodology, "value") else str(methodology)
                    ),
                    "business_type_id": business_type_id,
                    "country_code": cc,
                },
            )

            # Initialize multiples
            ebitda_multiple = None
            revenue_multiple = None
            data_source = "unknown"
            normalized_contract: Dict[str, object] = {}

            if is_resolved_benchmark_contract(benchmark_contract):
                normalized_contract = normalize_benchmark_contract(benchmark_contract)
                metrics = normalized_contract.get("metrics", {})
                if isinstance(metrics, dict):
                    ev_ebitda_metric = metrics.get("ev_ebitda")
                    ev_revenue_metric = metrics.get("ev_revenue")
                    if (
                        isinstance(ev_ebitda_metric, dict)
                        and ev_ebitda_metric.get("median") is not None
                    ):
                        ebitda_multiple = Decimal(str(ev_ebitda_metric["median"]))
                    if (
                        isinstance(ev_revenue_metric, dict)
                        and ev_revenue_metric.get("median") is not None
                    ):
                        revenue_multiple = Decimal(str(ev_revenue_metric["median"]))

                if (
                    normalized_contract.get("primary_metric") == "ev_ebitda"
                    and ebitda_multiple is None
                ):
                    median = normalized_contract.get("median")
                    if median is not None:
                        ebitda_multiple = Decimal(str(median))
                if (
                    normalized_contract.get("primary_metric") == "ev_revenue"
                    and revenue_multiple is None
                ):
                    median = normalized_contract.get("median")
                    if median is not None:
                        revenue_multiple = Decimal(str(median))

                data_source = benchmark_contract_data_source(benchmark_contract)
                self.logger.info(
                    "Using resolved benchmark contract for quick valuation",
                    extra={
                        "benchmark_id": normalized_contract.get("benchmark_id"),
                        "dataset_version_id": normalized_contract.get("dataset_version_id"),
                        "country_code": normalized_contract.get("country_code"),
                        "region_key": normalized_contract.get("region_key"),
                        "tier": normalized_contract.get("tier"),
                        "scope_stage": normalized_contract.get("scope_stage"),
                        "source": data_source,
                    },
                )
            elif not allow_untrusted_multiples_fallback:
                raise MultiplesCalculationError(
                    "Resolved benchmark contract required for quick valuation multiples. "
                    "Quick valuation will not publish DB, generic, or hardcoded fallback multiples "
                    "unless allow_untrusted_multiples_fallback=true is explicit.",
                    step="quick_valuation_benchmark_contract",
                    calculation_type="Quick Valuation",
                    context={
                        "code": "BENCHMARK_CONTRACT_REQUIRED",
                        "business_type_id": business_type_id,
                        "country_code": cc,
                    },
                )

            # DISCLOSED FALLBACK: legacy DB/cache multiples. This branch is only
            # reachable with explicit caller consent.
            if (
                allow_untrusted_multiples_fallback
                and (ebitda_multiple is None or revenue_multiple is None)
                and business_type_id
                and self.multiples_adapter
            ):
                try:
                    self.logger.debug(
                        "🔍 Fetching disclosed fallback DB-driven multiples",
                        extra={"business_type_id": business_type_id, "country_code": cc},
                    )

                    bt_multiples = self.multiples_adapter.get_multiples_dict(business_type_id, cc)
                    if bt_multiples:
                        ebitda_multiple = bt_multiples.get("ev_ebitda")
                        revenue_multiple = bt_multiples.get("ev_revenue")
                        data_source = "disclosed_business_type_cache_fallback"

                        self.logger.info(
                            f"✅ Using DB multiples for {business_type_id}: "
                            f"EV/EBITDA={ebitda_multiple}, EV/Revenue={revenue_multiple}, "
                            f"DATA_SOURCE={data_source}",
                            extra={
                                "business_type_id": business_type_id,
                                "ev_ebitda": ebitda_multiple,
                                "ev_revenue": revenue_multiple,
                                "source": data_source,
                            },
                        )
                    else:
                        self.logger.warning(
                            "⚠️ No DB multiples found for business_type_id",
                            extra={"business_type_id": business_type_id},
                        )

                except Exception as e:
                    self.logger.warning(
                        f"⚠️ Failed to fetch DB multiples: {e}",
                        extra={
                            "business_type_id": business_type_id,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )

            # PRIORITY 2: Try industry multiples from business rules
            if ebitda_multiple is None or revenue_multiple is None:
                if not allow_untrusted_multiples_fallback:
                    missing_metric = "ev_ebitda" if ebitda_multiple is None else "ev_revenue"
                    raise MultiplesCalculationError(
                        f"Resolved benchmark contract is missing required {missing_metric} metric.",
                        step="quick_valuation_benchmark_contract",
                        calculation_type="Quick Valuation",
                        context={
                            "code": "BENCHMARK_METRIC_REQUIRED",
                            "benchmark_id": normalized_contract.get("benchmark_id"),
                            "missing_metric": missing_metric,
                        },
                    )
                self.logger.info(
                    "📊 Using explicitly disclosed fallback industry multiples from business rules",
                    extra={"industry": industry},
                )

                industry_multiples = self.business_rules.get("industry_multiples", {}).get(
                    industry, {}
                )

                if ebitda_multiple is None:
                    ebitda_multiple = industry_multiples.get("ebitda_multiple", Decimal("5.0"))
                if revenue_multiple is None:
                    revenue_multiple = industry_multiples.get("revenue_multiple", Decimal("1.5"))
                data_source = (
                    "disclosed_industry_rules_fallback"
                    if industry_multiples
                    else "disclosed_hardcoded_fallback"
                )

                self.logger.info(
                    "✅ Fallback multiples applied",
                    extra={
                        "ev_ebitda": ebitda_multiple,
                        "ev_revenue": revenue_multiple,
                        "source": data_source,
                    },
                )

            # Calculate valuation based on financial metrics
            use_revenue_multiple = ebitda <= 0 or ebitda < revenue * Decimal("0.05")
            if use_revenue_multiple and revenue_multiple is None:
                raise MultiplesCalculationError(
                    "Resolved benchmark contract did not provide EV/Revenue for quick valuation.",
                    step="quick_valuation_benchmark_contract",
                    calculation_type="Quick Valuation",
                    context={"code": "BENCHMARK_METRIC_REQUIRED", "metric": "ev_revenue"},
                )
            if not use_revenue_multiple and ebitda_multiple is None:
                raise MultiplesCalculationError(
                    "Resolved benchmark contract did not provide EV/EBITDA for quick valuation.",
                    step="quick_valuation_benchmark_contract",
                    calculation_type="Quick Valuation",
                    context={"code": "BENCHMARK_METRIC_REQUIRED", "metric": "ev_ebitda"},
                )

            if use_revenue_multiple:  # Less than 5% margin
                base_valuation = revenue * revenue_multiple
                self.logger.info(
                    f"💵 Using revenue multiple",
                    extra={
                        "multiple": revenue_multiple,
                        "revenue": revenue,
                        "valuation": base_valuation,
                        "reason": "negative_or_low_ebitda",
                        "source": data_source,
                    },
                )
            else:
                base_valuation = ebitda * ebitda_multiple
                self.logger.info(
                    f"💵 Using EBITDA multiple",
                    extra={
                        "multiple": ebitda_multiple,
                        "ebitda": ebitda,
                        "valuation": base_valuation,
                        "source": data_source,
                    },
                )

            self.logger.info(
                "✅ Quick valuation calculated",
                extra={"base_valuation": base_valuation, "data_source": data_source},
            )

            return base_valuation

        except MultiplesCalculationError:
            raise
        except Exception as e:
            self.logger.error(
                "❌ Error calculating quick valuation",
                extra={
                    "error": str(e),
                    "revenue": revenue,
                    "ebitda": ebitda,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )

            if not allow_untrusted_multiples_fallback:
                raise MultiplesCalculationError(
                    "Quick valuation failed before a resolved benchmark contract "
                    "could be applied. Refusing silent fallback.",
                    step="quick_valuation_calculation",
                    calculation_type="Quick Valuation",
                    context={"code": "BENCHMARK_CONTRACT_REQUIRED"},
                ) from e

            # Explicit fallback to conservative 1.5x revenue
            fallback = revenue * Decimal("1.5")
            self.logger.warning(
                f"⚠️ Using fallback valuation: {fallback}",
                extra={"fallback_multiple": Decimal("1.5"), "fallback_valuation": fallback},
            )
            return fallback

    async def apply_adjustments(
        self, base_valuation: Decimal, business_type: BusinessType, industry: str
    ) -> Decimal:
        """
        Apply business type and industry adjustments

        Args:
            base_valuation: Base valuation amount
            business_type: Business type
            industry: Industry category

        Returns:
            Adjusted valuation amount
        """
        try:
            self.logger.info(
                "🎨 Applying business type adjustments",
                extra={
                    "base_valuation": base_valuation,
                    "business_type": (
                        business_type.value
                        if hasattr(business_type, "value")
                        else str(business_type)
                    ),
                    "industry": industry,
                },
            )

            # Get adjustment factors
            adjustment_factors = self.business_rules.get("business_type_adjustments", {})
            factor = adjustment_factors.get(
                getattr(business_type, "value", str(business_type)), Decimal("1.0")
            )

            self.logger.info(
                f"📊 Business type factor: {factor}",
                extra={
                    "business_type": (
                        business_type.value
                        if hasattr(business_type, "value")
                        else str(business_type)
                    ),
                    "factor": factor,
                },
            )

            # Apply industry-specific adjustments
            industry_adjustments = self.business_rules.get("industry_adjustments", {})
            industry_factor = industry_adjustments.get(industry, Decimal("1.0"))

            self.logger.info(
                f"📊 Industry factor: {industry_factor}",
                extra={"industry": industry, "factor": industry_factor},
            )

            adjusted_valuation = base_valuation * factor * industry_factor

            self.logger.info(
                "✅ Adjustments applied",
                extra={
                    "base_valuation": base_valuation,
                    "business_type_factor": factor,
                    "industry_factor": industry_factor,
                    "adjusted_valuation": adjusted_valuation,
                    "total_adjustment": f"{((adjusted_valuation/base_valuation - 1) * 100):.1f}%",
                },
            )

            return adjusted_valuation

        except Exception as e:
            self.logger.error(
                "❌ Error applying adjustments",
                extra={
                    "error": str(e),
                    "base_valuation": base_valuation,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return base_valuation

    async def calculate_value_range(
        self, base_valuation: Decimal, business_type: BusinessType, industry: str
    ) -> Dict[str, Decimal]:
        """
        Calculate value range

        Args:
            base_valuation: Base valuation amount
            business_type: Business type
            industry: Industry category

        Returns:
            Dictionary with low, high, mid values
        """
        try:
            self.logger.info("📈 Calculating value range", extra={"base_valuation": base_valuation})

            # Determine range factors
            range_factors = self.business_rules.get("value_range_factors", {})
            business_factor = range_factors.get(
                getattr(business_type, "value", str(business_type)), Decimal("0.3")
            )
            industry_factor = range_factors.get(industry, Decimal("0.2"))

            # Use the maximum of the two for conservative range
            range_percentage = max(business_factor, industry_factor)

            self.logger.info(
                "📊 Range factors determined",
                extra={
                    "business_factor": business_factor,
                    "industry_factor": industry_factor,
                    "range_percentage": range_percentage,
                },
            )

            low_value = base_valuation * (1 - range_percentage)
            high_value = base_valuation * (1 + range_percentage)

            result = {"low": low_value, "high": high_value, "mid": base_valuation}

            self.logger.info(
                "✅ Value range calculated",
                extra={
                    "low": low_value,
                    "mid": base_valuation,
                    "high": high_value,
                    "range_percentage": f"{range_percentage*100}%",
                },
            )

            return result

        except Exception as e:
            self.logger.error(
                "❌ Error calculating value range",
                extra={
                    "error": str(e),
                    "base_valuation": base_valuation,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )

            # Fallback to ±30% range
            return {
                "low": base_valuation * Decimal("0.7"),
                "high": base_valuation * Decimal("1.3"),
                "mid": base_valuation,
            }

    async def calculate_confidence_score(
        self, request: QuickValuationRequest, valuation: Decimal, methodology: ValuationMethod
    ) -> Decimal:
        """
        Calculate confidence score

        Args:
            request: Quick valuation request
            valuation: Calculated valuation
            methodology: Valuation methodology used

        Returns:
            Confidence score (Decimal('0.0') to Decimal('1.0'))
        """
        try:
            self.logger.info(
                "🎯 Calculating confidence score",
                extra={
                    "methodology": (
                        methodology.value if hasattr(methodology, "value") else str(methodology)
                    )
                },
            )

            base_confidence = Decimal("0.6")  # Base confidence for quick valuation
            adjustments = []

            # Adjust based on data completeness
            if request.employee_count is not None:
                base_confidence += Decimal("0.1")
                adjustments.append("employee_count: +0.1")
            if request.owner_role is not None:
                base_confidence += Decimal("0.1")
                adjustments.append("owner_role: +0.1")
            if request.owner_hours is not None:
                base_confidence += Decimal("0.1")
                adjustments.append("owner_hours: +0.1")

            self.logger.info(
                f"📊 Data completeness adjustments: {adjustments}",
                extra={"adjustments": adjustments},
            )

            # Adjust based on business type
            business_type_confidence = self.business_rules.get("confidence_factors", {}).get(
                getattr(request, "business_type", "OTHER"), Decimal("0.0")
            )
            if business_type_confidence:
                base_confidence += business_type_confidence
                self.logger.info(f"📊 Business type adjustment: +{business_type_confidence}")

            # Adjust based on industry
            industry_confidence = self.business_rules.get("confidence_factors", {}).get(
                getattr(request.industry, "value", str(request.industry)), Decimal("0.0")
            )
            if industry_confidence:
                base_confidence += industry_confidence
                self.logger.info(f"📊 Industry adjustment: +{industry_confidence}")

            # Clamp to valid range
            final_confidence = min(Decimal("1.0"), max(Decimal("0.0"), base_confidence))

            self.logger.info(
                "✅ Confidence score calculated",
                extra={
                    "base_confidence": Decimal("0.6"),
                    "final_confidence": final_confidence,
                    "percentage": f"{final_confidence*100:.0f}%",
                },
            )

            return final_confidence

        except Exception as e:
            self.logger.error(
                "❌ Error calculating confidence score",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return Decimal("0.6")

    async def generate_key_factors(
        self, request: QuickValuationRequest, valuation: Decimal, methodology: ValuationMethod
    ) -> List[str]:
        """
        Generate key factors affecting valuation

        Args:
            request: Quick valuation request
            valuation: Calculated valuation
            methodology: Valuation methodology used

        Returns:
            List of key factor descriptions
        """
        try:
            self.logger.info("📝 Generating key factors")

            factors = []

            # Revenue-based factors (quantitative)
            if request.revenue > 1000000:
                factors.append(f"Strong revenue base (€{request.revenue:,.0f} annually)")
                self.logger.info(
                    "✅ Factor: Strong revenue base", extra={"revenue": request.revenue}
                )
            elif request.revenue < 100000:
                factors.append(f"Early-stage revenue (€{request.revenue:,.0f} annually)")
                self.logger.info(
                    "⚠️ Factor: Early-stage revenue", extra={"revenue": request.revenue}
                )

            # EBITDA-based factors (quantitative)
            if request.ebitda > 0 and request.revenue > 0:
                margin = request.ebitda / request.revenue
                if margin > Decimal("0.2"):
                    factors.append(f"High profitability ({margin*100:.1f}% EBITDA margin)")
                    self.logger.info(
                        "✅ Factor: High profitability", extra={"margin": f"{margin*100:.1f}%"}
                    )
                elif margin < Decimal("0.05"):
                    factors.append(f"Low profitability ({margin*100:.1f}% EBITDA margin)")
                    self.logger.info(
                        "⚠️ Factor: Low profitability", extra={"margin": f"{margin*100:.1f}%"}
                    )
            elif request.ebitda <= 0:
                factors.append("Negative EBITDA - operating at a loss")
                self.logger.warning("❌ Factor: Negative EBITDA", extra={"ebitda": request.ebitda})

            # REMOVED: Generic "Industry: {industry}" - not a quantitative value driver
            # REMOVED: Generic "Business type: {type}" - not a quantitative value driver
            # Industry and business type are context, not value drivers themselves

            self.logger.info(
                f"✅ Generated {len(factors)} key factors",
                extra={"factor_count": len(factors), "factors": factors},
            )

            return factors

        except Exception as e:
            self.logger.error(
                "❌ Error generating key factors",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return []

    async def generate_recommendations(
        self, request: QuickValuationRequest, valuation: Decimal, confidence_score: Decimal
    ) -> List[str]:
        """
        Generate recommendations

        Args:
            request: Quick valuation request
            valuation: Calculated valuation
            confidence_score: Confidence score

        Returns:
            List of recommendation descriptions
        """
        try:
            self.logger.info(
                "💡 Generating recommendations", extra={"confidence_score": confidence_score}
            )

            recommendations = []

            # Confidence-based recommendations
            if confidence_score < Decimal("0.7"):
                recommendations.append(
                    "Consider providing more detailed financial data for a comprehensive valuation"
                )
                self.logger.info(
                    "💡 Recommendation: Provide more data",
                    extra={"reason": "low_confidence", "confidence": confidence_score},
                )

            # Data completeness recommendations
            if request.employee_count is None:
                recommendations.append("Providing employee count would improve valuation accuracy")
            if hasattr(request, "owner_role") and request.owner_role is None:
                recommendations.append("Owner role information would help assess owner dependency")

            # Profitability recommendations
            if request.ebitda <= 0:
                recommendations.append(
                    "Focus on improving profitability to increase business value"
                )
                self.logger.info(
                    "💡 Recommendation: Improve profitability", extra={"ebitda": request.ebitda}
                )
            elif request.ebitda < request.revenue * Decimal("0.1"):
                recommendations.append(
                    "Improving profit margins could significantly increase valuation"
                )

            self.logger.info(
                f"✅ Generated {len(recommendations)} recommendations",
                extra={"recommendation_count": len(recommendations)},
            )

            return recommendations

        except Exception as e:
            self.logger.error(
                "❌ Error generating recommendations",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return ["Consult with a business valuation expert for detailed analysis"]
