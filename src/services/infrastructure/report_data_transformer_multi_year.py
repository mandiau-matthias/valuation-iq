"""
Multi-year EBITDA extraction for the legacy report data transformer.

The active report pipeline no longer uses ReportDataTransformer directly, but
compatibility callers still exercise its multi-year EBITDA method. Keeping this
logic outside the deprecated facade avoids growing that legacy module.
"""

from decimal import Decimal
from typing import List, Optional, Tuple

from src.api.schemas import ValuationRequest, ValuationResponse, YearlyEBITDA
from src.services.infrastructure.translations import get_translations, normalize_report_locale
from src.utils.filing_year_labels import format_year_column_with_filing_role
from src.utils.fiscal_year import primary_filing_year_for_report_data


def _year_value(year_data: object, default: int = 0) -> int:
    if isinstance(year_data, dict):
        return int(year_data.get("year", default) or default)
    return int(getattr(year_data, "year", None) or default)


def _ebitda_values(year_data: object) -> Tuple[int, Decimal, Decimal]:
    if isinstance(year_data, dict):
        year = int(year_data.get("year", 0) or 0)
        ebitda_field = Decimal(str(year_data.get("ebitda", 0) or 0))
        meta = year_data.get("ebitda_normalization_metadata") or {}
    else:
        year = int(getattr(year_data, "year", None) or 0)
        ebitda_field = Decimal(str(getattr(year_data, "ebitda", 0) or 0))
        meta = getattr(year_data, "ebitda_normalization_metadata", None) or {}

    if isinstance(meta, dict) and meta.get("reported_ebitda") is not None:
        reported = Decimal(str(meta["reported_ebitda"]))
    else:
        reported = ebitda_field

    if isinstance(meta, dict) and meta.get("normalized_ebitda") is not None:
        normalized = Decimal(str(meta["normalized_ebitda"]))
    else:
        normalized = ebitda_field

    return year, reported, normalized


def _selected_years_and_weights(
    request: ValuationRequest,
    ordered_years: list[object],
) -> tuple[list[object], tuple[Decimal, ...]]:
    raw_weighting_mode = (
        str(getattr(request, "historical_ebitda_weighting_mode", "standard") or "standard")
        .strip()
        .lower()
    )
    raw_weights = getattr(request, "historical_ebitda_weights", None)

    if hasattr(raw_weights, "items"):
        custom_weights = {
            int(year): Decimal(str(weight))
            for year, weight in raw_weights.items()
            if Decimal(str(weight)) >= 0
        }
        custom_total = sum(custom_weights.values(), Decimal("0"))
        if custom_total > Decimal("1.5"):
            custom_weights = {
                year: weight / Decimal("100") for year, weight in custom_weights.items()
            }
            custom_total = sum(custom_weights.values(), Decimal("0"))
        if raw_weighting_mode == "weighted" and custom_total > 0:
            selected_years = [
                year_data for year_data in ordered_years if _year_value(year_data) in custom_weights
            ][:5]
            weights_desc = tuple(
                custom_weights[_year_value(year_data)] / custom_total
                for year_data in selected_years
            )
            return selected_years, weights_desc

    selected_years = ordered_years[:5]
    weight = Decimal("1") / Decimal(len(selected_years)) if selected_years else Decimal("0")
    return selected_years, tuple(weight for _ in selected_years)


def extract_multi_year_ebitda(
    response: ValuationResponse,
    request: Optional[ValuationRequest],
) -> Optional[List[YearlyEBITDA]]:
    """Extract multi-year EBITDA data using the canonical report year set."""
    if not request:
        return None

    historical = getattr(request, "historical_years_data", None) or []
    current = getattr(request, "current_year_data", None)
    if not historical and not current:
        return None

    series_by_year = {}
    for year_data in historical:
        year = (
            year_data.get("year")
            if isinstance(year_data, dict)
            else getattr(year_data, "year", None)
        )
        key = year if year is not None else id(year_data)
        series_by_year[key] = year_data

    if current:
        current_year = getattr(current, "year", None)
        key = current_year if current_year is not None else id(current)
        series_by_year[key] = current

    ordered_years = sorted(
        series_by_year.values(),
        key=lambda year_data: _year_value(year_data),
        reverse=True,
    )

    selected_years, weights_desc = _selected_years_and_weights(request, ordered_years)
    filing_year = primary_filing_year_for_report_data(
        request=request,
        response=response,
        multi_year=selected_years,
    )

    rows_data: List[Tuple[int, Decimal, Decimal, Decimal]] = []
    for index, year_data in enumerate(selected_years):
        weight = weights_desc[index] if index < len(weights_desc) else Decimal("0")
        year, reported, normalized = _ebitda_values(year_data)
        if year == 0:
            year = filing_year - index
        rows_data.append((year, reported, normalized, weight))

    if not rows_data:
        return None

    base = max(row[0] for row in rows_data)
    raw_loc = str(getattr(request, "locale", None) or "en")
    country_code = getattr(request, "country_code", None) or "BE"
    country_code = str(country_code).strip().upper() or "BE"
    translations = get_translations(
        normalize_report_locale(raw_loc),
        country_code=country_code,
    )

    years: List[YearlyEBITDA] = []
    for year, reported, normalized, weight in rows_data:
        years.append(
            YearlyEBITDA(
                year=year,
                year_display=format_year_column_with_filing_role(year, base, translations),
                reported_ebitda=reported,
                normalized_ebitda=normalized,
                weight=weight,
            )
        )

    return years
