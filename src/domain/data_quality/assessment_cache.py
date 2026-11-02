"""
Per-process cache for DataQualityAssessor results.

The cache is keyed by request identity, baseline score, and a compact financial
fingerprint to avoid stale hits when Python reuses object ids after GC.
"""

from collections import OrderedDict
from decimal import Decimal
from threading import Lock
from typing import Optional

ASSESSMENT_CACHE_MAX = 32
AssessmentCacheKey = tuple[int, Optional[int], tuple[object, ...]]

_assessment_cache: "OrderedDict[AssessmentCacheKey, dict[str, object]]" = OrderedDict()
_assessment_cache_lock = Lock()


def assessment_cache_get(key: AssessmentCacheKey) -> Optional[dict[str, object]]:
    with _assessment_cache_lock:
        value = _assessment_cache.get(key)
        if value is not None:
            _assessment_cache.move_to_end(key)
        return value


def assessment_cache_put(key: AssessmentCacheKey, value: dict[str, object]) -> None:
    with _assessment_cache_lock:
        _assessment_cache[key] = value
        _assessment_cache.move_to_end(key)
        while len(_assessment_cache) > ASSESSMENT_CACHE_MAX:
            _assessment_cache.popitem(last=False)


def _cache_scalar(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, Decimal, bool)):
        return str(value)
    return repr(value)


def _year_signature(year_data: object) -> tuple[object, object, object, object]:
    return (
        _cache_scalar(getattr(year_data, "year", None)),
        _cache_scalar(getattr(year_data, "revenue", None)),
        _cache_scalar(getattr(year_data, "ebitda", None)),
        _cache_scalar(getattr(year_data, "is_forecast", None)),
    )


def _historical_signature(request: object) -> tuple[object, ...]:
    historical_years = getattr(request, "historical_years_data", None)
    if historical_years is None:
        historical_years = getattr(request, "historical_years", None)
    if not isinstance(historical_years, (list, tuple)):
        return (_cache_scalar(historical_years),)
    return tuple(_year_signature(year_data) for year_data in historical_years)


def assessment_cache_key(request: object, baseline_score: Optional[int]) -> AssessmentCacheKey:
    current_year_data = getattr(request, "current_year_data", None)
    fingerprint = (
        _cache_scalar(getattr(current_year_data, "revenue", None)),
        _cache_scalar(getattr(current_year_data, "ebitda", None)),
        _cache_scalar(getattr(current_year_data, "total_assets", None)),
        _cache_scalar(getattr(current_year_data, "cash", None)),
        _cache_scalar(getattr(current_year_data, "total_debt", None)),
        _historical_signature(request),
    )
    return (id(request), baseline_score, fingerprint)
