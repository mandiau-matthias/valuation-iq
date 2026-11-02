"""
Triage engine types: TriageDecision and TriageAction.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class TriageAction(str, Enum):
    ASK_QUESTION = "ask_question"
    COMPLETE = "complete"


@dataclass
class TriageDecision:
    action: TriageAction
    field_name: Optional[str] = None
    next_question: Optional[str] = None
    confidence: float = 0.0
    reasoning: Optional[str] = None
    input_type: Optional[str] = None
    help_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
