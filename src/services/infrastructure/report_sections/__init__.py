"""
Report Section Builders

Extracted from MainReportDataAggregator to reduce the monolith's surface area
and allow focused testing of each report section independently.

Each module exports pure functions that take response/request data and return
a template context dict fragment.
"""

from .hybrid_section import build_hybrid_context
from .dcf_section import build_dcf_context
from .fiscal_section import build_fiscal_reference_context
from .validation import validate_report_context

__all__ = [
    "build_hybrid_context",
    "build_dcf_context",
    "build_fiscal_reference_context",
    "validate_report_context",
]
