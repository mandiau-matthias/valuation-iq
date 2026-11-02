"""
Weighted EBITDA Calculator

Implements weighted average EBITDA calculation per academic valuation standards (Koller, Goedhart & Wessels 2020).

Academic References:
    [1] McKinsey & Company (2015). "Valuation: Measuring and Managing
        the Value of Companies", 6th Edition, Chapter 7.
    [2] Damodaran, A. (2012). "Investment Valuation: Tools and Techniques
        for Determining the Value of Any Asset", 3rd Edition, pp. 234-237.
    [3] PwC (2020). "Guide to Valuations", Section 4.2: Normalized Earnings.
    [4] Brealey, R. A., Myers, S. C., & Allen, F. (2020). "Principles of
        Corporate Finance", 13th Edition, Chapter 4.

Implementation:
    Three-year weighting: (Year1 × 1/6) + (Year2 × 2/6) + (Year3 × 3/6)
    Rationale: Recent performance weighted 3x heavier to capture momentum
    and current trajectory, which is more predictive of future performance
    than historical averages.

Author: UpSwitch CTO Team
Date: November 2025
Version: 1.0.0
"""

from decimal import Decimal, InvalidOperation

from src.api.routes.valuation.calculators.weighted_metric_calculation import (
    WeightedMetricCalculationMixin,
)
from src.api.schemas import ValuationRequest
from src.config.valuation_constants import recency_weights
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    MultiplesCalculationError,
    ValidationError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class WeightedEBITDACalculator(WeightedMetricCalculationMixin):
    """
    Calculates weighted financial metrics (revenue and EBITDA) with recent years
    weighted heavier, via a linear recency ramp over the five most recent fiscal years.

    Default weighting (``recency_weights(n)``, oldest→newest ∝ rank, summing to 1.0):
    - 3 years: 1/6, 2/6, 3/6  (= 17% / 33% / 50%, the canonical McKinsey split)
    - 2 years: 1/3, 2/3
    - 4-5 years: the same ramp extended (e.g. 10/20/30/40; 7/13/20/27/33)
    - 1 year: direct value (no weighting)

    Advisors may override the per-year weights (``historical_ebitda_weights``); the
    override applies to BOTH revenue and EBITDA. The scheme emphasizes recent
    performance as a better predictor of future cash flows (Koller, Goedhart &
    Wessels 2020).
    """

    def __init__(self):
        """Initialize the weighted EBITDA calculator."""
        self.logger = logger

    @staticmethod
    def _has_admitted_financials(year_data: object) -> bool:
        """Exclude empty UI placeholders from the weighted actual-year basis."""

        revenue = getattr(year_data, "revenue", None)
        ebitda = getattr(year_data, "ebitda", None)
        if revenue is None or ebitda is None:
            return False
        try:
            revenue_value = Decimal(str(revenue))
            ebitda_value = Decimal(str(ebitda))
        except (InvalidOperation, TypeError, ValueError):
            return False
        return revenue_value.is_finite() and revenue_value > 0 and ebitda_value.is_finite()

    def _build_weighting_series(self, request: ValuationRequest) -> list[object]:
        """
        Build a deduplicated year series for weighting.

        Returns every non-forecast historical year plus the current year, deduped by
        year (current_year_data wins when the current year is already in history) and
        sorted oldest-first. The recency ramp is then applied over the five most recent
        of these (see ``_recency_weighted_entries_computation``), matching the years the
        report table shows so the headline and the table never drift.
        """
        series_by_year: dict[object, object] = {}

        for year_data in request.historical_years_data or []:
            if getattr(year_data, "is_forecast", False) or not self._has_admitted_financials(
                year_data
            ):
                continue
            year = getattr(year_data, "year", None)
            key = year if year is not None else id(year_data)
            series_by_year[key] = year_data

        current_data = getattr(request, "current_year_data", None)
        if current_data is not None and self._has_admitted_financials(current_data):
            current_year = getattr(current_data, "year", None)
            key = current_year if current_year is not None else id(current_data)
            series_by_year[key] = current_data

        return sorted(
            series_by_year.values(),
            key=lambda year_data: getattr(year_data, "year", 0) or 0,
        )

    def _normalize_custom_ebitda_weights(
        self, request: ValuationRequest
    ) -> dict[int, Decimal] | None:
        weighting_mode = str(
            getattr(request, "historical_ebitda_weighting_mode", "standard") or "standard"
        ).lower()
        raw_weights = getattr(request, "historical_ebitda_weights", None)
        if weighting_mode != "weighted" and not raw_weights:
            return None
        if not raw_weights:
            self.logger.warning(
                "Advisor-weighted EBITDA requested without weights; using standard weighting"
            )
            return None

        normalized: dict[int, Decimal] = {}
        try:
            items = raw_weights.items() if isinstance(raw_weights, dict) else []
            for year, weight in items:
                weight_dec = to_decimal(str(weight))
                if weight_dec < 0:
                    raise ValueError("custom EBITDA weights cannot be negative")
                normalized[int(year)] = weight_dec
        except Exception as exc:
            self.logger.warning(
                "Invalid advisor EBITDA weights; using standard weighting",
                extra={"error": str(exc), "weights": raw_weights},
            )
            return None

        total = sum(normalized.values(), Decimal("0"))
        if abs(total - Decimal("100")) <= Decimal("2"):
            normalized = {year: weight / Decimal("100") for year, weight in normalized.items()}
            total = sum(normalized.values(), Decimal("0"))

        if abs(total - Decimal("1")) > Decimal("0.02"):
            self.logger.warning(
                "Advisor EBITDA weights do not sum to 100%; using standard weighting",
                extra={"weight_sum": from_decimal(total, precision=4), "weights": raw_weights},
            )
            return None

        if total > 0 and total != Decimal("1"):
            normalized = {year: weight / total for year, weight in normalized.items()}

        if not (3 <= len(normalized) <= 5):
            self.logger.warning(
                "Advisor EBITDA weighting needs 3 to 5 years; using standard weighting",
                extra={"year_count": len(normalized), "weights": raw_weights},
            )
            return None

        return normalized

    def _build_custom_weight_entries(
        self,
        request: ValuationRequest,
        weighted_series_entries: list[dict[str, object]],
    ) -> list[dict[str, object]] | None:
        custom_weights = self._normalize_custom_ebitda_weights(request)
        if not custom_weights:
            return None

        entries_by_year = {
            int(entry["year"]): entry
            for entry in weighted_series_entries
            if entry.get("year") is not None
        }
        missing_years = sorted(year for year in custom_weights if year not in entries_by_year)
        if missing_years:
            self.logger.warning(
                "Advisor EBITDA weights reference years not present in the valuation series; using standard weighting",
                extra={
                    "missing_years": missing_years,
                    "available_years": sorted(entries_by_year.keys()),
                },
            )
            return None

        return [
            {
                "year": year,
                "weight": custom_weights[year],
                "value": entries_by_year[year]["value"],
            }
            for year in sorted(custom_weights.keys())
        ]

    def calculate_weighted_ebitda(self, request: ValuationRequest) -> Decimal:
        """
        Calculate weighted EBITDA with recent years weighted heavier.

        Formula (3 years): Year1×1/6 + Year2×2/6 + Year3×3/6
        Rationale: Recent performance (Year3) weighted 3x heavier than oldest (Year1)
        to capture current trajectory and momentum.

        Args:
            request: ValuationRequest with historical_years_data

        Returns:
            Weighted EBITDA value in euros

        References:
            - McKinsey Valuation (2015), Chapter 7: Normalized Earnings
            - Damodaran (2012): "Investment Valuation", pp. 234-237

        Example:
            Year 1: €80K EBITDA (weight 1/6) = €13.3K
            Year 2: €90K EBITDA (weight 2/6) = €30K
            Year 3: €100K EBITDA (weight 3/6) = €50K
            Weighted EBITDA = €93.3K
        """
        return self._calculate_weighted_metric(request, "ebitda")

    def calculate_weighted_revenue(self, request: ValuationRequest) -> Decimal:
        """
        Calculate weighted revenue with recent years weighted heavier.

        Uses the same weighting logic as EBITDA to maintain consistency
        across financial metrics.

        Args:
            request: ValuationRequest with historical_years_data

        Returns:
            Weighted revenue value in euros

        References:
            - McKinsey Valuation (2015), Chapter 7
            - PwC Valuation Guidelines (2020), Section Decimal('4.2')
        """
        return self._calculate_weighted_metric(request, "revenue")

    def calculate_cagr(self, request: ValuationRequest, metric: str = "revenue") -> Decimal:
        """
        Calculate Compound Annual Growth Rate (CAGR) for a given metric.

        Formula: CAGR = ((Ending Value / Beginning Value)^(1/n)) - 1

        Args:
            request: ValuationRequest with historical_years_data
            metric: Metric name ('revenue', 'ebitda', 'net_income', etc.)

        Returns:
            CAGR as a decimal (e.g., Decimal('0.15') for 15% growth)
            Returns Decimal('0.0') if insufficient data or calculation not possible

        References:
            - Damodaran (2012): "Investment Valuation", Chapter 11
            - Brealey-Myers (2020): "Principles of Corporate Finance", Chapter 4
        """
        try:
            historical_data = [
                year
                for year in (request.historical_years_data or [])
                if not getattr(year, "is_forecast", False)
            ]
            current_value = getattr(request.current_year_data, metric, None)

            if not historical_data or current_value is None or current_value <= 0:
                # DEBUG: CAGR insufficient-data is the normal single-year case;
                # the "Weighted metrics calculated" summary line carries the
                # final answer (cagr_value = 0).
                self.logger.debug(
                    f"CAGR not calculated for {metric}: insufficient data",
                    extra={
                        "historical_years": len(historical_data),
                        "current_value": current_value,
                    },
                )
                return Decimal("0.0")

            # Sort by year to ensure proper ordering (oldest first)
            sorted_historical = sorted(historical_data, key=lambda x: x.year)

            # Get earliest value
            earliest_value = getattr(sorted_historical[0], metric, None)

            if earliest_value is None or earliest_value <= 0:
                self.logger.warning(
                    f"Cannot calculate CAGR for {metric}: invalid earliest value",
                    extra={"earliest_value": earliest_value},
                )
                return Decimal("0.0")

            num_years = max(1, request.current_year_data.year - sorted_historical[0].year)

            ratio = float(current_value / earliest_value)
            cagr = Decimal(str(ratio ** (1 / num_years) - 1))

            self.logger.info(
                f"📈 CAGR calculated for {metric}",
                extra={
                    "metric": metric,
                    "earliest_value": earliest_value,
                    "current_value": current_value,
                    "num_years": num_years,
                    "cagr": round(cagr * 100, 2),
                },
            )

            return cagr

        except Exception as e:
            self.logger.error(
                f"Error calculating CAGR for {metric}: {e}",
                extra={"error_type": type(e).__name__, "error": str(e), "metric": metric},
                exc_info=True,
            )
            return Decimal("0.0")

    def get_weighting_schema(self, request: ValuationRequest) -> dict[str, object]:
        """
        Return the weighting schema used based on the canonical valuation year set.

        Args:
            request: ValuationRequest with historical_years_data

        Returns:
            Dictionary containing:
                - years_available: Number of years in the weighting series
                - weights: List of weights applied (e.g., [1/6, 2/6, 3/6])
                - method: Description of weighting method
                - rationale: Academic justification
        """
        weighting_series = self._build_weighting_series(request)
        custom_weights = self._normalize_custom_ebitda_weights(request)
        if custom_weights:
            selected_years = sorted(custom_weights.keys())
            return {
                "years_available": len(selected_years),
                "weights": [
                    from_decimal(custom_weights[year], precision=4) for year in selected_years
                ],
                "weight_labels": [
                    f"{year}: {from_decimal(custom_weights[year] * Decimal('100'), precision=2)}%"
                    for year in selected_years
                ],
                "year_weights": {
                    str(year): from_decimal(custom_weights[year], precision=4)
                    for year in selected_years
                },
                "method": "Advisor-weighted EBITDA average",
                "rationale": "Manual historical EBITDA weighting set by advisor.",
                "total_weight": Decimal("1.0"),
                "academic_reference": "Advisor override",
                "custom_weights": True,
            }

        selected_years = [
            getattr(year_data, "year", None)
            for year_data in weighting_series[-5:]
            if getattr(year_data, "year", None) is not None
        ]
        if not selected_years:
            return {
                "years_available": 0,
                "weights": [],
                "weight_labels": [],
                "method": "Current year only",
                "rationale": "No historical data available",
                "total_weight": Decimal("1.0"),
                "academic_reference": "N/A",
                "custom_weights": False,
            }

        weights = list(recency_weights(len(selected_years)))
        num_years = len(selected_years)
        if num_years == 1:
            method = "Single year (no weighting)"
            rationale = "Insufficient historical data for weighted average."
        else:
            method = "Recency-weighted historical average"
            rationale = (
                "Most recent year weighted heaviest via a linear recency ramp; "
                "reduces to the 50/33/17 split for three years "
                "(McKinsey Valuation, 2015, Chapter 7)."
            )
        return {
            "years_available": len(selected_years),
            "weights": [from_decimal(weight, precision=4) for weight in weights],
            "weight_labels": [
                f"{year}: {from_decimal(weight * Decimal('100'), precision=2)}%"
                for year, weight in zip(selected_years, weights)
            ],
            "year_weights": {
                str(year): from_decimal(weight, precision=4)
                for year, weight in zip(selected_years, weights)
            },
            "method": method,
            "rationale": rationale,
            "total_weight": Decimal("1.0"),
            "academic_reference": "McKinsey Valuation (2015), Chapter 7; Damodaran (2012)",
            "custom_weights": False,
        }

    def calculate_all_weighted_metrics(self, request: ValuationRequest) -> dict[str, object]:
        """
        Calculate all weighted metrics in one call for efficiency.

        Args:
            request: ValuationRequest with historical and current year data

        Returns:
            Dictionary containing:
                - weighted_ebitda: Weighted EBITDA value
                - weighted_revenue: Weighted revenue value
                - ebitda_cagr: EBITDA compound annual growth rate
                - revenue_cagr: Revenue compound annual growth rate
                - weighting_schema: Weighting methodology details
        """
        try:
            weighted_ebitda = self.calculate_weighted_ebitda(request)
            weighted_revenue = self.calculate_weighted_revenue(request)
            ebitda_cagr = self.calculate_cagr(request, "ebitda")
            revenue_cagr = self.calculate_cagr(request, "revenue")
            weighting_schema = self.get_weighting_schema(request)

            result = {
                "weighted_ebitda": weighted_ebitda,
                "weighted_revenue": weighted_revenue,
                "ebitda_cagr": ebitda_cagr,
                "revenue_cagr": revenue_cagr,
                "weighting_schema": weighting_schema,
            }

            # DEBUG: per-metric summary; the comprehensive orchestrator emits
            # "Weighted metrics calculated (McKinsey standard)" as the canonical INFO.
            self.logger.debug(
                "📊 All weighted metrics calculated",
                extra={
                    "weighted_ebitda": weighted_ebitda,
                    "weighted_revenue": weighted_revenue,
                    "ebitda_cagr": round(ebitda_cagr * 100, 2),
                    "revenue_cagr": round(revenue_cagr * 100, 2),
                    "method": weighting_schema["method"],
                },
            )

            return result

        except (CalculationError, DataQualityError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(
                f"Error calculating all weighted metrics: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
                exc_info=True,
            )
            cyd = request.current_year_data
            return {
                "weighted_ebitda": (cyd.ebitda if cyd and cyd.ebitda else None) or Decimal("0.0"),
                "weighted_revenue": (cyd.revenue if cyd and cyd.revenue else None)
                or Decimal("0.0"),
                "ebitda_cagr": Decimal("0.0"),
                "revenue_cagr": Decimal("0.0"),
                "weighting_schema": self.get_weighting_schema(request),
            }
