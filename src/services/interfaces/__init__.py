"""
Service Layer Interfaces

Protocol definitions for service layer dependencies.
These interfaces allow services to work with request/response objects
without depending on API layer implementations.
"""

from .request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
    QuickValuationRequestProtocol,
    CurrentYearDataProtocol,
    HistoricalYearDataProtocol,
)
from .orchestrator_protocol import ValuationOrchestratorProtocol
from .api_protocols import (
    FinancialDataProtocol,
    MarketDataProtocol,
    YearDataInputProtocol,
    BusinessTypeProtocol,
    IndustryCategoryProtocol,
)
from .report_protocols import (
    ReportDataProtocol,
    StepOutputProtocol,
)
from .triage_protocols import (
    BusinessTypeCategory,
    BusinessTypeTriageEngineProtocol,
)

__all__ = [
    "ValuationRequestProtocol",
    "ValuationResponseProtocol",
    "QuickValuationRequestProtocol",
    "CurrentYearDataProtocol",
    "HistoricalYearDataProtocol",
    "ValuationOrchestratorProtocol",
    "FinancialDataProtocol",
    "MarketDataProtocol",
    "YearDataInputProtocol",
    "BusinessTypeProtocol",
    "IndustryCategoryProtocol",
    "ReportDataProtocol",
    "StepOutputProtocol",
    "BusinessTypeCategory",
    "BusinessTypeTriageEngineProtocol",
]

