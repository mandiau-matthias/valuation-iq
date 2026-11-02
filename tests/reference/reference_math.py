"""Pure-Python reference implementations of every M&A SME valuation method.

These are intentionally minimal and dependency-free so that:

  1. Claude (or any reviewer) can read 200 lines and verify the math
     against any textbook (Damodaran, McKinsey, Pratt's, BizBuySell).
  2. Property-based tests can compare engine output against this
     reference under tight tolerance.
  3. Reference cases under ``tests/reference/cases/*.json`` declare
     inputs + expected outputs computed *here* — pinning a regression
     net under every documented method.

Every formula carries an inline citation so that a future maintainer
or auditor can re-derive it without digging through the engine.

Conventions:
  - All money in EUR, all rates as decimals (0.10 = 10%).
  - "EV" = enterprise value, "EQ" = equity value, "Eq" used in formulas.
  - Net debt = total_debt − cash. This is the standard M&A bridge.

Methods covered:
  1. DCF — Gordon Growth + perpetuity
  2. EBITDA Multiple
  3. Revenue Multiple
  4. SDE Multiple
  5. ARR Multiple
  6. Adjusted NAV
  7. Real-estate yield / income capitalisation
  8. Fiscal 4× EBITDA (Belgian statutory anchor)
  9. Adaptive (weighted blend)
 10. Startup (Berkus / Scorecard composite, summarised)
 11. Liquidation Analysis (statement-of-affairs recovery less claims)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. DCF — Discounted Cash Flow
# ---------------------------------------------------------------------------


def free_cash_flow(
    *,
    ebit: float,
    tax_rate: float,
    depreciation: float,
    capex: float,
    nwc_change: float,
) -> float:
    """Reference free cash flow (FCF) per Damodaran ch. 3.

    FCF = EBIT × (1 − T) + D&A − CapEx − ΔNWC
    """
    return ebit * (1.0 - tax_rate) + depreciation - capex - nwc_change


def gordon_terminal_value(*, fcf_n: float, wacc: float, g: float) -> float:
    """Gordon Growth Model — McKinsey "Valuation" 7e ch. 12.

        TV = FCF_N × (1 + g) / (WACC − g),   requires WACC > g

    Raises ``ValueError`` if WACC ≤ g.
    """
    if wacc <= g:
        raise ValueError(f"Gordon model undefined when WACC ≤ g; got WACC={wacc}, g={g}")
    return fcf_n * (1.0 + g) / (wacc - g)


def discount_factor(*, wacc: float, n: float) -> float:
    """DF_N = (1 + WACC)^N"""
    return (1.0 + wacc) ** n


def present_value(*, future_value: float, wacc: float, n: float) -> float:
    """PV(FV) = FV / (1 + WACC)^N"""
    return future_value / discount_factor(wacc=wacc, n=n)


def dcf_enterprise_value(
    *,
    fcf_projections: List[float],
    wacc: float,
    terminal_growth: float,
) -> Tuple[float, float, List[float]]:
    """Full reference DCF EV.

    Returns ``(EV, PV_TV, [PV_FCF_t for t in 1..N])``.
    """
    pv_fcfs = [
        present_value(future_value=fcf, wacc=wacc, n=t + 1) for t, fcf in enumerate(fcf_projections)
    ]
    tv = gordon_terminal_value(fcf_n=fcf_projections[-1], wacc=wacc, g=terminal_growth)
    pv_tv = present_value(future_value=tv, wacc=wacc, n=len(fcf_projections))
    ev = sum(pv_fcfs) + pv_tv
    return ev, pv_tv, pv_fcfs


def dcf_equity_value(
    *,
    enterprise_value: float,
    total_debt: float,
    cash: float,
    ownership: float = 1.0,
    nwc_adjustment: float = 0.0,
) -> float:
    """Reference equity bridge for DCF (no risk discount — risk is in WACC).

        Eq = (EV − Net_Debt + NWC_adj) × Ownership

    Negative equity is clamped to 0 (matches ``methods/_shared.equity_from_ev``).
    """
    net_debt = total_debt - cash
    eq = (enterprise_value - net_debt + nwc_adjustment) * ownership
    return max(eq, 0.0) if math.isfinite(eq) else 0.0


def apv_tax_shield_value(
    *,
    tax_shield_projections: List[float],
    discount_rate: float,
    mid_year_discounting: bool = False,
) -> Tuple[float, List[float]]:
    """PV of explicit APV debt tax-shield cash flows."""
    pv_tax_shields = [
        present_value(
            future_value=tax_shield,
            wacc=discount_rate,
            n=(t + 0.5) if mid_year_discounting else (t + 1),
        )
        for t, tax_shield in enumerate(tax_shield_projections)
    ]
    return sum(pv_tax_shields), pv_tax_shields


# ---------------------------------------------------------------------------
# 2. Multiples — EBITDA, Revenue, SDE, ARR
# ---------------------------------------------------------------------------


def equity_from_ev(
    *,
    enterprise_value: float,
    total_adjustment: float,
    total_debt: float,
    cash: float,
    ownership: float = 1.0,
    nwc_adjustment: float = 0.0,
) -> float:
    """Reference EV→equity bridge for multiples.

        Eq = (EV × (1 − total_adj) − debt + cash + nwc_adj) × ownership

    ``total_adjustment`` aggregates size, liquidity, country-risk discounts
    that are NOT priced into the multiple itself. DCF must NOT use this —
    use ``dcf_equity_value`` instead (risk is already in WACC).
    """
    eq = (
        enterprise_value * (1.0 - total_adjustment) - total_debt + cash + nwc_adjustment
    ) * ownership
    return max(eq, 0.0) if math.isfinite(eq) else 0.0


def ebitda_multiple_valuation(
    *,
    ebitda: float,
    ev_ebitda_multiple: float,
    total_adjustment: float = 0.0,
    total_debt: float = 0.0,
    cash: float = 0.0,
    ownership: float = 1.0,
    nwc_adjustment: float = 0.0,
    saas_adjustment_factor: float = 1.0,
) -> float:
    """EV/EBITDA multiple → equity, with optional SaaS-quality factor."""
    if ebitda <= 0 or ev_ebitda_multiple <= 0:
        return 0.0
    ev = ebitda * ev_ebitda_multiple * saas_adjustment_factor
    return equity_from_ev(
        enterprise_value=ev,
        total_adjustment=total_adjustment,
        total_debt=total_debt,
        cash=cash,
        ownership=ownership,
        nwc_adjustment=nwc_adjustment,
    )


def revenue_multiple_valuation(
    *,
    revenue: float,
    ev_revenue_multiple: float,
    total_adjustment: float = 0.0,
    total_debt: float = 0.0,
    cash: float = 0.0,
    ownership: float = 1.0,
    nwc_adjustment: float = 0.0,
) -> float:
    """EV/Revenue multiple → equity. Used when EBITDA is unreliable."""
    if revenue <= 0 or ev_revenue_multiple <= 0:
        return 0.0
    ev = revenue * ev_revenue_multiple
    return equity_from_ev(
        enterprise_value=ev,
        total_adjustment=total_adjustment,
        total_debt=total_debt,
        cash=cash,
        ownership=ownership,
        nwc_adjustment=nwc_adjustment,
    )


def sde_valuation(
    *,
    ebitda: float,
    owner_salary_addback: float,
    sde_multiple: float,
    total_adjustment: float = 0.0,
    total_debt: float = 0.0,
    cash: float = 0.0,
    ownership: float = 1.0,
    nwc_adjustment: float = 0.0,
) -> float:
    """SDE (Seller's Discretionary Earnings) per BizBuySell 2024.

    SDE = EBITDA + Owner_Salary_Addback
    EV  = SDE × multiple
    Eq  = bridge(EV)
    """
    if ebitda <= 0:
        return 0.0
    sde = ebitda + max(owner_salary_addback, 0.0)
    ev = sde * sde_multiple
    return equity_from_ev(
        enterprise_value=ev,
        total_adjustment=total_adjustment,
        total_debt=total_debt,
        cash=cash,
        ownership=ownership,
        nwc_adjustment=nwc_adjustment,
    )


def arr_multiple_valuation(
    *,
    arr: float,
    arr_multiple: float,
    total_adjustment: float = 0.0,
    total_debt: float = 0.0,
    cash: float = 0.0,
    ownership: float = 1.0,
    nwc_adjustment: float = 0.0,
) -> float:
    """SaaS ARR multiple. Comparable transactions: EV / ARR.

    Eligibility (recurring share ≥60%, growth/retention signals) lives
    in ``saas_eligibility``; this function assumes eligibility was
    pre-checked.
    """
    if arr <= 0 or arr_multiple <= 0:
        return 0.0
    ev = arr * arr_multiple
    return equity_from_ev(
        enterprise_value=ev,
        total_adjustment=total_adjustment,
        total_debt=total_debt,
        cash=cash,
        ownership=ownership,
        nwc_adjustment=nwc_adjustment,
    )


# ---------------------------------------------------------------------------
# 3. Adjusted NAV
# ---------------------------------------------------------------------------


def adjusted_nav_valuation(
    *,
    book_equity: float,
    asset_revaluations: float = 0.0,
    deferred_tax_rate: float = 0.25,
    ownership: float = 1.0,
) -> float:
    """Reference adjusted NAV per Belgian SME practice.

        Eq = (Book_Equity + Revaluations × (1 − T_def)) × Ownership

    The deferred-tax adjustment captures the latent tax liability on
    unrealised capital gains (meerwaardebelasting). ``ownership`` is
    always applied last.
    """
    revaluations_after_tax = asset_revaluations * (1.0 - deferred_tax_rate)
    eq = (book_equity + revaluations_after_tax) * ownership
    return max(eq, 0.0)


# ---------------------------------------------------------------------------
# 4. Real-estate yield — governed income capitalisation
# ---------------------------------------------------------------------------


def real_estate_yield_valuation(
    *,
    sustainable_noi: float,
    cap_rate: float,
    property_debt: float = 0.0,
    unrestricted_cash: float = 0.0,
    nwc_adjustment: float = 0.0,
    nav_equity_floor: float | None = None,
    ownership: float = 1.0,
) -> tuple[float, float]:
    """Reference property income capitalisation and single equity bridge.

        EV = sustainable NOI / cap rate
        Full-company Eq = max(EV - property debt + cash + NWC, governed NAV floor)
        Subject Eq = Full-company Eq × ownership

    The floor is an equity floor, never an enterprise-value substitute. This
    mirrors the canonical runtime and prevents property debt being deducted
    twice when an adjusted-NAV cross-check is present.
    """
    if sustainable_noi <= 0 or cap_rate <= 0 or not 0 <= ownership <= 1:
        return 0.0, 0.0
    enterprise_value = sustainable_noi / cap_rate
    full_company_equity = enterprise_value - property_debt + unrestricted_cash + nwc_adjustment
    if nav_equity_floor is not None:
        full_company_equity = max(full_company_equity, nav_equity_floor)
    return enterprise_value, max(full_company_equity * ownership, 0.0)


# ---------------------------------------------------------------------------
# 5. Fiscal 4× — Belgian statutory anchor
# ---------------------------------------------------------------------------


def fiscal_4x_valuation(
    *,
    ebitda: float,
    book_equity: float,
    ownership: float = 1.0,
) -> float:
    """Belgian fiscal calculation reference; applicability is not established here.

        Eq = (Book_Equity + 4 × EBITDA) × Ownership

    This helper reproduces the arithmetic only, not tax-law eligibility or
    market valuation. EBITDA must be > 0 for the formula to apply.
    """
    if ebitda <= 0:
        return 0.0
    eq = (book_equity + 4.0 * ebitda) * ownership
    return max(eq, 0.0)


# ---------------------------------------------------------------------------
# 6. Adaptive — weighted blend of primary methods
# ---------------------------------------------------------------------------


@dataclass
class WeightedMethod:
    """One method's contribution to the adaptive blend."""

    method_key: str
    equity_value: float
    weight: float


def adaptive_blend(*, methods: List[WeightedMethod]) -> float:
    """Reference adaptive blend.

        Eq = Σ(method_eq_i × w_i)   where Σ w_i = 1.0

    Weights are normalised if they don't sum to exactly 1.0 (within 1e-6
    tolerance — we forgive bank-rounding drift).
    """
    if not methods:
        return 0.0
    total_weight = sum(m.weight for m in methods)
    if total_weight <= 0:
        return 0.0
    if abs(total_weight - 1.0) > 1e-6:
        # Normalise — caller might have un-renormalised weights post-clamp.
        norm = 1.0 / total_weight
        methods = [
            WeightedMethod(
                method_key=m.method_key,
                equity_value=m.equity_value,
                weight=m.weight * norm,
            )
            for m in methods
        ]
    return sum(m.equity_value * m.weight for m in methods)


# ---------------------------------------------------------------------------
# 7. Startup — Berkus + Scorecard composite (simplified)
# ---------------------------------------------------------------------------


def berkus_pre_money(
    *,
    sound_idea_pct: int,  # 0–100
    prototype_pct: int,
    management_pct: int,
    relationships_pct: int,
    rollout_pct: int,
    max_per_factor: float = 500_000.0,
) -> float:
    """Berkus method (Berkus 2009) — common pre-money cap of €2.5M.

    Each of 5 qualitative factors contributes up to ``max_per_factor``
    (default €500k → €2.5M total cap).
    """
    factors_pct = [
        sound_idea_pct,
        prototype_pct,
        management_pct,
        relationships_pct,
        rollout_pct,
    ]
    return sum(max_per_factor * (pct / 100.0) for pct in factors_pct)


def scorecard_pre_money(
    *,
    base_pre_money: float,
    opportunity_size: float = 1.0,
    competitive: float = 1.0,
    sales_marketing: float = 1.0,
    funding_need: float = 1.0,
    other_factors: float = 1.0,
    weights: Optional[Tuple[float, float, float, float, float]] = None,
) -> float:
    """Scorecard method (Payne 2011).

        Adjusted_Pre = Base × Σ(weight_i × factor_i)

    Default weights from the original paper:
        Strength of management team:    0.30   (here: opportunity_size proxy)
        Size of opportunity:            0.25
        Strength of product/tech:       0.15   (here: competitive proxy)
        Competitive environment:        0.10
        Marketing/Sales/Partnerships:   0.10
        Need for additional investment: 0.05
        Other:                          0.05
    """
    w = weights or (0.30, 0.25, 0.15, 0.15, 0.15)
    factors = (opportunity_size, competitive, sales_marketing, funding_need, other_factors)
    multiplier = sum(wi * fi for wi, fi in zip(w, factors))
    return base_pre_money * multiplier


def startup_composite_pre_money(
    *,
    berkus_value: float,
    scorecard_value: float,
    berkus_weight: float = 0.5,
    scorecard_weight: float = 0.5,
) -> float:
    """Startup pre-money composite.

        PreMoney = Berkus × w_b + Scorecard × w_s

    This deliberately stays narrower than the production startup engine,
    which may add VC and SaaS-forward legs when revenue/ARR signals exist.
    The reference corpus uses this clean two-leg version as an accountant-
    reviewable floor for pre-revenue / seed-stage cases.
    """
    return adaptive_blend(
        methods=[
            WeightedMethod("berkus", berkus_value, berkus_weight),
            WeightedMethod("scorecard", scorecard_value, scorecard_weight),
        ]
    )


# ---------------------------------------------------------------------------
# 8. Liquidation Analysis — downside premise of value
# ---------------------------------------------------------------------------


def liquidation_equity_value(
    *,
    asset_recoveries: List[dict],
    secured_debt: float = 0.0,
    unsecured_liabilities: float = 0.0,
    wind_down_costs: float = 0.0,
    tax_leakage: float = 0.0,
    rate_key: str = "orderly_recovery_rate",
    ownership: float = 1.0,
) -> float:
    """Statement-of-affairs liquidation equity.

        Eq = (Σ asset_book_i × recovery_i − claims − wind_down − tax) × ownership

    This is the audit-friendly core of IVS 104's liquidation premise of
    value. The production engine adds creditor cascades, PV schedules,
    sensitivity, disclosures and legal packs; this reference formula pins
    the irreducible accountant/lawyer arithmetic.
    """
    gross_realisable_assets = sum(
        float(row["book_value"]) * float(row.get(rate_key, 0.0)) for row in asset_recoveries
    )
    claims = secured_debt + unsecured_liabilities
    equity = (gross_realisable_assets - claims - wind_down_costs - tax_leakage) * ownership
    return max(equity, 0.0) if math.isfinite(equity) else 0.0


# ---------------------------------------------------------------------------
# 9. Convenience: complete reference report shape
# ---------------------------------------------------------------------------


@dataclass
class ReferenceValuation:
    """A reference-grade valuation snapshot — what a textbook example would look like."""

    company_name: str
    country_code: str
    revenue: float
    ebitda: float
    total_debt: float
    cash: float
    ownership: float

    # Method outputs
    dcf_equity: Optional[float] = None
    ebitda_equity: Optional[float] = None
    revenue_equity: Optional[float] = None
    sde_equity: Optional[float] = None
    arr_equity: Optional[float] = None
    nav_equity: Optional[float] = None
    fiscal_4x_equity: Optional[float] = None
    startup_equity: Optional[float] = None

    # Synthesis
    adaptive_equity: Optional[float] = None
    weights: dict = field(default_factory=dict)

    def methods_available(self) -> List[str]:
        """Methods that produced a non-None positive equity value."""
        candidates = {
            "dcf": self.dcf_equity,
            "ebitda_multiple": self.ebitda_equity,
            "revenue_multiple": self.revenue_equity,
            "sde": self.sde_equity,
            "arr_multiple": self.arr_equity,
            "adjusted_nav": self.nav_equity,
            "fiscal_4x": self.fiscal_4x_equity,
            "startup": self.startup_equity,
        }
        return [k for k, v in candidates.items() if v is not None and v > 0]
