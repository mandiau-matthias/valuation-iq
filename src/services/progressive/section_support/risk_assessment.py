"""Risk assessment helpers for progressive valuation sections."""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from src.utils.decimal_helpers import from_decimal, to_decimal


class RiskFactor(TypedDict):
    name: str
    description: str
    severity: str
    impact: float


class RiskAdjustment(TypedDict):
    name: str
    value: float


def calculate_size_risk(revenue: Decimal | float | int) -> tuple[int, RiskFactor | None]:
    """Calculate size-based risk factor."""
    revenue_decimal = to_decimal(revenue)
    if revenue_decimal < Decimal("1000000"):
        return 25, {
            "name": "Company Size Risk",
            "description": "Small company size increases operational and market risk",
            "severity": "high",
            "impact": -15.0,
        }
    if revenue_decimal < Decimal("5000000"):
        return 15, {
            "name": "Company Size Risk",
            "description": "Medium-sized company with moderate scale risk",
            "severity": "medium",
            "impact": -8.0,
        }
    return 5, {
        "name": "Company Size Risk",
        "description": "Adequate company size with limited scale risk",
        "severity": "low",
        "impact": -3.0,
    }


def calculate_profitability_risk(
    ebitda: Decimal | float | int,
    revenue: Decimal | float | int,
) -> tuple[int, RiskFactor | None]:
    """Calculate profitability-based risk factor."""
    ebitda_decimal = to_decimal(ebitda)
    revenue_decimal = to_decimal(revenue)

    if ebitda_decimal <= 0 or revenue_decimal <= 0:
        return 0, None

    ebitda_margin_decimal = (ebitda_decimal / revenue_decimal) * Decimal("100")
    ebitda_margin_float = from_decimal(ebitda_margin_decimal)

    if ebitda_margin_float < 10:
        return 20, {
            "name": "Profitability Risk",
            "description": "Low margins indicate operational efficiency challenges",
            "severity": "high",
            "impact": -12.0,
        }
    if ebitda_margin_float < 20:
        return 10, {
            "name": "Profitability Risk",
            "description": "Moderate margins with room for improvement",
            "severity": "medium",
            "impact": -5.0,
        }
    return 5, {
        "name": "Profitability Risk",
        "description": "Strong margins demonstrate operational excellence",
        "severity": "low",
        "impact": -2.0,
    }


def calculate_growth_risk(growth_rate: float) -> tuple[int, RiskFactor | None]:
    """Calculate growth-based risk factor."""
    if growth_rate < 0:
        return 25, {
            "name": "Growth Risk",
            "description": "Negative growth indicates market or operational challenges",
            "severity": "high",
            "impact": -15.0,
        }
    if growth_rate < 10:
        return 15, {
            "name": "Growth Risk",
            "description": "Modest growth rate below industry averages",
            "severity": "medium",
            "impact": -7.0,
        }
    return 5, {
        "name": "Growth Risk",
        "description": "Strong growth trajectory supports valuation",
        "severity": "low",
        "impact": -2.0,
    }


def calculate_team_risk(employees: int) -> tuple[int, RiskFactor | None]:
    """Calculate team size-based risk factor."""
    if employees < 5:
        return 20, {
            "name": "Team Dependency Risk",
            "description": "Small team increases key person dependency",
            "severity": "high",
            "impact": -10.0,
        }
    if employees < 20:
        return 10, {
            "name": "Team Dependency Risk",
            "description": "Limited team size creates succession planning needs",
            "severity": "medium",
            "impact": -5.0,
        }
    return 0, None


def build_risk_adjustments(risk_factors: list[RiskFactor]) -> tuple[list[RiskAdjustment], float]:
    """Build valuation adjustment rows and total adjustment from risk factors."""
    adjustments = [{"name": risk["name"], "value": risk["impact"]} for risk in risk_factors]
    total_adjustment = sum(float(risk["impact"]) for risk in risk_factors)
    return adjustments, total_adjustment


def get_mitigation_strategies() -> list[str]:
    """Get standard mitigation strategies for progressive risk assessment."""
    return [
        "Diversify customer base to reduce concentration risk",
        "Implement robust financial controls and reporting",
        "Develop succession planning and knowledge transfer programs",
        "Build operational resilience through process documentation",
        "Strengthen market position through differentiation",
    ]
