"""Currency-safe indicative artifacts from the immutable engine run; no repricing."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from decimal import Decimal
from html import escape

from src.api.schemas.stateless_report_schemas import GenerateReportRequest
from src.api.schemas.valuation_contracts import ValuationRunV2
from src.domain.financial_arithmetic import decimal_number
from src.services.reports.automated_indicative_policy import COPY

LABELS = {
    "en": [
        "Valuation range",
        "Enterprise value",
        "Shareholder value",
        "Low",
        "Base",
        "High",
        "Financial inputs",
        "Metric",
        "Amount",
        "Method selection",
        "Method",
        "Weight",
        "Evidence and assumptions",
        "Reported EBITDA",
        "Normalized EBITDA",
        "Fiscal year",
        "Adjustment",
        "Status",
        "Limitations",
        "Unavailable",
    ],
    "nl": [
        "Waarderingsbandbreedte",
        "Ondernemingswaarde",
        "Aandeelhouderswaarde",
        "Laag",
        "Basis",
        "Hoog",
        "Financiële invoer",
        "Maatstaf",
        "Bedrag",
        "Methodeselectie",
        "Methode",
        "Gewicht",
        "Bewijs en aannames",
        "Gerapporteerde EBITDA",
        "Genormaliseerde EBITDA",
        "Boekjaar",
        "Correctie",
        "Status",
        "Beperkingen",
        "Niet beschikbaar",
    ],
    "fr": [
        "Fourchette de valorisation",
        "Valeur d’entreprise",
        "Valeur des actionnaires",
        "Basse",
        "Base",
        "Haute",
        "Données financières",
        "Indicateur",
        "Montant",
        "Sélection des méthodes",
        "Méthode",
        "Poids",
        "Preuves et hypothèses",
        "EBITDA publié",
        "EBITDA normalisé",
        "Exercice",
        "Ajustement",
        "Statut",
        "Limites",
        "Indisponible",
    ],
}

METRIC_LABELS = {
    "en": {
        "revenue": "Revenue",
        "ebitda": "EBITDA",
        "cash": "Unrestricted cash",
        "total_debt": "Financial debt",
        "net_debt": "Net debt",
        "reported_ebitda": "Reported EBITDA",
        "normalized_ebitda": "Normalized EBITDA",
    },
    "nl": {
        "revenue": "Omzet",
        "ebitda": "EBITDA",
        "cash": "Vrij beschikbare kasmiddelen",
        "total_debt": "Financiële schuld",
        "net_debt": "Nettoschuld",
        "reported_ebitda": "Gerapporteerde EBITDA",
        "normalized_ebitda": "Genormaliseerde EBITDA",
    },
    "fr": {
        "revenue": "Chiffre d’affaires",
        "ebitda": "EBITDA",
        "cash": "Trésorerie disponible",
        "total_debt": "Dette financière",
        "net_debt": "Dette nette",
        "reported_ebitda": "EBITDA publié",
        "normalized_ebitda": "EBITDA normalisé",
    },
}

RANGE_LABELS = {
    "en": {
        "supplied_multiple_bounds": "Supplied multiple bounds",
        "assumed_multiple_spread": "Assumed multiple spread",
        "sensitivity_grid_extrema": "Sensitivity grid limits",
        "supplied_sensitivity_bounds": "Supplied sensitivity limits",
        "point_only": "Point scenario; no range evidence",
    },
    "nl": {
        "supplied_multiple_bounds": "Aangeleverde multiplegrenzen",
        "assumed_multiple_spread": "Aangenomen multiplespreiding",
        "sensitivity_grid_extrema": "Grenzen gevoeligheidsmatrix",
        "supplied_sensitivity_bounds": "Aangeleverde gevoeligheidsgrenzen",
        "point_only": "Puntscenario; geen bewijs voor bandbreedte",
    },
    "fr": {
        "supplied_multiple_bounds": "Bornes des multiples fournies",
        "assumed_multiple_spread": "Dispersion supposée des multiples",
        "sensitivity_grid_extrema": "Limites de la grille de sensibilité",
        "supplied_sensitivity_bounds": "Limites de sensibilité fournies",
        "point_only": "Scénario ponctuel ; fourchette non étayée",
    },
}
STATUS_LABELS = {
    "en": {
        "proposed": "Proposed, unpriced",
        "pending": "Pending, unpriced",
        "rejected": "Rejected, unpriced",
        "accepted": "Accepted",
    },
    "nl": {
        "proposed": "Voorgesteld, niet toegepast",
        "pending": "In afwachting, niet toegepast",
        "rejected": "Afgewezen, niet toegepast",
        "accepted": "Aanvaard",
    },
    "fr": {
        "proposed": "Proposé, non appliqué",
        "pending": "En attente, non appliqué",
        "rejected": "Rejeté, non appliqué",
        "accepted": "Accepté",
    },
}


def render_automatic_html(request: GenerateReportRequest, locale: str) -> str:
    """Project stored amounts and adjustment decisions, without recalculating a range."""
    run = request.valuation_result.valuation_run
    if not isinstance(run, ValuationRunV2):
        raise ValueError("Automatic numeric report requires a verified immutable v2 run")
    lang = locale[:2] if locale[:2] in LABELS else "en"
    l = LABELS[lang]
    transition = {"en": "to", "nl": "naar", "fr": "vers"}[lang]
    title, notice = COPY[lang]
    currency = run.currency or l[19]

    def text(value: object) -> str:
        return escape(str(value))

    def amount(value: object) -> str:
        if value is None:
            return l[19]
        number = decimal_number(value)
        rendered = format(number, ",.2f")
        if lang in {"nl", "fr"}:
            rendered = rendered.replace(",", "\u202f").replace(".", ",")
        return f"{text(currency)} {rendered}"

    def table(headers: list[str], rows: list[list[str]]) -> str:
        return (
            "<table><thead><tr>"
            + "".join(f"<th>{text(h)}</th>" for h in headers)
            + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>" for row in rows)
            + "</tbody></table>"
        )

    bands = []
    for label, band in ((l[1], run.enterprise_value_range), (l[2], run.valuation_range)):
        if band is not None:
            bands.append([label, *[amount(getattr(band, key)) for key in ("low", "mid", "high")]])
    sections = [f"<h2>{l[0]}</h2>" + table([l[7], *l[3:6]], bands)]
    layers = run.driver_ledger.get("layers")
    if isinstance(layers, Mapping):
        shareholder = layers.get("shareholder_transaction")
        if isinstance(shareholder, Mapping) and shareholder.get("ownership_percentage") is not None:
            sections.append(
                "<p>"
                + text(shareholder.get("label") or "")
                + ": "
                + text(shareholder["ownership_percentage"])
                + "%</p>"
            )
        bridge = layers.get("enterprise_to_equity")
        if isinstance(bridge, Mapping):
            rows = []
            for group in ("bridge", "explicit_adjustments"):
                values = bridge.get(group)
                if isinstance(values, Mapping):
                    for key, value in values.items():
                        if key in {
                            "enterprise_value",
                            "net_debt",
                            "total_debt",
                            "cash",
                            "nwc_adjustment",
                            "equity_value",
                            "real_estate_surplus",
                            "restricted_cash",
                            "lease_liabilities",
                            "debt_like_items",
                            "surplus_assets",
                        }:
                            bridge_label = (
                                l[1]
                                if key == "enterprise_value"
                                else (
                                    l[2]
                                    if key == "equity_value"
                                    else (
                                        {
                                            "en": "Working capital adjustment",
                                            "nl": "Werkkapitaalcorrectie",
                                            "fr": "Ajustement du fonds de roulement",
                                        }[lang]
                                        if key == "nwc_adjustment"
                                        else METRIC_LABELS[lang].get(key, key.replace("_", " "))
                                    )
                                )
                            )
                            rows.append([text(bridge_label), amount(value)])
            if rows:
                sections.append(
                    "<h2>"
                    + l[1]
                    + " "
                    + transition
                    + " "
                    + l[2]
                    + "</h2>"
                    + table([l[7], l[8]], rows)
                )

    monetary_metrics = {
        "revenue",
        "ebitda",
        "reported_ebitda",
        "normalized_ebitda",
        "cash",
        "total_debt",
        "net_debt",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "operating_cash_flow",
        "capex",
        "free_cash_flow",
    }
    metrics = {
        key: value for key, value in run.financial_metrics.items() if key in monetary_metrics
    }
    sections.append(
        f"<h2>{l[6]}</h2>"
        + table(
            [l[7], l[8]],
            [
                [text(METRIC_LABELS[lang].get(key, key.replace("_", " "))), amount(value)]
                for key, value in metrics.items()
                if value is None
                or isinstance(value, (str, int, float, Decimal))
                and not isinstance(value, bool)
            ],
        )
    )
    mix = {str(row.get("method_key")): row.get("weight") for row in run.method_mix}
    methods = []
    for key, raw in run.method_results.items():
        if not isinstance(raw, Mapping):
            continue
        details = raw.get("details")
        basis = details.get("range_basis") if isinstance(details, Mapping) else None
        reason = raw.get("unavailable_reason")
        if raw.get("available"):
            evidence = (
                text(RANGE_LABELS[lang].get(str(basis.get("kind")), str(basis.get("kind"))))
                if isinstance(basis, Mapping)
                else text(run.response_snapshot.get("data_tier") or "indicative")
            )
        else:
            evidence = text(reason or l[19])
        weight = mix.get(key)
        methods.append(
            [
                text(raw.get("label") or key),
                text(weight if weight is not None else "0"),
                amount(raw.get("enterprise_value")),
                amount(
                    raw.get("equity_value")
                    if raw.get("equity_value") is not None
                    else raw.get("value")
                ),
                evidence,
            ]
        )
    if not methods:
        methods.append([l[19], "", l[19], l[19], l[19]])
    sections.append(f"<h2>{l[9]}</h2>" + table([l[10], l[11], l[1], l[2], l[12]], methods))
    ledger = run.response_snapshot.get("earnings_basis_ledger")
    if isinstance(ledger, Mapping):
        annual = ledger.get("rows")
        if isinstance(annual, list):
            rows = []
            for row in annual:
                if not isinstance(row, Mapping):
                    continue
                rows.append(
                    [
                        text(row.get("year", row.get("fiscal_year", ""))),
                        amount(row.get("reported_ebitda")),
                        amount(row.get("normalized_ebitda")),
                        text(row.get("weight", "")),
                    ]
                )
            sections.append(
                f"<h2>{l[13]} {transition} {l[14]}</h2>" + table([l[15], l[13], l[14], l[11]], rows)
            )
            adjustments = []
            for row in annual:
                if not isinstance(row, Mapping):
                    continue
                for group in ("applied_adjustments", "pending_adjustments", "rejected_adjustments"):
                    items = row.get(group)
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if isinstance(item, Mapping):
                            adjustments.append(
                                [
                                    text(row.get("year", row.get("fiscal_year", ""))),
                                    text(
                                        item.get("label")
                                        or item.get("category")
                                        or item.get("id")
                                        or ""
                                    ),
                                    amount(item.get("signed_amount", item.get("amount"))),
                                    text(
                                        STATUS_LABELS[lang].get(
                                            str(item.get("status")),
                                            str(item.get("status") or group),
                                        )
                                    ),
                                    text(item.get("source") or item.get("evidence_id") or ""),
                                    text(item.get("rule_version") or ""),
                                ]
                            )
            if adjustments:
                sections.append(
                    table(
                        [
                            l[15],
                            l[16],
                            l[8],
                            l[17],
                            l[12],
                            {"en": "Rule", "nl": "Regel", "fr": "Règle"}[lang],
                        ],
                        adjustments,
                    )
                )
    limitations = [notice, str(run.response_snapshot.get("data_tier_rationale") or "")]
    risks = run.response_snapshot.get("risk_factors")
    if isinstance(risks, list):
        limitations.extend(str(risk) for risk in risks)
    sections.append(
        f"<h2>{l[18]}</h2><ul>"
        + "".join(f"<li>{text(item)}</li>" for item in limitations if item)
        + "</ul>"
    )
    styles = """@page { size:A4; margin:16mm; @bottom-right { content:counter(page); font-size:9pt; } }
    * { box-sizing:border-box; } body { font-family:Arial,sans-serif; color:#152c3b; font-size:10pt; line-height:1.5; max-width:1100px; margin:24px auto; padding:16px; }
    h1 { font-size:23pt; } h2 { margin-top:22px; font-size:14pt; break-after:avoid; } .notice { padding:12px; border-left:4px solid #247b80; background:#eff8f8; }
    table { width:100%; border-collapse:collapse; table-layout:fixed; font-size:9pt; margin-bottom:16px; } thead { display:table-header-group; } tr { break-inside:avoid; } th,td { padding:8px; border-bottom:1px solid #cbd5db; overflow-wrap:anywhere; vertical-align:top; text-align:left; } th { background:#e8f1f4; } li { overflow-wrap:anywhere; }
    footer { margin-top:24px; font-size:8pt; overflow-wrap:anywhere; } @media(max-width:600px) { body { margin:0; padding:12px; } table { font-size:8pt; } th,td { padding:4px; } } @media print { body { margin:0; padding:0; max-width:none; } }"""
    return (
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{text(request.company_name)} — {text(title)}</title><style>{styles}</style></head><body><h1>{text(request.company_name)}</h1><p>{text(title)} · {text(run.valuation_lens_date)} · {text(currency)}</p><p class="notice">{text(notice)}</p>'
        + "".join(sections)
        + f"<footer>{text(run.run_id)}<br>{text(run.run_hash)}</footer></body></html>"
    )


async def generate_automatic_outputs(
    request: GenerateReportRequest, locale: str
) -> tuple[str | None, str | None]:
    html = render_automatic_html(request, locale)
    pdf = None
    if request.include_pdf:
        from src.services.infrastructure.report_generation.metrics_collector import MetricsCollector
        from src.services.infrastructure.report_generation.strategies.pdf_strategy import (
            PDFGenerationStrategy,
        )
        from src.utils.logging import get_logger

        run = request.valuation_result.valuation_run
        assert isinstance(run, ValuationRunV2)
        strategy = PDFGenerationStrategy(
            logger_instance=get_logger(__name__), metrics_collector=MetricsCollector()
        )
        from src.services.infrastructure.pdf.font_css import get_pdf_font_face_css

        # PDF glyphs must come from the bundled static faces. Host Arial can
        # embed incomplete glyph outlines even when extraction sees correct text.
        pdf_font_css = (
            get_pdf_font_face_css()
            + "* { font-family: 'Noto Sans', 'Noto Sans Symbols 2', sans-serif !important; } @page { @bottom-right { font-family: 'Noto Sans'; } }"
        )
        pdf_html = html.replace("</head>", f"<style>{pdf_font_css}</style></head>", 1)
        data = await strategy.generate(
            html_content=pdf_html,
            template_data={
                "company_name": request.company_name,
                "valuation_id": run.valuation_id,
                "archival_pdfa": True,
                "artifact_timestamp": run.recording_timestamp,
                "artifact_identifier": run.run_hash,
                "locale": locale,
            },
            correlation_id=run.run_id[:8],
        )
        if not data:
            raise ValueError("Automatic PDF generation returned no bytes")
        pdf = base64.b64encode(data).decode()
    return html if request.include_html else None, pdf
