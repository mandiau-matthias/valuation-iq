"""
Log Formatters for Financial Data

Specialized formatters for logging financial data with proper precision, formatting,
and privacy controls. Supports different formatting modes for development vs production.

ARCHITECTURE:
- Financial data formatters with precision control
- Privacy-aware formatting (hash sensitive values)
- Performance metrics formatting
- Calculation step formatting
- Audit trail formatting

USAGE:
    Use FinancialDataFormatter (optionally with privacy_mode) and AuditFormatter for structured
    financial and audit-oriented log payloads.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, TypedDict, Union

import structlog

LogPayload = dict[str, object]


def _mapping_or_empty(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


# Lazy imports to avoid circular dependency
def _get_core_decimal_helpers():
    """Lazy import of decimal helpers to avoid circular dependency."""
    from src.utils.decimal_helpers import from_decimal, to_decimal

    return to_decimal, from_decimal


def _get_core_formatters():
    """Lazy import of core formatters to avoid circular dependency."""
    from src.utils.core import format_currency as core_format_currency
    from src.utils.core import format_percent as core_format_percent

    return core_format_currency, core_format_percent


class FinancialDataFormatter:
    """
    Formatter for financial data with precision control and privacy features.

    Features:
    - Configurable precision for monetary values
    - Privacy mode for sensitive data (hashing)
    - Currency formatting
    - Percentage formatting
    - Ratio formatting
    """

    def __init__(
        self, precision: int = 2, privacy_mode: bool = False, currency_symbol: str = "\u20AC"
    ) -> None:
        self.precision = precision
        self.privacy_mode = privacy_mode
        self.currency_symbol = currency_symbol

        # Fields that should be hashed in privacy mode
        self.sensitive_fields = {
            "revenue",
            "ebitda",
            "ebit",
            "net_income",
            "cash",
            "debt",
            "equity",
            "assets",
            "liabilities",
            "working_capital",
            "capex",
            "depreciation",
            "free_cash_flow",
            "enterprise_value",
            "equity_value",
        }

    def format_financial_data(self, data: Mapping[str, object]) -> LogPayload:
        """Format financial data with appropriate precision and privacy controls"""
        formatted: LogPayload = {}

        for key, value in data.items():
            if isinstance(value, (int, float, Decimal)):
                if self.privacy_mode and key.lower() in self.sensitive_fields:
                    # Hash sensitive financial values
                    formatted[key] = self._hash_financial_value(value)
                else:
                    # Format with precision
                    formatted[key] = self._format_numeric_value(value)
            elif isinstance(value, Mapping):
                # Recursively format nested dictionaries
                formatted[key] = self.format_financial_data(value)
            elif isinstance(value, list):
                # Format lists of financial data
                formatted[key] = [self._format_list_item(item) for item in value]
            else:
                formatted[key] = value

        return formatted

    def _format_numeric_value(self, value: Union[int, Decimal, float]) -> Union[float, str]:
        """Format a numeric value with appropriate precision for JSON serialization"""
        to_decimal, _ = _get_core_decimal_helpers()
        if isinstance(value, Decimal):
            # Round Decimal to specified precision, then convert to float for JSON serialization
            rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return float(rounded)  # Convert to float only for JSON serialization
        elif isinstance(value, (int, float)):
            # Convert to Decimal for rounding, then back to float for JSON serialization
            decimal_value = to_decimal(value)
            rounded = decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return float(rounded)  # Convert to float only for JSON serialization
        else:
            return value

    def _hash_financial_value(self, value: Union[int, float, Decimal]) -> str:
        """Hash a financial value for privacy"""
        to_decimal, _ = _get_core_decimal_helpers()
        if isinstance(value, Decimal):
            value_str = str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        else:
            value_str = str(round(to_decimal(value), self.precision))

        # Create a hash that preserves some information (e.g., order of magnitude)
        hash_obj = hashlib.sha256(value_str.encode())
        return f"<HASHED:{hash_obj.hexdigest()[:8]}>"

    def _format_list_item(self, item: object) -> object:
        """Format an item in a list"""
        if isinstance(item, Mapping):
            return self.format_financial_data(item)
        elif isinstance(item, (int, float, Decimal)):
            return self._format_numeric_value(item)
        else:
            return item

    def format_currency(self, value: Union[int, float, Decimal]) -> str:
        """
        Format a value as currency.

        Uses unified utility from src.utils.core when not in privacy mode.
        In privacy mode, hashes the value for security.
        """
        if self.privacy_mode:
            return self._hash_financial_value(value)

        # Use unified utility for consistent formatting
        core_format_currency, _ = _get_core_formatters()
        currency_code = (
            "EUR"
            if self.currency_symbol == "\u20AC"
            else "USD" if self.currency_symbol == "$" else "GBP"
        )
        return core_format_currency(value, currency=currency_code, precision=self.precision)

    def format_percentage(
        self, value: Union[int, float, Decimal], precision: Optional[int] = None
    ) -> str:
        """
        Format a value as percentage.

        Uses unified utility from src.utils.core when not in privacy mode.
        In privacy mode, hashes the value for security.
        """
        if precision is None:
            precision = self.precision

        if self.privacy_mode:
            return self._hash_financial_value(value)

        # Use unified utility for consistent formatting
        # format_percent expects decimal (0.15 for 15%) and multiplies by 100 internally
        # The old implementation did: formatted_value * 100, meaning input was already decimal
        # So we can pass the value directly to the core utility
        _, core_format_percent = _get_core_formatters()
        return core_format_percent(value, precision=precision, include_sign=False)

    def format_ratio(
        self, value: Union[int, float, Decimal], precision: Optional[int] = None
    ) -> str:
        """Format a value as a ratio"""
        if precision is None:
            precision = self.precision

        if self.privacy_mode:
            return self._hash_financial_value(value)

        formatted_value = self._format_numeric_value(value)
        return f"{formatted_value:.{precision}f}x"


class CalculationStepFormatter:
    """
    Formatter for calculation steps with detailed logging.

    Features:
    - Step-by-step calculation logging
    - Input/output formatting
    - Formula tracking
    - Validation results
    """

    def __init__(self, financial_formatter: Optional[FinancialDataFormatter] = None) -> None:
        """
        Initialize calculation step formatter.

        Args:
            financial_formatter: Optional financial data formatter instance
        """
        self.financial_formatter = financial_formatter or FinancialDataFormatter()

    def format_calculation_step(
        self,
        step_name: str,
        inputs: Mapping[str, object],
        outputs: Mapping[str, object],
        formula: Optional[str] = None,
        validation: Optional[Mapping[str, object]] = None,
    ) -> LogPayload:
        """Format a calculation step with inputs, outputs, and metadata"""
        return {
            "step_name": step_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "inputs": self.financial_formatter.format_financial_data(inputs),
            "outputs": self.financial_formatter.format_financial_data(outputs),
            "formula": formula,
            "validation": validation,
            "step_type": "calculation",
        }

    def format_validation_step(
        self,
        validation_name: str,
        data: Mapping[str, object],
        rules: Sequence[str],
        results: Mapping[str, object],
    ) -> LogPayload:
        """Format a validation step"""
        return {
            "step_name": validation_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": self.financial_formatter.format_financial_data(data),
            "rules": rules,
            "results": results,
            "step_type": "validation",
        }

    def format_error_step(
        self,
        step_name: str,
        error: Exception,
        context: Mapping[str, object],
    ) -> LogPayload:
        """Format an error step"""
        return {
            "step_name": step_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": self.financial_formatter.format_financial_data(context),
            "step_type": "error",
        }


class AuditFormatter:
    """
    Formatter for audit trail logging with compliance features.

    Features:
    - Complete audit trail formatting
    - Data lineage tracking
    - Privacy compliance logging
    - Security event logging
    """

    def __init__(self, financial_formatter: Optional[FinancialDataFormatter] = None) -> None:
        """
        Initialize audit formatter.

        Args:
            financial_formatter: Optional financial data formatter instance
        """
        self.financial_formatter = financial_formatter or FinancialDataFormatter()

    def format_audit_event(
        self,
        event_type: str,
        actor: str,
        action: str,
        resource: str,
        data: Optional[Mapping[str, object]] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> LogPayload:
        """Format an audit event"""
        return {
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "resource": resource,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": self.financial_formatter.format_financial_data(data) if data else None,
            "metadata": metadata or {},
            "audit_level": "compliance",
        }

    def format_data_lineage(
        self,
        source: str,
        transformations: Sequence[Mapping[str, object]],
        destination: str,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> LogPayload:
        """Format data lineage information"""
        return {
            "source": source,
            "transformations": [
                {
                    "step": t.get("step"),
                    "timestamp": t.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    "data": self.financial_formatter.format_financial_data(
                        _mapping_or_empty(t.get("data", {}))
                    ),
                    "metadata": _mapping_or_empty(t.get("metadata", {})),
                }
                for t in transformations
            ],
            "destination": destination,
            "metadata": metadata or {},
            "lineage_type": "data_flow",
        }

    def format_privacy_event(
        self,
        event_type: str,
        data_classification: str,
        action: str,
        details: Optional[Mapping[str, object]] = None,
    ) -> LogPayload:
        """Format a privacy-related event"""
        return {
            "event_type": event_type,
            "data_classification": data_classification,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
            "privacy_level": "sensitive",
        }


class PerformanceFormatter:
    """
    Formatter for performance metrics and monitoring data.

    Features:
    - Performance metric formatting
    - Timing information
    - Resource usage formatting
    - Throughput calculations
    """

    def __init__(self) -> None:
        """Initialize performance formatter."""
        pass

    def format_performance_metric(
        self,
        metric_name: str,
        value: Union[int, float, Decimal],
        unit: str,
        timestamp: Optional[datetime] = None,
    ) -> LogPayload:
        """Format a performance metric"""
        return {
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            "metric_type": "performance",
        }

    def format_timing_metric(
        self,
        operation: str,
        duration: Decimal,
        start_time: datetime,
        end_time: datetime,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> LogPayload:
        """Format a timing metric"""
        return {
            "operation": operation,
            "duration_seconds": round(duration, 4),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "metadata": metadata or {},
            "metric_type": "timing",
        }

    def format_throughput_metric(
        self,
        operation: str,
        count: int,
        duration: Decimal,
        unit: str = "operations/second",
    ) -> LogPayload:
        """Format a throughput metric"""
        throughput = count / duration if duration > 0 else 0
        return {
            "operation": operation,
            "count": count,
            "duration_seconds": duration,
            "throughput": round(throughput, 2),
            "unit": unit,
            "metric_type": "throughput",
        }


# Factory function for creating formatters
class FormatterRegistry(TypedDict):
    financial: FinancialDataFormatter
    calculation: CalculationStepFormatter
    audit: AuditFormatter
    performance: PerformanceFormatter


def create_formatters(precision: int = 2, privacy_mode: bool = False) -> FormatterRegistry:
    """Create a set of formatters with consistent configuration"""
    financial_formatter = FinancialDataFormatter(precision=precision, privacy_mode=privacy_mode)

    return {
        "financial": financial_formatter,
        "calculation": CalculationStepFormatter(financial_formatter),
        "audit": AuditFormatter(financial_formatter),
        "performance": PerformanceFormatter(),
    }


# Export all formatters
__all__ = [
    "FinancialDataFormatter",
    "CalculationStepFormatter",
    "AuditFormatter",
    "PerformanceFormatter",
    "create_formatters",
]
