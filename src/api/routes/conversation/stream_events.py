"""
Stream Events Module - SSE Event Generation

RESPONSIBILITIES:
- Generate all SSE event types with consistent format
- Handle event data serialization
- Provide type-safe event creation
- Ensure proper SSE formatting

CRITICAL BUG FIXES:
- ✅ Consistent SSE format across all event types
- ✅ Proper JSON serialization for complex objects
- ✅ Proper newline handling (double newline terminator)
- ✅ Type validation for event data

REFACTORING NOTE:
Extracted from intelligent_conversation_stream.py to centralize
event generation and ensure consistency.
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from src.utils.logging import get_logger
from src.api.streaming.sse import format_sse_event, sanitize_for_sse
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class StreamEventType(Enum):
    """Enumeration of all SSE event types"""

    TYPING = "typing"
    MESSAGE_START = "message_start"
    MESSAGE_CHUNK = "message_chunk"
    MESSAGE_COMPLETE = "message_complete"
    DATA_COLLECTED = "data_collected"
    PROGRESS_UPDATE = "progress_update"
    HTML_PREVIEW = "html_preview"
    ERROR = "error"
    SUGGESTION_OFFERED = "suggestion_offered"
    CLARIFICATION_NEEDED = "clarification_needed"
    REGISTRY_DATA = "registry_data"
    COMPLETE = "complete"


class StreamEventGenerator:
    """
    Generates standardized SSE events for all conversation interactions

    All events follow consistent format:
    ```
    data: {"type": "event_type", "content": "...", "session_id": "...", ...}

    ```
    """

    @staticmethod
    def typing_event(session_id: str, duration: Decimal = Decimal("1.0")) -> str:
        """
        Generate typing indicator event

        Args:
            session_id: Session identifier
            duration: Expected duration of typing in seconds

        Returns:
            Formatted SSE event
        """
        logger.debug(
            "⌨️ Generating typing event", extra={"session_id": session_id, "duration": duration}
        )
        data = {
            "type": StreamEventType.TYPING.value,
            "session_id": session_id,
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return format_sse_event(StreamEventType.TYPING.value, data)

    @staticmethod
    def message_start_event(session_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate message start event

        Args:
            session_id: Session identifier
            metadata: Optional metadata about the message

        Returns:
            Formatted SSE event
        """
        data = {
            "type": StreamEventType.MESSAGE_START.value,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            **(metadata or {}),
        }
        return format_sse_event(StreamEventType.MESSAGE_START.value, data)

    @staticmethod
    def message_chunk_event(
        content: str, session_id: str, chunk_index: Optional[int] = None
    ) -> str:
        """
        Generate message chunk event for streaming text

        Args:
            content: Text content chunk
            session_id: Session identifier
            chunk_index: Optional index of this chunk

        Returns:
            Formatted SSE event
        """
        # Sanitize content for safe SSE transmission
        safe_content = sanitize_for_sse(content)

        data: Dict[str, Any] = {
            "type": StreamEventType.MESSAGE_CHUNK.value,
            "content": safe_content,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if chunk_index is not None:
            data["chunk_index"] = chunk_index

        return format_sse_event(StreamEventType.MESSAGE_CHUNK.value, data)

    @staticmethod
    def message_complete_event(
        session_id: str, full_message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate message complete event

        Args:
            session_id: Session identifier
            full_message: Complete message text
            metadata: Optional metadata (field collected, etc.)

        Returns:
            Formatted SSE event
        """
        data = {
            "type": StreamEventType.MESSAGE_COMPLETE.value,
            "content": sanitize_for_sse(full_message),
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            **(metadata or {}),
        }
        return format_sse_event(StreamEventType.MESSAGE_COMPLETE.value, data)

    @staticmethod
    def data_collected_event(
        field: str, value: Any, session_id: str, confidence: Optional[Decimal] = None
    ) -> str:
        """
        Generate data collected event when field is successfully extracted

        Args:
            field: Field name that was collected
            value: Value that was collected
            session_id: Session identifier
            confidence: Optional confidence score (0-1)

        Returns:
            Formatted SSE event
        """
        logger.info(
            "📦 Generating data_collected event", extra={"session_id": session_id, "field": field}
        )

        # Convert value to serializable format
        if hasattr(value, "__dict__"):
            serialized_value = value.__dict__
        elif isinstance(value, (list, tuple, set)):
            serialized_value = list(value)
        else:
            serialized_value = value

        data = {
            "type": StreamEventType.DATA_COLLECTED.value,
            "field": field,
            "value": serialized_value,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if confidence is not None:
            data["confidence"] = confidence

        return format_sse_event(StreamEventType.DATA_COLLECTED.value, data)

    @staticmethod
    def progress_update_event(
        progress: Decimal,
        session_id: str,
        phase: Optional[str] = None,
        message: Optional[str] = None,
    ) -> str:
        """
        Generate progress update event

        Args:
            progress: Progress percentage (0-100)
            session_id: Session identifier
            phase: Optional phase description
            message: Optional progress message

        Returns:
            Formatted SSE event
        """
        data = {
            "type": StreamEventType.PROGRESS_UPDATE.value,
            "progress": min(Decimal("100.0"), max(Decimal("0.0"), progress)),
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if phase:
            data["phase"] = phase
        if message:
            data["message"] = message

        return format_sse_event(StreamEventType.PROGRESS_UPDATE.value, data)

    @staticmethod
    def html_preview_event(
        html_content: str, session_id: str, preview_type: str = "progressive"
    ) -> str:
        """
        Generate HTML preview event for progressive reports

        Args:
            html_content: HTML content to preview
            session_id: Session identifier
            preview_type: Type of preview (progressive, final, etc.)

        Returns:
            Formatted SSE event
        """
        data = {
            "type": StreamEventType.HTML_PREVIEW.value,
            "html": html_content,
            "preview_type": preview_type,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return format_sse_event(StreamEventType.HTML_PREVIEW.value, data)

    @staticmethod
    def section_loading_event(
        section_id: str, section_name: str, html: str, session_id: str
    ) -> str:
        """
        Generate section loading event for progressive reports

        Args:
            section_id: Unique section identifier
            section_name: Human-readable section name
            html: Loading placeholder HTML
            session_id: Session identifier

        Returns:
            Formatted SSE event
        """
        data = {
            "type": "section_loading",
            "section_id": section_id,
            "section_name": section_name,
            "html": html,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return format_sse_event("section_loading", data)

    @staticmethod
    def section_complete_event(
        section_id: str, section_name: str, html: str, progress: int, session_id: str
    ) -> str:
        """
        Generate section complete event for progressive reports

        Args:
            section_id: Unique section identifier
            section_name: Human-readable section name
            html: Completed section HTML
            progress: Overall progress percentage (0-100)
            session_id: Session identifier

        Returns:
            Formatted SSE event
        """
        data = {
            "type": "section_complete",
            "section_id": section_id,
            "section_name": section_name,
            "html": html,
            "progress": progress,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return format_sse_event("section_complete", data)

    @staticmethod
    def error_event(
        error_message: str,
        session_id: str,
        error_type: Optional[str] = None,
        recoverable: bool = True,
    ) -> str:
        """
        Generate error event

        Args:
            error_message: Error message to display
            session_id: Session identifier
            error_type: Optional error type/category
            recoverable: Whether the error is recoverable

        Returns:
            Formatted SSE event
        """
        data = {
            "type": StreamEventType.ERROR.value,
            "message": error_message,
            "session_id": session_id,
            "recoverable": recoverable,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if error_type:
            data["error_type"] = error_type

        logger.error(
            "Error event generated",
            extra={
                "session_id": session_id,
                "error_type": error_type,
                "error_message": error_message,
            },
        )

        return format_sse_event(StreamEventType.ERROR.value, data)

    @staticmethod
    def suggestion_offered_event(
        field: str, original_value: Any, suggestions: List[Dict[str, Any]], session_id: str
    ) -> str:
        """
        Generate suggestion offered event

        Args:
            field: Field name for suggestions
            original_value: User's original input
            suggestions: List of suggestion dicts with text, confidence, reason
            session_id: Session identifier

        Returns:
            Formatted SSE event
        """
        data = {
            "type": StreamEventType.SUGGESTION_OFFERED.value,
            "field": field,
            "original_value": original_value,
            "suggestions": suggestions,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return format_sse_event(StreamEventType.SUGGESTION_OFFERED.value, data)

    @staticmethod
    def clarification_needed_event(
        field: str,
        value: Any,
        concern: str,
        question: str,
        session_id: str,
        suggested_range: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate clarification needed event

        Args:
            field: Field requiring clarification
            value: Extracted value that needs confirmation
            concern: Why clarification is needed
            question: Clarification question to ask
            session_id: Session identifier
            suggested_range: Optional suggested value range

        Returns:
            Formatted SSE event
        """
        data = {
            "type": StreamEventType.CLARIFICATION_NEEDED.value,
            "field": field,
            "value": value,
            "concern": concern,
            "question": question,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if suggested_range:
            data["suggested_range"] = suggested_range

        return format_sse_event(StreamEventType.CLARIFICATION_NEEDED.value, data)

    @staticmethod
    def registry_data_event(
        company_name: str, registry_data: Dict[str, Any], session_id: str
    ) -> str:
        """
        Generate registry data event (KBO lookup results)

        Args:
            company_name: Company name that was looked up
            registry_data: Registry data found
            session_id: Session identifier

        Returns:
            Formatted SSE event
        """
        data = {
            "type": StreamEventType.REGISTRY_DATA.value,
            "company_name": company_name,
            "registry_data": registry_data,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return format_sse_event(StreamEventType.REGISTRY_DATA.value, data)

    @staticmethod
    def complete_event(session_id: str, summary: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate conversation complete event

        Args:
            session_id: Session identifier
            summary: Optional summary of conversation

        Returns:
            Formatted SSE event
        """
        data = {
            "type": StreamEventType.COMPLETE.value,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            **(summary or {}),
        }
        return format_sse_event(StreamEventType.COMPLETE.value, data)

    @classmethod
    def batch_events(cls, events: List[str]) -> str:
        """
        Batch multiple events into a single SSE message

        Args:
            events: List of formatted SSE events

        Returns:
            Combined SSE events
        """
        return "".join(events)

    @classmethod
    def validate_event_data(cls, event_type: StreamEventType, data: Dict[str, Any]) -> bool:
        """
        Validate event data has required fields

        Args:
            event_type: Type of event
            data: Event data to validate

        Returns:
            True if valid, False otherwise
        """
        # All events must have session_id
        if "session_id" not in data:
            logger.warning("Event missing session_id", extra={"event_type": event_type.value})
            return False

        # Type-specific validation
        if event_type == StreamEventType.DATA_COLLECTED:
            if "field" not in data or "value" not in data:
                logger.warning(
                    "data_collected event missing required fields",
                    extra={"event_type": event_type.value},
                )
                return False

        elif event_type == StreamEventType.MESSAGE_CHUNK:
            if "content" not in data:
                logger.warning(
                    "message_chunk event missing content", extra={"event_type": event_type.value}
                )
                return False

        return True


# Convenience functions for common event patterns
def send_typing_then_message(
    message: str, session_id: str, typing_duration: Decimal = Decimal("0.5")
) -> List[str]:
    """
    Generate typing indicator followed by message

    Args:
        message: Message to send
        session_id: Session identifier
        typing_duration: Duration of typing indicator

    Returns:
        List of SSE events [typing, message_start, message_chunk, message_complete]
    """
    gen = StreamEventGenerator()

    return [
        gen.typing_event(session_id, typing_duration),
        gen.message_start_event(session_id),
        gen.message_chunk_event(message, session_id),
        gen.message_complete_event(session_id, message),
    ]


def send_error_with_recovery(
    error_message: str, session_id: str, recovery_message: Optional[str] = None
) -> List[str]:
    """
    Generate error event with optional recovery message

    Args:
        error_message: Error to report
        session_id: Session identifier
        recovery_message: Optional message explaining recovery

    Returns:
        List of SSE events
    """
    gen = StreamEventGenerator()

    events = [gen.error_event(error_message, session_id, recoverable=True)]

    if recovery_message:
        events.extend(send_typing_then_message(recovery_message, session_id, Decimal("0.3")))

    return events
