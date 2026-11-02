"""
Domain Layer Interfaces

Protocol definitions for domain layer dependencies.
These interfaces allow the domain layer to depend on abstractions,
not concrete implementations from other layers.
"""

from .business_type_protocol import BusinessTypeTriageProtocol
from .repository_protocol import BusinessTypesRepositoryProtocol
from .request_protocol import ValuationRequestProtocol
from .transparency_protocol import TransparencyTrackerProtocol

__all__ = [
    "BusinessTypeTriageProtocol",
    "BusinessTypesRepositoryProtocol",
    "ValuationRequestProtocol",
    "TransparencyTrackerProtocol",
]

