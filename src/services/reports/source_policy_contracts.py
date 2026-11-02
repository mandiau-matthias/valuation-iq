"""Validate additive sealed contracts while preserving historical run readers."""

from collections.abc import Mapping

from src.api.schemas.financial_history import financial_history_from_lineage
from src.api.schemas.method_eligibility import MethodEligibility

from .range_provenance import RangeProvenance


def validate_optional_source_policy_contracts(
    lineage: Mapping[str, object], *, currency: str | None = None
) -> None:
    history = financial_history_from_lineage(lineage)
    if history is not None and currency is not None and history.currency != currency:
        raise ValueError("SOURCE_POLICY_CURRENCY_MISMATCH: financial history differs from run")
    eligibility = None
    provenance = None
    if lineage.get("method_eligibility") is not None:
        eligibility = MethodEligibility.model_validate(lineage["method_eligibility"])
    if lineage.get("range_provenance") is not None:
        provenance = RangeProvenance.model_validate(lineage["range_provenance"])
    if eligibility is not None and provenance is not None:
        if eligibility.resolved_weights != provenance.resolved_weights:
            raise ValueError("SOURCE_POLICY_WEIGHT_MISMATCH: method and range weights differ")
