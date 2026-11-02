"""Fiscal EBITDA reference helpers for report builders."""

from collections.abc import Callable
from decimal import Decimal
from typing import TypeAlias, cast

from src.services.reports.fiscal_year_data import latest_closed_fiscal_year_data
from src.services.reports.protocol_adapter import DictWrapper, _attr, _unwrap
from src.services.reports.report_bridge_helpers import has_numeric_value
from src.utils.decimal_helpers import safe_decimal_or_zero

JsonMap: TypeAlias = dict[str, object]
LatestClosedFiscalYearResolver: TypeAlias = Callable[[object | None], object]
NormalizedEbitdaDeriver: TypeAlias = Callable[[Decimal, JsonMap, bool], Decimal]


def _normalization_metadata(year_data: object) -> JsonMap:
    metadata_raw = _attr(year_data, "ebitda_normalization_metadata", None) or {}
    metadata = _unwrap(metadata_raw) if isinstance(metadata_raw, DictWrapper) else metadata_raw
    if not isinstance(metadata, dict):
        return {}
    return cast(JsonMap, metadata)


def fiscal_ebitda(
    request: object | None,
    sustainable_ebitda: Decimal,
    derive_normalized_ebitda: NormalizedEbitdaDeriver,
    latest_closed_fiscal_year_resolver: LatestClosedFiscalYearResolver = latest_closed_fiscal_year_data,
) -> Decimal:
    """Return the EBITDA basis for the Belgian fiscal 4x reference formula."""
    latest_closed = latest_closed_fiscal_year_resolver(request)
    if latest_closed is None:
        return sustainable_ebitda

    metadata = _normalization_metadata(latest_closed)
    # Article 102 uses closed-year statutory earnings. An accepted M&A
    # add-back must not replace an available pre-normalization figure here.
    reported_basis = fiscal_reported_ebitda(request, latest_closed_fiscal_year_resolver)
    if reported_basis is not None:
        return reported_basis

    metadata_normalized = (
        metadata.get("normalized_ebitda")
        if metadata.get("normalized_ebitda") is not None
        else metadata.get("sustainable_ebitda")
    )
    if has_numeric_value(metadata_normalized):
        return cast(Decimal, safe_decimal_or_zero(metadata_normalized))

    reported = metadata.get("reported_ebitda")
    if not has_numeric_value(reported):
        reported = _attr(latest_closed, "reported_ebitda", None)
    if has_numeric_value(reported):
        return cast(Decimal, safe_decimal_or_zero(reported))

    raw_ebitda = _attr(latest_closed, "ebitda", None)
    if has_numeric_value(raw_ebitda):
        raw_value = cast(Decimal, safe_decimal_or_zero(raw_ebitda))
        if _attr(latest_closed, "ebitda_normalized", False):
            return derive_normalized_ebitda(raw_value, metadata, True)
        return raw_value

    return sustainable_ebitda


def fiscal_reported_ebitda(
    request: object | None,
    latest_closed_fiscal_year_resolver: LatestClosedFiscalYearResolver = latest_closed_fiscal_year_data,
) -> Decimal | None:
    """Return statutory EBITDA for the latest closed fiscal year when reconstructable."""
    latest_closed = latest_closed_fiscal_year_resolver(request)
    if latest_closed is None:
        return None

    metadata = _normalization_metadata(latest_closed)
    reported = metadata.get("reported_ebitda")
    if not has_numeric_value(reported):
        reported = _attr(latest_closed, "reported_ebitda", None)
    if has_numeric_value(reported):
        return cast(Decimal, safe_decimal_or_zero(reported))

    raw_ebitda = _attr(latest_closed, "ebitda", None)
    was_normalized = bool(_attr(latest_closed, "ebitda_normalized", False))
    if has_numeric_value(raw_ebitda) and not was_normalized:
        return cast(Decimal, safe_decimal_or_zero(raw_ebitda))

    return None
