"""Multiple extraction helpers for report aggregation."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol, TypeAlias, cast

from src.services.reports.protocol_adapter import _attr
from src.utils.decimal_helpers import safe_decimal_or_zero

ReportMap: TypeAlias = dict[str, object]
MultipleBand: TypeAlias = tuple[Decimal, Decimal, Decimal]
MultipleContextValues: TypeAlias = tuple[Decimal, Decimal, Decimal, Decimal, str]


class TranslationLike(Protocol):
    report_multiple_suffix_ev_revenue: str
    report_multiple_suffix_ev_ebitda: str
    report_multiple_label_prefix_hybrid: str
    cover_multiple_label: str
    report_benchmark_median_ev_revenue: str
    report_benchmark_median_ev_ebitda: str


@dataclass(frozen=True)
class _RevenueMultipleValues:
    applied: Decimal
    low: Decimal
    high: Decimal
    base: Decimal


def _decimal(value: object) -> Decimal:
    parsed = safe_decimal_or_zero(value)
    if isinstance(parsed, Decimal):
        return parsed
    try:
        return Decimal(str(parsed))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _first_present(*values: object) -> object | None:
    """Return the first explicitly present value, preserving zero."""
    for value in values:
        if value is not None:
            return value
    return None


def _raw_multiple_band(
    multiples_valuation: object,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    raw_applied = (
        _attr(multiples_valuation, "ebitda_multiple", None)
        or _attr(multiples_valuation, "ev_ebitda_multiple", None)
        or _attr(multiples_valuation, "applied_multiple", None)
    )
    raw_low = _attr(multiples_valuation, "p25_ebitda_multiple", None)
    raw_high = _attr(multiples_valuation, "p75_ebitda_multiple", None)
    return (
        _decimal(raw_applied) if raw_applied else None,
        _decimal(raw_low) if raw_low else None,
        _decimal(raw_high) if raw_high else None,
    )


def _enterprise_value_mid(multiples_valuation: object | None) -> object | None:
    if not multiples_valuation:
        return None
    return _attr(multiples_valuation, "enterprise_value_mid", None) or _attr(
        multiples_valuation,
        "ev_mid",
        None,
    )


def _implied_applied_multiple(
    *,
    multiples_valuation: object | None,
    fallback_ebitda: Decimal,
) -> Decimal | None:
    enterprise_value = _enterprise_value_mid(multiples_valuation)
    if fallback_ebitda > Decimal("0") and enterprise_value:
        return _decimal(enterprise_value) / fallback_ebitda
    return None


def _fallback_applied_multiple(benchmark_ev_ebitda: Decimal | None) -> Decimal:
    if benchmark_ev_ebitda and benchmark_ev_ebitda > Decimal("0"):
        return benchmark_ev_ebitda
    return Decimal("0")


def _discard_stale_band_value(
    *,
    band_value: Decimal | None,
    applied: Decimal,
) -> Decimal | None:
    if band_value is not None and band_value < Decimal("2.0") and applied > Decimal("2.0"):
        return None
    return band_value


def _normalize_multiple_band(
    *,
    applied: Decimal,
    low: Decimal | None,
    high: Decimal | None,
) -> MultipleBand:
    if applied <= Decimal("0"):
        return Decimal("0"), Decimal("0"), Decimal("0")

    low = _discard_stale_band_value(band_value=low, applied=applied)
    high = _discard_stale_band_value(band_value=high, applied=applied)
    if low is None:
        low = applied * Decimal("0.80")
    if high is None:
        high = applied * Decimal("1.20")
    if low > applied:
        low = applied * Decimal("0.80")
    if high < applied:
        high = applied * Decimal("1.20")
    return applied, low, high


def extract_multiple_values(
    *,
    response: object,
    benchmark_ev_ebitda: Decimal | None = None,
    fallback_ebitda: Decimal = Decimal("0"),
) -> MultipleBand:
    """Extract applied, low, and high EV/EBITDA multiples for report context."""
    applied: Decimal | None = None
    low: Decimal | None = None
    high: Decimal | None = None

    multiples_valuation = _attr(response, "multiples_valuation", None)
    if multiples_valuation:
        applied, low, high = _raw_multiple_band(multiples_valuation)

    if applied is None:
        applied = _implied_applied_multiple(
            multiples_valuation=multiples_valuation,
            fallback_ebitda=fallback_ebitda,
        )

    if applied is None:
        applied = _fallback_applied_multiple(benchmark_ev_ebitda)

    return _normalize_multiple_band(applied=applied, low=low, high=high)


def base_multiple_value(
    *,
    response: object,
    applied_multiple: Decimal,
) -> Decimal:
    """Return market/base median multiple before discounts."""
    multiples_valuation = _attr(response, "multiples_valuation", None)
    raw_base = _attr(multiples_valuation, "p50_ebitda_multiple", None)
    if raw_base:
        base = _decimal(raw_base)
        if base > Decimal("0"):
            if applied_multiple > Decimal("0") and base < applied_multiple * Decimal("0.25"):
                return applied_multiple
            return base
    return applied_multiple


def _metric_type_from_pipeline(response: object, pipeline: ReportMap) -> str:
    primary_method = ""
    multiples_valuation = _attr(response, "multiples_valuation", None)
    if multiples_valuation:
        primary_method = str(_attr(multiples_valuation, "primary_method", "") or "").upper()

    metric_type = str(pipeline.get("metric_type") or "").upper()
    if metric_type:
        return metric_type
    return "REVENUE" if "REVENUE" in primary_method else "EBITDA"


def _apply_revenue_multiple_context(
    *,
    response: object,
    applied: Decimal,
    low: Decimal,
    high: Decimal,
    base: Decimal,
    source: str,
) -> MultipleContextValues:
    multiples_valuation = _attr(response, "multiples_valuation", None)
    if not multiples_valuation:
        return applied, low, high, base, source

    values, source = _normalized_revenue_multiple_values(
        _revenue_multiple_values(multiples_valuation),
        source=source,
    )
    return values.applied, values.low, values.high, values.base, source


def _revenue_multiple_values(multiples_valuation: object) -> _RevenueMultipleValues:
    return _RevenueMultipleValues(
        applied=_decimal(
            _first_present(
                _attr(multiples_valuation, "revenue_multiple", None),
                _attr(multiples_valuation, "ev_revenue_multiple", None),
            )
        ),
        low=_decimal(
            _first_present(
                _attr(multiples_valuation, "p25_revenue_multiple", None),
                _attr(multiples_valuation, "ev_revenue_p25", None),
            )
        ),
        high=_decimal(
            _first_present(
                _attr(multiples_valuation, "p75_revenue_multiple", None),
                _attr(multiples_valuation, "ev_revenue_p75", None),
            )
        ),
        base=_decimal(
            _first_present(
                _attr(multiples_valuation, "p50_revenue_multiple", None),
                _attr(multiples_valuation, "ev_revenue_p50", None),
            )
        ),
    )


def _positive_or_zero(value: Decimal) -> Decimal:
    return value if value > Decimal("0") else Decimal("0")


def _normalized_revenue_multiple_values(
    values: _RevenueMultipleValues,
    *,
    source: str,
) -> tuple[_RevenueMultipleValues, str]:
    applied = _positive_or_zero(values.applied)
    low = _positive_or_zero(values.low)
    high = _positive_or_zero(values.high)
    base = _positive_or_zero(values.base)
    if applied <= Decimal("0"):
        return _RevenueMultipleValues(applied, low, high, base), source

    source = "multiples_valuation_revenue"
    if low <= Decimal("0"):
        low = applied * Decimal("0.80")
    if high <= Decimal("0"):
        high = applied * Decimal("1.20")
    if base <= Decimal("0"):
        base = applied
    return _RevenueMultipleValues(applied, low, high, base), source


def _apply_pipeline_multiple_context(
    *,
    pipeline: ReportMap,
    applied: Decimal,
    low: Decimal,
    high: Decimal,
    base: Decimal,
    source: str,
) -> MultipleContextValues:
    pipeline_initial_mid = _decimal(
        _first_present(pipeline.get("initial_multiple_mid"), pipeline.get("initial_multiple"))
    )
    pipeline_final_low = _decimal(pipeline.get("final_multiple_low"))
    pipeline_final_mid = _decimal(
        _first_present(pipeline.get("final_multiple_mid"), pipeline.get("final_multiple"))
    )
    pipeline_final_high = _decimal(pipeline.get("final_multiple_high"))

    if pipeline_final_mid <= 0:
        return applied, low, high, base, source

    applied = pipeline_final_mid
    source = "step_11_multiple_pipeline"
    if pipeline_final_low > 0:
        low = pipeline_final_low
    if pipeline_final_high > 0:
        high = pipeline_final_high
    if pipeline_initial_mid > 0:
        base = pipeline_initial_mid
    return applied, low, high, base, source


def build_multiple_report_context(
    *,
    response: object,
    step_data: ReportMap,
    industry_benchmarks: ReportMap,
    t: TranslationLike,
    is_hybrid: bool,
    fallback_ebitda: Decimal,
) -> ReportMap:
    """Build report-ready multiple data with source, metric, and labels."""
    raw_pipeline = step_data.get("multiple_pipeline", {}) if step_data else {}
    pipeline = cast(ReportMap, raw_pipeline) if isinstance(raw_pipeline, dict) else {}
    metric_type = _metric_type_from_pipeline(response, pipeline)

    benchmark_ev_ebitda = _decimal(industry_benchmarks.get("ev_ebitda_p50"))
    applied, low, high = extract_multiple_values(
        response=response,
        benchmark_ev_ebitda=benchmark_ev_ebitda,
        fallback_ebitda=fallback_ebitda,
    )
    base = base_multiple_value(response=response, applied_multiple=applied)
    source = "legacy_response"

    if metric_type == "REVENUE":
        applied, low, high, base, source = _apply_revenue_multiple_context(
            response=response,
            applied=applied,
            low=low,
            high=high,
            base=base,
            source=source,
        )

    applied, low, high, base, source = _apply_pipeline_multiple_context(
        pipeline=pipeline,
        applied=applied,
        low=low,
        high=high,
        base=base,
        source=source,
    )

    benchmark_mid = Decimal("0")
    benchmark_low = Decimal("0")
    benchmark_high = Decimal("0")
    if metric_type == "REVENUE":
        benchmark_mid = _decimal(industry_benchmarks.get("ev_revenue_median"))
    else:
        benchmark_mid = _decimal(industry_benchmarks.get("ev_ebitda_p50"))
        benchmark_low = _decimal(industry_benchmarks.get("ev_ebitda_p25"))
        benchmark_high = _decimal(industry_benchmarks.get("ev_ebitda_p75"))

    metric_suffix = (
        t.report_multiple_suffix_ev_revenue
        if metric_type == "REVENUE"
        else t.report_multiple_suffix_ev_ebitda
    )
    label_prefix = t.report_multiple_label_prefix_hybrid if is_hybrid else t.cover_multiple_label
    benchmark_label = (
        t.report_benchmark_median_ev_revenue
        if metric_type == "REVENUE"
        else t.report_benchmark_median_ev_ebitda
    )

    return {
        "applied_multiple": applied,
        "multiple_low": low,
        "multiple_high": high,
        "base_multiple": base,
        "benchmark_multiple_mid": benchmark_mid,
        "benchmark_multiple_low": benchmark_low,
        "benchmark_multiple_high": benchmark_high,
        "metric_type": metric_type,
        "multiple_display_label": f"{label_prefix} ({metric_suffix})",
        "benchmark_multiple_label": benchmark_label,
        "uses_canonical_pipeline": source == "step_11_multiple_pipeline",
        "multiple_source": source,
        "is_hybrid_component_multiple": is_hybrid,
    }
