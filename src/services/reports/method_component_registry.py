"""Report component registry for valuation methods.

This module is the report-side contract for what each valuation method must
surface in an enterprise SME valuation pack. It does not decide whether a
method is selected; it describes the components, evidence fields, and
methodology references expected when that method appears.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from src.domain.method_keys import normalize_method_key


@dataclass(frozen=True)
class MethodReportComponent:
    component_id: str
    label_en: str
    label_nl: str
    required_context_keys: tuple[str, ...] = field(default_factory=tuple)
    optional_context_keys: tuple[str, ...] = field(default_factory=tuple)
    evidence_level: str = "supporting"

    def as_template_context(self) -> dict[str, object]:
        return {
            "id": self.component_id,
            "label_en": self.label_en,
            "label_nl": self.label_nl,
            "required_context_keys": list(self.required_context_keys),
            "optional_context_keys": list(self.optional_context_keys),
            "evidence_level": self.evidence_level,
        }


@dataclass(frozen=True)
class MethodReportProfile:
    method_key: str
    label_en: str
    label_nl: str
    label_fr: str
    subtitle_en: str
    subtitle_nl: str
    subtitle_fr: str
    sources: tuple[str, ...]
    components: tuple[MethodReportComponent, ...]
    aliases: tuple[str, ...] = field(default_factory=tuple)
    section_ids: tuple[str, ...] = field(default_factory=tuple)
    combinable: bool = True
    # NL translation of the `sources` list — author + year stay in their
    # published English form (universal academic convention), only the
    # short descriptor after the dash is translated.  When unset, the
    # template falls back to `sources` so an unmigrated profile still
    # renders cleanly (just in English).
    sources_nl: tuple[str, ...] | None = None
    sources_fr: tuple[str, ...] | None = None

    def required_context_keys(self) -> tuple[str, ...]:
        keys: list[str] = []
        for component in self.components:
            keys.extend(component.required_context_keys)
        return tuple(dict.fromkeys(keys))

    def as_template_context(self) -> dict[str, object]:
        return {
            "method_key": self.method_key,
            "aliases": list(self.aliases),
            "label_en": self.label_en,
            "label_nl": self.label_nl,
            "label_fr": self.label_fr,
            "subtitle_en": self.subtitle_en,
            "subtitle_nl": self.subtitle_nl,
            "subtitle_fr": self.subtitle_fr,
            "sources": list(self.sources),
            "sources_nl": list(self.sources_nl)
            if self.sources_nl
            else list(self.sources),
            "sources_fr": list(self.sources_fr)
            if self.sources_fr
            else list(self.sources),
            "section_ids": list(self.section_ids),
            "combinable": self.combinable,
            "required_context_keys": list(self.required_context_keys()),
            "components": [
                component.as_template_context() for component in self.components
            ],
        }


METHOD_REPORT_PROFILES: tuple[MethodReportProfile, ...] = (
    MethodReportProfile(
        method_key="upswitch_adaptive",
        aliases=("adaptive", "hybrid_adaptive"),
        label_en="Upswitch Adaptive",
        label_nl="Upswitch Adaptive",
        label_fr="Upswitch Adaptive",
        subtitle_en="Hybrid weighted methodology, business-type-tuned",
        subtitle_nl="Gewogen hybride methodologie, afgestemd op bedrijfstype",
        subtitle_fr="Methodologie hybride pondérée, ajustée au type d'entreprise",
        sources=(
            "Koller, Goedhart & Wessels (2020) - weighted EBITDA reconciliation",
            "Damodaran (2012) - multiples methodology and adjustment vehicle",
            "Trugman (2017) - SME size and owner-dependency calibration",
            "Pratt & Niculita (2008) - multi-method reconciliation",
            "IVS 2022 - range methodology selection",
            "Duff & Phelps (2024) - size premium and cost of capital",
        ),
        sources_nl=(
            "Koller, Goedhart & Wessels (2020) - gewogen EBITDA-reconciliatie",
            "Damodaran (2012) - multiples-methodologie en aanpassingsvehikel",
            "Trugman (2017) - omvang- en eigenaarsafhankelijkheidskalibratie MKB",
            "Pratt & Niculita (2008) - reconciliatie van meerdere methodes",
            "IVS 2022 - keuze van bandbreedte-methodologie",
            "Duff & Phelps (2024) - size premium en kapitaalkosten",
        ),
        sources_fr=(
            "Koller, Goedhart & Wessels (2020) - rapprochement EBITDA pondéré",
            "Damodaran (2012) - méthodologie des multiples et vecteur d'ajustement",
            "Trugman (2017) - calibrage de la taille PME et de la dépendance au dirigeant",
            "Pratt & Niculita (2008) - rapprochement multi-méthodes",
            "IVS 2022 - sélection de la méthodologie de fourchette",
            "Duff & Phelps (2024) - prime de taille et coût du capital",
        ),
        section_ids=("upswitch_adaptive",),
        components=(
            MethodReportComponent(
                "adaptive_composition",
                "Adaptive blend composition",
                "Adaptive blend-samenstelling",
                ("adaptive_primary_basis", "upswitch_adaptive_value"),
                (
                    "adaptive_multiples_weight",
                    "adaptive_dcf_weight",
                    "adaptive_multiple_used",
                ),
                "required",
            ),
            MethodReportComponent(
                "adaptive_dcf_leg",
                "DCF leg assumptions",
                "DCF-leg assumpties",
                (),
                (
                    "dcf_wacc",
                    "dcf_projection_years",
                    "dcf_terminal_value_methodology",
                    "dcf_terminal_growth_rate",
                ),
            ),
            MethodReportComponent(
                "adaptive_multiples_leg",
                "Market multiples leg",
                "Marktmultiple-leg",
                (),
                (
                    "benchmark_sample_size",
                    "benchmark_multiple_mid",
                    "multiple_metric_type",
                ),
            ),
        ),
    ),
    MethodReportProfile(
        method_key="dcf",
        label_en="Discounted Cash Flow (DCF)",
        label_nl="Discounted Cash Flow (DCF)",
        label_fr="Flux de trésorerie actualisés (DCF)",
        subtitle_en="Present value of projected cash flows at the WACC",
        subtitle_nl="Contante waarde van geprojecteerde kasstromen tegen de WACC",
        subtitle_fr="Valeur actuelle des flux de trésorerie projetés au WACC",
        sources=(
            "Koller, Goedhart & Wessels (2020) - DCF eligibility and forecast basis",
            "Damodaran (2012) - risk-free rate, equity risk premium, beta",
            "Duff & Phelps (2024) - SME size premium for WACC",
        ),
        sources_nl=(
            "Koller, Goedhart & Wessels (2020) - DCF-geschiktheid en prognosebasis",
            "Damodaran (2012) - risicovrije voet, aandelen-risicopremie en beta",
            "Duff & Phelps (2024) - MKB size premium voor de WACC",
        ),
        sources_fr=(
            "Koller, Goedhart & Wessels (2020) - éligibilité DCF et base prévisionnelle",
            "Damodaran (2012) - taux sans risque, prime de risque actions et bêta",
            "Duff & Phelps (2024) - prime de taille PME pour le WACC",
        ),
        section_ids=("dcf",),
        components=(
            MethodReportComponent(
                "dcf_wacc_buildup",
                "WACC buildup",
                "WACC-opbouw",
                ("dcf_wacc",),
                ("dcf_cost_of_equity", "dcf_cost_of_debt", "dcf_tax_rate"),
                "required",
            ),
            MethodReportComponent(
                "dcf_projection_table",
                "FCFF projection table",
                "FCFF-prognosetabel",
                ("dcf_projection_years", "dcf_pv_fcf_projections"),
                ("dcf_revenue_growth_rates", "dcf_ebitda_margins"),
                "required",
            ),
            MethodReportComponent(
                "dcf_terminal_value",
                "Terminal value and enterprise value",
                "Terminal value en ondernemingswaarde",
                ("dcf_enterprise_value",),
                (
                    "dcf_pv_terminal_value",
                    "dcf_terminal_value_methodology",
                    "dcf_terminal_growth_rate",
                    "dcf_terminal_exit_multiple",
                ),
                "required",
            ),
            MethodReportComponent(
                "dcf_sensitivity",
                "WACC and terminal growth sensitivity",
                "WACC- en terminale-groei sensitiviteit",
                (),
                ("dcf_sensitivity_matrix", "dcf_sensitivity_matrix_2d"),
            ),
        ),
    ),
    MethodReportProfile(
        method_key="ebitda_multiple",
        label_en="EV / EBITDA Multiple",
        label_nl="EV / EBITDA-multiple",
        label_fr="Multiple VE / EBITDA",
        subtitle_en="Calibrated peer-anchor multiple applied to normalised EBITDA",
        subtitle_nl="Gekalibreerde peer-multiple toegepast op genormaliseerde EBITDA",
        subtitle_fr="Multiple de pairs calibré appliqué à l'EBITDA normalisé",
        sources=(
            "Damodaran (2012) - multiples adjusted for fundamental differences",
            "Hitchner (2017) - company-specific multiple framework",
            "McKinsey (2020) - multiple as valuation adjustment vehicle",
        ),
        sources_nl=(
            "Damodaran (2012) - multiples gecorrigeerd voor fundamentele verschillen",
            "Hitchner (2017) - kader voor bedrijfsspecifieke multiples",
            "McKinsey (2020) - multiple als waarderingsaanpassing",
        ),
        sources_fr=(
            "Damodaran (2012) - multiples ajustés pour les différences fondamentales",
            "Hitchner (2017) - cadre des multiples propres à l'entreprise",
            "McKinsey (2020) - multiple comme vecteur d'ajustement de valeur",
        ),
        section_ids=("ebitda_multiple",),
        components=(
            MethodReportComponent(
                "ebitda_multiple_buildup",
                "Peer multiple buildup",
                "Peer multiple-opbouw",
                ("applied_multiple", "benchmark_multiple_label"),
                ("base_multiple", "multiple_low", "multiple_high"),
                "required",
            ),
            MethodReportComponent(
                "ebitda_ev_summary",
                "EBITDA to enterprise value bridge",
                "EBITDA naar ondernemingswaarde",
                ("ebitda_normalized", "ev_ebitda_enterprise_value"),
                (),
                "required",
            ),
            MethodReportComponent(
                "ebitda_peer_evidence",
                "Comparable deals and market evidence",
                "Vergelijkbare transacties en marktevidence",
                (),
                (
                    "comparables",
                    "benchmark_sample_size",
                    "benchmark_window_months",
                    "benchmark_refresh_date",
                ),
            ),
            MethodReportComponent(
                "ebitda_sensitivity",
                "EBITDA and multiple sensitivity",
                "EBITDA- en multiple-sensitiviteit",
                (),
                ("ebitda_sensitivity_matrix_2d",),
            ),
        ),
    ),
    MethodReportProfile(
        method_key="revenue_multiple",
        aliases=("omzet_multiple", "ev_sales", "ev_revenue"),
        label_en="EV / Revenue Multiple",
        label_nl="EV / Omzet-multiple",
        label_fr="Multiple VE / chiffre d'affaires",
        subtitle_en="Revenue-anchored multiple for EBITDA-thin or pre-profit companies",
        subtitle_nl="Omzet-multiple voor EBITDA-arme of pre-winstgevende ondernemingen",
        subtitle_fr="Multiple ancré sur le chiffre d'affaires pour entreprises à faible EBITDA ou avant rentabilité",
        sources=(
            "Trugman (2017) and West (2012) - revenue multiple SME calibration",
            "Damodaran (2012) - revenue multiples for unprofitable or growth firms",
        ),
        sources_nl=(
            "Trugman (2017) en West (2012) - MKB-kalibratie van omzet-multiples",
            "Damodaran (2012) - omzet-multiples voor verliesgevende of groeibedrijven",
        ),
        sources_fr=(
            "Trugman (2017) et West (2012) - calibrage PME des multiples de chiffre d'affaires",
            "Damodaran (2012) - multiples de chiffre d'affaires pour entreprises déficitaires ou en croissance",
        ),
        section_ids=("revenue_multiple",),
        components=(
            MethodReportComponent(
                "revenue_multiple_buildup",
                "Revenue multiple buildup",
                "Omzetmultiple-opbouw",
                ("revenue_multiple_applied",),
                ("revenue_multiple_low", "revenue_multiple_high"),
                "required",
            ),
            MethodReportComponent(
                "revenue_ev_summary",
                "Revenue to enterprise value bridge",
                "Omzet naar ondernemingswaarde",
                ("ev_revenue_enterprise_value",),
                ("operating_revenue", "revenue"),
                "required",
            ),
            MethodReportComponent(
                "revenue_growth_check",
                "Growth-adjusted band check",
                "Groeigecorrigeerde bandcheck",
                (),
                ("revenue_growth_3y_cagr",),
            ),
            MethodReportComponent(
                "revenue_sensitivity",
                "Revenue and multiple sensitivity",
                "Omzet- en multiple-sensitiviteit",
                (),
                ("revenue_sensitivity_matrix_2d",),
            ),
        ),
    ),
    MethodReportProfile(
        method_key="sde_multiple",
        aliases=("sde",),
        label_en="Seller's Discretionary Earnings (SDE)",
        label_nl="Seller's Discretionary Earnings (SDE)",
        label_fr="Résultat discrétionnaire du vendeur (SDE)",
        subtitle_en="Owner-operated SME standard based on sustainable discretionary earnings",
        subtitle_nl="Standaard voor eigenaar-geleide SME op basis van duurzame discretionaire winst",
        subtitle_fr="Référence PME exploitée par le dirigeant, fondée sur un résultat discrétionnaire durable",
        sources=(
            "Trugman (2017) - SDE as standard for owner-operated SMEs",
            "BizBuySell - SDE multiples database",
        ),
        sources_nl=(
            "Trugman (2017) - SDE als standaard voor eigenaar-geleide MKB",
            "BizBuySell - SDE-multiples database",
        ),
        sources_fr=(
            "Trugman (2017) - SDE comme référence pour PME dirigées par leur propriétaire",
            "BizBuySell - base de données de multiples SDE",
        ),
        section_ids=("sde",),
        components=(
            MethodReportComponent(
                "sde_bridge",
                "Reported earnings to SDE bridge",
                "Gerapporteerde winst naar SDE-brug",
                ("sde_value",),
                ("sde_bridge", "sde_components"),
                "required",
            ),
            MethodReportComponent(
                "sde_multiple_summary",
                "SDE to enterprise value bridge",
                "SDE naar ondernemingswaarde",
                ("sde_base_multiple", "ev_sde_enterprise_value"),
                ("sde_multiple_p25", "sde_multiple_p75"),
                "required",
            ),
            MethodReportComponent(
                "sde_buyer_band",
                "Buyer-comparable size band",
                "Buyer-comparable grootteband",
                (),
                ("sde_business_size", "sde_country_code"),
            ),
        ),
    ),
    MethodReportProfile(
        method_key="adjusted_nav",
        aliases=("asset_based", "nav"),
        label_en="Adjusted Net Asset Value (NAV)",
        label_nl="Aangepaste Net Asset Value (NAV)",
        label_fr="Valeur nette d'actif ajustée (NAV)",
        subtitle_en="Floor-value methodology for asset-heavy and holding companies",
        subtitle_nl="Vloerwaarde-methodologie voor activumzware en holdingvennootschappen",
        subtitle_fr="Méthodologie de valeur plancher pour sociétés patrimoniales ou à forte intensité d'actifs",
        sources=(
            "Pratt & Niculita (2008) - NAV and book-value methodology",
            "IVS 2022 - asset-based valuation standard",
            "Damodaran (2012) - floor value versus going-concern reconciliation",
        ),
        sources_nl=(
            "Pratt & Niculita (2008) - NAV- en boekwaarde-methodologie",
            "IVS 2022 - asset-based waarderingsstandaard",
            "Damodaran (2012) - vloerwaarde versus going-concern reconciliatie",
        ),
        sources_fr=(
            "Pratt & Niculita (2008) - méthodologie NAV et valeur comptable",
            "IVS 2022 - norme de valorisation fondée sur les actifs",
            "Damodaran (2012) - rapprochement valeur plancher versus continuité d'exploitation",
        ),
        section_ids=("adjusted_nav",),
        components=(
            MethodReportComponent(
                "nav_bridge",
                "Book equity to corrected NAV bridge",
                "Boekwaarde naar gecorrigeerde NAV",
                ("nav_book_equity", "nav_corrected_value"),
                ("nav_manual_adjustments_note", "ownership_multiplier"),
                "required",
            ),
            MethodReportComponent(
                "nav_tax_latencies",
                "Tax latency adjustments",
                "Belastinglatenties",
                (),
                ("tax_latencies", "nav_tax_latencies"),
            ),
            MethodReportComponent(
                "nav_audit_trail",
                "Balance-sheet audit trail",
                "Balansaudit trail",
                (),
                ("nav_audit_trail",),
            ),
            MethodReportComponent(
                "nav_deal_structure",
                "Share deal versus asset deal structure",
                "Share deal versus asset deal-structuur",
                (),
                ("nav_deal_structure",),
            ),
        ),
    ),
    MethodReportProfile(
        method_key="holding_sotp",
        aliases=("sotp", "holding", "patrimonium"),
        label_en="Holding Company Sum of the Parts (SOTP)",
        label_nl="Holdingvennootschap Sum of the Parts (SOTP)",
        label_fr="Somme des parties (SOTP) de la holding",
        subtitle_en="Entity-by-entity value, ownership, tax and intercompany reconciliation",
        subtitle_nl="Entiteit-per-entiteit waardering, eigendom, fiscaliteit en intercompany-reconciliatie",
        subtitle_fr="Rapprochement entité par entité des valeurs, participations, impôts et flux intragroupe",
        sources=(
            "IVS 2022 - aggregation of separately valued assets and interests",
            "Koller, Goedhart & Wessels (2020) - sum-of-the-parts valuation",
            "IFRS 10 - control, consolidation and intercompany eliminations",
        ),
        sources_nl=(
            "IVS 2022 - aggregatie van afzonderlijk gewaardeerde activa en belangen",
            "Koller, Goedhart & Wessels (2020) - sum-of-the-parts waardering",
            "IFRS 10 - zeggenschap, consolidatie en intercompany-eliminaties",
        ),
        sources_fr=(
            "IVS 2022 - agrégation d'actifs et de participations valorisés séparément",
            "Koller, Goedhart & Wessels (2020) - valorisation par somme des parties",
            "IFRS 10 - contrôle, consolidation et éliminations intragroupe",
        ),
        section_ids=("holding_sotp",),
        combinable=False,
        components=(
            MethodReportComponent(
                "holding_entity_schedule",
                "Entity valuation and ownership schedule",
                "Entiteitswaardering en eigendomsschema",
                ("holding_sotp",),
                ("holdings_consolidation", "holding_sotp_method"),
                "required",
            ),
            MethodReportComponent(
                "holding_eliminations",
                "Participation and intercompany eliminations",
                "Participatie- en intercompany-eliminaties",
                ("holding_sotp",),
                (),
                "required",
            ),
            MethodReportComponent(
                "holding_value_ranges",
                "Enterprise and equity value ranges",
                "Ondernemings- en eigenvermogensbandbreedtes",
                ("holding_sotp",),
                (),
                "required",
            ),
        ),
    ),
    MethodReportProfile(
        method_key="arr_multiple",
        aliases=("arr", "saas_arr"),
        label_en="ARR Multiple",
        label_nl="ARR-multiple",
        label_fr="Multiple ARR",
        subtitle_en="SaaS recurring-revenue multiple with retention and growth evidence",
        subtitle_nl="SaaS recurring-revenue multiple met retentie- en groei-evidence",
        subtitle_fr="Multiple de revenus récurrents SaaS avec preuves de rétention et de croissance",
        sources=(
            "SaaS Capital - ARR multiple benchmarking",
            "Bessemer State of the Cloud - SaaS growth and retention benchmarks",
            "Damodaran (2012) - revenue multiples for growth firms",
        ),
        sources_nl=(
            "SaaS Capital - ARR multiple benchmarking",
            "Bessemer State of the Cloud - SaaS-groei- en retentiebenchmarks",
            "Damodaran (2012) - omzet-multiples voor groeibedrijven",
        ),
        sources_fr=(
            "SaaS Capital - benchmarking des multiples ARR",
            "Bessemer State of the Cloud - benchmarks de croissance et de rétention SaaS",
            "Damodaran (2012) - multiples de chiffre d'affaires pour entreprises de croissance",
        ),
        section_ids=("saas_appendix", "saas_cap_table"),
        components=(
            MethodReportComponent(
                "arr_metrics",
                "ARR, growth, churn and retention metrics",
                "ARR, groei, churn en retentiemetrics",
                (
                    "saas_arr",
                    "saas_arr_growth_pct",
                    "saas_gross_margin_pct",
                ),
                (
                    "saas_nrr_pct",
                    "saas_gross_revenue_churn_pct",
                    "saas_customer_churn_pct",
                ),
                "required",
            ),
            MethodReportComponent(
                "arr_value_bridge",
                "ARR to enterprise value bridge",
                "ARR naar ondernemingswaarde",
                ("saas_arr_multiple", "saas_enterprise_value"),
                ("saas_base_multiple", "saas_adjustment_breakdown"),
                "required",
            ),
            MethodReportComponent(
                "saas_cap_table",
                "SaaS ownership and dilution context",
                "SaaS eigendom en verwatering",
                (),
                ("saas_cap_table", "cap_table"),
            ),
        ),
    ),
    MethodReportProfile(
        method_key="fiscal_4x",
        label_en="Belgian Fiscal 4x Reference",
        label_nl="Belgische fiscale 4x-referentie",
        label_fr="Référence fiscale belge 4x",
        subtitle_en="Belgian fiscal reference anchor: book equity plus 4x EBITDA",
        subtitle_nl="Belgische fiscale referentie: eigen vermogen plus 4x EBITDA",
        subtitle_fr="Ancrage fiscal belge: capitaux propres comptables plus 4x EBITDA",
        sources=(
            "Belgian statutory valuation practice - equity plus earnings anchor",
            "WIB 92 - fiscal transfer-value reference context",
        ),
        sources_nl=(
            "Belgische fiscale waarderingspraktijk - eigen vermogen plus winstanker",
            "WIB 92 - fiscale referentiecontext voor overdrachtswaarde",
        ),
        sources_fr=(
            "Pratique fiscale belge de valorisation - capitaux propres plus ancrage bénéficiaire",
            "CIR 92 - contexte de référence fiscale pour valeur de transfert",
        ),
        section_ids=("fiscal_reference",),
        combinable=False,
        components=(
            MethodReportComponent(
                "fiscal_formula",
                "Book equity plus 4x EBITDA formula",
                "Eigen vermogen plus 4x EBITDA-formule",
                ("fiscal_normalized_ebitda", "fiscal_ebitda_multiple"),
                ("fiscal_book_equity", "fiscal_reference_value"),
                "required",
            ),
            MethodReportComponent(
                "fiscal_scope",
                "Fiscal scope and legal basis",
                "Fiscale scope en wettelijke basis",
                (),
                (
                    "fiscal_reference_date",
                    "fiscal_internal_transfer",
                    "fiscal_company_role",
                ),
            ),
        ),
    ),
    MethodReportProfile(
        method_key="startup_valuation",
        aliases=("venture", "startup"),
        label_en="Startup Valuation",
        label_nl="Startupwaardering",
        label_fr="Valorisation de startup",
        subtitle_en="Venture valuation blend using milestones, market method and dilution context",
        subtitle_nl="Venturewaardering op basis van milestones, marktbenadering en verwatering",
        subtitle_fr="Valorisation venture combinant jalons, approche de marché et contexte de dilution",
        sources=(
            "Berkus Method - milestone-based early-stage valuation",
            "Scorecard Method - local market early-stage calibration",
            "VC method - exit value and dilution reconciliation",
        ),
        sources_nl=(
            "Berkus-methode - mijlpaalgebaseerde waardering voor pre-revenue startups",
            "Scorecard-methode - lokale marktkalibratie voor vroege fase",
            "Venture-Capital-methode - reconciliatie van exitwaarde en verwatering",
        ),
        sources_fr=(
            "Méthode Berkus - valorisation early-stage fondée sur les jalons",
            "Méthode Scorecard - calibrage local du marché early-stage",
            "Méthode VC - rapprochement valeur de sortie et dilution",
        ),
        section_ids=("startup_one_pager", "startup_method_breakdown"),
        combinable=False,
        components=(
            MethodReportComponent(
                "startup_method_breakdown",
                "Startup method breakdown",
                "Startup methode-opbouw",
                ("startup_report",),
                ("startup_report.method_breakdown", "startup_report.risks_register"),
                "required",
            ),
        ),
    ),
    MethodReportProfile(
        method_key="liquidation_analysis",
        aliases=("liquidation", "wind_down"),
        label_en="Liquidation Analysis",
        label_nl="Liquidatieanalyse",
        label_fr="Analyse de liquidation",
        subtitle_en="Orderly or forced wind-down analysis by asset realisation and creditor priority",
        subtitle_nl="Ordentelijke of gedwongen afwikkeling via activarealisatie en schuldeisersrang",
        subtitle_fr="Analyse de liquidation ordonnée ou forcée par réalisation des actifs et priorité des créanciers",
        sources=(
            "IVS 2022 - premise of value and liquidation basis",
            "Insolvency practice - creditor priority waterfall",
        ),
        sources_nl=(
            "IVS 2022 - waarderingsuitgangspunt en liquidatiebasis",
            "Insolventiepraktijk - rangorde-watervaldiagram van schuldeisers",
        ),
        sources_fr=(
            "IVS 2022 - prémisse de valeur et base de liquidation",
            "Pratique de l'insolvabilité - cascade de priorité des créanciers",
        ),
        section_ids=("liquidation_executive_summary",),
        combinable=False,
        components=(
            MethodReportComponent(
                "liquidation_priority_cascade",
                "Creditor priority cascade",
                "Schuldeisersrang cascade",
                ("liquidation_report",),
                ("liquidation_report.priority_cascade",),
                "required",
            ),
        ),
    ),
)


def _clean_key(method_key: object) -> str:
    if method_key is None:
        return ""
    return str(method_key).strip().lower().replace("-", "_").replace(" ", "_")


def _registry_lookup_key(method_key: object) -> str:
    raw = _clean_key(method_key)
    if raw == "omzet_multiple":
        return "revenue_multiple"
    normalized = normalize_method_key(raw)
    if normalized == "omzet_multiple":
        return "revenue_multiple"
    return normalized or raw


def _build_profile_lookup() -> dict[str, MethodReportProfile]:
    lookup: dict[str, MethodReportProfile] = {}
    for profile in METHOD_REPORT_PROFILES:
        for key in (profile.method_key, *profile.aliases):
            lookup[_clean_key(key)] = profile
            lookup[_registry_lookup_key(key)] = profile
    return lookup


_PROFILE_BY_KEY = _build_profile_lookup()


def get_method_report_profile(method_key: object) -> MethodReportProfile | None:
    key = _clean_key(method_key)
    if not key:
        return None
    return _PROFILE_BY_KEY.get(key) or _PROFILE_BY_KEY.get(_registry_lookup_key(key))


def iter_method_report_profiles() -> Iterable[MethodReportProfile]:
    return iter(METHOD_REPORT_PROFILES)


def build_method_report_registry_context() -> dict[str, dict[str, object]]:
    registry: dict[str, dict[str, object]] = {}
    for profile in METHOD_REPORT_PROFILES:
        data = profile.as_template_context()
        for key in (profile.method_key, *profile.aliases):
            registry[_clean_key(key)] = data
    return registry


def build_active_method_report_profiles(
    method_keys: Iterable[object],
) -> list[dict[str, object]]:
    active_keys = {
        profile.method_key
        for key in method_keys
        if (profile := get_method_report_profile(key)) is not None
    }
    return [
        profile.as_template_context()
        for profile in METHOD_REPORT_PROFILES
        if profile.method_key in active_keys
    ]


def _has_context_value(context: dict[str, object], key: str) -> bool:
    value = context.get(key)
    return value is not None and value != "" and value != [] and value != {}


def build_method_component_coverage(
    context: dict[str, object],
    method_keys: Iterable[object] | None = None,
) -> dict[str, dict[str, object]]:
    if method_keys is None:
        method_results = context.get("method_results_by_key") or {}
        method_keys = method_results.keys() if hasattr(method_results, "keys") else []

    coverage: dict[str, dict[str, object]] = {}
    profiles = [
        get_method_report_profile(key)
        for key in method_keys
        if get_method_report_profile(key) is not None
    ]
    seen: set[str] = set()

    for profile in profiles:
        if profile is None or profile.method_key in seen:
            continue
        seen.add(profile.method_key)

        component_rows: list[dict[str, object]] = []
        missing_all: list[str] = []
        for component in profile.components:
            missing = [
                key
                for key in component.required_context_keys
                if not _has_context_value(context, key)
            ]
            missing_all.extend(missing)
            row = component.as_template_context()
            row["missing_required_context_keys"] = missing
            row["is_complete"] = not missing
            component_rows.append(row)

        missing_unique = list(dict.fromkeys(missing_all))
        coverage[profile.method_key] = {
            "method_key": profile.method_key,
            "is_complete": not missing_unique,
            "coverage_state": "complete" if not missing_unique else "partial",
            "missing_required_context_keys": missing_unique,
            "components": component_rows,
        }

    return coverage
