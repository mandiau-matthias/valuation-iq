"""Source citations and currency admission for sealed reports."""

from __future__ import annotations

from src.api.schemas.stateless_report_schemas import GenerateReportRequest
from src.services.reports.report_external_reference_context import (
    _as_report_mapping as _as_report_mapping,
)


class UnsupportedCanonicalReportCurrency(ValueError):
    """Raised when euro-specific templates would mislabel a canonical run."""


def _assert_canonical_report_currency_supported(
    request: GenerateReportRequest,
) -> None:
    """Prevent the legacy euro templates from relabelling another currency.

    Structured API/graph results remain currency-agnostic.  The current HTML
    and PDF template family contains euro-specific presentation helpers, so a
    canonical non-EUR run must be converted with an explicit FX snapshot before
    it can be rendered.  Failing closed is preferable to a pristine but false
    currency label.
    """

    run = request.valuation_result.valuation_run
    if run is None:
        return
    if run.currency != "EUR":
        raise UnsupportedCanonicalReportCurrency(
            "Canonical report rendering currently supports EUR only; provide "
            "an explicit, source-dated FX conversion before generating HTML/PDF."
        )


def _client_indicative_source_references(
    request: GenerateReportRequest,
    run: object,
) -> list[object]:
    """Project a concise client bibliography from the immutable run only.

    A canonical accounting package can contain dozens of field-level citations.
    Those citations remain in the restricted run, evidence register and report
    data, but repeating every fact locator in a client PDF is neither useful nor
    readable.  This projection groups the same sealed evidence by filing and
    appends only the market and WACC contracts that actually informed the run.
    """

    locale = str(request.language or "en").strip().lower()[:2]
    labels = {
        "nl": {
            "uploaded": "Verzegeld financieel dossier",
            "uploaded_use": (
                "Aangeleverde actuals en regulatorreconciliatie die in de "
                "immutable waarderingsrun zijn vastgelegd."
            ),
            "filing_use": "Ingediende jaarrekening gebruikt voor bronreconciliatie.",
            "market_use": (
                "Niet-statistische externe marktreferentie; geen Index-percentielen "
                "of steekproefclaim."
            ),
            "market_use_sample_disclosed": (
                "Niet-statistische externe marktreferentie; geen Index-percentielen; "
                "de celspecifieke steekproefomvang is niet door de bron gepubliceerd."
            ),
            "context_use": "Externe sectorcontext en reasonableness check; geen zelfstandig waarderingsanker.",
            "wacc": "Direct toegepaste sector-WACC",
            "wacc_use": "Publieke sector-WACC die rechtstreeks in de DCF is toegepast.",
            "methodology_use": "Methodologische toelichting bij de rechtstreeks toegepaste sector-WACC.",
            "crosscheck_use": "Corroboratieve WACC-redelijkheidstoets; niet afzonderlijk geprijsd.",
            "market_crosscheck_use": (
                "Actuele markttoets (corroboratief); vervangt de verzegelde "
                "marktreferentie niet."
            ),
            "regulatory_use": "Regulatoire context voor vergunning en overdrachtsdiligence; geen waarderingsinput.",
        },
        "fr": {
            "uploaded": "Dossier financier scellé",
            "uploaded_use": (
                "Données historiques fournies et rapprochement réglementaire "
                "scellés dans le calcul immuable."
            ),
            "filing_use": "Comptes annuels déposés utilisés pour le rapprochement des sources.",
            "market_use": (
                "Référence de marché externe non statistique; aucun percentile Index "
                "ni taille d’échantillon revendiqués."
            ),
            "market_use_sample_disclosed": (
                "Référence de marché externe non statistique; aucun percentile Index; "
                "la taille d’échantillon spécifique à la cellule n’est pas publiée par la source."
            ),
            "context_use": "Contexte sectoriel externe et contrôle de cohérence; aucun ancrage autonome.",
            "wacc": "WACC sectoriel appliqué directement",
            "wacc_use": "WACC sectoriel public appliqué directement dans le DCF.",
            "methodology_use": "Méthodologie du WACC sectoriel directement appliqué.",
            "crosscheck_use": "Contrôle de cohérence du WACC; non valorisé séparément.",
            "market_crosscheck_use": (
                "Contrôle de marché actuel (corroboratif); ne remplace pas la "
                "référence de marché scellée."
            ),
            "regulatory_use": "Contexte réglementaire pour le permis et la due diligence; aucune donnée de valorisation.",
        },
        "en": {
            "uploaded": "Sealed financial dossier",
            "uploaded_use": (
                "Submitted actuals and regulatory reconciliation committed to the "
                "immutable valuation run."
            ),
            "filing_use": "Filed annual accounts used for source reconciliation.",
            "market_use": (
                "Non-statistical external market reference; no Index percentile or "
                "sample-size claim."
            ),
            "market_use_sample_disclosed": (
                "Non-statistical external market reference; no Index percentiles; "
                "the cell-specific sample size is not published by the source."
            ),
            "context_use": "External sector context and reasonableness check; not a standalone valuation anchor.",
            "wacc": "Directly applied sector WACC",
            "wacc_use": "Public sector WACC applied directly in the DCF.",
            "methodology_use": "Methodology for the directly applied sector WACC.",
            "crosscheck_use": "Corroborative WACC reasonableness check; not separately priced.",
            "market_crosscheck_use": (
                "Current market cross-check (corroborative); does not replace the "
                "sealed market reference."
            ),
            "regulatory_use": "Regulatory context for permit and transfer diligence; not a valuation input.",
        },
    }[locale if locale in {"nl", "fr"} else "en"]

    references: list[object] = []
    uploaded = _as_report_mapping(getattr(run, "uploaded_data_snapshot", None))
    if uploaded:
        references.append(
            {
                "title": labels["uploaded"],
                "document_hash": uploaded.get("snapshot_hash"),
                "use": labels["uploaded_use"],
            }
        )

    filings: dict[tuple[int, str], dict[str, object]] = {}
    context_sources: dict[str, dict[str, object]] = {}
    for raw in getattr(run, "source_citations", None) or []:
        citation = _as_report_mapping(raw)
        source_kind = str(citation.get("source_kind") or "").strip()
        if source_kind in {
            "wacc_methodology",
            "wacc_crosscheck",
            "market_crosscheck",
            "regulatory_context",
        }:
            context_sources[source_kind] = citation
        source_id = str(citation.get("source_id") or "")
        parts = source_id.split(":")
        if len(parts) >= 4 and parts[0] == "restricted" and parts[2].isdigit():
            filing_id = parts[1].strip()
            if filing_id.upper().startswith("NBB-"):
                filings[(int(parts[2]), filing_id)] = citation
                continue
        title = str(citation.get("title") or "")
        if source_kind == "regulator_filing":
            for token in title.replace("—", " ").split():
                if token.isdigit() and len(token) == 4:
                    filings[(int(token), str(citation.get("source_id") or title))] = citation
                    break
    # Present one readable regulator row while retaining every PDF/CSV/XBRL
    # locator and hash in the restricted run. This leaves room for the sealed
    # methodology, cross-check and regulatory sources the client needs.
    if filings:
        years = sorted({year for year, _ in filings})
        years_label = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
        references.append(
            {
                "title": f"NBB/CBSO jaarrekeningen {years_label}",
                "url": "https://consult.cbso.nbb.be/",
                "use": labels["filing_use"],
            }
        )

    multiples_results = _as_report_mapping(getattr(run, "multiples_results", None))
    market_contract = _as_report_mapping(
        multiples_results.get("external_market_reference_contract")
    )
    market_sources = market_contract.get("sources")
    if isinstance(market_sources, list):
        # A contract may carry several observation CELLS from one document
        # (applied cell, corridor low, outer stress). The bibliography lists
        # DOCUMENTS, so project one row per distinct title: the primary
        # reference first, then the first differently-titled context source.
        seen_titles: set[str] = set()
        distinct_sources: list[dict[str, object]] = []
        for raw in market_sources:
            source = _as_report_mapping(raw)
            if not source:
                continue
            title = str(source.get("source_title") or "External market reference")
            if title in seen_titles:
                continue
            seen_titles.add(title)
            distinct_sources.append(source)
            if len(distinct_sources) == 2:
                break
        for index, source in enumerate(distinct_sources):
            # "No sample-size claim" is imprecise when the source DOES publish
            # its total survey basis and only the cell count is undisclosed —
            # say exactly that whenever the sealed contract carries a
            # sample_disclosure.
            primary_use = (
                labels["market_use_sample_disclosed"]
                if source.get("sample_disclosure")
                else labels["market_use"]
            )
            references.append(
                {
                    "title": source.get("source_title") or "External market reference",
                    "url": source.get("source_url"),
                    "document_hash": source.get("content_sha256"),
                    "published_at": source.get("published_on"),
                    "use": primary_use if index == 0 else labels["context_use"],
                }
            )

    dcf_results = _as_report_mapping(getattr(run, "dcf_results", None))
    wacc_contract = _as_report_mapping(dcf_results.get("wacc_evidence_contract"))
    if wacc_contract:
        period = str(wacc_contract.get("period") or "").strip()
        title = labels["wacc"] + (f" ({period})" if period else "")
        references.append(
            {
                "title": title,
                "url": wacc_contract.get("source_url"),
                "document_hash": wacc_contract.get("content_sha256"),
                "locator": wacc_contract.get("chart_locator"),
                "use": labels["wacc_use"],
            }
        )

    for source_kind, use_label in (
        ("market_crosscheck", labels["market_crosscheck_use"]),
        ("wacc_methodology", labels["methodology_use"]),
        ("wacc_crosscheck", labels["crosscheck_use"]),
        ("regulatory_context", labels["regulatory_use"]),
    ):
        context_source = context_sources.get(source_kind)
        if not context_source:
            continue
        references.append(
            {
                "title": context_source.get("title"),
                "url": context_source.get("url"),
                "document_hash": context_source.get("document_hash"),
                "published_at": context_source.get("published_at"),
                "use": use_label,
            }
        )

    # Cap raised from 8: with a market cross-check in the projection the sealed
    # dossier + filings + 2 market sources + WACC trio + regulatory row already
    # occupy 8 rows, and the cap silently dropped the newest citations.
    return references[:10]


def _sealed_source_references(request: GenerateReportRequest) -> list[object]:
    """Prefer source citations committed to the immutable calculation run."""
    run = request.valuation_result.valuation_run
    if run is None:
        return list(request.source_references)
    if request.report_scope == "client_indicative":
        return _client_indicative_source_references(request, run)
    citations = getattr(run, "source_citations", None)
    if citations is None:
        # ``model_construct`` legacy/unit snapshots can omit the v2 field.
        # They are not an authority to erase the request's legacy sources.
        return list(request.source_references)
    return [
        citation.model_dump(mode="json") if hasattr(citation, "model_dump") else dict(citation)
        for citation in citations
    ]
