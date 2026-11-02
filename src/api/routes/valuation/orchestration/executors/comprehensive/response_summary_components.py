"""Summary component assembly for comprehensive valuation responses."""

from __future__ import annotations

from src.config import get_settings

DEFAULT_VALUATION_SUMMARY = "Valuation completed successfully"
DEFAULT_RISK_FACTOR = (
    "Valuation estimates are subject to market conditions and comparable company data availability"
)


def attach_summary_components(
    response_dict: dict[str, object],
    *,
    summary_generator: object,
    logger: object,
    request: object,
    detailed_results: dict[str, object],
    methodology: str,
    methodology_downgrade_reason: object,
    dcf_exclusion_reason_precheck: object,
) -> None:
    try:
        _attach_generated_summary_components(
            response_dict,
            summary_generator=summary_generator,
            logger=logger,
            request=request,
            detailed_results=detailed_results,
            methodology=methodology,
            methodology_downgrade_reason=methodology_downgrade_reason,
            dcf_exclusion_reason_precheck=dcf_exclusion_reason_precheck,
        )
        logger.debug("Summary components generated")
    except Exception as summary_error:
        _attach_fallback_summary_components(
            response_dict,
            summary_generator=summary_generator,
            logger=logger,
            request=request,
            detailed_results=detailed_results,
            methodology=methodology,
            dcf_exclusion_reason_precheck=dcf_exclusion_reason_precheck,
            summary_error=summary_error,
        )


def _attach_generated_summary_components(
    response_dict: dict[str, object],
    *,
    summary_generator: object,
    logger: object,
    request: object,
    detailed_results: dict[str, object],
    methodology: str,
    methodology_downgrade_reason: object,
    dcf_exclusion_reason_precheck: object,
) -> None:
    note_context = _methodology_note_context(
        request,
        detailed_results,
        dcf_exclusion_reason_precheck,
    )
    response_dict["methodology_downgrade_reason"] = methodology_downgrade_reason
    response_dict["valuation_summary"] = summary_generator.generate_summary(
        request, detailed_results
    )
    response_dict["key_value_drivers"] = summary_generator.extract_value_drivers(
        request, detailed_results
    )
    response_dict["risk_factors"] = summary_generator.extract_risk_factors(
        request, detailed_results
    )
    response_dict["methodology_notes"] = summary_generator.generate_methodology_notes(
        methodology,
        requested_methodology=note_context["requested_methodology"],
        dcf_included=note_context["dcf_included"],
        dcf_exclusion_reason=note_context["dcf_exclusion_reason"],
        locale=note_context["locale"],
        country_code=note_context["country_code"],
    )
    _repair_empty_summary_components(
        response_dict,
        summary_generator=summary_generator,
        logger=logger,
        request=request,
        detailed_results=detailed_results,
        methodology=methodology,
    )


def _repair_empty_summary_components(
    response_dict: dict[str, object],
    *,
    summary_generator: object,
    logger: object,
    request: object,
    detailed_results: dict[str, object],
    methodology: str,
) -> None:
    validation_errors: list[str] = []

    risk_factors = response_dict.get("risk_factors")
    if not risk_factors or len(risk_factors) == 0:
        validation_errors.append("risk_factors is empty")
        logger.warning("Risk factors empty, regenerating with fallback")
        response_dict["risk_factors"] = summary_generator._generate_fallback_risk_factors(
            request, detailed_results
        )

    methodology_notes = response_dict.get("methodology_notes")
    if not methodology_notes or len(str(methodology_notes).strip()) == 0:
        validation_errors.append("methodology_notes is empty")
        response_dict["methodology_notes"] = f"Methodology: {methodology}"
        logger.warning("Methodology notes empty, using default")

    if validation_errors:
        logger.warning(
            "Validation errors found and corrected",
            extra={"errors": validation_errors},
        )
        if get_settings().debug:
            logger.warning(
                "Response validation errors",
                extra={"validation_errors": validation_errors},
            )


def _attach_fallback_summary_components(
    response_dict: dict[str, object],
    *,
    summary_generator: object,
    logger: object,
    request: object,
    detailed_results: dict[str, object],
    methodology: str,
    dcf_exclusion_reason_precheck: object,
    summary_error: Exception,
) -> None:
    error_msg = str(summary_error) if summary_error else "Unknown summary error"
    logger.error(
        "Summary generation failed, using defaults",
        extra={
            "error_message": error_msg,
            "error_type": type(summary_error).__name__,
        },
        exc_info=True,
    )
    response_dict["valuation_summary"] = DEFAULT_VALUATION_SUMMARY
    response_dict["key_value_drivers"] = []
    response_dict["risk_factors"] = _fallback_risk_factors(
        summary_generator,
        request,
        detailed_results,
    )
    response_dict["methodology_notes"] = _fallback_methodology_notes(
        summary_generator,
        request,
        detailed_results,
        methodology,
        dcf_exclusion_reason_precheck,
    )


def _fallback_risk_factors(
    summary_generator: object,
    request: object,
    detailed_results: dict[str, object],
) -> list[object]:
    try:
        return summary_generator._generate_fallback_risk_factors(request, detailed_results)
    except Exception:
        return [DEFAULT_RISK_FACTOR]


def _fallback_methodology_notes(
    summary_generator: object,
    request: object,
    detailed_results: dict[str, object],
    methodology: str,
    dcf_exclusion_reason_precheck: object,
) -> str:
    try:
        note_context = _methodology_note_context(
            request,
            detailed_results,
            dcf_exclusion_reason_precheck,
        )
        return summary_generator.generate_methodology_notes(
            methodology,
            requested_methodology=note_context["requested_methodology"],
            dcf_included=note_context["dcf_included"],
            dcf_exclusion_reason=note_context["dcf_exclusion_reason"],
            locale=note_context["locale"],
            country_code=note_context["country_code"],
        )
    except Exception:
        return f"Methodology: {methodology}"


def _methodology_note_context(
    request: object,
    detailed_results: dict[str, object],
    dcf_exclusion_reason_precheck: object,
) -> dict[str, object]:
    dcf_included = detailed_results.get("dcf_valuation") is not None
    return {
        "requested_methodology": getattr(request, "methodology", None),
        "dcf_included": dcf_included,
        "dcf_exclusion_reason": dcf_exclusion_reason_precheck if not dcf_included else None,
        "locale": getattr(request, "locale", None) or "nl",
        "country_code": str(getattr(request, "country_code", None) or "BE").strip().upper() or "BE",
    }
