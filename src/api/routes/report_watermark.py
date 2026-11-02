"""PDF watermark and defensibility-banner injection helpers."""

from typing import Optional

from src.services.defensibility.banner import (
    DEFENSIBILITY_BANNER_INJECT_ANCHOR,
    defensibility_banner_div_count,
    strip_defensibility_banner_inject_anchor,
)

_WATERMARK_CSS = """
<style>
.upswitch-watermark-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  z-index: 9999;
  pointer-events: none;
}
.upswitch-watermark-overlay .wm-text {
  position: fixed;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%) rotate(-35deg);
  font-size: 54px;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  font-weight: 700;
  color: rgba(0, 0, 0, 0.06);
  white-space: nowrap;
  letter-spacing: 6px;
  text-transform: uppercase;
}
.upswitch-watermark-footer {
  position: fixed;
  bottom: 12px; left: 0; right: 0;
  text-align: center;
  font-size: 9px;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  color: rgba(0, 0, 0, 0.35);
  z-index: 9998;
  pointer-events: none;
}
.upswitch-defensibility-banner {
  display: block;
  margin: 0 0 14pt 0;
  padding: 10pt 14pt;
  background: hsl(35, 90%, 96%);
  border: 1pt solid hsl(35, 70%, 70%);
  border-left: 4pt solid hsl(35, 80%, 50%);
  border-radius: 4pt;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  page-break-inside: avoid;
}
.upswitch-defensibility-banner .ud-title {
  display: block;
  font-size: 9.5pt;
  font-weight: 700;
  color: hsl(35, 50%, 25%);
  text-transform: uppercase;
  letter-spacing: 0.5pt;
  margin-bottom: 4pt;
}
.upswitch-defensibility-banner .ud-body {
  display: block;
  font-size: 8.5pt;
  color: hsl(35, 50%, 30%);
  line-height: 1.5;
}
</style>
"""

_CSS_DEFENSIBILITY_BANNER_ONLY = """
<style>
.upswitch-defensibility-banner {
  display: block;
  margin: 0 0 14pt 0;
  padding: 10pt 14pt;
  background: hsl(35, 90%, 96%);
  border: 1pt solid hsl(35, 70%, 70%);
  border-left: 4pt solid hsl(35, 80%, 50%);
  border-radius: 4pt;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  page-break-inside: avoid;
}
.upswitch-defensibility-banner .ud-title {
  display: block;
  font-size: 9.5pt;
  font-weight: 700;
  color: hsl(35, 50%, 25%);
  text-transform: uppercase;
  letter-spacing: 0.5pt;
  margin-bottom: 4pt;
}
.upswitch-defensibility-banner .ud-body {
  display: block;
  font-size: 8.5pt;
  color: hsl(35, 50%, 30%);
  line-height: 1.5;
}
</style>
"""

_CSS_PLG_OVERLAY_FOOTER_ONLY = """
<style>
.upswitch-watermark-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  z-index: 9999;
  pointer-events: none;
}
.upswitch-watermark-overlay .wm-text {
  position: fixed;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%) rotate(-35deg);
  font-size: 54px;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  font-weight: 700;
  color: rgba(0, 0, 0, 0.06);
  white-space: nowrap;
  letter-spacing: 6px;
  text-transform: uppercase;
}
.upswitch-watermark-footer {
  position: fixed;
  bottom: 12px; left: 0; right: 0;
  text-align: center;
  font-size: 9px;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  color: rgba(0, 0, 0, 0.35);
  z-index: 9998;
  pointer-events: none;
}
</style>
"""


def _build_watermark_html(
    watermark_text: str = "Powered by Upswitch",
    footer_text: str = "This report was generated with Upswitch &mdash; upswitch.app",
) -> str:
    return (
        f'<div class="upswitch-watermark-overlay"><span class="wm-text">{watermark_text}</span></div>'
        f'<div class="upswitch-watermark-footer">{footer_text}</div>'
    )


def _inject_watermark(
    html: str,
    watermark_text: str = "Powered by Upswitch",
    footer_text: str = "This report was generated with Upswitch &mdash; upswitch.app",
    banner_html: Optional[str] = None,
    *,
    include_plg_overlay: bool = True,
) -> str:
    """Inject optional PLG diagonal watermark/footer and/or defensibility banner."""
    banner = (banner_html or "").strip()
    if banner and defensibility_banner_div_count(html) >= 1:
        banner = ""

    if not include_plg_overlay and not banner:
        return strip_defensibility_banner_inject_anchor(html)

    if banner and include_plg_overlay:
        css = _WATERMARK_CSS
    elif banner:
        css = _CSS_DEFENSIBILITY_BANNER_ONLY
    else:
        css = _CSS_PLG_OVERLAY_FOOTER_ONLY

    if "</head>" in html:
        html = html.replace("</head>", css + "</head>", 1)
    else:
        html = css + html

    if banner:
        if DEFENSIBILITY_BANNER_INJECT_ANCHOR in html:
            html = html.replace(DEFENSIBILITY_BANNER_INJECT_ANCHOR, banner, 1)
        else:
            close_body = "</body>"
            if close_body in html:
                html = html.replace(
                    close_body,
                    f'<div class="valuation-report">{banner}</div>' + close_body,
                    1,
                )
            else:
                html = html + banner

    if not include_plg_overlay:
        return strip_defensibility_banner_inject_anchor(html)

    overlay = _build_watermark_html(watermark_text, footer_text)
    close_body = "</body>"
    if close_body in html:
        return strip_defensibility_banner_inject_anchor(
            html.replace(close_body, overlay + close_body, 1)
        )
    return strip_defensibility_banner_inject_anchor(html + overlay)
