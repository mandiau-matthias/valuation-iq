"""DefensibilityReport — the structured, surfaced score the engine emits.

This is the public-facing wrapper around the existing
:class:`DefensibilityVerdict`. It composes:

  * the existing verdict (years × margin × engine signals → cap + watermark)
  * the new academic and ICP composite scores (0-10 each, with pillars)
  * the typed warnings list (severity + remediation)
  * a submit-gate decision (ALLOW / WARN / BLOCK_SOFT) + reasons
  * override prompts the user can act on to improve the score

Consumers:

  * **Cover chip** reads ``academic_score`` + ``icp_score`` to render the
    two-up score badge on page 1.
  * **Banner** still reads the existing ``verdict.engine_signals`` —
    backwards-compatible, no change required there.
  * **Submit gate** in the BFF reads ``submit_recommendation`` to decide
    whether to show "Are you sure?" before posting to the buyer view.
  * **PDF report renderer** reads ``warnings`` for the per-warning detail
    cards and ``override_prompts`` for the "How to improve this report"
    section.
  * **Telemetry** emits the score band + warning codes as Prometheus
    labels so we can monitor what shipped over time.

We intentionally do not gate the **engine** (the calculation itself) on
this — a low score still produces a number. The score is the
accountability layer between the number and the user.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from src.services.defensibility.classifier import (
    DefensibilityVerdict,
    classify_valuation_data,
)
from src.services.defensibility.methodology import Methodology
from src.services.defensibility.scoring import (
    CompositeScore,
    ScoreBand,
    compute_academic_score,
    compute_icp_score,
)
from src.services.defensibility.warnings import (
    DefensibilityWarning,
    WarningSeverity,
    collect_warnings,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Submit gate
# ---------------------------------------------------------------------------


class SubmitRecommendation(Enum):
    """What the engine recommends about distributing this report.

    The recommendation is *advisory*: the BFF can hard-block on
    ``BLOCK_SOFT`` or just paint a warning. The engine never silently
    refuses to compute a number — that lives in :class:`DefensibilityVerdict`
    (auto_watermark) for visual cues.
    """

    ALLOW = "allow"  # green light — Submit silently proceeds
    WARN = "warn"  # amber — show "Are you sure?" before submitting
    BLOCK_SOFT = "block_soft"  # red — engine recommends not submitting


@dataclass(frozen=True)
class SubmitGate:
    """The submit-gate decision with structured reasons.

    Why a separate dataclass: the BFF can render the reasons list as a
    bullet list under the "Are you sure?" modal. Putting them in a typed
    object instead of free text means the reasons survive serialization
    through to the frontend without translation drift.
    """

    recommendation: SubmitRecommendation
    reasons_en: List[str]
    reasons_nl: List[str]
    reasons_fr: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Override prompts — "what can the user do to improve the score"
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OverridePrompt:
    """One actionable suggestion to improve the report.

    Always derives from a warning — every prompt has a corresponding
    ``warning_code`` so the UI can correlate the prompt with the warning
    detail card. ``expected_delta`` is a string (not a number) because
    impact varies by methodology.
    """

    warning_code: str  # which warning this prompt addresses
    field_path: Optional[str]  # e.g. "current_year_data.cash" — None if not a single field
    suggested_action_en: str
    suggested_action_nl: str
    expected_delta: str  # e.g. "+1 academic point", "+5 confidence pts"


def _prompts_from_warning(w: DefensibilityWarning) -> Optional[OverridePrompt]:
    """Map each warning code to an override prompt.

    Codes without a clear single-field action (e.g. SYNTHETIC_PERCENTILES,
    GENERIC_MULTIPLE_FALLBACK) return None — those are corpus-coverage
    issues, not user-actionable.
    """
    if w.code == "BALANCE_SHEET_MISSING":
        return OverridePrompt(
            warning_code=w.code,
            field_path="current_year_data.cash, current_year_data.total_debt",
            suggested_action_en=(
                "Open the Financials section and fill in cash and total debt "
                "from the most recent balance sheet."
            ),
            suggested_action_nl=(
                "Open de Financiën-sectie en vul kas en totale schulden in "
                "vanuit de meest recente balans."
            ),
            expected_delta="+1 academic point; closes the EV→Equity bridge",
        )
    if w.code == "OWNER_NORMALIZATION_ZERO":
        return OverridePrompt(
            warning_code=w.code,
            field_path="ebitda_normalisations",
            suggested_action_en=(
                "Open the EBITDA Normalisation section and add market-rate "
                "owner compensation plus any one-time expenses."
            ),
            suggested_action_nl=(
                "Open de EBITDA-Normalisatie-sectie en voeg marktconforme "
                "eigenaarsvergoeding toe plus eventuele eenmalige posten."
            ),
            expected_delta="Typically +5-25% on the band; mid is preserved as gospel",
        )
    if w.code == "OWNER_PROFILE_SKIPPED":
        return OverridePrompt(
            warning_code=w.code,
            field_path="owner_profile_assessment",
            suggested_action_en=(
                "Complete the 9-question Owner Profile to quantify " "transferability risk."
            ),
            suggested_action_nl=(
                "Vul het 9-vragen Eigenaarsprofiel in om "
                "overdraagbaarheidsrisico te kwantificeren."
            ),
            expected_delta="+1 academic point; unlocks the structured equity adjustment",
        )
    if w.code == "THIN_HISTORICAL_DATA":
        return OverridePrompt(
            warning_code=w.code,
            field_path="historical_years_data",
            suggested_action_en=(
                "Add at least 2 prior years of revenue and EBITDA. "
                "Three or more years unlocks the full historical depth pillar."
            ),
            suggested_action_nl=(
                "Voeg minimaal 2 voorgaande jaren omzet en EBITDA toe. "
                "Drie of meer jaren ontgrendelt de volledige historische pijler."
            ),
            expected_delta="+1 academic point at 2 years, +2 at 3+",
        )
    if w.code == "OWNER_PROFILE_CAP_BOUND":
        return OverridePrompt(
            warning_code=w.code,
            field_path="advisor_review",
            suggested_action_en=(
                "Engage an accountant or advisor to validate the "
                "transferability assessment before pricing."
            ),
            suggested_action_nl=(
                "Schakel een accountant of adviseur in om de "
                "overdraagbaarheidsbeoordeling te valideren vóór prijsstelling."
            ),
            expected_delta="Trust signal — does not change the headline number, raises ICP",
        )
    if w.code == "INDUSTRY_MARGIN_DEVIATION":
        return OverridePrompt(
            warning_code=w.code,
            field_path="business_type_id, ebitda_normalisations",
            suggested_action_en=(
                "Verify the business_type / NACE classification matches the "
                "actual operations; if accurate, document the operational "
                "factors that explain the margin gap in the EBITDA "
                "normalisation notes."
            ),
            suggested_action_nl=(
                "Controleer of de business_type / NACE-classificatie "
                "overeenkomt met de werkelijke activiteiten; indien correct, "
                "documenteer de operationele factoren die het marge-verschil "
                "verklaren in de EBITDA-normalisatie-notities."
            ),
            expected_delta="Removes the cap and watermark when explained or reclassified.",
        )
    if w.code == "METHODOLOGY_DOWNGRADE":
        return OverridePrompt(
            warning_code=w.code,
            field_path="forecast_years_data",
            suggested_action_en=(
                "Add a 3-5 year forecast (revenue, EBITDA) to re-enable the "
                "DCF method, or accept the multiples-only result."
            ),
            suggested_action_nl=(
                "Voeg een 3-5-jaars forecast toe (omzet, EBITDA) om de "
                "DCF-methode opnieuw in te schakelen, of accepteer het "
                "multiples-only resultaat."
            ),
            expected_delta="Re-enables DCF cross-check; +1 academic point.",
        )
    if w.code == "EV_BRIDGE_SUPPRESSED_NO_BALANCE":
        return OverridePrompt(
            warning_code=w.code,
            field_path="current_year_data.cash, current_year_data.total_debt",
            suggested_action_en=(
                "Provide cash and total debt from the latest balance sheet "
                "to reinstate the EV→Equity bridge."
            ),
            suggested_action_nl=(
                "Verstrek kas en totale schulden uit de meest recente balans "
                "om de EV→Equity-brug te herstellen."
            ),
            expected_delta="Restores the proper bridge; equity may shift up or down.",
        )
    if w.code == "NET_DEBT_DERIVED_FROM_GAP":
        return OverridePrompt(
            warning_code=w.code,
            field_path="current_year_data.cash, current_year_data.total_debt",
            suggested_action_en=(
                "Re-import the balance sheet so Step 7 picks up cash and "
                "long-term debt directly, or override the derived value in "
                "the wizard."
            ),
            suggested_action_nl=(
                "Importeer de balans opnieuw zodat Step 7 kas en langlopende "
                "schulden direct oppakt, of overschrijf de afgeleide waarde "
                "in de wizard."
            ),
            expected_delta="Replaces a derived value with reported numbers.",
        )
    if w.code == "SAAS_INPUT_VALIDATION_ERROR":
        return OverridePrompt(
            warning_code=w.code,
            field_path="saas_metrics",
            suggested_action_en=(
                "Open the SaaS metrics section and correct each flagged "
                "field. The ARR multiple method re-runs automatically once "
                "all errors clear."
            ),
            suggested_action_nl=(
                "Open de SaaS-metrics-sectie en corrigeer elk gemarkeerd "
                "veld. De ARR-multiple-methode wordt automatisch opnieuw "
                "uitgevoerd zodra alle fouten zijn opgelost."
            ),
            expected_delta="Unblocks the ARR multiple leg in the synthesis.",
        )
    if w.code == "SAAS_INPUT_VALIDATION_WARNING":
        return OverridePrompt(
            warning_code=w.code,
            field_path="saas_metrics",
            suggested_action_en=(
                "Review each flagged SaaS metric. If the value is correct "
                "and atypical for a deliberate reason, document it in the "
                "EBITDA normalisation notes."
            ),
            suggested_action_nl=(
                "Beoordeel elk gemarkeerd SaaS-metric. Indien de waarde "
                "correct en om een bewuste reden atypisch is, documenteer "
                "dit in de EBITDA-normalisatie-notities."
            ),
            expected_delta="Trust signal; does not change the multiple.",
        )
    if w.code == "DCF_LIMITED_HISTORICAL_DATA":
        return OverridePrompt(
            warning_code=w.code,
            field_path="historical_years_data",
            suggested_action_en=(
                "Add at least 3 closed years of revenue and EBITDA to give "
                "the DCF projection a real baseline."
            ),
            suggested_action_nl=(
                "Voeg minimaal 3 afgesloten jaren omzet en EBITDA toe om "
                "de DCF-projectie een reële baseline te geven."
            ),
            expected_delta="+1 academic point at 2 years, +2 at 3+.",
        )
    if w.code == "DCF_FORECAST_MARGIN_EXPANSION":
        return OverridePrompt(
            warning_code=w.code,
            field_path="forecast_years_data, ebitda_normalisations",
            suggested_action_en=(
                "Either anchor the forecast margin to the historical "
                "baseline and add a named expansion driver (pricing, mix "
                "shift, scale), or widen the confidence band in the report "
                "disclosure."
            ),
            suggested_action_nl=(
                "Anker de forecast-marge aan de historische baseline en "
                "documenteer een expliciete expansiedriver (prijszetting, "
                "mix-verschuiving, schaal), of verbreed de "
                "betrouwbaarheidsband in de rapportage."
            ),
            expected_delta="Removes the WARN gate from the DCF leg.",
        )
    if w.code == "DCF_FORECAST_GROWTH_ACCELERATION":
        return OverridePrompt(
            warning_code=w.code,
            field_path="forecast_years_data",
            suggested_action_en=(
                "Document the catalyst (new product, market expansion, "
                "pricing) or moderate the growth trajectory."
            ),
            suggested_action_nl=(
                "Documenteer de katalysator (nieuw product, marktexpansie, "
                "prijszetting) of matig de groeicurve."
            ),
            expected_delta="Aligns DCF with historical record.",
        )
    if w.code == "DCF_TERMINAL_VALUE_CONCENTRATION":
        return OverridePrompt(
            warning_code=w.code,
            field_path="dcf.forecast_horizon, dcf.terminal_growth_rate",
            suggested_action_en=(
                "Extend the explicit forecast horizon, lower the terminal "
                "growth assumption, or raise the discount rate. Cross-check "
                "with a multiples synthesis."
            ),
            suggested_action_nl=(
                "Verleng de expliciete forecast-horizon, verlaag de "
                "terminal-growth-aanname, of verhoog de disconteringsvoet. "
                "Cross-check met een multiples-synthese."
            ),
            expected_delta="Reduces sensitivity to terminal-period assumptions.",
        )
    if w.code == "DCF_WACC_CEILING_CLAMP":
        return OverridePrompt(
            warning_code=w.code,
            field_path="advisor_review",
            suggested_action_en=(
                "Engage an advisor — the company sits outside the engine's "
                "design range. The DCF result should not drive pricing on "
                "its own at this risk level."
            ),
            suggested_action_nl=(
                "Schakel een adviseur in — het bedrijf valt buiten het "
                "ontwerpbereik van de motor. Het DCF-resultaat mag op dit "
                "risiconiveau niet alleen prijsbeslissingen sturen."
            ),
            expected_delta="Trust signal; recommends advisor co-sign before pricing.",
        )
    return None


def _decide_submit(
    academic: CompositeScore,
    icp: CompositeScore,
    warnings: List[DefensibilityWarning],
) -> SubmitGate:
    """Combine the two scores + warnings into a submit recommendation.

    Decision rules (deliberately conservative — easier to relax later):

      * Any CRITICAL warning → BLOCK_SOFT. Checked FIRST and unconditionally.
      * Either score carries an ``error`` marker (our plumbing failed, not
        the customer's data) → WARN.
      * Academic < 7 OR ICP < 6 OR any HIGH warning → WARN.
      * Otherwise ALLOW.

    Why a low score no longer BLOCKS
    --------------------------------
    BLOCK_SOFT is not advice — ``/api/v1/reports/pdf`` refuses with 422
    ``pdf_blocked_not_share_ready``, so it is a hard stop on the advisor's
    deliverable. The old rule blocked at ``academic < 5``, and the pillars that
    most often miss are OUR data limitations (synthetic percentiles because we
    have no Damodaran p25/p75 for the type; no owner profile because the flow
    never asked) rather than anything wrong with the customer's business.

    The first paying advisor hit exactly this: a real Silverfin import with four
    years of filed accounts and a resolved benchmark contract scored 4/10 and
    his PDF export silently stopped working. He experienced it as a broken
    button — nothing in the UI said a gate had refused.

    A qualified accountant is entitled to see the caveats and decide. The report
    already carries its watermark, its confidence band and its warning list, so
    the disclosure is intact. Reserve the hard stop for CRITICAL, which means
    "this number is not safe to put in front of a third party at all".
    """
    has_critical = any(w.severity == WarningSeverity.CRITICAL for w in warnings)
    has_high = any(w.severity == WarningSeverity.HIGH for w in warnings)
    # A fallback 0 from a crashed scorer must never drive BLOCK_SOFT: that
    # would recommend against distributing a customer's report because of a bug
    # on our side. Degrade to WARN and name the reason instead.
    degraded = bool(academic.error or icp.error)

    # CRITICAL is evaluated before `degraded` on purpose. Ordering them the other
    # way let any scorer crash silently downgrade a CRITICAL
    # "GENERIC_MULTIPLE_FALLBACK — do not distribute" to WARN, which is the one
    # direction this gate must never fail in.
    if has_critical:
        rec = SubmitRecommendation.BLOCK_SOFT
    elif degraded or academic.score < 7 or icp.score < 6 or has_high:
        rec = SubmitRecommendation.WARN
    else:
        rec = SubmitRecommendation.ALLOW

    reasons_en: List[str] = []
    reasons_nl: List[str] = []
    reasons_fr: List[str] = []
    if degraded:
        reasons_en.append(
            "Defensibility scoring did not complete — the scores shown are "
            "unavailable, not a judgement about this valuation."
        )
        reasons_nl.append(
            "De onderbouwingsscore kon niet worden berekend — de getoonde "
            "scores zijn niet beschikbaar, geen oordeel over deze waardering."
        )
        reasons_fr.append(
            "Le calcul des scores de solidité n’a pas abouti : les scores sont "
            "indisponibles et ne constituent pas un jugement sur cette valorisation."
        )
    # Suppress a score's reason only when THAT score is the one that failed to
    # compute. Gating both on a shared `degraded` flag meant a correctly measured
    # ICP 2/10 vanished from the reasons whenever the academic scorer happened to
    # crash — hiding a real finding behind an unrelated bug.
    if not academic.error and academic.score < 7:
        reasons_en.append(f"Academic score {academic.score}/10 below the strong threshold (7).")
        reasons_nl.append(f"Academische score {academic.score}/10 onder de sterke drempel (7).")
        reasons_fr.append(
            f"Score méthodologique de {academic.score}/10, inférieur au seuil de solidité (7)."
        )
    if not icp.error and icp.score < 6:
        reasons_en.append(f"ICP score {icp.score}/10 below the strong threshold (6).")
        reasons_nl.append(f"ICP-score {icp.score}/10 onder de sterke drempel (6).")
        reasons_fr.append(f"Score ICP de {icp.score}/10, inférieur au seuil de solidité (6).")
    for w in warnings:
        if w.severity in (WarningSeverity.HIGH, WarningSeverity.CRITICAL):
            reasons_en.append(f"{w.severity.value.upper()}: {w.message_en}")
            reasons_nl.append(f"{w.severity.value.upper()}: {w.message_nl}")
            severity_fr = "CRITIQUE" if w.severity == WarningSeverity.CRITICAL else "ÉLEVÉ"
            reasons_fr.append(f"{severity_fr} : {w.message('fr')}")

    return SubmitGate(
        recommendation=rec, reasons_en=reasons_en, reasons_nl=reasons_nl, reasons_fr=reasons_fr
    )


# ---------------------------------------------------------------------------
# Top-level structured report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DefensibilityReport:
    """Structured, public-facing defensibility output.

    Composes :class:`DefensibilityVerdict` (existing watermark / cap logic)
    with the new academic + ICP scores, typed warnings, override prompts,
    and submit gate. Backwards compatible: callers that only need the old
    verdict can read ``self.verdict`` and continue unchanged.
    """

    verdict: DefensibilityVerdict
    academic: CompositeScore
    icp: CompositeScore
    warnings: List[DefensibilityWarning]
    override_prompts: List[OverridePrompt]
    submit_gate: SubmitGate
    # Set when ``collect_warnings`` raised. An empty ``warnings`` list then
    # means "we could not look", not "nothing was wrong".
    warnings_error: Optional[str] = None

    @property
    def scoring_degraded(self) -> bool:
        """True when any part of the defensibility pipeline failed.

        While true, no consumer may present the scores as a verdict: the
        0/INSUFFICIENT beside a marker is a fallback, not a measurement.
        """
        return bool(self.academic.error or self.icp.error or self.warnings_error)

    @property
    def scoring_errors(self) -> List[str]:
        return [err for err in (self.academic.error, self.icp.error, self.warnings_error) if err]

    @property
    def methodology(self) -> Methodology:
        return self.verdict.methodology

    @property
    def auto_watermark(self) -> bool:
        return self.verdict.auto_watermark

    @property
    def confidence_cap(self) -> Decimal:
        return self.verdict.confidence_cap

    def to_serializable(self) -> Dict[str, Any]:
        """Render to a JSON-friendly dict for the response payload.

        The PDF renderer and the BFF both consume this. Keys are kept
        stable; do not rename without bumping a contract test.
        """
        return {
            "methodology": self.verdict.methodology.value,
            # Plumbing-failure marker. True means a scorer or the warning
            # collector raised, and any 0 / INSUFFICIENT below is a fallback
            # rather than a measurement. Renderers must show "score
            # unavailable", never a 0, while this is true.
            "scoring_degraded": self.scoring_degraded,
            "scoring_errors": self.scoring_errors,
            "academic": {
                "score": self.academic.score,
                "band": self.academic.band.value,
                "error": self.academic.error,
                "pillars": [
                    {
                        "code": p.code,
                        "description": p.description,
                        "points_earned": p.points_earned,
                        "points_possible": p.points_possible,
                    }
                    for p in self.academic.pillars
                ],
            },
            "icp": {
                "score": self.icp.score,
                "band": self.icp.band.value,
                "error": self.icp.error,
                "pillars": [
                    {
                        "code": p.code,
                        "description": p.description,
                        "points_earned": p.points_earned,
                        "points_possible": p.points_possible,
                    }
                    for p in self.icp.pillars
                ],
            },
            "warnings": [
                {
                    "code": w.code,
                    "severity": w.severity.value,
                    "message_en": w.message_en,
                    "message_nl": w.message_nl,
                    "message_fr": w.message("fr"),
                    "remediation_en": w.remediation_en,
                    "remediation_nl": w.remediation_nl,
                    "remediation_fr": w.remediation("fr"),
                    "impact": w.impact,
                }
                for w in self.warnings
            ],
            "override_prompts": [
                {
                    "warning_code": p.warning_code,
                    "field_path": p.field_path,
                    "suggested_action_en": p.suggested_action_en,
                    "suggested_action_nl": p.suggested_action_nl,
                    "expected_delta": p.expected_delta,
                }
                for p in self.override_prompts
            ],
            "submit_gate": {
                "recommendation": self.submit_gate.recommendation.value,
                "reasons_en": list(self.submit_gate.reasons_en),
                "reasons_nl": list(self.submit_gate.reasons_nl),
                "reasons_fr": list(self.submit_gate.reasons_fr),
            },
            # Existing verdict surface — backwards compatibility
            "auto_watermark": self.verdict.auto_watermark,
            "confidence_cap": float(self.verdict.confidence_cap),
            "is_full_report": self.verdict.is_full_report,
        }


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------


def build_defensibility_report(
    valuation_data: Dict[str, Any], locale: str = "nl"
) -> DefensibilityReport:
    """Compose the full structured defensibility report.

    Defensive: any failure in the score / warning pipeline falls back to
    a permissive default — the engine *cannot* refuse to produce a report
    over a defensibility-layer bug. The cap on ``DefensibilityVerdict``
    still applies as the existing safety net.
    """
    verdict = classify_valuation_data(valuation_data, locale=locale)
    methodology = verdict.methodology

    try:
        academic = compute_academic_score(valuation_data, methodology)
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("defensibility: academic scorer raised — emitting error marker")
        academic = CompositeScore(
            score=0,
            pillars=[],
            band=ScoreBand.INSUFFICIENT,
            # Type name only: never put ``str(exc)`` on the wire, it can carry
            # customer figures.
            error=f"academic_scorer_failed:{type(exc).__name__}",
        )

    try:
        icp = compute_icp_score(valuation_data, methodology)
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("defensibility: ICP scorer raised — emitting error marker")
        icp = CompositeScore(
            score=0,
            pillars=[],
            band=ScoreBand.INSUFFICIENT,
            error=f"icp_scorer_failed:{type(exc).__name__}",
        )

    warnings_error: Optional[str] = None
    try:
        warnings_list = collect_warnings(valuation_data, methodology)
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("defensibility: warning collector raised — emitting error marker")
        warnings_list = []
        warnings_error = f"warning_collector_failed:{type(exc).__name__}"

    prompts = [p for p in (_prompts_from_warning(w) for w in warnings_list) if p is not None]
    submit = _decide_submit(academic, icp, warnings_list)

    return DefensibilityReport(
        verdict=verdict,
        academic=academic,
        icp=icp,
        warnings=warnings_list,
        override_prompts=prompts,
        submit_gate=submit,
        warnings_error=warnings_error,
    )
