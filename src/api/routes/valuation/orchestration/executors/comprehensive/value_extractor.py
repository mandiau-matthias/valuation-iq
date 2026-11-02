"""
Value Extractor

Extracts and validates equity values from detailed_results with comprehensive
fallback logic to handle nested structures and ensure data integrity.
"""

from decimal import Decimal
from typing import Optional

from src.api.routes.valuation.orchestration.executors.comprehensive.value_extraction_components import (
    equity_sources_are_authoritative,
    extract_raw_equity_values,
    normalize_equity_range,
    value_sources,
)
from src.utils.valuation_logger import ValuationLogger


class ValueExtractor:
    """
    Extracts equity values from detailed_results with fallback logic.

    Handles:
    - Top-level value extraction
    - Nested multiples_valuation extraction
    - Nested dcf_valuation extraction
    - Value sanitization and minimum value handling
    - Step 11 source validation
    """

    def __init__(self, logger: Optional[ValuationLogger] = None):
        """
        Initialize value extractor.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or ValuationLogger(self.__class__.__name__)

    def extract_equity_values(
        self, detailed_results: dict[str, object]
    ) -> tuple[object, object, Decimal, Decimal, Decimal]:
        """
        Extract equity values from detailed_results.

        Args:
            detailed_results: Dictionary containing valuation results

        Returns:
            Tuple of (enterprise_value, equity_value, equity_value_low, equity_value_mid, equity_value_high);
            range components are Decimal with low <= mid <= high.
        """
        raw_values = extract_raw_equity_values(detailed_results)
        normalized_range = normalize_equity_range(raw_values)

        if normalized_range.used_equity_value_mid_fallback:
            self.logger.warning(
                "⚠️ Using equity_value as fallback for equity_value_mid",
                extra={"equity_value": raw_values.equity_value},
            )

        if normalized_range.recovered_missing_mid:
            self.logger.error(
                "❌ CRITICAL: equity_value_mid is None after all fallbacks",
                extra={
                    "detailed_results_keys": list(detailed_results.keys()),
                    "has_multiples_valuation": "multiples_valuation" in detailed_results,
                    "has_dcf_valuation": "dcf_valuation" in detailed_results,
                    "equity_value": raw_values.equity_value,
                },
            )

        if normalized_range.applied_minimum_floor:
            self.logger.error(
                "❌ CRITICAL: equity_value_mid is 0 or negative, setting to minimum value",
                extra={
                    "original_equity_value_mid": raw_values.equity_value_mid,
                    "equity_value": raw_values.equity_value,
                    "note": "This indicates a calculation error, but setting to minimum to avoid validation failure",
                },
            )

        if normalized_range.widened:
            self.logger.warning(
                "⚠️ Equity range widened so mid lies within [low, high]",
                extra={
                    "low": str(normalized_range.equity_value_low),
                    "mid": str(normalized_range.equity_value_mid),
                    "high": str(normalized_range.equity_value_high),
                },
            )

        sources = value_sources(detailed_results)
        self.logger.debug(
            "🔍 ValuationOrchestrator: Extracting equity values from detailed_results",
            extra={
                "equity_value_low": normalized_range.equity_value_low,
                "equity_value_mid": normalized_range.equity_value_mid,
                "equity_value_high": normalized_range.equity_value_high,
                "equity_value_low_source": sources.get("equity_value_low_source", "unknown"),
                "equity_value_mid_source": sources.get("equity_value_mid_source", "unknown"),
                "equity_value_high_source": sources.get("equity_value_high_source", "unknown"),
                "step_11_available": sources.get("step_11_available", False),
                "note": "These values should come from Step 11 or the final Hybrid aggregation, not Step 3 intermediate values",
            },
        )

        if not equity_sources_are_authoritative(sources):
            self.logger.warning(
                "⚠️ ValuationOrchestrator: Equity values not all from authoritative final sources",
                extra={
                    "equity_value_low_source": sources.get("equity_value_low_source", "unknown"),
                    "equity_value_mid_source": sources.get("equity_value_mid_source", "unknown"),
                    "equity_value_high_source": sources.get("equity_value_high_source", "unknown"),
                    "warning": "Main report should display Step 11 or Hybrid final values, not intermediate step values",
                },
            )

        return (
            raw_values.enterprise_value,
            raw_values.equity_value,
            normalized_range.equity_value_low,
            normalized_range.equity_value_mid,
            normalized_range.equity_value_high,
        )
