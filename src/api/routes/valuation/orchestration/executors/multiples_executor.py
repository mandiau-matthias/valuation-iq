"""
Multiples Executor

Executes Multiples valuation methodology.
Handles Multiples calculation orchestration and result processing.
"""

from typing import Any, Dict, Optional

from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import to_decimal
from src.utils.equity_range_normalization import (
    coerce_equity_range_triple,
    sync_nested_equity_range_bounds,
)
from src.utils.valuation_logger import ValuationLogger

from .methodology_executor import MethodologyExecutor


class MultiplesExecutor(MethodologyExecutor):
    """
    Executor for Multiples valuation methodology.

    Responsibilities:
    - Execute Multiples calculation via MultiplesCalculator
    - Handle Multiples-specific result processing
    - Extract and structure Multiples results
    """

    def __init__(self, multiples_calculator, logger: Optional[ValuationLogger] = None):
        """
        Initialize Multiples executor.

        Args:
            multiples_calculator: MultiplesCalculator instance
            logger: Optional logger instance
        """
        super().__init__(logger)
        self.multiples_calculator = multiples_calculator
        self.logger.debug("✅ MultiplesExecutor initialized")

    async def execute(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute Multiples valuation.

        Args:
            request: Valuation request
            context: Optional processing context

        Returns:
            Dictionary with Multiples valuation results
        """
        self.validate_request(request)

        try:
            # DEBUG: layer-internal entry; canonical INFO entry is the
            # "🚀 Starting full 11-step calculation" line from execution_orchestrator.
            self.logger.debug("📊 Executing Multiples valuation")

            # Execute Multiples calculation
            multiples_results = await self.multiples_calculator.calculate(request, context)

            # Structure results
            detailed_results = multiples_results.copy()
            detailed_results["multiples_valuation"] = multiples_results

            # Extract Step 11 values and populate _value_sources
            step_results = multiples_results.get("_step_results", {})
            step_11_output = None
            if isinstance(step_results, dict):
                # Try int, float, and string keys to handle mixed key types
                for key in (11, 11.0, "11"):
                    step_11_output = step_results.get(key)
                    if step_11_output is not None:
                        break

            self.logger.debug(
                "🔍 Checking Step 11 availability for value extraction",
                extra={
                    "has_step_results": bool(step_results),
                    "step_results_keys": list(step_results.keys()) if isinstance(step_results, dict) else [],
                    "step_results_key_types": list(set(type(k).__name__ for k in step_results.keys())) if isinstance(step_results, dict) else [],
                    "step_11_found": step_11_output is not None,
                    "has_result_attr": hasattr(step_11_output, "result") if step_11_output is not None else False,
                    "correlation_id": context.get("correlation_id") if context else None,
                },
            )

            if step_11_output and hasattr(step_11_output, "result") and step_11_output.result:
                step_11_result = step_11_output.result

                # Extract Step 11 valuation values ('is not None' checks preserve zero values)
                extraction_count = 0
                for src_key, dst_key in [
                    ("valuation_low", "equity_value_low"),
                    ("valuation_mid", "equity_value_mid"),
                    ("valuation_high", "equity_value_high"),
                ]:
                    if step_11_result.get(src_key) is not None:
                        detailed_results[dst_key] = to_decimal(step_11_result[src_key])
                        extraction_count += 1

                if detailed_results.get("equity_value_mid") is not None:
                    detailed_results["equity_value"] = detailed_results["equity_value_mid"]
                    detailed_results["adjusted_equity_value"] = detailed_results[
                        "equity_value_mid"
                    ]

                if step_11_result.get("asking_price") is not None:
                    detailed_results["step_11_asking_price"] = to_decimal(step_11_result["asking_price"])
                if step_11_result.get("recommended_asking_multiple") is not None:
                    detailed_results["step_11_asking_multiple"] = to_decimal(step_11_result["recommended_asking_multiple"])

                if "_value_sources" not in detailed_results:
                    detailed_results["_value_sources"] = {}
                detailed_results["_value_sources"]["step_11_available"] = True
                detailed_results["_value_sources"]["equity_value_low_source"] = "Step 11"
                detailed_results["_value_sources"]["equity_value_mid_source"] = "Step 11"
                detailed_results["_value_sources"]["equity_value_high_source"] = "Step 11"
                detailed_results["_value_sources"]["equity_value_source"] = "Step 11"

                self.logger.debug(
                    "✅ Step 11 values extracted",
                    extra={
                        "extraction_count": extraction_count,
                        "equity_value_mid": str(detailed_results.get("equity_value_mid")),
                    },
                )
            else:
                if "_value_sources" not in detailed_results:
                    detailed_results["_value_sources"] = {}
                detailed_results["_value_sources"]["step_11_available"] = False
                self.logger.warning(
                    "⚠️ Step 11 not available in step_results, using fallback values",
                    extra={
                        "has_step_results": "_step_results" in multiples_results,
                        "step_results_keys": list(step_results.keys()) if isinstance(step_results, dict) else [],
                        "step_results_key_types": list(set(type(k).__name__ for k in step_results.keys())) if isinstance(step_results, dict) else [],
                    },
                )

            # Surface Step 0 historical-years count at the top level so the
            # downstream ValuationValidator can run its
            # ``confidence_vs_data_thinness`` M&A invariant. This is
            # best-effort — if Step 0 isn't present, the invariant skips.
            step_0_output = None
            if isinstance(step_results, dict):
                for key in (0, 0.0, "0"):
                    step_0_output = step_results.get(key)
                    if step_0_output is not None:
                        break
            if (
                step_0_output is not None
                and hasattr(step_0_output, "result")
                and isinstance(step_0_output.result, dict)
            ):
                step_0_result = step_0_output.result
                # Step 0 stores year count under a few possible names; try them
                for k in ("historical_years_count", "years_of_data", "data_years"):
                    yrs = step_0_result.get(k)
                    if yrs is not None:
                        try:
                            # Add 1 for current year if Step 0 only counted historical
                            if k == "historical_years_count":
                                detailed_results["years_of_data"] = int(yrs) + 1
                            else:
                                detailed_results["years_of_data"] = int(yrs)
                            break
                        except (TypeError, ValueError):
                            pass

            # Final invariant gate: bound-widen so mid sits inside [low, high].
            # This is *not* a "fallback" — it's the contract every executor
            # must satisfy before the validator runs (which executes BEFORE
            # ValueExtractor, see comprehensive_valuation_orchestrator.py).
            # Any widening here indicates an upstream synthesis bug
            # (Step 11 SDE blend, post-deal swap, etc.) — investigate.
            if (
                detailed_results.get("equity_value_low") is not None
                and detailed_results.get("equity_value_mid") is not None
                and detailed_results.get("equity_value_high") is not None
            ):
                low, mid, high, widened = coerce_equity_range_triple(
                    detailed_results["equity_value_low"],
                    detailed_results["equity_value_mid"],
                    detailed_results["equity_value_high"],
                )
                detailed_results["equity_value_low"] = low
                detailed_results["equity_value_mid"] = mid
                detailed_results["equity_value_high"] = high
                detailed_results["equity_value"] = mid
                detailed_results["adjusted_equity_value"] = mid
                sync_nested_equity_range_bounds(detailed_results)
                if widened:
                    self.logger.warning(
                        "⚠️ Multiples band widened to contain mid — investigate Step 11 synthesis",
                        extra={
                            "low": str(low),
                            "mid": str(mid),
                            "high": str(high),
                        },
                    )

            self.logger.info(
                "✅ Multiples valuation completed",
                extra={
                    "enterprise_value": detailed_results.get("enterprise_value"),
                    "equity_value": detailed_results.get("equity_value"),
                    "equity_value_low": detailed_results.get("equity_value_low"),
                    "equity_value_mid": detailed_results.get("equity_value_mid"),
                    "equity_value_high": detailed_results.get("equity_value_high"),
                    "step_11_available": detailed_results.get("_value_sources", {}).get("step_11_available", False),
                },
            )

            return detailed_results

        except Exception as e:
            self.handle_execution_error(e, request, context)
            raise
