"""
Multiples Transparency Tracker

Extracted from MarketMultiplesEngine to follow Single Responsibility Principle.
Handles all transparency tracking for multiples calculations.

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.domain.transparency import DataSource
from src.domain.models import ComparableCompany, IndustryBenchmarks, FinancialData
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MultiplesTransparencyTracker:
    """
    Tracks transparency data for multiples calculations.
    
    Single Responsibility: Transparency tracking only.
    """
    
    def __init__(self, transparency_collector: Optional[Any] = None):
        """
        Initialize transparency tracker.
        
        Args:
            transparency_collector: Optional transparency collector for frontend
        """
        self.transparency_collector = transparency_collector
    
    def track_market_multiples(
        self,
        ebitda_multiple: Optional[Decimal],
        revenue_multiple: Optional[Decimal],
        pe_multiple: Optional[Decimal],
        comparables: List[ComparableCompany],
        industry_benchmarks: Optional[IndustryBenchmarks],
        financial_data: FinancialData
    ) -> None:
        """Track market multiples in transparency collector."""
        if not self.transparency_collector:
            return
        
        self.transparency_collector.add_calculation_step(
            description="Industry Market Multiples",
            formula=(
                f"EV/EBITDA = {float(ebitda_multiple):.2f}x, EV/Revenue = {float(revenue_multiple):.2f}x"
                if ebitda_multiple and revenue_multiple
                else "Multiples retrieved from industry benchmarks"
            ),
            inputs={
                "comparables_count": len(comparables),
                "industry": (
                    industry_benchmarks.industry
                    if industry_benchmarks
                    else "Unknown"
                ),
                "country": (
                    financial_data.country_code
                    if hasattr(financial_data, "country_code")
                    else "Unknown"
                ),
            },
            outputs={
                "ebitda_multiple": float(ebitda_multiple) if ebitda_multiple else None,  # Convert to float only for JSON serialization
                "revenue_multiple": (
                    float(revenue_multiple) if revenue_multiple else None
                ),  # Convert to float only for JSON serialization
                "pe_multiple": float(pe_multiple) if pe_multiple else None,  # Convert to float only for JSON serialization
            },
            explanation="Calculated median market multiples from comparable companies or industry benchmarks. "
            "EV/EBITDA is the primary multiple for profitable companies, while EV/Revenue is used for pre-profit or low-margin businesses.",
        )
    
    def track_data_sources(
        self,
        ebitda_multiple: Optional[Decimal],
        revenue_multiple: Optional[Decimal],
        comparables: List[ComparableCompany]
    ) -> None:
        """Track data sources for industry multiples."""
        if not self.transparency_collector or not hasattr(self.transparency_collector, 'add_data_source'):
            return
        
        if ebitda_multiple:
            self.transparency_collector.add_data_source(
                name="Industry EBITDA Multiple",
                value=float(ebitda_multiple),  # Convert to float only for JSON serialization
                source=DataSource.INDUSTRY_DATABASE,
                confidence=90,
                timestamp=datetime.now(timezone.utc),
            )
        
        if revenue_multiple:
            self.transparency_collector.add_data_source(
                name="Industry Revenue Multiple",
                value=float(revenue_multiple),  # Convert to float only for JSON serialization
                source=DataSource.INDUSTRY_DATABASE,
                confidence=90,
                timestamp=datetime.now(timezone.utc),
            )
        
        if len(comparables) > 0:
            self.transparency_collector.add_data_source(
                name="Comparable Companies",
                value=f"{len(comparables)} companies",
                source=(
                    DataSource.EXTERNAL_API
                    if len(comparables) > 0
                    else DataSource.INDUSTRY_DATABASE
                ),
                confidence=85,
                timestamp=datetime.now(timezone.utc),
            )
    
    def track_comparable_companies(self, comparables: List[ComparableCompany]) -> None:
        """Track top comparable companies."""
        if not self.transparency_collector or not comparables:
            return
        
        for comp in comparables[:10]:  # Top 10 comparable companies
            self.transparency_collector.add_comparable_company(
                name=comp.company_name if hasattr(comp, "company_name") else comp.symbol,
                country=comp.country_code if hasattr(comp, "country_code") else "Unknown",
                revenue=comp.revenue if hasattr(comp, "revenue") else 0,
                ebitda_multiple=(
                    comp.ebitda_multiple if hasattr(comp, "ebitda_multiple") else None
                ),
                revenue_multiple=(
                    comp.revenue_multiple if hasattr(comp, "revenue_multiple") else None
                ),
                similarity_score=(
                    comp.similarity_score if hasattr(comp, "similarity_score") else 85
                ),
                source="KBO Database / FMP API",
            )
    
    def track_enterprise_value_calculation(
        self,
        ev_ebitda_valuation: Optional[Decimal],
        ev_revenue_valuation: Optional[Decimal],
        ebitda_multiple: Optional[Decimal],
        revenue_multiple: Optional[Decimal],
        financial_data: FinancialData
    ) -> None:
        """Track enterprise value calculation in transparency collector."""
        if not self.transparency_collector:
            return
        
        formula_parts = []
        if ev_ebitda_valuation:
            formula_parts.append(
                f"EV(EBITDA) = {financial_data.current_year.ebitda:,.0f} × {ebitda_multiple:.2f} = \u20AC{ev_ebitda_valuation:,.0f}"
            )
        if ev_revenue_valuation:
            formula_parts.append(
                f"EV(Revenue) = {financial_data.current_year.revenue:,.0f} × {revenue_multiple:.2f} = \u20AC{ev_revenue_valuation:,.0f}"
            )
        
        formula_str = (
            " | ".join(formula_parts) if formula_parts else "No valid multiples available"
        )
        
        self.transparency_collector.add_calculation_step(
            description="Enterprise Value from Multiples",
            formula=formula_str,
            inputs={
                "ebitda": float(financial_data.current_year.ebitda) if financial_data.current_year.ebitda else None,  # Convert to float only for JSON serialization
                "ebitda_multiple": float(ebitda_multiple) if ebitda_multiple else None,  # Convert to float only for JSON serialization
                "revenue": float(financial_data.current_year.revenue) if financial_data.current_year.revenue else None,  # Convert to float only for JSON serialization
                "revenue_multiple": (
                    float(revenue_multiple) if revenue_multiple else None
                ),  # Convert to float only for JSON serialization
            },
            outputs={
                "ev_from_ebitda": (
                    float(ev_ebitda_valuation) if ev_ebitda_valuation else None
                ),  # Convert to float only for JSON serialization
                "ev_from_revenue": (
                    float(ev_revenue_valuation) if ev_revenue_valuation else None
                ),  # Convert to float only for JSON serialization
            },
            explanation="Applied industry multiples to company financials. EBITDA multiple is preferred for profitable companies "
            "as it reflects operational profitability. Revenue multiple is used when EBITDA is negative or for early-stage companies.",
        )
    
    def track_adjustments(
        self,
        size_discount: Decimal,
        liquidity_discount: Decimal,
        country_adjustment: Decimal,
        growth_premium: Decimal,
        total_adjustment: Decimal
    ) -> None:
        """Track adjustments calculation."""
        if not self.transparency_collector:
            return
        
        self.transparency_collector.add_calculation_step(
            description="Valuation Adjustments",
            formula=(
                f"Total Adjustment = 1.0 + Size({size_discount:.2%}) + "
                f"Liquidity({liquidity_discount:.2%}) + Country({country_adjustment:.2%}) + "
                f"Growth({growth_premium:.2%}) = {total_adjustment:.2%}"
            ),
            inputs={
                "size_discount": float(size_discount),  # Convert to float only for JSON serialization
                "liquidity_discount": float(liquidity_discount),  # Convert to float only for JSON serialization
                "country_adjustment": float(country_adjustment),  # Convert to float only for JSON serialization
                "growth_premium": float(growth_premium),  # Convert to float only for JSON serialization
            },
            outputs={
                "total_adjustment": float(total_adjustment),  # Convert to float only for JSON serialization
            },
            explanation="Applied standard SME valuation adjustments. Size discount reflects higher risk for smaller companies. "
            "Liquidity discount accounts for private company illiquidity. Country adjustment reflects market risk differences. "
            "Growth premium rewards high-growth companies.",
        )
    
    def track_error(
        self,
        error: Exception,
        financial_data: FinancialData,
        industry_benchmarks: Optional[IndustryBenchmarks],
        comparables: List[ComparableCompany]
    ) -> None:
        """Track error in transparency collector."""
        if not self.transparency_collector:
            return
        
        try:
            self.transparency_collector.add_error_step(
                description="Multiples Valuation Failed",
                error=error,
                inputs={
                    "company": financial_data.company_name,
                    "industry": (
                        industry_benchmarks.industry_name
                        if industry_benchmarks
                        else "Unknown"
                    ),
                    "comparables_count": len(comparables),
                    "revenue": getattr(financial_data.current_year, "revenue", None),
                    "ebitda": getattr(financial_data.current_year, "ebitda", None),
                },
            )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            # Don't fail on transparency tracking errors - log but continue
            logger.debug(f"Transparency tracking error (non-critical): {e}", exc_info=True)

