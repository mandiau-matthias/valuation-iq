"""Focused HTML report variant renderers used by ``HTMLReportService``."""

import asyncio
from collections.abc import Mapping
from typing import Optional, Protocol

from src.services.infrastructure.aggregator_cache import cached_aggregate
from src.services.infrastructure.exceptions import ReportGenerationError
from src.services.infrastructure.html_report_validation import validate_html_content
from src.services.infrastructure.main_report_data_aggregator import get_main_report_aggregator
from src.services.infrastructure.simplified_report_transformer import (
    get_simplified_report_transformer,
)
from src.services.infrastructure.template_service import TemplateService
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)


class ReportVariantLogger(Protocol):
    def info(
        self,
        msg: object,
        *args: object,
        extra: Optional[Mapping[str, object]] = ...,
        **kwargs: object,
    ) -> None: ...

    def error(
        self,
        msg: object,
        *args: object,
        exc_info: object = ...,
        extra: Optional[Mapping[str, object]] = ...,
        **kwargs: object,
    ) -> None: ...


def _aggregate_main_report_context(
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    locale: str,
) -> dict[str, object]:
    aggregator = get_main_report_aggregator()
    return cached_aggregate(
        response,
        request,
        locale,
        compute=lambda: aggregator.aggregate(response, request, locale=locale),
    )


async def render_main_report_html(
    *,
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    template_service: TemplateService,
    logger: ReportVariantLogger,
    context: Mapping[str, Optional[str]],
    report_type: str,
    locale: str,
    rendering_timeout_seconds: float,
    min_html_content_length: int,
) -> str:
    """Render the canonical screen HTML report variant."""
    template_context = _aggregate_main_report_context(response, request, locale)

    logger.info(
        f"[HTML-SERVICE] Data aggregation completed for {report_type}",
        extra={
            "company": context["company_name"],
            "correlation_id": context["correlation_id"],
            "valuation": template_context.get("valuation"),
            "ebitda": template_context.get("sustainable_ebitda"),
        },
    )

    try:
        html_content = await asyncio.wait_for(
            asyncio.to_thread(template_service.render_main_report, template_context, locale),
            timeout=rendering_timeout_seconds,
        )
    except asyncio.TimeoutError:
        raise ReportGenerationError(
            f"{report_type} rendering timed out after {rendering_timeout_seconds}s",
            company_name=context.get("company_name"),
            correlation_id=context.get("correlation_id"),
        )

    if not validate_html_content(
        html_content=html_content,
        context=context,
        report_type=report_type,
        min_length=min_html_content_length,
        logger=logger,
    ):
        raise ReportGenerationError(
            f"{report_type} rendered but HTML failed validation (empty or too short)",
            company_name=context.get("company_name"),
            correlation_id=context.get("correlation_id"),
        )

    page_count = html_content.count("a4-page") + html_content.count("cover-page")
    logger.info(
        f"[HTML-SERVICE] {report_type} generated successfully",
        extra={
            "company": context["company_name"],
            "correlation_id": context["correlation_id"],
            "html_length": len(html_content),
            "page_count": page_count,
        },
    )
    return html_content


async def render_main_report_pdf_html(
    *,
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    template_service: TemplateService,
    logger: ReportVariantLogger,
    context: Mapping[str, Optional[str]],
    report_type: str,
    locale: str,
    rendering_timeout_seconds: float,
    min_html_content_length: int,
) -> str:
    """Render the WeasyPrint-optimized HTML report variant."""
    template_context = _aggregate_main_report_context(response, request, locale)

    try:
        html_content = await asyncio.wait_for(
            asyncio.to_thread(template_service.render_main_report_pdf, template_context, locale),
            timeout=rendering_timeout_seconds,
        )
    except asyncio.TimeoutError:
        raise ReportGenerationError(
            f"{report_type} rendering timed out after {rendering_timeout_seconds}s",
            company_name=context.get("company_name"),
            correlation_id=context.get("correlation_id"),
        )

    if not validate_html_content(
        html_content=html_content,
        context=context,
        report_type=report_type,
        min_length=min_html_content_length,
        logger=logger,
    ):
        raise ReportGenerationError(
            f"{report_type} rendered but HTML failed validation (empty or too short)",
            company_name=context.get("company_name"),
            correlation_id=context.get("correlation_id"),
        )

    logger.info(
        f"[HTML-SERVICE] {report_type} generated successfully",
        extra={
            "company": context["company_name"],
            "correlation_id": context["correlation_id"],
            "html_length": len(html_content),
        },
    )
    return html_content


async def render_simplified_report_html(
    *,
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    template_service: TemplateService,
    logger: ReportVariantLogger,
    context: Mapping[str, Optional[str]],
    report_type: str,
    rendering_timeout_seconds: float,
    min_html_content_length: int,
) -> Optional[str]:
    """Render the legacy simplified report variant."""
    try:
        logger.info(
            f"[HTML-SERVICE] Transforming data for {report_type}",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
            },
        )

        transformer = get_simplified_report_transformer()
        template_data = transformer.transform(response, request)

        logger.info(
            f"[HTML-SERVICE] Data transformation completed for {report_type}",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
                "template_data_keys": list(template_data.keys()),
            },
        )

        html_content = await asyncio.wait_for(
            asyncio.to_thread(template_service.render_simplified_report, template_data),
            timeout=rendering_timeout_seconds,
        )

        if validate_html_content(
            html_content=html_content,
            context=context,
            report_type=report_type,
            min_length=min_html_content_length,
            logger=logger,
        ):
            logger.info(
                f"[HTML-SERVICE] {report_type} generated successfully",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "html_length": len(html_content) if html_content else 0,
                },
            )
            return html_content
        return None

    except asyncio.TimeoutError:
        logger.error(
            f"[HTML-SERVICE] {report_type} generation timed out",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
                "timeout_seconds": rendering_timeout_seconds,
            },
            exc_info=True,
        )
        return None
    except Exception as error:
        logger.error(
            f"[HTML-SERVICE] {report_type} generation failed",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            exc_info=True,
        )
        return None
