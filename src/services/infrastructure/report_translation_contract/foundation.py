"""Aggregate foundation report translation contract fields."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.infrastructure.report_translation_contract.foundation_cover import (
    ReportTranslationFoundationCoverFields,
)
from src.services.infrastructure.report_translation_contract.foundation_executive_summary import (
    ReportTranslationFoundationExecutiveSummaryFields,
)
from src.services.infrastructure.report_translation_contract.foundation_ebitda_normalization import (
    ReportTranslationFoundationEbitdaNormalizationFields,
)
from src.services.infrastructure.report_translation_contract.foundation_disclaimers import (
    ReportTranslationFoundationDisclaimerFields,
)
from src.services.infrastructure.report_translation_contract.foundation_attestation import (
    ReportTranslationFoundationAttestationFields,
)
from src.services.infrastructure.report_translation_contract.foundation_sotp_trigger import (
    ReportTranslationFoundationSotpTriggerFields,
)
from src.services.infrastructure.report_translation_contract.foundation_components import (
    ReportTranslationFoundationComponentFields,
)
from src.services.infrastructure.report_translation_contract.foundation_calibration import (
    ReportTranslationFoundationCalibrationFields,
)
from src.services.infrastructure.report_translation_contract.foundation_dcf import (
    ReportTranslationFoundationDcfFields,
)
from src.services.infrastructure.report_translation_contract.foundation_saas_cap_table import (
    ReportTranslationFoundationSaasCapTableFields,
)
from src.services.infrastructure.report_translation_contract.foundation_adjusted_nav import (
    ReportTranslationFoundationAdjustedNavFields,
)
from src.services.infrastructure.report_translation_contract.foundation_per_method import (
    ReportTranslationFoundationPerMethodFields,
)


FOUNDATION_FIELD_SECTIONS = (
    ReportTranslationFoundationCoverFields,
    ReportTranslationFoundationExecutiveSummaryFields,
    ReportTranslationFoundationEbitdaNormalizationFields,
    ReportTranslationFoundationDisclaimerFields,
    ReportTranslationFoundationAttestationFields,
    ReportTranslationFoundationSotpTriggerFields,
    ReportTranslationFoundationComponentFields,
    ReportTranslationFoundationCalibrationFields,
    ReportTranslationFoundationDcfFields,
    ReportTranslationFoundationSaasCapTableFields,
    ReportTranslationFoundationAdjustedNavFields,
    ReportTranslationFoundationPerMethodFields,
)


# Dataclasses collect inherited fields in reverse base-class order, so the
# aggregate bases are intentionally listed from last report section to first.
@dataclass(frozen=True)
class ReportTranslationFoundationFields(
    ReportTranslationFoundationPerMethodFields,
    ReportTranslationFoundationAdjustedNavFields,
    ReportTranslationFoundationSaasCapTableFields,
    ReportTranslationFoundationDcfFields,
    ReportTranslationFoundationCalibrationFields,
    ReportTranslationFoundationComponentFields,
    ReportTranslationFoundationSotpTriggerFields,
    ReportTranslationFoundationAttestationFields,
    ReportTranslationFoundationDisclaimerFields,
    ReportTranslationFoundationEbitdaNormalizationFields,
    ReportTranslationFoundationExecutiveSummaryFields,
    ReportTranslationFoundationCoverFields,
):
    """Stable aggregate for all foundation report translation fields."""


__all__ = [
    "FOUNDATION_FIELD_SECTIONS",
    "ReportTranslationFoundationFields",
]
