"""Shared helpers for startup report context assembly."""

from __future__ import annotations

from decimal import Decimal

from src.utils.decimal_helpers import pin_band_monotone as _pin_decimal_band

FormatValue = str | int | float | Decimal | None
JsonMap = dict[str, object]
JsonRows = list[JsonMap]


def pin_float_band(low: float, mid: float, high: float) -> tuple[float, float, float]:
    """Float wrapper around ``pin_band_monotone`` for startup report ranges."""
    low_decimal = Decimal(str(low)) if low and low > 0 else Decimal("0")
    mid_decimal = Decimal(str(mid)) if mid and mid > 0 else Decimal("0")
    high_decimal = Decimal(str(high)) if high and high > 0 else Decimal("0")
    pinned_low, pinned_mid, pinned_high = _pin_decimal_band(
        low_decimal,
        mid_decimal,
        high_decimal,
    )
    return (float(pinned_low), float(pinned_mid), float(pinned_high))


def format_eur_digits(value: FormatValue, loc: str) -> str:
    """Locale-aware EUR digits-only formatter without the currency symbol."""
    try:
        from src.services.infrastructure.template_formatter import TemplateFormatter
    except ImportError:  # pragma: no cover - defensive import for partial trees
        try:
            return f"{float(value):,.0f}"
        except (TypeError, ValueError):
            return "—"
    return TemplateFormatter.format_eur_amount(value, locale=loc)


def format_eur(value: FormatValue, loc: str) -> str:
    """Locale-aware EUR renderer with the currency symbol."""
    digits = format_eur_digits(value, loc)
    if digits == "—":
        return digits
    return f"€{digits}"


def safe_get(obj: object, key: str, default: object = None) -> object:
    """Read a key or attribute from mixed dict/model inputs."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def coerce_dict(obj: object) -> dict[str, object]:
    """Return a plain dict from dict-like report bridge objects."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj

    # DictWrapper (main_report_data_aggregator) exposes missing attributes as
    # None, so prefer its underlying dict before probing model_dump.
    underlying = getattr(obj, "_data", None)
    if isinstance(underlying, dict):
        return underlying

    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    return {}


def safe_float(value: FormatValue) -> float | None:
    """Return ``float(value)`` or ``None`` for non-numeric / missing input."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_startup_method(valuation_results: object) -> dict[str, object] | None:
    """Return the ``startup_valuation`` MethodResult as a plain dict."""
    if not valuation_results:
        return None
    candidate = None
    if isinstance(valuation_results, dict):
        candidate = valuation_results.get("startup_valuation")
    else:
        candidate = getattr(valuation_results, "startup_valuation", None) or getattr(
            valuation_results,
            "get",
            lambda *_: None,
        )("startup_valuation")
    if candidate is None:
        return None
    return coerce_dict(candidate)
