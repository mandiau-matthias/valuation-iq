"""Helpers for DCF cross-check multiples shown in API/report output."""

from src.utils.decimal_helpers import to_decimal


def resolve_implied_ev_ebitda(
    dcf_result: object | None,
    *,
    has_manual_override: bool,
    ebitda: object | None,
    enterprise_value: object | None,
) -> object | None:
    """Return the EV/EBITDA multiple that matches the displayed enterprise value."""
    implied_ev_ebitda = (
        getattr(dcf_result, "implied_ev_ebitda", None) if dcf_result is not None else None
    )
    if not has_manual_override or ebitda is None:
        return implied_ev_ebitda

    try:
        ebitda_base = to_decimal(ebitda)
        if ebitda_base > 0:
            return to_decimal(enterprise_value) / ebitda_base
    except (ArithmeticError, ValueError, TypeError):
        pass

    return implied_ev_ebitda
