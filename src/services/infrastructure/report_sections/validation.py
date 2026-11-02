"""
Report Context Validation

Validates that the aggregated template context contains all required fields
before the template engine renders the report.  Returns structured lists of
missing/warning fields so the caller can decide whether to proceed.
"""

from decimal import Decimal, InvalidOperation
from typing import Optional, TypeAlias, cast

from src.services.infrastructure.translations import (
    ReportTranslations,
    get_translations,
    normalize_report_locale,
)

JsonMap: TypeAlias = dict[str, object]
REQUIRED_FIELDS = (
    "company_name",
    "valuation",
    "sustainable_ebitda",
)
RECOMMENDED_FIELDS = (
    "valuation_date",
    "report_id",
    "ebitda_adjustments",
)
OPTIONAL_FIELDS = (
    "industry",
    "revenue",
    "kbo_number",
    "legal_form",
    "founded_year",
    "employee_count",
    "comparables_count",
    "data_quality_score",
    "benchmark_ev_ebitda_p50",
    "calibration_steps",
    "trial_balance_anomalies",
    "nwc_normalization",
    "market_data_provenance",
)
REGISTRY_OPTIONAL_FIELDS = {"kbo_number", "legal_form", "founded_year"}


def _context_indicates_startup_valuation_report(context: JsonMap) -> bool:
    """True when the report is the venture/startup stack (not SME multiples-first).

    Prefer the aggregator-set flag; also accept a non-empty ``startup_report``
    payload so validation stays aligned with templates if keys ever diverge.
    """
    if bool(context.get("is_startup_valuation_report")):
        return True
    sr = context.get("startup_report")
    return isinstance(sr, dict) and bool(sr)


def _missing_method_multiples(context: JsonMap) -> list[str]:
    """Validate each displayed method's metric-specific saved multiple.

    A valid revenue or SDE cross-check does not require an EBITDA multiple.
    Conversely, a valid EBITDA multiple cannot admit an unpriced revenue page.
    The SDE field precedence matches the screen and PDF templates exactly.
    """
    if context.get("is_fiscal_method_only") or context.get("is_holding_sotp_method"):
        return []
    fields = (
        ("has_ebitda_multiple_page", "applied_multiple"),
        ("has_revenue_multiple_page", "revenue_multiple_applied"),
        ("has_sde_page", "sde_multiple" if "sde_multiple" in context else "sde_base_multiple"),
    )
    missing: list[str] = []
    for page, field in fields:
        if not context.get(page):
            continue
        value = context.get(field)
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            missing.append(field)
            continue
        try:
            multiple = Decimal(str(value))
        except InvalidOperation:
            missing.append(field)
            continue
        if not multiple.is_finite() or multiple <= 0:
            missing.append(field)
    return missing


def _translations_for_context(
    context: JsonMap,
    t: Optional[ReportTranslations],
) -> ReportTranslations:
    if t is not None:
        return t
    raw_locale = context.get("locale")
    locale = normalize_report_locale(raw_locale if isinstance(raw_locale, str) else None)
    country_code = str(context.get("country_code") or "BE").strip().upper() or "BE"
    return get_translations(locale, country_code=country_code)


def _missing_required_fields(
    context: JsonMap,
    t: ReportTranslations,
) -> list[str]:
    is_startup_report = _context_indicates_startup_valuation_report(context)

    missing_required: list[str] = []
    for field in REQUIRED_FIELDS:
        if is_startup_report and field == "sustainable_ebitda":
            continue

        value = context.get(field)
        if value is None:
            missing_required.append(field)
        elif field == "valuation" and value == 0:
            missing_required.append(t.report_validation_required_zero.format(field=field))
    if not is_startup_report:
        missing_required.extend(_missing_method_multiples(context))
    return missing_required


def _missing_recommended_warnings(
    context: JsonMap,
    t: ReportTranslations,
) -> list[str]:
    warnings: list[str] = []
    for field in RECOMMENDED_FIELDS:
        value = context.get(field)
        if value is None or (isinstance(value, list) and len(value) == 0):
            warnings.append(t.report_validation_missing_recommended.format(field=field))
    return warnings


def _registry_label(context: JsonMap, t: ReportTranslations) -> object:
    if context.get("registry_name"):
        return context["registry_name"]
    if context.get("country_code") == "NL":
        return t.report_registry_short_kvk
    return t.report_registry_short_kbo


def _optional_field_warning(
    *,
    field: str,
    context: JsonMap,
    t: ReportTranslations,
) -> str | None:
    if field in REGISTRY_OPTIONAL_FIELDS:
        return cast(str, t.report_validation_registry_unavailable).format(
            registry=_registry_label(context, t),
            field=field,
        )
    if field == "comparables_count":
        return cast(str, t.report_validation_no_comparables)
    if field == "benchmark_ev_ebitda_p50":
        return cast(str, t.report_validation_no_benchmark)
    return None


def _optional_warnings(context: JsonMap, t: ReportTranslations) -> list[str]:
    warnings = _missing_recommended_warnings(context, t)
    for field in OPTIONAL_FIELDS:
        if context.get(field) is not None:
            continue
        warning = _optional_field_warning(field=field, context=context, t=t)
        if warning:
            warnings.append(warning)

    if context.get("has_dcf") and not context.get("has_market_data_provenance"):
        warnings.append(t.report_validation_no_dcf_provenance)
    return warnings


def validate_report_context(
    context: JsonMap,
    t: Optional[ReportTranslations] = None,
) -> tuple[list[str], list[str]]:
    """Validate report context for required fields.

    Returns:
        (missing_required, optional_warnings)
    """
    resolved_translations = _translations_for_context(context, t)
    return (
        _missing_required_fields(context, resolved_translations),
        _optional_warnings(context, resolved_translations),
    )
