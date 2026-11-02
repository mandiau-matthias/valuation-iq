"""
Synthesis Orchestrator for Step 11

Orchestrates the complete synthesis flow including value chain validation,
rounding, ordering validation, and final output formatting.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from prometheus_client import Counter, Histogram

from src.api.routes.valuation.steps.base_step import StepInput, StepStatus
from src.api.routes.valuation.steps.step_11_synthesis.rounding import (
    apply_rounding as apply_synthesis_rounding,
)
from src.api.routes.valuation.steps.step_11_synthesis.rounding import granularity_for
from src.api.routes.valuation.steps.step_11_synthesis.sde_synthesis import (
    synthesize_with_sde as synthesize_with_sde_values,
)
from src.config import get_settings
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.equity_range_normalization import coerce_equity_range_triple
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Prometheus metrics for value chain monitoring
value_chain_breaks = Counter(
    "valuation_value_chain_breaks_total",
    "Number of value chain breaks detected and auto-corrected",
    ["correction_type"],
)

value_chain_difference = Histogram(
    "valuation_value_chain_difference_percent",
    "Percentage difference in value chain validation",
    buckets=[
        Decimal("0.01"),
        Decimal("0.05"),
        Decimal("0.1"),
        Decimal("0.5"),
        Decimal("1.0"),
        Decimal("2.0"),
        Decimal("5.0"),
        Decimal("10.0"),
    ],
)

# Counter for the post-rounding ordering-clamp event. A non-zero rate here
# indicates that ``apply_rounding`` is silently fixing ordering breaks that
# would otherwise have surfaced as 422s — investigate Step 11 upstream
# (SDE blend, value chain validation, fallback range generation).
ordering_clamps_total = Counter(
    "valuation_step11_ordering_clamps_total",
    "Number of times Step 11 apply_rounding clamped low/high to preserve ordering",
    ["bound"],  # "low" or "high"
)


class SynthesisOrchestrator:
    """
    Orchestrates the complete Step 11 synthesis flow.

    Responsibilities:
    - Extract and validate valuation ranges
    - Perform value chain validation and correction
    - Handle rounding and ordering validation
    - Coordinate all synthesis operations
    """

    def __init__(self, range_calculator, validator, get_previous_step_result_func):
        """
        Initialize orchestrator.

        Args:
            range_calculator: RangeCalculator instance
            validator: SynthesisValidator instance
            get_previous_step_result_func: Function to get previous step result
        """
        self.range_calculator = range_calculator
        self.validator = validator
        self.get_previous_step_result = get_previous_step_result_func

    def extract_valuation_range(
        self, input_data: StepInput, use_fallback: bool
    ) -> Tuple[float, float, float, bool, bool, Optional[str], Optional[Decimal]]:
        """
        Extract valuation range from Step 10 or generate fallback.

        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high,
                     use_fallback, step10_values_preserved,
                     equity_source, equity_value_mid)
        """
        step10_result = self.get_previous_step_result(10, input_data.previous_results)
        step10_output = input_data.previous_results.get(10)
        step10_failed = (
            step10_output is None
            or step10_output.status != StepStatus.COMPLETED
            or input_data.context.get("step10_failed", False)
        )

        # Extract equity value from Step 7/8
        equity_value_mid, equity_source = self._extract_equity_value(input_data.previous_results)

        if not step10_result or step10_failed:
            # Use fallback logic
            valuation_low, valuation_mid, valuation_high = (
                self.range_calculator.generate_fallback_range(
                    input_data.previous_results, input_data.request
                )
            )

            if valuation_mid <= 0:
                logger.error(
                    "❌ Step 11 fallback failed: No valid equity value found",
                    extra={"step_number": 11},
                )
                valuation_mid = valuation_low = valuation_high = Decimal("0.0")

            return (
                valuation_low,
                valuation_mid,
                valuation_high,
                True,
                False,
                equity_source,
                equity_value_mid,
            )

        # Extract from Step 10 (use `is None` — Decimal("0") is a valid value)
        valuation_low = step10_result.get("valuation_low")
        valuation_low = Decimal("0") if valuation_low is None else to_decimal(valuation_low)
        valuation_mid = step10_result.get("valuation_mid")
        valuation_mid = Decimal("0") if valuation_mid is None else to_decimal(valuation_mid)
        valuation_high = step10_result.get("valuation_high")
        valuation_high = Decimal("0") if valuation_high is None else to_decimal(valuation_high)

        # Validate and correct value chain
        (
            valuation_low,
            valuation_mid,
            valuation_high,
            step10_values_preserved,
            value_chain_validated,
        ) = self._validate_and_correct_value_chain(
            valuation_low,
            valuation_mid,
            valuation_high,
            equity_value_mid,
            equity_source,
            step10_result,
        )

        return (
            valuation_low,
            valuation_mid,
            valuation_high,
            False,
            step10_values_preserved,
            equity_source,
            equity_value_mid,
        )

    def _extract_equity_value(
        self, previous_results: Dict[int, Any]
    ) -> Tuple[Optional[Decimal], Optional[str]]:
        """
        Extract equity value from Step 8, Step 7, Step 6 EV, or Step 2.7 SDE.

        Priority order:
        1. Step 8 (ownership-adjusted equity) - preferred
        2. Step 7 (equity value) - standard
        3. Step 6 (EV as equity approximation) - fallback when Step 7 fails
        4. Step 2.7 (SDE valuation) - for small owner-operated businesses
        """
        step8_output = previous_results.get(8)
        step7_output = previous_results.get(7)
        step6_output = previous_results.get(6)

        if step8_output and step8_output.status == StepStatus.COMPLETED:
            step8_result = step8_output.result
            equity_value_mid = step8_result.get("ownership_adjusted_equity_mid")
            if equity_value_mid is not None:
                return to_decimal(equity_value_mid), "Step 8 (ownership-adjusted)"

        if step7_output and step7_output.status == StepStatus.COMPLETED:
            step7_result = step7_output.result
            equity_value_mid = step7_result.get("equity_value_mid")
            if equity_value_mid is not None:
                return to_decimal(equity_value_mid), "Step 7 (equity)"

        # Fallback: Use Step 6 EV values when Step 7 fails
        if step6_output and step6_output.status == StepStatus.COMPLETED:
            step6_result = step6_output.result
            ev_mid = step6_result.get("enterprise_value_mid")
            if ev_mid is not None:
                logger.info(
                    "ℹ️ Using Step 6 EV as equity approximation (Step 7 unavailable)",
                    extra={
                        "step6_ev_mid": ev_mid,
                        "step7_status": step7_output.status.value if step7_output else "not_found",
                    },
                )
                return to_decimal(ev_mid), "Step 6 (EV approximation - Step 7 failed)"

        return None, None

    def synthesize_with_sde(
        self,
        ebitda_valuation_mid: Decimal,
        ebitda_valuation_low: Decimal,
        ebitda_valuation_high: Decimal,
        sde_valuation_mid: Optional[Decimal],
        sde_valuation_low: Optional[Decimal],
        sde_valuation_high: Optional[Decimal],
        sde_weight: Decimal = Decimal("0.0"),
    ) -> Tuple[Decimal, Decimal, Decimal, Dict[str, Any]]:
        """Compatibility wrapper for Step 11 SDE/EBITDA blend math."""
        return synthesize_with_sde_values(
            ebitda_valuation_mid=ebitda_valuation_mid,
            ebitda_valuation_low=ebitda_valuation_low,
            ebitda_valuation_high=ebitda_valuation_high,
            sde_valuation_mid=sde_valuation_mid,
            sde_valuation_low=sde_valuation_low,
            sde_valuation_high=sde_valuation_high,
            sde_weight=sde_weight,
            logger=logger,
        )

    def extract_sde_valuation(
        self, previous_results: Dict[int, Any]
    ) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal], Optional[str]]:
        """
        Extract SDE-based valuation from Step 2.7.

        SDE (Seller's Discretionary Earnings) is the standard methodology
        for small, owner-operated businesses (< EUR 2M revenue).

        Returns:
            Tuple of (sde_low, sde_mid, sde_high, methodology)
        """
        # Step 2.7 uses float key in step execution rules
        step27_output = previous_results.get(2.7)

        if step27_output and step27_output.status == StepStatus.COMPLETED:
            step27_result = step27_output.result

            sde_mid = step27_result.get("sde_valuation")
            sde_low = step27_result.get("sde_valuation_low")
            sde_high = step27_result.get("sde_valuation_high")

            if sde_mid is not None and sde_mid > 0:
                logger.debug(
                    "✅ SDE valuation extracted from Step 2.7",
                    extra={
                        "sde_mid": sde_mid,
                        "sde_low": sde_low,
                        "sde_high": sde_high,
                        "methodology": "SDE",
                    },
                )
                return (
                    to_decimal(sde_low) if sde_low is not None else None,
                    to_decimal(sde_mid),
                    to_decimal(sde_high) if sde_high is not None else None,
                    "SDE (Seller's Discretionary Earnings)",
                )

        return None, None, None, None

    def synthesize_multi_methodology(
        self,
        ebitda_low: Optional[Decimal],
        ebitda_mid: Optional[Decimal],
        ebitda_high: Optional[Decimal],
        sde_low: Optional[Decimal],
        sde_mid: Optional[Decimal],
        sde_high: Optional[Decimal],
        weights: Optional[Dict[str, Decimal]] = None,
    ) -> Tuple[Decimal, Decimal, Decimal, Dict[str, Any]]:
        """
        Synthesize valuation from multiple methodologies using weights.

        For small businesses (< EUR 2M), SDE typically gets higher weight.
        For larger businesses, EBITDA multiples get higher weight.

        If only one methodology is available, use that entirely.

        Args:
            ebitda_low: EBITDA-based valuation low
            ebitda_mid: EBITDA-based valuation mid
            ebitda_high: EBITDA-based valuation high
            sde_low: SDE-based valuation low
            sde_mid: SDE-based valuation mid
            sde_high: SDE-based valuation high
            weights: Optional weights dict (e.g., {"ebitda": 0.4, "sde": 0.6})

        Returns:
            Tuple of (synth_low, synth_mid, synth_high, synthesis_details)
        """
        synthesis_details = {
            "methodologies_used": [],
            "weights_applied": {},
            "synthesis_method": "weighted_average",
        }

        has_ebitda = ebitda_mid is not None
        has_sde = sde_mid is not None

        if has_ebitda and not has_sde:
            synthesis_details["methodologies_used"] = ["EBITDA"]
            synthesis_details["weights_applied"] = {"ebitda": 1.0}
            return (
                (ebitda_low if ebitda_low is not None else Decimal("0")),
                ebitda_mid,
                (ebitda_high if ebitda_high is not None else Decimal("0")),
                synthesis_details,
            )

        if has_sde and not has_ebitda:
            synthesis_details["methodologies_used"] = ["SDE"]
            synthesis_details["weights_applied"] = {"sde": 1.0}
            return (
                (sde_low if sde_low is not None else Decimal("0")),
                sde_mid,
                (sde_high if sde_high is not None else Decimal("0")),
                synthesis_details,
            )

        if has_ebitda and has_sde:
            # Default weights if not provided
            if not weights:
                # For similar values, use equal weights
                # For divergent values, favor the lower one (conservative)
                _max_mid = max(ebitda_mid, sde_mid)
                if _max_mid > 0 and abs(ebitda_mid - sde_mid) / _max_mid < Decimal("0.20"):
                    weights = {"ebitda": Decimal("0.50"), "sde": Decimal("0.50")}
                else:
                    # Weight the lower value slightly higher (conservative)
                    if ebitda_mid < sde_mid:
                        weights = {"ebitda": Decimal("0.55"), "sde": Decimal("0.45")}
                    else:
                        weights = {"ebitda": Decimal("0.45"), "sde": Decimal("0.55")}

            ebitda_weight = weights.get("ebitda", Decimal("0.50"))
            sde_weight = weights.get("sde", Decimal("0.50"))

            total_weight = ebitda_weight + sde_weight
            if total_weight <= 0:
                total_weight = Decimal("1.0")
                ebitda_weight = Decimal("0.50")
                sde_weight = Decimal("0.50")
            else:
                ebitda_weight = ebitda_weight / total_weight
                sde_weight = sde_weight / total_weight

            # Weighted average
            synth_mid = (ebitda_mid * ebitda_weight) + (sde_mid * sde_weight)

            # For low and high, use min/max to create full range
            all_lows = [v for v in [ebitda_low, sde_low] if v is not None]
            all_highs = [v for v in [ebitda_high, sde_high] if v is not None]

            synth_low = min(all_lows) if all_lows else synth_mid * Decimal("0.85")
            synth_high = max(all_highs) if all_highs else synth_mid * Decimal("1.15")

            synthesis_details["methodologies_used"] = ["EBITDA", "SDE"]
            synthesis_details["weights_applied"] = {
                "ebitda": float(ebitda_weight),
                "sde": float(sde_weight),
            }
            synthesis_details["individual_values"] = {
                "ebitda_mid": float(ebitda_mid),
                "sde_mid": float(sde_mid),
            }

            logger.info(
                "✅ Multi-methodology synthesis complete",
                extra={
                    "ebitda_mid": from_decimal(ebitda_mid),
                    "sde_mid": from_decimal(sde_mid),
                    "synth_mid": from_decimal(synth_mid),
                    "ebitda_weight": float(ebitda_weight),
                    "sde_weight": float(sde_weight),
                },
            )

            return synth_low, synth_mid, synth_high, synthesis_details

        # No values available
        return Decimal("0"), Decimal("0"), Decimal("0"), synthesis_details

    def _validate_and_correct_value_chain(
        self,
        valuation_low: Decimal,
        valuation_mid: Decimal,
        valuation_high: Decimal,
        equity_value_mid: Optional[Decimal],
        equity_source: Optional[str],
        step10_result: Dict[str, Any],
    ) -> Tuple[float, float, float, bool, bool]:
        """
        Validate value chain and auto-correct if needed.

        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high,
                     step10_values_preserved, value_chain_validated)
        """
        value_chain_validated = False
        step10_values_preserved = False

        if equity_value_mid is None or equity_value_mid <= 0:
            return (valuation_low, valuation_mid, valuation_high, False, False)

        settings = get_settings()
        tolerance_absolute = max(
            Decimal("0.01"), abs(equity_value_mid) * (settings.value_chain_tolerance_percent / 100)
        )
        difference = abs(valuation_mid - equity_value_mid)
        difference_percent = self.validator.safe_percentage_calculation(
            difference, equity_value_mid, Decimal("0.0")
        )

        if difference > tolerance_absolute:
            # Value chain break - auto-correct
            value_chain_breaks.labels(correction_type="step10_mismatch").inc()
            # Convert Decimal to float for Prometheus metrics (metrics require float)
            # All calculations use Decimal - conversion only for metrics export
            difference_percent_float = (
                float(difference_percent)
                if isinstance(difference_percent, Decimal)
                else float(difference_percent)
            )
            value_chain_difference.observe(difference_percent_float)

            logger.error(
                "❌ CRITICAL: Step 10 mid-point does NOT match Step 7/8 equity value - VALUE CHAIN BREAK",
                extra={
                    "step_number": 11,
                    "step10_valuation_mid": valuation_mid,
                    "step7_8_equity_value_mid": equity_value_mid,
                    "equity_source": equity_source,
                    "difference": difference,
                    "difference_percent": difference_percent,
                    "tolerance_absolute": tolerance_absolute,
                    "value_chain_broken": True,
                    "action": "Auto-correcting mid-point while preserving Step 10 spread",
                },
            )

            # Save original values
            step10_original_low = valuation_low
            step10_original_mid = valuation_mid
            step10_original_high = valuation_high

            # Auto-correct mid-point
            valuation_mid = equity_value_mid

            # Preserve Step 10's spread
            if step10_original_mid > 0:
                step10_low_spread = (
                    step10_original_mid - step10_original_low
                ) / step10_original_mid
                step10_high_spread = (
                    step10_original_high - step10_original_mid
                ) / step10_original_mid

                valuation_low = valuation_mid * (1 - step10_low_spread)
                valuation_high = valuation_mid * (1 + step10_high_spread)

                logger.warning(
                    "⚠️  Step 11: Auto-corrected valuation_mid to Step 8/7 equity_value_mid, preserved Step 10 spread",
                    extra={
                        "step_number": 11,
                        "corrected_valuation_mid": valuation_mid,
                        "corrected_valuation_low": valuation_low,
                        "corrected_valuation_high": valuation_high,
                        "step10_original_mid": step10_original_mid,
                        "step10_low_spread_pct": step10_low_spread * 100,
                        "step10_high_spread_pct": step10_high_spread * 100,
                        "value_chain_corrected": True,
                        "spread_preserved": True,
                    },
                )
        else:
            # Value chain validated - preserve all Step 10 values
            step10_values_preserved = True
            value_chain_validated = True
            logger.debug(
                "✅ Step 11: Value chain validation passed - Step 10 mid-point matches Step 7/8 equity, preserving Step 10 range",
                extra={
                    "step_number": 11,
                    "step10_valuation_low": valuation_low,
                    "step10_valuation_mid": valuation_mid,
                    "step10_valuation_high": valuation_high,
                    "step7_8_equity_value_mid": equity_value_mid,
                    "equity_source": equity_source,
                    "value_chain_validated": True,
                },
            )

        return (
            valuation_low,
            valuation_mid,
            valuation_high,
            step10_values_preserved,
            value_chain_validated,
        )

    def validate_and_fix_ordering(
        self,
        valuation_low: Decimal,
        valuation_mid: Decimal,
        valuation_high: Decimal,
        step10_values_preserved: bool,
        use_fallback: bool,
        step10_result: Optional[Dict[str, Any]],
    ) -> Tuple[float, float, float]:
        """
        Validate and fix range ordering (low <= mid <= high).

        Defense-in-depth contract
        -------------------------
        ``step10_values_preserved`` selects the *repair strategy* (use Step 10
        spread vs. fixed ±20%) but never gates whether ordering is checked.
        Callers historically used this flag as a "we already validated" hint;
        that turned out to be unsafe because intermediate stages (e.g. SDE
        cross-check) can rewrite the band without clearing the flag. We now
        always verify ``low <= mid <= high`` and only use the flag to choose
        a smarter repair when nothing's been mutated.

        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high)
        """
        # Fast path: already ordered → return unchanged regardless of caller's
        # claims. This preserves the original optimization for the common case
        # while ensuring no unordered band ever escapes this function.
        if valuation_low <= valuation_mid <= valuation_high:
            return (valuation_low, valuation_mid, valuation_high)

        original_low = valuation_low
        original_high = valuation_high

        def sane_spread(
            spread: Decimal,
            default: Decimal,
            bound_name: str,
        ) -> Decimal:
            """Use a Step 10 spread only if it would repair ordering."""
            max_spread = Decimal("0.95") if bound_name == "low" else Decimal("2.5")
            if Decimal("0") < spread <= max_spread:
                return spread
            logger.warning(
                "Ignored invalid Step 10 spread while repairing range ordering",
                extra={
                    "step_number": 11,
                    "bound": bound_name,
                    "invalid_spread": str(spread),
                    "fallback_spread": str(default),
                },
            )
            return default

        # Fix low > mid
        if valuation_low > valuation_mid:
            if not use_fallback and step10_result:
                _s10_mid = step10_result.get("valuation_mid")
                step10_original_mid = _s10_mid if _s10_mid is not None else 0
                _s10_low = step10_result.get("valuation_low")
                step10_original_low = _s10_low if _s10_low is not None else 0
                if step10_original_mid > 0:
                    step10_low_spread = (
                        step10_original_mid - step10_original_low
                    ) / step10_original_mid
                    step10_low_spread = sane_spread(
                        to_decimal(step10_low_spread),
                        Decimal("0.2"),
                        "low",
                    )
                    valuation_low = valuation_mid * (1 - step10_low_spread)
                    logger.warning(
                        "Invalid range ordering (low > mid), adjusted low using Step 10 spread",
                        extra={
                            "original_low": original_low,
                            "adjusted_low": valuation_low,
                            "step10_spread_used": step10_low_spread,
                        },
                    )
                else:
                    valuation_low = valuation_mid * Decimal("0.8")
                    logger.warning(
                        "Invalid range ordering (low > mid), adjusted low value",
                        extra={"original_low": original_low, "adjusted_low": valuation_low},
                    )
            else:
                valuation_low = valuation_mid * Decimal("0.8")
                logger.warning(
                    "Invalid range ordering (low > mid), adjusted low value",
                    extra={"original_low": original_low, "adjusted_low": valuation_low},
                )

        # Fix high < mid
        if valuation_high < valuation_mid:
            if not use_fallback and step10_result:
                _s10_mid_h = step10_result.get("valuation_mid")
                step10_original_mid = _s10_mid_h if _s10_mid_h is not None else 0
                _s10_high = step10_result.get("valuation_high")
                step10_original_high = _s10_high if _s10_high is not None else 0
                if step10_original_mid > 0:
                    step10_high_spread = (
                        step10_original_high - step10_original_mid
                    ) / step10_original_mid
                    step10_high_spread = sane_spread(
                        to_decimal(step10_high_spread),
                        Decimal("0.2"),
                        "high",
                    )
                    valuation_high = valuation_mid * (1 + step10_high_spread)
                    logger.warning(
                        "Invalid range ordering (high < mid), adjusted high using Step 10 spread",
                        extra={
                            "original_high": original_high,
                            "adjusted_high": valuation_high,
                            "step10_spread_used": step10_high_spread,
                        },
                    )
                else:
                    valuation_high = valuation_mid * Decimal("1.2")
                    logger.warning(
                        "Invalid range ordering (high < mid), adjusted high value",
                        extra={"original_high": original_high, "adjusted_high": valuation_high},
                    )
            else:
                valuation_high = valuation_mid * Decimal("1.2")
                logger.warning(
                    "Invalid range ordering (high < mid), adjusted high value",
                    extra={"original_high": original_high, "adjusted_high": valuation_high},
                )

        valuation_low, valuation_mid, valuation_high, widened = coerce_equity_range_triple(
            valuation_low,
            valuation_mid,
            valuation_high,
        )
        if widened:
            logger.warning(
                "Step 11 ordering repair widened bounds after spread-based correction",
                extra={
                    "step_number": 11,
                    "valuation_low": str(valuation_low),
                    "valuation_mid": str(valuation_mid),
                    "valuation_high": str(valuation_high),
                },
            )

        return (valuation_low, valuation_mid, valuation_high)

    @staticmethod
    def _granularity_for(value: Decimal) -> Decimal:
        """Compatibility wrapper for Step 11 rounding granularity tests."""
        return granularity_for(value)

    def apply_rounding(
        self,
        valuation_low: Decimal,
        valuation_mid: Decimal,
        valuation_high: Decimal,
        equity_value_mid: Optional[Decimal],
    ) -> Tuple[float, float, float, Dict[str, Any]]:
        """
        Apply rounding to valuation values.

        Invariant guarantee:
            ``valuation_low_rounded <= valuation_mid_rounded <= valuation_high_rounded``
            *always* holds after this call (assuming a non-degenerate input
            range). The mid-point is preserved at full precision; low/high are
            rounded to the appropriate granularity but clamped so banker-style
            rounding can never push low above mid or high below mid.

            This invariant matters because :meth:`apply_rounding` is the last
            mutation Step 11 makes to the band before it is written into
            ``detailed_results``, where the downstream
            ``ValuationValidator._validate_range`` enforces strict ordering and
            returns 422 on violation. See the photography (€48k–€82.9k with
            mid €42,430.75) regression — that case proved that "round
            low/high, preserve mid exact" is unsafe whenever an upstream
            rewrite (e.g. SDE blend) leaves mid below the rounded low.

        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high, rounding_details)
        """
        return apply_synthesis_rounding(
            range_calculator=self.range_calculator,
            validator=self.validator,
            valuation_low=valuation_low,
            valuation_mid=valuation_mid,
            valuation_high=valuation_high,
            equity_value_mid=equity_value_mid,
            ordering_clamps_total=ordering_clamps_total,
        )
