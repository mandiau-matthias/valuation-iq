"""Simplified DCF fallback construction for recoverable engine failures."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, cast

from src.domain.models import ConfidenceLevel
from src.utils.decimal_helpers import to_decimal

from .dcf_manual_overrides import discount_to_present


@dataclass(frozen=True)
class SimplifiedDCFResult:
    """Fallback result shape consumed by the API-layer DCF orchestrator."""

    enterprise_value: Decimal
    equity_value: Decimal
    wacc: Decimal
    cost_of_equity: Decimal
    cost_of_debt: Decimal
    terminal_growth_rate: Decimal
    terminal_value: Decimal
    pv_terminal_value: Decimal
    cash_flow_projections: list[Decimal]
    pv_fcf_projections: list[Decimal]
    sensitivity_wacc: dict[str, Decimal]
    sensitivity_growth: dict[str, Decimal]
    confidence: ConfidenceLevel
    confidence_score: int
    confidence_factors: dict[str, str]
    audit_trail: dict[str, object]
    ebitda_multiple: Decimal


def build_simplified_dcf_fallback(
    *,
    ebitda: Optional[Decimal],
    current_year_ebitda: Optional[Decimal],
    net_debt: Decimal,
    cash: Decimal,
    confidence: ConfidenceLevel,
    confidence_score: int,
    confidence_factors: dict[str, str],
    fallback_reason: str,
) -> SimplifiedDCFResult:
    """Build the conservative simplified fallback used when full DCF cannot run."""
    safe_ebitda = cast(
        Decimal,
        to_decimal(ebitda if ebitda is not None else (current_year_ebitda or Decimal("0.0"))),
    )
    net_debt_value = cast(Decimal, to_decimal(net_debt))
    cash_value = cast(Decimal, to_decimal(cash))

    ebitda_multiple = Decimal("8.0")
    enterprise_value = safe_ebitda * ebitda_multiple
    equity_value = enterprise_value - net_debt_value + cash_value
    wacc = Decimal("0.10")
    cost_of_equity = Decimal("0.12")
    cost_of_debt = Decimal("0.05")
    terminal_growth_rate = Decimal("0.03")
    terminal_value = enterprise_value * Decimal("0.6")
    pv_terminal_value = discount_to_present(
        terminal_value,
        wacc,
        Decimal("4.5"),
    )
    cash_flow_projections = [safe_ebitda * Decimal("0.8")] * 5
    pv_fcf_projections = [
        discount_to_present(
            projected_fcf,
            wacc,
            Decimal(str(index + 1)) - Decimal("0.5"),
        )
        for index, projected_fcf in enumerate(cash_flow_projections)
    ]

    return SimplifiedDCFResult(
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        wacc=wacc,
        cost_of_equity=cost_of_equity,
        cost_of_debt=cost_of_debt,
        terminal_growth_rate=terminal_growth_rate,
        terminal_value=terminal_value,
        pv_terminal_value=pv_terminal_value,
        cash_flow_projections=cash_flow_projections,
        pv_fcf_projections=pv_fcf_projections,
        sensitivity_wacc={},
        sensitivity_growth={},
        confidence=confidence,
        confidence_score=confidence_score,
        confidence_factors=confidence_factors,
        audit_trail={
            "step_count": 0,
            "source_count": 0,
            "steps": [],
            "sources": [],
            "fallback_reason": fallback_reason,
        },
        ebitda_multiple=ebitda_multiple,
    )
