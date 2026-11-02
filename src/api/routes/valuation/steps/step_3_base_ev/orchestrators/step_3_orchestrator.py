"""
Step 3 Orchestrator

Orchestrates the main execution flow for Step 3 Base EV calculation.
"""

import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.api.routes.valuation.benchmark_contract_utils import (
    is_country_baseline_benchmark_contract,
    is_resolved_benchmark_contract,
)
from src.config import get_settings
from src.services.academic.sme_business_type_lookup import synced_business_type_ev_ebitda
from src.utils.decimal_helpers import bank_round, from_decimal, money_multiply, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus
from ..builders.step_3_result_builder import Step3ResultBuilder
from ..calculators.step_3_ev_calculator import Step3EVCalculator
from ..handlers.step_3_error_handler import Step3ErrorHandler

logger = get_logger(__name__)


def _scale_percentiles_to_sector(
    p25: Decimal, p50: Decimal, p75: Decimal, sector_multiple: Decimal
) -> Tuple[Decimal, Decimal, Decimal]:
    """Anchor an EV/EBITDA percentile band to a sector multiple, preserving shape.

    Scales the band so the median equals ``sector_multiple`` while keeping the
    P25/P75 dispersion ratio intact. Scale-DOWN only: if the band median is
    already at or below the sector multiple, the band is returned unchanged.
    """
    p50_d = to_decimal(p50)
    sector = to_decimal(sector_multiple)
    if p50_d <= 0 or sector <= 0 or p50_d <= sector:
        return to_decimal(p25), p50_d, to_decimal(p75)
    scale = sector / p50_d
    return to_decimal(p25) * scale, sector, to_decimal(p75) * scale


def _maybe_sector_anchor_percentiles(
    request: object,
    benchmark_provenance: object,
    primary_method: str,
    percentiles: Tuple[Decimal, Decimal, Decimal],
) -> Tuple[Decimal, Decimal, Decimal]:
    """Anchor the EV/EBITDA band to the sector multiple for country-baseline fallbacks.

    No-op unless all hold: the kill-switch is on, the method is EV/EBITDA, Step 2
    served a country-baseline (non-defendable) benchmark, the request carries a
    business type, a synced sector multiple exists, and the band median exceeds it.
    """
    p25, p50, p75 = percentiles
    try:
        enabled = bool(getattr(get_settings(), "cap_country_baseline_multiple_to_sector", False))
    except Exception:
        enabled = False
    if not enabled or primary_method != "EV/EBITDA":
        return p25, p50, p75
    business_type_id = getattr(request, "business_type_id", None)
    if not business_type_id or not is_country_baseline_benchmark_contract(benchmark_provenance):
        return p25, p50, p75
    country = getattr(request, "country", None) or "Belgium"
    sector_multiple = synced_business_type_ev_ebitda(str(business_type_id), country)
    if not sector_multiple or to_decimal(p50) <= to_decimal(sector_multiple):
        return p25, p50, p75
    new_p25, new_p50, new_p75 = _scale_percentiles_to_sector(p25, p50, p75, sector_multiple)
    logger.info(
        "🧭 Sector-anchored EV/EBITDA band (no defendable benchmark)",
        extra={
            "step_number": 3,
            "reason": "country_baseline_fallback",
            "business_type_id": str(business_type_id),
            "sector_multiple": to_decimal(sector_multiple),
            "p50_before": to_decimal(p50),
            "p50_after": to_decimal(new_p50),
            "p25_after": to_decimal(new_p25),
            "p75_after": to_decimal(new_p75),
        },
    )
    return new_p25, new_p50, new_p75


class Step3Orchestrator:
    """Orchestrates the main execution flow for Step 3."""

    def __init__(self, step_name: str):
        """
        Initialize the orchestrator.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name
        self.error_handler = Step3ErrorHandler(step_name)
        self.calculator = Step3EVCalculator()
        self.result_builder = Step3ResultBuilder(step_name)

    async def orchestrate_execution(
        self,
        request: any,
        step1: Dict[str, Any],
        step2: Dict[str, Any],
        correlation_id: Optional[str],
        execution_start_time: Decimal,
        step2_5: Optional[Dict[str, Any]] = None,
    ) -> StepOutput:
        """
        Orchestrate the main execution flow.

        Args:
            request: Valuation request
            step1: Step 1 result dictionary
            step2: Step 2 result dictionary
            correlation_id: Correlation ID for tracing
            execution_start_time: Execution start time
            step2_5: Step 2.5 result (EBITDA normalization) - OPTIONAL

        Returns:
            StepOutput with calculation results
        """
        # Extract metrics from Step 1 with normalization from Step 2.5
        revenue, ebitda = self.calculator.extract_metrics(step1, request, step2_5)

        logger.debug(
            "📊 Step 3 input values extracted",
            extra={
                "step_number": 3,
                "revenue": to_decimal(revenue),
                "ebitda": to_decimal(ebitda) if ebitda else None,
                "precision": "Decimal (bank-grade)",
                "revenue_source": "step1" if step1.get("revenue", 0) > 0 else "request_fallback",
            },
        )

        # Validate revenue - return SKIPPED if zero
        if revenue <= 0:
            primary_method = step2.get("primary_method", "EV/Revenue")
            return self.error_handler.handle_invalid_revenue(
                to_decimal(revenue), primary_method, to_decimal(ebitda) if ebitda else None
            )

        # Determine and validate primary method
        primary_method = self.calculator.determine_primary_method(step2)
        benchmark_provenance = step2.get("benchmark_provenance") or step2.get("benchmark_contract")
        allow_untrusted_multiples_fallback = getattr(
            request, "allow_untrusted_multiples_fallback", False
        ) is True or (
            isinstance(getattr(request, "metadata", None), dict)
            and getattr(request, "metadata", {}).get("allow_untrusted_multiples_fallback") is True
        )
        if (
            getattr(request, "business_type_id", None)
            and not allow_untrusted_multiples_fallback
            and not is_resolved_benchmark_contract(benchmark_provenance)
        ):
            raise ValueError(
                "Step 3 refuses to calculate a business-type multiple valuation without "
                "the resolved benchmark contract used by Step 2"
            )

        # Validate Step 2 provides required data
        if not step2.get("primary_method"):
            return self.error_handler.handle_missing_primary_method()

        logger.debug(
            "🔍 Determining calculation method",
            extra={
                "step_number": 3,
                "primary_method": primary_method,
                "available_methods": ["EV/Revenue", "EV/EBITDA"],
                "revenue_available": revenue > 0,
                "ebitda_available": ebitda is not None and ebitda > 0 if ebitda else False,
            },
        )

        # Extract multiples with fallbacks and apply Step 2.5 quality calibration
        multiple, metric, metric_name, fallback_used = self.calculator.extract_multiples(
            step2, primary_method, revenue, ebitda, step2_5, request=request
        )

        # Check if multiples are available
        if multiple <= 0:
            return self.error_handler.handle_invalid_multiple(to_decimal(multiple), primary_method)

        # Validate metric/method consistency and update if needed
        metric, metric_name = self.calculator.validate_consistency(
            primary_method, metric_name, metric, revenue, ebitda
        )

        # Extract percentiles with validation, applying quality adjustment from Step 2.5
        quality_adj = (
            to_decimal(step2_5.get("quality_multiple_adjustment") or 0) if step2_5 else Decimal("0")
        )
        manual_adj, manual_note = self.calculator.extract_manual_multiple_calibration(request)
        total_multiple_adjustment = quality_adj + manual_adj
        multiple_p25, multiple_p50, multiple_p75, using_real_percentiles = (
            self.calculator.extract_percentiles(
                step2,
                primary_method,
                multiple,
                quality_adjustment=total_multiple_adjustment,
            )
        )

        # Anchor a non-defendable country-baseline band to the sector multiple so
        # a generic equity-market proxy (e.g. Damodaran European 5.65x) cannot
        # price a micro SME. Surgically gated; scale-down only; settings kill-switch.
        multiple_p25, multiple_p50, multiple_p75 = _maybe_sector_anchor_percentiles(
            request=request,
            benchmark_provenance=benchmark_provenance,
            primary_method=primary_method,
            percentiles=(multiple_p25, multiple_p50, multiple_p75),
        )

        # DEBUG: calculation start; the Step 3 EV Calculation Complete exit log
        # carries the final EV figure.
        logger.debug(
            "🧮 Calculating Enterprise Value using percentiles",
            extra={
                "step_number": 3,
                "step_name": "Base Enterprise Value",
                "calculation": {
                    "formula": f"Enterprise Value = {metric_name} × Multiple",
                    "metric_name": metric_name,
                    "metric_value": to_decimal(metric),
                    "primary_method": primary_method,
                },
                "multiples": {
                    "multiple_p25": to_decimal(multiple_p25),
                    "multiple_p50": to_decimal(multiple_p50),
                    "multiple_p75": to_decimal(multiple_p75),
                    "percentile_source": "real" if using_real_percentiles else "estimated",
                },
            },
        )

        # Calculate EV range
        enterprise_value_low, enterprise_value_mid, enterprise_value_high = (
            self.calculator.calculate_ev_range(metric, multiple_p25, multiple_p50, multiple_p75)
        )

        # Validate and correct range ordering
        enterprise_value_low, enterprise_value_mid, enterprise_value_high = (
            self.calculator.validate_and_correct_range(
                enterprise_value_low, enterprise_value_mid, enterprise_value_high
            )
        )

        # Round to 2 decimal places for currency precision
        enterprise_value_low = bank_round(enterprise_value_low, 2)
        enterprise_value_mid = bank_round(enterprise_value_mid, 2)
        enterprise_value_high = bank_round(enterprise_value_high, 2)

        # Final consistency check before converting to float
        if primary_method == "EV/Revenue" and metric_name != "Revenue":
            logger.error(
                "❌ CRITICAL: Step 3 consistency violation - EV/Revenue method but metric is not Revenue",
                extra={
                    "step_number": 3,
                    "primary_method": primary_method,
                    "metric_name": metric_name,
                    "metric_value": to_decimal(metric),
                },
            )
            # Force correction
            metric = revenue
            metric_name = "Revenue"
            enterprise_value_low = money_multiply(metric, multiple_p25)
            enterprise_value_mid = money_multiply(metric, multiple_p50)
            enterprise_value_high = money_multiply(metric, multiple_p75)
            logger.warning(
                "⚠️ Forced correction: Recalculated all three values using Revenue metric"
            )
        elif primary_method == "EV/EBITDA" and metric_name not in [
            "EBITDA",
            "Revenue (EBITDA fallback)",
        ]:
            logger.error(
                "❌ CRITICAL: Step 3 consistency violation - EV/EBITDA method but metric is not EBITDA",
                extra={
                    "step_number": 3,
                    "primary_method": primary_method,
                    "metric_name": metric_name,
                    "metric_value": to_decimal(metric),
                },
            )
            # Force correction if EBITDA available
            if ebitda and ebitda > 0:
                metric = ebitda
                metric_name = "EBITDA"
                enterprise_value_low = money_multiply(metric, multiple_p25)
                enterprise_value_mid = money_multiply(metric, multiple_p50)
                enterprise_value_high = money_multiply(metric, multiple_p75)
                logger.warning(
                    "⚠️ Forced correction: Recalculated all three values using EBITDA metric"
                )

        # Convert to float for JSON serialization
        ev_low_float = from_decimal(enterprise_value_low, 2)
        ev_mid_float = from_decimal(enterprise_value_mid, 2)
        ev_high_float = from_decimal(enterprise_value_high, 2)
        metric_float = from_decimal(metric, 2)
        multiple_float = to_decimal(multiple)
        multiple_p25_float = to_decimal(multiple_p25)
        multiple_p50_float = to_decimal(multiple_p50)
        multiple_p75_float = to_decimal(multiple_p75)

        # DEBUG: final consistency verification diagnostic.
        logger.debug(
            "🔍 Step 3: Final consistency verification",
            extra={
                "step_number": 3,
                "primary_method": primary_method,
                "metric_name": metric_name,
                "metric_value": metric_float,
                "ev_low": ev_low_float,
                "ev_mid": ev_mid_float,
                "ev_high": ev_high_float,
                "multiple_p25": multiple_p25_float,
                "multiple_p50": multiple_p50_float,
                "multiple_p75": multiple_p75_float,
                "consistency_check": "PASSED - All three use same metric and multiple type",
                "calculation_verified": f"Low/Mid/High all use {metric_name} × {primary_method} multiples",
            },
        )

        # Comprehensive completion log
        # CRITICAL FIX: Convert execution_start_time to float if it's Decimal to match time.time() return type
        execution_start_time_float = (
            float(execution_start_time)
            if isinstance(execution_start_time, Decimal)
            else execution_start_time
        )
        execution_time_ms = (time.time() - execution_start_time_float) * 1000
        logger.info(
            "📊 Step 3: Base Enterprise Value - Calculation Complete",
            extra={
                "step_number": 3,
                "step_name": "Base Enterprise Value",
                "status": "COMPLETED",
                "correlation_id": correlation_id,
                "execution_time_ms": round(execution_time_ms, 2),
                "inputs": {
                    "metric_name": metric_name,
                    "metric_value": metric_float,
                    "primary_method": primary_method,
                    "revenue": to_decimal(revenue),
                    "ebitda": to_decimal(ebitda) if ebitda else None,
                },
                "calculation": {
                    "formula": f"Enterprise Value = {metric_name} × Multiple",
                    "multiples": {
                        "multiple_p25": multiple_p25_float,
                        "multiple_p50": multiple_p50_float,
                        "multiple_p75": multiple_p75_float,
                        "percentile_source": "real" if using_real_percentiles else "estimated",
                    },
                },
                "outputs": {
                    "enterprise_value_low": ev_low_float,
                    "enterprise_value_mid": ev_mid_float,
                    "enterprise_value_high": ev_high_float,
                    "range_spread_pct": (
                        ((ev_high_float - ev_low_float) / ev_mid_float * 100)
                        if ev_mid_float > 0
                        else 0
                    ),
                },
                "critical_values": {
                    "enterprise_value_low": ev_low_float,
                    "enterprise_value_mid": ev_mid_float,
                    "enterprise_value_high": ev_high_float,
                    "primary_method": primary_method,
                    "metric_used": metric_name,
                    "metric_value": metric_float,
                },
            },
        )

        # Compute implied EBITDA multiple for transparency when Revenue is the primary method.
        # This helps advisors see what the Revenue-based EV implies in EBITDA terms.
        # e.g. "Revenue × 1.73 = €1.1M → implied EBITDA multiple of 19.3× (vs benchmark 6.4×)"
        implied_ebitda_multiple = None
        if (
            primary_method == "EV/Revenue"
            and ebitda is not None
            and ebitda > 0
            and ev_mid_float > 0
        ):
            implied_ebitda_multiple = to_decimal(ev_mid_float) / to_decimal(ebitda)
            logger.info(
                "📊 Step 3: Implied EBITDA multiple computed (transparency)",
                extra={
                    "step_number": 3,
                    "implied_ebitda_multiple": f"{implied_ebitda_multiple:.1f}x",
                    "ev_mid": ev_mid_float,
                    "ebitda": to_decimal(ebitda),
                    "primary_method": primary_method,
                    "note": "Transparency metric: what Revenue-based EV implies in EBITDA terms",
                },
            )

        # Build result and metadata
        result_dict = self.result_builder.build_result_dict(
            ev_low_float,
            ev_mid_float,
            ev_high_float,
            primary_method,
            metric_name,
            metric_float,
            multiple_float,
            multiple_p25_float,
            multiple_p50_float,
            multiple_p75_float,
            using_real_percentiles,
            implied_ebitda_multiple=implied_ebitda_multiple,
            benchmark_provenance=(
                benchmark_provenance if isinstance(benchmark_provenance, dict) else None
            ),
        )

        metadata_dict = self.result_builder.build_metadata_dict(
            metric_name,
            metric_float,
            multiple_p25_float,
            multiple_p50_float,
            multiple_p75_float,
            ev_low_float,
            ev_mid_float,
            ev_high_float,
            using_real_percentiles,
            benchmark_provenance=(
                benchmark_provenance if isinstance(benchmark_provenance, dict) else None
            ),
        )

        if manual_adj != Decimal("0"):
            sector_multiple = multiple - total_multiple_adjustment
            calibration_audit = {
                "sector_average_multiple": to_decimal(sector_multiple),
                "specific_risk_quality_premium": to_decimal(manual_adj),
                "quality_multiple_adjustment": to_decimal(quality_adj),
                "total_multiple_adjustment": to_decimal(total_multiple_adjustment),
                "calibrated_multiple": to_decimal(multiple),
                "note": manual_note,
            }
            result_dict["multiple_calibration"] = calibration_audit
            metadata_dict["multiple_calibration"] = calibration_audit

        return StepOutput(
            step_number=3,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            execution_time_ms=round(execution_time_ms, 2),
            result=result_dict,
            metadata=metadata_dict,
        )
