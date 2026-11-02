"""Startup report translation catalog facade.

The report copy is split into owned section modules under
``startup_translation_catalog``. Keep this facade as the stable import for
the startup report context and any tests that need the full catalog.
"""

from __future__ import annotations

from typing import Dict

from src.services.reports.startup_translation_catalog import (
    build_startup_report_translations,
)

STARTUP_REPORT_TRANSLATIONS: Dict[str, Dict[str, str]] = build_startup_report_translations()
