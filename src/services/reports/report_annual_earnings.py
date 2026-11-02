"""Project current-year earnings separately from a weighted valuation basis."""

from collections.abc import Mapping
from decimal import Decimal, localcontext

from src.utils.decimal_helpers import optional_decimal


def _amount(value: object) -> Decimal | None:
    parsed: Decimal | None = optional_decimal(value)
    if value is not None and parsed is None:
        raise ValueError("sealed annual earnings must contain finite decimal amounts")
    return parsed


def annual_earnings_for_report(metrics: Mapping[str, object], ledger: object) -> dict[str, object]:
    """Read sealed annual facts without relabelling the pricing denominator.

    New runs retain exact current-year amounts in the earnings ledger. Older
    runs fall back to their explicit annual metrics, then the historical single
    EBITDA field. An explicit null never becomes a zero or a weighted amount.
    """
    source = ledger if isinstance(ledger, Mapping) else {}
    reported = _amount(
        source.get("current_reported_ebitda")
        if "current_reported_ebitda" in source
        else metrics.get("reported_ebitda", metrics.get("ebitda"))
    )
    normalized = _amount(
        source.get("current_normalized_ebitda")
        if "current_normalized_ebitda" in source
        else metrics.get("normalized_ebitda", reported)
    )
    with localcontext() as context:
        context.prec = 60
        total = normalized - reported if normalized is not None and reported is not None else None
    return {
        "ebitda": normalized,
        "reported_ebitda": reported,
        "normalized_ebitda": normalized,
        "ebitda_normalized": total is not None and total != Decimal(0),
        "ebitda_normalization_metadata": {
            "reported_ebitda": reported,
            "normalized_ebitda": normalized,
            "total_adjustments": total,
        },
    }


def apply_saved_annual_earnings(context: dict[str, object], ledger: object) -> None:
    """Disclose admitted annual rows and weights without new outlier selection."""
    if not isinstance(ledger, Mapping) or ledger.get("version") != "stateless_earnings_basis_v1":
        return
    source_rows = ledger.get("rows")
    if not isinstance(source_rows, list) or not source_rows:
        return
    rows = []
    with localcontext() as arithmetic:
        arithmetic.prec = 100
        for row in source_rows:
            if not isinstance(row, Mapping):
                raise ValueError("sealed annual earnings require structured rows")
            reported, normalized, weight = (
                _amount(row.get(key)) for key in ("reported_ebitda", "normalized_ebitda", "weight")
            )
            if reported is None or normalized is None or weight is None or not 0 <= weight <= 1:
                raise ValueError("sealed annual earnings require amounts and normalized weights")
            adjustment = normalized - reported
            rows.append(
                {
                    "year": row["fiscal_year"],
                    "reported_ebitda": reported,
                    "normalized_ebitda": normalized,
                    "weight": weight,
                    "has_adjustments": adjustment != 0,
                    "adjustment_total": adjustment,
                    "ebitda_margin": None,
                }
            )
    context.update(
        {
            "multi_year_ebitda": rows,
            "weighted_ebitda_total": _amount(ledger.get("normalized_ebitda")),
            "valuation_basis_ebitda": _amount(ledger.get("normalized_ebitda")),
            "show_ebitda_weighting_footnote": len(rows) > 1,
            "has_custom_historical_ebitda_weighting": len(rows) > 1,
            "suppress_outlier_exclusion": True,
            "earnings_basis_ledger": dict(ledger),
        }
    )
