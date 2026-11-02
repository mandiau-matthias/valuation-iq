"""Owner-profiling cover-page context helpers."""

import math
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Protocol, TypeAlias, runtime_checkable

from src.utils.logging import get_logger

logger = get_logger(__name__)

ReportMap: TypeAlias = dict[str, object]


class CoverTranslations(Protocol):
    cover_owner_profiling_summary: str
    owner_profiling_severity_tier_label: str


@runtime_checkable
class ModelDumpLike(Protocol):
    def model_dump(self) -> object: ...


_SEVERITY_T_KEYS: dict[str, str] = {
    "minimal": "owner_profiling_severity_minimal",
    "moderate": "owner_profiling_severity_moderate",
    "severe": "owner_profiling_severity_severe",
    "extreme": "owner_profiling_severity_extreme",
}

_SEVERITY_BANDS = {
    "minimal": "good",
    "moderate": "caution",
    "severe": "warn",
    "extreme": "warn",
}


def build_cover_owner_profiling_cover(
    response: object | None,
    t: CoverTranslations,
    step_data: ReportMap,
) -> ReportMap:
    """Cover-page owner-profiling disclosure.

    Returns the same template keys the aggregator historically emitted.
    """
    if response is None:
        return _empty_cover_owner_profiling_context()

    odr = _owner_dependency_result(response)
    adj_raw = getattr(response, "owner_dependency_adjustment", None)
    if odr is None or adj_raw is None:
        return _empty_cover_owner_profiling_context()

    overall_b = _bounded_owner_dependency_score(odr)
    pct_num = _owner_dependency_adjustment_percent(adj_raw)
    risk_display = _owner_dependency_risk_display(odr, step_data)
    if overall_b is None or pct_num is None or not risk_display:
        return _empty_cover_owner_profiling_context()

    tri = int(round(100.0 - overall_b))
    tri = max(0, min(100, tri))
    text = _cover_owner_profiling_text(
        t,
        tri=tri,
        risk_display=risk_display,
        adjustment_percent=pct_num,
    )
    if text is None:
        return _empty_cover_owner_profiling_context()

    return {
        "show_cover_owner_profiling": True,
        "cover_owner_profiling_text": text,
        "cover_owner_profiling_band": _cover_owner_profiling_band(risk_display),
        "cover_owner_profiling_v2": build_cover_v2_chip_context(odr, t),
    }


def _empty_cover_owner_profiling_context() -> ReportMap:
    return {
        "show_cover_owner_profiling": False,
        "cover_owner_profiling_text": None,
        "cover_owner_profiling_band": None,
    }


def _owner_dependency_result(response: object) -> object | None:
    odr = getattr(response, "owner_dependency_result", None)
    if odr is None or isinstance(odr, (list, tuple, str, bytes)):
        return None
    return odr


def _owner_dependency_result_value(odr: object, key: str) -> object:
    return odr.get(key) if isinstance(odr, Mapping) else getattr(odr, key, None)


def _finite_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _bounded_owner_dependency_score(odr: object) -> float | None:
    overall = _finite_float(_owner_dependency_result_value(odr, "overall_score"))
    if overall is None:
        return None
    return max(0.0, min(100.0, overall))


def _owner_dependency_adjustment_percent(adj_raw: object) -> float | None:
    try:
        adjustment = Decimal(str(adj_raw))
    except (InvalidOperation, TypeError, ValueError, ArithmeticError):
        return None
    return _finite_float(adjustment * Decimal("100"))


def _owner_dependency_risk_display(odr: object, step_data: ReportMap) -> str:
    raw_rl = _owner_dependency_result_value(odr, "risk_level")
    if raw_rl is None:
        raw_rl = step_data.get("owner_dependency_risk_level")
    return str(raw_rl).strip() if raw_rl is not None else ""


def _cover_owner_profiling_text(
    t: CoverTranslations,
    *,
    tri: int,
    risk_display: str,
    adjustment_percent: float,
) -> str | None:
    try:
        return t.cover_owner_profiling_summary.format(
            tri=tri,
            risk_level=risk_display,
            adj_pct=f"{adjustment_percent:.0f}",
        )
    except (KeyError, ValueError, TypeError):
        logger.warning("[OWNER-PROFILING] cover summary format failed - suppressing chip")
        return None


def _cover_owner_profiling_band(risk_display: str) -> str:
    risk_level_upper = risk_display.upper()
    if risk_level_upper == "MINIMAL":
        return "good"
    if risk_level_upper in ("LOW", "MEDIUM"):
        return "neutral"
    if risk_level_upper == "HIGH":
        return "caution"
    if risk_level_upper == "CRITICAL":
        return "warn"
    return "neutral"


def build_cover_v2_chip_context(odr: object, t: CoverTranslations) -> ReportMap | None:
    """Tiny v2 metadata bundle for the cover chip: severity tier only."""
    tp_map = _transferability_profile_map(odr)
    if tp_map is None:
        return None

    gap_raw = tp_map.get("gap") or {}
    gap = gap_raw if isinstance(gap_raw, Mapping) else {}
    severity = gap.get("severity") or "minimal"
    sev_tier = int(gap.get("severity_tier") or 1)

    return {
        "severity_label": _severity_label(t, severity),
        "severity_tier_label": _severity_tier_label(t, sev_tier),
        "severity_band": _severity_band(severity),
    }


def _transferability_profile_map(odr: object) -> Mapping[str, object] | None:
    if odr is None:
        return None
    if isinstance(odr, Mapping):
        profile = odr.get("transferability_profile")
    else:
        profile = getattr(odr, "transferability_profile", None)
    if isinstance(profile, Mapping):
        return profile
    if not isinstance(profile, ModelDumpLike):
        return None
    dumped = profile.model_dump()
    return dumped if isinstance(dumped, Mapping) else None


def _severity_label(t: CoverTranslations, severity: object) -> str:
    severity_key = str(severity).lower()
    translation_key = _SEVERITY_T_KEYS.get(severity_key)
    localized = getattr(t, translation_key, None) if translation_key else None
    return str(localized or str(severity).capitalize())


def _severity_band(severity: object) -> str:
    return _SEVERITY_BANDS.get(str(severity).lower(), "neutral")


def _severity_tier_label(t: CoverTranslations, severity_tier: int) -> str:
    try:
        return t.owner_profiling_severity_tier_label.format(tier=severity_tier)
    except (KeyError, ValueError, TypeError):
        return f"Tier {severity_tier} / 4"
