
from src.errors.error_types import ValidationError
from src.utils.exceptions import CalculationError, DataQualityError, MultiplesCalculationError

"""
Template-Based Valuation Narrative Generator
Generates valuation explanations using templates (NO AI, NO data exposure)
GDPR compliant - all processing happens locally
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValuationNarrativeGenerator:
    """
    Generate valuation explanations using templates
    NO external AI, NO data exposure, GDPR compliant
    """

    def __init__(self):
        logger.info("✅ ValuationNarrativeGenerator initialized - Local processing only")

    def generate_narrative(
        self, valuation_result: Dict[str, Any], business_data: Dict[str, Any]
    ) -> str:
        """
        Generate narrative using templates and business logic
        ALL processing happens locally - NO external API calls
        """
        try:
            # Select template based on valuation method
            method = valuation_result.get("method", "market_multiple")

            logger.info(
                "Generating narrative",
                method=method,
                has_valuation_data=bool(valuation_result),
                has_business_data=bool(business_data),
            )

            if method == "market_multiple":
                return self._generate_market_multiple_narrative(valuation_result, business_data)
            elif method == "dcf":
                return self._generate_dcf_narrative(valuation_result, business_data)
            elif method == "asset_based":
                return self._generate_asset_based_narrative(valuation_result, business_data)
            else:
                return self._generate_generic_narrative(valuation_result, business_data)

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(
                "Narrative generation failed",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return self._generate_fallback_narrative()
        except MultiplesCalculationError as e:
            logger.error(
                "Unexpected error in narrative generation",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return self._generate_fallback_narrative()

    def _generate_market_multiple_narrative(
        self, valuation: Dict[str, Any], business: Dict[str, Any]
    ) -> str:
        """
        Template-based narrative for market multiple valuation
        """
        _industry = business.get("industry", "your industry")
        multiple = valuation.get("multiple_used", 3.5)
        valuation_range = valuation.get("valuation_range", {})
        low_value = valuation_range.get("low", 0)
        high_value = valuation_range.get("high", 0)

        # Determine business size category
        size_category = self._determine_business_size(business)

        narrative = f"""Based on our comprehensive analysis, your business has been valued using industry-standard market multiples for {industry} companies.

**Valuation Methodology:**
We applied a {multiple}x EBITDA multiple, which is typical for {size_category} businesses in your sector. This approach compares your business to similar companies that have been sold recently, providing a market-driven valuation that reflects current M&A conditions.

**Key Factors Considered:**
- Industry benchmarks for {industry} businesses
- Your company's financial performance and growth trajectory  
- Current market conditions and M&A activity in your sector
- Business risk factors and competitive positioning
- Market size and growth potential

**Valuation Range:**
The estimated value range of €{low_value:,.0f} to €{high_value:,.0f} reflects typical variations based on:
- Deal structure (cash vs. stock consideration)
- Buyer type (strategic vs. financial)
- Market timing and economic conditions
- Specific business characteristics and growth prospects

**Next Steps:**
This valuation provides a strong foundation for M&A discussions. Consider working with experienced advisors to:
- Maximize value through strategic positioning
- Optimize deal structure and timing
- Identify the right buyer profile for your business
- Prepare comprehensive due diligence materials

*This valuation is based on publicly available market data and should be used as a starting point for professional M&A discussions.*"""

        return narrative

    def _generate_dcf_narrative(self, valuation: Dict[str, Any], business: Dict[str, Any]) -> str:
        """
        Template-based narrative for DCF valuation
        """
        _industry = business.get("industry", "your industry")
        valuation_range = valuation.get("valuation_range", {})
        low_value = valuation_range.get("low", 0)
        high_value = valuation_range.get("high", 0)
        discount_rate = valuation.get("discount_rate", 10.0)

        narrative = f"""Your business has been valued using the Discounted Cash Flow (DCF) method, which is considered the gold standard for business valuation.

**Valuation Methodology:**
The DCF method projects your future cash flows and discounts them back to present value using a {discount_rate}% discount rate. This approach focuses on your business's intrinsic value based on its ability to generate cash flows.

**Key Assumptions:**
- Revenue growth projections based on historical performance
- Operating margin improvements over time
- Capital expenditure requirements for growth
- Working capital management efficiency
- Terminal value based on long-term growth expectations

**Valuation Range:**
The DCF analysis suggests a value range of €{low_value:,.0f} to €{high_value:,.0f}, reflecting:
- Conservative vs. optimistic growth scenarios
- Different discount rate assumptions
- Various terminal value calculations
- Sensitivity to key business drivers

**Strengths of DCF Approach:**
- Focuses on cash generation ability
- Accounts for business-specific risk factors
- Provides detailed financial modeling
- Suitable for businesses with predictable cash flows

**Next Steps:**
- Validate key assumptions with industry benchmarks
- Consider multiple scenarios (base, optimistic, pessimistic)
- Review with financial advisors for accuracy
- Use as foundation for investor discussions

*DCF valuations are sensitive to assumptions and should be regularly updated as business conditions change.*"""

        return narrative

    def _generate_asset_based_narrative(
        self, valuation: Dict[str, Any], business: Dict[str, Any]
    ) -> str:
        """
        Template-based narrative for asset-based valuation
        """
        _industry = business.get("industry", "your industry")
        valuation_range = valuation.get("valuation_range", {})
        low_value = valuation_range.get("low", 0)
        high_value = valuation_range.get("high", 0)

        narrative = f"""Your business has been valued using an asset-based approach, which focuses on the value of your company's tangible and intangible assets.

**Valuation Methodology:**
This method calculates the value of your business by assessing:
- Tangible assets (equipment, inventory, real estate)
- Intangible assets (brand value, customer relationships, intellectual property)
- Liabilities and debt obligations
- Net asset value and liquidation scenarios

**Asset Categories Considered:**
- **Physical Assets**: Equipment, inventory, real estate
- **Intellectual Property**: Patents, trademarks, proprietary technology
- **Customer Relationships**: Customer lists, contracts, recurring revenue
- **Brand Value**: Market recognition, reputation, goodwill
- **Human Capital**: Key employees, management team, expertise

**Valuation Range:**
The asset-based valuation suggests €{low_value:,.0f} to €{high_value:,.0f}, reflecting:
- Different asset valuation methods (cost, market, income)
- Asset condition and marketability
- Intangible asset strength and transferability
- Liquidation vs. going concern scenarios

**When Asset-Based Works Best:**
- Asset-heavy businesses (manufacturing, real estate)
- Businesses with significant intellectual property
- Distressed or liquidation scenarios
- Asset-rich, cash-poor situations

**Next Steps:**
- Conduct detailed asset inventory and valuation
- Assess intangible asset strength and transferability
- Consider market comparables for asset values
- Evaluate liquidation vs. going concern scenarios

*Asset-based valuations provide a floor value and are often used in combination with other methods.*"""

        return narrative

    def _generate_generic_narrative(
        self, valuation: Dict[str, Any], business: Dict[str, Any]
    ) -> str:
        """
        Generic template for unknown valuation methods
        """
        _industry = business.get("industry", "your industry")
        valuation_range = valuation.get("valuation_range", {})
        low_value = valuation_range.get("low", 0)
        high_value = valuation_range.get("high", 0)

        narrative = f"""Your business has been valued using a comprehensive approach that considers multiple factors relevant to {industry} companies.

**Valuation Approach:**
Our analysis combines various valuation methodologies to provide a balanced assessment of your business value, taking into account:
- Financial performance and growth trajectory
- Market position and competitive advantages
- Industry trends and market conditions
- Asset base and operational efficiency
- Future growth potential and risk factors

**Key Value Drivers:**
- Revenue growth and profitability trends
- Market position and competitive moats
- Management team and operational efficiency
- Industry growth prospects and market dynamics
- Financial stability and risk profile

**Valuation Range:**
The analysis suggests a value range of €{low_value:,.0f} to €{high_value:,.0f}, reflecting:
- Multiple valuation methodologies
- Different growth and risk assumptions
- Market timing and economic conditions
- Business-specific characteristics

**Next Steps:**
- Review valuation assumptions and methodology
- Consider professional valuation services for accuracy
- Prepare for investor or buyer discussions
- Focus on value enhancement opportunities

*This valuation provides a starting point for strategic planning and M&A discussions.*"""

        return narrative

    def _generate_fallback_narrative(self) -> str:
        """
        Fallback narrative when generation fails
        """
        return """Based on our analysis, your business has been valued using industry-standard methodologies.

**Valuation Summary:**
We've applied appropriate valuation techniques considering your business type, industry, and financial performance. The valuation takes into account market conditions, growth prospects, and risk factors.

**Key Considerations:**
- Financial performance and growth trajectory
- Market position and competitive advantages
- Industry trends and market conditions
- Future growth potential and risk profile

**Next Steps:**
This valuation provides a foundation for strategic planning and business discussions. Consider consulting with financial advisors for detailed analysis and strategic guidance.

*This valuation is based on available information and should be used as a starting point for professional business planning.*"""

    def _determine_business_size(self, business_data: Dict[str, Any]) -> str:
        """
        Determine business size category for narrative personalization
        """
        revenue = business_data.get("revenue", 0)
        employees = business_data.get("employee_count", 0)

        if revenue > 10_000_000 or employees > 100:
            return "large"
        elif revenue > 1_000_000 or employees > 20:
            return "medium"
        else:
            return "small"

    def generate_industry_insights(self, industry: str) -> str:
        """
        Generate industry-specific insights for narrative enhancement
        """
        insights = {
            "technology": "Technology companies often command higher multiples due to scalability and growth potential.",
            "manufacturing": "Manufacturing businesses are typically valued based on asset efficiency and market position.",
            "retail": "Retail valuations focus on location, customer base, and operational efficiency.",
            "services": "Service businesses are valued based on recurring revenue and customer relationships.",
            "healthcare": "Healthcare businesses require specialized valuation approaches due to regulatory factors.",
        }

        return insights.get(
            industry.lower(), "Industry-specific factors have been considered in this valuation."
        )

    def generate_risk_factors(self, business_data: Dict[str, Any]) -> List[str]:
        """
        Generate relevant risk factors for the narrative
        """
        risk_factors = []

        # Revenue concentration risk
        if business_data.get("customer_concentration", 0) > 0.3:
            risk_factors.append("Customer concentration risk")

        # Growth risk
        if business_data.get("revenue_growth", 0) < 0:
            risk_factors.append("Declining revenue trend")

        # Market risk
        if business_data.get("market_size", 0) < 100_000_000:
            risk_factors.append("Limited market size")

        # Operational risk
        if business_data.get("employee_count", 0) < 5:
            risk_factors.append("Key person dependency")

        return risk_factors[:3]  # Limit to top 3 factors
