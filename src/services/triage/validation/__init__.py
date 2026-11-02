"""
Q&A Validation Framework

Bank-grade validation system for conversational Q&A responses.
Implements 5-gate validation pipeline with expert review workflow.

Components:
- TruthDatabase: Canonical knowledge base for fact-checking
- ValidationPipeline: 5-gate validation system
- ReviewQueueManager: Expert review workflow
"""

from .review_queue_manager import ReviewPriority, ReviewQueueItem, ReviewQueueManager, ReviewStatus
from .truth_database import TruthDatabase, TruthEntry
from .validation_pipeline import (
    GateResult,
    ValidationGate,
    ValidationPipeline,
    ValidationReport,
    ValidationResult,
)

__all__ = [
    "TruthDatabase",
    "TruthEntry",
    "ValidationPipeline",
    "ValidationReport",
    "ValidationResult",
    "ValidationGate",
    "GateResult",
    "ReviewQueueManager",
    "ReviewQueueItem",
    "ReviewPriority",
    "ReviewStatus",
]
