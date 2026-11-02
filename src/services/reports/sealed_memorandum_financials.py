"""Financial-history and normalisation projections for sealed memoranda."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

from src.services.reports.sealed_memorandum_errors import SealedMemorandumModelError


def _map(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[object]:
    return (
        list(value)
        if isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
        else []
    )


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _source_period_years(value: object) -> set[int]:
    years: set[int] = set()
    for raw in _rows(value):
        text = str(raw)
        matches = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", text)]
        years.update(matches)
        if len(matches) == 2 and any(
            separator in text for separator in ("-", "–", "—", "to")
        ):
            start, end = matches
            if 0 <= end - start <= 20:
                years.update(range(start, end + 1))
    return years


def normalization_rows(
    context: Mapping[str, object], copy: Mapping[str, str], display
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for index, raw in enumerate(_rows(context.get("normalization_adjustments"))):
        row = _map(raw)
        fingerprint = str(
            row.get("proposal_fingerprint")
            or row.get("fingerprint")
            or row.get("id")
            or index
        )
        raw_decision = str(row.get("decision") or row.get("status") or "—")
        normalized_decision = raw_decision.strip().lower()
        if normalized_decision in {"accepted", "approved", "accept", "aanvaard"}:
            decision = copy["accepted"]
        elif normalized_decision in {"rejected", "declined", "reject", "afgewezen"}:
            decision = copy["declined"]
        else:
            decision = raw_decision
        output.append(
            {
                "row_id": fingerprint,
                "account": str(
                    row.get("account_name")
                    or row.get("account")
                    or row.get("description")
                    or "—"
                ),
                "year": str(row.get("fiscal_year") or row.get("year") or "—"),
                "decision": decision,
                "amount": display(
                    row.get("amount")
                    or row.get("adjustment_amount")
                    or row.get("value"),
                    "signed_currency",
                ),
                "amount_field_id": f"normalization.{fingerprint}.amount",
                "rationale": str(
                    row.get("rationale")
                    or row.get("reason")
                    or row.get("evidence")
                    or "—"
                ),
                "labels": {
                    "account": copy["account"],
                    "year": copy["year"],
                    "decision": copy["decision"],
                    "amount": copy["amount"],
                    "rationale": copy["rationale"],
                },
            }
        )
    return output


def financial_history_rows(
    context: Mapping[str, object],
    scope: Mapping[str, object],
    copy: Mapping[str, str],
    display,
) -> list[dict[str, object]]:
    included_years = _source_period_years(scope.get("source_periods"))
    raw_rows = [*_rows(context.get("historical_years_data"))]
    current = context.get("current_year_data")
    if isinstance(current, Mapping):
        raw_rows.append(current)

    by_year: dict[int, dict[str, object]] = {}
    for raw in raw_rows:
        row = _map(raw)
        year = _decimal(row.get("year"))
        if year is None or year != year.to_integral_value():
            continue
        fiscal_year = int(year)
        if row.get("is_forecast") is True or (
            included_years and fiscal_year not in included_years
        ):
            continue
        values = {
            "year": fiscal_year,
            "revenue": _decimal(row.get("revenue")),
            "reported_ebitda": (
                _decimal(row.get("reported_ebitda"))
                if row.get("reported_ebitda") is not None
                else _decimal(row.get("ebitda"))
            ),
            "total_assets": _decimal(row.get("total_assets")),
            "total_equity": (
                _decimal(row.get("total_equity"))
                if row.get("total_equity") is not None
                else _decimal(row.get("equity"))
            ),
        }
        existing = by_year.get(fiscal_year)
        if existing is not None and existing != values:
            raise SealedMemorandumModelError(
                f"financial history contains conflicting rows for {fiscal_year}"
            )
        by_year[fiscal_year] = values

    output: list[dict[str, object]] = []
    for fiscal_year, values in sorted(by_year.items()):
        revenue = values.get("revenue")
        ebitda = values.get("reported_ebitda")
        assert revenue is None or isinstance(revenue, Decimal)
        assert ebitda is None or isinstance(ebitda, Decimal)
        margin = (
            ebitda / revenue
            if ebitda is not None and revenue not in {None, 0}
            else None
        )
        output.append(
            {
                "year": str(fiscal_year),
                "cells": [
                    {
                        "field_id": f"financials.{fiscal_year}.{field_id}",
                        "label": copy[label],
                        "raw": str(value) if value is not None else "",
                        "display": display(value, kind),
                    }
                    for field_id, label, value, kind in (
                        ("revenue", "revenue_short", revenue, "currency"),
                        ("reported_ebitda", "reported_ebitda", ebitda, "currency"),
                        ("ebitda_margin", "ebitda_margin", margin, "percent_ratio"),
                        (
                            "total_assets",
                            "total_assets",
                            values.get("total_assets"),
                            "currency",
                        ),
                        (
                            "book_equity",
                            "book_equity",
                            values.get("total_equity"),
                            "currency",
                        ),
                    )
                ],
            }
        )
    return output
