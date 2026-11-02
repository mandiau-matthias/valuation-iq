"""
Owner Profiling Services — DEPRECATED.

This package is the pre-OWNER-PROFILING-1 implementation and is dormant in
production: the live owner-dependency adjustment runs through
`src.domain.synthesis.owner_dependency_processor.OwnerDependencyProcessor`,
backed by `src.domain.owner_dependency_engine.OwnerDependencyEngine`
(12-factor Damodaran). Nothing in the request path imports from this package.

DO NOT extend. New "owner risk" / "key person" / "transferability" features
must extend the live engine. See:
  - docs/product/features/active-development/owner-profiling-mvp.md
  - apps/valuation-iq/src/domain/owner_dependency_engine.py
  - apps/valuation-iq/src/domain/synthesis/owner_dependency_processor.py

Sprint 3 will delete this package outright. Until then, importing it emits
a DeprecationWarning so any drift back to this surface is visible in CI.

If you have a legitimate reason to silence the warning (e.g. a one-off
historical replay tool), set the env var
`UPSWITCH_ALLOW_OWNER_PROFILING_LEGACY=1` — but log a ticket first.
"""

from __future__ import annotations

import os
import warnings

if os.environ.get("UPSWITCH_ALLOW_OWNER_PROFILING_LEGACY") != "1":
    warnings.warn(
        (
            "src.services.owner_profiling is DEPRECATED and dormant in "
            "production. The live adjustment is "
            "src.domain.synthesis.owner_dependency_processor."
            "OwnerDependencyProcessor. Do not extend this package; it is "
            "scheduled for deletion in Sprint 3 (see docs/product/features/"
            "active-development/owner-profiling-mvp.md). Set "
            "UPSWITCH_ALLOW_OWNER_PROFILING_LEGACY=1 to silence."
        ),
        DeprecationWarning,
        stacklevel=2,
    )

from .owner_profiling_engine import OwnerProfilingEngine, OwnerProfile
from .enhanced_owner_profiling_engine import EnhancedOwnerProfilingEngineRefactored as EnhancedOwnerProfilingEngine

# Refactored modules
from .risk_analyzer import RiskAnalyzer
from .profile_builder import ProfileBuilder
from .profiling_types import (
    RiskLevel, TechnicalRequirement, OwnerRiskAssessment,
    OwnerRiskAssessmentReport, OWNER_QUESTIONS, TECHNICAL_REQUIREMENTS, RISK_ASSESSMENT_RULES
)

__all__ = [
    "OwnerProfilingEngine",
    "OwnerProfile",
    "EnhancedOwnerProfilingEngine",
    # Refactored modules
    "EnhancedOwnerProfilingEngineRefactored",
    "RiskAnalyzer",
    "ProfileBuilder",
    "RiskLevel",
    "TechnicalRequirement",
    "OwnerRiskAssessment",
    "OwnerRiskAssessmentReport",
    "OWNER_QUESTIONS",
    "TECHNICAL_REQUIREMENTS",
    "RISK_ASSESSMENT_RULES",
]
