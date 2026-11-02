"""Bind a revenue multiple to the denominator documented in its source cohort."""

from collections.abc import Mapping
from decimal import Decimal

from src.api.schemas.accounting_money_authority import authoritative_reported_values

SUPPORTED_REVENUE_BASES = frozenset({"turnover", "total_operating_income"})


def revenue_multiple_basis(request: object, contract: Mapping[str, object] | None) -> tuple[str | None, str | None, Decimal | None]:
    cohort_basis = None
    if contract is not None:
        outcomes = contract.get("metric_outcomes")
        rows = outcomes.values() if isinstance(outcomes, Mapping) else outcomes if isinstance(outcomes, list) else [contract]
        for row in rows:
            if isinstance(row, Mapping) and str(row.get("metric", row.get("metric_name", contract.get("primary_metric")))) in {"ev_revenue", "ev_revenue_multiple", "revenue_multiple"}:
                value = row.get("revenue_definition")
                if value in SUPPORTED_REVENUE_BASES:
                    cohort_basis = str(value)
    case = getattr(request, "valuation_case", None)
    evidence = getattr(case, "accounting_evidence", None)
    years = evidence.get("years", []) if isinstance(evidence, Mapping) else getattr(evidence, "years", [])
    for year in years:
        period = year.get("period") if isinstance(year, Mapping) else getattr(year, "period", None)
        fiscal_year = period.get("fiscal_year") if isinstance(period, Mapping) else getattr(period, "fiscal_year", None)
        if fiscal_year != getattr(getattr(request, "current_year", None), "year", None):
            continue
        reported = year.get("reported_facts") if isinstance(year, Mapping) else getattr(year, "reported_facts", None)
        if not isinstance(reported, Mapping):
            continue
        basis = reported.get("accounting_basis")
        if not isinstance(basis, Mapping) or basis.get("status") != "reconciled":
            continue
        facts = authoritative_reported_values(reported, str(getattr(request, "currency", "")))
        if cohort_basis in SUPPORTED_REVENUE_BASES and facts.get(cohort_basis) is not None:
            amount = Decimal(str(facts[cohort_basis]))
            if amount.is_finite():
                return cohort_basis, cohort_basis, amount
    return None, cohort_basis, None
