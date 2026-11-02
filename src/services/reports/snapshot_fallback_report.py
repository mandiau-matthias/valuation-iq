"""Currency-safe, nonnumeric-safe report from a validated calculation snapshot.

No valuation arithmetic, current-time facts, or generated financial prose lives
here. This renderer is deliberately independent of the full template pipeline.
"""

from __future__ import annotations

from decimal import Decimal
from html import escape

from babel.numbers import format_decimal

COPY = {
    "en": (
        "Valuation report",
        "Valuation range",
        "Enterprise value",
        "Equity value",
        "Low",
        "Base",
        "High",
        "Methodology",
        "Financial basis",
        "Assumptions and limitations",
        "No numerical valuation is available from the admitted financial evidence.",
        "Not available",
        "Currency was not recorded in the calculation snapshot.",
        "Calculation date",
        "Reported earnings",
        "Adjusted earnings",
        "Adjustment",
        "Range derivation is not recorded; no statistical coverage is claimed.",
    ),
    "nl": (
        "Waarderingsrapport",
        "Waarderingsbandbreedte",
        "Ondernemingswaarde",
        "Aandelenwaarde",
        "Laag",
        "Basis",
        "Hoog",
        "Methodologie",
        "Financiële basis",
        "Aannames en beperkingen",
        "De toegelaten financiële gegevens bieden geen basis voor een numerieke waardering.",
        "Niet beschikbaar",
        "De valuta is niet vastgelegd in de berekeningsmomentopname.",
        "Berekeningsdatum",
        "Gerapporteerd resultaat",
        "Aangepast resultaat",
        "Correctie",
        "De afleiding van de bandbreedte is niet vastgelegd; er wordt geen statistische dekking geclaimd.",
    ),
    "fr": (
        "Rapport de valorisation",
        "Fourchette de valorisation",
        "Valeur d’entreprise",
        "Valeur des capitaux propres",
        "Basse",
        "Centrale",
        "Haute",
        "Méthodologie",
        "Base financière",
        "Hypothèses et limites",
        "Les données financières admises ne permettent pas de produire une valorisation numérique.",
        "Non disponible",
        "La devise n’est pas enregistrée dans l’instantané du calcul.",
        "Date du calcul",
        "Résultat publié",
        "Résultat ajusté",
        "Ajustement",
        "La construction de la fourchette n’est pas documentée ; aucune couverture statistique n’est revendiquée.",
    ),
}


def render_snapshot_fallback(request, *, verified_assurance_authority=None, locale=None) -> str:
    result = request.valuation_result
    locale = str(locale or request.language or "en").split("-")[0].lower()
    locale = locale if locale in COPY else "en"
    c = COPY[locale]
    run = result.valuation_run
    metrics = result.financial_metrics or {}
    currency = str(getattr(run, "currency", None) or metrics.get("currency") or "")
    if currency and (len(currency) != 3 or not currency.isalpha()):
        raise ValueError("snapshot currency must be an ISO currency code")
    currency = currency.upper()

    def money(value):
        if value is None:
            return escape(c[11])
        amount = Decimal(str(value))
        if not amount.is_finite():
            raise ValueError("report amounts must be finite")
        return escape(
            (currency + " " if currency else "")
            + format_decimal(amount, format="#,##0.00", locale=locale)
        )

    enterprise = [
        result.enterprise_value_low,
        result.enterprise_value_mid,
        result.enterprise_value_high,
    ]
    equity = [result.equity_value_low, result.equity_value_mid, result.equity_value_high]
    headline = enterprise if request.headline_value_basis == "enterprise_value" else equity
    if verified_assurance_authority is not None:
        band = verified_assurance_authority.envelope.audience_display_band
        if band.value_basis != request.headline_value_basis:
            raise ValueError("assured audience band does not match headline value basis")
        headline = [band.display_low, band.display_mid, band.display_high]
    available = all(value is not None for value in headline)
    headline_html = (
        f'<p class="value">{money(headline[0])} - {money(headline[2])}</p>'
        if available
        else f'<p class="no-value">{escape(c[10])}</p>'
    )
    rows = []
    for label, values in [(c[2], enterprise), (c[3], equity)]:
        rows.append(
            f'<tr><th scope="row">{escape(label)}</th>'
            + "".join(f"<td>{money(v)}</td>" for v in values)
            + "</tr>"
        )
    table = (
        (
            '<div class="table-wrap"><table><thead><tr><th></th>'
            + "".join(f"<th>{escape(t)}</th>" for t in c[4:7])
            + "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></div>"
        )
        if available or any(v is not None for v in enterprise + equity)
        else ""
    )
    # The ledger already commits the reported-to-adjusted identity. Render its
    # values without recalculating adjustments or applying them a second time.
    buildup = result.multiple_build_up
    earnings = getattr(buildup, "earnings_basis", None)
    earnings_html = ""
    if earnings is not None:
        earnings_html = f"<h2>{escape(c[8])}</h2><dl><dt>{escape(c[14])}</dt><dd>{money(earnings.reported_earnings)}</dd><dt>{escape(c[15])}</dt><dd>{money(earnings.adjusted_earnings)}</dd></dl>"
        items = []
        for item in earnings.add_backs:
            if item.applied:
                items.append(
                    f'<tr><th scope="row">{escape(str(item.label))}</th><td>{money(item.signed_amount)}</td></tr>'
                )
        if items:
            earnings_html += "<table><tbody>" + "".join(items) + "</tbody></table>"
    disclosures = []
    from .range_provenance_projection import project_range_provenance
    provenance = project_range_provenance(run, locale)
    if provenance is not None:
        disclosures.extend([provenance["kind_label"], provenance["calibration_disclosure"]])
        disclosures.extend(
            f"{provenance['excluded_method_labels'].get(method, method)}: {reason}"
            for method, reason in provenance["excluded_methods"].items()
        )
    if result.valuation_disclaimer:
        disclosures.append(result.valuation_disclaimer)
    if not currency:
        disclosures.append(c[12])
    if available:
        disclosures.append(c[17])
    quality = result.data_quality or {}
    for key in ("assumptions", "limitations", "disclosures"):
        values = quality.get(key)
        if isinstance(values, list):
            disclosures.extend(str(v) for v in values)
    disclosure_html = "".join(
        f"<p>{escape(str(value))}</p>" for value in dict.fromkeys(disclosures)
    )
    company = escape(request.company_name or "")
    timestamp = escape(str(result.calculation_timestamp or ""))
    method_label = getattr(result, "valuation_method_label", None) or {
        "upswitch_adaptive": "Upswitch Adaptive",
        "HYBRID": "Upswitch Adaptive",
        "dcf": "DCF",
        "ebitda_multiple": "EV / EBITDA",
        "omzet_multiple": "EV / Revenue",
    }.get(result.methodology_used, result.methodology_used or "")
    method_html = f'<p class="meta">{escape(c[7])}: {escape(method_label)}</p>' if available else ""

    return f"""<!doctype html><html lang="{locale}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(c[0])} - {company}</title>
<style>
@page {{size:A4; margin:18mm; @bottom-right {{content:counter(page);font:9pt sans-serif;color:#64748b}}}}
* {{box-sizing:border-box}} body {{margin:0;background:#fff;color:#18323b;font-family:Arial,sans-serif;font-size:14px;line-height:1.55}} main {{max-width:960px;margin:auto;padding:40px}} header {{border-bottom:3px solid #0c6b63;padding-bottom:22px;margin-bottom:28px}} .brand {{font-size:12px;letter-spacing:.12em;color:#0c6b63}} h1 {{font-size:30px;line-height:1.2;overflow-wrap:anywhere}} h2 {{font-size:18px;margin-top:26px}} .meta,.disclosures {{color:#53616a;font-size:11px;line-height:1.6}} .value {{font-size:26px;color:#0c6b63;font-weight:600;overflow-wrap:anywhere}} .no-value {{font-size:18px;max-width:650px}} table {{border-collapse:collapse;table-layout:fixed;width:100%;font-variant-numeric:tabular-nums;font-size:12px}} th,td {{padding:10px 8px;border-bottom:1px solid #dbe4e6;text-align:right;overflow-wrap:anywhere}} th:first-child {{text-align:left;width:31%}} td {{font-size:11px}} thead {{display:table-header-group}} tr {{break-inside:avoid}} dl {{display:grid;grid-template-columns:1fr 1fr}} dd {{text-align:right}} .disclosures {{margin-top:30px;border-top:1px solid #dbe4e6;padding-top:12px}} .table-wrap {{overflow-x:auto}} @media(max-width:600px) {{main {{padding:20px}} h1 {{font-size:24px}} .value {{font-size:21px}} table {{font-size:11px}} th,td {{padding:8px 4px}}}} @media print {{main {{padding:0}} .table-wrap {{overflow:visible}} h2 {{break-after:avoid}}}}
</style></head><body><main><header><p class="brand">UPSWITCH</p><h1>{company}</h1><p>{escape(c[0])}</p><p class="meta">{escape(c[13])}: {timestamp}</p></header><section><h2>{escape(c[1])}</h2>{headline_html}{table}{method_html}</section>{earnings_html}<footer class="disclosures"><h2>{escape(c[9])}</h2>{disclosure_html}</footer></main></body></html>"""
