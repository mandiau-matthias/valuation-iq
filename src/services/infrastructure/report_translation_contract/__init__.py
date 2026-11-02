"""Section-owned dataclass bases for report translations."""

from src.services.infrastructure.report_translation_contract.accountant_audit_sources import (
    ReportTranslationAccountantAuditSourceFields,
)
from src.services.infrastructure.report_translation_contract.accountant_quality_strategy import (
    ReportTranslationAccountantQualityStrategyFields,
)
from src.services.infrastructure.report_translation_contract.accountant_sme_conditionals import (
    ReportTranslationAccountantSmeConditionalFields,
)
from src.services.infrastructure.report_translation_contract.fiscal_synthesis import (
    ReportTranslationFiscalSynthesisFields,
)
from src.services.infrastructure.report_translation_contract.foundation import (
    ReportTranslationFoundationFields,
)
from src.services.infrastructure.report_translation_contract.owner_sellability import (
    ReportTranslationOwnerSellabilityFields,
)
from src.services.infrastructure.report_translation_contract.stage_aware_breakdown import (
    ReportTranslationStageAwareBreakdownFields,
)
from src.services.infrastructure.report_translation_contract.transformer_accountant_core import (
    ReportTranslationTransformerAccountantCoreFields,
)

__all__ = [
    "ReportTranslationAccountantAuditSourceFields",
    "ReportTranslationAccountantQualityStrategyFields",
    "ReportTranslationAccountantSmeConditionalFields",
    "ReportTranslationFiscalSynthesisFields",
    "ReportTranslationFoundationFields",
    "ReportTranslationOwnerSellabilityFields",
    "ReportTranslationStageAwareBreakdownFields",
    "ReportTranslationTransformerAccountantCoreFields",
]
