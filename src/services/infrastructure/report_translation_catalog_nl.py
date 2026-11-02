"""Dutch report-copy catalog constructor facade."""

from src.services.infrastructure.report_translation_catalog_nl_sections import (
    build_dutch_translation_payload,
)


def build_dutch_report_translations(cls):
    """Return Dutch (nl) translations - Primary language."""
    return cls(**build_dutch_translation_payload())
