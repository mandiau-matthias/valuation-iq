"""
Owner Dependency Processor

Extracted from synthesizer.py to reduce complexity.
Handles owner dependency assessment and adjustment.

OWNER-PROFILING-1 (BET-180) MVP — see docs/product/features/active-development/owner-profiling-mvp.md
This module is the single source of truth for owner-profiling adjustment math.
The legacy `stateless_router._calculate_owner_adjustment` shim returns 0.0 to
prevent double-application; do not re-introduce it.
"""

from decimal import Decimal
from typing import Any, List, Optional, Tuple

from src.domain.models import (
    FinancialData,
    MVP_OWNER_ADJUSTMENT_CEILING,
    MVP_OWNER_ADJUSTMENT_FLOOR,
)
from src.utils.decimal_helpers import to_decimal, bank_round
from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    DomainError,
    SynthesisError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


# OWNER-PROFILING-1 MVP cap (SPIKE-1 §3.2). The constants live in
# `src.domain.models` so the Pydantic field on `SynthesizedValuation` can
# bind to the same values; we re-export here for back-compat with callers
# that still import from this module. New code should prefer the canonical
# location: `from src.domain.models import MVP_OWNER_ADJUSTMENT_FLOOR`.
__all__ = [
    "MVP_OWNER_ADJUSTMENT_FLOOR",
    "MVP_OWNER_ADJUSTMENT_CEILING",
    "OwnerDependencyProcessor",
    "_apply_mvp_cap",
]


def _apply_mvp_cap(raw_adjustment: Decimal) -> Decimal:
    """Clamp the engine's raw adjustment into the MVP-launch band.

    Pure function so the cap can be exercised in isolation by unit tests
    without instantiating an engine or supplying financial data.

    Band rationale (see `src.domain.models` constants header):
      - FLOOR (-0.15) is an MVP-launch underclaim of the engine's true
        -0.40 floor. Relax once ≥10 attributed deals validate the wider
        range; relaxation requires a Titan migration to update the CHECK
        on `owner_profile_assessment.applied_adjustment` in lockstep.
      - CEILING (0.00) is structural, not an underclaim. The Damodaran
        12-factor engine is a discount model — strong owner profiling
        reduces the haircut toward zero, never adds an uplift. Raising
        the ceiling requires a different engine, not a config change.
    """
    return max(
        MVP_OWNER_ADJUSTMENT_FLOOR,
        min(MVP_OWNER_ADJUSTMENT_CEILING, to_decimal(raw_adjustment)),
    )


class OwnerDependencyProcessor:
    """Processes owner dependency assessment and adjustments."""

    def __init__(self, financial_data: FinancialData, transparency_collector: Any):
        self.financial_data = financial_data
        self.transparency_collector = transparency_collector

    def process_owner_dependency(
        self,
        owner_dependency_factors: Optional[Any],
        equity_value_low: Decimal,
        equity_value_mid: Decimal,
        equity_value_high: Decimal,
        recommended_asking_price: Decimal,
        risk_factors: List[str],
        *,
        owner_hours_per_week: Optional[int] = None,
        eligible_methods: Optional[List[Any]] = None,
        composite_transferability_index: Optional[float] = None,
        owner_count: int = 1,
    ) -> Tuple[
        Optional[Any], Decimal, Decimal, Decimal, Decimal, Decimal, List[str]
    ]:
        """
        Process owner dependency assessment and apply adjustments.

        Returns:
            Tuple of (owner_dependency_result, owner_dependency_adjustment,
                     adjusted_equity_value_low, adjusted_equity_value_mid,
                     adjusted_equity_value_high, adjusted_recommended_asking_price,
                     updated_risk_factors)
        """
        owner_dependency_result = None
        owner_dependency_adjustment = Decimal("0.0")

        if not owner_dependency_factors:
            return (
                None,
                Decimal("0.0"),
                equity_value_low,
                equity_value_mid,
                equity_value_high,
                recommended_asking_price,
                risk_factors,
            )

        logger.info("Calculating owner dependency assessment")

        try:
            from src.domain.owner_dependency_engine import OwnerDependencyEngine

            od_engine = OwnerDependencyEngine(self.financial_data, self.transparency_collector)
            # Forward equity baseline + owner-hours so the engine can build
            # the v2 transferability profile (additive metadata; never
            # affects the headline adjustment).
            normalized_methods: Optional[List[str]] = None
            if eligible_methods:
                normalized_methods = [
                    str(m) for m in eligible_methods if m is not None
                ]
            owner_dependency_result = od_engine.calculate_dependency_score(
                owner_dependency_factors,
                equity_value_mid=to_decimal(equity_value_mid),
                owner_hours_per_week=owner_hours_per_week,
                eligible_methods=normalized_methods,
                # BET-218 — multi-owner composite passthrough. None for
                # single-owner callers; the engine no-ops on the default.
                composite_transferability_index=composite_transferability_index,
                owner_count=owner_count,
            )

            # MVP cap (SPIKE-1 §3.2). Preserve the unclamped figure on the
            # result for analytics, then narrow what flows downstream so the
            # adjustment we ship to clients can be defended on every deal.
            raw_adjustment = owner_dependency_result.valuation_adjustment
            owner_dependency_adjustment = _apply_mvp_cap(raw_adjustment)
            owner_dependency_result.raw_adjustment = raw_adjustment
            owner_dependency_result.valuation_adjustment = owner_dependency_adjustment

            # Re-stamp the v2 cascade with post-cap numbers so the report
            # shows the binding cap explicitly: line 4 reads "applied
            # -15.0% (engine wanted -32.0%)". The engine emits the cascade
            # against its pre-cap figure; the processor knows the cap and
            # is the right place to write the truth.
            tp = getattr(owner_dependency_result, "transferability_profile", None)
            if tp is not None:
                try:
                    from src.domain.owner_models.transferability import (
                        build_cascade_data,
                        build_narrative_cascade,
                        method_incidence_table,
                        blended_incidence,
                        derive_confidence_tier,
                    )

                    tp.method_incidence = method_incidence_table(
                        owner_dependency_adjustment
                    )
                    tp.blended_applied_pct = blended_incidence(
                        owner_dependency_adjustment, normalized_methods
                    )
                    tp.narrative_cascade = build_narrative_cascade(
                        decomposition=tp.decomposition,
                        buyer_profile=tp.buyer_profile,
                        gap=tp.gap,
                        headline_adjustment_pct=owner_dependency_adjustment,
                        raw_engine_adjustment_pct=raw_adjustment,
                        eligible_methods=normalized_methods,
                    )
                    # Structured cascade data for the locale-aware renderer.
                    tp.cascade_data = build_cascade_data(
                        decomposition=tp.decomposition,
                        buyer_profile=tp.buyer_profile,
                        gap=tp.gap,
                        headline_adjustment_pct=owner_dependency_adjustment,
                        raw_engine_adjustment_pct=raw_adjustment,
                        eligible_methods=normalized_methods,
                    )
                    # Re-derive confidence with the *post-cap* state. The
                    # engine's first pass thinks cap_binding=False because
                    # raw == headline at engine output; only the processor
                    # knows whether the cap actually clamped the figure.
                    tp.confidence = derive_confidence_tier(
                        tp.decomposition,
                        owner_hours_supplied=owner_hours_per_week is not None,
                        cap_binding=(
                            to_decimal(raw_adjustment)
                            < to_decimal(owner_dependency_adjustment)
                        ),
                    )
                except (ValueError, TypeError, AttributeError, KeyError) as exc:
                    logger.warning(
                        "Transferability v2 cascade re-stamp failed; engine cascade kept",
                        extra={"error": str(exc), "error_type": type(exc).__name__},
                    )

            if owner_dependency_adjustment != raw_adjustment:
                logger.info(
                    "Owner dependency MVP cap applied",
                    extra={
                        "raw_adjustment": f"{raw_adjustment:.4f}",
                        "applied_adjustment": f"{owner_dependency_adjustment:.4f}",
                        "cap_floor": f"{MVP_OWNER_ADJUSTMENT_FLOOR:.4f}",
                    },
                )

            # Apply (capped) adjustment to equity values
            adjustment_factor = Decimal("1") + to_decimal(owner_dependency_adjustment)
            adjusted_equity_value_low = to_decimal(equity_value_low) * adjustment_factor
            adjusted_equity_value_mid = to_decimal(equity_value_mid) * adjustment_factor
            adjusted_equity_value_high = to_decimal(equity_value_high) * adjustment_factor
            
            # Calculate raw adjusted asking price
            raw_adjusted_asking_price = (
                to_decimal(recommended_asking_price) * adjustment_factor
            )
            
            # Re-round to nearest 1,000 for professional presentation (clean numbers)
            # Using 1,000 instead of 10,000 here to preserve some granularity from the adjustment
            adjusted_recommended_asking_price = bank_round(raw_adjusted_asking_price / Decimal("1000"), 0) * Decimal("1000")

            logger.info(
                "Owner dependency assessment complete",
                overall_score=owner_dependency_result.overall_score,
                risk_level=owner_dependency_result.risk_level,
                adjustment=f"{owner_dependency_adjustment:.1%}",
                adjusted_mid=f"\u20AC{adjusted_equity_value_mid:,.0f}",
            )

            # Add to risk factors if the engine's *raw* adjustment is at or
            # past the MVP cap (i.e. true dependency is significant, even if
            # the headline number was clamped). Using the capped figure here
            # would silently suppress the warning for exactly the businesses
            # that need it, since `capped == FLOOR` and the original `<`
            # comparison is strict. SPIKE-1 §3.2 explicitly aligns the
            # threshold with the cap so the report's "significant discount"
            # framing always fires when the cap binds.
            if to_decimal(raw_adjustment) <= MVP_OWNER_ADJUSTMENT_FLOOR:
                risk_factors.insert(
                    0,
                    f"Owner Dependency: {owner_dependency_result.risk_level} risk ({abs(owner_dependency_adjustment):.0%} valuation discount)",
                )

            return (
                owner_dependency_result,
                owner_dependency_adjustment,
                adjusted_equity_value_low,
                adjusted_equity_value_mid,
                adjusted_equity_value_high,
                adjusted_recommended_asking_price,
                risk_factors,
            )

        except (CalculationError, DataQualityError, DomainError):
            # Re-raise specific errors
            raise
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(
                "Owner dependency assessment failed",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            # Continue without owner dependency assessment
            return (
                None,
                Decimal("0.0"),
                equity_value_low,
                equity_value_mid,
                equity_value_high,
                recommended_asking_price,
                risk_factors,
            )
        except SynthesisError as e:
            logger.error(
                "Unexpected error in owner dependency assessment",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            # Continue without owner dependency assessment
            return (
                None,
                Decimal("0.0"),
                equity_value_low,
                equity_value_mid,
                equity_value_high,
                recommended_asking_price,
                risk_factors,
            )

