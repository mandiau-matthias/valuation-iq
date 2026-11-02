"""
Multiple Journey Builder

Builds the multiple waterfall journey for display, showing how the base multiple
is adjusted through Steps 2, 2.5, 4, 5, 6 to arrive at the final adjusted multiple.

MULTIPLE-FIRST METHODOLOGY:
All quality and risk adjustments are applied to the multiple, creating a clear
"multiple waterfall" from base (4.0x) to final (2.6x).
"""

from __future__ import annotations

from src.services.interfaces.request_response_protocol import ValuationResponseProtocol
from src.utils.core.data_extraction_helpers import extract_step_result
from src.utils.logging import get_logger

from .multiple_journey_steps import (
    LIQUIDITY_DISCOUNT_STEP,
    OWNER_CONCENTRATION_STEP,
    SIZE_DISCOUNT_STEP,
    append_base_multiple_step,
    append_discount_step,
    append_quality_calibration_step,
)
from .multiple_journey_summary import (
    build_fallback_multiple_journey,
    get_multiple_journey_step_results,
    log_final_journey_summary,
    log_successful_multiple_journey,
)

logger = get_logger(__name__)


class MultipleJourneyBuilder:
    """
    Builds the multiple waterfall journey for display.

    Extracts multiple at each step to show the progression:
    Step 2:   4.00x (base from comparables)
    Step 2.5: 3.80x (-0.20x quality calibration)
    Step 4:   3.04x (-0.76x owner concentration)
    Step 5:   2.80x (-0.24x size discount)
    Step 6:   2.60x (-0.20x liquidity discount)

    This makes it crystal clear that ALL adjustments are applied to the multiple,
    not to EBITDA or the final price.
    """

    @staticmethod
    def build_multiple_journey(
        response: ValuationResponseProtocol,
    ) -> list[dict[str, object]]:
        """
        Build multiple waterfall journey from step results.

        WHAT: Extracts multiple progression from Steps 2, 2.5, 4, 5, 6
        WHY: Shows transparency in how base multiple is adjusted (Multiple-First Methodology)
        HOW: Extracts multiple_after_mid and multiple_before_mid from each step result
        WHEN: Called during Info Tab HTML generation

        Academic Reference: Damodaran (2012) - Multiple adjustments isolate risk factors
        Business Rule: All adjustments applied to multiple, not EBITDA (Big 4 standard)
        """
        journey: list[dict[str, object]] = []
        step_results = get_multiple_journey_step_results(response=response, logger=logger)
        if step_results is None:
            return journey

        step_2_result = extract_step_result(step_results.get(2))
        base_multiple = append_base_multiple_step(
            journey=journey,
            step_result=step_2_result,
            response=response,
            logger=logger,
        )

        append_quality_calibration_step(
            journey=journey,
            step_result=extract_step_result(step_results.get(2.5)),
            response=response,
            logger=logger,
        )

        for spec in (
            OWNER_CONCENTRATION_STEP,
            SIZE_DISCOUNT_STEP,
            LIQUIDITY_DISCOUNT_STEP,
        ):
            append_discount_step(
                journey=journey,
                step_results=step_results,
                spec=spec,
                response=response,
                logger=logger,
            )

        if journey:
            log_successful_multiple_journey(
                response=response,
                journey=journey,
                logger=logger,
            )
        else:
            journey = build_fallback_multiple_journey(
                response=response,
                step_results=step_results,
                base_multiple=base_multiple,
                logger=logger,
            )

        log_final_journey_summary(
            response=response,
            step_results=step_results,
            journey=journey,
            logger=logger,
        )

        return journey
