"""
Step 1: Input Validation & Normalization

This step validates and normalizes input data before valuation calculations begin.
"""

from typing import List

from src.api.routes.valuation.triage.step_registry import register_step
from src.utils.logging import get_logger

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_1_input_validation.builders import (
    Step1MetadataBuilder,
    Step1ResultBuilder,
)
from src.api.routes.valuation.steps.step_1_input_validation.calculators import (
    Step1MarginCalculator,
)
from src.api.routes.valuation.steps.step_1_input_validation.extractors import (
    Step1CompanyExtractor,
    Step1MetricsExtractor,
)

# Import new Step 1 modules
from src.api.routes.valuation.steps.step_1_input_validation.orchestrators import (
    Step1Orchestrator,
)
from src.api.routes.valuation.steps.step_1_input_validation.validators import (
    Step1Validator,
)

logger = get_logger(__name__)


@register_step
class Step1InputValidation(CalculationStep):
    """
    Input Validation and Normalization Step.

    Validates and normalizes:
    - Financial metrics (revenue, EBITDA, etc.)
    - Company information
    - Industry classification
    - EBITDA normalization if needed
    """

    @property
    def step_number(self) -> int:
        return 1

    @property
    def step_name(self) -> str:
        return "Input Data & Business Profile"

    @property
    def dependencies(self) -> List[int]:
        return [0]  # Depends on data quality assessment

    def should_execute(self, input_data: StepInput) -> bool:
        return True  # Always validate inputs

    def __init__(self):
        """Initialize Step 1 with refactored modules."""
        super().__init__()
        # Initialize extractors
        self.metrics_extractor = Step1MetricsExtractor()
        self.company_extractor = Step1CompanyExtractor()

        # Initialize calculators
        self.margin_calculator = Step1MarginCalculator()

        # Initialize validators
        self.validator = Step1Validator()

        # Initialize builders
        self.result_builder = Step1ResultBuilder()
        self.metadata_builder = Step1MetadataBuilder()

        # Initialize orchestrator
        self.orchestrator = Step1Orchestrator(
            self.step_name,
            self.metrics_extractor,
            self.company_extractor,
            self.margin_calculator,
            self.validator,
            self.result_builder,
            self.metadata_builder,
        )

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Validate and normalize input data.

        Per academic valuation standards (Koller, Goedhart & Wessels 2020), uses weighted metrics if available:
        - Weighted EBITDA: Year1×1/6 + Year2×2/6 + Year3×3/6
        - Weighted Revenue: Same weighting logic

        This captures recent trajectory and momentum.
        """
        request = input_data.request
        context = input_data.context or {}

        # Delegate to orchestrator
        return await self.orchestrator.orchestrate_execution(input_data, request, context)
