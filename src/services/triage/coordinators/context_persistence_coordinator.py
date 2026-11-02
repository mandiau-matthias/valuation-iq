"""
Context Persistence Coordinator

Handles loading, saving, verifying, and merging context data
for triage conversations including KBO registry data.
"""

import logging
from typing import Any, Dict, Optional

from src.services.core.types.conversation_context import ConversationContext


logger = logging.getLogger(__name__)

COMPANY_LEGAL_FORMS = {
    'BV', 'NV', 'BVBA', 'CV', 'VOF', 'CommV',
    'BV (Besloten Vennootschap)', 'NV (Naamloze Vennootschap)',
}
SOLE_TRADER_LEGAL_FORMS = {'Eenmanszaak'}

FIELD_ALIASES = [
    ('country', 'country_code'),
    ('founded_year', 'founding_year'),
]


class ContextPersistenceCoordinator:
    def __init__(self, context_manager):
        self.context_manager = context_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def load_or_create_context(
        self, session_id: str, context: Optional[ConversationContext] = None
    ) -> ConversationContext:
        if context is not None:
            return context
        return await self.context_manager.get_or_create_triage_context(session_id)

    async def save_and_verify_context(
        self, context: ConversationContext, session_id: str
    ) -> ConversationContext:
        await self.context_manager.update_triage_context(context)

        verified = await self.context_manager.get_or_create_triage_context(session_id)

        original_fields = set(context.collected_data.keys())
        verified_fields = set(verified.collected_data.keys())
        missing = original_fields - verified_fields
        if missing:
            self.logger.error(
                "Persistence verification failed: fields %s not persisted",
                missing,
                extra={"session_id": session_id, "missing_fields": list(missing)},
            )

        return verified

    async def reload_context_for_decision(self, session_id: str) -> ConversationContext:
        return await self.context_manager.get_or_create_triage_context(session_id, None)

    def merge_kbo_data(
        self, collected_data: Dict[str, Any], context: ConversationContext
    ) -> Dict[str, Any]:
        registry_data = getattr(context, "registry_data", None)
        if not registry_data or not registry_data.get("found"):
            return collected_data

        result = dict(collected_data)

        legal_form = registry_data.get("legal_form", "")
        if legal_form and "business_structure" not in result:
            if legal_form in SOLE_TRADER_LEGAL_FORMS:
                result["business_structure"] = "sole-trader"
            elif legal_form in COMPANY_LEGAL_FORMS or legal_form not in SOLE_TRADER_LEGAL_FORMS:
                result["business_structure"] = "company"

        founding_year = registry_data.get("founding_year")
        if founding_year is not None:
            if "founding_year" not in result:
                result["founding_year"] = founding_year
            if "founded_year" not in result:
                result["founded_year"] = founding_year

        result["_kbo_data"] = {
            k: v for k, v in registry_data.items()
        }

        return result

    def normalize_field_aliases(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(data)
        for field_a, field_b in FIELD_ALIASES:
            if field_a in result and field_b not in result:
                result[field_b] = result[field_a]
            elif field_b in result and field_a not in result:
                result[field_a] = result[field_b]
        return result
