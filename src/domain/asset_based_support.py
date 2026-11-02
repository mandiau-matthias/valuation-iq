import logging
from collections.abc import Mapping
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

from src.domain.asset_activity_classification import (
    is_ambiguous_head_office_activity,
    is_asset_heavy_holding_activity,
    is_holding_company_activity,
    is_real_estate_holding_activity,
)
from src.domain.asset_based_engine import AssetBasedEngine
from src.domain.asset_nav_core import ADJUSTED_NAV_LABEL, NAV_DEFAULT_PER_ASSET_TAX_RATES
from src.domain.asset_nav_core import (
    apply_nav_balance_sheet_adjustments as _apply_nav_balance_sheet_adjustments,
)
from src.domain.asset_nav_core import build_available_nav_payload as _build_available_nav_payload
from src.domain.asset_nav_core import build_current_year_data as _build_current_year_data
from src.domain.asset_nav_core import build_nav_details as _build_nav_details
from src.domain.asset_nav_core import calculate_deferred_tax as _calculate_deferred_tax
from src.domain.asset_nav_core import (
    compute_equipment_economic_meerwaarde as _compute_equipment_economic_meerwaarde,
)
from src.domain.asset_nav_core import derive_total_liabilities
from src.domain.asset_nav_core import nav_unavailable_payload as _nav_unavailable_payload
from src.domain.asset_nav_core import off_balance_deduction as _off_balance_deduction
from src.domain.asset_nav_core import (
    ownership_multiplier_or_default as _ownership_multiplier_or_default,
)
from src.domain.asset_nav_core import (
    resolve_adjusted_total_assets as _resolve_adjusted_total_assets,
)
from src.domain.asset_nav_core import (
    resolve_nav_adjustment_context as _resolve_nav_adjustment_context,
)
from src.domain.asset_nav_core import resolve_nav_balance_baseline as _resolve_nav_balance_baseline
from src.domain.asset_nav_core import resolve_nav_equity_values as _resolve_nav_equity_values
from src.domain.asset_nav_core import to_decimal_or_none
from src.domain.models import BusinessModel, FinancialData
from src.utils.fiscal_year import get_current_filing_year

__all__ = [
    "ADJUSTED_NAV_LABEL",
    "NAV_DEFAULT_PER_ASSET_TAX_RATES",
    "_compute_equipment_economic_meerwaarde",
    "book_nav_equity_floor",
    "calculate_adjusted_nav_payload",
    "derive_total_liabilities",
    "has_sufficient_asset_inputs",
    "is_asset_heavy_by_balance_sheet",
    "is_asset_heavy_holding_activity",
    "is_net_asset_dominant",
    "normalize_business_model",
    "to_decimal_or_none",
]


def normalize_business_model(value: Optional[str]) -> BusinessModel:
    raw = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    alias_map = {
        "b2b": BusinessModel.B2B_SAAS,
        "saas": BusinessModel.B2B_SAAS,
        "software": BusinessModel.B2B_SAAS,
        "platform": BusinessModel.B2B_SAAS,
        "subscription": BusinessModel.B2B_SAAS,
        "licensing": BusinessModel.B2B_SAAS,
        "b2c": BusinessModel.B2C,
        "transaction_based": BusinessModel.B2C,
        "advertising": BusinessModel.B2C,
        "marketplace": BusinessModel.MARKETPLACE,
        "ecommerce": BusinessModel.ECOMMERCE,
        "e_commerce": BusinessModel.ECOMMERCE,
        "online_retail": BusinessModel.ECOMMERCE,
        "product_sales": BusinessModel.MANUFACTURING,
        "products": BusinessModel.MANUFACTURING,
        "goods": BusinessModel.MANUFACTURING,
        "manufacturing": BusinessModel.MANUFACTURING,
        "services": BusinessModel.SERVICES,
        "service": BusinessModel.SERVICES,
        "professional_services": BusinessModel.SERVICES,
        "consulting": BusinessModel.SERVICES,
        "hybrid": BusinessModel.SERVICES,
        "other": BusinessModel.OTHER,
    }
    if raw in alias_map:
        return alias_map[raw]
    for candidate in BusinessModel:
        if candidate.value == raw:
            return candidate
    if any(token in raw for token in ("saas", "software", "tech", "platform")):
        return BusinessModel.B2B_SAAS
    if any(token in raw for token in ("ecommerce", "online", "digital")):
        return BusinessModel.ECOMMERCE
    if any(token in raw for token in ("product", "manufacturing", "goods")):
        return BusinessModel.MANUFACTURING
    if any(token in raw for token in ("service", "consulting", "professional")):
        return BusinessModel.SERVICES
    return BusinessModel.OTHER


def has_sufficient_asset_inputs(balance_sheet: Optional[Mapping[str, object]]) -> bool:
    if not balance_sheet:
        return False

    total_assets = to_decimal_or_none(balance_sheet.get("total_assets"))
    if total_assets is None or total_assets <= 0:
        return False

    return derive_total_liabilities(balance_sheet, total_assets) is not None


def is_net_asset_dominant(
    balance_sheet: Optional[Mapping[str, object]],
    current_year_ebitda: Optional[Decimal],
) -> bool:
    """Net-asset-dominance test for the AMBIGUOUS head-office / holding class only.

    Looser than `is_asset_heavy_by_balance_sheet`: it drops the 'fixed assets > 60%
    of total assets' COMPOSITION requirement, so a cash-rich holding (one that has
    just sold a subsidiary and now holds the proceeds) or a participation-rich
    holding whose stakes sit in financial fixed assets is still recognised. Fires
    when book equity ≥ 5× the current-year EBITDA — the net assets dwarf the
    earnings stream, so an operating multiple would understate the entity's value.

    SAFE only because every caller gates it behind
    `is_ambiguous_head_office_activity`: a normal operating company with a fat
    retained-earnings cushion is never NACE 70.10 / tagged 'holding', so it cannot
    reach this test and be misrouted to NAV.

    Book equity is taken via the ACCOUNTING IDENTITY (total_assets − total
    liabilities), NOT the raw `total_equity` field, for two reasons: (1) it is the
    exact equity the downstream Adjusted-NAV valuation reports, so the route and the
    number agree; (2) Hermes' raw equity class-sum understates book equity by the
    unappropriated current-year result ('onverwerkt resultaat' — no 14x rows in an
    annual-accounts trial balance; up to −33% in practice), which would silently
    under-fire this test and misroute a genuine holding to thin operating multiples.
    `derive_total_liabilities` prefers an explicit liabilities figure and only falls
    back to total_equity when that is all that's present."""
    if not balance_sheet:
        return False
    ebitda = to_decimal_or_none(current_year_ebitda)
    if ebitda is None or ebitda <= 0:
        return False
    total_assets = to_decimal_or_none(balance_sheet.get("total_assets"))
    if total_assets is None or total_assets <= 0:
        return False
    total_liabilities = derive_total_liabilities(balance_sheet, total_assets)
    if total_liabilities is None:
        return False
    book_equity = total_assets - total_liabilities
    if book_equity <= 0:
        return False
    return book_equity >= ebitda * Decimal("5")


def book_nav_equity_floor(balance_sheet: Optional[Mapping[str, object]]) -> Optional[Decimal]:
    """Conservative equity NAV floor = book net asset value (total_assets −
    total_liabilities). 'A buyer of the shares will not pay less than the entity's
    book net assets' — the same downside anchor the REAL_ESTATE_YIELD path applies.

    Uses the accounting identity (TA − derived liabilities) so the floor equals the
    equity the Adjusted-NAV valuation would report. Returns None when the balance
    sheet can't yield a POSITIVE book NAV (no floor to apply)."""
    if not balance_sheet:
        return None
    total_assets = to_decimal_or_none(balance_sheet.get("total_assets"))
    if total_assets is None or total_assets <= 0:
        return None
    total_liabilities = derive_total_liabilities(balance_sheet, total_assets)
    if total_liabilities is None:
        return None
    nav = total_assets - total_liabilities
    return nav if nav > 0 else None


def is_asset_heavy_by_balance_sheet(
    balance_sheet: Optional[Mapping[str, object]],
    current_year_ebitda: Optional[Decimal],
) -> bool:
    """Backstop heuristic: when neither NACE nor industry tag flags an entity but
    the balance sheet screams "asset-holding", route to NAV anyway.

    Fires when ALL of:
      - book equity ≥ 5× current-year EBITDA (and book equity > 0)
      - total_assets > 0 (otherwise can't compute ratio)
      - fixed assets / total assets > 60% (asset-heavy by composition)

    Conservative: bails to False the moment a required input is missing.
    Per BET-239 spec — designed for the advisor D2-shaped case where revenue
    is real but tiny next to the underlying real-estate book value."""
    if not balance_sheet:
        return False
    ebitda = to_decimal_or_none(current_year_ebitda)
    if ebitda is None or ebitda <= 0:
        return False

    total_assets = to_decimal_or_none(balance_sheet.get("total_assets"))
    if total_assets is None or total_assets <= 0:
        return False

    book_equity = to_decimal_or_none(balance_sheet.get("total_equity"))
    if book_equity is None:
        total_liabilities = derive_total_liabilities(balance_sheet, total_assets)
        if total_liabilities is None:
            return False
        book_equity = total_assets - total_liabilities
    if book_equity <= 0:
        return False

    if book_equity < ebitda * Decimal("5"):
        return False

    current_assets = to_decimal_or_none(balance_sheet.get("current_assets"))
    if current_assets is None:
        cash = to_decimal_or_none(balance_sheet.get("cash")) or Decimal("0")
        receivables = to_decimal_or_none(balance_sheet.get("accounts_receivable")) or Decimal("0")
        inventory = to_decimal_or_none(balance_sheet.get("inventory")) or Decimal("0")
        if cash == 0 and receivables == 0 and inventory == 0:
            return False
        current_assets = cash + receivables + inventory

    fixed_assets = total_assets - current_assets
    if fixed_assets <= 0:
        return False

    return (fixed_assets / total_assets) > Decimal("0.60")


def _text_or_default(value: str, default: str) -> str:
    return value if value else default


def _int_or_default(value: Optional[int], default: int) -> int:
    return value if value else default


def _resolve_reporting_year(reporting_year: Optional[int]) -> int:
    if reporting_year is not None:
        return reporting_year
    return get_current_filing_year()


def _build_asset_financial_data(
    *,
    company_name: str,
    country_code: str,
    industry: str,
    business_model: Optional[str],
    founding_year: Optional[int],
    current_year,
) -> FinancialData:
    company_name_resolved = _text_or_default(company_name, "Unknown Company")
    return FinancialData(
        company_id=f"asset-{_text_or_default(company_name, 'company')}",
        company_name=company_name_resolved,
        country_code=country_code,
        industry=_text_or_default(industry, "other"),
        business_model=normalize_business_model(business_model),
        founding_year=_int_or_default(founding_year, current_year.year),
        historical_years=[current_year],
        current_year=current_year,
        number_of_owners=1,
        has_complete_financials=True,
    )


def calculate_adjusted_nav_payload(
    *,
    company_name: str,
    industry: str,
    business_model: Optional[str],
    founding_year: Optional[int],
    reporting_year: Optional[int],
    revenue: object,
    ebitda: object,
    ownership_multiplier: Decimal = Decimal("1"),
    country_code: str = "BE",
    balance_sheet: Optional[Mapping[str, object]],
    business_context: Optional[Mapping[str, object]] = None,
) -> dict[str, object]:
    baseline, unavailable_payload = _resolve_nav_balance_baseline(balance_sheet)
    if unavailable_payload is not None:
        return unavailable_payload
    if baseline is None:
        return _nav_unavailable_payload(
            reason="Balansgegevens vereist — totale activa ontbreken.",
            code="NAV_BALANCE_SHEET_MISSING",
        )

    adjusted_balance_sheet = dict(balance_sheet)
    effective_reporting_year = _resolve_reporting_year(reporting_year)
    nav_context = _resolve_nav_adjustment_context(
        business_context,
        reporting_year=effective_reporting_year,
        country_code=country_code,
    )
    _apply_nav_balance_sheet_adjustments(adjusted_balance_sheet, nav_context)

    total_assets, unavailable_payload = _resolve_adjusted_total_assets(adjusted_balance_sheet)
    if unavailable_payload is not None:
        return unavailable_payload
    if total_assets is None:
        return _nav_unavailable_payload(
            reason="Balansgegevens vereist — totale activa moeten positief zijn.",
            code="NAV_ADJUSTED_TOTAL_ASSETS_NON_POSITIVE",
        )

    total_liabilities = baseline.total_liabilities
    ownership_multiplier_decimal = _ownership_multiplier_or_default(ownership_multiplier)

    current_year = _build_current_year_data(
        reporting_year=effective_reporting_year,
        revenue=revenue,
        ebitda=ebitda,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        adjusted_balance_sheet=adjusted_balance_sheet,
    )

    financial_data = _build_asset_financial_data(
        company_name=company_name,
        country_code=country_code,
        industry=industry,
        business_model=business_model,
        founding_year=founding_year,
        current_year=current_year,
    )

    result = AssetBasedEngine(
        financial_data,
        country_code=country_code,
    ).calculate_adjusted_book_value(
        industry=_text_or_default(industry, "other"),
        real_estate_fmv=nav_context.real_estate_adjustment,
        intangible_value=nav_context.hidden_reserves,
        other_revaluations=nav_context.other_revaluations,
    )

    nav_before_deductions = result.net_asset_value
    deferred_tax = _calculate_deferred_tax(nav_context, country_code=country_code)
    off_balance_deduction = _off_balance_deduction(nav_context)
    corrected_nav = nav_before_deductions - deferred_tax.deduction - off_balance_deduction

    equity_values, unavailable_payload = _resolve_nav_equity_values(
        corrected_nav=corrected_nav,
        ownership_multiplier=ownership_multiplier_decimal,
        deferred_tax=deferred_tax,
        off_balance_deduction=off_balance_deduction,
        logger=logger,
    )
    if unavailable_payload is not None:
        return unavailable_payload
    if equity_values is None:
        return _nav_unavailable_payload(
            reason="Gecorrigeerd nettovermogen is niet positief.",
            code="NAV_CORRECTED_EQUITY_NON_POSITIVE",
        )

    details = _build_nav_details(
        result=result,
        nav_context=nav_context,
        adjusted_balance_sheet=adjusted_balance_sheet,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        corrected_nav=corrected_nav,
        nav_before_deductions=nav_before_deductions,
        deferred_tax=deferred_tax,
        off_balance_deduction=off_balance_deduction,
        equity_values=equity_values,
        country_code=country_code,
    )

    return _build_available_nav_payload(
        result=result,
        corrected_nav=corrected_nav,
        equity_values=equity_values,
        details=details,
    )
