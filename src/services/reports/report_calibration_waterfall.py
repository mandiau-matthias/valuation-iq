"""Calibration-waterfall report helpers."""

from collections.abc import Mapping, Sequence
from decimal import Decimal

from src.services.infrastructure.translations import ReportTranslations
from src.services.reports.report_calibration_labels import (
    compact_balance_sheet_adjustment_label,
    compact_waterfall_label,
    localize_discount_waterfall_for_locale,
    localize_waterfall_row,
    localize_waterfall_row_nl,
)
from src.services.reports.report_calibration_steps import build_calibration_steps
from src.utils.decimal_helpers import optional_decimal as parse_decimal_or_none
from src.utils.decimal_helpers import safe_decimal_or_zero as safe_decimal
from src.utils.decimal_helpers import safe_float as to_float

JsonMap = dict[str, object]

_MULTIPLE_WATERFALL_LINEAGE_KEYS = (
    "model_adjustment",
    "effective_adjustment",
    "factor_before",
    "factor_after",
    "rationale",
    "source",
    "multiple_discount_key",
    "discount_key",
    "strength_factor_discount_key",
    "strength_factor_discount_adjustment",
    "strength_factor_discount_before",
    "strength_factor_discount_after",
    "strength_factor_discount_evidence",
    "strength_factor_evidence",
    "strength_factor_policy",
    "strength_factor_evidence_count",
    "strength_factor_multiple_discount_keys",
    "strength_factor_keys",
    "strength_factor_mapped_inputs",
    "strength_factor_valuation_effects",
    "strength_factor_captured_input_ids",
    "strength_factor_data_point_ids",
)


def _multiple_waterfall_lineage_payload(row: Mapping[str, object]) -> JsonMap:
    payload: JsonMap = {}
    for key in _MULTIPLE_WATERFALL_LINEAGE_KEYS:
        value = row.get(key)
        if value is not None:
            payload[key] = value

    evidence = payload.get("strength_factor_discount_evidence")
    if evidence is not None and "strength_factor_evidence" not in row:
        payload["strength_factor_evidence"] = evidence

    return payload


def build_multiple_waterfall_steps(
    calibration_steps: Sequence[Mapping[str, object]],
    applied_multiple: Decimal,
    t: ReportTranslations,
) -> list[JsonMap]:
    """Build a canonical multiple waterfall from calibration steps."""
    if not calibration_steps:
        return []

    steps: list[JsonMap] = []
    previous_multiple = Decimal("0")

    for index, row in enumerate(calibration_steps):
        multiple = safe_decimal(row.get("multiple"))
        label = str(row.get("label") or "")
        description = row.get("description")

        if index == 0:
            step = {
                "label": label,
                "short_label": compact_waterfall_label(label, t),
                "kind": "base",
                "tone": "neutral",
                "start_value": 0.0,
                "end_value": to_float(multiple),
                "delta_value": to_float(multiple),
                "annotation": description,
            }
            step.update(_multiple_waterfall_lineage_payload(row))
            steps.append(step)
        else:
            impact = parse_decimal_or_none(row.get("impact"))
            if impact is None:
                impact = multiple - previous_multiple
            if abs(to_float(impact)) < 0.0001:
                previous_multiple = multiple
                continue
            step = {
                "label": label,
                "short_label": compact_waterfall_label(label, t),
                "kind": "increase" if impact >= 0 else "decrease",
                "tone": "positive" if impact >= 0 else "negative",
                "start_value": to_float(previous_multiple),
                "end_value": to_float(multiple),
                "delta_value": to_float(impact),
                "annotation": description,
            }
            step.update(_multiple_waterfall_lineage_payload(row))
            steps.append(step)
        previous_multiple = multiple

    final_multiple = safe_decimal(
        applied_multiple if applied_multiple is not None else previous_multiple
    )
    steps.append(
        {
            "label": t.wf_applied_multiple,
            "short_label": t.wf_applied_multiple_short,
            "kind": "total",
            "tone": "brand",
            "start_value": 0.0,
            "end_value": to_float(final_multiple),
            "delta_value": to_float(final_multiple),
            "annotation": None,
        }
    )

    return steps


def _waterfall_step(
    *,
    label: str,
    short_label: str,
    kind: str,
    tone: str,
    start_value: Decimal,
    end_value: Decimal,
    delta_value: Decimal,
    annotation: object = None,
) -> JsonMap:
    return {
        "label": label,
        "short_label": short_label,
        "kind": kind,
        "tone": tone,
        "start_value": to_float(start_value),
        "end_value": to_float(end_value),
        "delta_value": to_float(delta_value),
        "annotation": annotation,
    }


def _signed_step(
    *,
    label: str,
    short_label: str,
    signed_amount: Decimal,
    running_total: Decimal,
    tone: str | None = None,
) -> JsonMap:
    return _waterfall_step(
        label=label,
        short_label=short_label,
        kind="increase" if signed_amount > 0 else "decrease",
        tone=tone or ("positive" if signed_amount > 0 else "negative"),
        start_value=running_total,
        end_value=running_total + signed_amount,
        delta_value=signed_amount,
    )


def _metric_basis_labels(metric_type: str, t: ReportTranslations) -> tuple[str, str]:
    metric_key = str(metric_type or "EBITDA").upper()
    if metric_key == "REVENUE":
        return t.wf_basis_revenue, t.wf_basis_revenue
    if metric_key == "SDE":
        return t.wf_basis_sde, t.wf_basis_sde_short
    return t.wf_basis_ebitda, t.wf_basis_ebitda_short


def _effective_multiple_annotation(
    effective_multiple: Decimal,
    t: ReportTranslations,
) -> str:
    value = f"{to_float(effective_multiple):.2f}"
    if str(getattr(t, "locale", "nl") or "nl").lower().startswith("nl"):
        value = value.replace(".", ",")
    return value + "×"


def _metric_bridge_steps(
    *,
    valuation_basis_value: Decimal,
    metric_type: str,
    applied_multiple: Decimal,
    enterprise_value_mid: Decimal,
    t: ReportTranslations,
    include_metric_bridge: bool,
    basis_labels: tuple[str, str] | None = None,
) -> list[JsonMap]:
    if not include_metric_bridge:
        return []

    # An EBITDA basis can be named by the caller (the cover's honest label —
    # "Gerapporteerde" unless adjustments were applied, "(gewogen)" only on a
    # weighted basis). Revenue / SDE bases keep their own contract strings.
    if basis_labels and str(metric_type or "EBITDA").upper() == "EBITDA":
        basis_label, basis_short = basis_labels
    else:
        basis_label, basis_short = _metric_basis_labels(metric_type, t)
    multiplier_delta = enterprise_value_mid - valuation_basis_value
    effective_multiple = (
        enterprise_value_mid / valuation_basis_value
        if valuation_basis_value > Decimal("0")
        else applied_multiple
    )
    return [
        _waterfall_step(
            label=basis_label,
            short_label=basis_short,
            kind="base",
            tone="neutral",
            start_value=Decimal("0"),
            end_value=valuation_basis_value,
            delta_value=valuation_basis_value,
        ),
        _waterfall_step(
            label=t.wf_applied_multiple,
            short_label=t.wf_bridge_multiple_short,
            kind="increase" if multiplier_delta >= 0 else "decrease",
            tone="bridge",
            start_value=valuation_basis_value,
            end_value=enterprise_value_mid,
            delta_value=multiplier_delta,
            annotation=_effective_multiple_annotation(effective_multiple, t),
        ),
    ]


def _cash_debt_bridge(
    *,
    total_debt: Decimal,
    cash_balance: Decimal,
    excess_cash: Decimal,
    exemption_applied: bool,
    net_debt: Decimal,
) -> tuple[Decimal, Decimal, bool]:
    # Under the operating-cash exemption ONLY the excess bridges to equity — that
    # is the method Step 7 actually applied. Falling back to the full balance when
    # the excess was zero drew "+cash" and then, to keep the split consistent,
    # invented a debt row of the same size: a EUR 314,966 "Financiële schuld" on a
    # debt-free company. Zero excess means no cash row, not a fabricated one.
    bridge_cash = excess_cash if exemption_applied else cash_balance
    bridge_debt = total_debt

    if bridge_debt <= 0 and bridge_cash > 0:
        derived_debt = net_debt + bridge_cash
        if derived_debt > 0:
            bridge_debt = derived_debt
    elif bridge_cash <= 0 and bridge_debt > 0:
        derived_cash = bridge_debt - net_debt
        if derived_cash > 0:
            bridge_cash = derived_cash

    has_consistent_split_bridge = (bridge_cash > 0 or bridge_debt > 0) and abs(
        (bridge_debt - bridge_cash) - net_debt
    ) < Decimal("0.01")
    return bridge_cash, bridge_debt, has_consistent_split_bridge


def _cash_step_labels(
    *,
    exemption_applied: bool,
    excess_cash: Decimal,
    t: ReportTranslations,
) -> tuple[str, str]:
    if exemption_applied and excess_cash > 0:
        return t.wf_excess_cash, t.wf_excess_cash_short
    return t.wf_cash_equivalents, t.wf_cash_short


def _append_cash_bridge_step(
    *,
    steps: list[JsonMap],
    running_total: Decimal,
    bridge_cash: Decimal,
    exemption_applied: bool,
    excess_cash: Decimal,
    t: ReportTranslations,
) -> Decimal:
    cash_label, cash_short = _cash_step_labels(
        exemption_applied=exemption_applied,
        excess_cash=excess_cash,
        t=t,
    )
    steps.append(
        _signed_step(
            label=cash_label,
            short_label=cash_short,
            signed_amount=bridge_cash,
            running_total=running_total,
        )
    )
    return running_total + bridge_cash


def _append_debt_bridge_step(
    *,
    steps: list[JsonMap],
    running_total: Decimal,
    bridge_debt: Decimal,
    t: ReportTranslations,
) -> Decimal:
    steps.append(
        _signed_step(
            label=t.wf_financial_debt,
            short_label=t.wf_debt_short,
            signed_amount=-bridge_debt,
            running_total=running_total,
        )
    )
    return running_total - bridge_debt


def _append_net_debt_fallback_step(
    *,
    steps: list[JsonMap],
    running_total: Decimal,
    net_debt: Decimal,
    t: ReportTranslations,
) -> Decimal:
    fallback_is_cash = net_debt < 0
    fallback_amount = abs(net_debt)
    fb_label = t.wf_net_cash if fallback_is_cash else t.wf_net_debt
    signed_amount = fallback_amount if fallback_is_cash else -fallback_amount
    steps.append(
        _signed_step(
            label=fb_label,
            short_label=fb_label,
            signed_amount=signed_amount,
            running_total=running_total,
        )
    )
    return running_total + signed_amount


def _append_cash_debt_bridge_steps(
    *,
    steps: list[JsonMap],
    running_total: Decimal,
    total_debt: Decimal,
    cash_balance: Decimal,
    excess_cash: Decimal,
    exemption_applied: bool,
    net_debt: Decimal,
    t: ReportTranslations,
) -> Decimal:
    bridge_cash, bridge_debt, has_consistent_split_bridge = _cash_debt_bridge(
        total_debt=total_debt,
        cash_balance=cash_balance,
        excess_cash=excess_cash,
        exemption_applied=exemption_applied,
        net_debt=net_debt,
    )

    if has_consistent_split_bridge and bridge_cash > 0:
        running_total = _append_cash_bridge_step(
            steps=steps,
            running_total=running_total,
            bridge_cash=bridge_cash,
            exemption_applied=exemption_applied,
            excess_cash=excess_cash,
            t=t,
        )

    if has_consistent_split_bridge and bridge_debt > 0:
        return _append_debt_bridge_step(
            steps=steps,
            running_total=running_total,
            bridge_debt=bridge_debt,
            t=t,
        )
    elif net_debt != 0 and not has_consistent_split_bridge:
        return _append_net_debt_fallback_step(
            steps=steps,
            running_total=running_total,
            net_debt=net_debt,
            t=t,
        )

    return running_total


def _append_optional_signed_step(
    *,
    steps: list[JsonMap],
    running_total: Decimal,
    amount: Decimal,
    label: str,
    short_label: str,
    tone: str | None = None,
) -> Decimal:
    if amount == 0:
        return running_total
    steps.append(
        _signed_step(
            label=label,
            short_label=short_label,
            signed_amount=amount,
            running_total=running_total,
            tone=tone,
        )
    )
    return running_total + amount


def _append_balance_sheet_adjustment_steps(
    *,
    steps: list[JsonMap],
    running_total: Decimal,
    balance_sheet_adjustments: Sequence[Mapping[str, object]],
    t: ReportTranslations,
) -> Decimal:
    category_counts: dict[str, int] = {}
    for adjustment in balance_sheet_adjustments or []:
        raw_amount = safe_decimal(adjustment.get("amount", 0))
        if raw_amount == 0:
            continue
        is_add = str(adjustment.get("type", "subtract")).lower() == "add"
        signed_amount = raw_amount if is_add else -raw_amount
        label = str(adjustment.get("label") or t.wf_balance_sheet_fallback)
        category = str(adjustment.get("category") or "other").lower()
        category_counts[category] = category_counts.get(category, 0) + 1
        steps.append(
            _signed_step(
                label=label,
                short_label=compact_balance_sheet_adjustment_label(
                    label,
                    category,
                    category_counts[category],
                    t,
                ),
                signed_amount=signed_amount,
                running_total=running_total,
            )
        )
        running_total += signed_amount
    return running_total


def build_valuation_waterfall_steps(
    valuation_basis_value: Decimal,
    metric_type: str,
    applied_multiple: Decimal,
    enterprise_value_mid: Decimal,
    total_debt: Decimal,
    cash_balance: Decimal,
    excess_cash: Decimal,
    exemption_applied: bool,
    net_debt: Decimal,
    tax_latency_net_impact: Decimal,
    balance_sheet_adjustments: Sequence[Mapping[str, object]],
    t: ReportTranslations,
    nwc_surplus_deficit: Decimal = Decimal("0"),
    equity_value: Decimal | None = Decimal("0"),
    include_metric_bridge: bool = True,
    basis_labels: tuple[str, str] | None = None,
) -> list[JsonMap]:
    """Build a canonical EUR waterfall from basis metric to equity value."""
    steps = _metric_bridge_steps(
        valuation_basis_value=valuation_basis_value,
        metric_type=metric_type,
        applied_multiple=applied_multiple,
        enterprise_value_mid=enterprise_value_mid,
        t=t,
        include_metric_bridge=include_metric_bridge,
        basis_labels=basis_labels,
    )

    steps.append(
        _waterfall_step(
            label=t.wf_enterprise_value,
            short_label=t.ledger_ev_short,
            kind="subtotal",
            tone="brand",
            start_value=Decimal("0"),
            end_value=enterprise_value_mid,
            delta_value=enterprise_value_mid,
        )
    )
    ev_row_index = len(steps) - 1
    if equity_value is None:
        steps[ev_row_index] = {**steps[ev_row_index], "kind": "total"}
        return steps

    running_total = enterprise_value_mid
    running_total = _append_cash_debt_bridge_steps(
        steps=steps,
        running_total=running_total,
        total_debt=total_debt,
        cash_balance=cash_balance,
        excess_cash=excess_cash,
        exemption_applied=exemption_applied,
        net_debt=net_debt,
        t=t,
    )
    running_total = _append_optional_signed_step(
        steps=steps,
        running_total=running_total,
        amount=tax_latency_net_impact,
        label=t.tax_latency_title,
        short_label=t.wf_tax_latency_short,
    )
    running_total = _append_balance_sheet_adjustment_steps(
        steps=steps,
        running_total=running_total,
        balance_sheet_adjustments=balance_sheet_adjustments,
        t=t,
    )
    running_total = _append_optional_signed_step(
        steps=steps,
        running_total=running_total,
        amount=nwc_surplus_deficit,
        label=t.exec_ev_bridge_nwc_label,
        short_label=t.wf_nwc_short,
        tone="neutral",
    )

    bridge_rows_emitted = len(steps) - (ev_row_index + 1)
    equity_is_distinct = abs(equity_value - enterprise_value_mid) > Decimal("0.005")
    if bridge_rows_emitted > 0 or equity_is_distinct:
        steps.append(
            _waterfall_step(
                label=t.wf_equity_value,
                short_label=t.wf_equity_short,
                kind="total",
                tone="brand",
                start_value=Decimal("0"),
                end_value=equity_value,
                delta_value=equity_value,
            )
        )
    else:
        # No bridge rows AND equity == EV: there is no EV→equity bridge. Appending
        # the equity row here published the ENTERPRISE value under the
        # "Aandelenwaarde" label and drew a waterfall whose only two bars were the
        # same number (VR-2026-9712). Terminate on the enterprise value instead;
        # the executive summary already carries `exec_ev_equity_no_balance`
        # explaining why no bridge exists, and an annotation here would be
        # truncated to 18 characters by the chart component.
        steps[ev_row_index] = {**steps[ev_row_index], "kind": "total"}

    return steps


def inject_sme_calibration_into_waterfall(
    waterfall: Sequence[Mapping[str, object]],
    step_data: Mapping[str, object] | None,
    metric_value: float,
    t: ReportTranslations,
) -> list[JsonMap]:
    """
    Prepend an explicit SME calibration step when the Step 11 waterfall starts
    from the post-calibration baseline.
    """
    if not step_data or not waterfall:
        return [dict(row) for row in waterfall]

    raw_val = step_data.get("sme_database_multiple_raw")
    factor_val = step_data.get("sme_calibration_factor")
    if not raw_val or not factor_val or factor_val == 1.0:
        return [dict(row) for row in waterfall]

    sme_raw = safe_decimal(raw_val)
    sme_factor = safe_decimal(factor_val)
    if sme_raw <= Decimal("0"):
        return [dict(row) for row in waterfall]

    calibrated_multiple = sme_raw * sme_factor
    sme_impact = to_float(calibrated_multiple - sme_raw)
    reduction_pct = to_float((Decimal("1") - sme_factor) * Decimal("100"))
    mv = to_float(metric_value)
    pct_s = f"{reduction_pct:.0f}"

    baseline_entry = {
        "label": t.calib_wf_market_median_db_p50,
        "multiple": to_float(sme_raw),
        "impact": None,
        "ev": mv * to_float(sme_raw) if mv else 0,
        "ref": "¹",
        "description": t.calib_wf_gross_multiple_before_sme,
    }
    calibration_entry = {
        "label": t.calib_wf_sme_calibration,
        "multiple": to_float(calibrated_multiple),
        "impact": sme_impact,
        "ev": mv * to_float(calibrated_multiple) if mv else 0,
        "ref": "",
        "description": t.calib_wf_sme_calibration_desc.format(pct=pct_s),
    }

    return [baseline_entry, calibration_entry] + [dict(row) for row in waterfall[1:]]
