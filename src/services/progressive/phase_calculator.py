"""
Phase Calculator

Responsibility: Calculate valuations for each phase.

Single Responsibility: Phase calculation coordination only.
"""

import time
from collections.abc import Mapping
from decimal import Decimal

from src.utils.logging import get_logger

from .coordinators import (
    HTMLGenerationCoordinator,
    MockCalculationCoordinator,
    SummaryGenerationCoordinator,
)
from .progressive_valuation_types import (
    ValuationAdvanced,
    ValuationComplete,
    ValuationInstant,
    ValuationIntermediate,
    ValuationPreview,
)

logger = get_logger(__name__)


class PhaseCalculator:
    """
    Calculates valuations for each phase.

    Single Responsibility: Phase calculation coordination only.
    """

    def __init__(
        self,
        html_coordinator: HTMLGenerationCoordinator,
        mock_coordinator: MockCalculationCoordinator,
        summary_coordinator: SummaryGenerationCoordinator,
    ) -> None:
        """
        Initialize phase calculator with injected dependencies

        Args:
            html_coordinator: HTML generation coordinator
            mock_coordinator: Mock calculation coordinator
            summary_coordinator: Summary generation coordinator
        """
        self.html_coordinator = html_coordinator
        self.mock_coordinator = mock_coordinator
        self.summary_coordinator = summary_coordinator
        self.logger = logger

    def _industry(self, data: Mapping[str, object]) -> str:
        return str(data.get("industry") or "unknown")

    async def calculate_phase_0_instant(self, data: Mapping[str, object]) -> ValuationInstant:
        """
        Phase 0: Instant preview from ANY data

        Args:
            data: Collected data dictionary

        Returns:
            ValuationInstant result
        """
        self.logger.info(
            f"[VALUATION] Calculating Phase 0 instant preview | data={list(data.keys())}"
        )

        # Count collected data
        collected_count = len([v for v in data.values() if v is not None and v != ""])
        total_fields = 8  # Total fields we'll collect

        # Generate welcome HTML
        welcome_html = self.html_coordinator.generate_welcome_html(data)

        # Generate progress HTML
        progress_html = self.html_coordinator.generate_progress_html(collected_count, total_fields)

        # Generate placeholder valuation range
        placeholder_range = self.html_coordinator.generate_placeholder_range(data)

        # Generate next steps
        next_steps = self.html_coordinator.generate_next_steps(data)

        return ValuationInstant(
            welcome_html=welcome_html,
            progress_html=progress_html,
            placeholder_range=placeholder_range,
            confidence="Preliminary",
            data_collected=collected_count,
            data_total=total_fields,
            next_steps=next_steps,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def calculate_phase_1_preview(
        self,
        data: Mapping[str, object],
        use_mock: bool = False,
    ) -> ValuationPreview:
        """
        Phase 1: Quick preview with revenue and industry

        Args:
            data: Collected data dictionary
            use_mock: Whether to use mock calculations

        Returns:
            ValuationPreview result
        """
        self.logger.info(f"[VALUATION] Calculating Phase 1 preview | use_mock={use_mock}")

        industry = self._industry(data)

        return ValuationPreview(
            value_low=Decimal("0"),
            value_mid=Decimal("0"),
            value_high=Decimal("0"),
            confidence_score=Decimal("0"),
            confidence_level="Low",
            methodology="Phase calculator placeholder",
            multiple_low=Decimal("0"),
            multiple_high=Decimal("0"),
            industry=industry,
            data_completeness=Decimal("25.0"),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def calculate_phase_2_intermediate(
        self,
        data: Mapping[str, object],
        use_mock: bool = False,
    ) -> ValuationIntermediate:
        """Phase 2: Intermediate calculation with DCF and Multiples"""
        self.logger.info(f"[VALUATION] Calculating Phase 2 intermediate | use_mock={use_mock}")

        return ValuationIntermediate(
            dcf_data={},
            multiples_data={},
            combined_value_low=Decimal("0"),
            combined_value_mid=Decimal("0"),
            combined_value_high=Decimal("0"),
            confidence_score=Decimal("0"),
            methodology_weights={"dcf": Decimal("0"), "multiples": Decimal("0")},
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def calculate_phase_3_advanced(
        self,
        data: Mapping[str, object],
        use_mock: bool = False,
    ) -> ValuationAdvanced:
        """Phase 3: Advanced calculation with all financial data"""
        self.logger.info(f"[VALUATION] Calculating Phase 3 advanced | use_mock={use_mock}")

        return ValuationAdvanced(
            dcf_complete={},
            adjustments={},
            final_value_low=Decimal("0"),
            final_value_mid=Decimal("0"),
            final_value_high=Decimal("0"),
            confidence_score=Decimal("0"),
            risk_factors=[],
            value_drivers=[],
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def calculate_phase_4_complete(
        self,
        data: Mapping[str, object],
        use_mock: bool = False,
    ) -> ValuationComplete:
        """Phase 4: Complete calculation with owner profiling"""
        self.logger.info(f"[VALUATION] Calculating Phase 4 complete | use_mock={use_mock}")
        final_valuation = {
            "value_low": Decimal("0"),
            "value_mid": Decimal("0"),
            "value_high": Decimal("0"),
        }
        owner_analysis: dict[str, object] = {}

        return ValuationComplete(
            owner_analysis=owner_analysis,
            final_valuation=final_valuation,
            valuation_id=str(data.get("valuation_id") or ""),
            executive_summary=self.summary_coordinator.generate_executive_summary(
                data,
                final_valuation,
            ),
            recommendations=self.summary_coordinator.generate_recommendations(
                data,
                owner_analysis,
            ),
            confidence_score=Decimal("0"),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
