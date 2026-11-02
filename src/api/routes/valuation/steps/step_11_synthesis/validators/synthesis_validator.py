"""
Synthesis Validator for Step 11

Handles value chain validation and result validation.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.config import get_settings
from src.domain.data_quality_assessor import DataQualityAssessor
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepStatus

logger = get_logger(__name__)


class SynthesisValidator:
    """
    Validator for synthesis operations.

    Responsibilities:
    - Validate value chain consistency
    - Validate final multiple ranges
    - Validate total discounts
    - Validate quality checkpoints
    """

    def __init__(self):
        """Initialize synthesis validator."""
        pass

    @staticmethod
    def _category_token(value: object) -> str:
        """Normalize enum/string category labels to a comparable token."""
        raw = getattr(value, "value", value)
        if raw is None:
            return ""
        return str(raw).strip().lower().replace("-", "_").replace(" ", "_")

    def safe_percentage_calculation(
        self, numerator: Decimal, denominator: Decimal, default: Decimal = Decimal("0.0")
    ) -> Decimal:
        """
        Safely calculate percentage with NaN/Infinity validation.

        Args:
            numerator: Numerator for percentage calculation
            denominator: Denominator (must be > 0)
            default: Default value if calculation is invalid

        Returns:
            Percentage value or default
        """
        import math

        if denominator <= 0:
            return default

        try:
            result = (numerator / denominator) * 100
            if not math.isfinite(float(result)):
                logger.warning(
                    "⚠️ Percentage calculation produced invalid result (NaN/Infinity), using default",
                    extra={
                        "step_number": 11,
                        "numerator": numerator,
                        "denominator": denominator,
                        "result": result,
                        "default": default,
                    },
                )
                return default
            return result
        except (ValueError, ZeroDivisionError, OverflowError) as e:
            logger.warning(
                "⚠️ Percentage calculation failed, using default",
                extra={
                    "step_number": 11,
                    "numerator": numerator,
                    "denominator": denominator,
                    "error": str(e),
                    "default": default,
                },
            )
            return default

    def validate_value_chain(
        self, step10_valuation_mid: Decimal, equity_value_mid: Decimal, equity_source: str
    ) -> Dict[str, Any]:
        """
        Validate value chain consistency between Step 10 and Step 7/8.

        Args:
            step10_valuation_mid: Mid-point from Step 10
            equity_value_mid: Equity value from Step 7/8
            equity_source: Source of equity value (e.g., 'Step 8 (ownership-adjusted)')

        Returns:
            Validation result dictionary
        """
        if equity_value_mid is None or equity_value_mid <= 0:
            return {
                "validated": False,
                "reason": "Equity value not available",
                "auto_corrected": False,
            }

        # Use configurable tolerance from settings
        settings = get_settings()
        tolerance_absolute = max(
            Decimal("0.01"), abs(equity_value_mid) * (settings.value_chain_tolerance_percent / 100)
        )
        difference = abs(step10_valuation_mid - equity_value_mid)

        # Safe percentage calculation
        import math

        if equity_value_mid > 0:
            difference_percent = difference / equity_value_mid * 100
            if not math.isfinite(float(difference_percent)):
                difference_percent = 0
        else:
            difference_percent = 0

        if difference > tolerance_absolute:
            return {
                "validated": False,
                "difference": difference,
                "difference_percent": difference_percent,
                "tolerance_absolute": tolerance_absolute,
                "step10_valuation_mid": step10_valuation_mid,
                "equity_value_mid": equity_value_mid,
                "equity_source": equity_source,
                "auto_corrected": True,
                "reason": "Value chain break detected - auto-correcting",
            }
        else:
            return {
                "validated": True,
                "difference": difference,
                "difference_percent": difference_percent,
                "tolerance_absolute": tolerance_absolute,
                "step10_valuation_mid": step10_valuation_mid,
                "equity_value_mid": equity_value_mid,
                "equity_source": equity_source,
                "auto_corrected": False,
                "reason": "Value chain validated successfully",
            }

    def validate_final_multiple_range(
        self,
        final_multiple: Decimal,
        revenue: Decimal,
        industry: str,
        business_category: Optional[str],
    ) -> Dict[str, Any]:
        """
        Validate final multiple falls within McKinsey target ranges for SMEs.

        Target ranges by industry and size (EBITDA multiples):
        - Asset-Light Services (SaaS, Consulting): 2x-10x
        - Manufacturing/Industrial: 2x-7x
        - Retail/Hospitality: 1.5x-6x

        Scaled by revenue tier:
        - Micro (<€500K): Lower end of range
        - Small (€500K-€2M): Mid range
        - Medium (€2M-€5M): Upper-mid range
        - Large (€5M-€10M): Upper range

        Args:
            final_multiple: Final EBITDA or Revenue multiple after all adjustments
            revenue: Company revenue
            industry: Industry identifier
            business_category: Business type category string

        Returns:
            Dict with validation results and warnings if outside range
        """
        from src.config.decimal_constants import DecimalConstants

        category_token = self._category_token(business_category)
        industry_token = self._category_token(industry)
        category_signals = {category_token, industry_token}

        # Determine industry-specific range
        if category_signals & {"saas_software", "technology", "saas", "software", "b2b_saas"}:
            min_multiple = to_decimal(DecimalConstants.TARGET_MULTIPLE_TECH_MIN)
            max_multiple = to_decimal(DecimalConstants.TARGET_MULTIPLE_TECH_MAX)
            industry_type = "Tech/SaaS (asset-light)"
        elif category_signals & {"manufacturing", "industrial", "construction"}:
            min_multiple = to_decimal(DecimalConstants.TARGET_MULTIPLE_MANUFACTURING_MIN)
            max_multiple = to_decimal(DecimalConstants.TARGET_MULTIPLE_MANUFACTURING_MAX)
            industry_type = "Manufacturing/Industrial"
        elif category_signals & {"retail", "retail_food", "hospitality", "food_services"}:
            min_multiple = to_decimal(DecimalConstants.TARGET_MULTIPLE_RETAIL_MIN)
            max_multiple = to_decimal(DecimalConstants.TARGET_MULTIPLE_RETAIL_MAX)
            industry_type = "Retail/Hospitality"
        elif category_signals & {
            "professional_services",
            "professional",
            "business_services",
            "consulting",
            "agency",
            "creative_media",
            "media_entertainment",
            "events_entertainment",
            "entertainment",
            "advertising",
            "marketing",
            "design",
        }:
            min_multiple = Decimal("2.5")
            max_multiple = Decimal("8.0")
            industry_type = "Professional Services"
        else:
            min_multiple = to_decimal(DecimalConstants.TARGET_MULTIPLE_SME_MIN)
            max_multiple = to_decimal(DecimalConstants.TARGET_MULTIPLE_SME_MAX)
            industry_type = "General SME"

        # Adjust range by revenue tier
        if revenue < 500_000:
            # Micro: Lower 40% of range
            effective_max = min_multiple + (max_multiple - min_multiple) * Decimal("0.4")
            tier = "Micro (<€500K)"
        elif revenue < 2_000_000:
            # Small: Lower 60% of range
            effective_max = min_multiple + (max_multiple - min_multiple) * Decimal("0.6")
            tier = "Small (€500K-€2M)"
        elif revenue < 5_000_000:
            # Medium: Lower 80% of range
            effective_max = min_multiple + (max_multiple - min_multiple) * Decimal("0.8")
            tier = "Medium (€2M-€5M)"
        else:
            # Large: Full range
            effective_max = max_multiple
            tier = "Large (€5M+)"

        # Validate
        is_valid = min_multiple <= final_multiple <= effective_max

        validation_result = {
            "is_valid": is_valid,
            "final_multiple": final_multiple,
            "expected_range": {"min": min_multiple, "max": effective_max, "full_max": max_multiple},
            "industry_type": industry_type,
            "revenue_tier": tier,
            "revenue": revenue,
        }

        if not is_valid:
            if final_multiple < min_multiple:
                validation_result["warning"] = (
                    f"Final multiple ({final_multiple:.2f}x) below expected minimum "
                    f"({min_multiple:.2f}x) for {industry_type} - {tier}. "
                    f"May indicate overly aggressive discounting. "
                    f"Review: (1) SME calibration factor, (2) Liquidity discount adjustment, (3) Risk factor stacking."
                )
            else:
                validation_result["warning"] = (
                    f"Final multiple ({final_multiple:.2f}x) above expected maximum "
                    f"({effective_max:.2f}x) for {industry_type} - {tier}. "
                    f"May indicate insufficient risk adjustment or calibration issue."
                )

            logger.warning(
                "⚠️ Final multiple outside McKinsey target range",
                extra={"step_number": 11, **validation_result},
            )
        else:
            # DEBUG: success path; failures still log at WARN.
            logger.debug(
                "✅ Final multiple within McKinsey target range",
                extra={"step_number": 11, **validation_result},
            )

        return validation_result

    def validate_total_discount(
        self,
        initial_multiple: Decimal,
        final_multiple: Decimal,
        revenue: Decimal,
        is_sole_trader: bool = False,
    ) -> Dict[str, Any]:
        """
        Validate total discount from initial to final multiple falls within
        McKinsey/Bain ranges, adjusted for SME-calibrated starting multiples.

        When the initial multiple is already SME-calibrated (< 6x), Steps 5 & 6
        apply 50% reduced discounts (Ibbotson/Duff & Phelps: SME transaction
        multiples already capture ~50% of size and liquidity risk). This lowers
        the expected total discount from the pipeline.

        Args:
            initial_multiple: Initial multiple before any adjustments (Step 3)
            final_multiple: Final multiple after all adjustments (Step 6/11)
            revenue: Company revenue
            is_sole_trader: Whether company is a sole trader

        Returns:
            Dict with validation results and warnings if outside expected range
        """
        total_discount_pct = self.safe_percentage_calculation(
            (initial_multiple - final_multiple), initial_multiple, Decimal("0.0")
        )

        # SME-calibrated multiples (< 6x) have Steps 5 & 6 reduced by 50%,
        # producing lower total discounts than raw Damodaran-based pipelines.
        sme_calibrated = initial_multiple < Decimal("6.0")

        if revenue < 500_000:
            if is_sole_trader:
                expected_min = Decimal("30.0") if sme_calibrated else Decimal("45.0")
                expected_max = Decimal("55.0")
                tier = "Micro (<€500K) Sole Trader"
            else:
                expected_min = Decimal("0.0") if sme_calibrated else Decimal("40.0")
                expected_max = Decimal("50.0")
                tier = "Micro (<€500K) Multi-owner"
        elif revenue < 2_000_000:
            if is_sole_trader:
                expected_min = Decimal("25.0") if sme_calibrated else Decimal("40.0")
                expected_max = Decimal("50.0")
                tier = "Small (€500K-€2M) Sole Trader"
            else:
                expected_min = Decimal("0.0") if sme_calibrated else Decimal("35.0")
                expected_max = Decimal("45.0")
                tier = "Small (€500K-€2M) Multi-owner"
        elif revenue < 5_000_000:
            if is_sole_trader:
                expected_min = Decimal("20.0") if sme_calibrated else Decimal("30.0")
                expected_max = Decimal("40.0")
                tier = "Medium (€2M-€5M) Sole Trader"
            else:
                expected_min = Decimal("0.0") if sme_calibrated else Decimal("25.0")
                expected_max = Decimal("35.0")
                tier = "Medium (€2M-€5M) Multi-owner"
        else:
            expected_min = Decimal("10.0")
            expected_max = Decimal("25.0")
            tier = "Mid-market (€5M+)"

        is_valid = expected_min <= total_discount_pct <= expected_max

        validation_result = {
            "is_valid": is_valid,
            "total_discount_pct": round(total_discount_pct, 1),
            "initial_multiple": initial_multiple,
            "final_multiple": final_multiple,
            "expected_range": {"min": expected_min, "max": expected_max},
            "revenue_tier": tier,
            "revenue": revenue,
            "is_sole_trader": is_sole_trader,
            "sme_calibrated": sme_calibrated,
            "post_step3_floor_removed": sme_calibrated and not is_sole_trader,
        }

        if not is_valid:
            if total_discount_pct < expected_min:
                validation_result["warning"] = (
                    f"Total discount ({total_discount_pct:.1f}%) below expected minimum "
                    f"({expected_min:.1f}%) for {tier}. "
                    f"Discounts may be too conservative. Review Steps 4-6."
                )
            else:
                validation_result["warning"] = (
                    f"Total discount ({total_discount_pct:.1f}%) above expected maximum "
                    f"({expected_max:.1f}%) for {tier}. "
                    f"Possible double-counting. Review discount stacking in Steps 2-6."
                )

            logger.warning(
                "⚠️ Total discount outside expected range",
                extra={"step_number": 11, **validation_result},
            )
        else:
            logger.debug(
                "✅ Total discount within expected range",
                extra={"step_number": 11, **validation_result},
            )

        return validation_result

    def validate_quality_checkpoint(
        self, request: Any, previous_results: Dict[int, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Final data quality validation before output.

        This is the final checkpoint to ensure data quality remains consistent
        throughout the entire valuation flow before delivering results to the user.

        Returns:
            Dict with final quality_checkpoint results or None if Step 0 not available
        """
        # Get Step 0 baseline
        step0_result = previous_results.get(0)
        if not step0_result or step0_result.status != StepStatus.COMPLETED:
            return None

        baseline_score = step0_result.result.get("quality_score")
        if baseline_score is None:
            return None

        # Re-assess quality at final checkpoint
        quality_assessor = DataQualityAssessor()
        checkpoint_assessment = quality_assessor.assess_quality(
            request, baseline_score=baseline_score
        )

        current_score = checkpoint_assessment["quality_score"]
        degradation = checkpoint_assessment.get("degradation", 0)

        # Log if significant degradation detected
        if degradation and degradation > 5:
            logger.warning(
                f"⚠️ Data quality degraded by {degradation} points at final checkpoint (Step 11)",
                extra={
                    "baseline_score": baseline_score,
                    "current_score": current_score,
                    "degradation": degradation,
                },
            )

        return {
            "baseline_score": baseline_score,
            "current_score": current_score,
            "degradation": degradation,
            "status": "degraded" if degradation and degradation > 5 else "stable",
            "warnings_count": len(checkpoint_assessment.get("warnings", [])),
            "final_validation": True,
        }
