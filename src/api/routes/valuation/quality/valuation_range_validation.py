"""Range validation helpers for final valuation results."""

from decimal import Decimal

from src.errors.error_types import ValidationError
from src.utils.equity_range_normalization import (
    coerce_equity_range_triple,
    sync_nested_equity_range_bounds,
)
from src.utils.exceptions import CalculationError


def validate_equity_range(results: dict, logger, repairs_counter_factory) -> None:
    """Validate and repair final equity range ordering while preserving mid."""
    try:
        previous_low, previous_mid, previous_high = (
            results["equity_value_low"],
            results["equity_value_mid"],
            results["equity_value_high"],
        )
        for name, value in (
            ("low", previous_low),
            ("mid", previous_mid),
            ("high", previous_high),
        ):
            if value is None:
                error_msg = f"Invalid range: equity_value_{name} is None"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)

        low, mid, high, _ = coerce_equity_range_triple(
            previous_low,
            previous_mid,
            previous_high,
        )
        results["equity_value_low"] = low
        results["equity_value_mid"] = mid
        results["equity_value_high"] = high
        sync_nested_equity_range_bounds(results)

        for name, value in (("low", low), ("mid", mid), ("high", high)):
            try:
                if isinstance(value, Decimal) and value.is_nan():
                    error_msg = f"Invalid range: equity_value_{name} is NaN"
                    logger.error(f"❌ {error_msg}")
                    raise ValueError(error_msg)
            except (AttributeError, TypeError):
                pass

        if low <= 0 or mid <= 0 or high <= 0:
            error_msg = f"Invalid range: non-positive value(s) low={low}, mid={mid}, high={high}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        previous_low, previous_mid, previous_high = low, mid, high
        new_low, new_mid, new_high, widened = coerce_equity_range_triple(low, mid, high)
        results["equity_value_low"] = new_low
        results["equity_value_mid"] = new_mid
        results["equity_value_high"] = new_high
        sync_nested_equity_range_bounds(results)

        if not widened:
            logger.debug(
                "✅ Range validation passed",
                extra={"low": new_low, "mid": new_mid, "high": new_high},
            )
            return

        counter = repairs_counter_factory()
        if counter is not None:
            try:
                counter.labels(repair_kind="bound_widening").inc()
            except Exception:
                pass

        logger.warning(
            "⚠️ Range bounds widened to contain mid (mid preserved as gospel) — investigate Step 11 synthesis",
            extra={
                "low_before": str(previous_low),
                "mid_before": str(previous_mid),
                "high_before": str(previous_high),
                "low_after": str(new_low),
                "mid_after": str(new_mid),
                "high_after": str(new_high),
                "note": (
                    "Step 11 emitted an unordered band. The user received a valid "
                    "valuation with mid preserved exactly; the band was widened to "
                    "contain it. Find and fix the upstream synthesis stage that "
                    "produced the inconsistency."
                ),
            },
        )

    except ValueError:
        raise
    except (ValidationError, CalculationError) as error:
        logger.error(
            f"❌ Range validation failed: {error}",
            extra={"error": str(error), "error_type": type(error).__name__},
            exc_info=True,
        )
        raise
    except Exception as error:
        logger.error(
            f"❌ Range validation failed due to data issue: {error}",
            extra={"error": str(error), "error_type": type(error).__name__},
            exc_info=True,
        )
        raise CalculationError(f"Unexpected error during range validation: {error}") from error
