"""Validation helpers for legacy valuation API schemas."""

import logging
import math
import re
from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Optional, cast

from src.api.historical_ebitda_weights import normalize_historical_ebitda_weights
from src.api.legacy_industry_validation import get_valid_industries
from src.domain.asset_based_support import normalize_business_model
from src.domain.models import BusinessModel
from src.utils.fiscal_year import get_max_confirmable_year

logger = logging.getLogger(__name__)
_MULTIPLE_DISTRIBUTION_KEYS = ("median", "p10", "p25", "p75", "p90")


def sanitize_industry(industry: str) -> str:
    """
    Sanitize industry string input.

    Args:
        industry: Raw industry string

    Returns:
        Sanitized industry string
    """
    if not industry:
        return ""

    sanitized = industry.strip().lower()
    return re.sub(r"[^a-z0-9\-_]", "", sanitized)


def validate_industry_field(industry: str) -> str:
    """
    Validate industry field with graceful degradation.

    NOTE: With the new architecture, industry should come from the business_types
    database (enriched by Titan). We now accept any well-formed industry string
    and only log warnings for unknown values - we NEVER reject.
    """
    logger.debug("[INDUSTRY-VALIDATION] Input: '%s'", industry)
    sanitized = sanitize_industry(industry)

    if not sanitized:
        logger.warning(
            "[INDUSTRY-VALIDATION] Industry empty after sanitization: '%s', using 'other'",
            industry,
        )
        return "other"

    if len(sanitized) < 2:
        logger.warning(
            "[INDUSTRY-VALIDATION] Industry too short: '%s', using 'other'",
            sanitized,
        )
        return "other"

    if len(sanitized) > 100:
        sanitized = sanitized[:100]
        logger.warning("[INDUSTRY-VALIDATION] Industry truncated to 100 chars")

    valid_industries = get_valid_industries()
    if sanitized not in valid_industries:
        logger.info(
            "[INDUSTRY-VALIDATION] Industry '%s' not in cached list "
            "(list has %s entries) - accepting as DB-sourced",
            sanitized,
            len(valid_industries),
        )
    else:
        logger.debug("[INDUSTRY-VALIDATION] Industry '%s' validated", sanitized)

    return sanitized


def _finite_distribution_float(dist: dict[object, object], key: str) -> Optional[float]:
    value = dist.get(key)
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _round_multiple(value: float) -> float:
    return round(value + 1e-9, 2)


def _clean_invalid_median_distribution(dist: dict[object, object]) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for key in _MULTIPLE_DISTRIBUTION_KEYS:
        value = _finite_distribution_float(dist, key)
        if key == "median":
            if value is not None and value > 0:
                cleaned[key] = _round_multiple(value)
        elif value is not None:
            cleaned[key] = _round_multiple(value)

    passthrough = {k: v for k, v in dist.items() if k not in _MULTIPLE_DISTRIBUTION_KEYS}
    passthrough.update(cleaned)
    return passthrough


def _ordered_percentiles(
    *,
    med: float,
    p10: Optional[float],
    p25: Optional[float],
    p75: Optional[float],
    p90: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    if p25 is not None:
        p25 = min(p25, med)
    if p10 is not None:
        p10 = min(p10, p25 if p25 is not None else med)
    if p10 is not None and p25 is not None:
        lo, hi = min(p10, p25), max(p10, p25)
        p10, p25 = lo, hi
    if p75 is not None:
        p75 = max(p75, med)
    if p90 is not None:
        p90 = max(p90, p75 if p75 is not None else med)
    if p75 is not None and p90 is not None:
        lo, hi = min(p75, p90), max(p75, p90)
        p75, p90 = lo, hi
    return p10, p25, p75, p90


def _rounded_ordered_percentiles(
    *,
    med: float,
    p10: Optional[float],
    p25: Optional[float],
    p75: Optional[float],
    p90: Optional[float],
) -> tuple[float, Optional[float], Optional[float], Optional[float], Optional[float]]:
    p10, p25, p75, p90 = _ordered_percentiles(
        med=med,
        p10=p10,
        p25=p25,
        p75=p75,
        p90=p90,
    )
    med_r = _round_multiple(med)
    p10_r = _round_multiple(p10) if p10 is not None else None
    p25_r = _round_multiple(p25) if p25 is not None else None
    p75_r = _round_multiple(p75) if p75 is not None else None
    p90_r = _round_multiple(p90) if p90 is not None else None
    p10_r, p25_r, p75_r, p90_r = _ordered_percentiles(
        med=med_r,
        p10=p10_r,
        p25=p25_r,
        p75=p75_r,
        p90=p90_r,
    )
    return med_r, p10_r, p25_r, p75_r, p90_r


def _normalize_multiple_distribution_dict(dist: object) -> object:
    """
    Enforce p10 <= p25 <= median <= p75 <= p90 for Titan enrichment dicts.

    DB/Damodaran data can be inconsistent; this mirrors Titan's
    normalizeEvMultipleDistribution and coerces numeric strings.
    """
    if dist is None:
        return None
    if not isinstance(dist, dict):
        return dist

    med = _finite_distribution_float(dist, "median")
    if med is None or med <= 0:
        return _clean_invalid_median_distribution(dist)

    med_r, p10x, p25x, p75x, p90x = _rounded_ordered_percentiles(
        med=med,
        p10=_finite_distribution_float(dist, "p10"),
        p25=_finite_distribution_float(dist, "p25"),
        p75=_finite_distribution_float(dist, "p75"),
        p90=_finite_distribution_float(dist, "p90"),
    )
    out: dict[str, object] = {**dist, "median": med_r}
    if p10x is not None:
        out["p10"] = p10x
    if p25x is not None:
        out["p25"] = p25x
    if p75x is not None:
        out["p75"] = p75x
    if p90x is not None:
        out["p90"] = p90x
    return out


def normalize_key_metrics_field(value: object) -> Optional[dict[str, object]]:
    """Accept Titan key metrics as dicts or lists and normalize to a dict."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {str(metric): True for metric in value if metric}
    try:
        return dict(cast(Iterable[tuple[object, object]], value)) if value else None
    except (TypeError, ValueError):
        return {"raw_value": str(value)} if value else None


def normalize_real_estate_treatment_field(value: object) -> Optional[str]:
    if value is None or value == "":
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "none": "none",
        "geen": "none",
        "geen_vastgoed": "none",
        "no_real_estate": "none",
        "carve_out": "carve_out",
        "vastgoed_carve_out": "carve_out",
        "exclude": "carve_out",
        "excluded": "carve_out",
        "included": "included",
        "include": "included",
        "vastgoed_inclusief": "included",
        "real_estate_included": "included",
        "owned_included": "owned_included",
        "owned_excluded": "owned_excluded",
        "leased": "leased",
        "unresolved": "unresolved",
    }
    if normalized not in aliases:
        raise ValueError(
            "real_estate_treatment must be one of: none, carve_out, included, "
            "owned_included, owned_excluded, leased, unresolved"
        )
    return aliases[normalized]


def normalize_historical_ebitda_weighting_mode_field(value: object) -> str:
    if value is None or value == "":
        return "standard"
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "standard": "standard",
        "standaard": "standard",
        "standard_average": "standard",
        "weighted": "weighted",
        "gewogen": "weighted",
        "weighted_average": "weighted",
    }
    if normalized not in aliases:
        raise ValueError("historical_ebitda_weighting_mode must be 'standard' or 'weighted'")
    return aliases[normalized]


def normalize_historical_ebitda_weights_field(value: object) -> Optional[dict[int, Decimal]]:
    return normalize_historical_ebitda_weights(value)


def normalize_business_model_field(value: object) -> BusinessModel:
    """Convert legacy string values to the canonical business model enum."""
    if isinstance(value, BusinessModel):
        return value
    if not value:
        return BusinessModel.SERVICES
    if isinstance(value, str):
        return normalize_business_model(value)
    raise ValueError(
        f"Invalid business_model value: {value}. Must be a string or BusinessModel enum."
    )


def validate_historical_years_order(value: object) -> object:
    if isinstance(value, list) and len(value) > 1:
        years = [year.year for year in value]
        if years != sorted(years):
            raise ValueError("Historical years must be in chronological order")
    return value


def validate_year_buckets_request(request: object) -> object:
    max_confirmable_year = get_max_confirmable_year()
    current_year_data = getattr(request, "current_year_data")
    if current_year_data.year > max_confirmable_year:
        raise ValueError(
            f"current_year_data.year ({current_year_data.year}) cannot be later than the previous calendar year ({max_confirmable_year})"
        )

    current_year = current_year_data.year

    for year_data in getattr(request, "historical_years_data"):
        if year_data.year >= current_year:
            raise ValueError(
                f"Historical year {year_data.year} must be earlier than current_year_data.year ({current_year})"
            )

    for year_data in getattr(request, "forecast_years_data"):
        if year_data.year <= current_year:
            raise ValueError(
                f"Forecast year {year_data.year} must be later than current_year_data.year ({current_year})"
            )

    return request


def _resolved_real_estate_treatment(request: object) -> object:
    treatment = getattr(request, "real_estate_treatment")
    if treatment is None and getattr(request, "exclude_real_estate"):
        return "carve_out"
    return treatment


def _validate_real_estate_inclusion(request: object, treatment: object) -> None:
    if treatment in {"included", "owned_included"}:
        if getattr(request, "real_estate_market_value") is None:
            raise ValueError(
                "real_estate_market_value is required when real_estate_treatment='included'"
            )
        if getattr(request, "real_estate_book_value") is None:
            raise ValueError(
                "real_estate_book_value is required when real_estate_treatment='included'"
            )


def _is_nonzero_decimal(value: object) -> bool:
    return (value or Decimal("0")) != Decimal("0")


def _has_note(value: object) -> bool:
    return bool((value or "").strip())


def _validate_multiple_calibration_note(request: object) -> None:
    adjustment = getattr(request, "multiple_calibration_adjustment") or Decimal("0")
    if _is_nonzero_decimal(adjustment) and not _has_note(
        getattr(request, "multiple_calibration_note")
    ):
        raise ValueError(
            "multiple_calibration_note is required when multiple_calibration_adjustment is non-zero"
        )


def _validate_effective_multiple_override_note(request: object) -> None:
    if getattr(request, "effective_multiple_override", None) is not None and not _has_note(
        getattr(request, "effective_multiple_override_note", None)
    ):
        raise ValueError(
            "effective_multiple_override_note is required when effective_multiple_override is set"
        )


def _validate_weighted_historical_ebitda_shape(
    request: object,
    weights: object,
) -> None:
    if getattr(request, "historical_ebitda_weighting_mode") == "weighted":
        if not weights:
            raise ValueError(
                "historical_ebitda_weights are required when historical_ebitda_weighting_mode='weighted'"
            )
        if not (3 <= len(weights) <= 5):
            raise ValueError("historical_ebitda_weights must contain 3 to 5 fiscal years")


def _validate_historical_ebitda_weight_sum(weights: object) -> None:
    if not weights:
        return

    if not isinstance(weights, Mapping):
        raise ValueError("historical_ebitda_weights must be a mapping of fiscal year weights")

    total = sum((Decimal(str(weight)) for weight in weights.values()), Decimal("0"))
    if not (
        abs(total - Decimal("1")) <= Decimal("0.02") or abs(total - Decimal("100")) <= Decimal("2")
    ):
        raise ValueError("historical_ebitda_weights must sum to 1.0 or 100")


def validate_advisor_controls_request(request: object) -> object:
    treatment = _resolved_real_estate_treatment(request)
    _validate_real_estate_inclusion(request, treatment)
    _validate_multiple_calibration_note(request)
    _validate_effective_multiple_override_note(request)

    weights = getattr(request, "historical_ebitda_weights")
    _validate_weighted_historical_ebitda_shape(request, weights)
    _validate_historical_ebitda_weight_sum(weights)

    return request


def normalize_enrichment_multiple_distributions_request(request: object) -> object:
    """Normalize Titan-supplied multiple distribution dicts in place."""
    if getattr(request, "ev_ebitda_multiple") and isinstance(
        getattr(request, "ev_ebitda_multiple"), dict
    ):
        setattr(
            request,
            "ev_ebitda_multiple",
            _normalize_multiple_distribution_dict(getattr(request, "ev_ebitda_multiple")),
        )
    if getattr(request, "ev_revenue_multiple") and isinstance(
        getattr(request, "ev_revenue_multiple"), dict
    ):
        setattr(
            request,
            "ev_revenue_multiple",
            _normalize_multiple_distribution_dict(getattr(request, "ev_revenue_multiple")),
        )
    if getattr(request, "pe_ratio") and isinstance(getattr(request, "pe_ratio"), dict):
        setattr(
            request, "pe_ratio", _normalize_multiple_distribution_dict(getattr(request, "pe_ratio"))
        )
    return request
