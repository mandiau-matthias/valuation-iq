"""French report-copy payload for the full ``ReportTranslations`` contract."""

from __future__ import annotations

from typing import Dict, Mapping

from src.services.infrastructure.report_translation_catalog_fr_sections.generated_payload import (
    FRENCH_TRANSLATION_PAYLOAD,
)
from src.services.infrastructure.report_translation_catalog_fr_sections.copy_spacing import (
    repair_french_report_copy_spacing,
)


FRENCH_REVIEWED_TRANSLATION_OVERRIDES: Dict[str, object] = {}


def build_french_translation_payload(
    reviewed_overrides: Mapping[str, object] | None = None,
) -> Dict[str, object]:
    """Return the complete French report translation payload with safe token spacing."""
    payload = dict(FRENCH_TRANSLATION_PAYLOAD)
    payload.update(FRENCH_REVIEWED_TRANSLATION_OVERRIDES)
    if reviewed_overrides:
        payload.update(reviewed_overrides)
    return repair_french_report_copy_spacing(payload)
