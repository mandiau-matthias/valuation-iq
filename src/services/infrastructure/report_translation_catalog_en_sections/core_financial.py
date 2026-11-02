"""English core-financial report copy assembled from section-owned catalogs."""

from __future__ import annotations

from src.services.infrastructure.report_translation_catalog_en_sections.core_financial_cover_exec import (
    COVER_AND_EXECUTIVE_TRANSLATIONS,
)
from src.services.infrastructure.report_translation_catalog_en_sections.core_financial_ebitda_disclosure import (
    EBITDA_AND_DISCLOSURE_TRANSLATIONS,
)
from src.services.infrastructure.report_translation_catalog_en_sections.core_financial_components_dcf import (
    COMPONENTS_CALIBRATION_AND_DCF_TRANSLATIONS,
)
from src.services.infrastructure.report_translation_catalog_en_sections.core_financial_saas_nav import (
    SAAS_AND_NAV_TRANSLATIONS,
)

CORE_FINANCIAL_TRANSLATION_SECTIONS: tuple[dict[str, object], ...] = (
    COVER_AND_EXECUTIVE_TRANSLATIONS,
    EBITDA_AND_DISCLOSURE_TRANSLATIONS,
    COMPONENTS_CALIBRATION_AND_DCF_TRANSLATIONS,
    SAAS_AND_NAV_TRANSLATIONS,
)


def build_english_core_financial_translations() -> dict[str, object]:
    """Return English cover, financial, DCF, SaaS, and NAV report copy."""
    payload: dict[str, object] = {}
    for section in CORE_FINANCIAL_TRANSLATION_SECTIONS:
        payload.update(section)
    return payload
