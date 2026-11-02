"""Metric presentation context for the simplified report transformer."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

from src.services.infrastructure.simplified_report_formatting import (
    format_currency,
    format_currency_exact,
    safe_decimal,
)
from src.services.infrastructure.simplified_report_types import JsonRows
from src.services.infrastructure.translations import get_translations, normalize_report_locale


@dataclass(frozen=True)
class MetricPresentationContext:
    ebitda: Decimal
    metric_type: str
    metric_value: Decimal
    ebitda_formatted_for_display: str
    metric_basis_label: str
    multiple_display_label: str
    use_weighted_for_valuation: bool


def build_metric_presentation_context(
    *,
    request: object | None,
    ebitda: Decimal,
    revenue: Decimal,
    multi_year: JsonRows,
    metric_type: str,
    sde_basis: Optional[Decimal],
    request_locale: str,
) -> MetricPresentationContext:
    weighted_total_numeric = _weighted_total_numeric(multi_year)
    use_weighted_for_valuation = _should_use_weighted_for_valuation(
        metric_type,
        multi_year,
        weighted_total_numeric,
    )
    ebitda, metric_value, ebitda_formatted = _metric_value_and_ebitda_display(
        ebitda=ebitda,
        revenue=revenue,
        multi_year=multi_year,
        metric_type=metric_type,
        weighted_total_numeric=weighted_total_numeric,
        use_weighted_for_valuation=use_weighted_for_valuation,
        sde_basis=sde_basis,
    )
    metric_basis_label, multiple_display_label = _metric_display_labels(
        metric_type,
        request,
        request_locale,
    )
    return MetricPresentationContext(
        ebitda=ebitda,
        metric_type=metric_type,
        metric_value=metric_value,
        ebitda_formatted_for_display=ebitda_formatted,
        metric_basis_label=metric_basis_label,
        multiple_display_label=multiple_display_label,
        use_weighted_for_valuation=use_weighted_for_valuation,
    )


def _weighted_total_numeric(multi_year: JsonRows) -> Decimal:
    if not multi_year:
        return Decimal("0")
    return sum(safe_decimal(row.get("weighted")) for row in multi_year)


def _should_use_weighted_for_valuation(
    metric_type: str,
    multi_year: JsonRows,
    weighted_total_numeric: Decimal,
) -> bool:
    return (
        metric_type == "EBITDA" and len(multi_year) >= 2 and weighted_total_numeric > Decimal("0")
    )


def _metric_value_and_ebitda_display(
    *,
    ebitda: Decimal,
    revenue: Decimal,
    multi_year: JsonRows,
    metric_type: str,
    weighted_total_numeric: Decimal,
    use_weighted_for_valuation: bool,
    sde_basis: Optional[Decimal],
) -> Tuple[Decimal, Decimal, str]:
    show_weighted_in_table = len(multi_year) >= 2 and weighted_total_numeric > Decimal("0")
    if metric_type == "SDE":
        metric_value = sde_basis if sde_basis is not None else Decimal("0")
        return ebitda, metric_value, format_currency(metric_value)
    if use_weighted_for_valuation:
        ebitda = weighted_total_numeric
        metric_value = revenue if metric_type == "REVENUE" else ebitda
        return ebitda, metric_value, format_currency_exact(ebitda)
    if show_weighted_in_table:
        metric_value = revenue if metric_type == "REVENUE" else ebitda
        return ebitda, metric_value, format_currency_exact(weighted_total_numeric)
    metric_value = revenue if metric_type == "REVENUE" else ebitda
    return ebitda, metric_value, format_currency(ebitda)


def _metric_display_labels(
    metric_type: str,
    request: object | None,
    request_locale: str,
) -> Tuple[str, str]:
    if metric_type == "REVENUE":
        return "Omzet", "EV/Revenue"
    if metric_type == "SDE":
        return _sde_display_labels(request, request_locale)
    return "Genormaliseerde EBITDA (gewogen)", "EV/EBITDA"


def _sde_display_labels(
    request: object | None,
    request_locale: str,
) -> Tuple[str, str]:
    country_code = (getattr(request, "country_code", None) or "BE") if request else "BE"
    country_code = str(country_code).strip().upper() or "BE"
    report_locale = normalize_report_locale(request_locale)
    translations = get_translations(report_locale, country_code=country_code)
    return translations.wf_basis_sde_short, "EV/SDE"
