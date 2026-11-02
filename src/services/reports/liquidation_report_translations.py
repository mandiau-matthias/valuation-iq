"""Liquidation report translation catalog facade."""

from __future__ import annotations

from typing import Dict

from src.services.reports.liquidation_report_translation_sections import (
    CASCADE_TIER_LABELS_EN,
    build_liquidation_report_translations,
)

LIQUIDATION_REPORT_TRANSLATIONS: Dict[str, Dict[str, str]] = build_liquidation_report_translations()

__all__ = [
    "CASCADE_TIER_LABELS_EN",
    "LIQUIDATION_REPORT_TRANSLATIONS",
]
