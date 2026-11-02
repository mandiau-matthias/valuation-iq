"""
Transparency Builder Coordinators

Specialized coordinators that orchestrate complex operations within the transparency builder.
These coordinators reuse existing services and utilities to avoid code duplication.

Architecture:
- StepDescriptionFormattingCoordinator: Orchestrates step description formatting
- KeyOutputExtractionCoordinator: Orchestrates key output extraction from step results
- AdjustmentExtractionCoordinator: Orchestrates adjustment extraction from steps
- MultiplePipelineBuilderCoordinator: Orchestrates multiple pipeline building
"""

from .step_description_formatting_coordinator import StepDescriptionFormattingCoordinator
from .key_output_extraction_coordinator import KeyOutputExtractionCoordinator
from .adjustment_extraction_coordinator import AdjustmentExtractionCoordinator
from .multiple_pipeline_builder_coordinator import MultiplePipelineBuilderCoordinator

# Export types for use in other modules
from .types import (
    PreviousResults,
    StepOutput,
    KeyOutputsUnion,
    Adjustment,
    DataSource,
    MultiplePipeline,
    TransparencyReport,
    Methodologies,
    AcademicSource,
    ProfessionalReviewReady,
    GetPreviousStepResultFunc,
)

# Export validation utilities
from .validation import BankGradeValidator

__all__ = [
    'StepDescriptionFormattingCoordinator',
    'KeyOutputExtractionCoordinator',
    'AdjustmentExtractionCoordinator',
    'MultiplePipelineBuilderCoordinator',
    # Types
    'PreviousResults',
    'StepOutput',
    'KeyOutputsUnion',
    'Adjustment',
    'DataSource',
    'MultiplePipeline',
    'TransparencyReport',
    'Methodologies',
    'AcademicSource',
    'ProfessionalReviewReady',
    'GetPreviousStepResultFunc',
    # Validation
    'BankGradeValidator',
]

