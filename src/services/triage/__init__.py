"""
Triage Services - Brain & Muscle Architecture

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) provides validation logic only.
Titan (The Brain) handles orchestration and user interaction.

KEPT (Validation logic for stateless API):
- GapAnalysisService: Analyzes data completeness, returns validation flags

DELETED (Moved to Titan):
- IntelligentTriageEngine: Conversation orchestration
- ConversationContextManager: Session state management
- UpswitchDataCollector: Data collection from Supabase
- QuestionStrategyEngine: Question generation logic
"""

# Gap Analysis Service (Validation logic for stateless API)
from .gap_analysis_service import GapAnalysisService

__all__ = [
    # Gap analysis (validation for stateless API)
    "GapAnalysisService",
]
