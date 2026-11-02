"""Structured defensibility warnings.

The existing :mod:`classifier` returns ``engine_signals: list[str]`` — free
text, no severity, no remediation, no machine-readable code. That is fine
for the banner (which wants prose) but not enough to:

  * decide whether a warning blocks Submit or just paints amber,
  * pipe a warning into a triage queue for the accountant,
  * tell the user *what to do* about each warning.

This module typifies the warnings: every one carries a stable
``code`` (machine-readable, never translated), a ``severity``, NL+EN
``message`` text, and a ``remediation`` field with the user-actionable
fix. Warnings are emitted by the same conditions :mod:`classifier` checks
for ``engine_signals`` — we deliberately do **not** duplicate that
detection logic here; instead the report builder re-emits each engine
signal as a structured warning by mapping its detection condition to a
known code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, TypeAlias

from src.services.defensibility.methodology import Methodology
from src.services.defensibility.warning_signal_detection import (
    _balance_sheet_missing,
    _dcf_forecast_warnings_by_type,
    _engine_warnings_by_key,
    _generic_multiple_fallback,
    _industry_margin_deviation_raw,
    _methodology_downgrade,
    _owner_normalization_zero,
    _owner_profile_cap_bound,
    _owner_profile_skipped,
    _safe_decimal,
    resolve_years_of_data,
    _saas_validation_buckets,
    _synthetic_percentiles,
    _thin_historical,
)
from src.services.infrastructure.translations import normalize_report_locale

JsonMap: TypeAlias = dict[str, object]


class WarningSeverity(Enum):
    """Severity ladder. CRITICAL is the only level that triggers Submit
    BLOCK_SOFT; HIGH paints the cover chip red but lets Submit proceed."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Warning codes — machine-readable, stable across translations and edits.
# Add new codes here; renaming an existing one is a breaking telemetry
# change. Each code corresponds to exactly one detection in the classifier.
WARNING_CODES = {
    "BALANCE_SHEET_MISSING": WarningSeverity.MEDIUM,
    "OWNER_NORMALIZATION_ZERO": WarningSeverity.HIGH,
    "OWNER_PROFILE_SKIPPED": WarningSeverity.MEDIUM,
    "OWNER_PROFILE_CAP_BOUND": WarningSeverity.MEDIUM,
    "INDUSTRY_MARGIN_DEVIATION": WarningSeverity.MEDIUM,
    "THIN_HISTORICAL_DATA": WarningSeverity.HIGH,
    "SYNTHETIC_PERCENTILES": WarningSeverity.LOW,
    "METHODOLOGY_DOWNGRADE": WarningSeverity.LOW,
    "GENERIC_MULTIPLE_FALLBACK": WarningSeverity.CRITICAL,
    # Aggregator engine_warnings (formerly free-text in the legacy banner).
    "EV_FORMULA_MISMATCH": WarningSeverity.MEDIUM,
    "EV_BRIDGE_SUPPRESSED_NO_BALANCE": WarningSeverity.INFO,
    "NET_DEBT_DERIVED_FROM_GAP": WarningSeverity.MEDIUM,
    # SaaS / ARR validation surface (collapsed to two codes; one warning row
    # per severity bucket so the Co-pilot rail isn't flooded with one row
    # per field. Field-level details ride along in `impact`).
    "SAAS_INPUT_VALIDATION_ERROR": WarningSeverity.HIGH,
    "SAAS_INPUT_VALIDATION_WARNING": WarningSeverity.MEDIUM,
    # DCF forecast assumption warnings — promoted from
    # `dcf_valuation.data_quality_warnings`.
    "DCF_LIMITED_HISTORICAL_DATA": WarningSeverity.MEDIUM,
    "DCF_FORECAST_MARGIN_EXPANSION": WarningSeverity.HIGH,
    "DCF_FORECAST_GROWTH_ACCELERATION": WarningSeverity.MEDIUM,
    "DCF_TERMINAL_VALUE_CONCENTRATION": WarningSeverity.MEDIUM,
    "DCF_WACC_CEILING_CLAMP": WarningSeverity.HIGH,
}


@dataclass(frozen=True)
class DefensibilityWarning:
    """One typed warning with the user-actionable fix.

    Frozen: passed through the report renderer; immutability prevents
    "remediation drift" between the cover chip and the warning detail card.
    """

    code: str  # Stable, machine-readable, all caps with underscores.
    severity: WarningSeverity
    message_en: str
    message_nl: str
    remediation_en: str
    remediation_nl: str
    impact: Optional[str] = None  # Free text on what changes if the user fixes this
    message_fr: Optional[str] = None
    remediation_fr: Optional[str] = None

    def message(self, locale: str = "nl") -> str:
        language = normalize_report_locale(locale)
        if language == "fr":
            return self.message_fr or self.message_en
        return self.message_nl if language == "nl" else self.message_en

    def remediation(self, locale: str = "nl") -> str:
        language = normalize_report_locale(locale)
        if language == "fr":
            return self.remediation_fr or self.remediation_en
        return self.remediation_nl if language == "nl" else self.remediation_en


# ---------------------------------------------------------------------------
# Detection — mirrors the conditions in classifier.py so the engine_signals
# list and the structured warnings list cannot disagree. New condition
# added to either side must be mirrored on the other.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Builders for typed warnings — text is i18n-ready, codes are stable.
# ---------------------------------------------------------------------------


def _w_balance_sheet_missing() -> DefensibilityWarning:
    return DefensibilityWarning(
        code="BALANCE_SHEET_MISSING",
        severity=WARNING_CODES["BALANCE_SHEET_MISSING"],
        message_en=(
            "No balance sheet data provided — net debt assumed to be zero; "
            "working capital and cash flow adjustments at handover must be "
            "determined separately."
        ),
        message_nl=(
            "Geen balansgegevens verstrekt — netto-schuld 0 verondersteld; "
            "werkkapitaal- en kasstroomcorrecties bij overdracht moeten "
            "afzonderlijk worden vastgesteld."
        ),
        remediation_en=(
            "Provide cash, total debt, and current liabilities from the latest "
            "balance sheet to enable a proper net-debt bridge."
        ),
        remediation_nl=(
            "Verstrek kas, totale schulden en kortlopende verplichtingen uit "
            "de meest recente balans voor een correcte netto-schuld bridge."
        ),
        impact="Closes the EV→Equity bridge gap (Step 7); +1 academic point.",
        message_fr="Aucune donnée de bilan fournie : la dette nette est supposée nulle. Les ajustements de fonds de roulement et de trésorerie au transfert doivent être déterminés séparément.",
        remediation_fr="Renseignez la trésorerie, la dette totale et les passifs courants du dernier bilan pour établir le passage de la valeur d’entreprise à celle des capitaux propres.",
    )


def _w_owner_normalization_zero() -> DefensibilityWarning:
    return DefensibilityWarning(
        code="OWNER_NORMALIZATION_ZERO",
        severity=WARNING_CODES["OWNER_NORMALIZATION_ZERO"],
        message_en=(
            "No normalised EBITDA adjustments entered for an owner-led business. "
            "Market-rate owner compensation and one-time items must be manually "
            "confirmed before external distribution."
        ),
        message_nl=(
            "Geen genormaliseerde EBITDA-aanpassingen ingevoerd voor een "
            "eigenaar-geleide onderneming. Marktconforme eigenaarsvergoeding en "
            "eenmalige posten dienen handmatig te worden bevestigd vóór externe "
            "distributie."
        ),
        remediation_en=(
            "Enter market-rate owner compensation and any non-recurring expenses "
            "in the EBITDA normalisation section."
        ),
        remediation_nl=(
            "Voer marktconforme eigenaarsvergoeding en eenmalige posten in onder "
            "EBITDA-normalisatie."
        ),
        impact="Increases reported EBITDA toward economic truth; typically +5-25% on the band.",
        message_fr="Aucun ajustement d’EBITDA normalisé n’a été saisi pour cette entreprise dirigée par son propriétaire. La rémunération de marché du dirigeant et les éléments non récurrents doivent être confirmés avant toute diffusion externe.",
        remediation_fr="Renseignez la rémunération de marché du dirigeant et les charges non récurrentes dans la section de normalisation de l’EBITDA.",
    )


def _w_owner_profile_skipped() -> DefensibilityWarning:
    return DefensibilityWarning(
        code="OWNER_PROFILE_SKIPPED",
        severity=WARNING_CODES["OWNER_PROFILE_SKIPPED"],
        message_en=(
            "Owner Profile not completed — equity adjustment defaulted to 0%; "
            "transferability risk has not been quantified for this report."
        ),
        message_nl=(
            "Eigenaarsprofiel niet ingevuld — aandelenwaarde-aanpassing ingesteld op 0%; "
            "overdraagbaarheidsrisico is voor dit rapport niet gekwantificeerd."
        ),
        remediation_en=(
            "Complete the 12-factor Owner Profile to quantify transferability "
            "risk and unlock the structured equity adjustment."
        ),
        remediation_nl=(
            "Vul het 12-factor Eigenaarsprofiel in om overdraagbaarheidsrisico "
            "te kwantificeren en de gestructureerde aandelenwaarde-aanpassing te activeren."
        ),
        impact="Surfaces transferability risk; affects the equity adjustment and confidence chip.",
        message_fr="Le profil du dirigeant n’a pas été renseigné : l’ajustement des capitaux propres est fixé à 0 %. Le risque de transférabilité n’a pas été quantifié pour ce rapport.",
        remediation_fr="Complétez les 12 facteurs du profil du dirigeant pour quantifier le risque de transférabilité et activer l’ajustement des capitaux propres.",
    )


def _w_owner_profile_cap_bound(valuation_data: JsonMap) -> DefensibilityWarning:
    odr = valuation_data.get("owner_dependency_result") or {}
    risk = (odr.get("risk_level") or "HIGH").strip().upper()
    risk_fr = {"LOW": "faible", "MEDIUM": "modérée", "HIGH": "élevée", "CRITICAL": "critique"}.get(
        risk, risk
    )
    cap_pct = abs(int(round(float(_safe_decimal(odr.get("valuation_adjustment"))) * 100)))
    raw_pct = abs(int(round(float(_safe_decimal(odr.get("raw_adjustment"))) * 100)))
    return DefensibilityWarning(
        code="OWNER_PROFILE_CAP_BOUND",
        severity=WARNING_CODES["OWNER_PROFILE_CAP_BOUND"],
        message_en=(
            f"Owner Profiling: {risk} dependency, {cap_pct}% MVP cap applied "
            f"(uncapped engine signal {raw_pct}%). Validate with an advisor "
            "before external use."
        ),
        message_nl=(
            f"Owner Profiling: {risk} afhankelijkheid, MVP-cap van {cap_pct}% "
            f"toegepast (ongekapt motorsignaal {raw_pct}%). Laat valideren door "
            "een adviseur vóór extern gebruik."
        ),
        remediation_en=(
            "Engage an advisor to validate the underlying transferability "
            "assessment before pricing decisions."
        ),
        remediation_nl=(
            "Schakel een adviseur in om de onderliggende overdraagbaarheidsbeoordeling "
            "te valideren voor prijsbeslissingen."
        ),
        impact="Gap between engine signal and applied cap is the discount the MVP currently absorbs.",
        message_fr=f"Profil du dirigeant : dépendance {risk_fr}, plafond de {cap_pct} % appliqué (signal du modèle avant plafonnement : {raw_pct} %). Faites valider cette évaluation par un conseiller avant tout usage externe.",
        remediation_fr="Faites valider l’évaluation de la transférabilité par un conseiller avant toute décision de prix.",
    )


def _w_thin_historical(valuation_data: JsonMap) -> DefensibilityWarning:
    # Same resolver the gate predicate uses, so the number in the message can
    # never disagree with the number that decided to show it. This used to be a
    # third private copy of the extraction and it under-reported the same way.
    years = resolve_years_of_data(valuation_data)
    return DefensibilityWarning(
        code="THIN_HISTORICAL_DATA",
        severity=WARNING_CODES["THIN_HISTORICAL_DATA"],
        message_en=(
            f"{years} year(s) of historical data — Big-4 reviewers expect ≥3 "
            "for a defensible market-multiples report."
        ),
        message_nl=(
            f"{years} jaar historische data — Big-4 reviewers verwachten ≥3 "
            "voor een verdedigbaar multiples-rapport."
        ),
        remediation_en=(
            "Add at least 3 years of historical financials. Two years gives "
            "partial credit; one year scores zero on this pillar."
        ),
        remediation_nl=(
            "Voeg minimaal 3 jaar historische cijfers toe. Twee jaar levert "
            "gedeeltelijke punten; één jaar scoort nul op deze pijler."
        ),
        impact="+1 academic point at 2 years, +2 at 3+ years.",
        message_fr=f"{years} année(s) de données historiques : les réviseurs Big Four attendent au moins 3 années pour étayer un rapport fondé sur les multiples de marché.",
        remediation_fr="Ajoutez au moins 3 années de données financières historiques. Deux années donnent un crédit partiel ; une seule année ne rapporte aucun point pour ce critère.",
    )


def _w_synthetic_percentiles() -> DefensibilityWarning:
    return DefensibilityWarning(
        code="SYNTHETIC_PERCENTILES",
        severity=WARNING_CODES["SYNTHETIC_PERCENTILES"],
        message_en=(
            "Multiple percentiles synthesized as ±20% around the median — real "
            "p25/p75 from comparable transactions were not available for this cell."
        ),
        message_nl=(
            "Multiple-percentielen gesynthetiseerd als ±20% rond de mediaan — "
            "echte p25/p75 uit vergelijkbare transacties waren niet beschikbaar "
            "voor deze cel."
        ),
        remediation_en=(
            "Coverage gap; cannot be fixed at request time. Track via the "
            "Upswitch Index corpus expansion programme."
        ),
        remediation_nl=(
            "Dekkingsgat; niet te verhelpen bij dit rapport. Volg via het "
            "Upswitch Index corpus-uitbreidingsprogramma."
        ),
        impact="Reduces the academic 'market_percentiles' pillar from 2 to 0.",
        message_fr="Les percentiles du multiple sont estimés à ±20 % autour de la médiane : les percentiles p25/p75 de transactions comparables ne sont pas disponibles pour ce segment.",
        remediation_fr="Cette limite de couverture ne peut pas être corrigée dans ce rapport. Elle relève de l’enrichissement des données de l’Upswitch Index.",
    )


def _w_industry_margin_deviation(raw: JsonMap) -> DefensibilityWarning:
    details = raw.get("details") or {}
    direction = str(details.get("direction") or "lower").lower()
    try:
        actual_pct = float(details.get("actual_margin_pct"))
        actual_str = f"{actual_pct:.1f}%"
    except (TypeError, ValueError):
        actual_str = "n/a"
    try:
        typical_pct = float(details.get("typical_margin_pct"))
        typical_str = f"{typical_pct:.1f}%"
    except (TypeError, ValueError):
        typical_str = "n/a"
    return DefensibilityWarning(
        code="INDUSTRY_MARGIN_DEVIATION",
        severity=WARNING_CODES["INDUSTRY_MARGIN_DEVIATION"],
        message_en=(
            f"EBITDA margin {actual_str} is "
            f"{'lower' if direction == 'lower' else 'higher'} "
            f"than the industry typical {typical_str}. Sector classification "
            "and operating context should be confirmed before external "
            "distribution."
        ),
        message_nl=(
            f"EBITDA-marge {actual_str} ligt "
            f"{'lager' if direction == 'lower' else 'hoger'} "
            f"dan sectortypisch {typical_str}. Sectorclassificatie en "
            "operationele context dienen te worden bevestigd vóór externe "
            "distributie."
        ),
        remediation_en=(
            "Verify the business_type / NACE classification matches the "
            "actual operations; if accurate, document the operational "
            "factors that explain the deviation in the EBITDA normalisation "
            "notes."
        ),
        remediation_nl=(
            "Controleer of de business_type / NACE-classificatie aansluit "
            "bij de werkelijke activiteiten; indien correct, documenteer "
            "de operationele factoren die de afwijking verklaren in de "
            "EBITDA-normalisatie-notities."
        ),
        impact="Three Towers regression — left unaddressed, the cap and watermark fire.",
        message_fr=(
            f"La marge d’EBITDA de {actual_str} est "
            f"{'inférieure' if direction == 'lower' else 'supérieure'} "
            f"à la référence sectorielle de {typical_str}. Confirmez la classification "
            "sectorielle et le contexte opérationnel avant toute diffusion externe."
        ),
        remediation_fr="Vérifiez que la classification d’activité / NACE correspond aux opérations réelles. Si elle est correcte, documentez les facteurs expliquant l’écart dans les notes de normalisation de l’EBITDA.",
    )


def _w_methodology_downgrade(reason: str) -> DefensibilityWarning:
    reason_str = reason[:200]
    return DefensibilityWarning(
        code="METHODOLOGY_DOWNGRADE",
        severity=WARNING_CODES["METHODOLOGY_DOWNGRADE"],
        message_en=(
            "Engine downgraded methodology — a richer method was excluded "
            f"and the report uses the thinner fallback. Reason: {reason_str}."
        ),
        message_nl=(
            "Motor heeft de methodologie gedegradeerd — een rijkere methode "
            f"is uitgesloten en het rapport gebruikt de dunnere terugval. "
            f"Reden: {reason_str}."
        ),
        remediation_en=(
            "Provide the inputs the excluded method needed (typically a "
            "multi-year forecast for DCF) to re-enable it, or accept the "
            "fallback result."
        ),
        remediation_nl=(
            "Verstrek de input die de uitgesloten methode nodig had "
            "(meestal een meerjarige prognose voor DCF) om deze opnieuw in "
            "te schakelen, of accepteer het terugval-resultaat."
        ),
        impact="Lower methodology depth; affects the academic 'methodology' pillar.",
        message_fr=f"Une méthode plus complète a été exclue ; le rapport utilise une méthode de repli. Motif fourni : {reason_str}.",
        remediation_fr="Renseignez les données nécessaires à la méthode exclue, généralement des prévisions pluriannuelles pour le DCF, afin de la réactiver, ou acceptez le résultat de repli.",
    )


def _w_ev_formula_mismatch(raw: JsonMap) -> DefensibilityWarning:
    msg = str(raw.get("message") or "").strip()
    return DefensibilityWarning(
        code="EV_FORMULA_MISMATCH",
        severity=WARNING_CODES["EV_FORMULA_MISMATCH"],
        message_en=(
            "Internal EV diverged from (metric × multiple) by more than 1%; "
            "the report was aligned to the formula. Confirm before external use."
        ),
        message_nl=(
            "Interne EV week meer dan 1% af van (metric × multiple); het "
            "rapport is uitgelijnd op de formule. Bevestig vóór extern gebruik."
        ),
        remediation_en=(
            "Re-run the calibration with the same multiple input or accept "
            "the formula-aligned EV. The numerical drift usually indicates "
            "a stale cached step result."
        ),
        remediation_nl=(
            "Voer de calibratie opnieuw uit met dezelfde multiple-input of "
            "accepteer de formule-uitgelijnde EV. Numerieke drift duidt "
            "meestal op een stale gecachet stap-resultaat."
        ),
        impact=(msg or "Formula vs internal EV reconciliation gap."),
        message_fr="La valeur d’entreprise calculée s’écartait de plus de 1 % de la formule indicateur × multiple. Le rapport a été aligné sur la formule. Confirmez ce résultat avant tout usage externe.",
        remediation_fr="Relancez le calcul avec le même multiple ou confirmez la valeur d’entreprise alignée sur la formule. L’écart peut provenir d’un résultat antérieur en cache.",
    )


def _w_ev_bridge_suppressed_no_balance() -> DefensibilityWarning:
    return DefensibilityWarning(
        code="EV_BRIDGE_SUPPRESSED_NO_BALANCE",
        severity=WARNING_CODES["EV_BRIDGE_SUPPRESSED_NO_BALANCE"],
        message_en=(
            "EV→Equity bridge suppressed because the seller did not provide "
            "balance-sheet data; the report shows EV ≡ Equity."
        ),
        message_nl=(
            "EV→Equity-brug onderdrukt omdat de verkoper geen balansgegevens "
            "heeft verstrekt; het rapport toont EV ≡ Equity."
        ),
        remediation_en=(
            "Provide cash and total debt from the latest balance sheet to "
            "reinstate the proper bridge."
        ),
        remediation_nl=(
            "Verstrek kas en totale schulden uit de meest recente balans om "
            "de correcte brug te herstellen."
        ),
        impact="Equity may be over- or under-stated by net cash/debt of the entity.",
        message_fr="Le passage de la valeur d’entreprise à celle des capitaux propres est indisponible faute de données de bilan. Le rapport présente une valeur d’entreprise égale à celle des capitaux propres.",
        remediation_fr="Renseignez la trésorerie et la dette totale du dernier bilan pour rétablir ce passage.",
    )


def _w_net_debt_derived_from_gap() -> DefensibilityWarning:
    return DefensibilityWarning(
        code="NET_DEBT_DERIVED_FROM_GAP",
        severity=WARNING_CODES["NET_DEBT_DERIVED_FROM_GAP"],
        message_en=(
            "Step 7 net-debt extraction failed; the engine derived net debt "
            "from the EV/Equity gap. Confirm against the balance sheet "
            "before external use."
        ),
        message_nl=(
            "Step 7 netto-schuld extractie is mislukt; de motor heeft "
            "netto-schuld afgeleid uit het EV/Equity-verschil. Bevestig "
            "tegen de balans vóór extern gebruik."
        ),
        remediation_en=(
            "Re-import the balance sheet so Step 7 picks up cash and "
            "long-term debt directly, or override the derived value in the "
            "wizard."
        ),
        remediation_nl=(
            "Importeer de balans opnieuw zodat Step 7 kas en langlopende "
            "schulden direct oppakt, of overschrijf de afgeleide waarde in "
            "de wizard."
        ),
        impact="Net debt is provisional; the bridge may shift on real numbers.",
        message_fr="L’extraction de la dette nette a échoué : elle a été déduite de l’écart entre la valeur d’entreprise et celle des capitaux propres. Confirmez-la à partir du bilan avant tout usage externe.",
        remediation_fr="Importez à nouveau le bilan pour reprendre directement la trésorerie et la dette à long terme, ou corrigez la valeur déduite dans le formulaire.",
    )


def _w_saas_input_validation(severity_bucket: str, flags: list[JsonMap]) -> DefensibilityWarning:
    """One typed warning summarising N SaaS validation flags of the same severity.

    ``severity_bucket`` is ``error`` or ``warning``; we map the count to a
    sentence and stash the field/code list in ``impact`` so the Co-pilot can
    expand it into per-field remediations later.
    """
    code = (
        "SAAS_INPUT_VALIDATION_ERROR"
        if severity_bucket == "error"
        else "SAAS_INPUT_VALIDATION_WARNING"
    )
    fields = sorted({str(f.get("field")) for f in flags if isinstance(f, dict) and f.get("field")})
    issue_codes = sorted(
        {
            str(f.get("issue") or f.get("code"))
            for f in flags
            if isinstance(f, dict) and (f.get("issue") or f.get("code"))
        }
    )
    fields_str = ", ".join(fields) if fields else "(unspecified)"
    n = len(flags)
    if severity_bucket == "error":
        msg_en = (
            f"{n} SaaS input validation error(s) — the ARR multiple method "
            f"is blocked until resolved. Affected fields: {fields_str}."
        )
        msg_nl = (
            f"{n} SaaS input-validatiefout(en) — de ARR-multiple-methode is "
            f"geblokkeerd totdat deze zijn opgelost. Betrokken velden: {fields_str}."
        )
        remediation_en = (
            "Open the SaaS metrics section and correct each flagged field. "
            "The ARR method re-runs automatically once all errors clear."
        )
        remediation_nl = (
            "Open de SaaS-metrics-sectie en corrigeer elk gemarkeerd veld. "
            "De ARR-methode wordt automatisch opnieuw uitgevoerd zodra alle "
            "fouten zijn opgelost."
        )
    else:
        msg_en = (
            f"{n} SaaS input plausibility warning(s) — the ARR multiple ran, "
            f"but values are atypical. Affected fields: {fields_str}."
        )
        msg_nl = (
            f"{n} SaaS input-aannemelijkheidswaarschuwing(en) — de ARR-multiple "
            f"is uitgevoerd maar waarden zijn atypisch. Betrokken velden: {fields_str}."
        )
        remediation_en = (
            "Review each flagged field. If the value is correct and "
            "atypical for a deliberate reason, document it in the EBITDA "
            "normalisation notes."
        )
        remediation_nl = (
            "Beoordeel elk gemarkeerd veld. Indien de waarde correct en om "
            "een bewuste reden atypisch is, documenteer dit in de "
            "EBITDA-normalisatie-notities."
        )
    impact = ("Codes: " + ", ".join(issue_codes)) if issue_codes else None
    return DefensibilityWarning(
        code=code,
        severity=WARNING_CODES[code],
        message_en=msg_en,
        message_nl=msg_nl,
        remediation_en=remediation_en,
        remediation_nl=remediation_nl,
        impact=impact,
        message_fr=(
            f"{n} erreur(s) de validation des données SaaS : la méthode du multiple d’ARR est bloquée jusqu’à leur correction. Champs concernés : {fields_str}."
            if severity_bucket == "error"
            else f"{n} avertissement(s) sur la plausibilité des données SaaS : le multiple d’ARR a été calculé, mais certaines valeurs sont atypiques. Champs concernés : {fields_str}."
        ),
        remediation_fr=(
            "Ouvrez les indicateurs SaaS et corrigez chaque champ signalé. La méthode ARR est relancée automatiquement lorsque toutes les erreurs sont résolues."
            if severity_bucket == "error"
            else "Vérifiez chaque champ signalé. Si une valeur atypique est correcte, expliquez-la dans les notes de normalisation de l’EBITDA."
        ),
    )


def _w_dcf_limited_historical_data(raw: JsonMap) -> DefensibilityWarning:
    msg = str(raw.get("message") or "").strip()
    return DefensibilityWarning(
        code="DCF_LIMITED_HISTORICAL_DATA",
        severity=WARNING_CODES["DCF_LIMITED_HISTORICAL_DATA"],
        message_en=(
            "DCF projection rests on a thin historical base — fewer than 3 "
            "usable historical years are available for cross-validation."
        ),
        message_nl=(
            "DCF-projectie steunt op een beperkte historische basis — "
            "minder dan 3 bruikbare historische jaren zijn beschikbaar "
            "voor cross-validatie."
        ),
        remediation_en=(
            "Add at least 3 closed years of revenue and EBITDA, or weight "
            "the DCF result against a multiples cross-check in the synthesis."
        ),
        remediation_nl=(
            "Voeg minimaal 3 afgesloten jaren aan omzet en EBITDA toe, of "
            "weeg het DCF-resultaat in de synthese tegen een multiples "
            "cross-check."
        ),
        impact=(
            msg or "Forecast assumptions cannot be validated against a multi-year track record."
        ),
        message_fr="La projection DCF repose sur un historique limité : moins de 3 années exploitables sont disponibles pour la vérification croisée.",
        remediation_fr="Ajoutez au moins 3 exercices clos de chiffre d’affaires et d’EBITDA, ou confrontez le résultat DCF à une valorisation par les multiples dans la synthèse.",
    )


def _w_dcf_forecast_margin_expansion(raw: JsonMap) -> DefensibilityWarning:
    msg = str(raw.get("message") or "").strip()
    sev = str(raw.get("severity") or "").lower()
    severity = WarningSeverity.HIGH if sev == "high" else WarningSeverity.MEDIUM
    return DefensibilityWarning(
        code="DCF_FORECAST_MARGIN_EXPANSION",
        severity=severity,
        message_en=(
            "Forecast EBITDA margin exceeds the historical weighted average "
            "without a stated operational driver."
        ),
        message_nl=(
            "Prognose EBITDA-marge ligt boven het historische gewogen "
            "gemiddelde zonder onderbouwde operationele driver."
        ),
        remediation_en=(
            "Either anchor the forecast margin to the historical baseline "
            "and add a named expansion driver (pricing, mix shift, scale), "
            "or widen the confidence band in the report disclosure."
        ),
        remediation_nl=(
            "Verlaag de forecast-marge naar de historische baseline en "
            "documenteer een expliciete expansiedriver (prijszetting, mix-"
            "verschuiving, schaal), of verbreed de betrouwbaarheidsband in "
            "de rapportage."
        ),
        impact=(msg or "Materially raises the FCFF projection."),
        message_fr="La marge d’EBITDA prévisionnelle dépasse la moyenne historique pondérée sans facteur opérationnel explicite.",
        remediation_fr="Alignez la marge prévisionnelle sur l’historique et documentez les facteurs d’expansion (prix, composition des ventes, économies d’échelle), ou élargissez l’intervalle d’incertitude dans le rapport.",
    )


def _w_dcf_forecast_growth_acceleration(raw: JsonMap) -> DefensibilityWarning:
    msg = str(raw.get("message") or "").strip()
    return DefensibilityWarning(
        code="DCF_FORECAST_GROWTH_ACCELERATION",
        severity=WARNING_CODES["DCF_FORECAST_GROWTH_ACCELERATION"],
        message_en=(
            "Forecast revenue CAGR exceeds the historical CAGR by ≥10 " "percentage points."
        ),
        message_nl=(
            "Prognose omzet-CAGR overstijgt het historische CAGR met ≥10 " "procentpunten."
        ),
        remediation_en=(
            "Document the catalyst (new product, market expansion, pricing) "
            "or moderate the growth trajectory."
        ),
        remediation_nl=(
            "Documenteer de katalysator (nieuw product, marktexpansie, "
            "prijszetting) of matig de groeicurve."
        ),
        impact=(
            msg
            or "Sustains the projection on an acceleration the historical record doesn't support."
        ),
        message_fr="La croissance annuelle composée prévisionnelle du chiffre d’affaires dépasse la croissance historique d’au moins 10 points de pourcentage.",
        remediation_fr="Documentez le facteur de croissance (nouveau produit, expansion du marché, prix) ou modérez la trajectoire de croissance.",
    )


def _w_dcf_terminal_value_concentration(raw: JsonMap) -> DefensibilityWarning:
    msg = str(raw.get("message") or "").strip()
    sev = str(raw.get("severity") or "").lower()
    severity = WarningSeverity.HIGH if sev == "high" else WarningSeverity.MEDIUM
    return DefensibilityWarning(
        code="DCF_TERMINAL_VALUE_CONCENTRATION",
        severity=severity,
        message_en=(
            "Terminal value carries a disproportionately high share of total "
            "enterprise value — the explicit forecast contributes little."
        ),
        message_nl=(
            "Eindwaarde draagt een onevenredig groot deel van de totale "
            "enterprise value — de expliciete forecast levert weinig bijdrage."
        ),
        remediation_en=(
            "Extend the explicit forecast horizon, lower the terminal "
            "growth assumption, or raise the discount rate. Cross-check "
            "with a multiples synthesis."
        ),
        remediation_nl=(
            "Verleng de expliciete forecast-horizon, verlaag de "
            "terminal-growth-aanname, of verhoog de disconteringsvoet. "
            "Cross-check met een multiples-synthese."
        ),
        impact=(msg or "Result is highly sensitive to terminal-period assumptions."),
        message_fr="La valeur terminale représente une part disproportionnée de la valeur d’entreprise ; les prévisions explicites contribuent peu au résultat.",
        remediation_fr="Allongez l’horizon de prévision explicite, réduisez l’hypothèse de croissance terminale ou augmentez le taux d’actualisation. Vérifiez le résultat par une approche fondée sur les multiples.",
    )


def _w_dcf_wacc_ceiling_clamp(raw: JsonMap) -> DefensibilityWarning:
    msg = str(raw.get("message") or "").strip()
    return DefensibilityWarning(
        code="DCF_WACC_CEILING_CLAMP",
        severity=WARNING_CODES["DCF_WACC_CEILING_CLAMP"],
        message_en=(
            "Cost-of-equity exceeded the 30% ceiling and was clamped — "
            "the unclamped value indicates the company sits outside the "
            "engine's design range."
        ),
        message_nl=(
            "Cost-of-equity overschreed het 30%-plafond en is geclampd — "
            "de ongeclampte waarde duidt erop dat het bedrijf buiten het "
            "ontwerpbereik van de motor valt."
        ),
        remediation_en=(
            "Engage an advisor to model the company outside the standard "
            "WACC framework. The DCF result should not drive pricing "
            "decisions on its own at this risk level."
        ),
        remediation_nl=(
            "Schakel een adviseur in om het bedrijf buiten het standaard "
            "WACC-kader te modelleren. Het DCF-resultaat mag op dit "
            "risiconiveau niet alleen prijsbeslissingen sturen."
        ),
        impact=(msg or "DCF is operating at the edge of its applicability."),
        message_fr="Le coût des capitaux propres dépassait le plafond de 30 % et a été plafonné. La valeur non plafonnée indique que l’entreprise se situe hors du domaine d’application du modèle.",
        remediation_fr="Faites intervenir un conseiller pour modéliser l’entreprise hors du cadre standard du coût moyen pondéré du capital. À ce niveau de risque, le résultat DCF ne doit pas guider seul les décisions de prix.",
    )


def _w_generic_multiple_fallback() -> DefensibilityWarning:
    return DefensibilityWarning(
        code="GENERIC_MULTIPLE_FALLBACK",
        severity=WARNING_CODES["GENERIC_MULTIPLE_FALLBACK"],
        message_en=(
            "CRITICAL: generic 8.0x EBITDA fallback used — every layer of the "
            "multiple sourcing pipeline failed for this cell. Do not distribute."
        ),
        message_nl=(
            "KRITIEK: generieke 8.0x EBITDA fallback gebruikt — elke laag van "
            "de multiples-pijplijn heeft gefaald voor deze cel. Niet distribueren."
        ),
        remediation_en=(
            "Engineering must investigate the (business_type_id, country_code) "
            "cell — refer to the CRITICAL alert in production logs."
        ),
        remediation_nl=(
            "Engineering moet de (business_type_id, country_code) cel onderzoeken "
            "— zie de CRITICAL alert in productielogs."
        ),
        impact="Submit gate: BLOCK_SOFT — engine recommends not distributing.",
        message_fr="Un multiple générique de repli de 8,0 fois l’EBITDA a été utilisé car aucune source de multiple n’a pu être obtenue pour ce segment. Ne pas diffuser ce rapport.",
        remediation_fr="Contactez le support pour faire vérifier la disponibilité des multiples pour l’activité et le pays concernés avant de relancer le calcul.",
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def collect_warnings(
    valuation_data: JsonMap, methodology: Methodology
) -> list[DefensibilityWarning]:
    """Build the structured warnings list. Order: most severe first.

    Sources, in detection order (see helpers above):
      * methodology / data-shape gates (legacy 7 codes)
      * industry margin deviation + methodology downgrade (newly typed)
      * aggregator engine_warnings (formula mismatch / phantom bridge / derived debt)
      * SaaS input validation buckets
      * DCF forecast assumption warnings
    """
    out: list[DefensibilityWarning] = []
    if _generic_multiple_fallback(valuation_data):
        out.append(_w_generic_multiple_fallback())
    if _balance_sheet_missing(valuation_data, methodology):
        out.append(_w_balance_sheet_missing())
    if _owner_normalization_zero(valuation_data, methodology):
        out.append(_w_owner_normalization_zero())
    if _owner_profile_cap_bound(valuation_data):
        out.append(_w_owner_profile_cap_bound(valuation_data))
    if _owner_profile_skipped(valuation_data, methodology):
        out.append(_w_owner_profile_skipped())
    if _thin_historical(valuation_data, methodology):
        out.append(_w_thin_historical(valuation_data))
    if _synthetic_percentiles(valuation_data, methodology):
        out.append(_w_synthetic_percentiles())

    margin_dev_raw = _industry_margin_deviation_raw(valuation_data)
    if margin_dev_raw is not None:
        out.append(_w_industry_margin_deviation(margin_dev_raw))

    downgrade_reason = _methodology_downgrade(valuation_data)
    if downgrade_reason:
        out.append(_w_methodology_downgrade(downgrade_reason))

    eng_index = _engine_warnings_by_key(valuation_data)
    if "formula_mismatch" in eng_index:
        out.append(_w_ev_formula_mismatch(eng_index["formula_mismatch"]))
    if "phantom_bridge_suppressed" in eng_index:
        out.append(_w_ev_bridge_suppressed_no_balance())
    if "derived_net_debt_from_gap" in eng_index:
        out.append(_w_net_debt_derived_from_gap())

    saas_buckets = _saas_validation_buckets(valuation_data)
    if saas_buckets["error"]:
        out.append(_w_saas_input_validation("error", saas_buckets["error"]))
    if saas_buckets["warning"]:
        out.append(_w_saas_input_validation("warning", saas_buckets["warning"]))

    dcf_index = _dcf_forecast_warnings_by_type(valuation_data)
    if "limited_historical_data" in dcf_index:
        out.append(_w_dcf_limited_historical_data(dcf_index["limited_historical_data"]))
    if "forecast_margin_expansion" in dcf_index:
        out.append(_w_dcf_forecast_margin_expansion(dcf_index["forecast_margin_expansion"]))
    if "forecast_growth_acceleration" in dcf_index:
        out.append(_w_dcf_forecast_growth_acceleration(dcf_index["forecast_growth_acceleration"]))
    if "terminal_value_concentration" in dcf_index:
        out.append(_w_dcf_terminal_value_concentration(dcf_index["terminal_value_concentration"]))
    if "wacc_ceiling_clamp" in dcf_index:
        out.append(_w_dcf_wacc_ceiling_clamp(dcf_index["wacc_ceiling_clamp"]))

    # Sort by severity (CRITICAL first)
    severity_order = {
        WarningSeverity.CRITICAL: 0,
        WarningSeverity.HIGH: 1,
        WarningSeverity.MEDIUM: 2,
        WarningSeverity.LOW: 3,
        WarningSeverity.INFO: 4,
    }
    out.sort(key=lambda w: severity_order[w.severity])
    return out
