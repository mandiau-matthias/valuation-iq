"""Report accent-color derivation utilities."""

from __future__ import annotations

import re
from typing import Optional, Tuple


_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _hex_to_hsl_components(hex_color: str) -> Optional[Tuple[int, int, int]]:
    """Convert '#RRGGBB' to (H, S%, L%) integers."""
    if not hex_color or not _HEX_COLOR_RE.match(hex_color):
        return None
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    lightness = (mx + mn) / 2.0
    if mx == mn:
        hue = saturation = 0.0
    else:
        delta = mx - mn
        saturation = (
            delta / (2.0 - mx - mn)
            if lightness > 0.5
            else delta / (mx + mn)
        )
        if mx == r:
            hue = (g - b) / delta + (6.0 if g < b else 0.0)
        elif mx == g:
            hue = (b - r) / delta + 2.0
        else:
            hue = (r - g) / delta + 4.0
        hue /= 6.0
    return (round(hue * 360), round(saturation * 100), round(lightness * 100))


def hex_color_variants(hex_color: str) -> Optional[dict]:
    """Derive HSL strings used by report templates from a brand hex color."""
    parts = _hex_to_hsl_components(hex_color)
    if not parts:
        return None
    hue, saturation, lightness = parts
    saturation = max(saturation, 20) if saturation < 15 else saturation
    lightness = (
        min(lightness, 50)
        if lightness > 55
        else max(lightness, 30)
        if lightness < 25
        else lightness
    )
    return {
        "hsl": f"{hue}, {saturation}%, {lightness}%",
        "hsl_light": f"{hue}, {max(saturation - 10, 0)}%, 92%",
        "hsl_dark": (
            f"{hue}, {min(saturation + 5, 100)}%, {max(lightness - 13, 18)}%"
        ),
    }


def build_color_context(hex_color: Optional[str]) -> dict:
    """Build report template variables for a single custom primary color."""
    variants = hex_color_variants(hex_color or "")
    if not variants:
        return {
            "primary_color_hsl": None,
            "primary_color_hsl_light": None,
            "primary_color_hsl_dark": None,
        }
    return {
        "primary_color_hsl": variants["hsl"],
        "primary_color_hsl_light": variants["hsl_light"],
        "primary_color_hsl_dark": variants["hsl_dark"],
    }
