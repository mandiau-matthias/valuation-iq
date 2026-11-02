"""Evidence, canonical-basis, sector, and method label copy."""

from __future__ import annotations

STARTUP_REPORT_EVIDENCE_LABEL_TRANSLATIONS: dict[str, dict[str, str]] = {
    "full_audit_trail": {
        "nl": "Volledig auditspoor → zie methode-uitsplitsing verderop.",
        "en": "Full audit trail → see method breakdown below.",
    },
    # CTA
    "cta_ready_for_term_sheet_title": {
        "nl": "Klaar voor een termsheet? Laat je accountant dit certificeren.",
        "en": "Ready for a term sheet? Have your accountant certify this.",
    },
    "cta_ready_for_term_sheet_subtitle": {
        "nl": (
            "Eén klik — we sturen een uitnodiging met dit rapport "
            "voorgevuld in de Upswitch-dataroom."
        ),
        "en": (
            "One click — we'll send an invitation with this report "
            "pre-filled in the Upswitch data room."
        ),
    },
    "cta_invite_accountant": {
        "nl": "Nodig mijn accountant uit",
        "en": "Invite my accountant",
    },
    # Defensibility row labels (server-built)
    "label_year5_revenue": {
        "nl": "Jaar-5 omzet (projectie)",
        "en": "Year-5 revenue (projection)",
    },
    "label_exit_revenue_multiple": {
        "nl": "Exit EV/omzet-multiple",
        "en": "Exit EV/Revenue multiple",
    },
    "label_vc_roi_target": {"nl": "VC ROI-doel", "en": "VC ROI target"},
    "label_round_to_raise": {
        "nl": "Op te halen ronde",
        "en": "Round being raised",
    },
    "label_forward_arr": {
        "nl": "Toekomstige ARR over 12 mnd",
        "en": "Forward 12mo ARR",
    },
    "label_applied_saas_multiple": {
        "nl": "Toegepaste SaaS-multiple",
        "en": "Applied SaaS multiple",
    },
    "label_basis_risk_discount": {
        "nl": "basis {base}x, risicokorting {disc}%",
        "en": "base {base}x, risk discount {disc}%",
    },
    "label_berkus_milestones_hit": {
        "nl": "Behaalde Berkus-mijlpalen",
        "en": "Berkus milestones achieved",
    },
    "label_scorecard_vs_region": {
        "nl": "Scorecard t.o.v. regio",
        "en": "Scorecard vs. region",
    },
    "label_scorecard_value": {
        "nl": "{mult:.2f}× regio-gemiddelde",
        "en": "{mult:.2f}× regional average",
    },
    "label_pedigree_multiplier": {
        "nl": "Multiplier oprichtersprofiel",
        "en": "Founder pedigree multiplier",
    },
    "label_pedigree_value": {
        "nl": "{mult:.2f}× op methodemix",
        "en": "{mult:.2f}× on leg blend",
    },
    "label_pedigree_unevidenced": {
        "nl": "Pedigree-claims zonder onderbouwing",
        "en": "Pedigree claims without evidence",
    },
    "label_pedigree_unevidenced_value": {
        "nl": ("{n} claim(s) niet meegenomen — voeg bewijs toe: {names}"),
        "en": ("{n} claim(s) not counted — add evidence: {names}"),
    },
    "label_legblend_baseline": {
        "nl": "Basiswaarde methodemix (vóór pedigree)",
        "en": "Leg-blend baseline (pre-pedigree)",
    },
    "label_outlier_cap_prefix": {
        "nl": "Uitschietercap",
        "en": "Outlier cap",
    },
    "label_outlier_cap_value": {
        "nl": "€{orig} → €{capped} (Tukey-fence k={k:.1f})",
        "en": "€{orig} → €{capped} (Tukey fence k={k:.1f})",
    },
    "label_sector_consistency": {
        "nl": "Sectorconsistentie",
        "en": "Sector consistency",
    },
    "label_sector_consistency_skip": {
        "nl": (
            "SaaS Forward methode niet toegepast — sector '{sector}' is "
            "geen SaaS-, fintech- of deeptech-AI-categorie met terugkerende omzet."
        ),
        "en": (
            "SaaS Forward method skipped — sector '{sector}' is not a "
            "recurring-revenue SaaS / Fintech / Deeptech-AI category."
        ),
    },
    "label_headline_basis": {
        "nl": "Basis hoofdcijfer",
        "en": "Headline basis",
    },
    "label_inception_lens": {
        "nl": "Inception-lens — {label}",
        "en": "Inception lens — {label}",
    },
    "label_lens_rationale": {
        "nl": "Onderbouwing lens",
        "en": "Lens rationale",
    },
    "label_lens_lift": {"nl": "{mult:.2f}× verhoging", "en": "{mult:.2f}× lift"},
    "label_lens_widen": {
        "nl": "±{pct:.0f}% bredere band",
        "en": "±{pct:.0f}% wider band",
    },
    "label_sector": {"nl": "Sector", "en": "Sector"},
    "label_stage": {"nl": "Stage", "en": "Stage"},
    # ------------------------------------------------------------------
    # Canonical-basis sentence (per ``canonical.basis_key`` from the
    # synthesis blender). Replaces the hardcoded NL strings the engine
    # used to ship as ``canonical.basis``. The engine still ships an EN
    # default in ``canonical.basis`` for backwards compatibility — the
    # report context overrides it with the locale match below.
    # ------------------------------------------------------------------
    "canonical_basis_blended": {
        "nl": (
            "Gewogen mediaan van de adviseursmix met 4 methoden en de "
            "oprichtersmix met 3 methoden (beide gerapporteerd in de methode-uitsplitsing)."
        ),
        "en": (
            "Blended median of the advisor 4-leg and founder 3-leg blends "
            "(both reported in the method breakdown)."
        ),
    },
    "canonical_basis_advisor_only": {
        "nl": (
            "Alleen adviseursmix met 4 methoden beschikbaar (oprichtersmix met 3 methoden "
            "leverde geen waarde)."
        ),
        "en": (
            "Only the advisor 4-leg blend is available (the founder 3-leg "
            "blend produced no value)."
        ),
    },
    "canonical_basis_founder_only": {
        "nl": (
            "Alleen oprichtersmix met 3 methoden beschikbaar (adviseursmix met 4 methoden "
            "leverde geen waarde)."
        ),
        "en": (
            "Only the founder 3-leg blend is available (the advisor 4-leg "
            "blend produced no value)."
        ),
    },
    "canonical_basis_insufficient": {
        "nl": "Onvoldoende invoer voor een verdedigbare pre-money.",
        "en": "Insufficient inputs to produce a defensible pre-money.",
    },
    # ------------------------------------------------------------------
    # Engine-sector display labels (replaces the lossy
    # ``sector.replace('_', ' ').title()`` chain that turned
    # ``biotech_healthtech`` into ``Biotech Healthtech``).
    # ------------------------------------------------------------------
    "sector_saas": {"nl": "B2B SaaS", "en": "B2B SaaS"},
    "sector_marketplace": {"nl": "Marktplaats", "en": "Marketplace"},
    "sector_fintech": {"nl": "Fintech", "en": "Fintech"},
    "sector_biotech_healthtech": {
        "nl": "Biotech / healthtech",
        "en": "Biotech / Healthtech",
    },
    "sector_deeptech_ai": {
        "nl": "Deeptech / AI",
        "en": "Deeptech / AI",
    },
    "sector_vertical_ai": {
        "nl": "Verticale AI / agentische workflow",
        "en": "Vertical AI / Agentic Workflow",
    },
    "sector_consumer": {"nl": "Consument", "en": "Consumer"},
    "sector_hardware": {"nl": "Hardware", "en": "Hardware"},
    "sector_other": {"nl": "Cross-sector", "en": "Cross-sector"},
    # ------------------------------------------------------------------
    # Berkus milestone labels — relabel the engine's English-only
    # ``BERKUS_LABELS`` per locale on the contribution table.  Without
    # this the ``main_report/pages/startup_method_breakdown.html``
    # Berkus rows show English text on every NL report.
    # ------------------------------------------------------------------
    "berkus_milestone_sound_idea": {
        "nl": "Onderbouwd idee (basiswaarde)",
        "en": "Sound idea (basic value)",
    },
    "berkus_milestone_prototype_status": {
        "nl": "Prototype (technologierisico)",
        "en": "Prototype (technology risk)",
    },
    "berkus_milestone_management_strength": {
        "nl": "Sterk managementteam (uitvoeringsrisico)",
        "en": "Quality management team (execution risk)",
    },
    "berkus_milestone_strategic_relationships": {
        "nl": "Strategische relaties (marktrisico)",
        "en": "Strategic relationships (market risk)",
    },
    "berkus_milestone_product_rollout": {
        "nl": "Productlancering / eerste verkoop (productierisico)",
        "en": "Product rollout / first sales (production risk)",
    },
    # ------------------------------------------------------------------
    # Scorecard factor labels (5-factor Upswitch variant).  Same fix as
    # the Berkus block above — the engine ships English-only
    # ``SCORECARD_LABELS`` and the breakdown table needs NL on NL reports.
    # ------------------------------------------------------------------
    "scorecard_factor_opportunity_size": {
        "nl": "Omvang van de kans",
        "en": "Size of the opportunity",
    },
    "scorecard_factor_competitive_environment": {
        "nl": "Concurrentieomgeving",
        "en": "Competitive environment",
    },
    "scorecard_factor_sales_marketing_channels": {
        "nl": "Sales-/marketingkanalen",
        "en": "Sales / marketing channels",
    },
    "scorecard_factor_need_for_additional_funding": {
        "nl": "Behoefte aan aanvullende financiering",
        "en": "Need for additional funding",
    },
    "scorecard_factor_other_factors": {
        "nl": "Overige factoren",
        "en": "Other factors",
    },
    # Executive summary additions
    "vc_oversubscribed_title": {
        "nl": "Je gevraagde ronde is groter dan wat de VC-methode rechtvaardigt",
        "en": "Your requested round exceeds what the VC method can justify",
    },
    "vc_oversubscribed_body": {
        "nl": (
            "Je vraagt <strong>€{ask}</strong> op, maar je jaar-5-projectie + "
            "exit-multiple impliceren slechts een post-money van "
            "<strong>€{post}</strong>. De VC-methode is voor deze mix op €0 "
            "gezet (zie waarderingsgrafiek). Verlaag je ronde met "
            "<strong>€{shortfall}</strong>, of verhoog je jaar-5-"
            "omzetprojectie / exit-multiple om de VC-methode weer mee te "
            "laten wegen."
        ),
        "en": (
            "You're asking for <strong>€{ask}</strong>, but your Year-5 "
            "projection × exit multiple implies a post-money of only "
            "<strong>€{post}</strong>. The VC method has been zeroed in this "
            "blend (see football field). Reduce the round by "
            "<strong>€{shortfall}</strong>, or raise your Year-5 revenue "
            "projection / exit multiple to bring the VC method back into "
            "the blend."
        ),
    },
}
