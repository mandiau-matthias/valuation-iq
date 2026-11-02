"""
Metrics & Logging Coordinator

Handles metrics tracking, logging, and telemetry for valuation requests.
Extracted from valuation.py calculate_valuation() function.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

from fastapi import Request

from src.api.schemas import ValuationRequest, ValuationResponse
from src.config import get_settings
from src.utils.logging import get_logger

from ..metrics import (
    mode_selection_counter,
    optional_fields_gauge,
    valuation_duration_seconds,
    valuation_failure_counter,
    valuation_requests_total,
    valuation_success_counter,
)
from ..quality.data_quality_telemetry import build_data_quality_telemetry

logger = get_logger(__name__)


class MetricsLoggingCoordinator:
    """
    Coordinates metrics tracking and logging activities.

    Responsibilities:
    - Request tracking
    - Success/failure metrics
    - Duration tracking
    - Field usage logging
    - Optional fields tracking
    """

    def __init__(self) -> None:
        """Initialize metrics logging coordinator."""
        self.logger = logger

    def track_request(self, valuation_request: ValuationRequest) -> None:
        """
        Track incoming valuation request.

        Args:
            valuation_request: Valuation request
        """
        # Track request
        valuation_requests_total.labels(
            methodology=getattr(valuation_request, "methodology", "HYBRID"),
            industry=valuation_request.industry,
            business_model=valuation_request.business_model,
        ).inc()

        # Track optional fields usage
        optional_fields = [
            "business_type",
            "business_description",
            "business_highlights",
            "reason_for_selling",
            "city",
            "shares_for_sale",
        ]
        for field in optional_fields:
            if getattr(valuation_request, field, None):
                optional_fields_gauge.labels(field_name=field).set(1)

        # NOTE: `log_field_usage` is called once by request_processing_coordinator
        # (Step 10 of process_request). A second call here produced a
        # duplicate "Field usage: N/N fields provided" INFO line per request.

    def track_mode_selection(self, use_quick_mode: bool, selection_method: str) -> None:
        """
        Track mode selection.

        Args:
            use_quick_mode: Whether quick mode is used
            selection_method: How mode was selected ("explicit" | "auto")
        """
        selected_mode = "quick" if use_quick_mode else "comprehensive"
        mode_selection_counter.labels(mode=selected_mode, selection_method=selection_method).inc()

    def track_success(
        self, valuation_request: ValuationRequest, valuation_response: ValuationResponse
    ) -> None:
        """
        Track successful valuation calculation.

        Args:
            valuation_request: Valuation request
            valuation_response: Valuation response
        """
        valuation_success_counter.labels(
            methodology=getattr(valuation_request, "methodology", "HYBRID")
        ).inc()

        # Defensibility-gate telemetry (Three Towers Capital, 2026-04-29).
        # Logs data-quality signals on every successful valuation so we can
        # observe gate-eligibility on past demos before the gate itself ships.
        telemetry = build_data_quality_telemetry(valuation_request, valuation_response)

        self.logger.info(
            "Valuation calculation completed successfully",
            extra={
                "valuation_id": getattr(valuation_response, "valuation_id", None),
                "equity_value_mid": getattr(valuation_response, "equity_value_mid", None),
                "company_name": valuation_request.company_name,
                **telemetry,
            },
        )

    def track_failure(self, valuation_request: ValuationRequest, error: Exception) -> None:
        """
        Track failed valuation calculation.

        Args:
            valuation_request: Valuation request
            error: Exception that occurred
        """
        valuation_failure_counter.labels(
            methodology=getattr(valuation_request, "methodology", "HYBRID")
        ).inc()

        self.logger.error(
            "Valuation calculation failed",
            extra={
                "company_name": valuation_request.company_name,
                "error": str(error),
                "error_type": type(error).__name__,
            },
            exc_info=True,
        )

    def track_duration(self, valuation_request: ValuationRequest, duration: float) -> None:
        """
        Track valuation duration.

        Args:
            valuation_request: Valuation request
            duration: Duration in seconds
        """
        valuation_duration_seconds.labels(
            methodology=getattr(valuation_request, "methodology", "HYBRID")
        ).observe(duration)

    async def log_raw_request(self, request: Request) -> None:
        """
        Log raw request body for debugging. Only active when debug mode is enabled.

        Args:
            request: FastAPI request object
        """
        if not get_settings().debug:
            return

        try:
            body = await request.body()
            self.logger.debug(f"Raw request body: {body.decode()}")
        except (ValueError, UnicodeDecodeError, AttributeError):
            pass
