"""
Phase Determiner

Responsibility: Determine valuation phase based on data completeness.

Single Responsibility: Phase determination logic only.
"""

from typing import Any, Dict

from src.utils.logging import get_logger

from .progressive_valuation_types import ValuationPhase

logger = get_logger(__name__)


class PhaseDeterminer:
    """
    Determines valuation phase based on data completeness.

    Single Responsibility: Phase determination only.
    """

    def __init__(self):
        """Initialize phase determiner"""
        self.logger = logger
        self.required_fields = {
            ValuationPhase.INSTANT: [],  # ANY data triggers instant preview
            ValuationPhase.PREVIEW: ["revenue", "industry"],
            ValuationPhase.INTERMEDIATE: ["revenue", "industry", "ebitda", "growth_rate"],
            ValuationPhase.ADVANCED: [
                "revenue",
                "industry",
                "ebitda",
                "growth_rate",
                "total_assets",
                "total_debt",
                "cash",
            ],
            ValuationPhase.COMPLETE: [
                "revenue",
                "industry",
                "ebitda",
                "growth_rate",
                "total_assets",
                "total_debt",
                "cash",
                "owner_profile",
            ],
        }

    def determine_phase(self, data: Dict[str, Any]) -> ValuationPhase:
        """
        Determine current phase based on data completeness

        Args:
            data: Collected data dictionary

        Returns:
            ValuationPhase enum value
        """
        self.logger.debug(f"[VALUATION] Determining phase | fields={list(data.keys())}")

        # Check if we have ANY data for instant preview
        has_any_data = len([v for v in data.values() if v is not None and v != ""]) > 0
        if has_any_data and not any(
            field in data and data[field] is not None for field in ["revenue", "industry"]
        ):
            self.logger.info(f"[VALUATION] Determined phase: INSTANT | has_any_data={has_any_data}")
            return ValuationPhase.INSTANT

        # Check phases in reverse order (most complete first)
        for phase in reversed(list(ValuationPhase)):
            if phase == ValuationPhase.INSTANT:
                continue  # Skip instant phase in main loop
            phase_fields = self.required_fields[phase]
            has_all_fields = all(
                field in data and data[field] is not None for field in phase_fields
            )
            self.logger.debug(
                f"[VALUATION] Phase {phase.name}: {has_all_fields} | required={phase_fields}"
            )
            if has_all_fields:
                self.logger.info(
                    f"[VALUATION] Determined phase: {phase.name} | criteria_met={phase_fields}"
                )
                return phase

        self.logger.info(
            f"[VALUATION] Defaulting to Phase 0 (INSTANT) | available_fields={[k for k, v in data.items() if v is not None]}"
        )
        return ValuationPhase.INSTANT
