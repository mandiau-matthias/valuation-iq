"""Deterministic no-basis report; no monetary calculation or generated prose."""

from __future__ import annotations

import base64
import hashlib
from html import escape
from typing import NoReturn

from src.api.schemas.valuation_assessment import (
    AssessmentReportResponse,
    GenerateAssessmentReportRequest,
    assessment_hash,
)

COPY = {
    "en": {
        "title": "Financial basis assessment",
        "conclusion": "A numerical valuation cannot yet be established from the supplied financial evidence.",
        "basis": "Financial information",
        "field": "Financial item",
        "period": "Fiscal year",
        "value": "Recorded value",
        "missing": "Not supplied",
        "methods": "Valuation methods",
        "method_note": "The methods below could not be applied because no financial basis was supplied. No enterprise value, equity value or valuation range has been calculated.",
        "next": "Information needed",
        "next_text": "Provide the latest financial statements and relevant historical periods, including revenue, reported EBITDA or operating profit and depreciation/amortization, balance-sheet assets, cash and liabilities. Add any proposed normalization with its period, signed amount and source. Forecasts and supporting evidence may enable additional methods.",
        "scope": "Scope and limitations",
        "scope_text": "This report records the available evidence and the reason a numerical conclusion is unavailable. It does not establish that the business has no value. Supplied facts, including an observed zero or loss, must be assessed separately before selecting a valuation method.",
        "omzet_multiple": "EV / Revenue",
        "real_estate_yield": "Property",
        "fiscal_4x": "Fiscal reference",
        "currency": "Reporting currency",
        "date": "Assessment date",
        "identity": "Assessment reference",
        "revenue": "Revenue",
        "ebitda": "EBITDA",
        "reported_ebitda": "Reported EBITDA",
        "total_assets": "Total assets",
        "total_debt": "Total debt",
        "cash": "Cash",
    },
    "nl": {
        "title": "Beoordeling van de financiële basis",
        "conclusion": "Op basis van de aangeleverde financiële gegevens kan nog geen numerieke waardering worden vastgesteld.",
        "basis": "Financiële informatie",
        "field": "Financiële post",
        "period": "Boekjaar",
        "value": "Vastgelegde waarde",
        "missing": "Niet aangeleverd",
        "methods": "Waarderingsmethoden",
        "method_note": "De onderstaande methoden konden niet worden toegepast omdat een financiële basis ontbreekt. Er is geen ondernemingswaarde, aandelenwaarde of waarderingsbandbreedte berekend.",
        "next": "Benodigde informatie",
        "next_text": "Lever de recentste jaarrekening en relevante historische perioden aan, met omzet, gerapporteerde EBITDA of bedrijfsresultaat en afschrijvingen, activa, liquide middelen en schulden. Vermeld bij elke voorgestelde normalisatie de periode, het bedrag met teken en de bron. Prognoses en onderbouwende gegevens kunnen aanvullende methoden mogelijk maken.",
        "scope": "Reikwijdte en beperkingen",
        "scope_text": "Dit rapport legt de beschikbare gegevens vast en verklaart waarom een numerieke conclusie ontbreekt. Het stelt niet vast dat de onderneming geen waarde heeft. Aangeleverde cijfers, waaronder nulwaarden en verliezen, moeten afzonderlijk worden beoordeeld voordat een waarderingsmethode wordt gekozen.",
        "omzet_multiple": "EV / Omzet",
        "real_estate_yield": "Vastgoed",
        "fiscal_4x": "Fiscale referentie",
        "currency": "Rapportagevaluta",
        "date": "Beoordelingsdatum",
        "identity": "Beoordelingsreferentie",
        "revenue": "Omzet",
        "ebitda": "EBITDA",
        "reported_ebitda": "Gerapporteerde EBITDA",
        "total_assets": "Totale activa",
        "total_debt": "Totale schuld",
        "cash": "Liquide middelen",
    },
    "fr": {
        "title": "Évaluation de la base financière",
        "conclusion": "Les éléments financiers fournis ne permettent pas encore d'établir une valorisation chiffrée.",
        "basis": "Informations financières",
        "field": "Poste financier",
        "period": "Exercice",
        "value": "Valeur enregistrée",
        "missing": "Non fourni",
        "methods": "Méthodes de valorisation",
        "method_note": "Les méthodes ci-dessous n'ont pas pu être appliquées faute de base financière. Aucune valeur d'entreprise, valeur des capitaux propres ni fourchette de valorisation n'a été calculée.",
        "next": "Informations nécessaires",
        "next_text": "Fournissez les derniers comptes annuels et les exercices historiques pertinents, avec le chiffre d'affaires, l'EBITDA déclaré ou le résultat d'exploitation et les amortissements, les actifs, la trésorerie et les dettes. Précisez pour chaque normalisation proposée la période, le montant signé et la source. Des prévisions et des justificatifs peuvent permettre d'autres méthodes.",
        "scope": "Portée et limites",
        "scope_text": "Ce rapport consigne les éléments disponibles et explique l'absence de conclusion chiffrée. Il ne signifie pas que l'entreprise est sans valeur. Les chiffres fournis, y compris les valeurs nulles ou les pertes, doivent être examinés séparément avant de choisir une méthode de valorisation.",
        "omzet_multiple": "VE / Chiffre d’affaires",
        "real_estate_yield": "Immobilier",
        "fiscal_4x": "Référence fiscale",
        "liquidation_analysis": "Liquidation",
        "currency": "Devise de présentation",
        "date": "Date d'évaluation",
        "identity": "Référence de l'évaluation",
        "revenue": "Chiffre d'affaires",
        "ebitda": "EBITDA",
        "reported_ebitda": "EBITDA déclaré",
        "total_assets": "Total des actifs",
        "total_debt": "Dette totale",
        "cash": "Trésorerie",
    },
}
METHOD_LABELS = {
    "dcf": "DCF / APV",
    "ebitda_multiple": "EV / EBITDA",
    "omzet_multiple": "EV / Revenue",
    "revenue_multiple": "EV / Revenue",
    "sde_multiple": "SDE",
    "adjusted_nav": "NAV",
    "holding_sotp": "Holding / SOTP",
    "upswitch_adaptive": "Upswitch Adaptive",
    "arr_multiple": "ARR",
    "real_estate_yield": "Property",
    "fiscal_4x": "Fiscal reference",
    "liquidation_analysis": "Liquidation",
    "startup_valuation": "Startup",
    "pe_ratio": "P/E",
    "owner_adaptive": "Owner Adaptive",
    "custom_weighted": "Custom weighting",
    "upswitch_adaptive_multiples_only": "Upswitch Adaptive (market)",
}


def render_assessment_html(request: GenerateAssessmentReportRequest) -> str:
    a = request.assessment
    c = COPY[request.language]
    rows = "".join(
        f'<tr><th scope="row">{escape(c.get(f.field, f.field.replace("_", " ")))}</th><td>{f.fiscal_year or "—"}</td><td>{escape(c["missing"])}</td></tr>'
        for f in sorted(a.financial_facts, key=lambda f: (f.fiscal_year or 0, f.field))
    )
    methods = ", ".join(
        dict.fromkeys(
            c.get(m.method, METHOD_LABELS.get(m.method, m.method))
            for m in sorted(a.method_exclusions, key=lambda m: m.method)
        )
    )
    return f"""<!doctype html><html lang="{request.language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(c['title'])} - {escape(a.company_name)}</title><style>
@page {{ size: A4; margin: 18mm; @bottom-right {{ content: counter(page); color:#53616a; font:9pt sans-serif; }} }}
* {{box-sizing:border-box}} body {{margin:0;color:#18323b;background:#fff;font:14px/1.55 Arial,sans-serif}} main {{max-width:960px;margin:auto;padding:40px}} header {{border-bottom:3px solid #0c6b63;padding-bottom:18px;margin-bottom:24px}} .brand {{font-size:12px;letter-spacing:.12em;color:#0c6b63}} h1 {{font-size:30px;line-height:1.2;overflow-wrap:anywhere}} h2 {{font-size:18px;break-after:avoid}} .conclusion {{font-size:19px;line-height:1.5}} .meta,footer {{font-size:11px;color:#53616a;line-height:1.6}} table {{border-collapse:collapse;width:100%;table-layout:fixed}} th,td {{padding:8px;border-bottom:1px solid #dbe4e6;text-align:left;overflow-wrap:anywhere}} thead {{display:table-header-group}} tr {{break-inside:avoid}} section {{margin-top:24px}} footer {{border-top:1px solid #dbe4e6;margin-top:28px;padding-top:10px;overflow-wrap:anywhere}} @media(max-width:600px) {{main {{padding:20px}} h1 {{font-size:24px}} .conclusion {{font-size:17px}} table {{font-size:12px}}}} @media print {{body {{font-size:13px;line-height:1.45}} main {{padding:0}} header {{padding-bottom:12px;margin-bottom:16px}} h1 {{font-size:28px;margin:12px 0}} h2 {{font-size:16px;margin:0 0 8px}} p {{margin:8px 0}} section {{margin-top:16px}} th,td {{padding:6px}} .conclusion {{font-size:17px}} footer {{margin-top:18px}} footer h2 {{font-size:14px}}}}
</style></head><body><main><header><p class="brand">UPSWITCH</p><h1>{escape(a.company_name)}</h1><p>{escape(c['title'])}</p><p class="meta">{escape(c['date'])}: {escape(a.assessed_at[:10])} · {escape(a.country_code)} · {escape(c['currency'])}: {escape(a.currency or c['missing'])}</p></header><p class="conclusion">{escape(c['conclusion'])}</p><section><h2>{escape(c['basis'])}</h2><table><thead><tr><th>{escape(c['field'])}</th><th>{escape(c['period'])}</th><th>{escape(c['value'])}</th></tr></thead><tbody>{rows}</tbody></table></section><section><h2>{escape(c['methods'])}</h2><p>{escape(c['method_note'])}</p><p class="meta">{escape(methods)}</p></section><section><h2>{escape(c['next'])}</h2><p>{escape(c['next_text'])}</p></section><footer><h2>{escape(c['scope'])}</h2><p>{escape(c['scope_text'])}</p><p>{escape(c['identity'])}: {escape(a.assessment_hash)}<br>{escape(a.policy_version)} · {escape(a.evidence_revision_id)}</p></footer></main></body></html>"""


def _deny_external_resource(url: str, *args: object, **kwargs: object) -> NoReturn:
    raise ValueError("Assessment reports do not load external resources")


def generate_assessment_report(
    request: GenerateAssessmentReportRequest,
) -> AssessmentReportResponse:
    # Revalidate even an in-process model_copy/construct; mutable nested lists
    # cannot silently change a previously sealed assessment.
    request = GenerateAssessmentReportRequest.model_validate(request.model_dump(mode="json"))
    html = render_assessment_html(request)
    pdf = None
    if request.include_pdf:
        from weasyprint import HTML

        pdf = HTML(string=html, url_fetcher=_deny_external_resource).write_pdf()
    a = request.assessment
    manifest = {
        "schema_version": "assessment_report_manifest.v1",
        **{
            field: getattr(a, field)
            for field in (
                "report_id",
                "workspace_id",
                "assessment_id",
                "assessment_hash",
                "evidence_revision_id",
                "evidence_snapshot_hash",
            )
        },
        "valuation_run_id": None,
        "valuation_run_hash": None,
        "language": request.language,
        "template_version": "financial_basis_assessment_report.v1",
        "html_sha256": hashlib.sha256(html.encode()).hexdigest(),
        "pdf_sha256": hashlib.sha256(pdf).hexdigest() if pdf is not None else None,
    }
    manifest["manifest_hash"] = assessment_hash(manifest)
    return AssessmentReportResponse(
        assessment=a,
        report_manifest=manifest,
        html_report=html,
        pdf_base64=base64.b64encode(pdf).decode() if pdf is not None else None,
    )
