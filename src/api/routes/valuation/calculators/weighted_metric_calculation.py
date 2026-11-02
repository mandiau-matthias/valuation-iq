"""Weighted metric calculation pipeline used by ``WeightedEBITDACalculator``."""

from dataclasses import dataclass
from decimal import Decimal

from src.api.schemas import ValuationRequest
from src.config.valuation_constants import recency_weights
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WeightedMetricSeries:
    values: list[Decimal]
    entries: list[dict[str, object]]
    divergence_findings: list[dict[str, object]]


@dataclass
class WeightedMetricComputation:
    value: Decimal
    years_used: int


class WeightedMetricCalculationMixin:
    def _log_weighted_metric_inputs(
        self,
        request: ValuationRequest,
        metric_name: str,
        current_value: object,
        weighting_series: list[object],
    ) -> None:
        # DEBUG: audit-trail input dump. Final canonical line is "Weighted
        # metrics calculated (McKinsey standard)" with the computed values.
        logger.debug(
            f"🔍 [WEIGHTED-CALC-AUDIT] Weighted {metric_name.upper()} calculation - INPUT DATA",
            extra={
                "metric": metric_name,
                "current_year_value": (
                    from_decimal(to_decimal(str(current_value)), precision=2)
                    if current_value
                    else None
                ),
                "current_year_label": (
                    f"{request.current_year_data.year if hasattr(request, 'current_year_data') and request.current_year_data else 'Current'} {metric_name}"
                ),
                "num_weighting_years_available": len(weighting_series),
                "weighting_years": (
                    [
                        {
                            "year": year_data.year,
                            "value": from_decimal(
                                to_decimal(str(getattr(year_data, metric_name, 0) or 0)),
                                precision=2,
                            ),
                        }
                        for year_data in weighting_series
                    ]
                    if weighting_series
                    else []
                ),
                "note": "Current year is included in the weighted basis when available",
            },
        )

    def _current_metric_value(self, request: ValuationRequest, metric_name: str) -> object:
        current_value = getattr(request.current_year_data, metric_name, None)
        if current_value is None:
            self.logger.warning(
                f"Current year {metric_name} is None, using 0", extra={"metric": metric_name}
            )
            return Decimal("0.0")
        return current_value

    def _build_weighted_metric_series(
        self, weighting_series: list[object], metric_name: str
    ) -> WeightedMetricSeries:
        values: list[Decimal] = []
        entries: list[dict[str, object]] = []
        divergence_findings: list[dict[str, object]] = []

        for year_data in weighting_series:
            value = self._metric_value_for_weighting(year_data, metric_name, divergence_findings)
            if value is None:
                self.logger.warning(
                    f"Missing {metric_name} for year {getattr(year_data, 'year', '?')}, skipping from weighted average",
                    extra={"metric": metric_name, "year": getattr(year_data, "year", None)},
                )
                continue

            value_dec = to_decimal(str(value))
            values.append(value_dec)
            entries.append(
                {
                    "year": getattr(year_data, "year", None),
                    "value": value_dec,
                }
            )

        return WeightedMetricSeries(
            values=values,
            entries=entries,
            divergence_findings=divergence_findings,
        )

    def _metric_value_for_weighting(
        self,
        year_data: object,
        metric_name: str,
        divergence_findings: list[dict[str, object]],
    ) -> object | None:
        if metric_name != "ebitda":
            return getattr(year_data, metric_name, None)

        normalized_value = self._normalized_ebitda_value(year_data)
        if normalized_value is None:
            return getattr(year_data, metric_name, None)

        divergence = self._ebitda_divergence_finding(year_data, metric_name, normalized_value)
        if divergence:
            divergence_findings.append(divergence)
        return normalized_value

    def _normalized_ebitda_value(self, year_data: object) -> object | None:
        if not hasattr(year_data, "ebitda_normalization_metadata"):
            return None

        metadata = getattr(year_data, "ebitda_normalization_metadata", None)
        if not metadata:
            return None

        if isinstance(metadata, dict):
            return metadata.get("normalized_ebitda")
        return getattr(metadata, "normalized_ebitda", None)

    def _ebitda_divergence_finding(
        self,
        year_data: object,
        metric_name: str,
        normalized_value: object,
    ) -> dict[str, object] | None:
        raw_field_val = getattr(year_data, metric_name, None)
        if raw_field_val is None:
            return None

        try:
            raw_dec = to_decimal(str(raw_field_val))
            normalized_dec = to_decimal(str(normalized_value))
            if abs(raw_dec - normalized_dec) <= to_decimal("1"):
                return None
            return {
                "year": getattr(year_data, "year", None),
                "ebitda_field": from_decimal(raw_dec, precision=2),
                "normalized_metadata": from_decimal(normalized_dec, precision=2),
                "delta": from_decimal(normalized_dec - raw_dec, precision=2),
            }
        except Exception:
            return None

    def _log_ebitda_divergences(
        self, metric_name: str, divergence_findings: list[dict[str, object]]
    ) -> None:
        if metric_name != "ebitda" or not divergence_findings:
            return

        self.logger.error(
            "🚨 [EBITDA-DIVERGENCE] ebitda field disagrees with ebitda_normalization_metadata.normalized_ebitda",
            extra={
                "metric": metric_name,
                "divergent_years": divergence_findings,
                "impact": (
                    "Weighted EBITDA used the metadata value, but downstream consumers reading "
                    "the bare `ebitda` field (report renderer, normalization bridge, sensitivity "
                    "table) will see the unnormalized number and the report will appear to drop "
                    "the user's adjustments."
                ),
                "remediation": "Fix the request builder to write the post-adjustment value into both `ebitda` and metadata.normalized_ebitda.",
            },
        )

    def _compute_weighted_metric_value(
        self,
        *,
        request: ValuationRequest,
        metric_name: str,
        current_value: object,
        series: WeightedMetricSeries,
    ) -> WeightedMetricComputation:
        custom_computation = self._custom_year_weight_computation(
            request, metric_name, series.entries
        )
        if custom_computation:
            return custom_computation

        return self._recency_weighted_entries_computation(
            metric_name, current_value, series.entries
        )

    def _custom_year_weight_computation(
        self,
        request: ValuationRequest,
        metric_name: str,
        weighted_series_entries: list[dict[str, object]],
    ) -> WeightedMetricComputation | None:
        """
        Apply the advisor's per-fiscal-year weights to ``metric_name``.

        The advisor weights the YEARS (via ``historical_ebitda_weights``), so the
        same per-year split drives BOTH the revenue and EBITDA aggregates — the
        sliders move "how much each year counts", not one metric in isolation.
        """
        custom_weight_entries = self._build_custom_weight_entries(request, weighted_series_entries)
        if not custom_weight_entries:
            return None

        weighted_value = sum(
            (entry["value"] * entry["weight"] for entry in custom_weight_entries),
            Decimal("0"),
        )
        self.logger.debug(
            f"✅ [WEIGHTED-CALC-AUDIT] Advisor per-year weighting applied to {metric_name.upper()}",
            extra={
                "metric": metric_name,
                "custom_weights": [
                    {
                        "year": entry["year"],
                        "value": from_decimal(entry["value"], precision=2),
                        "weight": from_decimal(entry["weight"], precision=4),
                        "contribution": from_decimal(entry["value"] * entry["weight"], precision=2),
                    }
                    for entry in custom_weight_entries
                ],
                "weighted_result": from_decimal(weighted_value, precision=2),
                "methodology": "Advisor-selected historical year weighting",
            },
        )
        return WeightedMetricComputation(
            value=weighted_value, years_used=len(custom_weight_entries)
        )

    def _recency_weighted_entries_computation(
        self,
        metric_name: str,
        current_value: object,
        weighted_series_entries: list[dict[str, object]],
    ) -> WeightedMetricComputation:
        """
        Default historical weighting: a linear recency ramp over the visible window.

        Weights the up-to-five most recent fiscal years by recency rank
        (oldest … most-recent), normalized to 1.0, so the most recent year carries
        the most weight. Reduces to the canonical 50/33/17 split for three years
        (McKinsey Valuation 2015, Ch. 7; Damodaran 2012, pp. 234-237) and extends
        the same principle smoothly to four/five-year windows.
        """
        selected_entries = weighted_series_entries[-5:]
        num_years = len(selected_entries)

        if num_years == 0:
            weighted_value = to_decimal(str(current_value))
            self.logger.warning(
                f"⚠️ No valid weighting series for {metric_name}, using current year",
                extra={
                    "metric": metric_name,
                    "value": from_decimal(weighted_value, precision=2),
                },
            )
            return WeightedMetricComputation(value=weighted_value, years_used=0)

        weights = list(recency_weights(num_years))
        weighted_value = sum(
            (entry["value"] * weight for entry, weight in zip(selected_entries, weights)),
            Decimal("0"),
        )
        self.logger.debug(
            f"✅ [WEIGHTED-CALC-AUDIT] Recency-weighted {metric_name.upper()} - CALCULATION BREAKDOWN",
            extra={
                "metric": metric_name,
                "num_years": num_years,
                "recency_weights": [
                    {
                        "year": entry["year"],
                        "value": from_decimal(entry["value"], precision=2),
                        "weight": from_decimal(weight, precision=4),
                        "contribution": from_decimal(entry["value"] * weight, precision=2),
                    }
                    for entry, weight in zip(selected_entries, weights)
                ],
                "weighted_result": from_decimal(weighted_value, precision=2),
                "methodology": "Linear recency ramp (most recent year weighted heaviest)",
                "academic_reference": "McKinsey Valuation (2015), Chapter 7; Damodaran (2012)",
            },
        )
        return WeightedMetricComputation(value=weighted_value, years_used=num_years)

    def _log_final_weighted_metric(
        self,
        *,
        metric_name: str,
        current_value: object,
        computation: WeightedMetricComputation,
        final_weighted_value: Decimal,
    ) -> None:
        # DEBUG: per-metric output audit; the cluster summary
        # "📊 Weighted metrics calculated (McKinsey standard)" is the
        # canonical INFO line for the weighted-metrics phase.
        logger.debug(
            f"🎯 [WEIGHTED-CALC-AUDIT] Weighted {metric_name.upper()} - FINAL OUTPUT",
            extra={
                "metric": metric_name,
                "final_weighted_value": final_weighted_value,
                "num_years_used": computation.years_used,
                "current_year_value_not_used": from_decimal(
                    to_decimal(str(current_value)), precision=2
                ),
                "note": "This weighted value will be used in downstream valuation steps",
                "academic_compliance": "McKinsey/Damodaran weighted averaging methodology",
            },
        )

    def _calculate_weighted_metric(self, request: ValuationRequest, metric_name: str) -> Decimal:
        """
        Internal method to calculate weighted average for any metric.

        Args:
            request: ValuationRequest with historical_years_data
            metric_name: Name of the metric attribute (e.g., 'ebitda', 'revenue')

        Returns:
            Weighted metric value
        """
        try:
            weighting_series = self._build_weighting_series(request)
            current_value = self._current_metric_value(request, metric_name)
            self._log_weighted_metric_inputs(request, metric_name, current_value, weighting_series)

            if not weighting_series:
                self.logger.info(
                    f"No weighting series for {metric_name}, using current year value",
                    extra={"metric": metric_name, "value": current_value},
                )
                return from_decimal(to_decimal(str(current_value)), precision=2)

            series = self._build_weighted_metric_series(weighting_series, metric_name)
            self._log_ebitda_divergences(metric_name, series.divergence_findings)
            computation = self._compute_weighted_metric_value(
                request=request,
                metric_name=metric_name,
                current_value=current_value,
                series=series,
            )
            final_weighted_value = from_decimal(computation.value, precision=2)
            self._log_final_weighted_metric(
                metric_name=metric_name,
                current_value=current_value,
                computation=computation,
                final_weighted_value=final_weighted_value,
            )
            return final_weighted_value

        except Exception as e:
            self.logger.error(
                f"❌ Error calculating weighted {metric_name}: {e}",
                extra={"error_type": type(e).__name__, "error": str(e), "metric": metric_name},
                exc_info=True,
            )
            fallback_value = getattr(
                request.current_year_data, metric_name, Decimal("0.0")
            ) or Decimal("0.0")
            return from_decimal(to_decimal(str(fallback_value)), precision=2)
