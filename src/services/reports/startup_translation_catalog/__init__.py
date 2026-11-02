"""Owned startup report translation catalog slices."""

from __future__ import annotations

from typing import Dict

from src.services.reports.startup_translation_catalog.evidence_labels import (
    STARTUP_REPORT_EVIDENCE_LABEL_TRANSLATIONS,
)
from src.services.reports.startup_translation_catalog.french import (
    STARTUP_REPORT_FRENCH_TRANSLATIONS,
)
from src.services.reports.startup_translation_catalog.methodology import (
    STARTUP_REPORT_METHODOLOGY_TRANSLATIONS,
)
from src.services.reports.startup_translation_catalog.overview import (
    STARTUP_REPORT_OVERVIEW_TRANSLATIONS,
)
from src.services.reports.startup_translation_catalog.risk_sensitivity import (
    STARTUP_REPORT_RISK_SENSITIVITY_TRANSLATIONS,
)


def build_startup_report_translations() -> Dict[str, Dict[str, str]]:
    """Return the startup report copy catalog in template render order."""
    catalog = {
        **STARTUP_REPORT_OVERVIEW_TRANSLATIONS,
        **STARTUP_REPORT_EVIDENCE_LABEL_TRANSLATIONS,
        **STARTUP_REPORT_METHODOLOGY_TRANSLATIONS,
        **STARTUP_REPORT_RISK_SENSITIVITY_TRANSLATIONS,
    }
    missing_french = sorted(set(catalog) - set(STARTUP_REPORT_FRENCH_TRANSLATIONS))
    extra_french = sorted(set(STARTUP_REPORT_FRENCH_TRANSLATIONS) - set(catalog))
    if missing_french or extra_french:
        raise RuntimeError(
            "Startup report French catalog mismatch: "
            f"missing={missing_french}, extra={extra_french}"
        )
    return {
        key: {**entry, "fr": STARTUP_REPORT_FRENCH_TRANSLATIONS[key]}
        for key, entry in catalog.items()
    }
