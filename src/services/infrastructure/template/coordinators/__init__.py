"""
Template Coordinators Package

This package contains coordinator classes that handle template rendering logic,
following the Single Responsibility Principle.

Coordinators:
- ReportRenderingCoordinator: Handles HTML report rendering
- PDFGenerationCoordinator: Handles PDF generation
- TemplateInitializationCoordinator: Handles template setup and initialization
- DataValidationCoordinator: Handles data validation before rendering
"""

from .report_rendering_coordinator import ReportRenderingCoordinator
from .pdf_generation_coordinator import PDFGenerationCoordinator
from .template_initialization_coordinator import TemplateInitializationCoordinator
from .data_validation_coordinator import DataValidationCoordinator

__all__ = [
    "ReportRenderingCoordinator",
    "PDFGenerationCoordinator",
    "TemplateInitializationCoordinator",
    "DataValidationCoordinator",
]

