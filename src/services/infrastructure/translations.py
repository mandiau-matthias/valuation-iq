"""Report translation dataclass and locale helpers for valuation reports."""

from dataclasses import dataclass
from typing import Optional

from src.services.infrastructure.report_display_helpers import (
    EbitdaAdjustmentLabels,
    build_synthesis_formula_display,
    resolve_ebitda_adjustment_labels,
    resolve_synthesis_method_label,
)
from src.services.infrastructure.report_locale import Locale, normalize_report_locale
from src.services.infrastructure.report_saas_labels import localize_saas_adjustment_breakdown
from src.services.infrastructure.report_translation_contract import (
    ReportTranslationAccountantAuditSourceFields,
    ReportTranslationAccountantQualityStrategyFields,
    ReportTranslationAccountantSmeConditionalFields,
    ReportTranslationFiscalSynthesisFields,
    ReportTranslationFoundationFields,
    ReportTranslationOwnerSellabilityFields,
    ReportTranslationStageAwareBreakdownFields,
    ReportTranslationTransformerAccountantCoreFields,
)
from src.services.infrastructure.warning_translations import (
    _TYPED_WARNING_TO_TRANSLATION_KEYS,
    QUALITY_WARNING_TRANSLATIONS,
    localize_typed_data_quality_warnings,
    translate_quality_warning,
)


@dataclass(frozen=True)
class ReportTranslations(
    ReportTranslationAccountantSmeConditionalFields,
    ReportTranslationAccountantQualityStrategyFields,
    ReportTranslationAccountantAuditSourceFields,
    ReportTranslationTransformerAccountantCoreFields,
    ReportTranslationOwnerSellabilityFields,
    ReportTranslationStageAwareBreakdownFields,
    ReportTranslationFiscalSynthesisFields,
    ReportTranslationFoundationFields,
):
    """All translatable strings for the valuation report."""

    @classmethod
    def dutch(cls) -> "ReportTranslations":
        """Return Dutch (nl) translations - Primary language."""
        from src.services.infrastructure.report_translation_catalog import (
            build_dutch_report_translations,
        )

        return build_dutch_report_translations(cls)

    @classmethod
    def english(cls) -> "ReportTranslations":
        """Return English (en) translations."""
        from src.services.infrastructure.report_translation_catalog import (
            build_english_report_translations,
        )

        return build_english_report_translations(cls)

    @classmethod
    def french(cls) -> "ReportTranslations":
        """Return French (fr) translations."""
        from src.services.infrastructure.report_translation_catalog import (
            build_french_report_translations,
        )

        return build_french_report_translations(cls)


def _apply_nl_overrides(t: "ReportTranslations", locale: Locale) -> "ReportTranslations":
    """
    Replace Belgian-specific legal references with Dutch equivalents.

    Belgian law (WVV, FSMA, Art. 90 WIB 92) does not apply to Dutch firms.
    Dutch equivalents: BW Boek 2 (company law), AFM (financial regulator).
    """
    from dataclasses import replace

    if locale == "nl":
        return replace(
            t,
            disc_custom_disclaimer_matches_primary_body=(
                "De vastgelegde dossierspecifieke tekst komt overeen met de standaarddisclaimer van dit rapport "
                "(Nederlands recht). Er is geen afwijkende aanvullende tekst toegevoegd."
            ),
            disc_primary_text=(
                "Dit document biedt een indicatieve waardeschatting uitsluitend ter informatie. "
                "Het vormt geen financieel, juridisch of fiscaal advies, geen fairness opinion, "
                "en geen wettelijke waardering volgens het Nederlands ondernemingsrecht (Boek 2 BW). "
                "Win onafhankelijk professioneel advies in voordat u investerings- of transactiebeslissingen neemt."
            ),
            disc_regulatory_text=(
                "Upswitch is geen erkend beleggingsbedrijf of auditor. "
                "Deze schatting voldoet niet aan wettelijke vereisten onder Nederlands recht of AFM-regelgeving."
            ),
            disc_legal_footer="Volledige voorwaarden op upswitch.app/terms-and-conditions • Nederlands recht van toepassing",
        )

    return replace(
        t,
        disc_custom_disclaimer_matches_primary_body=(
            "The dossier-specific text recorded for this report matches the standard disclaimer "
            "(Dutch law). No additional diverging text has been added."
        ),
        disc_primary_text=(
            "This document provides an indicative valuation estimate for informational purposes only. "
            "It does not constitute financial, legal or tax advice, a fairness opinion, "
            "or a statutory valuation under Dutch company law (Book 2 Civil Code). "
            "Seek independent professional advice before making investment or transaction decisions."
        ),
        disc_regulatory_text=(
            "Upswitch is not a licensed investment firm or auditor. "
            "This estimate does not meet statutory requirements under Dutch law or AFM regulations."
        ),
        disc_legal_footer="Full terms at upswitch.app/terms-and-conditions • Dutch law applies",
    )


def _apply_non_belgian_overrides(
    t: "ReportTranslations", locale: Locale, country_code: str
) -> "ReportTranslations":
    """Remove Belgian legal, tax and benchmark assumptions outside Belgium.

    The translation catalog was originally authored for Belgian reports.  A
    translated Belgian statement is still a Belgian statement: selecting
    French or English must never make WVV/WIB, NBB or Belgian SME evidence
    applicable to a French or Irish company.  Non-Belgian reports therefore
    use jurisdiction-neutral copy and must obtain priced evidence from the
    sealed run rather than from catalog prose.
    """
    from dataclasses import replace

    jurisdiction = "France" if country_code == "FR" else "Ireland"
    if locale == "fr":
        primary = (
            "Ce document fournit une estimation indicative à titre informatif. "
            "Il ne constitue ni un conseil financier, juridique ou fiscal, ni une "
            "attestation d'équité, ni une évaluation légale. Les exigences "
            f"applicables en {jurisdiction} doivent être confirmées par un conseiller local."
        )
        regulatory = (
            "Upswitch n'est ni une entreprise d'investissement agréée ni un auditeur. "
            f"Ce rapport ne certifie pas le respect des exigences légales de {jurisdiction}."
        )
        footer = (
            f"Conditions complètes sur upswitch.app/terms-and-conditions • Contexte sociétaire : {jurisdiction}"
        )
        official_head = "Vérification de la source officielle"
        official_match = (
            "Les chiffres saisis ont été rapprochés des preuves officielles "
            "identifiées dans le registre de sources scellé."
        )
        market_intro = (
            "Le multiple est ancré exclusivement sur les preuves de marché scellées "
            "pour le pays, la métrique et la date de valorisation indiqués."
        )
        market_note = (
            "La source, la méthodologie, l'échantillon et la date du multiple sont "
            "ceux du registre de preuves tarifées; aucun marché national n'est présumé."
        )
        nav_subtitle = (
            "Dossier par actif : réévaluation, passifs et traitement fiscal fondé "
            "sur des preuves selon le CountryPack applicable."
        )
        nav_tax_title = "Taux d'impôt résolu par le CountryPack"
        nav_deal = (
            "Comparaison entre transaction d'actions et transaction d'actifs; tout "
            "effet fiscal doit être sourcé et revu dans la juridiction concernée."
        )
        unsupported_fiscal = "Référence fiscale 4× non prise en charge dans cette juridiction"
        accountant_disclaimer = (
            "Rapport indicatif fondé sur les données fournies et les preuves scellées; "
            "il ne constitue ni audit, ni attestation, ni opinion d'équité."
        )
        academic = (
            "Les ajustements PME doivent être reliés à des preuves de marché "
            "spécifiques au pays, au secteur et à la date de valorisation."
        )
    elif locale == "nl":
        primary = (
            "Dit document bevat uitsluitend een indicatieve waardeschatting. Het is "
            "geen financieel, juridisch of fiscaal advies, fairness opinion of "
            f"wettelijke waardering. Vereisten in {jurisdiction} moeten door een lokale adviseur worden bevestigd."
        )
        regulatory = (
            "Upswitch is geen erkende beleggingsonderneming of auditor. Dit rapport "
            f"certificeert geen naleving van wettelijke vereisten in {jurisdiction}."
        )
        footer = (
            f"Volledige voorwaarden op upswitch.app/terms-and-conditions • Ondernemingscontext: {jurisdiction}"
        )
        official_head = "Controle officiële bron"
        official_match = (
            "De ingevoerde cijfers zijn afgestemd met de officiële bewijsstukken in "
            "het verzegelde bronnenregister."
        )
        market_intro = (
            "De multiple wordt uitsluitend verankerd op het verzegelde marktbewijs "
            "voor het vermelde land, de waarderingsmaatstaf en de peildatum."
        )
        market_note = (
            "Bron, methodologie, steekproef en datum volgen uit het geprijsde "
            "bewijsregister; er wordt geen nationale markt verondersteld."
        )
        nav_subtitle = (
            "Dossier per actief: herwaardering, verplichtingen en bewijsgebonden "
            "fiscale behandeling volgens het toepasselijke CountryPack."
        )
        nav_tax_title = "Door het CountryPack vastgesteld belastingtarief"
        nav_deal = (
            "Vergelijking van aandelen- en activatransactie; elk fiscaal effect moet "
            "binnen de toepasselijke jurisdictie zijn onderbouwd en beoordeeld."
        )
        unsupported_fiscal = "Fiscale 4×-referentie niet ondersteund in deze jurisdictie"
        accountant_disclaimer = (
            "Indicatief rapport op basis van aangeleverde gegevens en verzegeld bewijs; "
            "geen audit, attestering of fairness opinion."
        )
        academic = (
            "KMO-correcties moeten aansluiten op land-, sector- en datumgebonden marktbewijs."
        )
    else:
        primary = (
            "This document provides an indicative valuation estimate for information "
            "only. It is not financial, legal or tax advice, a fairness opinion, or a "
            f"statutory valuation. Requirements applicable in {jurisdiction} must be confirmed by local counsel."
        )
        regulatory = (
            "Upswitch is not a licensed investment firm or auditor. This report does "
            f"not certify compliance with statutory requirements in {jurisdiction}."
        )
        footer = f"Full terms at upswitch.app/terms-and-conditions • Company context: {jurisdiction}"
        official_head = "Official-source reconciliation"
        official_match = (
            "Submitted figures were reconciled to the official evidence identified in "
            "the sealed source register."
        )
        market_intro = (
            "The multiple is anchored only to sealed market evidence for the stated "
            "country, metric and valuation date."
        )
        market_note = (
            "The multiple source, methodology, sample and date are those in the priced "
            "evidence register; no national market is assumed."
        )
        nav_subtitle = (
            "Asset-by-asset evidence file: revaluation, liabilities and source-backed "
            "tax treatment under the applicable CountryPack."
        )
        nav_tax_title = "CountryPack-resolved tax rate"
        nav_deal = (
            "Share-deal versus asset-deal comparison; every tax effect must be sourced "
            "and reviewed for the applicable jurisdiction."
        )
        unsupported_fiscal = "Fiscal 4× reference is not supported in this jurisdiction"
        accountant_disclaimer = (
            "Indicative report based on supplied data and sealed evidence; it is not an "
            "audit, attestation or fairness opinion."
        )
        academic = (
            "SME adjustments must be tied to country-, sector- and date-specific market evidence."
        )

    return replace(
        t,
        exec_official_registry_head=official_head,
        exec_official_trust_match_verified=official_match,
        disc_primary_text=primary,
        disc_regulatory_text=regulatory,
        disc_legal_footer=footer,
        disc_biblio_vfb="Priced evidence register — governed market sources only.",
        disc_biblio_vlerick="CountryPack and method profile — versioned policy sources.",
        disc_biblio_marktlink="Benchmark snapshot — source, sample and date as sealed in the run.",
        nav_audit_trail_subtitle=nav_subtitle,
        nav_audit_trail_sme_title=nav_tax_title,
        nav_deal_structure_subtitle=nav_deal,
        ebitda_multiple_methodology_intro=market_intro,
        ebitda_multiple_assumptions_note=market_note,
        revenue_multiple_assumptions_note=market_note,
        sde_methodology_intro=market_intro,
        fiscal_subtitle=unsupported_fiscal,
        fiscal_scope_disclaimer=unsupported_fiscal,
        fiscal_legal_intro=unsupported_fiscal,
        fiscal_anchor_1_basis=unsupported_fiscal,
        cover_fiscal_note=unsupported_fiscal + " — {date}",
        omni_methodology_statement_fiscal_4x=unsupported_fiscal,
        accountant_cover_disclaimer_text=accountant_disclaimer,
        accountant_wf_footnote_market_consensus_body=(
            "Priced evidence register; source, sample and observation date required."
        ),
        accountant_audit_step3_ref="Reference: sealed priced evidence register",
        accountant_sources_app_vfb="Governed market evidence and method-specific adjustments",
        accountant_sme_multiple_db_default=(
            "Country- and business-type-specific multiples from the sealed benchmark snapshot"
        ),
        accountant_sme_academic_body=academic,
        accountant_sme_adj_breakdown_intro=academic,
        accountant_sme_adj_market=academic,
    )


def get_translations(locale: Locale = "en", country_code: str = "BE") -> ReportTranslations:
    """
    Get translations for the specified locale and country.

    Args:
        locale: Language code ('nl' for Dutch, 'en' for English); BCP-47 tags
            like ``en-US`` are accepted (English is selected when the tag starts
            with ``en``).
        country_code: Firm country ('BE' for Belgium, 'NL' for Netherlands);
            normalized with strip/upper so minor formatting differences still
            match overrides.

    Returns:
        ReportTranslations instance with country-appropriate legal text

    Note:
        For main and simplified reports, pass the same ``country_code`` as
        ``MainReportDataAggregator`` / ``TemplateService`` (firm jurisdiction),
        so disclaimer and related legal strings stay aligned end-to-end.
    """
    _loc = normalize_report_locale(locale)
    _cc = str(country_code or "BE").strip().upper() or "BE"
    if _loc == "fr":
        t = ReportTranslations.french()
    elif _loc == "en":
        t = ReportTranslations.english()
    else:
        t = ReportTranslations.dutch()
    if _cc == "NL":
        t = _apply_nl_overrides(t, _loc)
    elif _cc in {"FR", "IE"}:
        t = _apply_non_belgian_overrides(t, _loc, _cc)
    return t


def localize_data_quality_warnings(
    warnings: list,
    locale: Optional[str],
    country_code: str = "BE",
) -> list:
    """Translate typed `data_quality_warnings` in place for the response payload.

    Mirrors `MainReportDataAggregator._localize_warnings` but operates at the
    response layer so consumers that read the raw `data_quality_warnings`
    field (e.g. the Venus drawer rail) get the same localized strings the
    PDF report uses. Unknown warning types pass through unchanged so a new
    engine warning still surfaces while the catalog catches up.
    """
    t = get_translations(normalize_report_locale(locale), country_code)
    return localize_typed_data_quality_warnings(warnings, t)
