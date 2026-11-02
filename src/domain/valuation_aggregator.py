"""
Valuation Aggregator

Aggregates DCF and Multiples valuation results using calculated weights.
Handles three cases:
1. Multiples-only (DCF excluded)
2. Hybrid with Multiples primary
3. Hybrid with DCF primary

Properly extracts values from different result formats and applies weighted averaging.

@author UpSwitch CTO Team
@version 1.0.0
@date November 2025
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.domain.hybrid_types import (
    AggregatedValuation,
    MethodologyDecision,
    WeightResult,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _first_present(values: Dict[str, Any], *keys: str) -> Any:
    """Return the first non-None value, preserving explicit zeros."""
    for key in keys:
        if key in values and values[key] is not None:
            return values[key]
    return None


class ValuationAggregator:
    """
    Aggregates DCF and Multiples valuation results.

    Responsibilities:
    - Extract equity values from different result formats
    - Apply weighted averaging for hybrid methodology
    - Handle Multiples-only case (DCF excluded)
    - Preserve component results for transparency
    """

    def __init__(self):
        self.logger = get_logger(__name__)

    def aggregate_results(
        self,
        dcf_result: Optional[Dict[str, Any]],
        multiples_result: Dict[str, Any],
        weights: WeightResult,
        methodology_decision: MethodologyDecision,
    ) -> AggregatedValuation:
        """
        Aggregate DCF and Multiples results into final valuation.

        Args:
            dcf_result: DCF calculation result (None if excluded)
            multiples_result: Multiples calculation result (required)
            weights: Calculated DCF/Multiples weights
            methodology_decision: Methodology eligibility decision

        Returns:
            AggregatedValuation with weighted results
        """
        self.logger.info(
            "🎯 Starting valuation aggregation",
            extra={
                "methodology": methodology_decision.value,
                "dcf_weight": weights.dcf_weight,
                "multiples_weight": weights.multiples_weight,
                "has_dcf": dcf_result is not None,
                "weights_source": weights.source,
            },
        )

        warnings = []

        # Extract values based on methodology
        if methodology_decision == MethodologyDecision.MULTIPLES_ONLY:
            # Case 1: Multiples-only (DCF excluded)
            self.logger.debug(
                "📊 Aggregating Multiples-only valuation",
                extra={
                    "case": "Multiples-only (DCF excluded)",
                    "dcf_weight": Decimal("0.0"),
                    "multiples_weight": Decimal("1.0"),
                },
            )
            aggregated = self._aggregate_multiples_only(multiples_result, weights)
        else:
            # Case 2 & 3: Hybrid (with DCF)
            if dcf_result is None:
                self.logger.warning(
                    "⚠️  DCF expected but result is None, falling back to Multiples-only",
                    extra={
                        "methodology": methodology_decision.value,
                        "expected_dcf": True,
                        "dcf_result_available": False,
                        "fallback": "Multiples-only",
                    },
                )
                warnings.append("DCF calculation failed, using Multiples-only")
                aggregated = self._aggregate_multiples_only(multiples_result, weights)
            else:
                self.logger.debug(
                    "📊 Aggregating Hybrid valuation",
                    extra={
                        "case": "Hybrid (DCF + Multiples)",
                        "dcf_weight": weights.dcf_weight,
                        "multiples_weight": weights.multiples_weight,
                        "methodology": methodology_decision.value,
                    },
                )
                aggregated = self._aggregate_hybrid(
                    dcf_result, multiples_result, weights, methodology_decision
                )

        # Add warnings
        aggregated.warnings.extend(warnings)

        # Add metadata
        aggregated.calculation_timestamp = datetime.now(timezone.utc).isoformat()

        self.logger.info(
            "✅ Valuation aggregation complete",
            extra={
                "equity_value": aggregated.equity_value,
                "equity_value_low": aggregated.equity_value_low,
                "equity_value_high": aggregated.equity_value_high,
                "methodology": aggregated.methodology,
                "weights_source": weights.source,
                "warnings_count": len(aggregated.warnings),
                "calculation_timestamp": aggregated.calculation_timestamp,
            },
        )

        return aggregated

    def _aggregate_multiples_only(
        self, multiples_result: Dict[str, Any], weights: WeightResult
    ) -> AggregatedValuation:
        """
        Aggregate Multiples-only valuation (DCF excluded).

        Uses adjusted_equity_value from Multiples (includes all adjustments:
        size discount, liquidity discount, owner concentration, etc.)
        """
        self.logger.info("📊 Multiples-only aggregation")

        _adj_eq = multiples_result.get("adjusted_equity_value")
        _mid_eq = multiples_result.get("equity_value_mid")
        equity_value = _adj_eq if _adj_eq is not None else (_mid_eq if _mid_eq is not None else multiples_result.get("equity_value", 0))

        equity_value_low = multiples_result.get("equity_value_low")
        equity_value_high = multiples_result.get("equity_value_high")

        _ev = multiples_result.get("enterprise_value")
        enterprise_value = _ev if _ev is not None else multiples_result.get("enterprise_value_mid", 0)
        enterprise_value_low = multiples_result.get("enterprise_value_low")
        enterprise_value_high = multiples_result.get("enterprise_value_high")

        # Extract confidence and range methodology
        confidence_score = multiples_result.get("confidence_score")
        range_methodology = multiples_result.get("range_methodology")

        return AggregatedValuation(
            equity_value=equity_value,
            equity_value_low=equity_value_low,
            equity_value_high=equity_value_high,
            enterprise_value=enterprise_value,
            enterprise_value_low=enterprise_value_low,
            enterprise_value_high=enterprise_value_high,
            methodology="multiples_only",
            weights=weights,
            component_results={"multiples": multiples_result, "dcf": None},
            confidence_score=confidence_score,
            range_methodology=range_methodology,
        )

    def _aggregate_hybrid(
        self,
        dcf_result: Dict[str, Any],
        multiples_result: Dict[str, Any],
        weights: WeightResult,
        methodology_decision: MethodologyDecision,
    ) -> AggregatedValuation:
        """
        Aggregate hybrid valuation (DCF + Multiples weighted average).

        Applies weighted averaging to both point estimates and ranges.
        """
        self.logger.info(
            "📊 Hybrid aggregation",
            extra={"dcf_weight": weights.dcf_weight, "multiples_weight": weights.multiples_weight},
        )

        # Extract DCF values
        dcf_equity = dcf_result.get("equity_value", 0)
        dcf_equity_low = dcf_result.get("equity_value_low")
        dcf_equity_high = dcf_result.get("equity_value_high")

        _adj_eq = multiples_result.get("adjusted_equity_value")
        _mid_eq = multiples_result.get("equity_value_mid")
        multiples_equity = _adj_eq if _adj_eq is not None else (_mid_eq if _mid_eq is not None else multiples_result.get("equity_value", 0))
        multiples_equity_low = multiples_result.get("equity_value_low")
        multiples_equity_high = multiples_result.get("equity_value_high")

        # Convert to Decimal for calculations
        dcf_equity_decimal = to_decimal(dcf_equity)
        multiples_equity_decimal = to_decimal(multiples_equity)
        dcf_weight_decimal = to_decimal(weights.dcf_weight)
        multiples_weight_decimal = to_decimal(weights.multiples_weight)

        # Calculate weighted average for mid-point
        equity_value_decimal = (dcf_equity_decimal * dcf_weight_decimal) + (
            multiples_equity_decimal * multiples_weight_decimal
        )
        equity_value = from_decimal(equity_value_decimal)

        # Calculate weighted average for low/high if available
        equity_value_low = None
        equity_value_high = None

        if dcf_equity_low is not None and multiples_equity_low is not None:
            dcf_equity_low_decimal = to_decimal(dcf_equity_low)
            multiples_equity_low_decimal = to_decimal(multiples_equity_low)
            equity_value_low_decimal = (dcf_equity_low_decimal * dcf_weight_decimal) + (
                multiples_equity_low_decimal * multiples_weight_decimal
            )
            equity_value_low = from_decimal(equity_value_low_decimal)

        if dcf_equity_high is not None and multiples_equity_high is not None:
            dcf_equity_high_decimal = to_decimal(dcf_equity_high)
            multiples_equity_high_decimal = to_decimal(multiples_equity_high)
            equity_value_high_decimal = (dcf_equity_high_decimal * dcf_weight_decimal) + (
                multiples_equity_high_decimal * multiples_weight_decimal
            )
            equity_value_high = from_decimal(equity_value_high_decimal)

        # Extract enterprise values
        dcf_ev = dcf_result.get("enterprise_value", 0)
        _m_ev = multiples_result.get("enterprise_value")
        multiples_ev = _m_ev if _m_ev is not None else multiples_result.get("enterprise_value_mid", 0)

        dcf_ev_decimal = to_decimal(dcf_ev)
        multiples_ev_decimal = to_decimal(multiples_ev)
        enterprise_value_decimal = (dcf_ev_decimal * dcf_weight_decimal) + (
            multiples_ev_decimal * multiples_weight_decimal
        )
        enterprise_value = from_decimal(enterprise_value_decimal)

        # Calculate EV ranges if available
        dcf_ev_low = dcf_result.get("enterprise_value_low")
        dcf_ev_high = dcf_result.get("enterprise_value_high")
        multiples_ev_low = multiples_result.get("enterprise_value_low")
        multiples_ev_high = multiples_result.get("enterprise_value_high")

        enterprise_value_low = None
        enterprise_value_high = None

        if dcf_ev_low is not None and multiples_ev_low is not None:
            dcf_ev_low_decimal = to_decimal(dcf_ev_low)
            multiples_ev_low_decimal = to_decimal(multiples_ev_low)
            enterprise_value_low_decimal = (dcf_ev_low_decimal * dcf_weight_decimal) + (
                multiples_ev_low_decimal * multiples_weight_decimal
            )
            enterprise_value_low = from_decimal(enterprise_value_low_decimal)

        if dcf_ev_high is not None and multiples_ev_high is not None:
            dcf_ev_high_decimal = to_decimal(dcf_ev_high)
            multiples_ev_high_decimal = to_decimal(multiples_ev_high)
            enterprise_value_high_decimal = (dcf_ev_high_decimal * dcf_weight_decimal) + (
                multiples_ev_high_decimal * multiples_weight_decimal
            )
            enterprise_value_high = from_decimal(enterprise_value_high_decimal)

        # Average confidence scores if both available
        dcf_confidence = dcf_result.get("confidence_score")
        multiples_confidence = multiples_result.get("confidence_score")

        confidence_score = None
        if dcf_confidence is not None and multiples_confidence is not None:
            dcf_confidence_decimal = to_decimal(dcf_confidence)
            multiples_confidence_decimal = to_decimal(multiples_confidence)
            confidence_score_decimal = (dcf_confidence_decimal * dcf_weight_decimal) + (
                multiples_confidence_decimal * multiples_weight_decimal
            )
            confidence_score = from_decimal(confidence_score_decimal)
        elif multiples_confidence is not None:
            confidence_score = multiples_confidence
        elif dcf_confidence is not None:
            confidence_score = dcf_confidence

        # Determine range methodology (prefer DCF's if primary)
        if methodology_decision == MethodologyDecision.HYBRID_DCF_PRIMARY:
            range_methodology = dcf_result.get("range_methodology") or multiples_result.get(
                "range_methodology"
            )
        else:
            range_methodology = multiples_result.get("range_methodology") or dcf_result.get(
                "range_methodology"
            )

        # Log component values for transparency
        self.logger.info(
            "📊 Weighted average calculation",
            extra={
                "dcf_equity": dcf_equity,
                "dcf_weight": weights.dcf_weight,
                "multiples_equity": multiples_equity,
                "multiples_weight": weights.multiples_weight,
                "final_equity": equity_value,
                "methodology": methodology_decision.value,
            },
        )

        return AggregatedValuation(
            equity_value=equity_value,
            equity_value_low=equity_value_low,
            equity_value_high=equity_value_high,
            enterprise_value=enterprise_value,
            enterprise_value_low=enterprise_value_low,
            enterprise_value_high=enterprise_value_high,
            methodology=methodology_decision.value,
            weights=weights,
            component_results={"dcf": dcf_result, "multiples": multiples_result},
            confidence_score=confidence_score,
            range_methodology=range_methodology,
        )

    def extract_detailed_breakdown(self, aggregated: AggregatedValuation) -> Dict[str, Any]:
        """
        Extract detailed breakdown for transparency.

        Args:
            aggregated: Aggregated valuation result

        Returns:
            Dictionary with component breakdowns
        """
        breakdown = {
            "final_values": {
                "equity_value": aggregated.equity_value,
                "equity_value_low": aggregated.equity_value_low,
                "equity_value_high": aggregated.equity_value_high,
                "enterprise_value": aggregated.enterprise_value,
            },
            "methodology": aggregated.methodology,
            "weights": {
                "dcf": aggregated.weights.dcf_weight if aggregated.weights else None,
                "multiples": aggregated.weights.multiples_weight if aggregated.weights else None,
                "source": aggregated.weights.source if aggregated.weights else None,
                "rationale": aggregated.weights.rationale if aggregated.weights else None,
            },
            "components": {},
        }

        # Add DCF component if available
        if aggregated.component_results.get("dcf"):
            dcf = aggregated.component_results["dcf"]
            breakdown["components"]["dcf"] = {
                "equity_value": dcf.get("equity_value"),
                "enterprise_value": dcf.get("enterprise_value"),
                "confidence_score": dcf.get("confidence_score"),
            }

        # Add Multiples component
        if aggregated.component_results.get("multiples"):
            multiples = aggregated.component_results["multiples"]
            breakdown["components"]["multiples"] = {
                "equity_value": _first_present(
                    multiples,
                    "adjusted_equity_value",
                    "equity_value_mid",
                    "equity_value",
                ),
                "enterprise_value": _first_present(
                    multiples,
                    "enterprise_value",
                    "enterprise_value_mid",
                ),
                "confidence_score": multiples.get("confidence_score"),
            }

        return breakdown
