"""
Shared utilities for valuation calculations.

This module contains shared data structures and utilities used across
multiple valuation calculation steps.
"""

from decimal import Decimal

from src.utils.decimal_helpers import from_decimal, to_decimal

from .historical_years import (
    historical_years_in_chronological_order,
    newest_historical_year,
    oldest_and_newest_historical_years,
    oldest_historical_year,
)
from .multiple_pipeline import (
    MultiplePipeline,
    MultiplePipelineStage,
    calculate_total_reduction,
    create_pipeline_stage,
)

__all__ = [
    "MultiplePipeline",
    "MultiplePipelineStage",
    "create_pipeline_stage",
    "calculate_total_reduction",
    "oldest_historical_year",
    "newest_historical_year",
    "oldest_and_newest_historical_years",
    "historical_years_in_chronological_order",
]
