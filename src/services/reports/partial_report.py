"""Immutable partial-input financial reports, including EV-only and deficit results."""

import base64
import hashlib
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from html import escape

from src.api.schemas.partial_report import (
    GeneratePartialReportRequest,
    PartialReportManifest,
    PartialReportResponse,
)
from src.services.reports.assessment_report import METHOD_LABELS
from src.services.reports.partial_source_policy import FORECAST_REQUIRED, SOURCE_REQUIRED

COPY = {
    "en": [
        "Automatic indicative assessment",
        "Financial inputs",
        "Method results",
        "Enterprise value",
        "Shareholder value",
        "Low",
        "Base",
        "High",
        "Not supplied",
        "Evidence and limitations",
        "Eligible",
        "Excluded",
        "Source",
        "Fiscal year",
        "Annual actual",
        "Annual forecast",
        "Standalone 100% control value. Methods are shown individually; no blended range is invented. This is an indicative assessment, not a certification.",
    ],
    "nl": [
        "Automatische indicatieve beoordeling",
        "Financiële invoer",
        "Methoderesultaten",
        "Ondernemingswaarde",
        "Aandeelhouderswaarde",
        "Laag",
        "Basis",
        "Hoog",
        "Niet aangeleverd",
        "Bewijs en beperkingen",
        "Toepasbaar",
        "Uitgesloten",
        "Bron",
        "Boekjaar",
        "Jaarcijfers",
        "Jaarprognose",
        "Zelfstandige waarde voor 100% zeggenschap. Methoden worden afzonderlijk getoond; er wordt geen gecombineerde bandbreedte verzonnen. Dit is een indicatieve beoordeling, geen certificering.",
    ],
    "fr": [
        "Évaluation indicative automatique",
        "Données financières",
        "Résultats par méthode",
        "Valeur d’entreprise",
        "Valeur des actionnaires",
        "Basse",
        "Base",
        "Haute",
        "Non fourni",
        "Preuves et limites",
        "Applicable",
        "Exclue",
        "Source",
        "Exercice",
        "Comptes annuels",
        "Prévisions annuelles",
        "Valeur autonome pour 100 % du contrôle. Les méthodes sont présentées séparément ; aucune fourchette combinée n’est inventée. Il s’agit d’une évaluation indicative, pas d’une certification.",
    ],
}
METRICS = {
    "en": [
        "Revenue",
        "EBITDA",
        "Unrestricted cash",
        "Financial debt",
        "Working-capital adjustment",
    ],
    "nl": [
        "Omzet",
        "EBITDA",
        "Vrij beschikbare kasmiddelen",
        "Financiële schuld",
        "Werkkapitaalcorrectie",
    ],
    "fr": [
        "Chiffre d’affaires",
        "EBITDA",
        "Trésorerie disponible",
        "Dette financière",
        "Ajustement du fonds de roulement",
    ],
}

NOTES = {
    "No applicable country/currency methodology pack at the measurement date; no numerical method is eligible. No implicit FX conversion is applied.": (
        "Op de waarderingsdatum is geen passend methodologiepakket voor het land en de valuta beschikbaar; geen numerieke methode is toepasbaar. Er wordt geen valutaconversie verondersteld.",
        "Aucun cadre méthodologique applicable au pays et à la devise n’est disponible à la date d’évaluation ; aucune méthode chiffrée n’est admissible. Aucune conversion de change implicite n’est appliquée.",
    ),
    SOURCE_REQUIRED: (
        "Geverifieerde brongegevens zijn vereist. Aangeleverde bedragen, referenties en adviseursaannames blijven diagnostische scenario’s buiten de gepubliceerde waarderingsmethoden.",
        "Des sources vérifiées sont requises. Les montants, références et hypothèses du conseiller restent des scénarios diagnostiques exclus des méthodes de valorisation publiées.",
    ),
    FORECAST_REQUIRED: (
        "Een geverifieerde bedrijfsprognose of kasstroomplanning is vereist voor een DCF-waardering. Een adviseursaanname of een ongeverifieerd document volstaat niet als bronverificatie.",
        "Une prévision d’entreprise ou un échéancier de trésorerie vérifié est requis pour une valorisation DCF. Une hypothèse du conseiller ou un document non vérifié ne constitue pas une vérification de la source.",
    ),
    "Enterprise-value methods cannot report shareholder value until financial debt, unrestricted cash and the NWC adjustment are supplied.": (
        "Methoden voor ondernemingswaarde kunnen pas aandeelhouderswaarde rapporteren als financiële schuld, vrij beschikbare kasmiddelen en de werkkapitaalcorrectie zijn aangeleverd.",
        "Les méthodes de valeur d’entreprise ne peuvent présenter la valeur des actionnaires sans dette financière, trésorerie disponible et ajustement du fonds de roulement.",
    ),
    "The earnings period is unknown; earnings multiples are unavailable.": (
        "De winstperiode is onbekend; winst- en omzetmultiples zijn niet beschikbaar.",
        "La période des résultats est inconnue ; les multiples ne sont pas disponibles.",
    ),
    "Supplied-input scenarios support indicative arithmetic only. Country-specific accounting, tax applicability, market evidence and professional certification are not verified by this calculation.": (
        "Scenario’s met aangeleverde gegevens ondersteunen alleen indicatieve berekeningen. Landspecifieke boekhouding, fiscale toepasselijkheid, marktgegevens en professionele certificering worden door deze berekening niet geverifieerd.",
        "Les scénarios fondés sur les données fournies permettent uniquement des calculs indicatifs. La comptabilité locale, l’applicabilité fiscale, les données de marché et la certification professionnelle ne sont pas vérifiées par ce calcul.",
    ),
    "Required method-specific financial or market evidence is unavailable.": (
        "Vereiste financiële gegevens of marktgegevens voor deze methode ontbreken.",
        "Les données financières ou de marché nécessaires à cette méthode sont indisponibles.",
    ),
    "Reference currency, country or earnings period is incompatible.": (
        "De valuta, het land of de periode van de referentie is niet verenigbaar.",
        "La devise, le pays ou la période de la référence est incompatible.",
    ),
    "Forecast currency is incompatible; no implicit FX conversion.": (
        "De prognosevaluta is niet verenigbaar; er wordt geen valutaconversie verondersteld.",
        "La devise des prévisions est incompatible ; aucune conversion de change n’est supposée.",
    ),
    "Appraisal currency or measurement date is incompatible.": (
        "De taxatievaluta of waarderingsdatum is niet verenigbaar.",
        "La devise ou la date de l’évaluation des actifs est incompatible.",
    ),
    "Net asset deficit is preserved.": (
        "Het tekort aan nettoactiva blijft zichtbaar.",
        "Le déficit de l’actif net est conservé.",
    ),
    "No positive enterprise value.": (
        "Geen positieve ondernemingswaarde.",
        "Aucune valeur d’entreprise positive.",
    ),
    "Shareholder value is unavailable until financial debt, unrestricted cash and the NWC adjustment are supplied.": (
        "De aandeelhouderswaarde is niet beschikbaar totdat financiële schuld, vrij beschikbare kasmiddelen en de werkkapitaalcorrectie zijn aangeleverd.",
        "La valeur des actionnaires est indisponible tant que la dette financière, la trésorerie disponible et l’ajustement du fonds de roulement ne sont pas fournis.",
    ),
    "DCF prices the supplied unlevered forecast at annual interval ends; no APV financing benefit or inferred tax/reinvestment is added.": (
        "DCF waardeert de aangeleverde kasstroomprognose zonder financiering aan het einde van elk jaar. Er worden geen APV-financieringsvoordelen of veronderstelde belastingen of herinvesteringen toegevoegd.",
        "Le DCF valorise les flux fournis hors financement en fin d’année. Aucun avantage de financement APV ni impôt ou réinvestissement supposé n’est ajouté.",
    ),
    "Net asset value uses supplied fair values, all liabilities, disposal costs and tax latencies; no second EV-to-equity bridge is applied.": (
        "De nettoactivawaarde gebruikt aangeleverde reële waarden, alle verplichtingen, verkoopkosten en belastinglatenties. Er volgt geen tweede correctie van ondernemingswaarde naar aandeelhouderswaarde.",
        "L’actif net utilise les justes valeurs fournies, tous les passifs, les frais de cession et les impôts latents. Aucun second passage de la valeur d’entreprise aux capitaux propres n’est appliqué.",
    ),
    "This country has no enabled methodology pack; no numerical method is eligible.": (
        "Voor dit land is geen methodologiepakket beschikbaar; geen numerieke methode is toepasbaar.",
        "Aucun cadre méthodologique n’est disponible pour ce pays ; aucune méthode chiffrée n’est applicable.",
    ),
}

MULTILINGUAL_REASONS = {
    "Na aftrek van schulden resteert er geen positieve aandeelhouderswaarde.": (
        "No positive shareholder value remains after the cash/debt bridge; the deficit is retained.",
        "Na de kas- en schuldcorrectie blijft geen positieve aandeelhouderswaarde over; het tekort blijft zichtbaar.",
        "Après le passage par la trésorerie et la dette, aucune valeur positive des actionnaires ne subsiste ; le déficit est conservé.",
    ),
    "EBITDA is nul of negatief — multiples-methode vereist positieve EBITDA.": (
        "EBITDA is zero or negative; this multiple method requires positive EBITDA.",
        "EBITDA is nul of negatief; deze multiplemethode vereist positieve EBITDA.",
        "L’EBITDA est nul ou négatif ; cette méthode par multiple nécessite un EBITDA positif.",
    ),
    "Omzetmultiple kan niet worden toegepast bij €0 omzet.": (
        "The revenue multiple cannot price an observed zero revenue.",
        "De omzetmultiple kan niet worden toegepast bij een waargenomen nulomzet.",
        "Le multiple du chiffre d’affaires ne peut pas valoriser un chiffre d’affaires observé nul.",
    ),
}


def localized_note(note: str, language: str) -> str:
    index = {"en": 0, "nl": 1, "fr": 2}[language]
    if note in MULTILINGUAL_REASONS:
        return MULTILINGUAL_REASONS[note][index]
    if language == "en":
        return note
    if note in NOTES:
        return NOTES[note][index - 1]
    for metric in ("revenue", "ebitda"):
        missing = f"{metric} is missing; it is not an observed zero."
        name = (
            ("Omzet" if metric == "revenue" else "EBITDA")
            if language == "nl"
            else ("Le chiffre d’affaires" if metric == "revenue" else "L’EBITDA")
        )
        if note == missing:
            return (
                f"{name} ontbreekt; dit is geen waargenomen nulwaarde."
                if language == "nl"
                else f"{name} est absent ; il ne s’agit pas d’une valeur nulle observée."
            )
        prefix = f"{metric} multiple is a disclosed assumption: "
        if note.startswith(prefix):
            suffix = note[len(prefix) :]
            return (
                f"{name}-multiple is een expliciete aanname: {suffix}"
                if language == "nl"
                else f"Le multiple ({name}) est une hypothèse déclarée : {suffix}"
            )
    return note  # User-supplied source prose stays verbatim.


def render_partial_html(request: GeneratePartialReportRequest) -> str:
    saved = request.partial_valuation
    inputs = saved.inputs
    financials = inputs.financials
    labels = COPY[request.language]

    def text(value: object) -> str:
        return escape(str(value))

    currency_missing = {
        "en": "currency not supplied",
        "nl": "valuta niet aangeleverd",
        "fr": "devise non fournie",
    }[request.language]

    def amount(value: object, currency: str | None = financials.currency) -> str:
        return (
            labels[8]
            if value is None
            else f"{text(value)} {text(currency) if currency else '(' + currency_missing + ')'}"
        )

    def discounted_amount(value: object, currency: str | None) -> str:
        if value is None:
            return labels[8]
        exact = Decimal(str(value))
        with localcontext() as context:
            context.prec = max(50, len(exact.as_tuple().digits) + 3)
            displayed = exact.quantize(Decimal(".01"), rounding=ROUND_HALF_EVEN)
        return f'<span data-exact-amount="{text(value)}">{amount(displayed, currency)}</span>'

    rows = "".join(
        f"<tr><th>{name}</th><td>{amount(getattr(financials, key))}</td></tr>"
        for name, key in zip(
            METRICS[request.language],
            ("revenue", "ebitda", "cash", "financial_debt", "nwc_adjustment"),
        )
    )
    index = {"en": 0, "nl": 1, "fr": 2}[request.language]
    ledgers = []
    forecast = inputs.fcff_forecast
    if forecast is not None:
        names = [
            (
                "Supplied unlevered forecast",
                "Aangeleverde prognose zonder financiering",
                "Prévisions fournies hors financement",
            ),
            (
                "Annual interval from valuation date",
                "Jaarinterval vanaf waarderingsdatum",
                "Intervalle annuel depuis la date d’évaluation",
            ),
            (
                "Cash taxes (subtract)",
                "Contante belastingen (aftrekken)",
                "Impôts décaissés (à déduire)",
            ),
            (
                "Depreciation and amortization (add)",
                "Afschrijvingen (optellen)",
                "Amortissements (à ajouter)",
            ),
            (
                "Capital expenditure (subtract)",
                "Investeringen (aftrekken)",
                "Investissements (à déduire)",
            ),
            (
                "Change in working capital (subtract)",
                "Mutatie werkkapitaal (aftrekken)",
                "Variation du fonds de roulement (à déduire)",
            ),
            ("FCFF", "FCFF", "FCFF"),
            (
                "Present value of FCFF",
                "Contante waarde van FCFF",
                "Valeur actualisée des FCFF",
            ),
        ]
        dcf_details = saved.methods["dcf"].details or {}
        computed_rows = {
            row["year_index"]: row
            for row in dcf_details.get("explicit_fcff_ledger", [])
            if isinstance(row, dict) and "year_index" in row
        }
        tables = []
        for year in forecast.years:
            components: list[tuple[str, object]] = [
                ("EBIT", year.ebit),
                (names[2][index], year.cash_taxes),
                (names[3][index], year.depreciation_amortization),
                (names[4][index], year.capex),
                (names[5][index], year.change_in_nwc),
            ]
            computed = computed_rows.get(year.year_index)
            if computed is not None:
                components += [
                    (names[6][index], computed.get("fcff")),
                    (names[7][index], computed.get("present_value")),
                ]
            cells = "".join(
                f"<tr><th>{text(name)}</th><td>{discounted_amount(value, forecast.currency) if name == names[7][index] else amount(value, forecast.currency)}</td></tr>"
                for name, value in components
            )
            tables.append(f"<h3>{names[1][index]}: {year.year_index}</h3><table>{cells}</table>")
        rate_label = (
            "Discount rate (decimal)",
            "Discontovoet (decimaal)",
            "Taux d’actualisation (décimal)",
        )[index]
        growth_label = (
            "Terminal growth (decimal)",
            "Eindgroei (decimaal)",
            "Croissance terminale (décimal)",
        )[index]
        no_terminal = (
            "No terminal value supplied",
            "Geen eindwaarde aangeleverd",
            "Aucune valeur terminale fournie",
        )[index]
        growth = (
            text(forecast.terminal_growth) if forecast.terminal_growth is not None else no_terminal
        )
        timing = (
            "Discounted at annual interval ends",
            "Verdisconteerd aan het einde van elk jaarinterval",
            "Actualisation en fin d’intervalle annuel",
        )[index]
        display_policy = (
            "Discounted amounts are displayed to two decimal places using half-even rounding; the saved calculation retains full precision.",
            "Contante bedragen worden met twee decimalen en half-even-afronding getoond; de opgeslagen berekening behoudt de volledige precisie.",
            "Les montants actualisés sont affichés à deux décimales avec arrondi au pair ; le calcul enregistré conserve toute sa précision.",
        )[index]
        ledgers.append(
            f"<section><h2>{names[0][index]}</h2><p>{rate_label}: {text(forecast.discount_rate)}; {growth_label}: {growth}. {timing}.</p><p>{display_policy}</p>{''.join(tables)}</section>"
        )
        if dcf_details.get("terminal_present_value") is not None:
            terminal_label = (
                "Present value of terminal cash flows",
                "Contante waarde van eindkasstromen",
                "Valeur actualisée des flux terminaux",
            )[index]
            ledgers.append(
                f"<p>{terminal_label}: {discounted_amount(dcf_details['terminal_present_value'], forecast.currency)}</p>"
            )
    assets = inputs.fair_value_assets
    if assets is not None:
        asset_names = [
            (
                "Supplied net asset bridge",
                "Aangeleverde nettoactivabrug",
                "Passage fourni à l’actif net",
            ),
            (
                "Fair value of all assets",
                "Reële waarde van alle activa",
                "Juste valeur de tous les actifs",
            ),
            (
                "All liabilities (subtract)",
                "Alle verplichtingen (aftrekken)",
                "Tous les passifs (à déduire)",
            ),
            (
                "Disposal costs (subtract)",
                "Verkoopkosten (aftrekken)",
                "Frais de cession (à déduire)",
            ),
            (
                "Tax latencies (subtract)",
                "Belastinglatenties (aftrekken)",
                "Impôts latents (à déduire)",
            ),
        ]
        asset_rows = "".join(
            f"<tr><th>{name[index]}</th><td>{amount(value, assets.currency)}</td></tr>"
            for name, value in zip(
                asset_names[1:],
                (
                    assets.fair_value_assets,
                    assets.all_liabilities,
                    assets.disposal_costs,
                    assets.tax_latencies,
                ),
            )
        )
        ledgers.append(
            f"<section><h2>{asset_names[0][index]}</h2><p>{text(assets.valuation_date)}</p><table>{asset_rows}</table></section>"
        )
    methods = []
    exclusions = []
    for key, result in saved.methods.items():
        method_label = METHOD_LABELS.get(key, result.label)
        method_label = {
            "dcf": (
                "DCF (unlevered)",
                "DCF (zonder financiering)",
                "DCF (hors financement)",
            ),
            "omzet_multiple": ("EV / Revenue", "EV / Omzet", "VE / Chiffre d’affaires"),
            "real_estate_yield": ("Property", "Vastgoed", "Immobilier"),
            "fiscal_4x": (
                "Fiscal reference",
                "Fiscale referentie",
                "Référence fiscale",
            ),
            "liquidation_analysis": ("Liquidation", "Liquidatie", "Liquidation"),
        }.get(key, (method_label, method_label, method_label))[
            {"en": 0, "nl": 1, "fr": 2}[request.language]
        ]
        if result.enterprise_value is None and result.equity_value is None:
            reason = localized_note(
                result.unavailable_reason
                or "Required method-specific financial or market evidence is unavailable.",
                request.language,
            )
            exclusions.append(f"<li><strong>{text(method_label)}</strong>: {text(reason)}</li>")
            continue
        method_rows = "".join(
            "<tr><th>"
            + basis
            + "</th>"
            + "".join(f"<td>{amount(value)}</td>" for value in values)
            + "</tr>"
            for basis, values in (
                (
                    labels[3],
                    (
                        result.enterprise_value_low,
                        result.enterprise_value,
                        result.enterprise_value_high,
                    ),
                ),
                (
                    labels[4],
                    (
                        result.equity_value_low,
                        result.equity_value,
                        result.equity_value_high,
                    ),
                ),
            )
        )
        details = result.details or {}
        reference = details.get("reference_source") or details.get("forecast_source")
        range_basis = details.get("range_basis")
        notes = [
            (
                localized_note(result.unavailable_reason, request.language)
                if result.unavailable_reason
                else None
            ),
            reference,
        ]
        if isinstance(range_basis, dict):
            kind = range_basis.get("kind")
            range_labels = {
                "supplied_multiple_bounds": (
                    "Supplied multiple bounds; no statistical coverage is established.",
                    "Aangeleverde multiplegrenzen; statistische dekking is niet vastgesteld.",
                    "Bornes des multiples fournies ; aucune couverture statistique n’est établie.",
                ),
                "assumed_multiple_spread": (
                    "Missing multiple bounds use an assumed spread; no statistical coverage is established.",
                    "Ontbrekende multiplegrenzen gebruiken een aangenomen spreiding; statistische dekking is niet vastgesteld.",
                    "Les bornes manquantes utilisent un écart supposé ; aucune couverture statistique n’est établie.",
                ),
                "point_only": (
                    "Point estimate only; no sensitivity range is supplied.",
                    "Puntschatting; geen gevoeligheidsbereik aangeleverd.",
                    "Estimation ponctuelle ; aucune fourchette de sensibilité n’est fournie.",
                ),
            }
            if kind in range_labels:
                notes.append(range_labels[kind][{"en": 0, "nl": 1, "fr": 2}[request.language]])
            if kind == "assumed_multiple_spread" and range_basis.get("assumed_spread") is not None:
                percentage = format(Decimal(str(range_basis["assumed_spread"])) * 100, "f")
                notes.append(
                    {
                        "en": f"Each missing bound uses {percentage}% from the base multiple; supplied bounds are retained.",
                        "nl": f"Elke ontbrekende grens gebruikt {percentage}% vanaf de basismultiple; aangeleverde grenzen blijven behouden.",
                        "fr": f"Chaque borne manquante utilise {percentage}% autour du multiple de base ; les bornes fournies sont conservées.",
                    }[request.language]
                )
        method_notes = "".join(f"<p>{text(note)}</p>" for note in notes if note)
        method_status = (
            labels[10]
            if result.available
            else {
                "en": "Calculated reference",
                "nl": "Berekende referentie",
                "fr": "Référence calculée",
            }[request.language]
        )
        methods.append(
            f"<section><h3>{text(method_label)} — {method_status}</h3><div class='table'><table><thead><tr><th></th><th>{labels[5]}</th><th>{labels[6]}</th><th>{labels[7]}</th></tr></thead><tbody>{method_rows}</tbody></table></div>{method_notes}</section>"
        )
    methods.append(
        f"<section><h3>{labels[11]}</h3><ul>{''.join(exclusions)}</ul></section>"
        if exclusions
        else ""
    )
    assumptions = "".join(
        f"<li>{text(localized_note(note, request.language))}</li>" for note in saved.assumptions
    )
    evidence_labels = {
        "en": {
            "revenue": "Revenue",
            "ebitda": "EBITDA",
            "disclosed_assumption": "Disclosed assumption",
            "supplied_market_reference": "Supplied market reference",
            "supplied_forecast": "Supplied forecast",
            "supplied_appraisal": "Supplied appraisal",
        },
        "nl": {
            "revenue": "Omzet",
            "ebitda": "EBITDA",
            "disclosed_assumption": "Expliciete aanname",
            "supplied_market_reference": "Aangeleverde marktreferentie",
            "supplied_forecast": "Aangeleverde prognose",
            "supplied_appraisal": "Aangeleverde taxatie",
        },
        "fr": {
            "revenue": "Chiffre d’affaires",
            "ebitda": "EBITDA",
            "disclosed_assumption": "Hypothèse déclarée",
            "supplied_market_reference": "Référence de marché fournie",
            "supplied_forecast": "Prévisions fournies",
            "supplied_appraisal": "Évaluation des actifs fournie",
        },
    }[request.language]
    sources = "".join(
        f"<li>{text(evidence_labels.get(ref.metric, ref.metric))}: {text(evidence_labels.get(ref.evidence_status, ref.evidence_status))} — {text(ref.source_reference)} ({text(ref.observed_on)})</li>"
        for ref in inputs.references
    )
    for evidence in (inputs.fcff_forecast, inputs.fair_value_assets):
        if evidence is not None:
            sources += f"<li>{text(evidence_labels.get(evidence.evidence_status, evidence.evidence_status))} — {text(evidence.source_reference)}</li>"
    return f"""<!doctype html><html lang="{request.language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{labels[0]}</title><style>
    @page{{size:A4;margin:16mm}} body{{font-family:'Noto Sans',sans-serif;max-width:900px;margin:auto;padding:16px;color:#17202a}}h1{{font-size:24px}}h2{{font-size:19px}}h3{{font-size:15px}}table{{width:100%;border-collapse:collapse;table-layout:fixed}}th,td{{text-align:left;border-bottom:1px solid #ccc;padding:6px;overflow-wrap:anywhere}}thead{{display:table-header-group}}tr{{break-inside:avoid}}p,li{{overflow-wrap:anywhere}}section{{margin-top:16px}}.identity{{font-size:10px;overflow-wrap:anywhere}}@media(max-width:500px){{body{{padding:8px}}th,td{{font-size:11px;padding:4px}}}}@media print{{body{{padding:0}}h3{{break-after:avoid}}}}
    </style></head><body><h1>{labels[0]}</h1><h2>{text(inputs.company_name)}</h2><p>{labels[16]}</p><p>{labels[13]}: {financials.fiscal_year if financials.fiscal_year is not None else labels[8]} — {labels[14] if financials.period_kind == 'annual_actual' else labels[15]}</p><p>{labels[12]}: {text(financials.source_reference) if financials.source_reference else labels[8]}</p><h2>{labels[1]}</h2><table>{rows}</table>{''.join(ledgers)}<h2>{labels[2]}</h2>{''.join(methods)}<h2>{labels[9]}</h2><ul>{sources}{assumptions}</ul><p class="identity">{text(request.report_id)}<br>{text(saved.assessment_id)}<br>{text(saved.content_sha256)}<br>{text(saved.evidence_revision_id)}</p></body></html>"""


async def generate_partial_report(
    request: GeneratePartialReportRequest,
) -> PartialReportResponse:
    html = render_partial_html(request)
    pdf = None
    if request.include_pdf:
        from starlette.concurrency import run_in_threadpool
        from weasyprint import HTML

        from src.services.infrastructure.pdf.font_css import get_pdf_font_face_css

        # Static bundled faces make render hosts agree; report inputs never
        # supply URLs, CSS or executable HTML.
        pdf_html = html.replace("</style>", get_pdf_font_face_css() + "</style>")
        pdf = await run_in_threadpool(lambda: HTML(string=pdf_html).write_pdf())
    saved = request.partial_valuation
    return PartialReportResponse(
        partial_valuation=saved,
        html_report=html,
        pdf_base64=base64.b64encode(pdf).decode("ascii") if pdf is not None else None,
        report_manifest=PartialReportManifest(
            report_id=request.report_id,
            assessment_id=saved.assessment_id,
            content_sha256=saved.content_sha256,
            evidence_revision_id=saved.evidence_revision_id,
            language=request.language,
            html_sha256=hashlib.sha256(html.encode()).hexdigest(),
            html_bytes=len(html.encode()),
            pdf_sha256=hashlib.sha256(pdf).hexdigest() if pdf is not None else None,
            pdf_bytes=len(pdf) if pdf is not None else None,
        ),
    )
