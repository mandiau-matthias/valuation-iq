"""Terminal earnings admitted from a reconciled, signed company forecast."""

from decimal import Decimal

from .forecast_admission import require_verified_forecast


def verified_fcff_terminal_ebitda(request: object) -> Decimal | None:
    """Legacy FCFF-only rows have no earnings authority; v1 forecasts do."""
    case = getattr(request, "valuation_case", None)
    if getattr(case, "forecast_evidence", None) is None:
        return None
    forecast = require_verified_forecast(request)
    terminal_ebitda = Decimal(forecast.periods[-1].ebitda)
    if terminal_ebitda <= 0:
        raise ValueError("EXIT_MULTIPLE_REQUIRES_POSITIVE_VERIFIED_TERMINAL_EBITDA")
    return terminal_ebitda
