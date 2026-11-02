"""Exact response-to-run integrity checks with observable intentional failures."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from src.utils.source_policy_monitoring import SourcePolicyIssue, record_source_policy_issue

if TYPE_CHECKING:
    from src.api.schemas.valuation_contracts import CanonicalValuationRange


def _assert_run_range_matches(
    *,
    label: str,
    run_range: CanonicalValuationRange,
    low: Decimal,
    mid: Decimal,
    high: Decimal,
) -> None:
    for key, expected in (("low", low), ("mid", mid), ("high", high)):
        raw = run_range.get(key)
        try:
            actual = Decimal(str(raw))
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise ValueError(f"valuation_run {label} range has invalid {key}") from exc
        if actual != expected:
            record_source_policy_issue(SourcePolicyIssue.REPORT_CALCULATION_MISMATCH)
            raise ValueError(f"{label}_value_{key} does not match valuation_run range")


def _assert_run_payload_matches(
    *,
    label: str,
    outer: object,
    committed: object,
) -> None:
    from src.services.reports.stateless_valuation_run import (
        canonical_hash,
        transport_stable_valuation_run_value,
    )

    stable_outer = transport_stable_valuation_run_value(outer)
    stable_committed = transport_stable_valuation_run_value(committed)
    if canonical_hash(stable_outer) != canonical_hash(stable_committed):
        record_source_policy_issue(SourcePolicyIssue.REPORT_CALCULATION_MISMATCH)
        # Report field names only. This makes a sealed-run contract failure
        # operable without ever placing company values or evidence in logs.
        differing_fields: list[str] = []
        if isinstance(stable_outer, dict) and isinstance(stable_committed, dict):
            for key in sorted(set(stable_outer) | set(stable_committed)):
                if canonical_hash(stable_outer.get(key)) != canonical_hash(
                    stable_committed.get(key)
                ):
                    differing_fields.append(str(key))
        suffix = f" (differing_fields={','.join(differing_fields)})" if differing_fields else ""
        raise ValueError(f"{label} does not match immutable valuation_run{suffix}")
