"""Current-year display context for main report aggregation."""

from __future__ import annotations

from src.utils.decimal_helpers import safe_float

JsonMap = dict[str, object]


def build_current_year_data_context(
    *,
    response: object,
    request: object | None = None,
) -> JsonMap | None:
    """Return a float-valued current-year dict for templates."""
    src = getattr(response, "current_year_data", None) or (
        getattr(request, "current_year_data", None) if request is not None else None
    )
    if src is None:
        return None
    return {
        "year": getattr(src, "year", None),
        "revenue": safe_float(getattr(src, "revenue", None)),
        "ebitda": safe_float(getattr(src, "ebitda", None)),
        "net_income": safe_float(getattr(src, "net_income", None)),
        "total_assets": safe_float(getattr(src, "total_assets", None)),
        "total_liabilities": safe_float(getattr(src, "total_liabilities", None)),
        "cash": safe_float(getattr(src, "cash", None)),
    }
