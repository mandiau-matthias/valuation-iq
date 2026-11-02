"""Static configuration for the business-type triage engine."""

from __future__ import annotations

from decimal import Decimal


def build_business_type_categories(BusinessTypeCategory) -> dict:
    return {
        # SaaS/Software
        "saas-platform": BusinessTypeCategory.SAAS_SOFTWARE,
        "saas": BusinessTypeCategory.SAAS_SOFTWARE,
        "software-development": BusinessTypeCategory.SAAS_SOFTWARE,
        "webdev": BusinessTypeCategory.SAAS_SOFTWARE,
        "app-development": BusinessTypeCategory.SAAS_SOFTWARE,
        "software-consulting": BusinessTypeCategory.SAAS_SOFTWARE,
        "it-services": BusinessTypeCategory.SAAS_SOFTWARE,
        "tech-support": BusinessTypeCategory.SAAS_SOFTWARE,
        # E-commerce
        "ecommerce-platform": BusinessTypeCategory.ECOMMERCE,
        "ecommerce": BusinessTypeCategory.ECOMMERCE,
        "online-store": BusinessTypeCategory.ECOMMERCE,
        "dropshipping": BusinessTypeCategory.ECOMMERCE,
        "marketplace": BusinessTypeCategory.ECOMMERCE,
        "affiliate-marketing": BusinessTypeCategory.ECOMMERCE,
        "digital-products": BusinessTypeCategory.ECOMMERCE,
        # Professional Services
        "consulting-firm": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "consulting": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "marketing-agency": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "accounting-firm": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "accounting": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "legal-services": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "law-firm": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "engineering": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "architecture": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "design-agency": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "pr-agency": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "hr-consulting": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "coaching": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "training": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        # Retail/Food
        "bakery": BusinessTypeCategory.RETAIL_FOOD,
        "restaurant": BusinessTypeCategory.RETAIL_FOOD,
        "catering": BusinessTypeCategory.RETAIL_FOOD,
        "coffee-shop": BusinessTypeCategory.RETAIL_FOOD,
        "food-truck": BusinessTypeCategory.RETAIL_FOOD,
        "brewery": BusinessTypeCategory.RETAIL_FOOD,
        "winery": BusinessTypeCategory.RETAIL_FOOD,
        "retail-store": BusinessTypeCategory.RETAIL_FOOD,
        "retail": BusinessTypeCategory.RETAIL_FOOD,
        "spa": BusinessTypeCategory.RETAIL_FOOD,
        "fitness-studio": BusinessTypeCategory.RETAIL_FOOD,
        "gym": BusinessTypeCategory.RETAIL_FOOD,
        "salon": BusinessTypeCategory.RETAIL_FOOD,
        "barbershop": BusinessTypeCategory.RETAIL_FOOD,
        "boutique": BusinessTypeCategory.RETAIL_FOOD,
        "clothing-store": BusinessTypeCategory.RETAIL_FOOD,
        "jewelry-store": BusinessTypeCategory.RETAIL_FOOD,
        "bookstore": BusinessTypeCategory.RETAIL_FOOD,
        "toy-store": BusinessTypeCategory.RETAIL_FOOD,
        # Manufacturing
        "manufacturing-industrial": BusinessTypeCategory.MANUFACTURING,
        "manufacturing": BusinessTypeCategory.MANUFACTURING,
        "food-manufacturing": BusinessTypeCategory.MANUFACTURING,
        "textile-manufacturing": BusinessTypeCategory.MANUFACTURING,
        # Construction
        "construction": BusinessTypeCategory.CONSTRUCTION,
        "general-contractor": BusinessTypeCategory.CONSTRUCTION,
        "plumbing": BusinessTypeCategory.CONSTRUCTION,
        "electrical": BusinessTypeCategory.CONSTRUCTION,
        "roofing": BusinessTypeCategory.CONSTRUCTION,
        "landscaping": BusinessTypeCategory.CONSTRUCTION,
        # Healthcare
        "healthcare-services": BusinessTypeCategory.HEALTHCARE,
        "healthcare": BusinessTypeCategory.HEALTHCARE,
        "medical-practice": BusinessTypeCategory.HEALTHCARE,
        "dental-practice": BusinessTypeCategory.HEALTHCARE,
        "veterinary": BusinessTypeCategory.HEALTHCARE,
        "pharmacy": BusinessTypeCategory.HEALTHCARE,
        "wellness-center": BusinessTypeCategory.HEALTHCARE,
        # Financial Services
        "fintech": BusinessTypeCategory.FINANCIAL_SERVICES,
        "financial-services": BusinessTypeCategory.FINANCIAL_SERVICES,
        "insurance": BusinessTypeCategory.FINANCIAL_SERVICES,
        "bookkeeping": BusinessTypeCategory.FINANCIAL_SERVICES,
        "tax-preparation": BusinessTypeCategory.FINANCIAL_SERVICES,
        # Real Estate
        "real-estate-services": BusinessTypeCategory.REAL_ESTATE,
        "realestate": BusinessTypeCategory.REAL_ESTATE,
        "property-management": BusinessTypeCategory.REAL_ESTATE,
        "real-estate-investment": BusinessTypeCategory.REAL_ESTATE,
        # Transportation
        "logistics": BusinessTypeCategory.TRANSPORTATION,
        "transportation": BusinessTypeCategory.TRANSPORTATION,
        "delivery": BusinessTypeCategory.TRANSPORTATION,
        "trucking": BusinessTypeCategory.TRANSPORTATION,
        "automotive": BusinessTypeCategory.TRANSPORTATION,
        "auto-repair": BusinessTypeCategory.TRANSPORTATION,
    }


def build_step_execution_rules(BusinessTypeCategory, StepExecutionRule) -> dict:
    return {
        BusinessTypeCategory.SAAS_SOFTWARE: {
            0: StepExecutionRule.ALWAYS,  # Data Quality
            1: StepExecutionRule.ALWAYS,  # Input Validation
            2: StepExecutionRule.ALWAYS,  # Benchmarking
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE Calculation (for micro/small SaaS)
            3: StepExecutionRule.ALWAYS,  # Base EV
            4: StepExecutionRule.CONDITIONAL_DATA,  # Owner Concentration (less critical for SaaS)
            5: StepExecutionRule.ALWAYS,  # Size Discount
            6: StepExecutionRule.ALWAYS,  # Liquidity Discount
            7: StepExecutionRule.ALWAYS,  # EV to Equity
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,  # Confidence Score
            10: StepExecutionRule.ALWAYS,  # Range Methodology
            11: StepExecutionRule.ALWAYS,  # Final Synthesis
        },
        BusinessTypeCategory.PROFESSIONAL_SERVICES: {
            0: StepExecutionRule.ALWAYS,
            1: StepExecutionRule.ALWAYS,
            2: StepExecutionRule.ALWAYS,
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE Calculation (CRITICAL for services)
            3: StepExecutionRule.ALWAYS,
            4: StepExecutionRule.CONDITIONAL_DATA,  # Owner Concentration (CRITICAL for services)
            5: StepExecutionRule.ALWAYS,
            6: StepExecutionRule.ALWAYS,
            7: StepExecutionRule.ALWAYS,
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,
            10: StepExecutionRule.ALWAYS,
            11: StepExecutionRule.ALWAYS,
        },
        BusinessTypeCategory.RETAIL_FOOD: {
            0: StepExecutionRule.ALWAYS,
            1: StepExecutionRule.ALWAYS,
            2: StepExecutionRule.ALWAYS,
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE Calculation
            3: StepExecutionRule.ALWAYS,
            4: StepExecutionRule.CONDITIONAL_DATA,  # Owner Concentration
            5: StepExecutionRule.ALWAYS,
            6: StepExecutionRule.ALWAYS,
            7: StepExecutionRule.ALWAYS,
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,
            10: StepExecutionRule.ALWAYS,
            11: StepExecutionRule.ALWAYS,
        },
        BusinessTypeCategory.MANUFACTURING: {
            0: StepExecutionRule.ALWAYS,
            1: StepExecutionRule.ALWAYS,
            2: StepExecutionRule.ALWAYS,
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE for smaller manufacturers
            3: StepExecutionRule.ALWAYS,
            4: StepExecutionRule.CONDITIONAL_DATA,
            5: StepExecutionRule.ALWAYS,
            6: StepExecutionRule.ALWAYS,
            7: StepExecutionRule.ALWAYS,
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,
            10: StepExecutionRule.ALWAYS,
            11: StepExecutionRule.ALWAYS,
        },
        BusinessTypeCategory.CONSTRUCTION: {
            0: StepExecutionRule.ALWAYS,
            1: StepExecutionRule.ALWAYS,
            2: StepExecutionRule.ALWAYS,
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE for small contractors
            3: StepExecutionRule.ALWAYS,
            4: StepExecutionRule.CONDITIONAL_DATA,
            5: StepExecutionRule.ALWAYS,
            6: StepExecutionRule.ALWAYS,
            7: StepExecutionRule.ALWAYS,
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,
            10: StepExecutionRule.ALWAYS,
            11: StepExecutionRule.ALWAYS,
        },
        BusinessTypeCategory.ECOMMERCE: {
            0: StepExecutionRule.ALWAYS,
            1: StepExecutionRule.ALWAYS,
            2: StepExecutionRule.ALWAYS,
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE for smaller e-commerce
            3: StepExecutionRule.ALWAYS,
            4: StepExecutionRule.CONDITIONAL_DATA,
            5: StepExecutionRule.ALWAYS,
            6: StepExecutionRule.ALWAYS,
            7: StepExecutionRule.ALWAYS,
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,
            10: StepExecutionRule.ALWAYS,
            11: StepExecutionRule.ALWAYS,
        },
        BusinessTypeCategory.HEALTHCARE: {
            0: StepExecutionRule.ALWAYS,
            1: StepExecutionRule.ALWAYS,
            2: StepExecutionRule.ALWAYS,
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE for medical practices
            3: StepExecutionRule.ALWAYS,
            4: StepExecutionRule.CONDITIONAL_DATA,
            5: StepExecutionRule.ALWAYS,
            6: StepExecutionRule.ALWAYS,
            7: StepExecutionRule.ALWAYS,
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,
            10: StepExecutionRule.ALWAYS,
            11: StepExecutionRule.ALWAYS,
        },
        BusinessTypeCategory.FINANCIAL_SERVICES: {
            0: StepExecutionRule.ALWAYS,
            1: StepExecutionRule.ALWAYS,
            2: StepExecutionRule.ALWAYS,
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE for small practices
            3: StepExecutionRule.ALWAYS,
            4: StepExecutionRule.CONDITIONAL_DATA,
            5: StepExecutionRule.ALWAYS,
            6: StepExecutionRule.ALWAYS,
            7: StepExecutionRule.ALWAYS,
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,
            10: StepExecutionRule.ALWAYS,
            11: StepExecutionRule.ALWAYS,
        },
        BusinessTypeCategory.REAL_ESTATE: {
            0: StepExecutionRule.ALWAYS,
            1: StepExecutionRule.ALWAYS,
            2: StepExecutionRule.ALWAYS,
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE for small agencies
            3: StepExecutionRule.ALWAYS,
            4: StepExecutionRule.CONDITIONAL_DATA,
            5: StepExecutionRule.ALWAYS,
            6: StepExecutionRule.ALWAYS,
            7: StepExecutionRule.ALWAYS,
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,
            10: StepExecutionRule.ALWAYS,
            11: StepExecutionRule.ALWAYS,
        },
        BusinessTypeCategory.TRANSPORTATION: {
            0: StepExecutionRule.ALWAYS,
            1: StepExecutionRule.ALWAYS,
            2: StepExecutionRule.ALWAYS,
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE for owner-operators
            3: StepExecutionRule.ALWAYS,
            4: StepExecutionRule.CONDITIONAL_DATA,
            5: StepExecutionRule.ALWAYS,
            6: StepExecutionRule.ALWAYS,
            7: StepExecutionRule.ALWAYS,
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,
            10: StepExecutionRule.ALWAYS,
            11: StepExecutionRule.ALWAYS,
        },
        BusinessTypeCategory.OTHER: {
            # Default rules for unknown business types
            0: StepExecutionRule.ALWAYS,
            1: StepExecutionRule.ALWAYS,
            2: StepExecutionRule.ALWAYS,
            2.7: StepExecutionRule.CONDITIONAL_SDE,  # SDE for small businesses
            3: StepExecutionRule.ALWAYS,
            4: StepExecutionRule.CONDITIONAL_DATA,
            5: StepExecutionRule.ALWAYS,
            6: StepExecutionRule.ALWAYS,
            7: StepExecutionRule.ALWAYS,
            8: StepExecutionRule.CONDITIONAL_DATA,  # Ownership Adjustment (requires shares_for_sale < 100%)
            9: StepExecutionRule.ALWAYS,
            10: StepExecutionRule.ALWAYS,
            11: StepExecutionRule.ALWAYS,
        },
    }


def build_size_discount_adjustments(BusinessTypeCategory) -> dict:
    return {
        BusinessTypeCategory.SAAS_SOFTWARE: {
            "micro_multiplier": Decimal("0.9"),  # Less discount for SaaS (growth potential)
            "small_multiplier": Decimal("0.95"),
            "mid_multiplier": Decimal("1.0"),
        },
        BusinessTypeCategory.PROFESSIONAL_SERVICES: {
            "micro_multiplier": Decimal("1.1"),  # More discount (owner dependency)
            "small_multiplier": Decimal("1.05"),
            "mid_multiplier": Decimal("1.0"),
        },
        BusinessTypeCategory.RETAIL_FOOD: {
            "micro_multiplier": Decimal("1.0"),  # Standard
            "small_multiplier": Decimal("1.0"),
            "mid_multiplier": Decimal("1.0"),
        },
        BusinessTypeCategory.MANUFACTURING: {
            "micro_multiplier": Decimal("1.0"),
            "small_multiplier": Decimal("1.0"),
            "mid_multiplier": Decimal("1.0"),
        },
        BusinessTypeCategory.ECOMMERCE: {
            "micro_multiplier": Decimal("0.95"),  # Less discount (scalable, growth potential)
            "small_multiplier": Decimal("0.98"),
            "mid_multiplier": Decimal("1.0"),
        },
        BusinessTypeCategory.CONSTRUCTION: {
            "micro_multiplier": Decimal(
                "1.05"
            ),  # More discount (project volatility, owner dependency)
            "small_multiplier": Decimal("1.02"),
            "mid_multiplier": Decimal("1.0"),
        },
        BusinessTypeCategory.HEALTHCARE: {
            "micro_multiplier": Decimal("1.0"),  # Standard (regulatory risk balanced by stability)
            "small_multiplier": Decimal("1.0"),
            "mid_multiplier": Decimal("1.0"),
        },
        BusinessTypeCategory.FINANCIAL_SERVICES: {
            "micro_multiplier": Decimal("1.0"),  # Standard (regulatory risk balanced by stability)
            "small_multiplier": Decimal("1.0"),
            "mid_multiplier": Decimal("1.0"),
        },
        BusinessTypeCategory.REAL_ESTATE: {
            "micro_multiplier": Decimal("1.0"),  # Standard (asset-backed, moderate risk)
            "small_multiplier": Decimal("1.0"),
            "mid_multiplier": Decimal("1.0"),
        },
        BusinessTypeCategory.TRANSPORTATION: {
            "micro_multiplier": Decimal("1.0"),  # Standard (operational risk, moderate)
            "small_multiplier": Decimal("1.0"),
            "mid_multiplier": Decimal("1.0"),
        },
        BusinessTypeCategory.OTHER: {
            "micro_multiplier": Decimal("1.0"),  # Default (no adjustment)
            "small_multiplier": Decimal("1.0"),
            "mid_multiplier": Decimal("1.0"),
        },
    }


def build_liquidity_discount_adjustments(BusinessTypeCategory) -> dict:
    return {
        BusinessTypeCategory.SAAS_SOFTWARE: {
            "base_discount": -Decimal("0.12"),  # Less discount (easier to sell SaaS, recurring revenue)
            "high_margin_bonus": Decimal("0.03"),
        },
        BusinessTypeCategory.PROFESSIONAL_SERVICES: {
            "base_discount": -Decimal("0.18"),  # More discount (harder to sell, owner-dependent)
            "high_margin_bonus": Decimal("0.02"),
        },
        BusinessTypeCategory.RETAIL_FOOD: {
            "base_discount": -Decimal("0.15"),  # Standard (location-dependent)
            "high_margin_bonus": Decimal("0.02"),
        },
        BusinessTypeCategory.MANUFACTURING: {
            "base_discount": -Decimal("0.16"),  # Asset-heavy, moderate discount
            "high_margin_bonus": Decimal("0.02"),
        },
        BusinessTypeCategory.ECOMMERCE: {
            "base_discount": -Decimal("0.13"),  # Between SaaS and Retail (scalable, moderate liquidity)
            "high_margin_bonus": Decimal("0.025"),
        },
        BusinessTypeCategory.CONSTRUCTION: {
            "base_discount": -Decimal("0.17"),  # Project-based volatility, moderate liquidity
            "high_margin_bonus": Decimal("0.02"),
        },
        BusinessTypeCategory.HEALTHCARE: {
            "base_discount": -Decimal("0.16"),  # Regulatory stability balanced by complexity
            "high_margin_bonus": Decimal("0.02"),
        },
        BusinessTypeCategory.FINANCIAL_SERVICES: {
            "base_discount": -Decimal("0.17"),  # Regulatory requirements, lower liquidity
            "high_margin_bonus": Decimal("0.02"),
        },
        BusinessTypeCategory.REAL_ESTATE: {
            "base_discount": -Decimal("0.16"),  # Asset-backed, moderate liquidity
            "high_margin_bonus": Decimal("0.02"),
        },
        BusinessTypeCategory.TRANSPORTATION: {
            "base_discount": -Decimal("0.16"),  # Operational complexity, moderate liquidity
            "high_margin_bonus": Decimal("0.02"),
        },
        BusinessTypeCategory.OTHER: {
            "base_discount": -Decimal("0.15"),  # Default standard
            "high_margin_bonus": Decimal("0.02"),
        },
    }


def build_category_id_to_enum(BusinessTypeCategory) -> dict:
    return {
        # Creative & Media
        "creative-media": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "creative_media": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        # Professional Services
        "professional-services": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "professional_services": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        # Technology & SaaS
        "technology": BusinessTypeCategory.SAAS_SOFTWARE,
        "saas-software": BusinessTypeCategory.SAAS_SOFTWARE,
        "saas_software": BusinessTypeCategory.SAAS_SOFTWARE,
        "tech-digital": BusinessTypeCategory.SAAS_SOFTWARE,
        "tech_digital": BusinessTypeCategory.SAAS_SOFTWARE,
        # E-commerce
        "ecommerce": BusinessTypeCategory.ECOMMERCE,
        "e-commerce": BusinessTypeCategory.ECOMMERCE,
        # Food & Beverage / Hospitality
        "food-beverage": BusinessTypeCategory.RETAIL_FOOD,
        "food_beverage": BusinessTypeCategory.RETAIL_FOOD,
        "hospitality": BusinessTypeCategory.RETAIL_FOOD,
        "food-services": BusinessTypeCategory.RETAIL_FOOD,
        "food_services": BusinessTypeCategory.RETAIL_FOOD,
        # Retail
        "retail": BusinessTypeCategory.RETAIL_FOOD,
        # Healthcare
        "healthcare": BusinessTypeCategory.HEALTHCARE,
        "health-wellness": BusinessTypeCategory.HEALTHCARE,
        "health_wellness": BusinessTypeCategory.HEALTHCARE,
        # Financial Services
        "financial-services": BusinessTypeCategory.FINANCIAL_SERVICES,
        "financial_services": BusinessTypeCategory.FINANCIAL_SERVICES,
        "finance": BusinessTypeCategory.FINANCIAL_SERVICES,
        # Real Estate
        "real-estate": BusinessTypeCategory.REAL_ESTATE,
        "real_estate": BusinessTypeCategory.REAL_ESTATE,
        # Manufacturing
        "manufacturing": BusinessTypeCategory.MANUFACTURING,
        # Construction
        "construction": BusinessTypeCategory.CONSTRUCTION,
        "home-services": BusinessTypeCategory.CONSTRUCTION,
        "home_services": BusinessTypeCategory.CONSTRUCTION,
        # Transportation
        "transportation": BusinessTypeCategory.TRANSPORTATION,
        "logistics": BusinessTypeCategory.TRANSPORTATION,
        # Education
        "education": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        # Beauty & Wellness
        "beauty-wellness": BusinessTypeCategory.RETAIL_FOOD,
        "beauty_wellness": BusinessTypeCategory.RETAIL_FOOD,
        # Fitness
        "fitness": BusinessTypeCategory.RETAIL_FOOD,
        # Events & Entertainment
        "events-entertainment": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "events_entertainment": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        # Pet Services
        "pet-services": BusinessTypeCategory.RETAIL_FOOD,
        "pet_services": BusinessTypeCategory.RETAIL_FOOD,
        # Automotive
        "automotive": BusinessTypeCategory.TRANSPORTATION,
        # Agriculture
        "agriculture": BusinessTypeCategory.MANUFACTURING,
        # Arts & Crafts
        "arts-crafts": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "arts_crafts": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        # Security
        "security": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        # Environmental
        "environmental": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        # Repair & Maintenance
        "repair-maintenance": BusinessTypeCategory.CONSTRUCTION,
        "repair_maintenance": BusinessTypeCategory.CONSTRUCTION,
        # synced_business_types.json category_ids
        "home-property": BusinessTypeCategory.CONSTRUCTION,
        "home_property": BusinessTypeCategory.CONSTRUCTION,
        "education-training": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "education_training": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "ecommerce-retail": BusinessTypeCategory.ECOMMERCE,
        "ecommerce_retail": BusinessTypeCategory.ECOMMERCE,
        "fitness-health": BusinessTypeCategory.HEALTHCARE,
        "fitness_health": BusinessTypeCategory.HEALTHCARE,
        "transportation-logistics": BusinessTypeCategory.TRANSPORTATION,
        "transportation_logistics": BusinessTypeCategory.TRANSPORTATION,
        "cleaning-maintenance": BusinessTypeCategory.CONSTRUCTION,
        "cleaning_maintenance": BusinessTypeCategory.CONSTRUCTION,
        "media-entertainment": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "media_entertainment": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "personal-services": BusinessTypeCategory.RETAIL_FOOD,
        "personal_services": BusinessTypeCategory.RETAIL_FOOD,
        "business-services": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "business_services": BusinessTypeCategory.PROFESSIONAL_SERVICES,
        "it-services": BusinessTypeCategory.SAAS_SOFTWARE,
        "it_services": BusinessTypeCategory.SAAS_SOFTWARE,
    }
