"""Belgian arithmetic reference (4x EBITDA + book equity), not tax certification."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Optional

from src.api.schemas.stateless_api import MethodResult
from src.domain.financial_arithmetic import FinancialNumber, decimal_number, money

from ._shared import resolve_book_equity

_LABEL = "Fiscale Referentiewaarde (4× EBITDA)"


def _unavailable(reason: str) -> MethodResult:
    return MethodResult(
        value=None, method_key="fiscal_4x", label=_LABEL, available=False, unavailable_reason=reason
    )


def calculate_fiscal_4x_result(
    *,
    country_code: str,
    ebitda: FinancialNumber,
    balance_sheet: Optional[Mapping[str, object]],
    ownership_multiplier: Decimal,
) -> MethodResult:
    """Preserve the reference formula and round only final monetary outputs."""
    if country_code != "BE":
        return _unavailable(
            "Fiscale referentiewaarde is enkel beschikbaar voor Belgische ondernemingen."
        )
    try:
        earnings = decimal_number(ebitda, "EBITDA")
        ownership = decimal_number(ownership_multiplier, "ownership multiplier")
        if not Decimal(0) <= ownership <= Decimal(1):
            raise ValueError("Ownership multiplier must fall between zero and one.")
        if balance_sheet is not None:
            for field in ("total_equity", "total_assets", "total_liabilities"):
                if balance_sheet.get(field) is not None:
                    decimal_number(balance_sheet[field], field)
    except ValueError as exc:
        return _unavailable(str(exc))
    if earnings <= 0:
        return _unavailable("Fiscale referentie vereist positieve EBITDA.")

    # A rounded anchor is presentation only; never feed it back into ownership.
    fiscal_anchor = earnings * Decimal(4)
    book_equity = resolve_book_equity(balance_sheet)
    if book_equity is None:
        return _unavailable(
            "Fiscale referentie vereist boekhoudkundig eigen vermogen of een volledige balans."
        )
    full_equity = book_equity + fiscal_anchor
    equity = money(full_equity * ownership)
    details = {
        "book_equity": money(book_equity),
        "fiscal_anchor": money(fiscal_anchor),
        "exact_components": {"book_equity": book_equity, "fiscal_anchor": fiscal_anchor},
        "full_company_equity_before_ownership": money(full_equity),
        "ownership_multiplier": ownership,
        "value_basis": "equity_value",
        "reference_purpose": "arithmetic_reference_not_tax_certification",
        "range_basis": {
            "schema_version": "valuation_range_basis.v1",
            "kind": "point_only",
            "empirical_percentiles": False,
            "statistical_coverage": None,
        },
        "description": "Rekenreferentie: eigen vermogen + 4× EBITDA. Fiscale toepasselijkheid vereist een afzonderlijke toets van de peildatum en voorwaarden.",
    }
    if full_equity <= 0:
        return MethodResult(
            value=None,
            equity_value=equity,
            method_key="fiscal_4x",
            label=_LABEL,
            available=False,
            details=details,
            unavailable_reason="Boekhoudkundig eigen vermogen is te negatief voor een positieve fiscale referentiewaarde.",
        )
    return MethodResult(
        value=equity,
        equity_value=equity,
        value_basis="equity_value",
        method_key="fiscal_4x",
        label=_LABEL,
        multiple_used=Decimal(4),
        available=True,
        details=details,
    )
