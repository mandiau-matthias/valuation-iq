"""
Compatibility exports for triage service protocols.

Business-type taxonomy and triage protocol ownership live in the domain layer.
This module preserves the service-layer import path without duplicating enums
or protocol method contracts.
"""

from src.domain.interfaces.business_type_protocol import (
    BusinessTypeCategory,
    BusinessTypeTriageProtocol,
)

BusinessTypeTriageEngineProtocol = BusinessTypeTriageProtocol

__all__ = ["BusinessTypeCategory", "BusinessTypeTriageEngineProtocol"]
