from src.utils.exceptions import BusinessTypeError, MultiplesCalculationError

"""
Industry Mappings for Business Type Methodology Selection

This module contains industry-specific mappings and characteristics
for determining optimal valuation methodologies.
"""

from typing import Dict, List, Optional, Any
from src.utils.logging import get_logger
from .methodology_types import (
    ValuationMethodology,
    BusinessCategory,
    AssetIntensity,
    GrowthPotential,
    RevenuePredictability,
    IndustryFactors
)

logger = get_logger(__name__)


class IndustryMappings:
    """
    Industry-specific mappings and characteristics.

    Provides industry-specific rules and characteristics for
    methodology selection and business analysis.
    """

    def __init__(self):
        """Initialize industry mappings"""
        self.logger = logger
        self.industry_mappings = self._initialize_industry_mappings()
        self.business_type_categories = self._initialize_business_categories()

    def _initialize_industry_mappings(self) -> Dict[str, IndustryFactors]:
        """Initialize industry-specific mappings"""
        return {
            "food_beverage": IndustryFactors(
                industry_name="Food & Beverage",
                typical_asset_intensity=AssetIntensity.MEDIUM,
                growth_characteristics=GrowthPotential.MEDIUM,
                revenue_patterns=RevenuePredictability.HIGH,
                key_valuation_drivers=["location", "reputation", "operational_efficiency", "brand_value"],
                common_multiple_types=["revenue", "ebitda", "sales_per_sqft"],
                methodology_preferences=[ValuationMethodology.MULTIPLES, ValuationMethodology.DCF]
            ),

            "technology": IndustryFactors(
                industry_name="Technology",
                typical_asset_intensity=AssetIntensity.LOW,
                growth_characteristics=GrowthPotential.HIGH,
                revenue_patterns=RevenuePredictability.MEDIUM,
                key_valuation_drivers=["user_base", "recurring_revenue", "growth_rate", "market_penetration"],
                common_multiple_types=["arr", "revenue", "user_metrics"],
                methodology_preferences=[ValuationMethodology.ARR_MULTIPLES, ValuationMethodology.DCF]
            ),

            "healthcare": IndustryFactors(
                industry_name="Healthcare",
                typical_asset_intensity=AssetIntensity.MEDIUM,
                growth_characteristics=GrowthPotential.MEDIUM,
                revenue_patterns=RevenuePredictability.HIGH,
                key_valuation_drivers=["patient_base", "specialization", "regulatory_compliance", "reputation"],
                common_multiple_types=["revenue", "ebitda", "patient_metrics"],
                methodology_preferences=[ValuationMethodology.DCF, ValuationMethodology.MULTIPLES]
            ),

            "manufacturing": IndustryFactors(
                industry_name="Manufacturing",
                typical_asset_intensity=AssetIntensity.HIGH,
                growth_characteristics=GrowthPotential.MEDIUM,
                revenue_patterns=RevenuePredictability.MEDIUM,
                key_valuation_drivers=["production_capacity", "equipment_value", "supply_chain", "efficiency"],
                common_multiple_types=["revenue", "ebitda", "asset_value"],
                methodology_preferences=[ValuationMethodology.DCF, ValuationMethodology.ASSET_BASED]
            ),

            "services": IndustryFactors(
                industry_name="Professional Services",
                typical_asset_intensity=AssetIntensity.LOW,
                growth_characteristics=GrowthPotential.MEDIUM,
                revenue_patterns=RevenuePredictability.HIGH,
                key_valuation_drivers=["client_base", "reputation", "talent", "specialization"],
                common_multiple_types=["revenue", "ebitda", "client_metrics"],
                methodology_preferences=[ValuationMethodology.MULTIPLES, ValuationMethodology.DCF]
            ),

            "retail": IndustryFactors(
                industry_name="Retail",
                typical_asset_intensity=AssetIntensity.MEDIUM,
                growth_characteristics=GrowthPotential.MEDIUM,
                revenue_patterns=RevenuePredictability.MEDIUM,
                key_valuation_drivers=["location", "inventory", "brand", "customer_traffic"],
                common_multiple_types=["revenue", "ebitda", "sales_per_sqft"],
                methodology_preferences=[ValuationMethodology.MULTIPLES, ValuationMethodology.DCF]
            ),

            "real_estate": IndustryFactors(
                industry_name="Real Estate",
                typical_asset_intensity=AssetIntensity.HIGH,
                growth_characteristics=GrowthPotential.LOW,
                revenue_patterns=RevenuePredictability.HIGH,
                key_valuation_drivers=["property_value", "location", "rental_income", "market_conditions"],
                common_multiple_types=["revenue", "asset_value", "rental_yield"],
                methodology_preferences=[ValuationMethodology.ASSET_BASED, ValuationMethodology.DCF]
            ),

            "construction": IndustryFactors(
                industry_name="Construction",
                typical_asset_intensity=AssetIntensity.HIGH,
                growth_characteristics=GrowthPotential.MEDIUM,
                revenue_patterns=RevenuePredictability.LOW,
                key_valuation_drivers=["equipment_value", "project_pipeline", "reputation", "safety_record"],
                common_multiple_types=["revenue", "ebitda", "project_value"],
                methodology_preferences=[ValuationMethodology.DCF, ValuationMethodology.ASSET_BASED]
            )
        }

    def _initialize_business_categories(self) -> Dict[str, str]:
        """Initialize business type to category mappings"""
        return {
            # Food & Beverage
            'restaurant': 'food_beverage',
            'catering': 'food_beverage',
            'brewery': 'food_beverage',
            'coffee_shop': 'food_beverage',
            'food_truck': 'food_beverage',
            'bakery': 'food_beverage',
            'bar': 'food_beverage',
            'food_delivery': 'food_beverage',
            'food_manufacturing': 'food_beverage',
            'wine_production': 'food_beverage',
            'distillery': 'food_beverage',
            'food_retail': 'food_beverage',
            'food_wholesale': 'food_beverage',
            'food_service': 'food_beverage',
            'food_consulting': 'food_beverage',

            # Technology
            'saas': 'technology',
            'software': 'technology',
            'mobile_app': 'technology',
            'ecommerce': 'technology',
            'web_development': 'technology',
            'it_consulting': 'technology',
            'cybersecurity': 'technology',
            'data_analytics': 'technology',
            'artificial_intelligence': 'technology',
            'blockchain': 'technology',
            'fintech': 'technology',
            'edtech': 'technology',
            'healthtech': 'technology',
            'proptech': 'technology',
            'gaming': 'technology',

            # Healthcare
            'medical_practice': 'healthcare',
            'dental_practice': 'healthcare',
            'veterinary': 'healthcare',
            'pharmacy': 'healthcare',
            'medical_device': 'healthcare',
            'healthcare_consulting': 'healthcare',
            'telemedicine': 'healthcare',
            'mental_health': 'healthcare',
            'physical_therapy': 'healthcare',
            'home_healthcare': 'healthcare',
            'medical_laboratory': 'healthcare',
            'healthcare_technology': 'healthcare',
            'medical_equipment': 'healthcare',
            'healthcare_facilities': 'healthcare',
            'healthcare_services': 'healthcare',

            # Manufacturing
            'manufacturing': 'manufacturing',
            'automotive': 'manufacturing',
            'electronics': 'manufacturing',
            'textiles': 'manufacturing',
            'chemicals': 'manufacturing',
            'machinery': 'manufacturing',
            'aerospace': 'manufacturing',
            'pharmaceuticals': 'manufacturing',
            'food_processing': 'manufacturing',
            'metalworking': 'manufacturing',
            'plastics': 'manufacturing',
            'furniture': 'manufacturing',
            'apparel': 'manufacturing',
            'packaging': 'manufacturing',
            'industrial_equipment': 'manufacturing',

            # Services
            'consulting': 'services',
            'legal': 'services',
            'accounting': 'services',
            'marketing': 'services',
            'advertising': 'services',
            'public_relations': 'services',
            'human_resources': 'services',
            'financial_services': 'services',
            'insurance': 'services',
            'real_estate_services': 'services',
            'travel_services': 'services',
            'event_planning': 'services',
            'cleaning_services': 'services',
            'security_services': 'services',
            'logistics': 'services',

            # Retail
            'retail': 'retail',
            'fashion': 'retail',
            'electronics_retail': 'retail',
            'home_garden': 'retail',
            'automotive_retail': 'retail',
            'beauty_cosmetics': 'retail',
            'sports_recreation': 'retail',
            'books_media': 'retail',
            'jewelry': 'retail',
            'furniture_retail': 'retail',
            'grocery': 'retail',
            'pharmacy_retail': 'retail',
            'convenience_store': 'retail',
            'department_store': 'retail',
            'specialty_store': 'retail',

            # Real Estate
            'real_estate': 'real_estate',
            'property_development': 'real_estate',
            'property_management': 'real_estate',
            'real_estate_investment': 'real_estate',
            'commercial_real_estate': 'real_estate',
            'residential_real_estate': 'real_estate',
            'real_estate_brokerage': 'real_estate',
            'real_estate_consulting': 'real_estate',
            'real_estate_finance': 'real_estate',
            'real_estate_technology': 'real_estate',
            'real_estate_valuation': 'real_estate',
            'real_estate_legal': 'real_estate',
            'real_estate_marketing': 'real_estate',
            'real_estate_construction': 'real_estate',
            'real_estate_services': 'real_estate',

            # Construction
            'construction': 'construction',
            'residential_construction': 'construction',
            'commercial_construction': 'construction',
            'industrial_construction': 'construction',
            'infrastructure': 'construction',
            'renovation': 'construction',
            'electrical': 'construction',
            'plumbing': 'construction',
            'hvac': 'construction',
            'roofing': 'construction',
            'landscaping': 'construction',
            'concrete': 'construction',
            'steel': 'construction',
            'construction_equipment': 'construction',
            'construction_services': 'construction'
        }

    def get_industry_factors(self, business_type: str) -> Optional[IndustryFactors]:
        """Get industry factors for a business type"""
        try:
            # Get category for business type
            category = self.business_type_categories.get(business_type.lower())

            if not category:
                return None

            # Get industry factors
            return self.industry_mappings.get(category)

        except BusinessTypeError as e:
            self.logger.error(f"Error getting industry factors: {e}")
            return None

    def get_business_category(self, business_type: str) -> str:
        """Get business category for a business type"""
        return self.business_type_categories.get(business_type.lower(), 'other')

    def get_industry_characteristics(self, industry: str) -> Dict[str, Any]:
        """Get characteristics for an industry"""
        try:
            factors = self.industry_mappings.get(industry)

            if not factors:
                return {
                    'industry_name': industry,
                    'asset_intensity': 'medium',
                    'growth_potential': 'medium',
                    'revenue_predictability': 'medium',
                    'key_drivers': ['revenue', 'profitability'],
                    'multiple_types': ['revenue', 'ebitda'],
                    'methodology_preferences': ['multiples', 'dcf']
                }

            return {
                'industry_name': factors.industry_name,
                'asset_intensity': factors.typical_asset_intensity.value,
                'growth_potential': factors.growth_characteristics.value,
                'revenue_predictability': factors.revenue_patterns.value,
                'key_drivers': factors.key_valuation_drivers,
                'multiple_types': factors.common_multiple_types,
                'methodology_preferences': [m.value for m in factors.methodology_preferences]
            }

        except MultiplesCalculationError as e:
            self.logger.error(f"Error getting industry characteristics: {e}")
            return {}

    def get_industry_specific_considerations(self, industry: str) -> List[str]:
        """Get industry-specific considerations for valuation"""
        try:
            factors = self.industry_mappings.get(industry)

            if not factors:
                return ['market_conditions', 'competitive_position']

            # Generate considerations based on industry factors
            considerations = []

            if factors.typical_asset_intensity == AssetIntensity.HIGH:
                considerations.append('asset_depreciation')
                considerations.append('equipment_maintenance')

            if factors.growth_characteristics == GrowthPotential.HIGH:
                considerations.append('growth_sustainability')
                considerations.append('market_expansion')

            if factors.revenue_patterns == RevenuePredictability.LOW:
                considerations.append('revenue_volatility')
                considerations.append('seasonal_variations')

            # Add industry-specific considerations
            if industry == 'technology':
                considerations.extend(['intellectual_property', 'market_penetration', 'user_acquisition'])
            elif industry == 'healthcare':
                considerations.extend(['regulatory_compliance', 'patient_retention', 'medical_liability'])
            elif industry == 'manufacturing':
                considerations.extend(['supply_chain_risks', 'equipment_efficiency', 'production_capacity'])
            elif industry == 'services':
                considerations.extend(['key_person_risk', 'client_retention', 'talent_retention'])

            return considerations

        except MultiplesCalculationError as e:
            self.logger.error(f"Error getting industry considerations: {e}")
            return ['market_conditions', 'competitive_position']

    def get_optimal_multiple_types(self, business_type: str) -> List[str]:
        """Get optimal multiple types for a business type"""
        try:
            category = self.get_business_category(business_type)
            factors = self.industry_mappings.get(category)

            if not factors:
                return ['revenue', 'ebitda']

            return factors.common_multiple_types

        except MultiplesCalculationError as e:
            self.logger.error(f"Error getting optimal multiple types: {e}")
            return ['revenue', 'ebitda']

    def get_key_valuation_drivers(self, business_type: str) -> List[str]:
        """Get key valuation drivers for a business type"""
        try:
            category = self.get_business_category(business_type)
            factors = self.industry_mappings.get(category)

            if not factors:
                return ['revenue', 'profitability', 'market_position']

            return factors.key_valuation_drivers

        except BusinessTypeError as e:
            self.logger.error(f"Error getting key valuation drivers: {e}")
            return ['revenue', 'profitability', 'market_position']
