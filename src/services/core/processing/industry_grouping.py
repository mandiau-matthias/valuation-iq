"""Shared grouping helpers for pattern processing."""

from collections.abc import Iterable
from typing import Protocol, TypeVar


class IndustryValuation(Protocol):
    industry: str


ValuationT = TypeVar("ValuationT", bound=IndustryValuation)


def group_by_industry(valuations: Iterable[ValuationT]) -> dict[str, list[ValuationT]]:
    """Group valuation-like objects by their industry value."""
    groups: dict[str, list[ValuationT]] = {}
    for valuation in valuations:
        groups.setdefault(valuation.industry, []).append(valuation)
    return groups
