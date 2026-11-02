"""Section-owned liquidation report translation payloads."""

from __future__ import annotations

from typing import Dict

from src.services.reports.liquidation_report_translation_sections.cascade_labels import (
    CASCADE_TIER_LABELS_EN,
)
from src.services.reports.liquidation_report_translation_sections.creditor_buyer import (
    build_creditor_buyer_translations,
)
from src.services.reports.liquidation_report_translation_sections.disclosures_statement import (
    build_disclosures_statement_translations,
)
from src.services.reports.liquidation_report_translation_sections.executive_distress import (
    build_executive_distress_translations,
)
from src.services.reports.liquidation_report_translation_sections.realisation_waterfall import (
    build_realisation_waterfall_translations,
)


def build_liquidation_report_translations() -> Dict[str, Dict[str, str]]:
    """Return the full liquidation report translation payload."""
    payload: Dict[str, Dict[str, str]] = {}
    for section in (
        build_executive_distress_translations(),
        build_realisation_waterfall_translations(),
        build_disclosures_statement_translations(),
        build_creditor_buyer_translations(),
    ):
        payload.update(section)
    return payload


__all__ = [
    "CASCADE_TIER_LABELS_EN",
    "build_liquidation_report_translations",
]
