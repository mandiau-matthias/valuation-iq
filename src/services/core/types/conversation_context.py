"""
Conversation Context types for triage flow.

Provides the ConversationContext dataclass used throughout the triage coordinators
and the DataCompletenessLevel enum for tracking data collection progress.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class DataCompletenessLevel(str, Enum):
    MINIMAL = "minimal"
    BASIC = "basic"
    STANDARD = "standard"
    MODERATE = "moderate"
    COMPREHENSIVE = "comprehensive"


@dataclass
class ConversationContext:
    session_id: str
    company_name: Optional[str] = None
    last_asked_field: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    revenue: Optional[Decimal] = None
    ebitda: Optional[Decimal] = None
    industry: Optional[str] = None
    employees: Optional[int] = None
    founding_year: Optional[int] = None
    founded_year: Optional[int] = None
    business_type: Optional[str] = None
    business_structure: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    total_assets: Optional[Decimal] = None
    total_debt: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    owner_profile: Optional[Dict[str, Any]] = None
    registry_data: Optional[Dict[str, Any]] = None
    awaiting_response_for: Optional[str] = None
    company_info: Optional[Dict[str, Any]] = None
    completeness: Optional[DataCompletenessLevel] = None
    business_type_id: Optional[str] = None
    business_type_metadata: Optional[Dict[str, Any]] = None
    business_type_suggestions: Optional[List[Any]] = None
    pending_clarification_field: Optional[str] = None
    pending_clarification_value: Optional[Any] = None
    pending_clarification_raw_input: Optional[str] = None
    kbo_suggestion: Optional[Dict[str, Any]] = None

    _COLLECTED_FIELDS = [
        'company_name', 'revenue', 'ebitda', 'industry', 'employees',
        'founding_year', 'founded_year', 'business_type', 'business_structure',
        'country', 'country_code', 'total_assets', 'total_debt', 'net_income',
        'business_type_id',
    ]

    @property
    def collected_data(self) -> Dict[str, Any]:
        result = {}
        for f in self._COLLECTED_FIELDS:
            val = getattr(self, f, None)
            if val is not None:
                result[f] = val
        return result
