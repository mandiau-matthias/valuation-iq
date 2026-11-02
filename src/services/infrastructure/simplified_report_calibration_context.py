"""Sensitivity and calibration context helpers for simplified reports."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from src.services.infrastructure.simplified_report_formatting import (
    format_currency,
    format_multiple,
    parse_decimal_or_none,
    safe_decimal,
)
from src.services.infrastructure.simplified_report_types import JsonRows

_DEFAULT_OWNER_DISCOUNT = Decimal("-0.35")
_MULTIPLE_TOLERANCE = Decimal("0.01")


def build_sensitivity_table(
    metric_value: Decimal,
    metric_type: str,
    multiple: Optional[Decimal],
    multiple_low: Optional[Decimal],
    multiple_high: Optional[Decimal],
) -> JsonRows:
    """Build sensitivity analysis rows for the simplified report."""
    if metric_value is None or multiple is None:
        return []

    metric_variations = [Decimal("-0.20"), Decimal("0"), Decimal("0.20")]

    mult_low = multiple_low if multiple_low is not None else (multiple * Decimal("0.7"))
    mult_high = multiple_high if multiple_high is not None else (multiple * Decimal("1.3"))
    multiples = [mult_low, multiple, mult_high]

    rows: JsonRows = []
    for metric_var in metric_variations:
        adjusted_metric = metric_value * (1 + metric_var)
        ev_values = [adjusted_metric * active_multiple for active_multiple in multiples]

        rows.append(
            {
                "metric_value": adjusted_metric,
                "metric_formatted": format_currency(adjusted_metric),
                "metric_type": metric_type,
                "ev_low": f"€{int(ev_values[0] / 1000)}K",
                "ev_mid": f"€{int(ev_values[1] / 1000)}K",
                "ev_high": f"€{int(ev_values[2] / 1000)}K",
                "is_base": metric_var == Decimal("0"),
            }
        )

    return rows


def build_calibration_steps(
    metric_value: Decimal,
    metric_type: str,
    base_multiple: Decimal,
    final_multiple: Optional[Decimal],
    response: object,
) -> JsonRows:
    """Build simplified calibration ledger rows."""
    del metric_type
    if metric_value is None or final_multiple is None:
        return []

    metric_value = safe_decimal(metric_value)
    base_multiple = safe_decimal(base_multiple)
    final_multiple = safe_decimal(final_multiple)
    steps: JsonRows = []
    running_multiple = base_multiple
    has_discount_gap = final_multiple < (base_multiple - _discount_threshold(base_multiple))

    ev = metric_value * running_multiple
    steps.append(
        {
            "label": "1. Markt Consensus (P50 Mediaan)",
            "description": None,
            "running_multiple": format_multiple(running_multiple),
            "impact": None,
            "impact_formatted": "—",
            "ev": ev,
            "ev_formatted": format_currency(ev),
            "ref": "¹",
        }
    )

    key_person_discount = Decimal("0")
    if getattr(response, "owner_dependency_result", None) and has_discount_gap:
        key_person_discount = _clamp_discount_to_remaining_gap(
            _DEFAULT_OWNER_DISCOUNT,
            final_multiple - running_multiple,
        )

    if key_person_discount != 0:
        running_multiple += key_person_discount
        ev = metric_value * running_multiple
        steps.append(
            {
                "label": "2. Sleutelpersoon Risico",
                "description": "Beoordeling: GEMIDDELD",
                "running_multiple": format_multiple(running_multiple),
                "impact": key_person_discount,
                "impact_formatted": f"{format_multiple(key_person_discount)}×",
                "ev": ev,
                "ev_formatted": format_currency(ev),
                "ref": "",
            }
        )
    else:
        steps.append(
            {
                "label": "2. Sleutelpersoon Risico",
                "description": "Beoordeling: LAAG — gediversifieerd klantenbestand",
                "running_multiple": format_multiple(running_multiple),
                "impact": None,
                "impact_formatted": "—",
                "ev": ev,
                "ev_formatted": format_currency(ev),
                "ref": "",
            }
        )

    size_discount = extract_size_discount_for_calibration(response)
    if not has_discount_gap:
        size_discount = Decimal("0")
    else:
        size_discount = _clamp_discount_to_remaining_gap(
            size_discount,
            final_multiple - running_multiple,
        )
    if size_discount != Decimal("0"):
        running_multiple += size_discount
        ev = metric_value * running_multiple
        steps.append(
            {
                "label": "3. Micro-KMO Korting",
                "description": "Afzonderlijke omvangscorrectie uit rekenstap 5",
                "running_multiple": format_multiple(running_multiple),
                "impact": size_discount,
                "impact_formatted": f"{format_multiple(size_discount)}×",
                "ev": ev,
                "ev_formatted": format_currency(ev),
                "ref": "²",
            }
        )
    else:
        steps.append(
            {
                "label": "3. Omvangscorrectie",
                "description": "Ingebed in de SME/private-transactie referentiemultiple",
                "running_multiple": format_multiple(running_multiple),
                "impact": None,
                "impact_formatted": "—",
                "ev": ev,
                "ev_formatted": format_currency(ev),
                "ref": "²",
            }
        )

    dlom = final_multiple - running_multiple
    if has_discount_gap and dlom < -_MULTIPLE_TOLERANCE:
        running_multiple = final_multiple
        ev = metric_value * running_multiple
        steps.append(
            {
                "label": "4. Illiquiditeitskorting (DLOM)",
                "description": "Privé-ondernemingen verkopen trager",
                "running_multiple": format_multiple(running_multiple),
                "impact": dlom,
                "impact_formatted": f"{format_multiple(dlom)}×",
                "ev": ev,
                "ev_formatted": format_currency(ev),
                "ref": "³",
            }
        )
    else:
        steps.append(
            {
                "label": "4. Illiquiditeitskorting (DLOM)",
                "description": "Geen afzonderlijke DLOM toegepast in deze indicatie",
                "running_multiple": format_multiple(running_multiple),
                "impact": None,
                "impact_formatted": "—",
                "ev": ev,
                "ev_formatted": format_currency(ev),
                "ref": "³",
            }
        )

    return steps


def _discount_threshold(base_multiple: Decimal) -> Decimal:
    return max(abs(base_multiple) * Decimal("0.01"), _MULTIPLE_TOLERANCE)


def _clamp_discount_to_remaining_gap(discount: Decimal, remaining_gap: Decimal) -> Decimal:
    """Keep fallback discounts from crossing below the applied multiple."""
    if discount >= Decimal("0") or remaining_gap >= Decimal("0"):
        return Decimal("0")
    return max(discount, remaining_gap)


def extract_size_discount_for_calibration(response: object) -> Decimal:
    """Return the explicit size-discount delta for the simplified ledger."""
    transparency = getattr(response, "transparency", None)
    calculation_steps = getattr(transparency, "calculation_steps", None)
    if not isinstance(calculation_steps, dict):
        return Decimal("0")

    multiples_steps = calculation_steps.get("multiples")
    if not isinstance(multiples_steps, list) or len(multiples_steps) <= 5:
        return Decimal("0")

    step_5 = multiples_steps[5]
    result = step_5.get("result") if isinstance(step_5, dict) else None
    if not isinstance(result, dict):
        return Decimal("0")

    raw = result.get("size_discount_percentage")
    if raw is None:
        raw = result.get("size_discount")
    value = parse_decimal_or_none(raw)
    if value is None or value == Decimal("0"):
        return Decimal("0")
    if value > Decimal("0"):
        value = -value
    if abs(value) > Decimal("1"):
        value = value / Decimal("100")
    return value
