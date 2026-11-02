"""Section-owned Dutch report-copy payload builders."""

from __future__ import annotations

from typing import Dict

from src.services.infrastructure.report_translation_catalog_nl_sections.core_financial import (
    build_dutch_core_financial_translations,
)
from src.services.infrastructure.report_translation_catalog_nl_sections.methodology_fiscal import (
    build_dutch_methodology_fiscal_translations,
)


def build_dutch_translation_payload() -> Dict[str, object]:
    """Return Dutch report copy kwargs in constructor order."""
    payload: Dict[str, object] = {}
    payload.update(build_dutch_core_financial_translations())
    payload.update(build_dutch_methodology_fiscal_translations())
    return payload
