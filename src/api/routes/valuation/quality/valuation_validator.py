from src.errors.error_types import ValidationError
from src.utils.exceptions import CalculationError

"""
Valuation Validator Module

Validates valuation results for completeness and reasonableness.

RESPONSIBILITIES:
- Validate required fields presence
- Check value reasonableness
- Ensure non-negative valuations
- Validate range calculations
- Detect and handle NaN/Infinity values

REFACTORING NOTE:
Extracted from valuation_orchestrator.py for better error handling and validation.
"""

import math
import threading
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

from .ma_invariant_checks import build_ma_invariant_warnings
from .valuation_range_validation import validate_equity_range

logger = get_logger(__name__)

# Lazy Prometheus counter — defense-in-depth telemetry for any range
# ordering drift that escaped Step 11 and reached the final validator.
# A non-zero rate here is a high-priority signal: it means either
# (a) Step 11's ordering invariant broke, or
# (b) a downstream stage (multiples_executor, post-deal swap) corrupted
# the band after Step 11. Investigate immediately.
#
# Thread-safety: lazy initialization is guarded by a module-level lock
# so concurrent first-callers don't race to create duplicate Prometheus
# metrics (which would raise ValueError("Duplicated timeseries...")).
_validator_repairs_counter = None
_validator_repairs_counter_lock = threading.Lock()


def _get_validator_repairs_counter():
    """Thread-safe lazy init for the range-repairs Prometheus counter."""
    global _validator_repairs_counter
    if _validator_repairs_counter is not None:
        return _validator_repairs_counter
    with _validator_repairs_counter_lock:
        # Double-checked locking: another thread may have initialized
        # while we waited for the lock.
        if _validator_repairs_counter is not None:
            return _validator_repairs_counter
        try:
            from prometheus_client import Counter

            _validator_repairs_counter = Counter(
                "valuation_validator_range_repairs_total",
                "Range ordering drift repaired by the final validator (defense-in-depth)",
                ["repair_kind"],  # "bound_widening"
            )
        except ValueError:
            # Already registered (e.g. test re-runs in same process). Use the
            # registry's name map instead of scanning arbitrary collectors.
            try:
                from prometheus_client import REGISTRY

                names_to_collectors = getattr(REGISTRY, "_names_to_collectors", {})
                _validator_repairs_counter = names_to_collectors.get(
                    "valuation_validator_range_repairs"
                ) or names_to_collectors.get("valuation_validator_range_repairs_total")
            except Exception:
                pass
        except Exception:
            pass
    return _validator_repairs_counter


class ValuationValidator:
    """
    Validates valuation calculation results

    Features:
    - Required field validation
    - Value reasonableness checks
    - Range validation
    - Error reporting
    """

    def __init__(self):
        """Initialize valuation validator"""
        self.logger = logger
        self.logger.debug("✅ ValuationValidator initialized")

    async def validate_results(self, results: Dict[str, Any], methodology: str) -> None:
        """
        Validate valuation results

        Args:
            results: Valuation calculation results
            methodology: Valuation methodology used

        Raises:
            ValueError: If validation fails
        """
        try:
            self.logger.debug("🔍 Validating valuation results", extra={"methodology": methodology})

            # Required fields
            required_fields = [
                "enterprise_value",
                "equity_value",
                "equity_value_low",
                "equity_value_mid",
                "equity_value_high",
            ]

            # Check each field
            missing_fields = []
            invalid_fields = []

            for field in required_fields:
                if field not in results:
                    missing_fields.append(field)
                    self.logger.error(
                        f"❌ Missing required field: {field}",
                        extra={"field": field, "methodology": methodology},
                    )
                elif results[field] is None or results[field] <= 0:
                    invalid_fields.append(field)
                    self.logger.error(
                        f"❌ Invalid value for {field}: {results.get(field)}",
                        extra={
                            "field": field,
                            "value": results.get(field),
                            "methodology": methodology,
                        },
                    )

            # Raise error if any validation failed
            if missing_fields:
                error_msg = (
                    f"Valuation failed: Missing required fields: {', '.join(missing_fields)}"
                )
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            if invalid_fields:
                error_msg = (
                    f"Valuation failed: Invalid values for fields: {', '.join(invalid_fields)}"
                )
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            # Validate range logic
            await self._validate_range(results)

            # CRITICAL: Validate for NaN/Infinity values
            nan_fields = self._validate_nan_infinity(results)
            if nan_fields:
                self.logger.error(
                    f"❌ Validation failed: Found NaN/Infinity in fields: {', '.join(nan_fields)}",
                    extra={"methodology": methodology, "nan_fields": nan_fields},
                )
                raise ValueError(
                    f"Valuation failed: Invalid values (NaN/Infinity) in fields: {', '.join(nan_fields)}"
                )

            # M&A invariants — non-fatal but high-signal for QA
            self._validate_ma_invariants(results, methodology)

            # DEBUG: validation pass; failures still log at WARN/ERROR.
            self.logger.debug(
                "✅ Valuation results validated successfully",
                extra={
                    "methodology": methodology,
                    "enterprise_value": results["enterprise_value"],
                    "equity_value": results["equity_value"],
                },
            )

        except ValueError:
            raise
        except (ValidationError, CalculationError) as e:
            self.logger.error(
                f"❌ Validation error: {e}",
                extra={"error": str(e), "error_type": type(e).__name__, "methodology": methodology},
                exc_info=True,
            )
            raise ValidationError(f"Validation failed: {str(e)}") from e
        except Exception as e:
            self.logger.error(
                f"❌ Validation error due to data issue: {e}",
                extra={"error": str(e), "error_type": type(e).__name__, "methodology": methodology},
                exc_info=True,
            )
            raise ValidationError(f"Validation failed for required fields: {e}") from e

    async def _validate_range(self, results: Dict[str, Any]) -> None:
        """Validate that range values are logically consistent."""
        validate_equity_range(results, self.logger, _get_validator_repairs_counter)

    def _validate_ma_invariants(self, results: Dict[str, Any], methodology: str) -> None:
        """M&A defensibility invariants — never fatal, always loud.

        These checks codify expectations a competent M&A practitioner would
        make about a finished valuation. Each violation is logged at
        WARNING level with structured context so QA can spot patterns in
        production. We deliberately do NOT raise — the checks are about
        catching regressions in upstream stages, not blocking valuations.

        Invariants checked (all configurable via ``Settings.ma_invariant_*``):

        1. **asking_price_above_mid** — asking price > equity_value_mid
           (recommended ask below mid is nonsensical for a sell-side report).
        2. **ev_equity_bridge** — EV ≈ Equity + Net Debt within ~1% tolerance
           (accounting bridge must reconcile).
        3. **equity_value_in_band** — canonical equity_value lies in [low, high]
           (catches drift between equity_value and band fields).
        4. **implied_ebitda_multiple_bounds** — EV/EBITDA in [1×, 25×] per
           Damodaran / McKinsey practitioner band (catches multiple
           miscalibration).
        5. **confidence_vs_data_thinness** — confidence ≥80% with ≤1 year of
           data is overconfident (confidence model mismatch).
        6. **band_width_too_narrow / too_wide** — (high-low)/mid in [10%, 250%]
           (catches overconfident or uselessly wide ranges).
        7. **ebitda_sde_cross_method_divergence** — EBITDA-path mid and
           SDE-path mid should triangulate within 100% (catches owner-comp
           normalization or methodology selection errors per Trugman 2017).
        8. **sole_trader_methodology_advisory** — for ≤1 employee businesses
           with primary=EBITDA but SDE available, advise SDE review
           (BizBuySell / Trugman: SDE is M&A-standard for owner-operated).
        9. **per_share_consistency** — per_share_value × shares_outstanding
           ≈ equity_value within 1% (per-share derivation correct).
        10. **asking_price_markup_too_high** — markup over mid ≤ 50% default
            (catches advisor override or config errors).
        """
        warnings = build_ma_invariant_warnings(results)

        # Persist violations on the result payload so report-layer consumers
        # can make deterministic gate decisions without log parsing.
        results["ma_invariant_violations"] = warnings

        if warnings:
            # Pass-9: surface the invariant codes inline so a `grep` of the
            # message string reveals which invariant failed instead of
            # forcing a structured-log viewer round-trip. Previously this
            # logged only "One or more failed" — the `extra={"violations":
            # warnings}` payload had the detail but our log shipper
            # truncated extras in some sinks. Codes pulled defensively in
            # case a future violation dict drops the `code` key.
            codes = []
            for w in warnings:
                if isinstance(w, dict):
                    code = w.get("invariant") or w.get("code") or w.get("type") or "unknown"
                    codes.append(str(code))
            codes_label = ",".join(sorted(set(codes))) if codes else "unknown"
            self.logger.warning(
                f"[MA-INVARIANT] {len(warnings)} M&A defensibility invariant(s) failed: {codes_label}",
                extra={
                    "methodology": methodology,
                    "violations": warnings,
                    "violation_count": len(warnings),
                    "violation_codes": sorted(set(codes)),
                    "note": "Non-fatal — investigate upstream Step 11 / methodology selection",
                },
            )

    def _validate_nan_infinity(
        self, data: Any, path: str = "", nan_fields: Optional[List[str]] = None
    ) -> List[str]:
        """
        Recursively validate data structure for NaN/Infinity values.

        Args:
            data: Data to validate (dict, list, or primitive)
            path: Current path in data structure (for error reporting)
            nan_fields: List to accumulate fields with NaN/Infinity

        Returns:
            List of field paths containing NaN/Infinity
        """
        if nan_fields is None:
            nan_fields = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                self._validate_nan_infinity(value, current_path, nan_fields)
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                current_path = f"{path}[{idx}]" if path else f"[{idx}]"
                self._validate_nan_infinity(item, current_path, nan_fields)
        elif isinstance(data, (int, float, Decimal)):
            try:
                val = float(data)
            except (TypeError, ValueError, OverflowError):
                return nan_fields
            if math.isnan(val) or math.isinf(val):
                nan_fields.append(path if path else "root")
                self.logger.warning(
                    f"⚠️ Found NaN/Infinity value at path: {path}",
                    extra={"path": path, "value": data},
                )

        return nan_fields

    def validate_valuation_response(self, response: Any) -> List[str]:
        """
        Validate ValuationResponse object for NaN/Infinity values.

        Args:
            response: ValuationResponse object or dict

        Returns:
            List of field paths with NaN/Infinity values (empty if all valid)
        """
        try:
            # Convert response to dict if it's a Pydantic model
            if hasattr(response, "model_dump"):
                response_dict = response.model_dump()
            elif hasattr(response, "dict"):
                response_dict = response.dict()
            elif isinstance(response, dict):
                response_dict = response
            else:
                self.logger.warning("Cannot validate response: not a dict or Pydantic model")
                return []

            # Validate all numeric fields
            nan_fields = self._validate_nan_infinity(response_dict)

            # Additional validation for critical fields (accountant-grade: no NaN/Infinity)
            critical_fields = [
                "equity_value_low",
                "equity_value_mid",
                "equity_value_high",
                "confidence_score",
                "enterprise_value",
                "enterprise_value_mid",  # Stateless API field; must be valid when present
                "equity_value",
            ]

            for field in critical_fields:
                if field in response_dict:
                    value = response_dict[field]
                    if value is None:
                        continue
                    # Handle int, float, Decimal (Pydantic model_dump may preserve Decimal)
                    try:
                        val_float = float(value)
                    except (TypeError, ValueError):
                        continue
                    if math.isnan(val_float) or math.isinf(val_float):
                        if field not in nan_fields:
                            nan_fields.append(field)
                    # Additional range validation for equity fields only (EV can be < equity when net_debt < 0)
                    elif field in [
                        "equity_value_low",
                        "equity_value_mid",
                        "equity_value_high",
                    ]:
                        if val_float <= 0:
                            self.logger.warning(
                                f"⚠️ Critical field {field} has non-positive value: {val_float}",
                                extra={"field": field, "value": val_float},
                            )
                    elif field == "confidence_score":
                        if not (0 <= val_float <= 100):
                            self.logger.warning(
                                f"⚠️ Confidence score outside valid range (0-100): {val_float}",
                                extra={"field": field, "value": val_float},
                            )

            if nan_fields:
                self.logger.error(
                    f"❌ ValuationResponse validation failed: NaN/Infinity found in {len(nan_fields)} field(s)",
                    extra={"nan_fields": nan_fields},
                )
            else:
                self.logger.debug("✅ ValuationResponse validated: No NaN/Infinity values found")

            return nan_fields

        except (ValidationError, CalculationError) as e:
            self.logger.error(
                f"❌ Error during ValuationResponse validation: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return []
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.error(
                f"❌ Error during ValuationResponse validation due to data issue: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return []
        except Exception as e:
            self.logger.error(
                f"❌ An unexpected error occurred during ValuationResponse validation: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return []
