"""
Hybrid Methodology Package

Contains modular components for hybrid valuation (DCF + Multiples).

Components:
- HybridMethodologyOrchestrator: Main coordinator
- MethodologyEligibilityDecider: DCF eligibility decision (in domain/)
- HybridWeightCalculator: Weight calculation (in domain/)
- ValuationAggregator: Result aggregation (in domain/)

@author UpSwitch CTO Team
@version 1.0.0
@date November 2025
"""

from .hybrid_methodology_orchestrator import HybridMethodologyOrchestrator

__all__ = ["HybridMethodologyOrchestrator"]
