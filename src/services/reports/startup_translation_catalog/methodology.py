"""Method breakdown, advisor CTA, and methodology appendix copy."""

from __future__ import annotations

STARTUP_REPORT_METHODOLOGY_TRANSLATIONS: dict[str, dict[str, str]] = {
    "triangulation_per_method": {
        "nl": "Triangulatie per methode",
        "en": "Triangulation per method",
    },
    "triangulation_caption": {
        "nl": (
            "Elke staaf toont de pre-money implicatie van één methodologie "
            "vóór weging. De stippellijn markeert de gewogen mix (€{mid})."
        ),
        "en": (
            "Each bar shows the pre-money implied by a single methodology "
            "before blending. The dashed line marks the weighted blend (€{mid})."
        ),
    },
    "blended_pre_money_legend": {
        "nl": "Gewogen pre-money (methodemix): €{mid}",
        "en": "Blended pre-money (weighted mix): €{mid}",
    },
    "method_vc_short": {"nl": "VC-methode", "en": "VC method"},
    "defensibility_section_title": {
        "nl": "Verdedigbaarheid — kernveronderstellingen",
        "en": "Defensibility — key assumptions",
    },
    "defensibility_section_caption": {
        "nl": (
            "Deze lijst is bedoeld om in een dataroom of investeerdersmemo te "
            "plaatsen: elk getal hierboven is direct herleidbaar naar één van "
            "deze aannames."
        ),
        "en": (
            "This list is designed to drop into a data room or investor memo: "
            "every number above can be traced directly to one of these "
            "assumptions."
        ),
    },
    "vc_assumptions_title": {
        "nl": "Kernveronderstellingen (VC-methode)",
        "en": "Key assumptions (VC method)",
    },
    "label_y5_revenue_simple": {
        "nl": "Jaar-5 omzet (projectie)",
        "en": "Year-5 revenue (projection)",
    },
    "label_exit_ev_revenue_multiple": {
        "nl": "Exit EV/omzet-multiple",
        "en": "Exit EV/revenue multiple",
    },
    # B3 — Source citation for the exit multiple. Renders inline under
    # the multiple in the VC method table so the M&A reader sees
    # provenance next to the number, not 200 lines below in the comps
    # table. ``source`` interpolates the canonical Athena/Damodaran
    # label that the engine emits per sector.
    "vc_multiple_source_caption": {
        "nl": (
            "Bron: {source} · {sector} · sector-mediaan, range {p25}×–{p75}×. "
            "Volledige peer-tabel: zie de Vergelijkbare bedrijven sectie verderop."
        ),
        "en": (
            "Source: {source} · {sector} · sector median, range {p25}×–{p75}×. "
            "Full peer table: see the Sector Comparables section below."
        ),
    },
    "vc_multiple_source_caption_unsourced": {
        "nl": (
            "Geen sector-mediaan beschikbaar uit de peer-tabel — de huidige "
            "multiple is afkomstig uit de regionale standaardwaarden van de motor "
            "(Athena Q1 2026)."
        ),
        "en": (
            "No sector median available from the peer table — the current "
            "multiple comes from the engine's regional defaults (Athena "
            "Q1 2026)."
        ),
    },
    # B3 — Triangulation range framed as P10/P50/P90. Engine emits
    # low/mid/high from the leg-blend (Berkus + SaaS Forward + VC). We
    # relabel for M&A readers fluent in percentile framing and call
    # out explicitly that this is an empirical range, not a Monte-Carlo
    # distribution.
    "pre_money_distribution_title": {
        "nl": "Pre-money triangulatiebereik (P10 · P50 · P90)",
        "en": "Pre-money triangulation range (P10 · P50 · P90)",
    },
    "pre_money_distribution_caption": {
        "nl": (
            "P10 / P50 / P90 zijn de empirische ondergrens, mediaan en "
            "bovengrens van de methodemix-triangulatie. Geen Monte-Carlo-"
            "distributie — een Monte-Carlo-lens komt in een latere release."
        ),
        "en": (
            "P10 / P50 / P90 are the empirical low, median and high of the "
            "leg-blend triangulation. Not a Monte-Carlo distribution — a "
            "Monte-Carlo lens ships in a later release."
        ),
    },
    "pre_money_distribution_p10": {"nl": "P10 (ondergrens)", "en": "P10 (low)"},
    "pre_money_distribution_p50": {"nl": "P50 (mediaan)", "en": "P50 (median)"},
    "pre_money_distribution_p90": {"nl": "P90 (bovengrens)", "en": "P90 (high)"},
    "pre_money_distribution_spread_label": {
        "nl": "Spread (P90 ÷ P10)",
        "en": "Spread (P90 ÷ P10)",
    },
    "label_target_roi": {
        "nl": "Doel-ROI investeerder",
        "en": "Investor target ROI",
    },
    "traction_snapshot": {
        "nl": "Tractie-overzicht",
        "en": "Traction snapshot",
    },
    "label_mom_growth": {"nl": "MoM-groei", "en": "MoM growth"},
    "label_monthly_churn": {
        "nl": "Maandelijkse churn",
        "en": "Monthly churn",
    },
    "label_runway": {"nl": "Kasrunway", "en": "Runway"},
    "unit_months_short": {"nl": "mnd", "en": "mo"},
    # PDF-only twins (executive summary)
    "indicative_pre_money_canonical": {
        "nl": "Indicatieve pre-money waardering (canoniek hoofdcijfer)",
        "en": "Indicative pre-money valuation (canonical headline)",
    },
    "method_mix_advisor": {
        "nl": "Methodemix (adviseur, 4 methoden)",
        "en": "Method mix (advisor 4-leg)",
    },
    "method_mix_founder_3leg_caption": {
        "nl": "Methodemix (oprichter, 3 methoden)",
        "en": "Method mix (founder 3-leg)",
    },
    "vc_oversubscribed_pdf_body": {
        "nl": (
            "Je vraagt <strong>€{ask}</strong> op, maar je jaar-5-projectie + "
            "exit-multiple impliceren slechts een post-money van "
            "<strong>€{post}</strong>. De VC-methode is voor deze mix op €0 "
            "gezet. Verlaag je ronde met <strong>€{shortfall}</strong>, of "
            "verhoog je jaar-5-projectie / exit-multiple."
        ),
        "en": (
            "You're asking for <strong>€{ask}</strong>, but your Year-5 "
            "projection × exit multiple implies a post-money of only "
            "<strong>€{post}</strong>. The VC method has been zeroed in this "
            "blend. Reduce the round by <strong>€{shortfall}</strong>, or "
            "raise your Year-5 projection / exit multiple."
        ),
    },
    "outlier_capped_title": {
        "nl": "Eén of meer methoden zijn afgevlakt door het uitschieterbeleid",
        "en": "One or more methods were flattened by the outlier policy",
    },
    "outlier_capped_body": {
        "nl": (
            "De Tukey-fence-cap (k={k}) verhindert dat één methode de mix "
            "onevenredig naar boven trekt. Mediaan: €{median}; grens: €{fence}."
        ),
        "en": (
            "The Tukey fence (k={k}) cap prevents any single leg from pulling "
            "the blend disproportionately upward. Median: €{median}; "
            "fence: €{fence}."
        ),
    },
    "sector_consistency_title": {
        "nl": "Sectorconsistentie: SaaS-forwardmethode niet toegepast",
        "en": "Sector consistency: SaaS Forward method skipped",
    },
    "sector_consistency_body": {
        "nl": (
            "Sector <strong>{sector}</strong> is geen SaaS-, fintech- of "
            "deeptech-AI-categorie met terugkerende omzet; de SaaS-forwardmethode levert "
            "hier geen verdedigbaar getal en is bewust uitgeschakeld."
        ),
        "en": (
            "Sector <strong>{sector}</strong> is not a recurring-revenue SaaS / "
            "Fintech / Deeptech-AI category; the SaaS Forward Multiple method "
            "doesn't yield a defensible number here and was deliberately "
            "skipped."
        ),
    },
    "triangulation_pdf_caption": {
        "nl": (
            "Elke staaf toont de pre-money implicatie per methode (na "
            "uitschietercap). Het canonieke hoofdcijfer (€{head}) wordt berekend "
            "als de mediaan van de adviseursmix met 4 methoden (€{advisor}) en de "
            "oprichtersmix met 3 methoden (€{founder})."
        ),
        "en": (
            "Each bar shows the pre-money implied per method (after the "
            "outlier cap). The canonical headline (€{head}) is computed as "
            "the median of the advisor 4-leg blend (€{advisor}) and the "
            "founder 3-leg blend (€{founder})."
        ),
    },
    "canonical_pre_money_blended_median": {
        "nl": "Canonieke pre-money (gewogen mediaan)",
        "en": "Canonical pre-money (blended median)",
    },
    "defensibility_data_room_caption": {
        "nl": (
            "Plaats deze lijst direct in een dataroom of investeerdersmemo — elk "
            "getal hierboven is hieruit herleidbaar."
        ),
        "en": (
            "Drop this list straight into a data room or investor memo — "
            "every number above traces back to one of these assumptions."
        ),
    },
    # Advisor CTA partial
    "advisor_cta_section_title": {
        "nl": "Volgende stap — certificering",
        "en": "Next step — certification",
    },
    "advisor_cta_lead_p1": {
        "nl": (
            "Dit rapport is een sterke basis voor de eerste "
            "investeerdersgesprekken — de drie methodologieën hierboven "
            "(Berkus, Scorecard, VC-methode{saas}) geven angels en "
            "seed-fondsen het soort triangulatie waar ze om vragen."
        ),
        "en": (
            "This report is a strong baseline for first investor "
            "conversations — the three methodologies above (Berkus, "
            "Scorecard, VC method{saas}) give angels and seed funds the "
            "kind of triangulation they expect."
        ),
    },
    "advisor_cta_with_saas_suffix": {
        "nl": " + SaaS-forwardmultiple",
        "en": " + SaaS forward multiple",
    },
    "advisor_cta_lead_p2": {
        "nl": (
            "<strong>Voor formele term sheets en SAFE-overeenkomsten</strong> "
            "heb je een gevalideerd financieel model en een door je "
            "accountant ondertekende participatietabel nodig. Eén klik — we sturen "
            "een uitnodiging naar je accountant met dit rapport voorgevuld "
            "in de volledige Upswitch-dataroom."
        ),
        "en": (
            "<strong>For formal term sheets and SAFE agreements</strong> "
            "you'll need a validated financial model and a cap table signed "
            "off by your accountant. One click — we'll send your accountant "
            "an invitation with this report pre-filled into the full "
            "Upswitch data room."
        ),
    },
    "advisor_cta_button": {
        "nl": (
            "Nodig mijn accountant uit — certificeer & ontgrendel de "
            "volledige Upswitch-dataroom"
        ),
        "en": ("Invite my accountant — certify & unlock the full Upswitch " "data room"),
    },
    "advisor_cta_footnote": {
        "nl": "Gratis voor de oprichter · deelt alleen dit rapport · GDPR-veilig",
        "en": "Free for the founder · shares only this report · GDPR-safe",
    },
    "advisor_cta_what_title": {
        "nl": "Wat krijgt je accountant?",
        "en": "What does your accountant receive?",
    },
    "advisor_cta_li_1": {
        "nl": "Volledig auditspoor van alle 4 methodologieën (Berkus, Scorecard, VC, SaaS-forward).",
        "en": "Full audit trail across all 4 methodologies (Berkus, Scorecard, VC, SaaS forward).",
    },
    "advisor_cta_li_2": {
        "nl": "Pre-money/post-moneysimulator met SAFE-conversies en optiepoolverwatering.",
        "en": "Pre-money / post-money simulator with SAFE conversions and option-pool dilution.",
    },
    "advisor_cta_li_3": {
        "nl": "Ondertekenbaar PDF-certificaat — klaar voor de dataroom en de notaris.",
        "en": "Signable PDF certificate — ready for the data room and the notary.",
    },
    "advisor_cta_li_4": {
        "nl": "Eén klik om over te schakelen naar normalisaties + Yuki/Exact/Silverfin live-koppeling.",
        "en": "One click to switch to normalisations + Yuki/Exact/Silverfin live connection.",
    },
    # Method-breakdown page
    "method_breakdown_title": {
        "nl": "Methode-uitsplitsing",
        "en": "Method breakdown",
    },
    "berkus_section_caption": {
        "nl": (
            "Vijf risico-mijlpalen, elk maximaal €{max}. "
            "Cap-niveau gekalibreerd op Atomico SoEU 2024 + Dealroom Benelux 2024 (Athena Q1 2026)."
        ),
        "en": (
            "Five risk-reduction milestones, each capped at €{max}. "
            "Cap level calibrated against Atomico SoEU 2024 + Dealroom Benelux 2024 (Athena Q1 2026)."
        ),
    },
    "berkus_col_milestone": {"nl": "Mijlpaal", "en": "Milestone"},
    "berkus_col_score": {"nl": "Score", "en": "Score"},
    "berkus_col_contribution": {"nl": "Bijdrage", "en": "Contribution"},
    "scorecard_section_caption": {
        "nl": (
            "Regio-gemiddelde €{avg} × multiplier {mult}×. "
            "Regio-gemiddelde uit Athena Q1 2026 (Atomico + Dealroom Benelux 2024)."
        ),
        "en": (
            "Regional average €{avg} × multiplier {mult}×. "
            "Regional average drawn from Athena Q1 2026 (Atomico + Dealroom Benelux 2024)."
        ),
    },
    "scorecard_col_factor": {"nl": "Factor", "en": "Factor"},
    "scorecard_col_weight": {"nl": "Gewicht", "en": "Weight"},
    "scorecard_col_score": {"nl": "Score", "en": "Score"},
    "scorecard_col_multiplier": {"nl": "Multiplier", "en": "Multiplier"},
    "scorecard_col_weighted": {"nl": "Gewogen", "en": "Weighted"},
    "saas_forward_section_caption": {
        "nl": (
            "Toekomstige ARR over 12 maanden × risico-aangepaste regio-multiple. "
            "Bron: Atomico SoEU 2024 + Dealroom Benelux."
        ),
        "en": (
            "Forward 12-month ARR × risk-adjusted regional multiple. "
            "Source: Atomico SoEU 2024 + Dealroom Benelux."
        ),
    },
    "saas_label_current_arr": {"nl": "Huidige ARR", "en": "Current ARR"},
    "saas_label_forward_arr": {
        "nl": "Toekomstige ARR over 12 maanden (proj.)",
        "en": "Forward 12-month ARR (proj.)",
    },
    "saas_label_mom_growth_used": {
        "nl": "MoM-groeitempo gebruikt",
        "en": "MoM growth rate used",
    },
    "saas_label_base_multiple": {
        "nl": "Basis EV/Omzet multiple (regio)",
        "en": "Base EV/Revenue multiple (regional)",
    },
    "saas_label_risk_discount": {
        "nl": "Risicokorting (Berkus-oppervlak)",
        "en": "Risk discount (Berkus surface)",
    },
    "saas_label_churn_drag": {
        "nl": "Churn-effect",
        "en": "Churn drag",
    },
    "saas_label_applied_multiple": {
        "nl": "Toegepaste multiple",
        "en": "Applied multiple",
    },
    # Sector comparables block (M&A/VC-grade peer table)
    "comps_section_title": {
        "nl": "Sectorvergelijking — multiples van vergelijkbare bedrijven",
        "en": "Sector comparables — peer multiples",
    },
    "comps_section_caption": {
        "nl": (
            "Top-{n} vergelijkbare bedrijfstypen voor jouw sector ({sector}). "
            "Multiples (P25 / mediaan / P75) komen uit de Damodaran-corpus en "
            "publieke transacties — gebruikt om je VC-methode en SaaS-forwardanker "
            "te controleren."
        ),
        "en": (
            "Top-{n} comparable business types for your sector ({sector}). "
            "Multiples (P25 / median / P75) drawn from the Damodaran corpus + "
            "public transactions — used to cross-check the VC method and "
            "SaaS-forward anchor."
        ),
    },
    "comps_col_business_type": {"nl": "Bedrijfstype", "en": "Business type"},
    "comps_col_ev_ebitda": {"nl": "EV / EBITDA", "en": "EV / EBITDA"},
    "comps_col_ev_revenue": {"nl": "EV / Omzet", "en": "EV / Revenue"},
    "comps_col_ebitda_margin": {"nl": "Typ. EBITDA-marge", "en": "Typ. EBITDA margin"},
    "comps_col_source": {"nl": "Bron", "en": "Source"},
    # Quartile sub-headers for the split-column sector-comparables table
    # (audit issue #20).  Lowercase ``p25`` / ``p75`` so they read as
    # statistical labels rather than a brand.
    "comps_col_p25": {"nl": "P25", "en": "P25"},
    "comps_col_median": {"nl": "Mediaan", "en": "Median"},
    "comps_col_p75": {"nl": "P75", "en": "P75"},
    "comps_band_template": {
        "nl": "{p25}× / {median}× / {p75}×",
        "en": "{p25}× / {median}× / {p75}×",
    },
    "comps_band_legend": {
        "nl": "Formaat: P25 / mediaan / P75",
        "en": "Format: P25 / median / P75",
    },
    # ------------------------------------------------------------------
    # Methodology appendix — defensibility audit trail. The page renders
    # the math + sources behind every leg + the canonical headline
    # construction.  Lives at the end of the startup report (section 06)
    # so an M&A reviewer can flip there directly when challenging the
    # numbers.  See ``main_report/pages/startup_methodology.html``.
    # ------------------------------------------------------------------
    "methodology_section_title": {
        "nl": "Methodologie & verdedigbaarheid",
        "en": "Methodology & defensibility",
    },
    "methodology_section_lead": {
        "nl": (
            "Deze appendix legt uit hoe elk getal tot stand komt: welke methoden "
            "de motor draait, welke formule erachter zit, hoe de canonieke "
            "hoofdcijfer wordt gekozen, en welke benchmarks worden geraadpleegd. "
            "Ontworpen voor accountants en M&A-beoordelaars die de cijfers willen "
            "narekenen."
        ),
        "en": (
            "This appendix explains how every number is produced: which methods "
            "the engine runs, the formula behind each one, how the canonical "
            "headline is selected, and which benchmarks are consulted. Designed "
            "for accountants and M&A reviewers who want to recompute the math."
        ),
    },
    "methodology_methods_title": {
        "nl": "1. De vier methoden",
        "en": "1. The four methods",
    },
    "methodology_source_label": {"nl": "Bron", "en": "Source"},
    # PDF column headers (table-flavoured layout)
    "methodology_col_method": {"nl": "Methode", "en": "Method"},
    "methodology_col_purpose": {"nl": "Doel", "en": "Purpose"},
    "methodology_col_formula": {"nl": "Formule", "en": "Formula"},
    "methodology_col_source": {"nl": "Bron", "en": "Source"},
    # ---- Berkus
    "methodology_berkus_purpose": {
        "nl": "Risicoreductie — kwantificeert hoeveel uitvoeringsrisico is weggenomen.",
        "en": "Risk reduction — quantifies how much execution risk has been retired.",
    },
    "methodology_berkus_body": {
        "nl": (
            "Vijf mijlpalen (idee, prototype, team, partnerships, eerste verkoop) "
            "elk gescoord 0–100. Elke score levert een aandeel van een per-mijlpaal "
            "plafond op dat regionaal is geijkt op de mediane Benelux-pre-seed."
        ),
        "en": (
            "Five milestones (idea, prototype, team, partnerships, first sales) "
            "each scored 0–100. Each score unlocks a share of a per-milestone "
            "ceiling, calibrated to the median Benelux pre-seed."
        ),
    },
    "methodology_berkus_formula": {
        "nl": "pre-money = Σ ( score / 100 × max_per_milestone )",
        "en": "pre-money = Σ ( score / 100 × max_per_milestone )",
    },
    "methodology_berkus_source": {
        "nl": "Dave Berkus (~1990s) · 2024 herkalibratie tegen Atomico/Dealroom Benelux mediane pre-seed.",
        "en": "Dave Berkus (~1990s) · 2024 recalibration against Atomico/Dealroom Benelux median pre-seed.",
    },
    # ---- Scorecard
    "methodology_scorecard_purpose": {
        "nl": "Verdedigbaarheid — vergelijkt de startup met de regionale mediane gefinancierde peer.",
        "en": "Defensibility — benchmarks the startup against the regional median funded peer.",
    },
    "methodology_scorecard_body": {
        "nl": (
            "Vijf gewogen factoren (kansomvang, concurrentie, sales/marketing, "
            "kapitaalbehoefte, overig). Score 50 = 1.0× peer; 100 = 1.5×; 0 = 0.5×. "
            "Multiplier toegepast op de regionale mediane pre-money."
        ),
        "en": (
            "Five weighted factors (opportunity size, competition, sales / "
            "marketing, capital efficiency, other). Score 50 = 1.0× peer; "
            "100 = 1.5×; 0 = 0.5×. The multiplier is applied to the regional "
            "median pre-money."
        ),
    },
    "methodology_scorecard_formula": {
        "nl": "pre-money = average_pre_money × Σ ( weight_i × multiplier_i )",
        "en": "pre-money = average_pre_money × Σ ( weight_i × multiplier_i )",
    },
    "methodology_scorecard_source": {
        "nl": "Bill Payne / Frontier Angels — gepubliceerde methodologie, 2024 update. Upswitch-variant: management & product worden in Berkus geprijsd, niet hier (geen dubbele telling).",
        "en": "Bill Payne / Frontier Angels — published methodology, 2024 update. Upswitch variant: management + product are priced in Berkus, not here (no double-counting).",
    },
    # ---- VC method
    "methodology_vc_purpose": {
        "nl": "Exit-gedreven — wat moet het fonds zien om de cheque te schrijven?",
        "en": "Exit-driven — what does the fund need to see to write the cheque?",
    },
    "methodology_vc_body": {
        "nl": (
            "Y5-omzet × exit EV/omzet-multiple geeft de eindwaarde. "
            "Gedeeld door de doel-ROI levert de post-money van vandaag op; minus "
            "de op te halen ronde levert de pre-money. Begrensd op ≥ 0 wanneer de "
            "ronde groter is dan de impliciete post-money (het 'je vraagt te veel'-signaal)."
        ),
        "en": (
            "Y5 revenue × exit EV/Revenue multiple gives the terminal value. "
            "Divided by the target ROI yields today's post-money; subtracting "
            "the round size yields the pre-money. Clamped to ≥ 0 when the "
            "round exceeds the implied post-money (the 'you're asking too much' signal)."
        ),
    },
    "methodology_vc_formula": {
        "nl": "pre = ( Y5 × exit_mult / target_roi ) − round_size",
        "en": "pre = ( Y5 × exit_mult / target_roi ) − round_size",
    },
    "methodology_vc_source": {
        "nl": "Bill Sahlman, Harvard Business Review (1987) — sector-multiples van Damodaran corpus + recente public-deals (Athena Q1 2026).",
        "en": "Bill Sahlman, Harvard Business Review (1987) — sector multiples from Damodaran corpus + recent public deals (Athena Q1 2026).",
    },
    # ---- SaaS Forward
    "methodology_saas_forward_purpose": {
        "nl": "Tractie-gedreven — alleen actief wanneer er terugkerende omzet draait.",
        "en": "Traction-driven — only active when recurring revenue is on the books.",
    },
    "methodology_saas_forward_body": {
        "nl": (
            "Forward-12 ARR (huidige MRR × 12 maanden samengestelde groei) × een "
            "regionale forward-multiple, risico-gecorrigeerd op basis van de Berkus-"
            "oppervlakte en maandelijkse churn. Geen omzet → methode wordt overgeslagen."
        ),
        "en": (
            "Forward-12 ARR (current MRR compounded 12 months) × a regional "
            "forward multiple, risk-adjusted by the Berkus surface and monthly "
            "churn. No revenue → leg is skipped."
        ),
    },
    "methodology_saas_forward_formula": {
        "nl": "pre = forward_arr × ( base_multiple × risk_discount − churn_drag )",
        "en": "pre = forward_arr × ( base_multiple × risk_discount − churn_drag )",
    },
    "methodology_saas_forward_source": {
        "nl": "Index Ventures · Seedcamp · Point Nine consortium-blueprint, INSEAD/LBS 2025 — Bessemer State of the Cloud + KeyBanc/OpenView Private SaaS Survey voor multiples.",
        "en": "Index Ventures · Seedcamp · Point Nine consortium blueprint, INSEAD/LBS 2025 — Bessemer State of the Cloud + KeyBanc/OpenView Private SaaS Survey for multiples.",
    },
    # ---- Canonical headline
    "methodology_canonical_title": {
        "nl": "2. Het canonieke hoofdcijfer",
        "en": "2. The canonical headline",
    },
    "methodology_canonical_body": {
        "nl": (
            "Twee methodemixen draaien parallel; het paginahoofdcijfer is hun mediaan. "
            "Bewust ontworpen om te voorkomen dat aangrenzende pagina's twee "
            "verschillende getallen tonen (april-2026 hardening)."
        ),
        "en": (
            "Two blends run in parallel; the page headline is their median. "
            "Deliberately designed to prevent adjacent pages from showing two "
            "different numbers (April 2026 hardening)."
        ),
    },
    "methodology_canonical_advisor_label": {"nl": "Adviseur, 4 methoden", "en": "Advisor 4-leg"},
    "methodology_canonical_advisor_body": {
        "nl": "Berkus + Scorecard + VC + SaaS Forward, fase-gewogen.",
        "en": "Berkus + Scorecard + VC + SaaS Forward, stage-weighted.",
    },
    "methodology_canonical_founder_label": {"nl": "Oprichter, 3 methoden", "en": "Founder 3-leg"},
    "methodology_canonical_founder_body": {
        "nl": "Berkus + VC + SaaS Forward (Scorecard verschuift naar verdedigbaarheid). Consortium-blauwdruk.",
        "en": "Berkus + VC + SaaS Forward (Scorecard moves under defensibility). Consortium blueprint.",
    },
    "methodology_canonical_headline_label": {"nl": "Canoniek", "en": "Canonical"},
    "methodology_canonical_headline_body": {
        "nl": "Mediaan van beide methodemixen. Bandbreedte omspant de unie van beide banden.",
        "en": "Median of both blends. Range spans the union of both bands.",
    },
    # ---- Overlay layers
    "methodology_overlays_title": {
        "nl": "3. Overlay-lagen",
        "en": "3. Overlay layers",
    },
    "methodology_overlay_col_layer": {"nl": "Laag", "en": "Layer"},
    "methodology_overlay_col_what": {"nl": "Wat", "en": "What"},
    "methodology_overlay_col_when": {"nl": "Wanneer actief", "en": "When active"},
    "methodology_overlay_pedigree_layer": {
        "nl": "Oprichter-pedigree",
        "en": "Founder pedigree",
    },
    "methodology_overlay_pedigree_what": {
        "nl": "Multiplicatieve overlay 0.70× – 1.80× op de basiswaarde van de methodemix. Per claim alleen meegenomen met onderbouwing (geen onderbouwing → delta wordt op nul gezet).",
        "en": "Multiplicative overlay 0.70× – 1.80× on the leg-blend baseline. Per-claim evidence-gated (no rationale → delta zeroed).",
    },
    "methodology_overlay_pedigree_when": {
        "nl": "Wanneer ≥1 kwalificatie aangevinkt.",
        "en": "When ≥1 qualification is checked.",
    },
    "methodology_overlay_lens_layer": {
        "nl": "Inception-lens",
        "en": "Inception lens",
    },
    "methodology_overlay_lens_what": {
        "nl": "Optionele overlay voor momentum-gedreven of inception-bet-profielen. Verhoogt het middencijfer en verbreedt de variantieband (eerlijk over hogere onzekerheid).",
        "en": "Opt-in overlay for momentum-driven or inception-bet profiles. Lifts the mid and widens the variance band (honest about increased variance).",
    },
    "methodology_overlay_lens_when": {
        "nl": "Wanneer de oprichter actief een lens kiest (standaard = mijlpaalgedreven, geen wijziging).",
        "en": "When the founder actively picks a lens (default = milestones-driven, no-op).",
    },
    "methodology_overlay_outlier_layer": {
        "nl": "Uitschietercap (Tukey)",
        "en": "Outlier cap (Tukey)",
    },
    "methodology_overlay_outlier_what": {
        "nl": "Een Tukey-fence dempt extreme methode-uitkomsten zodat de mix niet door één agressieve Y5 wordt gedragen.",
        "en": "A Tukey fence dampens extreme leg outputs so the blend isn't pulled by a single aggressive Y5.",
    },
    "methodology_overlay_outlier_when": {
        "nl": "Wanneer ≥3 methoden bijdragen.",
        "en": "When ≥3 legs contribute.",
    },
    "methodology_overlay_sector_layer": {
        "nl": "Sector-consistentie",
        "en": "Sector consistency",
    },
    "methodology_overlay_sector_what": {
        "nl": "SaaS Forward wordt uitgeschakeld voor sectoren zonder terugkerende omzet (hardware / consument / overig).",
        "en": "SaaS Forward is disabled for sectors without recurring revenue (hardware / consumer / other).",
    },
    "methodology_overlay_sector_when": {
        "nl": "Per actieve sector — zie het verdedigbaarheidspaneel voor de gemarkeerde keuze.",
        "en": "Per active sector — see the defensibility panel for the flagged choice.",
    },
    # ---- Sources
    "methodology_sources_title": {
        "nl": "4. Bronnen",
        "en": "4. Sources",
    },
    "methodology_source_atomico": {
        "nl": "Atomico — State of European Tech 2024 (Benelux pre-seed mediaanpre-money + verwateringscohorten).",
        "en": "Atomico — State of European Tech 2024 (Benelux pre-seed median pre-money + dilution cohorts).",
    },
    "methodology_source_dealroom": {
        "nl": "Dealroom — Benelux 2024 (sector-mediaan exit-EV/Omzet, oprichter-pedigree-cohorten).",
        "en": "Dealroom — Benelux 2024 (sector-median exit EV/Revenue, founder-pedigree cohorts).",
    },
    "methodology_source_bessemer": {
        "nl": "Bessemer — State of the Cloud 2024 (forward-multipleband per ARR-niveau).",
        "en": "Bessemer — State of the Cloud 2024 (forward multiple band per ARR tier).",
    },
    "methodology_source_keybanc": {
        "nl": "KeyBanc / OpenView — Private SaaS Survey (groei-/churnmediaan + terugverdienbanden).",
        "en": "KeyBanc / OpenView — Private SaaS Survey (growth / churn medians + payback bands).",
    },
    "methodology_source_damodaran": {
        "nl": "Damodaran — sector-multiples (NYU Stern), aangevuld met recente publieke transactieobservaties (Athena Q1 2026).",
        "en": "Damodaran — sector multiples (NYU Stern), augmented with recent public-deal observations (Athena Q1 2026).",
    },
    "methodology_disclaimer": {
        "nl": (
            "Een waardering is altijd een driehoeking. Voor een term sheet of "
            "SAFE-conversie moet een accountant de participatietabel valideren — de "
            "advisor-CTA bovenaan dit rapport opent dat traject in één klik."
        ),
        "en": (
            "A valuation is always a triangulation. For a term sheet or SAFE "
            "conversion, an accountant should sign off the cap table — the "
            "advisor CTA at the top of this report opens that flow in one click."
        ),
    },
}
