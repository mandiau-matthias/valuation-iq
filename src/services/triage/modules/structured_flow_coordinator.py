"""
Structured flow coordinator types.

Provides FlowSection enum used by the structured question flow.
"""

from enum import Enum


class FlowSection(str, Enum):
    BASIC_INFO = "basic_info"
    OWNERSHIP = "ownership"
    FINANCIALS = "financials"
    COMPLETE = "complete"
