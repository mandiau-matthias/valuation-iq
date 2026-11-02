"""Business label and icon display context for reports."""

from collections.abc import Mapping
from dataclasses import dataclass

from src.domain.report_contact.sanitize import is_legal_form_label
from src.services.reports.business_label_localization import localize_business_label
from src.services.reports.report_industry_display import (
    BusinessTypeDisplayEntry,
    get_business_type_display_by_nace,
    get_industry_emoji,
)


@dataclass(frozen=True)
class BusinessDisplayContext:
    industry: str | None
    business_type_title: str | None
    business_type_icon: str
    sector: str | None


def _localized_label(value: object, locale: str) -> str | None:
    return localize_business_label(str(value) if value is not None else None, locale)


def _benchmark_nace_code(industry_benchmarks: Mapping[str, object]) -> str:
    benchmark_nace = (
        industry_benchmarks.get("source_primary_nace_code")
        or industry_benchmarks.get("primary_nace_code")
        or industry_benchmarks.get("nace_code")
    )
    return str(benchmark_nace or "")


def _business_type_display_by_nace(
    *,
    nace_code: str | None,
    industry_benchmarks: Mapping[str, object],
) -> BusinessTypeDisplayEntry | None:
    return get_business_type_display_by_nace(nace_code or _benchmark_nace_code(industry_benchmarks))


def _display_industry(
    *,
    industry: str | None,
    localized_business_type_title: str | None,
    localized_nace_title: str | None,
    localized_business_type_id: str | None,
    locale: str,
) -> str | None:
    return (
        localize_business_label(industry, locale)
        or localized_business_type_title
        or localized_nace_title
        or localized_business_type_id
    )


def _display_business_type_title(
    *,
    localized_business_type_title: str | None,
    localized_nace_title: str | None,
    display_industry: str | None,
    localized_business_type_id: str | None,
) -> str | None:
    return (
        localized_business_type_title
        or localized_nace_title
        or display_industry
        or localized_business_type_id
    )


def _is_generic_business_icon(value: object) -> bool:
    return not value or value == "🏢"


def _catalog_icon_candidate(
    *,
    business_type_id: str | None,
    nace_display: BusinessTypeDisplayEntry | None,
    display_business_type_title: str | None,
    display_industry: str | None,
) -> str:
    icon_candidate = get_industry_emoji(business_type_id) if business_type_id else None
    if _is_generic_business_icon(icon_candidate) and nace_display and nace_display.icon:
        icon_candidate = nace_display.icon
    if _is_generic_business_icon(icon_candidate):
        icon_candidate = get_industry_emoji(display_business_type_title or display_industry)
    return str(icon_candidate or "🏢")


def _display_business_type_icon(
    *,
    industry_benchmarks: Mapping[str, object],
    business_type_id: str | None,
    nace_display: BusinessTypeDisplayEntry | None,
    display_business_type_title: str | None,
    display_industry: str | None,
) -> str:
    benchmark_icon = industry_benchmarks.get("business_type_icon")
    if not _is_generic_business_icon(benchmark_icon):
        return str(benchmark_icon)
    return _catalog_icon_candidate(
        business_type_id=business_type_id,
        nace_display=nace_display,
        display_business_type_title=display_business_type_title,
        display_industry=display_industry,
    )


def _display_sector(industry_benchmarks: Mapping[str, object], locale: str) -> str | None:
    sector = _localized_label(industry_benchmarks.get("sector"), locale)
    if sector and is_legal_form_label(sector):
        return None
    return sector


def build_business_display_context(
    *,
    industry: str | None,
    business_type_id: str | None,
    nace_code: str | None = None,
    industry_benchmarks: Mapping[str, object],
    locale: str,
) -> BusinessDisplayContext:
    """Resolve localized business labels and a stable industry icon."""
    localized_business_type_title = _localized_label(
        industry_benchmarks.get("business_type_title"), locale
    )
    localized_business_type_id = localize_business_label(business_type_id, locale)
    nace_display = _business_type_display_by_nace(
        nace_code=nace_code,
        industry_benchmarks=industry_benchmarks,
    )
    localized_nace_title = localize_business_label(
        nace_display.title if nace_display else None,
        locale,
    )

    display_industry = _display_industry(
        industry=industry,
        localized_business_type_title=localized_business_type_title,
        localized_nace_title=localized_nace_title,
        localized_business_type_id=localized_business_type_id,
        locale=locale,
    )
    display_business_type_title = _display_business_type_title(
        localized_business_type_title=localized_business_type_title,
        localized_nace_title=localized_nace_title,
        display_industry=display_industry,
        localized_business_type_id=localized_business_type_id,
    )

    return BusinessDisplayContext(
        industry=display_industry,
        business_type_title=display_business_type_title,
        business_type_icon=_display_business_type_icon(
            industry_benchmarks=industry_benchmarks,
            business_type_id=business_type_id,
            nace_display=nace_display,
            display_business_type_title=display_business_type_title,
            display_industry=display_industry,
        ),
        sector=_display_sector(industry_benchmarks, locale),
    )
