"""Render a distinct acquisition report on the authoritative ValuationIQ document base."""

import base64
import re
from pathlib import Path
from src.domain.acquisition_shortlist import AcquisitionShortlistSnapshot
from src.services.infrastructure.template_service import get_template_service
from src.services.infrastructure.pdf.font_css import get_pdf_font_face_css
from src.services.infrastructure.pdf_generator import get_pdf_generator
from src.services.reports.shortlist_chart import shortlist_chart

COPY = {
    "en": dict(
        title="Acquisition shortlist",
        prepared="Prepared for",
        brief="Agreed mandate",
        comparison="The shortlist",
        candidates="Candidate dossiers",
        sources="Sources & research record",
        next="Next investigation",
        evidence="Criteria & evidence",
        financials="Financial evidence",
        valuation="Indicative valuation evidence",
        unknown="Not available",
        meets="Supported",
        fails="Not met",
        unresolved="Unresolved",
        essential="Essential",
        preference="Preference",
        company="Company",
        fit="Why it fits",
        period="Period",
        turnover="Turnover",
        ebitda="EBITDA",
        profit="Operating profit",
        checked="Checked",
        asof="As of",
        confidential="Confidential",
        page="Page",
        of="of",
        version="Version",
        limitations="Research identifies candidates for investigation. Inclusion does not establish that a company is for sale. Financial momentum does not establish owner intent.",
        unavailable="The available filing does not establish this metric.",
        scope="Research coverage",
        source="Source",
        identity="Legal identity",
        summary="Match explanation",
        open="Open company research",
        actions="Unresolved questions & next steps",
        no_open="No unresolved criteria in the agreed mandate.",
        sample="Illustrative sample",
        sample_note="All companies, figures and source records in this example are fictional. Evidence states demonstrate the product; they are not findings about real businesses.",
        latest="Latest available period",
        essentials="Essential criteria supported",
        read="Read dossier",
    ),
    "nl": dict(
        title="Overnameshortlist",
        prepared="Opgesteld voor",
        brief="Overeengekomen mandaat",
        comparison="De shortlist",
        candidates="Bedrijfsdossiers",
        sources="Bronnen & onderzoeksdossier",
        next="Volgende onderzoeksstap",
        evidence="Criteria & onderbouwing",
        financials="Financiële onderbouwing",
        valuation="Indicatieve waarderingsgegevens",
        unknown="Niet beschikbaar",
        meets="Onderbouwd",
        fails="Niet voldaan",
        unresolved="Onopgelost",
        essential="Vereiste",
        preference="Voorkeur",
        company="Onderneming",
        fit="Waarom deze past",
        period="Periode",
        turnover="Omzet",
        ebitda="EBITDA",
        profit="Bedrijfsresultaat",
        checked="Gecontroleerd",
        asof="Per",
        confidential="Vertrouwelijk",
        page="Pagina",
        of="van",
        version="Versie",
        limitations="Dit onderzoek identificeert kandidaten voor verdere verkenning. Opname betekent niet dat een onderneming te koop staat. Financiële ontwikkeling bewijst geen verkoopintentie.",
        unavailable="De beschikbare jaarrekening onderbouwt deze maatstaf niet.",
        scope="Onderzoeksdekking",
        source="Bron",
        identity="Juridische identiteit",
        summary="Toelichting bij de match",
        open="Open bedrijfsonderzoek",
        actions="Open vragen & volgende stappen",
        no_open="Geen onopgeloste criteria binnen het overeengekomen mandaat.",
        sample="Illustratief voorbeeld",
        sample_note="Alle bedrijven, cijfers en brongegevens in dit voorbeeld zijn fictief. De bewijsstatussen tonen het product en zijn geen bevindingen over echte bedrijven.",
        latest="Meest recente beschikbare periode",
        essentials="Onderbouwde vereisten",
        read="Lees dossier",
    ),
    "fr": dict(
        title="Sélection d’acquisitions",
        prepared="Préparée pour",
        brief="Mandat convenu",
        comparison="La sélection",
        candidates="Dossiers des entreprises",
        sources="Sources et dossier de recherche",
        next="Prochaine étape de recherche",
        evidence="Critères et justificatifs",
        financials="Données financières",
        valuation="Éléments de valorisation indicative",
        unknown="Non disponible",
        meets="Étayé",
        fails="Non satisfait",
        unresolved="À vérifier",
        essential="Exigence",
        preference="Préférence",
        company="Entreprise",
        fit="Pourquoi elle correspond",
        period="Période",
        turnover="Chiffre d’affaires",
        ebitda="EBITDA",
        profit="Résultat d’exploitation",
        checked="Vérifié",
        asof="Au",
        confidential="Confidentiel",
        page="Page",
        of="sur",
        version="Version",
        limitations="Cette recherche identifie des candidats à examiner. Leur inclusion ne signifie pas que l’entreprise est à vendre. L’évolution financière ne démontre pas l’intention du propriétaire.",
        unavailable="Les comptes disponibles ne permettent pas d’établir cet indicateur.",
        scope="Périmètre de recherche",
        source="Source",
        identity="Identité juridique",
        summary="Justification de la correspondance",
        open="Ouvrir la recherche",
        actions="Questions ouvertes et prochaines étapes",
        no_open="Aucun critère non résolu dans le mandat convenu.",
        sample="Exemple illustratif",
        sample_note="Toutes les entreprises, données et sources de cet exemple sont fictives. Les statuts illustrent le produit et ne constituent pas des conclusions sur des entreprises réelles.",
        latest="Dernière période disponible",
        essentials="Exigences étayées",
        read="Lire le dossier",
    ),
}


for language, words in {
    'en': dict(taxonomy='Business-type context; not verified for this company.', historical='Indicative valuation by accounting period', calculated='Calculated', equity_value='Equity value estimate', enterprise_value='Enterprise value estimate', net_asset_reference='Net-asset reference'),
    'nl': dict(taxonomy='Context van het bedrijfstype; niet geverifieerd voor deze onderneming.', historical='Indicatieve waardering per boekhoudperiode', calculated='Berekend', equity_value='Indicatieve aandelenwaarde', enterprise_value='Indicatieve ondernemingswaarde', net_asset_reference='Referentie nettoactief'),
    'fr': dict(taxonomy='Contexte du type d’activité ; non vérifié pour cette entreprise.', historical='Valorisation indicative par période comptable', calculated='Calculée', equity_value='Valeur indicative des capitaux propres', enterprise_value='Valeur indicative d’entreprise', net_asset_reference='Référence d’actif net'),
}.items():
    COPY[language].update(words)


def report_number(value: float | None, locale: str) -> str:
    if value is None:
        return "—"
    grouped = f"{value:,.0f}"
    return grouped.replace(",", "." if locale == "nl" else "\u202f" if locale == "fr" else ",")


def render_shortlist_html(
    snapshot: AcquisitionShortlistSnapshot, variant: str = "screen", *, illustrative: bool = False
) -> str:
    t = COPY[snapshot.locale]
    # Enumerate sources in reading order. Reuse dates only when the financial
    # reference unambiguously identifies one reviewed source record.
    sources = []
    source_numbers = {}
    financial_source_numbers = {}
    known_sources = {}
    for c in snapshot.candidates:
        for source in list(c.identitySources) + [s for a in c.criteria for s in a.sources] + [s for f in c.businessProfile for s in f.sources] + [s for p in c.valuationHistory for s in p.sources]:
            known_sources[(source.url, source.checkedOn, source.asOf)] = source.model_dump()

    def add_source(record):
        key = (record['url'], record['checkedOn'], record['asOf'])
        if key not in source_numbers:
            source_numbers[key] = len(sources) + 1
            sources.append(record)
        return source_numbers[key]

    def source_number(source):
        return source_numbers[(source.url, source.checkedOn, source.asOf)]

    def source_references(refs):
        seen = set()
        result = []
        for source in refs:
            number = source_number(source)
            if number not in seen:
                seen.add(number)
                result.append(source)
        return result

    for c in snapshot.candidates:
        for source in c.identitySources:
            add_source(source.model_dump())
        for finding in c.businessProfile:
            for source in finding.sources:
                add_source(source.model_dump())
        for point in c.valuationHistory:
            for source in point.sources:
                add_source(source.model_dump())
        for index, financial in enumerate(c.financials):
            if not financial.sourceUrl:
                continue
            period = financial.periodEnd or (str(financial.year) if financial.year else None)
            matches = [record for record in known_sources.values()
                       if record['url'] == financial.sourceUrl and record['asOf'] == period]
            record = matches[0] if len(matches) == 1 else dict(
                title=financial.source or t['source'], url=financial.sourceUrl,
                checkedOn=None, asOf=period)
            financial_source_numbers[(c.key, index)] = add_source(record)
        for criterion in c.criteria:
            for source in criterion.sources:
                add_source(source.model_dump())
    base_t = dict(
        cover_estimate_label=t["title"],
        footer_confidential=t["confidential"],
        footer_indicative_estimate=t["title"],
        footer_page=t["page"],
        footer_of=t["of"],
    )
    fonts = get_pdf_font_face_css()
    if variant == "screen":
        # Browser previews use the very same bundled faces, with no external font requests.
        def embed(match):
            path = Path(match.group(1).removeprefix("file://"))
            mime = "font/woff2" if path.suffix == ".woff2" else "font/ttf"
            return (
                "url('data:"
                + mime
                + ";base64,"
                + base64.b64encode(path.read_bytes()).decode()
                + "')"
            )

        # Only the primary faces are needed in the browser; its Unicode fallback remains available.
        fonts = "\n".join(
            block + "}" for block in fonts.split("}") if "Noto" not in block and block.strip()
        )
        fonts = re.sub(r"url\('([^']+)'\)", embed, fonts)
    env = get_template_service().env
    if env is None:
        raise RuntimeError("Report templates unavailable")
    html = env.get_template("acquisition_shortlist/report.html").render(
        base_template=f"main_report{'_pdf' if variant == 'pdf' else ''}/base.html",
        s=snapshot,
        copy=t,
        t=base_t,
        company_name=t["sample"] if illustrative else snapshot.organization,
        locale=snapshot.locale,
        pdf_font_face_css=fonts,
        shortlist_fonts=fonts,
        sources=sources,
        source_number=source_number,
        source_references=source_references,
        financial_source_numbers=financial_source_numbers,
        charts={c.key: shortlist_chart(c.valuationHistory) for c in snapshot.candidates},
        variant=variant,
        report_number=lambda value: report_number(value, snapshot.locale),
        report_certification_footer_label=t["title"],
        accountant_firm_name="Upswitch",
        illustrative=illustrative,
        latest_financials={
            c.key: max(
                c.financials,
                key=lambda f: (f.periodEnd or str(f.year or "")),
                default=None,
            )
            for c in snapshot.candidates
        },
    )
    if variant == "screen":
        html = re.sub(r"@import url\([^;]+;", "", html)
        policy = "default-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src data:; base-uri 'none'; form-action 'none'"
        html = html.replace(
            "<head>",
            '<head><meta http-equiv="Content-Security-Policy" content="' + policy + '">',
            1,
        )
    return html


def render_shortlist(snapshot: AcquisitionShortlistSnapshot, *, illustrative: bool = False):
    html = render_shortlist_html(snapshot, "screen", illustrative=illustrative)
    pdf_html = render_shortlist_html(snapshot, "pdf", illustrative=illustrative)
    pdf = get_pdf_generator().generate_pdf(pdf_html)
    return html, pdf
