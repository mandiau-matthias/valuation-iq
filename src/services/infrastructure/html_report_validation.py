"""Rendered HTML validation policy for report services."""

from __future__ import annotations


def validate_html_content(
    *,
    html_content: str | None,
    context: dict[str, str | None],
    report_type: str,
    min_length: int,
    logger: object,
) -> bool:
    if html_content and isinstance(html_content, str) and len(html_content) >= min_length:
        logger.info(
            f"✅ [HTML-SERVICE] {report_type} HTML generated successfully",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
                "report_type": report_type,
                "html_length": len(html_content) if html_content else 0,
            },
        )
        return True

    logger.warning(
        f"⚠️ [HTML-SERVICE] {report_type} HTML generation returned empty or too short content",
        extra={
            "company": context["company_name"],
            "correlation_id": context["correlation_id"],
            "report_type": report_type,
            "html_content_is_none": html_content is None,
            "html_content_type": type(html_content).__name__ if html_content else "None",
            "html_content_length": len(html_content) if html_content else 0,
            "minimum_required_length": min_length,
        },
    )
    return False
