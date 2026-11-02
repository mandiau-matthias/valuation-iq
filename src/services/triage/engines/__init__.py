"""
Triage Engines - DEPRECATED

BRAIN & MUSCLE ARCHITECTURE:
All orchestration and engine logic has moved to Titan (The Brain).
ValuationIQ (The Muscle) only provides stateless validation via GapAnalysisService.

For triage functionality, use:
- Titan's TriageService for routing decisions
- Titan's ClaudeService for question generation
- ValuationIQ's GapAnalysisService for data validation
"""

__all__: list[str] = []
