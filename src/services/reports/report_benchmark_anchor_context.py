"""Benchmark anchor backfills for report multiple context."""

from __future__ import annotations

from decimal import Decimal
from typing import TypeAlias

from src.utils.decimal_helpers import safe_decimal_or_zero

JsonMap: TypeAlias = dict[str, object]


def backfill_missing_benchmark_anchor(
    multiple_context: JsonMap,
    *,
    business_type_id: object,
    country_code: str = "BE",
) -> bool:
    """Backfill the raw business-types DB benchmark anchor when extraction missed it."""
    if str(multiple_context.get("metric_type") or "").upper() == "REVENUE":
        return False
    if safe_decimal_or_zero(multiple_context.get("benchmark_multiple_mid")) > 0:
        return False
    if not business_type_id:
        return False

    try:
        from src.database.business_types_repository import get_business_types_repository

        with get_business_types_repository() as repo:
            multiples = repo.get_valuation_multiples(str(business_type_id), country_code)
            metadata = repo.get_business_type(str(business_type_id))
    except Exception:
        return False

    db_anchor = (
        safe_decimal_or_zero(multiples.get("ev_ebitda_multiple"))
        if isinstance(multiples, dict)
        else Decimal("0")
    )
    if db_anchor <= 0:
        return False

    multiple_context["benchmark_multiple_mid"] = db_anchor
    db_p25 = safe_decimal_or_zero(getattr(metadata, "ev_ebitda_multiple_p25", None) or 0)
    db_p75 = safe_decimal_or_zero(getattr(metadata, "ev_ebitda_multiple_p75", None) or 0)
    if Decimal("0") < db_p25 <= db_anchor <= db_p75:
        multiple_context["benchmark_multiple_low"] = db_p25
        multiple_context["benchmark_multiple_high"] = db_p75
    return True
