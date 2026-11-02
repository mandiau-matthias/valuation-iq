"""
Structured Question Coordinator

Orchestrates the structured question flow using FlowSection-based progression
with section transitions and completion handling.
"""

import logging
from typing import Any, Dict, Optional

from src.services.triage.modules.structured_flow_coordinator import FlowSection
from src.utils.exceptions import DataValidationError, DomainError, ValidationError


class StructuredQuestionCoordinator:
    def __init__(self, flow_coordinator=None, message_generation_coordinator=None):
        self.flow_coordinator = flow_coordinator
        self.message_generation_coordinator = message_generation_coordinator
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def get_next_structured_question(
        self,
        session_id: str,
        collected_data: Dict[str, Any],
        context: Any = None,
    ) -> Dict[str, Any]:
        try:
            current_section = self.flow_coordinator.get_current_section(collected_data)

            if current_section == FlowSection.COMPLETE:
                message = self.message_generation_coordinator.generate_completion_message(collected_data)
                return {
                    "complete": True,
                    "message": message,
                    "collected_data": collected_data,
                }

            question = self.flow_coordinator.get_next_question_for_section(
                section=current_section,
                collected_data=collected_data,
                context=context,
            )

            if question is not None:
                progress = self.flow_coordinator.get_section_progress(collected_data)
                question["progress"] = progress
                return question

            section_order = self.flow_coordinator.section_order
            current_idx = section_order.index(current_section)
            completed_name = self.flow_coordinator._get_section_display_name(current_section)

            for next_section in section_order[current_idx + 1:]:
                if next_section == FlowSection.COMPLETE:
                    message = self.message_generation_coordinator.generate_completion_message(collected_data)
                    return {
                        "complete": True,
                        "message": message,
                        "collected_data": collected_data,
                    }

                next_question = self.flow_coordinator.get_next_question_for_section(
                    section=next_section,
                    collected_data=collected_data,
                    context=context,
                )
                if next_question is not None:
                    progress = self.flow_coordinator.get_section_progress(collected_data)
                    next_question["progress"] = progress
                    next_question["section_transition"] = f"{completed_name} complete"
                    return next_question

            message = self.message_generation_coordinator.generate_completion_message(collected_data)
            return {
                "complete": True,
                "message": message,
                "collected_data": collected_data,
            }

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            raise ValidationError(
                f"Invalid input for question generation: {e}"
            ) from e
        except DataValidationError as e:
            raise DomainError(
                f"Failed to generate structured question: {e}"
            ) from e
