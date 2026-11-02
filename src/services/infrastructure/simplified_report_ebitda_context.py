"""EBITDA extraction helpers for simplified report context assembly."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Optional, Tuple, TypeAlias

from src.api.schemas import ValuationRequest, ValuationResponse
from src.services.infrastructure.simplified_report_formatting import (
    parse_decimal_or_none,
    safe_decimal,
)
from src.services.reports.ebitda_normalization import current_year_normalization_metadata
from src.services.reports.ebitda_normalization import (
    derive_normalized_ebitda as resolve_normalized_ebitda,
)
from src.services.reports.ebitda_normalization import (
    has_explicit_normalization_metadata as has_explicit_ebitda_normalization_metadata,
)
from src.services.reports.ebitda_normalization import normalization_result_from_detailed_results

JsonObject: TypeAlias = Dict[str, object]


def _request_current_year_data(request: Optional[ValuationRequest]) -> object | None:
    return getattr(request, "current_year_data", None) if request else None


def _current_year_is_normalized(request: Optional[ValuationRequest]) -> bool:
    current_year_data = _request_current_year_data(request)
    return bool(getattr(current_year_data, "ebitda_normalized", False))


def _reported_ebitda_from_current_year(
    current_year_data: object | None,
) -> Optional[Decimal]:
    if current_year_data is None or getattr(current_year_data, "ebitda", None) is None:
        return None
    return safe_decimal(getattr(current_year_data, "ebitda"))


def _resolve_reported_ebitda(
    *,
    response: ValuationResponse,
    request: Optional[ValuationRequest],
    current_year_meta: JsonObject,
) -> Optional[Decimal]:
    metadata_reported_ebitda = parse_decimal_or_none(current_year_meta.get("reported_ebitda"))
    if metadata_reported_ebitda is not None:
        return metadata_reported_ebitda

    request_reported_ebitda = _reported_ebitda_from_current_year(
        _request_current_year_data(request)
    )
    if request_reported_ebitda is not None:
        return request_reported_ebitda

    return _reported_ebitda_from_current_year(getattr(response, "current_year_data", None))


def _normalized_ebitda_from_metadata(
    *,
    reported_ebitda: Optional[Decimal],
    current_year_meta: JsonObject,
    current_year_is_normalized: bool,
) -> Optional[Decimal]:
    if not has_explicit_ebitda_normalization_metadata(
        current_year_meta,
        current_year_is_normalized,
    ):
        return None
    return resolve_normalized_ebitda(
        reported_ebitda or Decimal("0"),
        current_year_meta,
        current_year_is_normalized,
    )


def _normalized_ebitda_from_detailed_results(response: ValuationResponse) -> Optional[Decimal]:
    normalization = normalization_result_from_detailed_results(
        getattr(response, "detailed_results", None)
    )
    if not normalization:
        return None
    norm_val = normalization.get("normalized_ebitda")
    if norm_val is None:
        norm_val = normalization.get("sustainable_ebitda")
    return parse_decimal_or_none(norm_val)


def _normalized_ebitda_from_current_year_request(
    *,
    request: Optional[ValuationRequest],
    current_year_is_normalized: bool,
) -> Optional[Decimal]:
    current_year_data = _request_current_year_data(request)
    if (
        not current_year_is_normalized
        or current_year_data is None
        or getattr(current_year_data, "ebitda", None) is None
    ):
        return None
    return safe_decimal(getattr(current_year_data, "ebitda"))


def _finalize_ebitda_values(
    *,
    response: ValuationResponse,
    reported_ebitda: Optional[Decimal],
    normalized_ebitda: Optional[Decimal],
) -> Tuple[Decimal, Optional[Decimal]]:
    if normalized_ebitda is not None:
        sustainable_ebitda = normalized_ebitda
    elif reported_ebitda is not None:
        normalized_ebitda = reported_ebitda
        sustainable_ebitda = reported_ebitda
    else:
        sustainable_ebitda = Decimal("0")

    return sustainable_ebitda, normalized_ebitda


def extract_simplified_ebitda(
    response: ValuationResponse,
    request: Optional[ValuationRequest],
) -> Tuple[Decimal, Optional[Decimal], Optional[Decimal]]:
    """
    Extract simplified report EBITDA values from response/request.

    Returns:
        (sustainable_ebitda, reported_ebitda, normalized_ebitda)
    """
    current_year_meta: JsonObject = current_year_normalization_metadata(request)
    current_year_is_normalized = _current_year_is_normalized(request)
    reported_ebitda = _resolve_reported_ebitda(
        response=response,
        request=request,
        current_year_meta=current_year_meta,
    )
    normalized_ebitda = _normalized_ebitda_from_metadata(
        reported_ebitda=reported_ebitda,
        current_year_meta=current_year_meta,
        current_year_is_normalized=current_year_is_normalized,
    )
    if normalized_ebitda is None:
        normalized_ebitda = _normalized_ebitda_from_detailed_results(response)
    if normalized_ebitda is None:
        normalized_ebitda = _normalized_ebitda_from_current_year_request(
            request=request,
            current_year_is_normalized=current_year_is_normalized,
        )

    sustainable_ebitda, normalized_ebitda = _finalize_ebitda_values(
        response=response,
        reported_ebitda=reported_ebitda,
        normalized_ebitda=normalized_ebitda,
    )
    return sustainable_ebitda, reported_ebitda, normalized_ebitda
