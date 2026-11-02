"""Composable field bases for :class:`ReportTranslations`."""

from .required_core import ReportTranslationRequiredCoreFields
from .required_methods import ReportTranslationRequiredMethodFields
from .default_tax_sellability import ReportTranslationDefaultTaxSellabilityFields
from .default_transferability import ReportTranslationDefaultTransferabilityFields
from .default_transformer import ReportTranslationDefaultTransformerFields
from .default_accountant_audit import ReportTranslationDefaultAccountantAuditFields
from .default_accountant_sections import ReportTranslationDefaultAccountantSectionFields

__all__ = [
    "ReportTranslationRequiredCoreFields",
    "ReportTranslationRequiredMethodFields",
    "ReportTranslationDefaultTaxSellabilityFields",
    "ReportTranslationDefaultTransferabilityFields",
    "ReportTranslationDefaultTransformerFields",
    "ReportTranslationDefaultAccountantAuditFields",
    "ReportTranslationDefaultAccountantSectionFields",
]
