"""
Adjustment Extraction Coordinator

Orchestrates adjustment extraction from step results for transparency reporting.
"""

from decimal import Decimal
from typing import List, NamedTuple, Optional

from src.api.routes.valuation.steps.strength_factor_discount_adjustments import (
    strength_factor_discount_lineage_payload,
)
from src.errors import ValidationError
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

from ....base_step import StepStatus
from .types import Adjustment, PreviousResults
from .validation import BankGradeValidator

logger = get_logger(__name__)


class _AdjustmentValidationSpec(NamedTuple):
    step_number: int
    adjustment_type: str
    result_keys: tuple[str, ...]
    value_label: str


_ADJUSTMENT_VALIDATION_SPECS = (
    _AdjustmentValidationSpec(
        step_number=4,
        adjustment_type="owner_concentration",
        result_keys=("owner_concentration_adjustment", "adjustment_percentage"),
        value_label="adjustment",
    ),
    _AdjustmentValidationSpec(
        step_number=5,
        adjustment_type="size_discount",
        result_keys=("size_discount_percentage",),
        value_label="discount",
    ),
    _AdjustmentValidationSpec(
        step_number=6,
        adjustment_type="liquidity_discount",
        result_keys=("total_discount_percentage",),
        value_label="discount",
    ),
)


class AdjustmentExtractionCoordinator:
    """
    Coordinates adjustment extraction from step results.
    """

    def __init__(self) -> None:
        self.logger = logger

    def extract_adjustments(self, previous_results: PreviousResults) -> List[Adjustment]:
        """
        Extract adjustments applied with detailed information.

        BANK-GRADE: Includes input validation and comprehensive audit trail.

        Args:
            previous_results: Results from previous steps

        Returns:
            List of adjustment dictionaries

        Raises:
            ValidationError: If previous_results structure is invalid
        """
        # Bank-grade input validation
        try:
            BankGradeValidator.validate_previous_results(previous_results)
        except ValidationError as e:
            self.logger.error(
                f"❌ CRITICAL: Invalid previous_results structure: {e}",
                extra={"step_number": 11},
            )
            raise

        self.logger.debug(
            "🔍 Starting adjustment extraction (bank-grade audit trail)",
            extra={
                "step_number": 11,
                "previous_results_count": len(previous_results),
                "available_steps": sorted(previous_results.keys()),
            },
        )

        adjustments = []

        # Extract adjustments from each step
        self._extract_step_4_adjustment(previous_results, adjustments)
        self._extract_step_5_adjustment(previous_results, adjustments)
        self._extract_step_6_adjustment(previous_results, adjustments)
        self._extract_step_8_adjustment(previous_results, adjustments)

        # Validate extraction
        validation_warnings = self._validate_extraction(previous_results, adjustments)

        if validation_warnings:
            self.logger.error(
                "❌ CRITICAL: Discount extraction validation failed",
                extra={
                    "step_number": 11,
                    "validation_warnings": validation_warnings,
                    "total_warnings": len(validation_warnings),
                },
            )

        self.logger.debug(
            "🔍 DIAGNOSTIC Step 11: Adjustment extraction complete",
            extra={
                "step_number": 11,
                "total_adjustments_extracted": len(adjustments),
                "adjustment_types": [adj["type"] for adj in adjustments],
                "adjustment_percentages": {
                    adj["type"]: adj["adjustment_pct"] for adj in adjustments
                },
                "has_owner_concentration": any(
                    adj["type"] == "owner_concentration" for adj in adjustments
                ),
                "has_size_discount": any(adj["type"] == "size_discount" for adj in adjustments),
                "has_liquidity_discount": any(
                    adj["type"] == "liquidity_discount" for adj in adjustments
                ),
                "validation_warnings": validation_warnings,
            },
        )

        return adjustments

    def _extract_step_4_adjustment(
        self, previous_results: PreviousResults, adjustments: List[Adjustment]
    ) -> None:
        """Extract Step 4 (Owner Concentration) adjustment."""
        step4 = previous_results.get(4)
        if step4 and step4.status == StepStatus.COMPLETED:
            owner_adj = None
            for key in ("owner_concentration_adjustment", "adjustment_percentage"):
                value = step4.result.get(key)
                if value is not None:
                    owner_adj = value
                    break

            if owner_adj is not None:
                # Bank-grade: Ensure Decimal type
                owner_adj_decimal = BankGradeValidator.ensure_decimal(
                    owner_adj, "owner_concentration_adjustment", Decimal("0.0")
                )

                # Bank-grade: Validate percentage range
                try:
                    BankGradeValidator.validate_percentage(
                        owner_adj_decimal,
                        "owner_concentration_adjustment",
                        allow_negative=True,
                        min_value=Decimal("-1.0"),  # -100%
                        max_value=Decimal("0.0"),  # 0% (discounts are negative)
                    )
                except ValidationError as e:
                    self.logger.warning(
                        f"⚠️ Step 4 adjustment validation warning: {e}",
                        extra={"step_number": 4, "adjustment": str(owner_adj_decimal)},
                    )

                adjustments.append(
                    {
                        "step": step4.step_name,
                        "step_number": 4,
                        "adjustment": owner_adj_decimal,
                        "adjustment_pct": owner_adj_decimal * Decimal("100.0"),
                        "type": "owner_concentration",
                        "rationale": "Key person risk adjustment",
                    }
                )

                # Bank-grade: Log calculation provenance
                BankGradeValidator.log_calculation_provenance(
                    "Step 4 Adjustment Extraction",
                    {"owner_concentration_adjustment": str(owner_adj_decimal)},
                    {"adjustment_pct": str(owner_adj_decimal * Decimal("100.0"))},
                    4,
                )
            else:
                self.logger.warning(
                    "⚠️ Step 11: Step 4 completed but no adjustment found",
                    extra={
                        "step_number": 11,
                        "step_4_result": step4.result,
                        "step_4_metadata": step4.metadata if hasattr(step4, "metadata") else None,
                    },
                )

    def _extract_step_5_adjustment(
        self, previous_results: PreviousResults, adjustments: List[Adjustment]
    ) -> None:
        """Extract Step 5 (Size Discount) adjustment."""
        step5 = previous_results.get(5)
        if step5 and step5.status == StepStatus.COMPLETED:
            size_discount = None
            for key in (
                "size_discount_percentage",
                "size_discount",
                "adjustment_percentage",
            ):
                value = step5.result.get(key)
                if value is not None:
                    size_discount = value
                    break

            if size_discount is not None:
                size_discount_decimal = to_decimal(size_discount)
                adjustment = {
                    "step": step5.step_name,
                    "step_number": 5,
                    "adjustment": size_discount_decimal,
                    "adjustment_pct": size_discount_decimal * Decimal("100"),
                    "type": "size_discount",
                    "tier": step5.result.get("size_tier", ""),
                    "rationale": f"Size premium discount for {step5.result.get('size_tier', 'company size')}",
                }
                adjustment.update(strength_factor_discount_lineage_payload(step5.result))
                adjustments.append(adjustment)
            else:
                self.logger.warning(
                    "⚠️ Step 11: Step 5 completed but no discount found",
                    extra={
                        "step_number": 11,
                        "step_5_result": step5.result,
                        "step_5_metadata": step5.metadata if hasattr(step5, "metadata") else None,
                    },
                )

    def _extract_step_6_adjustment(
        self, previous_results: PreviousResults, adjustments: List[Adjustment]
    ) -> None:
        """Extract Step 6 (Liquidity Discount) adjustment."""
        step6 = previous_results.get(6)
        if step6 and step6.status == StepStatus.COMPLETED:
            liquidity_discount = None
            for key in (
                "total_discount_percentage",
                "liquidity_discount_percentage",
                "adjustment_percentage",
            ):
                value = step6.result.get(key)
                if value is not None:
                    liquidity_discount = value
                    break

            liquidity_discount_decimal = (
                to_decimal(liquidity_discount) if liquidity_discount is not None else None
            )

            self.logger.debug(
                "🔍 DIAGNOSTIC Step 11: Extracting Step 6 (Liquidity Discount)",
                extra={
                    "step_number": 11,
                    "step_6_result_keys": (
                        list(step6.result.keys()) if isinstance(step6.result, dict) else []
                    ),
                    "liquidity_discount_percentage": step6.result.get(
                        "liquidity_discount_percentage"
                    ),
                    "total_discount_percentage": step6.result.get("total_discount_percentage"),
                    "adjustment_percentage": step6.result.get("adjustment_percentage"),
                    "extracted_liquidity_discount": liquidity_discount_decimal,
                    "liquidity_discount_pct": (
                        liquidity_discount_decimal * Decimal("100")
                        if liquidity_discount_decimal is not None
                        else None
                    ),
                },
            )

            if liquidity_discount_decimal is not None:
                adjustment = {
                    "step": step6.step_name,
                    "step_number": 6,
                    "adjustment": liquidity_discount_decimal,
                    "adjustment_pct": liquidity_discount_decimal * Decimal("100"),
                    "type": "liquidity_discount",
                    "rationale": "Private company illiquidity discount",
                }
                adjustment.update(strength_factor_discount_lineage_payload(step6.result))
                adjustments.append(adjustment)
            else:
                self.logger.warning(
                    "⚠️ Step 11: Step 6 completed but no discount found",
                    extra={
                        "step_number": 11,
                        "step_6_result": step6.result,
                        "step_6_metadata": step6.metadata if hasattr(step6, "metadata") else None,
                    },
                )

    def _extract_step_8_adjustment(
        self, previous_results: PreviousResults, adjustments: List[Adjustment]
    ) -> None:
        """Extract Step 8 (Ownership Adjustment) adjustment."""
        step8 = previous_results.get(8)
        if step8 and step8.status == StepStatus.COMPLETED:
            ownership_pct = step8.result.get("ownership_percentage", 100)
            adjustment_type = step8.result.get("adjustment_type")
            adjustment_pct = step8.result.get("adjustment_percentage", 0)
            if adjustment_pct != 0:
                adjustments.append(
                    {
                        "step": step8.step_name,
                        "step_number": 8,
                        "adjustment": adjustment_pct
                        / Decimal("100.0"),  # Convert percentage to decimal
                        "adjustment_pct": adjustment_pct,
                        "type": adjustment_type,  # 'control_premium', 'minority_discount', or 'deadlock_discount'
                        "ownership_percentage": ownership_pct,
                        "rationale": step8.result.get("tier_description", "Ownership adjustment"),
                    }
                )

    def _validate_extraction(
        self, previous_results: PreviousResults, adjustments: List[Adjustment]
    ) -> List[str]:
        """
        Validate that all non-zero adjustments were extracted.

        Returns:
            List of validation warning messages
        """
        validation_warnings = []
        for spec in _ADJUSTMENT_VALIDATION_SPECS:
            warning = self._missing_adjustment_warning(previous_results, adjustments, spec)
            if warning:
                validation_warnings.append(warning)

        return validation_warnings

    def _missing_adjustment_warning(
        self,
        previous_results: PreviousResults,
        adjustments: List[Adjustment],
        spec: _AdjustmentValidationSpec,
    ) -> Optional[str]:
        step_result = previous_results.get(spec.step_number)
        if not step_result or step_result.status != StepStatus.COMPLETED:
            return None
        if any(adj["type"] == spec.adjustment_type for adj in adjustments):
            return None

        adjustment_value = _first_present_result_value(
            step_result.result,
            *spec.result_keys,
        )
        if not _is_material_adjustment(adjustment_value):
            return None

        return (
            f"Step {spec.step_number} completed with {spec.value_label} "
            f"{adjustment_value}, but not extracted!"
        )


def _first_present_result_value(result: dict[str, object], *keys: str) -> Optional[object]:
    for key in keys:
        value = result.get(key)
        if value is not None:
            return value
    return None


def _is_material_adjustment(value: object) -> bool:
    if value is None:
        return False
    return abs(to_decimal(value)) > Decimal("0.0001")
