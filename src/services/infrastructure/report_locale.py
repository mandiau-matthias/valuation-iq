"""Locale policy for report rendering.

This module is intentionally tiny and strict-island eligible. The large
``translations`` catalog re-exports these names for compatibility, but new code
should import locale policy from here instead of coupling to translation data.
"""

from typing import Literal

Locale = Literal["nl", "en", "fr"]


def normalize_report_locale(locale: str | None) -> Locale:
    """Map raw locale tags to ``en``, ``fr`` or ``nl``.

    BCP-47 tags such as ``en-US`` / ``fr-BE`` select English / French. All other
    tags fall back to Dutch, matching the product's default report audience.
    """

    raw = str(locale if locale is not None else "nl").strip()
    if not raw:
        raw = "nl"
    lowered = raw.lower()
    if lowered.startswith("en"):
        return "en"
    if lowered.startswith("fr"):
        return "fr"
    return "nl"
