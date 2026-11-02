"""SaaS / ARR-multiple eligibility — pure module, no I/O.

This is the gate that should have prevented the 2026-04-29 Three Towers
report from silently using EV/Revenue when the user picked an ARR multiple
on a 9%-recurring consultancy.

The rule book — defended against the Big-4 / academic panel review:

  1. **Recurring revenue share must dominate.** If ARR / total revenue is
     below ``min_recurring_share`` (default 40%), the company is *not*
     a SaaS for valuation purposes; its multiple should anchor on EBITDA,
     SDE, or EV/Revenue with explicit consulting comps — not on KeyBanc's
     SaaS distribution. 40% is the threshold below which the recurring
     line is too small to drive the headline (KeyBanc 2024: median listed
     SaaS recurring share = 88%; even hybrid acquirers want > 40%).

  2. **ARR must be material.** If ARR is below ``min_arr_eur`` (default
     €100k), market multiples have no statistical support — the comp set
     does not exist. Below this, the method is unavailable.

  3. **Core SaaS metrics must be present.** ARR multiples without ARR
     growth and at least one retention signal (NRR or gross-revenue
     churn) are not defensible — the multiple distribution is too wide
     without growth/retention conditioning.

  4. **No blocking validation errors.** Errors from
     ``saas_input_validation`` block; warnings are surfaced but allow
     the method to run.

Usage from the orchestrator::

    verdict = evaluate_saas_eligibility(
        revenue=Decimal("1000000"),
        business_context=request.business_context,
        validation_report=validation_report,
    )
    if not verdict.eligible:
        # surface verdict.reasons in MethodResult.unavailable_reason
        ...
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.domain.saas_input_validation import SaasValidationReport
from src.utils.adaptive_input_helpers import (
    get_business_context_decimal,
    get_business_context_percent,
)

# ── Defaults — tuned for Belgian / EU SME SaaS ───────────────────────

DEFAULT_MIN_RECURRING_SHARE = Decimal("0.40")  # ARR / total revenue
DEFAULT_MIN_ARR_EUR = Decimal("100000")
DEFAULT_REQUIRED_GROWTH_OR_RETENTION = True  # require ARR-growth + (NRR or churn)


@dataclass(frozen=True)
class EligibilityThresholds:
    """All knobs that gate ARR-method eligibility. Override per request if
    Titan starts shipping per-business-type SaaS thresholds."""

    min_recurring_share: Decimal = DEFAULT_MIN_RECURRING_SHARE
    min_arr_eur: Decimal = DEFAULT_MIN_ARR_EUR
    require_growth_or_retention: bool = DEFAULT_REQUIRED_GROWTH_OR_RETENTION

    @classmethod
    def for_business_type(cls, business_type_id: Optional[str]) -> "EligibilityThresholds":
        """Return tuned thresholds for a given Titan business-type id.

        Mostly-software businesses get a relaxed share threshold (50–60%);
        services/consulting profiles get a strict one (80%) so the ARR lens
        only fires when the business is *predominantly* recurring. Unknown
        types fall back to the conservative 40% default.

        The lookup is intentionally small and explicit — this is not a
        place for fuzzy industry classification. If the business-type
        layer adds new IDs, register them here so the gate stays
        deterministic.
        """
        if not business_type_id:
            return cls()
        bt = str(business_type_id).strip().lower()

        # Pure-SaaS — smallest threshold; the engine should run when the
        # company is at least half recurring.
        if bt in {"saas", "saas_software", "b2b_saas", "saas-software"}:
            return cls(min_recurring_share=Decimal("0.50"))

        # Software-adjacent — same floor as default but a relaxed
        # growth/retention requirement isn't appropriate; keep both.
        if bt in {"software", "platform", "mobile_app", "fintech", "marketplace"}:
            return cls(min_recurring_share=Decimal("0.50"))

        # Services / consulting — gate hard so the ARR lens only fires
        # when the business is truly subscription-led, not a project
        # shop with a recurring add-on.
        if bt in {
            "consulting",
            "professional_services",
            "professional-services",
            "agency",
            "law_firm",
            "accountancy",
            "accounting",
        }:
            return cls(min_recurring_share=Decimal("0.80"))

        return cls()


@dataclass(frozen=True)
class SaasEligibilityVerdict:
    """Structured verdict on whether the ARR / SaaS lens applies.

    ``eligible`` is the load-bearing flag; ``blocking_reasons`` are
    user-facing strings (already i18n-friendly Dutch) suitable for
    ``MethodResult.unavailable_reason`` or a PDF banner. ``signals``
    surfaces machine-readable metrics for the report context.
    """

    eligible: bool
    recurring_share: Optional[Decimal]
    arr: Optional[Decimal]
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    signals: dict[str, object] = field(default_factory=dict)
    suggested_alternative_method: Optional[str] = None

    def as_dict(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "recurring_share": (
                float(self.recurring_share) if self.recurring_share is not None else None
            ),
            "arr": float(self.arr) if self.arr is not None else None,
            "blocking_reasons": list(self.blocking_reasons),
            "warnings": list(self.warnings),
            "signals": dict(self.signals),
            "suggested_alternative_method": self.suggested_alternative_method,
        }


def _resolve_arr(
    *,
    business_context: Mapping[str, object],
    revenue: Optional[Decimal],
    recurring_revenue_percentage: Optional[Decimal],
) -> Optional[Decimal]:
    """Match the resolution priority used by ``saas_valuation_adjuster``:
    explicit ARR > MRR×12 > recurring% × revenue.
    """
    explicit_arr = get_business_context_decimal(business_context, "saas_arr")
    if explicit_arr is not None and explicit_arr > 0:
        return explicit_arr

    mrr = get_business_context_decimal(business_context, "saas_mrr")
    if mrr is not None and mrr > 0:
        return mrr * Decimal("12")

    if (
        recurring_revenue_percentage is not None
        and recurring_revenue_percentage > 0
        and revenue is not None
        and revenue > 0
    ):
        return revenue * recurring_revenue_percentage

    return None


def _recurring_share_for(
    *,
    revenue: Optional[Decimal],
    arr: Optional[Decimal],
) -> Optional[Decimal]:
    if revenue is not None and revenue > 0 and arr is not None:
        return arr / revenue
    return None


def _apply_validation_error_rule(
    *,
    validation_report: Optional[SaasValidationReport],
    blocking_reasons: list[str],
) -> None:
    if validation_report is None or not validation_report.has_errors:
        return
    for err_flag in validation_report.by_severity("error"):
        blocking_reasons.append(err_flag.message)


def _apply_arr_materiality_rule(
    *,
    arr: Optional[Decimal],
    thresholds: EligibilityThresholds,
    blocking_reasons: list[str],
) -> Optional[str]:
    if arr is None or arr <= 0:
        blocking_reasons.append(
            "ARR ontbreekt of is nul. Vul Annual Recurring Revenue, MRR, of "
            "een aandeel terugkerende omzet in om de ARR-multiple te activeren."
        )
        return "ebitda_multiple"

    if arr >= thresholds.min_arr_eur:
        return None

    blocking_reasons.append(
        f"ARR (€{float(arr):,.0f}) ligt onder de drempel van "
        f"€{float(thresholds.min_arr_eur):,.0f} waarboven SaaS-multiples "
        "statistisch onderbouwd zijn."
    )
    return "sde_multiple" if arr < Decimal("250000") else "ebitda_multiple"


def _apply_recurring_share_rule(
    *,
    revenue: Optional[Decimal],
    recurring_share: Optional[Decimal],
    thresholds: EligibilityThresholds,
    blocking_reasons: list[str],
    warnings: list[str],
    suggested_alt: Optional[str],
) -> Optional[str]:
    if revenue is None or revenue <= 0 or recurring_share is None:
        return suggested_alt

    if recurring_share < thresholds.min_recurring_share:
        blocking_reasons.append(
            f"Terugkerende omzet (ARR) is slechts "
            f"{float(recurring_share * 100):.1f}% van de totaalomzet — onder "
            f"de drempel van {float(thresholds.min_recurring_share * 100):.0f}% "
            "die nodig is om SaaS-multiples als hoofdlens te gebruiken."
        )
        return suggested_alt or "ebitda_multiple"

    if recurring_share < Decimal("0.65"):
        warnings.append(
            f"Terugkerende omzet is {float(recurring_share * 100):.1f}% van "
            "totaalomzet — het bedrijf is hybride. Triangulatie met EBITDA "
            "of SDE wordt sterk aanbevolen."
        )

    return suggested_alt


def _apply_growth_retention_rule(
    *,
    ctx: Mapping[str, object],
    thresholds: EligibilityThresholds,
    blocking_reasons: list[str],
    suggested_alt: Optional[str],
) -> Optional[str]:
    if not thresholds.require_growth_or_retention or blocking_reasons:
        return suggested_alt

    arr_growth = get_business_context_percent(ctx, "saas_arr_growth_pct")
    nrr = get_business_context_percent(ctx, "saas_nrr_pct")
    revenue_churn = get_business_context_percent(ctx, "saas_churn_pct")
    has_retention = nrr is not None or revenue_churn is not None
    if arr_growth is None:
        blocking_reasons.append(
            "ARR-groei (saas_arr_growth_pct) ontbreekt — vereist voor een "
            "verdedigbare ARR-multiple."
        )
    if not has_retention:
        blocking_reasons.append(
            "Geen retentie-signaal (NRR of bruto-omzetchurn) — vereist om "
            "ARR-multiples op kwaliteit te kunnen calibreren."
        )
    return suggested_alt or "ebitda_multiple" if blocking_reasons else suggested_alt


def _validation_warning_messages(
    validation_report: Optional[SaasValidationReport],
) -> list[str]:
    if validation_report is None:
        return []
    return [warn_flag.message for warn_flag in validation_report.by_severity("warning")]


def _eligibility_signals(
    *,
    arr: Optional[Decimal],
    recurring_share: Optional[Decimal],
    thresholds: EligibilityThresholds,
    validation_report: Optional[SaasValidationReport],
) -> dict[str, object]:
    return {
        "arr_eur": float(arr) if arr is not None else None,
        "recurring_share": float(recurring_share) if recurring_share is not None else None,
        "min_recurring_share_threshold": float(thresholds.min_recurring_share),
        "min_arr_eur_threshold": float(thresholds.min_arr_eur),
        "validation_error_count": (
            len(validation_report.by_severity("error")) if validation_report else 0
        ),
        "validation_warning_count": (
            len(validation_report.by_severity("warning")) if validation_report else 0
        ),
    }


def evaluate_saas_eligibility(
    *,
    revenue: Optional[Decimal],
    business_context: Optional[Mapping[str, object]],
    recurring_revenue_percentage: Optional[Decimal] = None,
    validation_report: Optional[SaasValidationReport] = None,
    thresholds: Optional[EligibilityThresholds] = None,
) -> SaasEligibilityVerdict:
    """Decide whether the ARR multiple is a defensible primary lens.

    Pure function. Caller decides what to do with an ineligible verdict
    (return ``MethodResult(available=False)``, raise to UI, downgrade
    primary method, etc.).
    """
    thresholds = thresholds or EligibilityThresholds()
    ctx = dict(business_context or {})

    arr = _resolve_arr(
        business_context=ctx,
        revenue=revenue,
        recurring_revenue_percentage=recurring_revenue_percentage,
    )

    recurring_share = _recurring_share_for(revenue=revenue, arr=arr)
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    suggested_alt: Optional[str] = None

    _apply_validation_error_rule(
        validation_report=validation_report,
        blocking_reasons=blocking_reasons,
    )
    suggested_alt = _apply_arr_materiality_rule(
        arr=arr,
        thresholds=thresholds,
        blocking_reasons=blocking_reasons,
    )
    suggested_alt = _apply_recurring_share_rule(
        revenue=revenue,
        recurring_share=recurring_share,
        thresholds=thresholds,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        suggested_alt=suggested_alt,
    )
    suggested_alt = _apply_growth_retention_rule(
        ctx=ctx,
        thresholds=thresholds,
        blocking_reasons=blocking_reasons,
        suggested_alt=suggested_alt,
    )
    warnings.extend(_validation_warning_messages(validation_report))

    eligible = not blocking_reasons

    return SaasEligibilityVerdict(
        eligible=eligible,
        recurring_share=recurring_share,
        arr=arr,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        signals=_eligibility_signals(
            arr=arr,
            recurring_share=recurring_share,
            thresholds=thresholds,
            validation_report=validation_report,
        ),
        suggested_alternative_method=suggested_alt if not eligible else None,
    )
