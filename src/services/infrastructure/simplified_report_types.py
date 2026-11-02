"""Shared types for simplified report context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, TypeAlias

JsonObject: TypeAlias = Dict[str, object]
JsonRows: TypeAlias = List[JsonObject]
TemplateContext: TypeAlias = Dict[str, object]


@dataclass
class AdjustmentData:
    """EBITDA adjustment for display in template."""

    label: str
    amount: Decimal
    amount_formatted: str
    type: str  # 'base', 'add', 'subtract', 'result'
    category: str  # 'owner', 'nonRecurring', 'base', 'result'
    description: Optional[str] = None
    source: Optional[str] = None  # 'yuki', 'exact', 'manual', 'suggestion'
    source_ref: Optional[str] = None
    status: Optional[str] = None  # 'approved', 'pending', 'rejected'
    approved_by: Optional[str] = None


@dataclass
class MultiYearData:
    """Multi-year EBITDA data for display."""

    year: int
    reported: Decimal
    reported_formatted: str
    normalized: Decimal
    normalized_formatted: str
    weight: Decimal
    weight_pct: int
    weighted: Decimal
    weighted_formatted: str


@dataclass
class SensitivityRow:
    """Row in the sensitivity analysis table."""

    ebitda: Decimal
    ebitda_formatted: str
    ev_low: str
    ev_mid: str
    ev_high: str
    is_base: bool


@dataclass
class CalibrationStep:
    """Step in the calibration ledger."""

    label: str
    description: Optional[str]
    running_multiple: str
    impact: Optional[Decimal]
    impact_formatted: str
    ev: Decimal
    ev_formatted: str
    ref: Optional[str]
