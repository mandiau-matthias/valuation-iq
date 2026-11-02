"""Scenario valuation from the explicitly supplied advisor forecast drivers."""

from __future__ import annotations

from decimal import Decimal

from src.api.routes.valuation.calculators.dcf_tax_policy import resolve_dcf_tax_assumption
from src.api.schemas.stateless_api import CalculateRequest, YearDataStateless
from src.utils.adaptive_input_helpers import get_percent_override
from src.utils.decimal_helpers import to_decimal

from .stateless_dcf_forecast import (
    _generate_stateless_dcf_forecast_years,
    _split_stateless_forecast_years,
)

_ADVISOR_RANGE_KEYS = (
    "dcf_sensitivity_wacc_delta_pct",
    "dcf_sensitivity_terminal_growth_min_pct",
    "dcf_sensitivity_terminal_growth_max_pct",
    "dcf_sensitivity_ebitda_margin_min_pct",
    "dcf_sensitivity_ebitda_margin_max_pct",
)


def resolve_advisor_dcf_sensitivity(
    request: CalculateRequest,
    *,
    wacc: Decimal,
    terminal_growth_rate: Decimal,
    mid_year_discounting: bool,
    terminal_value_methodology: str,
    operating_enterprise_value: Decimal,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """Admit optional ranges only on the headline model's financial basis."""
    context = request.business_context or {}
    if not any(context.get(key) is not None for key in _ADVISOR_RANGE_KEYS):
        return None, None
    reason = None
    if terminal_value_methodology != "gordon_growth":
        reason = "terminal_method_not_gordon_growth"
    elif getattr(request, "dcf_input_mode", None) == "fcff_only":
        reason = "explicit_fcff_has_no_margin_bridge"
    if reason is not None:
        return None, _excluded_advisor_range(reason)
    candidate = _build_advisor_dcf_sensitivity(
        request,
        wacc=wacc,
        terminal_growth_rate=terminal_growth_rate,
        mid_year_discounting=mid_year_discounting,
    )
    if candidate is None:
        return None, None
    base = candidate["sensitivity_wacc"][str(wacc)]
    # All enabled European reporting currencies have a two-decimal minor unit.
    # Do not let an independently rebuilt operating forecast replace the
    # authoritative model's sensitivity grid when their base values differ.
    if base.quantize(Decimal(".01")) != operating_enterprise_value.quantize(Decimal(".01")):
        return None, {
            **_excluded_advisor_range("base_cash_flows_do_not_reconcile"),
            "overlay_base_value": base,
            "authoritative_base_value": operating_enterprise_value,
        }
    if (
        not candidate["enterprise_value_low"]
        <= operating_enterprise_value
        <= candidate["enterprise_value_high"]
    ):
        return None, _excluded_advisor_range("scenario_range_does_not_contain_base")
    return candidate, None


def _excluded_advisor_range(reason: str) -> dict[str, object]:
    return {
        "policy_version": "advisor_dcf_three_driver.v2",
        "status": "excluded",
        "reason": reason,
        "retained_sensitivity": "engine_headline_model",
    }


def _discounted_fcff_enterprise_value(
    *,
    fcff: list[Decimal],
    wacc: Decimal,
    terminal_growth: Decimal,
    mid_year_discounting: bool,
) -> Decimal:
    if not fcff:
        raise ValueError("DCF sensitivity requires at least one forecast FCFF")
    if not wacc.is_finite() or wacc <= 0:
        raise ValueError("DCF sensitivity requires a finite positive WACC")
    if not terminal_growth.is_finite() or terminal_growth <= -1 or wacc <= terminal_growth:
        raise ValueError("DCF sensitivity requires -100% < terminal growth < WACC")
    if any(not value.is_finite() for value in fcff):
        raise ValueError("DCF sensitivity requires finite cash flows")
    offset = Decimal("0.5") if mid_year_discounting else Decimal("0")
    pv_explicit = sum(
        (value / ((Decimal("1") + wacc) ** (Decimal(index) - offset)))
        for index, value in enumerate(fcff, start=1)
    )
    # Match the headline model: retain every explicit loss, but a non-positive
    # terminal cash flow has no going-concern perpetuity in this DCF policy.
    terminal_value = (
        fcff[-1] * (Decimal("1") + terminal_growth) / (wacc - terminal_growth)
        if fcff[-1] > 0
        else Decimal("0")
    )
    terminal_period = Decimal(len(fcff)) - offset
    return pv_explicit + terminal_value / ((Decimal("1") + wacc) ** terminal_period)


def _margin_fcff_from_forecasts(
    *,
    forecast_years: list[YearDataStateless],
    ebitda_margin: Decimal,
    tax_rate: Decimal,
) -> list[Decimal]:
    fcff: list[Decimal] = []
    for row in sorted(forecast_years, key=lambda value: value.year):
        required = (
            row.revenue,
            row.depreciation,
            row.capex,
            row.nwc_change,
        )
        if any(value is None for value in required):
            raise ValueError(
                "advisor DCF sensitivity requires revenue, D&A, capex and ΔNWC "
                f"for forecast year {row.year}"
            )
        revenue = to_decimal(row.revenue)
        d_and_a = to_decimal(row.depreciation) + to_decimal(row.amortization or 0)
        ebit = revenue * ebitda_margin - d_and_a
        taxes = max(Decimal("0"), ebit) * tax_rate
        fcff.append(ebit - taxes + d_and_a - to_decimal(row.capex) - to_decimal(row.nwc_change))
    return fcff


def _build_advisor_dcf_sensitivity(
    request: CalculateRequest,
    *,
    wacc: Decimal,
    terminal_growth_rate: Decimal,
    mid_year_discounting: bool,
) -> dict[str, object] | None:
    """Build a sealed-input three-driver DCF sensitivity for advisor dossiers.

    Legacy runs retain the engine's default WACC × g grid. This path activates
    only when the caller supplies every range endpoint in business_context.
    """
    wacc_delta = get_percent_override(request, "dcf_sensitivity_wacc_delta_pct")
    growth_min = get_percent_override(request, "dcf_sensitivity_terminal_growth_min_pct")
    growth_max = get_percent_override(request, "dcf_sensitivity_terminal_growth_max_pct")
    margin_min = get_percent_override(request, "dcf_sensitivity_ebitda_margin_min_pct")
    margin_max = get_percent_override(request, "dcf_sensitivity_ebitda_margin_max_pct")
    margin_base = get_percent_override(request, "dcf_ebitda_margin_pct")
    range_endpoints = (
        wacc_delta,
        growth_min,
        growth_max,
        margin_min,
        margin_max,
    )
    # Base operating assumptions such as margin and tax rate are ordinary DCF
    # inputs. They must not accidentally opt the request into the optional
    # advisor sensitivity overlay. Only an explicit range endpoint activates it.
    if all(value is None for value in range_endpoints):
        return None
    required = (
        *range_endpoints,
        margin_base,
    )
    if any(value is None for value in required):
        raise ValueError("advisor DCF sensitivity requires every configured range endpoint")
    assert wacc_delta is not None
    assert growth_min is not None
    assert growth_max is not None
    assert margin_min is not None
    assert margin_max is not None
    assert margin_base is not None
    tax_assumption = resolve_dcf_tax_assumption(request)
    tax_rate = tax_assumption.rate
    if wacc_delta <= 0 or growth_min > terminal_growth_rate or growth_max < terminal_growth_rate:
        raise ValueError("advisor DCF sensitivity range does not contain the base case")
    if margin_min > margin_base or margin_max < margin_base:
        raise ValueError("advisor EBITDA-margin sensitivity does not contain the base case")

    _actuals, explicit_forecasts = _split_stateless_forecast_years(request)
    forecast_years = explicit_forecasts or _generate_stateless_dcf_forecast_years(
        request,
        base_year=request.current_year,
        projection_years=request.projection_years,
    )
    margins = sorted({margin_min, margin_base, margin_max})
    wacc_values = sorted({wacc - wacc_delta, wacc, wacc + wacc_delta})
    growth_values = sorted({growth_min, terminal_growth_rate, growth_max})
    if wacc_values[0] <= growth_values[-1]:
        raise ValueError("advisor DCF sensitivity requires WACC > g in every scenario")

    fcff_by_margin = {
        margin: _margin_fcff_from_forecasts(
            forecast_years=forecast_years,
            ebitda_margin=margin,
            tax_rate=tax_rate,
        )
        for margin in margins
    }
    base_fcff = fcff_by_margin[margin_base]
    ev_matrix = [
        [
            _discounted_fcff_enterprise_value(
                fcff=base_fcff,
                wacc=scenario_wacc,
                terminal_growth=scenario_growth,
                mid_year_discounting=mid_year_discounting,
            )
            for scenario_growth in growth_values
        ]
        for scenario_wacc in wacc_values
    ]
    margin_sensitivity = {
        str(margin): _discounted_fcff_enterprise_value(
            fcff=fcff_by_margin[margin],
            wacc=wacc,
            terminal_growth=terminal_growth_rate,
            mid_year_discounting=mid_year_discounting,
        )
        for margin in margins
    }
    enterprise_low = _discounted_fcff_enterprise_value(
        fcff=fcff_by_margin[margin_min],
        wacc=wacc + wacc_delta,
        terminal_growth=growth_min,
        mid_year_discounting=mid_year_discounting,
    )
    enterprise_high = _discounted_fcff_enterprise_value(
        fcff=fcff_by_margin[margin_max],
        wacc=wacc - wacc_delta,
        terminal_growth=growth_max,
        mid_year_discounting=mid_year_discounting,
    )
    return {
        "sensitivity_wacc": {
            str(scenario_wacc): _discounted_fcff_enterprise_value(
                fcff=base_fcff,
                wacc=scenario_wacc,
                terminal_growth=terminal_growth_rate,
                mid_year_discounting=mid_year_discounting,
            )
            for scenario_wacc in wacc_values
        },
        "sensitivity_growth": {
            str(scenario_growth): _discounted_fcff_enterprise_value(
                fcff=base_fcff,
                wacc=wacc,
                terminal_growth=scenario_growth,
                mid_year_discounting=mid_year_discounting,
            )
            for scenario_growth in growth_values
        },
        "sensitivity_matrix_2d": {
            "schema_version": "dcf_sensitivity.v2",
            "wacc_values": wacc_values,
            "growth_values": growth_values,
            "secondary_values": growth_values,
            "secondary_axis_key": "terminal_growth",
            "secondary_axis_format": "percent",
            "ev_matrix": ev_matrix,
            "terminal_value_policy": "gordon_growth",
        },
        "ebitda_margin_sensitivity": margin_sensitivity,
        "enterprise_value_low": enterprise_low,
        "enterprise_value_high": enterprise_high,
        "sensitivity_range_policy": {
            "policy_version": "advisor_dcf_three_driver.v2",
            "cash_tax_assumption": tax_assumption.provenance(),
            "terminal_value_policy": "positive_fcff_gordon_growth",
            "range_definition": (
                "low = margin_min + WACC_high + g_min; " "high = margin_max + WACC_low + g_max"
            ),
            "wacc_delta": wacc_delta,
            "terminal_growth_min": growth_min,
            "terminal_growth_base": terminal_growth_rate,
            "terminal_growth_max": growth_max,
            "ebitda_margin_min": margin_min,
            "ebitda_margin_base": margin_base,
            "ebitda_margin_max": margin_max,
        },
    }
