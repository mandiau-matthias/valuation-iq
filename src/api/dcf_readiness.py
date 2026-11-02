"""DCF admission shared by the legacy and stateless APIs.

``current_year_data`` is the latest *closed* basis fiscal year at the API
boundary (future/current calendar years are rejected by the request schemas).
It is therefore one actual observation for DCF readiness, not a projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Protocol

REQUIRED_DCF_ACTUAL_YEARS = 3


class _DcfYear(Protocol):
    year: int
    revenue: object
    ebitda: object
    free_cash_flow: object
    is_forecast: bool


@dataclass(frozen=True)
class DcfReadiness:
    # Kept under the legacy attribute name for compatibility. The tuple now
    # includes the closed basis fiscal year and therefore represents all
    # admitted actual fiscal years.
    admitted_historical_years: tuple[int, ...]
    explicit_fcff_projection_years: tuple[int, ...]

    @property
    def admitted_actual_years(self) -> tuple[int, ...]:
        return self.admitted_historical_years

    @property
    def missing_actual_years(self) -> int:
        return max(0, REQUIRED_DCF_ACTUAL_YEARS - len(self.admitted_actual_years))

    @property
    def ready(self) -> bool:
        return len(self.admitted_actual_years) >= REQUIRED_DCF_ACTUAL_YEARS or bool(
            self.explicit_fcff_projection_years
        )


def _finite_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def resolve_dcf_readiness(
    *,
    current_year_data: _DcfYear,
    historical_rows: Iterable[_DcfYear],
    forecast_rows: Iterable[_DcfYear],
    dcf_input_mode: str | None,
) -> DcfReadiness:
    current_year = getattr(current_year_data, "year", None)
    admitted: set[int] = set()

    current_revenue = _finite_decimal(getattr(current_year_data, "revenue", None))
    current_ebitda = _finite_decimal(getattr(current_year_data, "ebitda", None))
    if (
        isinstance(current_year, int)
        and not getattr(current_year_data, "is_forecast", False)
        and current_revenue is not None
        and current_revenue > 0
        and current_ebitda is not None
    ):
        admitted.add(current_year)

    for row in historical_rows:
        year = getattr(row, "year", None)
        if not isinstance(year, int):
            continue
        if isinstance(current_year, int) and year >= current_year:
            continue
        if getattr(row, "is_forecast", False):
            continue
        revenue = _finite_decimal(getattr(row, "revenue", None))
        ebitda = _finite_decimal(getattr(row, "ebitda", None))
        if revenue is None or revenue <= 0 or ebitda is None:
            continue
        admitted.add(year)

    projections: set[int] = set()
    if dcf_input_mode == "fcff_only":
        for row in forecast_rows:
            year = getattr(row, "year", None)
            free_cash_flow = _finite_decimal(getattr(row, "free_cash_flow", None))
            if (
                isinstance(year, int)
                and isinstance(current_year, int)
                and year > current_year
                and free_cash_flow is not None
            ):
                projections.add(year)

    return DcfReadiness(
        admitted_historical_years=tuple(sorted(admitted)),
        explicit_fcff_projection_years=tuple(sorted(projections)),
    )


def explicitly_requests_dcf(request: object) -> bool:
    """Return true only for durable user/advisor DCF intent.

    ``use_dcf``/``include_dcf`` are capability switches with legacy defaults;
    their presence is deliberately not treated as an explicit method choice.
    """

    selected_method = str(getattr(request, "selected_method", "") or "").strip().lower()
    if selected_method == "dcf":
        return True

    selected_methods = getattr(request, "selected_methods", None)
    if isinstance(selected_methods, Iterable) and not isinstance(selected_methods, (str, bytes)):
        if any(str(method).strip().lower() == "dcf" for method in selected_methods):
            return True

    if getattr(request, "user_configured_dcf", False):
        return True

    if getattr(request, "dcf_input_mode", None) == "fcff_only":
        return True

    user_weights = getattr(request, "user_weights", None)
    if isinstance(user_weights, Mapping):
        for key, raw_weight in user_weights.items():
            weight = _finite_decimal(raw_weight)
            if "dcf" in str(key).lower() and weight is not None and weight > 0:
                return True

    return str(getattr(request, "methodology", "") or "").strip().upper() == "DCF"


def require_dcf_readiness(readiness: DcfReadiness) -> None:
    if readiness.ready:
        return
    admitted = ", ".join(str(year) for year in readiness.admitted_historical_years) or "none"
    projections = (
        ", ".join(str(year) for year in readiness.explicit_fcff_projection_years) or "none"
    )
    raise ValueError(
        "DCF_NOT_READY: DCF requires three distinct admitted historical fiscal years "
        "including the closed basis fiscal year, or explicit FCFF projections "
        f"(admitted={admitted}; missing={readiness.missing_actual_years}; "
        f"fcff={projections})"
    )
