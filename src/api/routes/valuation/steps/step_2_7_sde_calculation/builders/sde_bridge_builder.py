"""SDE bridge row builder for Step 2.7 reporting."""

from __future__ import annotations

from typing import Optional


def _component_float(sde_components: dict, key: str) -> float:
    return float(sde_components.get(key) or 0)


def _owner_compensation_label(owner_role: Optional[str]) -> str:
    if owner_role == "passive":
        return "Passive investor compensation add-back (full)"
    if owner_role == "working":
        return "Working owner — delta vs. market salary"
    return "Owner compensation add-back"


def _bridge_row(label: str, amount: float, running_total: float, kind: str) -> dict[str, object]:
    return {
        "label": label,
        "amount": round(amount, 2),
        "running_total": round(running_total, 2),
        "kind": kind,
    }


def _append_addback(
    bridge: list[dict[str, object]],
    *,
    label: str,
    amount: float,
    running_total: float,
) -> float:
    running_total += amount
    bridge.append(_bridge_row(label, amount, running_total, "addback"))
    return running_total


def _build_ebitda_fallback_bridge(
    *,
    ebitda: float,
    explicit_addback: float,
    owner_label: str,
) -> list[dict[str, object]]:
    return [
        _bridge_row("Normalised EBITDA", ebitda, ebitda, "anchor"),
        _bridge_row(
            f"+ {owner_label}",
            explicit_addback,
            ebitda + explicit_addback,
            "addback",
        ),
    ]


def build_sde_bridge(
    *,
    sde_components: dict,
    ebitda: float,
    explicit_addback: float,
    owner_role: Optional[str] = None,
) -> list[dict[str, object]]:
    """Build the Reported Net Profit -> SDE reconciliation ladder."""
    try:
        net_income = _component_float(sde_components, "net_income")
        interest = _component_float(sde_components, "interest_expense")
        depreciation = _component_float(sde_components, "depreciation")
        amortisation = _component_float(sde_components, "amortization")
        owner_salary = _component_float(sde_components, "owner_salary")
        owner_benefits = _component_float(sde_components, "owner_benefits")
        owner_perks = _component_float(sde_components, "owner_perks")
        non_recurring = _component_float(sde_components, "non_recurring_expenses")
        non_operating = _component_float(sde_components, "non_operating_income")
        total_sde = _component_float(sde_components, "total_sde")
    except (TypeError, ValueError):
        return []

    owner_label = _owner_compensation_label(owner_role)
    running_total = net_income
    bridge = [_bridge_row("Reported net income", net_income, running_total, "anchor")]

    addbacks = [
        ("+ Interest expense", interest),
        ("+ Depreciation", depreciation),
        ("+ Amortisation", amortisation),
        (f"+ {owner_label}", owner_salary),
        ("+ Owner benefits", owner_benefits),
        ("+ Owner perks / discretionary", owner_perks),
        ("+ Non-recurring expenses", non_recurring),
        ("− Non-operating income", -non_operating if non_operating else 0),
    ]
    for label, amount in addbacks:
        if amount:
            running_total = _append_addback(
                bridge,
                label=label,
                amount=amount,
                running_total=running_total,
            )

    if explicit_addback and not owner_salary:
        bridge = _build_ebitda_fallback_bridge(
            ebitda=ebitda,
            explicit_addback=explicit_addback,
            owner_label=owner_label,
        )

    bridge.append(
        _bridge_row(
            "= Seller's Discretionary Earnings (SDE)",
            total_sde,
            total_sde,
            "total",
        )
    )
    return bridge
