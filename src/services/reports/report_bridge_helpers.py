"""Pure report helpers for EV-to-equity bridge and localized dates."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, localcontext
from typing import TypeAlias

from src.domain.financial_arithmetic import money
from src.services.infrastructure.translations import normalize_report_locale
from src.services.reports.protocol_adapter import _parse_date
from src.services.reports.report_value_admission import report_decimal

ReportMap: TypeAlias = dict[str, object]

DUTCH_MONTHS = [
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
]

ENGLISH_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

FRENCH_MONTHS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


def has_numeric_value(value: object) -> bool:
    """Return True when a value is present and can be parsed as Decimal."""
    try:
        report_decimal(value, "financial observation")
        return True
    except ValueError:
        return False


def build_bridge_residual_context(
    bridge_residual: Decimal,
    enterprise_value_mid: Decimal | None = None,
) -> ReportMap:
    """Convert a residual Decimal into the template/FE context fields."""
    return {
        "bridge_residual": bridge_residual,
        "bridge_residual_operator": "+" if bridge_residual >= 0 else "−",
        "bridge_residual_amount": bridge_residual.copy_abs(),
        "has_bridge_residual": bridge_residual != Decimal("0"),
    }


def compute_ev_equity_bridge_residual(
    *,
    enterprise_value_mid: Decimal,
    equity_value: Decimal | None,
    net_debt: Decimal,
    tax_latency_net_impact: Decimal,
    balance_sheet_adjustments: list[object],
    nwc_surplus_deficit: Decimal,
) -> Decimal:
    """Compute the EV-to-equity bridge reconciliation residual."""
    if equity_value is None:
        return Decimal("0")  # No equity bridge exists to reconcile.
    with localcontext() as context:
        context.prec = 100
        bs_signed_total = Decimal("0")
        for adjustment in balance_sheet_adjustments:
            if not isinstance(adjustment, dict):
                raise ValueError("Bridge adjustment must contain its amount and direction")
            amount = report_decimal(adjustment.get("amount"), "bridge adjustment amount")
            direction = str(adjustment.get("type") or "add").lower()
            if direction in {"subtract", "deduct", "minus", "negative"}:
                bs_signed_total -= abs(amount)
            elif direction in {"add", "positive"}:
                bs_signed_total += abs(amount)
            else:
                raise ValueError("Bridge adjustment direction is not admitted")
        known_total = (
            enterprise_value_mid
            - net_debt
            + tax_latency_net_impact
            + bs_signed_total
            + nwc_surplus_deficit
        )
        return money(equity_value - known_total)


def format_date_dutch(d: date | None) -> str:
    """Format date in Dutch locale, e.g. '15 januari 2026'."""
    if d is None:
        d = datetime.now().date()
    if isinstance(d, datetime):
        d = d.date()
    try:
        return f"{d.day} {DUTCH_MONTHS[d.month - 1]} {d.year}"
    except (AttributeError, IndexError):
        return str(d)


def format_date_english(d: date | None) -> str:
    """Format date in English locale, e.g. 'January 15, 2026'."""
    if d is None:
        d = datetime.now().date()
    if isinstance(d, datetime):
        d = d.date()
    try:
        return f"{ENGLISH_MONTHS[d.month - 1]} {d.day}, {d.year}"
    except (AttributeError, IndexError):
        return str(d)


def format_date_french(d: date | None) -> str:
    """Format date in Belgian French, e.g. '15 janvier 2026'."""
    if d is None:
        d = datetime.now().date()
    if isinstance(d, datetime):
        d = d.date()
    try:
        return f"{d.day} {FRENCH_MONTHS[d.month - 1]} {d.year}"
    except (AttributeError, IndexError):
        return str(d)


def format_date_localized(d: date | None, locale: str = "nl") -> str:
    """Format a date according to report locale."""
    parsed_date = _parse_date(d) or datetime.now().date()
    report_locale = normalize_report_locale(locale)
    if report_locale == "en":
        return format_date_english(parsed_date)
    if report_locale == "fr":
        return format_date_french(parsed_date)
    return format_date_dutch(parsed_date)
