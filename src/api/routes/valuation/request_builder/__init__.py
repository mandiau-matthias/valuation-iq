"""
Request Builder Module

This module provides centralized data packaging and transformation logic
for creating ValuationRequest objects from various data sources.

Architecture:
    - ValuationRequestBuilder: Main builder class with validation
    - AI-Guided Adapter: Converts AI-guided conversation data → ValuationRequest
    - Manual Form Adapter: Converts form data → ValuationRequest
    - Database Adapter: Converts user business profile → ValuationRequest

Benefits:
    - Single Responsibility: Data transformation logic centralized
    - DRY: No duplicate ValuationRequest creation code
    - Testability: Isolated unit tests for data transformation
    - Maintainability: Single point of change for request structure
    - Validation: Centralized data quality checks before calculation
"""

from .ai_guided_adapter import AIGuidedAdapter
from .database_adapter import DatabaseAdapter
from .manual_form_adapter import ManualFormAdapter
from .valuation_request_builder import ValuationRequestBuilder

__all__ = [
    "ValuationRequestBuilder",
    "AIGuidedAdapter",
    "ManualFormAdapter",
    "DatabaseAdapter",
]
