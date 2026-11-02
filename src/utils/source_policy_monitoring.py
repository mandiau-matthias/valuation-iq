"""Bounded operational counters; no company identifiers or amounts in labels."""

from enum import Enum

from prometheus_client import Counter


class SourcePolicyIssue(str, Enum):
    EVIDENCE_REJECTION = "evidence_rejection"
    CURRENCY_PERIOD_CONFLICT = "currency_period_conflict"
    NORMALIZATION_DUPLICATION = "normalization_duplication"
    REPORT_CALCULATION_MISMATCH = "report_calculation_mismatch"


SOURCE_POLICY_REJECTIONS = Counter(
    "valuation_source_policy_rejections_total",
    "Source policy rejections and projection integrity failures, with bounded PII-free labels.",
    ["issue"],
)


def record_source_policy_issue(issue: SourcePolicyIssue) -> None:
    SOURCE_POLICY_REJECTIONS.labels(issue=issue.value).inc()
