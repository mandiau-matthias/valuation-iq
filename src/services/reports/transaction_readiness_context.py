"""Transaction-readiness context for SME valuation reports.

This module translates the valuation report context into a first-pass
deal-room checklist: price mechanics, evidence, buyer challenges, SPA
implications, and legal handoff status.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.services.reports.transaction_readiness_labels import fallback_label as _fallback_label
from src.services.reports.transaction_readiness_labels import (
    price_mechanism_label as _price_mechanism_label,
)
from src.services.reports.transaction_readiness_labels import severity_label as _severity_label
from src.services.reports.transaction_readiness_labels import spa_area_label as _spa_area_label
from src.services.reports.transaction_readiness_labels import (
    spa_instrument_label as _spa_instrument_label,
)
from src.services.reports.transaction_readiness_labels import status_label as _status_label
from src.services.reports.transaction_readiness_labels import text as _text
from src.services.reports.transaction_readiness_package import (
    legal_release_status as _legal_release_status,
)
from src.services.reports.transaction_readiness_package_state import BuyerPackageState
from src.services.reports.transaction_readiness_package_state import (
    attach_buyer_package_manifest as _attach_buyer_package_manifest,
)
from src.services.reports.transaction_readiness_package_state import (
    build_buyer_package_state as _buyer_package_state,
)
from src.services.reports.transaction_readiness_strength_factor_lineage import (
    owner_strength_factor_lineage as _owner_strength_factor_lineage,
)

JsonMap = dict[str, object]


@dataclass(frozen=True)
class MemoReadinessState:
    missing_count: int
    review_count: int
    blocked_count: int
    score: int
    report_handoff_status: str
    legal_release_status: str


def _as_dict(value: object) -> JsonMap:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return _as_dict(dumped)
    return {}


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _num(value: object, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional(value: object) -> object | None:
    return value or None


def _first_text(context: JsonMap, *keys: str) -> str:
    for key in keys:
        value = context.get(key)
        if value:
            return str(value)
    return ""


def _official_data_health_failed(data_health: object) -> bool:
    """Whether the official-filing fetch failed and returned branded boilerplate only.

    Delphi writes `state`; the report templates read `status` first — accept both.
    """
    if not isinstance(data_health, Mapping):
        return False
    states = {str(data_health.get(key) or "").strip().lower() for key in ("state", "status")}
    return bool(states & {"degraded", "unavailable", "disabled", "error", "failed"})


def _clean_text(value: object) -> str:
    return str(value).strip() if value is not None and str(value).strip() else ""


def _text_items(value: object) -> list[str]:
    return [_clean_text(item) for item in _as_list(value) if _clean_text(item)]


def _row_by_id(rows: list[JsonMap], row_id: str) -> JsonMap:
    return next((row for row in rows if row.get("id") == row_id), {})


def _challenge_by_code(challenges: list[JsonMap], code: str) -> JsonMap:
    return next((challenge for challenge in challenges if challenge.get("code") == code), {})


def _evidence_row(
    *,
    evidence_id: str,
    label: str,
    status: str,
    consequence: str,
    source: str | None = None,
) -> JsonMap:
    return {
        "id": evidence_id,
        "label": label,
        "status": status,
        "status_label": _fallback_label(status),
        "source": source,
        "transaction_consequence": consequence,
    }


def _method_debt_overhangs(context: JsonMap) -> list[JsonMap]:
    overhangs: list[JsonMap] = []
    method_results = _as_dict(context.get("method_results_by_key"))
    for method_key, method in method_results.items():
        method_map = _as_dict(method)
        details = _as_dict(method_map.get("details"))
        debt_overhang = _num(details.get("debt_overhang"))
        if debt_overhang <= 0:
            continue
        overhangs.append(
            {
                "method_key": method_key,
                "label": method_map.get("label") or method_key,
                "equity_value": method_map.get("value") or details.get("equity_value"),
                "debt_overhang": debt_overhang,
                "net_debt": details.get("net_debt"),
            }
        )
    return overhangs


def _build_price_bridge(context: JsonMap, locale: str) -> JsonMap:
    price_mechanism = (
        "completion_accounts"
        if context.get("has_balance_data")
        else "locked_box_not_recommended_until_balance_sheet_verified"
    )
    is_holding_sotp = bool(context.get("is_holding_sotp_report"))

    # ``valuation*`` is the selected headline basis.  For an equity-primary
    # holding SOTP it therefore contains the group equity range, even though
    # the immutable run also carries a distinct entity-aggregated EV range.
    # The transaction memo must disclose both canonical bases instead of
    # relabelling the equity headline as EV. Prefer explicit EV for every
    # method; the legacy fallback is only valid for an EV headline.
    if is_holding_sotp:
        enterprise_value_low = context.get("enterprise_value_low")
        enterprise_value_mid = context.get("enterprise_value_mid")
        enterprise_value_high = context.get("enterprise_value_high")
        bridge_basis = "holding_sotp_group_ev_to_equity"
    elif context.get("enterprise_value_mid") is not None:
        enterprise_value_low = context.get("enterprise_value_low")
        enterprise_value_mid = context.get("enterprise_value_mid")
        enterprise_value_high = context.get("enterprise_value_high")
        bridge_basis = "cash_free_debt_free_equity_bridge"
    elif (
        context.get("headline_value_basis", context.get("value_basis", "enterprise_value"))
        == "enterprise_value"
    ):
        enterprise_value_low = context.get("valuation_low")
        enterprise_value_mid = context.get("valuation")
        enterprise_value_high = context.get("valuation_high")
        bridge_basis = "cash_free_debt_free_equity_bridge"
    else:
        enterprise_value_low = enterprise_value_mid = enterprise_value_high = None
        bridge_basis = "enterprise_value_unavailable"

    return {
        "basis": bridge_basis,
        "enterprise_value_low_eur": enterprise_value_low,
        "enterprise_value_mid_eur": enterprise_value_mid,
        "enterprise_value_high_eur": enterprise_value_high,
        "equity_value_low_eur": context.get("equity_value_low"),
        "equity_value_mid_eur": context.get("equity_value"),
        "equity_value_high_eur": context.get("equity_value_high"),
        "recommended_asking_price_eur": context.get("recommended_asking_price"),
        "net_debt_eur": context.get("net_debt"),
        "nwc_adjustment_eur": (
            context.get("nwc_adjustment")
            if context.get("nwc_adjustment") is not None
            else context.get("nwc_surplus_deficit")
        ),
        "currency": context.get("report_currency", context.get("currency")),
        "source_run_id": context.get("valuation_run_id"),
        "source_run_hash": context.get("valuation_run_hash"),
        "tax_latency_net_impact_eur": context.get("tax_latency_net_impact"),
        "bridge_residual_eur": context.get("bridge_residual"),
        "equity_equals_ev_pending_balance": bool(
            context.get("equity_value_assumed_equal_ev_due_to_missing_balance")
        ),
        "price_mechanism_default": price_mechanism,
        "price_mechanism_label": _price_mechanism_label(price_mechanism, locale),
    }


def refresh_transaction_price_bridge(context: JsonMap, locale: str) -> None:
    """Refresh monetary projections after the canonical conclusion is restored."""
    bridge = _build_price_bridge(context, locale)
    context["transaction_price_bridge"] = bridge
    context["buyer_ready_pricing"] = bridge


def _market_benchmark_status(*, benchmark_sample: int, has_benchmark_source: bool) -> str:
    if benchmark_sample >= 3:
        return "present"
    if has_benchmark_source:
        return "review"
    return "missing"


def _corporate_identity_status(*, has_registry: bool, has_ubo_clearance: bool) -> str:
    if has_registry and has_ubo_clearance:
        return "present"
    if has_registry:
        return "review"
    return "missing"


def _normalised_ebitda_status(*, has_adjustments: bool, has_multi_year: bool) -> str:
    if has_adjustments or has_multi_year:
        return "present"
    return "review"


def _has_owner_transferability(context: JsonMap) -> bool:
    return bool(context.get("owner_risk_ledger")) or bool(
        context.get("show_owner_profiling_section")
    )


def _revenue_quality_source(context: JsonMap) -> str:
    return ", ".join(
        str(row.get("label"))
        for row in _as_list(context.get("revenue_quality_summary_rows"))
        if isinstance(row, Mapping) and row.get("label")
    )


def _revenue_quality_evidence_row(context: JsonMap, locale: str) -> JsonMap:
    return _evidence_row(
        evidence_id="revenue_quality",
        label=_text(
            locale,
            "Omzetkwaliteit",
            "Revenue quality",
            "Qualité du chiffre d'affaires",
        ),
        status="present",
        source=_revenue_quality_source(context),
        consequence=_text(
            locale,
            "Terugkerende omzet, concentratie en backlog moeten aansluiten op contracten of omzetanalyse.",
            "Recurring revenue, concentration and backlog must reconcile to contracts or revenue analysis.",
            "Le chiffre d'affaires récurrent, la concentration et le carnet de commandes doivent se rapprocher des contrats ou de l'analyse du chiffre d'affaires.",
        ),
    )


def _build_evidence_checklist(context: JsonMap, locale: str) -> list[JsonMap]:
    benchmark_sample = int(_num(context.get("benchmark_sample_size")))
    has_benchmark_source = bool(context.get("benchmark_data_source"))
    has_balance_data = bool(context.get("has_balance_data"))
    has_official_financials = bool(context.get("has_official_financials"))
    # A failed Staatsbladmonitor/NBB fetch still ships the branded stub: source_label
    # "NBB filing via Staatsbladmonitor", both source_links, every figure null and
    # data_health "degraded". Printing that as `Bewijs:` claims evidence the report does
    # not have, so only name the filing when the snapshot is healthy.
    official_snapshot_usable = has_official_financials and not _official_data_health_failed(
        context.get("official_data_health")
    )
    official_evidence_source = (
        _first_text(context, "official_source_label", "official_source")
        if official_snapshot_usable
        else ""
    )
    adjustment_rows = _as_list(context.get("ebitda_adjustments"))
    # Base/result anchors are structural rows, not EBITDA normalisations.
    # Treating their presence as a completed normalisation bridge can turn an
    # explicitly unnormalised earnings basis into a green buyer-readiness item.
    has_adjustments = any(
        not isinstance(row, Mapping)
        or str(row.get("type") or "").strip().lower() not in {"base", "result"}
        for row in adjustment_rows
    )
    headline_ebitda_is_reported = bool(context.get("headline_ebitda_is_reported"))
    has_multi_year = len(_as_list(context.get("multi_year_ebitda"))) >= 2
    has_method_map = bool(_as_dict(context.get("method_results_by_key")))
    has_registry = bool(context.get("registration_number"))
    has_revenue_quality_inputs = bool(context.get("has_revenue_quality_inputs"))
    aml_status = str(context.get("aml_clearance_status") or "").strip().lower()
    has_ubo_clearance = bool(context.get("ubo_verified") or aml_status in {"clear", "cleared"})
    has_owner = _has_owner_transferability(context)
    owner_transferability_row = _evidence_row(
        evidence_id="owner_transferability",
        label=_text(
            locale,
            "Eigenaarsafhankelijkheid en overdraagbaarheid",
            "Owner dependency and transferability",
            "Dépendance au dirigeant et transférabilité",
        ),
        status="present" if has_owner else "review",
        consequence=_text(
            locale,
            "Hoge afhankelijkheid wordt vaak vertaald in earn-out, retentiebeding of prijsdruk.",
            "High dependency often becomes earn-out, retention covenant or price pressure.",
            "Une forte dépendance se traduit souvent par un earn-out, une clause de rétention ou une pression sur le prix.",
        ),
    )
    owner_transferability_row.update(_owner_strength_factor_lineage(context, locale))

    evidence_rows = [
        _evidence_row(
            evidence_id="financial_statements",
            label=_text(
                locale,
                "Jaarrekening en financiële basis",
                "Financial statements and base data",
                "Comptes annuels et données de base",
            ),
            status="present" if official_snapshot_usable else "review",
            # `_evidence_row` omits the Bewijs line entirely when `source` is falsy.
            source=official_evidence_source or None,
            consequence=_text(
                locale,
                "Zonder officiële aansluiting zal koper reconciliatie vragen.",
                "Without official-source alignment, buyer will ask for reconciliation.",
                "Sans rapprochement aux sources officielles, l'acquéreur demandera une réconciliation.",
            ),
        ),
        _evidence_row(
            evidence_id="normalised_ebitda_bridge",
            label=_text(
                locale,
                (
                    "Gerapporteerde EBITDA-basis — normalisatie openstaand"
                    if headline_ebitda_is_reported
                    else "Genormaliseerde EBITDA-brug"
                ),
                (
                    "Reported EBITDA basis — normalization outstanding"
                    if headline_ebitda_is_reported
                    else "Normalised EBITDA bridge"
                ),
                (
                    "Base d'EBITDA publiée — normalisation en attente"
                    if headline_ebitda_is_reported
                    else "Pont d'EBITDA normalisé"
                ),
            ),
            status=(
                "review"
                if headline_ebitda_is_reported
                else _normalised_ebitda_status(
                    has_adjustments=has_adjustments,
                    has_multi_year=has_multi_year,
                )
            ),
            consequence=_text(
                locale,
                (
                    "Eigenaars-/titularisvergoeding, inzet en vervangingskost moeten nog worden bewezen; de waardering gebruikt gerapporteerde, niet-genormaliseerde EBITDA."
                    if headline_ebitda_is_reported
                    else "Normalisaties zonder bewijs worden prijsdiscussies of escrow-items."
                ),
                (
                    "Owner/titular remuneration, involvement and replacement cost remain to be evidenced; the valuation uses reported, unnormalised EBITDA."
                    if headline_ebitda_is_reported
                    else "Unsupported normalisations become price chips or escrow items."
                ),
                (
                    "La rémunération et l'implication du titulaire ainsi que le coût de remplacement restent à justifier ; la valorisation utilise l'EBITDA publié non normalisé."
                    if headline_ebitda_is_reported
                    else "Les normalisations non justifiées deviennent des points de négociation de prix ou des montants sous séquestre."
                ),
            ),
        ),
        _evidence_row(
            evidence_id="balance_sheet_net_debt",
            label=_text(
                locale,
                "Balans, nettoschuld en werkkapitaal",
                "Balance sheet, net debt and working capital",
                "Bilan, dette nette et fonds de roulement",
            ),
            status=(
                "review"
                if has_balance_data
                and context.get("valuation_run")
                and not context.get("has_nwc_normalization")
                else "present" if has_balance_data else "missing"
            ),
            consequence=_text(
                locale,
                "Koper zal een cash- en schuldenvrije prijs en werkkapitaalmechaniek niet accepteren zonder balansbewijs.",
                "Buyer will not accept cash-free/debt-free pricing or working-capital mechanics without balance evidence.",
                "L'acquéreur n'acceptera pas un prix « cash-free/debt-free » ni un mécanisme de fonds de roulement sans preuve du bilan.",
            ),
        ),
        _evidence_row(
            evidence_id="market_benchmark",
            label=_text(
                locale,
                "Transactiebenchmark en multiple",
                "Transaction benchmark and multiple",
                "Référence transactionnelle et multiple",
            ),
            status=_market_benchmark_status(
                benchmark_sample=benchmark_sample,
                has_benchmark_source=has_benchmark_source,
            ),
            source=(
                _first_text(context, "benchmark_data_source")
                if context.get("valuation_run")
                else _first_text(context, "benchmark_data_source", "multiple_source")
            ),
            consequence=_text(
                locale,
                "Dunne benchmarks verhogen het risico op multiple haircut.",
                "Thin benchmarks increase the risk of a multiple haircut.",
                "Des références peu nombreuses augmentent le risque de décote du multiple.",
            ),
        ),
        _evidence_row(
            evidence_id="method_trace",
            label=_text(
                locale,
                "Methodekaart en methodologische onderbouwing",
                "Method map and methodology substantiation",
                "Carte des méthodes et justification méthodologique",
            ),
            status="present" if has_method_map else "missing",
            consequence=_text(
                locale,
                "Elk prijsanker moet naar een methode, input en beperking traceerbaar zijn.",
                "Every price anchor must trace to a method, input and limitation.",
                "Chaque ancrage de prix doit être traçable jusqu'à une méthode, une donnée d'entrée et une limite.",
            ),
        ),
        _evidence_row(
            evidence_id="corporate_identity_ubo",
            label=_text(
                locale,
                "Vennootschap, registratie en UBO",
                "Corporate identity, registry and UBO",
                "Identité de la société, registre et bénéficiaire effectif (UBO)",
            ),
            status=_corporate_identity_status(
                has_registry=has_registry,
                has_ubo_clearance=has_ubo_clearance,
            ),
            consequence=_text(
                locale,
                "Registratie is niet hetzelfde als UBO/AML-clearing; juridische beoordeling blijft nodig.",
                "Registry evidence is not UBO/AML clearance; legal review remains required.",
                "La preuve d'immatriculation ne vaut pas vérification UBO/AML ; une revue juridique reste nécessaire.",
            ),
        ),
        owner_transferability_row,
    ]
    if has_revenue_quality_inputs:
        evidence_rows.insert(4, _revenue_quality_evidence_row(context, locale))
    return evidence_rows


def _build_revenue_quality_snapshot(context: JsonMap, locale: str) -> JsonMap:
    rows = [
        dict(row)
        for row in _as_list(context.get("revenue_quality_summary_rows"))
        if isinstance(row, Mapping)
    ]
    if not rows:
        return {}
    return {
        "title": _text(
            locale, "Omzetkwaliteit", "Revenue quality", "Qualité du chiffre d'affaires"
        ),
        "latest_revenue_eur": context.get("revenue_quality_latest_revenue_eur"),
        "rows": rows,
    }


def _build_buyer_challenges(
    context: JsonMap,
    evidence_rows: list[JsonMap],
    debt_overhangs: list[JsonMap],
    locale: str,
) -> list[JsonMap]:
    challenges: list[JsonMap] = []
    weak_evidence = [row for row in evidence_rows if row.get("status") in {"missing", "review"}]
    benchmark_sample = int(_num(context.get("benchmark_sample_size")))
    if benchmark_sample and benchmark_sample < 3:
        challenges.append(
            {
                "code": "thin_comparables",
                "severity": "high",
                "challenge": _text(
                    locale,
                    "Koper kan de multiple betwisten wegens een dunne vergelijkingsbasis.",
                    "Buyer may challenge the multiple because the comparable set is thin.",
                    "L'acquéreur peut contester le multiple en raison d'une base de comparables limitée.",
                ),
                "likely_price_effect": "multiple_haircut",
                "rebuttal_evidence_needed": "additional_sector_transactions_or_advisor_benchmark",
            }
        )
    if not context.get("has_balance_data"):
        challenges.append(
            {
                "code": "unverified_net_debt_wc",
                "severity": "high",
                "challenge": _text(
                    locale,
                    "Koper kan de prijs openhouden tot nettoschuld en werkkapitaal zijn onderbouwd.",
                    "Buyer may keep price open until net debt and working capital are evidenced.",
                    "L'acquéreur peut laisser le prix ouvert tant que la dette nette et le fonds de roulement ne sont pas justifiés.",
                ),
                "likely_price_effect": "completion_accounts_adjustment",
                "rebuttal_evidence_needed": "balance_sheet_debt_schedule_wc_analysis",
            }
        )
    if debt_overhangs:
        challenges.append(
            {
                "code": "debt_overhang",
                "severity": "critical",
                "challenge": _text(
                    locale,
                    "De schuldpositie overstijgt de ondernemingswaarde in minstens één methode.",
                    "Debt exceeds enterprise value in at least one method.",
                    "L'endettement dépasse la valeur d'entreprise dans au moins une méthode.",
                ),
                "likely_price_effect": "restructuring_or_negative_equity_discussion",
                "rebuttal_evidence_needed": "debt_schedule_refinancing_or_asset_carve_out",
                "affected_methods": debt_overhangs,
            }
        )

    owner_transferability = _row_by_id(evidence_rows, "owner_transferability")
    owner_discount_key = _clean_text(owner_transferability.get("multiple_discount_key"))
    owner_data_point_ids = _text_items(owner_transferability.get("strength_factor_data_point_ids"))
    if owner_discount_key or owner_data_point_ids:
        challenge_text = _text(
            locale,
            "Koper zal testen of eigenaarsafhankelijkheid retentieverplichtingen, earn-outmechaniek of multiple-druk rechtvaardigt.",
            "Buyer will test whether owner dependency supports retention obligations, earn-out mechanics or multiple pressure.",
            "L'acquéreur vérifiera si la dépendance au dirigeant justifie des obligations de rétention, un earn-out ou une pression sur le multiple.",
        )
        if owner_discount_key:
            challenge_text = (
                f"{challenge_text} "
                f"{_text(locale, 'Multiplekorting', 'Multiple discount', 'Décote de multiple')}: "
                f"{owner_discount_key}."
            )
        if owner_data_point_ids:
            challenge_text = (
                f"{challenge_text} "
                f"{_text(locale, 'Datapunten', 'Data points', 'Points de données')}: "
                f"{', '.join(owner_data_point_ids[:4])}."
            )

        challenges.append(
            {
                "code": "owner_transferability_discount",
                "severity": "high",
                "challenge": challenge_text,
                "likely_price_effect": "owner_retention_earn_out_or_multiple_haircut",
                "rebuttal_evidence_needed": _clean_text(
                    owner_transferability.get("rebuttal_evidence_needed")
                )
                or "owner_transition_plan_customer_relationships_second_line_management",
                "source": _clean_text(owner_transferability.get("source")),
                "multiple_discount_key": owner_discount_key or None,
                "strength_factor_keys": _text_items(
                    owner_transferability.get("strength_factor_keys")
                ),
                "strength_factor_data_point_ids": owner_data_point_ids,
            }
        )
    if len(weak_evidence) >= 4:
        challenges.append(
            {
                "code": "data_room_not_ready",
                "severity": "high",
                "challenge": _text(
                    locale,
                    "Ontbrekende documentatie kan leiden tot diligencevertraging en prijsdruk.",
                    "Missing documentation may lead to diligence delay and price pressure.",
                    "Une documentation manquante peut entraîner un retard de due diligence et une pression sur le prix.",
                ),
                "likely_price_effect": "escrow_or_process_delay",
                "rebuttal_evidence_needed": "completed_data_room_manifest",
            }
        )
    return challenges


def _build_spa_implications(
    context: JsonMap,
    evidence_rows: list[JsonMap],
    buyer_challenges: list[JsonMap],
    locale: str,
) -> list[JsonMap]:
    implications: list[JsonMap] = []
    if context.get("has_balance_data"):
        implications.append(
            {
                "area": "price_mechanics",
                "area_label": _spa_area_label("price_mechanics", locale),
                "instrument": "completion_accounts_or_locked_box_with_leakage_covenant",
                "instrument_label": _spa_instrument_label(
                    "completion_accounts_or_locked_box_with_leakage_covenant",
                    locale,
                ),
                "note": _text(
                    locale,
                    "Leg nettoschuld, cash en werkkapitaal expliciet vast in de SPA.",
                    "Define net debt, cash and working capital explicitly in the SPA.",
                    "Définissez explicitement la dette nette, la trésorerie et le fonds de roulement dans le SPA.",
                ),
            }
        )
    else:
        implications.append(
            {
                "area": "price_mechanics",
                "area_label": _spa_area_label("price_mechanics", locale),
                "instrument": "completion_accounts_required",
                "instrument_label": _spa_instrument_label(
                    "completion_accounts_required",
                    locale,
                ),
                "note": _text(
                    locale,
                    "Locked-box-mechaniek is niet geschikt zonder gevalideerde balans.",
                    "Locked-box mechanics are not suitable without a validated balance sheet.",
                    "Le mécanisme locked-box n'est pas adapté sans bilan validé.",
                ),
            }
        )

    if any(row.get("status") == "missing" for row in evidence_rows):
        implications.append(
            {
                "area": "disclosure_schedule",
                "area_label": _spa_area_label("disclosure_schedule", locale),
                "instrument": "seller_disclosure_and_document_completion",
                "instrument_label": _spa_instrument_label(
                    "seller_disclosure_and_document_completion",
                    locale,
                ),
                "note": _text(
                    locale,
                    "Ontbrekende stukken moeten voor signing worden aangevuld of als disclosure worden opgenomen.",
                    "Missing documents must be completed before signing or scheduled as disclosures.",
                    "Les pièces manquantes doivent être complétées avant la signature ou intégrées en annexe de divulgation.",
                ),
            }
        )

    owner_challenge = _challenge_by_code(buyer_challenges, "owner_transferability_discount")
    if owner_challenge:
        owner_discount_key = _clean_text(owner_challenge.get("multiple_discount_key"))
        note = _text(
            locale,
            "Vertaal eigenaarsafhankelijkheid naar overdrachtsplichten, bewijs voor kopersdiligence en waar nodig earn-out- of retentiemechaniek.",
            "Translate owner-dependency evidence into transition duties, buyer diligence proof and, where needed, earn-out or retention mechanics.",
            "Traduisez la dépendance au dirigeant en obligations de transition, preuves de diligence acquéreur et, si nécessaire, mécanismes d'earn-out ou de rétention.",
        )
        if owner_discount_key:
            note = (
                f"{note} "
                f"{_text(locale, 'Multiplekorting', 'Multiple discount', 'Décote de multiple')}: "
                f"{owner_discount_key}."
            )
        implications.append(
            {
                "area": "management_continuity",
                "area_label": _spa_area_label("management_continuity", locale),
                "instrument": "owner_transition_covenant_or_earn_out",
                "instrument_label": _spa_instrument_label(
                    "owner_transition_covenant_or_earn_out",
                    locale,
                ),
                "note": note,
                "source": _clean_text(owner_challenge.get("source")),
                "rebuttal_evidence_needed": _clean_text(
                    owner_challenge.get("rebuttal_evidence_needed")
                ),
                "multiple_discount_key": owner_discount_key or None,
                "strength_factor_data_point_ids": _text_items(
                    owner_challenge.get("strength_factor_data_point_ids")
                ),
            }
        )

    if any(challenge.get("severity") == "critical" for challenge in buyer_challenges):
        implications.append(
            {
                "area": "risk_allocation",
                "area_label": _spa_area_label("risk_allocation", locale),
                "instrument": "specific_indemnity_or_restructuring_condition",
                "instrument_label": _spa_instrument_label(
                    "specific_indemnity_or_restructuring_condition",
                    locale,
                ),
                "note": _text(
                    locale,
                    "Kritieke prijsrisico's vragen specifieke vrijwaring, escrow of closing condition.",
                    "Critical price risks require specific indemnity, escrow or closing condition.",
                    "Les risques de prix critiques exigent une indemnité spécifique, un séquestre ou une condition de closing.",
                ),
            }
        )
    return implications


def _memo_readiness_state(
    evidence_rows: list[JsonMap],
    buyer_challenges: list[JsonMap],
) -> MemoReadinessState:
    missing_count = sum(1 for row in evidence_rows if row.get("status") == "missing")
    review_count = sum(1 for row in evidence_rows if row.get("status") == "review")
    blocked_count = sum(
        1 for challenge in buyer_challenges if challenge.get("severity") == "critical"
    )
    score = max(0, 100 - missing_count * 18 - review_count * 8 - blocked_count * 20)
    report_handoff_status = (
        "blocked"
        if blocked_count
        else "lawyer_review_required" if missing_count or review_count else "ready"
    )
    return MemoReadinessState(
        missing_count=missing_count,
        review_count=review_count,
        blocked_count=blocked_count,
        score=score,
        report_handoff_status=report_handoff_status,
        legal_release_status=_legal_release_status(report_handoff_status),
    )


def _build_legal_readiness(
    context: JsonMap,
    evidence_rows: list[JsonMap],
    memo_state: MemoReadinessState,
) -> JsonMap:
    return {
        "jurisdiction": context.get("country_code") or context.get("registry_country_code") or "BE",
        "deal_structure": "share_deal",
        "buyer_release_status": memo_state.legal_release_status,
        "counsel_review_required": True,
        "clear_count": len(evidence_rows) - memo_state.missing_count - memo_state.review_count,
        "review_count": memo_state.review_count,
        "blocked_count": memo_state.blocked_count + memo_state.missing_count,
        "score": memo_state.score,
    }


def _transaction_readiness_summary(
    *,
    is_specialty: bool,
    memo_state: MemoReadinessState,
    package_state: BuyerPackageState,
    locale: str,
) -> JsonMap:
    return {
        "enabled": not is_specialty,
        "score": memo_state.score,
        "memo_readiness_score": memo_state.score,
        "buyer_package_readiness_score": package_state.buyer_package_score,
        "display_readiness_score": package_state.display_readiness_score,
        "package_integrity_issue_count": package_state.package_integrity_issue_count,
        "has_buyer_package_manifest": package_state.has_buyer_package_manifest,
        "package_gate_active": package_state.package_gate_active,
        "report_handoff_status": memo_state.report_handoff_status,
        "report_handoff_status_label": _status_label(
            memo_state.report_handoff_status,
            locale,
        ),
        "full_buyer_package_status": package_state.package_status,
        "full_buyer_package_status_label": _status_label(package_state.package_status, locale),
        "full_buyer_package_requested": package_state.full_package_requested,
        "buyer_release_status": memo_state.legal_release_status,
        "buyer_release_status_label": _status_label(memo_state.legal_release_status, locale),
        "effective_buyer_release_status": package_state.effective_buyer_release_status,
        "effective_buyer_release_status_label": _status_label(
            package_state.effective_buyer_release_status,
            locale,
        ),
        "missing_evidence_count": memo_state.missing_count,
        "review_evidence_count": memo_state.review_count,
        "critical_challenge_count": memo_state.blocked_count,
        "package_status": package_state.package_status,
        "package_status_label": _status_label(package_state.package_status, locale),
        "missing_package_artifact_count": package_state.missing_artifact_count,
        "review_package_artifact_count": package_state.review_artifact_count,
        "blocked_package_artifact_count": package_state.blocked_artifact_count,
        "duplicate_package_artifact_types": package_state.duplicate_artifact_types,
        "invalid_package_status": _optional(package_state.invalid_package_status),
        "invalid_package_artifact_statuses": package_state.invalid_artifact_statuses,
        "artifact_count_mismatch": _optional(package_state.artifact_count_mismatch),
        "invalid_valuation_pdf_status": _optional(package_state.invalid_valuation_pdf_status),
        "valuation_pdf_status_mismatch": _optional(package_state.valuation_pdf_status_mismatch),
        "package_release_status": _optional(package_state.manifest_release_status),
        "effective_package_release_status": (
            _optional(package_state.effective_manifest_release_status)
        ),
        "invalid_package_release_status": _optional(package_state.invalid_manifest_release_status),
        "package_release_status_mismatch": _optional(
            package_state.manifest_release_status_mismatch
        ),
        "missing_package_artifacts": package_state.missing_artifact_labels,
    }


def build_transaction_readiness_context(
    context: JsonMap,
    *,
    locale: str,
    metadata: Mapping[str, object] | None = None,
) -> JsonMap:
    """Return transaction-pack primitives derived from valuation context."""
    is_specialty = bool(
        context.get("is_startup_valuation_report")
        or context.get("is_liquidation_report")
        or context.get("is_fiscal_method_only")
    )
    evidence_rows = _build_evidence_checklist(context, locale)
    for row in evidence_rows:
        row["status_label"] = _status_label(row.get("status"), locale)
    debt_overhangs = _method_debt_overhangs(context)
    buyer_challenges = _build_buyer_challenges(context, evidence_rows, debt_overhangs, locale)
    for challenge in buyer_challenges:
        challenge["severity_label"] = _severity_label(challenge.get("severity"), locale)
    spa_implications = _build_spa_implications(context, evidence_rows, buyer_challenges, locale)

    memo_state = _memo_readiness_state(evidence_rows, buyer_challenges)
    price_bridge = _build_price_bridge(context, locale)
    revenue_quality_snapshot = _build_revenue_quality_snapshot(context, locale)
    legal_readiness = _build_legal_readiness(context, evidence_rows, memo_state)
    package_context = {
        **context,
        "transaction_buyer_challenges": buyer_challenges,
    }
    package_state = _buyer_package_state(
        package_context,
        locale=locale,
        metadata=metadata,
        legal_release_status=memo_state.legal_release_status,
        memo_readiness_score=memo_state.score,
    )

    result: JsonMap = {
        "transaction_readiness": _transaction_readiness_summary(
            is_specialty=is_specialty,
            memo_state=memo_state,
            package_state=package_state,
            locale=locale,
        ),
        "show_transaction_readiness_section": not is_specialty,
        "transaction_price_bridge": price_bridge,
        "transaction_revenue_quality": revenue_quality_snapshot,
        "transaction_evidence_checklist": evidence_rows,
        "transaction_buyer_challenges": buyer_challenges,
        "transaction_spa_implications": spa_implications,
        "transaction_debt_overhangs": debt_overhangs,
        "transaction_package_manifest": package_state.formal_package_manifest,
        "buyer_ready_pricing": price_bridge,
        "buyer_ready_revenue_quality": revenue_quality_snapshot,
        "buyer_ready_legal_readiness": legal_readiness,
    }
    _attach_buyer_package_manifest(result, package_state)
    return result
