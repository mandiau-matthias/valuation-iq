"""Overview, cap-table, advisory, and defensibility report copy."""

from __future__ import annotations

STARTUP_REPORT_OVERVIEW_TRANSLATIONS: dict[str, dict[str, str]] = {
    # Hero / executive summary
    "indicative_pre_money": {
        "nl": "Indicatieve pre-money (gewogen)",
        "en": "Indicative pre-money (blended)",
    },
    "indicative_pre_money_valuation": {
        "nl": "Indicatieve pre-money waardering",
        "en": "Indicative pre-money valuation",
    },
    "cover_pre_money_label": {
        "nl": "Pre-money aandelenwaarde",
        "en": "Pre-money equity value",
    },
    "cover_pre_money_methodology": {
        "nl": "Startup-methodemix",
        "en": "Startup method blend",
    },
    "range": {"nl": "Bandbreedte", "en": "Range"},
    "method_mix": {"nl": "Methodemix", "en": "Method mix"},
    "method_mix_founder": {
        "nl": "Methodemix (oprichterstriangulatie)",
        "en": "Method mix (founder triangulation)",
    },
    "pre_money_triangulation": {
        "nl": "Pre-money triangulatie",
        "en": "Pre-money triangulation",
    },
    "pre_money_valuation_section": {
        "nl": "Pre-money waardering",
        "en": "Pre-money valuation",
    },
    "fundraising_one_pager": {
        "nl": "Fondsenwerving one-pager",
        "en": "Fundraising one-pager",
    },
    # Method-family label.  The panel brands this method as "EV/Revenue
    # valuation"; the report needs to say so on the cover so M&A readers
    # can identify the engine at a glance.  Used in the badge slot on
    # the one-pager and the executive summary.
    "method_family_ev_revenue": {
        "nl": "Methode: EV/Omzet-triangulatie",
        "en": "Method: EV/Revenue triangulation",
    },
    # B3 — section badge "Startup Valuation · Pre-seed".  The previous
    # template literal ("Startup Valuation · ...") was English-only;
    # NL founders saw the English string on what's otherwise a fully
    # NL exec summary.  The pipe between the family label and the stage
    # is intentional — the template renders ``{{ x }} · {{ stage_display }}``.
    "section_badge_startup": {
        "nl": "Startup-waardering",
        "en": "Startup valuation",
    },
    # Stage display labels — replaces the lossy ``replace('_', ' ')|title``
    # pattern that produced "Pre Seed" / "Series A" without the canonical
    # hyphen.  Keys mirror :class:`StartupStage` exactly.
    "stage_pre_seed": {"nl": "Pre-seed", "en": "Pre-seed"},
    "stage_seed": {"nl": "Seed", "en": "Seed"},
    "stage_series_a": {"nl": "Series A", "en": "Series A"},
    # Method labels (fallback when canonical key isn't matched)
    "method_berkus": {"nl": "Berkus methode", "en": "Berkus method"},
    "method_scorecard": {"nl": "Scorecard", "en": "Scorecard"},
    "method_scorecard_payne": {
        "nl": "Scorecard (Bill Payne)",
        "en": "Scorecard (Bill Payne)",
    },
    "method_vc": {
        "nl": "Venture Capital methode",
        "en": "Venture Capital method",
    },
    "method_saas_forward": {
        "nl": "SaaS-forwardmultiple",
        "en": "SaaS forward multiple",
    },
    "method_saas_forward_short": {
        "nl": "SaaS-forwardmult.",
        "en": "SaaS forward mult.",
    },
    # Founder-supplied evidence + pitch surfaces (Studio v2)
    "founder_pitch_label": {
        "nl": "Pitch van de oprichter",
        "en": "Founder's pitch",
    },
    "exit_multiple_rationale_label": {
        "nl": "Onderbouwing exit-multiple",
        "en": "Exit-multiple rationale",
    },
    "founder_evidence_label": {
        "nl": "Onderbouwing van de oprichter",
        "en": "Founder's evidence",
    },
    # Methodemix footnote
    "method_mix_footnote": {
        "nl": (
            "Scorecard staat als controle onder verdedigbaarheid — de "
            "triangulatie boven de waarderingsgrafiek gebruikt de drie "
            "consortiummethoden (Berkus, SaaS-forward, VC-methode)."
        ),
        "en": (
            "Scorecard is shown as a sanity-check under defensibility — "
            "the triangulation above the football field uses the three "
            "consortium legs (Berkus, SaaS forward, VC method)."
        ),
    },
    # Football field
    "football_field": {"nl": "Waarderingsgrafiek", "en": "Football field"},
    "football_field_caption": {
        "nl": (
            "Drie oprichtersmethoden op één schaal. De gearceerde band toont de "
            "gewogen bandbreedte; de stippellijn markeert de gewogen "
            "pre-money (€{mid})."
        ),
        "en": (
            "Three founder legs on a single axis. The shaded band shows "
            "the blended range; the dashed line marks the blended "
            "pre-money (€{mid})."
        ),
    },
    # Subhead pinning the chart's lens.  The one-pager renders the
    # 3-leg founder triangulation; the executive summary renders the
    # 4-leg advisor blend.  Without this label readers wondered "where
    # is Scorecard?" on the one-pager — the chart looked like it was
    # missing data when in fact it was rendering the founder view by
    # design.  Audit issue D2.
    "football_field_lens_founder": {
        "nl": "Oprichterstriangulatie · 3 methoden (Berkus + SaaS-forward + VC)",
        "en": "Founder triangulation · 3 legs (Berkus + SaaS Forward + VC)",
    },
    "football_field_lens_advisor": {
        "nl": "Adviseursmix · 4 methoden (Berkus + Scorecard + VC + SaaS-forward)",
        "en": "Advisor blend · 4 legs (Berkus + Scorecard + VC + SaaS Forward)",
    },
    "not_available": {"nl": "— niet beschikbaar", "en": "— not available"},
    "blend": {"nl": "Mix", "en": "Blend"},
    "football_field_aria": {
        "nl": "Waarderingsgrafiek — pre-money triangulatie per methode",
        "en": "Football field — pre-money triangulation per method",
    },
    # Cap-table simulator
    "cap_table_simulator": {
        "nl": "Participatietabelsimulator",
        "en": "Cap-table simulator",
    },
    "cap_table_simulator_ask": {
        "nl": (
            "Bij een ronde van <strong>€{amount}</strong> tegen een "
            "pre-money van <strong>€{pre}</strong> verwater je "
            "<strong>{dilution}%</strong> van je aandelen."
        ),
        "en": (
            "Raising <strong>€{amount}</strong> at a pre-money of "
            "<strong>€{pre}</strong> dilutes founders by "
            "<strong>{dilution}%</strong>."
        ),
    },
    "cap_table_simulator_proxy": {
        "nl": (
            "Op basis van je vorige ronde-grootte van <strong>€{amount}</strong>: "
            "een ronde tegen een pre-money van <strong>€{pre}</strong> komt "
            "overeen met <strong>{dilution}%</strong> verwatering."
        ),
        "en": (
            "Based on your last round size of <strong>€{amount}</strong>: "
            "a round at a pre-money of <strong>€{pre}</strong> implies "
            "<strong>{dilution}%</strong> dilution."
        ),
    },
    "based_on_last_round": {
        "nl": "(o.b.v. vorige ronde)",
        "en": "(based on last round)",
    },
    "pre_money": {"nl": "Pre-money", "en": "Pre-money"},
    "pre_money_valuation": {
        "nl": "Pre-moneywaardering",
        "en": "Pre-money valuation",
    },
    "plus_round_to_raise": {
        "nl": "+ Op te halen ronde",
        "en": "+ Round being raised",
    },
    "equals_post_money": {"nl": "= Post-money", "en": "= Post-money"},
    "post_money": {"nl": "Post-money", "en": "Post-money"},
    "option_pool_drag": {"nl": "Optiepool-effect", "en": "Option pool drag"},
    "safe_conversion_drag": {
        "nl": "SAFE-conversie-effect",
        "en": "SAFE conversion drag",
    },
    "founder_dilution": {
        "nl": "Verwatering oprichters",
        "en": "Founder dilution",
    },
    "cap_table_empty": {
        "nl": (
            "Vul een <em>op te halen ronde</em> in om de verwatering te "
            "zien — dit blok verschijnt automatisch zodra je dat doet."
        ),
        "en": (
            "Enter a <em>round being raised</em> to see your dilution — "
            "this block appears automatically once you do."
        ),
    },
    # Cap-table page
    "cap_table_and_dilution": {
        "nl": "Participatietabel & verwatering",
        "en": "Cap table & dilution",
    },
    "cap_table_summary": {
        "nl": "Samenvatting participatietabel",
        "en": "Cap table summary",
    },
    "next_round_pre_money_target": {
        "nl": "Doel pre-money volgende ronde",
        "en": "Next round pre-money target",
    },
    "option_pool_reserved": {
        "nl": "Optiepool (gereserveerd)",
        "en": "Option pool (reserved)",
    },
    "last_round_amount": {
        "nl": "Laatste ronde — bedrag",
        "en": "Last round — amount",
    },
    "last_round_post_money": {
        "nl": "Laatste ronde — post-money",
        "en": "Last round — post-money",
    },
    "last_round_date": {
        "nl": "Laatste ronde — datum",
        "en": "Last round — date",
    },
    "safe_notes_and_convertibles": {
        "nl": "SAFE-notes & converteerbare leningen",
        "en": "SAFE notes & convertibles",
    },
    "holder": {"nl": "Houder", "en": "Holder"},
    "amount": {"nl": "Bedrag", "en": "Amount"},
    "discount": {"nl": "Korting", "en": "Discount"},
    "cap": {"nl": "Plafond", "en": "Cap"},
    "total": {"nl": "Totaal", "en": "Total"},
    "next_round_dilution_scenario": {
        "nl": "Verwateringsscenario volgende ronde",
        "en": "Next round dilution scenario",
    },
    "indicative_dilution_caption": {
        "nl": ("Indicatieve verwatering door SAFE-conversies en de " "gereserveerde optiepool."),
        "en": ("Indicative dilution from SAFE conversions and the reserved " "option pool."),
    },
    "expected_post_money_with_safes": {
        "nl": "Verwacht post-money (incl. SAFEs)",
        "en": "Expected post-money (incl. SAFEs)",
    },
    "safe_dilution": {
        "nl": "Verwatering door SAFEs",
        "en": "SAFE dilution",
    },
    "option_pool": {"nl": "Optiepool", "en": "Option pool"},
    # NOTE: the underlying number is pool % + SAFE-conversion drag —
    # the legacy `dilution_scenario` block deliberately EXCLUDES the
    # new-investor stake (covered by the cap-table simulator card +
    # the dilution scenarios table). Label scoped explicitly so an
    # angel reading "Total founder dilution 10%" doesn't conclude
    # founders only give up 10% — they give up 28% including the
    # new investor. The new `dilution_scenarios` table below carries
    # the full figure. Audit 2026-05-19.
    "total_founder_dilution": {
        "nl": "Pool + SAFE-effect (excl. nieuwe investeerder)",
        "en": "Pool + SAFE drag (excl. new investor)",
    },
    # Dilution scenarios — labels + a one-line "why this lever" hint.
    # Rendered as a 4-row negotiation table on the cap-table page so
    # every founder sees what their headline dilution moves to under
    # the standard 3 negotiation levers, instead of treating the
    # cap-table simulator's single point as a fait accompli.
    "dilution_scenarios_title": {
        "nl": "Verwateringsscenario's — onderhandelingsruimte",
        "en": "Dilution scenarios — negotiation room",
    },
    "dilution_scenarios_caption": {
        "nl": (
            "Hetzelfde model met drie standaard hefbomen. P75 is "
            "het bovenste kwartiel van de canonieke band — daar komt een "
            "lead-investeerder die jouw sector kent vaak op uit."
        ),
        "en": (
            "The same model under three standard negotiation levers. "
            "P75 is the top quartile of the canonical band — where a "
            "lead investor familiar with your sector typically prices."
        ),
    },
    "scenario_label_current": {
        "nl": "Huidig — zoals je het hebt ingegeven",
        "en": "Current — as entered",
    },
    "scenario_label_lead_at_p75": {
        "nl": "Lead-investeerder prijst op P75 van de band",
        "en": "Lead prices at P75 of the band",
    },
    "scenario_label_smaller_pool": {
        "nl": "5% optiepool i.p.v. 10% (aanvulling bij Seed)",
        "en": "5% option pool instead of 10% (top up at Seed)",
    },
    "scenario_label_smaller_round": {
        "nl": "Kleinere ronde (−25%)",
        "en": "Smaller round (−25%)",
    },
    "scenario_col_pre_money": {"nl": "Pre-money", "en": "Pre-money"},
    "scenario_col_raise": {"nl": "Op te halen bedrag", "en": "Raise"},
    "scenario_col_pool": {"nl": "Pool", "en": "Pool"},
    "scenario_col_new_investor": {"nl": "Nieuwe investeerder", "en": "New investor"},
    "scenario_col_founders_remaining": {
        "nl": "Oprichters blijven",
        "en": "Founders remaining",
    },
    # Share-distribution bar (visual cap-table split rendered above
    # the simulator table on the one-pager and the cap-table page).
    # Mirrors the wizard's RoundSimulatorStep bar so the founder sees
    # the same picture in Venus and on the angel-facing PDF.
    "share_distribution_title": {
        "nl": "Aandeelverdeling — deze geprijsde ronde",
        "en": "Share distribution — this priced close",
    },
    "founders": {"nl": "Oprichters", "en": "Founders"},
    "new_investor": {"nl": "Nieuwe investeerder", "en": "New investor"},
    "safe_converters": {
        "nl": "SAFE-converteerders",
        "en": "SAFE converters",
    },
    # Cap-table founder-floor advisory. Surfaced when this priced
    # close lands founders below ~30% — the empirical floor most
    # seed/Series-A VCs need to underwrite a next round (a board
    # seat at 28% founder ownership is much harder to support).
    # Title / body / action are rendered as a 3-line block on the
    # cap-table page so the founder sees the deal-readiness
    # consequence next to the dilution number itself. Same advisory
    # used to live in the Venus left panel; relocated here on
    # 2026-05-10 to keep the input panel input-only.
    "founder_floor_advisory_title": {
        "nl": "Oprichters onder de ~30%-vloer",
        "en": "Founders below the ~30% floor",
    },
    "founder_floor_advisory_body": {
        "nl": (
            "Bij deze geprijsde closing houden oprichters ~{foundersPct}% van het "
            "bedrijf — onder de ~30%-vloer die de meeste seed- en Series-A-fondsen "
            "willen zien om de volgende ronde te kunnen onderschrijven. Een "
            "bestuurszetel verdedigen op 28% oprichtersbelang is materieel "
            "moeilijker."
        ),
        "en": (
            "At this priced close founders end up holding ~{foundersPct}% of the "
            "company — below the ~30% floor most seed and Series-A funds want "
            "to see before they can underwrite the next round. Defending a "
            "board seat at 28% founder ownership is materially harder."
        ),
    },
    # Inception-lens recommendation block — surfaces "your profile
    # fits the Inception-bet / Momentum-driven lens" as analytical
    # advisory in the advisor-CTA partial. Same logic that briefly
    # lived in the Venus useStudioIssues nudge surface; relocated
    # here on 2026-05-10 to keep the input panel input-only. Two
    # variants share copy keys; the template branches on the
    # `kind` field of the advisory dict.
    "inception_lens_advisory_bet_title": {
        "nl": "Profiel past bij de Inception-bet-lens",
        "en": "Profile fits the Inception-bet lens",
    },
    "inception_lens_advisory_bet_body": {
        "nl": (
            "Pre-seed + deeptech / biotech + sterke pedigree + nog geen omzet "
            "is exact het profiel waar de standaardmix Berkus + Scorecard + VC "
            "structureel onder waardeert. De Inception-bet overlay tilt het "
            "middencijfer met +25% én verbreedt de bandbreedte om de hogere "
            "variantie eerlijk te rapporteren — geen valse precisie."
        ),
        "en": (
            "Pre-seed + deeptech / biotech + credentialed pedigree + no revenue "
            "is exactly the profile where the standard Berkus + Scorecard + VC "
            "blend systematically under-prices. The Inception-bet overlay lifts "
            "the mid +25% AND widens the band to honestly report the higher "
            "variance — no false precision."
        ),
    },
    "inception_lens_advisory_momentum_title": {
        "nl": "Profiel past bij de momentumgedreven lens",
        "en": "Profile fits the Momentum-driven lens",
    },
    "inception_lens_advisory_momentum_body": {
        "nl": (
            '"Pre-seed wordt gewonnen door momentum, niet door moats." '
            "Uitzonderlijke teamsterkte + actieve strategische partnerships + "
            "nog geen omzet is exact het empirische patroon dat de momentumlens "
            "corrigeert: +10% middencijfer, ±15% bredere band."
        ),
        "en": (
            '"Pre-seed is won by momentum, not moats." Exceptional management '
            "strength + active strategic relationships + no revenue yet is the "
            "empirical pattern the Momentum lens corrects for: +10% mid, ±15% "
            "wider band."
        ),
    },
    "inception_lens_advisory_action": {
        "nl": (
            "Een adviseur kan de overlay aanzetten voor een gecertificeerde "
            "herberekening; het canonieke cijfer in dit rapport blijft mijlpaalgedreven "
            "(de neutrale basislijn) tot dat moment."
        ),
        "en": (
            "An advisor can flip the overlay on for a certified re-run; the "
            "canonical number in this report stays milestones-driven (the "
            "neutral baseline) until then."
        ),
    },
    "founder_floor_advisory_action": {
        "nl": (
            "Drie hefbomen: (1) verlaag de optiepool als die boven ~12% zit, "
            "(2) verlaag het op te halen bedrag, of (3) duw de pre-money omhoog "
            "via een sterker investeerdersdeck (Y5-omzet, exit-multiple, of risico-"
            "reductiemijlpalen)."
        ),
        "en": (
            "Three levers: (1) lower the option pool if it sits above ~12%, "
            "(2) lower the round size, or (3) push pre-money up via a stronger "
            "investor deck (Y5 revenue, exit multiple, or risk-reduction "
            "milestones)."
        ),
    },
    # Defensibility / one-pager extras
    "defensibility_score_label": {
        "nl": "Verdedigbaarheidsscore",
        "en": "Defensibility score",
    },
    "defensibility_assumptions": {
        "nl": "Verdedigbaarheid — kernveronderstellingen",
        "en": "Defensibility — key assumptions",
    },
    # Composite-score caption rendered next to the score chip on the
    # founder one-pager and the executive summary.  Replaced four
    # hardcoded ``{% if locale == 'en' %}`` blocks in the PDF templates;
    # keeping the copy in the translation table is the single source of
    # truth so future edits never have to touch templates.
    "defensibility_score_caption": {
        "nl": (
            "Composiet-score over coherentie, sector-consistentie, "
            "pedigree-onderbouwing, toekomstgerichte inputs en tractie. Volledige "
            "uitsplitsing op de managementsamenvatting."
        ),
        "en": (
            "Composite score across coherence, sector consistency, "
            "pedigree evidence, forward inputs and traction. Full "
            "breakdown on the executive summary."
        ),
    },
    # Title for the in-page table that lists the 5 sub-factor scores
    # (B7 — surface the breakdown the engine already computes but the
    # report never rendered).
    "defensibility_breakdown_title": {
        "nl": "Verdedigbaarheid — uitsplitsing per factor",
        "en": "Defensibility — factor breakdown",
    },
    "defensibility_breakdown_caption": {
        "nl": (
            "Vijf gewogen factoren die de samengestelde verdedigbaarheidsscore "
            "bepalen. Een lage score op één factor versmalt de onderhandelings"
            "ruimte; gebruik de onderbouwingskolom als checklist voor het eerste "
            "investeerdersgesprek."
        ),
        "en": (
            "Five weighted factors that determine the composite "
            "defensibility score. A low score on any single factor "
            "narrows your negotiating room — use the rationale column as a "
            "checklist for the first investor call."
        ),
    },
    "defensibility_factor_col": {
        "nl": "Factor",
        "en": "Factor",
    },
    "defensibility_factor_score_col": {
        "nl": "Score",
        "en": "Score",
    },
    # B14 — investor-expected anchor column added to the defensibility
    # breakdown so a reader auditing the score has a comparison
    # benchmark instead of an opaque "7/10".  Labelled "Investor
    # expected" rather than "Sector median" because the value is the
    # consortium-defensibility threshold (7/10) the engine already
    # uses internally — not a per-sector cohort statistic (we'd need
    # an Athena cohort for that).
    "defensibility_factor_sector_median_col": {
        "nl": "Verwacht (investeerder)",
        "en": "Investor expected",
    },
    "defensibility_factor_rationale_col": {
        "nl": "Onderbouwing",
        "en": "Rationale",
    },
    # Localized labels for the 5 canonical defensibility factors. The
    # engine emits NL-only labels by default (defensibility.py), so we
    # override per locale in the report context (see overrides_for_loc
    # below).
    "defensibility_factor_headline_coherence": {
        "nl": "Coherentie van de methoden",
        "en": "Method coherence",
    },
    "defensibility_factor_sector_consistency": {
        "nl": "Sector ↔ methode-consistentie",
        "en": "Sector ↔ method consistency",
    },
    "defensibility_factor_pedigree_evidence": {
        "nl": "Onderbouwing oprichtersprofiel",
        "en": "Founder pedigree evidence",
    },
    "defensibility_factor_forward_inputs": {
        "nl": "Toekomstgerichte inputs (Y5, multiple, ROI)",
        "en": "Forward inputs (Y5, multiple, ROI)",
    },
    "defensibility_factor_traction_signal": {
        "nl": "Tractie-signaal (MRR / ARR)",
        "en": "Traction signal (MRR / ARR)",
    },
    # Canonical-headline explainer rendered under the headline pre-money
    # number on the PDF one-pager. Replaced an inline locale conditional.
    "canonical_headline_explainer": {
        "nl": (
            "Het canonieke hoofdcijfer is de mediaan van de adviseursmix met 4 methoden "
            "en de oprichtersmix met 3 methoden."
        ),
        "en": (
            "The canonical headline is the median of the advisor 4-leg "
            "and the founder 3-leg blends."
        ),
    },
}
