"""Multi-year EBITDA table context builders for valuation reports."""

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Optional, TypeAlias, cast

from src.config.valuation_constants import recency_weights_desc
from src.services.infrastructure.translations import (
    EbitdaAdjustmentLabels,
    ReportTranslations,
    resolve_ebitda_adjustment_labels,
)
from src.services.reports.ebitda_normalization import (
    current_year_is_ebitda_normalized,
    derive_normalized_ebitda,
    has_explicit_normalization_metadata,
    is_adjustment_applied,
)
from src.services.reports.protocol_adapter import DictWrapper, _attr, _unwrap
from src.utils.decimal_helpers import optional_decimal, safe_decimal_or_zero, safe_float
from src.utils.filing_year_labels import format_year_column_with_filing_role
from src.utils.fiscal_year import get_current_filing_year

JsonMap: TypeAlias = dict[str, object]
YearRows: TypeAlias = list[object]
MultiYearRows: TypeAlias = list[JsonMap]
CurrencyFormatter: TypeAlias = Callable[[Optional[Decimal]], str]


def _metadata_dict(value: Optional[Mapping[str, object]]) -> JsonMap:
    unwrapped = _unwrap(value)
    return cast(JsonMap, unwrapped) if isinstance(unwrapped, dict) else {}


def _year_as_int(year_data: object, default: int = 0) -> int:
    try:
        return int(_attr(year_data, "year", default) or default)
    except (TypeError, ValueError):
        return default


def _value(year_data: object, key: str, default: object = None) -> object:
    unwrapped = _unwrap(year_data)
    if isinstance(unwrapped, dict):
        return unwrapped.get(key, default)
    return _attr(year_data, key, default)


def _safe_year(year_data: object) -> Optional[int]:
    try:
        value = _value(year_data, "year")
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _year_value(year_data: object) -> object:
    return _value(year_data, "year")


def resolve_historical_ebitda_weighting_mode(
    request: Optional[object],
    request_metadata: Optional[Mapping[str, object]] = None,
) -> str:
    """Resolve advisor-selected historical EBITDA weighting mode."""
    metadata = _metadata_dict(request_metadata)
    raw_weighting_mode = (
        str(_attr(request, "historical_ebitda_weighting_mode", "standard") or "standard")
        .strip()
        .lower()
        if request
        else "standard"
    )
    if raw_weighting_mode == "standard" and metadata.get("historical_ebitda_weighting_mode"):
        raw_weighting_mode = str(metadata.get("historical_ebitda_weighting_mode")).strip().lower()
    return raw_weighting_mode


def _historical_ebitda_weights(
    request: Optional[object],
    request_metadata: Optional[Mapping[str, object]] = None,
) -> object:
    metadata = _metadata_dict(request_metadata)
    raw_weights = _unwrap(_attr(request, "historical_ebitda_weights", None)) if request else None
    if not isinstance(raw_weights, dict):
        raw_weights = metadata.get("historical_ebitda_weights")
    return raw_weights


def _custom_weights_are_applicable(
    custom_weights_by_year: Mapping[object, object],
    present_years: set,
) -> bool:
    """Whether advisor per-year weights actually drove the valuation.

    Mirrors the engine calculator (``_normalize_custom_ebitda_weights`` +
    ``_build_custom_weight_entries``): custom weights apply only when there are 3-5 of
    them AND every weighted year is present in the series. Otherwise the headline falls
    back to the recency ramp, so neither the table nor the advisor-weighting audit block
    may present the custom weights as if they were used.
    """
    return (
        bool(custom_weights_by_year)
        and 3 <= len(custom_weights_by_year) <= 5
        and all(year in present_years for year in custom_weights_by_year)
    )


def _normalized_custom_weights(
    *,
    request: object,
    request_metadata: JsonMap,
) -> dict[int, float]:
    raw_weighting_mode = resolve_historical_ebitda_weighting_mode(
        request,
        request_metadata,
    )
    raw_custom_weights = _historical_ebitda_weights(request, request_metadata)

    custom_weights_by_year: dict[int, float] = {}
    if raw_weighting_mode != "weighted" or not isinstance(raw_custom_weights, dict):
        return custom_weights_by_year

    for year_key, weight_value in raw_custom_weights.items():
        try:
            year_int = int(year_key)
        except (TypeError, ValueError):
            continue
        weight_decimal = optional_decimal(weight_value)
        if weight_decimal is None or weight_decimal < 0:
            continue
        custom_weights_by_year[year_int] = float(weight_decimal)

    custom_total = sum(custom_weights_by_year.values())
    if custom_total > 1.5:
        custom_weights_by_year = {
            year: weight / 100 for year, weight in custom_weights_by_year.items()
        }
        custom_total = sum(custom_weights_by_year.values())
    if custom_total > 0:
        custom_weights_by_year = {
            year: weight / custom_total for year, weight in custom_weights_by_year.items()
        }

    return custom_weights_by_year


def _selected_years_and_weights(
    *,
    years: YearRows,
    request: object,
    request_metadata: JsonMap,
) -> tuple[YearRows, list[float]]:
    custom_weights_by_year = _normalized_custom_weights(
        request=request,
        request_metadata=request_metadata,
    )
    present_years = {_year_as_int(year_data) for year_data in years}
    if _custom_weights_are_applicable(custom_weights_by_year, present_years):
        selected_years = [
            year_data for year_data in years if _year_as_int(year_data) in custom_weights_by_year
        ][:5]
        weights = [
            custom_weights_by_year.get(_year_as_int(year_data), 0.0) for year_data in selected_years
        ]
        return selected_years, weights

    visible_year_count = min(len(years), 5)
    selected_years = years[:visible_year_count]
    # `years` are ordered most-recent-first, so use the descending recency ramp
    # (most recent year heaviest). Matches the weighted-EBITDA valuation basis.
    weights = [float(weight) for weight in recency_weights_desc(visible_year_count)]
    return selected_years, weights


def _normalized_custom_weights_decimal(
    *,
    request: object,
    request_metadata: Optional[Mapping[str, object]] = None,
) -> dict[int, Decimal]:
    raw_weighting_mode = resolve_historical_ebitda_weighting_mode(
        request,
        request_metadata,
    )
    raw_custom_weights = _historical_ebitda_weights(request, request_metadata)

    custom_weights_by_year: dict[int, Decimal] = {}
    if raw_weighting_mode != "weighted" or not hasattr(raw_custom_weights, "items"):
        return custom_weights_by_year

    for year_key, weight_value in cast(Mapping[object, object], raw_custom_weights).items():
        try:
            year_int = int(year_key)
            weight = Decimal(str(weight_value))
        except Exception:
            continue
        if weight >= 0:
            custom_weights_by_year[year_int] = weight

    custom_total = sum(custom_weights_by_year.values(), Decimal("0"))
    if custom_total > Decimal("1.5"):
        custom_weights_by_year = {
            year: weight / Decimal("100") for year, weight in custom_weights_by_year.items()
        }
        custom_total = sum(custom_weights_by_year.values(), Decimal("0"))
    if custom_total > 0:
        custom_weights_by_year = {
            year: weight / custom_total for year, weight in custom_weights_by_year.items()
        }

    return custom_weights_by_year


def _selected_years_and_decimal_weights(
    *,
    years: YearRows,
    request: object,
    request_metadata: Optional[Mapping[str, object]] = None,
) -> tuple[YearRows, list[Decimal]]:
    custom_weights_by_year = _normalized_custom_weights_decimal(
        request=request,
        request_metadata=request_metadata,
    )
    present_years = {(_safe_year(year_data) or 0) for year_data in years}
    if _custom_weights_are_applicable(custom_weights_by_year, present_years):
        selected_years = [
            year_data
            for year_data in years
            if (_safe_year(year_data) or 0) in custom_weights_by_year
        ][:5]
        weights = [
            custom_weights_by_year.get(_safe_year(year_data) or 0, Decimal("0"))
            for year_data in selected_years
        ]
        return selected_years, weights

    selected_years = years[:5]
    # `years` are ordered most-recent-first, so use the descending recency ramp
    # (most recent year heaviest). Matches the weighted-EBITDA valuation basis.
    weights = list(recency_weights_desc(len(selected_years)))
    return selected_years, weights


def _normalization_metadata(year_data: object) -> JsonMap:
    metadata = _unwrap(_value(year_data, "ebitda_normalization_metadata", None) or {})
    return metadata if isinstance(metadata, dict) else {}


def _safe_ebitda(year_data: object) -> Decimal:
    raw_value = _value(year_data, "ebitda")
    if raw_value is None:
        raw_value = _value(year_data, "ebitda_normalized")
    return cast(Decimal, safe_decimal_or_zero(raw_value))


def _safe_reported_ebitda(year_data: object, ebitda_fallback: Decimal) -> Decimal:
    reported = optional_decimal(_normalization_metadata(year_data).get("reported_ebitda"))
    return cast(Decimal, reported) if reported is not None else ebitda_fallback


def _safe_normalized_ebitda(year_data: object, fallback: Decimal) -> Decimal:
    should_read_metadata = isinstance(_unwrap(year_data), dict) or bool(
        _value(year_data, "ebitda_normalized", False)
    )
    if should_read_metadata:
        normalized = optional_decimal(_normalization_metadata(year_data).get("normalized_ebitda"))
        if normalized is not None:
            return cast(Decimal, normalized)
    ebitda_value = _safe_ebitda(year_data)
    return ebitda_value if ebitda_value != Decimal("0") else fallback


def _adjustment_rows_and_total(
    *,
    year_metadata: JsonMap,
    fallback_label: str,
) -> tuple[list[JsonMap], Decimal]:
    adjustments: list[JsonMap] = []
    adjustment_total = Decimal("0")

    year_adjustments = year_metadata.get("adjustments", [])
    if not isinstance(year_adjustments, list):
        return adjustments, adjustment_total

    for adjustment in year_adjustments:
        adjustment_data = _unwrap(adjustment) if isinstance(adjustment, DictWrapper) else adjustment
        if not isinstance(adjustment_data, dict):
            continue
        # Status-aware: pending/rejected candidates are not applied, so they must
        # not show as a per-year "+€X aanp." annotation while the normalized
        # column stays equal to reported (same contradiction class as page 4).
        if not is_adjustment_applied(adjustment_data):
            continue
        raw_amount = safe_decimal_or_zero(adjustment_data.get("amount", 0))
        adjustment_type = adjustment_data.get("type")
        if adjustment_type is not None:
            display_amount = abs(raw_amount)
            if str(adjustment_type).lower() in {
                "subtract",
                "deduct",
                "minus",
                "negative",
            }:
                adjustment_total -= display_amount
            else:
                adjustment_total += display_amount
        else:
            display_amount = abs(raw_amount)
            adjustment_type = "subtract" if raw_amount < 0 else "add"
            adjustment_total += raw_amount
        adjustments.append(
            {
                "label": adjustment_data.get("label", fallback_label),
                "amount": safe_float(display_amount),
                "type": adjustment_type,
                "category": adjustment_data.get("category", "owner"),
            }
        )

    return adjustments, adjustment_total


def _main_years_with_current(
    request: object,
    *,
    current_year: int,
) -> YearRows:
    historical_years = _attr(request, "historical_years_data", None)
    if historical_years is None:
        return []

    # Mirror the valuation weighting basis (_build_weighting_series): drop forecast
    # rows and dedupe by year (last row wins) so the report table reflects exactly
    # the years the weighted-EBITDA headline was computed from.
    by_year: dict[object, object] = {}
    for year_data in historical_years:
        if getattr(year_data, "is_forecast", False):
            continue
        year = _year_value(year_data)
        by_year[year if year is not None else id(year_data)] = year_data

    current_year_data = _attr(request, "current_year_data", None)
    if current_year_data is not None and hasattr(current_year_data, "ebitda"):
        cy = _year_value(current_year_data)
        by_year[cy if cy is not None else id(current_year_data)] = current_year_data

    years = sorted(by_year.values(), key=_year_as_int, reverse=True)
    return years


def _main_base_filing_year(years: YearRows, *, current_year: int) -> int:
    try:
        return int(_year_value(years[0]))
    except (IndexError, TypeError, ValueError):
        return int(current_year or get_current_filing_year())


def _main_effective_metadata(
    *,
    year: object,
    year_data: object,
    current_year: int,
    current_year_metadata: JsonMap,
) -> JsonMap:
    if year == current_year and current_year_metadata:
        return current_year_metadata
    return _normalization_metadata(year_data)


def _main_effective_normalized_flag(
    *,
    request: object,
    year: object,
    year_data: object,
    current_year: int,
) -> bool:
    if year == current_year:
        return current_year_is_ebitda_normalized(request)
    return bool(_attr(year_data, "ebitda_normalized", False))


def _main_ebitda_values(
    *,
    year_data: object,
    effective_metadata: JsonMap,
    effective_normalized_flag: bool,
) -> tuple[Decimal, Decimal]:
    raw_ebitda = safe_decimal_or_zero(_attr(year_data, "ebitda", 0))
    metadata_reported = optional_decimal(effective_metadata.get("reported_ebitda"))
    reported_decimal = cast(
        Decimal,
        metadata_reported if metadata_reported is not None else raw_ebitda,
    )

    metadata_normalized = optional_decimal(effective_metadata.get("normalized_ebitda"))
    if metadata_normalized is None:
        metadata_normalized = optional_decimal(effective_metadata.get("sustainable_ebitda"))
    if metadata_normalized is not None:
        return reported_decimal, cast(Decimal, metadata_normalized)

    normalized_decimal = (
        derive_normalized_ebitda(
            reported_decimal,
            effective_metadata,
            effective_normalized_flag,
        )
        or raw_ebitda
    )
    return reported_decimal, normalized_decimal


def _main_adjustment_total(
    *,
    adjustment_total: Decimal,
    effective_metadata: JsonMap,
    effective_normalized_flag: bool,
) -> Decimal:
    if adjustment_total != Decimal("0"):
        return adjustment_total
    if not has_explicit_normalization_metadata(effective_metadata, effective_normalized_flag):
        return adjustment_total
    if effective_metadata.get("total_adjustments") is None:
        return adjustment_total
    return safe_decimal_or_zero(effective_metadata.get("total_adjustments"))


def _main_multi_year_row(
    *,
    index: int,
    year_data: object,
    weight: float,
    base_filing_year: int,
    current_year: int,
    current_year_metadata: JsonMap,
    translations: ReportTranslations,
    adjustment_labels: EbitdaAdjustmentLabels,
    request: object,
) -> JsonMap:
    year = _year_value(year_data) or current_year - index
    effective_metadata = _main_effective_metadata(
        year=year,
        year_data=year_data,
        current_year=current_year,
        current_year_metadata=current_year_metadata,
    )
    effective_normalized_flag = _main_effective_normalized_flag(
        request=request,
        year=year,
        year_data=year_data,
        current_year=current_year,
    )
    reported_decimal, normalized_decimal = _main_ebitda_values(
        year_data=year_data,
        effective_metadata=effective_metadata,
        effective_normalized_flag=effective_normalized_flag,
    )
    adjustments, adjustment_total = _adjustment_rows_and_total(
        year_metadata=effective_metadata,
        fallback_label=adjustment_labels.adj_fallback,
    )
    adjustment_total = _main_adjustment_total(
        adjustment_total=adjustment_total,
        effective_metadata=effective_metadata,
        effective_normalized_flag=effective_normalized_flag,
    )
    normalized = safe_float(normalized_decimal)
    weighted = normalized * weight
    revenue = safe_float(_attr(year_data, "revenue", 0))
    ebitda_margin = (normalized / revenue * 100) if revenue > 0 else None

    return {
        "year": year,
        "year_display": format_year_column_with_filing_role(
            year,
            base_filing_year,
            translations,
        ),
        "reported_ebitda": safe_float(reported_decimal),
        "normalized_ebitda": normalized,
        "weight": weight,
        "weighted_ebitda": weighted,
        "adjustments": adjustments,
        "adjustment_total": safe_float(adjustment_total),
        "has_adjustments": len(adjustments) > 0 or adjustment_total != Decimal("0"),
        "revenue": revenue,
        "ebitda_margin": ebitda_margin,
    }


def build_main_multi_year_ebitda_data(
    *,
    request: Optional[object],
    locale: str,
    translations: ReportTranslations,
    current_year: int,
    country_code: str,
    current_year_metadata: JsonMap,
    request_metadata: Optional[Mapping[str, object]] = None,
) -> MultiYearRows:
    """Build main-report multi-year EBITDA rows from request data."""
    if request is None:
        return []

    years = _main_years_with_current(request, current_year=current_year)
    if not years:
        return []

    base_filing_year = _main_base_filing_year(years, current_year=current_year)
    metadata = _metadata_dict(request_metadata)
    selected_years, weights = _selected_years_and_weights(
        years=years,
        request=request,
        request_metadata=metadata,
    )
    adjustment_labels = resolve_ebitda_adjustment_labels(locale, translations)
    return [
        _main_multi_year_row(
            index=index,
            year_data=year_data,
            weight=weights[index] if index < len(weights) else 0.0,
            base_filing_year=base_filing_year,
            current_year=current_year,
            current_year_metadata=current_year_metadata,
            translations=translations,
            adjustment_labels=adjustment_labels,
            request=request,
        )
        for index, year_data in enumerate(selected_years)
    ]


def _simplified_years_with_current(request: object) -> YearRows:
    historical_years = _value(request, "historical_years_data")
    if historical_years is None:
        return []

    # Mirror the valuation weighting basis: drop forecast rows and dedupe by year
    # (last row wins) so the simplified table matches the weighted headline.
    by_year: dict[object, object] = {}
    for year_data in historical_years:
        if getattr(year_data, "is_forecast", False):
            continue
        year = _safe_year(year_data)
        by_year[year if year is not None else id(year_data)] = year_data

    current_year_data = _value(request, "current_year_data")
    if current_year_data:
        cy = _safe_year(current_year_data)
        by_year[cy if cy is not None else id(current_year_data)] = current_year_data

    years = sorted(by_year.values(), key=lambda year_data: _safe_year(year_data) or 0, reverse=True)
    return years


def _simplified_base_filing_year(
    years: YearRows,
    *,
    effective_report_year: int,
) -> int:
    try:
        base_filing_year = int(_safe_year(years[0]) or 0)
    except (IndexError, TypeError, ValueError):
        base_filing_year = effective_report_year
    return base_filing_year if base_filing_year > 0 else effective_report_year


def _simplified_multi_year_row(
    *,
    index: int,
    year_data: object,
    weight: Decimal,
    base_filing_year: int,
    effective_report_year: int,
    translations: ReportTranslations,
    format_currency: CurrencyFormatter,
    format_currency_exact: CurrencyFormatter,
) -> JsonMap:
    ebitda_field = _safe_ebitda(year_data)
    reported = _safe_reported_ebitda(year_data, ebitda_field)
    normalized = _safe_normalized_ebitda(year_data, ebitda_field)
    weighted = normalized * weight
    year = _safe_year(year_data) or (effective_report_year - index)
    adjustment_total = normalized - reported

    return {
        "year": year,
        "year_display": format_year_column_with_filing_role(
            year,
            base_filing_year,
            translations,
        ),
        "reported": reported,
        "reported_ebitda": reported,
        "reported_formatted": format_currency(reported),
        "normalized": normalized,
        "normalized_ebitda": normalized,
        "normalized_formatted": format_currency(normalized),
        "has_adjustments": adjustment_total != 0,
        "adjustment_total": adjustment_total,
        "weight": weight,
        "weight_pct": int(weight * 100),
        "weighted": weighted,
        "weighted_formatted": format_currency_exact(weighted),
    }


def build_simplified_multi_year_ebitda_data(
    *,
    request: Optional[object],
    locale: str,
    translations: ReportTranslations,
    effective_report_year: int,
    format_currency: CurrencyFormatter,
    format_currency_exact: CurrencyFormatter,
    request_metadata: Optional[Mapping[str, object]] = None,
) -> MultiYearRows:
    """Build simplified-report multi-year EBITDA rows from request data."""
    if request is None:
        return []

    years = _simplified_years_with_current(request)
    if not years:
        return []

    base_filing_year = _simplified_base_filing_year(
        years,
        effective_report_year=effective_report_year,
    )
    selected_years, weights = _selected_years_and_decimal_weights(
        years=years,
        request=request,
        request_metadata=request_metadata,
    )
    return [
        _simplified_multi_year_row(
            index=index,
            year_data=year_data,
            weight=weights[index] if index < len(weights) else Decimal("0"),
            base_filing_year=base_filing_year,
            effective_report_year=effective_report_year,
            translations=translations,
            format_currency=format_currency,
            format_currency_exact=format_currency_exact,
        )
        for index, year_data in enumerate(selected_years)
    ]


def build_advisor_historical_ebitda_weighting(
    *,
    request: Optional[object],
    request_metadata: Optional[Mapping[str, object]],
    multi_year_data: MultiYearRows,
) -> Optional[JsonMap]:
    """Build report context for advisor-selected historical EBITDA weighting."""
    raw_weighting_mode = resolve_historical_ebitda_weighting_mode(
        request,
        request_metadata,
    )
    raw_historical_weights = _historical_ebitda_weights(request, request_metadata)
    if (
        raw_weighting_mode != "weighted"
        or not isinstance(raw_historical_weights, dict)
        or not multi_year_data
    ):
        return None

    # Only present the advisor-weighting audit when the custom weights actually drove the
    # valuation. If they were rejected (wrong count / missing year) the headline used the
    # recency ramp, so labelling those weights as "advisor-selected" would be misleading.
    custom_weights_by_year = _normalized_custom_weights(
        request=request,
        request_metadata=_metadata_dict(request_metadata),
    )
    present_years: set = set()
    for row in multi_year_data:
        try:
            present_years.add(int(row.get("year")))
        except (TypeError, ValueError):
            continue
    if not _custom_weights_are_applicable(custom_weights_by_year, present_years):
        return None

    return {
        "mode": "weighted",
        "rows": [
            {
                "year": row.get("year"),
                "year_display": row.get("year_display") or row.get("year"),
                "weight_percent": safe_float(
                    safe_decimal_or_zero(row.get("weight", 0)) * Decimal("100")
                ),
                "normalized_ebitda": safe_float(row.get("normalized_ebitda", 0)),
                "weighted_ebitda": safe_float(row.get("weighted_ebitda", 0)),
            }
            for row in multi_year_data
            if safe_decimal_or_zero(row.get("weight", 0)) > Decimal("0")
        ],
        "weighted_ebitda_total": safe_float(
            sum(safe_decimal_or_zero(row.get("weighted_ebitda", 0)) for row in multi_year_data)
        ),
    }
