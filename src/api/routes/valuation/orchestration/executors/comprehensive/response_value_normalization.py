"""Schema-boundary value normalization for comprehensive responses."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.utils.decimal_helpers import to_decimal

MIN_RESPONSE_VALUE = Decimal("1.0")
VALID_CONFIDENCE_LEVELS = {"low", "medium", "high"}


@dataclass(frozen=True)
class NormalizedResponseValues:
    recommended_asking_price: object
    recommended_asking_multiple: object
    confidence_level: str
    clamped_confidence_score: int
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    dcf_weight: Decimal
    multiples_weight: Decimal


def normalize_response_values(
    *,
    logger: object,
    detailed_results: dict[str, object],
    methodology: str,
    recommended_asking_price: object,
    recommended_asking_multiple: object,
    confidence_level: str,
    confidence_score: Decimal,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
) -> NormalizedResponseValues:
    recommended_asking_price = _normalize_asking_price(
        logger,
        recommended_asking_price,
        equity_value_mid,
    )
    recommended_asking_multiple = _normalize_asking_multiple(
        logger,
        recommended_asking_multiple,
    )
    clamped_confidence_score = _clamp_confidence_score(confidence_score)
    confidence_level = _normalize_confidence_level(logger, confidence_level)
    equity_value_low, equity_value_mid, equity_value_high = _normalize_equity_values(
        logger,
        equity_value_low,
        equity_value_mid,
        equity_value_high,
    )
    dcf_weight, multiples_weight = _normalize_weights(detailed_results, methodology)

    return NormalizedResponseValues(
        recommended_asking_price=recommended_asking_price,
        recommended_asking_multiple=recommended_asking_multiple,
        confidence_level=confidence_level,
        clamped_confidence_score=clamped_confidence_score,
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
        dcf_weight=dcf_weight,
        multiples_weight=multiples_weight,
    )


def _normalize_asking_price(
    logger: object,
    recommended_asking_price: object,
    equity_value_mid: Decimal,
) -> object:
    if recommended_asking_price is not None and recommended_asking_price > 0:
        return recommended_asking_price
    logger.warning(
        "⚠️ recommended_asking_price was non-positive, flooring to equity_value_mid",
        extra={
            "original_value": str(recommended_asking_price),
            "floored_to": str(equity_value_mid),
        },
    )
    return max(equity_value_mid, MIN_RESPONSE_VALUE)


def _normalize_asking_multiple(
    logger: object,
    recommended_asking_multiple: object,
) -> object:
    if recommended_asking_multiple is None or recommended_asking_multiple > 0:
        return recommended_asking_multiple
    logger.warning(
        "⚠️ recommended_asking_multiple was non-positive, setting to None",
        extra={"original_value": str(recommended_asking_multiple)},
    )
    return None


def _clamp_confidence_score(confidence_score: Decimal) -> int:
    raw_confidence_score = (
        int(confidence_score * 100) if confidence_score <= Decimal("1.0") else int(confidence_score)
    )
    return max(0, min(100, raw_confidence_score))


def _normalize_confidence_level(logger: object, confidence_level: str) -> str:
    if confidence_level in VALID_CONFIDENCE_LEVELS:
        return confidence_level
    logger.warning(
        "⚠️ Invalid confidence_level, defaulting to 'medium'",
        extra={"original_value": confidence_level},
    )
    return "medium"


def _normalize_equity_values(
    logger: object,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    if equity_value_low is None or equity_value_low <= 0:
        logger.warning(
            "⚠️ equity_value_low non-positive, flooring",
            extra={"original": str(equity_value_low)},
        )
        equity_value_low = MIN_RESPONSE_VALUE
    if equity_value_mid is None or equity_value_mid <= 0:
        logger.warning(
            "⚠️ equity_value_mid non-positive, flooring",
            extra={"original": str(equity_value_mid)},
        )
        equity_value_mid = max(equity_value_low, MIN_RESPONSE_VALUE)
    if equity_value_high is None or equity_value_high <= 0:
        logger.warning(
            "⚠️ equity_value_high non-positive, flooring",
            extra={"original": str(equity_value_high)},
        )
        equity_value_high = max(equity_value_mid, MIN_RESPONSE_VALUE)
    return equity_value_low, equity_value_mid, equity_value_high


def _normalize_weights(
    detailed_results: dict[str, object],
    methodology: str,
) -> tuple[Decimal, Decimal]:
    raw_dcf_weight = detailed_results.get(
        "dcf_weight",
        (
            Decimal("1.0")
            if methodology == "DCF"
            else (Decimal("0.5") if methodology == "HYBRID" else Decimal("0.0"))
        ),
    )
    raw_multiples_weight = detailed_results.get(
        "multiples_weight",
        (
            Decimal("1.0")
            if methodology == "MULTIPLES"
            else (Decimal("0.5") if methodology == "HYBRID" else Decimal("0.0"))
        ),
    )
    return _clamp_unit_decimal(raw_dcf_weight), _clamp_unit_decimal(raw_multiples_weight)


def _clamp_unit_decimal(value: object) -> Decimal:
    return max(Decimal("0"), min(Decimal("1"), to_decimal(value)))
