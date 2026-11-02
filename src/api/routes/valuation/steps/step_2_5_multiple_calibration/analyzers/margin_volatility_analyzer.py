"""
Margin Volatility Analyzer

Detects EBITDA margin volatility and estimates one-time expenses.
Academic Source: Hitchner (2017), Quality of Earnings analysis
"""

import statistics
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MarginVolatilityAnalyzer:
    """
    Analyzes EBITDA margin patterns to detect:
    1. Margin volatility (quality of earnings issue)
    2. One-time expenses that should be added back
    3. Normalized margin estimates
    """

    # Volatility thresholds (percentage points)
    HIGH_VOLATILITY_THRESHOLD = Decimal("5.0")  # 5pp stdev
    MEDIUM_VOLATILITY_THRESHOLD = Decimal("3.0")  # 3pp stdev

    # Margin collapse thresholds
    MARGIN_COLLAPSE_THRESHOLD = Decimal("-10.0")  # -10pp drop YoY

    def analyze_margin_pattern(
        self, current_ebitda: Decimal, current_revenue: Decimal, historical_data: List[Any]
    ) -> Dict[str, Any]:
        """
        Analyze EBITDA margin pattern across years.

        Args:
            current_ebitda: Current year EBITDA
            current_revenue: Current year revenue
            historical_data: List of historical year data (with revenue, ebitda attrs)

        Returns:
            Analysis results including volatility, normalized margin, and adjustments
        """
        current_margin = (
            (current_ebitda / current_revenue * 100) if current_revenue > 0 else Decimal("0")
        )

        # Extract historical margins
        margins = [current_margin]
        revenues = [current_revenue]
        ebitdas = [current_ebitda]

        for year_data in historical_data:
            revenue = to_decimal(getattr(year_data, "revenue", 0))
            ebitda = to_decimal(getattr(year_data, "ebitda", 0))
            if revenue > 0:
                margin = ebitda / revenue * 100
                margins.append(margin)
                revenues.append(revenue)
                ebitdas.append(ebitda)

        if len(margins) < 2:
            logger.info(
                "Insufficient data for margin volatility analysis (need 2+ years)",
                extra={"years_available": len(margins)},
            )
            return self._create_default_result(current_margin, current_ebitda, current_revenue)

        # Calculate volatility metrics
        margin_floats = [float(m) for m in margins]
        avg_margin = Decimal(str(statistics.mean(margin_floats)))
        margin_stdev = (
            Decimal(str(statistics.stdev(margin_floats)))
            if len(margin_floats) > 1
            else Decimal("0")
        )

        # Detect margin collapse (YoY)
        if len(margins) >= 2:
            margin_change_yoy = margins[0] - margins[1]  # Current - Previous
        else:
            margin_change_yoy = Decimal("0")

        # Classify volatility
        if margin_stdev > self.HIGH_VOLATILITY_THRESHOLD:
            volatility_level = "HIGH"
            qoe_flag = True
        elif margin_stdev > self.MEDIUM_VOLATILITY_THRESHOLD:
            volatility_level = "MEDIUM"
            qoe_flag = True
        else:
            volatility_level = "LOW"
            qoe_flag = False

        # Estimate normalized margin
        normalized_margin = self._estimate_normalized_margin(margins, margin_stdev, avg_margin)

        # Estimate one-time expenses if margin collapsed
        one_time_estimate = self._estimate_one_time_expenses(
            current_revenue, current_margin, normalized_margin, margin_change_yoy
        )

        logger.info(
            "📊 Margin volatility analysis complete",
            extra={
                "current_margin": from_decimal(current_margin),
                "avg_margin": from_decimal(avg_margin),
                "margin_stdev": from_decimal(margin_stdev),
                "volatility_level": volatility_level,
                "quality_of_earnings_flag": qoe_flag,
                "normalized_margin": from_decimal(normalized_margin),
                "one_time_estimate": from_decimal(one_time_estimate),
            },
        )

        return {
            "current_margin": current_margin,
            "average_margin": avg_margin,
            "margin_stdev": margin_stdev,
            "volatility_level": volatility_level,
            "quality_of_earnings_flag": qoe_flag,
            "margin_change_yoy": margin_change_yoy,
            "normalized_margin": normalized_margin,
            "one_time_expense_estimate": one_time_estimate,
            "margins_by_year": margins,
            "years_analyzed": len(margins),
        }

    def _estimate_normalized_margin(
        self, margins: List[Decimal], stdev: Decimal, avg_margin: Decimal
    ) -> Decimal:
        """
        Estimate normalized (sustainable) margin.

        Strategy:
        - High volatility: Use weighted average favoring recent stable years
        - Low volatility: Use simple average
        - If recent margin is outlier, use historical average
        """
        if len(margins) < 2:
            return margins[0]

        current_margin = margins[0]

        # If high volatility, be conservative
        if stdev > self.HIGH_VOLATILITY_THRESHOLD:
            # Use 3-year weighted average: 50% current, 30% y-1, 20% y-2
            if len(margins) >= 3:
                normalized = (
                    margins[0] * Decimal("0.50")
                    + margins[1] * Decimal("0.30")
                    + margins[2] * Decimal("0.20")
                )
            elif len(margins) == 2:
                normalized = margins[0] * Decimal("0.60") + margins[1] * Decimal("0.40")
            else:
                normalized = current_margin

            # Conservative cap: Don't exceed historical max
            max_historical = max(margins[1:]) if len(margins) > 1 else current_margin
            normalized = min(normalized, max_historical)

            logger.info(
                "📉 High volatility detected, using conservative weighted average",
                extra={
                    "normalized_margin": from_decimal(normalized),
                    "current_margin": from_decimal(current_margin),
                    "avg_margin": from_decimal(avg_margin),
                },
            )
        else:
            # Low volatility: simple average is fine
            normalized = avg_margin

        return normalized

    def _estimate_one_time_expenses(
        self,
        current_revenue: Decimal,
        current_margin: Decimal,
        normalized_margin: Decimal,
        margin_change_yoy: Decimal,
    ) -> Decimal:
        """
        Estimate one-time expenses from margin collapse.

        Logic: If margin is below normalized, estimate non-recurring hit
        """
        margin_deficit = normalized_margin - current_margin

        # Only estimate if there's a deficit AND it's significant
        if margin_deficit > Decimal("2.0"):  # >2pp below normal
            one_time_estimate = current_revenue * (margin_deficit / 100)

            logger.warning(
                "⚠️ Margin significantly below normalized level - estimating one-time expenses",
                extra={
                    "current_margin": from_decimal(current_margin),
                    "normalized_margin": from_decimal(normalized_margin),
                    "margin_deficit_pp": from_decimal(margin_deficit),
                    "one_time_estimate": from_decimal(one_time_estimate),
                },
            )

            return one_time_estimate

        return Decimal("0")

    def _create_default_result(
        self, current_margin: Decimal, current_ebitda: Decimal, current_revenue: Decimal
    ) -> Dict[str, Any]:
        """Create default result when insufficient data."""
        return {
            "current_margin": current_margin,
            "average_margin": current_margin,
            "margin_stdev": Decimal("0"),
            "volatility_level": "UNKNOWN",
            "quality_of_earnings_flag": False,
            "margin_change_yoy": Decimal("0"),
            "normalized_margin": current_margin,
            "one_time_expense_estimate": Decimal("0"),
            "margins_by_year": [current_margin],
            "years_analyzed": 1,
        }
