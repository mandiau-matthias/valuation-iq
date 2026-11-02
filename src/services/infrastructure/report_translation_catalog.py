"""Locale catalog constructor compatibility exports."""

from src.services.infrastructure.report_translation_catalog_en import (
    build_english_report_translations,
)
from src.services.infrastructure.report_translation_catalog_fr import (
    build_french_report_translations,
)
from src.services.infrastructure.report_translation_catalog_nl import (
    build_dutch_report_translations,
)

__all__ = [
    "build_dutch_report_translations",
    "build_english_report_translations",
    "build_french_report_translations",
]
