"""
Reports API Router - Titan Integration

Provides /api/v1/reports/* endpoints for Titan to call ValuationIQ.

PDF architecture: screen and PDF templates use the same MainReportDataAggregator
context. Aggregation/rendering failures surface instead of falling back silently.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import NoReturn, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import Response

from src.api.routes.report_assurance_marking import _inject_advisor_assurance_marking
from src.api.routes.report_context_builder import _build_report_context
from src.api.routes.report_defensibility_compat import (  # noqa: F401 - compatibility export
    _apply_classification_to_asking_price,
)
from src.api.routes.report_defensibility_compat import (  # noqa: F401 - compatibility export
    _classify_valuation_data,
)
from src.api.routes.report_payload_context import (
    JsonMap,
    _build_defensibility_input,
    _coerce_boolish,
    _extract_renderable_persisted_report_context,
    _json_safe,
    _looks_degenerate_preview_payload,
)
from src.api.routes.report_pdf_html_builder import (  # noqa: F401 - compatibility export
    _DEFENSIBILITY_OVERLAY_KEYS,
)
from src.api.routes.report_pdf_html_builder import (  # noqa: F401 - compatibility export
    _overlay_pdf_defensibility_from_canonical,
)
from src.api.routes.report_pdf_html_builder import _build_pdf_html as _build_pdf_html_impl
from src.api.routes.report_watermark import _inject_watermark
from src.middleware.auth import require_service_auth
from src.services.defensibility.banner import (
    defensibility_banner_div_count,
    strip_defensibility_banner_inject_anchor,
)
from src.services.reports.report_fresh_context_keys import (  # noqa: F401 - compatibility export
    FRESH_CONTEXT_ALWAYS_WINS as _FRESH_ALWAYS_WINS,
)
from src.services.reports.report_presentation_surface import screen_context_for_presentation_surface
from src.utils.logging import get_logger

logger = get_logger(__name__)

_IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_service_auth)],
)


def _resolve_report_locale(override: object, body: JsonMap, embedded: JsonMap) -> str:
    # Preserve the legacy default when no locale was supplied. Explicit locales
    # outside the supported EN/FR/NL set use the international English fallback.
    raw = next(
        (
            value.strip()
            for value in (override, body.get("locale"), embedded.get("locale"))
            if isinstance(value, str) and value.strip()
        ),
        "nl",
    )
    language = raw.lower().replace("_", "-").split("-", 1)[0]
    return language if language in {"en", "fr", "nl"} else "en"


def _require_canonical_share_ready_manifest(
    *,
    body: JsonMap,
    valuation_data: JsonMap,
    enforce_share_ready: bool,
    effective_company_name: str | None = None,
    effective_report_id: str | None = None,
    effective_locale: str | None = None,
    effective_selected_method: str | None = None,
    effective_watermark: bool | None = None,
) -> None:
    """Keep generic v1 rendering preview/recovery-only."""
    del body, valuation_data, effective_company_name, effective_report_id
    del effective_locale, effective_selected_method, effective_watermark
    if not enforce_share_ready:
        return

    # This endpoint is the generic v1 renderer. Even a syntactically valid,
    # self-hashed v2 manifest is only attacker-controlled input here; a digest
    # proves consistency, not release authority. Final/share-ready artifacts
    # may only be minted by the canonical v2 generate-report flow, where the
    # gate is recomputed from the in-memory ValuationRunV2 after rendering.
    _raise_share_ready_contract_error(
        code="legacy_report_cannot_claim_share_ready",
        message=(
            "Generic /api/v1 report rendering is preview/recovery only and cannot "
            "claim final or share-ready status. Use canonical v2 report generation."
        ),
    )


def _raise_share_ready_contract_error(*, code: str, message: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": code, "message": message},
    )


def _build_pdf_html(
    valuation_data: JsonMap,
    company_name: str,
    report_id: str,
    locale: str = "nl",
    selected_method: str | None = None,
    *,
    canonical_report_context: Optional[JsonMap] = None,
    render_outcome: Optional[dict[str, str]] = None,
) -> str:
    return _build_pdf_html_impl(
        valuation_data,
        company_name,
        report_id,
        locale=locale,
        selected_method=selected_method,
        canonical_report_context=canonical_report_context,
        report_context_builder=_build_report_context,
        render_outcome=render_outcome,
    )


@router.post(
    "/render",
    status_code=status.HTTP_200_OK,
    summary="Render HTML and canonical report context",
    description="Render screen HTML, PDF HTML, and canonical report context from valuation data.",
)
async def render_report_assets(
    body: JsonMap = Body(...),
    lang: Optional[str] = Query(
        default=None,
        description="Optional report locale override, e.g. ?lang=fr.",
    ),
) -> JsonMap:
    from src.services.infrastructure.template_service import get_template_service

    valuation_data = body.get("valuation_data")
    embedded = valuation_data if isinstance(valuation_data, dict) else {}
    embedded_render = embedded.get("render_contract")
    embedded_render = embedded_render if isinstance(embedded_render, dict) else {}
    company_name = (
        body.get("company_name")
        or body.get("business_name")
        or embedded_render.get("company_name")
        or embedded.get("company_name")
        or "Unknown"
    )
    report_id = (
        body.get("report_id")
        or body.get("valuation_id")
        or embedded_render.get("report_id")
        or embedded.get("report_id")
        or "unknown"
    )
    locale = _resolve_report_locale(lang, body, embedded)

    accountant_logo_url = body.get("accountant_logo_url")
    accountant_firm_name = body.get("accountant_firm_name")
    if isinstance(accountant_logo_url, str) and not accountant_logo_url.strip():
        accountant_logo_url = None
    if isinstance(accountant_firm_name, str) and not accountant_firm_name.strip():
        accountant_firm_name = None
    if (
        valuation_data
        and isinstance(valuation_data, dict)
        and (accountant_logo_url or accountant_firm_name)
    ):
        raw_metadata = valuation_data.get("metadata")
        metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
        if accountant_logo_url is not None:
            metadata["accountant_logo_url"] = accountant_logo_url
        if accountant_firm_name is not None:
            metadata["accountant_firm_name"] = accountant_firm_name
        valuation_data = {**valuation_data, "metadata": metadata}

    if not valuation_data or not isinstance(valuation_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="valuation_data is required and must be a dict",
        )

    selected_method = body.get("selected_method", embedded_render.get("selected_method"))
    enforce_share_ready = _coerce_boolish(body.get("enforce_share_ready"), default=False)
    _require_canonical_share_ready_manifest(
        body=body,
        valuation_data=valuation_data,
        enforce_share_ready=enforce_share_ready,
        effective_company_name=str(company_name),
        effective_report_id=str(report_id),
        effective_locale=str(locale),
        effective_selected_method=(str(selected_method) if selected_method is not None else None),
    )
    allow_non_share_ready_preview = _coerce_boolish(
        body.get("allow_non_share_ready_preview"),
        default=False,
    )
    allow_degenerate_preview = _coerce_boolish(
        body.get("allow_degenerate_preview"),
        default=False,
    )
    presentation_surface = body.get("presentation_surface", "final_artifact")

    # ROBUSTNESS CONTRACT
    # ------------------
    # /render must ALWAYS return a usable {html_report, pdf_html_report,
    # report_context} or the entire downstream chain breaks: Titan's advisor
    # normalization (`venus-normalization.controller.refreshRenderedAssets`),
    # Omni-Calc method switch (`valuations.controller` line ~1640), the PDF
    # export's on-demand re-render (`pdf-generation.service`), and the
    # async PDF processor (`pdf-generation.processor`) all consume this
    # endpoint and rely on it succeeding so they never have to surface a
    # "Service temporarily unavailable" to a business owner or advisor.
    #
    # Behaviour:
    #   1. Try the templated render via TemplateService. Happy path.
    #   2. If templating throws OR returns short/empty output, fall through
    #      to the shared `safety_net_report.build_safety_net_reports`. That
    #      function is the single source of truth for degraded rendering and
    #      ALWAYS produces non-empty HTML satisfying the length contract
    #      (screen >= 100, pdf >= 500).
    #   3. The safety-net response is tagged with
    #      `report_context.safety_net.active = true` so observability can
    #      detect silent degradation.
    from src.services.infrastructure.safety_net_report import (
        build_safety_net_reports as _build_safety_net,
    )

    safety_net_reason: Optional[str] = None
    template_context: Optional[JsonMap] = None
    html_report: Optional[str] = None
    pdf_html_report: Optional[str] = None

    if _looks_degenerate_preview_payload(valuation_data) and not allow_degenerate_preview:
        safety_net_reason = "render_degenerate_payload_preview_suppressed"
        logger.info(
            "render_report_assets: sparse payload, suppressing screen preview",
            extra={
                "report_id": (report_id[:8] + "...") if report_id else "unknown",
                "company_name": company_name,
                "locale": locale,
            },
        )
    else:
        try:
            template_context = _build_report_context(
                valuation_data,
                company_name,
                report_id,
                locale=locale,
                selected_method=selected_method,
            )
            template_service = get_template_service()
            screen_context = screen_context_for_presentation_surface(
                template_context,
                presentation_surface=presentation_surface,
                locale=locale,
            )
            html_report = template_service.render_main_report(screen_context, locale=locale)
            pdf_html_report = template_service.render_main_report_pdf(
                template_context, locale=locale
            )
        except Exception as exc:
            logger.warning(
                "render_report_assets: template rendering failed - falling back to safety-net",
                extra={
                    "report_id": (report_id[:8] + "...") if report_id else "unknown",
                    "company_name": company_name,
                    "locale": locale,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:300],
                },
                exc_info=False,
            )
            safety_net_reason = f"template_render_exception:{type(exc).__name__}"

    if safety_net_reason is None and (not html_report or len(html_report.strip()) < 100):
        safety_net_reason = "screen_html_too_short"
        logger.warning(
            "render_report_assets: screen HTML output incomplete - falling back to safety-net",
            extra={
                "report_id": (report_id[:8] + "...") if report_id else "unknown",
                "html_length": len(html_report or ""),
            },
        )
    if safety_net_reason is None and (not pdf_html_report or len(pdf_html_report.strip()) < 500):
        safety_net_reason = "pdf_html_too_short"
        logger.warning(
            "render_report_assets: PDF HTML output incomplete - falling back to safety-net",
            extra={
                "report_id": (report_id[:8] + "...") if report_id else "unknown",
                "pdf_html_length": len(pdf_html_report or ""),
            },
        )

    # Preview contract: when defensibility recommends BLOCK_SOFT, suppress
    # screen HTML by forcing the safety-net path (PDF internals only) unless
    # explicitly overridden.
    if (
        safety_net_reason is None
        and isinstance(template_context, dict)
        and enforce_share_ready
        and not allow_non_share_ready_preview
    ):
        submit_recommendation = (
            str(template_context.get("defensibility_submit_recommendation") or "").strip().lower()
        )
        if submit_recommendation == "block_soft":
            safety_net_reason = "render_not_share_ready_block_soft"
            logger.warning(
                "render_report_assets: defensibility gate suppressed screen HTML preview",
                extra={
                    "report_id": (report_id[:8] + "...") if report_id else "unknown",
                    "company_name": company_name,
                    "locale": locale,
                    "submit_recommendation": submit_recommendation,
                },
            )

    if safety_net_reason is not None:
        safety = _build_safety_net(
            valuation_data,
            company_name=company_name,
            locale=locale,
            reason=safety_net_reason,
            correlation_id=report_id,
        )
        # Preserve any partial context the templated path produced so
        # downstream readers (Mercury/Venus extractors) keep their existing
        # numeric fields. Mark safety_net active in the merged context.
        merged_context: JsonMap = {}
        if isinstance(template_context, dict):
            _INTERNAL_CONTEXT_KEYS = {"t", "config"}
            merged_context.update(
                {k: v for k, v in template_context.items() if k not in _INTERNAL_CONTEXT_KEYS}
            )
        merged_context["safety_net"] = safety["report_context"]["safety_net"]
        # Why: the user-facing preview must never display the safety-net
        # summary-card as if it were a full report. Internal recovery callers
        # may opt into the degraded assets so they can log, inspect, or use the
        # PDF-specific fallback, but Titan treats report_context.safety_net as
        # non-renderable for the main report preview and persisted html_report.
        # Return degraded screen HTML only on that explicit opt-in.
        return {
            "html_report": safety["html_report"] if allow_degenerate_preview else None,
            "pdf_html_report": safety["pdf_html_report"],
            "report_context": _json_safe(merged_context),
        }

    _INTERNAL_CONTEXT_KEYS = {"t", "config"}
    ctx_for_persist = {
        k: v for k, v in template_context.items() if k not in _INTERNAL_CONTEXT_KEYS
    }  # type: ignore[union-attr]
    return {
        "html_report": html_report,
        "pdf_html_report": pdf_html_report,
        "report_context": _json_safe(ctx_for_persist),
    }


@router.post(
    "/pdf",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Generate PDF from valuation data",
    description="Render the 5-page valuation report as a PDF using WeasyPrint.",
)
async def generate_pdf_from_html(
    body: JsonMap = Body(...),
    lang: Optional[str] = Query(
        default=None,
        description="Optional report locale override, e.g. ?lang=fr.",
    ),
) -> Response:
    """
    Generate PDF from valuation_data.

    Titan sends: { valuation_data, company_name, report_id
    [, accountant_logo_url, accountant_firm_name ] }
    Accountant branding can come from valuation_data.metadata or as top-level body overrides.
    """
    valuation_data = body.get("valuation_data")
    embedded = valuation_data if isinstance(valuation_data, dict) else {}
    embedded_render = embedded.get("render_contract")
    embedded_render = embedded_render if isinstance(embedded_render, dict) else {}
    company_name = (
        body.get("company_name")
        or body.get("business_name")
        or embedded_render.get("company_name")
        or embedded.get("company_name")
        or "Unknown"
    )
    report_id = (
        body.get("report_id")
        or body.get("valuation_id")
        or embedded_render.get("report_id")
        or embedded.get("report_id")
        or "unknown"
    )
    locale = _resolve_report_locale(lang, body, embedded)

    # Merge top-level accountant branding into valuation_data.metadata so aggregator finds it
    accountant_logo_url = body.get("accountant_logo_url")
    accountant_firm_name = body.get("accountant_firm_name")
    if isinstance(accountant_logo_url, str) and not accountant_logo_url.strip():
        accountant_logo_url = None
    if isinstance(accountant_firm_name, str) and not accountant_firm_name.strip():
        accountant_firm_name = None
    if (
        valuation_data
        and isinstance(valuation_data, dict)
        and (accountant_logo_url or accountant_firm_name)
    ):
        raw_metadata = valuation_data.get("metadata")
        metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
        if accountant_logo_url is not None:
            metadata["accountant_logo_url"] = accountant_logo_url
        if accountant_firm_name is not None:
            metadata["accountant_firm_name"] = accountant_firm_name
        valuation_data = {**valuation_data, "metadata": metadata}

    # DEBUG: AUDIT POST /api/v1/reports/pdf line is the canonical request signal.
    logger.debug(
        "PDF request received",
        extra={
            "report_id": report_id,
            "company_name": company_name,
            "locale": locale,
            "has_valuation_data": valuation_data is not None,
            "vd_keys": list(valuation_data.keys())[:15] if isinstance(valuation_data, dict) else [],
            "has_accountant_logo": bool(
                (valuation_data or {}).get("metadata", {}).get("accountant_logo_url")
                or body.get("accountant_logo_url")
            ),
        },
    )

    if not valuation_data or not isinstance(valuation_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="valuation_data is required and must be a dict",
        )

    selected_method = body.get("selected_method", embedded_render.get("selected_method"))
    subscription_watermark = _coerce_boolish(body.get("watermark"), default=False)
    report_assurance_level = (
        "advisor_approved"
        if body.get("report_assurance_level") == "advisor_approved"
        else "indicative"
    )
    report_superseded = _coerce_boolish(body.get("report_superseded"), default=False)

    # Defensibility gate: classify the input and may require a scope banner when
    # the report falls below FULL_REPORT (insufficient years, severe losses,
    # low data quality) OR when engine-side defensibility signals fire
    # (balance data missing, EBITDA normalisation = 0 for owner-led, formula
    # mismatch, derived net debt). Three Towers Capital regression: N=2y,
    # 10% margin vs 28% industry, no balance data -> LIMITED_SCOPE +
    # banner with both the years cap and the engine signals.
    from src.services.defensibility import (
        SubmitRecommendation,
        build_defensibility_banner,
        build_defensibility_report,
    )
    from src.services.defensibility.banner import watermark_footer as _wm_footer
    from src.services.defensibility.banner import watermark_text as _wm_text

    persisted_for_gate = _extract_renderable_persisted_report_context(valuation_data)
    canonical_report_context: Optional[JsonMap] = None
    defensibility_context: JsonMap = dict(persisted_for_gate)
    try:
        # Keep share-ready/watermark decisions aligned with the same canonical
        # composition pipeline used for screen/PDF templates.
        canonical_report_context = _build_report_context(
            valuation_data,
            company_name,
            report_id,
            locale=locale,
            selected_method=selected_method,
            include_persisted_context=True,
        )
        defensibility_context = canonical_report_context
    except Exception as exc:
        logger.warning(
            (
                "PDF: failed to build canonical defensibility context; "
                "falling back to persisted context"
            ),
            extra={
                "report_id": report_id[:8] if report_id else "unknown",
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:300],
            },
            exc_info=False,
        )
    # Mirror ``_build_report_context`` - persisted keys must overlay the same way
    # as ``{**persisted_for_gate, **context}`` so share-gate / PLG flags match
    # ``defensibility_scope_banner_html`` (disclaimers section in templates).
    defensibility_input = _build_defensibility_input(
        valuation_data,
        {**persisted_for_gate, **defensibility_context},
    )
    # When aggregation succeeded, defensibility was already computed inside
    # ``_build_report_context``. Re-running ``build_defensibility_report`` here
    # could only diverge from the scope banner / submit gate baked into that
    # context - reuse the stashed fields instead.
    defensibility_report = None
    verdict = None
    scope_banner_html_stored = ""

    if canonical_report_context is not None:
        submit_rec = str(canonical_report_context.get("defensibility_submit_recommendation") or "")
        reasons_en = list(canonical_report_context.get("defensibility_submit_reasons_en") or [])
        reasons_nl = list(canonical_report_context.get("defensibility_submit_reasons_nl") or [])
        reasons_fr = list(canonical_report_context.get("defensibility_submit_reasons_fr") or [])
        warning_codes_gate = list(canonical_report_context.get("defensibility_warning_codes") or [])
        scope_banner_html_stored = str(
            canonical_report_context.get("defensibility_scope_banner_html") or ""
        )
        auto_wm = bool(canonical_report_context.get("defensibility_auto_watermark")) or bool(
            scope_banner_html_stored.strip()
        )
    else:
        defensibility_report = build_defensibility_report(defensibility_input, locale=locale)
        verdict = defensibility_report.verdict
        submit_rec = defensibility_report.submit_gate.recommendation.value
        reasons_en = list(defensibility_report.submit_gate.reasons_en)
        reasons_nl = list(defensibility_report.submit_gate.reasons_nl)
        reasons_fr = list(defensibility_report.submit_gate.reasons_fr)
        warning_codes_gate = [w.code for w in defensibility_report.warnings]
        auto_wm = bool(verdict.auto_watermark)
        if verdict.auto_watermark:
            scope_banner_html_stored = build_defensibility_banner(
                classification_value=verdict.classification_value,
                confidence_cap=verdict.confidence_cap,
                cap_reason=verdict.cap_reason,
                margin_warning=verdict.margin_warning,
                engine_signals=verdict.engine_signals,
                locale=locale,
                is_full_report=verdict.is_full_report,
            )

    enforce_share_ready = _coerce_boolish(body.get("enforce_share_ready"), default=False)
    _require_canonical_share_ready_manifest(
        body=body,
        valuation_data=valuation_data,
        enforce_share_ready=enforce_share_ready,
        effective_company_name=str(company_name),
        effective_report_id=str(report_id),
        effective_locale=str(locale),
        effective_selected_method=(str(selected_method) if selected_method is not None else None),
        effective_watermark=subscription_watermark,
    )
    allow_non_share_ready_pdf = _coerce_boolish(
        body.get("allow_non_share_ready_pdf"),
        default=False,
    )
    if (
        enforce_share_ready
        and not allow_non_share_ready_pdf
        and submit_rec == SubmitRecommendation.BLOCK_SOFT.value
    ):
        reasons = {"en": reasons_en, "nl": reasons_nl, "fr": reasons_fr or reasons_en}.get(
            locale, reasons_en
        )
        logger.warning(
            "PDF blocked by defensibility share-ready gate",
            extra={
                "report_id": report_id[:8] if report_id else "unknown",
                "locale": locale,
                "submit_recommendation": submit_rec,
                "warning_codes": warning_codes_gate,
                "reason_count": len(reasons),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "pdf_blocked_not_share_ready",
                "message": {
                    "en": "Report is not share-ready for external distribution.",
                    "nl": "Rapport is niet deel-klaar voor externe distributie.",
                    "fr": "Ce rapport n’est pas prêt à être diffusé à des tiers.",
                }.get(locale, "Report is not share-ready for external distribution."),
                "recommendation": submit_rec,
                "reasons": reasons,
                "warning_codes": warning_codes_gate,
            },
        )

    watermark_text = "Powered by Upswitch"
    footer_text = "This report was generated with Upswitch &mdash; upswitch.app"
    if auto_wm and subscription_watermark:
        watermark_text = _wm_text(locale)
        footer_text = _wm_footer(locale)
    if auto_wm:
        if verdict is not None:
            # DEBUG: defensibility decision provenance; the verdict surfaces
            # via the rendered watermark + scope banner in the PDF itself.
            logger.debug(
                (
                    "PDF: Defensibility scope disclosure (banner); PLG overlay "
                    "follows subscription flag"
                ),
                extra={
                    "report_id": report_id[:8] if report_id else "unknown",
                    "methodology": verdict.methodology.value,
                    "classification": verdict.classification_value,
                    "confidence_cap": float(verdict.confidence_cap),
                    "engine_signals": len(verdict.engine_signals),
                    "has_margin_warning": verdict.margin_warning is not None,
                    "locale": locale,
                    "subscription_watermark": subscription_watermark,
                },
            )
        else:
            logger.debug(
                (
                    "PDF: Defensibility scope disclosure (banner); PLG overlay "
                    "follows subscription flag"
                ),
                extra={
                    "report_id": report_id[:8] if report_id else "unknown",
                    "defensibility_source": "canonical_report_context",
                    "warning_codes": warning_codes_gate,
                    "locale": locale,
                    "subscription_watermark": subscription_watermark,
                },
            )

    include_plg_overlay = subscription_watermark

    # Which path produced the HTML. The resulting PDF is encrypted, so this is the only
    # way a caller can tell the full report from the one-page safety-net summary.
    render_outcome: dict[str, str] = {}
    try:
        html_report = _build_pdf_html(
            valuation_data,
            company_name,
            report_id,
            locale=locale,
            selected_method=selected_method,
            canonical_report_context=canonical_report_context,
            render_outcome=render_outcome,
        )
        html_report = _inject_advisor_assurance_marking(
            html_report,
            locale=locale,
            assurance_level=report_assurance_level,
            superseded=report_superseded,
        )

        # Templated PDFs embed the scope banner on the disclaimers page via
        # ``defensibility_scope_banner_html`` (same pipeline as /render). Safety-net
        # / minimal HTML omits that - inject at the anchor so behaviour stays aligned.
        banner_fallback: Optional[str] = None
        # Div-count probe: substring on the raw ``<div class="..."`` prefix misses
        # single-quoted attributes and could inject a duplicate next to Jinja output.
        if auto_wm and defensibility_banner_div_count(html_report) == 0:
            banner_fallback = scope_banner_html_stored.strip() or None
            if banner_fallback is None:
                from src.services.defensibility.classifier import classify_valuation_data

                v_fb = classify_valuation_data(defensibility_input)
                banner_fallback = build_defensibility_banner(
                    classification_value=v_fb.classification_value,
                    confidence_cap=v_fb.confidence_cap,
                    cap_reason=v_fb.cap_reason,
                    margin_warning=v_fb.margin_warning,
                    engine_signals=v_fb.engine_signals,
                    locale=locale,
                    is_full_report=v_fb.is_full_report,
                )

        needs_pdf_markings = include_plg_overlay or banner_fallback is not None
        if needs_pdf_markings:
            html_report = _inject_watermark(
                html_report,
                watermark_text=watermark_text,
                footer_text=footer_text,
                banner_html=banner_fallback,
                include_plg_overlay=include_plg_overlay,
            )
            logger.info(
                "PDF: markings injected",
                extra={
                    "report_id": report_id[:8] if report_id else "unknown",
                    "defensibility_banner_fallback": banner_fallback is not None,
                    "plg_overlay": include_plg_overlay,
                },
            )
    except Exception as e:
        logger.error(
            "PDF: HTML build failed",
            extra={
                "report_id": report_id,
                "error_type": type(e).__name__,
                "error_message": str(e)[:300],
            },
            exc_info=True,
        )
        detail = "PDF generation failed" if _IS_PRODUCTION else f"PDF generation failed: {e}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)

    try:
        from src.services.infrastructure.html_report_service import get_html_report_service

        service = get_html_report_service()
        html_report = strip_defensibility_banner_inject_anchor(html_report)
        pdf_bytes = await service.generate_accountant_view_pdf(
            html_content=html_report,
            template_data={"company_name": company_name, "report_id": report_id},
            correlation_id=report_id,
        )

        if not pdf_bytes:
            logger.error(
                "PDF: generate_accountant_view_pdf returned None",
                extra={"report_id": report_id, "company_name": company_name},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="WeasyPrint returned empty PDF",
            )

        # DEBUG: pdf_strategy already emits "PDF generated successfully" with
        # size; AUDIT POST /api/v1/reports/pdf is the canonical request exit.
        logger.debug(
            "PDF: Generated successfully",
            extra={
                "report_id": report_id,
                "company_name": company_name,
                "pdf_size_bytes": len(pdf_bytes),
                "pdf_size_kb": round(len(pdf_bytes) / 1024, 2),
            },
        )

        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in (company_name or ""))
        safe_name = safe_name.replace(" ", "_")[:80].strip("_") or "company"
        filename = (
            f"valuation_report_{safe_name}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
        )
        render_mode = render_outcome.get("mode", "template")
        if render_mode != "template":
            logger.warning(
                "PDF: safety-net summary returned instead of the full report",
                extra={
                    "report_id": report_id[:8] if report_id else "unknown",
                    "render_mode": render_mode,
                    "safety_net_reason": render_outcome.get("reason"),
                },
            )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/pdf",
                # template | safety_net — see _build_pdf_html "RENDER OUTCOME".
                "X-Report-Render-Mode": render_mode,
                **(
                    {"X-Report-Safety-Net-Reason": render_outcome["reason"][:120]}
                    if render_outcome.get("reason")
                    else {}
                ),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "PDF: WeasyPrint conversion failed",
            extra={
                "report_id": report_id,
                "company_name": company_name,
                "error_type": type(e).__name__,
                "error_message": str(e)[:500],
            },
            exc_info=True,
        )
        detail = "PDF generation failed" if _IS_PRODUCTION else f"PDF generation failed: {e}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)
