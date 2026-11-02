"""Final validation boundary for main-report aggregation."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Callable, Optional, Protocol

from src.services.reports.main_report_context_postprocessing import (
    BridgeCashSplitContext,
    MainReportMethodologyContext,
    apply_main_report_post_build_context,
)
from src.services.reports.main_report_contracts import (
    MainReportContext,
    ReportLocale,
    assert_main_report_context,
)
from src.services.reports.report_context_finalizer import finalize_report_context

if TYPE_CHECKING:
    from src.services.infrastructure.translations import ReportTranslations


ReportContextValidator = Callable[
    [dict[str, object], Optional["ReportTranslations"]],
    tuple[list[str], list[str]],
]
ReportCompletenessScorer = Callable[[dict[str, object]], int]


class ReportAggregationLogger(Protocol):
    def debug(self, message: str, *args: object, **kwargs: object) -> None:
        """Log debug report aggregation events."""

    def info(self, message: str, *args: object, **kwargs: object) -> None:
        """Log informational report aggregation events."""


class MainReportPostBuildAggregator(Protocol):
    logger: ReportAggregationLogger

    def _extract_dcf_data(self, *args: object, **kwargs: object) -> dict[str, object]: ...

    def _extract_sde_data(self, *args: object, **kwargs: object) -> dict[str, object]: ...

    def _extract_sde_cross_check(self, *args: object, **kwargs: object) -> dict[str, object]: ...

    def _extract_hybrid_weights(self, *args: object, **kwargs: object) -> dict[str, object]: ...

    def _extract_report_intelligence(
        self, *args: object, **kwargs: object
    ) -> dict[str, object]: ...

    def _promote_upswitch_adaptive_from_valuation_results(
        self, *args: object, **kwargs: object
    ) -> None: ...

    def _validate_context(
        self, context: dict[str, object], translations: "ReportTranslations"
    ) -> tuple[list[str], list[str]]: ...

    def _calculate_completeness_score(self, context: dict[str, object]) -> int: ...


def apply_and_finalize_main_report_context(
    context: dict[str, object],
    *,
    aggregator: MainReportPostBuildAggregator,
    response: object,
    request: object | None,
    request_metadata: Optional[dict[str, object]],
    locale: str,
    report_locale: ReportLocale,
    translations: "ReportTranslations",
    show_bridge_cash_split: bool,
    bridge_cash_total: Decimal,
    bridge_operating_cash_held: Decimal,
    bridge_excess_cash: Decimal,
    bridge_ib_debt: Decimal,
) -> MainReportContext:
    """Apply post-build enrichment, then validate and type-check the report context."""
    post_build_request_metadata = request_metadata if request else None
    dcf_data = aggregator._extract_dcf_data(response, locale, translations, request)
    sde_data = aggregator._extract_sde_data(response, request, locale=locale, t=translations)
    apply_main_report_post_build_context(
        context,
        response=response,
        request=request,
        locale=locale,
        report_locale=report_locale,
        translations=translations,
        methodology=MainReportMethodologyContext(
            request_metadata=post_build_request_metadata,
            dcf_data=dcf_data,
            sde_data=sde_data,
            sde_cross_check=aggregator._extract_sde_cross_check(
                response, request, sde_data, t=translations
            ),
            hybrid_data=aggregator._extract_hybrid_weights(response, locale, translations, request),
            report_intelligence=aggregator._extract_report_intelligence(
                response, request, locale, translations
            ),
            promote_upswitch_adaptive=lambda: aggregator._promote_upswitch_adaptive_from_valuation_results(
                response, context, locale=locale
            ),
        ),
        bridge_cash_split=BridgeCashSplitContext(
            show_bridge_cash_split=show_bridge_cash_split,
            bridge_cash_total=bridge_cash_total,
            bridge_operating_cash_held=bridge_operating_cash_held,
            bridge_excess_cash=bridge_excess_cash,
            bridge_ib_debt=bridge_ib_debt,
        ),
        logger=aggregator.logger,
    )

    return finalize_validated_main_report_context(
        context,
        response=response,
        request_metadata=post_build_request_metadata,
        locale=locale,
        report_locale=report_locale,
        translations=translations,
        validate_context=aggregator._validate_context,
        calculate_completeness_score=aggregator._calculate_completeness_score,
        logger=aggregator.logger,
    )


def finalize_validated_main_report_context(
    context: dict[str, object],
    *,
    response: object,
    request_metadata: Optional[dict[str, object]],
    locale: str,
    report_locale: ReportLocale,
    translations: "ReportTranslations",
    validate_context: ReportContextValidator,
    calculate_completeness_score: ReportCompletenessScorer,
    logger: ReportAggregationLogger,
) -> MainReportContext:
    """Finalize, validate, stamp, and type-check the rendered report context."""
    finalize_report_context(
        context,
        locale=locale,
        metadata=request_metadata,
        include_attestation=True,
        refresh_adaptive_gates=True,
    )

    # Belt-and-suspenders: defensively localise the Adaptive page rationale at
    # the final stage. The earlier `promote_upswitch_adaptive_context` already
    # runs the localiser, but if a persisted_context overlay or cache key
    # squashes the fresh value (Three Towers Capital regression, 2026-05-26),
    # the English engine prose ("HYBRID methodology was requested, but DCF was
    # excluded...") leaks into a Dutch report. Re-running the pattern matcher
    # here is a no-op when the text already matches a localised template, and
    # catches the leak otherwise.
    if report_locale in ("nl", "fr"):
        justification = context.get("adaptive_methodology_justification")
        if isinstance(justification, str) and justification.strip():
            if report_locale == "nl":
                from src.services.reports.report_quality_warnings import (
                    _localise_substitution_reason_to_nl as _localise_justification,
                )
            else:
                from src.services.reports.report_quality_warnings import (
                    _localise_substitution_reason_to_fr as _localise_justification,
                )
            localised = _localise_justification(justification)
            if localised != justification:
                context["adaptive_methodology_justification"] = localised

    missing_required, optional_warnings = validate_context(context, translations)
    company_name = getattr(response, "company_name", "unknown")

    if missing_required:
        raise ValueError(
            f"Aggregation produced incomplete context for {company_name}: "
            f"missing required fields {missing_required}. "
            "Report cannot render without these values."
        )

    if optional_warnings:
        # DEBUG: optional-data notes (e.g., "KBO-gegevens niet beschikbaar")
        # surface on the report itself as Onvolledige-data badges; the log
        # line was duplicating that surface.
        logger.debug(
            f"[AGGREGATOR] Optional data notes: {optional_warnings}",
            extra={
                "warnings": optional_warnings,
                "company_name": getattr(response, "company_name", None),
            },
        )

    validation_context: dict[str, object] = {
        "missing_required": [],
        "optional_warnings": optional_warnings,
        "is_complete": True,
        "completeness_score": calculate_completeness_score(context),
    }
    context["_validation"] = validation_context
    context["t"] = translations
    context["locale"] = report_locale

    # DEBUG: aggregator exit ack. The caller's AUDIT line (POST /reports/...)
    # and the per-report intermediate INFOs (LIMITED_SCOPE, missing-data
    # warnings) carry the operational signal.
    logger.debug(
        f"✅ [AGGREGATOR] Data aggregation complete for {company_name}",
        extra={
            "context_keys": list(context.keys()),
            "valuation": context["valuation"],
            "ebitda": context["sustainable_ebitda"],
            "completeness_score": validation_context["completeness_score"],
        },
    )

    return assert_main_report_context(context)
