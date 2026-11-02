"""Pure M&A defensibility invariant checks for final valuation payloads."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

Results = dict[str, object]
Violation = dict[str, object]


@dataclass(frozen=True)
class MAInvariantThresholds:
    bridge_tol_pct: Decimal
    ebitda_multiple_min: Decimal
    ebitda_multiple_max: Decimal
    high_conf_threshold: int
    thin_year_threshold: int
    ebitda_sde_max_div: Decimal
    dcf_market_max_div: Decimal
    band_width_min: Decimal
    band_width_max: Decimal
    ask_markup_max: Decimal


def load_ma_invariant_thresholds() -> MAInvariantThresholds:
    try:
        from src.config import get_settings

        cfg = get_settings()
        return MAInvariantThresholds(
            bridge_tol_pct=cfg.ma_invariant_ev_equity_bridge_tolerance,
            ebitda_multiple_min=cfg.ma_invariant_implied_ebitda_multiple_min,
            ebitda_multiple_max=cfg.ma_invariant_implied_ebitda_multiple_max,
            high_conf_threshold=cfg.ma_invariant_high_confidence_threshold,
            thin_year_threshold=cfg.ma_invariant_thin_data_year_threshold,
            ebitda_sde_max_div=cfg.ma_invariant_ebitda_sde_max_divergence,
            dcf_market_max_div=cfg.ma_invariant_dcf_market_max_divergence,
            band_width_min=cfg.ma_invariant_band_width_min,
            band_width_max=cfg.ma_invariant_band_width_max,
            ask_markup_max=cfg.ma_invariant_asking_markup_max,
        )
    except Exception:
        return MAInvariantThresholds(
            bridge_tol_pct=Decimal("0.01"),
            ebitda_multiple_min=Decimal("1.0"),
            ebitda_multiple_max=Decimal("25.0"),
            high_conf_threshold=80,
            thin_year_threshold=1,
            ebitda_sde_max_div=Decimal("1.0"),
            dcf_market_max_div=Decimal("1.0"),
            band_width_min=Decimal("0.10"),
            band_width_max=Decimal("2.50"),
            ask_markup_max=Decimal("0.50"),
        )


def _safe_decimal(raw: object, default: Decimal | None = None) -> Decimal | None:
    try:
        return Decimal(str(raw))
    except Exception:
        return default


def _add_asking_price_below_mid_warning(
    warnings: list[Violation], asking_price: object, mid: object
) -> None:
    if asking_price is None or mid is None:
        return
    ask = _safe_decimal(asking_price)
    midpoint = _safe_decimal(mid)
    if ask is None or midpoint is None or ask >= midpoint:
        return
    warnings.append(
        {
            "invariant": "asking_price_above_mid",
            "asking_price": str(asking_price),
            "equity_value_mid": str(mid),
            "note": "Asking price below mid valuation — recommended ask is irrational for a sell-side report",
        }
    )


def _balance_sheet_missing(results: Results) -> bool:
    metadata = results.get("metadata") or {}
    current = results.get("current_year_data") or {}
    bs_provided = (
        bool(metadata.get("balance_sheet_provided")) if isinstance(metadata, dict) else False
    )
    cash_val = _safe_decimal(
        current.get("cash") if isinstance(current, dict) else None, Decimal("0")
    )
    debt_val = _safe_decimal(
        current.get("total_debt") if isinstance(current, dict) else None, Decimal("0")
    )
    return not bs_provided and cash_val == Decimal("0") and debt_val == Decimal("0")


def _add_ev_equity_bridge_warning(
    warnings: list[Violation],
    results: Results,
    enterprise_value: object,
    equity_value: object,
    thresholds: MAInvariantThresholds,
) -> None:
    if enterprise_value is None or equity_value is None:
        return
    ev = _safe_decimal(enterprise_value)
    eq = _safe_decimal(equity_value)
    if ev is None or eq is None:
        return

    net_debt_raw = (
        results.get("net_debt")
        if results.get("net_debt") is not None
        else results.get("step7_net_debt")
    )
    nd = _safe_decimal(net_debt_raw, Decimal("0"))
    if (net_debt_raw is None or nd == Decimal("0")) and _balance_sheet_missing(results):
        nd = ev - eq

    bridge_diff = abs((eq + nd) - ev)
    tol = max(Decimal("1"), abs(ev) * thresholds.bridge_tol_pct)
    if bridge_diff <= tol:
        return
    warnings.append(
        {
            "invariant": "ev_equity_bridge",
            "enterprise_value": str(ev),
            "equity_value": str(eq),
            "net_debt": str(nd),
            "bridge_diff": str(bridge_diff),
            "tolerance": str(tol),
            "note": "EV ≠ Equity + Net Debt within tolerance — accounting bridge broken",
        }
    )


def _add_equity_value_in_band_warning(
    warnings: list[Violation], equity_value: object, low: object, high: object
) -> None:
    if not all(v is not None for v in (equity_value, low, high)):
        return
    eq = _safe_decimal(equity_value)
    lo = _safe_decimal(low)
    hi = _safe_decimal(high)
    if eq is None or lo is None or hi is None or lo <= eq <= hi:
        return
    warnings.append(
        {
            "invariant": "equity_value_in_band",
            "equity_value": str(eq),
            "equity_value_low": str(lo),
            "equity_value_high": str(hi),
            "note": "Canonical equity_value is outside [low, high] band",
        }
    )


def _add_implied_ebitda_multiple_warning(
    warnings: list[Violation],
    ebitda: object,
    enterprise_value: object,
    thresholds: MAInvariantThresholds,
) -> None:
    if ebitda is None or enterprise_value is None:
        return
    ebitda_value = _safe_decimal(ebitda)
    ev = _safe_decimal(enterprise_value)
    if ebitda_value is None or ev is None or ebitda_value <= 0:
        return
    implied = ev / ebitda_value
    if thresholds.ebitda_multiple_min <= implied <= thresholds.ebitda_multiple_max:
        return
    warnings.append(
        {
            "invariant": "implied_ebitda_multiple_bounds",
            "implied_multiple": f"{float(implied):.2f}x",
            "enterprise_value": str(ev),
            "ebitda": str(ebitda_value),
            "bounds": f"[{thresholds.ebitda_multiple_min}x, {thresholds.ebitda_multiple_max}x]",
            "note": (
                f"Implied EV/EBITDA outside reasonable band "
                f"[{thresholds.ebitda_multiple_min}x, {thresholds.ebitda_multiple_max}x] — "
                "review methodology selection"
            ),
        }
    )


def _add_confidence_data_thinness_warning(
    warnings: list[Violation],
    confidence_score: object,
    years_of_data: object,
    thresholds: MAInvariantThresholds,
) -> None:
    if confidence_score is None or years_of_data is None:
        return
    try:
        cs = float(confidence_score)
        yrs = int(years_of_data)
    except (TypeError, ValueError):
        return
    if cs < float(thresholds.high_conf_threshold) or yrs > int(thresholds.thin_year_threshold):
        return
    warnings.append(
        {
            "invariant": "confidence_vs_data_thinness",
            "confidence_score": cs,
            "years_of_data": yrs,
            "thresholds": {
                "high_confidence": int(thresholds.high_conf_threshold),
                "thin_year": int(thresholds.thin_year_threshold),
            },
            "note": (
                f"Confidence ≥{int(thresholds.high_conf_threshold)}% with "
                f"≤{int(thresholds.thin_year_threshold)} year(s) of data is "
                "overconfident; review confidence model"
            ),
        }
    )


def _add_band_width_warning(
    warnings: list[Violation],
    low: object,
    mid: object,
    high: object,
    thresholds: MAInvariantThresholds,
) -> None:
    if not all(v is not None for v in (low, mid, high)):
        return
    lo = _safe_decimal(low)
    md = _safe_decimal(mid)
    hi = _safe_decimal(high)
    if lo is None or md is None or hi is None or md <= 0:
        return
    band_width = (hi - lo) / md
    if band_width < thresholds.band_width_min:
        warnings.append(
            {
                "invariant": "band_width_too_narrow",
                "band_width_pct": f"{float(band_width) * 100:.1f}%",
                "min_pct": f"{float(thresholds.band_width_min) * 100:.1f}%",
                "low": str(lo),
                "mid": str(md),
                "high": str(hi),
                "note": (
                    "Band width below floor — claims unrealistic precision; "
                    "consider widening confidence spread"
                ),
            }
        )
    elif band_width > thresholds.band_width_max:
        warnings.append(
            {
                "invariant": "band_width_too_wide",
                "band_width_pct": f"{float(band_width) * 100:.1f}%",
                "max_pct": f"{float(thresholds.band_width_max) * 100:.1f}%",
                "low": str(lo),
                "mid": str(md),
                "high": str(hi),
                "note": (
                    "Band width above ceiling — no information content; "
                    "review confidence model or methodology"
                ),
            }
        )


def _sde_mid_value(results: Results) -> object:
    sde_cross_check = results.get("sde_cross_check") or {}
    if isinstance(sde_cross_check, dict):
        sde_mid_value = sde_cross_check.get("sde_mid")
        if sde_mid_value is not None:
            return sde_mid_value
    step27 = results.get("_step_27_sde") or {}
    if isinstance(step27, dict):
        return step27.get("sde_valuation")
    return None


def _ebitda_path_mid_value(results: Results, mid: object) -> object:
    multiples_valuation = results.get("multiples_valuation")
    if isinstance(multiples_valuation, dict):
        return multiples_valuation.get("equity_value_mid") or mid
    return mid


def _add_sde_cross_method_divergence_warning(
    warnings: list[Violation],
    sde_mid_value: object,
    ebitda_path_mid_value: object,
    thresholds: MAInvariantThresholds,
) -> None:
    if sde_mid_value is None or ebitda_path_mid_value is None:
        return
    sde_mid_d = _safe_decimal(sde_mid_value)
    eb_mid_d = _safe_decimal(ebitda_path_mid_value)
    if sde_mid_d is None or eb_mid_d is None or sde_mid_d <= 0 or eb_mid_d <= 0:
        return
    smaller = min(sde_mid_d, eb_mid_d)
    divergence = abs(sde_mid_d - eb_mid_d) / smaller
    if divergence <= thresholds.ebitda_sde_max_div:
        return
    warnings.append(
        {
            "invariant": "ebitda_sde_cross_method_divergence",
            "ebitda_path_mid": str(eb_mid_d),
            "sde_path_mid": str(sde_mid_d),
            "divergence_pct": f"{float(divergence) * 100:.1f}%",
            "max_pct": f"{float(thresholds.ebitda_sde_max_div) * 100:.1f}%",
            "note": (
                "EBITDA-path and SDE-path valuations diverge — "
                "review owner-compensation normalization and "
                "methodology selection (Trugman 2017 §5)"
            ),
        }
    )


def _component_leg_ev(results: Results, leg: str) -> object:
    """Enterprise value of one hybrid leg ('dcf' or 'multiples'), or None.

    Reads the canonical ``component_results`` block the hybrid result builder
    populates for every blended valuation — the authoritative per-leg figures
    before the weighted synthesis collapses them into the headline.
    """
    component_results = results.get("component_results")
    if isinstance(component_results, dict):
        node = component_results.get(leg)
        if isinstance(node, dict):
            return node.get("enterprise_value")
    return None


def _add_dcf_market_divergence_warning(
    warnings: list[Violation],
    dcf_ev: object,
    multiples_ev: object,
    dcf_weight: object,
    thresholds: MAInvariantThresholds,
) -> None:
    """Warn when a hybrid's DCF leg and market-multiple leg diverge too far.

    A DCF leg that dwarfs the market leg implies an EV/EBITDA multiple well above
    the benchmark and rests on forecast assumptions the history may not support.
    This is the cross-check the EBITDA↔SDE divergence invariant performs for the
    two market paths — extended to the income-vs-market split (Koller et al. 2020
    §6). Fires only when BOTH legs are present and positive (a genuine blend);
    single-method valuations have nothing to triangulate against.
    """
    if dcf_ev is None or multiples_ev is None:
        return
    dcf_d = _safe_decimal(dcf_ev)
    mkt_d = _safe_decimal(multiples_ev)
    if dcf_d is None or mkt_d is None or dcf_d <= 0 or mkt_d <= 0:
        return
    smaller = min(dcf_d, mkt_d)
    divergence = abs(dcf_d - mkt_d) / smaller
    if divergence <= thresholds.dcf_market_max_div:
        return
    weight_d = _safe_decimal(dcf_weight)
    weight_note = (
        f" A {float(weight_d) * 100:.0f}% DCF weight makes the headline lean on the DCF leg."
        if weight_d is not None and weight_d > 0
        else ""
    )
    warnings.append(
        {
            "invariant": "dcf_market_cross_method_divergence",
            "dcf_enterprise_value": str(dcf_d),
            "multiples_enterprise_value": str(mkt_d),
            "divergence_pct": f"{float(divergence) * 100:.1f}%",
            "max_pct": f"{float(thresholds.dcf_market_max_div) * 100:.1f}%",
            "dcf_weight": (str(weight_d) if weight_d is not None else None),
            "note": (
                "DCF-leg and market-multiple valuations diverge beyond tolerance — "
                "the DCF implies a multiple well above the market benchmark and rests "
                "on forecast assumptions the history may not support." + weight_note +
                " Re-check the forecast inputs or re-weight toward the market approach "
                "(Koller et al. 2020 §6 cross-check)."
            ),
        }
    )


def _primary_method(results: Results) -> object:
    multiples_valuation = results.get("multiples_valuation")
    if isinstance(multiples_valuation, dict):
        return multiples_valuation.get("primary_method") or results.get("primary_method")
    return results.get("primary_method")


def _employee_count(results: Results) -> int | None:
    raw_count = results.get("num_employees")
    if raw_count is None:
        raw_count = results.get("employees") or results.get("staff_count")
    return _safe_int(raw_count)


def _is_ebitda_primary_method(primary_method: object) -> bool:
    return primary_method is not None and "EBITDA" in str(primary_method).upper()


def _add_sole_trader_methodology_warning(
    warnings: list[Violation], results: Results, sde_mid_value: object
) -> None:
    primary_method = _primary_method(results)
    if not _is_ebitda_primary_method(primary_method) or sde_mid_value is None:
        return
    employees = _employee_count(results)
    sde_mid = _safe_decimal(sde_mid_value)
    if not _is_positive_sole_trader_sde(employees, sde_mid):
        return
    warnings.append(
        {
            "invariant": "sole_trader_methodology_advisory",
            "primary_method": str(primary_method),
            "num_employees": employees,
            "sde_mid_available": str(sde_mid_value),
            "note": (
                "Owner-operated business (≤1 employee) typically "
                "values better via SDE methodology than EBITDA. "
                "Review primary method selection."
            ),
        }
    )


def _is_positive_sole_trader_sde(employees: int | None, sde_mid: Decimal | None) -> bool:
    if employees is None or sde_mid is None:
        return False
    return employees <= 1 and sde_mid > 0


def _safe_int(raw: object) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError, ArithmeticError):
        return None


def _positive_decimal_triplet(
    first: object, second: object, third: object
) -> tuple[Decimal, Decimal, Decimal] | None:
    first_decimal = _safe_decimal(first)
    second_decimal = _safe_decimal(second)
    third_decimal = _safe_decimal(third)
    if first_decimal is None or second_decimal is None or third_decimal is None:
        return None
    if first_decimal <= 0 or second_decimal <= 0 or third_decimal <= 0:
        return None
    return first_decimal, second_decimal, third_decimal


def _add_per_share_consistency_warning(
    warnings: list[Violation],
    shares_outstanding: object,
    per_share_value: object,
    equity_value: object,
) -> None:
    if shares_outstanding is None or per_share_value is None or equity_value is None:
        return
    decimals = _positive_decimal_triplet(shares_outstanding, per_share_value, equity_value)
    if decimals is None:
        return
    shr, pps, eq = decimals
    implied_eq = pps * shr
    diff = abs(implied_eq - eq) / eq
    if diff <= Decimal("0.01"):
        return
    warnings.append(
        {
            "invariant": "per_share_consistency",
            "per_share_value": str(pps),
            "shares_outstanding": str(shr),
            "implied_equity": str(implied_eq),
            "equity_value": str(eq),
            "divergence_pct": f"{float(diff) * 100:.2f}%",
            "note": (
                "per_share_value × shares_outstanding ≠ equity_value — "
                "per-share figure incorrectly derived"
            ),
        }
    )


def _add_asking_price_markup_warning(
    warnings: list[Violation],
    asking_price: object,
    mid: object,
    thresholds: MAInvariantThresholds,
) -> None:
    if asking_price is None or mid is None:
        return
    ap = _safe_decimal(asking_price)
    md = _safe_decimal(mid)
    if ap is None or md is None or md <= 0:
        return
    markup = (ap - md) / md
    if markup <= thresholds.ask_markup_max:
        return
    warnings.append(
        {
            "invariant": "asking_price_markup_too_high",
            "asking_price": str(ap),
            "equity_value_mid": str(md),
            "markup_pct": f"{float(markup) * 100:.1f}%",
            "max_pct": f"{float(thresholds.ask_markup_max) * 100:.1f}%",
            "note": (
                "Asking-price markup over mid exceeds ceiling — "
                "review asking_price_buffer_pct or advisor override"
            ),
        }
    )


def build_ma_invariant_warnings(results: Results) -> list[Violation]:
    thresholds = load_ma_invariant_thresholds()
    warnings: list[Violation] = []

    low = results.get("equity_value_low")
    mid = results.get("equity_value_mid")
    high = results.get("equity_value_high")
    equity_value = results.get("equity_value")
    enterprise_value = results.get("enterprise_value")
    asking_price = (
        results.get("asking_price")
        or results.get("recommended_asking_price")
        or results.get("step_11_asking_price")
    )

    _add_asking_price_below_mid_warning(warnings, asking_price, mid)
    _add_ev_equity_bridge_warning(warnings, results, enterprise_value, equity_value, thresholds)
    _add_equity_value_in_band_warning(warnings, equity_value, low, high)
    _add_implied_ebitda_multiple_warning(
        warnings,
        results.get("ebitda") or results.get("weighted_ebitda") or results.get("normalized_ebitda"),
        enterprise_value,
        thresholds,
    )
    _add_confidence_data_thinness_warning(
        warnings,
        results.get("confidence_score"),
        results.get("years_of_data") or results.get("data_years"),
        thresholds,
    )
    _add_band_width_warning(warnings, low, mid, high, thresholds)

    sde_mid = _sde_mid_value(results)
    _add_sde_cross_method_divergence_warning(
        warnings, sde_mid, _ebitda_path_mid_value(results, mid), thresholds
    )
    _add_dcf_market_divergence_warning(
        warnings,
        _component_leg_ev(results, "dcf"),
        _component_leg_ev(results, "multiples"),
        results.get("dcf_weight"),
        thresholds,
    )
    _add_sole_trader_methodology_warning(warnings, results, sde_mid)
    _add_per_share_consistency_warning(
        warnings,
        results.get("shares_outstanding") or results.get("number_of_shares"),
        results.get("per_share_value"),
        equity_value,
    )
    _add_asking_price_markup_warning(warnings, asking_price, mid, thresholds)
    return warnings
