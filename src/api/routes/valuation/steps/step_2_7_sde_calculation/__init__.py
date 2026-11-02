"""
Step 2.7: SDE (Seller's Discretionary Earnings) Calculation

This step calculates SDE-based valuation for small, owner-operated businesses.
SDE is the standard methodology for businesses with revenue < EUR 2M.

ACADEMIC FOUNDATION:
- Trugman (2017): "Understanding Business Valuation" - THE definitive SME standard
- West & Jones (2012): "Handbook of Business Valuation" - SDE normalization
- BizBuySell (2024): Market Report - SDE multiples by industry
- Pepperdine (2024): Private Capital Markets Report

WHEN EXECUTED:
- Revenue < EUR 500K: Always execute (primary methodology)
- Revenue EUR 500K-2M + owner-operated: Execute (primary)
- Revenue EUR 2M-10M + service business: Execute (secondary for transparency)
- Revenue > EUR 10M: Skip (use EBITDA multiples instead)

TRIAGE RULE: CONDITIONAL_SDE in business_type_triage.py

@module step_2_7_sde_calculation
@author UpSwitch CTO Team
@date January 2026
"""

from .orchestrators.step_2_7_orchestrator import Step27Orchestrator
from .step_2_7 import Step27SDECalculation

__all__ = ["Step27Orchestrator", "Step27SDECalculation"]
