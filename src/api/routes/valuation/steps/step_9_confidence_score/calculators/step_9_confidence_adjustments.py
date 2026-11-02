"""Adjustment rules for Step 9 confidence scoring."""

from collections.abc import Mapping
from decimal import Decimal

from src.utils.decimal_helpers import from_decimal, to_decimal

ConfidenceAdjustment = dict[str, object]

_STATIC_WARNING_ADJUSTMENTS = {
    "micro_business_risk": (
        -5,
        "Micro business (<€500K) - higher uncertainty",
    ),
    "small_absolute_ebitda": (
        -3,
        "Small EBITDA base (<€100K) - increased sensitivity",
    ),
    "low_margin_warning": (
        -5,
        "Low profitability margin (3-5%) - elevated risk",
    ),
    "small_business_quality": (
        -3,
        "Small business size (€500K-€1M) - size risk only",
    ),
}


def adjustment_total(adjustments: list[ConfidenceAdjustment]) -> int:
    return sum(int(adjustment["adjustment"]) for adjustment in adjustments)


def quality_of_earnings_adjustments(
    step2_5: Mapping[str, object] | None
) -> list[ConfidenceAdjustment]:
    if not step2_5:
        return []

    margin_analysis = step2_5.get("margin_analysis", {})
    if not isinstance(margin_analysis, Mapping):
        return []

    margin_stdev = to_decimal(margin_analysis.get("margin_stdev", 0))
    if not margin_analysis.get("quality_of_earnings_flag", False):
        return []

    if margin_stdev > Decimal("5.0"):
        return [
            {
                "type": "quality_of_earnings_high_volatility",
                "adjustment": -10,
                "reason": (
                    f"High margin volatility ({from_decimal(margin_stdev):.1f}pp stdev) "
                    "- Quality of Earnings concern per Hitchner (2017)"
                ),
                "margin_stdev": margin_stdev,
                "volatility_level": margin_analysis.get("volatility_level", "LOW"),
                "log_level": "warning",
            }
        ]

    if margin_stdev > Decimal("3.0"):
        return [
            {
                "type": "quality_of_earnings_medium_volatility",
                "adjustment": -5,
                "reason": (
                    f"Medium margin volatility ({from_decimal(margin_stdev):.1f}pp stdev) "
                    "- earnings consistency concern"
                ),
                "margin_stdev": margin_stdev,
                "log_level": "info",
            }
        ]

    return []


def data_quality_warning_adjustments(
    step2: Mapping[str, object] | None
) -> list[ConfidenceAdjustment]:
    if not step2:
        return []

    warnings = step2.get("data_quality_warnings", [])
    if not isinstance(warnings, list):
        return []

    return [
        adjustment
        for warning in warnings
        if isinstance(warning, Mapping)
        for adjustment in [_data_quality_warning_adjustment(warning)]
        if adjustment is not None
    ]


def _data_quality_warning_adjustment(warning: Mapping[str, object]) -> ConfidenceAdjustment | None:
    warning_type = warning.get("type")
    if not isinstance(warning_type, str):
        return None

    if warning_type in _STATIC_WARNING_ADJUSTMENTS:
        adjustment, reason = _STATIC_WARNING_ADJUSTMENTS[warning_type]
        return {"type": warning_type, "adjustment": adjustment, "reason": reason}

    if warning_type == "industry_margin_deviation":
        return _industry_margin_deviation_adjustment(warning)

    if warning_type == "thin_comparables_proxy":
        return _thin_comparables_proxy_adjustment(warning)

    return None


def _industry_margin_deviation_adjustment(
    warning: Mapping[str, object],
) -> ConfidenceAdjustment | None:
    details = _details_mapping(warning)

    # PROVENANCE GATE: never dock confidence against a sector margin that is not
    # a measured distribution. 147 of the 197 rows in
    # `business_types.typical_ebitda_margin_median` carry the seeded 15.00
    # default with NULL min/max; docking for a "deviation" from a placeholder
    # invents a penalty. Fail closed — an unflagged warning is unproven.
    if details.get("benchmark_measured") is not True:
        return None

    try:
        deviation_pct = float(details["deviation_pct"])
    except (KeyError, TypeError, ValueError):
        return None

    adjustment = -min(int(deviation_pct / 10), 10)
    if adjustment == 0:
        return None

    return {
        "type": "industry_margin_deviation",
        "adjustment": adjustment,
        "reason": (
            "EBITDA margin deviates from the measured sector band "
            f"({deviation_pct:.0f}% deviation)"
        ),
    }


def _thin_comparables_proxy_adjustment(warning: Mapping[str, object]) -> ConfidenceAdjustment:
    details = _details_mapping(warning)
    sample_size = details.get("sample_size")
    quality_score = details.get("quality_score")
    penalty = _thin_comparables_penalty(sample_size, quality_score)
    return {
        "type": "thin_comparables_proxy",
        "adjustment": -penalty,
        "reason": (
            "Industry multiple sourced from thin or proxy-sector data ("
            f"sample_size={sample_size}, quality_score={quality_score})"
        ),
    }


def _thin_comparables_penalty(sample_size: object, quality_score: object) -> int:
    penalty = 5
    try:
        if sample_size is not None and int(sample_size) <= 1:
            penalty = max(penalty, 10)
        if quality_score is not None and float(quality_score) < 0.5:
            penalty = max(penalty, 10)
    except (TypeError, ValueError):
        return penalty
    return penalty


def _details_mapping(warning: Mapping[str, object]) -> Mapping[str, object]:
    details = warning.get("details", {})
    return details if isinstance(details, Mapping) else {}
