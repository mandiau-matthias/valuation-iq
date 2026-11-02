"""Typed contracts for the main-report aggregation boundary.

The template context is intentionally broad, but the public aggregator
boundary should still make its required shape explicit. Keep this module
small and dependency-light so section builders can import it without pulling
in the monolithic aggregator.
"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Literal,
    Mapping,
    MutableMapping,
    NotRequired,
    Required,
    TypedDict,
    cast,
)

if TYPE_CHECKING:
    from src.services.infrastructure.translations import ReportTranslations

ReportLocale = Literal["nl", "en", "fr"]


class ReportValidationContext(TypedDict):
    missing_required: list[str]
    optional_warnings: list[str]
    is_complete: bool
    completeness_score: int


class MainReportContext(TypedDict, total=False):
    report_id: Required[str]
    company_name: Required[str]
    valuation_date: Required[str]
    valuation: Required[float]
    valuation_low: Required[float]
    valuation_high: Required[float]
    sustainable_ebitda: Required[float]
    applied_multiple: Required[float]
    industry: Required[str]
    industry_emoji: Required[str]
    ebitda_adjustments: Required[list[object]]
    calibration_steps: Required[list[object]]
    _validation: Required[ReportValidationContext]
    t: Required["ReportTranslations"]
    locale: Required[ReportLocale]
    step_data: NotRequired[Mapping[str, object]]
    startup_report: NotRequired[Mapping[str, object]]
    liquidation_report: NotRequired[Mapping[str, object]]


MAIN_REPORT_REQUIRED_CONTEXT_KEYS = (
    "report_id",
    "company_name",
    "valuation_date",
    "valuation",
    "valuation_low",
    "valuation_high",
    "sustainable_ebitda",
    "applied_multiple",
    "industry",
    "industry_emoji",
    "ebitda_adjustments",
    "calibration_steps",
    "_validation",
    "t",
    "locale",
)


class MainReportContextContractError(ValueError):
    """Raised when aggregation exits without the template's core contract."""


def missing_main_report_context_keys(context: Mapping[str, object]) -> list[str]:
    return [key for key in MAIN_REPORT_REQUIRED_CONTEXT_KEYS if key not in context]


def assert_main_report_context(context: MutableMapping[str, object]) -> MainReportContext:
    missing = missing_main_report_context_keys(context)
    if missing:
        raise MainReportContextContractError(
            f"Main report context is missing required key(s): {', '.join(missing)}"
        )

    validation = context.get("_validation")
    if not isinstance(validation, Mapping):
        raise MainReportContextContractError("Main report context _validation must be a mapping")
    if validation.get("is_complete") is not True:
        raise MainReportContextContractError("Main report context must be complete before render")
    if context.get("locale") not in ("nl", "en", "fr"):
        raise MainReportContextContractError(
            "Main report context locale must be 'nl', 'en', or 'fr'"
        )

    return cast(MainReportContext, context)
