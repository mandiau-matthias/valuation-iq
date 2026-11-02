from src.utils.exceptions import APIError, DatabaseError, ExternalServiceError

"""
Valuation Routes Types and Shared Utilities

This module defines shared types, utilities, and helper functions
for the valuation API routes refactoring.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.domain.models import (
    FinancialData,
    IndustryBenchmarks,
    MarketContext,
    YearData,
)
from src.domain.asset_based_support import normalize_business_model
from src.domain.market_defaults import resolve_equity_risk_premium
from src.api.schemas import ValuationRequest

logger = get_logger(__name__)


def categorize_valuation(equity_value: Decimal) -> str:
    """
    Categorize valuation size (public aggregated data)

    Args:
        equity_value: Equity value to categorize

    Returns:
        Category string: micro, small, medium, large, or enterprise
    """
    if equity_value < 1_000_000:
        return "micro"
    elif equity_value < 5_000_000:
        return "small"
    elif equity_value < 25_000_000:
        return "medium"
    elif equity_value < 100_000_000:
        return "large"
    else:
        return "enterprise"


def format_market_insights(insights: dict) -> str:
    """
    Format legacy market-insights dictionary into readable text.

    Args:
        insights: Dictionary of deterministic market insights

    Returns:
        Formatted string of insights
    """
    try:
        if isinstance(insights, dict):
            sections = []

            if 'industry_insights' in insights:
                sections.append(f"Industry Insights: {', '.join(insights['industry_insights'])}")

            if 'market_conditions' in insights:
                sections.append(f"Market Conditions: {insights['market_conditions']}")

            if 'valuation_considerations' in insights:
                sections.append(f"Valuation Considerations: {', '.join(insights['valuation_considerations'])}")

            return " | ".join(sections)
        else:
            return str(insights)
    except APIError as e:
        logger.error(f"Error formatting market insights: {e}")
        return "Market insights available but formatting failed"


def format_ai_insights(insights: dict) -> str:
    """Legacy alias for deterministic market-insight formatting."""
    return format_market_insights(insights)


def convert_request_to_domain(request: ValuationRequest) -> FinancialData:
    """
    Convert API request to domain FinancialData model

    Args:
        request: ValuationRequest from API

    Returns:
        FinancialData domain model
    """
    # Convert historical years
    historical_years = [
        YearData(
            year=year.year,
            revenue=year.revenue,
            ebitda=year.ebitda,
            cogs=year.cogs,
            gross_profit=year.gross_profit,
            operating_expenses=year.operating_expenses,
            ebit=year.ebit,
            depreciation=year.depreciation,
            amortization=year.amortization,
            interest_expense=year.interest_expense,
            tax_expense=year.tax_expense,
            net_income=year.net_income,
            total_assets=year.total_assets,
            current_assets=year.current_assets,
            cash=year.cash,
            accounts_receivable=year.accounts_receivable,
            accounts_payable=year.accounts_payable,
            inventory=year.inventory,
            total_liabilities=year.total_liabilities,
            current_liabilities=year.current_liabilities,
            short_term_debt=year.short_term_debt,
            total_debt=year.total_debt,
            total_equity=year.total_equity,
            capex=year.capex,
            nwc_change=year.nwc_change,
            is_forecast=getattr(year, 'is_forecast', False),
        )
        for year in request.historical_years_data
        if not getattr(year, 'is_forecast', False)
    ]

    forecast_years = [
        YearData(
            year=year.year,
            revenue=year.revenue,
            ebitda=year.ebitda,
            cogs=year.cogs,
            gross_profit=year.gross_profit,
            operating_expenses=year.operating_expenses,
            ebit=year.ebit,
            depreciation=year.depreciation,
            amortization=year.amortization,
            interest_expense=year.interest_expense,
            tax_expense=year.tax_expense,
            net_income=year.net_income,
            total_assets=year.total_assets,
            current_assets=year.current_assets,
            cash=year.cash,
            accounts_receivable=year.accounts_receivable,
            accounts_payable=year.accounts_payable,
            inventory=year.inventory,
            total_liabilities=year.total_liabilities,
            current_liabilities=year.current_liabilities,
            short_term_debt=year.short_term_debt,
            total_debt=year.total_debt,
            total_equity=year.total_equity,
            capex=year.capex,
            nwc_change=year.nwc_change,
            is_forecast=True,
        )
        for year in (getattr(request, "forecast_years_data", None) or [])
    ]

    # Convert current year
    current = request.current_year_data
    current_year = YearData(
        year=current.year,
        revenue=current.revenue,
        ebitda=current.ebitda,
        cogs=current.cogs,
        gross_profit=current.gross_profit,
        operating_expenses=current.operating_expenses,
        ebit=current.ebit,
        depreciation=current.depreciation,
        amortization=current.amortization,
        interest_expense=current.interest_expense,
        tax_expense=current.tax_expense,
        net_income=current.net_income,
        total_assets=current.total_assets,
        current_assets=current.current_assets,
        cash=current.cash,
        accounts_receivable=current.accounts_receivable,
        accounts_payable=current.accounts_payable,
        inventory=current.inventory,
        total_liabilities=current.total_liabilities,
        current_liabilities=current.current_liabilities,
        short_term_debt=current.short_term_debt,
        total_debt=current.total_debt,
        total_equity=current.total_equity,
        capex=current.capex,
        nwc_change=current.nwc_change,
        is_forecast=getattr(current, 'is_forecast', False),
    )

    if not historical_years:
        historical_years = [current_year]

    return FinancialData(
        company_id=str(uuid.uuid4()),
        company_name=request.company_name,
        country_code=request.country_code,
        industry=request.industry,
        business_model=normalize_business_model(request.business_model),
        founding_year=request.founding_year,
        historical_years=historical_years,
        current_year=current_year,
        forecast_years=forecast_years,
        number_of_employees=request.number_of_employees,
        number_of_owners=request.number_of_owners,
        recurring_revenue_percentage=request.recurring_revenue_percentage,
        has_complete_financials=True,
    )


def get_industry_benchmarks(industry: str, country_code: str) -> IndustryBenchmarks:
    """
    Get industry benchmarks (will eventually fetch from adapters)

    Args:
        industry: Industry name
        country_code: Country code

    Returns:
        IndustryBenchmarks with defaults or fetched data
    """
    # Industry-specific defaults
    # In production, these would come from FMP adapter or database
    industry_defaults = {
        "technology": {
            "expected_growth_rate": Decimal('0.15'),
            "average_beta": Decimal('1.2'),
            "avg_ebitda_margin": Decimal('0.25'),
            "median_ev_ebitda": Decimal('12.5'),
            "median_ev_revenue": Decimal('3.5'),
            "median_pe": Decimal('22.0'),
        },
        "manufacturing": {
            "expected_growth_rate": Decimal('0.08'),
            "average_beta": Decimal('1.0'),
            "avg_ebitda_margin": Decimal('0.15'),
            "median_ev_ebitda": Decimal('7.0'),
            "median_ev_revenue": Decimal('1.2'),
            "median_pe": Decimal('15.0'),
        },
        "retail": {
            "expected_growth_rate": Decimal('0.10'),
            "average_beta": Decimal('1.1'),
            "avg_ebitda_margin": Decimal('0.12'),
            "median_ev_ebitda": Decimal('8.0'),
            "median_ev_revenue": Decimal('0.8'),
            "median_pe": Decimal('18.0'),
        },
        "services": {
            "expected_growth_rate": Decimal('0.12'),
            "average_beta": Decimal('1.05'),
            "avg_ebitda_margin": Decimal('0.18'),
            "median_ev_ebitda": Decimal('9.0'),
            "median_ev_revenue": Decimal('1.5'),
            "median_pe": Decimal('20.0'),
        },
        "healthcare": {
            "expected_growth_rate": Decimal('0.14'),
            "average_beta": Decimal('0.9'),
            "avg_ebitda_margin": Decimal('0.22'),
            "median_ev_ebitda": Decimal('15.0'),
            "median_ev_revenue": Decimal('4.0'),
            "median_pe": Decimal('25.0'),
        },
    }

    defaults = industry_defaults.get(industry.lower(), industry_defaults["services"])

    # Corporate tax rates by country — kept in sync with dcf_data_adapter.py COUNTRY_DEFAULTS
    # and Titan's tax-rate-by-country.util.ts.
    _TAX_RATE_BY_COUNTRY: dict[str, Decimal] = {
        "BE": Decimal("0.25"),
        "NL": Decimal("0.258"),   # VPB top bracket
        "DE": Decimal("0.30"),
        "FR": Decimal("0.25"),
        "LU": Decimal("0.2494"),
        "GB": Decimal("0.25"),
        "UK": Decimal("0.25"),
        "US": Decimal("0.21"),
        # Nordics (BET-420) — flat statutory CIT, matching COUNTRY_DEFAULTS.
        "DK": Decimal("0.22"),    # Denmark flat CIT 22%
        "FI": Decimal("0.20"),    # Finland flat CIT 20%
        "NO": Decimal("0.22"),    # Norway flat CIT 22%
        "SE": Decimal("0.206"),   # Sweden flat CIT 20.6%
    }
    avg_tax_rate = _TAX_RATE_BY_COUNTRY.get(
        (country_code or "").strip().upper(), Decimal("0.25")
    )

    return IndustryBenchmarks(
        industry=industry,
        region=country_code,
        expected_growth_rate=defaults["expected_growth_rate"],
        average_beta=defaults["average_beta"],
        avg_tax_rate=avg_tax_rate,
        avg_ebitda_margin=defaults["avg_ebitda_margin"],
        avg_capex_to_revenue=Decimal('0.03'),
        median_ev_ebitda=defaults["median_ev_ebitda"],
        median_ev_revenue=defaults["median_ev_revenue"],
        median_pe=defaults["median_pe"],
        data_quality="medium",
    )


async def get_market_context(
    country_code: str,
    government_bond_yield: Optional[Decimal] = None,
    long_term_gdp_growth: Optional[Decimal] = None,
    equity_risk_premium: Optional[Decimal] = None,
    cache_service: Optional[Any] = None,
    economic_context: Optional[Dict[str, Any]] = None,
) -> MarketContext:
    """
    Get market context from Titan-provided data, overrides, or adapters.

    PRIORITY ORDER:
    1. Titan-provided economic_context (from enriched request)
    2. Explicit overrides (government_bond_yield, long_term_gdp_growth)
    3. OECD/ECB API calls with caching (fallback only)
    4. Static defaults (last resort)

    WITH APHRODITE CACHING: 95%+ cache hit rate, <100ms response time

    Args:
        country_code: Country code
        government_bond_yield: Override for government bond yield
        long_term_gdp_growth: Override for GDP growth
        cache_service: Optional cache service for performance optimization
        economic_context: Titan-provided economic context (preferred source)

    Returns:
        MarketContext with economic data
    """
    resolved_erp, _ = resolve_equity_risk_premium(
        country_code=country_code,
        explicit_override=equity_risk_premium,
        economic_context=economic_context,
    )

    economic_context = economic_context or {}
    context_gdp_growth = (
        economic_context.get("gdp_growth_rate")
        if economic_context.get("gdp_growth_rate") is not None
        else economic_context.get("terminal_growth_rate")
    )
    context_inflation = economic_context.get("inflation_rate", 0.025)
    context_risk_free_override = (
        economic_context.get("risk_free_rate")
        if bool(economic_context.get("risk_free_rate_is_override"))
        else None
    )

    # PRIORITY 1: Explicit top-level overrides from the caller
    if government_bond_yield is not None and (
        long_term_gdp_growth is not None or context_gdp_growth is not None
    ):
        logger.info(f"Using explicit overrides for {country_code}")
        return MarketContext(
            country_code=country_code,
            government_bond_yield=government_bond_yield,
            long_term_gdp_growth=Decimal(
                str(
                    long_term_gdp_growth
                    if long_term_gdp_growth is not None
                    else context_gdp_growth
                )
            ),
            inflation_rate=Decimal(str(context_inflation)),
            equity_risk_premium=resolved_erp,
        )

    # PRIORITY 2: Titan-provided risk-free rate only when explicitly marked as override
    if context_risk_free_override is not None and context_gdp_growth is not None:
        logger.info(f"✅ Using Titan economic-context override for {country_code}")
        return MarketContext(
            country_code=country_code,
            government_bond_yield=Decimal(str(context_risk_free_override)),
            long_term_gdp_growth=Decimal(
                str(
                    long_term_gdp_growth
                    if long_term_gdp_growth is not None
                    else context_gdp_growth
                )
            ),
            inflation_rate=Decimal(str(context_inflation)),
            equity_risk_premium=resolved_erp,
        )

    # PRIORITY 3: Fetch from adapters (with Aphrodite caching pattern)
    try:
        from src.adapters.oecd_adapter import OECDAdapter
        from src.adapters.ecb_adapter import ECBAdapter
        from src.services.market.market_cache_service import CacheDataType
        from src.domain.market_defaults import cache_risk_free_rate_snapshot

        oecd_adapter = OECDAdapter()
        ecb_adapter = ECBAdapter()

        # Get economic data with caching (Aphrodite pattern)
        if cache_service:
            # Cache-first approach: 9-15s → <100ms for cached data
            try:
                # GDP Growth (cached for 24h)
                gdp_growth = await cache_service.get_or_fetch(
                    data_type=CacheDataType.ECONOMIC_INDICATORS,
                    primary_key=f"{country_code}_gdp",
                    fetch_function=oecd_adapter.get_gdp_growth,
                    query_params={'country_code': country_code}
                )

                # Inflation Rate (cached for 24h)
                inflation_rate = await cache_service.get_or_fetch(
                    data_type=CacheDataType.ECONOMIC_INDICATORS,
                    primary_key=f"{country_code}_inflation",
                    fetch_function=oecd_adapter.get_inflation_rate,
                    query_params={'country_code': country_code}
                )

                # Risk-Free Rate (cached for 24h)
                risk_free_rate = await cache_service.get_or_fetch(
                    data_type=CacheDataType.ECONOMIC_INDICATORS,
                    primary_key=f"{country_code}_risk_free",
                    fetch_function=ecb_adapter.get_risk_free_rate,
                    query_params={'country': country_code}
                )

                logger.info(f"✅ Market data fetched with cache for {country_code}")
            except DatabaseError as cache_error:
                logger.warning(f"⚠️ Cache failed, fetching directly: {cache_error}")
                # Fallback to direct API calls
                gdp_growth = await oecd_adapter.get_gdp_growth(country_code)
                inflation_rate = await oecd_adapter.get_inflation_rate(country_code)
                risk_free_rate = await ecb_adapter.get_risk_free_rate(country_code)
        else:
            # No cache available - direct API calls (slower)
            gdp_growth = await oecd_adapter.get_gdp_growth(country_code)
            inflation_rate = await oecd_adapter.get_inflation_rate(country_code)
            risk_free_rate = await ecb_adapter.get_risk_free_rate(country_code)

        risk_free_rate_value = risk_free_rate.get("yield") if isinstance(risk_free_rate, dict) else risk_free_rate
        risk_free_rate_source = risk_free_rate.get("source") if isinstance(risk_free_rate, dict) else "adapter_fetch"
        cache_risk_free_rate_snapshot(country_code, risk_free_rate_value, source=f"cached ECB snapshot ({risk_free_rate_source})")

        await oecd_adapter.close_session()
        await ecb_adapter.close_session()

        return MarketContext(
            country_code=country_code,
            government_bond_yield=Decimal(str(risk_free_rate_value)),
            long_term_gdp_growth=Decimal(
                str(
                    long_term_gdp_growth
                    if long_term_gdp_growth is not None
                    else (context_gdp_growth if context_gdp_growth is not None else gdp_growth)
                )
            ),
            inflation_rate=Decimal(
                str(context_inflation if context_inflation is not None else inflation_rate)
            ),
            equity_risk_premium=resolved_erp,
        )
    except Exception as e:
        logger.warning(f"Failed to fetch market data, using defaults: {e}")
        # PRIORITY 4: Fallback to reasonable defaults
        return MarketContext(
            country_code=country_code,
            government_bond_yield=Decimal('0.025'),
            long_term_gdp_growth=Decimal('0.020'),
            inflation_rate=Decimal('0.025'),
            equity_risk_premium=resolved_erp,
        )
