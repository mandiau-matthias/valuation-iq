"""Fallback calibration-step rows for report multiple waterfalls."""

from collections.abc import Mapping
from decimal import Decimal

from src.services.infrastructure.translations import ReportTranslations
from src.utils.decimal_helpers import safe_decimal_or_zero as safe_decimal
from src.utils.decimal_helpers import safe_float as to_float

JsonMap = dict[str, object]


def _calibration_step(
    *,
    label: str,
    description: object,
    multiple: Decimal,
    impact: Decimal | None,
    metric_value: Decimal,
    ref: str,
) -> JsonMap:
    return {
        "label": label,
        "description": description,
        "multiple": to_float(multiple),
        "impact": to_float(impact) if impact is not None else None,
        "ev": to_float(metric_value * multiple),
        "ref": ref,
    }


def _not_applicable_calibration_step(t: ReportTranslations) -> JsonMap:
    return {
        "label": t.calib_wf_not_applicable,
        "description": t.calib_wf_not_applicable_desc,
        "multiple": 0.0,
        "impact": None,
        "ev": 0.0,
        "ref": "",
    }


def _sme_calibration_inputs(
    step_data: Mapping[str, object] | None,
) -> tuple[Decimal | None, Decimal | None]:
    if not step_data:
        return None, None
    raw_val = step_data.get("sme_database_multiple_raw")
    factor_val = step_data.get("sme_calibration_factor")
    if not raw_val or not factor_val or factor_val == 1.0:
        return None, None
    return safe_decimal(raw_val), safe_decimal(factor_val)


def _append_baseline_calibration_steps(
    *,
    steps: list[JsonMap],
    metric_value: Decimal,
    base_multiple: Decimal,
    step_data: Mapping[str, object] | None,
    t: ReportTranslations,
) -> Decimal:
    sme_raw, sme_factor = _sme_calibration_inputs(step_data)
    if sme_raw and sme_factor and sme_raw > Decimal("0"):
        steps.append(
            _calibration_step(
                label=t.calib_wf_market_median_db_p50,
                description=t.calib_wf_gross_multiple_before_sme,
                multiple=sme_raw,
                impact=None,
                metric_value=metric_value,
                ref="¹",
            )
        )

        calibrated_multiple = sme_raw * sme_factor
        reduction_pct = to_float((Decimal("1") - sme_factor) * Decimal("100"))
        steps.append(
            _calibration_step(
                label=t.calib_wf_sme_calibration,
                description=t.calib_wf_sme_calibration_desc.format(pct=f"{reduction_pct:.0f}"),
                multiple=calibrated_multiple,
                impact=calibrated_multiple - sme_raw,
                metric_value=metric_value,
                ref="",
            )
        )
        return calibrated_multiple

    steps.append(
        _calibration_step(
            label=t.calib_wf_market_consensus_p50,
            description=None,
            multiple=base_multiple,
            impact=None,
            metric_value=metric_value,
            ref="¹",
        )
    )
    return base_multiple


def _owner_risk_labels(
    step_data: Mapping[str, object] | None,
    t: ReportTranslations,
) -> tuple[str, str]:
    risk_level = step_data.get("owner_dependency_risk_level") if step_data else None
    normalized = str(risk_level or "").upper()
    if normalized in ("HIGH", "HOOG"):
        return t.ledger_risk_label_high, t.ledger_risk_high
    if normalized in ("MEDIUM", "GEMIDDELD"):
        return t.ledger_risk_label_medium, t.ledger_risk_medium
    return t.ledger_risk_label_low, t.ledger_risk_low


def _normalized_ratio(raw: object, *, force_negative: bool) -> Decimal:
    if not raw or raw == 0:
        return Decimal("0")
    ratio = safe_decimal(raw)
    if abs(to_float(ratio)) > 1:
        ratio = ratio / Decimal("100")
    if force_negative and ratio > 0:
        ratio = -ratio
    return ratio


def _owner_dependency_adjustment(
    *,
    step_data: Mapping[str, object] | None,
    response: object,
    base_multiple: Decimal,
    final_multiple: Decimal,
) -> tuple[Decimal, bool]:
    owner_pct = _normalized_ratio(
        step_data.get("owner_dependency_adjustment", 0.0) if step_data else 0.0,
        force_negative=False,
    )
    net_discount_threshold = base_multiple * Decimal("0.01")
    if (
        owner_pct == Decimal("0")
        and getattr(response, "owner_dependency_result", None)
        and final_multiple < base_multiple - net_discount_threshold
    ):
        return Decimal("-0.07"), True
    return owner_pct, False


def _discount_threshold(base_multiple: Decimal) -> Decimal:
    return max(abs(base_multiple) * Decimal("0.01"), Decimal("0.01"))


def _has_real_discount_gap(base_multiple: Decimal, final_multiple: Decimal) -> bool:
    return final_multiple < base_multiple - _discount_threshold(base_multiple)


def _append_calibration_adjustment_step(
    *,
    steps: list[JsonMap],
    metric_value: Decimal,
    running_multiple: Decimal,
    ratio: Decimal,
    label: str,
    description: object,
    ref: str,
) -> Decimal:
    if ratio == 0:
        return running_multiple
    impact = running_multiple * ratio
    next_multiple = running_multiple + impact
    steps.append(
        _calibration_step(
            label=label,
            description=description,
            multiple=next_multiple,
            impact=impact,
            metric_value=metric_value,
            ref=ref,
        )
    )
    return next_multiple


def _size_discount_label(step_data: Mapping[str, object] | None, t: ReportTranslations) -> str:
    size_tier = t.ledger_tier_micro
    if step_data and step_data.get("size_tier"):
        size_tier = str(step_data.get("size_tier"))
    return f"{size_tier} {t.calib_wf_size_discount_suffix}"


def _append_residual_calibration_step(
    *,
    steps: list[JsonMap],
    metric_value: Decimal,
    running_multiple: Decimal,
    base_multiple: Decimal,
    final_multiple: Decimal,
    t: ReportTranslations,
) -> Decimal:
    residual = final_multiple - running_multiple
    if abs(to_float(residual)) <= 0.01 * to_float(base_multiple):
        return running_multiple
    steps.append(
        _calibration_step(
            label=t.calib_wf_other_adjustment,
            description=t.calib_wf_other_adjustment_desc,
            multiple=final_multiple,
            impact=residual,
            metric_value=metric_value,
            ref="",
        )
    )
    return final_multiple


def build_calibration_steps(
    metric_value: Decimal,
    metric_type: str,
    base_multiple: Decimal,
    final_multiple: Decimal,
    response: object,
    step_data: Mapping[str, object] | None,
    t: ReportTranslations,
) -> list[JsonMap]:
    """
    Build fallback calibration steps when the Step 11 discount waterfall is unavailable.

    Converts percentage adjustments from Steps 4-6 into multiplicative multiple
    impacts. ``metric_type`` is retained for compatibility with existing callers.
    """
    del metric_type

    metric_value = safe_decimal(metric_value)
    base_multiple = safe_decimal(base_multiple)
    final_multiple = safe_decimal(final_multiple)

    if metric_value == 0 or final_multiple == 0:
        return [_not_applicable_calibration_step(t)]

    steps: list[JsonMap] = []
    running_multiple = _append_baseline_calibration_steps(
        steps=steps,
        metric_value=metric_value,
        base_multiple=base_multiple,
        step_data=step_data,
        t=t,
    )
    has_discount_gap = _has_real_discount_gap(base_multiple, final_multiple)
    owner_pct, used_default_owner_discount = _owner_dependency_adjustment(
        step_data=step_data,
        response=response,
        base_multiple=base_multiple,
        final_multiple=final_multiple,
    )
    if not has_discount_gap:
        owner_pct = Decimal("0")
        used_default_owner_discount = False
    owner_risk_level, owner_risk_desc = _owner_risk_labels(step_data, t)
    if used_default_owner_discount:
        owner_risk_level = t.ledger_risk_label_medium
        owner_risk_desc = t.ledger_risk_medium

    running_multiple = _append_calibration_adjustment_step(
        steps=steps,
        metric_value=metric_value,
        running_multiple=running_multiple,
        ratio=owner_pct,
        label=t.ledger_key_person_risk,
        description=f"{t.calib_wf_assessment_label}: {owner_risk_level} — {owner_risk_desc}",
        ref="",
    )
    running_multiple = _append_calibration_adjustment_step(
        steps=steps,
        metric_value=metric_value,
        running_multiple=running_multiple,
        ratio=(
            _normalized_ratio(
                step_data.get("size_discount_percentage", 0.0) if step_data else 0.0,
                force_negative=True,
            )
            if has_discount_gap
            else Decimal("0")
        ),
        label=_size_discount_label(step_data, t),
        description=t.calib_wf_size_discount_desc,
        ref="²",
    )
    running_multiple = _append_calibration_adjustment_step(
        steps=steps,
        metric_value=metric_value,
        running_multiple=running_multiple,
        ratio=(
            _normalized_ratio(
                step_data.get("total_discount_percentage", 0.0) if step_data else 0.0,
                force_negative=True,
            )
            if has_discount_gap
            else Decimal("0")
        ),
        label=t.ledger_dlom,
        description=t.ledger_dlom_desc,
        ref="³",
    )
    _append_residual_calibration_step(
        steps=steps,
        metric_value=metric_value,
        running_multiple=running_multiple,
        base_multiple=base_multiple,
        final_multiple=final_multiple,
        t=t,
    )

    return steps
