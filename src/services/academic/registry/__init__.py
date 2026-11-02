"""
Academic Registry Modules

Registry classes for managing academic sources and calculation metadata.

Author: Upswitch CTO Team
Date: December 2025
"""

from src.services.academic.registry.academic_source_registry import AcademicSourceRegistry
from src.services.academic.registry.calculation_metadata_registry import CalculationMetadataRegistry

__all__ = [
    'AcademicSourceRegistry',
    'CalculationMetadataRegistry'
]
