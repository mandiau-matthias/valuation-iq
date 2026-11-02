"""HTML/PDF rendering for the stateless report endpoint.

The route owns HTTP logging and response shaping.  This module owns the
template-context lifecycle, report rendering, PDF generation, and fallback
HTML path so those concerns can be tested without FastAPI.
"""

from __future__ import annotations

import asyncio
import base64
import re
from dataclasses import dataclass
from typing import List, Optional

from src.api.schemas.stateless_api import GenerateReportRequest
from src.api.schemas.valuation_contracts import ValuationRunV2
from src.services.reports.stateless_report_context import (
    UnsupportedCanonicalReportCurrency,
    build_stateless_report_context,
)
from src.services.reports.stateless_report_manifest import scoped_report_release_decision
from src.services.reports.valuation_assurance_status import CurrentValuationAssuranceAuthority
from src.utils.fiscal_year import get_current_filing_year
from src.utils.logging import get_logger

logger = get_logger(__name__)

_PDF_FALLBACK_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class StatelessReportOutputs:
    html_report: Optional[str]
    pdf_base64: Optional[str]
    generation_warnings: List[str]


async def generate_stateless_report_outputs(
    request: GenerateReportRequest,
    *,
    locale: str,
    verified_assurance_authority: CurrentValuationAssuranceAuthority | None = None,
) -> StatelessReportOutputs:
    if getattr(request, "report_scope", "standard") == "automated_indicative":
        from src.services.reports.automated_indicative_renderer import generate_automatic_outputs

        html, pdf = await generate_automatic_outputs(request, locale)
        return StatelessReportOutputs(html_report=html, pdf_base64=pdf, generation_warnings=[])

    html_report: Optional[str] = None
    pdf_base64: Optional[str] = None
    generation_warnings: List[str] = []

    template_context = None
    template_service = None

    if request.include_html or request.include_pdf:
        try:
            report_context = build_stateless_report_context(
                request,
                locale=locale,
                verified_assurance_authority=verified_assurance_authority,
            )
            template_context = report_context.template_context
            template_service = report_context.template_service
        except UnsupportedCanonicalReportCurrency:
            generation_warnings.append(
                "Full template does not support snapshot currency; using currency-safe report"
            )
        except Exception as exc:
            logger.error(
                "Template context build failed — PDF/HTML will use fallback",
                exc_info=True,
                extra={
                    "company_name": request.company_name,
                    "valuation_id": request.valuation_result.valuation_id[:8],
                },
            )
            generation_warnings.append(
                f"Template context build failed: {type(exc).__name__}: {exc}"
            )

    if request.include_html and template_context and template_service:
        try:
            html_report = template_service.render_main_report(
                template_context,
                locale=locale,
            )
        except Exception:
            logger.warning("HTML generation failed", exc_info=True)
            html_report = generate_fallback_html(
                request, verified_assurance_authority=verified_assurance_authority, locale=locale
            )
            generation_warnings.append("HTML render failed, using fallback template.")
    elif request.include_html:
        html_report = generate_fallback_html(
            request, verified_assurance_authority=verified_assurance_authority, locale=locale
        )
        generation_warnings.append("Template context unavailable — using fallback HTML")

    if html_report is not None and _is_diagnostic_preview(
        request,
        verified_assurance_authority=verified_assurance_authority,
    ):
        html_report = _inject_diagnostic_preview_watermark(html_report)

    if request.include_pdf and template_context and template_service:
        try:
            pdf_html = template_service.render_main_report_pdf(
                template_context,
                locale=locale,
            )
            if pdf_html and _is_diagnostic_preview(
                request,
                verified_assurance_authority=verified_assurance_authority,
            ):
                pdf_html = _inject_diagnostic_preview_watermark(pdf_html)
            if pdf_html and len(pdf_html) >= 500:
                from src.services.infrastructure.report_generation.metrics_collector import (
                    MetricsCollector,
                )
                from src.services.infrastructure.report_generation.strategies.pdf_strategy import (
                    PDFGenerationStrategy,
                )

                pdf_strategy = PDFGenerationStrategy(
                    logger_instance=logger,
                    metrics_collector=MetricsCollector(),
                )
                template_data = {
                    "company_name": request.company_name,
                    "company_id": request.valuation_result.valuation_id,
                    "valuation_id": request.valuation_result.valuation_id,
                    "valuation_date": (
                        request.valuation_date
                        if request.valuation_date
                        else (
                            f"{request.reporting_year}-12-31"
                            if request.reporting_year
                            else f"{get_current_filing_year()}-12-31"
                        )
                    ),
                    # Canonical artifacts are archival evidence. PDF/A forbids
                    # encryption, and random owner-password encryption also
                    # makes two renders of the same sealed run byte-unstable.
                    # Keep legacy delivery behavior separate; a ValuationRunV2
                    # is rendered as deterministic PDF/A from its immutable
                    # recording instant.
                    "archival_pdfa": isinstance(
                        request.valuation_result.valuation_run, ValuationRunV2
                    ),
                    "artifact_timestamp": (
                        request.valuation_result.valuation_run.recording_timestamp
                        if isinstance(request.valuation_result.valuation_run, ValuationRunV2)
                        else None
                    ),
                    "artifact_identifier": (
                        request.valuation_result.valuation_run.run_hash
                        if isinstance(request.valuation_result.valuation_run, ValuationRunV2)
                        else None
                    ),
                    "locale": locale,
                }
                pdf_bytes = await pdf_strategy.generate(
                    html_content=pdf_html,
                    template_data=template_data,
                    correlation_id=request.valuation_result.valuation_id[:8],
                )
                if pdf_bytes:
                    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
                else:
                    generation_warnings.append(
                        "Primary PDF strategy returned empty — attempting fallback"
                    )
                    pdf_base64 = await pdf_fallback_with_timeout(pdf_html)
            else:
                logger.warning("PDF template rendered empty or too short - skipping PDF")
                generation_warnings.append("PDF template too short — skipped")
        except ImportError:
            logger.warning("WeasyPrint not available - skipping PDF generation")
            generation_warnings.append("WeasyPrint not installed — PDF skipped")
        except Exception:
            logger.error("PDF generation failed", exc_info=True)
            generation_warnings.append("PDF generation failed.")
    elif request.include_pdf:
        generation_warnings.append(
            "Template context unavailable — attempting snapshot PDF fallback"
        )

    if request.include_pdf and pdf_base64 is None:
        fallback_html = generate_fallback_html(
            request, verified_assurance_authority=verified_assurance_authority, locale=locale
        )
        if _is_diagnostic_preview(
            request, verified_assurance_authority=verified_assurance_authority
        ):
            fallback_html = _inject_diagnostic_preview_watermark(fallback_html)
        pdf_base64 = await pdf_fallback_with_timeout(fallback_html)
        if pdf_base64 is None:
            generation_warnings.append("Snapshot fallback PDF renderer was unavailable")

    return StatelessReportOutputs(
        html_report=html_report,
        pdf_base64=pdf_base64,
        generation_warnings=generation_warnings,
    )


def _is_diagnostic_preview(
    request: GenerateReportRequest,
    *,
    verified_assurance_authority: CurrentValuationAssuranceAuthority | None = None,
) -> bool:
    run = request.valuation_result.valuation_run
    return isinstance(run, ValuationRunV2) and (
        scoped_report_release_decision(
            run,
            report_scope=request.report_scope,
            assurance_authority=verified_assurance_authority,
        ).generation_status
        == "diagnostic_preview"
    )


def _inject_diagnostic_preview_watermark(html: str) -> str:
    language_match = re.search(
        r"<html\b[^>]*\blang=[\"']([^\"']+)[\"']",
        html,
        flags=re.IGNORECASE,
    )
    language = language_match.group(1).lower() if language_match else "en"
    if language.startswith("nl"):
        message = "Dit dossier is een concept voor beoordeling. Vrijgave voor verspreiding is nog niet vastgelegd."
    elif language.startswith("fr"):
        message = "Ce dossier est un projet pour examen. L’autorisation de diffusion n’est pas encore enregistrée."
    else:
        message = "This dossier is a draft for review. Authorization for distribution has not yet been recorded."
    disclosure = (
        '<p data-report-publication="blocked" style="margin:16px 24px;'
        'font:11px/1.5 Arial,sans-serif;color:#53616a;">'
        f"{message}</p>"
    )
    rendered, replacements = re.subn(
        r"</body\s*>",
        lambda match: f"{disclosure}{match.group(0)}",
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    return rendered if replacements else f"{html}{disclosure}"


async def pdf_fallback_with_timeout(html: str) -> Optional[str]:
    """Generate PDF via basic PDFGenerator with a timeout guard."""
    try:
        from src.services.infrastructure.pdf_generator import PDFGenerator

        loop = asyncio.get_running_loop()
        pdf_generator = PDFGenerator()
        pdf_bytes = await asyncio.wait_for(
            loop.run_in_executor(None, pdf_generator.generate_pdf, html),
            timeout=_PDF_FALLBACK_TIMEOUT_SECONDS,
        )
        if pdf_bytes:
            return base64.b64encode(pdf_bytes).decode("utf-8")
    except asyncio.TimeoutError:
        logger.error(
            "Fallback PDF generation timed out after %.0fs",
            _PDF_FALLBACK_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.error("Fallback PDF generation failed", exc_info=True)
    return None


def generate_fallback_html(
    request: GenerateReportRequest,
    *,
    verified_assurance_authority: CurrentValuationAssuranceAuthority | None = None,
    locale: str | None = None,
) -> str:
    """Render a validated snapshot without financial recomputation."""
    from src.services.reports.snapshot_fallback_report import render_snapshot_fallback

    return render_snapshot_fallback(
        request, verified_assurance_authority=verified_assurance_authority, locale=locale
    )
