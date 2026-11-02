"""
Owner Dependency Coordinator

Handles owner dependency adjustment logic.
Extracted from synthesizer.py to improve modularity.

DORMANCY NOTE (OWNER-PROFILING-1, 2026-04-30):
This coordinator is NOT on the live request path. The synthesizer
instantiates it but never calls it; the live owner-dependency math runs
through `OwnerDependencyProcessor.process_owner_dependency` at the
synthesizer boundary instead. The coordinator stays here as a future-
proof shim — if any caller ever wires it back, the MVP cap is applied
inside `apply_owner_dependency_adjustment` so the resulting
`SynthesizedValuation` cannot violate the Pydantic floor on
`owner_dependency_adjustment`. Defense in depth, not active behavior.
"""

from decimal import Decimal
from typing import Any

from src.domain.models import SynthesizedValuation
from src.domain.synthesis.owner_dependency_processor import _apply_mvp_cap
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import CalculationError, DataQualityError
from src.errors.error_types import DomainError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OwnerDependencyCoordinator:
    """
    Coordinates owner dependency adjustment logic.
    
    Responsibilities:
    - Apply owner dependency adjustments
    - Handle adjustment failures gracefully
    - Log adjustment details
    """
    
    def __init__(self):
        """Initialize owner dependency coordinator."""
        self.logger = logger
    
    def apply_owner_dependency_adjustment(
        self, valuation: SynthesizedValuation, dependency_score: Decimal, adjustment_factor: Decimal
    ) -> SynthesizedValuation:
        """
        Apply owner dependency adjustment to valuation.
        
        Args:
            valuation: Original valuation result
            dependency_score: Owner dependency score (Decimal('0.0') to Decimal('1.0'))
            adjustment_factor: Adjustment factor (-Decimal('0.4') to Decimal('0.0'))
            
        Returns:
            Adjusted valuation with owner dependency impact
        """
        try:
            dependency_score_decimal = to_decimal(dependency_score)
            # MVP cap inside the dormant coordinator (defense in depth) —
            # caller may pass the engine's raw figure (-0.40..0.00); we
            # narrow it here so the SynthesizedValuation Pydantic Field
            # (bound to MVP_OWNER_ADJUSTMENT_FLOOR) cannot reject the
            # construction. If the cap relaxes, the constant in
            # `src.domain.models` updates and this site tracks
            # automatically via `_apply_mvp_cap`.
            raw_adjustment_decimal = to_decimal(adjustment_factor)
            adjustment_factor_decimal = _apply_mvp_cap(raw_adjustment_decimal)

            self.logger.info(
                "Applying owner dependency adjustment",
                dependency_score=from_decimal(dependency_score_decimal),
                raw_adjustment_factor=from_decimal(raw_adjustment_decimal),
                applied_adjustment_factor=from_decimal(adjustment_factor_decimal),
            )

            # Convert to Decimal for calculations
            equity_low_decimal = to_decimal(valuation.equity_value_low)
            equity_mid_decimal = to_decimal(valuation.equity_value_mid)
            equity_high_decimal = to_decimal(valuation.equity_value_high)

            # Apply adjustment to equity values
            adjusted_equity_low_decimal = equity_low_decimal * (
                Decimal("1") + adjustment_factor_decimal
            )
            adjusted_equity_mid_decimal = equity_mid_decimal * (
                Decimal("1") + adjustment_factor_decimal
            )
            adjusted_equity_high_decimal = equity_high_decimal * (
                Decimal("1") + adjustment_factor_decimal
            )
            
            adjusted_equity_low = from_decimal(adjusted_equity_low_decimal)
            adjusted_equity_mid = from_decimal(adjusted_equity_mid_decimal)
            adjusted_equity_high = from_decimal(adjusted_equity_high_decimal)
            
            # Create adjusted valuation
            adjusted_valuation = SynthesizedValuation(
                # Original values
                equity_value_low=adjusted_equity_low,
                equity_value_mid=adjusted_equity_mid,
                equity_value_high=adjusted_equity_high,
                # Keep other values from original
                dcf_result=valuation.dcf_result,
                multiples_result=valuation.multiples_result,
                confidence_level=valuation.confidence_level,
                methodology_weights=valuation.methodology_weights,
                key_value_drivers=valuation.key_value_drivers,
                risk_factors=valuation.risk_factors,
                recommendations=valuation.recommendations,
                # Add owner dependency metadata
                owner_dependency_adjustment=from_decimal(adjustment_factor_decimal),
                owner_dependency_score=from_decimal(dependency_score_decimal),
                original_equity_value_mid=valuation.equity_value_mid,
                adjustment_reason=f"Owner dependency adjustment: {from_decimal(abs(adjustment_factor_decimal) * Decimal('100'), precision=0):.0f}% reduction due to key person risk",
            )
            
            self.logger.info(
                "Owner dependency adjustment applied",
                original_value=valuation.equity_value_mid,
                adjusted_value=adjusted_equity_mid,
                adjustment_percentage=from_decimal(abs(adjustment_factor_decimal) * Decimal("100")),
            )
            
            return adjusted_valuation
        
        except (CalculationError, DataQualityError, DomainError):
            raise  # Re-raise specific errors
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            self.logger.error(
                "Failed to apply owner dependency adjustment",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            # Return original valuation if adjustment fails
            return valuation

