"""
Info Tab Report Strategy

Implements report generation strategy for Info Tab HTML reports.
The Info Tab shows calculation breakdown and transparency data.
"""

import asyncio
import time
from typing import Dict, Optional, Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.infrastructure.exceptions import (
    MissingDataError,
    DataTransformationError,
    TemplateRenderingError,
)
from src.services.infrastructure.report_generation.strategies.base_report_strategy import (
    BaseReportStrategy,
)
from src.services.infrastructure.report_generation.circuit_breaker import (
    CircuitBreakerOpenError,
    CircuitState,
)
from src.services.infrastructure.report_generation.config import (
    ReportGenerationConfig,
)

if TYPE_CHECKING:
    from src.services.infrastructure.template_service import TemplateService


class InfoTabStrategy(BaseReportStrategy):
    """Strategy for generating Info Tab HTML reports."""

    def get_report_type(self) -> str:
        return "Info Tab"

    def get_timeout_seconds(self) -> float:
        return 30.0

    def get_min_content_length(self) -> int:
        return 50

    async def generate(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        context: Dict[str, Optional[str]],
        template_service: Any,
        transform_func: Callable,
        render_method: str,
    ) -> Optional[str]:
        report_type = self.get_report_type()
        start_time = time.monotonic()

        try:
            if self.circuit_breaker.get_state() == CircuitState.OPEN:
                self.logger.warning("%s circuit breaker is open — using fallback", report_type)
                return self._generate_fallback(response, request, context)

            result = await self._execute_with_retry(
                response, request, context, template_service, transform_func, render_method
            )

            if result:
                self.circuit_breaker._record_success()
                self.metrics_collector.record_success(report_type, time.monotonic() - start_time)
                return result

            self.circuit_breaker._record_failure()
            self.metrics_collector.record_failure(report_type, "empty_result", time.monotonic() - start_time)
            self.metrics_collector.record_fallback(report_type)
            return self._generate_fallback(response, request, context)

        except CircuitBreakerOpenError:
            self.metrics_collector.record_fallback(report_type)
            return self._generate_fallback(response, request, context)
        except (TemplateRenderingError, DataTransformationError) as e:
            self.logger.error("%s generation failed: %s", report_type, e)
            self.circuit_breaker._record_failure()
            self.metrics_collector.record_failure(report_type, type(e).__name__, time.monotonic() - start_time)
            self.metrics_collector.record_fallback(report_type)
            return self._generate_fallback(response, request, context)
        except Exception as e:
            self.logger.exception("%s unexpected error: %s", report_type, e)
            self.metrics_collector.record_failure(report_type, type(e).__name__, time.monotonic() - start_time)
            self.metrics_collector.record_fallback(report_type)
            return self._generate_fallback(response, request, context)

    async def _execute_with_retry(
        self, response, request, context, template_service, transform_func, render_method
    ) -> Optional[str]:
        report_data = transform_func(response, request, context)
        if not report_data:
            return None
        render_fn = getattr(template_service, render_method, None)
        if render_fn is None:
            return None
        return render_fn(report_data)

    def _generate_fallback(self, response, request, context) -> str:
        from src.services.infrastructure.report_generation.fallback_generator import FallbackGenerator
        return FallbackGenerator.generate_info_tab_fallback(response, request)
