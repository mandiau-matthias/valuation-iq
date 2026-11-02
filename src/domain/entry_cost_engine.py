"""
Entry Cost / Replacement Cost Valuation Engine

Calculates what it would cost to replicate a business from scratch.
This provides a CEILING for acquisition price - rational buyers won't pay
more than the cost of starting a similar business themselves.

ACADEMIC FOUNDATION:
- Damodaran, A. (2012): "Investment Valuation" - Replacement Cost Method
- Pratt & Niculita (2008): "Valuing a Business" - Cost Approach
- Porter, M.E. (1980): "Competitive Strategy" - Entry Barriers

PURPOSE:
Entry cost establishes the maximum rational price a buyer would pay.
If entry cost < going concern value, this signals:
- High barriers to entry (brand, licenses, relationships)
- Potential overpayment risk
- Need for deeper due diligence on intangibles

COMPONENTS:
1. Asset Acquisition Costs
   - Equipment, vehicles, furniture
   - Initial inventory
   - Leasehold improvements

2. Customer Acquisition Costs
   - Marketing spend to acquire customer base
   - Sales team costs during ramp-up
   - Customer lifetime value × customer count × CAC

3. Employee Costs
   - Recruiting/hiring costs
   - Training and onboarding
   - Productivity ramp-up period

4. Regulatory/Licensing
   - Business licenses
   - Industry certifications
   - Professional licenses

5. Brand Development
   - Logo, website, marketing materials
   - Initial advertising
   - PR and brand building

6. Time-to-Revenue
   - Working capital during ramp-up
   - Opportunity cost of delayed revenue

@author UpSwitch CTO Team
@date January 2026
@version 1.0.0
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal, bank_round
from src.domain.models import FinancialData, ConfidenceLevel

logger = get_logger(__name__)


# ============================================================================
# CUSTOMER ACQUISITION COSTS BY INDUSTRY
# Source: Industry benchmarks, SaaS metrics, B2B/B2C data
# ============================================================================
CUSTOMER_ACQUISITION_COSTS = {
    # CAC as % of first-year customer revenue
    "saas": Decimal("0.80"),           # 80% of year 1 revenue (high CAC)
    "technology": Decimal("0.60"),
    "professional-services": Decimal("0.40"),
    "consulting": Decimal("0.35"),
    "healthcare": Decimal("0.50"),
    "retail": Decimal("0.15"),         # Low CAC, high volume
    "ecommerce": Decimal("0.25"),
    "manufacturing": Decimal("0.20"),
    "construction": Decimal("0.15"),
    "restaurant": Decimal("0.10"),
    "services": Decimal("0.30"),
    "default": Decimal("0.25"),
}

# Employee hiring/training costs by role type
EMPLOYEE_COSTS = {
    "recruiting_cost_per_hire": Decimal("5000"),   # EUR per hire
    "training_cost_months": Decimal("3"),          # Months of salary for training
    "productivity_ramp_months": Decimal("6"),      # Months to full productivity
}

# Startup time by industry (months to reach steady state)
STARTUP_TIMELINE = {
    "saas": 18,
    "technology": 12,
    "professional-services": 6,
    "consulting": 4,
    "healthcare": 12,
    "retail": 6,
    "ecommerce": 9,
    "manufacturing": 18,
    "construction": 8,
    "restaurant": 6,
    "services": 6,
    "default": 9,
}


@dataclass
class EntryCostComponent:
    """Individual cost component for transparency."""
    category: str
    description: str
    amount: Decimal
    assumptions: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "amount": from_decimal(self.amount),
            "assumptions": self.assumptions,
        }


@dataclass
class EntryCostResult:
    """
    Result of entry/replacement cost calculation.
    """
    # Total entry cost
    total_entry_cost: Decimal
    
    # Component breakdown
    asset_costs: Decimal
    customer_acquisition_costs: Decimal
    employee_costs: Decimal
    regulatory_costs: Decimal
    brand_development_costs: Decimal
    working_capital_needs: Decimal
    
    # Detailed breakdown
    cost_components: List[EntryCostComponent] = field(default_factory=list)
    
    # Timeline
    months_to_breakeven: int = 12
    
    # Comparison
    premium_over_entry: Optional[Decimal] = None  # Going concern value vs entry cost
    
    # Value range (±20% uncertainty)
    value_low: Decimal = Decimal("0")
    value_high: Decimal = Decimal("0")
    
    # Metadata
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    methodology: str = "Entry Cost"
    sources: List[str] = field(default_factory=list)
    rationale: str = ""
    warnings: List[str] = field(default_factory=list)
    industry: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_entry_cost": from_decimal(self.total_entry_cost),
            "asset_costs": from_decimal(self.asset_costs),
            "customer_acquisition_costs": from_decimal(self.customer_acquisition_costs),
            "employee_costs": from_decimal(self.employee_costs),
            "regulatory_costs": from_decimal(self.regulatory_costs),
            "brand_development_costs": from_decimal(self.brand_development_costs),
            "working_capital_needs": from_decimal(self.working_capital_needs),
            "cost_components": [c.to_dict() for c in self.cost_components],
            "months_to_breakeven": self.months_to_breakeven,
            "premium_over_entry": from_decimal(self.premium_over_entry) if self.premium_over_entry is not None else None,
            "value_low": from_decimal(self.value_low),
            "value_high": from_decimal(self.value_high),
            "confidence": self.confidence.value,
            "methodology": self.methodology,
            "sources": self.sources,
            "rationale": self.rationale,
            "warnings": self.warnings,
            "industry": self.industry,
        }


class EntryCostEngine:
    """
    Entry/Replacement Cost Valuation Engine.
    
    Calculates the cost to replicate a business from scratch,
    providing a ceiling for rational acquisition price.
    
    Usage:
        engine = EntryCostEngine(financial_data)
        result = engine.calculate_entry_cost(
            industry="consulting",
            customer_count=50,
            employee_count=5,
        )
    """
    
    def __init__(
        self,
        financial_data: FinancialData,
        country_code: str = "BE",
    ):
        """
        Initialize Entry Cost Engine.
        
        Args:
            financial_data: Company financial data
            country_code: ISO country code
        """
        self.financial_data = financial_data
        self.country_code = country_code
        self.current_year = financial_data.current_year
        
        logger.info(
            f"EntryCostEngine initialized",
            company=financial_data.company_name,
            revenue=from_decimal(self.current_year.revenue),
            country=country_code,
        )
    
    def _get_cac_rate(self, industry: str) -> Decimal:
        """Get customer acquisition cost rate for industry."""
        industry_norm = industry.lower().strip()
        
        for key in CUSTOMER_ACQUISITION_COSTS:
            if key in industry_norm or industry_norm in key:
                return CUSTOMER_ACQUISITION_COSTS[key]
        
        return CUSTOMER_ACQUISITION_COSTS["default"]
    
    def _get_startup_months(self, industry: str) -> int:
        """Get startup timeline for industry."""
        industry_norm = industry.lower().strip()
        
        for key in STARTUP_TIMELINE:
            if key in industry_norm or industry_norm in key:
                return STARTUP_TIMELINE[key]
        
        return STARTUP_TIMELINE["default"]
    
    def calculate_entry_cost(
        self,
        industry: str,
        customer_count: Optional[int] = None,
        employee_count: Optional[int] = None,
        requires_special_licensing: bool = False,
        has_significant_brand: bool = False,
        asset_replacement_cost: Optional[Decimal] = None,
    ) -> EntryCostResult:
        """
        Calculate total entry/replacement cost.
        
        Args:
            industry: Business industry
            customer_count: Number of customers to replicate
            employee_count: Number of employees to hire
            requires_special_licensing: Whether special licenses are needed
            has_significant_brand: Whether brand has significant value
            asset_replacement_cost: Override for asset costs if known
            
        Returns:
            EntryCostResult with detailed breakdown
        """
        year_data = self.current_year
        cost_components = []
        warnings = []
        
        # Estimate unknowns from financials
        if customer_count is None:
            if year_data.revenue > 0:
                avg_revenue_per_customer = year_data.revenue / Decimal("100")
                customer_count = max(1, int(year_data.revenue / avg_revenue_per_customer))
            else:
                customer_count = 1
            warnings.append(f"Customer count estimated at {customer_count}")
        
        if employee_count is None:
            # Estimate from revenue (typical €100-200k revenue per employee for SMEs)
            employee_count = max(1, int(year_data.revenue / Decimal("150000"))) if year_data.revenue > 0 else 1
            warnings.append(f"Employee count estimated at {employee_count}")
        
        # 1. ASSET COSTS
        if asset_replacement_cost is not None:
            asset_costs = asset_replacement_cost
        else:
            if year_data.total_assets is not None and year_data.total_assets > 0:
                asset_costs = year_data.total_assets * Decimal("1.20")
            else:
                asset_costs = year_data.revenue * Decimal("0.30")
        
        cost_components.append(EntryCostComponent(
            category="Asset Acquisition",
            description="Equipment, inventory, leasehold improvements",
            amount=asset_costs,
            assumptions="20% premium over book value for new assets"
        ))
        
        # 2. CUSTOMER ACQUISITION COSTS
        cac_rate = self._get_cac_rate(industry)
        avg_customer_revenue = year_data.revenue / Decimal(str(customer_count)) if customer_count > 0 else Decimal("0")
        cac_per_customer = avg_customer_revenue * cac_rate
        total_cac = cac_per_customer * Decimal(str(customer_count))
        
        cost_components.append(EntryCostComponent(
            category="Customer Acquisition",
            description=f"Acquire {customer_count} customers at industry CAC rate",
            amount=total_cac,
            assumptions=f"CAC = {from_decimal(cac_rate * 100):.0f}% of first-year customer revenue"
        ))
        
        # 3. EMPLOYEE COSTS
        avg_salary = Decimal("50000")  # EUR average for Belgian SME
        recruiting_per_hire = EMPLOYEE_COSTS["recruiting_cost_per_hire"]
        training_months = EMPLOYEE_COSTS["training_cost_months"]
        
        recruiting_costs = Decimal(str(employee_count)) * recruiting_per_hire
        training_costs = Decimal(str(employee_count)) * avg_salary * (training_months / Decimal("12"))
        total_employee_costs = recruiting_costs + training_costs
        
        cost_components.append(EntryCostComponent(
            category="Employee Hiring & Training",
            description=f"Recruit and train {employee_count} employees",
            amount=total_employee_costs,
            assumptions=f"€{from_decimal(recruiting_per_hire):,.0f} recruiting + {from_decimal(training_months):.0f} months training"
        ))
        
        # 4. REGULATORY/LICENSING COSTS
        regulatory_costs = Decimal("5000")  # Base for all businesses
        if requires_special_licensing:
            regulatory_costs += Decimal("25000")  # Professional licenses
        
        cost_components.append(EntryCostComponent(
            category="Regulatory & Licensing",
            description="Business licenses, certifications, permits",
            amount=regulatory_costs,
            assumptions="Standard business setup + industry-specific licenses"
        ))
        
        # 5. BRAND DEVELOPMENT COSTS
        if has_significant_brand:
            brand_costs = year_data.revenue * Decimal("0.20")  # 20% of revenue to rebuild brand
        else:
            brand_costs = Decimal("15000")  # Basic brand setup
        
        cost_components.append(EntryCostComponent(
            category="Brand Development",
            description="Logo, website, marketing materials, initial advertising",
            amount=brand_costs,
            assumptions="Significant brand" if has_significant_brand else "Basic brand setup"
        ))
        
        # 6. WORKING CAPITAL DURING RAMP-UP
        startup_months = self._get_startup_months(industry)
        monthly_operating_costs = year_data.revenue * Decimal("0.08")  # ~8% of annual revenue per month
        working_capital = monthly_operating_costs * Decimal(str(startup_months))
        
        cost_components.append(EntryCostComponent(
            category="Working Capital",
            description=f"Operating capital during {startup_months}-month ramp-up",
            amount=working_capital,
            assumptions=f"{startup_months} months to reach steady state revenue"
        ))
        
        # TOTAL
        total_entry_cost = (
            asset_costs +
            total_cac +
            total_employee_costs +
            regulatory_costs +
            brand_costs +
            working_capital
        )
        
        # Calculate range (±20% uncertainty)
        value_low = total_entry_cost * Decimal("0.80")
        value_high = total_entry_cost * Decimal("1.20")
        
        # Confidence based on data quality
        confidence = ConfidenceLevel.MEDIUM
        if len(warnings) > 2:
            confidence = ConfidenceLevel.LOW
        if asset_replacement_cost is not None and customer_count is not None and employee_count is not None:
            confidence = ConfidenceLevel.HIGH
        
        result = EntryCostResult(
            total_entry_cost=bank_round(total_entry_cost),
            asset_costs=bank_round(asset_costs),
            customer_acquisition_costs=bank_round(total_cac),
            employee_costs=bank_round(total_employee_costs),
            regulatory_costs=bank_round(regulatory_costs),
            brand_development_costs=bank_round(brand_costs),
            working_capital_needs=bank_round(working_capital),
            cost_components=cost_components,
            months_to_breakeven=startup_months,
            value_low=bank_round(value_low),
            value_high=bank_round(value_high),
            confidence=confidence,
            methodology="Entry/Replacement Cost",
            sources=[
                "Damodaran (2012) Investment Valuation",
                "Pratt & Niculita (2008) Valuing a Business",
                "Porter (1980) Competitive Strategy - Entry Barriers",
            ],
            rationale=f"Entry cost to replicate {industry} business with {customer_count} customers and {employee_count} employees",
            warnings=warnings,
            industry=industry,
        )
        
        logger.info(
            f"Entry cost calculated",
            total_entry_cost=from_decimal(total_entry_cost),
            components_count=len(cost_components),
            months_to_breakeven=startup_months,
            confidence=confidence.value,
        )
        
        return result
    
    def compare_to_going_concern(
        self,
        going_concern_value: Decimal,
        entry_cost_result: EntryCostResult,
    ) -> Dict[str, Any]:
        """
        Compare entry cost to going concern value.
        
        Args:
            going_concern_value: Value from income/market approach
            entry_cost_result: Result from calculate_entry_cost
            
        Returns:
            Comparison analysis
        """
        premium = going_concern_value - entry_cost_result.total_entry_cost
        premium_pct = (premium / entry_cost_result.total_entry_cost) * Decimal("100") if entry_cost_result.total_entry_cost > 0 else Decimal("0")
        
        # Interpretation
        if premium_pct > Decimal("50"):
            interpretation = "HIGH PREMIUM: Going concern value significantly exceeds entry cost. This suggests strong intangible value (brand, relationships, barriers to entry) OR potential overvaluation."
            risk = "high"
        elif premium_pct > Decimal("20"):
            interpretation = "MODERATE PREMIUM: Going concern value exceeds entry cost by a reasonable margin. Premium likely reflects established business value."
            risk = "medium"
        elif premium_pct > Decimal("0"):
            interpretation = "LOW PREMIUM: Going concern value slightly above entry cost. Fair pricing with minimal acquisition premium."
            risk = "low"
        else:
            interpretation = "DISCOUNT: Going concern value below entry cost. Either the business is distressed OR entry barriers are very high."
            risk = "review_required"
        
        return {
            "going_concern_value": from_decimal(going_concern_value),
            "entry_cost": from_decimal(entry_cost_result.total_entry_cost),
            "premium": from_decimal(premium),
            "premium_percentage": from_decimal(premium_pct),
            "interpretation": interpretation,
            "risk_level": risk,
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_entry_cost_engine(
    financial_data: FinancialData,
    country_code: str = "BE",
) -> EntryCostEngine:
    """
    Factory function to create Entry Cost Engine.
    
    Args:
        financial_data: Company financial data
        country_code: ISO country code
        
    Returns:
        Configured EntryCostEngine instance
    """
    return EntryCostEngine(financial_data=financial_data, country_code=country_code)
