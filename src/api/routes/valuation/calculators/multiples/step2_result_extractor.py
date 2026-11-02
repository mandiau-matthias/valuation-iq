"""
Step 2 Result Extractor

Responsibility: Extract and recover Step 2 results without bypassing the
Delphi benchmark-contract gate for concrete business-type valuations.

Single Responsibility: Step 2 result extraction and recovery only.
"""

from decimal import Decimal
from typing import Dict, Optional

from src.api.routes.valuation.benchmark_contract_utils import extract_resolved_benchmark_contract
from src.api.routes.valuation.benchmark_contract_utils import (
    request_allows_untrusted_multiples_fallback as _request_allows_untrusted_multiples_fallback,
)
from src.api.schemas import ValuationRequest
from src.utils.valuation_logger import ValuationLogger

from ..step2_recovery_handler import Step2RecoveryHandler

logger = ValuationLogger(__name__)


def _resolved_benchmark_contract(step_2: Dict[str, object]) -> Optional[Dict[str, object]]:
    return extract_resolved_benchmark_contract(step_2)


def _requires_resolved_contract(request: ValuationRequest) -> bool:
    return not _request_allows_untrusted_multiples_fallback(request)


class Step2ResultExtractor:
    """
    Extracts Step 2 results with comprehensive recovery logic.

    Single Responsibility: Step 2 result extraction and recovery only.
    """

    def __init__(self, step2_recovery: Optional[Step2RecoveryHandler] = None):
        """
        Initialize extractor with injected dependencies

        Args:
            step2_recovery: Step 2 recovery handler instance
        """
        self.logger = logger
        self.step2_recovery = step2_recovery or Step2RecoveryHandler()

    def extract_step_2_result(
        self,
        step_results: Dict[int, object],
        request: ValuationRequest,
        context: Optional[Dict[str, object]],
    ) -> Dict[str, object]:
        """
        Extract step_2 result with comprehensive recovery logic.

        Args:
            step_results: Dictionary mapping step numbers to StepOutput objects
            request: Valuation request
            context: Optional calculation context

        Returns:
            Step 2 result dictionary. Concrete business-type valuations must
            carry the resolved benchmark contract unless fallback
            consent is explicit.
        """
        correlation_id = context.get("correlation_id") if context else None

        # Case 1: Step 2 exists in results
        if 2 in step_results:
            step_2_output = step_results[2]

            # Validate StepOutput structure
            if not hasattr(step_2_output, "result"):
                self.logger.error(
                    "❌ CRITICAL: Step 2 output missing result attribute",
                    extra={
                        "step_2_output_type": type(step_2_output).__name__,
                        "step_2_output_attrs": [
                            attr for attr in dir(step_2_output) if not attr.startswith("_")
                        ],
                        "step_2_status": (
                            step_2_output.status.value if hasattr(step_2_output, "status") else None
                        ),
                        "all_step_numbers": list(step_results.keys()),
                    },
                )
                step_2 = {}
            elif not isinstance(step_2_output.result, dict):
                self.logger.error(
                    "❌ CRITICAL: Step 2 result is not a dict",
                    extra={
                        "step_2_result_type": type(step_2_output.result).__name__,
                        "step_2_result_value": step_2_output.result,
                        "step_2_status": (
                            step_2_output.status.value if hasattr(step_2_output, "status") else None
                        ),
                    },
                )
                step_2 = {}
            else:
                step_2 = step_2_output.result

            # Check if result needs recovery
            if not step_2 or len(step_2) == 0:
                self.logger.warning(
                    "⚠️ Step 2 result missing required fields, attempting recovery",
                    extra={
                        "has_ev_revenue": "ev_revenue_multiple" in step_2,
                        "has_ev_ebitda": "ev_ebitda_multiple" in step_2,
                        "has_data_source": "data_source" in step_2,
                        "has_primary_method": "primary_method" in step_2,
                        "result_keys": list(step_2.keys()),
                        "result_size": len(step_2),
                    },
                )

                # Attempt recovery through multiple paths
                step_2 = self._attempt_recovery(step_2_output, request, correlation_id)

        else:
            # Case 2: Step 2 not in results. Missing benchmark output cannot
            # be reconstructed from generic defaults unless the caller opted
            # into a disclosed untrusted fallback.
            if _requires_resolved_contract(request):
                raise ValueError(
                    "Step 2 result is missing. "
                    "Refusing to reconstruct valuation multiples without the "
                    "resolved benchmark contract or explicit fallback consent."
                )
            self.logger.warning(
                "⚠️ Step 2 not found in step_results, reconstructing from request",
                extra={
                    "available_steps": list(step_results.keys()),
                    "step_statuses": {
                        k: v.status.value if hasattr(v, "status") else "unknown"
                        for k, v in step_results.items()
                    },
                    "step_0_exists": 0 in step_results,
                    "step_1_exists": 1 in step_results,
                },
            )
            step_2 = self.step2_recovery.reconstruct_step_2_from_request(request)
            self.logger.info(
                "✅ Step 2 reconstructed from request (fallback recovery)",
                extra={"fallback_multiples": step_2},
            )

        if _requires_resolved_contract(request) and not _resolved_benchmark_contract(step_2):
            raise ValueError(
                "Step 2 recovery produced multiples without a resolved Delphi "
                "benchmark contract. Refusing legacy fallback valuation."
            )

        # Log step_2 extraction for debugging
        self.logger.debug(
            "🔍 DEBUG: Extracting step_2 from step_results",
            extra={
                "step_2_exists": 2 in step_results,
                "step_2_type": type(step_results[2]).__name__ if 2 in step_results else None,
                "step_2_has_result": (
                    hasattr(step_results[2], "result") if 2 in step_results else False
                ),
                "step_2_result_type": (
                    type(step_results[2].result).__name__
                    if (2 in step_results and hasattr(step_results[2], "result"))
                    else None
                ),
                "step_2_keys": list(step_2.keys()) if step_2 else [],
                "step_2_is_empty": len(step_2) == 0 if step_2 else True,
                "step_2_ev_revenue_multiple": step_2.get("ev_revenue_multiple") if step_2 else None,
                "step_2_ev_ebitda_multiple": step_2.get("ev_ebitda_multiple") if step_2 else None,
                "step_2_data_source": step_2.get("data_source") if step_2 else None,
                "using_database_multiples": (
                    step_2.get("data_source") == "business_type_db" if step_2 else False
                ),
            },
        )

        # When titan_enrichment or another higher-priority source provided
        # the multiples, the data_source will not be "business_type_db" even
        # though business_type_id is set.  This is expected behaviour, not an
        # anomaly, so log at debug rather than warning.
        if (
            step_2
            and step_2.get("business_type_id")
            and step_2.get("data_source") != "business_type_db"
        ):
            self.logger.debug(
                "🔍 business_type_id present but data_source is not business_type_db",
                extra={
                    "business_type_id": step_2.get("business_type_id"),
                    "data_source": step_2.get("data_source"),
                    "multiples_source": step_2.get("multiples_source"),
                    "ev_revenue_multiple": step_2.get("ev_revenue_multiple"),
                    "ev_ebitda_multiple": step_2.get("ev_ebitda_multiple"),
                },
            )

        return step_2

    def _attempt_recovery(
        self,
        step_2_output: object,
        request: ValuationRequest,
        correlation_id: Optional[str],
    ) -> Dict[str, object]:
        """
        Attempt recovery through multiple paths.

        Args:
            step_2_output: Step 2 output object
            correlation_id: Optional correlation ID

        Returns:
            Recovered step 2 dictionary
        """
        recovery_successful = False
        recovery_source = None
        step_2 = {}

        # Recovery Path 1: __dict__
        if not recovery_successful:
            recovered, success = self.step2_recovery.recover_step_2_from_dict(
                step_2_output, correlation_id
            )
            if success:
                step_2 = recovered
                recovery_successful = True
                recovery_source = "__dict__[result]"

        # Recovery Path 2: Metadata
        if not recovery_successful:
            recovered, source = self.step2_recovery.recover_step_2_from_metadata(
                step_2_output, correlation_id
            )
            if recovered:
                step_2 = recovered
                recovery_successful = True
                recovery_source = source

        # Recovery Path 3: getattr
        if not recovery_successful:
            recovered, source = self.step2_recovery.recover_step_2_from_attributes(step_2_output)
            if recovered:
                step_2 = recovered
                recovery_successful = True
                recovery_source = source or "getattr_alternative"

        # Final fallback if all recovery failed. Concrete business-type
        # valuations fail closed instead of manufacturing default multiples.
        if not recovery_successful:
            self.logger.error(
                "❌ [DIAG-EXTRACT] CRITICAL: All recovery paths failed for step_2",
                extra={
                    "step_2_output_type": type(step_2_output).__name__,
                    "has_metadata": hasattr(step_2_output, "metadata"),
                    "metadata_type": (
                        type(step_2_output.metadata).__name__
                        if hasattr(step_2_output, "metadata")
                        else None
                    ),
                    "metadata_keys": (
                        list(step_2_output.metadata.keys())
                        if hasattr(step_2_output, "metadata")
                        and isinstance(step_2_output.metadata, dict)
                        else []
                    ),
                },
            )
            if _requires_resolved_contract(request):
                raise ValueError(
                    "Step 2 recovery failed. Refusing default multiples without "
                    "a resolved benchmark contract or explicit fallback consent."
                )
            step_2 = {
                "ev_revenue_multiple": Decimal("1.5"),
                "ev_ebitda_multiple": Decimal("7.0"),
                "data_source": "fallback_recovery_failed",
                "primary_method": "EV/Revenue",
                "warning": (
                    "Step 2 result recovery failed; using explicitly disclosed "
                    "untrusted fallback multiples"
                ),
            }
            self.logger.warning(
                "⚠️ Using fallback multiples due to Step 2 recovery failure",
                extra={"fallback_multiples": step_2},
            )
        else:
            self.logger.debug(
                "🔍 [DIAG-EXTRACT] After recovery attempt",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "operation": "after_recovery",
                    "recovery_successful": recovery_successful,
                    "recovery_source": recovery_source,
                    "step_2_keys": list(step_2.keys()) if isinstance(step_2, dict) else [],
                    "step_2_size": len(step_2) if isinstance(step_2, dict) else 0,
                    "has_ev_revenue_multiple": (
                        "ev_revenue_multiple" in step_2 if isinstance(step_2, dict) else False
                    ),
                    "has_ev_ebitda_multiple": (
                        "ev_ebitda_multiple" in step_2 if isinstance(step_2, dict) else False
                    ),
                },
            )

        return step_2
