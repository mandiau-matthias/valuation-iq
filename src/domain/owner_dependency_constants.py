"""
Owner-dependency cap + engine band constants.

Single source of truth, lifted into its own module so both
`src.domain.models` and `src.domain.owner_models.owner_dependency` can
import these values at class-definition time without triggering a
circular import via `src.domain.models/__init__.py` (which re-exports
both modules).

See `src.domain.models` header for the relaxation playbook and the
engine-design rationale on the ceiling.
"""

from __future__ import annotations

from decimal import Decimal


# OWNER-PROFILING-1 MVP cap (SPIKE-1 §3.2)
MVP_OWNER_ADJUSTMENT_FLOOR: Decimal = Decimal("-0.15")
MVP_OWNER_ADJUSTMENT_CEILING: Decimal = Decimal("0.00")

# Damodaran 12-factor engine band — the raw output range of
# `OwnerDependencyEngine._determine_valuation_adjustment`. The MVP cap
# is a strict subset of this band; the cross-app drift guard at
# `tests/unit/synthesis/test_titan_prisma_check_drift.py` enforces that.
OWNER_DEPENDENCY_ENGINE_FLOOR: Decimal = Decimal("-0.40")
OWNER_DEPENDENCY_ENGINE_CEILING: Decimal = Decimal("0.00")
