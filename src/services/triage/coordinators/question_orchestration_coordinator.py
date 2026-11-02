"""
Question Orchestration Coordinator

Orchestrates KBO data merging, pre-filled data, field alias normalization,
structured question retrieval with fallback, and fail-safe checks.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from src.services.triage.engines.types import TriageAction, TriageDecision


COMPANY_LEGAL_FORMS = {
    'BV', 'NV', 'BVBA', 'CV', 'VOF', 'CommV',
    'BV (Besloten Vennootschap)', 'NV (Naamloze Vennootschap)',
}
SOLE_TRADER_LEGAL_FORMS = {'Eenmanszaak'}

FIELD_ALIASES = [
    ('country', 'country_code'),
    ('founded_year', 'founding_year'),
]

FALLBACK_QUESTIONS: Dict[str, str] = {
    'company_name': "What is your company name?",
    'revenue': "What is your annual revenue?",
    'industry': "What industry does your company operate in?",
    'employees': "How many employees does your company have?",
    'ebitda': "What is your company's EBITDA?",
}


class QuestionOrchestrationCoordinator:
    def __init__(self, flow_coordinator=None, decision_coordinator=None, triage_context_manager=None):
        self.flow_coordinator = flow_coordinator
        self.decision_coordinator = decision_coordinator
        self.triage_context_manager = triage_context_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def merge_kbo_data(
        self,
        collected_data: Dict[str, Any],
        registry_data: Optional[Dict[str, Any]],
        session_id: str,
    ) -> Dict[str, Any]:
        if not registry_data or not registry_data.get("found"):
            return collected_data

        result = dict(collected_data)

        legal_form = registry_data.get("legal_form", "")
        if legal_form and "business_structure" not in result:
            if legal_form in SOLE_TRADER_LEGAL_FORMS:
                result["business_structure"] = "sole-trader"
            else:
                result["business_structure"] = "company"

        founding_year = registry_data.get("founding_year")
        if founding_year is not None:
            if "founding_year" not in result:
                result["founding_year"] = founding_year
            if "founded_year" not in result:
                result["founded_year"] = founding_year

        industry_desc = registry_data.get("industry_description")
        if industry_desc and "industry" not in result:
            result["industry"] = industry_desc

        result["_kbo_data"] = dict(registry_data)
        return result

    def merge_pre_filled_data(
        self,
        collected_data: Dict[str, Any],
        pre_filled_data: Optional[Dict[str, Any]],
        session_id: str,
    ) -> Dict[str, Any]:
        if not pre_filled_data:
            return collected_data

        result = dict(collected_data)
        for key, value in pre_filled_data.items():
            if value is None:
                continue
            if key not in result:
                result[key] = value
        return result

    def normalize_field_aliases(self, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(collected_data)
        for field_a, field_b in FIELD_ALIASES:
            if field_a in result and field_b not in result:
                result[field_b] = result[field_a]
            elif field_b in result and field_a not in result:
                result[field_a] = result[field_b]
        return result

    async def get_next_question_with_fallback(
        self,
        session_id: str,
        collected_data: Dict[str, Any],
        flow_context: Dict[str, Any],
        context: Any,
        get_next_structured_question_method: Callable,
    ) -> TriageDecision:
        try:
            structured = await get_next_structured_question_method(
                session_id=session_id,
                collected_data=collected_data,
                context=context,
            )

            if structured.get("complete"):
                return TriageDecision(
                    action=TriageAction.COMPLETE,
                    next_question=structured.get("message", "All done!"),
                    confidence=1.0,
                )

            return self._convert_structured_to_decision(structured, session_id)

        except Exception as e:
            self.logger.warning("Structured question failed, falling back: %s", e)
            return await self.decision_coordinator.determine_next_action(context)

    async def apply_fail_safe_checks(
        self,
        decision: TriageDecision,
        context: Any,
        session_id: str,
    ) -> Optional[TriageDecision]:
        collected = getattr(context, "collected_data", {})
        field_name = decision.field_name

        is_already_collected = field_name in collected and collected[field_name] is not None

        if not is_already_collected:
            return None

        missing_fields = await self.triage_context_manager.get_missing_fields(context)
        if not missing_fields:
            return None

        next_field = missing_fields[0]
        question_text = FALLBACK_QUESTIONS.get(
            next_field, f"Could you provide your {next_field.replace('_', ' ')}?"
        )

        return TriageDecision(
            action=TriageAction.ASK_QUESTION,
            field_name=next_field,
            next_question=question_text,
            confidence=0.7,
            reasoning=f"Fail-safe: skipped already-collected {field_name}, moved to {next_field}",
        )

    def _convert_structured_to_decision(
        self, structured_question: Dict[str, Any], session_id: str
    ) -> TriageDecision:
        metadata = {}
        for key in ('button_text', 'button_action', 'section', 'required'):
            if key in structured_question:
                metadata[key] = structured_question[key]

        return TriageDecision(
            action=TriageAction.ASK_QUESTION,
            field_name=structured_question["field"],
            next_question=structured_question["question"],
            confidence=0.9,
            input_type=structured_question.get("input_type", "text"),
            help_text=structured_question.get("help_text"),
            metadata=metadata,
        )
