"""Normalize ISO 3166-1 alpha-2 country codes for valuation APIs (aligned with Titan default BE)."""

from __future__ import annotations

from typing import Optional

DEFAULT_VALUATION_COUNTRY = "BE"


def normalize_iso3166_alpha2(
    country_code: Optional[str],
    default: str = DEFAULT_VALUATION_COUNTRY,
) -> str:
    """
    Return a 2-letter uppercase code, or ``default`` if missing/invalid.

    Rejects empty input, single characters, and non-alphabetic pairs (e.g. ``"12"``).
    Longer strings use the first two letters only if both are A–Z (e.g. ``"nld"`` → ``"NL"`` is wrong;
    ``"NL"`` / ``"nl"`` → ``"NL"``).
    """
    if not country_code or not str(country_code).strip():
        return default
    s = str(country_code).strip().upper()
    if len(s) < 2:
        return default
    pair = s[:2]
    if not (pair[0].isalpha() and pair[1].isalpha()):
        return default
    return pair
