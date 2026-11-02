"""Market configuration tables for Seller's Discretionary Earnings valuation."""

from decimal import Decimal

from src.config.belgian_salary_benchmarks import OWNER_COMPENSATION_BY_SIZE

# TITAN INTEGRATION: Normalization Categories
# These match the NormalizationCategory enum in Titan's normalization module
TITAN_NORMALIZATION_CATEGORIES = {
    "owner_compensation_adjustment": True,  # Add-back
    "one_time_expenses": True,  # Add-back
    "personal_expenses": True,  # Add-back
    "related_party_transactions": True,  # Add-back
    "non_recurring_revenue": False,  # Subtract
    "non_recurring_costs": True,  # Add-back
    "depreciation_adjustment": True,  # Add-back
    "family_expenses": True,  # Add-back
    "unusual_transactions": True,  # Add-back
    "tax_optimization_reversal": True,  # Add-back
    "discretionary_expenses": True,  # Add-back
    "other_adjustments": True,  # Add-back (default)
}


# SDE MULTIPLES BY INDUSTRY (BizBuySell 2024, Pepperdine 2024)
# These are empirically derived from actual small business transactions
# and represent the market's view of value for different industries.
SDE_MULTIPLES_BY_INDUSTRY = {
    # Professional Services - Higher multiples due to recurring revenue potential
    "professional-services": {
        "micro": Decimal("2.0"),  # < EUR 500K
        "small": Decimal("2.3"),  # EUR 500K - 2M
        "lower_middle": Decimal("2.8"),  # EUR 2M - 5M
    },
    "consulting": {
        "micro": Decimal("1.8"),
        "small": Decimal("2.2"),
        "lower_middle": Decimal("2.6"),
    },
    "accounting": {
        "micro": Decimal("2.2"),  # Recurring revenue premium
        "small": Decimal("2.5"),
        "lower_middle": Decimal("3.0"),
    },
    "legal": {
        "micro": Decimal("1.5"),  # High owner dependency discount
        "small": Decimal("1.8"),
        "lower_middle": Decimal("2.2"),
    },
    # Technology & Software
    "technology": {
        "micro": Decimal("2.5"),
        "small": Decimal("3.0"),
        "lower_middle": Decimal("3.5"),
    },
    "saas": {
        "micro": Decimal("3.0"),  # Recurring revenue premium
        "small": Decimal("3.5"),
        "lower_middle": Decimal("4.0"),  # Transitions to EBITDA multiple
    },
    # Healthcare & Medical
    "healthcare": {
        "micro": Decimal("2.0"),
        "small": Decimal("2.5"),
        "lower_middle": Decimal("3.0"),
    },
    "dental": {
        "micro": Decimal("2.0"),
        "small": Decimal("2.3"),
        "lower_middle": Decimal("2.8"),
    },
    "veterinary": {
        "micro": Decimal("2.2"),
        "small": Decimal("2.5"),
        "lower_middle": Decimal("2.8"),
    },
    # Retail & Consumer
    "retail": {
        "micro": Decimal("1.5"),
        "small": Decimal("1.8"),
        "lower_middle": Decimal("2.2"),
    },
    "ecommerce": {
        "micro": Decimal("2.0"),
        "small": Decimal("2.5"),
        "lower_middle": Decimal("3.0"),
    },
    "restaurant": {
        "micro": Decimal("1.2"),  # Low multiples due to risk
        "small": Decimal("1.5"),
        "lower_middle": Decimal("1.8"),
    },
    "food-services": {
        "micro": Decimal("1.3"),
        "small": Decimal("1.6"),
        "lower_middle": Decimal("2.0"),
    },
    # Manufacturing & Industrial
    "manufacturing": {
        "micro": Decimal("1.8"),
        "small": Decimal("2.2"),
        "lower_middle": Decimal("2.5"),
    },
    "construction": {
        "micro": Decimal("1.5"),
        "small": Decimal("1.8"),
        "lower_middle": Decimal("2.2"),
    },
    # Personal & Home Services
    "home-services": {
        "micro": Decimal("1.5"),
        "small": Decimal("1.8"),
        "lower_middle": Decimal("2.2"),
    },
    "beauty-wellness": {
        "micro": Decimal("1.3"),
        "small": Decimal("1.6"),
        "lower_middle": Decimal("2.0"),
    },
    "fitness": {
        "micro": Decimal("1.5"),
        "small": Decimal("1.8"),
        "lower_middle": Decimal("2.2"),
    },
    # Default fallback
    "services": {
        "micro": Decimal("1.8"),
        "small": Decimal("2.0"),
        "lower_middle": Decimal("2.5"),
    },
    "other": {
        "micro": Decimal("1.5"),
        "small": Decimal("1.8"),
        "lower_middle": Decimal("2.2"),
    },
}

OWNER_COMPENSATION_BENCHMARKS = OWNER_COMPENSATION_BY_SIZE
