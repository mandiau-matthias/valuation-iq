"""
Transparency Builder for Step 11 Synthesis - Refactored (Coordinator Pattern)

Handles transparency report generation, key output extraction, and step formatting.

Architecture (Coordinator Pattern):
- StepDescriptionFormattingCoordinator: Formats step descriptions with actual values
- KeyOutputExtractionCoordinator: Extracts key outputs from step results
- AdjustmentExtractionCoordinator: Extracts adjustments from steps
- MultiplePipelineBuilderCoordinator: Builds multiple discount pipeline

REFACTORING (January 2025):
- File size reduced from 992 → 268 lines (73.0% reduction)
- Extracted 4 coordinator classes following Coordinator Pattern
- Improved maintainability, testability, and separation of concerns
"""

from typing import List, Optional

from src.errors import ValidationError
from src.utils.logging import get_logger

from ...base_step import StepStatus
from .coordinators import (
    AdjustmentExtractionCoordinator,
    KeyOutputExtractionCoordinator,
    MultiplePipelineBuilderCoordinator,
    StepDescriptionFormattingCoordinator,
)
from .coordinators.types import (
    AcademicSource,
    DataSource,
    Methodologies,
    PreviousResults,
    ProfessionalReviewReady,
    TransparencyReport,
)
from .coordinators.validation import BankGradeValidator
from .transparency_report_assembly import (
    add_optional_methodology_sections,
    build_transparency_payload,
    build_transparency_steps,
    log_final_transparency_assembly,
    log_transparency_generation_start,
)

logger = get_logger(__name__)


class TransparencyBuilder:
    """
    Builder for transparency report operations (Coordinator Pattern).

    Responsibilities:
    - Generate comprehensive transparency reports
    - Coordinate transparency report generation using specialized coordinators

    Architecture:
    - Delegates to coordinators for complex operations:
      - StepDescriptionFormattingCoordinator: Step description formatting
      - KeyOutputExtractionCoordinator: Key output extraction
      - AdjustmentExtractionCoordinator: Adjustment extraction
      - MultiplePipelineBuilderCoordinator: Multiple pipeline building
    """

    def __init__(self, confidence_calculator):
        """
        Initialize transparency builder.

        Args:
            confidence_calculator: ConfidenceCalculator instance
        """
        self.confidence_calculator = confidence_calculator

        # Initialize coordinators
        self.description_formatter = StepDescriptionFormattingCoordinator()
        self.output_extractor = KeyOutputExtractionCoordinator()
        self.adjustment_extractor = AdjustmentExtractionCoordinator()
        self.pipeline_builder = MultiplePipelineBuilderCoordinator()

    def build_multiple_pipeline(
        self,
        previous_results: PreviousResults,
        get_previous_step_result_func,
    ):
        """Delegate to the pipeline builder coordinator."""
        return self.pipeline_builder.build_multiple_pipeline(
            previous_results, get_previous_step_result_func
        )

    def generate_transparency_report(
        self,
        previous_results: PreviousResults,
        methodologies: Optional[Methodologies] = None,
        methodology_statement: Optional[str] = None,
        academic_sources: Optional[List[AcademicSource]] = None,
        professional_review_ready: Optional[ProfessionalReviewReady] = None,
    ) -> TransparencyReport:
        """
        Generate comprehensive transparency report.

        Phase Decimal('2.5'): Enhanced with step descriptions and methodology information.

        CRITICAL: Includes ALL steps (0-11), even if skipped, so frontend can
        display them with proper explanations.

        BANK-GRADE: Includes input validation, data integrity checks, and comprehensive audit trail.
        """
        # Bank-grade input validation
        try:
            BankGradeValidator.validate_previous_results(previous_results)
        except ValidationError as e:
            logger.error(
                f"❌ CRITICAL: Invalid previous_results structure in generate_transparency_report: {e}",
                extra={"step_number": 11},
            )
            raise

        log_transparency_generation_start(
            previous_results,
            methodologies=methodologies,
            methodology_statement=methodology_statement,
            academic_sources=academic_sources,
            professional_review_ready=professional_review_ready,
        )
        calculation_steps, sub_steps = build_transparency_steps(
            previous_results,
            description_formatter=self.description_formatter,
            output_extractor=self.output_extractor,
        )
        data_sources = self.extract_data_sources(previous_results)
        adjustments_applied = self.adjustment_extractor.extract_adjustments(previous_results)
        confidence_breakdown = self.confidence_calculator.extract_confidence(previous_results)

        transparency = build_transparency_payload(
            calculation_steps=calculation_steps,
            sub_steps=sub_steps,
            data_sources=data_sources,
            adjustments_applied=adjustments_applied,
            confidence_breakdown=confidence_breakdown,
        )
        log_final_transparency_assembly(
            transparency,
            data_sources=data_sources,
            adjustments_applied=adjustments_applied,
        )
        add_optional_methodology_sections(
            transparency,
            methodology_statement=methodology_statement,
            academic_sources=academic_sources,
            professional_review_ready=professional_review_ready,
        )

        return transparency

    def extract_data_sources(self, previous_results: PreviousResults) -> List[DataSource]:
        """Extract data sources used."""
        sources = []
        step2 = previous_results.get(2)
        if step2 and step2.status == StepStatus.COMPLETED:
            sources.append(
                {"type": "Multiples", "source": step2.result.get("data_source", "unknown")}
            )
        return sources
