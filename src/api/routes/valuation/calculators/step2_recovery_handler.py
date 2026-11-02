"""
Step 2 Recovery Handler

Encapsulates all recovery logic for Step 2 (multiples selection) when the result
is missing or invalid. Implements trusted recovery paths with checksum validation.
Concrete business-type valuations are guarded by ``Step2ResultExtractor`` and
must not use reconstructed defaults unless explicit fallback consent is present.

Recovery Paths:
1. __dict__ access
2. Metadata backup locations (multiples_backup, result_backup, multiples, outputs)
3. getattr with alternative attribute names
4. Reconstruction from request data for non-concrete or explicitly opted-in requests
"""

from decimal import Decimal
from typing import Dict, Optional, Tuple

from src.api.routes.valuation.benchmark_contract_utils import (
    request_allows_untrusted_multiples_fallback,
)
from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


class Step2RecoveryHandler:
    """Handles recovery of Step 2 multiples data through multiple fallback paths."""

    def recover_step_2_from_dict(
        self, step_2_output: object, correlation_id: Optional[str]
    ) -> Tuple[Optional[Dict[str, object]], bool]:
        """
        Recovery Path 1: Try accessing result via __dict__.

        Args:
            step_2_output: StepOutput object
            correlation_id: Optional correlation ID for logging

        Returns:
            Tuple of (recovered_result_dict, success_flag)
        """
        try:
            if hasattr(step_2_output, "__dict__"):
                step_2_dict = step_2_output.__dict__
                if (
                    "result" in step_2_dict
                    and isinstance(step_2_dict["result"], dict)
                    and len(step_2_dict["result"]) > 0
                ):
                    logger.info(
                        "✅ [DIAG-EXTRACT] Recovered step_2 from __dict__['result']",
                        extra={
                            "step_number": 2,
                            "correlation_id": correlation_id,
                            "operation": "recovery_success",
                            "recovery_source": "__dict__[result]",
                            "recovered_keys": list(step_2_dict["result"].keys()),
                            "recovered_size": len(step_2_dict["result"]),
                        },
                    )
                    return step_2_dict["result"], True
        except Exception as e:
            logger.debug(
                "⚠️ Recovery path 1 (__dict__) failed",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
        return None, False

    def recover_step_2_from_metadata(
        self, step_2_output: object, correlation_id: Optional[str]
    ) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
        """
        Recovery Path 2: Try metadata backup locations.

        Args:
            step_2_output: StepOutput object
            correlation_id: Optional correlation ID for logging

        Returns:
            Tuple of (recovered_result_dict, recovery_source_name)
        """
        if not hasattr(step_2_output, "metadata") or not isinstance(step_2_output.metadata, dict):
            return None, None

        metadata = step_2_output.metadata

        # Try multiples_backup first (with checksum validation)
        if "multiples_backup" in metadata and isinstance(metadata["multiples_backup"], dict):
            step_2 = metadata["multiples_backup"].copy()

            # Validate checksum if available
            if "multiples_checksum" in metadata:
                import hashlib
                import json

                checksum_data = {
                    "ev_revenue": from_decimal(
                        to_decimal(str(step_2.get("ev_revenue_multiple", 0))), precision=2
                    ),
                    "ev_ebitda": from_decimal(
                        to_decimal(str(step_2.get("ev_ebitda_multiple", 0))), precision=2
                    ),
                    "data_source": step_2.get("data_source", ""),
                }
                recovered_checksum = hashlib.md5(
                    json.dumps(checksum_data, sort_keys=True).encode(),
                    usedforsecurity=False,
                ).hexdigest()

                if recovered_checksum != metadata["multiples_checksum"]:
                    logger.warning(
                        "⚠️ Step 2 data integrity mismatch: recovered data differs from original",
                        extra={
                            "original_checksum": metadata["multiples_checksum"],
                            "recovered_checksum": recovered_checksum,
                            "ev_revenue": step_2.get("ev_revenue_multiple"),
                            "ev_ebitda": step_2.get("ev_ebitda_multiple"),
                        },
                    )
                else:
                    logger.info(
                        "✅ Step 2 checksum validation passed",
                        extra={"checksum": recovered_checksum},
                    )

            logger.debug(
                "✅ [DIAG-EXTRACT] Recovered step_2 from metadata.multiples_backup",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "operation": "recovery_success",
                    "recovery_source": "metadata.multiples_backup",
                    "recovered_keys": list(step_2.keys()),
                    "recovered_size": len(step_2),
                },
            )
            return step_2, "metadata.multiples_backup"

        # Try result_backup
        elif (
            "result_backup" in metadata
            and isinstance(metadata["result_backup"], dict)
            and len(metadata["result_backup"]) > 0
        ):
            step_2 = metadata["result_backup"]
            logger.debug(
                "✅ [DIAG-EXTRACT] Recovered step_2 from metadata.result_backup",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "operation": "recovery_success",
                    "recovery_source": "metadata.result_backup",
                    "recovered_keys": list(step_2.keys()),
                    "recovered_size": len(step_2),
                },
            )
            return step_2, "metadata.result_backup"

        # Try multiples
        elif "multiples" in metadata:
            step_2 = metadata.get("multiples", {})
            if step_2 and len(step_2) > 0:
                logger.debug(
                    "✅ Recovered step_2 from metadata.multiples",
                    extra={"recovered_keys": list(step_2.keys())},
                )
                return step_2, "metadata.multiples"

        # Try outputs
        elif "outputs" in metadata:
            step_2 = metadata.get("outputs", {})
            if step_2 and len(step_2) > 0:
                logger.debug(
                    "✅ Recovered step_2 from metadata.outputs",
                    extra={"recovered_keys": list(step_2.keys())},
                )
                return step_2, "metadata.outputs"

        return None, None

    def recover_step_2_from_attributes(
        self, step_2_output: object
    ) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
        """
        Recovery Path 3: Try getattr with different attribute names.

        Args:
            step_2_output: StepOutput object

        Returns:
            Tuple of (recovered_result_dict, recovery_source_name)
        """
        for attr_name in ["result", "_result", "data", "output"]:
            try:
                attr_value = getattr(step_2_output, attr_name, None)
                if isinstance(attr_value, dict) and len(attr_value) > 0:
                    logger.debug(
                        f"✅ Recovered step_2 from getattr('{attr_name}')",
                        extra={"recovered_keys": list(attr_value.keys())},
                    )
                    return attr_value, f"getattr_{attr_name}"
            except Exception:
                continue
        return None, None

    def reconstruct_step_2_from_request(self, request: ValuationRequest) -> Dict[str, object]:
        """
        Reconstruct step_2 from request data when step is missing.

        Args:
            request: Valuation request

        Returns:
            Reconstructed step_2 dictionary
        """
        if not request_allows_untrusted_multiples_fallback(request):
            raise ValueError(
                "Refusing Step 2 reconstruction without a resolved Delphi "
                "benchmark contract or explicit allow_untrusted_multiples_fallback=true"
            )

        business_type_id = getattr(request, "business_type_id", None)
        industry = getattr(request, "industry", None)
        business_model = getattr(request, "business_model", None)

        if business_type_id or industry or business_model:
            try:
                from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriage

                triage = BusinessTypeTriage()
                business_category = triage.get_business_type_category(
                    business_type_id, business_model, industry
                )

                defaults_by_category = {
                    "consulting": {"revenue": Decimal("1.5"), "ebitda": 7.0},
                    "saas_software": {"revenue": Decimal("3.5"), "ebitda": 12.0},
                    "ecommerce": {"revenue": Decimal("1.2"), "ebitda": 8.0},
                    "manufacturing": {"revenue": Decimal("1.2"), "ebitda": 7.0},
                    "retail": {"revenue": Decimal("0.8"), "ebitda": 6.0},
                    "professional_services": {"revenue": Decimal("1.5"), "ebitda": 8.0},
                    "services": {"revenue": Decimal("1.5"), "ebitda": 8.0},
                }

                category_value = (
                    business_category.value
                    if hasattr(business_category, "value")
                    else str(business_category)
                )
                defaults = defaults_by_category.get(
                    category_value, {"revenue": Decimal("1.5"), "ebitda": 7.0}
                )

                step_2 = {
                    "ev_revenue_multiple": defaults["revenue"],
                    "ev_ebitda_multiple": defaults["ebitda"],
                    "data_source": f"fallback_business_type_{category_value}",
                    "primary_method": "EV/Revenue",
                    "warning": f"Step 2 reconstructed from business type defaults ({category_value}) - independent of Step 0/1",
                }
                logger.info(
                    "✅ Reconstructed Step 2 from business type defaults (independent of Step 0/1)",
                    extra={"reconstructed_step_2": step_2, "business_category": category_value},
                )
                return step_2
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logger.warning(
                    "⚠️ Failed to get business category for Step 2 reconstruction",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "business_type_id": business_type_id,
                        "industry": industry,
                    },
                )
            except Exception as e:
                logger.warning(
                    "⚠️ Unexpected error getting business category for Step 2 reconstruction",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "business_type_id": business_type_id,
                        "industry": industry,
                    },
                )

        # Disclosed fallback: only reachable after explicit caller consent.
        return {
            "ev_revenue_multiple": Decimal("1.5"),
            "ev_ebitda_multiple": Decimal("7.0"),
            "data_source": "fallback_step_2_missing",
            "primary_method": "EV/Revenue",
            "warning": (
                "Step 2 not found in results; using explicitly disclosed "
                "untrusted fallback multiples"
            ),
        }
