"""
Decision Coordinator

Coordinates the decision-making process for triage conversations,
determining whether to ask the next question or complete the flow.
"""

import logging
from typing import Any

from src.services.triage.engines.types import TriageAction, TriageDecision


class DecisionCoordinator:
    def __init__(self, decision_algorithms=None, context_analyzer=None, triage_context_manager=None):
        self.decision_algorithms = decision_algorithms
        self.context_analyzer = context_analyzer
        self.triage_context_manager = triage_context_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def determine_next_action(self, context: Any) -> TriageDecision:
        missing_fields = self.triage_context_manager.get_missing_fields(context)

        if not missing_fields:
            return TriageDecision(
                action=TriageAction.COMPLETE,
                confidence=1.0,
                reasoning="All required fields collected",
            )

        decision = await self.decision_algorithms.determine_next_question(
            context=context,
            missing_fields=missing_fields,
        )
        return decision
