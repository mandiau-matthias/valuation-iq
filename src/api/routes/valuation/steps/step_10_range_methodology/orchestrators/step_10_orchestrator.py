"""
Step 10 Orchestrator

Orchestrates the main execution flow for Step 10 range methodology.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
from src.domain.range_methodology_calculator import RangeMethodologyCalculator
from src.services.academic.calculation_provenance_tracker import record_calculation_safe
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.exceptions import CalculationError
from src.utils.logging import get_logger
from src.utils.sole_trader_detector import SoleTraderDetector

from .equity_extraction import extract_equity_value

logger = get_logger(__name__)


class Step10Orchestrator:
    """Orchestrates the main execution flow for Step 10."""

    def __init__(
        self,
        range_calculator: RangeMethodologyCalculator,
        business_type_triage: BusinessTypeTriageEngine,
        calculator,
        result_builder,
        error_handler,
        step_name: str,
    ):
        """
        Initialize the orchestrator.

        Args:
            range_calculator: Range methodology calculator
            business_type_triage: Business type triage engine
            calculator: Step 10 range calculator instance
            result_builder: Step 10 result builder instance
            error_handler: Step 10 error handler instance
            step_name: Step name for logging
        """
        self.range_calculator = range_calculator
        self.business_type_triage = business_type_triage
        self.calculator = calculator
        self.result_builder = result_builder
        self.error_handler = error_handler
        self.step_name = step_name

    async def orchestrate_execution(
        self,
        request: any,
        step0: Optional[Dict[str, Any]],
        step1: Optional[Dict[str, Any]],
        step2: Optional[Dict[str, Any]],
        step7_output: any,
        step8_output: Optional[any],
        step9_confidence_result: Optional[Dict[str, Any]],
        step6_output: Optional[any] = None,
        correlation_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Orchestrate the main execution flow.

        Args:
            request: The valuation request
            step0: Step 0 result dictionary
            step1: Step 1 result dictionary
            step2: Step 2 result dictionary (optional)
            step7_output: Step 7 output (optional, falls back to Step 6 if unavailable)
            step8_output: Step 8 output (optional)
            step9_confidence_result: Step 9 confidence result (optional)
            step6_output: Step 6 output (optional fallback for equity value)
            correlation_id: Correlation ID for logging

        Returns:
            Tuple of (result_dict, metadata_dict)
        """
        # Extract equity value (Step 8 preferred, Step 7 fallback, Step 6 as last resort)
        equity_mid, equity_source, ownership_adjusted_equity, step7_equity_for_validation = (
            self._extract_equity_value(step7_output, step8_output, step6_output)
        )

        # BANK-GRADE: Validate equity_mid before proceeding
        if equity_mid is None or equity_mid <= 0:
            step7_status = (
                step7_output.status.value
                if step7_output and hasattr(step7_output, "status")
                else ("status_missing" if step7_output else "not_found")
            )
            step8_status = (
                step8_output.status.value
                if step8_output and hasattr(step8_output, "status")
                else ("status_missing" if step8_output else "not_found")
            )
            step6_status = (
                step6_output.status.value
                if step6_output and hasattr(step6_output, "status")
                else ("status_missing" if step6_output else "not_found")
            )
            logger.error(
                "❌ Step 10 failed: No valid equity value available",
                extra={
                    "step_number": 10,
                    "equity_mid": str(equity_mid) if equity_mid is not None else "None",
                    "equity_source": equity_source,
                    "step7_status": step7_status,
                    "step8_status": step8_status,
                    "step6_status": step6_status,
                    "step7_output_type": type(step7_output).__name__ if step7_output else "None",
                    "step8_output_type": type(step8_output).__name__ if step8_output else "None",
                    "step6_output_type": type(step6_output).__name__ if step6_output else "None",
                    "correlation_id": correlation_id,
                },
            )
            raise CalculationError(
                f"No valid equity value available for range calculation. "
                f"Step 7 status: {step7_status}, Step 8 status: {step8_status}, Step 6 status: {step6_status}"
            )

        # Extract confidence score from Step 9 (with fallback)
        confidence_score, confidence_level = self._extract_confidence_score(step9_confidence_result)

        # Extract data quality score from Step 0
        data_quality_score = step0.get("quality_score") if step0 else None

        # Extract financial metrics
        revenue = to_decimal(step1.get("revenue", 0) or 0) if step1 else Decimal("0")
        ebitda_margin = step1.get("ebitda_margin") if step1 else None
        if ebitda_margin is not None:
            ebitda_margin = ebitda_margin / Decimal("100.0")  # Convert percentage to decimal

        # Calculate growth rate
        growth_rate = self.calculator.calculate_growth_rate(request)
        growth_validated = self.calculator.determine_growth_validated(request)

        # Get business category
        business_category = None
        try:
            business_category = self.business_type_triage.get_business_type_category(
                getattr(request, "business_type_id", None),
                getattr(request, "business_model", None),
                getattr(request, "industry", None),
                category_id=getattr(request, "category_id", None),
            )
        except Exception as e:
            logger.debug(
                f"Could not determine business category: {e}",
                extra={"step_number": 10, "error": str(e)},
            )

        # Extract comparables data from Step 2
        (
            comparables_found,
            sufficient_comparables,
            primary_method,
            ev_revenue_p25,
            ev_revenue_p50,
            ev_revenue_p75,
            ev_ebitda_p25,
            ev_ebitda_p50,
            ev_ebitda_p75,
        ) = self._extract_comparables_data(step2)

        # Determine methodology
        use_dispersion = self.calculator.should_use_dispersion(
            sufficient_comparables,
            comparables_found,
            primary_method,
            ev_revenue_p25,
            ev_revenue_p75,
            ev_ebitda_p25,
            ev_ebitda_p75,
        )

        # Calculate range
        equity_low, equity_high, methodology, spread_result = await self._calculate_range(
            equity_mid=equity_mid,
            use_dispersion=use_dispersion,
            primary_method=primary_method,
            ev_revenue_p25=ev_revenue_p25,
            ev_revenue_p50=ev_revenue_p50,
            ev_revenue_p75=ev_revenue_p75,
            ev_ebitda_p25=ev_ebitda_p25,
            ev_ebitda_p50=ev_ebitda_p50,
            ev_ebitda_p75=ev_ebitda_p75,
            confidence_score=confidence_score,
            revenue=revenue,
            business_category=business_category,
            growth_rate=growth_rate,
            growth_validated=growth_validated,
            ebitda_margin=ebitda_margin,
            data_quality_score=data_quality_score,
            request=request,
        )

        # Round to 2 decimal places
        equity_low = bank_round(equity_low, 2)
        equity_high = bank_round(equity_high, 2)

        # Convert to float
        equity_low_float = from_decimal(equity_low, 2)
        equity_mid_float = from_decimal(equity_mid, 2)
        equity_high_float = from_decimal(equity_high, 2)

        # Academic provenance: rule `valuation_range_width` enforces
        # 15% - 50% per McKinsey (2020) / Damodaran (2012). The validated
        # value is the half-spread = (high - low) / (2 * mid), matching
        # AcademicValidationEngine.validate_valuation_results().
        if equity_mid > 0:
            range_width = float(
                (to_decimal(equity_high) - to_decimal(equity_low))
                / (to_decimal("2") * to_decimal(equity_mid))
            )
            record_calculation_safe(
                "valuation_range",
                range_width,
                step_number=10,
                section_name="Valuation Range",
                inputs={
                    "equity_low": equity_low_float,
                    "equity_mid": equity_mid_float,
                    "equity_high": equity_high_float,
                    "methodology": methodology,
                },
            )

        # Build result and metadata
        result_dict = self.result_builder.build_result_dict(
            equity_low_float=equity_low_float,
            equity_mid_float=equity_mid_float,
            equity_high_float=equity_high_float,
            methodology=methodology,
            confidence_level=confidence_level,
        )

        metadata_dict = self.result_builder.build_metadata_dict(
            equity_low=equity_low,
            equity_mid=equity_mid,
            equity_high=equity_high,
            methodology=methodology,
            use_dispersion=use_dispersion,
            comparables_found=comparables_found,
            sufficient_comparables=sufficient_comparables,
            primary_method=primary_method,
            base_spread=spread_result.get("base_spread") if spread_result else None,
            size_adjustment=spread_result.get("size_adjustment") if spread_result else None,
            business_type_multiplier=(
                spread_result.get("business_type_multiplier") if spread_result else None
            ),
            growth_adjustment=spread_result.get("growth_adjustment") if spread_result else None,
            profitability_adjustment=(
                spread_result.get("profitability_adjustment") if spread_result else None
            ),
            data_quality_adjustment=(
                spread_result.get("data_quality_adjustment") if spread_result else None
            ),
            spread=spread_result.get("total_spread") if spread_result else None,
            spread_breakdown=spread_result.get("breakdown") if spread_result else None,
            use_asymmetric=spread_result.get("use_asymmetric", False) if spread_result else False,
            downside_pct=spread_result.get("downside_pct") if spread_result else None,
            upside_pct=spread_result.get("upside_pct") if spread_result else None,
            ev_revenue_p25=ev_revenue_p25,
            ev_revenue_p50=ev_revenue_p50,
            ev_revenue_p75=ev_revenue_p75,
            ev_ebitda_p25=ev_ebitda_p25,
            ev_ebitda_p50=ev_ebitda_p50,
            ev_ebitda_p75=ev_ebitda_p75,
            business_category=business_category,
            growth_rate=growth_rate,
            growth_validated=growth_validated,
            ebitda_margin=ebitda_margin,
            data_quality_score=data_quality_score,
            step7_equity_value_mid=equity_mid_float,
            ownership_adjusted_equity=(
                to_decimal(ownership_adjusted_equity) if ownership_adjusted_equity else None
            ),
        )

        return result_dict, metadata_dict

    def _extract_equity_value(
        self, step7_output: Any, step8_output: Optional[Any], step6_output: Optional[Any] = None
    ) -> Tuple[Optional[Decimal], Optional[str], Any | None, Any | None]:
        """Extract equity value from Step 8 or Step 7 only."""
        return extract_equity_value(step7_output, step8_output, step6_output)

    def _extract_confidence_score(
        self, step9_confidence_result: Optional[Dict[str, Any]]
    ) -> Tuple[int, str]:
        """Extract confidence score from Step 9 with fallback."""
        if not step9_confidence_result:
            logger.warning(
                "⚠️  Step 9 results not available, using default confidence for range calculation",
                extra={"step_number": 10, "default_confidence": 66, "default_level": "MEDIUM"},
            )
            return 66, "MEDIUM"

        confidence_score = step9_confidence_result.get("overall_confidence_score", 66)
        confidence_level = step9_confidence_result.get("confidence_level", "MEDIUM")
        logger.debug(
            "✅ Confidence score extracted from Step 9",
            extra={
                "step_number": 10,
                "confidence_score": confidence_score,
                "confidence_level": confidence_level,
            },
        )
        return confidence_score, confidence_level

    def _extract_comparables_data(self, step2: Optional[Dict[str, Any]]) -> Tuple[
        int,
        bool,
        str,
        Optional[Decimal],
        Optional[Decimal],
        Optional[Decimal],
        Optional[Decimal],
        Optional[Decimal],
        Optional[Decimal],
    ]:
        """Extract comparables data from Step 2."""
        if not step2:
            return 0, False, "EV/EBITDA", None, None, None, None, None, None

        comparables_found = step2.get("comparables_found", 0) or 0
        sufficient_comparables = step2.get("sufficient_comparables", False) or False

        primary_method_raw = step2.get("primary_method", "EV/EBITDA")
        token = str(primary_method_raw).strip().upper()
        if token in {"EV/REVENUE", "REVENUE_MULTIPLE", "REVENUE", "EV_REVENUE"}:
            primary_method = "EV/Revenue"
        else:
            primary_method = "EV/EBITDA"

        ev_revenue_p25 = step2.get("ev_revenue_p25") if primary_method == "EV/Revenue" else None
        ev_revenue_p50 = step2.get("ev_revenue_p50") if primary_method == "EV/Revenue" else None
        ev_revenue_p75 = step2.get("ev_revenue_p75") if primary_method == "EV/Revenue" else None
        ev_ebitda_p25 = step2.get("ev_ebitda_p25") if primary_method == "EV/EBITDA" else None
        ev_ebitda_p50 = step2.get("ev_ebitda_p50") if primary_method == "EV/EBITDA" else None
        ev_ebitda_p75 = step2.get("ev_ebitda_p75") if primary_method == "EV/EBITDA" else None

        return (
            comparables_found,
            sufficient_comparables,
            primary_method,
            ev_revenue_p25,
            ev_revenue_p50,
            ev_revenue_p75,
            ev_ebitda_p25,
            ev_ebitda_p50,
            ev_ebitda_p75,
        )

    async def _calculate_range(
        self,
        equity_mid: Decimal,
        use_dispersion: bool,
        primary_method: str,
        ev_revenue_p25: Optional[Decimal],
        ev_revenue_p50: Optional[Decimal],
        ev_revenue_p75: Optional[Decimal],
        ev_ebitda_p25: Optional[Decimal],
        ev_ebitda_p50: Optional[Decimal],
        ev_ebitda_p75: Optional[Decimal],
        confidence_score: int,
        revenue: Decimal,
        business_category: any,
        growth_rate: Optional[Decimal],
        growth_validated: bool,
        ebitda_margin: Optional[Decimal],
        data_quality_score: Optional[int],
        request: any,
    ) -> Tuple[Decimal, Decimal, str, Optional[Dict[str, Any]]]:
        """Calculate range using appropriate methodology."""
        spread_result = None

        if use_dispersion:
            equity_low, equity_high, success = self.calculator.calculate_dispersion_range(
                equity_mid,
                primary_method,
                ev_revenue_p25,
                ev_revenue_p50,
                ev_revenue_p75,
                ev_ebitda_p25,
                ev_ebitda_p50,
                ev_ebitda_p75,
            )

            if success:
                methodology = "Multiple Dispersion"
                return equity_low, equity_high, methodology, None

            # Fall through to confidence spread if dispersion failed
            use_dispersion = False

        # Use enhanced confidence spread
        business_type_id = getattr(request, "business_type_id", None)
        valuation_preferences = getattr(request, "valuation_preferences", None)
        spread_result = self.range_calculator.calculate_confidence_spread(
            confidence_score=confidence_score,
            revenue=revenue,
            business_category=business_category,
            growth_rate=growth_rate,
            growth_validated=growth_validated,
            ebitda_margin=ebitda_margin,
            data_quality_score=data_quality_score,
            business_type_id=business_type_id,
            valuation_preferences=valuation_preferences,
        )

        total_spread = spread_result["total_spread"]
        total_spread, is_declining = self.calculator.adjust_spread_for_declining_revenue(
            growth_rate, total_spread
        )

        # Check for asymmetric range
        # Use unified utility for owner/employee extraction
        from src.utils.core.data_extraction_helpers import (
            extract_owner_employee_counts_from_request,
        )

        num_owners, num_employees = extract_owner_employee_counts_from_request(request)

        is_sole_trader = SoleTraderDetector.detect(
            business_structure=getattr(request, "business_type", None),
            business_type=getattr(request, "business_type", None),
            number_of_owners=num_owners,
            number_of_employees=num_employees,
            is_sole_trader=getattr(request, "is_sole_trader", None),
            business_context=getattr(request, "business_context", None),
        )

        use_asymmetric = is_sole_trader or self.range_calculator.should_use_asymmetric_range(
            revenue=revenue, business_category=business_category, ebitda_margin=ebitda_margin
        )

        if use_asymmetric:
            methodology = "Asymmetric Range"
            range_result = self.range_calculator.calculate_asymmetric_range(
                equity_mid=equity_mid, business_category=business_category
            )
            equity_low = range_result["equity_low"]
            equity_high = range_result["equity_high"]
            spread_result["use_asymmetric"] = True
            spread_result["downside_pct"] = range_result["downside_percentage"]
            spread_result["upside_pct"] = range_result["upside_percentage"]
        else:
            methodology = "Confidence Spread"
            range_result = self.range_calculator.calculate_symmetric_range(
                equity_mid=equity_mid, total_spread=total_spread
            )
            equity_low = range_result["equity_low"]
            equity_high = range_result["equity_high"]
            spread_result["use_asymmetric"] = False
            spread_result["downside_pct"] = None
            spread_result["upside_pct"] = None

        spread_result["total_spread"] = total_spread

        return equity_low, equity_high, methodology, spread_result
