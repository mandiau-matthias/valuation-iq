"""Pure helper calculations for the stateless valuation route."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from src.api.schemas.stateless_api import (
    BusinessTypeCalibration,
    OwnerDependencyInput,
    YearDataStateless,
)
from src.config.country_packs import country_pack
from src.utils.decimal_helpers import float_or_none, safe_float


def convert_year_data(year_data: YearDataStateless) -> dict[str, object]:
    """Convert YearDataStateless to internal dict format."""
    return {
        "year": year_data.year,
        "financial_observations": dict(year_data.financial_observations),
        "revenue": safe_float(year_data.revenue),
        "ebitda": safe_float(year_data.ebitda),
        "cogs": float_or_none(year_data.cogs),
        "operating_expenses": float_or_none(year_data.operating_expenses),
        "ebit": float_or_none(year_data.ebit),
        "depreciation": float_or_none(year_data.depreciation),
        "amortization": float_or_none(year_data.amortization),
        "tax_expense": float_or_none(year_data.tax_expense),
        "capex": float_or_none(year_data.capex),
        "nwc_change": float_or_none(year_data.nwc_change),
        "free_cash_flow": float_or_none(year_data.free_cash_flow),
        "total_assets": float_or_none(year_data.total_assets),
        "current_assets": float_or_none(year_data.current_assets),
        "total_debt": float_or_none(year_data.total_debt),
        "short_term_debt": float_or_none(year_data.short_term_debt),
        "cash": float_or_none(year_data.cash),
        "accounts_receivable": float_or_none(year_data.accounts_receivable),
        "accounts_payable": float_or_none(year_data.accounts_payable),
        "inventory": float_or_none(year_data.inventory),
        "total_liabilities": float_or_none(year_data.total_liabilities),
        "current_liabilities": float_or_none(year_data.current_liabilities),
        "total_equity": float_or_none(year_data.total_equity),
    }


def is_usable_actual_year(year_data: YearDataStateless) -> bool:
    """Return True for any substantive non-forecast historical observation."""
    if getattr(year_data, "is_forecast", False):
        return False
    return not is_placeholder_current_year(year_data)


def filter_usable_actual_years(
    historical_years: Sequence[YearDataStateless],
) -> list[YearDataStateless]:
    """Drop placeholder/non-operating actual rows before stateless calculations."""
    return [year for year in historical_years if is_usable_actual_year(year)]


def is_placeholder_current_year(year_data: YearDataStateless) -> bool:
    """True for a current-year row with no operating figures AND no balance-sheet substance.

    This is the shape an accounting import produces for an open filing year
    before any books exist (revenue 0, EBITDA 0, empty balance sheet) — it must
    not be confused with a legitimate zero-turnover holding, which carries
    total assets + liabilities and is valued asset-based. Historical rows get
    the equivalent treatment via :func:`filter_usable_actual_years`; without
    this check the *current* year is taken at face value and a no-books year
    becomes the valuation basis (EBITDA basis 0, revenue growth -100%).
    """
    # Local imports: stateless_balance_sheet/asset_based_support sit one layer
    # above this pure-helpers module in the import graph elsewhere; importing
    # lazily keeps this module free of import-order coupling.
    from src.domain.asset_based_support import has_sufficient_asset_inputs
    from src.services.reports.stateless_balance_sheet import build_balance_sheet_payload

    # Observed/derived zeros are real closed-period observations. Dropping or
    # re-anchoring them would erase a shutdown/break-even year and inflate the
    # historical earnings basis. Labels without a monetary value are not evidence.
    if any(
        status in {"observed", "derived"} and isinstance(getattr(year_data, field, None), Decimal)
        for field, status in year_data.financial_observations.items()
    ):
        return False

    # An explicit FCFF row is economically populated even if accounting P&L
    # drivers are intentionally zero (the canonical `fcff_only` contract).
    if getattr(year_data, "free_cash_flow", None) is not None:
        return False
    if safe_float(year_data.revenue) > 0:
        return False
    if safe_float(year_data.ebitda) != 0:
        return False
    return not has_sufficient_asset_inputs(build_balance_sheet_payload(year_data))


def maybe_reanchor_placeholder_current_year(
    current_year: YearDataStateless,
    historical_years: Sequence[YearDataStateless],
) -> tuple[YearDataStateless, list[YearDataStateless], dict[str, int] | None]:
    """Re-anchor the valuation basis when the current year is a no-books placeholder.

    M&A practice: when the open filing year has no books yet, the valuation is
    based on the latest CLOSED accounts — not on a zero-filled draft. When
    ``current_year`` is a placeholder and usable closed years exist, promote the
    most recent usable year to be the basis and keep the remaining rows as
    history. Returns ``(current_year, historical_years, reanchor)`` where
    ``reanchor`` is ``None`` when nothing changed, else
    ``{"from_year": <placeholder year>, "to_year": <promoted year>}``.
    """
    if not is_placeholder_current_year(current_year):
        return current_year, list(historical_years), None
    usable = filter_usable_actual_years(historical_years)
    if not usable:
        return current_year, list(historical_years), None
    promoted = max(usable, key=lambda y: y.year)
    remaining = [year for year in historical_years if year is not promoted]
    return promoted, remaining, {"from_year": current_year.year, "to_year": promoted.year}


_SIZE_DISCOUNT_TIERS: tuple[tuple[float, str | None, float], ...] = (
    (250_000, "sme_size_discount_micro", 0.225),
    (500_000, "sme_size_discount_small", 0.15),
    (1_000_000, "sme_size_discount_small", 0.10),
    (2_000_000, "sme_size_discount_small", 0.05),
    (3_000_000, "sme_size_discount_medium", 0.035),
    (10_000_000, "sme_size_discount_medium", 0.025),
    (25_000_000, None, 0.015),
    (50_000_000, None, 0.01),
)


def calculate_size_discount(revenue: float, calibration: BusinessTypeCalibration) -> float:
    """Calculate size discount based on revenue tier.

    9-tier system aligned with Step 5 size discount calculator.
    Database calibration values (micro/small/medium) override defaults when available.
    """
    for revenue_ceiling, calibration_field, default_discount in _SIZE_DISCOUNT_TIERS:
        if revenue < revenue_ceiling:
            if calibration_field is None:
                return default_discount
            calibrated = getattr(calibration, calibration_field)
            return safe_float(calibrated) if calibrated is not None else default_discount
    return 0.0


def calculate_country_adjustment(country_code: str) -> float:
    """Return any separate market-method country adjustment.

    Canonical requests already require a supported CountryPack and a
    country-scoped benchmark. Country risk therefore belongs in that benchmark
    (and in DCF macro inputs), not in an undisclosed blanket haircut. Unknown
    countries fail closed at the request boundary and here as defense in depth.
    """
    code = str(country_code or "").strip().upper()
    if country_pack(code) is None:
        raise ValueError(f"no CountryPack configured for {code!r}")
    return 0.0


def calculate_confidence_score(
    historical_data: Sequence[object],
    calibration: BusinessTypeCalibration,
    data_quality: bool,
) -> int:
    """Calculate overall confidence score."""
    score = 70  # Base score

    # Historical data bonus
    if len(historical_data) >= 3:
        score += 15
    elif len(historical_data) >= 2:
        score += 10
    elif len(historical_data) >= 1:
        score += 5

    # Calibration quality bonus
    if calibration.calibration_quality_score:
        score += int(safe_float(calibration.calibration_quality_score) * 10)

    # Data quality bonus
    if data_quality:
        score += 5

    return min(100, max(0, score))


def score_to_level(score: int) -> str:
    """Convert confidence score to level."""
    if score >= 80:
        return "HIGH"
    elif score >= 60:
        return "MEDIUM"
    else:
        return "LOW"


def generate_valuation_summary(
    company_name: str,
    equity_value_mid: Decimal,
    methodology: str,
    confidence_level: str,
) -> str:
    """Generate human-readable valuation summary."""
    value_formatted = f"€{float(equity_value_mid):,.0f}"
    return (
        f"{company_name} is valued at {value_formatted} using the {methodology} methodology. "
        f"This valuation has {confidence_level.lower()} confidence based on data quality and comparables."
    )


def identify_value_drivers(
    ebitda_margin: float,
    revenue_growth: float,
    calibration: BusinessTypeCalibration,
) -> list[str]:
    """Identify key value drivers."""
    drivers: list[str] = []

    typical_margin = float(calibration.typical_ebitda_margin or 0.15)
    if ebitda_margin > typical_margin * 1.2:
        drivers.append("Above-average profitability")

    if revenue_growth > 0.10:
        drivers.append("Strong revenue growth")

    if calibration.ev_ebitda_median and float(calibration.ev_ebitda_median) > 6:
        drivers.append("Industry commands premium multiples")

    if not drivers:
        drivers.append("Stable business operations")

    return drivers[:5]


def identify_risk_factors(
    owner_dependency: OwnerDependencyInput | None,
    revenue: float,
    ebitda: float,
    historical_years: int,
) -> list[str]:
    """Identify key risk factors."""
    risks: list[str] = []

    if owner_dependency and owner_dependency.overall_dependency_score:
        if owner_dependency.overall_dependency_score >= 60:
            risks.append("High owner dependency")

    if ebitda <= 0:
        risks.append("Negative EBITDA")
    elif revenue > 0 and ebitda / revenue < 0.05:
        risks.append("Low profit margins")

    if historical_years < 2:
        risks.append("Limited historical track record")

    if revenue < 500_000:
        risks.append("Small company size")

    if not risks:
        risks.append("No major risk factors identified")

    return risks[:5]
