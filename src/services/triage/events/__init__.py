"""
Triage Events Package

WHAT: Standardized event schema for conversational flow
WHY: Fix duplicate messages, ensure consistent event handling
HOW: Single source of truth for all event types and schemas

REFACTORING (December 2025):
- Standardized event schema with event_id for deduplication
- Separated data collection from confirmation messages
- Type-safe event definitions
"""

from .schema import (
    BaseEvent,
    ClarificationNeededEvent,
    ConfirmationEvent,
    DataCollectedEvent,
    ErrorEvent,
    EventType,
    HtmlPreviewEvent,
    MessageChunkEvent,
    MessageCompleteEvent,
    MessageStartEvent,
    ProgressUpdateEvent,
    SuggestionOfferedEvent,
    TypingEvent,
    ValuationCompleteEvent,
    ValuationPreviewEvent,
)

__all__ = [
    "EventType",
    "BaseEvent",
    "TypingEvent",
    "MessageStartEvent",
    "MessageChunkEvent",
    "MessageCompleteEvent",
    "DataCollectedEvent",
    "ConfirmationEvent",
    "ErrorEvent",
    "ValuationCompleteEvent",
    "ValuationPreviewEvent",
    "SuggestionOfferedEvent",
    "ClarificationNeededEvent",
    "ProgressUpdateEvent",
    "HtmlPreviewEvent",
]
