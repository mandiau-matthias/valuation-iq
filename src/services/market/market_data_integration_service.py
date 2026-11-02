"""
Market Data Integration Service

This service provides integration with market data services and industry
benchmarks, leveraging the current business type catalog from the frontend to
create intelligent decision factors for valuation methodologies.

Features:
1. Industry Benchmarks - Get industry-specific benchmarks for business types
2. Comparable Companies - Find comparable companies for business types
3. Market Context - Get market context and economic indicators
4. Business Type Adjustments - Apply business type specific adjustments
5. Market Data Quality - Assess market data quality and availability

BRAIN & MUSCLE ARCHITECTURE:
When STATELESS_MODE=true, market data should come from Titan via payload.
This service will raise StatelessModeError when database access is attempted
in stateless mode. Use Titan's enrichment for market data.

Author: Upswitch CTO Team
Date: October 2025
Status: Production Ready (Brain & Muscle Architecture)
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union, Protocol
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
from decimal import Decimal

# Database imports - guarded by stateless mode check
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

# Internal imports
from src.config import get_settings
from src.utils.logging import get_logger
from src.utils.exceptions import DataQualityError, MultiplesCalculationError
from src.database.connection import is_stateless_mode, StatelessModeError
from src.domain.models import FinancialData, MarketContext, IndustryCode, BusinessModel
from src.utils.decimal_helpers import to_decimal, from_decimal


class BusinessType(str, Enum):
    """Business type enum for market data integration"""
    SOLE_PROPRIETOR = "sole_proprietor"
    PARTNERSHIP = "partnership"
    LLC = "llc"
    CORPORATION = "corporation"


class IndustryCategory(str, Enum):
    """Industry category enum for market data integration"""
    CONSTRUCTION = "construction"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    SERVICES = "services"
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    OTHER = "other"


class ConversationContext(Protocol):
    """Protocol for conversation context (actual implementation in Titan)"""
    business_type: BusinessType
    industry: IndustryCategory

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class IndustryBenchmarks:
    """Industry benchmarks for business type"""
    industry: str
    region: str
    expected_growth_rate: Decimal
    average_beta: Decimal
    avg_ebitda_margin: Decimal
    median_ev_ebitda: Decimal
    median_ev_revenue: Decimal
    median_pe: Decimal
    data_quality: Decimal
    sample_size: int
    last_updated: datetime


@dataclass
class ComparableCompany:
    """Comparable company data"""
    company_name: str
    industry: str
    business_type: str
    revenue: Decimal
    ebitda: Decimal
    equity_value: Decimal
    ev_ebitda: Decimal
    ev_revenue: Decimal
    pe_ratio: Decimal
    data_quality: Decimal
    similarity_score: Decimal
    last_updated: datetime


@dataclass
class MarketContextData:
    """Market context data"""
    country_code: str
    government_bond_yield: Decimal
    gdp_growth_rate: Decimal
    inflation_rate: Decimal
    market_volatility: Decimal
    economic_indicators: Dict[str, Any]
    sector_performance: Dict[str, Any]
    last_updated: datetime


@dataclass
class BusinessTypeFactors:
    """Business type specific factors"""
    growth_adjustment: Decimal
    beta_adjustment: Decimal
    margin_adjustment: Decimal
    ev_ebitda_adjustment: Decimal
    ev_revenue_adjustment: Decimal
    pe_adjustment: Decimal
    risk_adjustment: Decimal
    market_adjustment: Decimal


class MarketDataIntegrationService:
    """
    Service for integrating market data with business type analysis.
    
    BRAIN & MUSCLE ARCHITECTURE:
    When STATELESS_MODE=true, database access is disabled.
    Market data should come from Titan via request payload enrichment.
    """

    def __init__(self, db: Optional[AsyncSession] = None, market_service=None):
        """
        Initialize market data integration service.
        
        BRAIN & MUSCLE: In stateless mode, db should be None.
        Market data comes from Titan via payload.
        
        Raises:
            StatelessModeError: If db is provided and STATELESS_MODE=true
        """
        # Check for stateless mode
        if is_stateless_mode() and db is not None:
            raise StatelessModeError(
                "MarketDataIntegrationService cannot use database in STATELESS_MODE=true. "
                "Market data should come from Titan via request payload."
            )
            
        self.db = db
        self.market_service = market_service
        self.business_type_factors = self._load_business_type_factors()

        mode = "stateless" if is_stateless_mode() else "stateful"
        logger.info(f"✅ MarketDataIntegrationService initialized (mode={mode})")

    async def get_industry_benchmarks_for_business_type(
        self,
        business_type: str
    ) -> IndustryBenchmarks:
        """Get industry benchmarks for specific business type"""

        try:
            logger.info(f"📊 Getting industry benchmarks for business type: {business_type}")

            # Get business type configuration
            config = await self._get_business_type_config(business_type)

            # Get industry benchmarks
            benchmarks = await self.market_service.get_industry_benchmarks(
                industry=config.get("industry", "unknown"),
                country_code="BE"
            )

            # Apply business type specific adjustments
            adjusted_benchmarks = self._apply_business_type_adjustments(
                benchmarks, business_type
            )

            return adjusted_benchmarks

        except MultiplesCalculationError as e:
            logger.error(f"❌ Failed to get industry benchmarks: {str(e)}")
            raise

    async def get_comparable_companies_for_business_type(
        self,
        business_type: str,
        financial_data: FinancialData
    ) -> List[ComparableCompany]:
        """Get comparable companies for specific business type"""

        try:
            logger.info(f"🏢 Getting comparable companies for business type: {business_type}")

            # Get business type configuration
            config = await self._get_business_type_config(business_type)

            # Search for comparable companies
            comparables = await self.market_service.search_comparable_companies(
                industry=config.get("industry", "unknown"),
                business_type=business_type,
                revenue_range_min=financial_data.revenue * Decimal('0.5'),
                revenue_range_max=financial_data.revenue * Decimal('2.0')
            )

            # Filter and rank comparables
            filtered_comparables = self._filter_comparable_companies(
                comparables, business_type, financial_data
            )

            return filtered_comparables

        except MultiplesCalculationError as e:
            logger.error(f"❌ Failed to get comparable companies: {str(e)}")
            raise

    async def get_market_context_for_business_type(
        self,
        business_type: str,
        country_code: str = "BE"
    ) -> MarketContextData:
        """Get market context for specific business type"""

        try:
            logger.info(f"🌍 Getting market context for business type: {business_type}")

            # Get general market context
            market_context = await self.market_service.get_market_context(
                country_code=country_code
            )

            # Apply business type specific adjustments
            adjusted_context = self._apply_business_type_market_adjustments(
                market_context, business_type
            )

            return adjusted_context

        except DataQualityError as e:
            logger.error(f"❌ Failed to get market context: {str(e)}")
            raise

    async def assess_market_data_quality(
        self,
        business_type: str
    ) -> Decimal:
        """Assess market data quality for business type"""

        try:
            logger.info(f"🔍 Assessing market data quality for business type: {business_type}")

            # Get business type configuration
            config = await self._get_business_type_config(business_type)

            # Check industry benchmarks availability
            benchmarks_available = await self._check_industry_benchmarks_availability(
                config.get("industry", "unknown")
            )

            # Check comparable companies availability
            comparables_available = await self._check_comparable_companies_availability(
                business_type
            )

            # Check market data freshness
            data_freshness = await self._check_market_data_freshness(
                config.get("industry", "unknown")
            )

            # Calculate overall quality score
            quality_score = self._calculate_market_data_quality_score(
                benchmarks_available, comparables_available, data_freshness
            )

            return quality_score

        except MultiplesCalculationError as e:
            logger.error(f"❌ Failed to assess market data quality: {str(e)}")
            raise

    async def get_business_type_market_analysis(
        self,
        business_type: str,
        financial_data: FinancialData
    ) -> Dict[str, Any]:
        """Get comprehensive market analysis for business type"""

        try:
            logger.info(f"📈 Getting market analysis for business type: {business_type}")

            # Get industry benchmarks
            benchmarks = await self.get_industry_benchmarks_for_business_type(business_type)

            # Get comparable companies
            comparables = await self.get_comparable_companies_for_business_type(
                business_type, financial_data
            )

            # Get market context
            market_context = await self.get_market_context_for_business_type(business_type)

            # Assess market data quality
            data_quality = await self.assess_market_data_quality(business_type)

            # Generate comprehensive analysis
            analysis = {
                "business_type": business_type,
                "industry_benchmarks": {
                    "expected_growth_rate": benchmarks.expected_growth_rate,
                    "average_beta": benchmarks.average_beta,
                    "avg_ebitda_margin": benchmarks.avg_ebitda_margin,
                    "median_ev_ebitda": benchmarks.median_ev_ebitda,
                    "median_ev_revenue": benchmarks.median_ev_revenue,
                    "median_pe": benchmarks.median_pe,
                    "data_quality": benchmarks.data_quality,
                    "sample_size": benchmarks.sample_size
                },
                "comparable_companies": {
                    "count": len(comparables),
                    "avg_revenue": sum(c.revenue for c in comparables) / len(comparables) if comparables else 0,
                    "avg_ebitda": sum(c.ebitda for c in comparables) / len(comparables) if comparables else 0,
                    "avg_ev_ebitda": sum(c.ev_ebitda for c in comparables) / len(comparables) if comparables else 0,
                    "avg_ev_revenue": sum(c.ev_revenue for c in comparables) / len(comparables) if comparables else 0,
                    "avg_pe_ratio": sum(c.pe_ratio for c in comparables) / len(comparables) if comparables else 0,
                    "companies": [
                        {
                            "company_name": c.company_name,
                            "revenue": c.revenue,
                            "ebitda": c.ebitda,
                            "equity_value": c.equity_value,
                            "ev_ebitda": c.ev_ebitda,
                            "ev_revenue": c.ev_revenue,
                            "pe_ratio": c.pe_ratio,
                            "similarity_score": c.similarity_score
                        } for c in comparables
                    ]
                },
                "market_context": {
                    "country_code": market_context.country_code,
                    "government_bond_yield": market_context.government_bond_yield,
                    "gdp_growth_rate": market_context.gdp_growth_rate,
                    "inflation_rate": market_context.inflation_rate,
                    "market_volatility": market_context.market_volatility,
                    "economic_indicators": market_context.economic_indicators,
                    "sector_performance": market_context.sector_performance
                },
                "data_quality": data_quality,
                "analysis_timestamp": datetime.now().isoformat()
            }

            return analysis

        except MultiplesCalculationError as e:
            logger.error(f"❌ Failed to get market analysis: {str(e)}")
            raise

    def _apply_business_type_adjustments(
        self,
        benchmarks: IndustryBenchmarks,
        business_type: str
    ) -> IndustryBenchmarks:
        """Apply business type specific adjustments to benchmarks"""

        # Get business type specific factors
        factors = self._get_business_type_factors(business_type)

        # Apply adjustments
        adjusted_benchmarks = IndustryBenchmarks(
            industry=benchmarks.industry,
            region=benchmarks.region,
            expected_growth_rate=benchmarks.expected_growth_rate * factors.growth_adjustment,
            average_beta=benchmarks.average_beta * factors.beta_adjustment,
            avg_ebitda_margin=benchmarks.avg_ebitda_margin * factors.margin_adjustment,
            median_ev_ebitda=benchmarks.median_ev_ebitda * factors.ev_ebitda_adjustment,
            median_ev_revenue=benchmarks.median_ev_revenue * factors.ev_revenue_adjustment,
            median_pe=benchmarks.median_pe * factors.pe_adjustment,
            data_quality=benchmarks.data_quality * factors.market_adjustment,
            sample_size=benchmarks.sample_size,
            last_updated=benchmarks.last_updated
        )

        return adjusted_benchmarks

    def _apply_business_type_market_adjustments(
        self,
        market_context: MarketContextData,
        business_type: str
    ) -> MarketContextData:
        """Apply business type specific adjustments to market context"""

        # Get business type specific factors
        factors = self._get_business_type_factors(business_type)

        # Apply adjustments
        adjusted_context = MarketContextData(
            country_code=market_context.country_code,
            government_bond_yield=market_context.government_bond_yield * factors.risk_adjustment,
            gdp_growth_rate=market_context.gdp_growth_rate * factors.growth_adjustment,
            inflation_rate=market_context.inflation_rate * factors.market_adjustment,
            market_volatility=market_context.market_volatility * factors.beta_adjustment,
            economic_indicators=market_context.economic_indicators,
            sector_performance=market_context.sector_performance,
            last_updated=market_context.last_updated
        )

        return adjusted_context

    def _filter_comparable_companies(
        self,
        comparables: List[ComparableCompany],
        business_type: str,
        financial_data: FinancialData
    ) -> List[ComparableCompany]:
        """Filter and rank comparable companies"""

        # Filter by business type and industry
        filtered = [
            c for c in comparables
            if c.business_type == business_type or c.industry == self._get_industry_for_business_type(business_type)
        ]

        # Filter by revenue range (50% to 200% of target revenue)
        revenue_min = financial_data.revenue * Decimal('0.5')
        revenue_max = financial_data.revenue * Decimal('2.0')

        filtered = [
            c for c in filtered
            if revenue_min <= c.revenue <= revenue_max
        ]

        # Calculate similarity scores
        for comparable in filtered:
            comparable.similarity_score = self._calculate_similarity_score(
                comparable, financial_data, business_type
            )

        # Sort by similarity score
        filtered.sort(key=lambda x: x.similarity_score, reverse=True)

        # Return top 10 most similar companies
        return filtered[:10]

    def _calculate_similarity_score(
        self,
        comparable: ComparableCompany,
        financial_data: FinancialData,
        business_type: str
    ) -> Decimal:
        """Calculate similarity score for comparable company"""

        # Revenue similarity (40% weight)
        revenue_similarity = Decimal('1.0') - abs(comparable.revenue - financial_data.revenue) / max(comparable.revenue, financial_data.revenue)

        # EBITDA margin similarity (30% weight)
        comparable_margin = comparable.ebitda / comparable.revenue if comparable.revenue > 0 else 0
        target_margin = financial_data.ebitda / financial_data.revenue if financial_data.revenue > 0 else 0
        margin_similarity = Decimal('1.0') - abs(comparable_margin - target_margin) / max(comparable_margin, target_margin, Decimal('0.1'))

        # Business type similarity (20% weight)
        business_type_similarity = Decimal('1.0') if comparable.business_type == business_type else Decimal('0.5')

        # Data quality (10% weight)
        data_quality_score = comparable.data_quality

        # Calculate weighted similarity score
        similarity_score = (
            revenue_similarity * Decimal('0.4') +
            margin_similarity * Decimal('0.3') +
            business_type_similarity * Decimal('0.2') +
            data_quality_score * Decimal('0.1')
        )

        return min(similarity_score, Decimal('1.0'))

    def _calculate_market_data_quality_score(
        self,
        benchmarks_available: bool,
        comparables_available: bool,
        data_freshness: Decimal
    ) -> Decimal:
        """Calculate overall market data quality score"""

        # Base score
        quality_score = Decimal('0.0')

        # Benchmarks availability (40% weight)
        if benchmarks_available:
            quality_score += Decimal('0.4')

        # Comparables availability (40% weight)
        if comparables_available:
            quality_score += Decimal('0.4')

        # Data freshness (20% weight)
        quality_score += data_freshness * Decimal('0.2')

        return min(quality_score, Decimal('1.0'))

    def _get_business_type_factors(self, business_type: str) -> BusinessTypeFactors:
        """Get business type specific factors"""

        # Default factors
        default_factors = BusinessTypeFactors(
            growth_adjustment=Decimal('1.0'),
            beta_adjustment=Decimal('1.0'),
            margin_adjustment=Decimal('1.0'),
            ev_ebitda_adjustment=Decimal('1.0'),
            ev_revenue_adjustment=Decimal('1.0'),
            pe_adjustment=Decimal('1.0'),
            risk_adjustment=Decimal('1.0'),
            market_adjustment=Decimal('1.0')
        )

        # Business type specific factors
        factors_map = {
            # Technology
            "saas": BusinessTypeFactors(Decimal('1.2'), Decimal('1.1'), Decimal('1.3'), Decimal('1.2'), Decimal('1.5'), Decimal('1.3'), Decimal('0.9'), Decimal('1.1')),
            "software-development": BusinessTypeFactors(Decimal('1.1'), Decimal('1.0'), Decimal('1.2'), Decimal('1.1'), Decimal('1.3'), Decimal('1.2'), Decimal('0.95'), Decimal('1.05')),
            "ecommerce": BusinessTypeFactors(Decimal('1.0'), Decimal('1.0'), Decimal('1.0'), Decimal('1.0'), Decimal('1.0'), Decimal('1.0'), Decimal('1.0'), Decimal('1.0')),

            # Food & Beverage
            "restaurant": BusinessTypeFactors(Decimal('0.8'), Decimal('0.9'), Decimal('0.7'), Decimal('0.8'), Decimal('0.6'), Decimal('0.8'), Decimal('1.1'), Decimal('0.9')),
            "brewery": BusinessTypeFactors(Decimal('0.9'), Decimal('0.95'), Decimal('0.8'), Decimal('0.9'), Decimal('0.7'), Decimal('0.9'), Decimal('1.05'), Decimal('0.95')),
            "coffee-shop": BusinessTypeFactors(Decimal('0.7'), Decimal('0.8'), Decimal('0.6'), Decimal('0.7'), Decimal('0.5'), Decimal('0.7'), Decimal('1.2'), Decimal('0.8')),

            # Professional Services
            "consulting": BusinessTypeFactors(Decimal('0.9'), Decimal('0.95'), Decimal('1.1'), Decimal('0.9'), Decimal('0.8'), Decimal('0.9'), Decimal('1.05'), Decimal('0.95')),
            "photography": BusinessTypeFactors(Decimal('0.8'), Decimal('0.9'), Decimal('0.9'), Decimal('0.8'), Decimal('0.7'), Decimal('0.8'), Decimal('1.1'), Decimal('0.9')),
            "legal": BusinessTypeFactors(Decimal('0.95'), Decimal('0.9'), Decimal('1.2'), Decimal('0.95'), Decimal('0.9'), Decimal('0.95'), Decimal('0.95'), Decimal('1.0')),

            # Beauty & Wellness
            "hairstyling": BusinessTypeFactors(Decimal('0.8'), Decimal('0.9'), Decimal('0.8'), Decimal('0.8'), Decimal('0.6'), Decimal('0.8'), Decimal('1.1'), Decimal('0.9')),
            "massage": BusinessTypeFactors(Decimal('0.8'), Decimal('0.9'), Decimal('0.8'), Decimal('0.8'), Decimal('0.6'), Decimal('0.8'), Decimal('1.1'), Decimal('0.9')),

            # Home & Property
            "real-estate": BusinessTypeFactors(Decimal('1.0'), Decimal('0.8'), Decimal('1.1'), Decimal('1.0'), Decimal('1.2'), Decimal('1.0'), Decimal('0.9'), Decimal('1.0')),
            "cleaning": BusinessTypeFactors(Decimal('0.9'), Decimal('0.95'), Decimal('0.9'), Decimal('0.9'), Decimal('0.8'), Decimal('0.9'), Decimal('1.05'), Decimal('0.95')),

            # Transportation
            "delivery": BusinessTypeFactors(Decimal('0.9'), Decimal('1.0'), Decimal('0.8'), Decimal('0.9'), Decimal('0.7'), Decimal('0.9'), Decimal('1.1'), Decimal('0.95')),

            # Financial Services
            "insurance": BusinessTypeFactors(Decimal('1.0'), Decimal('0.8'), Decimal('1.2'), Decimal('1.0'), Decimal('1.1'), Decimal('1.0'), Decimal('0.9'), Decimal('1.0')),

            # Education
            "coaching": BusinessTypeFactors(Decimal('0.9'), Decimal('0.95'), Decimal('0.9'), Decimal('0.9'), Decimal('0.8'), Decimal('0.9'), Decimal('1.05'), Decimal('0.95')),

            # Events
            "event-planning": BusinessTypeFactors(Decimal('0.8'), Decimal('0.9'), Decimal('0.8'), Decimal('0.8'), Decimal('0.6'), Decimal('0.8'), Decimal('1.1'), Decimal('0.9')),

            # Pet Services
            "pet-grooming": BusinessTypeFactors(Decimal('0.8'), Decimal('0.9'), Decimal('0.8'), Decimal('0.8'), Decimal('0.6'), Decimal('0.8'), Decimal('1.1'), Decimal('0.9'))
        }

        return factors_map.get(business_type, default_factors)

    def _get_industry_for_business_type(self, business_type: str) -> str:
        """Get industry for business type"""

        industry_map = {
            "saas": "Technology",
            "software-development": "Technology",
            "ecommerce": "E-commerce",
            "restaurant": "Food & Beverage",
            "brewery": "Food & Beverage",
            "coffee-shop": "Food & Beverage",
            "consulting": "Professional Services",
            "photography": "Creative & Media",
            "legal": "Professional Services",
            "hairstyling": "Beauty & Wellness",
            "massage": "Beauty & Wellness",
            "real-estate": "Real Estate",
            "cleaning": "Home Services",
            "delivery": "Transportation",
            "insurance": "Financial Services",
            "coaching": "Education",
            "event-planning": "Events",
            "pet-grooming": "Pet Services"
        }

        return industry_map.get(business_type, "Unknown")

    async def _get_business_type_config(self, business_type: str) -> Dict[str, Any]:
        """Get business type configuration"""

        # This would typically query the database
        # For now, return a placeholder configuration
        return {
            "business_type": business_type,
            "industry": self._get_industry_for_business_type(business_type),
            "category": "unknown"
        }

    async def _check_industry_benchmarks_availability(self, industry: str) -> bool:
        """Check if industry benchmarks are available"""

        # This would typically query a market data service
        # For now, return a placeholder value
        return True

    async def _check_comparable_companies_availability(self, business_type: str) -> bool:
        """Check if comparable companies are available"""

        # This would typically query a market data service
        # For now, return a placeholder value
        return True

    async def _check_market_data_freshness(self, industry: str) -> Decimal:
        """Check market data freshness"""

        # This would typically query a market data service
        # For now, return a placeholder value
        return Decimal('0.8')

    def _load_business_type_factors(self) -> Dict[str, BusinessTypeFactors]:
        """Load business type factors from configuration"""

        # This would typically load from a configuration file or database
        # For now, return empty dict
        return {}

