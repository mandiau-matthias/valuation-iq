"""Template rendering timeout/error policy for HTML reports."""

from __future__ import annotations

import asyncio

from src.services.infrastructure.exceptions import TemplateRenderingError

TemplateData = dict[str, object]


async def render_template_with_timeout(
    *,
    template_service: object,
    logger: object,
    template_data: TemplateData,
    context: dict[str, str | None],
    report_type: str,
    render_method: str,
    timeout: float,
) -> str:
    logger.info(
        f"🔍 [HTML-SERVICE] Rendering template for {report_type}",
        extra={
            "company": context["company_name"],
            "correlation_id": context["correlation_id"],
            "report_type": report_type,
            "template_data_type": type(template_data).__name__,
            "template_data_keys": (
                list(template_data.keys()) if isinstance(template_data, dict) else "not_a_dict"
            ),
            "timeout_seconds": timeout,
        },
    )

    try:
        render_func = getattr(template_service, render_method)
        logger.info(
            f"🔍 [HTML-SERVICE] About to render template for {report_type}",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
                "report_type": report_type,
                "render_method": render_method,
                "template_service_available": template_service is not None,
                "render_func_type": type(render_func).__name__,
            },
        )
        html_content = await asyncio.wait_for(
            asyncio.to_thread(render_func, template_data), timeout=timeout
        )

        logger.info(
            f"🔍 [HTML-SERVICE] Template rendering completed for {report_type}",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
                "report_type": report_type,
                "html_content_type": type(html_content).__name__ if html_content else "None",
                "html_content_length": len(html_content) if html_content else 0,
            },
        )
        return html_content

    except asyncio.TimeoutError:
        logger.error(
            f"❌ [HTML-SERVICE] Template rendering timed out for {report_type}",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
                "report_type": report_type,
                "timeout_seconds": timeout,
                "error_category": "timeout_error",
            },
            exc_info=True,
        )
        raise TemplateRenderingError(
            f"Template rendering timed out after {timeout} seconds for {report_type}",
            company_name=context["company_name"],
            correlation_id=context["correlation_id"],
        )
    except Exception as render_error:
        logger.error(
            f"❌ [HTML-SERVICE] Template rendering failed for {report_type}",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
                "report_type": report_type,
                "error_type": type(render_error).__name__,
                "error_message": str(render_error),
                "error_category": "template_rendering_error",
            },
            exc_info=True,
        )
        raise TemplateRenderingError(
            f"Template rendering failed for {report_type}: {str(render_error)}",
            company_name=context["company_name"],
            correlation_id=context["correlation_id"],
        ) from render_error
