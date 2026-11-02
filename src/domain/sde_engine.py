"""
Seller's Discretionary Earnings (SDE) Valuation Engine

SDE is THE standard valuation methodology for small businesses (< EUR 5M revenue).
It captures the true economic benefit to a single owner-operator, which EBITDA misses.

ACADEMIC FOUNDATION:
- Trugman, G.R. (2017): "Understanding Business Valuation" (AICPA) - THE definitive SME standard
- West, T.L. & Jones, J.D. (2012): "Handbook of Business Valuation" - SDE normalization
- Pratt, S.P. & Niculita, A.V. (2008): "Valuing a Business" - Owner compensation adjustment
- BizBuySell (2024): Market Report - SDE multiples by industry (1.5x-3.5x)
- IBBA (2024): Market Pulse Survey - Small business transaction data

SDE FORMULA:
    SDE = Net Income
        + Owner's Salary (actual or market rate)
        + Owner's Benefits (health, retirement, life insurance)
        + Owner's Perquisites (car, travel, meals, personal expenses)
        + Depreciation & Amortization
        + Interest Expense
        + Non-recurring Expenses (legal, one-time costs)
        - Non-operating Income (rental income, investment gains)

WHEN TO USE SDE vs EBITDA:
- Revenue < EUR 2M: Primary methodology is SDE
- Owner-operated (1-3 owners): SDE captures owner benefit
- Service businesses with low assets: SDE more relevant than asset-based
- Professional practices: SDE is standard

SDE MULTIPLES (BizBuySell 2024, Pepperdine 2024):
- Micro businesses (<EUR 500K): 1.0x - 2.0x SDE
- Small businesses (EUR 500K - 2M): 1.5x - 2.5x SDE
- Lower middle market (EUR 2M - 5M): 2.0x - 3.5x SDE

ADJUSTMENTS:
- Industry risk premium/discount
- Geographic location adjustment
- Customer concentration risk
- Owner dependency discount (if high key-person risk)
- Growth trajectory adjustment
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.domain.models import ConfidenceLevel, FinancialData
from src.domain.sde_market_config import (
    OWNER_COMPENSATION_BENCHMARKS,
    SDE_MULTIPLES_BY_INDUSTRY,
    TITAN_NORMALIZATION_CATEGORIES,
)
from src.domain.sde_titan_adjustments import bucket_titan_sde_adjustments
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SDEComponents:
    """Breakdown of SDE components for transparency."""

    net_income: Decimal
    owner_salary: Decimal
    owner_benefits: Decimal
    owner_perks: Decimal
    depreciation: Decimal
    amortization: Decimal
    interest_expense: Decimal
    non_recurring_expenses: Decimal
    non_operating_income: Decimal
    other_addbacks: Decimal = Decimal("0")
    total_sde: Decimal = Decimal("0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "net_income": from_decimal(self.net_income),
            "owner_salary": from_decimal(self.owner_salary),
            "owner_benefits": from_decimal(self.owner_benefits),
            "owner_perks": from_decimal(self.owner_perks),
            "depreciation": from_decimal(self.depreciation),
            "amortization": from_decimal(self.amortization),
            "interest_expense": from_decimal(self.interest_expense),
            "non_recurring_expenses": from_decimal(self.non_recurring_expenses),
            "non_operating_income": from_decimal(self.non_operating_income),
            "other_addbacks": from_decimal(self.other_addbacks),
            "total_sde": from_decimal(self.total_sde),
        }


@dataclass
class SDEValuationResult:
    """
    Result of SDE-based valuation.

    Includes the calculated SDE, applied multiple, adjustments, and final value.
    """

    # Core valuation
    sde: Decimal
    sde_multiple: Decimal
    base_value: Decimal  # SDE * Multiple

    # Adjustments
    adjustments: Dict[str, Decimal] = field(default_factory=dict)
    total_adjustment_percent: Decimal = Decimal("0")

    # Final values
    adjusted_value: Decimal = Decimal("0")
    value_low: Decimal = Decimal("0")
    value_high: Decimal = Decimal("0")

    # Components for transparency
    sde_components: Optional[SDEComponents] = None

    # Metadata
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    methodology: str = "SDE"
    sources: List[str] = field(default_factory=list)
    rationale: str = ""
    warnings: List[str] = field(default_factory=list)

    # Business classification
    business_size: str = ""  # micro, small, lower_middle
    industry: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sde": from_decimal(self.sde),
            "sde_multiple": from_decimal(self.sde_multiple),
            "base_value": from_decimal(self.base_value),
            "adjustments": {k: from_decimal(v) for k, v in self.adjustments.items()},
            "total_adjustment_percent": from_decimal(self.total_adjustment_percent),
            "adjusted_value": from_decimal(self.adjusted_value),
            "value_low": from_decimal(self.value_low),
            "value_high": from_decimal(self.value_high),
            "sde_components": self.sde_components.to_dict() if self.sde_components else None,
            "confidence": self.confidence.value,
            "methodology": self.methodology,
            "sources": self.sources,
            "rationale": self.rationale,
            "warnings": self.warnings,
            "business_size": self.business_size,
            "industry": self.industry,
        }


class SDEEngine:
    """
    Seller's Discretionary Earnings Valuation Engine.

    Calculates the value of a small business based on the cash flow
    available to a single owner-operator.

    Usage:
        engine = SDEEngine(financial_data)
        result = engine.calculate_valuation(
            industry="consulting",
            owner_salary=Decimal("60000"),
            owner_benefits=Decimal("10000"),
        )
    """

    # Revenue thresholds for business size classification (EUR)
    MICRO_THRESHOLD = Decimal("500000")  # < EUR 500K
    SMALL_THRESHOLD = Decimal("2000000")  # EUR 500K - 2M
    LOWER_MIDDLE_THRESHOLD = Decimal("5000000")  # EUR 2M - 5M

    def __init__(
        self,
        financial_data: FinancialData,
        country_code: str = "BE",
    ):
        """
        Initialize SDE Engine.

        Args:
            financial_data: Company financial data
            country_code: ISO country code for market adjustments
        """
        self.financial_data = financial_data
        self.country_code = country_code
        self.current_year = financial_data.current_year

        logger.info(
            f"SDEEngine initialized",
            company=financial_data.company_name,
            revenue=from_decimal(self.current_year.revenue),
            country=country_code,
        )

    def classify_business_size(self, revenue: Decimal) -> str:
        """
        Classify business size based on revenue.

        Args:
            revenue: Annual revenue in EUR

        Returns:
            Size classification: 'micro', 'small', 'lower_middle', or 'large'
        """
        if revenue < self.MICRO_THRESHOLD:
            return "micro"
        elif revenue < self.SMALL_THRESHOLD:
            return "small"
        elif revenue < self.LOWER_MIDDLE_THRESHOLD:
            return "lower_middle"
        else:
            return "large"

    def calculate_sde_from_titan_adjustments(
        self,
        ebitda_normalization_metadata: Dict[str, Any],
    ) -> SDEComponents:
        """
        Calculate SDE using Titan's normalization adjustments.

        Titan provides a structured breakdown of all normalization adjustments.
        This method converts that to SDE components.

        Args:
            ebitda_normalization_metadata: Normalization metadata from Titan

        Returns:
            SDEComponents with breakdown
        """
        year_data = self.current_year

        # Start with reported EBITDA (before normalization) when available.
        ebitda = to_decimal(
            ebitda_normalization_metadata.get("reported_ebitda") or year_data.ebitda or Decimal("0")
        )

        # Extract components from Titan's metadata
        adjustments = ebitda_normalization_metadata.get("adjustments") or []
        adjustment_buckets = bucket_titan_sde_adjustments(adjustments)

        depreciation = year_data.depreciation or Decimal("0")
        amortization = year_data.amortization or Decimal("0")
        interest = year_data.interest_expense or Decimal("0")

        tax = year_data.tax_expense or Decimal("0")
        net_income = ebitda - depreciation - amortization - interest - tax

        # Total SDE = EBITDA + Owner comp + other add-backs that were already expensed
        # (Note: Titan's adjustments are already in "add-back" form)
        total_sde = (
            ebitda
            + adjustment_buckets.owner_salary
            + adjustment_buckets.owner_benefits
            + adjustment_buckets.owner_perks
            + adjustment_buckets.non_recurring
            + adjustment_buckets.other_addbacks
            - adjustment_buckets.non_operating
        )

        components = SDEComponents(
            net_income=net_income,
            owner_salary=adjustment_buckets.owner_salary,
            owner_benefits=adjustment_buckets.owner_benefits,
            owner_perks=adjustment_buckets.owner_perks,
            depreciation=depreciation,
            amortization=amortization,
            interest_expense=interest,
            non_recurring_expenses=adjustment_buckets.non_recurring,
            non_operating_income=adjustment_buckets.non_operating,
            other_addbacks=adjustment_buckets.other_addbacks,
            total_sde=total_sde,
        )

        logger.info(
            f"SDE calculated from Titan normalization metadata",
            ebitda=from_decimal(ebitda),
            titan_adjustments_count=len(adjustments),
            total_sde=from_decimal(total_sde),
        )

        return components

    def calculate_sde(
        self,
        owner_salary: Optional[Decimal] = None,
        owner_benefits: Optional[Decimal] = None,
        owner_perks: Optional[Decimal] = None,
        non_recurring_expenses: Optional[Decimal] = None,
        non_operating_income: Optional[Decimal] = None,
        ebitda_normalization_metadata: Optional[Dict[str, Any]] = None,
    ) -> SDEComponents:
        """
        Calculate Seller's Discretionary Earnings.

        TITAN INTEGRATION:
        If ebitda_normalization_metadata is provided (from Titan's normalization module),
        use that as the source of truth for adjustments. Otherwise, use the provided
        parameters or fall back to benchmarks.

        SDE = Net Income + Owner Compensation + D&A + Interest + Non-recurring
              - Non-operating Income

        Args:
            owner_salary: Owner's annual salary (uses benchmark if not provided)
            owner_benefits: Owner's benefits (health, retirement)
            owner_perks: Owner's perquisites (car, travel)
            non_recurring_expenses: One-time expenses to add back
            non_operating_income: Non-operating income to subtract
            ebitda_normalization_metadata: Titan's normalization metadata (takes precedence)

        Returns:
            SDEComponents with breakdown of all components
        """
        # If Titan provided normalization metadata, use that
        if ebitda_normalization_metadata and ebitda_normalization_metadata.get("adjustments"):
            logger.info("Using Titan's normalization metadata for SDE calculation")
            return self.calculate_sde_from_titan_adjustments(ebitda_normalization_metadata)

        year_data = self.current_year
        business_size = self.classify_business_size(year_data.revenue)

        # Get net income (use EBITDA - D&A - Interest - Tax if not available)
        net_income = year_data.net_income
        if net_income is None:
            ebitda_val = year_data.ebitda or Decimal("0")
            depreciation = year_data.depreciation or Decimal("0")
            amortization = year_data.amortization or Decimal("0")
            interest = year_data.interest_expense or Decimal("0")
            tax = year_data.tax_expense or Decimal("0")
            net_income = ebitda_val - depreciation - amortization - interest - tax

        # Use provided values or benchmarks
        benchmarks = OWNER_COMPENSATION_BENCHMARKS.get(
            business_size, OWNER_COMPENSATION_BENCHMARKS["small"]
        )

        salary = owner_salary if owner_salary is not None else benchmarks["salary"]
        benefits = owner_benefits if owner_benefits is not None else benchmarks["benefits"]
        perks = owner_perks if owner_perks is not None else benchmarks["perks"]

        # Get D&A and Interest from financial data
        depreciation = year_data.depreciation or Decimal("0")
        amortization = year_data.amortization or Decimal("0")
        interest = year_data.interest_expense or Decimal("0")

        # Non-recurring and non-operating (default to 0)
        non_recurring = non_recurring_expenses or Decimal("0")
        non_operating = non_operating_income or Decimal("0")

        # Calculate total SDE
        total_sde = (
            net_income
            + salary
            + benefits
            + perks
            + depreciation
            + amortization
            + interest
            + non_recurring
            - non_operating
        )

        components = SDEComponents(
            net_income=net_income,
            owner_salary=salary,
            owner_benefits=benefits,
            owner_perks=perks,
            depreciation=depreciation,
            amortization=amortization,
            interest_expense=interest,
            non_recurring_expenses=non_recurring,
            non_operating_income=non_operating,
            total_sde=total_sde,
        )

        logger.info(
            f"SDE calculated",
            net_income=from_decimal(net_income),
            owner_compensation=from_decimal(salary + benefits + perks),
            total_sde=from_decimal(total_sde),
            business_size=business_size,
        )

        return components

    def get_sde_multiple(
        self,
        industry: str,
        business_size: str,
        owner_dependency: Optional[Decimal] = None,
        growth_rate: Optional[Decimal] = None,
        customer_concentration: Optional[Decimal] = None,
        sde_calibration: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Decimal, str, List[str]]:
        """
        Get appropriate SDE multiple with adjustments.

        PRIORITY CASCADE (Titan Integration):
        1. Titan's sde_calibration data (from business_types DB)
        2. Hardcoded SDE_MULTIPLES_BY_INDUSTRY tables

        Args:
            industry: Business industry
            business_size: 'micro', 'small', or 'lower_middle' (maps to _micro, _small, _medium)
            owner_dependency: Owner dependency score (0-1, higher = more dependent)
            growth_rate: Revenue growth rate
            customer_concentration: Top customer revenue concentration (0-1)
            sde_calibration: SDE calibration data from Titan (takes precedence)

        Returns:
            Tuple of (adjusted_multiple, rationale, sources)
        """
        # Normalize industry
        industry_norm = industry.lower().strip().replace(" ", "-")

        base_multiple = None
        data_source = "hardcoded"

        # PRIORITY 1: Use Titan's SDE calibration if available
        if sde_calibration:
            # Map business_size to Titan's field names
            size_to_field = {
                "micro": "sde_multiple_micro",
                "small": "sde_multiple_small",
                "lower_middle": "sde_multiple_medium",  # lower_middle maps to medium
                "medium": "sde_multiple_medium",
            }
            field_name = size_to_field.get(business_size, "sde_multiple_small")

            titan_multiple = sde_calibration.get(field_name)
            if titan_multiple is not None:
                base_multiple = to_decimal(titan_multiple)
                data_source = sde_calibration.get("sde_source", "database")
                logger.info(
                    f"Using Titan's SDE multiple from database",
                    industry=industry_norm,
                    size=business_size,
                    multiple=from_decimal(base_multiple),
                    source=data_source,
                )

        # PRIORITY 2: Fall back to hardcoded industry tables
        if base_multiple is None:
            industry_multiples = SDE_MULTIPLES_BY_INDUSTRY.get(
                industry_norm,
                SDE_MULTIPLES_BY_INDUSTRY.get("services", SDE_MULTIPLES_BY_INDUSTRY["other"]),
            )
            base_multiple = industry_multiples.get(business_size, Decimal("2.0"))
            data_source = "hardcoded"
            logger.info(
                f"Using hardcoded SDE multiple",
                industry=industry_norm,
                size=business_size,
                multiple=from_decimal(base_multiple),
            )

        sources = [
            f"{data_source}" if data_source != "hardcoded" else "BizBuySell (2024) Market Report",
            "Pepperdine (2024) Private Capital Markets",
            "Trugman (2017) Understanding Business Valuation",
        ]

        adjustments = []
        adjusted_multiple = base_multiple

        # Owner dependency adjustment (-5% to -20%)
        # Use Titan's factor if available
        owner_dep_factor = None
        if sde_calibration and sde_calibration.get("sde_owner_dependency_factor"):
            owner_dep_factor = to_decimal(sde_calibration["sde_owner_dependency_factor"])

        if owner_dependency is not None and owner_dependency > Decimal("0.5"):
            if owner_dep_factor is not None:
                # Use database-driven factor
                discount = (Decimal("1") - owner_dep_factor) * owner_dependency
            else:
                discount = (owner_dependency - Decimal("0.5")) * Decimal("0.4")  # Max -20%
            adjusted_multiple = adjusted_multiple * (Decimal("1") - discount)
            adjustments.append(f"Owner dependency discount: -{from_decimal(discount * 100):.1f}%")

        # Growth rate adjustment (+/-10%)
        # Use Titan's growth factor if available
        growth_factor = None
        if sde_calibration and sde_calibration.get("sde_growth_factor"):
            growth_factor = to_decimal(sde_calibration["sde_growth_factor"])

        if growth_rate is not None:
            if growth_rate > Decimal("0.15"):  # >15% growth
                if growth_factor is not None:
                    premium = (growth_factor - Decimal("1")) * (growth_rate / Decimal("0.20"))
                else:
                    premium = min(growth_rate - Decimal("0.15"), Decimal("0.10"))
                adjusted_multiple = adjusted_multiple * (Decimal("1") + premium)
                adjustments.append(f"Growth premium: +{from_decimal(premium * 100):.1f}%")
            elif growth_rate < Decimal("-0.05"):  # Declining
                discount = min(abs(growth_rate), Decimal("0.15"))
                adjusted_multiple = adjusted_multiple * (Decimal("1") - discount)
                adjustments.append(f"Decline discount: -{from_decimal(discount * 100):.1f}%")

        # Customer concentration adjustment (-5% to -15%)
        if customer_concentration is not None and customer_concentration > Decimal("0.30"):
            discount = (customer_concentration - Decimal("0.30")) * Decimal("0.3")  # Max -21%
            adjusted_multiple = adjusted_multiple * (Decimal("1") - discount)
            adjustments.append(
                f"Customer concentration discount: -{from_decimal(discount * 100):.1f}%"
            )

        # Build rationale
        rationale_parts = [
            f"Base SDE multiple for {industry_norm} ({business_size}): {from_decimal(base_multiple):.2f}x",
        ]
        rationale_parts.extend(adjustments)
        rationale_parts.append(f"Adjusted multiple: {from_decimal(adjusted_multiple):.2f}x")

        rationale = ". ".join(rationale_parts)

        return adjusted_multiple, rationale, sources

    def calculate_valuation(
        self,
        industry: str,
        owner_salary: Optional[Decimal] = None,
        owner_benefits: Optional[Decimal] = None,
        owner_perks: Optional[Decimal] = None,
        non_recurring_expenses: Optional[Decimal] = None,
        non_operating_income: Optional[Decimal] = None,
        owner_dependency: Optional[Decimal] = None,
        growth_rate: Optional[Decimal] = None,
        customer_concentration: Optional[Decimal] = None,
        sde_calibration: Optional[Dict[str, Any]] = None,
        ebitda_normalization_metadata: Optional[Dict[str, Any]] = None,
    ) -> SDEValuationResult:
        """
        Calculate complete SDE-based business valuation.

        TITAN INTEGRATION:
        - sde_calibration: Database-driven SDE multiples and adjustment factors
        - ebitda_normalization_metadata: User-entered normalization adjustments

        Args:
            industry: Business industry
            owner_salary: Owner's annual salary
            owner_benefits: Owner's benefits
            owner_perks: Owner's perquisites
            non_recurring_expenses: One-time expenses to add back
            non_operating_income: Non-operating income to subtract
            owner_dependency: Owner dependency score (0-1)
            growth_rate: Revenue growth rate
            customer_concentration: Top customer concentration
            sde_calibration: SDE calibration data from Titan (database-driven)
            ebitda_normalization_metadata: Normalization adjustments from Titan

        Returns:
            SDEValuationResult with complete valuation breakdown
        """
        revenue = self.current_year.revenue
        business_size = self.classify_business_size(revenue)

        # Check if SDE is appropriate
        warnings = []
        if business_size == "large":
            warnings.append(
                "Revenue exceeds EUR 5M - consider using EBITDA multiples or DCF instead of SDE"
            )

        # Calculate SDE (uses Titan's normalization metadata if available)
        sde_components = self.calculate_sde(
            owner_salary=owner_salary,
            owner_benefits=owner_benefits,
            owner_perks=owner_perks,
            non_recurring_expenses=non_recurring_expenses,
            non_operating_income=non_operating_income,
            ebitda_normalization_metadata=ebitda_normalization_metadata,
        )

        sde = sde_components.total_sde

        # Handle negative SDE
        if sde <= Decimal("0"):
            warnings.append(
                "SDE is negative or zero - business may not be viable for sale at this price"
            )
            return SDEValuationResult(
                sde=sde,
                sde_multiple=Decimal("0"),
                base_value=Decimal("0"),
                adjusted_value=Decimal("0"),
                value_low=Decimal("0"),
                value_high=Decimal("0"),
                sde_components=sde_components,
                confidence=ConfidenceLevel.LOW,
                methodology="SDE",
                sources=["N/A - Negative SDE"],
                rationale="SDE is negative, indicating the business does not generate positive owner benefit.",
                warnings=warnings,
                business_size=business_size,
                industry=industry,
            )

        # Get SDE multiple (uses Titan's SDE calibration data if available)
        sde_multiple, rationale, sources = self.get_sde_multiple(
            industry=industry,
            business_size=business_size,
            owner_dependency=owner_dependency,
            growth_rate=growth_rate,
            customer_concentration=customer_concentration,
            sde_calibration=sde_calibration,
        )

        # Calculate base value
        base_value = sde * sde_multiple

        # Calculate adjustments
        adjustments = {}
        total_adjustment = Decimal("1")

        # Belgian market adjustment (Belgian SMEs trade at slight premium to US)
        if self.country_code == "BE":
            belgian_premium = Decimal("0.05")  # +5%
            adjustments["Belgian market premium"] = belgian_premium
            total_adjustment += belgian_premium

        # Calculate adjusted value
        adjusted_value = base_value * total_adjustment

        # Calculate range (±15% for typical range)
        range_factor = Decimal("0.15")
        value_low = adjusted_value * (Decimal("1") - range_factor)
        value_high = adjusted_value * (Decimal("1") + range_factor)

        # Determine confidence
        confidence = ConfidenceLevel.MEDIUM
        if owner_salary is not None and owner_benefits is not None:
            confidence = ConfidenceLevel.HIGH
        if len(warnings) > 0:
            confidence = ConfidenceLevel.LOW

        # Compile result
        total_adjustment_percent = (total_adjustment - Decimal("1")) * Decimal("100")

        result = SDEValuationResult(
            sde=sde,
            sde_multiple=sde_multiple,
            base_value=base_value,
            adjustments=adjustments,
            total_adjustment_percent=total_adjustment_percent,
            adjusted_value=bank_round(adjusted_value),
            value_low=bank_round(value_low),
            value_high=bank_round(value_high),
            sde_components=sde_components,
            confidence=confidence,
            methodology="SDE",
            sources=sources,
            rationale=rationale,
            warnings=warnings,
            business_size=business_size,
            industry=industry,
        )

        logger.info(
            f"SDE valuation completed",
            sde=from_decimal(sde),
            multiple=from_decimal(sde_multiple),
            adjusted_value=from_decimal(adjusted_value),
            confidence=confidence.value,
            business_size=business_size,
        )

        return result

    def is_sde_appropriate(self) -> Tuple[bool, str]:
        """
        Determine if SDE is the appropriate valuation methodology.

        Returns:
            Tuple of (is_appropriate, reason)
        """
        revenue = self.current_year.revenue
        business_size = self.classify_business_size(revenue)

        if business_size == "large":
            return False, "Revenue exceeds EUR 5M - use EBITDA multiples or DCF"

        # Check if business is profitable
        ebitda = self.current_year.ebitda
        if ebitda <= Decimal("0"):
            return False, "Negative EBITDA - consider asset-based valuation"

        return (
            True,
            f"SDE appropriate for {business_size} business with revenue EUR {from_decimal(revenue):,.0f}",
        )


def create_sde_engine(
    financial_data: FinancialData,
    country_code: str = "BE",
) -> SDEEngine:
    """
    Factory function to create SDE Engine.

    Args:
        financial_data: Company financial data
        country_code: ISO country code

    Returns:
        Configured SDEEngine instance
    """
    return SDEEngine(financial_data=financial_data, country_code=country_code)
