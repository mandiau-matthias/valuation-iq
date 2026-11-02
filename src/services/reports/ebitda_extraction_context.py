"""EBITDA extraction cascade for report aggregation."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TypeAlias, cast

from src.services.reports.ebitda_normalization import (
    current_year_is_ebitda_normalized,
    derive_normalized_ebitda,
    has_explicit_normalization_metadata,
)
from src.services.reports.protocol_adapter import _attr
from src.services.reports.report_bridge_helpers import has_numeric_value
from src.utils.decimal_helpers import optional_decimal, safe_decimal_or_zero, safe_float

ReportMap: TypeAlias = dict[str, object]
EbitdaValues: TypeAlias = tuple[Decimal, Decimal, Decimal]
ZERO = Decimal("0")


@dataclass
class _EbitdaExtractionState:
    sustainable_ebitda: Decimal = ZERO
    reported_ebitda: Decimal = ZERO
    normalized_ebitda: Decimal = ZERO
    sustainable_ebitda_set: bool = False
    reported_ebitda_set: bool = False
    normalized_ebitda_set: bool = False

    def set_sustainable(self, value: Decimal | None) -> None:
        if value is None:
            return
        self.sustainable_ebitda = value
        self.sustainable_ebitda_set = True

    def set_reported(self, value: Decimal, is_set: bool) -> None:
        if not is_set:
            return
        self.reported_ebitda = value
        self.reported_ebitda_set = True

    def set_normalized(self, value: Decimal | None) -> None:
        if value is None:
            return
        self.normalized_ebitda = value
        self.normalized_ebitda_set = True

    def use_basis_for_normalized_and_sustainable(self, value: Decimal | None) -> None:
        self.set_normalized(value)
        self.set_sustainable(value)

    def finalize_normalized_from_sustainable(self) -> None:
        if self.normalized_ebitda_set:
            return
        self.normalized_ebitda = self.sustainable_ebitda

    def as_tuple(self) -> EbitdaValues:
        return self.sustainable_ebitda, self.reported_ebitda, self.normalized_ebitda


@dataclass(frozen=True)
class _CurrentYearNormalization:
    current_year_normalized: Decimal | None
    normalized_ebitda: Decimal | None


def _decimal(value: object) -> Decimal:
    parsed = safe_decimal_or_zero(value)
    if isinstance(parsed, Decimal):
        return parsed
    try:
        return Decimal(str(parsed))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _optional_decimal(value: object) -> Decimal | None:
    parsed = optional_decimal(value)
    return cast(Decimal | None, parsed)


def _current_year_ebitda(container: object) -> object:
    current_year_data = _attr(container, "current_year_data", None)
    return _attr(current_year_data, "ebitda", None)


def _pipeline_ebitda_basis(step_data: ReportMap | None) -> Decimal | None:
    pipeline = (step_data or {}).get("multiple_pipeline")
    if not isinstance(pipeline, dict):
        return None

    metric_type = str(pipeline.get("metric_type", "") or "").upper()
    metric_value = pipeline.get("metric_value")
    if "EBITDA" not in metric_type or not has_numeric_value(metric_value):
        return None
    return _decimal(metric_value)


def _reported_ebitda_from_sources(
    *,
    response: object,
    request: object,
    current_year_metadata: ReportMap,
) -> tuple[Decimal, bool]:
    metadata_reported_ebitda = _optional_decimal(current_year_metadata.get("reported_ebitda"))
    if metadata_reported_ebitda is not None:
        return metadata_reported_ebitda, True

    for container in (request, response):
        current_year_ebitda = _current_year_ebitda(container)
        if current_year_ebitda is not None:
            return _decimal(current_year_ebitda), True
    return ZERO, False


def _current_year_normalization(
    *,
    request: object,
    reported_ebitda: Decimal,
    current_year_metadata: ReportMap,
) -> _CurrentYearNormalization:
    current_year_is_normalized = current_year_is_ebitda_normalized(request)
    current_year_normalized = derive_normalized_ebitda(
        reported_ebitda,
        current_year_metadata,
        current_year_is_normalized,
    )
    if not has_explicit_normalization_metadata(
        current_year_metadata,
        current_year_is_normalized,
    ):
        return _CurrentYearNormalization(current_year_normalized, None)
    if current_year_normalized is not None:
        return _CurrentYearNormalization(current_year_normalized, current_year_normalized)

    request_ebitda = _current_year_ebitda(request)
    normalized_from_request = _decimal(request_ebitda) if request_ebitda is not None else None
    return _CurrentYearNormalization(current_year_normalized, normalized_from_request)


def _normalization_result_ebitda(normalization: ReportMap) -> Decimal | None:
    normalized_value = normalization.get("normalized_ebitda")
    if normalized_value is None:
        normalized_value = normalization.get("sustainable_ebitda")
    return _optional_decimal(normalized_value)


def _request_metadata_basis(
    *,
    request: object,
    current_year_normalized: Decimal | None,
) -> Decimal | None:
    request_ebitda = _current_year_ebitda(request)
    if request_ebitda is None:
        return None
    if current_year_normalized is not None:
        return current_year_normalized
    return _decimal(request_ebitda)


def _response_or_reported_basis(
    *,
    response: object,
    reported_ebitda: Decimal,
    reported_ebitda_set: bool,
) -> Decimal | None:
    response_ebitda = _current_year_ebitda(response)
    if response_ebitda is not None:
        return _decimal(response_ebitda)
    if reported_ebitda_set:
        return reported_ebitda
    return None


def _implied_ebitda_from_multiples(response: object) -> Decimal | None:
    multiples_valuation = _attr(response, "multiples_valuation", None)
    if not multiples_valuation:
        return None

    enterprise_value = (
        _attr(multiples_valuation, "enterprise_value_mid", None)
        or _attr(multiples_valuation, "ev_mid", None)
        or _attr(multiples_valuation, "equity_value_mid", None)
    )
    multiple = _attr(multiples_valuation, "ebitda_multiple", None) or _attr(
        multiples_valuation,
        "ev_ebitda_multiple",
        None,
    )
    if not enterprise_value or not multiple or safe_float(multiple) <= 0:
        return None
    return _decimal(enterprise_value) / _decimal(multiple)


def extract_ebitda_values(
    *,
    response: object,
    request: object,
    step_data: ReportMap | None = None,
    normalization: ReportMap | None = None,
    current_year_metadata: ReportMap | None = None,
) -> EbitdaValues:
    """Extract sustainable, reported, and normalized EBITDA for report context."""
    state = _EbitdaExtractionState()
    normalization = normalization or {}
    current_year_metadata = current_year_metadata or {}

    state.set_sustainable(_pipeline_ebitda_basis(step_data))
    reported_ebitda, reported_ebitda_set = _reported_ebitda_from_sources(
        response=response,
        request=request,
        current_year_metadata=current_year_metadata,
    )
    state.set_reported(reported_ebitda, reported_ebitda_set)

    metadata_normalization = _current_year_normalization(
        request=request,
        reported_ebitda=state.reported_ebitda,
        current_year_metadata=current_year_metadata,
    )
    state.set_normalized(metadata_normalization.normalized_ebitda)

    if not state.normalized_ebitda_set:
        state.set_normalized(_normalization_result_ebitda(normalization))

    if not state.sustainable_ebitda_set:
        if state.normalized_ebitda_set:
            state.set_sustainable(state.normalized_ebitda)
        elif current_year_metadata:
            state.use_basis_for_normalized_and_sustainable(
                _request_metadata_basis(
                    request=request,
                    current_year_normalized=metadata_normalization.current_year_normalized,
                )
            )
        else:
            state.set_sustainable(
                _response_or_reported_basis(
                    response=response,
                    reported_ebitda=state.reported_ebitda,
                    reported_ebitda_set=state.reported_ebitda_set,
                )
            )

    if not state.sustainable_ebitda_set:
        state.set_sustainable(_implied_ebitda_from_multiples(response))

    state.finalize_normalized_from_sustainable()
    return state.as_tuple()
