"""
Report Transformer Orchestrators — DEPRECATED / LEGACY

.. deprecated::
    Not used by the production report pipeline.  The active path is
    ``MainReportDataAggregator`` via ``src.api.routes.reports``.
"""

from .report_transformer_orchestrator import ReportTransformerOrchestrator

__all__ = [
    'ReportTransformerOrchestrator'
]

