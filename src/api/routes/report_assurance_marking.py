"""Place release disclosures in PDF page margins and on the cover."""

import re


def _inject_advisor_assurance_marking(
    html: str,
    *,
    locale: str,
    assurance_level: str,
    superseded: bool,
) -> str:
    """Put the advisor release state inside the bytes that become the PDF.

    Titan may request a five-minute download URL, but access controls do not
    survive once a customer shares the downloaded file. The artifact therefore
    carries its own fail-closed release state. Unknown/missing levels are
    treated as indicative.
    """

    lang = str(locale or "nl").lower()[:2]
    if superseded:
        messages = {
            "nl": "VERVANGEN RAPPORT — AUDITKOPIE; NIET ALS ACTUEEL DELEN",
            "en": "SUPERSEDED REPORT — AUDIT COPY; DO NOT SHARE AS CURRENT",
            "fr": "RAPPORT REMPLACÉ — COPIE D’AUDIT; NE PAS PARTAGER COMME ACTUEL",
        }
        message = messages.get(lang, messages["en"])
        border = "#991B1B"
        background = "#FFF1F2"
    elif assurance_level == "advisor_approved":
        return html
    elif 'data-report-release-note="indicative"' in html:
        # Our template already carries a visible cover disclosure and page
        # footers. Keep one treatment; generic/safety-net HTML still fails closed.
        return html
    else:
        messages = {
            "nl": "INDICATIEVE WAARDERING",
            "en": "INDICATIVE VALUATION",
            "fr": "VALORISATION INDICATIVE",
        }
        message = messages.get(lang, messages["en"])
        border = "#365F60"
        background = "#F0F7F6"

    # Page margin boxes repeat without covering report headings. The absolute
    # cover copy remains visible on the first page, which has zero margins.
    disclosure = f"""
    <style>
      @page {{ @top-right {{ content: "{message}"; color:{border};
        font:700 7px/1.25 Arial,sans-serif; letter-spacing:.04em;
        vertical-align:middle; }} }}
      @page :first {{ @top-right {{ content:none; }} }}
      @page cover {{ @top-right {{ content:none; }} }}
    </style>
    <div data-advisor-assurance="{'superseded' if superseded else 'indicative'}"
      style="position:absolute;z-index:2147483646;top:4mm;right:5mm;max-width:82mm;
      padding:3px 6px;border:1px solid {border};background:{background};color:{border};
      text-align:center;font:700 7px/1.25 Arial,sans-serif;letter-spacing:.04em;
      opacity:.97;box-sizing:border-box;">{message}</div>
    """
    rendered, replacements = re.subn(
        r"(<body\b[^>]*>)",
        lambda match: f"{match.group(1)}{disclosure}",
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    return rendered if replacements else f"{disclosure}{html}"
