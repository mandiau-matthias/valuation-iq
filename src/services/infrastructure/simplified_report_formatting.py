"""Formatting helpers for the simplified report transformer."""

import re
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Optional

from src.services.reports.report_value_admission import report_decimal
from src.utils.decimal_helpers import optional_decimal, safe_decimal_or_zero


def format_currency(value: Optional[Decimal], show_decimals: bool = False) -> str:
    """Format a decimal value as currency with European locale."""
    if value is None:
        return "—"

    try:
        amount = report_decimal(value, "display amount")

        if amount >= 1_000_000:
            return f"€{amount / 1_000_000:.2f}M"
        if amount >= 1_000:
            return f"€{amount / 1_000:.0f}K"
        return f"€{amount:,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def format_currency_exact(value: Optional[Decimal]) -> str:
    """Preserve saved cents; HALF_EVEN applies only at the display boundary."""
    if value is None:
        return "—"
    try:
        with localcontext() as ctx:
            ctx.prec = 100
            amount = report_decimal(value, "display amount").quantize(
                Decimal(".01"), rounding=ROUND_HALF_EVEN
            )
            places = 0 if amount == amount.to_integral_value() else 2
            formatted = (
                f"{amount:,.{places}f}".replace(",", "_").replace(".", ",").replace("_", ".")
            )
            return f"€{formatted}"
    except (TypeError, ValueError):
        return "—"


def format_multiple(value: Optional[Decimal], decimals: int = 2) -> str:
    """Format a multiple value."""
    if value is None:
        return "—"
    try:
        return f"{report_decimal(value, 'display multiple'):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


safe_decimal = safe_decimal_or_zero
parse_decimal_or_none = optional_decimal

_UUID_RE_FULL = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_UUID_RE_BARE = re.compile(r"^[0-9a-fA-F]{32}$")


def format_valuation_reference(
    valuation_id: Optional[str],
    valuation_date: object = None,
) -> str:
    """Format a raw UUID into a professional VAL-YYYY-XXXX reference."""
    if not valuation_id or not isinstance(valuation_id, str):
        return ""
    s = valuation_id.strip()
    if not s:
        return ""
    if s.upper().startswith("VAL-"):
        return s
    is_uuid = _UUID_RE_FULL.match(s) or _UUID_RE_BARE.match(s.replace("-", ""))
    if not is_uuid:
        return s
    year = None
    try:
        if hasattr(valuation_date, "year"):
            year = valuation_date.year
        elif isinstance(valuation_date, str) and len(valuation_date) >= 4:
            year = int(valuation_date[:4])
    except (ValueError, TypeError):
        year = None
    if not year:
        year = datetime.now().year
    short = s.replace("-", "")[:4].upper()
    return f"VAL-{year}-{short}"


def format_date_dutch(d: Optional[date]) -> str:
    """Format date in Dutch locale."""
    if d is None:
        return "—"

    months_dutch = [
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

    try:
        return f"{d.day} {months_dutch[d.month - 1]} {d.year}"
    except (AttributeError, IndexError):
        return str(d)
