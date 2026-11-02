"""Report context completeness scoring."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

_MAX_COMPLETENESS_SCORE = 100
_PresencePredicate = Callable[[object], bool]


@dataclass(frozen=True)
class _CompletenessRule:
    field: str
    points: int
    is_present: _PresencePredicate


def _is_core_value_present(value: object) -> bool:
    return value is not None and value != 0


def _is_important_value_present(value: object) -> bool:
    if isinstance(value, list):
        return bool(value)
    return value is not None


def _is_enrichment_value_present(value: object) -> bool:
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, list):
        return bool(value)

    if isinstance(value, (int, float)):
        return value > 0

    if isinstance(value, str):
        return bool(value)

    return False


def _rules_from_points(
    field_points: Mapping[str, int],
    is_present: _PresencePredicate,
) -> tuple[_CompletenessRule, ...]:
    return tuple(
        _CompletenessRule(field=field, points=points, is_present=is_present)
        for field, points in field_points.items()
    )


_CORE_RULES = _rules_from_points(
    {
        "company_name": 10,
        "valuation": 10,
        "sustainable_ebitda": 10,
        "applied_multiple": 10,
    },
    _is_core_value_present,
)

_IMPORTANT_RULES = _rules_from_points(
    {
        "valuation_date": 5,
        "report_id": 5,
        "industry": 5,
        "revenue": 5,
        "ebitda_adjustments": 5,
        "calibration_steps": 5,
    },
    _is_important_value_present,
)

_ENRICHMENT_RULES = _rules_from_points(
    {
        "kbo_number": 3,
        "legal_form": 3,
        "founded_year": 3,
        "employee_count": 3,
        "data_quality_score": 3,
        "comparables_count": 3,
        "benchmark_ev_ebitda_p50": 3,
        "has_industry_benchmarks": 3,
        "has_kbo_data": 3,
        "multi_year_ebitda": 3,
    },
    _is_enrichment_value_present,
)

_COMPLETENESS_RULES = _CORE_RULES + _IMPORTANT_RULES + _ENRICHMENT_RULES


def _score_rule(context: Mapping[str, object], rule: _CompletenessRule) -> int:
    value = context.get(rule.field)
    if rule.is_present(value):
        return rule.points
    return 0


def calculate_report_completeness_score(context: Mapping[str, object]) -> int:
    """Calculate a report-context completeness score from 0 to 100."""
    score = sum(_score_rule(context, rule) for rule in _COMPLETENESS_RULES)
    return min(_MAX_COMPLETENESS_SCORE, score)
