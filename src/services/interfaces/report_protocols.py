"""
Report Protocols for Services Layer

Protocol definitions for report-related schemas.
These allow report transformers to work with API schemas without runtime dependencies.
"""

from typing import Protocol, Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime


class ReportDataProtocol(Protocol):
    """Protocol for report data structures."""
    
    company_name: Optional[str]
    valuation_id: Optional[str]
    enterprise_value: Optional[Decimal]
    equity_value: Optional[Decimal]
    methodology: Optional[str]
    confidence_score: Optional[Decimal]
    
    @property
    def transparency(self) -> Optional[Dict[str, Any]]:
        """Transparency data."""
        ...
    
    @property
    def steps(self) -> Optional[List[Dict[str, Any]]]:
        """Step outputs."""
        ...


class StepOutputProtocol(Protocol):
    """Protocol for step output structures."""
    
    step_number: int
    step_name: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    formula: Optional[str]
    explanation: Optional[str]

