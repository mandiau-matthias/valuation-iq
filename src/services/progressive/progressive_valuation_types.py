"""Shared DTOs for the progressive valuation workflow."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict


class ValuationPhase(Enum):
    """Valuation calculation phases based on data completeness."""

    INSTANT = 0
    PREVIEW = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    COMPLETE = 4


@dataclass
class ValuationInstant:
    """Phase 0: instant preview from any data."""

    welcome_html: str
    progress_html: str
    placeholder_range: str
    confidence: str
    data_collected: int
    data_total: int
    next_steps: list
    timestamp: str


@dataclass
class ValuationPreview:
    """Phase 1: quick multiple-based estimate."""

    value_low: Decimal
    value_mid: Decimal
    value_high: Decimal
    confidence_score: Decimal
    confidence_level: str
    methodology: str
    multiple_low: Decimal
    multiple_high: Decimal
    industry: str
    data_completeness: Decimal
    timestamp: str


@dataclass
class ValuationIntermediate:
    """Phase 2: simplified DCF plus multiples."""

    dcf_data: Dict[str, object]
    multiples_data: Dict[str, object]
    combined_value_low: Decimal
    combined_value_mid: Decimal
    combined_value_high: Decimal
    confidence_score: Decimal
    methodology_weights: Dict[str, Decimal]
    timestamp: str


@dataclass
class ValuationAdvanced:
    """Phase 3: full DCF plus multiples and adjustments."""

    dcf_complete: Dict[str, object]
    adjustments: Dict[str, object]
    final_value_low: Decimal
    final_value_mid: Decimal
    final_value_high: Decimal
    confidence_score: Decimal
    risk_factors: list
    value_drivers: list
    timestamp: str


@dataclass
class ValuationComplete:
    """Phase 4: complete valuation with owner factor."""

    owner_analysis: Dict[str, object]
    final_valuation: Dict[str, object]
    valuation_id: str
    executive_summary: str
    recommendations: list
    confidence_score: Decimal
    timestamp: str


__all__ = [
    "ValuationAdvanced",
    "ValuationComplete",
    "ValuationInstant",
    "ValuationIntermediate",
    "ValuationPhase",
    "ValuationPreview",
]
