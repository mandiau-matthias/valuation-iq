"""
Step 11: Final Valuation Synthesis

Assembles final valuation with rounding, asking price, and transparency report.

REFACTORED: Extracted calculators, validators, and builders into modular structure.
"""

from datetime import datetime
from decimal import Decimal
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from src.api.routes.valuation.triage.step_registry import register_step
from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_11_final_synthesis.builders import (
    Step11MetadataBuilder,
    Step11ResultBuilder,
)
from src.api.routes.valuation.steps.step_11_final_synthesis.handlers import (
    Step11ErrorHandler,
)
from src.api.routes.valuation.steps.step_11_final_synthesis.orchestrators import (
    Step11Orchestrator,
)
from src.api.routes.valuation.steps.step_11_synthesis.builders import (
    MethodologyBuilder,
    TransparencyBuilder,
)
from src.api.routes.valuation.steps.step_11_synthesis.calculators import (
    AdjustmentCalculator,
    ConfidenceCalculator,
    RangeCalculator,
)
from src.api.routes.valuation.steps.step_11_synthesis.orchestrator import (
    SynthesisOrchestrator,
)
from src.api.routes.valuation.steps.step_11_synthesis.validators import (
    SynthesisValidator,
)
from src.domain.data_quality_assessor import DataQualityAssessor
from src.domain.methodology_source_registry import get_methodology_source_registry
from src.utils.logging import get_logger
from src.utils.sole_trader_detector import SoleTraderDetector

try:
    from prometheus_client import REGISTRY, Counter, Histogram

    _prometheus_available = True
except ImportError:
    Counter = None
    Histogram = None
    _prometheus_available = False
from src.config import get_settings

logger = get_logger(__name__)

# Prometheus metrics for value chain monitoring (lazy initialization to avoid duplicate registration)
_value_chain_breaks = None
_value_chain_difference = None
_value_chain_metrics_lock = Lock()


def _get_existing_prometheus_collector(*names: str):
    names_to_collectors = (
        getattr(REGISTRY, "_names_to_collectors", {}) if _prometheus_available else {}
    )
    for name in names:
        collector = names_to_collectors.get(name)
        if collector is not None:
            return collector
    return None


def _get_value_chain_breaks():
    global _value_chain_breaks
    if _value_chain_breaks is None and _prometheus_available:
        with _value_chain_metrics_lock:
            if _value_chain_breaks is None:
                try:
                    _value_chain_breaks = Counter(
                        "valuation_value_chain_breaks_total",
                        "Number of value chain breaks detected and auto-corrected",
                        ["correction_type"],
                    )
                except ValueError:
                    _value_chain_breaks = _get_existing_prometheus_collector(
                        "valuation_value_chain_breaks",
                        "valuation_value_chain_breaks_total",
                    )
    return _value_chain_breaks


def _get_value_chain_difference():
    global _value_chain_difference
    if _value_chain_difference is None and _prometheus_available:
        with _value_chain_metrics_lock:
            if _value_chain_difference is None:
                try:
                    _value_chain_difference = Histogram(
                        "valuation_value_chain_difference_percent",
                        "Percentage difference in value chain validation",
                        buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
                    )
                except ValueError:
                    _value_chain_difference = _get_existing_prometheus_collector(
                        "valuation_value_chain_difference_percent",
                    )
    return _value_chain_difference


@register_step
class Step11FinalSynthesis(CalculationStep):
    """
    Final Valuation Synthesis Step.

    Responsibilities:
    - Round values to meaningful precision
    - Apply asking price markup if requested
    - Generate comprehensive transparency report
    - Format final output for API response
    """

    @property
    def step_number(self) -> int:
        return 11

    @property
    def step_name(self) -> str:
        return "Final Valuation Range"

    @property
    def dependencies(self) -> List[int]:
        # Step 10 is preferred but not required - can fallback to Step 7/6 equity values
        return []

    @property
    def optional_dependencies(self) -> List[int]:
        """
        Optional dependencies that enhance the final synthesis if available.

        Priority order for equity/valuation values:
        - Step 10 (preferred) - provides valuation range
        - Step 7 (equity) - provides equity values
        - Step 6 (EV fallback) - provides EV values as equity approximation
        - Step 8 (ownership-adjusted) - provides ownership-adjusted equity

        Additional optional dependencies that enhance transparency:
        - Step 0: Data Quality Assessment (enhances transparency report)
        - Steps 4-5: Discount steps (enhance adjustment breakdown)
        - Step 9: Confidence Score (enhances confidence breakdown, but Step 10 is fallback)
        """
        return [
            10,
            7,
            6,
            8,
            0,
            4,
            5,
            9,
        ]  # Priority order: 10 > 7 > 6 > 8, then 0, 4, 5, 9 for transparency

    def should_execute(self, input_data: StepInput) -> bool:
        return True  # Always synthesize final result

    def __init__(self):
        """Initialize Step 11 with refactored modules."""
        super().__init__()
        # Initialize calculators
        self.range_calculator = RangeCalculator()
        self.confidence_calculator = ConfidenceCalculator()
        self.adjustment_calculator = AdjustmentCalculator(self.range_calculator)

        # Initialize validators
        self.validator = SynthesisValidator()

        # Initialize builders
        self.methodology_builder = MethodologyBuilder()
        self.transparency_builder = TransparencyBuilder(self.confidence_calculator)

        # Initialize synthesis orchestrator (from step_11_synthesis)
        self.synthesis_orchestrator = SynthesisOrchestrator(
            self.range_calculator, self.validator, self.get_previous_step_result
        )

        # Initialize new Step 11 modules
        self.error_handler = Step11ErrorHandler(self.step_name)
        self.result_builder = Step11ResultBuilder()
        self.metadata_builder = Step11MetadataBuilder()

        # Initialize Step 11 orchestrator
        self.orchestrator = Step11Orchestrator(
            self.step_name,
            self.range_calculator,
            self.confidence_calculator,
            self.adjustment_calculator,
            self.validator,
            self.methodology_builder,
            self.transparency_builder,
            self.synthesis_orchestrator,
            self.get_previous_step_result,
            self.error_handler,
            self.result_builder,
            self.metadata_builder,
        )

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Synthesize final valuation with rounding, asking price, and transparency report.

        This is the final step that:
        1. Validates value chain consistency (Step 10 mid = Step 8/7 equity)
        2. Rounds values to meaningful precision
        3. Applies asking price markup if requested
        4. Generates comprehensive transparency report
        5. Formats final output for API response
        """
        request = input_data.request
        context = input_data.context or {}
        correlation_id = context.get("correlation_id")

        # Delegate to orchestrator
        return await self.orchestrator.orchestrate_execution(input_data, request, correlation_id)
