"""PDF HTML construction and fallback policy for report routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from src.api.routes.report_context_builder import _build_report_context
from src.api.routes.report_payload_context import JsonMap, _looks_degenerate_preview_payload
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Keys whose values are determined by the defensibility verdict that the
# /pdf endpoint computed once on ``canonical_report_context`` (the gate
# decision used to authorise this PDF render). When the slow re-aggregation
# path runs (because canonical render failed or produced too-short HTML), the
# freshly-aggregated context recomputes its own verdict, which may diverge
# from the one that was promised to the caller. Overlay these keys so the
# embedded scope banner, submit-gate copy and asking-price buffer stay
# aligned with the verdict outside the function trusted.
_DEFENSIBILITY_OVERLAY_KEYS = (
    "defensibility_gate_passed",
    "defensibility_block_reason",
    "defensibility_checks",
    "defensibility_submit_recommendation",
    "defensibility_submit_reasons_en",
    "defensibility_submit_reasons_nl",
    "defensibility_submit_reasons_fr",
    "defensibility_warning_codes",
    "defensibility_auto_watermark",
    "defensibility_scope_banner_html",
    "recommended_asking_price",
    "recommended_asking_price_buffer_suppressed",
    "recommended_asking_price_buffer_reason",
)


def _overlay_pdf_defensibility_from_canonical(
    context: JsonMap,
    canonical: Optional[JsonMap],
) -> None:
    """Overlay the defensibility verdict from ``canonical`` onto ``context``.

    Mutates ``context`` in place. No-op when ``canonical`` is missing or not a
    dict (typical for direct ``_build_pdf_html`` callers that did not
    pre-compute a canonical context).
    """
    if not isinstance(canonical, dict):
        return
    for key in _DEFENSIBILITY_OVERLAY_KEYS:
        if key in canonical:
            context[key] = canonical[key]


def _build_pdf_html(
    valuation_data: JsonMap,
    company_name: str,
    report_id: str,
    locale: str = "nl",
    selected_method: str | None = None,
    *,
    canonical_report_context: Optional[JsonMap] = None,
    report_context_builder: Callable[..., JsonMap] = _build_report_context,
    render_outcome: Optional[dict[str, str]] = None,
) -> str:
    """
    Build WeasyPrint-optimized HTML for PDF generation.

    Always re-renders from valuation_data using main_report_pdf/ templates to
    guarantee the PDF matches the requested locale and uses the latest template
    version. Never uses pre-rendered HTML or screen HTML (main_report/).

    When ``canonical_report_context`` is supplied (same dict returned from a
    successful report-context build for this request), we render PDF HTML from
    it directly - no second aggregation - so the defensibility scope banner
    placement and body stay identical to the verdict embedded in that context.

    ROBUSTNESS CONTRACT
    -------------------
    Always returns a non-empty WeasyPrint-safe HTML string. If aggregation
    or templating fails, falls through to the shared safety-net builder
    (``safety_net_report.build_safety_net_reports``) which produces
    self-contained, inline-styled HTML from the raw numeric payload. This
    keeps the /pdf endpoint a guaranteed-success contract for downstream
    Titan callers (sync export + async BullMQ processor).

    RENDER OUTCOME
    --------------
    "Guaranteed success" must not mean "indistinguishable success". The PDF this
    HTML becomes is AES-256 encrypted, so a caller cannot inspect it: a one-page
    safety-net summary and the full 21-page report look identical on the wire
    (HTTP 200, application/pdf). When ``render_outcome`` is supplied it is filled
    with ``mode`` (``template`` | ``safety_net``) and, for the safety net, the
    ``reason`` — the route publishes both as response headers so the caller can
    refuse to store a summary as if it were the report.
    """
    from src.services.infrastructure.safety_net_report import (
        build_safety_net_reports as _build_safety_net,
    )
    from src.services.infrastructure.template_service import get_template_service

    rid = report_id[:8] if report_id else "unknown"

    # A value band with nothing behind it is not a report. /render already suppresses the
    # screen preview for such a payload; the templates here would print it as a ten-page
    # document stating "EUR 0" EBITDA and a "0,00x" multiple - missing values presented as
    # zeros (probed 2026-09-18). The safety-net summary prints a dash for what it does not
    # know, and the caller is told it received a summary (see RENDER OUTCOME).
    if _looks_degenerate_preview_payload(valuation_data):
        logger.warning(
            "PDF: sparse payload - summary instead of a templated report of zeros",
            extra={"report_id": rid, "company_name": company_name},
        )
        safety = _build_safety_net(
            valuation_data,
            company_name=company_name,
            locale=locale,
            reason="pdf_degenerate_payload",
            correlation_id=report_id,
        )
        if render_outcome is not None:
            render_outcome["mode"] = "safety_net"
            render_outcome["reason"] = "pdf_degenerate_payload"
        return safety["pdf_html_report"]

    if canonical_report_context is not None:
        try:
            template_service = get_template_service()
            html_fast = template_service.render_main_report_pdf(
                canonical_report_context, locale=locale
            )
            if html_fast and len(html_fast.strip()) >= 500:
                # DEBUG: TEMPLATE-SERVICE renders are logged at the lower layer.
                logger.debug(
                    "PDF: HTML rendered from canonical report context (single aggregation)",
                    extra={
                        "report_id": rid,
                        "company_name": company_name,
                        "html_length": len(html_fast),
                    },
                )
                if render_outcome is not None:
                    render_outcome["mode"] = "template"
                return html_fast
            logger.warning(
                "PDF: canonical context produced short HTML — re-aggregating",
                extra={"report_id": rid, "html_length": len(html_fast or "")},
            )
        except Exception as exc:
            logger.warning(
                "PDF: canonical context render failed — re-aggregating",
                extra={
                    "report_id": rid,
                    "company_name": company_name,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:300],
                },
                exc_info=False,
            )

    safety_reason: Optional[str] = None
    html: Optional[str] = None
    try:
        template_service = get_template_service()
        context = report_context_builder(
            valuation_data,
            company_name,
            report_id,
            locale=locale,
            selected_method=selected_method,
            include_persisted_context=True,
        )
        logger.info(
            "PDF: Aggregation complete (re-rendered, no pre-rendered pdf_html_report)",
            extra={
                "report_id": rid,
                "company": context.get("company_name"),
                "valuation": context.get("valuation"),
                "context_keys": len(context),
            },
        )
        _overlay_pdf_defensibility_from_canonical(context, canonical_report_context)
        html = template_service.render_main_report_pdf(context, locale=locale)
    except Exception as exc:
        logger.warning(
            (
                "PDF: template build failed (with persisted report_context) — "
                "retrying clean aggregation"
            ),
            extra={
                "report_id": rid,
                "company_name": company_name,
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:300],
            },
            exc_info=False,
        )
        try:
            context = report_context_builder(
                valuation_data,
                company_name,
                report_id,
                locale=locale,
                selected_method=selected_method,
                include_persisted_context=False,
            )
            logger.info(
                "PDF: Retry aggregation succeeded without persisted report_context",
                extra={
                    "report_id": rid,
                    "company": context.get("company_name"),
                    "valuation": context.get("valuation"),
                    "context_keys": len(context),
                },
            )
            template_service = get_template_service()
            _overlay_pdf_defensibility_from_canonical(context, canonical_report_context)
            html = template_service.render_main_report_pdf(context, locale=locale)
        except Exception as retry_exc:
            logger.warning(
                "PDF: retry without persisted report_context failed — falling back to safety-net",
                extra={
                    "report_id": rid,
                    "company_name": company_name,
                    "error_type": type(retry_exc).__name__,
                    "error_message": str(retry_exc)[:300],
                },
                exc_info=False,
            )
            safety_reason = f"pdf_template_exception:{type(retry_exc).__name__}"

    if safety_reason is None and (not html or len(html) < 500):
        safety_reason = "pdf_template_too_short"
        logger.warning(
            "PDF: template HTML too short — falling back to safety-net",
            extra={"report_id": rid, "html_length": len(html or "")},
        )

    if safety_reason is not None:
        safety = _build_safety_net(
            valuation_data,
            company_name=company_name,
            locale=locale,
            reason=safety_reason,
            correlation_id=report_id,
        )
        # Use the PDF-shaped output (table-based, A4 sized) - never the
        # screen variant - so WeasyPrint produces a clean printable doc.
        if render_outcome is not None:
            render_outcome["mode"] = "safety_net"
            render_outcome["reason"] = safety_reason
        return safety["pdf_html_report"]

    logger.info(
        "PDF: HTML rendered from main_report_pdf templates",
        extra={
            "report_id": rid,
            "company_name": company_name,
            "html_length": len(html or ""),
        },
    )
    if render_outcome is not None:
        render_outcome["mode"] = "template"
    return html  # type: ignore[return-value]
