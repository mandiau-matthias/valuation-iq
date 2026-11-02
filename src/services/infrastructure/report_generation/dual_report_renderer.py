"""Dual HTML report renderer for screen and PDF report variants."""

import asyncio
from typing import Mapping, Optional, Protocol

from src.services.infrastructure.html_report_safety_net import (
    build_html_service_safety_net_reports,
)
from src.services.infrastructure.template_service import TemplateService
from src.services.reports.report_presentation_surface import (
    screen_context_for_presentation_surface,
)
from src.services.reports.report_assurance import report_assurance_projection
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)


class DualReportLogger(Protocol):
    def error(
        self,
        msg: object,
        *args: object,
        exc_info: object = ...,
        extra: Optional[Mapping[str, object]] = ...,
        **kwargs: object,
    ) -> None: ...

    def warning(
        self,
        msg: object,
        *args: object,
        extra: Optional[Mapping[str, object]] = ...,
        **kwargs: object,
    ) -> None: ...


class ReportContextAggregator(Protocol):
    def aggregate(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        *,
        locale: str,
    ) -> dict[str, object]: ...


def _canonical_run_from_response(response: object) -> object | None:
    raw_run = getattr(response, "valuation_run", None)
    if raw_run is None and isinstance(response, Mapping):
        raw_run = response.get("valuation_run")
    if not isinstance(raw_run, dict) or raw_run.get("schema_version") != "valuation_run.v2":
        return None
    from src.api.schemas.valuation_contracts import ValuationRunV2

    try:
        return ValuationRunV2.model_validate(raw_run)
    except (TypeError, ValueError):
        return None


def ensure_calculate_context_assurance_projection(
    template_context: dict[str, object],
    response: object,
    *,
    locale: str,
    logger: DualReportLogger,
    context: Mapping[str, object],
) -> None:
    """Project assurance labels into a calculate-time context that lacks them.

    ``/reports/render`` builds its context through ``report_context_builder``,
    which always runs ``report_assurance_projection``. The calculate-time path
    aggregates straight from the engine response and historically skipped it,
    so the screen template drew the advisor-workspace certification chip with
    no label - an empty white box on the cover. Presentation only: a failure
    here never breaks the render, and the projection defaults to
    legacy/uncertified when no canonical run is present.
    """
    if "report_certification_status" in template_context:
        return
    try:
        template_context.update(
            report_assurance_projection(_canonical_run_from_response(response), locale=locale)
        )
    except Exception as exc:  # noqa: BLE001 - presentation only
        logger.warning(
            "Report assurance projection skipped for calculate-time render",
            extra={
                **context,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )


async def generate_dual_report_variants(
    *,
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    aggregator: ReportContextAggregator,
    template_service: TemplateService,
    logger: DualReportLogger,
    context: Mapping[str, object],
    locale: str,
    rendering_timeout_seconds: float,
    screen_min_length: int,
    pdf_min_length: int = 500,
) -> dict[str, object]:
    """Render screen and WeasyPrint report variants with one coherent safety net."""
    template_context: Optional[dict[str, object]] = None
    try:
        template_context = aggregator.aggregate(response, request, locale=locale)
    except Exception as agg_err:  # noqa: BLE001 — safety net is intentional
        logger.error(
            "🛟 [HTML-SAFETY-NET] Report context aggregation failed — falling back: "
            f"{type(agg_err).__name__}: {agg_err}",
            extra={
                **context,
                "error_type": type(agg_err).__name__,
                "error_message": str(agg_err),
            },
            exc_info=True,
        )
        return build_html_service_safety_net_reports(
            response,
            request,
            locale=locale,
            reason=f"aggregator_failed:{type(agg_err).__name__}",
            context=context,
        )

    ensure_calculate_context_assurance_projection(
        template_context,
        response,
        locale=locale,
        logger=logger,
        context=context,
    )

    # Defensibility asking-price gate. Mirrors the /render and /pdf endpoints
    # in reports.py — without this, the calculate-time html_report shows the
    # full +5..10% buffer even for LIMITED_SCOPE reports while the same
    # request via /render later collapses it to the equity midpoint. Three
    # Towers Capital regression (2026-05-26): the user's report read
    # "Voorgestelde Vraagprijs €404K (+5,1%)" even though the gate log
    # confirmed "Asking-price buffer suppressed" on subsequent /render calls.
    # Wrapped in try/except so a gate failure never breaks the render path.
    try:
        from src.services.defensibility import (
            apply_asking_price_gate,
            build_engine_side_gate_input,
        )

        gate_input = build_engine_side_gate_input(request, response)
        apply_asking_price_gate(template_context, gate_input)
    except Exception as gate_err:  # noqa: BLE001 — gate must never break render
        logger.warning(
            "Defensibility asking-price gate skipped — non-blocking",
            extra={
                **context,
                "error_type": type(gate_err).__name__,
                "error_message": str(gate_err),
            },
        )

    screen_context = screen_context_for_presentation_surface(
        template_context,
        presentation_surface=getattr(request, "presentation_surface", None),
        locale=locale,
    )

    html: Optional[str] = None
    try:
        html = await asyncio.wait_for(
            asyncio.to_thread(
                template_service.render_main_report,
                screen_context,
                locale,
            ),
            timeout=rendering_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.error(
            "🛟 [HTML-SAFETY-NET] Main report rendering timed out — falling back",
            extra={**context, "timeout_s": rendering_timeout_seconds},
        )
    except Exception as render_err:  # noqa: BLE001
        logger.error(
            "🛟 [HTML-SAFETY-NET] Main report render raised — falling back",
            extra={
                **context,
                "error_type": type(render_err).__name__,
                "error_message": str(render_err),
            },
            exc_info=True,
        )

    pdf_html_result: Optional[str] = None
    try:
        pdf_html_result = await asyncio.wait_for(
            asyncio.to_thread(
                template_service.render_main_report_pdf,
                template_context,
                locale,
            ),
            timeout=rendering_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.error(
            "🛟 [HTML-SAFETY-NET] PDF HTML rendering timed out — falling back",
            extra={**context, "timeout_s": rendering_timeout_seconds},
        )
    except Exception as render_err:  # noqa: BLE001
        logger.error(
            "🛟 [HTML-SAFETY-NET] PDF HTML render raised — falling back",
            extra={
                **context,
                "error_type": type(render_err).__name__,
                "error_message": str(render_err),
            },
            exc_info=True,
        )

    screen_ok = isinstance(html, str) and len(html.strip()) >= screen_min_length
    pdf_ok = isinstance(pdf_html_result, str) and len(pdf_html_result.strip()) >= pdf_min_length

    if screen_ok and pdf_ok:
        return {
            "html_report": html,
            "pdf_html_report": pdf_html_result,
            "report_context": template_context,
        }

    logger.warning(
        "🛟 [HTML-SAFETY-NET] One or both rendered outputs invalid — substituting safety-net HTML",
        extra={
            **context,
            "screen_html_ok": screen_ok,
            "screen_html_length": len(html) if isinstance(html, str) else 0,
            "pdf_html_ok": pdf_ok,
            "pdf_html_length": len(pdf_html_result) if isinstance(pdf_html_result, str) else 0,
        },
    )
    safety = build_html_service_safety_net_reports(
        response,
        request,
        locale=locale,
        reason="rendered_output_too_short",
        context=context,
    )
    if screen_ok:
        safety["html_report"] = html
    if pdf_ok:
        safety["pdf_html_report"] = pdf_html_result

    merged_ctx = dict(template_context)
    report_context = safety.get("report_context", {})
    safety_net = report_context.get("safety_net", {}) if isinstance(report_context, dict) else {}
    merged_ctx["safety_net"] = safety_net
    safety["report_context"] = merged_ctx
    return safety
