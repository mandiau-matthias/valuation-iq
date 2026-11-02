"""
Historical FCF readiness context for the DCF report section.
"""

from dataclasses import dataclass
from decimal import Decimal

from src.services.infrastructure.report_sections.dcf_context_support import unwrap
from src.services.infrastructure.translations import ReportTranslations


@dataclass(frozen=True)
class DcfReadinessContext:
    raw: dict[str, object] | None
    status: object
    years: int
    capex_years: int
    tax_years: int
    nwc_years: int
    forecast_fcff_years: int
    missing_fields: list[str]
    note: str | None


def build_dcf_readiness_context(
    readiness: object,
    translations: ReportTranslations,
) -> DcfReadinessContext:
    readiness_dict = unwrap(readiness) if readiness is not None else None
    if not isinstance(readiness_dict, dict):
        readiness_dict = None

    years = _readiness_int(readiness_dict, "historical_years_count")
    capex_years = _readiness_int(readiness_dict, "actual_capex_years")
    tax_years = _readiness_int(readiness_dict, "actual_tax_years")
    nwc_years = _readiness_int(readiness_dict, "actual_nwc_years")
    forecast_fcff_years = _readiness_int(readiness_dict, "forecast_fcff_years")
    status = readiness_dict.get("status") if readiness_dict else None

    return DcfReadinessContext(
        raw=readiness_dict,
        status=status,
        years=years,
        capex_years=capex_years,
        tax_years=tax_years,
        nwc_years=nwc_years,
        forecast_fcff_years=forecast_fcff_years,
        missing_fields=_missing_readiness_fields(
            translations=translations,
            readiness_dict=readiness_dict,
            status=status,
            years=years,
            capex_years=capex_years,
            tax_years=tax_years,
            nwc_years=nwc_years,
        ),
        note=_readiness_note(
            translations=translations,
            status=status,
            years=years,
            capex_years=capex_years,
            tax_years=tax_years,
            nwc_years=nwc_years,
            forecast_fcff_years=forecast_fcff_years,
        ),
    )


def parse_optional_decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value)) if value is not None else None
    except (ValueError, TypeError):
        return None


def _readiness_int(readiness_dict: dict[str, object] | None, key: str) -> int:
    return int(readiness_dict.get(key, 0) or 0) if readiness_dict else 0


def _missing_readiness_fields(
    *,
    translations: ReportTranslations,
    readiness_dict: dict[str, object] | None,
    status: object,
    years: int,
    capex_years: int,
    tax_years: int,
    nwc_years: int,
) -> list[str]:
    if not readiness_dict:
        return []
    if status == "explicit_fcff_forecast":
        return []
    missing_fields: list[str] = []
    if capex_years < years:
        missing_fields.append(translations.dcf_missing_field_label_capex)
    if tax_years < years:
        missing_fields.append(translations.dcf_missing_field_label_tax)
    if nwc_years < max(0, years - 1):
        missing_fields.append(translations.dcf_missing_field_label_nwc)
    return missing_fields


def _readiness_note(
    *,
    translations: ReportTranslations,
    status: object,
    years: int,
    capex_years: int,
    tax_years: int,
    nwc_years: int,
    forecast_fcff_years: int,
) -> str | None:
    if status == "explicit_fcff_forecast":
        return translations.dcf_readiness_note_explicit_fcff.format(
            forecast_years=forecast_fcff_years,
        )
    if status == "imported_ready":
        return translations.dcf_readiness_note_imported_ready.format(
            years=years,
            capex_years=capex_years,
            tax_years=tax_years,
            nwc_years=nwc_years,
        )
    if status == "partial":
        return translations.dcf_readiness_note_partial.format(
            capex_years=capex_years,
            tax_years=tax_years,
            nwc_years=nwc_years,
        )
    if status == "manual_fallback":
        return translations.dcf_readiness_note_manual_fallback
    return None
