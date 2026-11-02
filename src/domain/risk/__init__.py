"""
Risk Factor Correlation and Calibration Module

This module provides correlation-aware risk adjustment calibration for SME valuations.
It handles the interaction between correlated risk factors (size, revenue trend, liquidity)
to prevent over-conservative valuations while maintaining academic rigor.

Academic Foundation:
- McKinsey (2015): "Valuation", Chapter 11 - Correlated risk adjustment framework
- Duff & Phelps (2024): Empirical validation of combined adjustments
- Size × Liquidity correlation: r ≈ 0.65 (Officer 2007, Koeplin 2000)
- Size × Revenue Trend correlation: r ≈ 0.40 (empirical SME transaction data)

Author: Upswitch Engineering Team
Date: December 20, 2025
Status: Production Ready
"""

from .correlation_aware_calculator import CorrelationAwareCalculator

__all__ = ["CorrelationAwareCalculator"]

