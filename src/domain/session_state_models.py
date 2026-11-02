"""Hybrid valuation session field-state models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FieldStatus(str, Enum):
    """Status of a data field in the valuation session."""

    AVAILABLE = "available"
    UNCERTAIN = "uncertain"
    MISSING = "missing"
    NORMALIZED = "normalized"


class DataSource(str, Enum):
    """Source of a data field value."""

    KBO = "kbo"
    KVK = "kvk"
    IMPORT = "import"
    HISTORY = "history"
    USER_INPUT = "user_input"
    AI_SUGGESTED = "ai_suggested"


class InterfaceRoute(str, Enum):
    """Target interface for handling missing or uncertain data."""

    MANUAL = "manual"
    CHAT = "chat"


class FieldMetadata(BaseModel):
    """Metadata for status, source, confidence, and audit trail of a field."""

    status: FieldStatus
    source: DataSource
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    original_value: Optional[Any] = Field(None, description="Original value before normalization")
    normalized_value: Optional[Any] = Field(
        None, description="Value after normalization (if applicable)"
    )
    normalization_reason: Optional[str] = Field(None, description="Reason for normalization")
    source_reference: Optional[str] = Field(
        None,
        description="Specific source reference (e.g., 'KBO 0123.456.789', 'Yuki Import 2024-01-15')",
    )
    suggested_interface: Optional[InterfaceRoute] = Field(
        None,
        description="Suggested UI for handling this field",
    )
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = Field(None, description="User ID or 'system' for automatic updates")
    validation_message: Optional[str] = Field(
        None, description="Validation warning or error message"
    )


class ActionItem(BaseModel):
    """Missing or uncertain data that needs user attention."""

    field: str = Field(..., description="Field name (e.g., 'owner_salary', 'ebitda')")
    field_label: str = Field(..., description="Human-readable field label for UI")
    reason: str = Field(..., description="Why this action is needed")
    interface: InterfaceRoute = Field(..., description="Where to handle this action")
    priority: int = Field(1, ge=1, le=10, description="Priority 1 (highest) to 10 (lowest)")
    suggested_question: Optional[str] = Field(
        None,
        description="Suggested question for the assistant to ask (for chat-routed items)",
    )
    current_value: Optional[Any] = Field(None, description="Current value if any")
    suggested_value: Optional[Any] = Field(None, description="AI-suggested value if applicable")
    context: Optional[Dict[str, object]] = Field(
        None, description="Additional context for handling"
    )


class GapAnalysisResult(BaseModel):
    """Data-completeness and quality analysis for a valuation session."""

    completeness_score: int = Field(
        ..., ge=0, le=100, description="Overall data completeness 0-100%"
    )
    ready_for_calculation: bool = Field(..., description="True if minimum data requirements met")
    fields_by_status: Dict[str, List[str]] = Field(
        default_factory=lambda: {"available": [], "uncertain": [], "missing": [], "normalized": []},
        description="Fields grouped by their status",
    )
    action_items: List[ActionItem] = Field(
        default_factory=list, description="Prioritized action items"
    )
    available_count: int = Field(0, description="Number of available fields")
    uncertain_count: int = Field(0, description="Number of uncertain fields needing review")
    missing_count: int = Field(0, description="Number of missing required fields")
    chat_action_count: int = Field(0, description="Number of actions routed to chat")
    manual_action_count: int = Field(0, description="Number of actions routed to manual UI")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = Field(None, description="Associated session ID")


class SessionFieldState(BaseModel):
    """Complete calculator/chat synced field state for a valuation session."""

    data: Dict[str, Any] = Field(default_factory=dict, description="Field name to value mapping")
    field_metadata: Dict[str, FieldMetadata] = Field(
        default_factory=dict,
        description="Field name to metadata mapping",
    )
    gap_analysis: Optional[GapAnalysisResult] = Field(
        None, description="Latest gap analysis result"
    )
    sync_version: int = Field(0, description="Increments on any change for sync detection")
    focused_field: Optional[str] = Field(None, description="Field currently focused in Calculator")
    active_view: Optional[str] = Field(None, description="Current view: 'calculator' or 'chat'")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


__all__ = [
    "ActionItem",
    "DataSource",
    "FieldMetadata",
    "FieldStatus",
    "GapAnalysisResult",
    "InterfaceRoute",
    "SessionFieldState",
]
