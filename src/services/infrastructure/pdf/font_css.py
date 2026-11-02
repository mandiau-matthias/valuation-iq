"""Render the original report layout using redistributable local typefaces."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# ``font_css.py`` lives at ``src/services/infrastructure/pdf/font_css.py``;
# parents[3] is ``src``.
_FONTS_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"

# (family, font-weight, font-style, filename, css-format)
_FONT_FACES: tuple[tuple[str, int, str, str, str], ...] = (
    ("Satoshi", 400, "normal", "NotoSans-Full-Regular.ttf", "truetype"),
    ("Satoshi", 500, "normal", "NotoSans-Full-Regular.ttf", "truetype"),
    ("Satoshi", 700, "normal", "NotoSans-Full-Bold.ttf", "truetype"),
    ("Satoshi", 900, "normal", "NotoSans-Full-Bold.ttf", "truetype"),
    # JetBrains Mono ships as one variable woff2; map the weights the report
    # uses (400/500/700) onto it so WeasyPrint picks consistent instances.
    ("JetBrains Mono", 400, "normal", "JetBrainsMono.woff2", "woff2"),
    ("JetBrains Mono", 500, "normal", "JetBrainsMono.woff2", "woff2"),
    ("JetBrains Mono", 700, "normal", "JetBrainsMono.woff2", "woff2"),
    # Full static Noto Sans (Latin+Greek+Cyrillic) so the fallback covers every
    # glyph the reports use — including Greek Δ/Σ that the Latin subset lacked.
    ("Noto Sans", 400, "normal", "NotoSans-Full-Regular.ttf", "truetype"),
    ("Noto Sans", 700, "normal", "NotoSans-Full-Bold.ttf", "truetype"),
    # Monochrome symbols (★ ⚠ ✗ and other dingbats/misc-symbols) used in
    # callouts and rating ledgers. Bundled so they embed as deterministic text
    # glyphs instead of leaking to a host symbol/colour-emoji font. One weight;
    # WeasyPrint synthesises bold.
    ("Noto Sans Symbols 2", 400, "normal", "NotoSansSymbols2-Regular.ttf", "truetype"),
    ("Noto Sans Symbols 2", 700, "normal", "NotoSansSymbols2-Regular.ttf", "truetype"),
)


@lru_cache(maxsize=1)
def get_pdf_font_face_css() -> str:
    """Return the ``@font-face`` block for the bundled PDF fonts.

    Cached for the process lifetime. Raises ``FileNotFoundError`` at first use
    if a bundled font is missing, so a broken deploy fails loudly instead of
    silently rendering with host fonts.
    """
    blocks: list[str] = []
    for family, weight, style, filename, css_format in _FONT_FACES:
        font_path = _FONTS_DIR / filename
        if not font_path.is_file():
            raise FileNotFoundError(
                f"Bundled PDF font missing: {font_path}. "
                "Report fonts must be present for deterministic rendering."
            )
        url = font_path.as_uri()
        blocks.append(
            "@font-face {\n"
            f"    font-family: '{family}';\n"
            f"    font-style: {style};\n"
            f"    font-weight: {weight};\n"
            "    font-display: swap;\n"
            f"    src: url('{url}') format('{css_format}');\n"
            "}"
        )
    return "\n".join(blocks)
