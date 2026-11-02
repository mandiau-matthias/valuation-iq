"""French report-copy catalog constructor facade."""

from src.services.infrastructure.report_translation_catalog_fr_sections import (
    build_french_translation_payload,
)


def build_french_report_translations(cls):
    """Return French (fr) translations."""
    return cls(**build_french_translation_payload())
