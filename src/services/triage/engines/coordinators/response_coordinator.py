"""
Response Coordinator

Coordinates streaming response generation for triage decisions,
including KBO match messages and progress events.
"""

import logging
from typing import Any, AsyncIterator, Dict, Optional


class ResponseCoordinator:
    def __init__(
        self,
        stream_handler=None,
        html_preview_generator=None,
        valuation_preview=None,
        triage_context_manager=None,
    ):
        self.stream_handler = stream_handler
        self.html_preview_generator = html_preview_generator
        self.valuation_preview = valuation_preview
        self.triage_context_manager = triage_context_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def generate_streaming_response(
        self, decision: Any, context: Any
    ) -> AsyncIterator[Dict[str, Any]]:
        from src.services.triage.engines.types import TriageAction

        registry_data = getattr(context, "registry_data", None)
        if registry_data and registry_data.get("found") and not registry_data.get("processed"):
            kbo_message = self._generate_kbo_match_message(registry_data)
            if kbo_message:
                yield {"type": "kbo_match", "message": kbo_message}
            registry_data["processed"] = True

        if decision.action == TriageAction.ASK_QUESTION:
            async for event in self.stream_handler.stream_question(decision, context):
                yield event

        elif decision.action == TriageAction.COMPLETE:
            complete_event = self.stream_handler.create_complete_event(decision, context)
            yield complete_event

    def _generate_kbo_match_message(self, registry_data: Dict[str, Any]) -> str:
        company_name = registry_data.get("company_name", "your company")
        parts = [f"We found a match for {company_name} in the KBO registry."]

        vat = registry_data.get("vat_number")
        if vat:
            parts.append(f"VAT: {vat}")

        return " ".join(parts)
