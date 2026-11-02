"""
Academic Services Module

Provides comprehensive academic methodology validation, provenance tracking,
and citation generation for world-class valuation reports.

Components:
- Academic Metadata Service: Central registry linking calculations to academic sources
- Calculation Provenance Tracker: Runtime tracking of methodologies used
- Academic Validation Engine: Post-calculation validation against standards
- Dynamic Reference Generator: Citation generation based on actual usage
- Citation Formatter: Academic citation formatting (APA, Chicago, Harvard)

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from src.services.academic.academic_metadata_service import AcademicMetadataService
from src.services.academic.models import (
    AcademicSource,
    CalculationMetadata,
    ValidationRule,
    ProvenanceRecord,
    Citation
)

__all__ = [
    'AcademicMetadataService',
    'AcademicSource',
    'CalculationMetadata',
    'ValidationRule',
    'ProvenanceRecord',
    'Citation'
]

