"""Venture Capital (VC) Method.

Backsolves a defensible pre-money from a Year-5 exit assumption.

**Consortium-spec formula (preferred when investment_amount_sought is known)**::

    terminal_value   = year5_revenue * exit_revenue_multiple
    post_money_today = terminal_value / target_roi_x
    pre_money_today  = post_money_today - investment_amount_sought   # consortium ask

This mirrors how angels and seed funds actually price rounds: they fix
the investor's exit-return target, work backward to today's post-money,
then carve out the round size to land on the founder's pre-money.

**Fallback formula (when investment amount is missing)**::

    pre_money_today  = post_money_today * (1 - dilution_assumption_pct)

Used for backwards compatibility with payloads that pre-date the
``investment_amount_sought`` field.

When the founder has not supplied year-5 projections, we fall back to
extrapolating from current ARR using a stage-aware compounded growth
defined in :class:`.regional_data.RegionalReferenceData`.
"""

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
from .regional_data import RegionalReferenceData, get_sector_defaults
from .schemas import StartupInputs

VC_LEG_LABEL: str = "Venture Capital Method"


@dataclass(frozen=True)
class VcOutput:
    """VC Method output."""

    pre_money: Decimal
    post_money: Decimal
    terminal_value: Decimal
    year5_revenue: Decimal
    exit_revenue_multiple: Decimal
    target_roi_x: Decimal
    dilution_pct: Decimal
    used_year5_projection: bool
    """True when the founder supplied year5_revenue_projection; False
    when we extrapolated from ARR."""
    investment_amount_sought: Decimal
    """The funding amount used to derive pre-money from post-money.
    Zero when the founder did not supply one (fallback formula used)."""
    used_investment_amount: bool
    """True when the consortium-spec subtraction formula was applied;
    False when we fell back to the dilution-percentage approximation."""
    next_round_dilution_pct: Decimal
    """Implied equity dilution if the round closes at the calculated
    pre-money. Drives the Cap Table Simulator on the founder report."""

    def to_leg_result(self) -> LegResult:
        """Adapt to the unified :class:`LegResult` consumed by synthesis."""
        if self.pre_money <= ZERO:
            return LegResult(
                key="vc",
                label=VC_LEG_LABEL,
                pre_money=ZERO,
                available=False,
                unavailable_reason=(
                    "No year-5 projection or current ARR — the VC method needs "
                    "one or the other to compute a terminal value."
                ),
            )
        return LegResult(
            key="vc",
            label=VC_LEG_LABEL,
            pre_money=self.pre_money,
            available=True,
            assumptions={
                "year5_revenue": self.year5_revenue,
                "exit_revenue_multiple": self.exit_revenue_multiple,
                "target_roi_x": self.target_roi_x,
                "investment_amount_sought": self.investment_amount_sought,
            },
        )


def _project_year5_revenue(
    inputs: StartupInputs, *, region_data: RegionalReferenceData
) -> Optional[Decimal]:
    """Extrapolate year-5 revenue from current ARR using stage growth.

    Returns ``None`` when ARR is missing or zero (engine then rejects
    the VC contribution by returning a zero-pre-money output).
    """
    if inputs.arr is None or inputs.arr <= ZERO:
        return None
    growth = region_data.default_yoy_growth_factor
    # ARR_year5 = ARR_today * (1 + growth) ^ 5
    factor = (ONE + growth) ** 5
    return q_eur(inputs.arr * factor)


def _zero_output(
    *,
    exit_multiple: Decimal,
    target_roi: Decimal,
    dilution_pct: Decimal,
    used_projection: bool,
    investment_sought: Decimal,
) -> VcOutput:
    """Build a zero-pre-money :class:`VcOutput` (leg drops out of the blend)."""
    return VcOutput(
        pre_money=ZERO,
        post_money=ZERO,
        terminal_value=ZERO,
        year5_revenue=ZERO,
        exit_revenue_multiple=exit_multiple,
        target_roi_x=target_roi,
        dilution_pct=dilution_pct,
        used_year5_projection=used_projection,
        investment_amount_sought=investment_sought,
        used_investment_amount=False,
        next_round_dilution_pct=ZERO,
    )


def calculate_vc(
    inputs: StartupInputs,
    *,
    region_data: RegionalReferenceData,
) -> VcOutput:
    """Compute the VC Method pre-money valuation.

    Falls back to regional defaults when individual VC inputs are missing.
    Returns a zero-everything VcOutput when neither year-5 projection nor
    ARR is available — synthesis will then drop this leg from the blend.
    """
    sector_defaults = get_sector_defaults(inputs.sector)

    used_projection = (
        inputs.year5_revenue_projection is not None
        and inputs.year5_revenue_projection > ZERO
    )
    year5_revenue = (
        inputs.year5_revenue_projection
        if used_projection
        else _project_year5_revenue(inputs, region_data=region_data)
    )

    # Sector-driven smart default beats the generic regional fallback so a
    # SaaS founder gets 6×, a Fintech founder gets 8×, etc.
    exit_multiple = (
        inputs.exit_revenue_multiple
        or sector_defaults.exit_revenue_multiple
        or region_data.comparable_exit_revenue_multiple
    )
    target_roi = inputs.target_roi_x or region_data.default_target_roi_x
    dilution_pct = (
        inputs.dilution_assumption_pct
        if inputs.dilution_assumption_pct is not None
        else region_data.default_dilution_pct
    )
    investment_sought = inputs.investment_amount_sought or ZERO
    use_investment = investment_sought > ZERO

    if year5_revenue is None or year5_revenue <= ZERO or target_roi <= ZERO:
        return _zero_output(
            exit_multiple=exit_multiple,
            target_roi=target_roi,
            dilution_pct=dilution_pct,
            used_projection=used_projection,
            investment_sought=investment_sought,
        )

    terminal_value = q_eur(year5_revenue * exit_multiple)
    post_money = q_eur(terminal_value / target_roi)

    if use_investment:
        # Consortium-spec: pre = post − investment.  Clamp to >= 0 so an
        # ask larger than the implied post-money produces a 0 pre-money
        # (a deliberate "you're asking too much for this stage" signal)
        # rather than a confusing negative figure.
        pre_money = q_eur(clamp(post_money - investment_sought, low=ZERO, high=post_money))
        # Implied dilution at this round.  Guard against div-by-zero when
        # post_money rounds to 0 (extremely high target_roi vs Y5 ARR).
        next_round_dilution_pct = (
            q_pct(investment_sought / post_money * ONE_HUNDRED)
            if post_money > ZERO
            else ZERO
        )
    else:
        # Fallback when no investment ask is provided: shave the
        # dilution_pct off post-money.  Preserved for backwards compat
        # with payloads predating ``investment_amount_sought``.
        dilution_factor = clamp(
            ONE - dilution_pct / ONE_HUNDRED, low=ZERO, high=ONE
        )
        pre_money = q_eur(post_money * dilution_factor)
        next_round_dilution_pct = q_pct(dilution_pct)

    return VcOutput(
        pre_money=pre_money,
        post_money=post_money,
        terminal_value=terminal_value,
        year5_revenue=q_eur(year5_revenue),
        exit_revenue_multiple=q_rate(exit_multiple),
        target_roi_x=q_rate(target_roi),
        dilution_pct=q_pct(dilution_pct),
        used_year5_projection=used_projection,
        investment_amount_sought=q_eur(investment_sought),
        used_investment_amount=use_investment,
        next_round_dilution_pct=next_round_dilution_pct,
    )
