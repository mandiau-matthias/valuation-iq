"""Canonical report context composition for report routes."""

from __future__ import annotations

from src.api.routes.report_payload_context import (
    JsonMap,
    _build_defensibility_input,
    _extract_persisted_report_context,
    _extract_renderable_persisted_report_context,
    _strip_safety_net_context,
    _strip_safety_net_context_from_valuation_data,
)
from src.domain.valuation_contract import is_asset_method_key, normalize_method_key
from src.services.reports.adaptive_report_gates import refresh_adaptive_gates_on_context
from src.services.reports.omni_calc_overrides import apply_omni_calc_overrides
from src.services.reports.report_fresh_context_keys import (
    FRESH_CONTEXT_ALWAYS_WINS as _FRESH_ALWAYS_WINS,
    REGENERATED_PRESENTATION_KEYS,
)
from src.services.reports.report_margin_note_refresh import refresh_report_margin_notes
from src.services.reports.report_pagination import (
    assign_sme_html_footer_page_numbers,
    assign_startup_html_footer_page_numbers,
    build_sme_report_page_flags,
    compute_total_pages,
)
from src.services.reports.report_readiness_context import build_report_readiness_context
from src.services.reports.saas_context import build_saas_report_context
from src.services.reports.transaction_readiness_context import build_transaction_readiness_context
from src.services.reports.weighted_synthesis_context import (
    promote_weighted_synthesis_headline_context,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _prepare_aggregation_input(
    valuation_data: JsonMap,
    company_name: str,
    report_id: str,
    selected_method: str | None,
    include_persisted_context: bool,
) -> tuple[JsonMap, JsonMap | None, str | None]:
    persisted_context = (
        _extract_persisted_report_context(valuation_data) if include_persisted_context else None
    )
    sanitized_persisted_context = _strip_safety_net_context(persisted_context)

    aggregation_input = _strip_safety_net_context_from_valuation_data(valuation_data)
    if sanitized_persisted_context:
        aggregation_input = {**aggregation_input, **sanitized_persisted_context}
        # A saved presentation date may already be translated. Rebuild labels
        # from the immutable calculation date when rendering another locale.
        if valuation_data.get("valuation_date") is not None:
            aggregation_input["valuation_date"] = valuation_data["valuation_date"]
    if company_name:
        aggregation_input["company_name"] = company_name
    if report_id:
        aggregation_input["report_id"] = report_id

    normalized_selected_method = normalize_method_key(selected_method)
    if normalized_selected_method:
        aggregation_input["selected_method"] = normalized_selected_method

    return aggregation_input, sanitized_persisted_context, normalized_selected_method


def _aggregate_main_report_context(
    aggregation_input: JsonMap,
    *,
    locale: str,
    report_id: str,
    selected_method: str | None,
    company_name: str,
) -> JsonMap:
    from src.services.infrastructure.aggregator_cache import cached_aggregate_from_valuation_data
    from src.services.infrastructure.main_report_data_aggregator import get_main_report_aggregator

    aggregator = get_main_report_aggregator()
    try:
        # Cached around the aggregator call so Mercury's /render -> /pdf
        # flow (typically 2-3 hits within ~30s for the same content) only
        # rebuilds the ~250-key context once. The persisted-context merge
        # below (and the _FRESH_ALWAYS_WINS overlay) still runs on every
        # call, so cache hits do not change render semantics.
        return cached_aggregate_from_valuation_data(
            aggregation_input,
            locale,
            report_id=report_id,
            selected_method=selected_method,
            compute=lambda: aggregator.aggregate_from_valuation_data(
                aggregation_input, locale=locale
            ),
        )
    except (KeyError, AttributeError, ValueError, TypeError, ZeroDivisionError) as agg_err:
        _raise_aggregation_error(
            agg_err,
            aggregation_input=aggregation_input,
            report_id=report_id,
            selected_method=selected_method,
            company_name=company_name,
            locale=locale,
        )


def _raise_aggregation_error(
    agg_err: Exception,
    *,
    aggregation_input: JsonMap,
    report_id: str,
    selected_method: str | None,
    company_name: str,
    locale: str,
) -> None:
    rid = report_id[:8] if report_id else "unknown"
    # Why include the exception details inline in the log message:
    # production log streams sometimes drop the structured `extra` fields
    # (the May 14 prod logs we were given showed only the headline
    # message, not error_type/error_message/missing_field), which makes
    # it impossible to diagnose which aggregator phase actually failed.
    # The redundant inline format is a small price for actionable
    # observability on every failure.
    err_type = type(agg_err).__name__
    err_msg = str(agg_err) or "<no message>"
    first_arg = (
        agg_err.args[0]
        if isinstance(getattr(agg_err, "args", None), tuple) and agg_err.args
        else None
    )
    logger.error(
        f"Reports: aggregate_from_valuation_data failed [{err_type}] {err_msg}",
        extra={
            "report_id": rid,
            "error_type": err_type,
            "error_message": err_msg,
            "missing_field": first_arg,
            "selected_method": selected_method,
            "company_name": company_name,
            "locale": locale,
            # Surface payload shape (not contents) so we can correlate
            # failures with specific persisted-data variants without
            # spilling PII into log streams.
            "vd_keys": sorted(list(aggregation_input.keys()))[:60],
        },
        exc_info=True,
    )
    raise ValueError(
        f"Aggregation failed: [{err_type}] {err_msg}. "
        "valuation_data may be missing required fields "
        "(company_name, valuation, sustainable_ebitda, etc.)."
    ) from agg_err


def _merge_persisted_context(
    context: JsonMap,
    sanitized_persisted_context: JsonMap | None,
    *,
    report_id: str,
) -> JsonMap:
    rid = report_id[:8] if report_id else "unknown"
    if not sanitized_persisted_context:
        logger.debug(
            "Reports: report context resolved (no persisted fallback)",
            extra={
                "report_id": rid,
                "company": context.get("company_name"),
                "valuation": context.get("valuation"),
                "context_keys": len(context),
            },
        )
        return context

    is_canonical = "_validation" in sanitized_persisted_context
    if is_canonical:
        merged = {**context, **sanitized_persisted_context}
        for key in _FRESH_ALWAYS_WINS:
            if key in context:
                merged[key] = context[key]
            elif key in REGENERATED_PRESENTATION_KEYS:
                merged.pop(key, None)
        context = merged
    else:
        context = {**sanitized_persisted_context, **context}

    # DEBUG: the merge with persisted_context runs unconditionally, even
    # on a cache HIT - so the prior "re-aggregated" wording was
    # misleading (it suggested the heavy aggregator re-ran when it
    # actually returned a cached snapshot). Cache HIT/MISS is logged
    # at DEBUG inside aggregator_cache.cached_aggregate_from_valuation_data.
    logger.debug(
        "Reports: report context resolved (persisted fallback merged)",
        extra={
            "report_id": rid,
            "company": context.get("company_name"),
            "context_keys": len(context),
            "is_canonical": is_canonical,
        },
    )
    return context


def _apply_report_identity(
    context: JsonMap,
    valuation_data: JsonMap,
    *,
    company_name: str,
    report_id: str,
) -> None:
    if company_name:
        context["company_name"] = company_name
    if not report_id:
        return

    context["report_id"] = report_id
    # Format raw UUIDs as VAL-YYYY-XXXX so the public-facing report does
    # not surface a developer-grade UUID. Three Towers Capital regression:
    # the cover page printed "00000000-0000-4000-8000-000000000001" instead
    # of "VAL-2026-61DC".
    try:
        from src.services.infrastructure.simplified_report_transformer import (
            format_valuation_reference,
        )

        valuation_date = valuation_data.get("valuation_date") or context.get("valuation_date")
        display = format_valuation_reference(report_id, valuation_date)
        if display:
            context["report_id_display"] = display
    except Exception:  # pragma: no cover - never fail render on formatting
        context["report_id_display"] = report_id


def _apply_context_enrichments(
    context: JsonMap,
    valuation_data: JsonMap,
    *,
    selected_method: str | None,
    locale: str,
) -> None:
    apply_omni_calc_overrides(context, valuation_data, selected_method, locale=locale)

    # If SDE is the active method but the override path did not apply the
    # channel (e.g. user selected an unavailable method like ARR and the
    # engine fell back to an SDE-recommended adaptive result), apply the
    # SDE channel idempotently here. Without this pass the EBITDA cascade
    # would leak into the SDE rendering.
    from src.services.reports.sde_channel import ensure_sde_channel_applied

    ensure_sde_channel_applied(context, valuation_data, locale=locale)
    context.update(
        build_saas_report_context(valuation_data, context, selected_method, locale=locale)
    )

    # ``ensure_sde_channel_applied`` may stamp ``primary_method_key`` / SDE metric
    # type after omni already refreshed Pass-8/9 - re-align once the stack is final.
    refresh_adaptive_gates_on_context(context)
    promote_weighted_synthesis_headline_context(context)

    from src.services.reports.advisor_multiple_transparency_context import (
        enrich_advisor_multiple_transparency_context,
    )

    from src.services.reports.sde_blend_bridge_context import apply_sde_blend_bridge_context

    apply_sde_blend_bridge_context(context, locale=locale)
    enrich_advisor_multiple_transparency_context(context)

    metadata = valuation_data.get("metadata")
    context.update(
        build_transaction_readiness_context(
            context,
            locale=locale,
            metadata=metadata if isinstance(metadata, dict) else None,
        )
    )

    context["is_asset_methodology"] = is_asset_method_key(
        context.get("method_override_selected_method") or context.get("primary_method_key")
    )
    context["is_fiscal_method_only"] = str(context.get("selected_method") or "").strip() == (
        "fiscal_4x"
    ) and bool(context.get("fiscal_value_complete"))


def _apply_report_pagination(context: JsonMap) -> None:
    context["total_pages"] = compute_total_pages(build_sme_report_page_flags(context))
    assign_sme_html_footer_page_numbers(context)
    # B11 - startup-track section badges + footer page numbers. No-op when
    # ``is_startup_valuation_report`` is false, so the SME path is untouched.
    # Templates read ``startup_*_section_number`` from context instead of
    # hardcoding "01..05" inline.
    assign_startup_html_footer_page_numbers(context)


def _apply_defensibility_context(
    context: JsonMap,
    valuation_data: JsonMap,
    *,
    locale: str,
) -> None:
    # Defensibility output gate - runs LAST so it sees the final, fully
    # composed context. Validates that the displayed metric x multiple equals
    # the displayed enterprise value within tolerance, and that the EV -> equity
    # bridge is internally consistent. Soft mode by default so we never block a
    # customer-facing render; the ``defensibility_block_reason`` field is
    # surfaced into the template so the report can render an explicit caveat.
    from src.services.reports.formula_consistency_gate import apply_gate_to_context

    apply_gate_to_context(context, soft=True)

    # Defensibility-aware asking-price buffer override.
    # Methodology-aware: also suppresses the buffer for asset-based and
    # startup methodologies where a "+X% negotiation buffer" doesn't fit
    # the methodology's defensibility framework. See
    # ``src/services/defensibility/asking_price_gate.py``.
    from src.services.defensibility import (
        apply_asking_price_gate,
        build_defensibility_banner,
        build_defensibility_report,
    )

    persisted_for_gate = _extract_renderable_persisted_report_context(valuation_data)
    defensibility_input = _build_defensibility_input(
        valuation_data, {**persisted_for_gate, **context}
    )
    defensibility_report = build_defensibility_report(defensibility_input, locale=locale)
    context["defensibility_submit_recommendation"] = (
        defensibility_report.submit_gate.recommendation.value
    )
    context["defensibility_submit_reasons_en"] = list(defensibility_report.submit_gate.reasons_en)
    context["defensibility_submit_reasons_nl"] = list(defensibility_report.submit_gate.reasons_nl)
    context["defensibility_submit_reasons_fr"] = list(defensibility_report.submit_gate.reasons_fr)
    context["defensibility_warning_codes"] = [w.code for w in defensibility_report.warnings]
    # Plumbing-failure marker. When true the academic/ICP numbers are fallbacks
    # from a swallowed exception, not measurements — templates must render
    # "unavailable" rather than a 0. ``reports.py`` reuses these stashed keys
    # instead of re-running the builder, so it has to be stashed here to reach
    # the PDF path at all.
    context["defensibility_scoring_degraded"] = defensibility_report.scoring_degraded
    context["defensibility_scoring_errors"] = list(defensibility_report.scoring_errors)
    if defensibility_report.scoring_degraded:
        logger.error(
            "Reports: defensibility scoring degraded — scores are fallbacks, not measurements",
            extra={"scoring_errors": defensibility_report.scoring_errors},
        )
    apply_asking_price_gate(
        context,
        defensibility_input,
        verdict=defensibility_report.verdict,
    )

    verdict = defensibility_report.verdict
    context["defensibility_auto_watermark"] = bool(verdict.auto_watermark)
    if verdict.auto_watermark:
        context["defensibility_scope_banner_html"] = build_defensibility_banner(
            classification_value=verdict.classification_value,
            confidence_cap=verdict.confidence_cap,
            cap_reason=verdict.cap_reason,
            margin_warning=verdict.margin_warning,
            engine_signals=verdict.engine_signals,
            locale=locale,
            is_full_report=verdict.is_full_report,
        )
    else:
        context["defensibility_scope_banner_html"] = ""


def _build_report_context(
    valuation_data: JsonMap,
    company_name: str,
    report_id: str,
    locale: str = "nl",
    selected_method: str | None = None,
    include_persisted_context: bool = True,
) -> JsonMap:
    aggregation_input, sanitized_persisted_context, normalized_selected_method = (
        _prepare_aggregation_input(
            valuation_data,
            company_name,
            report_id,
            selected_method,
            include_persisted_context,
        )
    )

    context = _aggregate_main_report_context(
        aggregation_input,
        locale=locale,
        report_id=report_id,
        selected_method=normalized_selected_method,
        company_name=company_name,
    )
    context = _merge_persisted_context(
        context,
        sanitized_persisted_context,
        report_id=report_id,
    )
    _apply_report_identity(
        context,
        valuation_data,
        company_name=company_name,
        report_id=report_id,
    )
    _apply_context_enrichments(
        context,
        valuation_data,
        selected_method=selected_method,
        locale=locale,
    )
    refresh_report_margin_notes(context, valuation_data, locale=locale)
    _apply_report_pagination(context)
    _apply_defensibility_context(context, valuation_data, locale=locale)
    context.update(build_report_readiness_context(context))
    # Generic /reports/render is preview/recovery-only and performs no live
    # Titan assurance-head lookup. Never preserve caller/persisted certified,
    # legal or outcome labels here. Canonical generate-report builds its own
    # context through stateless_report_context after the online authority gate.
    from src.api.schemas.valuation_contracts import ValuationRunV2
    from src.services.reports.report_assurance import report_assurance_projection

    raw_run = valuation_data.get("valuation_run")
    try:
        untrusted_run = (
            ValuationRunV2.model_validate(raw_run)
            if isinstance(raw_run, dict) and raw_run.get("schema_version") == "valuation_run.v2"
            else None
        )
    except (TypeError, ValueError):
        untrusted_run = None
    context.update(report_assurance_projection(untrusted_run, locale=locale))
    return context
