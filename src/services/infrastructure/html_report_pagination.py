"""Pagination policy for HTML report output."""

from __future__ import annotations


async def apply_css_pagination_policy(
    *,
    html_content: str,
    context: dict[str, str | None],
    report_type: str,
    enable_smart_pagination: bool,
    pagination_service: object | None,
    logger: object,
) -> str:
    logger.error(
        f"🚨 [HTML-SERVICE] _apply_smart_pagination() ENTRY: {report_type}",
        extra={
            "company": context.get("company_name", "unknown"),
            "correlation_id": context.get("correlation_id"),
            "report_type": report_type,
            "enable_smart_pagination": enable_smart_pagination,
            "pagination_service_exists": pagination_service is not None,
            "html_content_length": len(html_content) if html_content else 0,
            "html_content_is_none": html_content is None,
        },
    )
    logger.info(
        f"✅ [HTML-SERVICE] Using CSS-driven pagination for {report_type}",
        extra={
            "company": context.get("company_name", "unknown"),
            "correlation_id": context.get("correlation_id"),
            "report_type": report_type,
            "pagination_approach": "CSS print rules",
            "html_length": len(html_content) if html_content else 0,
            "html_content_is_none": html_content is None,
            "rationale": "H1 page-break-before + table page-break-inside provides natural pagination",
        },
    )
    return html_content
