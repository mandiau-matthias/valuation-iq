"""Result-shaping helpers for API-layer DCF responses."""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import cast

from src.domain.models import ConfidenceLevel
from src.utils.decimal_helpers import from_decimal, optional_decimal, to_decimal


def full_dcf_projection_vectors(dcf_result: object) -> tuple[list[Decimal], list[Decimal]]:
    """Preserve the complete priced horizon for overrides and sensitivity math.

    Missing or invalid engine cells are an invalid calculation result, never
    zero cash flow. Display-only five-year previews must be made downstream.
    """
    vectors: list[list[Decimal]] = []
    for field in ("fcf_projections", "pv_fcf_projections"):
        raw_values = getattr(dcf_result, field, None)
        if (
            not isinstance(raw_values, Sequence)
            or isinstance(raw_values, (bytes, str))
            or not raw_values
        ):
            raise ValueError(f"DCF engine requires a nonempty {field} sequence")
        values: list[Decimal] = []
        for raw_value in raw_values:
            value = optional_decimal(raw_value)
            if value is None:
                raise ValueError(f"DCF engine requires finite {field} cells")
            values.append(value)
        vectors.append(values)
    if len(vectors[0]) != len(vectors[1]):
        raise ValueError("DCF engine cash-flow and present-value horizons must match")
    return vectors[0], vectors[1]


def five_year_projection_values(raw_values: object) -> list[Decimal]:
    """Legacy display preview only; never use to calculate or amend a valuation."""
    values: list[Decimal] = []
    if isinstance(raw_values, Sequence) and not isinstance(raw_values, (bytes, str)):
        for raw_value in raw_values[:5]:
            try:
                value = cast(Decimal, to_decimal(raw_value))
                values.append(value if value.is_finite() else Decimal("0.0"))
            except (ValueError, TypeError, ArithmeticError):
                values.append(Decimal("0.0"))
    return values + [Decimal("0.0")] * max(0, 5 - len(values))


def five_year_dcf_projection_vectors(
    dcf_result: object | None,
) -> tuple[list[Decimal], list[Decimal]]:
    """Extract API-ready 5-year FCF and PV-FCF vectors from a DCF engine result."""
    if dcf_result is None:
        return five_year_projection_values(None), five_year_projection_values(None)
    return (
        five_year_projection_values(getattr(dcf_result, "fcf_projections", None)),
        five_year_projection_values(getattr(dcf_result, "pv_fcf_projections", None)),
    )


def confidence_level_from_engine(raw_confidence: object) -> ConfidenceLevel:
    """Normalize engine confidence strings to the public ConfidenceLevel enum."""
    if isinstance(raw_confidence, str):
        try:
            return ConfidenceLevel(raw_confidence.lower())
        except (ValueError, AttributeError):
            return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.MEDIUM


def confidence_score_from_engine(raw_score: object) -> int:
    """Normalize engine confidence score to an integer percentage in the 0-100 range."""
    if raw_score is None:
        return 50
    try:
        score_decimal = to_decimal(raw_score)
    except (ValueError, TypeError):
        score = 50
    else:
        if Decimal("0") <= score_decimal <= Decimal("1"):
            score = int(score_decimal * Decimal("100"))
        else:
            score = int(score_decimal)
    return max(0, min(100, score))


def confidence_factors_from_engine(raw_factors: object) -> dict[str, str]:
    """Normalize engine confidence factors to the response schema's string map."""
    if raw_factors is None:
        return {}
    if isinstance(raw_factors, list):
        return {f"factor_{index + 1}": str(factor) for index, factor in enumerate(raw_factors)}
    if isinstance(raw_factors, Mapping):
        return {str(key): str(value) for key, value in raw_factors.items()}
    return {}


def build_dcf_audit_trail(transparency_collector: object) -> dict[str, object]:
    """Serialize transparency collector steps and sources for the DCF response payload."""
    collector_steps_raw = getattr(transparency_collector, "calculation_steps", [])
    collector_steps = (
        collector_steps_raw
        if isinstance(collector_steps_raw, Sequence)
        and not isinstance(collector_steps_raw, (bytes, str))
        else []
    )
    data_tracker = getattr(transparency_collector, "data_tracker")
    collector_sources_raw = data_tracker.get_sources()
    collector_sources = (
        collector_sources_raw
        if isinstance(collector_sources_raw, Sequence)
        and not isinstance(collector_sources_raw, (bytes, str))
        else []
    )

    return {
        "step_count": len(collector_steps),
        "source_count": len(collector_sources),
        "steps": [
            {
                "step_number": getattr(step, "step_number"),
                "description": getattr(step, "description"),
                "formula": getattr(step, "formula"),
                "explanation": getattr(step, "explanation"),
            }
            for step in collector_steps[:8]
        ],
        "sources": [
            {
                "name": getattr(source, "name"),
                "source": getattr(source, "source"),
                "confidence": from_decimal(getattr(source, "confidence")),
                "cache_status": getattr(source, "cache_status"),
            }
            for source in collector_sources[:8]
        ],
    }
