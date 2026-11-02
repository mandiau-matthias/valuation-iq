"""Resolve per-period evidence dates without carrying facts across years."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

from src.api.schemas.stateless_api import CalculateRequest
from src.api.schemas.valuation_contracts import (
    iter_accounting_reported_facts,
    priced_accounting_evidence,
)


def evidence_source_as_of(request: CalculateRequest, fiscal_year: int) -> str | None:
    candidates: list[str] = []
    case = request.valuation_case
    package = priced_accounting_evidence(case)
    if package is not None:
        for fact in iter_accounting_reported_facts(package):
            if fact.fiscal_year != fiscal_year:
                continue
            for source in fact.source_refs:
                _append_iso(candidates, source.observed_at)
        if package.period_end and package.period_end.startswith(str(fiscal_year)):
            _append_iso(candidates, package.period_end)

    metadata = request.metadata if isinstance(request.metadata, Mapping) else {}
    by_year = metadata.get("public_financial_inputs_by_year")
    raw_rows = by_year.get(str(fiscal_year)) if isinstance(by_year, Mapping) else None
    if isinstance(raw_rows, list):
        for raw in raw_rows:
            if not isinstance(raw, Mapping):
                continue
            for key in (
                "source_as_of",
                "observed_at",
                "deposited_at",
                "filing_date",
                "effective_date",
            ):
                _append_iso(candidates, raw.get(key))

    year_row = next(
        (
            row
            for row in [request.current_year, *request.historical_years]
            if row.year == fiscal_year
        ),
        None,
    )
    year_metadata = (
        year_row.ebitda_normalization_metadata
        if year_row is not None and isinstance(year_row.ebitda_normalization_metadata, Mapping)
        else {}
    )
    for key in ("source_as_of", "observed_at", "financials_as_of"):
        _append_iso(candidates, year_metadata.get(key))

    return max(candidates, key=_sort_key) if candidates else None


def _append_iso(target: list[str], value: object) -> None:
    if isinstance(value, (datetime, date)):
        target.append(value.isoformat().replace("+00:00", "Z"))
        return
    if isinstance(value, str) and value.strip():
        candidate = value.strip()
        try:
            datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            try:
                date.fromisoformat(candidate[:10])
            except ValueError:
                return
        target.append(candidate)


def _sort_key(value: str) -> tuple[str, str]:
    return value[:10], value
