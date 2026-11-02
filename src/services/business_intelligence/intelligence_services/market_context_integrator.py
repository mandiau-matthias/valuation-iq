"""
Market Context Integrator Service

BANK-GRADE SRP-COMPLIANT: Market context integration ONLY

WHAT: Integrates market data, benchmarks, and comparable companies
WHY: Single responsibility - market context integration
HOW: Retrieves and processes market data for valuation context

SINGLE RESPONSIBILITY: Market context data integration
- Industry benchmarks retrieval
- Market conditions analysis
- Comparable companies identification
- Market adjustments calculation

EXTRACTED FROM: BusinessTypeIntelligenceService (780 lines)
COMPLIANCE: Bank-Grade Excellence Framework - SRP Phase 1
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal

logger = get_logger(__name__)


class MarketAdjustments:
    """Market adjustments for valuation methodology"""
    def __init__(
        self,
        dcf_factor: Decimal,
        multiples_factor: Decimal,
        growth_expectations_factor: Decimal,
        risk_factor: Decimal,
        benchmark_availability_factor: Decimal
    ):
        self.dcf_factor = dcf_factor
        self.multiples_factor = multiples_factor
        self.growth_expectations_factor = growth_expectations_factor
        self.risk_factor = risk_factor
        self.benchmark_availability_factor = benchmark_availability_factor


class MarketContextIntegrator:
    """
    BANK-GRADE SRP-COMPLIANT: Market context integration.
    
    SINGLE RESPONSIBILITY: Integrate market context data ONLY.
    
    This service focuses solely on retrieving and processing market context data
    including industry benchmarks, market conditions, and comparable companies.
    
    Design Pattern: Service Pattern
    - Separates market data logic from business analysis
    - Enables independent testing and caching
    - Allows extending with new market data sources
    
    Responsibilities:
    - Industry benchmark retrieval
    - Market conditions analysis
    - Comparable company identification
    - Market adjustment calculation
    """
    
    def __init__(self):
        """
        Initialize market context integrator.
        
        SRP: Focused on market data integration only
        """
        self.logger = logger
        
        # Market data cache (simple in-memory cache)
        self.benchmark_cache: Dict[str, Any] = {}
        self.comparable_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        self.logger.info("✅ [MARKET-CONTEXT] MarketContextIntegrator initialized (SRP-compliant)")
    
    async def integrate_market_data(
        self,
        industry: str,
        business_type: str,
        business_characteristics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Integrate comprehensive market data.
        
        SRP: Only integrates market data, doesn't make decisions.
        
        Args:
            industry: Industry category
            business_type: Business type identifier
            business_characteristics: Business characteristics for comparison
            
        Returns:
            Dict containing:
            - benchmarks: Industry benchmarks
            - comparable_companies: List of comparable companies
            - market_conditions: Current market conditions
            - data_quality: Quality score of market data
        """
        self.logger.info(
            f"🔍 [MARKET-CONTEXT] Integrating market data",
            extra={
                'industry': industry,
                'business_type': business_type
            }
        )
        
        # Get industry benchmarks
        benchmarks = await self.get_industry_benchmarks(industry)
        
        # Get comparable companies
        comparables = await self.find_comparable_companies(
            business_type,
            industry,
            business_characteristics
        )
        
        # Analyze market conditions
        market_conditions = await self.analyze_market_conditions(industry)
        
        # Calculate data quality
        data_quality = self._calculate_data_quality(benchmarks, comparables)
        
        market_data = {
            'benchmarks': benchmarks,
            'comparable_companies': comparables,
            'market_conditions': market_conditions,
            'data_quality': data_quality,
            'integration_timestamp': datetime.now().isoformat()
        }
        
        self.logger.info(
            f"✅ [MARKET-CONTEXT] Market data integrated",
            extra={
                'benchmarks_count': len(benchmarks),
                'comparables_count': len(comparables),
                'data_quality': float(data_quality)
            }
        )
        
        return market_data
    
    async def get_industry_benchmarks(
        self,
        industry: str
    ) -> Dict[str, Decimal]:
        """
        Get industry-specific benchmarks.
        
        SRP: Only retrieves benchmarks, doesn't analyze or compare.
        
        Args:
            industry: Industry category
            
        Returns:
            Dict containing industry benchmarks:
            - avg_revenue_multiple: Average revenue multiple
            - avg_ebitda_multiple: Average EBITDA multiple
            - avg_growth_rate: Average growth rate
            - avg_margin: Average profit margin
        """
        self.logger.info(
            f"🔍 [MARKET-CONTEXT] Getting industry benchmarks for {industry}",
            extra={'industry': industry}
        )
        
        # Check cache
        if industry in self.benchmark_cache:
            self.logger.info(f"✅ [MARKET-CONTEXT] Benchmarks retrieved from cache")
            return self.benchmark_cache[industry]
        
        # Industry benchmark data (simplified - would come from database)
        benchmark_map = {
            'Technology': {
                'avg_revenue_multiple': Decimal('5.0'),
                'avg_ebitda_multiple': Decimal('12.0'),
                'avg_growth_rate': Decimal('0.25'),
                'avg_margin': Decimal('0.20')
            },
            'Food & Beverage': {
                'avg_revenue_multiple': Decimal('1.5'),
                'avg_ebitda_multiple': Decimal('6.0'),
                'avg_growth_rate': Decimal('0.10'),
                'avg_margin': Decimal('0.15')
            },
            'Professional Services': {
                'avg_revenue_multiple': Decimal('2.0'),
                'avg_ebitda_multiple': Decimal('8.0'),
                'avg_growth_rate': Decimal('0.15'),
                'avg_margin': Decimal('0.25')
            },
            'Health & Medical': {
                'avg_revenue_multiple': Decimal('3.0'),
                'avg_ebitda_multiple': Decimal('10.0'),
                'avg_growth_rate': Decimal('0.12'),
                'avg_margin': Decimal('0.18')
            },
            'Retail & E-commerce': {
                'avg_revenue_multiple': Decimal('2.5'),
                'avg_ebitda_multiple': Decimal('7.0'),
                'avg_growth_rate': Decimal('0.18'),
                'avg_margin': Decimal('0.12')
            }
        }
        
        benchmarks = benchmark_map.get(industry, {
            'avg_revenue_multiple': Decimal('2.0'),
            'avg_ebitda_multiple': Decimal('7.0'),
            'avg_growth_rate': Decimal('0.10'),
            'avg_margin': Decimal('0.15')
        })
        
        # Cache benchmarks
        self.benchmark_cache[industry] = benchmarks
        
        self.logger.info(
            f"✅ [MARKET-CONTEXT] Industry benchmarks retrieved",
            extra={'industry': industry, 'benchmarks': benchmarks}
        )
        
        return benchmarks
    
    async def find_comparable_companies(
        self,
        business_type: str,
        industry: str,
        business_characteristics: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find comparable companies for benchmarking.
        
        SRP: Only finds comparables, doesn't analyze or value them.
        
        Args:
            business_type: Business type identifier
            industry: Industry category
            business_characteristics: Business characteristics for matching
            
        Returns:
            List of comparable company data including:
            - company_name: Name of company
            - revenue: Annual revenue
            - valuation: Last valuation
            - multiple: Valuation multiple used
        """
        self.logger.info(
            f"🔍 [MARKET-CONTEXT] Finding comparable companies",
            extra={
                'business_type': business_type,
                'industry': industry
            }
        )
        
        # Check cache
        cache_key = f"{business_type}:{industry}"
        if cache_key in self.comparable_cache:
            self.logger.info(f"✅ [MARKET-CONTEXT] Comparables retrieved from cache")
            return self.comparable_cache[cache_key]
        
        # Simplified comparable companies (would come from database)
        # In production, this would query actual transaction data
        comparables = []
        
        # Generate sample comparables based on business type
        if business_type in ['saas', 'software', 'b2b_saas']:
            comparables = [
                {
                    'company_name': f'Tech Company A',
                    'revenue': Decimal('500000'),
                    'valuation': Decimal('2500000'),
                    'multiple': Decimal('5.0'),
                    'methodology': 'Multiples'
                },
                {
                    'company_name': f'Tech Company B',
                    'revenue': Decimal('750000'),
                    'valuation': Decimal('4500000'),
                    'multiple': Decimal('6.0'),
                    'methodology': 'Multiples'
                }
            ]
        elif business_type in ['restaurant', 'catering', 'bakery']:
            comparables = [
                {
                    'company_name': f'F&B Company A',
                    'revenue': Decimal('300000'),
                    'valuation': Decimal('450000'),
                    'multiple': Decimal('1.5'),
                    'methodology': 'Multiples'
                }
            ]
        
        # Cache comparables
        self.comparable_cache[cache_key] = comparables
        
        self.logger.info(
            f"✅ [MARKET-CONTEXT] Found {len(comparables)} comparable companies",
            extra={'count': len(comparables)}
        )
        
        return comparables
    
    async def analyze_market_conditions(
        self,
        industry: str
    ) -> Dict[str, Any]:
        """
        Analyze current market conditions.
        
        SRP: Only analyzes market conditions, doesn't make decisions.
        
        Args:
            industry: Industry category
            
        Returns:
            Dict containing:
            - expected_growth_rate: Expected industry growth
            - average_beta: Average market risk (beta)
            - market_sentiment: Current sentiment (Positive/Neutral/Negative)
            - volatility: Market volatility score
        """
        self.logger.info(
            f"🔍 [MARKET-CONTEXT] Analyzing market conditions for {industry}",
            extra={'industry': industry}
        )
        
        # Simplified market conditions (would come from external APIs)
        market_conditions = {
            'expected_growth_rate': Decimal('0.05'),  # 5% default growth
            'average_beta': Decimal('1.0'),  # Market average
            'market_sentiment': 'Neutral',
            'volatility': Decimal('0.15'),  # 15% volatility
            'analysis_date': datetime.now().isoformat()
        }
        
        # Industry-specific adjustments
        if industry == 'Technology':
            market_conditions['expected_growth_rate'] = Decimal('0.15')
            market_conditions['volatility'] = Decimal('0.25')
        elif industry == 'Food & Beverage':
            market_conditions['expected_growth_rate'] = Decimal('0.08')
            market_conditions['volatility'] = Decimal('0.10')
        
        self.logger.info(
            f"✅ [MARKET-CONTEXT] Market conditions analyzed",
            extra={'conditions': market_conditions}
        )
        
        return market_conditions
    
    def calculate_market_adjustments(
        self,
        market_context: Dict[str, Any],
        historical_analysis: Optional[Any] = None
    ) -> MarketAdjustments:
        """
        Calculate market context adjustments for methodology selection.
        
        SRP: Only calculates adjustments, doesn't make methodology decision.
        
        Args:
            market_context: Market context data
            historical_analysis: Historical data analysis (optional)
            
        Returns:
            MarketAdjustments object with adjustment factors
        """
        self.logger.info(
            "🔍 [MARKET-CONTEXT] Calculating market adjustments",
            extra={'market_context_keys': list(market_context.keys())}
        )
        
        # DCF adjustments
        dcf_factor = Decimal('1.0')
        
        # Higher growth expectations favor DCF
        expected_growth = market_context.get("expected_growth_rate", Decimal('0.05'))
        if expected_growth > Decimal('0.1'):
            dcf_factor *= Decimal('1.2')
        elif expected_growth > Decimal('0.05'):
            dcf_factor *= Decimal('1.1')
        
        # Lower risk (beta) favors DCF
        beta = market_context.get("average_beta", Decimal('1.0'))
        if beta < Decimal('1.0'):
            dcf_factor *= Decimal('1.1')
        
        # Multiples adjustments
        multiples_factor = Decimal('1.0')
        
        # More industry benchmarks favor multiples
        if historical_analysis and hasattr(historical_analysis, 'industry_benchmarks_available'):
            if historical_analysis.industry_benchmarks_available:
                multiples_factor *= Decimal('1.3')
        
        # Better market data quality favors multiples
        if historical_analysis and hasattr(historical_analysis, 'market_data_quality'):
            market_quality = historical_analysis.market_data_quality
            if market_quality > Decimal('0.8'):
                multiples_factor *= Decimal('1.2')
            elif market_quality > Decimal('0.6'):
                multiples_factor *= Decimal('1.1')
        
        adjustments = MarketAdjustments(
            dcf_factor=dcf_factor,
            multiples_factor=multiples_factor,
            growth_expectations_factor=expected_growth * Decimal('10'),
            risk_factor=beta,
            benchmark_availability_factor=Decimal('1.3') if (historical_analysis and hasattr(historical_analysis, 'industry_benchmarks_available') and historical_analysis.industry_benchmarks_available) else Decimal('1.0')
        )
        
        self.logger.info(
            f"✅ [MARKET-CONTEXT] Market adjustments calculated",
            extra={
                'dcf_factor': float(dcf_factor),
                'multiples_factor': float(multiples_factor)
            }
        )
        
        return adjustments
    
    def _calculate_data_quality(
        self,
        benchmarks: Dict[str, Any],
        comparables: List[Dict[str, Any]]
    ) -> Decimal:
        """
        Calculate overall market data quality score.
        
        Args:
            benchmarks: Industry benchmarks
            comparables: Comparable companies
            
        Returns:
            Data quality score (0-1)
        """
        score = Decimal('0.5')  # Base score
        
        # Benchmarks availability
        if benchmarks:
            score += Decimal('0.2')
        
        # Comparables count
        if len(comparables) >= 5:
            score += Decimal('0.3')
        elif len(comparables) >= 2:
            score += Decimal('0.2')
        elif len(comparables) >= 1:
            score += Decimal('0.1')
        
        return min(score, Decimal('1.0'))
    
    def clear_cache(self) -> None:
        """
        Clear market data cache.
        
        SRP: Only cache management, doesn't affect data retrieval logic.
        """
        self.logger.info("🔄 [MARKET-CONTEXT] Clearing market data cache")
        self.benchmark_cache.clear()
        self.comparable_cache.clear()
        self.logger.info("✅ [MARKET-CONTEXT] Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.
        
        Returns:
            Dict containing:
            - service_name: Name of this service
            - responsibility: Single responsibility description
            - cache_size: Current cache sizes
            - status: Operational status
        """
        return {
            'service_name': 'MarketContextIntegrator',
            'responsibility': 'Market context data integration',
            'cache_size': {
                'benchmarks': len(self.benchmark_cache),
                'comparables': len(self.comparable_cache)
            },
            'status': 'operational',
            'srp_compliant': True
        }
