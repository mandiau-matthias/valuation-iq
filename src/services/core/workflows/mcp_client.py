"""
MCP Client - Stateless Implementation

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
- No database queries (historical data comes from Titan if needed)
- No model/provider integration (AI lives in Titan)
- Sample data generation for testing/benchmarking

For generated narrative, use Titan-owned endpoints.
For historical data, Titan queries the database and passes via payload.

@author UpSwitch CTO Team
@version 2.0.0 - Brain & Muscle Stateless
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from src.config import get_settings
from src.utils.logging import get_logger
from .mcp_types import (
    MCPConfiguration,
    DEFAULT_MCP_CONFIG, SAMPLE_INDUSTRIES, SAMPLE_COUNTRIES,
    INDUSTRY_CHARACTERISTICS,
)

# Pandas for data processing (with fallback)
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

logger = get_logger(__name__)


class MCPClient:
    """
    MCP Client for valuation data processing.

    BRAIN & MUSCLE ARCHITECTURE:
    - No database queries (data comes from request payload)
    - No model/provider integration (AI lives in Titan)
    - Sample data generation for testing and benchmarking
    - Data processing utilities using Pandas

    For generated narrative, use Titan-owned orchestration endpoints.
    For historical data, Titan passes data via the stateless API.
    """

    def __init__(self, config: Optional[MCPConfiguration] = None):
        """Initialize MCP client (stateless mode)."""
        self.config = config or DEFAULT_MCP_CONFIG
        self.settings = get_settings()

        logger.info("MCPClient initialized (stateless mode)",
                   pandas_available=PANDAS_AVAILABLE)

    def process_historical_data(
        self,
        historical_records: List[Dict[str, Any]],
    ) -> Optional["pd.DataFrame"]:
        """
        Process historical valuation data provided via payload.

        BRAIN & MUSCLE: Data comes from Titan (The Brain), not from DB.

        Args:
            historical_records: List of historical valuation records from request

        Returns:
            DataFrame with processed historical data or None
        """
        if not PANDAS_AVAILABLE:
            logger.warning("Pandas not available - cannot process data")
            return None

        if not historical_records:
            logger.debug("No historical records provided")
            return None

        try:
            df = pd.DataFrame(historical_records)
            logger.info("Historical data processed",
                       records=len(df),
                       columns=list(df.columns))
            return df
        except Exception as e:
            logger.error(f"Failed to process historical data: {e}")
            return None

    def create_sample_data(self, n_samples: int = 200) -> Optional["pd.DataFrame"]:
        """
        Create sample valuation data for testing and benchmarking.

        Args:
            n_samples: Number of sample records to generate

        Returns:
            DataFrame with sample valuation data or None
        """
        if not PANDAS_AVAILABLE:
            return None

        logger.info("Creating sample valuation data", n_samples=n_samples)

        try:
            np.random.seed(42)  # Reproducible sample data

            data = []
            for i in range(n_samples):
                industry = np.random.choice(SAMPLE_INDUSTRIES)

                # Get industry characteristics
                industry_config = INDUSTRY_CHARACTERISTICS.get(industry, {
                    'base_multiple': 3.0,
                    'margin': 0.30,
                    'growth_rate_range': (0.0, 0.3)
                })

                base_multiple = industry_config['base_multiple']
                margin = industry_config['margin']
                growth_range = industry_config['growth_rate_range']

                # Generate realistic financial data
                revenue = np.random.lognormal(14, 1.2)  # Mean ~€1.5M
                ebitda = revenue * margin * np.random.uniform(0.8, 1.2)

                # Add variation to multiples
                multiple_variation = np.random.normal(1, 0.2)
                revenue_multiple = base_multiple * multiple_variation
                equity_value = revenue * revenue_multiple

                # Quarterly seasonality (Q4 premium)
                quarter = np.random.randint(1, 5)
                if quarter == 4:
                    equity_value *= 1.12  # Q4 premium

                # Generate additional financial metrics
                total_assets = revenue * np.random.uniform(0.5, 1.5)
                total_debt = revenue * np.random.uniform(0.2, 0.8)
                cash = revenue * np.random.uniform(0.1, 0.3)
                employees = int(revenue / 100000 * np.random.uniform(0.5, 2))
                revenue_growth_rate = np.random.uniform(growth_range[0], growth_range[1])

                data.append({
                    'id': f'val_{i}',
                    'company_name': f'Company_{i}',
                    'industry': industry,
                    'country_code': np.random.choice(SAMPLE_COUNTRIES),
                    'revenue': revenue,
                    'ebitda': ebitda,
                    'equity_value_low': equity_value * 0.85,
                    'equity_value_mid': equity_value,
                    'equity_value_high': equity_value * 1.15,
                    'confidence_score': np.random.uniform(65, 95),
                    'total_assets': total_assets,
                    'total_debt': total_debt,
                    'cash': cash,
                    'employees': employees,
                    'valuation_method': 'synthesized',
                    'created_at': datetime.now() - timedelta(days=np.random.randint(0, 365)),
                    'revenue_growth_rate': revenue_growth_rate
                })

            df = pd.DataFrame(data)
            logger.info("Sample valuation data created",
                       records=len(df),
                       industries=df['industry'].nunique())

            return df

        except Exception as e:
            logger.error(f"Sample data creation failed: {e}")
            return None

    def generate_fallback_insights(
        self,
        industry: Optional[str] = None,
        valuation_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate deterministic market notes for legacy callers.

        BRAIN & MUSCLE: For generated narrative, use Titan-owned endpoints.

        Args:
            industry: Industry code for the valuation
            valuation_data: Current valuation being analyzed

        Returns:
            Fallback insights string
        """
        insights_parts = []
        insights_parts.append("## Valuation Intelligence Report\n")

        # Executive Summary
        insights_parts.append("""
### Executive Summary
Analysis based on historical valuation data patterns.
This report provides insights derived from comparable transactions and market trends.
""")

        # Industry Insights
        if industry:
            insights_parts.append(f"""
### Industry Benchmarking
Your industry ({industry}) analysis shows:
- Industry-specific valuation multiples and trends
- Comparable transaction benchmarks
- Market positioning insights
""")

        # Recommendations
        insights_parts.append("""
### Recommendations
1. Review comparable transactions in your industry for positioning insights
2. Consider market timing - seasonal patterns may affect optimal exit timing
3. Strengthen financial documentation to improve confidence scores
4. Benchmark against premium exits to identify value optimization opportunities
5. Monitor industry trends for strategic positioning opportunities
""")

        return "\n".join(insights_parts)

    def get_client_status(self) -> Dict[str, Any]:
        """Get client status and health."""
        return {
            "mode": "stateless",
            "direct_llm_egress_enabled": False,
            "market_context_available": True,
            "pandas_available": PANDAS_AVAILABLE,
            "config": {
                "enable_mcp": self.config.enable_mcp,
                "max_records": self.config.max_records,
                "min_confidence_score": self.config.min_confidence_score,
            },
            "last_updated": datetime.utcnow().isoformat()
        }
