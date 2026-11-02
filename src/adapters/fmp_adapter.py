from src.utils.exceptions import MultiplesCalculationError

"""
Financial Modeling Prep (FMP) API Adapter

Fetches market data for valuation multiples
- Industry multiples (EV/EBITDA, EV/Revenue, P/E)
- Comparable company data
- Company financials
- Market capitalization data

API Documentation: https://site.financialmodelingprep.com/developer/docs/
"""

from typing import Dict, List, Optional, Any

from src.utils.logging import get_logger

from src.adapters.base_adapter import BaseAdapter, DataNotFoundError, ValidationError
from src.config import get_settings
from decimal import Decimal

logger = get_logger(__name__)
settings = get_settings()


class FMPAdapter(BaseAdapter):
    """
    Financial Modeling Prep API adapter

    Provides access to:
    - Industry multiples (EV/EBITDA, EV/Revenue)
    - Comparable company search
    - Company financials
    - Market data
    
    Architecture (post-refactoring):
    - Can accept pre-fetched market data from Titan API via constructor
    - When external data is provided, uses it instead of making API calls
    - Enables ValuationIQ to run without FMP API key
    """

    # Industry sector mappings
    SECTOR_MAPPINGS = {
        "technology": "Technology",
        "software": "Technology",
        "saas": "Technology",
        "ecommerce": "Consumer Cyclical",
        "retail": "Consumer Cyclical",
        "manufacturing": "Industrials",
        "services": "Consumer Defensive",
        "healthcare": "Healthcare",
        "finance": "Financial Services",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        external_market_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize FMP adapter

        Args:
            api_key: FMP API key (optional if external_market_data provided)
            external_market_data: Pre-fetched market data from Titan API
                Expected format: {
                    "industry_multiples": {...},
                    "economic_indicators": {...},
                    "comparable_companies": [...]
                }
        """
        super().__init__(
            base_url=settings.fmp_base_url,
            api_key=api_key or settings.fmp_api_key,
            timeout=30,
            max_retries=3,
            cache_ttl=settings.market_data_cache_ttl,  # 1 hour
        )

        # Store external market data from Titan
        self._external_market_data = external_market_data
        
        if external_market_data:
            logger.info("FMP adapter initialized with external market data from Titan")
        elif not self.api_key:
            logger.warning("FMP API key not configured - using fallback data")

    def _get_default_headers(self) -> Dict[str, str]:
        """FMP uses API key in query params, not headers"""
        return {
            "User-Agent": f"Upswitch-Valuation-Engine/{settings.app_version}",
            "Accept": "application/json",
        }

    def _add_api_key_param(self, params: Optional[Dict] = None) -> Dict:
        """
        Add API key to query parameters

        FMP requires apikey in query string
        """
        params = params or {}
        if self.api_key:
            params["apikey"] = self.api_key
        return params

    async def get_industry_multiples(
        self,
        sector: str,
        region: str = "EU"
    ) -> Dict[str, Any]:
        """
        Get industry multiples for a sector

        Args:
            sector: Industry sector (e.g., "technology", "manufacturing")
            region: Geographic region

        Returns:
            Dict with industry multiples:
            {
                "sector": "Technology",
                "region": "EU",
                "multiples": {
                    "ev_ebitda_median": 12.5,
                    "ev_ebitda_range": [8.0, 18.0],
                    "ev_revenue_median": 3.5,
                    "ev_revenue_range": [2.0, 6.0],
                    "pe_median": 20.0,
                    "pe_range": [15.0, 30.0]
                },
                "company_count": 150,
                "source": "FMP",
                "retrieved_at": "2025-10-03T12:00:00Z"
            }
        """
        # PRIORITY 1: Use external market data from Titan if available
        if self._external_market_data and self._external_market_data.get("industry_multiples"):
            logger.info("Using external industry multiples from Titan", sector=sector)
            return self._format_external_multiples(
                self._external_market_data["industry_multiples"],
                sector,
                region
            )

        mapped_sector = self.SECTOR_MAPPINGS.get(sector.lower(), "Technology")

        logger.info("Fetching industry multiples", sector=sector, region=region)

        if not self.api_key:
            return self._get_fallback_multiples(sector, region)

        try:
            # FMP endpoint for ratios TTM (Trailing Twelve Months)
            endpoint = "ratios-ttm"
            params = self._add_api_key_param({"sector": mapped_sector})

            response = await self._request("GET", endpoint, params=params)

            if not self.validate_response(response):
                raise ValidationError("Invalid multiples data format")

            # Calculate median multiples from company data
            multiples = self._calculate_sector_multiples(response, sector)

            logger.info("Industry multiples retrieved", sector=sector)

            return multiples

        except MultiplesCalculationError as e:
            logger.error("Failed to fetch industry multiples", error=str(e), sector=sector)
            return self._get_fallback_multiples(sector, region)
    
    def _format_external_multiples(
        self,
        external_data: Dict[str, Any],
        sector: str,
        region: str
    ) -> Dict[str, Any]:
        """
        Format external market data from Titan into the expected structure.
        
        Args:
            external_data: Industry multiples from Titan API
            sector: Industry sector
            region: Geographic region
            
        Returns:
            Formatted multiples dict
        """
        ev_ebitda = external_data.get("ev_ebitda_median")
        ev_ebitda_p25 = external_data.get("ev_ebitda_p25")
        ev_ebitda_p75 = external_data.get("ev_ebitda_p75")
        
        ev_revenue = external_data.get("ev_revenue_median")
        ev_revenue_p25 = external_data.get("ev_revenue_p25")
        ev_revenue_p75 = external_data.get("ev_revenue_p75")
        
        pe = external_data.get("pe_ratio_median")
        pe_p25 = external_data.get("pe_ratio_p25")
        pe_p75 = external_data.get("pe_ratio_p75")
        
        return {
            "sector": sector,
            "region": region,
            "multiples": {
                "ev_ebitda_median": ev_ebitda,
                "ev_ebitda_range": [ev_ebitda_p25, ev_ebitda_p75] if ev_ebitda_p25 and ev_ebitda_p75 else None,
                "ev_revenue_median": ev_revenue,
                "ev_revenue_range": [ev_revenue_p25, ev_revenue_p75] if ev_revenue_p25 and ev_revenue_p75 else None,
                "pe_median": pe,
                "pe_range": [pe_p25, pe_p75] if pe_p25 and pe_p75 else None,
            },
            "company_count": external_data.get("sample_size", 0),
            "source": external_data.get("source", "Titan API"),
            "retrieved_at": external_data.get("last_updated", ""),
            "is_external": True,
        }

    async def find_comparable_companies(
        self,
        sector: str,
        revenue_min: Decimal,
        revenue_max: Decimal,
        country: str = "EU",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find comparable public companies

        Args:
            sector: Industry sector
            revenue_min: Minimum revenue (in EUR)
            revenue_max: Maximum revenue (in EUR)
            country: Country/region filter
            limit: Maximum number of companies to return

        Returns:
            List of comparable companies with key metrics
        """
        # PRIORITY 1: Use external comparable companies from Titan if available
        if self._external_market_data and self._external_market_data.get("comparable_companies"):
            logger.info("Using external comparable companies from Titan", sector=sector)
            return self._format_external_comparables(
                self._external_market_data["comparable_companies"],
                limit
            )

        mapped_sector = self.SECTOR_MAPPINGS.get(sector.lower(), "Technology")

        logger.info(
            "Finding comparable companies",
            sector=sector,
            revenue_range=f"€{revenue_min:,.0f}-€{revenue_max:,.0f}",
            limit=limit
        )

        if not self.api_key:
            return self._get_fallback_comparables(sector)

        try:
            # FMP endpoint for stock screener
            endpoint = "stock-screener"
            params = self._add_api_key_param({
                "sector": mapped_sector,
                "limit": limit * 2,  # Get more then filter
            })

            response = await self._request("GET", endpoint, params=params)

            if not isinstance(response, list):
                raise ValidationError("Expected list of companies")

            # Filter by revenue range and format
            comparables = self._filter_and_format_comparables(
                response,
                revenue_min,
                revenue_max,
                limit
            )

            logger.info("Comparable companies found", count=len(comparables))

            return comparables

        except MultiplesCalculationError as e:
            logger.error("Failed to find comparables", error=str(e))
            return self._get_fallback_comparables(sector)
    
    def _format_external_comparables(
        self,
        external_data: List[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Format external comparable companies from Titan.
        
        Args:
            external_data: List of comparable companies from Titan API
            limit: Maximum number of companies to return
            
        Returns:
            Formatted list of comparable companies
        """
        formatted = []
        for company in external_data[:limit]:
            formatted.append({
                "name": company.get("name", ""),
                "ticker": company.get("symbol", "N/A"),
                "sector": company.get("sector", ""),
                "industry": company.get("industry", ""),
                "revenue": company.get("revenue", 0),
                "ebitda": company.get("ebitda", 0),
                "market_cap": company.get("market_cap", 0),
                "enterprise_value": company.get("enterprise_value", 0),
                "ev_ebitda": company.get("ev_ebitda"),
                "ev_revenue": company.get("ev_revenue"),
                "pe_ratio": company.get("pe_ratio"),
                "country": company.get("country", "EU"),
                "is_external": True,
            })
        return formatted

    def _calculate_sector_multiples(
        self,
        companies_data: List[Dict],
        sector: str
    ) -> Dict[str, Any]:
        """Calculate median multiples from company data"""
        # Placeholder implementation
        # Real implementation would calculate from actual company data
        return self._get_fallback_multiples(sector, "EU")

    def _filter_and_format_comparables(
        self,
        companies: List[Dict],
        revenue_min: Decimal,
        revenue_max: Decimal,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Filter companies by revenue and format response"""
        # Placeholder implementation
        return []

    def _get_fallback_multiples(
        self,
        sector: str,
        region: str
    ) -> Dict[str, Any]:
        """
        Fallback industry multiples based on industry averages

        Source: Historical averages and market research
        """
        # Industry-specific multiples (conservative estimates)
        multiples_by_sector = {
            "technology": {
                "ev_ebitda_median": 12.5,
                "ev_ebitda_range": [8.0, 18.0],
                "ev_revenue_median": 3.5,
                "ev_revenue_range": [2.0, 6.0],
                "pe_median": 22.0,
                "pe_range": [15.0, 32.0],
            },
            "software": {
                "ev_ebitda_median": 15.0,
                "ev_ebitda_range": [10.0, 25.0],
                "ev_revenue_median": 5.0,
                "ev_revenue_range": [3.0, 8.0],
                "pe_median": 28.0,
                "pe_range": [20.0, 40.0],
            },
            "manufacturing": {
                "ev_ebitda_median": 8.5,
                "ev_ebitda_range": [6.0, 12.0],
                "ev_revenue_median": 1.2,
                "ev_revenue_range": [0.8, 1.8],
                "pe_median": 15.0,
                "pe_range": [10.0, 20.0],
            },
            "retail": {
                "ev_ebitda_median": 10.0,
                "ev_ebitda_range": [7.0, 14.0],
                "ev_revenue_median": 0.8,
                "ev_revenue_range": [0.5, 1.2],
                "pe_median": 18.0,
                "pe_range": [12.0, 25.0],
            },
            "services": {
                "ev_ebitda_median": 9.0,
                "ev_ebitda_range": [6.5, 13.0],
                "ev_revenue_median": 1.5,
                "ev_revenue_range": [1.0, 2.5],
                "pe_median": 16.0,
                "pe_range": [12.0, 22.0],
            },
        }

        sector_lower = sector.lower()
        multiples = multiples_by_sector.get(
            sector_lower,
            multiples_by_sector["services"]  # Default to services
        )

        return {
            "sector": sector,
            "region": region,
            "multiples": multiples,
            "company_count": 0,
            "source": "Fallback (Industry Averages)",
            "retrieved_at": settings.app_version,
            "is_fallback": True,
            "note": "Using historical industry averages. Connect FMP API for real-time data."
        }

    def _get_fallback_comparables(self, sector: str) -> List[Dict[str, Any]]:
        """Fallback comparable companies"""
        return [{
            "name": "Sample Company (Placeholder)",
            "ticker": "N/A",
            "sector": sector,
            "revenue": 0,
            "ebitda": 0,
            "market_cap": 0,
            "is_placeholder": True,
            "note": "FMP API key required for real comparable data"
        }]

    async def test_connection(self) -> bool:
        """
        Test connection to FMP API

        Returns:
            True if connection successful
        """
        if not self.api_key:
            logger.warning("FMP API key not configured")
            return False

        try:
            await self.get_industry_multiples("technology")
            logger.info("FMP API connection successful")
            return True
        except MultiplesCalculationError as e:
            logger.error("FMP API connection failed", error=str(e))
            return False

    def validate_response(self, data: Any) -> bool:
        """
        Validate FMP API response

        Args:
            data: Response data to validate

        Returns:
            True if valid
        """
        # FMP can return lists or dicts depending on endpoint
        return isinstance(data, (dict, list))

