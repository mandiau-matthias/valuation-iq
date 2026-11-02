"""English report-copy catalog constructor facade."""

from src.services.infrastructure.report_translation_catalog_en_sections import (
    build_english_translation_payload,
)


def build_english_report_translations(cls):
    """Return English (en) translations."""
    return cls(**build_english_translation_payload())
