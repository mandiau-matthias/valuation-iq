"""Runtime dependency assembly for ``HTMLReportService``."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.services.domain.charts.financial_charts import FinancialChartService
from src.services.infrastructure.html_report_runtime import HTMLReportRuntimeSupport
from src.services.infrastructure.pagination.pagination_service import PaginationService
from src.services.infrastructure.report_generation.health_checker import HealthChecker
from src.services.infrastructure.report_generation.metrics_collector import MetricsCollector
from src.services.infrastructure.report_generation.parallel_report_orchestrator import (
    ParallelReportOrchestrator,
)
from src.services.infrastructure.report_generation.shared_transformer import SharedDataTransformer
from src.services.infrastructure.report_generation.strategies import (
    AccountantViewStrategy,
    InfoTabStrategy,
    PDFGenerationStrategy,
)
from src.services.infrastructure.template_service import TemplateService
from src.utils.logging import get_logger


@dataclass(frozen=True)
class HTMLReportServiceRuntime:
    logger: object
    enable_smart_pagination: bool
    shared_transformer: SharedDataTransformer
    chart_service: FinancialChartService
    metrics_collector: MetricsCollector
    parallel_orchestrator: ParallelReportOrchestrator
    pagination_service: PaginationService | None
    accountant_view_strategy: AccountantViewStrategy
    info_tab_strategy: InfoTabStrategy
    pdf_strategy: PDFGenerationStrategy
    template_service: TemplateService | None
    health_checker: HealthChecker
    runtime_support: HTMLReportRuntimeSupport


def build_html_report_service_runtime(
    *,
    template_service: TemplateService | None,
    logger_instance: object | None,
    jinja_available: bool,
    template_service_factory: Callable[[], TemplateService],
) -> HTMLReportServiceRuntime:
    logger = logger_instance or get_logger(__name__)
    shared_transformer = SharedDataTransformer()
    chart_service = FinancialChartService()
    metrics_collector = MetricsCollector()
    parallel_orchestrator = ParallelReportOrchestrator(logger_instance=logger)
    pagination_service = None
    enable_smart_pagination = False

    logger.debug(
        "✅ [HTML-SERVICE] Using CSS-driven pagination (smart pagination disabled)",
        extra={
            "pagination_approach": "CSS print rules",
            "smart_pagination_disabled": True,
            "rationale": "H1 page-break-before + table page-break-inside handles pagination naturally",
            "target_page_count": "10-12 for typical reports",
            "benefits": [
                "Simpler code",
                "Faster performance",
                "More predictable",
                "Standard CSS",
            ],
        },
    )

    accountant_view_strategy = AccountantViewStrategy(
        logger_instance=logger,
        metrics_collector=metrics_collector,
    )
    info_tab_strategy = InfoTabStrategy(
        logger_instance=logger,
        metrics_collector=metrics_collector,
    )
    pdf_strategy = PDFGenerationStrategy(
        logger_instance=logger,
        metrics_collector=metrics_collector,
    )

    resolved_template_service = _resolve_template_service(
        template_service=template_service,
        logger=logger,
        jinja_available=jinja_available,
        template_service_factory=template_service_factory,
    )
    health_checker = HealthChecker(
        template_service=resolved_template_service,
        logger=logger,
    )
    runtime_support = HTMLReportRuntimeSupport(
        logger=logger,
        metrics_collector=metrics_collector,
        health_checker=health_checker,
        pdf_strategy=pdf_strategy,
    )

    logger.debug(
        "✅ [HTML-SERVICE] Rocket-Grade Twin Endpoint Architecture initialized",
        extra={
            "has_strategies": True,
            "has_circuit_breakers": True,
            "has_retry_handlers": True,
            "has_fallback_generators": True,
            "has_metrics_collector": True,
            "has_health_checker": True,
            "has_shared_transformer": True,
            "has_parallel_orchestrator": True,
            "has_smart_pagination": enable_smart_pagination and pagination_service is not None,
        },
    )

    return HTMLReportServiceRuntime(
        logger=logger,
        enable_smart_pagination=enable_smart_pagination,
        shared_transformer=shared_transformer,
        chart_service=chart_service,
        metrics_collector=metrics_collector,
        parallel_orchestrator=parallel_orchestrator,
        pagination_service=pagination_service,
        accountant_view_strategy=accountant_view_strategy,
        info_tab_strategy=info_tab_strategy,
        pdf_strategy=pdf_strategy,
        template_service=resolved_template_service,
        health_checker=health_checker,
        runtime_support=runtime_support,
    )


def _resolve_template_service(
    *,
    template_service: TemplateService | None,
    logger: object,
    jinja_available: bool,
    template_service_factory: Callable[[], TemplateService],
) -> TemplateService | None:
    if template_service is not None:
        logger.debug(
            "✅ [HTML-SERVICE] TemplateService injected",
            extra={
                "template_service_type": type(template_service).__name__,
                "jinja_available": jinja_available,
            },
        )
        return template_service

    if not jinja_available:
        logger.warning(
            "⚠️ [HTML-SERVICE] JINJA not available - template service not initialized",
            extra={
                "jinja_available": False,
                "template_service_is_none": True,
            },
        )
        return None

    try:
        resolved = template_service_factory()
        logger.info(
            "✅ [HTML-SERVICE] TemplateService initialized successfully",
            extra={
                "template_service_type": type(resolved).__name__,
                "jinja_available": True,
            },
        )
        return resolved
    except (ImportError, AttributeError, TypeError, ValueError) as init_error:
        logger.error(
            "❌ [HTML-SERVICE] TemplateService initialization failed",
            extra={
                "error_type": type(init_error).__name__,
                "error_message": str(init_error),
                "jinja_available": jinja_available,
                "error_category": "initialization_error",
            },
            exc_info=True,
        )
        return None
    except Exception as unexpected_init_error:
        logger.error(
            "❌ [HTML-SERVICE] Unexpected error during TemplateService initialization",
            extra={
                "error_type": type(unexpected_init_error).__name__,
                "error_message": str(unexpected_init_error),
                "jinja_available": jinja_available,
                "error_category": "unexpected_initialization_error",
            },
            exc_info=True,
        )
        return None
