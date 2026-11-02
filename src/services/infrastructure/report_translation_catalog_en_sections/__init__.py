"""Section-owned English report-copy payload builders."""

from __future__ import annotations

from typing import Dict

from src.services.infrastructure.report_translation_catalog_en_sections.accountant_audit_quality import (
    build_english_accountant_audit_quality_translations,
)
from src.services.infrastructure.report_translation_catalog_en_sections.accountant_core import (
    build_english_accountant_core_translations,
)
from src.services.infrastructure.report_translation_catalog_en_sections.audit_methodology import (
    build_english_audit_methodology_translations,
)
from src.services.infrastructure.report_translation_catalog_en_sections.core_financial import (
    build_english_core_financial_translations,
)
from src.services.infrastructure.report_translation_catalog_en_sections.sellability import (
    build_english_sellability_translations,
)


def build_english_translation_payload() -> Dict[str, object]:
    """Return English report copy kwargs in constructor order."""
    payload: Dict[str, object] = {}
    payload.update(build_english_core_financial_translations())
    payload.update(build_english_audit_methodology_translations())
    payload.update(build_english_sellability_translations())
    payload.update(build_english_accountant_core_translations())
    payload.update(build_english_accountant_audit_quality_translations())
    return payload
