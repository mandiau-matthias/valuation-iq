"""
Synthesis Executors

Extracted from synthesizer.py to reduce complexity.
These executors handle individual valuation methodology execution.
"""

from decimal import Decimal
from typing import Any, Optional, Tuple

from src.domain.models import DCFResult, FinancialMetrics, MultiplesResult
from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    DCFCalculationError,
    MarketDataError,
    MultiplesCalculationError,
    DomainError,
)
from src.utils.logging import get_logger, log_calculation_step
from src.utils.logging_context import get_current_context

logger = get_logger(__name__)


class DCFValuationExecutor:
    """Executes DCF valuation with error handling."""

    def __init__(self, dcf_engine, validation_coordinator, financial_data):
        self.dcf_engine = dcf_engine
        self.validation_coordinator = validation_coordinator
        self.financial_data = financial_data

    def execute(
        self,
        use_dcf: bool,
        projection_years: int,
        financial_metrics: FinancialMetrics,
        all_validation_warnings: list,
    ) -> Tuple[Optional[DCFResult], bool, list]:
        """
        Execute DCF valuation with comprehensive error handling.

        Returns:
            Tuple of (dcf_result, use_dcf_flag, updated_validation_warnings)
        """
        dcf_result = None

        # Skip DCF if EBITDA is negative (unprofitable companies)
        if use_dcf and self.financial_data.current_year.ebitda is not None:
            if self.financial_data.current_year.ebitda < Decimal("0"):
                logger.info(
                    "Skipping DCF for unprofitable company",
                    extra={
                        "ebitda": self.financial_data.current_year.ebitda,
                        "company": self.financial_data.company_name,
                    },
                )
                use_dcf = False

        if not use_dcf:
            return None, False, all_validation_warnings

        log_calculation_step(
            "dcf_valuation_start",
            inputs={
                "projection_years": projection_years,
                "company_name": self.financial_data.company_name,
            },
            outputs={},
            formula="DCF_Start = Initialize_DCF + Setup_Projection_Years + Start_Calculation",
        )

        try:
            dcf_result = self.dcf_engine.calculate_dcf_valuation(projection_years=projection_years)

            log_calculation_step(
                "dcf_valuation_complete",
                inputs={"dcf_result": dcf_result},
                outputs={
                    "equity_value": dcf_result.equity_value,
                    "confidence": (
                        dcf_result.confidence.value
                        if hasattr(dcf_result.confidence, "value")
                        else dcf_result.confidence
                    ),
                    "enterprise_value": dcf_result.enterprise_value,
                },
                formula="DCF_Complete = Calculate_DCF + Extract_Results + Log_Confidence",
            )

            session_id = self._get_session_id()
            logger.calculation(
                "DCF valuation completed",
                session_id=session_id,
                equity_value=f"\u20AC{dcf_result.equity_value:,.0f}",
                confidence=(
                    dcf_result.confidence.value
                    if hasattr(dcf_result.confidence, "value")
                    else dcf_result.confidence
                ),
            )

            # Validate DCF results
            dcf_validation_warnings = self.validation_coordinator.validate_calculation_results(
                dcf_result, financial_metrics
            )
            if dcf_validation_warnings:
                all_validation_warnings.extend(dcf_validation_warnings)
                for warning in dcf_validation_warnings:
                    logger.warning("DCF validation check", warning=warning)

            return dcf_result, True, all_validation_warnings

        except (CalculationError, DataQualityError, MarketDataError, DomainError):
            # Re-raise specific errors
            raise
        except (ValueError, TypeError, ZeroDivisionError, AttributeError, KeyError) as e:
            self._handle_dcf_error(e, projection_years)
            return None, False, all_validation_warnings
        except DCFCalculationError as e:
            self._handle_dcf_error(e, projection_years)
            return None, False, all_validation_warnings

    def _handle_dcf_error(self, error: Exception, projection_years: int) -> None:
        """Handle DCF calculation errors."""
        logger.error(
            "DCF valuation failed",
            extra={
                "error": str(error),
                "error_type": type(error).__name__,
                "company": self.financial_data.company_name,
                "revenue": self.financial_data.current_year.revenue,
                "ebitda": self.financial_data.current_year.ebitda,
                "projection_years": projection_years,
            },
            exc_info=True,
        )
        log_calculation_step(
            "dcf_valuation_failed",
            inputs={"error": str(error), "error_type": type(error).__name__},
            outputs={},
            formula="DCF_Failed = Error_Occurred + Log_Details + Set_Use_DCF_False",
        )

    def _get_session_id(self) -> Optional[str]:
        """Get current session ID from logging context."""
        logging_context = get_current_context()
        return (
            getattr(logging_context, "current_session_id", None) if logging_context else None
        )


class MultiplesValuationExecutor:
    """Executes multiples valuation with error handling."""

    def __init__(self, multiples_engine, financial_data):
        self.multiples_engine = multiples_engine
        self.financial_data = financial_data

    def execute(self, use_multiples: bool) -> Tuple[Optional[MultiplesResult], bool]:
        """
        Execute multiples valuation with comprehensive error handling.

        Returns:
            Tuple of (multiples_result, use_multiples_flag)
        """
        if not use_multiples:
            return None, False

        log_calculation_step(
            "multiples_valuation_start",
            inputs={
                "company_name": self.financial_data.company_name,
                "comparables_count": len(self.multiples_engine.comparables),
            },
            outputs={},
            formula="Multiples_Start = Initialize_Multiples + Setup_Comparables + Start_Calculation",
        )

        try:
            multiples_result = self.multiples_engine.calculate_multiples_valuation()

            log_calculation_step(
                "multiples_valuation_complete",
                inputs={"multiples_result": multiples_result},
                outputs={
                    "equity_value": multiples_result.adjusted_equity_value,
                    "confidence": (
                        multiples_result.confidence.value
                        if hasattr(multiples_result.confidence, "value")
                        else multiples_result.confidence
                    ),
                    "enterprise_value": multiples_result.ev_ebitda_valuation or multiples_result.ev_revenue_valuation,
                },
                formula="Multiples_Complete = Calculate_Multiples + Extract_Results + Log_Confidence",
            )

            logger.calculation(
                "Multiples valuation completed",
                equity_value=f"€{multiples_result.adjusted_equity_value:,.0f}",
                confidence=(
                    multiples_result.confidence.value
                    if hasattr(multiples_result.confidence, "value")
                    else multiples_result.confidence
                ),
            )

            return multiples_result, True

        except (CalculationError, DataQualityError, MarketDataError, DomainError):
            # Re-raise specific errors
            raise
        except (ValueError, TypeError, ZeroDivisionError, AttributeError, KeyError) as e:
            self._handle_multiples_error(e)
            return None, False
        except MultiplesCalculationError as e:
            self._handle_multiples_error(e)
            return None, False

    def _handle_multiples_error(self, error: Exception) -> None:
        """Handle multiples calculation errors."""
        logger.error(
            "Multiples valuation failed",
            extra={
                "error": str(error),
                "error_type": type(error).__name__,
                "company": self.financial_data.company_name,
                "industry": self.financial_data.industry,
                "comparables_count": len(self.multiples_engine.comparables),
                "revenue": self.financial_data.current_year.revenue,
                "ebitda": self.financial_data.current_year.ebitda,
            },
            exc_info=True,
        )
        log_calculation_step(
            "multiples_valuation_failed",
            inputs={"error": str(error), "error_type": type(error).__name__},
            outputs={},
            formula="Multiples_Failed = Error_Occurred + Log_Details + Set_Use_Multiples_False",
        )

