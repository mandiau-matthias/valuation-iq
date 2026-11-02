"""Advisor M&A analysis report sections (ValuationIQ engine).

Productized from the advisor advisor benchmark. These ADDITIVE,
NON-WEIGHTED analysis pages answer M&A-advisor feedback (Jan Vandenberghe /
advisor) that the engine's core report did not natively surface:

  * growth x multiple sensitivity            (feedback #6)
  * indicative DCF cross-check               (feedback #3 — multiples-primary dossiers)
  * equivalent-WACC reconciliation           (feedback #5 — yield/asset dossiers)

Design invariants
-----------------
* They render ONLY for advisor-audience reports (``report_audience == 'advisor'``)
  and are individually gated on data availability, so consumer self-service
  reports are completely unaffected.
* They are computed entirely in the REPORT layer from the already-aggregated
  ``context`` (+ the request for historical revenue) and NEVER feed the weighted
  method synthesis. The ten valuation methods (solo and weighted together) are
  untouched — these are presentation-only analysis pages.
* Every section self-skips on missing inputs, so a DB-down / partial run still
  renders a valid report (graceful degradation) rather than failing.

The page flags this module sets in ``context`` (``show_growth_multiple_sensitivity``,
``show_dcf_crosscheck``, ``show_equivalent_wacc``) are read
by ``report_pagination.build_sme_report_page_flags`` to drive the manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.services.infrastructure.template_formatter import TemplateFormatter

# ───────────────────────────── numeric coercion ──────────────────────────────


def _num(value: Any) -> float:
    """Coerce Decimal/float/int/str/None to float; never raises."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _cy(context: dict, key: str) -> float:
    """Read a numeric field off ``current_year_data`` (dict or model)."""
    cy = context.get("current_year_data")
    if isinstance(cy, dict):
        return _num(cy.get(key))
    return _num(getattr(cy, key, None))


def _req_cy(request: Any, key: str) -> float:
    """Read a numeric field off the request's current-year input.

    The granular balance-sheet/P&L fields (depreciation, cash, AR/inventory/AP,
    total_debt) live on ``request.current_year_data`` (the YearDataInput), NOT on
    the aggregated ``context['current_year_data']`` dict, which only carries the
    headline figures. The DCF cross-check needs the granular fields, so it sources
    them here.
    """
    cy = getattr(request, "current_year_data", None)
    if cy is None:
        return 0.0
    return _num(getattr(cy, key, None))


@dataclass(frozen=True)
class _AdvisorDisplay:
    """Presentation only; all calculation inputs remain numeric."""

    locale: str = "nl"
    currency: str = "EUR"

    def decimal(self, value: float, places: int = 1) -> str:
        label = f"{value:.{places}f}"
        return label.replace(".", ",") if self.locale.lower().startswith(("nl", "fr")) else label

    def full(self, value: float) -> str:
        return TemplateFormatter.format_currency(round(_num(value)), self.currency, self.locale)

    def compact(self, value: float) -> str:
        return TemplateFormatter.format_currency_compact(value, self.currency, self.locale)

    def pct(self, value: float, places: int = 1) -> str:
        return f"{self.decimal(value, places)}%"

    def pp(self, value: float, places: int = 1) -> str:
        return f"{self.decimal(value, places)}pp"

    def multiple(self, value: float, places: int = 2) -> str:
        return f"{self.decimal(value, places)}×"


# ─────────────────────────────── shared helpers ──────────────────────────────


def _history_revenue_cagr(request: Any) -> float:
    """Geometric revenue CAGR across the full actuals series.

    Spans the earliest historical year THROUGH the current (latest) year, so a
    recent decline is not masked by an earlier rise (e.g. a distributor that
    grew 2022→2023 then fell back in 2024 reads ~flat, not +13%). Clamped to
    [-2%, +7%]; defaults to +2% when fewer than two positive-revenue years exist.
    """
    rows: list[tuple[int, float]] = []
    years = list(getattr(request, "historical_years_data", None) or [])
    current = getattr(request, "current_year_data", None)
    if current is not None:
        years = years + [current]
    for h in years:
        rev = _num(getattr(h, "revenue", None))
        year = getattr(h, "year", None) or getattr(h, "fiscal_year", None)
        if rev > 0 and year:
            rows.append((int(year), rev))
    if len(rows) < 2:
        return 0.02
    rows.sort()
    (first_y, first_r), (last_y, last_r) = rows[0], rows[-1]
    years = max(1, last_y - first_y)
    if first_r <= 0 or last_r <= 0:
        return 0.02
    return _clamp((last_r / first_r) ** (1 / years) - 1, -0.02, 0.07)


# DCF cross-check is only informative above this revenue materiality threshold;
# below it (small owner-operator SMEs) a multiples-only dossier is the honest
# deliverable and asserting a DCF/WACC/FCFF chain would be a phantom claim.
_DCF_CROSSCHECK_MIN_REVENUE = 5_000_000.0


@dataclass(frozen=True)
class _DcfCrosscheckInputs:
    applied: float
    revenue: float
    ebitda: float
    net_debt: float
    multiples_ev: float
    fiscal_year: int
    gross_debt: float
    equity_value: float


@dataclass(frozen=True)
class _DcfCrosscheckAssumptions:
    terminal_growth: float
    tax_rate: float
    risk_free: float
    equity_risk_premium: float
    beta: float
    size_premium: float
    company_specific_risk: float
    cost_of_equity: float
    cost_of_debt: float
    debt_weight: float
    equity_weight: float
    wacc: float
    growth_path: list[float]
    margin: float
    depreciation_pct: float
    capex_pct: float
    nwc_pct: float


# ─────────────────────────── section #6: growth × multiple ────────────────────


def _build_growth_multiple(context: dict, cagr: float, locale: str = "nl") -> Optional[dict]:
    """Omzetgroei x EV/EBITDA sensitivity around the run-rate EBITDA basis."""
    applied = _num(context.get("applied_multiple"))
    ebitda = _num(context.get("sustainable_ebitda"))
    revenue = _num(context.get("revenue"))
    if applied <= 0 or ebitda <= 0:
        return None  # not a multiples-primary dossier (e.g. yield/asset) — skip

    # This is a MARKET-multiple sensitivity: it always brackets the applied
    # EV/EBITDA multiple and its real benchmark band. On a weighted/hybrid headline
    # it therefore reconciles to the MARKET LEG (EBITDA × applied), NOT the blended
    # headline — the headline also carries the separately-weighted DCF leg (shown in
    # the DCF chapter). Forcing the centre to the blended implied multiple (headline
    # EV ÷ EBITDA) so the Basis cell equalled the headline printed, for a DCF-heavy
    # blend, an EV/EBITDA the market never supported AND — paired with the market
    # low/high — an incoherent non-monotonic band (IJsjes: 2.27× / 8.73× / 3.98×).
    # Bracket the market multiple; the caption reconciles to the market leg.
    reconciles_to_headline = not bool(context.get("has_weighted_synthesis"))

    low = _num(context.get("multiple_low")) or round(applied * 0.78, 2)
    high = _num(context.get("multiple_high")) or round(applied * 1.30, 2)
    # Never let the band invert around the applied multiple — a market low/high can
    # straddle it oddly; the grid must always read low ≤ applied ≤ high.
    low = min(low, applied)
    high = max(high, applied)
    band = [low, applied, high]

    # Symmetric +/- growth band around zero so the central "Basis" row sits at the
    # market-leg EV (no growth applied) and the Downside row is strictly below it.
    # EBITDA per scenario = run-rate basis x (1 +/- growth).
    delta = _clamp(abs(cagr) if cagr else 0.03, 0.02, 0.05)
    scenarios = (("Downside", -delta), ("Basis", 0.0), ("Upside", +delta))

    display = _AdvisorDisplay(locale, str(context.get("currency") or "EUR"))

    rows = []
    for label, growth in scenarios:
        proj_revenue = revenue * (1 + growth)
        proj_ebitda = ebitda * (1 + growth)
        rows.append(
            {
                "label": label,
                "is_basis": label == "Basis",
                "growth": f"{display.decimal(growth * 100)}%",
                "revenue": display.compact(proj_revenue),
                "ebitda": display.compact(proj_ebitda),
                "cells": [display.compact(proj_ebitda * m) for m in band],
            }
        )

    margin = _clamp(ebitda / revenue, 0.01, 0.40) if revenue > 0 else 0.0
    return {
        "currency": display.currency,
        "band_labels": [f"{display.decimal(m, 2)}×" for m in band],
        "rows": rows,
        "delta_pct": f"{display.decimal(delta * 100)}%",
        "margin_pct": display.pct(margin * 100, 1),
        "is_hybrid": bool(context.get("has_dcf"))
        and context.get("dcf_method_available") is not False
        and not bool(context.get("is_adaptive_multiples_only")),
        "reconciles_to_headline": reconciles_to_headline,
    }


# ─────────────────────────── section #3: DCF cross-check ──────────────────────


def _dcf_crosscheck_inputs(context: dict, request: Any) -> Optional[_DcfCrosscheckInputs]:
    if context.get("is_asset_methodology") or context.get("is_yield_methodology"):
        return None
    if context.get("has_dcf"):
        return None

    applied = _num(context.get("applied_multiple"))
    revenue = _num(context.get("revenue"))
    ebitda = _num(context.get("sustainable_ebitda"))
    if applied <= 0 or ebitda <= 0 or revenue < _DCF_CROSSCHECK_MIN_REVENUE:
        return None

    net_debt = _num(context.get("net_debt"))
    multiples_ev = _num(context.get("enterprise_value_mid")) or (applied * ebitda)
    fiscal_year = int(_req_cy(request, "year")) if _req_cy(request, "year") else 2024
    cash = _req_cy(request, "cash")
    gross_debt = _req_cy(request, "total_debt") or max(0.0, net_debt + cash)
    equity_value = _num(context.get("equity_value")) or max(1.0, multiples_ev - net_debt)
    return _DcfCrosscheckInputs(
        applied=applied,
        revenue=revenue,
        ebitda=ebitda,
        net_debt=net_debt,
        multiples_ev=multiples_ev,
        fiscal_year=fiscal_year,
        gross_debt=gross_debt,
        equity_value=equity_value,
    )


def _size_premium_for_revenue(revenue: float) -> float:
    if revenue < 3_000_000:
        return 0.040
    if revenue < 10_000_000:
        return 0.030
    return 0.020


def _dcf_crosscheck_assumptions(
    inputs: _DcfCrosscheckInputs,
    request: Any,
    cagr: float,
) -> _DcfCrosscheckAssumptions:
    terminal_growth = 0.015
    tax_rate = 0.25
    risk_free = 0.031
    equity_risk_premium = 0.062
    beta = 1.05
    size_premium = _size_premium_for_revenue(inputs.revenue)
    company_specific_risk = 0.010
    cost_of_equity = risk_free + beta * equity_risk_premium + size_premium + company_specific_risk
    cost_of_debt = 0.055
    debt_weight = _clamp(
        inputs.gross_debt / max(inputs.equity_value + inputs.gross_debt, 1.0),
        0.0,
        0.35,
    )
    equity_weight = 1.0 - debt_weight
    wacc = _clamp(
        cost_of_equity * equity_weight + cost_of_debt * (1 - tax_rate) * debt_weight,
        0.085,
        0.145,
    )
    depreciation_pct = _clamp(
        _req_cy(request, "depreciation") / inputs.revenue if inputs.revenue else 0.0,
        0.005,
        0.04,
    )
    nwc = (
        _req_cy(request, "accounts_receivable")
        + _req_cy(request, "inventory")
        - _req_cy(request, "accounts_payable")
    )
    return _DcfCrosscheckAssumptions(
        terminal_growth=terminal_growth,
        tax_rate=tax_rate,
        risk_free=risk_free,
        equity_risk_premium=equity_risk_premium,
        beta=beta,
        size_premium=size_premium,
        company_specific_risk=company_specific_risk,
        cost_of_equity=cost_of_equity,
        cost_of_debt=cost_of_debt,
        debt_weight=debt_weight,
        equity_weight=equity_weight,
        wacc=wacc,
        growth_path=[
            _clamp(cagr, -0.01, 0.06),
            _clamp(cagr * 0.80, 0.00, 0.05),
            _clamp(cagr * 0.60, 0.00, 0.04),
            0.025,
            0.020,
        ],
        margin=_clamp(inputs.ebitda / inputs.revenue, 0.02, 0.35),
        depreciation_pct=depreciation_pct,
        capex_pct=max(depreciation_pct, 0.012),
        nwc_pct=_clamp(nwc / inputs.revenue if inputs.revenue else 0.0, 0.03, 0.18),
    )


def _dcf_forecast(
    inputs: _DcfCrosscheckInputs,
    assumptions: _DcfCrosscheckAssumptions,
    display: _AdvisorDisplay,
) -> tuple[list[dict], list[float], list[float], float, float, float]:
    rows: list[dict] = []
    fcf: list[float] = []
    pv_fcf: list[float] = []
    forecast_revenue = inputs.revenue
    prior_revenue = inputs.revenue

    for idx, growth in enumerate(assumptions.growth_path, start=1):
        forecast_revenue *= 1 + growth
        projected_ebitda = forecast_revenue * assumptions.margin
        depreciation = forecast_revenue * assumptions.depreciation_pct
        ebit = projected_ebitda - depreciation
        taxes = max(0.0, ebit * assumptions.tax_rate)
        capex = forecast_revenue * assumptions.capex_pct
        nwc_change = max(0.0, (forecast_revenue - prior_revenue) * assumptions.nwc_pct)
        free_cash_flow = ebit - taxes + depreciation - capex - nwc_change
        pv = free_cash_flow / ((1 + assumptions.wacc) ** (idx - 0.5))
        rows.append(
            {
                "year": str(inputs.fiscal_year + idx),
                "growth": display.pct(growth * 100, 1),
                "revenue": display.compact(forecast_revenue),
                "ebitda": display.compact(projected_ebitda),
                "fcf": display.compact(free_cash_flow),
                "pv": display.compact(pv),
            }
        )
        fcf.append(free_cash_flow)
        pv_fcf.append(pv)
        prior_revenue = forecast_revenue

    terminal_fcf = fcf[-1] * (1 + assumptions.terminal_growth)
    terminal_value = terminal_fcf / max(assumptions.wacc - assumptions.terminal_growth, 0.01)
    # Mid-year convention throughout: explicit FCFs discount at (t - 0.5), so
    # the terminal value must discount at (N - 0.5) too.
    pv_terminal = terminal_value / ((1 + assumptions.wacc) ** (len(fcf) - 0.5))
    enterprise_value = sum(pv_fcf) + pv_terminal
    return rows, fcf, pv_fcf, terminal_value, pv_terminal, enterprise_value


def _dcf_sensitivity_matrix(
    *,
    fcf: list[float],
    wacc: float,
    terminal_growth: float,
    display: _AdvisorDisplay,
) -> tuple[list[dict], list[str]]:
    wacc_values = [wacc - 0.01, wacc, wacc + 0.01]
    growth_values = [0.010, terminal_growth, 0.020]
    matrix = []
    for w in wacc_values:
        cells = []
        for g in growth_values:
            tv = fcf[-1] * (1 + g) / max(w - g, 0.01)
            ev = sum(v / ((1 + w) ** (i + 0.5)) for i, v in enumerate(fcf)) + tv / (
                (1 + w) ** (len(fcf) - 0.5)
            )
            cells.append(display.compact(ev))
        matrix.append({"wacc": display.pct(w * 100, 1), "cells": cells})
    return matrix, [display.pct(g * 100, 1) for g in growth_values]


def _dcf_wacc_buildup(assumptions: _DcfCrosscheckAssumptions, display: _AdvisorDisplay) -> dict:
    return {
        "risk_free": display.pct(assumptions.risk_free * 100, 1),
        "beta": display.decimal(assumptions.beta, 2),
        "erp": display.pct(assumptions.equity_risk_premium * 100, 1),
        "size_premium": display.pct(assumptions.size_premium * 100, 1),
        "company_specific": display.pct(assumptions.company_specific_risk * 100, 1),
        "cost_of_equity": display.pct(assumptions.cost_of_equity * 100, 1),
        "cost_of_debt": display.pct(assumptions.cost_of_debt * 100, 1),
        "cost_of_debt_after_tax": display.pct(
            assumptions.cost_of_debt * (1 - assumptions.tax_rate) * 100,
            1,
        ),
        "debt_weight": display.pct(assumptions.debt_weight * 100, 0),
        "equity_weight": display.pct(assumptions.equity_weight * 100, 0),
    }


def _build_dcf_crosscheck(
    context: dict, request: Any, cagr: float, locale: str = "nl"
) -> Optional[dict]:
    """Deterministic, assumption-led DCF cross-check for multiples-primary cases.

    NON-WEIGHTED: an independent triangulation of the multiples headline, not a
    blended method. Ported from the panel-approved benchmark math (FCFF + CAPM
    build-up + Gordon terminal value + WACC x terminal-growth sensitivity). The
    granular P&L/balance-sheet drivers (depreciation, cash, NWC) come from the
    request's current-year input; net_debt and equity use the canonical engine
    context so the equity bridge ties to the headline.
    """
    # Only for operating, multiples-primary dossiers where the engine did NOT
    # already render a native (weighted) DCF chapter.
    inputs = _dcf_crosscheck_inputs(context, request)
    if inputs is None:
        return None

    display = _AdvisorDisplay(locale, str(context.get("currency") or "EUR"))
    assumptions = _dcf_crosscheck_assumptions(inputs, request, cagr)
    rows, fcf, pv_fcf, terminal_value, pv_terminal, enterprise_value = _dcf_forecast(
        inputs,
        assumptions,
        display,
    )
    matrix, matrix_growth_labels = _dcf_sensitivity_matrix(
        fcf=fcf,
        wacc=assumptions.wacc,
        terminal_growth=assumptions.terminal_growth,
        display=display,
    )
    delta_vs_multiples = (
        (enterprise_value - inputs.multiples_ev) / inputs.multiples_ev
        if inputs.multiples_ev
        else 0.0
    )
    implied_multiple = enterprise_value / inputs.ebitda if inputs.ebitda else 0.0
    component_total = round(sum(pv_fcf)) + round(pv_terminal)
    return {
        "rows": rows,
        "wacc_pct": display.pct(assumptions.wacc * 100, 1),
        "terminal_growth_pct": display.pct(assumptions.terminal_growth * 100, 1),
        # Sum-of-displayed convention: the printed total must equal the sum of
        # the printed components to the euro (independent rounding produced a
        # €1 footing miss — the first check a reviewer runs on this row).
        "enterprise_value": display.full(component_total),
        "equity_value": display.full(component_total - round(inputs.net_debt)),
        "pv_explicit": display.full(round(sum(pv_fcf))),
        "pv_terminal": display.full(round(pv_terminal)),
        "terminal_value": display.full(terminal_value),
        "multiples_ev": display.full(inputs.multiples_ev),
        "delta_vs_multiples_pct": display.pct(delta_vs_multiples * 100, 1),
        "implied_multiple": display.multiple(implied_multiple, 1),
        "applied_multiple": display.multiple(inputs.applied, 1),
        "dcf_above": delta_vs_multiples > 0,
        # "Broadly corroborates" when within ±25% — a normal DCF-vs-multiple band
        # for a stable cash generator; the market multiple stays the headline.
        "corroborates": abs(delta_vs_multiples) <= 0.25,
        "matrix": matrix,
        "matrix_growth_labels": matrix_growth_labels,
        "wacc_buildup": _dcf_wacc_buildup(assumptions, display),
    }


# ───────────────────────── section #5: equivalent WACC ────────────────────────


def _build_equivalent_wacc(context: dict, request: Any, locale: str = "nl") -> Optional[dict]:
    """Implied property discount rate = cap-rate + rental growth, vs group WACC.

    Single-entity reconciliation for a yield/asset dossier (Gordon perpetuity:
    value = NOI / (r - g) => cap-rate = r - g => r = cap-rate + g). Decoupled
    from the multi-entity SOTP bridge.
    """
    if not context.get("is_yield_methodology"):
        return None
    # ONE NOI everywhere (panel blocker B10): the yield ENGINE capitalises
    # EBITDA (operating-only NOI — revenue−opex used to leak 75x financial
    # income into the capitalised rent), so this page must use the SAME basis
    # or the implied cap-rate contradicts the headline yield pipeline on a
    # facing page. Fall back to revenue − opex only when EBITDA is absent.
    noi = _num(context.get("sustainable_ebitda"))
    if noi <= 0:
        revenue = _num(context.get("revenue"))
        opex = _req_cy(request, "operating_expenses")
        noi = max(0.0, revenue - opex) if revenue > 0 and opex > 0 else 0.0
    property_value = _num(context.get("enterprise_value_mid")) or _num(context.get("equity_value"))
    if noi <= 0 or property_value <= 0:
        return None

    cap_rate = _clamp(noi / property_value, 0.02, 0.12)
    rental_growth = 0.015
    implied_discount = cap_rate + rental_growth
    opco_wacc = 0.10  # CAPM-build-up reference (cf. operating-company DCF)
    spread = opco_wacc - implied_discount
    display = _AdvisorDisplay(locale, str(context.get("currency") or "EUR"))
    return {
        "cap_rate_pct": display.pct(cap_rate * 100, 1),
        "rental_growth_pct": display.pct(rental_growth * 100, 1),
        "implied_discount_pct": display.pct(implied_discount * 100, 1),
        "opco_wacc_pct": display.pct(opco_wacc * 100, 1),
        "spread_pp": display.pp(spread * 100, 1),
        "noi": display.full(noi),
        "property_value": display.full(property_value),
    }


# ───────────────────────────────── entrypoint ────────────────────────────────


def build_advisor_analysis_context(
    context: dict,
    *,
    response: Any = None,
    request: Any = None,
    locale: str = "nl",
) -> None:
    """Populate advisor analysis sections + their page flags on ``context``.

    No-op (flags stay False) unless ``report_audience == 'advisor'``. Mutates
    ``context`` in place; must run BEFORE ``finalize_report_context`` so the
    flags drive the SME report manifest.
    """
    # Default every flag off so the manifest gates are always defined.
    context.setdefault("show_growth_multiple_sensitivity", False)
    context.setdefault("show_dcf_crosscheck", False)
    context.setdefault("show_equivalent_wacc", False)

    if str(context.get("report_audience") or "").strip().lower() != "advisor":
        return

    cagr = _history_revenue_cagr(request)

    growth_multiple = _build_growth_multiple(context, cagr, locale)
    if growth_multiple:
        context["advisor_growth_multiple"] = growth_multiple
        context["show_growth_multiple_sensitivity"] = True

    dcf_crosscheck = _build_dcf_crosscheck(context, request, cagr, locale)
    if dcf_crosscheck:
        context["advisor_dcf_crosscheck"] = dcf_crosscheck
        context["show_dcf_crosscheck"] = True

    equivalent_wacc = _build_equivalent_wacc(context, request, locale)
    if equivalent_wacc:
        context["advisor_equivalent_wacc"] = equivalent_wacc
        context["show_equivalent_wacc"] = True
