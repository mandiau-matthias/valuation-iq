"""Legacy compatibility base for older report translation field imports."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationRequiredCoreFields:
    """Legacy empty base retained for import compatibility."""
