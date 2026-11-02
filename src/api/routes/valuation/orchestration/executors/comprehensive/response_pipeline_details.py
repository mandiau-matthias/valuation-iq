"""Pipeline detail attachment helpers for comprehensive valuation responses."""

from __future__ import annotations

NORMALIZATION_RESULT_KEYS = (
    "ebitda_normalization_results",
    "step_2_5_multiple_calibration",
    "step_2_5_ebitda_normalization",
    "normalization_result",
)


def attach_multiples_pipeline_details(
    response_dict: dict[str, object],
    detailed_results: dict[str, object],
    *,
    correlation_id: str,
    logger: object,
) -> None:
    multiples_results = detailed_results.get("multiples_valuation", {})
    if isinstance(multiples_results, dict):
        _attach_step_results(
            response_dict,
            multiples_results,
            correlation_id=correlation_id,
            logger=logger,
        )
    _attach_ebitda_normalization(
        response_dict,
        detailed_results,
        correlation_id=correlation_id,
        logger=logger,
    )


def attach_multiples_prompt_payloads(
    response_dict: dict[str, object],
    detailed_results: dict[str, object],
) -> None:
    multiples_results = detailed_results.get("multiples_valuation") or {}
    if not isinstance(multiples_results, dict):
        return

    step_results = multiples_results.get("_step_results", {})
    if not isinstance(step_results, dict):
        return

    anomaly_data = _step_result_field(step_results, 1, "trial_balance_anomalies")
    if isinstance(anomaly_data, dict) and anomaly_data.get("has_anomalies"):
        response_dict["trial_balance_anomalies"] = anomaly_data

    nwc_data = _step_result_field(step_results, 7, "nwc_normalization")
    if nwc_data:
        response_dict["nwc_normalization"] = nwc_data


def _attach_step_results(
    response_dict: dict[str, object],
    multiples_results: dict[str, object],
    *,
    correlation_id: str,
    logger: object,
) -> None:
    step_results = multiples_results.get("_step_results")
    if not step_results or not isinstance(step_results, dict):
        return

    details = _response_details(response_dict)
    details["step_results"] = step_results
    details["multiples_valuation"] = multiples_results
    logger.debug(
        "✅ Added step_results to response_dict.detailed_results",
        extra={
            "step_results_keys": list(step_results.keys()),
            "total_steps": len(step_results),
            "correlation_id": correlation_id,
        },
    )


def _attach_ebitda_normalization(
    response_dict: dict[str, object],
    detailed_results: dict[str, object],
    *,
    correlation_id: str,
    logger: object,
) -> None:
    normalization_results = _first_normalization_result(detailed_results)
    if not normalization_results:
        return

    details = _response_details(response_dict)
    details["ebitda_normalization"] = normalization_results

    if isinstance(normalization_results, dict):
        logger.info(
            "✅ Added quality calibration to response_dict.detailed_results",
            extra={
                "has_quality_factors": bool(normalization_results.get("quality_factors")),
                "quality_multiple_adjustment": normalization_results.get(
                    "quality_multiple_adjustment"
                ),
                "normalized_ebitda": normalization_results.get("normalized_ebitda"),
                "correlation_id": correlation_id,
            },
        )


def _first_normalization_result(detailed_results: dict[str, object]) -> object:
    for key in NORMALIZATION_RESULT_KEYS:
        value = detailed_results.get(key)
        if value:
            return value
    return None


def _response_details(response_dict: dict[str, object]) -> dict[str, object]:
    details = response_dict.get("detailed_results")
    if not isinstance(details, dict):
        details = {}
        response_dict["detailed_results"] = details
    return details


def _step_result_field(
    step_results: dict[object, object],
    step_number: int,
    field_name: str,
) -> object:
    step_output = (
        step_results.get(step_number)
        or step_results.get(float(step_number))
        or step_results.get(str(step_number))
    )
    result = _step_result_payload(step_output)
    if isinstance(result, dict):
        return result.get(field_name)
    return None


def _step_result_payload(step_output: object) -> object:
    if step_output is None:
        return None
    if isinstance(step_output, dict):
        return step_output.get("result")
    return getattr(step_output, "result", None)
