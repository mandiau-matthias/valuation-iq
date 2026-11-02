"""
Report Generation Strategies

Implements Strategy Pattern for different report types.
Each strategy encapsulates report-specific generation logic.
"""

from src.services.infrastructure.report_generation.strategies.base_report_strategy import (
    ReportStrategy,
    BaseReportStrategy,
)
from src.services.infrastructure.report_generation.strategies.accountant_view_strategy import (
    AccountantViewStrategy,
)
from src.services.infrastructure.report_generation.strategies.info_tab_strategy import (
    InfoTabStrategy,
)
from src.services.infrastructure.report_generation.strategies.pdf_strategy import (
    PDFGenerationStrategy,
)

__all__ = [
    "ReportStrategy",
    "BaseReportStrategy",
    "AccountantViewStrategy",
    "InfoTabStrategy",
    "PDFGenerationStrategy",
]

