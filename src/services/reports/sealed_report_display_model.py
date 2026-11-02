"""Build the immutable presentation projection consumed by sealed templates.

The calculation engine remains authoritative. This module only derives display
rows (weights, bridge subtotals, ratios and chart inputs) once, in typed Python,
so Jinja never becomes a second calculation engine.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation


class SealedDisplayModelError(ValueError):
    pass


def _number(value: object, *, default: Decimal | None = None) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return default
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default
    return result if result.is_finite() else default


def _row_value(row: object, key: str, default: object = None) -> object:
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def _normalized_weights(context: Mapping[str, object]) -> dict[str, object]:
    market = _number(
        context.get(
            "adaptive_presentation_multiples_weight", context.get("multiples_weight")
        ),
        default=Decimal("0"),
    ) or Decimal("0")
    dcf = _number(
        context.get("adaptive_presentation_dcf_weight", context.get("dcf_weight")),
        default=Decimal("0"),
    ) or Decimal("0")
    total = market + dcf
    if total <= 0:
        return {"market_pct": None, "dcf_pct": None}
    market_pct = (market / total * Decimal("100")).quantize(Decimal("1"))
    return {"market_pct": int(market_pct), "dcf_pct": 100 - int(market_pct)}


def _dcf_projection_rows(context: Mapping[str, object]) -> list[dict[str, object]]:
    rows = context.get("dcf_projection_detail")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return []
    wacc = _number(context.get("dcf_wacc"), default=Decimal("0")) or Decimal("0")
    if wacc <= Decimal("-1"):
        raise SealedDisplayModelError("DCF display requires WACC greater than -100%")
    mid_year = context.get("dcf_mid_year_discounting") is not False
    pv_values = context.get("dcf_pv_fcf_projections")
    pv_rows = (
        pv_values
        if isinstance(pv_values, Sequence)
        and not isinstance(pv_values, (str, bytes, bytearray))
        else []
    )
    projected: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        revenue = _number(_row_value(row, "revenue"), default=Decimal("0")) or Decimal(
            "0"
        )
        ebitda = _number(_row_value(row, "ebitda"), default=Decimal("0")) or Decimal(
            "0"
        )
        ebit = _number(_row_value(row, "ebit"), default=Decimal("0")) or Decimal("0")
        exponent = Decimal(index) + (Decimal("0.5") if mid_year else Decimal("1"))
        discount_factor = Decimal("1") / ((Decimal("1") + wacc) ** exponent)
        projected.append(
            {
                "year": _row_value(row, "year"),
                "revenue": revenue,
                "ebitda": ebitda,
                "ebit": ebit,
                "taxes": _number(_row_value(row, "taxes"), default=Decimal("0")),
                "capex": _number(_row_value(row, "capex"), default=Decimal("0")),
                "nwc_change": _number(_row_value(row, "nwc_change")),
                "free_cash_flow": _number(
                    _row_value(row, "free_cash_flow"), default=Decimal("0")
                ),
                "present_value_free_cash_flow": _number(
                    pv_rows[index] if index < len(pv_rows) else None,
                    default=Decimal("0"),
                ),
                "growth_pct": (
                    _number(_row_value(row, "growth_rate"), default=Decimal("0"))
                    or Decimal("0")
                )
                * Decimal("100"),
                "margin_pct": (ebitda / revenue * Decimal("100"))
                if revenue
                else Decimal("0"),
                "depreciation_amortization": abs(ebitda - ebit),
                "discount_factor": discount_factor,
            }
        )
    return projected


def _multi_year_ebitda(context: Mapping[str, object]) -> dict[str, object]:
    raw_rows = context.get("multi_year_ebitda")
    if not isinstance(raw_rows, Sequence) or isinstance(
        raw_rows, (str, bytes, bytearray)
    ):
        return {"rows": [], "has_outlier": False, "recurring_reference": None}
    values = [
        _number(_row_value(row, "normalized_ebitda"), default=Decimal("0"))
        or Decimal("0")
        for row in raw_rows
    ]
    total = sum(values, Decimal("0"))
    suppress = bool(context.get("suppress_outlier_exclusion"))
    flags = [
        not suppress
        and len(values) >= 3
        and total > 0
        and value > total * Decimal("0.55")
        for value in values
    ]
    recurring_values = [
        value for value, excluded in zip(values, flags, strict=True) if not excluded
    ]
    has_outlier = any(flags)
    recurring_reference = (
        sum(recurring_values, Decimal("0")) / Decimal(len(recurring_values))
        if has_outlier and recurring_values
        else _number(
            context.get("weighted_ebitda_total", context.get("sustainable_ebitda"))
        )
    )
    equal_weight_pct = (
        Decimal("100") / Decimal(len(recurring_values)) if recurring_values else None
    )
    rows: list[dict[str, object]] = []
    for row, value, excluded in zip(raw_rows, values, flags, strict=True):
        source = dict(row) if isinstance(row, Mapping) else dict(vars(row))
        weight = _number(_row_value(row, "weight"), default=Decimal("0")) or Decimal(
            "0"
        )
        source.update(
            {
                "sealed_is_nonrecurring": excluded,
                "sealed_weight_pct": (
                    None
                    if excluded
                    else equal_weight_pct
                    if has_outlier
                    else weight * Decimal("100")
                ),
                "sealed_weighted_contribution": (
                    None
                    if excluded
                    else value / Decimal(len(recurring_values))
                    if has_outlier and recurring_values
                    else value * weight
                ),
            }
        )
        rows.append(source)
    return {
        "rows": rows,
        "has_outlier": has_outlier,
        "recurring_reference": recurring_reference,
    }


def build_sealed_report_display_model(context: dict[str, object]) -> dict[str, object]:
    weights = _normalized_weights(context)
    metric_type = str(context.get("multiple_metric_type") or "EBITDA").upper()
    metric_basis = _number(
        context.get("revenue")
        if metric_type == "REVENUE"
        else context.get("sustainable_ebitda")
    )
    multiples_leg_ev = _number(
        context.get("ev_revenue_enterprise_value")
        if metric_type == "REVENUE"
        else context.get("ev_ebitda_enterprise_value")
    )
    applied_multiple = _number(context.get("applied_multiple"))
    if (
        multiples_leg_ev is None
        and metric_basis is not None
        and applied_multiple is not None
    ):
        multiples_leg_ev = metric_basis * applied_multiple
    sustainable_ebitda = _number(context.get("sustainable_ebitda"))
    ebitda_crosscheck_ev = _number(context.get("ev_ebitda_enterprise_value"))
    revenue = _number(context.get("revenue"))
    net_income = _number(context.get("net_income"))
    equity_value = _number(context.get("equity_value"))

    dcf_ev = _number(context.get("dcf_enterprise_value"))
    pv_values = context.get("dcf_pv_fcf_projections")
    pv_explicit = (
        sum(
            (
                _number(value, default=Decimal("0")) or Decimal("0")
                for value in pv_values
            ),
            Decimal("0"),
        )
        if isinstance(pv_values, Sequence)
        and not isinstance(pv_values, (str, bytes, bytearray))
        else Decimal("0")
    )
    pv_terminal = _number(
        context.get("dcf_pv_terminal_value"), default=Decimal("0")
    ) or Decimal("0")
    terminal_pct = _number(context.get("dcf_terminal_value_pct_of_total"))
    if terminal_pct is None and dcf_ev and dcf_ev > 0:
        terminal_pct = pv_terminal / dcf_ev * Decimal("100")
    has_apv = bool(context.get("dcf_has_apv_tax_shield"))
    dcf_operating_ev = (
        _number(context.get("dcf_enterprise_value_before_apv")) if has_apv else dcf_ev
    )
    if has_apv and (dcf_operating_ev is None or dcf_operating_ev <= 0):
        raise SealedDisplayModelError(
            "APV display requires canonical enterprise value before APV"
        )

    nav_book = _number(context.get("nav_book_equity"), default=Decimal("0")) or Decimal(
        "0"
    )
    nav_corrected = _number(context.get("nav_corrected_value"))
    nav_uplift = nav_corrected - nav_book if nav_corrected is not None else None
    nav_uplift_pct = (
        nav_uplift / nav_book * Decimal("100")
        if nav_uplift is not None and abs(nav_book) >= Decimal("10000")
        else None
    )
    nav_uplift_multiple = (
        nav_corrected / nav_book
        if nav_corrected is not None and Decimal("0") < nav_book < Decimal("10000")
        else None
    )

    pre_multiple = _number(
        context.get("pre_synthesis_multiple"), default=applied_multiple
    )
    growth = _number(context.get("revenue_growth_3y_cagr"))
    revenue_multiple = _number(context.get("revenue_multiple_applied"))
    sealed = {
        "schema_version": "report_display_model.v1",
        "field_ids": {
            "multiples_leg_ev": "method.market.enterprise_value",
            "dcf_enterprise_value": "method.dcf.enterprise_value",
            "dcf_operating_enterprise_value": "method.dcf.enterprise_value_before_apv",
            "nav_uplift": "method.adjusted_nav.revaluation_uplift",
            "recurring_ebitda": "earnings.recurring_reference",
        },
        "weights": weights,
        "multiples": {
            "metric_type": metric_type,
            "metric_basis": metric_basis,
            "sustainable_ebitda": sustainable_ebitda,
            "applied_multiple": applied_multiple,
            "leg_enterprise_value": multiples_leg_ev,
            "pre_synthesis_enterprise_value": (
                metric_basis * pre_multiple
                if metric_basis is not None and pre_multiple is not None
                else None
            ),
            "ebitda_crosscheck_enterprise_value": ebitda_crosscheck_ev,
            "implied_ev_sales": (
                ebitda_crosscheck_ev / revenue
                if ebitda_crosscheck_ev is not None
                and revenue is not None
                and revenue > 0
                else None
            ),
            "implied_price_earnings": (
                equity_value / net_income
                if equity_value is not None
                and equity_value > 0
                and net_income is not None
                and net_income > 0
                else None
            ),
            "revenue_growth_pct": growth * Decimal("100")
            if growth is not None
            else None,
            "implied_peg": (
                revenue_multiple / (growth * Decimal("100"))
                if growth and growth > 0 and revenue_multiple is not None
                else None
            ),
        },
        "dcf": {
            "pv_explicit": pv_explicit,
            "pv_terminal": pv_terminal,
            "enterprise_value": dcf_ev,
            "operating_enterprise_value": dcf_operating_ev,
            "terminal_value_pct": terminal_pct,
            "projection_rows": _dcf_projection_rows(context),
        },
        "nav": {
            "book_equity": nav_book,
            "corrected_value": nav_corrected,
            "uplift": nav_uplift,
            "uplift_pct": nav_uplift_pct,
            "uplift_multiple": nav_uplift_multiple,
            "ownership_pct": (
                (_number(context.get("ownership_multiplier")) or Decimal("0"))
                * Decimal("100")
                if context.get("ownership_multiplier") is not None
                else None
            ),
        },
        "ebitda": _multi_year_ebitda(context),
    }
    context["sealed_display"] = sealed
    return sealed
