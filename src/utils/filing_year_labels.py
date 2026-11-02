"""Filing-year column labels for reports (aligned with Venus Base / Base−n)."""

from __future__ import annotations

from typing import Any

from src.services.infrastructure.translations import ReportTranslations
from src.utils.fiscal_year import get_filing_year_historical_offset


def format_year_column_with_filing_role(
    year: Any,
    base_filing_year: int,
    t: ReportTranslations,
) -> str:
    """Append (Base) or (Base − n) to the calendar year for multi-year tables."""
    off = get_filing_year_historical_offset(year, base_filing_year)
    ys = str(year)
    if off is None:
        return ys
    if off == 0:
        return f"{ys} ({t.filing_year_col_base})"
    return f"{ys} ({t.filing_year_col_base_minus.format(n=off)})"
