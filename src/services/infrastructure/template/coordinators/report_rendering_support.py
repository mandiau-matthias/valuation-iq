"""Support helpers for accountant-view report rendering."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from src.utils.exceptions import APIError

MASTER_TEMPLATE_PATH = "accountant_view/master_report.html"
REQUIRED_ACCOUNTANT_INCLUDES = [
    "accountant_view/cover_page.html",
    "accountant_view/executive_summary.html",
    "accountant_view/financial_analysis.html",
    "accountant_view/appendices.html",
    "accountant_view/table_of_contents.html",
    "accountant_view/sections/_ebitda_normalization.html",
    "accountant_view/sections/_master_valuation_waterfall.html",
    "accountant_view/sections/_strategic_roadmap.html",
]
REQUIRED_ACCOUNTANT_SECTIONS = [
    ("section-1", "Description of Engagement"),
    ("section-2", "Information Sources"),
    ("section-3", "Executive Summary"),
    ("section-4", "Company Overview"),
    ("section-5", "Financial Analysis"),
    ("section-6", "Valuation Methodologies"),
    ("section-7", "Valuation Conclusion"),
    ("section-8", "Appendices"),
]


def safe_company_name(valuation_data: Dict[str, Any] | None) -> object:
    return valuation_data.get("company_name", "N/A") if valuation_data else "N/A"


def require_jinja_available(logger: Any, jinja_available: bool) -> None:
    if jinja_available:
        return
    logger.error("Jinja2 not installed - cannot render template")
    raise ImportError(
        "Jinja2 is required for HTML report generation. "
        "Install with: pip install jinja2. "
        "Full report must be generated - fallback HTML is not acceptable."
    )


def is_missing_template_error(error: Exception) -> bool:
    error_msg = str(error)
    return (
        "Template not found" in error_msg
        or "not found" in error_msg.lower()
        or isinstance(error, FileNotFoundError)
    )


def template_environment_unavailable(env: object, error: Exception) -> bool:
    return not env or (isinstance(error, AttributeError) and "env" in str(error).lower())


def log_required_field_status(logger: Any, valuation_data: Dict[str, Any]) -> None:
    required_fields = ["company_name", "valuation_id", "valuation_date"]
    missing_fields = [
        field
        for field in required_fields
        if field not in valuation_data or valuation_data.get(field) is None
    ]
    if missing_fields:
        logger.warning(
            "⚠️ Missing required fields in template data",
            extra={
                "missing_fields": missing_fields,
                "company_name": valuation_data.get("company_name", "N/A"),
                "available_fields": list(valuation_data.keys())[:20],
            },
        )
        return

    logger.debug(
        "✅ All required fields present for template rendering",
        extra={
            "company_name": valuation_data.get("company_name", "N/A"),
            "valuation_id": valuation_data.get("valuation_id", "N/A"),
        },
    )


def attach_academic_references(logger: Any, valuation_data: Dict[str, Any]) -> None:
    academic_citations = valuation_data.get("academic_citations")
    if isinstance(academic_citations, dict) and "bibliography" in academic_citations:
        logger.info(
            "Using dynamic academic citations from provenance tracker",
            extra={"sources_count": academic_citations.get("total_sources", 0)},
        )
        references = academic_citations["bibliography"]
    else:
        from src.services.infrastructure.academic_references import get_references_for_report

        logger.info("Using static academic references (no dynamic citations available)")
        references = get_references_for_report()

    appendices = valuation_data.get("appendices")
    if isinstance(appendices, dict):
        appendices["academic_references"] = references
    else:
        valuation_data["appendices"] = {"academic_references": references}


def add_generation_timestamp(valuation_data: Dict[str, Any]) -> None:
    valuation_data["generation_timestamp"] = datetime.now(timezone.utc).isoformat()


def require_master_template(templates_dir: Path) -> None:
    master_template_file = templates_dir / MASTER_TEMPLATE_PATH
    if not master_template_file.exists():
        raise FileNotFoundError(
            f"Master template not found: {master_template_file}. "
            f"Templates directory: {templates_dir}"
        )


def missing_required_includes(
    templates_dir: Path,
    includes: Iterable[str] = REQUIRED_ACCOUNTANT_INCLUDES,
) -> List[str]:
    return [
        include_path for include_path in includes if not (templates_dir / include_path).exists()
    ]


def log_include_status(
    logger: Any,
    *,
    valuation_data: Dict[str, Any],
    templates_dir: Path,
    missing_includes: List[str],
) -> None:
    if missing_includes:
        logger.error(
            "❌ Required template includes not found",
            extra={
                "company_name": valuation_data.get("company_name", "N/A"),
                "missing_includes": missing_includes,
                "templates_dir": str(templates_dir),
            },
        )
        return

    logger.debug(
        "✅ All required template includes verified",
        extra={
            "company_name": valuation_data.get("company_name", "N/A"),
            "includes_count": len(REQUIRED_ACCOUNTANT_INCLUDES),
        },
    )


def prepare_accountant_template_context(valuation_data: Dict[str, Any]) -> Dict[str, Any]:
    from src.services.infrastructure.translations import get_translations, normalize_report_locale

    template_context = dict(valuation_data)
    locale = template_context.get("locale") or "nl"
    normalized_locale = normalize_report_locale(locale)
    country_code = str(template_context.get("country_code", "BE") or "BE").strip().upper() or "BE"
    template_context["locale"] = normalized_locale
    template_context["country_code"] = country_code
    template_context["t"] = get_translations(
        normalized_locale,
        country_code=country_code,
    )
    return template_context


def log_cover_page_status(logger: Any, *, html: str, valuation_data: Dict[str, Any]) -> None:
    if "cover-page" not in html.lower() and "cover_page" not in html.lower():
        logger.warning(
            "⚠️ Cover page may not have rendered - 'cover-page' class not found in HTML",
            extra={
                "company_name": valuation_data.get("company_name", "N/A"),
                "html_length": len(html),
                "has_valuation_id": "valuation_id" in valuation_data,
                "has_company_name": "company_name" in valuation_data,
                "has_valuation_date": "valuation_date" in valuation_data,
                "has_generation_timestamp": "generation_timestamp" in valuation_data,
            },
        )
        return

    logger.debug(
        "✅ Cover page detected in rendered HTML",
        extra={
            "company_name": valuation_data.get("company_name", "N/A"),
            "html_length": len(html),
        },
    )


def classify_rendered_sections(html: str) -> Tuple[List[str], List[str]]:
    rendered_sections = []
    missing_sections = []
    for section_id, section_name in REQUIRED_ACCOUNTANT_SECTIONS:
        if section_rendered(html, section_id):
            rendered_sections.append(section_name)
        else:
            missing_sections.append(section_name)
    return rendered_sections, missing_sections


def section_rendered(html: str, section_id: str) -> bool:
    if f'id="{section_id}"' in html or f"id='{section_id}'" in html or f"id={section_id}" in html:
        return True
    section_markers = {
        "section-1": ("Description of Assignment", "Description of Engagement"),
        "section-2": ("Information Sources",),
        "section-3": ("Executive Summary",),
        "section-4": ("Company Overview",),
        "section-5": ("Financial Analysis",),
        "section-6": ("Valuation Methodologies",),
        "section-7": ("Valuation Conclusion",),
        "section-8": ("Appendices",),
    }
    return any(marker in html for marker in section_markers.get(section_id, ()))


def log_section_status(logger: Any, *, html: str, valuation_data: Dict[str, Any]) -> None:
    rendered_sections, missing_sections = classify_rendered_sections(html)
    if missing_sections:
        logger.warning(
            "⚠️ Some sections may not have rendered completely",
            extra={
                "company_name": valuation_data.get("company_name", "N/A"),
                "missing_sections": missing_sections,
                "rendered_sections": rendered_sections,
                "html_length": len(html),
                "html_preview": html[:500] if html else None,
            },
        )
        return

    logger.debug(
        "✅ All required sections detected in rendered HTML",
        extra={
            "company_name": valuation_data.get("company_name", "N/A"),
            "sections_count": len(rendered_sections),
            "html_length": len(html),
        },
    )


def optimize_for_streaming(logger: Any, html: str) -> str:
    try:
        from src.services.progressive.html_optimizer import StreamingHTMLOptimizer

        optimizer = StreamingHTMLOptimizer()
        optimized_html = optimizer.optimize_for_streaming(html)
        logger.info(f"  ✓ HTML optimized for streaming: {len(optimized_html):,} chars")
        return optimized_html
    except ImportError:
        logger.warning("StreamingHTMLOptimizer not available - skipping optimization")
    except (ImportError, AttributeError) as opt_error:
        logger.warning(f"HTML optimization failed (non-critical): {opt_error}")
    except APIError as opt_error:
        logger.warning(f"Unexpected error during HTML optimization (non-critical): {opt_error}")
    return html


def performance_metrics(*, generation_duration: float, html: str) -> Dict[str, float]:
    return {
        "total_time_seconds": round(generation_duration, 2),
        "html_size_chars": len(html),
        "html_size_kb": round(len(html) / 1024, 2),
        "chars_per_second": (
            round(len(html) / generation_duration, 0) if generation_duration > 0 else 0
        ),
    }


def log_performance_thresholds(
    logger: Any,
    *,
    generation_duration: float,
    valuation_data: Dict[str, Any],
    metrics: Dict[str, float],
) -> None:
    if generation_duration > 10.0:
        logger.warning(
            "⚠️ Report generation exceeded 10s threshold",
            extra={
                "generation_time_seconds": generation_duration,
                "company_name": valuation_data.get("company_name", "N/A"),
                **metrics,
            },
        )
    elif generation_duration > 5.0:
        logger.info(
            "ℹ️ Report generation took >5s (acceptable but monitor)",
            extra={
                "generation_time_seconds": generation_duration,
                "company_name": valuation_data.get("company_name", "N/A"),
                **metrics,
            },
        )


def validate_rendered_html(
    html: object, *, template_path: str, templates_dir: Path, logger: Any
) -> str:
    if not html or len(str(html).strip()) == 0:
        raise ValueError("Master template rendered empty HTML - check template and data structure")
    if not isinstance(html, str):
        logger.error(
            "❌ CRITICAL: Generated HTML is not a string",
            extra={
                "html_type": type(html).__name__,
                "html_value": str(html)[:200],
            },
        )
        raise TypeError(f"Generated HTML is {type(html).__name__}, expected str")
    if len(html) == 0:
        logger.error(
            "❌ CRITICAL: Generated HTML is empty",
            extra={
                "template_path": template_path,
                "templates_dir": str(templates_dir),
            },
        )
        raise ValueError("Generated HTML is empty - master template rendered empty content")
    return html
