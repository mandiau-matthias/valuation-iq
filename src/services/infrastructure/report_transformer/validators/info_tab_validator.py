"""
InfoTabValidator

Validates Info Tab data structures including multiple pipeline stages
and valuation waterfall steps.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class InfoTabValidator:
    def validate_multiple_pipeline_stages(self, info_tab_data: Dict[str, Any]) -> None:
        pipeline = info_tab_data.get("multiple_pipeline")
        if pipeline is None:
            return

        stages = pipeline.get("stages")
        if not stages:
            return

        for i, stage in enumerate(stages):
            if "stage_name" not in stage:
                logger.warning("Pipeline stage %d missing stage_name", i)
            if "multiple" not in stage:
                logger.warning("Pipeline stage %d missing multiple", i)

    def validate_valuation_waterfall_steps(self, info_tab_data: Dict[str, Any]) -> None:
        waterfall = info_tab_data.get("valuation_waterfall")
        if waterfall is None:
            return

        steps = waterfall.get("steps")
        if not steps:
            return

        for i, step in enumerate(steps):
            if "step_name" not in step:
                logger.warning("Waterfall step %d missing step_name", i)
            if "after_value" not in step:
                logger.warning("Waterfall step %d missing after_value", i)
