"""Disclosures, statement of affairs, replacement cost, and audit-trail copy."""

from __future__ import annotations

from typing import Dict


def build_disclosures_statement_translations() -> Dict[str, Dict[str, str]]:
    """Return disclosures, statement of affairs, replacement cost, and audit-trail copy."""
    return {
        # ---------------------------------------------------------------
        # Phase 4 — Section 10: Disclosures (IVS 104 / USPAP / IFRS 13)
        # ---------------------------------------------------------------
        "disclosure_section_title": {
            "nl": "Disclosures & methodologie",
            "en": "Disclosures & methodology",
        },
        "disclosure_section_subtitle": {
            "nl": "Methodologische referenties — geen conformiteitsverklaring",
            "en": "Methodological references — no conformity statement",
        },
        "disclosure_bases_title": {
            "nl": "Toegepaste waardebases (IVS 104 §10)",
            "en": "Bases of value applied (IVS 104 §10)",
        },
        "disclosure_premise_title": {
            "nl": "Premisse van de waarde",
            "en": "Premise of value",
        },
        "disclosure_approaches_title": {
            "nl": "Gehanteerde benaderingen (IVS 105)",
            "en": "Approaches used (IVS 105)",
        },
        "disclosure_compliance_title": {
            "nl": "Methodologische referenties & beperkingen",
            "en": "Methodological references & limitations",
        },
        "disclosure_fv_hierarchy_title": {
            "nl": "IFRS 13 fair-value hiërarchie",
            "en": "IFRS 13 fair-value hierarchy",
        },
        "disclosure_fv_col_item": {"nl": "Item", "en": "Item"},
        "disclosure_fv_col_level": {"nl": "Niveau", "en": "Level"},
        "disclosure_fv_col_rationale": {"nl": "Rationale", "en": "Rationale"},
        "disclosure_fv_level_1": {"nl": "Level 1", "en": "Level 1"},
        "disclosure_fv_level_2": {"nl": "Level 2", "en": "Level 2"},
        "disclosure_fv_level_3": {"nl": "Level 3", "en": "Level 3"},
        # Per-row labels for the IFRS-13 fair-value hierarchy table —
        # keyed by `FairValueHierarchyEntry.code`.  Engine defaults remain
        # English (engine-level tests still pass); report context overlays
        # the locale on the way to the templates.
        "disclosure_fv_item_fv_cash": {
            "nl": "Liquide middelen & equivalenten",
            "en": "Cash & cash equivalents",
        },
        "disclosure_fv_item_fv_trade_receivables": {
            "nl": "Handelsvorderingen",
            "en": "Trade receivables",
        },
        "disclosure_fv_item_fv_inventory": {"nl": "Voorraad", "en": "Inventory"},
        "disclosure_fv_item_fv_real_estate": {
            "nl": "Onroerend goed (terrein + gebouwen)",
            "en": "Real estate (land + buildings)",
        },
        "disclosure_fv_item_fv_machinery": {
            "nl": "Machines & uitrusting",
            "en": "Machinery & equipment",
        },
        "disclosure_fv_item_fv_intangibles": {
            "nl": "Immateriële activa",
            "en": "Intangible assets",
        },
        "disclosure_fv_rationale_fv_cash": {
            "nl": ("Genoteerde prijzen in actieve markten; nominale waarde " "op alle peildata."),
            "en": ("Quoted prices in active markets; par value at all dates."),
        },
        "disclosure_fv_rationale_fv_trade_receivables": {
            "nl": (
                "Waarneembare counterparty-data + ageringsschema; "
                "recovery-rate afgeleid uit historische inning."
            ),
            "en": (
                "Observable counterparty data + aging schedule; recovery "
                "rate derived from observable collection histories."
            ),
        },
        "disclosure_fv_rationale_fv_inventory": {
            "nl": (
                "Geen actieve markt voor SME-onderhanden werk of "
                "gespecialiseerd eindproduct bij distress-verkoop; "
                "recovery-factor uit Pratt&Niculita / EY academische data."
            ),
            "en": (
                "No active market for SME-grade work-in-progress or "
                "specialised finished goods at distress sale; recovery "
                "factor sourced from Pratt&Niculita / EY academic data."
            ),
        },
        "disclosure_fv_rationale_fv_real_estate": {
            "nl": (
                "Waarneembare vergelijkbare verkopen in de lokale commerciële "
                "vastgoedmarkt; taxateur past een haircut toe voor de "
                "distress-afbouwtijdlijn."
            ),
            "en": (
                "Observable comparable sales in the local commercial real-"
                "estate market; appraisal applies a haircut for distressed "
                "wind-down timeline."
            ),
        },
        "disclosure_fv_rationale_fv_machinery": {
            "nl": (
                "Gespecialiseerde SME-machines; geen actieve markt. "
                "Recovery-factor uit cohort-data (Upswitch Index NACE × klasse) "
                "met academische fallback."
            ),
            "en": (
                "Specialised SME machinery; no active market. Recovery "
                "factor sourced from cohort data (Upswitch Index NACE × class) "
                "with academic fallback."
            ),
        },
        "disclosure_fv_rationale_fv_intangibles": {
            "nl": (
                "Geen actieve markt voor SME-goodwill / handelsmerken bij "
                "liquidatie; taxateur hanteert sterk gedisconteerde "
                "recovery-factor (typisch 5-20%)."
            ),
            "en": (
                "No active market for SME goodwill / trademarks at "
                "liquidation; valuer applies highly-discounted recovery "
                "factor (typically 5-20%)."
            ),
        },
        "disclosure_limitations_title": {"nl": "Beperkingen", "en": "Limitations"},
        "disclosure_out_of_scope_title": {
            "nl": "Buiten reikwijdte",
            "en": "Out of scope",
        },
        "disclosure_assumptions_title": {"nl": "Aannames", "en": "Assumptions"},
        "disclosure_signatory_title": {"nl": "Ondertekening", "en": "Signatory"},
        # ---------------------------------------------------------------
        # Default disclosure list copy — translated whole-list overrides.
        # Engine emits English strings as fallback (preserves engine tests
        # + direct dict consumers).  Report context swaps in the locale
        # variant when present; falls back to engine list otherwise.
        # Each item maps positionally to the engine's tuple ordering in
        # `disclosure.py:_DEFAULT_*` — adding a new default entry on
        # the engine side requires adding the same-position entry here
        # in both locales.  Length-mismatch falls through to the engine
        # list (safer than emitting a half-translated page).
        # ---------------------------------------------------------------
        "disclosure_default_limitations.0": {
            "nl": (
                "Recovery-factoren boven de cohort-vloer worden toegepast "
                "wanneer de Upswitch Index onvoldoende k-anon-beschermde sample heeft; "
                "het rapport markeert die regels expliciet."
            ),
            "en": (
                "Recovery factors above the cohort floor are applied where "
                "the Upswitch Index has insufficient k-anon-protected sample; report "
                "flags those lines explicitly."
            ),
        },
        "disclosure_default_limitations.1": {
            "nl": (
                "Schuldeisersrangorde-percentages weerspiegelen wettelijke "
                "default-allocaties (Boek XX WER / Faillissementswet) bij "
                "afwezigheid van expliciete per-rang schuldenbuckets door "
                "de taxateur."
            ),
            "en": (
                "Insolvency priority cascade percentages reflect statutory "
                "default allocations (Boek XX WER / Faillissementswet) absent "
                "explicit per-tier liability buckets supplied by the appraiser."
            ),
        },
        "disclosure_default_limitations.2": {
            "nl": (
                "Afbouwkosten gebruiken jurisdictie-default-aannames "
                "(ontslagvergoedingsmultiplier, professional-fees-percentage, "
                "huurbeëindiging). Materiële afwijking vereist expliciete override."
            ),
            "en": (
                "Wind-down cost estimates use jurisdiction-default assumptions "
                "(severance multiplier, professional-fees percentage, lease "
                "termination). Material deviation requires explicit override."
            ),
        },
        "disclosure_default_limitations.3": {
            "nl": (
                "PV-discount past een distress WACC van 15% geordend / 25% "
                "gedwongen toe (Damodaran 2012 Hfdst. 23 SME-range). "
                "Custom WACC kan worden geleverd waar de cap-stack dit ondersteunt."
            ),
            "en": (
                "PV-discount applies a distress WACC of 15% orderly / 25% forced "
                "(Damodaran 2012 Ch. 23 SME range). Custom WACC may be supplied "
                "where the cap-stack supports it."
            ),
        },
        "disclosure_default_out_of_scope.0": {
            "nl": (
                "Litigatiereserves en voorwaardelijke juridische "
                "verplichtingen — deze moeten worden gekwantificeerd door "
                "de externe advocaat van de entiteit; het rapport schat de "
                "exposure NIET."
            ),
            "en": (
                "Litigation reserve and contingent legal liabilities — these "
                "must be quantified by the entity's outside counsel; the report "
                "does NOT estimate exposure."
            ),
        },
        "disclosure_default_out_of_scope.1": {
            "nl": (
                "Milieu-sanering — locatiespecifiek, vereist een Phase II "
                "milieu-onderzoek door een gekwalificeerd consultant."
            ),
            "en": (
                "Environmental remediation — site-specific, requires Phase II "
                "environmental assessment by qualified consultant."
            ),
        },
        "disclosure_default_out_of_scope.2": {
            "nl": (
                "Pensioenonderdekking — vereist een actuariële waardering "
                "volgens IAS 19; het rapport gaat ervan uit dat de "
                "geleverde DTL-bucket dit al dekt."
            ),
            "en": (
                "Pension underfunding — requires actuarial valuation per IAS 19; "
                "the report assumes the supplied DTL bucket already captures it."
            ),
        },
        "disclosure_default_out_of_scope.3": {
            "nl": (
                "Grensoverschrijdende fiscale planning — internationale "
                "structurering valt buiten de scope van een liquidatie-"
                "analyse voor één enkel land."
            ),
            "en": (
                "Cross-border tax planning — international structuring is outside "
                "the scope of a single-country liquidation analysis."
            ),
        },
        "disclosure_default_assumptions.0": {
            "nl": "Peildatum van de waardering = de geleverde balansrapportagedatum.",
            "en": "Effective date of valuation = balance-sheet reporting date supplied.",
        },
        "disclosure_default_assumptions.1": {
            "nl": "Presentatievaluta = EUR; geen FX-omrekening toegepast.",
            "en": "Currency of presentation = EUR; no FX translation applied.",
        },
        "disclosure_default_assumptions.2": {
            "nl": (
                "Going-concern premisse is van toepassing tenzij het distress-"
                "signaal liquidatie activeert volgens de IVS 104 §80 beslisboom."
            ),
            "en": (
                "Going-concern premise applies unless distress signal triggers "
                "liquidation per IVS 104 §80 decision tree."
            ),
        },
        "disclosure_default_assumptions.3": {
            "nl": (
                "Alle bedragen zijn vóór DLOM; gebrek-aan-verhandelbaarheidsdiscount "
                "is een aparte aanpassing buiten deze engine."
            ),
            "en": (
                "All figures are pre-DLOM; lack-of-marketability discount is a "
                "separate adjustment outside this engine."
            ),
        },
        "disclosure_default_independence_statement": {
            "nl": (
                "De software is geen taxateur en kan geen professionele "
                "onafhankelijkheidsverklaring afleggen. De goedkeurende adviseur "
                "moet voor deze opdracht persoonlijke en kantoorrelaties, "
                "vergoedingen, belangenconflicten en elk economisch belang vastleggen."
            ),
            "en": (
                "The software is not a valuer and cannot make a professional independence "
                "declaration. The approving advisor must document personal and firm-level "
                "relationships, fees, conflicts and any economic interest for this engagement."
            ),
        },
        "disclosure_default_conflicts_disclosure": {
            "nl": (
                "Geen materiële belangenconflicten geïdentificeerd op "
                "engine-niveau. Wanneer een menselijke taxateur de engine-"
                "output mede-ondertekent voor gerechtelijk werk, moet die "
                "taxateur zijn eigen AICPA SSVS No. 1 §52 conflictenverklaring "
                "toevoegen met betrekking tot persoonlijke en firma-niveau "
                "relaties met de entiteit, haar schuldeisers en eventuele "
                "potentiële bieders."
            ),
            "en": (
                "No material conflicts of interest identified at the model level. "
                "When a human appraiser counter-signs the model output for an "
                "independent professional report, that appraiser must add their own "
                "AICPA SSVS No. 1 §52 conflicts disclosure covering personal and "
                "firm-level relationships with the subject, its creditors, and "
                "any prospective bidders."
            ),
        },
        # ---------------------------------------------------------------
        # Net headline (post cascade + tax + wind-down)
        # ---------------------------------------------------------------
        "net_headline_label": {
            "nl": "Netto naar aandeelhouder (na cascade + belasting + afbouwkosten)",
            "en": "Net to shareholder (post cascade + tax + wind-down)",
        },
        # Caption shown under the orderly NET headline in the executive
        # summary, contextualising the gross-orderly fallback figure.
        # Replaces the hardcoded Dutch parenthetical that previously leaked
        # into EN reports (audit 2026-05-10, C2).
        "headline_gross_caption": {
            "nl": "(ondernemingswaarde vóór aandeelhoudersbelasting)",
            "en": "(company equity estimate before shareholder tax)",
        },
        # Inline label paired with the gross forced figure under the net
        # forced headline.  Replaces the hardcoded Dutch ``Bruto:`` literal
        # that previously leaked into EN reports (audit 2026-05-10, C3).
        "label_gross": {
            "nl": "Bruto",
            "en": "Gross",
        },
        # ---------------------------------------------------------------
        # Section 0 — Statement of Affairs (EY/KPMG M&A cover doc)
        # ---------------------------------------------------------------
        "soa_section_title": {
            "nl": "Statement of Affairs — M&A samenvatting",
            "en": "Statement of Affairs — M&A summary",
        },
        "soa_section_subtitle": {
            "nl": "Voorwaardelijke kasbrug per liquidatiescenario",
            "en": "Conditional cash bridge per liquidation scenario",
        },
        "soa_headline_net_orderly": {
            "nl": "Netto naar aandeelhouder (geordend)",
            "en": "Net to shareholder (orderly)",
        },
        "soa_headline_net_forced": {
            "nl": "Netto naar aandeelhouder (gedwongen)",
            "en": "Net to shareholder (forced)",
        },
        "soa_headline_book_equity": {
            "nl": "Boekwaarde eigen vermogen (referentie)",
            "en": "Book equity (reference)",
        },
        "soa_waterfall_title_orderly": {
            "nl": "Waterval — geordende liquidatie",
            "en": "Waterfall — orderly liquidation",
        },
        "soa_waterfall_title_forced": {
            "nl": "Waterval — gedwongen liquidatie",
            "en": "Waterfall — forced liquidation",
        },
        "buyer_range_not_assessed": {
            "nl": "Geen onderbouwde biedingsrange: netto-uitkeringen aan de eigenaar, ondernemingswaarde en bruto vervangingskosten hebben verschillende waarderingsgrondslagen. Koperspremies vereisen afzonderlijke onderbouwing.",
            "en": "Buyer bid range not assessed: after-tax owner proceeds, company equity and gross replacement cost have different value bases. Buyer premiums require separate supporting evidence.",
        },
        "soa_band_title": {
            "nl": "M&A koper-bid-band",
            "en": "M&A buyer bid band",
        },
        "soa_band_floor": {
            "nl": "Vloer (liquidatie, netto)",
            "en": "Floor (liquidation, net)",
        },
        "soa_band_reference": {
            "nl": "Referentie (going-concern)",
            "en": "Reference (going-concern)",
        },
        "soa_band_ceiling": {
            "nl": "Plafond (replacement cost)",
            "en": "Ceiling (replacement cost)",
        },
        # SoA waterfall step labels + rationales — keyed by
        # `WaterfallStep.step_code`.  Labels use `.format(**label_params)`
        # interpolation where the step carries dynamic content.  Rationales
        # are static per step_code.  Engine retains Dutch fallbacks so the
        # base engine tests + direct dict consumers stay green; the
        # report-context layer overlays the locale variant on the way to
        # the templates.
        "soa_waterfall_label_gross_assets_at_fmv": {
            "nl": "{scenario}: bruto activa op FMV",
            "en": "{scenario}: gross assets at FMV",
        },
        "soa_waterfall_rationale_gross_assets_at_fmv": {
            "nl": "Som van het 12-class realisatieschema, vóór kosten + crediteuren.",
            "en": "Sum of the 12-class realisation schedule, before costs + creditors.",
        },
        "soa_waterfall_label_deduction_wind_down": {
            "nl": "− Afbouwkosten (operationeel)",
            "en": "− Wind-down costs (operational)",
        },
        "soa_waterfall_rationale_deduction_wind_down": {
            "nl": (
                "Bottom-up build-up: payroll runway + huur + ontslagvergoeding "
                "+ professional fees + retentie + overige eenmalige kosten. "
                "EY/KPMG werkpapierformat."
            ),
            "en": (
                "Bottom-up build-up: payroll runway + rent + severance + "
                "professional fees + retention + other one-off costs. "
                "EY/KPMG working-paper format."
            ),
        },
        "soa_waterfall_label_subtotal_available_for_creditors": {
            "nl": "= Beschikbaar voor schuldeisers",
            "en": "= Available for creditors",
        },
        "soa_waterfall_rationale_subtotal_available_for_creditors": {
            "nl": "Netto-boedel voor de prioriteitscascade.",
            "en": "Net estate available for the priority cascade.",
        },
        "soa_waterfall_label_deduction_cascade_tier": {
            "nl": "− {prefix}: {tier_label}",
            "en": "− {prefix}: {tier_label}",
        },
        "soa_waterfall_label_subtotal_gross_distribution": {
            "nl": "= Bruto uitkering aan aandeelhouders",
            "en": "= Gross distribution to shareholders",
        },
        "soa_waterfall_rationale_subtotal_gross_distribution": {
            "nl": "Vóór belastingen.",
            "en": "Before taxes.",
        },
        "soa_waterfall_label_deduction_tax_leakage": {
            "nl": "− {tax_label}",
            "en": "− {tax_label}",
        },
        "soa_waterfall_rationale_deduction_tax_leakage": {
            "nl": "Liquidatiebonus / box-2 / DTL-reversal.",
            "en": "Liquidation bonus / box-2 / DTL reversal.",
        },
        "soa_waterfall_label_net_to_shareholder": {
            "nl": "= Netto naar aandeelhouder",
            "en": "= Net to shareholder",
        },
        "soa_waterfall_rationale_net_to_shareholder": {
            "nl": "Wat de eigenaar werkelijk in handen krijgt.",
            "en": "What the owner actually pockets.",
        },
        "soa_waterfall_rationale_net_to_shareholder_corrected": {
            "nl": (
                "Engine-gecorrigeerd. Cascade- of belastingclamp werd toegepast. "
                "Voor exacte reconciliatie zie individuele secties hieronder."
            ),
            "en": (
                "Engine-corrected. A cascade or tax clamp was applied. "
                "For exact reconciliation see the individual sections below."
            ),
        },
        # Scenario labels — also used as the {scenario} param above.
        "soa_scenario_orderly_label": {
            "nl": "Geordende liquidatie",
            "en": "Orderly liquidation",
        },
        "soa_scenario_forced_label": {
            "nl": "Gedwongen liquidatie",
            "en": "Forced liquidation",
        },
        # SoA root rationale (Section 00 cover prose).
        "soa_root_rationale": {
            "nl": "Kasbrug per scenario van realisatieopbrengsten naar de voorwaardelijke netto-uitkering aan aandeelhouders. Een biedingsrange vereist afzonderlijke onderbouwing en vergelijkbare waarderingsgrondslagen.",
            "en": "Per-scenario cash bridge from realisation proceeds to conditional after-tax shareholder proceeds. A buyer bid range requires separate evidence and comparable value bases.",
        },
        "soa_band_rationale": {
            "nl": "Deze historische waarden hebben verschillende grondslagen en vormen geen onderbouwde biedingsrange.",
            "en": "These historical values have different bases and do not establish a supported buyer bid range.",
        },
        "soa_tax_label_be": {
            "nl": "Belastinglekkage (BE liquidatiebonus + aanvullende vennootschapsbelasting)",
            "en": "Tax leakage (BE liquidation bonus + incremental corporate tax)",
        },
        "soa_tax_label_nl": {
            "nl": "Belastinglekkage (NL box-2 + aanvullende vennootschapsbelasting)",
            "en": "Tax leakage (NL box-2 + incremental corporate tax)",
        },
        # ---------------------------------------------------------------
        # Section 0b — Replacement Cost (M&A buyer ceiling)
        # ---------------------------------------------------------------
        "rc_section_title": {
            "nl": "Indicatieve vervangingskosten van activa",
            "en": "Indicative asset replacement cost",
        },
        "rc_section_subtitle": {
            "nl": "Kostenbenadering op basis van modelaannames; geen plafond voor een overnamebod",
            "en": "Cost approach using model assumptions; does not establish a buyer bid ceiling",
        },
        "rc_col_class": {"nl": "Activacategorie", "en": "Asset class"},
        "rc_col_book": {"nl": "Boek FMV", "en": "Book FMV"},
        "rc_col_crn_mult": {"nl": "CRN-factor", "en": "CRN factor"},
        "rc_col_crn_value": {
            "nl": "Cost of Reproduction New",
            "en": "Cost of Reproduction New",
        },
        "rc_col_remaining_life": {
            "nl": "Resterende levensduur",
            "en": "Remaining life",
        },
        "rc_col_depreciated": {"nl": "Afgeschreven waarde", "en": "Depreciated value"},
        "rc_total_tangible": {
            "nl": "Totaal materiële replacement",
            "en": "Total tangible replacement",
        },
        "rc_intangibles_uplift": {
            "nl": "Identificeerbare immateriële activa-opslag",
            "en": "Identifiable intangibles uplift",
        },
        # Caption shown beneath the intangibles uplift label, citing the
        # academic anchor.  Uses ``{pct}`` for the rounded percentage so
        # both NL+EN show locale-neutral digits.  Replaces the hardcoded
        # English ``... — Reilly & Schweihs (1998) Ch. 16`` that previously
        # leaked into NL reports (audit 2026-05-10, C4).
        "rc_intangibles_uplift_caption": {
            "nl": "{pct}% van de materiële basis — Reilly & Schweihs (1998) hfd. 16",
            "en": "{pct}% of tangible base — Reilly & Schweihs (1998) Ch. 16",
        },
        "rc_total_replacement": {
            "nl": "Totale indicatieve vervangingskosten",
            "en": "Total indicative replacement cost",
        },
        # ---------------------------------------------------------------
        # Audit Trail — Run ID + payload hash + engine version
        # ---------------------------------------------------------------
        "audit_trail_title": {
            "nl": "Audit-trail",
            "en": "Audit trail",
        },
        "audit_trail_run_id": {
            "nl": "Run-ID",
            "en": "Run ID",
        },
        "audit_trail_effective_date": {
            "nl": "Peildatum (effective date)",
            "en": "Effective date",
        },
        "audit_trail_computed_at": {
            "nl": "Berekend op",
            "en": "Computed at",
        },
        "audit_trail_engine_version": {
            "nl": "Modelversie",
            "en": "Calculation model version",
        },
        "audit_trail_payload_hash": {
            "nl": "Payload hash (SHA-256)",
            "en": "Payload hash (SHA-256)",
        },
        "audit_trail_explainer": {
            "nl": (
                "Elke valuation run heeft een unieke Run-ID. De payload-hash "
                "bevestigt dat de inputs niet gewijzigd zijn tussen berekening "
                "en rapport-lezing. Reproduceerbaar volgens AICPA SSVS No. 1 §57(d)."
            ),
            "en": (
                "Each valuation run has a unique Run ID. The payload hash "
                "confirms inputs haven't drifted between computation and "
                "report reading. Reproducible per AICPA SSVS No. 1 §57(d)."
            ),
        },
    }
