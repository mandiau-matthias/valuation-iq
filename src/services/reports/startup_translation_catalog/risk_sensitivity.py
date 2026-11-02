"""Sensitivity, risk-register, and VC walkthrough copy."""

from __future__ import annotations

STARTUP_REPORT_RISK_SENSITIVITY_TRANSLATIONS: dict[str, dict[str, str]] = {
    # Sensitivity analysis (Y5 + exit multiple ±20%)
    "sensitivity_section_title": {
        "nl": "Gevoeligheidsanalyse",
        "en": "Sensitivity analysis",
    },
    # Compact mini-grid on the exec summary (audit issue D8) — three
    # corner values from the full method-breakdown grid (worst /
    # centre / best).  Investors who only read the exec summary
    # shouldn't need to flip pages to see the headline's robustness.
    "sensitivity_mini_title": {
        "nl": "Gevoeligheid · Y5 × multiple",
        "en": "Sensitivity · Y5 × multiple",
    },
    "sensitivity_mini_caption": {
        "nl": (
            "Pre-money als beide meest-gehefboomde inputs gelijktijdig ±20% "
            "schuiven. Volledig 3×3 raster op de methode-uitsplitsing."
        ),
        "en": (
            "Pre-money if both most-leveraged inputs move ±20% in tandem. "
            "Full 3×3 grid on the method breakdown."
        ),
    },
    "sensitivity_mini_worst": {
        "nl": "Worst case (−20% / −20%)",
        "en": "Worst case (−20% / −20%)",
    },
    "sensitivity_mini_centre": {
        "nl": "Hoofdcijfer (huidige inputs)",
        "en": "Headline (current inputs)",
    },
    "sensitivity_mini_best": {
        "nl": "Best case (+20% / +20%)",
        "en": "Best case (+20% / +20%)",
    },
    "sensitivity_section_caption": {
        "nl": (
            "Hoe verschuift de pre-money als de twee gevoeligste inputs ±20% "
            "afwijken? De pre-money van het hoofdcijfer zit in het midden; de hoeken laten "
            "het worst- en best-case scenario zien."
        ),
        "en": (
            "How does the pre-money shift if the two most-leveraged inputs move "
            "±20%? The headline pre-money sits in the centre; the corners show "
            "the worst- and best-case scenarios."
        ),
    },
    "sensitivity_col_y5_low": {"nl": "Y5 −20%", "en": "Y5 −20%"},
    "sensitivity_col_y5_mid": {"nl": "Y5 (huidig)", "en": "Y5 (current)"},
    "sensitivity_col_y5_high": {"nl": "Y5 +20%", "en": "Y5 +20%"},
    "sensitivity_row_mult_low": {
        "nl": "Exit-multiple −20%",
        "en": "Exit multiple −20%",
    },
    "sensitivity_row_mult_mid": {
        "nl": "Exit-multiple (huidig)",
        "en": "Exit multiple (current)",
    },
    "sensitivity_row_mult_high": {
        "nl": "Exit-multiple +20%",
        "en": "Exit multiple +20%",
    },
    # Risk register — institutional "investor objections" page
    "risks_section_title": {
        "nl": "Risicoregister — bezwaren van investeerders",
        "en": "Risk register — investor objections",
    },
    "risks_section_caption": {
        "nl": (
            "De punten waarop investeerders je gaan toetsen, en wat de motor "
            "automatisch heeft opgemerkt.  Toon dit blad zelf vóór je "
            "investeerder ze bovenhaalt — eerlijkheid leest sterker dan "
            "verrassing."
        ),
        "en": (
            "The points investors will challenge, and what the engine flagged "
            "automatically.  Surface this page yourself before an investor "
            "raises it — pre-empted concerns read stronger than surprises."
        ),
    },
    "risks_empty_state": {
        "nl": (
            "Geen automatische signalen — de motor zag geen overvraagde "
            "ronde, geen uitschietermethode, geen sectormismatch en geen lage "
            "verdedigbaarheidsscore.  Toets je pitch wel met je adviseur."
        ),
        "en": (
            "No automatic flags — the engine saw no oversubscribed round, "
            "no outlier-capped leg, no sector mismatch, and no low "
            "defensibility score.  Still stress-test your pitch with an "
            "advisor."
        ),
    },
    "risks_severity_high": {"nl": "Hoog", "en": "High"},
    "risks_severity_medium": {"nl": "Medium", "en": "Medium"},
    "risks_severity_info": {"nl": "Info", "en": "Info"},
    "risks_col_severity": {"nl": "Risico", "en": "Severity"},
    "risks_col_title": {"nl": "Bevinding", "en": "Finding"},
    "risks_col_action": {"nl": "Actie", "en": "Action"},
    # Round-oversubscribed risk
    "risk_oversub_title": {
        "nl": "Ronde groter dan geïmpliceerde post-money",
        "en": "Round size exceeds implied post-money",
    },
    "risk_oversub_body": {
        "nl": (
            "Je vraagt €{ask} op tegen een geïmpliceerde post-money van "
            "€{post} (Y5 × multiple ÷ ROI).  De VC-methode is op €0 begrensd; "
            "het tekort is €{shortfall}."
        ),
        "en": (
            "You're asking €{ask} against an implied post-money of €{post} "
            "(Y5 × multiple ÷ ROI).  The VC leg is clamped to €0; "
            "the shortfall is €{shortfall}."
        ),
    },
    "risk_oversub_action": {
        "nl": "Verlaag de ronde, of verhoog Y5 / exit-multiple met expliciete onderbouwing.",
        "en": "Lower the round size, or raise Y5 / exit multiple with explicit evidence.",
    },
    # Outlier-cap risk — singular vs plural picked by count at call
    # site (no template engine doing the grammar, no "method(s)"
    # placeholder reading like a leaked template variable).
    "risk_outlier_title_one": {
        "nl": "1 methode buiten bandbreedte — begrensd",
        "en": "1 method outside the band — capped",
    },
    "risk_outlier_title_many": {
        "nl": "{count} methoden buiten bandbreedte — begrensd",
        "en": "{count} methods outside the band — capped",
    },
    # Legacy key — preserved for any external dashboard / monitoring
    # tool that still queries the i18n table by `risk_outlier_title`.
    "risk_outlier_title": {
        "nl": "{count} methoden buiten bandbreedte — begrensd",
        "en": "{count} methods outside the band — capped",
    },
    "risk_outlier_body": {
        "nl": (
            "Een of meer methode-uitkomsten lagen ≥ 1.5× boven de mediaan van "
            "de andere methoden (mediaan €{median}, Tukey-fence €{fence}).  "
            "De motor heeft ze begrensd zodat één optimistische methode het "
            "hoofdcijfer niet vertekent."
        ),
        "en": (
            "One or more leg outputs sat ≥ 1.5× above the median of the "
            "other legs (median €{median}, Tukey fence €{fence}).  "
            "The engine clamped them so a single optimistic leg can't "
            "skew the headline."
        ),
    },
    "risk_outlier_action": {
        "nl": "Bekijk de methode-uitsplitsing om te zien welke methode begrensd is en waarom.",
        "en": "Review the method breakdown to see which leg was capped and why.",
    },
    # Sector-mismatch risk
    "risk_sector_title": {
        "nl": "SaaS-forwardmethode uit door sectorkeuze",
        "en": "SaaS-forward leg disabled by sector choice",
    },
    "risk_sector_body": {
        "nl": (
            "Sector ‘{sector}’ is geen model met terugkerende omzet; de motor "
            "heeft de SaaS-forwardmethode overgeslagen om geen valse "
            "ARR-multiple op te leggen aan een non-SaaS verdienmodel."
        ),
        "en": (
            "Sector ‘{sector}’ isn't a recurring-revenue model; the engine "
            "skipped the SaaS-forward leg to avoid forcing an ARR multiple "
            "on a non-SaaS revenue model."
        ),
    },
    "risk_sector_action": {
        "nl": "Als je écht SaaS-achtig bent, kies dan de SaaS-sector op het Profiel-blok.",
        "en": "If you're genuinely SaaS-like, switch the sector on the Profile block.",
    },
    # Low defensibility score
    "risk_low_defs_title": {
        "nl": "Verdedigbaarheidsscore laag ({score}/10)",
        "en": "Defensibility score is low ({score}/10)",
    },
    "risk_low_defs_body": {
        "nl": (
            "De samengestelde score over coherentie, sectorconsistentie, "
            "pedigree-onderbouwing, toekomstgerichte inputs en tractie ligt onder "
            "5/10.  Investeerders gaan meerdere veronderstellingen "
            "tegelijk toetsen."
        ),
        "en": (
            "The composite score across coherence, sector consistency, "
            "pedigree evidence, forward inputs, and traction is below "
            "5/10.  Investors will challenge multiple assumptions in "
            "parallel."
        ),
    },
    "risk_low_defs_action": {
        "nl": "Vul ontbrekende mijlpalen + onderbouwingen aan in Berkus en Scorecard.",
        "en": "Backfill missing milestones + evidence on Berkus and Scorecard.",
    },
    # Active inception lens
    "risk_inception_title": {
        "nl": "Inception-lens actief ({lens})",
        "en": "Inception lens applied ({lens})",
    },
    "risk_inception_body": {
        "nl": (
            "Een optionele overlay verhoogt het middencijfer en verbreedt de variantieband — "
            "een eerlijke manier om de thesis ‘beste oprichters kosten meer’ te "
            "rapporteren.  Verwacht dat de meeste lead-VC's hier expliciet "
            "naar gaan vragen."
        ),
        "en": (
            "An opt-in overlay lifts the mid and widens the variance band — "
            "an honest way to encode the ‘best-founders-cost-more’ thesis.  "
            "Expect most lead VCs to ask about this explicitly."
        ),
    },
    "risk_inception_action": {
        "nl": "Kun je de overlay onderbouwen met momentum-/edge-bewijs? Zo niet, schakel terug naar mijlpaalgedreven.",
        "en": "Can you back the overlay with momentum / edge evidence? If not, switch back to milestones-driven.",
    },
    "sensitivity_legend": {
        "nl": (
            "Cel = pre-money implicatie als beide inputs samen schuiven, "
            "VC-formule = (Y5 × multiple ÷ doel-ROI) − ronde."
        ),
        "en": (
            "Cell = pre-money implied when both inputs shift together, "
            "VC formula = (Y5 × multiple ÷ target ROI) − round size."
        ),
    },
    "vc_section_title_template": {
        "nl": "VC-methode (terugrekenen) — €{value}",
        "en": "VC method (backsolve) — €{value}",
    },
    "vc_label_y5_revenue_projection": {
        "nl": "Jaar-5 omzetprojectie",
        "en": "Year-5 revenue projection",
    },
    "vc_extrapolated_suffix": {
        "nl": " (geëxtrapoleerd)",
        "en": " (extrapolated)",
    },
    # Promoted Y5-extrapolation disclaimer — fires when the founder
    # didn't supply Y5 directly and the engine compounded current ARR
    # forward.  Was previously a muted grey suffix on the same row as
    # the value, easily missed.  Lives next to the Y5 row as a tinted
    # callout so an investor can't read past it.  Audit issue D7.
    "vc_extrapolated_callout_label": {
        "nl": "Geëxtrapoleerd",
        "en": "Extrapolated",
    },
    "vc_extrapolated_callout_body": {
        "nl": (
            "Jaar-5-omzet werd niet door de oprichter ingevoerd — de "
            "motor heeft je huidige ARR doorgerekend met de standaard "
            "groeicurve. Vervang het cijfer met je eigen projectie als "
            "je een go-to-market plan kunt verdedigen, anders behandelen "
            "investeerders dit als een sectorgemiddelde."
        ),
        "en": (
            "Year-5 revenue was not entered by the founder — the engine "
            "compounded current ARR forward at a default growth curve. "
            "Replace this with your own projection if you can defend a "
            "go-to-market plan; otherwise investors will treat it as a "
            "sector average."
        ),
    },
    "vc_label_exit_multiple": {
        "nl": "Exit EV/omzet-multiple",
        "en": "Exit EV/Revenue multiple",
    },
    "vc_label_terminal_value": {
        "nl": "Eindwaarde",
        "en": "Terminal value",
    },
    "vc_label_roi_expectation": {
        "nl": "VC ROI-verwachting",
        "en": "VC ROI expectation",
    },
    "vc_label_post_money_today": {
        "nl": "Post-money vandaag",
        "en": "Post-money today",
    },
    "vc_label_expected_dilution_to_exit": {
        "nl": "Verwachte verwatering tot exit",
        "en": "Expected dilution to exit",
    },
    "berkus_section_title_template": {
        "nl": "Berkus methode — €{value}",
        "en": "Berkus method — €{value}",
    },
    "scorecard_section_title_template": {
        "nl": "Scorecard (Bill Payne) — €{value}",
        "en": "Scorecard (Bill Payne) — €{value}",
    },
    "saas_forward_section_title_template": {
        "nl": "SaaS-forwardmultiple — €{value}",
        "en": "SaaS forward multiple — €{value}",
    },
    # ---------------------------------------------------------------
    # VC method formula breakdown — advisory content explaining the
    # EV/Revenue chain (Y5 × multiple ÷ ROI = pre-money) line-by-line.
    # Lives on the report (method_breakdown page), NOT on the input
    # panel: the panel collects data, the report explains the method.
    # ---------------------------------------------------------------
    "vc_formula_walkthrough_title": {
        "nl": "Hoe we je cijfer berekend hebben",
        "en": "How we calculated your number",
    },
    "vc_formula_walkthrough_caption": {
        "nl": (
            "Sahlman's VC-methode (1987): de exit-waarde wordt teruggediscountteerd "
            "naar vandaag aan de hand van de doel-ROI van de investeerder. Drie "
            "inputs sturen het hele rapport — wijzig één en het kopcijfer beweegt mee."
        ),
        "en": (
            "Sahlman's VC method (1987): the exit value is discounted back to today "
            "using the investor's target ROI. Three inputs drive the whole report — "
            "change one and the headline moves with it."
        ),
    },
    "vc_formula_row_y5": {
        "nl": "Jaar-5 omzet",
        "en": "Year-5 revenue",
    },
    "vc_formula_row_multiply": {
        "nl": "× Exit EV/Omzet-multiple",
        "en": "× Exit EV/Revenue multiple",
    },
    "vc_formula_row_exit_value": {
        "nl": "= Exit-ondernemingswaarde",
        "en": "= Exit enterprise value",
    },
    "vc_formula_row_divide_roi": {
        "nl": "÷ Doel-ROI investeerder",
        "en": "÷ Investor target ROI",
    },
    "vc_formula_row_pre_money": {
        "nl": "= Pre-money vandaag",
        "en": "= Today's pre-money",
    },
}
