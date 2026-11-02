"""
Multiples processing support for Step 2 benchmarking.

This module keeps calibration, validation, and checksum generation out of the
main orchestration class while preserving the existing return contract.
"""

from __future__ import annotations


async def process_multiples(
    *,
    request,
    multiples_data,
    multiples_data_backup,
    revenue,
    ebitda_margin,
    business_category,
    correlation_id: str | None,
    sme_calibration_coordinator,
    data_quality_coordinator,
    logger,
) -> tuple[dict, dict, str]:
    try:
        calibration_result = (
            sme_calibration_coordinator.apply_sme_calibration_and_adjustments(
                request, multiples_data, revenue, ebitda_margin, business_category
            )
        )
        if isinstance(calibration_result, tuple) and len(calibration_result) == 2:
            multiples_data, sme_calibration_data = calibration_result
        else:
            logger.error(
                "Step 2: apply_sme_calibration_and_adjustments returned unexpected format",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "return_type": type(calibration_result).__name__,
                    "return_length": (
                        len(calibration_result)
                        if isinstance(calibration_result, tuple)
                        else None
                    ),
                },
            )
            if isinstance(calibration_result, tuple):
                multiples_data = (
                    calibration_result[0]
                    if len(calibration_result) > 0
                    else multiples_data
                )
                sme_calibration_data = (
                    calibration_result[1] if len(calibration_result) > 1 else {}
                )
            else:
                sme_calibration_data = {}
    except ValueError as unpack_error:
        logger.error(
            "Step 2: Unpacking error in apply_sme_calibration_and_adjustments",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "error_type": type(unpack_error).__name__,
                "error_message": str(unpack_error),
            },
            exc_info=True,
        )
        sme_calibration_data = {}

    allow_untrusted_multiples_fallback = getattr(
        request,
        "allow_untrusted_multiples_fallback",
        False,
    )
    if not allow_untrusted_multiples_fallback and isinstance(
        getattr(request, "metadata", None), dict
    ):
        allow_untrusted_multiples_fallback = (
            request.metadata.get("allow_untrusted_multiples_fallback") is True
        )
    multiples_data = data_quality_coordinator.validate_multiples_data(
        multiples_data,
        allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
    )

    if not multiples_data or not isinstance(multiples_data, dict):
        logger.error(
            "Step 2: multiples_data is invalid after validation",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "multiples_data_type": (
                    type(multiples_data).__name__ if multiples_data else None
                ),
            },
        )
        multiples_data = {}

    if multiples_data and isinstance(multiples_data, dict) and len(multiples_data) > 0:
        multiples_data_backup = multiples_data.copy()

    multiples_checksum = data_quality_coordinator.generate_multiples_checksum(
        multiples_data_backup
    )

    return multiples_data, sme_calibration_data, multiples_checksum
