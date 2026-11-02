"""Stateless report-context assembly for HTML/PDF generation.

The stateless API route should orchestrate request/response behavior.  The
report-context pipeline belongs here so aggregation, method overrides,
SDE-channel enrichment, pagination flags, and formula gates evolve behind a
single service boundary.
"""

from __future__ import annotations

from src.services.reports.report_value_admission import report_decimal

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import TypeAlias, cast

from src.api.schemas.stateless_api import GenerateReportRequest
from src.api.schemas.valuation_contracts import ValuationRunV2
from src.domain.method_keys import normalize_selected_method_key
from src.domain.report_contact.sanitize import (
    sanitize_report_email,
    sanitize_report_phone,
)
from src.services.reports.formula_consistency_gate import apply_gate_to_context
from src.services.reports.canonical_auxiliary_disclosures import (
    apply_canonical_auxiliary_disclosures,
)
from src.services.reports.canonical_fallback_disclosure import canonical_fallback_disclosure
from src.services.reports.canonical_report_sensitivity import apply_multiple_report_sensitivity
from src.services.reports.transaction_readiness_context import refresh_transaction_price_bridge
from src.services.reports.growth_method_sensitivity_context import (
    apply_saved_growth_multiple_scenario,
)
from src.services.reports.method_sensitivity_context import (
    apply_saved_method_sensitivities,
)
from src.services.reports.report_assurance import report_assurance_projection
from src.services.reports.report_benchmark_context import (
    build_benchmark_provenance_snapshot,
)
from src.services.reports.report_context_finalizer import finalize_report_context
from src.services.reports.report_external_reference_context import (
    _apply_governed_external_market_context as _apply_governed_external_market_context,
)
from src.services.reports.report_external_reference_context import (
    _as_report_mapping as _as_report_mapping,
)
from src.services.reports.report_external_reference_context import (
    _decimal_or_zero as _decimal_or_zero,
)
from src.services.reports.report_external_reference_context import (
    _external_reference_country_label as _external_reference_country_label,
)
from src.services.reports.report_external_reference_context import (
    _external_reference_geography_matches as _external_reference_geography_matches,
)
from src.services.reports.report_external_reference_context import (
    _optional_decimal as _optional_decimal,
)
from src.services.reports.report_external_reference_context import (
    _reported_ebitda_maintainability_check as _reported_ebitda_maintainability_check,
)
from src.services.reports.report_external_reference_context import (
    _reported_ebitda_movement_bridge as _reported_ebitda_movement_bridge,
)
from src.services.reports.report_external_reference_context import (
    _sealed_source_reconciliation_notes as _sealed_source_reconciliation_notes,
)
from src.services.reports.stateless_priced_evidence_projection import (
    build_stateless_priced_evidence_projection,
)
from src.services.reports.transaction_readiness_context import (
    build_transaction_readiness_context,
    refresh_transaction_price_bridge,
)
from src.services.reports.valuation_assurance_status import (
    CurrentValuationAssuranceAuthority,
)
from src.services.reports.valuation_presentation import (
    honest_presentation_render_enabled,
)
from src.utils.fiscal_year import get_current_filing_year

ReportMap: TypeAlias = dict[str, object]


@dataclass(frozen=True)
class StatelessReportContext:
    template_context: ReportMap
    template_service: object


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

    references: list[dict[str, object]] = []
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
    return list[object](references[:10])


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
        (citation.model_dump(mode="json") if hasattr(citation, "model_dump") else dict(citation))
        for citation in citations
    ]


def _apply_enterprise_value_primary_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Pin an EV-primary report to the engine's canonical EV contract.

    The legacy report aggregator was built when the stateless response only
    exposed an equity headline. An explicit EV-primary request must never let
    the equity bridge leak back into EV-labelled formulas or ranges.
    """
    if request.headline_value_basis != "enterprise_value":
        return

    result = request.valuation_result
    if (
        result.enterprise_value_low is None
        or result.enterprise_value_mid is None
        or result.enterprise_value_high is None
    ):
        raise ValueError("enterprise-value report requires low/mid/high EV fields")

    ev_low = _decimal_or_zero(result.enterprise_value_low)
    ev_mid = _decimal_or_zero(result.enterprise_value_mid)
    ev_high = _decimal_or_zero(result.enterprise_value_high)
    eq_low = _decimal_or_zero(result.equity_value_low)
    eq_mid = _decimal_or_zero(result.equity_value_mid)
    eq_high = _decimal_or_zero(result.equity_value_high)
    metrics = result.financial_metrics or {}
    debt = _decimal_or_zero(metrics.get("total_debt"))
    cash = _decimal_or_zero(metrics.get("cash"))
    net_debt = debt - cash

    context.update(
        {
            "valuation": float(ev_mid),
            "valuation_low": float(ev_low),
            "valuation_high": float(ev_high),
            "enterprise_value_mid": float(ev_mid),
            "enterprise_value_low": float(ev_low),
            "enterprise_value_high": float(ev_high),
            "equity_value": float(eq_mid),
            "equity_value_low": float(eq_low),
            "equity_value_high": float(eq_high),
            "upswitch_adaptive_value": float(ev_mid),
            "valuation_band_is_meaningful": ev_low < ev_high,
            "equity_value_band_is_meaningful": eq_low < eq_high,
            "ev_sourced_from_engine_equity": False,
            "supports_metric_to_ev_bridge": True,
            "total_debt": float(debt),
            "cash_balance": float(cash),
            "net_debt": float(net_debt),
            "has_net_debt_adjustment": net_debt != 0,
            "bridge_net_debt_amount": float(abs(net_debt)),
            "bridge_net_debt_operator": "+" if net_debt < 0 else "−",
            "bridge_uses_net_cash_label": net_debt < 0,
            "show_ev_equity_bridge": True,
            "show_enterprise_to_equity_bridge": True,
        }
    )

    adaptive_method = context.get("upswitch_adaptive_method")
    if isinstance(adaptive_method, dict):
        adaptive_method = dict(adaptive_method)
        adaptive_method["value"] = str(ev_mid)
        adaptive_details = dict(cast(dict[str, object], adaptive_method.get("details") or {}))
        adaptive_details.update(
            {
                "enterprise_value_low": str(ev_low),
                "enterprise_value_mid": str(ev_mid),
                "enterprise_value_high": str(ev_high),
            }
        )
        adaptive_method["details"] = adaptive_details
        context["upswitch_adaptive_method"] = adaptive_method

    results_by_key = context.get("method_results_by_key")
    if isinstance(results_by_key, dict) and isinstance(
        results_by_key.get("upswitch_adaptive"), dict
    ):
        updated_results = dict(results_by_key)
        updated_adaptive = dict(cast(dict[str, object], results_by_key["upswitch_adaptive"]))
        updated_adaptive["value"] = str(ev_mid)
        updated_results["upswitch_adaptive"] = updated_adaptive
        context["method_results_by_key"] = updated_results

    transparency = context.get("advisor_multiple_transparency")
    if isinstance(transparency, dict):
        transparency = dict(transparency)
        transparency["equity_bridge"] = {
            "rows": [
                {"label": "Enterprise value", "amount": str(ev_mid), "operator": None},
                {
                    "label": "Add: preliminary net cash",
                    "amount": str(abs(net_debt)),
                    "operator": "+" if net_debt < 0 else "−",
                },
                {
                    "label": "Illustrative equity value",
                    "amount": str(eq_mid),
                    "operator": "=",
                },
            ],
            "disclosures": [
                "Illustrative only; restricted cash, leases, debt-like items, normalized working capital and completion accounts remain unverified."
            ],
            "reconciles": abs((ev_mid - net_debt) - eq_mid) <= Decimal("0.01"),
        }
        context["advisor_multiple_transparency"] = transparency


def _apply_disclosed_fallback_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    multiples_results = request.valuation_result.multiples_results or {}
    is_fallback = multiples_results.get("multiples_source") == "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
    context["is_disclosed_external_market_fallback"] = is_fallback
    if not is_fallback:
        return

    run = request.valuation_result.valuation_run
    if run is not None:
        context.update(
            canonical_fallback_disclosure(
                run.multiples_results or {},
                language=str(context.get("locale") or request.language or "nl"),
                business_label=request.business_type_label or request.industry,
                country=request.country_code,
            )
        )
        return

    base_multiple = _decimal_or_zero(context.get("base_multiple"))
    basis = _decimal_or_zero(context.get("valuation_basis_value"))
    business_type_id = str(
        multiples_results.get("business_type_id")
        or multiples_results.get("primary_business_type_id")
        or "selected-business-type"
    )
    market_key = f"{business_type_id} × {request.country_code}"
    segments = cast(
        list[object],
        (multiples_results.get("multiple_build_up") or {}).get("segments") or [],
    )
    first_segment = segments[0] if segments and isinstance(segments[0], dict) else {}
    category_label = str(
        cast(dict[str, object], first_segment).get("business_type_title") or request.industry
    )
    business_type_label = request.business_type_label or business_type_id.replace("_", " ").title()
    if business_type_id == "pharmacy" and (request.language or "nl").lower().startswith("nl"):
        # Preserve the canonical ID/label in the run while presenting the
        # correct client-facing Dutch activity label in an advisor report.
        business_type_label = "Apotheek"
    business_type_descriptor = business_type_label
    if request.nace_code:
        business_type_descriptor = f"{business_type_descriptor} · NACE {request.nace_code}"
    multiple_display = f"{base_multiple:.2f}".replace(".", ",")
    external_reference = multiples_results.get("disclosed_external_market_reference")
    external_reference = (
        dict(cast(dict[str, object], external_reference))
        if isinstance(external_reference, dict)
        else None
    )
    reference_summary = (
        str(external_reference.get("evidence_summary") or "") if external_reference else ""
    )
    reference_low = _decimal_or_zero(
        external_reference.get("range_low_multiple") if external_reference else None
    )
    reference_high = _decimal_or_zero(
        external_reference.get("range_high_multiple") if external_reference else None
    )
    has_external_reference_range = (
        reference_low > 0 and reference_high > 0 and reference_low <= reference_high
    )
    financial_metrics = request.valuation_result.financial_metrics or {}
    management_turnover_unaudited = (
        isinstance(financial_metrics, dict)
        and str(financial_metrics.get("revenue_source") or "").lower()
        == "management_workbook_unaudited"
    )
    earnings_ledger = multiples_results.get("earnings_basis_ledger")
    is_explicitly_weighted_reported_ebitda = bool(
        isinstance(earnings_ledger, dict) and earnings_ledger.get("mode") == "advisor_weighted"
    )
    current_reported_ebitda = _decimal_or_zero(
        financial_metrics.get("reported_ebitda") if isinstance(financial_metrics, dict) else None
    )

    context.update(
        {
            "has_industry_benchmarks": False,
            "has_benchmark_reference_multiple": False,
            "show_benchmark_reference_without_table": False,
            "benchmark_multiple_mid": None,
            "benchmark_multiple_low": None,
            "benchmark_multiple_high": None,
            "benchmark_sample_size": None,
            "benchmark_contract": None,
            "bridge_contract_resolved": False,
            "multiple_source": "DISCLOSED_EXTERNAL_MARKET_FALLBACK",
            "industry": business_type_label,
            "sector": business_type_label,
            "business_type_title": business_type_label,
            "cover_sub_line": business_type_label,
            "fallback_business_type_id": business_type_id,
            "fallback_business_type_label": business_type_label,
            "fallback_category_label": category_label,
            "fallback_country_code": request.country_code,
            "fallback_market_key": market_key,
            "fallback_applied_multiple": float(base_multiple),
            "disclosed_external_market_reference": external_reference,
            "fallback_reference_title": (
                str(external_reference.get("source_title") or "") if external_reference else None
            ),
            "fallback_reference_summary": reference_summary or None,
            "fallback_reference_range_low": (
                float(reference_low) if has_external_reference_range else None
            ),
            "fallback_reference_range_high": (
                float(reference_high) if has_external_reference_range else None
            ),
            # This is a disclosed external reference range, not a benchmark
            # percentile band.  Overwrite engine-derived ±20% presentation
            # bounds only for this explicit fallback path.
            "multiple_low": (float(reference_low) if has_external_reference_range else None),
            "multiple_high": (float(reference_high) if has_external_reference_range else None),
            "is_external_reference_range": has_external_reference_range,
            "management_turnover_unaudited": management_turnover_unaudited,
            "data_inputs": (
                [
                    "Managementomzet (niet-geauditeerd)",
                    "Gerapporteerde EBITDA (brongebonden)",
                ]
                if management_turnover_unaudited
                and (request.language or "nl").lower().startswith("nl")
                else context.get("data_inputs")
            ),
            "is_explicitly_weighted_reported_ebitda": (is_explicitly_weighted_reported_ebitda),
            # Keep the latest statutory EBITDA distinct from the multi-year
            # valuation basis.  A weighted basis must never be captioned as
            # "reported [latest year]" in a client-facing KPI card.
            "current_reported_ebitda": (
                float(current_reported_ebitda) if current_reported_ebitda > 0 else None
            ),
            "fallback_reasonableness_note": request.fallback_reasonableness_note,
            "show_size_discount_skipped_note": False,
            "limited_scope_years": len(request.valuation_result.valuation_timeline or []),
            "adaptive_methodology_justification": (
                f"Er is geen opgelost {market_key} Upswitch Index-contract. "
                "De conclusie gebruikt uitsluitend de uitdrukkelijk aanvaarde "
                f"externe marktreferentie van {multiple_display}× gerapporteerde EBITDA. "
                "Er zijn geen empirische percentielen, steekproef, vergelijkbare "
                "transacties of bedrijfsspecifieke aanpassingen toegepast; DCF "
                "draagt 0% bij."
            ),
            "methodology_statement": (
                f"De ondernemingswaarde is berekend als {multiple_display}× de gerapporteerde "
                f"EBITDA {request.reporting_year or context.get('current_year')} via de uitdrukkelijk aanvaarde "
                "externe marktreferentie. Dit is geen "
                f"{market_key} Index-contract, geen empirische benchmark en geen "
                "bewijs van vergelijkbare transacties. DCF en andere "
                "methoden dragen 0% bij aan de conclusie."
            ),
            "value_waterfall_intro_text": (
                "Van gerapporteerde EBITDA naar ondernemingswaarde en een "
                "uitsluitend illustratieve aandelenwaarde. Kas en financiële "
                "schuld komen uit de aangeleverde balans; restricted cash, leases, "
                "schuldachtige posten, genormaliseerd werkkapitaal en completion "
                "accounts moeten nog worden bevestigd."
            ),
        }
    )

    fallback_step = {
        "label": "Externe marktreferentie",
        "short_label": "Referentie",
        "kind": "base",
        "tone": "brand",
        "start_value": 0,
        "end_value": float(base_multiple),
        "multiple": float(base_multiple),
        "impact": None,
        "ev": float(base_multiple * basis),
        "ref": "†",
        "description": (
            f"No {market_key} Index contract; no empirical percentiles, "
            "sample or transaction attribution."
        ),
    }
    context["multiple_waterfall_steps"] = [fallback_step]
    context["calibration_steps"] = [fallback_step]
    context["discount_waterfall"] = [fallback_step]

    valuation_steps = context.get("valuation_waterfall_steps")
    if isinstance(valuation_steps, list) and valuation_steps:
        reported_steps = [
            dict(step) if isinstance(step, dict) else step for step in valuation_steps
        ]
        if isinstance(reported_steps[0], dict):
            reported_steps[0]["label"] = "Gerapporteerde EBITDA"
            reported_steps[0]["short_label"] = "Gerapp. EBITDA"
        context["valuation_waterfall_steps"] = reported_steps

    transparency = context.get("advisor_multiple_transparency")
    if isinstance(transparency, dict):
        transparency = dict(transparency)
        transparency.update(
            {
                "earnings_basis_rationale": (
                    "Gerapporteerde EBITDA; er zijn geen normalisaties toegepast."
                ),
                "risk_analysis_enabled": False,
                "risk_analysis_reference_only": True,
                "discount_floor_factor_percent": None,
                "discount_rows": [],
                "blend_rows": [],
                "segment_rows": [],
                "multiple_rows": [
                    {
                        "label": "Externe marktreferentie",
                        "multiple": str(base_multiple),
                        "enterprise_value": str(base_multiple * basis),
                    }
                ],
            }
        )
        transparency["benchmark_evidence"] = {
            "basis_label": "Externe marktreferentie (EV/EBITDA)",
            "business_type_title": business_type_descriptor,
            "low": (external_reference.get("range_low_multiple") if external_reference else None),
            "mid": (external_reference.get("applied_multiple") if external_reference else None),
            "high": (external_reference.get("range_high_multiple") if external_reference else None),
            "data_source": (
                external_reference.get("source_title")
                if external_reference
                else "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
            ),
            "sample_size": None,
            "as_of": (external_reference.get("source_as_of") if external_reference else None),
            "range_type": (external_reference.get("range_type") if external_reference else None),
            "source_url": (external_reference.get("source_url") if external_reference else None),
            "evidence_summary": (
                reference_summary
                or "Geen Upswitch Index-attributie; de band is geen empirische percentielverdeling."
            ),
        }
        previous_bridge = cast(dict[str, object], transparency.get("equity_bridge") or {})
        uses_net_cash = bool(context.get("bridge_uses_net_cash_label"))
        transparency["equity_bridge"] = {
            "rows": [
                {
                    "label": "Ondernemingswaarde (EV)",
                    "amount": str(context.get("enterprise_value_mid")),
                    "operator": None,
                },
                {
                    "label": (
                        "Toevoegen: voorlopige nettokas"
                        if uses_net_cash
                        else "Aftrek: voorlopige nettoschuld"
                    ),
                    "amount": str(context.get("bridge_net_debt_amount")),
                    "operator": "+" if uses_net_cash else "−",
                },
                {
                    "label": "Illustratieve aandelenwaarde",
                    "amount": str(context.get("equity_value")),
                    "operator": "=",
                },
            ],
            "disclosures": [
                "Uitsluitend illustratief; restricted cash, leases, schuldachtige posten, genormaliseerd werkkapitaal en completion accounts zijn nog niet geverifieerd."
            ],
            "reconciles": bool(previous_bridge.get("reconciles")),
        }
        context["advisor_multiple_transparency"] = transparency


def _apply_unweighted_lens_disclosure_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Render-only cross-check lenses, shown at 0% weight.

    Written straight onto the finalized template context on purpose. It is
    deliberately NOT routed through the aggregation dict (the legacy pricing
    path never sees it) and NOT appended to ``synthesis_contributions``: the
    displayed low/high band is derived from those rows by min/max with no
    weight filter, so a 0%-weight disclosure placed there would silently move
    the client-visible band.
    """

    lenses = list(getattr(request, "unweighted_valuation_lenses", []) or [])
    context["unweighted_valuation_lenses"] = [
        {
            "lens_id": lens.lens_id,
            "label": lens.label,
            "value": lens.value,
            "value_basis": lens.value_basis,
            "computation_note": lens.computation_note,
            "zero_weight_reason": lens.zero_weight_reason,
            "weight_pct": 0,
        }
        for lens in lenses
    ]
    context["show_unweighted_lens_disclosure"] = bool(lenses)
    if not lenses:
        return
    # "2 methodes" contradicts a report that visibly examines three lenses.
    # State both numbers: lenses examined vs comparable methods weighted.
    weighted_value = context.get("synthesis_contributions")
    weighted = weighted_value if isinstance(weighted_value, list) else []
    locale = str(context.get("locale") or "nl").strip().lower()[:2]
    # Count LENSES, not rows: several cases of one rule of thumb are one lens.
    families = {lens.lens_family or lens.lens_id for lens in lenses}
    examined = len(weighted) + len(families)
    # This lands in a narrow stat card, so keep it short; the full framing is
    # spelled out in prose on the synthesis page.
    if locale == "fr":
        label = f"{examined} lentilles · {len(weighted)} pondérées"
    elif locale == "en":
        label = f"{examined} lenses · {len(weighted)} weighted"
    else:
        label = f"{examined} lenzen · {len(weighted)} gewogen"
    context["synthesis_method_count_label"] = label


def _apply_report_option_gates(context: ReportMap, request: GenerateReportRequest) -> None:
    context["include_ebitda_normalization_page"] = request.include_ebitda_normalization_page
    context["show_transaction_readiness_section"] = bool(
        context.get("show_transaction_readiness_section")
        and request.include_transaction_readiness_section
    )
    context["show_business_growth_maturity_section"] = bool(
        context.get("show_business_growth_maturity_section")
        and request.include_business_growth_maturity_section
    )
    context["show_growth_multiple_sensitivity"] = bool(
        context.get("show_growth_multiple_sensitivity")
        and request.include_growth_multiple_sensitivity
    )
    context["suppress_sde_cross_check"] = not request.include_sde_cross_check
    if not request.include_generic_next_steps:
        context["show_limited_scope_advisory_panel"] = False
    if not request.include_sde_cross_check:
        context["show_sde_cross_check"] = False
        context["has_sde_page"] = False
    if not request.include_attestation_page:
        context["has_attestation_page"] = False


def _apply_client_presentation_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Apply advisor wording without altering an executed valuation contract.

    The fields in this function are deliberately display-only.  Monetary values,
    method selection, benchmark flags and fallback disclosures are always
    assembled before this function runs and remain untouched.
    """
    context["suppress_engine_product_name"] = request.suppress_engine_product_name
    context["report_scope"] = request.report_scope
    context["is_sealed_advisor_memorandum"] = bool(
        request.report_scope == "advisor_memorandum" and request.publication_intent == "final"
    )
    if context["is_sealed_advisor_memorandum"]:
        # These are separately commissioned transaction-advisory work products,
        # not valuation evidence. Keep them out even when a legacy valuation
        # payload carried the corresponding display flags forward.
        context["show_sellability_section"] = False
        context["show_transaction_readiness_section"] = False
        context["show_business_growth_maturity_section"] = False
        context["has_nav_deal_structure"] = False
    context["engagement_scope"] = (
        request.engagement_scope.model_dump(mode="json")
        if request.engagement_scope is not None
        else None
    )
    context["registry_snapshot"] = (
        request.registry_snapshot.model_dump(mode="json")
        if request.registry_snapshot is not None
        else None
    )
    context["report_assurance_level"] = request.report_assurance_level
    context["scope_prohibits_customer_persistence"] = request.report_scope == "client_indicative"
    context["scope_prohibits_t4"] = request.report_scope == "client_indicative"
    context["client_delivery_verdict"] = (
        "Approved for client delivery — indicative/as-reported"
        if request.report_scope == "client_indicative"
        else None
    )
    context["client_presentation_method_label"] = request.client_presentation_method_label
    context["show_weighted_synthesis_range_on_cover"] = (
        request.show_weighted_synthesis_range_on_cover
    )
    context["client_presentation_methodology_statement"] = (
        request.client_presentation_methodology_statement
    )
    if request.client_presentation_method_label:
        context["valuation_methodology_display"] = request.client_presentation_method_label
        context["primary_method_label"] = request.client_presentation_method_label
    if request.client_presentation_methodology_statement:
        context["methodology_statement"] = request.client_presentation_methodology_statement
    if request.report_scope == "client_indicative":
        weighted = request.valuation_result.weighted_valuation
        if weighted is not None:
            weights = {
                str(row.method_key): round(float(row.weight) * 100)
                for row in weighted.contributions
                if float(row.weight) > 0
            }
            market_weight = weights.get("ebitda_multiple")
            dcf_weight = weights.get("dcf")
            if market_weight is not None and dcf_weight is not None:
                language = (request.language or "nl").lower()
                market_label = (
                    "marché"
                    if language.startswith("fr")
                    else "market" if language.startswith("en") else "markt"
                )
                context["synthesis_weight_compact"] = (
                    f"{market_weight}% {market_label} + {dcf_weight}% DCF"
                )
        # Generic buyer-package readiness is an internal workflow surface.  A
        # finished limited-scope client valuation must not expose internal
        # evidence tokens, scores or contradictory distribution gates.
        context["show_transaction_readiness_section"] = False
        _suppress_client_internal_method_artifacts(context, request)


def _suppress_client_internal_method_artifacts(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Expose only selected synthesis legs and the governed direct WACC."""

    result = request.valuation_result
    weighted = result.weighted_valuation
    allowed_method_keys = {
        str(row.method_key)
        for row in (weighted.contributions if weighted is not None else [])
        if float(row.weight) > 0
    }
    raw_results = context.get("method_results_by_key")
    if isinstance(raw_results, dict) and allowed_method_keys:
        context["method_results_by_key"] = {
            key: value for key, value in raw_results.items() if str(key) in allowed_method_keys
        }
    # The synthesis label is the product-facing methodology. Never render the
    # adaptive intermediate page or its legacy product label beside a 70/30
    # weighted report.
    context["has_upswitch_adaptive_page"] = False
    context["upswitch_adaptive_method"] = None
    context["upswitch_adaptive_value"] = None
    context["valuation_method_label"] = request.client_presentation_method_label

    dcf = result.dcf_results if isinstance(result.dcf_results, dict) else None
    contract = dcf.get("wacc_evidence_contract") if dcf else None
    if isinstance(contract, dict):
        direct_wacc = Decimal(str(contract["value_pct"])) / Decimal("100")
        context["dcf_wacc"] = float(direct_wacc)
        context["dcf_wacc_buildup"] = {
            "mode": "direct_sector_wacc",
            "wacc": direct_wacc,
            "wacc_override_applied": True,
            "component_buildup_applicable": False,
            "wacc_evidence_contract": contract,
        }
        context.pop("engine_wacc", None)
        context.pop("engine_cost_of_equity", None)


def _apply_benchmark_provenance_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    snapshot = build_benchmark_provenance_snapshot(request.valuation_result.multiples_results)
    context["benchmark_provenance"] = snapshot
    if snapshot is None and request.valuation_result.valuation_run is not None:
        # Legacy enrichment converts missing evidence to zero/default copy.
        # A saved run without the source contract has no comparable distribution.
        transparency = context.get("advisor_multiple_transparency")
        if isinstance(transparency, dict):
            transparency = dict(transparency)
            transparency["benchmark_evidence"] = {
                "status": "unavailable",
                "low": None,
                "mid": None,
                "high": None,
                "data_source": None,
                "sample_size": None,
                "as_of": None,
            }
            context["advisor_multiple_transparency"] = transparency
    if snapshot:
        # One immutable normalized contract backs the API context and both
        # screen/PDF template trees.
        context["benchmark_contract"] = snapshot["contract"]
        context.update(
            {
                "benchmark_multiple_low": _optional_decimal(snapshot.get("low")),
                "benchmark_multiple_mid": _optional_decimal(snapshot.get("mid")),
                "benchmark_multiple_high": _optional_decimal(snapshot.get("high")),
                "benchmark_sample_size": snapshot.get("sample_size"),
                "benchmark_data_source": snapshot.get("source"),
                "benchmark_published_at": snapshot.get("published_at"),
                "benchmark_id": snapshot.get("benchmark_id"),
                "benchmark_dataset_version_id": snapshot.get("dataset_version_id"),
                "benchmark_country_code": snapshot.get("country_code"),
                "benchmark_region_key": snapshot.get("region_key"),
                "benchmark_tier": snapshot.get("tier"),
                "benchmark_walk_step": snapshot.get("walk_step"),
                "benchmark_scope_stage": snapshot.get("scope_stage"),
                "benchmark_confidence_band": snapshot.get("confidence_band"),
                "benchmark_source_mix": snapshot.get("source_mix"),
                "benchmark_evidence_summary": snapshot.get("evidence_summary"),
                "benchmark_methodology_version": snapshot.get("methodology_version"),
                "bridge_contract_resolved": True,
            }
        )
        if snapshot.get("metric") == "ev_ebitda_multiple":
            context.update(
                {
                    "benchmark_ev_ebitda_p25": _optional_decimal(snapshot.get("low")),
                    "benchmark_ev_ebitda_p50": _optional_decimal(snapshot.get("mid")),
                    "benchmark_ev_ebitda_p75": _optional_decimal(snapshot.get("high")),
                }
            )

        # Finalization constructs the advisor appendix before this stateless
        # contract is reasserted. Refresh its evidence row from the identical
        # snapshot so API, screen and PDF cannot disagree on source or band.
        transparency = context.get("advisor_multiple_transparency")
        if isinstance(transparency, dict):
            transparency = dict(transparency)
            evidence = transparency.get("benchmark_evidence")
            evidence = dict(evidence) if isinstance(evidence, dict) else {}
            evidence.update(
                {
                    "low": snapshot.get("low"),
                    "mid": snapshot.get("mid"),
                    "high": snapshot.get("high"),
                    "sample_size": snapshot.get("sample_size"),
                    "data_source": snapshot.get("source"),
                    "as_of": snapshot.get("published_at"),
                    "region": snapshot.get("region_key") or snapshot.get("country_code"),
                    "tier": snapshot.get("tier"),
                    "scope_stage": snapshot.get("scope_stage"),
                    "source_mix": snapshot.get("source_mix"),
                    "evidence_summary": snapshot.get("evidence_summary"),
                }
            )
            transparency["benchmark_evidence"] = evidence
            context["advisor_multiple_transparency"] = transparency


def _apply_valuation_run_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Bind every report surface to the exact immutable calculation run."""
    run = request.valuation_result.valuation_run
    if run is None:
        return
    payload = cast(ReportMap, run.model_dump(mode="python"))
    context.update(
        {
            "valuation_run": payload,
            "valuation_run_id": run.run_id,
            "valuation_run_hash": run.run_hash,
            "currency": run.currency,
            "valuation_run_schema_version": run.schema_version,
            "valuation_engine_version": run.engine_version,
            "valuation_policy_version": run.policy_version,
            "valuation_input_hash": run.input_hash,
            "valuation_evidence_hash": run.evidence_hash,
            "valuation_benchmark_hash": run.benchmark_hash,
            "valuation_calculation_hash": run.calculation_hash,
            "valuation_audit_hash": run.audit_hash,
            "valuation_range": payload.get("valuation_range"),
            "enterprise_value_range": payload.get("enterprise_value_range"),
            "value_driver_ledger": run.driver_ledger,
            "calculation_lineage": payload.get("calculation_lineage"),
        }
    )


def _apply_priced_evidence_projection_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Expose one run-bound projection to both template renderers.

    Screen and PDF share ``template_context``.  Keeping the projection here,
    after legacy aggregation/finalization, prevents either template tree from
    reconstructing monetary lines from mutable presentation fields.
    """

    if request.report_scope == "client_indicative":
        context.update(
            {
                "priced_evidence_register": None,
                "actionable_adjustment_projection": None,
                "actionable_adjustment_lines": [],
                "show_canonical_evidence_adjustments_appendix": False,
            }
        )
        return

    run = request.valuation_result.valuation_run
    if not isinstance(run, ValuationRunV2):
        context.update(
            {
                "priced_evidence_register": None,
                "actionable_adjustment_projection": None,
                "actionable_adjustment_lines": [],
                "show_canonical_evidence_adjustments_appendix": False,
            }
        )
        return
    projection = build_stateless_priced_evidence_projection(run)
    context.update(projection.as_report_context())


def _apply_canonical_balance_sheet_bridge_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Bind gross debt, cash and net debt to the canonical response inputs.

    Legacy report aggregation sometimes populated ``net_debt`` from gross debt
    when Step 7 detail was absent.  That makes a correct sealed EV/equity result
    look arithmetically inconsistent in SDE and other stateless reports.  A
    canonical run may use the committed response's balance-sheet metrics; it
    must never reconstruct this bridge from mutable report context.
    """

    result = request.valuation_result
    if result.valuation_run is None or result.enterprise_value_mid is None:
        return
    metrics = result.financial_metrics
    if not isinstance(metrics, dict):
        return
    if metrics.get("equity_status") == "unavailable_incomplete_bridge":
        context.update(
            {
                "total_debt": metrics.get("total_debt"),
                "cash_balance": metrics.get("cash"),
                "net_debt": None,
                "has_net_debt_adjustment": False,
                "show_ev_equity_bridge": False,
                "show_enterprise_to_equity_bridge": False,
            }
        )
        return

    debt_raw, cash_raw = metrics.get("total_debt"), metrics.get("cash")
    debt = report_decimal(debt_raw, "total debt") if debt_raw is not None else None
    cash = report_decimal(cash_raw, "cash") if cash_raw is not None else None
    explicit_net_debt = metrics.get("net_debt")
    net_debt = (
        report_decimal(explicit_net_debt, "net debt") if explicit_net_debt is not None else None
    )
    if net_debt is None and debt is not None and cash is not None:
        with localcontext() as precision:
            precision.prec = 100
            net_debt = debt - cash
    known = net_debt is not None and result.equity_value_mid is not None
    context.update(
        {
            "total_debt": debt,
            "cash_balance": cash,
            "net_debt": net_debt,
            "has_net_debt_adjustment": net_debt is not None and net_debt != 0,
            "show_ev_equity_bridge": known,
            "show_enterprise_to_equity_bridge": known,
            "bridge_net_debt_amount": (net_debt.copy_abs() if net_debt is not None else None),
            "bridge_net_debt_operator": ("+" if net_debt is not None and net_debt < 0 else "−"),
            "bridge_uses_net_cash_label": net_debt is not None and net_debt < 0,
        }
    )


def _apply_canonical_multiple_build_up_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Use the sealed post-adjustment multiple and earnings basis in formulas.

    The legacy aggregator starts from the pre-discount benchmark multiple.  A
    canonical run commits the effective multiple after method-level size and
    liquidity adjustments in ``multiple_build_up``.  Using the former beside
    final EV creates a false equation in the PDF even though the headline is
    correct.  Rebind both values from the sealed run before the formula gate.
    """

    run = request.valuation_result.valuation_run
    multiples = run.multiples_results if run is not None else None
    if not isinstance(multiples, dict):
        return
    build_up = multiples.get("multiple_build_up")
    if not isinstance(build_up, dict):
        return
    effective_multiple = _decimal_or_zero(build_up.get("effective_multiple"))
    earnings_basis = build_up.get("earnings_basis")
    adjusted_earnings = (
        _decimal_or_zero(earnings_basis.get("adjusted_earnings"))
        if isinstance(earnings_basis, dict)
        else Decimal("0")
    )
    if effective_multiple > 0:
        context["applied_multiple"] = effective_multiple
        context["sensitivity_pricing_multiple"] = effective_multiple
    if adjusted_earnings > 0:
        context["valuation_basis_value"] = adjusted_earnings
        context["sensitivity_pricing_metric"] = adjusted_earnings

    # A revenue or ARR headline shares the benchmark/discount evidence with
    # the EBITDA build-up, but its formula must come from its own sealed
    # MethodResult. Never pair the EBITDA effective multiple with revenue/ARR.
    selected_method = normalize_selected_method_key(request.selected_method)
    method_results = run.method_results
    selected_result = (
        method_results.get(selected_method) if isinstance(method_results, dict) else None
    )
    if not isinstance(selected_result, dict):
        return
    selected_multiple = _decimal_or_zero(selected_result.get("multiple_used"))
    details = selected_result.get("details")
    if selected_multiple <= 0 or not isinstance(details, dict):
        return
    if selected_method == "omzet_multiple":
        revenue = _decimal_or_zero(details.get("revenue"))
        if revenue > 0:
            context.update(
                {
                    "applied_multiple": selected_multiple,
                    "valuation_basis_value": revenue,
                    "revenue": revenue,
                    "multiple_metric_type": "REVENUE",
                }
            )
    elif selected_method == "arr_multiple":
        arr = _decimal_or_zero(details.get("arr"))
        if arr > 0:
            context.update(
                {
                    "applied_multiple": selected_multiple,
                    "valuation_basis_value": arr,
                    "multiple_metric_type": "ARR",
                }
            )
    elif selected_method == "ebitda_multiple" and adjusted_earnings > 0:
        selected_multiple = effective_multiple if effective_multiple > 0 else selected_multiple
        context.update(
            {
                "applied_multiple": selected_multiple,
                "valuation_basis_value": adjusted_earnings,
                "multiple_metric_type": "EBITDA",
            }
        )


def _apply_canonical_run_headline_context(
    context: ReportMap,
    request: GenerateReportRequest,
    assurance_authority: CurrentValuationAssuranceAuthority | None = None,
) -> None:
    """Pin report headlines to the immutable run instead of recalculating them.

    The legacy report finalizer still contains presentation-era alignment and
    asking-price rules.  Those rules may enrich legacy reports, but once a
    ``ValuationRun`` exists the API result is the monetary authority.  Reapply
    its exact equity/enterprise ranges and asking price after finalization so
    HTML, PDF, API and graph projections cannot quote different conclusions.
    """

    result = request.valuation_result
    if result.valuation_run is None:
        return

    if any(
        value is None
        for value in (result.equity_value_low, result.equity_value_mid, result.equity_value_high)
    ):
        if request.headline_value_basis != "enterprise_value":
            raise ValueError("equity headline requires an available equity range")
        ev_values = (
            result.enterprise_value_low,
            result.enterprise_value_mid,
            result.enterprise_value_high,
        )
        if any(value is None for value in ev_values):
            raise ValueError("enterprise headline requires an available enterprise range")
        low, mid, high = (report_decimal(value, "enterprise value") for value in ev_values)
        context.update(
            {
                "equity_value": None,
                "equity_value_mid": None,
                "equity_value_low": None,
                "equity_value_high": None,
                "equity_value_band_is_meaningful": False,
                "valuation": mid,
                "valuation_low": low,
                "valuation_high": high,
                "enterprise_value": mid,
                "enterprise_value_mid": mid,
                "enterprise_value_low": low,
                "enterprise_value_high": high,
                "headline_value_basis": "enterprise_value",
                "recommended_asking_price": None,
                "show_ev_equity_bridge": False,
                "show_enterprise_to_equity_bridge": False,
            }
        )
        transparency = context.get("advisor_multiple_transparency")
        if isinstance(transparency, dict):
            transparency.pop("equity_bridge", None)
        return

    equity_low = _decimal_or_zero(result.equity_value_low)
    equity_mid = _decimal_or_zero(result.equity_value_mid)
    equity_high = _decimal_or_zero(result.equity_value_high)
    assured_band = (
        assurance_authority.envelope.audience_display_band
        if assurance_authority is not None
        else None
    )
    if assured_band is not None and assured_band.value_basis == "equity_value":
        equity_low = Decimal(assured_band.display_low)
        equity_mid = Decimal(assured_band.display_mid)
        equity_high = Decimal(assured_band.display_high)
    context.update(
        {
            "equity_value": equity_mid,
            "equity_value_mid": equity_mid,
            "equity_value_low": equity_low,
            "equity_value_high": equity_high,
            "equity_value_band_is_meaningful": equity_low < equity_high,
            "recommended_asking_price_realigned": False,
        }
    )

    enterprise_low = result.enterprise_value_low
    enterprise_mid = result.enterprise_value_mid
    enterprise_high = result.enterprise_value_high
    ev_low: Decimal | None
    ev_mid: Decimal | None
    ev_high: Decimal | None
    if enterprise_low is not None and enterprise_mid is not None and enterprise_high is not None:
        ev_low = _decimal_or_zero(enterprise_low)
        ev_mid = _decimal_or_zero(enterprise_mid)
        ev_high = _decimal_or_zero(enterprise_high)
        if assured_band is not None and assured_band.value_basis == "enterprise_value":
            ev_low = Decimal(assured_band.display_low)
            ev_mid = Decimal(assured_band.display_mid)
            ev_high = Decimal(assured_band.display_high)
        context.update(
            {
                "enterprise_value_low": ev_low,
                "enterprise_value_mid": ev_mid,
                "enterprise_value_high": ev_high,
                "enterprise_value_applicability": "applicable",
            }
        )
    else:
        ev_low = ev_mid = ev_high = None
        # The legacy aggregator may have derived an EV-looking scalar from a
        # supporting market method. A canonical pure-equity run must erase it
        # before HTML/PDF flags and formulas are finalized.
        context.update(
            {
                "enterprise_value": None,
                "enterprise_value_low": None,
                "enterprise_value_mid": None,
                "enterprise_value_high": None,
                "enterprise_value_applicability": "not_applicable",
                "supports_metric_to_ev_bridge": False,
                "show_ev_equity_bridge": False,
                "show_enterprise_to_equity_bridge": False,
                "has_net_debt_adjustment": False,
            }
        )

    if (
        request.headline_value_basis == "enterprise_value"
        or result.valuation_run.value_basis == "enterprise_value"
    ):
        if ev_low is None or ev_mid is None or ev_high is None:
            raise ValueError(
                "enterprise-value report is not applicable to the selected equity-premise method"
            )
        headline_low, headline_mid, headline_high = ev_low, ev_mid, ev_high
    else:
        headline_low, headline_mid, headline_high = (
            equity_low,
            equity_mid,
            equity_high,
        )
    context.update(
        {
            "valuation": headline_mid,
            "valuation_low": headline_low,
            "valuation_high": headline_high,
            "valuation_band_is_meaningful": headline_low < headline_high,
            "ev_sourced_from_engine_equity": False,
        }
    )

    if request.show_asking_price:
        asking_price = result.recommended_asking_price
        context["recommended_asking_price"] = (
            _decimal_or_zero(asking_price) if asking_price is not None else None
        )
    else:
        context["recommended_asking_price"] = None


def request_to_aggregation_dict(request: GenerateReportRequest) -> ReportMap:
    """Flatten ``GenerateReportRequest`` into the aggregator input shape.

    ``MainReportDataAggregator.aggregate_from_valuation_data()`` wraps this
    dict and reads fields via attribute access.  We keep the bridge here so the
    HTTP route does not need to know the aggregator's legacy read patterns.
    """
    result = request.valuation_result
    d = cast(ReportMap, result.model_dump(mode="python"))

    d["company_name"] = request.company_name
    d["industry"] = request.industry
    d["country_code"] = request.country_code
    d["founded_year"] = request.founding_year
    d["employee_count"] = request.number_of_employees
    d["number_of_employees"] = request.number_of_employees
    d["registration_number"] = request.registration_number
    d["kbo_number"] = request.registration_number if request.country_code == "BE" else None
    d["nace_code"] = request.nace_code
    d["legal_form"] = request.legal_form
    d["city"] = request.city
    d["founded_year"] = request.founding_year
    d["founding_date"] = request.incorporated_on
    if request.business_type_label:
        d["business_type_title"] = request.business_type_label

    reporting_year = request.reporting_year or get_current_filing_year()
    d["current_year"] = reporting_year
    d["reporting_year"] = request.reporting_year
    d["headline_value_basis"] = request.headline_value_basis
    d["value_basis"] = request.headline_value_basis
    d["equity_bridge_is_illustrative"] = request.equity_bridge_is_illustrative
    if not request.show_asking_price:
        d["recommended_asking_price"] = None
    d["risk_factors"] = list(
        dict.fromkeys(
            [
                *(cast(list[object], d.get("risk_factors") or [])),
                *request.additional_risk_factors,
            ]
        )
    )[:10]
    d["source_references"] = _sealed_source_references(request)

    if request.current_year_data is not None:
        d["current_year_data"] = request.current_year_data.model_dump(mode="python")
        d["historical_years_data"] = [
            row.model_dump(mode="python") for row in request.historical_years_data
        ]

    raw_financial_metrics = d.get("financial_metrics")
    fm = cast(ReportMap, raw_financial_metrics) if isinstance(raw_financial_metrics, dict) else {}
    if fm and "current_year_data" not in d:
        from .report_annual_earnings import annual_earnings_for_report

        run = result.valuation_run
        annual_ledger = run.response_snapshot.get("earnings_basis_ledger") if run else None
        d["current_year_data"] = {
            "year": reporting_year,
            **annual_earnings_for_report(fm, annual_ledger),
            "revenue": fm.get("revenue"),
            "total_debt": fm.get("total_debt"),
            "cash": fm.get("cash"),
            "total_assets": fm.get("total_assets"),
            # ``YearDataStateless`` and the fiscal-reference resolver use the
            # canonical balance-sheet name. Keep the legacy alias beside it
            # for older report consumers, but never make the statutory
            # equity line look absent merely because CalculateResponse calls
            # it ``financial_metrics.equity``.
            "total_equity": fm.get("equity"),
            "equity": fm.get("equity"),
        }
        if fm.get("revenue_source") is not None:
            cast(ReportMap, d["current_year_data"])["revenue_source"] = fm.get("revenue_source")

    if d.get("multiples_results") and "multiples_valuation" not in d:
        d["multiples_valuation"] = dict(cast(ReportMap, d["multiples_results"]))

    if d.get("dcf_results") and "dcf_valuation" not in d:
        d["dcf_valuation"] = d["dcf_results"]

    d["valuation_date"] = request.valuation_date or f"{reporting_year}-12-31"
    d["financial_reference_date"] = request.financial_reference_date or f"{reporting_year}-12-31"
    # The report request is already cryptographically bound to the sealed
    # run's methodology by ``GenerateReportRequest``.  Preserve that canonical
    # selector when adapting into the legacy aggregator protocol; otherwise
    # specialty tracks (liquidation/startup) and the Belgian fiscal annex are
    # resolved before the later presentation override and silently render the
    # generic SME report instead.
    d["selected_method"] = request.selected_method

    if request.branding:
        b = request.branding
        safe_email = sanitize_report_email(b.email) if b.email is not None else None
        safe_phone = sanitize_report_phone(b.phone) if b.phone is not None else None
        d["metadata"] = {
            "accountant_firm_name": b.firm_name,
            "accountant_logo_url": b.logo_data_uri or b.logo_url,
            "accountant_email": safe_email,
            "accountant_phone": safe_phone,
            "show_cover_price": (b.show_cover_price if b.show_cover_price is not None else True),
            "valuation_goal": b.valuation_goal,
            "custom_disclaimer": b.custom_disclaimer,
        }

    return d


def _apply_negative_ebitda_recovery_context(
    context: ReportMap,
    request: GenerateReportRequest,
    *,
    locale: str,
) -> None:
    resolution_model = request.valuation_result.negative_ebitda_resolution
    if resolution_model is None:
        context["has_negative_ebitda_recovery"] = False
        return

    resolution = resolution_model.model_dump(mode="python")
    language = (locale or "nl").lower().split("-")[0]
    copy = {
        "nl": {
            "title": "Herstelwaardering bij negatieve EBITDA",
            "subtitle": "Een voorwaardelijke beoordeling van herstelpad, financiering en bewijs.",
            "no_range": "Nog geen verdedigbare waarderingsrange vastgesteld",
            "conclusion": "Conclusie",
            "position": "Huidige positie en oorzaken",
            "causes": "Oorzaak- en risicosignalen",
            "normalization_bridge": "Normalisatiebrug",
            "accepted_adjustments": "Aanvaarde aanpassingen",
            "break_even_bridge": "Break-evenbrug (basisscenario)",
            "scenarios": "Herstelscenario’s",
            "funding": "Financiering en aandeelhoudersbrug",
            "evidence": "Vereist bewijs",
            "limitations": "Beperkingen",
            "actions": "Waardeopbouwende acties",
            "reported_ebitda": "Gerapporteerde EBITDA",
            "normalized_ebitda": "Genormaliseerde EBITDA",
            "operating_trajectory": "Operationele richting",
            "scenario": "Scenario",
            "probability": "Waarschijnlijkheid",
            "break_even": "Break-even",
            "funding_need": "Financieringsbehoefte",
            "equity_midpoint": "Middenwaarde eigen vermogen",
            "enterprise_midpoint": "Middenwaarde onderneming",
            "revenue_at_break_even": "Omzet bij break-even",
            "ebitda_at_break_even": "EBITDA bij break-even",
            "fcff_at_break_even": "FCFF bij break-even",
            "current_cash": "Huidige cash",
            "minimum_cash": "Minimale operationele cash",
            "excess_cash": "Overtollige cash",
            "current_debt": "Huidige schuld",
            "shareholder_basis": "Basis aandeelhouderswaarde",
            "terminal_value_share": "Aandeel eindwaarde",
            "cross_checks": "Kruiscontroles",
            "no_cross_check": "Geen verdedigbare kruiscontrole aanvaard.",
            "confidence": "betrouwbaarheid",
            "limitations_copy": "Scenariokansen omvatten het overlevingsrisico al; er wordt geen extra overlevingskorting toegepast. De financieringsbehoefte wordt afzonderlijk getoond en niet nogmaals van de ondernemingswaarde afgetrokken.",
        },
        "en": {
            "title": "Negative-EBITDA recovery valuation",
            "subtitle": "A conditional assessment of the recovery path, funding and evidence.",
            "no_range": "No defensible range established yet",
            "conclusion": "Conclusion",
            "position": "Current position and causes",
            "causes": "Cause and risk signals",
            "normalization_bridge": "Normalization bridge",
            "accepted_adjustments": "Accepted adjustments",
            "break_even_bridge": "Break-even bridge (base scenario)",
            "scenarios": "Recovery scenarios",
            "funding": "Funding and shareholder bridge",
            "evidence": "Required evidence",
            "limitations": "Limitations",
            "actions": "Value-building actions",
            "reported_ebitda": "Reported EBITDA",
            "normalized_ebitda": "Normalized EBITDA",
            "operating_trajectory": "Operating trajectory",
            "scenario": "Scenario",
            "probability": "Probability",
            "break_even": "Break-even",
            "funding_need": "Funding need",
            "equity_midpoint": "Equity midpoint",
            "enterprise_midpoint": "Enterprise midpoint",
            "revenue_at_break_even": "Revenue at break-even",
            "ebitda_at_break_even": "EBITDA at break-even",
            "fcff_at_break_even": "FCFF at break-even",
            "current_cash": "Current cash",
            "minimum_cash": "Minimum operating cash",
            "excess_cash": "Excess cash",
            "current_debt": "Current debt",
            "shareholder_basis": "Shareholder-value basis",
            "terminal_value_share": "Terminal-value share",
            "cross_checks": "Cross-checks",
            "no_cross_check": "No defensible cross-check accepted.",
            "confidence": "confidence",
            "limitations_copy": "Scenario probabilities already incorporate survival risk; no additional survival haircut is applied. Funding need is disclosed separately and is not deducted a second time from enterprise value.",
        },
        "fr": {
            "title": "Valorisation de redressement avec EBITDA négatif",
            "subtitle": "Une évaluation conditionnelle de la trajectoire, du financement et des preuves.",
            "no_range": "Aucune fourchette défendable établie à ce stade",
            "conclusion": "Conclusion",
            "position": "Situation actuelle et causes",
            "causes": "Signaux de cause et de risque",
            "normalization_bridge": "Pont de normalisation",
            "accepted_adjustments": "Ajustements acceptés",
            "break_even_bridge": "Pont vers le seuil de rentabilité (scénario de base)",
            "scenarios": "Scénarios de redressement",
            "funding": "Financement et pont actionnarial",
            "evidence": "Preuves requises",
            "limitations": "Limites",
            "actions": "Actions de création de valeur",
            "reported_ebitda": "EBITDA déclaré",
            "normalized_ebitda": "EBITDA normalisé",
            "operating_trajectory": "Trajectoire opérationnelle",
            "scenario": "Scénario",
            "probability": "Probabilité",
            "break_even": "Seuil de rentabilité",
            "funding_need": "Besoin de financement",
            "equity_midpoint": "Valeur médiane des fonds propres",
            "enterprise_midpoint": "Valeur médiane de l’entreprise",
            "revenue_at_break_even": "Chiffre d’affaires au seuil",
            "ebitda_at_break_even": "EBITDA au seuil",
            "fcff_at_break_even": "FCFF au seuil",
            "current_cash": "Trésorerie actuelle",
            "minimum_cash": "Trésorerie opérationnelle minimale",
            "excess_cash": "Trésorerie excédentaire",
            "current_debt": "Dette actuelle",
            "shareholder_basis": "Base de valeur actionnariale",
            "terminal_value_share": "Part de la valeur terminale",
            "cross_checks": "Recoupements",
            "no_cross_check": "Aucun recoupement défendable accepté.",
            "confidence": "fiabilité",
            "limitations_copy": "Les probabilités des scénarios intègrent déjà le risque de survie ; aucune décote de survie supplémentaire n’est appliquée. Le besoin de financement est présenté séparément et n’est pas déduit une seconde fois de la valeur d’entreprise.",
        },
    }.get(language, {})
    no_range = resolution.get("primary_method") is None
    normalization_bridge = resolution.get("normalization_bridge") or {
        "reported_ebitda": resolution.get("reported_ebitda"),
        "accepted_adjustments": (
            resolution.get("normalized_ebitda") - resolution.get("reported_ebitda")
            if resolution.get("normalized_ebitda") is not None
            and resolution.get("reported_ebitda") is not None
            else None
        ),
        "normalized_ebitda": resolution.get("normalized_ebitda"),
    }
    context.update(
        {
            "has_negative_ebitda_recovery": True,
            "negative_ebitda_resolution": resolution,
            "negative_ebitda_recovery_copy": copy,
            "negative_ebitda_no_range": no_range,
            "negative_ebitda_conclusion": (
                copy.get("no_range")
                if no_range
                else str(resolution.get("primary_method") or "")
                .replace("_", " ")
                .title()
                .replace("Dcf", "DCF")
                .replace("Nav", "NAV")
                .replace("Arr", "ARR")
            ),
            "negative_ebitda_scenarios": resolution.get("scenario_results") or [],
            "negative_ebitda_trajectory": resolution.get("operating_trajectory") or {},
            "negative_ebitda_required_evidence": resolution.get("required_evidence") or [],
            "negative_ebitda_blockers": resolution.get("blockers") or [],
            "negative_ebitda_actions": resolution.get("value_building_actions") or [],
            "negative_ebitda_causes": resolution.get("cause_codes") or [],
            # Older persisted recovery snapshots predate the explicit bridge.
            # Reconstruct it from canonical reported/normalized fields so
            # report regeneration remains useful and never formats Undefined.
            "negative_ebitda_normalization_bridge": normalization_bridge,
            "negative_ebitda_break_even_bridge": resolution.get("break_even_bridge") or {},
            "negative_ebitda_equity_bridge": resolution.get("equity_bridge") or {},
        }
    )
    if no_range:
        # The assessment is complete but not numeric. Keep every report surface
        # on the same null conclusion; do not let legacy formatting turn it into €0.
        context.update(
            {
                "valuation": None,
                "valuation_low": None,
                "valuation_high": None,
                "equity_value": None,
                "equity_value_low": None,
                "equity_value_mid": None,
                "equity_value_high": None,
                "enterprise_value": None,
                "enterprise_value_low": None,
                "enterprise_value_mid": None,
                "enterprise_value_high": None,
                "recommended_asking_price": None,
                "headline_value_basis": None,
                "primary_method_label": copy.get("no_range"),
                "show_ev_equity_bridge": False,
                "show_enterprise_to_equity_bridge": False,
                "valuation_band_is_meaningful": False,
                "equity_value_band_is_meaningful": False,
                "has_upswitch_adaptive_page": False,
                "has_dcf": False,
                "show_dcf_before_calibration": False,
                "has_ebitda_multiple_page": False,
                "has_sde_page": False,
                "has_revenue_multiple_page": False,
                "has_weighted_synthesis": False,
                "show_advisor_multiple_transparency_appendix": False,
                "show_multiple_evidence_appendix": False,
                "show_discount_methodology_appendix": False,
            }
        )
    else:
        # The immutable recovery resolution is the sole report authority. A
        # regenerated report must not inherit an older top-level band or render
        # a parallel legacy method chapter whose numbers are not bound by the
        # recovery resolution hash.
        equity_low = resolution.get("headline_equity_value_low")
        equity_mid = resolution.get("headline_equity_value_mid")
        equity_high = resolution.get("headline_equity_value_high")
        enterprise_low = resolution.get("headline_enterprise_value_low")
        enterprise_mid = resolution.get("headline_enterprise_value_mid")
        enterprise_high = resolution.get("headline_enterprise_value_high")
        headline_low = equity_low if equity_low is not None else enterprise_low
        headline_mid = equity_mid if equity_mid is not None else enterprise_mid
        headline_high = equity_high if equity_high is not None else enterprise_high
        has_equity_bridge = equity_mid is not None and enterprise_mid is not None
        context.update(
            {
                "valuation": headline_mid,
                "valuation_low": headline_low,
                "valuation_high": headline_high,
                "equity_value": equity_mid,
                "equity_value_low": equity_low,
                "equity_value_mid": equity_mid,
                "equity_value_high": equity_high,
                "enterprise_value": enterprise_mid,
                "enterprise_value_low": enterprise_low,
                "enterprise_value_mid": enterprise_mid,
                "enterprise_value_high": enterprise_high,
                "recommended_asking_price": None,
                "headline_value_basis": (
                    "equity_value" if equity_mid is not None else "enterprise_value"
                ),
                "primary_method_label": context["negative_ebitda_conclusion"],
                "show_ev_equity_bridge": has_equity_bridge,
                "show_enterprise_to_equity_bridge": has_equity_bridge,
                "valuation_band_is_meaningful": headline_mid is not None,
                "equity_value_band_is_meaningful": equity_mid is not None,
                "has_upswitch_adaptive_page": False,
                "has_dcf": False,
                "show_dcf_before_calibration": False,
                "has_ebitda_multiple_page": False,
                "has_sde_page": False,
                "has_revenue_multiple_page": False,
                "has_weighted_synthesis": False,
                "show_advisor_multiple_transparency_appendix": False,
                "show_multiple_evidence_appendix": False,
                "show_discount_methodology_appendix": False,
            }
        )


def build_stateless_report_context(
    request: GenerateReportRequest,
    *,
    locale: str,
    verified_assurance_authority: CurrentValuationAssuranceAuthority | None = None,
) -> StatelessReportContext:
    _assert_canonical_report_currency_supported(request)
    from src.services.infrastructure.main_report_data_aggregator import (
        get_main_report_aggregator,
    )
    from src.services.infrastructure.template_service import get_template_service
    from src.services.reports.omni_calc_overrides import apply_omni_calc_overrides
    from src.services.reports.report_pagination import (
        assign_sme_html_footer_page_numbers,
        build_sme_report_page_flags,
        compute_total_pages,
    )
    from src.services.reports.saas_context import build_saas_report_context
    from src.services.reports.sde_channel_applicator import ensure_sde_channel_applied

    template_service = get_template_service()
    aggregation_dict = request_to_aggregation_dict(request)
    aggregator = get_main_report_aggregator()
    template_context = aggregator.aggregate_from_valuation_data(
        aggregation_dict,
        locale=locale,
    )

    apply_omni_calc_overrides(
        template_context,
        aggregation_dict,
        request.selected_method,
        locale=locale,
    )
    ensure_sde_channel_applied(template_context, aggregation_dict, locale=locale)
    template_context.update(
        build_saas_report_context(
            aggregation_dict,
            template_context,
            request.selected_method,
            locale=locale,
        )
    )
    template_context["headline_value_basis"] = request.headline_value_basis
    template_context["value_basis"] = request.headline_value_basis
    # The balance-sheet date the figures were taken from is a separate fact from
    # the valuation date. The legacy adapter dict carries it, but it never
    # reached the rendered context, so the cover could only show "when we
    # valued" and never "as of which accounts".
    template_context["financial_reference_date"] = request.financial_reference_date
    # Sealed advisor judgments. Qualifications are committed to the immutable
    # run (report-time overlays are rejected), but the run's risk_factors never
    # reached the rendered report, so a judgment the advisor sealed — e.g. why
    # a sector reference multiple on a different earnings basis reconciles to
    # this conclusion — stayed invisible to the client it was written for. The
    # source-reconciliation prefixes render in their own evidence box already.
    template_context["advisor_judgment_notes"] = [
        note
        for note in (str(value or "").strip() for value in request.valuation_result.risk_factors)
        if note
        and not note.startswith(
            (
                "Bronreconciliatie:",
                "De management/NBB-verschillen",
                "De NBB-geschiedenis",
            )
        )
    ]
    template_context["methodology_used"] = request.valuation_result.methodology_used
    template_context["equity_bridge_is_illustrative"] = request.equity_bridge_is_illustrative
    if not request.show_asking_price:
        template_context["recommended_asking_price"] = None
    template_context["source_references"] = _sealed_source_references(request)
    if request.report_id:
        template_context["report_id"] = request.report_id
        template_context["report_id_display"] = request.report_id
    _apply_negative_ebitda_recovery_context(template_context, request, locale=locale)
    _apply_enterprise_value_primary_context(template_context, request)
    _apply_disclosed_fallback_context(template_context, request)
    _apply_governed_external_market_context(template_context, request)
    _apply_benchmark_provenance_context(template_context, request)
    _apply_valuation_run_context(template_context, request)
    _apply_canonical_run_headline_context(template_context, request, verified_assurance_authority)
    _apply_canonical_balance_sheet_bridge_context(template_context, request)
    _apply_canonical_multiple_build_up_context(template_context, request)
    _apply_governed_external_market_context(template_context, request)
    _apply_report_option_gates(template_context, request)
    _apply_client_presentation_context(template_context, request)
    finalize_report_context(
        template_context,
        locale=locale,
        refresh_adaptive_gates=True,
        apply_formula_gate=True,
    )
    # Finalization refreshes several legacy report gates. Re-assert the explicit
    # stateless report contract and recompute pagination from the final page set.
    template_context["headline_value_basis"] = request.headline_value_basis
    template_context["value_basis"] = request.headline_value_basis
    # The balance-sheet date the figures were taken from is a separate fact from
    # the valuation date. The legacy adapter dict carries it, but it never
    # reached the rendered context, so the cover could only show "when we
    # valued" and never "as of which accounts".
    template_context["financial_reference_date"] = request.financial_reference_date
    # Sealed advisor judgments. Qualifications are committed to the immutable
    # run (report-time overlays are rejected), but the run's risk_factors never
    # reached the rendered report, so a judgment the advisor sealed — e.g. why
    # a sector reference multiple on a different earnings basis reconciles to
    # this conclusion — stayed invisible to the client it was written for. The
    # source-reconciliation prefixes render in their own evidence box already.
    template_context["advisor_judgment_notes"] = [
        note
        for note in (str(value or "").strip() for value in request.valuation_result.risk_factors)
        if note
        and not note.startswith(
            (
                "Bronreconciliatie:",
                "De management/NBB-verschillen",
                "De NBB-geschiedenis",
            )
        )
    ]
    template_context["methodology_used"] = request.valuation_result.methodology_used
    template_context["equity_bridge_is_illustrative"] = request.equity_bridge_is_illustrative
    if not request.show_asking_price:
        template_context["recommended_asking_price"] = None
    template_context["source_references"] = _sealed_source_references(request)
    if request.report_id:
        template_context["report_id"] = request.report_id
        template_context["report_id_display"] = request.report_id
    _apply_negative_ebitda_recovery_context(template_context, request, locale=locale)
    _apply_enterprise_value_primary_context(template_context, request)
    _apply_disclosed_fallback_context(template_context, request)
    _apply_governed_external_market_context(template_context, request)
    _apply_benchmark_provenance_context(template_context, request)
    _apply_valuation_run_context(template_context, request)
    _apply_canonical_run_headline_context(template_context, request, verified_assurance_authority)
    _apply_canonical_balance_sheet_bridge_context(template_context, request)
    _apply_canonical_multiple_build_up_context(template_context, request)
    _apply_governed_external_market_context(template_context, request)
    _apply_report_option_gates(template_context, request)
    _apply_client_presentation_context(template_context, request)
    _apply_unweighted_lens_disclosure_context(template_context, request)
    _apply_priced_evidence_projection_context(template_context, request)
    from .source_method_publication import apply_sealed_earnings_display

    apply_sealed_earnings_display(template_context, request.valuation_result.valuation_run)
    apply_multiple_report_sensitivity(template_context, request.valuation_result.valuation_run)
    apply_saved_method_sensitivities(template_context)
    # The legacy finalizer mutates method and bridge presentation fields. Run
    # the defensibility gate only after the immutable run has been re-applied,
    # otherwise a stale pre-canonical failure can survive on an exact report.
    apply_gate_to_context(template_context, soft=True)
    # Canonical headline and method applicators above support legacy positive-
    # EBITDA reports and can rewrite monetary presentation fields. Recovery
    # reports finish by reapplying the signed resolution so neither those
    # applicators nor the defensibility gate can become a second authority.
    _apply_negative_ebitda_recovery_context(template_context, request, locale=locale)
    if request.valuation_result.valuation_run is not None:
        _apply_disclosed_fallback_context(template_context, request)
        from src.services.reports.report_annual_earnings import apply_saved_annual_earnings

        apply_saved_annual_earnings(
            template_context,
            request.valuation_result.valuation_run.response_snapshot.get("earnings_basis_ledger"),
        )
        apply_canonical_auxiliary_disclosures(template_context)
        template_context.update(
            build_transaction_readiness_context(template_context, locale=str(locale))
        )
    apply_saved_growth_multiple_scenario(template_context)
    refresh_transaction_price_bridge(template_context, str(locale))
    _apply_report_option_gates(template_context, request)
    template_context["total_pages"] = compute_total_pages(
        build_sme_report_page_flags(template_context)
    )
    assign_sme_html_footer_page_numbers(template_context)

    # BET-458 — honest presentation: an `indicative` valuation (the contract's
    # `present_point_estimate` is False) must headline the low–high range, never a
    # false-precision point. Pre-compute the gate here so the cover template stays a
    # single conditional. The feature flag continues to govern ordinary indicative
    # reports; an explicitly consented disclosed fallback is always range-led, because
    # its missing benchmark evidence is a core, client-visible limitation rather than
    # an experiment that can be dark-launched.
    _valuation_result = getattr(request, "valuation_result", None)
    _multiples_results = getattr(_valuation_result, "multiples_results", None)
    _is_disclosed_fallback = bool(
        isinstance(_multiples_results, dict)
        and _multiples_results.get("multiples_source") == "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
    )
    cast("ReportMap", template_context)["honest_present_range"] = bool(
        getattr(_valuation_result, "present_point_estimate", True) is False
        and (honest_presentation_render_enabled() or _is_disclosed_fallback)
    )
    valuation_run = request.valuation_result.valuation_run
    template_context.update(
        report_assurance_projection(
            valuation_run,
            locale=locale,
            report_scope=request.report_scope,
            assurance_authority=verified_assurance_authority,
        )
    )
    from .range_provenance_projection import project_range_provenance

    template_context["range_provenance_disclosure"] = project_range_provenance(
        valuation_run, locale
    )
    from .source_method_publication import apply_source_method_publication

    apply_source_method_publication(template_context, valuation_run, locale=locale)
    if valuation_run is not None and valuation_run.value_basis == "enterprise_value":
        band = valuation_run.valuation_range
        template_context.update(
            {
                "valuation": band.mid,
                "valuation_low": band.low,
                "valuation_high": band.high,
                "headline_value_basis": "enterprise_value",
                "is_enterprise_value_primary": True,
                "equity_value": None,
                "equity_value_mid": None,
                "equity_value_low": None,
                "equity_value_high": None,
                "equity_value_band_is_meaningful": False,
                "recommended_asking_price": None,
                "net_debt": None,
                "show_ev_equity_bridge": False,
                "show_enterprise_to_equity_bridge": False,
            }
        )
    if request.report_scope == "automated_indicative":
        from .automated_indicative_policy import automatic_report_context

        template_context.update(automatic_report_context(locale))

    return StatelessReportContext(
        template_context=template_context,
        template_service=template_service,
    )
