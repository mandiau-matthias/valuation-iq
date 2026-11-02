"""
Summary and fallback helpers for the multiple journey builder.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from src.utils.core.data_extraction_helpers import extract_step_result
from src.utils.decimal_helpers import from_decimal, to_decimal


def get_multiple_journey_step_results(*, response, logger):
    if not hasattr(response, "detailed_results") or not response.detailed_results:
        correlation_id = getattr(response, "correlation_id", None)
        logger.error(
            "[MULTIPLE-JOURNEY-BUILDER] Cannot build multiple journey - detailed_results not available",
            extra={
                "company_name": response.company_name,
                "correlation_id": correlation_id,
                "has_detailed_results": hasattr(response, "detailed_results"),
                "detailed_results_is_none": (
                    response.detailed_results is None
                    if hasattr(response, "detailed_results")
                    else True
                ),
            },
        )
        return None

    step_results = response.detailed_results.get("step_results", {})
    correlation_id = getattr(response, "correlation_id", None)
    logger.error(
        "[MULTIPLE-JOURNEY-BUILDER] Building multiple journey from step results",
        extra={
            "company_name": response.company_name,
            "correlation_id": correlation_id,
            "available_steps": list(step_results.keys()) if step_results else [],
            "has_step_2": 2 in step_results if step_results else False,
            "has_step_2_5": 2.5 in step_results if step_results else False,
            "has_step_4": 4 in step_results if step_results else False,
            "has_step_5": 5 in step_results if step_results else False,
            "has_step_6": 6 in step_results if step_results else False,
            "step_results_type": type(step_results).__name__,
            "step_results_is_none": step_results is None,
        },
    )
    return step_results


def log_successful_multiple_journey(*, response, journey, logger) -> None:
    correlation_id = getattr(response, "correlation_id", None)
    total_adjustment = (
        journey[-1]["multiple"] - journey[0]["multiple"]
        if len(journey) > 1
        else Decimal("0")
    )
    logger.error(
        "[MULTIPLE-JOURNEY-BUILDER] Multiple journey built successfully",
        extra={
            "company_name": response.company_name,
            "correlation_id": correlation_id,
            "num_steps": len(journey),
            "base_multiple": float(journey[0]["multiple"]) if journey else None,
            "final_multiple": float(journey[-1]["multiple"]) if journey else None,
            "total_adjustment": float(total_adjustment),
            "methodology": "Multiple-first approach (Big 4 standard)",
            "journey_steps": [
                {
                    "step": item["step"],
                    "name": item["name"],
                    "multiple": float(item["multiple"]),
                }
                for item in journey
            ],
        },
    )


def build_fallback_multiple_journey(*, response, step_results, base_multiple, logger) -> list:
    correlation_id = getattr(response, "correlation_id", None)
    logger.error(
        "Multiple journey is empty - detailed diagnosis",
        extra={
            "company_name": response.company_name,
            "correlation_id": correlation_id,
            "has_step_results": (
                hasattr(response, "detailed_results")
                and response.detailed_results is not None
            ),
            "step_results_keys": list(step_results.keys()) if step_results else [],
            "has_step_2": 2 in step_results if step_results else False,
            "has_step_2_5": 2.5 in step_results if step_results else False,
            "has_step_4": 4 in step_results if step_results else False,
            "has_step_5": 5 in step_results if step_results else False,
            "has_step_6": 6 in step_results if step_results else False,
            "base_multiple_found": base_multiple is not None,
            "base_multiple_value": str(base_multiple) if base_multiple else None,
        },
    )

    logger.error(
        "[MULTIPLE-JOURNEY-BUILDER] Multiple journey empty; attempting fallback",
        extra={
            "company_name": response.company_name,
            "correlation_id": correlation_id,
            "has_base_multiple": base_multiple is not None,
            "has_equity_value": (
                hasattr(response, "equity_value_mid")
                and response.equity_value_mid is not None
            ),
        },
    )

    if (
        not base_multiple
        and hasattr(response, "multiples_valuation")
        and response.multiples_valuation
    ):
        multiples_valuation = response.multiples_valuation
        if (
            hasattr(multiples_valuation, "final_ebitda_multiple")
            and multiples_valuation.final_ebitda_multiple
        ):
            base_multiple = multiples_valuation.final_ebitda_multiple
            logger.error(
                "[MULTIPLE-JOURNEY-BUILDER] Using base multiple from multiples_valuation for fallback",
                extra={
                    "company_name": response.company_name,
                    "correlation_id": correlation_id,
                    "base_multiple": str(base_multiple),
                },
            )

    if not (
        base_multiple
        and hasattr(response, "equity_value_mid")
        and response.equity_value_mid
    ):
        return []

    step_results_fallback = (
        response.detailed_results.get("step_results", {})
        if hasattr(response, "detailed_results") and response.detailed_results
        else {}
    )
    ebitda = _get_fallback_ebitda(step_results_fallback)

    if ebitda:
        try:
            ebitda_decimal = to_decimal(ebitda)
            if ebitda_decimal <= 0:
                raise ValueError("Fallback EBITDA must be positive")
            equity_decimal = to_decimal(response.equity_value_mid)
            implied_multiple_decimal = equity_decimal / ebitda_decimal
            implied_multiple_float = float(from_decimal(implied_multiple_decimal))

            base_multiple_decimal = to_decimal(base_multiple)
            base_multiple_float = float(from_decimal(base_multiple_decimal))

            adjustment_decimal = implied_multiple_decimal - base_multiple_decimal
            adjustment_float = float(from_decimal(adjustment_decimal))

            journey = [
                {
                    "step": "1",
                    "name": "Base Multiple (Database)",
                    "multiple": base_multiple_float,
                    "adjustment": None,
                    "source": "Market data",
                    "reason": "Sector median from comparables",
                },
                {
                    "step": "5",
                    "name": "Final Calibrated Multiple",
                    "multiple": implied_multiple_float,
                    "adjustment": adjustment_float,
                    "source": "Risk adjustments",
                    "reason": "After owner, size, and liquidity discounts",
                },
            ]
            logger.error(
                "[MULTIPLE-JOURNEY-BUILDER] Created fallback journey with base and implied multiples",
                extra={
                    "company_name": response.company_name,
                    "correlation_id": correlation_id,
                    "base_multiple": str(base_multiple_float),
                    "implied_multiple": str(implied_multiple_float),
                    "ebitda": str(ebitda),
                    "equity_value": str(response.equity_value_mid),
                    "journey_length": len(journey),
                },
            )
            return journey
        except (ValueError, TypeError, InvalidOperation, ZeroDivisionError) as error:
            logger.error(
                "[MULTIPLE-JOURNEY-BUILDER] Failed to create fallback journey",
                extra={
                    "company_name": response.company_name,
                    "correlation_id": correlation_id,
                    "error": str(error),
                    "ebitda": str(ebitda),
                    "equity_value": (
                        str(response.equity_value_mid)
                        if hasattr(response, "equity_value_mid")
                        else None
                    ),
                },
                exc_info=True,
            )
            return []

    logger.error(
        "[MULTIPLE-JOURNEY-BUILDER] Cannot create fallback journey - EBITDA not found or invalid",
        extra={
            "company_name": response.company_name,
            "correlation_id": correlation_id,
            "ebitda": str(ebitda) if ebitda else None,
            "equity_value": (
                str(response.equity_value_mid)
                if hasattr(response, "equity_value_mid")
                else None
            ),
        },
    )
    return []


def log_final_journey_summary(*, response, step_results, journey, logger) -> None:
    correlation_id = getattr(response, "correlation_id", None)
    logger.error(
        "[MULTIPLE-JOURNEY-BUILDER] Final journey summary",
        extra={
            "company_name": response.company_name,
            "correlation_id": correlation_id,
            "journey_length": len(journey),
            "journey_is_empty": len(journey) == 0,
            "journey_steps": [step.get("step") for step in journey] if journey else [],
            "has_step_2": 2 in step_results if step_results else False,
            "has_step_2_5": 2.5 in step_results if step_results else False,
            "has_step_4": 4 in step_results if step_results else False,
            "has_step_5": 5 in step_results if step_results else False,
            "has_step_6": 6 in step_results if step_results else False,
            "fallback_used": (
                len(journey) > 0 and journey[-1].get("step") == "Fallback"
                if journey
                else False
            ),
        },
    )


def _get_fallback_ebitda(step_results):
    for step_number in (1, 2.5, 3):
        step_result = extract_step_result(step_results.get(step_number))
        if not step_result:
            continue
        ebitda = step_result.get("ebitda")
        if ebitda is None:
            ebitda = step_result.get("normalized_ebitda")
        if ebitda is not None:
            return ebitda
    return None
