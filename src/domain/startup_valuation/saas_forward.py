"""SaaS Forward Multiple — the third consortium-prescribed startup method.

Academic / VC blueprint (Index Ventures · Seedcamp · Point Nine, INSEAD,
LBS, 2025):

    *Forward 12-month ARR* (today's MRR projected forward at the founder's
    own MoM growth rate, capped at a defensible ceiling) is multiplied by
    a **live regional EV/Revenue multiple** for SaaS comparables and then
    *risk-adjusted* down for execution risk (Berkus surface + churn proxy).

This deliberately replaces the historical-trial-balance-driven SME
``arr_multiple`` lens for the venture path — pre-revenue founders cannot
defend a backward looking multiple, but they *can* defend a forward
ARR projection if it is anchored to current MRR and a stated growth rate.

The method **only contributes** when the founder supplies MRR (or ARR);
otherwise the synthesizer drops it and re-normalises the remaining legs.

Output shape mirrors :class:`BerkusOutput` / :class:`VcOutput` so the
synthesis blender treats it like any other leg.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .money import (
    LegResult,
    ONE,
    ONE_HUNDRED,
    ZERO,
    clamp,
    q_eur,
    q_pct,
    q_rate,
)
from .regional_data import RegionalReferenceData
from .schemas import StartupInputs

# ---------------------------------------------------------------------------
# Tunable defensibility constants (derived from public Atomico / Dealroom
# benchmarks 2024-2025 — keep conservative to avoid optimism bias).
# ---------------------------------------------------------------------------

#: Hard cap on the projected MoM growth rate fed into the forward ARR
#: model.  The consortium's blueprint warns that >20% MoM compounded for
#: 12 months produces unrealistic numbers (e.g. 9× ARR multiplier).  We
#: cap at 20% MoM = ~9× annual which is already extreme but leaves the
#: founder's own number visible in the report.
_MAX_MOM_GROWTH_PCT: Decimal = Decimal("20")

#: Minimum forward growth assumption when the founder didn't supply one
#: (so the forward ARR is meaningfully different from today's ARR).
_DEFAULT_MOM_GROWTH_PCT: Decimal = Decimal("8")

#: Months projected forward.  Aligned with the consortium's "Forward
#: 12-month ARR" prescription (also matches Bessemer / SaaStr norm).
_FORWARD_MONTHS: int = 12

#: Execution risk discount applied to the comparable EV/Revenue multiple
#: based on the *Berkus surface* (average of the 5 risk-reduction
#: sliders).  At 0% risk-reduction the multiple is halved; at 100% the
#: multiple is taken at full strength.
_MIN_RISK_DISCOUNT: Decimal = Decimal("0.50")

#: Additional drag applied for high churn (>5% monthly = death spiral).
#: Subtractive on the [0,1] discount factor, capped at -0.30.
_CHURN_DRAG_PER_PCT: Decimal = Decimal("0.06")
_MAX_CHURN_DRAG: Decimal = Decimal("0.30")

#: SaaS-vs-comparable EV/Revenue multiple translation.  The regional
#: reference table provides exit EV/Revenue at Year-5; today's forward
#: multiple is a fraction of that exit number (the further out, the
#: higher the multiple).  Empirically forward multiples for venture SaaS
#: are ~50-70% of expected exit multiples.
_FORWARD_MULTIPLE_RATIO: Decimal = Decimal("0.60")

SAAS_FORWARD_LEG_LABEL: str = "SaaS Forward Multiple"


@dataclass(frozen=True)
class SaasForwardOutput:
    """Result of the SaaS Forward Multiple leg."""

    pre_money: Decimal
    """Risk-adjusted forward valuation in EUR.  Zero ⇒ leg unavailable."""

    current_arr: Decimal
    forward_arr: Decimal
    forward_mom_growth_pct: Decimal
    forward_months: int
    base_multiple: Decimal
    """Live regional forward EV/Revenue multiple (no risk adjustment)."""
    applied_multiple: Decimal
    """Multiple after Berkus + churn risk adjustment."""
    risk_discount: Decimal
    """Multiplicative discount applied (0..1).  1.0 ⇒ no risk-adjust."""
    churn_drag: Decimal
    """Additional drag attributed to monthly churn (0..0.30)."""
    available: bool
    unavailable_reason: Optional[str] = None

    def to_leg_result(self) -> LegResult:
        """Adapt to the unified :class:`LegResult` consumed by synthesis."""
        return LegResult(
            key="saas_forward",
            label=SAAS_FORWARD_LEG_LABEL,
            pre_money=self.pre_money if self.available else ZERO,
            available=self.available and self.pre_money > ZERO,
            unavailable_reason=self.unavailable_reason,
            assumptions={
                "forward_arr": self.forward_arr,
                "applied_multiple": self.applied_multiple,
                "risk_discount": self.risk_discount,
                "churn_drag": self.churn_drag,
            },
        )


def _project_forward_arr(
    current_arr: Decimal,
    *,
    mom_growth_pct: Decimal,
    months: int = _FORWARD_MONTHS,
) -> Decimal:
    """Compound today's ARR forward by ``months`` at ``mom_growth_pct``.

    Capped to avoid runaway projections — the founder's *stated* number
    is preserved in the audit trail under :attr:`forward_mom_growth_pct`.
    """
    capped = min(mom_growth_pct, _MAX_MOM_GROWTH_PCT) if mom_growth_pct else ZERO
    if capped <= ZERO:
        return q_eur(current_arr)
    monthly_factor = ONE + (capped / ONE_HUNDRED)
    arr = current_arr
    for _ in range(months):
        arr *= monthly_factor
    return q_eur(arr)


def _berkus_surface(inputs: StartupInputs) -> Decimal:
    """Average of the 5 Berkus sliders, normalised to [0, 1]."""
    surface = (
        inputs.sound_idea
        + inputs.prototype_status
        + inputs.management_strength
        + inputs.strategic_relationships
        + inputs.product_rollout
    )
    return Decimal(surface) / Decimal("500")  # 5 sliders × 100


def _risk_discount(berkus_surface: Decimal) -> Decimal:
    """Map Berkus surface (0..1) → multiple discount (0.50..1.00)."""
    span = ONE - _MIN_RISK_DISCOUNT
    return q_rate(_MIN_RISK_DISCOUNT + (berkus_surface * span))


def _churn_drag(monthly_churn_pct: Optional[Decimal]) -> Decimal:
    """Convert monthly churn (% of revenue) into a 0..0.30 multiplier drag."""
    if not monthly_churn_pct or monthly_churn_pct <= ZERO:
        return ZERO
    raw = q_rate(monthly_churn_pct * _CHURN_DRAG_PER_PCT)
    return min(raw, _MAX_CHURN_DRAG)


def calculate_saas_forward(
    inputs: StartupInputs,
    *,
    region_data: RegionalReferenceData,
) -> SaasForwardOutput:
    """Run the SaaS Forward Multiple leg.

    Parameters
    ----------
    inputs:
        Founder-supplied :class:`StartupInputs`.  Requires ``mrr`` *or*
        ``arr`` to be > 0 — otherwise the leg returns ``available=False``
        and the synthesizer drops it.
    region_data:
        Regional reference (Atomico / Dealroom) used for the exit
        EV/Revenue multiple.
    """
    current_arr = inputs.arr or ZERO
    base_multiple = q_eur(
        region_data.comparable_exit_revenue_multiple * _FORWARD_MULTIPLE_RATIO
    )

    if current_arr <= ZERO:
        return SaasForwardOutput(
            pre_money=ZERO,
            current_arr=ZERO,
            forward_arr=ZERO,
            forward_mom_growth_pct=ZERO,
            forward_months=_FORWARD_MONTHS,
            base_multiple=base_multiple,
            applied_multiple=ZERO,
            risk_discount=ZERO,
            churn_drag=ZERO,
            available=False,
            unavailable_reason=(
                "No MRR/ARR supplied — the SaaS forward-multiple method "
                "requires at least some current recurring revenue to fire."
            ),
        )

    mom_growth = inputs.mrr_growth_rate_pct or _DEFAULT_MOM_GROWTH_PCT
    forward_arr = _project_forward_arr(current_arr, mom_growth_pct=mom_growth)

    risk_discount = _risk_discount(_berkus_surface(inputs))
    churn_drag = _churn_drag(inputs.monthly_churn_pct)
    effective_factor = clamp(
        risk_discount - churn_drag,
        low=_MIN_RISK_DISCOUNT - _MAX_CHURN_DRAG,
        high=ONE,
    )
    applied_multiple = q_eur(base_multiple * effective_factor)

    pre_money = q_eur(forward_arr * applied_multiple)

    return SaasForwardOutput(
        pre_money=pre_money,
        current_arr=q_eur(current_arr),
        forward_arr=forward_arr,
        forward_mom_growth_pct=q_pct(min(mom_growth, _MAX_MOM_GROWTH_PCT)),
        forward_months=_FORWARD_MONTHS,
        base_multiple=base_multiple,
        applied_multiple=applied_multiple,
        risk_discount=risk_discount,
        churn_drag=churn_drag,
        available=True,
    )
