"""
Key Output Extraction Coordinator

Orchestrates key output extraction from step results for transparency reporting.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any, Dict, Mapping, Union

from src.errors import ValidationError
from src.utils.logging import get_logger

from ....base_step import StepStatus
from .types import (
    KeyOutputsUnion,
    Step0KeyOutputs,
    Step1KeyOutputs,
    Step2KeyOutputs,
    Step3KeyOutputs,
    Step4KeyOutputs,
    Step5KeyOutputs,
    Step6KeyOutputs,
    Step7KeyOutputs,
    Step8KeyOutputs,
    Step9KeyOutputs,
    Step10KeyOutputs,
    Step11KeyOutputs,
    StepOutput,
)
from .validation import BankGradeValidator

logger = get_logger(__name__)


class KeyOutputExtractionCoordinator:
    """
    Coordinates key output extraction from step results.
    """

    def __init__(self) -> None:
        self.logger = logger

    @staticmethod
    def _first_present(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        """Return first present non-None value while preserving explicit zeroes."""
        for key in keys:
            if key in mapping and mapping[key] is not None:
                return mapping[key]
        return default

    def extract_key_outputs(self, result: StepOutput) -> KeyOutputsUnion:
        """
        Extract key outputs from a step result.

        ENHANCED: Include comprehensive step data for frontend display.
        Priority: Include ALL relevant calculation outputs for transparency.

        BANK-GRADE: Includes input validation and audit trail logging.

        Args:
            result: Step result object

        Returns:
            Dictionary of key outputs for the step
        """
        # Bank-grade input validation
        if result is None:
            self.logger.error(
                "❌ CRITICAL: extract_key_outputs called with None result",
                extra={"step_number": "unknown"},
            )
            raise ValidationError("result cannot be None")

        # Validate step result structure
        try:
            BankGradeValidator.validate_step_result(result, result.step_number)
        except ValidationError as e:
            self.logger.error(
                f"❌ CRITICAL: Invalid step result structure: {e}",
                extra={"step_number": getattr(result, "step_number", "unknown")},
            )
            raise

        if result.status != StepStatus.COMPLETED:
            self.logger.debug(
                f"Step {result.step_number} not completed, returning empty outputs",
                extra={
                    "step_number": result.step_number,
                    "status": result.status.value,
                },
            )
            return {}

        # Extract relevant fields based on step - COMPREHENSIVE OUTPUT
        step_num = result.step_number

        # Log calculation provenance (bank-grade audit trail)
        self.logger.debug(
            f"📊 Extracting key outputs for Step {step_num}",
            extra={
                "step_number": step_num,
                "step_name": result.step_name,
                "status": result.status.value,
                "result_keys_count": len(result.result) if result.result else 0,
            },
        )

        extractor = self._extractor_for_step(step_num)
        if extractor is not None:
            return extractor(result)

        # Fallback: return entire result dict for any other step
        return result.result

    def _extractor_for_step(self, step_num: int) -> Callable[[StepOutput], KeyOutputsUnion] | None:
        return {
            0: self._extract_step_0_outputs,
            1: self._extract_step_1_outputs,
            2: self._extract_step_2_outputs,
            3: self._extract_step_3_outputs,
            4: self._extract_step_4_outputs,
            5: self._extract_step_5_outputs,
            6: self._extract_step_6_outputs,
            7: self._extract_step_7_outputs,
            8: self._extract_step_8_outputs,
            9: self._extract_step_9_outputs,
            10: self._extract_step_10_outputs,
            11: self._extract_step_11_outputs,
        }.get(step_num)

    def _extract_step_0_outputs(self, result: StepOutput) -> Step0KeyOutputs:
        """Extract Step 0 (Data Quality Assessment) outputs."""
        quality_score = result.result.get("quality_score")
        quality_level = result.result.get("quality_level") or result.metadata.get("quality_level")

        if quality_score is None or quality_score == 0:
            self.logger.warning(
                "⚠️ Step 0 quality_score is None or 0",
                extra={
                    "step_number": 0,
                    "quality_score": quality_score,
                    "result_keys": list(result.result.keys()) if result.result else [],
                    "metadata_keys": list(result.metadata.keys()) if result.metadata else [],
                },
            )

        return {
            "quality_score": quality_score if quality_score is not None else 0,
            "dimension_scores": result.result.get("dimension_scores", {}),
            "dcf_eligible": result.result.get("dcf_eligible", False),
            "dcf_exclusion_reason": result.result.get("dcf_exclusion_reason"),
            "multiples_method": result.result.get("multiples_method", "primary"),
            "warnings": result.result.get("warnings", []),
            "recommendations": result.result.get("recommendations", []),
            "quality_level": quality_level or "UNKNOWN",
        }

    def _extract_step_1_outputs(self, result: StepOutput) -> Step1KeyOutputs:
        """Extract Step 1 (Input Validation) outputs."""
        return {
            "revenue": result.result.get("revenue"),
            "ebitda": result.result.get("ebitda"),
            "ebitda_margin": result.result.get("ebitda_margin"),
            "weighted_revenue": result.result.get("weighted_revenue"),
            "weighted_ebitda": result.result.get("weighted_ebitda"),
            "using_weighted_metrics": result.result.get("using_weighted_metrics"),
            "company_name": result.result.get("company_name"),
            "industry": result.result.get("industry"),
            "country": result.result.get("country"),
        }

    def _extract_step_2_outputs(self, result: StepOutput) -> Step2KeyOutputs:
        """Extract Step 2 (Industry Benchmarking) outputs."""
        return {
            "primary_method": result.result.get("primary_method"),
            "primary_method_reason": result.result.get("primary_method_reason"),
            "ev_ebitda_multiple": result.result.get("ev_ebitda_multiple"),
            "ev_revenue_multiple": result.result.get("ev_revenue_multiple"),
            "multiples_p25": result.result.get("multiples_p25"),
            "multiples_p50": result.result.get("multiples_p50"),
            "multiples_p75": result.result.get("multiples_p75"),
            "p25_ebitda_multiple": result.result.get("p25_ebitda_multiple"),
            "p50_ebitda_multiple": result.result.get("p50_ebitda_multiple"),
            "p75_ebitda_multiple": result.result.get("p75_ebitda_multiple"),
            "p25_revenue_multiple": result.result.get("p25_revenue_multiple"),
            "p50_revenue_multiple": result.result.get("p50_revenue_multiple"),
            "p75_revenue_multiple": result.result.get("p75_revenue_multiple"),
            "comparables_count": result.result.get("comparables_count"),
            "comparables_quality": result.result.get("comparables_quality"),
            "data_source": result.result.get("data_source"),
            "dcf_eligible": result.result.get("dcf_eligible"),
            "recommended_methodology": result.result.get("recommended_methodology"),
            "dcf_suitability_score": result.result.get("dcf_suitability_score"),
            "business_category": result.result.get("business_category"),
        }

    def _extract_step_3_outputs(self, result: StepOutput) -> Step3KeyOutputs:
        """Extract Step 3 (Base Enterprise Value) outputs."""
        result_map = result.result
        return {
            "enterprise_value_low": result_map.get("enterprise_value_low"),
            "enterprise_value_mid": result_map.get("enterprise_value_mid"),
            "enterprise_value_high": result_map.get("enterprise_value_high"),
            "metric_used": self._first_present(result_map, "metric_used", "primary_metric"),
            "metric_value": self._first_present(result_map, "metric_value", "primary_metric_value"),
            "multiple_low": self._first_present(result_map, "multiple_low", "multiple_p25"),
            "multiple_mid": self._first_present(
                result_map, "multiple_mid", "multiple_p50", "primary_multiple"
            ),
            "multiple_high": self._first_present(result_map, "multiple_high", "multiple_p75"),
            "multiple_p25": self._first_present(result_map, "multiple_p25", "multiple_low"),
            "multiple_p50": self._first_present(
                result_map, "multiple_p50", "multiple_mid", "primary_multiple"
            ),
            "multiple_p75": self._first_present(result_map, "multiple_p75", "multiple_high"),
            "percentile_source": result_map.get("percentile_source"),
            "primary_method": result_map.get("primary_method"),
            "auto_corrected": result_map.get("auto_corrected", False),
        }

    def _extract_step_4_outputs(self, result: StepOutput) -> Step4KeyOutputs:
        """Extract Step 4 (Owner Concentration) outputs."""
        # Bank-grade: Ensure Decimal types
        adjustment_pct = result.result.get("adjustment_percentage")
        if adjustment_pct is None:
            owner_adj_decimal = result.result.get("owner_concentration_adjustment")
            if owner_adj_decimal is not None:
                # Bank-grade: Ensure Decimal conversion
                owner_adj_decimal = BankGradeValidator.ensure_decimal(
                    owner_adj_decimal, "owner_concentration_adjustment", Decimal("0.0")
                )
                adjustment_pct = owner_adj_decimal * Decimal("100.0")

        # Bank-grade: Validate Decimal types for enterprise values
        ev_low = BankGradeValidator.ensure_decimal(
            result.result.get("enterprise_value_low"), "enterprise_value_low", Decimal("0.0")
        )
        ev_mid = BankGradeValidator.ensure_decimal(
            result.result.get("enterprise_value_mid"), "enterprise_value_mid", Decimal("0.0")
        )
        ev_high = BankGradeValidator.ensure_decimal(
            result.result.get("enterprise_value_high"), "enterprise_value_high", Decimal("0.0")
        )

        # Bank-grade: Validate range ordering
        try:
            BankGradeValidator.validate_range(ev_low, ev_mid, ev_high, "enterprise_value")
        except ValidationError as e:
            self.logger.warning(
                f"⚠️ Step 4 range validation warning: {e}",
                extra={
                    "step_number": 4,
                    "ev_low": str(ev_low),
                    "ev_mid": str(ev_mid),
                    "ev_high": str(ev_high),
                },
            )

        outputs = {
            "enterprise_value_low": ev_low,
            "enterprise_value_mid": ev_mid,
            "enterprise_value_high": ev_high,
            "owner_employee_ratio": BankGradeValidator.ensure_decimal(
                result.result.get("owner_employee_ratio"), "owner_employee_ratio", None
            ),
            "risk_level": result.result.get("risk_level"),
            "adjustment_percentage": (
                BankGradeValidator.ensure_decimal(adjustment_pct, "adjustment_percentage", None)
                if adjustment_pct is not None
                else None
            ),
            "number_of_owners": result.result.get("number_of_owners"),
            "number_of_employees": result.result.get("number_of_employees"),
            "calibration_type": result.result.get("calibration_type"),
            "business_type_id": result.result.get("business_type_id"),
            "ev_low_before": BankGradeValidator.ensure_decimal(
                self._first_present(result.result, "ev_low_before", "unadjusted_ev_low"),
                "ev_low_before",
                None,
            ),
            "ev_mid_before": BankGradeValidator.ensure_decimal(
                self._first_present(result.result, "ev_mid_before", "unadjusted_ev"),
                "ev_mid_before",
                None,
            ),
            "ev_high_before": BankGradeValidator.ensure_decimal(
                self._first_present(result.result, "ev_high_before", "unadjusted_ev_high"),
                "ev_high_before",
                None,
            ),
        }

        # Bank-grade: Log calculation provenance
        BankGradeValidator.log_calculation_provenance(
            "Step 4 Key Output Extraction",
            {"step_result_keys": list(result.result.keys())},
            {"extracted_keys": list(outputs.keys())},
            4,
        )

        return outputs

    def _extract_step_5_outputs(self, result: StepOutput) -> Step5KeyOutputs:
        """Extract Step 5 (Size Discount) outputs."""
        return {
            "enterprise_value_low": result.result.get("enterprise_value_low"),
            "enterprise_value_mid": result.result.get("enterprise_value_mid"),
            "enterprise_value_high": result.result.get("enterprise_value_high"),
            "revenue_tier": result.result.get("revenue_tier"),
            "base_discount": result.result.get("base_discount"),
            "adjustment_multiplier": self._first_present(
                result.result, "business_type_multiplier", "adjustment_multiplier"
            ),
            "size_discount_percentage": result.result.get("size_discount_percentage"),
            "business_category": result.result.get("business_category"),
            "ev_low_before": result.result.get("ev_low_before"),
            "ev_mid_before": result.result.get("ev_mid_before"),
            "ev_high_before": result.result.get("ev_high_before"),
        }

    def _extract_step_6_outputs(self, result: StepOutput) -> Step6KeyOutputs:
        """Extract Step 6 (Liquidity Discount) outputs."""
        return {
            "enterprise_value_low": result.result.get("enterprise_value_low"),
            "enterprise_value_mid": result.result.get("enterprise_value_mid"),
            "enterprise_value_high": result.result.get("enterprise_value_high"),
            "base_discount": result.result.get("base_discount"),
            "margin_bonus": result.result.get("margin_bonus"),
            "growth_bonus": result.result.get("growth_bonus"),
            "recurring_revenue_bonus": result.result.get("recurring_revenue_bonus"),
            "size_bonus": result.result.get("size_bonus"),
            "total_discount_percentage": result.result.get("total_discount_percentage"),
            "business_category": result.result.get("business_category"),
            "base_step": result.result.get("base_step"),
            "ev_low_before": result.result.get("ev_low_before"),
            "ev_mid_before": result.result.get("ev_mid_before"),
            "ev_high_before": result.result.get("ev_high_before"),
        }

    def _extract_step_7_outputs(self, result: StepOutput) -> Step7KeyOutputs:
        """Extract Step 7 (EV to Equity Conversion) outputs."""
        return {
            "equity_value_low": result.result.get("equity_value_low"),
            "equity_value_mid": result.result.get("equity_value_mid"),
            "equity_value_high": result.result.get("equity_value_high"),
            "total_debt": result.result.get("total_debt"),
            "cash": result.result.get("cash"),
            "operating_cash": result.result.get("operating_cash"),
            "excess_cash": result.result.get("excess_cash"),
            "net_debt": result.result.get("net_debt"),
            "balance_sheet_available": result.result.get("balance_sheet_available"),
            "ev_source_step": result.result.get("ev_source_step"),
            "exemption_applied": result.result.get("exemption_applied"),
            "range_validated": result.result.get("range_validated"),
            "ev_low": result.result.get("ev_low"),
            "ev_mid": result.result.get("ev_mid"),
            "ev_high": result.result.get("ev_high"),
        }

    def _extract_step_8_outputs(self, result: StepOutput) -> Step8KeyOutputs:
        """Extract Step 8 (Ownership Adjustment) outputs."""
        return {
            "equity_value_low": result.result.get("equity_value_low"),
            "equity_value_mid": result.result.get("equity_value_mid"),
            "equity_value_high": result.result.get("equity_value_high"),
            "ownership_percentage": result.result.get("ownership_percentage"),
            "adjustment_type": result.result.get("adjustment_type"),
            "adjustment_percentage": result.result.get("adjustment_percentage"),
            "equity_low_before": result.result.get("equity_low_before"),
            "equity_mid_before": result.result.get("equity_mid_before"),
            "equity_high_before": result.result.get("equity_high_before"),
        }

    def _extract_step_9_outputs(self, result: StepOutput) -> Step9KeyOutputs:
        """Extract Step 9 (Confidence Score) outputs."""
        return {
            "overall_confidence_score": result.result.get("overall_confidence_score"),
            "confidence_level": result.result.get("confidence_level"),
            "factor_scores": result.result.get("factor_scores", {}),
        }

    def _extract_step_10_outputs(self, result: StepOutput) -> Step10KeyOutputs:
        """Extract Step 10 (Range Methodology) outputs."""
        return {
            "valuation_low": result.result.get("valuation_low"),
            "valuation_mid": result.result.get("valuation_mid"),
            "valuation_high": result.result.get("valuation_high"),
            "methodology": result.result.get("methodology"),
            "confidence_level": result.result.get("confidence_level"),
            "base_spread": result.result.get("base_spread"),
            "business_type_multiplier": result.result.get("business_type_multiplier"),
            "size_adjustment": result.result.get("size_adjustment"),
            "growth_adjustment": result.result.get("growth_adjustment"),
            "profitability_adjustment": result.result.get("profitability_adjustment"),
            "data_quality_adjustment": result.result.get("data_quality_adjustment"),
            "total_spread": result.result.get("total_spread"),
            "asymmetric_adjustment": result.result.get("asymmetric_adjustment"),
            "downside_factor": result.result.get("downside_factor"),
            "upside_factor": result.result.get("upside_factor"),
            "step7_equity_value_mid": result.result.get("step7_equity_value_mid"),
            "value_preservation_validated": result.result.get("value_preservation_validated"),
        }

    def _extract_step_11_outputs(self, result: StepOutput) -> Step11KeyOutputs:
        """Extract Step 11 (Final Valuation) outputs."""
        return {
            "valuation_low": result.result.get("valuation_low"),
            "valuation_mid": result.result.get("valuation_mid"),
            "valuation_high": result.result.get("valuation_high"),
            "confidence_score": result.result.get("confidence_score"),
            "methodology_statement": result.result.get("methodology_statement"),
            "professional_review_ready": result.result.get("professional_review_ready"),
            "value_chain_validated": result.result.get("value_chain_validated"),
            # Surface the SDE cross-check/blend so the report can reconcile the
            # EBITDA-leg + SDE-leg -> blended headline (otherwise the report sees
            # only the post-blend number with no visible bridge). Additive: does
            # not change any valuation figure.
            "sde_cross_check": result.result.get("sde_cross_check"),
        }
