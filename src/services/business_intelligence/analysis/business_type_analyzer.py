"""
Business Type Analyzer

Analyzes business types and provides detailed characteristics and insights
for methodology selection.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, List, Optional, Any
from src.utils.logging import get_logger
from ..integration.mapper_types import (
    BusinessCharacteristics, BusinessCategory, AssetIntensity, 
    GrowthPotential, RevenuePredictability, BUSINESS_CATEGORIES,
    ValuationMethodology
)

logger = get_logger(__name__)


class BusinessTypeAnalyzer:
    """Analyzes business types and provides characteristics"""

    def __init__(self):
        self.business_type_map = self._build_business_type_mapping()

    def _build_business_type_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Build comprehensive mapping of business types to characteristics"""
        return {
            # =============================================================================
            # FOOD & BEVERAGE (15 types)
            # =============================================================================
            'restaurant': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'medium',
                'key_factors': ['location', 'seating_capacity', 'reputation', 'lease_terms'],
                'special_considerations': ['seasonality', 'local_competition', 'food_costs'],
                'growth_weighted': False,
                'reasoning': 'Restaurants are asset-light with predictable revenue streams, making multiples most appropriate'
            },
            'catering': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.ASSET_BASED,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['client_base', 'equipment', 'staff_quality', 'reputation'],
                'special_considerations': ['event_seasonality', 'client_retention', 'equipment_value'],
                'growth_weighted': False,
                'reasoning': 'Catering businesses rely on equipment and client relationships, suitable for multiples with asset backup'
            },
            'brewery': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['equipment_value', 'distribution_network', 'brand_value', 'production_capacity'],
                'special_considerations': ['brewer_requirement', 'regulatory_compliance', 'distribution_contracts'],
                'growth_weighted': True,
                'reasoning': 'Breweries have significant equipment value and recurring distribution revenue, requiring DCF with multiples validation'
            },
            'coffee_shop': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'medium',
                'key_factors': ['location', 'foot_traffic', 'brand', 'lease_terms'],
                'special_considerations': ['morning_rush', 'local_competition', 'equipment_maintenance'],
                'growth_weighted': False,
                'reasoning': 'Coffee shops are location-dependent with predictable daily revenue patterns'
            },
            'food_truck': {
                'primary': ValuationMethodology.ASSET_BASED,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue'],
                'asset_intensity': 'high',
                'key_factors': ['truck_value', 'equipment', 'permits', 'route_quality'],
                'special_considerations': ['weather_dependency', 'permit_costs', 'fuel_costs'],
                'growth_weighted': False,
                'reasoning': 'Food trucks are highly asset-dependent with mobile operations'
            },
            'bakery': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.ASSET_BASED,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'medium',
                'key_factors': ['equipment', 'location', 'product_quality', 'wholesale_contracts'],
                'special_considerations': ['early_hours', 'ingredient_costs', 'equipment_maintenance'],
                'growth_weighted': False,
                'reasoning': 'Bakeries combine equipment value with recurring revenue streams'
            },
            'bar': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'medium',
                'key_factors': ['location', 'licenses', 'inventory', 'atmosphere'],
                'special_considerations': ['licensing_costs', 'inventory_management', 'peak_hours'],
                'growth_weighted': False,
                'reasoning': 'Bars are location-dependent with predictable revenue patterns'
            },
            'winery': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.ASSET_BASED,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['vineyard_value', 'equipment', 'brand', 'distribution'],
                'special_considerations': ['harvest_cycles', 'aging_inventory', 'regulatory_compliance'],
                'growth_weighted': True,
                'reasoning': 'Wineries have significant land and equipment value with long-term revenue cycles'
            },
            'distillery': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.ASSET_BASED,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['equipment', 'licenses', 'brand', 'distribution'],
                'special_considerations': ['aging_process', 'regulatory_compliance', 'equipment_specialization'],
                'growth_weighted': True,
                'reasoning': 'Distilleries require significant equipment investment and have long production cycles'
            },
            'food_delivery': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['delivery_network', 'technology', 'restaurant_partnerships', 'market_share'],
                'special_considerations': ['commission_rates', 'driver_costs', 'market_competition'],
                'growth_weighted': True,
                'reasoning': 'Food delivery is technology-driven with network effects and growth potential'
            },

            # =============================================================================
            # TECHNOLOGY & SOFTWARE (20 types)
            # =============================================================================
            'saas': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.ARR_MULTIPLES,
                'multiple_types': ['arr', 'mrr', 'revenue'],
                'asset_intensity': 'low',
                'key_factors': ['arr', 'churn_rate', 'growth_rate', 'customer_acquisition_cost'],
                'special_considerations': ['recurring_revenue', 'scalability', 'market_size'],
                'growth_weighted': True,
                'reasoning': 'SaaS businesses have predictable recurring revenue and high growth potential, ideal for DCF with ARR multiples'
            },
            'mobile_app': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'user_base'],
                'asset_intensity': 'low',
                'key_factors': ['user_growth', 'monetization', 'retention', 'market_size'],
                'special_considerations': ['platform_dependency', 'user_acquisition', 'viral_coefficient'],
                'growth_weighted': True,
                'reasoning': 'Mobile apps have high growth potential and network effects'
            },
            'ecommerce': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'medium',
                'key_factors': ['inventory', 'brand', 'customer_base', 'logistics'],
                'special_considerations': ['seasonality', 'inventory_management', 'shipping_costs'],
                'growth_weighted': False,
                'reasoning': 'E-commerce combines inventory assets with revenue growth potential'
            },
            'marketplace': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'gmv'],
                'asset_intensity': 'low',
                'key_factors': ['network_effects', 'take_rate', 'user_growth', 'market_size'],
                'special_considerations': ['chicken_egg_problem', 'scalability', 'competition'],
                'growth_weighted': True,
                'reasoning': 'Marketplaces have network effects and high growth potential'
            },
            'fintech': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['regulatory_compliance', 'user_base', 'revenue_per_user', 'market_size'],
                'special_considerations': ['regulatory_risk', 'scalability', 'trust_factors'],
                'growth_weighted': True,
                'reasoning': 'Fintech has high growth potential but regulatory complexity'
            },
            'ai_ml': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['technology_advantage', 'data_assets', 'talent', 'market_size'],
                'special_considerations': ['technology_risk', 'talent_retention', 'scalability'],
                'growth_weighted': True,
                'reasoning': 'AI/ML businesses have high growth potential and technology moats'
            },
            'cybersecurity': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['technology', 'customer_base', 'recurring_revenue', 'market_size'],
                'special_considerations': ['threat_landscape', 'compliance', 'talent_shortage'],
                'growth_weighted': True,
                'reasoning': 'Cybersecurity has strong recurring revenue and growth potential'
            },
            'blockchain': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'token_value'],
                'asset_intensity': 'low',
                'key_factors': ['technology', 'adoption', 'tokenomics', 'market_size'],
                'special_considerations': ['regulatory_uncertainty', 'volatility', 'adoption_risk'],
                'growth_weighted': True,
                'reasoning': 'Blockchain businesses have high growth potential but regulatory uncertainty'
            },
            'gaming': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'user_base'],
                'asset_intensity': 'low',
                'key_factors': ['user_engagement', 'monetization', 'content_pipeline', 'market_size'],
                'special_considerations': ['hit_dependency', 'platform_risk', 'user_acquisition'],
                'growth_weighted': True,
                'reasoning': 'Gaming has high growth potential but hit-driven nature'
            },
            'edtech': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'user_base'],
                'asset_intensity': 'low',
                'key_factors': ['content_quality', 'user_engagement', 'market_size', 'recurring_revenue'],
                'special_considerations': ['adoption_cycles', 'content_creation', 'market_education'],
                'growth_weighted': True,
                'reasoning': 'EdTech has strong growth potential with recurring revenue models'
            },

            # =============================================================================
            # MANUFACTURING & INDUSTRIAL (15 types)
            # =============================================================================
            'manufacturing': {
                'primary': ValuationMethodology.ASSET_BASED,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['equipment', 'inventory', 'facilities', 'supply_chain'],
                'special_considerations': ['equipment_age', 'maintenance_costs', 'raw_material_costs'],
                'growth_weighted': False,
                'reasoning': 'Manufacturing is asset-intensive with significant equipment and inventory value'
            },
            'automotive': {
                'primary': ValuationMethodology.ASSET_BASED,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['equipment', 'inventory', 'facilities', 'supplier_relationships'],
                'special_considerations': ['equipment_specialization', 'inventory_management', 'regulatory_compliance'],
                'growth_weighted': False,
                'reasoning': 'Automotive manufacturing is highly asset-intensive with specialized equipment'
            },
            'textiles': {
                'primary': ValuationMethodology.ASSET_BASED,
                'secondary': ValuationMethodology.MULTIPLES,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['machinery', 'inventory', 'facilities', 'labor_costs'],
                'special_considerations': ['equipment_age', 'fashion_cycles', 'labor_intensity'],
                'growth_weighted': False,
                'reasoning': 'Textile manufacturing requires significant machinery and inventory investment'
            },
            'electronics': {
                'primary': ValuationMethodology.ASSET_BASED,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['equipment', 'technology', 'inventory', 'supply_chain'],
                'special_considerations': ['technology_obsolescence', 'inventory_management', 'supply_chain_risk'],
                'growth_weighted': False,
                'reasoning': 'Electronics manufacturing requires significant equipment and technology investment'
            },
            'chemicals': {
                'primary': ValuationMethodology.ASSET_BASED,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['equipment', 'facilities', 'permits', 'raw_materials'],
                'special_considerations': ['safety_compliance', 'environmental_regulations', 'equipment_specialization'],
                'growth_weighted': False,
                'reasoning': 'Chemical manufacturing requires specialized equipment and regulatory compliance'
            },
            'pharmaceuticals': {
                'primary': ValuationMethodology.DCF,
                'secondary': ValuationMethodology.ASSET_BASED,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['patents', 'equipment', 'regulatory_approval', 'pipeline'],
                'special_considerations': ['regulatory_risk', 'patent_expiry', 'r&d_investment'],
                'growth_weighted': True,
                'reasoning': 'Pharmaceuticals combine high asset intensity with significant growth potential from R&D'
            },
            'aerospace': {
                'primary': ValuationMethodology.ASSET_BASED,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['equipment', 'facilities', 'certifications', 'contracts'],
                'special_considerations': ['regulatory_compliance', 'long_cycles', 'equipment_specialization'],
                'growth_weighted': False,
                'reasoning': 'Aerospace manufacturing requires highly specialized equipment and certifications'
            },
            'defense': {
                'primary': ValuationMethodology.ASSET_BASED,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'high',
                'key_factors': ['equipment', 'facilities', 'clearances', 'contracts'],
                'special_considerations': ['security_clearances', 'government_contracts', 'equipment_specialization'],
                'growth_weighted': False,
                'reasoning': 'Defense manufacturing requires specialized equipment and security clearances'
            },

            # =============================================================================
            # SERVICES & PROFESSIONAL (25 types)
            # =============================================================================
            'consulting': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['expertise', 'client_base', 'reputation', 'talent'],
                'special_considerations': ['key_person_risk', 'client_concentration', 'talent_retention'],
                'growth_weighted': False,
                'reasoning': 'Consulting is people-based with predictable revenue streams'
            },
            'legal': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['expertise', 'client_base', 'reputation', 'partnership'],
                'special_considerations': ['key_person_risk', 'client_relationships', 'regulatory_changes'],
                'growth_weighted': False,
                'reasoning': 'Legal services are expertise-based with recurring client relationships'
            },
            'accounting': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['client_base', 'recurring_revenue', 'expertise', 'compliance'],
                'special_considerations': ['seasonality', 'client_retention', 'regulatory_changes'],
                'growth_weighted': False,
                'reasoning': 'Accounting has strong recurring revenue from compliance services'
            },
            'marketing_agency': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['client_base', 'creative_talent', 'reputation', 'campaign_results'],
                'special_considerations': ['client_retention', 'talent_retention', 'project_based_revenue'],
                'growth_weighted': False,
                'reasoning': 'Marketing agencies are talent-based with project-driven revenue'
            },
            'advertising': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['client_base', 'media_relationships', 'creative_talent', 'campaign_performance'],
                'special_considerations': ['client_retention', 'media_commission', 'campaign_cycles'],
                'growth_weighted': False,
                'reasoning': 'Advertising agencies rely on client relationships and media partnerships'
            },
            'pr_agency': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['client_base', 'media_relationships', 'crisis_management', 'reputation'],
                'special_considerations': ['client_retention', 'crisis_events', 'media_relationships'],
                'growth_weighted': False,
                'reasoning': 'PR agencies are relationship-based with recurring client work'
            },
            'recruitment': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['client_base', 'candidate_network', 'industry_expertise', 'placement_success'],
                'special_considerations': ['economic_cycles', 'client_retention', 'candidate_quality'],
                'growth_weighted': False,
                'reasoning': 'Recruitment agencies are network-based with placement-driven revenue'
            },
            'hr_consulting': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['expertise', 'client_base', 'compliance_knowledge', 'talent_development'],
                'special_considerations': ['regulatory_changes', 'client_retention', 'talent_shortage'],
                'growth_weighted': False,
                'reasoning': 'HR consulting is expertise-based with recurring compliance work'
            },
            'it_consulting': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['technical_expertise', 'client_base', 'project_management', 'certifications'],
                'special_considerations': ['technology_changes', 'project_cycles', 'talent_retention'],
                'growth_weighted': False,
                'reasoning': 'IT consulting is expertise-based with project-driven revenue'
            },
            'management_consulting': {
                'primary': ValuationMethodology.MULTIPLES,
                'secondary': ValuationMethodology.DCF,
                'multiple_types': ['revenue', 'ebitda'],
                'asset_intensity': 'low',
                'key_factors': ['expertise', 'client_base', 'methodology', 'reputation'],
                'special_considerations': ['key_person_risk', 'client_retention', 'project_based_revenue'],
                'growth_weighted': False,
                'reasoning': 'Management consulting is expertise-based with high-value projects'
            }
        }

    def get_business_type_characteristics(self, business_type: str) -> BusinessCharacteristics:
        """Get detailed characteristics for a business type"""
        normalized_type = self._normalize_business_type(business_type)

        if normalized_type not in self.business_type_map:
            return self._get_default_characteristics(business_type)

        config = self.business_type_map[normalized_type]

        return BusinessCharacteristics(
            business_type=business_type,
            category=self._get_business_category(normalized_type),
            asset_intensity=config.get('asset_intensity', 'medium'),
            growth_potential='high' if config.get('growth_weighted', False) else 'medium',
            revenue_predictability='high' if config.get('asset_intensity') == 'high' else 'medium',
            key_success_factors=config['key_factors'],
            common_risks=config['special_considerations'],
            optimal_methodology=config['primary'],
            alternative_methodology=config.get('secondary')
        )

    def _normalize_business_type(self, business_type: str) -> str:
        """Normalize business type to match mapping keys"""
        if not business_type:
            return "other"

        # Convert to lowercase and handle common variations
        normalized = business_type.lower().strip()

        # Handle common variations
        variations = {
            'saas': 'saas',
            'software_as_a_service': 'saas',
            'restaurant': 'restaurant',
            'cafe': 'coffee_shop',
            'coffee shop': 'coffee_shop',
            'brewery': 'brewery',
            'brewing': 'brewery',
            'manufacturing': 'manufacturing',
            'manufacturer': 'manufacturing',
            'consulting': 'consulting',
            'consultant': 'consulting',
            'retail': 'retail',
            'retailer': 'retail',
            'ecommerce': 'ecommerce',
            'e-commerce': 'ecommerce',
            'online retail': 'ecommerce'
        }

        return variations.get(normalized, normalized)

    def _get_business_category(self, business_type: str) -> str:
        """Get business category for a business type"""
        return BUSINESS_CATEGORIES.get(business_type, BusinessCategory.OTHER.value)

    def _get_default_characteristics(self, business_type: str) -> BusinessCharacteristics:
        """Get default characteristics for unknown business types"""
        return BusinessCharacteristics(
            business_type=business_type,
            category='other',
            asset_intensity='medium',
            growth_potential='medium',
            revenue_predictability='medium',
            key_success_factors=['market_position', 'operational_efficiency', 'customer_satisfaction'],
            common_risks=['market_competition', 'economic_cycles', 'operational_challenges'],
            optimal_methodology=ValuationMethodology.MULTIPLES,
            alternative_methodology=ValuationMethodology.ASSET_BASED
        )

    def get_business_type_config(self, business_type: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific business type"""
        normalized_type = self._normalize_business_type(business_type)
        return self.business_type_map.get(normalized_type)

    def list_business_types(self) -> List[str]:
        """Get list of all supported business types"""
        return list(self.business_type_map.keys())

    def get_business_types_by_category(self, category: str) -> List[str]:
        """Get business types for a specific category"""
        return [
            business_type for business_type, config in self.business_type_map.items()
            if self._get_business_category(business_type) == category
        ]