"""
Transformers for converting ValuationResponse to template-friendly data structures.

.. deprecated::
    These transformers are NOT used by the production report pipeline.
    The active report path is ``MainReportDataAggregator`` (called by
    ``src.api.routes.reports._build_report_context``).  These modules
    exist for backward compatibility but should not receive new features.
"""

from .base_transformer import BaseTransformer
from .executive_summary_transformer import ExecutiveSummaryTransformer
from .company_overview_transformer import CompanyOverviewTransformer
from .financial_analysis_transformer import FinancialAnalysisTransformer
from .valuation_methodology_transformer import ValuationMethodologyTransformer
from .valuation_conclusion_transformer import ValuationConclusionTransformer
from .appendices_transformer import AppendicesTransformer
from .description_transformer import DescriptionTransformer
from .information_sources_transformer import InformationSourcesTransformer

__all__ = [
    'BaseTransformer',
    'ExecutiveSummaryTransformer',
    'CompanyOverviewTransformer',
    'FinancialAnalysisTransformer',
    'ValuationMethodologyTransformer',
    'ValuationConclusionTransformer',
    'AppendicesTransformer',
    'DescriptionTransformer',
    'InformationSourcesTransformer',
]

