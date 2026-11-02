"""
Safety-net report builder.

Generates a minimal, self-contained HTML + PDF HTML pair from raw valuation
data when the templated rendering pipeline cannot produce a complete output.

Design contract:
- Pure function. No I/O, no Jinja, no external state.
- Works on raw dicts (no protocol/typed-class dependency) so it can be
  called both from `HTMLReportService.generate_both_reports` (where the
  caller has typed Protocols) and from the FastAPI `/api/v1/reports/render`
  route (where the caller only has the inbound JSON payload).
- WeasyPrint-safe output: inline CSS, no JS, no external fonts.
- Always satisfies downstream length guards for the generated fallback strings
  (summary HTML >= 100, PDF HTML >= 500). Callers that serve screen previews
  must clear/suppress the summary HTML before returning to Venus.
- Returns the same shape the templated pipeline returns:
    { "html_report": str, "pdf_html_report": str, "report_context": dict }
  with `report_context.safety_net.active = True` so observability dashboards
  and downstream readers can flag the response.

This module is the single source of truth for the safety-net rendering
contract — never inline a "minimal HTML" elsewhere; route through here.
"""

from __future__ import annotations

import html as _html_escape
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from typing import Any, Dict, Mapping, Optional

from babel.numbers import format_decimal

from src.services.defensibility.banner import DEFENSIBILITY_BANNER_INJECT_ANCHOR
from src.services.reports.report_value_admission import report_decimal


@dataclass(frozen=True)
class SafetyNetDisplayValues:
    company_safe: str
    methodology_safe: str
    equity_low: str
    equity_mid: str
    equity_high: str
    ev_ebitda: str
    ev_revenue: str
    correlation_safe: str


EN_LABELS = {
    "title": "Valuation — summary",
    "subtitle": "Detailed report unavailable. Review the recorded figures and missing evidence.",
    "range": "Estimated equity range",
    "mid": "Central estimate",
    "methodology": "Methodology",
    "ev_ebitda": "EV/EBITDA multiple",
    "ev_revenue": "EV/Revenue multiple",
    "disclaimer": (
        "This limited summary uses recorded figures only. Missing or invalid amounts are unavailable. "
        "No valuation range or statistical coverage is inferred. Review the source data and "
        "regenerate the detailed report before relying on it."
    ),
    "generated": "Generated on",
    "reference": "Reference",
}

NL_LABELS = {
    "title": "Waardeschatting — samenvatting",
    "subtitle": "Gedetailleerd rapport niet beschikbaar. Controleer de vastgelegde cijfers en ontbrekende gegevens.",
    "range": "Vastgelegde aandeelhouderswaarde",
    "mid": "Centrale schatting",
    "methodology": "Methodologie",
    "ev_ebitda": "EV/EBITDA multiple",
    "ev_revenue": "EV/Omzet multiple",
    "disclaimer": (
        "Deze beperkte samenvatting gebruikt uitsluitend vastgelegde cijfers. Ontbrekende of ongeldige "
        "bedragen zijn niet beschikbaar. Er wordt geen waarderingsbereik of statistische dekking "
        "afgeleid. Controleer de brongegevens en genereer het gedetailleerde rapport opnieuw."
    ),
    "generated": "Gegenereerd op",
    "reference": "Referentie",
}


FR_LABELS = {
    "title": "Valorisation — synthèse",
    "subtitle": "Rapport détaillé indisponible. Vérifiez les chiffres enregistrés et les données manquantes.",
    "range": "Fourchette des capitaux propres enregistrée",
    "mid": "Estimation centrale",
    "methodology": "Méthodologie",
    "ev_ebitda": "Multiple VE/EBITDA",
    "ev_revenue": "Multiple VE/chiffre d’affaires",
    "disclaimer": (
        "Cette synthèse limitée utilise uniquement les chiffres enregistrés. Les montants manquants "
        "ou invalides sont indisponibles. Aucune fourchette ni couverture statistique n’est déduite. "
        "Vérifiez les sources et générez à nouveau le rapport détaillé avant de vous y fier."
    ),
    "generated": "Rendu le",
    "reference": "Référence",
}


def _num(value: object) -> Optional[Decimal]:
    try:
        return report_decimal(value, "report amount")
    except ValueError:
        return None


def _fmt_money(value: object, currency: str, locale: str = "en") -> str:
    n = _num(value)
    if n is None:
        return "—"
    # Decimal formatting preserves cents even beyond the binary-float boundary.
    language = str(locale).lower()[:2]
    language = language if language in {"en", "nl", "fr"} else "en"
    with localcontext() as context:
        context.prec = 100
        amount = format_decimal(n, format="#,##0.00", locale=language)
    symbol = "€" if currency == "EUR" else f"{currency} " if currency else ""
    return f"{symbol}{amount}"


def _fmt_mult(value: object) -> str:
    n = _num(value)
    return "—" if n is None else f"{n:.2f}x"


def _read_first(source: Any, *keys: str) -> Any:
    """Look up the first non-None value across a nested-dict candidate chain.

    Each key may be dotted (e.g. ``details.equity_value_low``) for nested
    lookups inside the same source. Useful because Titan persists numbers
    under multiple aliases (``equity_value`` vs ``equity_value_mid``,
    ``valuation_min`` vs ``equity_value_low``, etc.).
    """
    if not isinstance(source, dict):
        return None
    for key in keys:
        cur: Any = source
        for part in key.split("."):
            if not isinstance(cur, dict):
                cur = None
                break
            cur = cur.get(part)
        if cur is not None:
            return cur
    return None


def _first_present(*values: Any) -> Any:
    """Return the first explicitly present value, preserving numeric zero."""
    for value in values:
        if value is not None:
            return value
    return None


def _labels_for_locale(locale: str) -> Mapping[str, str]:
    if locale and str(locale).lower().startswith("nl"):
        return NL_LABELS
    if locale and str(locale).lower().startswith("fr"):
        return FR_LABELS
    return EN_LABELS


def _nested_dict(source: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = source.get(key)
    return value if isinstance(value, dict) else {}


def _resolved_company(
    vd: Mapping[str, object], nested_vr: Mapping[str, object], company_name: Optional[str]
) -> str:
    return str(
        (company_name and str(company_name).strip())
        or _read_first(vd, "company_name", "business_name", "details.company_name")
        or _read_first(nested_vr, "company_name", "business_name")
        or "—"
    )


def _resolved_currency(vd: Mapping[str, object], nested_vr: Mapping[str, object]) -> str:
    raw = _first_present(
        _read_first(vd, "currency", "details.currency"),
        _read_first(nested_vr, "currency"),
    )
    if not isinstance(raw, str):
        return ""
    code = raw.strip().upper()
    return code if len(code) == 3 and code.isascii() and code.isalpha() else ""


def _equity_raw_values(
    vd: Mapping[str, object], nested_vr: Mapping[str, object]
) -> tuple[object, object, object]:
    # Use one source container; never splice an incomplete top-level result
    # with a nested result from a potentially different calculation.
    for source in (vd, _nested_dict(vd, "details"), nested_vr):
        values = (
            _read_first(source, "equity_value_low", "valuation_min"),
            _read_first(source, "equity_value_mid", "equity_value", "valuation_midpoint"),
            _read_first(source, "equity_value_high", "valuation_max"),
        )
        if any(value is not None for value in values):
            return values
    return None, None, None


def _enterprise_raw_values(
    vd: Mapping[str, object], nested_vr: Mapping[str, object]
) -> tuple[object, object, object]:
    for source in (vd, _nested_dict(vd, "details"), nested_vr):
        values = (
            _read_first(source, "enterprise_value_low"),
            _read_first(source, "enterprise_value_mid", "enterprise_value"),
            _read_first(source, "enterprise_value_high"),
        )
        if any(value is not None for value in values):
            return values
    return None, None, None


def _admitted_display_band(raw: tuple[object, object, object]) -> tuple[object, object, object]:
    low, mid, high = (_num(value) for value in raw)
    if any(value is not None and _num(value) is None for value in raw):
        return None, None, None
    if low is None and high is None:
        return None, mid, None
    if low is None or high is None or low > high:
        return None, None, None
    if mid is not None and not low <= mid <= high:
        return None, None, None
    return low, mid, high


def _methodology_raw(vd: Mapping[str, object], nested_vr: Mapping[str, object]) -> object:
    return (
        _read_first(vd, "methodology", "details.methodology", "selected_valuation_method")
        or _read_first(nested_vr, "methodology", "selected_valuation_method")
        or "—"
    )


def _multiple_raw_values(
    vd: Mapping[str, object], nested_vr: Mapping[str, object]
) -> tuple[object, object]:
    ev_ebitda_raw = _first_present(
        _read_first(
            vd, "ebitda_multiple", "details.ebitda_multiple", "report_context.ebitda_multiple"
        ),
        _read_first(nested_vr, "ebitda_multiple"),
    )
    ev_revenue_raw = _first_present(
        _read_first(
            vd,
            "revenue_multiple",
            "details.revenue_multiple",
            "report_context.revenue_multiple",
            "omzet_multiple",
        ),
        _read_first(nested_vr, "revenue_multiple", "omzet_multiple"),
    )
    return ev_ebitda_raw, ev_revenue_raw


def _resolve_display_values(
    vd: Mapping[str, object],
    *,
    company_name: Optional[str],
    correlation_id: Optional[str],
    locale: str = "en",
) -> SafetyNetDisplayValues:
    nested_vr = _nested_dict(vd, "valuation_result")
    resolved_company = _resolved_company(vd, nested_vr, company_name)
    currency = _resolved_currency(vd, nested_vr)
    equity_low_raw, equity_mid_raw, equity_high_raw = _admitted_display_band(
        _equity_raw_values(vd, nested_vr)
    )
    ev_ebitda_raw, ev_revenue_raw = _multiple_raw_values(vd, nested_vr)
    return SafetyNetDisplayValues(
        company_safe=_html_escape.escape(str(resolved_company)),
        methodology_safe=_html_escape.escape(str(_methodology_raw(vd, nested_vr))),
        equity_low=_fmt_money(equity_low_raw, currency, locale),
        equity_mid=_fmt_money(equity_mid_raw, currency, locale),
        equity_high=_fmt_money(equity_high_raw, currency, locale),
        ev_ebitda=_fmt_mult(ev_ebitda_raw),
        ev_revenue=_fmt_mult(ev_revenue_raw),
        correlation_safe=_html_escape.escape(str(correlation_id or "—")),
    )


def build_safety_net_reports(
    valuation_data: Optional[Dict[str, Any]],
    *,
    company_name: Optional[str],
    locale: str,
    reason: str,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a safety-net {html_report, pdf_html_report, report_context}.

    Args:
        valuation_data: Raw valuation result dict (Titan's ``valuation_result``
            payload, or any equivalent flattened dict). May be ``None`` or
            missing fields — output still satisfies the length contract.
        company_name: Display name for the header. Falls back to a value from
            ``valuation_data`` if available, then to "—".
        locale: 'nl', 'en' or 'fr' (anything else is treated as 'en').
        reason: Short machine string explaining why the safety-net fired
            (logged in ``report_context.safety_net.reason``).
        correlation_id: Optional correlation ID for traceability.
    """
    vd: Dict[str, Any] = valuation_data if isinstance(valuation_data, dict) else {}
    display = _resolve_display_values(
        vd,
        company_name=company_name,
        correlation_id=correlation_id,
        locale=locale,
    )
    labels = _labels_for_locale(locale)
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    currency_missing = not _resolved_currency(vd, _nested_dict(vd, "valuation_result"))
    currency_note = (
        {
            "en": "Currency was not recorded or is invalid.",
            "nl": "De valuta is niet vastgelegd of ongeldig.",
            "fr": "La devise n’est pas enregistrée ou est invalide.",
        }.get(str(locale).lower()[:2], "Currency was not recorded or is invalid.")
        if currency_missing
        else ""
    )

    # Screen body: every visible element carries inline styles. We do NOT
    # rely on a <style> block because Mercury's DOMPurify sanitizer strips
    # <style> tags before injecting the HTML into the report viewer (XSS
    # hardening). Inline styles ride on the `style` attribute which is
    # explicitly allowed, so the card always renders properly. Class
    # attributes are preserved alongside in case a downstream consumer
    # wants to override the look. <header>/<footer> tags are also stripped
    # by DOMPurify, so we use <section>/<div> wrappers throughout.
    _S_TITLE = "font-size:1.5rem;margin:0 0 .25rem;color:#0f172a"
    _S_SUBTITLE = "color:#64748b;margin:0 0 .75rem"
    _S_COMPANY = "font-size:1.125rem;margin:0;color:#0f172a"
    _S_RANGE_LABEL = (
        "font-size:.875rem;text-transform:uppercase;letter-spacing:.04em;"
        "color:#475569;margin:0 0 .5rem"
    )
    _S_RANGE_VALUES = "font-size:2rem;font-weight:600;margin:.25rem 0 .5rem;color:#0f172a"
    _S_SEP = "color:#94a3b8;margin:0 .5rem"
    _S_MID = "color:#334155;margin:0 0 1.25rem"
    _S_FACTS_GRID = "display:grid;grid-template-columns:1fr 1fr;gap:.5rem 1rem;margin:0 0 1.5rem"
    _S_DT = "color:#64748b;font-size:.8125rem"
    _S_DD = "margin:0;font-weight:500;color:#0f172a"
    _S_DISCLAIMER = (
        "background:#f1f5f9;border-left:4px solid #2563eb;padding:.75rem 1rem;"
        "border-radius:6px;color:#1e293b;font-size:.875rem;margin:0 0 1rem"
    )
    _S_FOOTER = "margin-top:1rem;color:#94a3b8;font-size:.75rem"
    _S_HEADER = "border-bottom:1px solid #e2e8f0;padding-bottom:1rem;margin-bottom:1.25rem"
    # No box-shadow: WeasyPrint logs it as unsupported; border + radius is enough for screen/PDF parity.
    _S_CARD = (
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
        "color:#0f172a;max-width:720px;margin:2rem auto;padding:2rem;"
        "border:1px solid #cbd5e1;border-radius:12px;background:#ffffff"
    )

    enterprise_section = ""
    enterprise_raw = _enterprise_raw_values(vd, _nested_dict(vd, "valuation_result"))
    if any(value is not None for value in enterprise_raw):
        enterprise_band = _admitted_display_band(enterprise_raw)
        currency = _resolved_currency(vd, _nested_dict(vd, "valuation_result"))
        ev_low, ev_mid, ev_high = (
            _html_escape.escape(_fmt_money(value, currency, locale)) for value in enterprise_band
        )
        enterprise_label = {
            "en": "Recorded enterprise value",
            "nl": "Vastgelegde ondernemingswaarde",
            "fr": "Valeur d’entreprise enregistrée",
        }.get(str(locale).lower()[:2], "Recorded enterprise value")
        enterprise_section = f"""<section class="vs-enterprise" data-value-basis="enterprise_value">
          <h3 style="{_S_RANGE_LABEL}">{enterprise_label}</h3>
          <p><span class="vs-enterprise-low">{ev_low}</span> — <span class="vs-enterprise-high">{ev_high}</span></p>
          <p>{labels['mid']}: <strong class="vs-enterprise-mid">{ev_mid}</strong></p>
        </section>"""

    body = f"""
<section class="valuation-summary" style="{_S_CARD}">
  <div class="vs-header" style="{_S_HEADER}">
    <h1 class="vs-title" style="{_S_TITLE}">{labels['title']}</h1>
    <p class="vs-subtitle" style="{_S_SUBTITLE}">{labels['subtitle']}</p>
    <p class="vs-currency-note" style="{_S_SUBTITLE}">{currency_note}</p>
    <h2 class="vs-company" style="{_S_COMPANY}">{display.company_safe}</h2>
  </div>
  {enterprise_section}
  <section class="vs-range" data-value-basis="equity_value">
    <h3 style="{_S_RANGE_LABEL}">{labels['range']}</h3>
    <p class="vs-range-values" style="{_S_RANGE_VALUES}">
      <span class="vs-low">{_html_escape.escape(display.equity_low)}</span>
      <span class="vs-sep" style="{_S_SEP}">—</span>
      <span class="vs-high">{_html_escape.escape(display.equity_high)}</span>
    </p>
    <p class="vs-mid" style="{_S_MID}">{labels['mid']}: <strong>{_html_escape.escape(display.equity_mid)}</strong></p>
  </section>
  <section class="vs-facts">
    <dl style="{_S_FACTS_GRID}">
      <dt style="{_S_DT}">{labels['methodology']}</dt><dd style="{_S_DD}">{display.methodology_safe}</dd>
      <dt style="{_S_DT}">{labels['ev_ebitda']}</dt><dd style="{_S_DD}">{_html_escape.escape(display.ev_ebitda)}</dd>
      <dt style="{_S_DT}">{labels['ev_revenue']}</dt><dd style="{_S_DD}">{_html_escape.escape(display.ev_revenue)}</dd>
    </dl>
  </section>
  {DEFENSIBILITY_BANNER_INJECT_ANCHOR}
  <p class="vs-disclaimer" style="{_S_DISCLAIMER}">{labels['disclaimer']}</p>
  <div class="vs-footer" style="{_S_FOOTER}">
    <small>{labels['generated']}: {generated_at} · {labels['reference']}: {display.correlation_safe}</small>
  </div>
</section>
""".strip()

    # Kept as a no-op for the screen variant — every rule is now inline on
    # each element. The <style> block survives in the full document below
    # for consumers that don't pass through DOMPurify (e.g. the standalone
    # browser preview), but the page is fully styled even without it.
    screen_style = """
<style>
  /* Inline styles on each element are the source of truth. This block is
     purely a progressive enhancement for unsanitized contexts. */
  .valuation-summary{box-sizing:border-box}
</style>
""".strip()

    pdf_style = """
<style>
  @page{size:A4;margin:2cm}
  body{font-family:'Helvetica','Arial',sans-serif;color:#0f172a}
  .valuation-summary{padding:0}
  .vs-header{border-bottom:1pt solid #cbd5e1;padding-bottom:12pt;margin-bottom:16pt}
  .vs-title{font-size:18pt;margin:0 0 4pt}
  .vs-subtitle{color:#475569;margin:0 0 8pt}
  .vs-company{font-size:14pt;margin:0}
  .vs-range h3{font-size:9pt;text-transform:uppercase;letter-spacing:1pt;color:#475569;margin:0 0 6pt}
  .vs-range-values{font-size:22pt;font-weight:700;margin:4pt 0 6pt}
  .vs-sep{color:#94a3b8;margin:0 6pt}
  .vs-mid{color:#334155;margin:0 0 14pt}
  .vs-facts table{width:100%;border-collapse:collapse;margin-bottom:14pt}
  .vs-facts td{padding:4pt 6pt;border-bottom:1pt solid #e2e8f0;font-size:10pt}
  .vs-facts td.label{color:#475569;width:50%}
  .vs-disclaimer{background:#f1f5f9;padding:8pt 10pt;border-left:3pt solid #2563eb;font-size:10pt}
  .vs-footer{margin-top:12pt;color:#94a3b8;font-size:8pt}
</style>
""".strip()

    # Match styled opening tags as well as closing tags. Replacing only the
    # latter leaves malformed markup that PDF engines repair differently.
    pdf_body = re.sub(r"<dl\b[^>]*>", "<table>", body).replace("</dl>", "</table>")
    pdf_body = re.sub(r"<dt\b[^>]*>", '<tr><td class="label">', pdf_body).replace("</dt>", "</td>")
    pdf_body = re.sub(r"<dd\b[^>]*>", "<td>", pdf_body).replace("</dd>", "</td></tr>")

    locale_safe = _html_escape.escape(str(locale or "en"))
    title_safe = f"{display.company_safe} — {labels['title']}"

    html_report = f"""<!doctype html>
<html lang="{locale_safe}">
<head>
<meta charset="utf-8"/>
<title>{title_safe}</title>
{screen_style}
</head>
<body>
{body}
</body>
</html>
""".strip()

    pdf_html_report = f"""<!doctype html>
<html lang="{locale_safe}">
<head>
<meta charset="utf-8"/>
<title>{title_safe}</title>
{pdf_style}
</head>
<body>
{pdf_body}
</body>
</html>
""".strip()

    safety_flag = {
        "active": True,
        "reason": reason,
        "generated_at": generated_at,
        "correlation_id": str(correlation_id or ""),
        "currency_available": not currency_missing,
        "statistical_coverage": None,
    }

    return {
        "html_report": html_report,
        "pdf_html_report": pdf_html_report,
        "report_context": {"safety_net": safety_flag},
    }
