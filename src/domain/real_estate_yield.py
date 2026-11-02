"""
Real-estate yield valuation method.

For asset-anchored property entities (vastgoedvennootschap, propco), book
value is the floor and EBITDA-multiples are misleading. The market value
sits at *income capitalisation*: net annual rent divided by an applicable
cap-rate. This module computes that range and produces a result shape
that mirrors the existing valuation methods so the synthesis layer can
consume it without special-casing.

    market_value = net_annual_rent / cap_rate

Cap rates are sourced from regional commercial-real-estate benchmarks
(DTZ Stadim, JLL, Cushman & Wakefield BE prime ranges, smoothed). They
vary by property type and location quality. The module ships with
conservative BE prime + secondary defaults; production seeds in the
business_types DB can override per-sector.

Design parallels ``asset_based_engine``: Decimal-precision throughout,
frozen dataclass result, transparent rationale string, registry of
typical inputs separate from the calculator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Optional


# ============================================================================
# CAP-RATE REGISTRY
# Sources: DTZ Stadim BE Yield Compass 2024, JLL EMEA Capital Markets 2024
# ============================================================================
class PropertyType(str, Enum):
    """Property type taxonomy aligned with BE commercial-real-estate market."""
    OFFICE_PRIME = "office_prime"
    OFFICE_SECONDARY = "office_secondary"
    RETAIL_HIGH_STREET = "retail_high_street"
    RETAIL_OUT_OF_TOWN = "retail_out_of_town"
    INDUSTRIAL_LOGISTICS = "industrial_logistics"
    INDUSTRIAL_LIGHT = "industrial_light"
    RESIDENTIAL = "residential"
    MIXED_USE = "mixed_use"


# Net cap-rate ranges (low = optimistic / hot market, high = conservative).
# Values reflect mid-market BE 2024-2025 benchmarks, smoothed.
# Format: (low_yield, high_yield) — low yield → high market value.
_CAP_RATE_RANGES: dict[PropertyType, tuple[Decimal, Decimal]] = {
    PropertyType.OFFICE_PRIME: (Decimal("0.045"), Decimal("0.060")),
    PropertyType.OFFICE_SECONDARY: (Decimal("0.060"), Decimal("0.080")),
    PropertyType.RETAIL_HIGH_STREET: (Decimal("0.040"), Decimal("0.055")),
    PropertyType.RETAIL_OUT_OF_TOWN: (Decimal("0.055"), Decimal("0.075")),
    PropertyType.INDUSTRIAL_LOGISTICS: (Decimal("0.045"), Decimal("0.060")),
    PropertyType.INDUSTRIAL_LIGHT: (Decimal("0.060"), Decimal("0.080")),
    PropertyType.RESIDENTIAL: (Decimal("0.035"), Decimal("0.050")),
    PropertyType.MIXED_USE: (Decimal("0.050"), Decimal("0.070")),
}

# Default for unknown / mixed property — conservative middle band.
_DEFAULT_CAP_RATE_RANGE: tuple[Decimal, Decimal] = (Decimal("0.055"), Decimal("0.075"))


def cap_rate_range(property_type: Optional[PropertyType]) -> tuple[Decimal, Decimal]:
    """Look up the (low, high) cap-rate range for a property type.

    Returns the conservative default when the type is unknown or None.
    Both values are net yields expressed as decimals (e.g. 0.045 = 4.5%).
    """
    if property_type is None:
        return _DEFAULT_CAP_RATE_RANGE
    return _CAP_RATE_RANGES.get(property_type, _DEFAULT_CAP_RATE_RANGE)


# ============================================================================
# INPUTS / RESULT
# ============================================================================


@dataclass(frozen=True)
class RealEstateYieldInputs:
    """Inputs for the yield valuation. All amounts in EUR.

    ``net_annual_rent`` is rent received minus operating costs (utilities,
    maintenance, property management, insurance — the items that net the
    rental income to the cash-flow available to the property owner). For
    a single-property entity this typically equals
    ``revenue - operating_expenses`` from the P&L.

    ``cap_rate_low`` / ``cap_rate_high`` are optional overrides; when
    omitted, the registry default for ``property_type`` is used. Pass
    explicit values when the data team has seeded a per-business-type
    yield band.

    ``nav_book_value`` is the book equity of the property, used as the
    floor of the valuation range — under-shoots of yield × rent below
    book are typically not realised in a transaction because the seller
    can hold and refinance.
    """

    net_annual_rent: Decimal
    property_type: Optional[PropertyType] = None
    cap_rate_low: Optional[Decimal] = None
    cap_rate_high: Optional[Decimal] = None
    nav_book_value: Optional[Decimal] = None


@dataclass(frozen=True)
class RealEstateYieldResult:
    """Frozen output. Same shape conventions as the rest of the engine."""

    method: str = "real_estate_yield"
    applicable: bool = False
    skip_reason: str = ""

    # Core valuation outputs (all EUR / Decimal).
    enterprise_value_low: Optional[Decimal] = None
    enterprise_value_mid: Optional[Decimal] = None
    enterprise_value_high: Optional[Decimal] = None
    equity_value_low: Optional[Decimal] = None
    equity_value_mid: Optional[Decimal] = None
    equity_value_high: Optional[Decimal] = None

    # Inputs echoed back for transparency.
    net_annual_rent: Optional[Decimal] = None
    cap_rate_low: Optional[Decimal] = None
    cap_rate_high: Optional[Decimal] = None
    property_type: Optional[str] = None
    nav_floor_applied: bool = False

    # Audit string for the report's per-method card.
    rationale: str = ""
    confidence: str = "medium"  # 'high' | 'medium' | 'low'


# ============================================================================
# CALCULATOR
# ============================================================================


def _round_eur(value: Decimal) -> Decimal:
    """Round EUR to whole units. Avoids ¢-level noise in reports."""
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def value_real_estate_by_yield(inputs: RealEstateYieldInputs) -> RealEstateYieldResult:
    """Compute the (low, mid, high) market-value range for a property entity.

    ``net_rent / cap_rate`` runs the income-capitalisation model:
        - lower cap-rate → higher market value (hot market)
        - higher cap-rate → lower market value (conservative / risk-off)

    NAV-floor logic: when the high-end yield-derived value falls below
    book NAV, the result range is anchored at NAV instead. This reflects
    the practical reality that an owner with positive book equity has
    refinancing options that prevent fire-sale pricing in a normal market.
    Only applies when ``nav_book_value`` is provided.
    """
    if inputs.net_annual_rent <= 0:
        return RealEstateYieldResult(
            applicable=False,
            skip_reason="Net annual rent is not positive — yield method requires positive operating cash flow.",
            net_annual_rent=inputs.net_annual_rent,
            confidence="low",
        )

    # Resolve cap-rate range: explicit overrides win, registry default otherwise.
    cap_low: Optional[Decimal] = inputs.cap_rate_low
    cap_high: Optional[Decimal] = inputs.cap_rate_high
    if cap_low is None or cap_high is None:
        registry_low, registry_high = cap_rate_range(inputs.property_type)
        cap_low = cap_low if cap_low is not None else registry_low
        cap_high = cap_high if cap_high is not None else registry_high

    if cap_low <= 0 or cap_high <= 0 or cap_low > cap_high:
        return RealEstateYieldResult(
            applicable=False,
            skip_reason=f"Invalid cap-rate range: ({cap_low}, {cap_high}).",
            net_annual_rent=inputs.net_annual_rent,
            cap_rate_low=cap_low,
            cap_rate_high=cap_high,
            confidence="low",
        )

    # Lower yield → higher value, so swap the divisors.
    value_high = inputs.net_annual_rent / cap_low
    value_low = inputs.net_annual_rent / cap_high
    value_mid = (value_low + value_high) / Decimal("2")

    # NAV floor — only raises the range, never lowers it.
    nav_floor_applied = False
    if inputs.nav_book_value is not None and inputs.nav_book_value > 0:
        if value_low < inputs.nav_book_value:
            value_low = inputs.nav_book_value
            nav_floor_applied = True
        if value_mid < inputs.nav_book_value:
            value_mid = inputs.nav_book_value
            nav_floor_applied = True
        if value_high < inputs.nav_book_value:
            value_high = inputs.nav_book_value
            nav_floor_applied = True

    rationale = (
        f"Income capitalisation: net annual rent {_round_eur(inputs.net_annual_rent):,} EUR "
        f"capitalised at a {cap_high * 100:.1f}%–{cap_low * 100:.1f}% net yield range "
        f"(higher yield ⇒ lower market value)."
    )
    if nav_floor_applied:
        rationale += " NAV floor applied — yield-derived value would have been below book equity."

    confidence = "high" if inputs.property_type is not None else "medium"

    return RealEstateYieldResult(
        applicable=True,
        enterprise_value_low=_round_eur(value_low),
        enterprise_value_mid=_round_eur(value_mid),
        enterprise_value_high=_round_eur(value_high),
        # For pure property entities EV ≈ equity (no operating debt structure
        # beyond the mortgage, which is captured separately at synthesis time).
        equity_value_low=_round_eur(value_low),
        equity_value_mid=_round_eur(value_mid),
        equity_value_high=_round_eur(value_high),
        net_annual_rent=_round_eur(inputs.net_annual_rent),
        cap_rate_low=cap_low,
        cap_rate_high=cap_high,
        property_type=inputs.property_type.value if inputs.property_type else None,
        nav_floor_applied=nav_floor_applied,
        rationale=rationale,
        confidence=confidence,
    )
