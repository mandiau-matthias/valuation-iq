"""
Standardized Event Schema for Conversational Flow

WHAT: Type-safe event definitions for all SSE events
WHY: Eliminate duplicate messages, ensure consistent event handling across backend/frontend
HOW: Dataclasses with unique event IDs, clear event types, no overlap in responsibilities

DESIGN PRINCIPLES:
1. Each event has exactly one responsibility
2. Events carry unique IDs for deduplication
3. Data collection events do NOT include confirmation messages
4. Confirmation messages are separate events
5. All events include timestamp for ordering

REFACTORING (December 2025):
- Created from scratch to fix Bug #1 (Duplicate Messages)
- Replaces inconsistent dict-based events
- Enables frontend deduplication by event_id
"""

import time
import uuid
from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(str, Enum):
    """
    All event types in the conversational flow.

    MESSAGE EVENTS: For AI message streaming
    - typing: AI is thinking
    - message_start: New message starting
    - message_chunk: Partial message content
    - message_complete: Message finished

    DATA EVENTS: For data collection
    - data_collected: Field value collected (NO confirmation text)
    - confirmation: Separate confirmation message

    SYSTEM EVENTS: For system state
    - error: Error occurred
    - clarification_needed: Need user clarification

    VALUATION EVENTS: For valuation process
    - valuation_complete: Data collection complete, ready for calculation
    - valuation_preview: Preview of valuation report
    - html_preview: HTML report preview

    SUGGESTION EVENTS: For AI suggestions
    - suggestion_offered: Business type or KBO suggestions

    PROGRESS EVENTS: For progress tracking
    - progress_update: Progress percentage update
    """

    # Message events
    TYPING = "typing"
    MESSAGE_START = "message_start"
    MESSAGE_CHUNK = "message_chunk"
    MESSAGE_COMPLETE = "message_complete"

    # Data events
    DATA_COLLECTED = "data_collected"
    CONFIRMATION = "confirmation"

    # System events
    ERROR = "error"
    CLARIFICATION_NEEDED = "clarification_needed"

    # Valuation events
    VALUATION_COMPLETE = "valuation_complete"
    VALUATION_PREVIEW = "valuation_preview"
    HTML_PREVIEW = "html_preview"

    # Suggestion events
    SUGGESTION_OFFERED = "suggestion_offered"

    # Progress events
    PROGRESS_UPDATE = "progress_update"


@dataclass
class BaseEvent:
    """
    Base event with common fields.

    WHAT: Foundation for all events
    WHY: Ensures all events have event_id for deduplication
    HOW: All event classes inherit from this

    FIELDS:
    - type: Event type from EventType enum
    - event_id: Unique ID for deduplication (UUID)
    - session_id: Session identifier
    - timestamp: Unix timestamp for ordering
    """

    type: EventType
    event_id: str
    session_id: str
    timestamp: float = dataclass_field(default_factory=time.time)

    @classmethod
    def generate_id(cls) -> str:
        """Generate unique event ID."""
        return str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        NOTE: Converts EventType enum to string value
        """
        result = asdict(self)
        result["type"] = self.type.value  # Convert enum to string
        return result


@dataclass
class TypingEvent(BaseEvent):
    """
    AI is typing/thinking.

    USAGE: Show loading indicator to user
    """

    type: EventType = dataclass_field(default=EventType.TYPING, init=False)
    context: Optional[str] = None  # What AI is thinking about


@dataclass
class MessageStartEvent(BaseEvent):
    """
    New message starting.

    USAGE: Prepare UI for new message, clear any previous streaming state
    CRITICAL: This signals a NEW message, not continuation of previous
    """

    type: EventType = dataclass_field(default=EventType.MESSAGE_START, init=False)


@dataclass
class MessageChunkEvent(BaseEvent):
    """
    Partial message content for streaming.

    USAGE: Append to current streaming message
    NOTE: Content is additive, not cumulative
    """

    content: str = ""  # Default empty string for safety
    type: EventType = dataclass_field(default=EventType.MESSAGE_CHUNK, init=False)


@dataclass
class MessageCompleteEvent(BaseEvent):
    """
    Message finished streaming.

    USAGE: Finalize message, hide loading indicators
    """

    type: EventType = dataclass_field(default=EventType.MESSAGE_COMPLETE, init=False)
    content: Optional[str] = None  # Final complete message (optional)


@dataclass
class DataCollectedEvent(BaseEvent):
    """
    Field value collected from user.

    WHAT: Notifies that a field value has been extracted and stored
    WHY: Update UI with collected data, track progress
    HOW: Emit after successful field extraction

    CRITICAL: Does NOT include confirmation_text
    CRITICAL: Confirmation is a separate ConfirmationEvent or MessageCompleteEvent

    FIELDS:
    - field: Field name (company_name, revenue, etc.)
    - value: Extracted value (sanitized for storage)
    - display_value: Human-readable value for UI
    - confidence: Confidence score (0.0-1.0)
    - metadata: Additional field-specific data
    """

    field: str = ""  # Required fields with defaults to fix dataclass ordering
    value: Any = None
    display_value: str = ""
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None
    type: EventType = dataclass_field(default=EventType.DATA_COLLECTED, init=False)


@dataclass
class ConfirmationEvent(BaseEvent):
    """
    Confirmation message (separate from data collection).

    WHAT: Confirms data was saved
    WHY: User feedback, but separate from data event to avoid duplication
    HOW: Send AFTER DataCollectedEvent if confirmation needed

    NOTE: This is typically a MessageCompleteEvent with confirmation text
    """

    message: str = ""
    field: Optional[str] = None  # Which field was confirmed
    type: EventType = dataclass_field(default=EventType.CONFIRMATION, init=False)


@dataclass
class ErrorEvent(BaseEvent):
    """
    Error occurred.

    WHAT: Notifies of error
    WHY: Show error message to user, allow retry
    HOW: Include error message and optional error code

    FIELDS:
    - message: User-friendly error message
    - error_code: Machine-readable error code
    - recoverable: Whether user can retry
    - details: Additional error details
    """

    message: str = ""
    error_code: Optional[str] = None
    recoverable: bool = True
    details: Optional[Dict[str, Any]] = None
    type: EventType = dataclass_field(default=EventType.ERROR, init=False)


@dataclass
class ClarificationNeededEvent(BaseEvent):
    """
    Need clarification from user.

    USAGE: Show clarification question, highlight which field needs clarification
    """

    field: str = ""
    message: str = ""
    suggestions: Optional[List[str]] = None
    type: EventType = dataclass_field(default=EventType.CLARIFICATION_NEEDED, init=False)


@dataclass
class ValuationCompleteEvent(BaseEvent):
    """
    Data collection complete, ready for valuation.

    USAGE: Transition to calculation step, show success message
    """

    message: str = ""
    collected_data: Dict[str, Any] = dataclass_field(default_factory=dict)
    completeness: int = 0  # Percentage
    type: EventType = dataclass_field(default=EventType.VALUATION_COMPLETE, init=False)


@dataclass
class ValuationPreviewEvent(BaseEvent):
    """
    Preview of valuation data/results.

    USAGE: Show preview card or summary
    """

    preview_data: Dict[str, Any] = dataclass_field(default_factory=dict)
    type: EventType = dataclass_field(default=EventType.VALUATION_PREVIEW, init=False)


@dataclass
class HtmlPreviewEvent(BaseEvent):
    """
    HTML report preview.

    USAGE: Render HTML preview in UI
    """

    html_content: str = ""
    milestone: int = 0  # Progress milestone (25, 50, 75, 100)
    type: EventType = dataclass_field(default=EventType.HTML_PREVIEW, init=False)


@dataclass
class SuggestionOfferedEvent(BaseEvent):
    """
    AI suggestions (business types, KBO matches).

    USAGE: Show suggestion chips/buttons
    """

    field: str = ""
    suggestions: List[Dict[str, Any]] = dataclass_field(default_factory=list)
    message: Optional[str] = None
    type: EventType = dataclass_field(default=EventType.SUGGESTION_OFFERED, init=False)


@dataclass
class ProgressUpdateEvent(BaseEvent):
    """
    Progress update.

    USAGE: Update progress bar
    """

    percentage: int = 0
    fields_collected: int = 0
    fields_total: int = 0  # Required fields must come before optional ones
    message: Optional[str] = None
    type: EventType = dataclass_field(default=EventType.PROGRESS_UPDATE, init=False)


# Helper functions for creating events


def create_typing_event(session_id: str, context: Optional[str] = None) -> Dict[str, Any]:
    """Create typing event."""
    event = TypingEvent(event_id=BaseEvent.generate_id(), session_id=session_id, context=context)
    return event.to_dict()


def create_message_start_event(session_id: str) -> Dict[str, Any]:
    """Create message start event."""
    event = MessageStartEvent(event_id=BaseEvent.generate_id(), session_id=session_id)
    return event.to_dict()


def create_message_chunk_event(session_id: str, content: str) -> Dict[str, Any]:
    """Create message chunk event."""
    event = MessageChunkEvent(
        event_id=BaseEvent.generate_id(), session_id=session_id, content=content
    )
    return event.to_dict()


def create_message_complete_event(session_id: str, content: Optional[str] = None) -> Dict[str, Any]:
    """Create message complete event."""
    event = MessageCompleteEvent(
        event_id=BaseEvent.generate_id(), session_id=session_id, content=content
    )
    return event.to_dict()


def create_data_collected_event(
    session_id: str,
    field: str,
    value: Any,
    display_value: str,
    confidence: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create data collected event (NO confirmation text).

    CRITICAL: This event does NOT include confirmation_text
    CRITICAL: Send separate MessageCompleteEvent for confirmation
    """
    event = DataCollectedEvent(
        event_id=BaseEvent.generate_id(),
        session_id=session_id,
        field=field,
        value=value,
        display_value=display_value,
        confidence=confidence,
        metadata=metadata or {},
    )
    return event.to_dict()


def create_error_event(
    session_id: str,
    message: str,
    error_code: Optional[str] = None,
    recoverable: bool = True,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create error event."""
    event = ErrorEvent(
        event_id=BaseEvent.generate_id(),
        session_id=session_id,
        message=message,
        error_code=error_code,
        recoverable=recoverable,
        details=details,
    )
    return event.to_dict()


def create_valuation_complete_event(
    session_id: str, message: str, collected_data: Dict[str, Any], completeness: int
) -> Dict[str, Any]:
    """Create valuation complete event."""
    event = ValuationCompleteEvent(
        event_id=BaseEvent.generate_id(),
        session_id=session_id,
        message=message,
        collected_data=collected_data,
        completeness=completeness,
    )
    return event.to_dict()
