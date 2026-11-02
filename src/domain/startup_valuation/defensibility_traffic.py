"""Defensibility-score traffic-light design tokens — Jinja side.

Canonical source for the ``traffic_light`` → HSL mapping used by the
defensibility-score chip on the startup report (cover, one-pager,
executive summary).  Mirrors the pattern set by
``src/domain/owner_profiling_bands.py``.

Why a module instead of inline HSL?
    Before this helper, three startup pages each inlined their own
    HSL triple for the green/yellow/red traffic-light chip:

        main_report/pages/startup_one_pager.html
        main_report/pages/startup_executive_summary.html
        main_report_pdf/pages/startup_executive_summary.html
        main_report_pdf/pages/startup_one_pager.html

    A palette tune in one would silently drift from the others. The
    audit (2026-05-10, issue #17) flagged the duplication. Centralising
    the colours here lets every template render the chip via a single
    Jinja global (``defensibility_traffic_bg`` / ``_fg``).

Engine source-of-truth for the ``traffic_light`` value:
    apps/valuation-iq/src/domain/startup_valuation/defensibility.py
"""

from __future__ import annotations

from typing import Dict, Literal

DefensibilityTraffic = Literal["green", "yellow", "red"]


# HSL triples (no `hsl(` wrapper). Two strips: one for the chip
# *background*, one for the chip *foreground* (text). Picked to keep
# WCAG AA contrast against the background tone.
DEFENSIBILITY_TRAFFIC_HSL_BG: Dict[str, str] = {
    "green": "160, 60%, 92%",
    "yellow": "45, 95%, 92%",
    "red": "355, 75%, 93%",
}

DEFENSIBILITY_TRAFFIC_HSL_FG: Dict[str, str] = {
    "green": "160, 60%, 28%",
    "yellow": "35, 75%, 32%",
    "red": "355, 70%, 38%",
}


def _resolve_traffic(traffic: str | None) -> str:
    """Coerce any traffic-light input to a known key.

    The engine emits one of {``green``, ``yellow``, ``red``}; defensive
    callers can pass ``None`` (or ``""``) and we default to ``yellow``
    — same fallback the templates used inline before this module.
    """
    if not traffic:
        return "yellow"
    key = str(traffic).strip().lower()
    return key if key in DEFENSIBILITY_TRAFFIC_HSL_BG else "yellow"


def defensibility_traffic_bg(traffic: str | None) -> str:
    """``hsl(<triple>)`` for the chip background.

    Used as a Jinja global so templates write
    ``{{ defensibility_traffic_bg(defs.traffic_light) }}`` instead of
    inlining HSL.
    """
    return f"hsl({DEFENSIBILITY_TRAFFIC_HSL_BG[_resolve_traffic(traffic)]})"


def defensibility_traffic_fg(traffic: str | None) -> str:
    """``hsl(<triple>)`` for the chip foreground (text)."""
    return f"hsl({DEFENSIBILITY_TRAFFIC_HSL_FG[_resolve_traffic(traffic)]})"


# Solid-hex PDF mirrors of the screen tinted-bg + dark-fg pattern.
# WeasyPrint renders alpha-blended HSL inconsistently in tight chip
# contexts, so we ship solid hex.  Values approximate the screen chip
# rendered against a white card, so the same letter grade reads the
# same intensity on screen and in the printed PDF.  Audit issue D10 —
# previously the PDF used full-saturation white-on-coloured pills,
# which felt loud next to the softer screen tones for the same data.
DEFENSIBILITY_TRAFFIC_PDF_BG: Dict[str, str] = {
    "green": "#dbf2ee",
    "yellow": "#fdf3d3",
    "red": "#fadcdb",
}

DEFENSIBILITY_TRAFFIC_PDF_FG: Dict[str, str] = {
    "green": "#1d7268",
    "yellow": "#8f5614",
    "red": "#a52a30",
}


def defensibility_traffic_pdf_bg(traffic: str | None) -> str:
    """Solid-fill background for the PDF chip (no HSL)."""
    return DEFENSIBILITY_TRAFFIC_PDF_BG[_resolve_traffic(traffic)]


def defensibility_traffic_pdf_fg(traffic: str | None) -> str:
    """Solid-fill foreground (text) for the PDF chip (no HSL).

    Pairs with :func:`defensibility_traffic_pdf_bg` to render the
    tinted-with-dark-text pattern the screen chip uses.
    """
    return DEFENSIBILITY_TRAFFIC_PDF_FG[_resolve_traffic(traffic)]
