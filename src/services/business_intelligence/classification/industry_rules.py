"""
Industry Rules

Defines industry-specific rules and scoring logic for methodology selection.
Handles special cases and industry-specific considerations.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, List, Optional, Any, Tuple
from src.utils.logging import get_logger
from ..integration.mapper_types import ValuationMethodology, BusinessCategory
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class IndustryRules:
    """Handles industry-specific rules and scoring"""

    def __init__(self):
        self.industry_rules = self._build_industry_rules()
        self.special_cases = self._build_special_cases()

    def _build_industry_rules(self) -> Dict[str, Dict[str, Any]]:
        """Build industry-specific rules for methodology selection"""
        return {
            'technology': {
                'preferred_methodologies': [ValuationMethodology.DCF, ValuationMethodology.ARR_MULTIPLES],
                'avoid_methodologies': [ValuationMethodology.ASSET_BASED],
                'key_factors': ['growth_rate', 'market_size', 'competitive_advantage', 'scalability'],
                'special_considerations': ['technology_risk', 'market_adoption', 'regulatory_changes'],
                'revenue_thresholds': {
                    'small': 100000,  # < €100K
                    'medium': 1000000,  # < €1M
                    'large': 10000000  # > €10M
                },
                'growth_weighted': True,
                'asset_intensity': 'low'
            },
            'manufacturing': {
                'preferred_methodologies': [ValuationMethodology.ASSET_BASED, ValuationMethodology.MULTIPLES],
                'avoid_methodologies': [ValuationMethodology.ARR_MULTIPLES],
                'key_factors': ['equipment', 'inventory', 'facilities', 'supply_chain', 'efficiency'],
                'special_considerations': ['equipment_age', 'maintenance_costs', 'raw_material_costs', 'regulatory_compliance'],
                'revenue_thresholds': {
                    'small': 500000,  # < €500K
                    'medium': 5000000,  # < €5M
                    'large': 50000000  # > €50M
                },
                'growth_weighted': False,
                'asset_intensity': 'high'
            },
            'services': {
                'preferred_methodologies': [ValuationMethodology.MULTIPLES, ValuationMethodology.DCF],
                'avoid_methodologies': [ValuationMethodology.ASSET_BASED],
                'key_factors': ['client_base', 'expertise', 'reputation', 'talent', 'recurring_revenue'],
                'special_considerations': ['key_person_risk', 'client_retention', 'talent_retention', 'regulatory_changes'],
                'revenue_thresholds': {
                    'small': 200000,  # < €200K
                    'medium': 2000000,  # < €2M
                    'large': 20000000  # > €20M
                },
                'growth_weighted': False,
                'asset_intensity': 'low'
            },
            'retail': {
                'preferred_methodologies': [ValuationMethodology.MULTIPLES, ValuationMethodology.ASSET_BASED],
                'avoid_methodologies': [ValuationMethodology.ARR_MULTIPLES],
                'key_factors': ['inventory', 'location', 'brand', 'customer_base', 'same_store_sales'],
                'special_considerations': ['seasonality', 'inventory_management', 'competition', 'ecommerce_disruption'],
                'revenue_thresholds': {
                    'small': 300000,  # < €300K
                    'medium': 3000000,  # < €3M
                    'large': 30000000  # > €30M
                },
                'growth_weighted': False,
                'asset_intensity': 'medium'
            },
            'healthcare': {
                'preferred_methodologies': [ValuationMethodology.DCF, ValuationMethodology.MULTIPLES],
                'avoid_methodologies': [],
                'key_factors': ['patient_volume', 'reimbursement', 'quality_metrics', 'regulatory_compliance'],
                'special_considerations': ['regulatory_risk', 'insurance_relationships', 'quality_standards'],
                'revenue_thresholds': {
                    'small': 500000,  # < €500K
                    'medium': 5000000,  # < €5M
                    'large': 50000000  # > €50M
                },
                'growth_weighted': False,
                'asset_intensity': 'medium'
            }
        }

    def _build_special_cases(self) -> Dict[str, Dict[str, Any]]:
        """Build special cases and exceptions for methodology selection"""
        return {
            'saas_early_stage': {
                'conditions': ['saas', 'revenue < 100000', 'years < 2'],
                'methodology': ValuationMethodology.ARR_MULTIPLES,
                'reasoning': 'Early-stage SaaS businesses are best valued using ARR multiples'
            },
            'saas_mature': {
                'conditions': ['saas', 'revenue > 1000000', 'years > 3'],
                'methodology': ValuationMethodology.DCF,
                'reasoning': 'Mature SaaS businesses with predictable revenue are suitable for DCF'
            },
            'manufacturing_small': {
                'conditions': ['manufacturing', 'revenue < 500000'],
                'methodology': ValuationMethodology.ASSET_BASED,
                'reasoning': 'Small manufacturing businesses are primarily asset-based'
            },
            'consulting_high_growth': {
                'conditions': ['consulting', 'revenue > 2000000', 'growth_rate > 20'],
                'methodology': ValuationMethodology.DCF,
                'reasoning': 'High-growth consulting firms benefit from DCF analysis'
            },
            'retail_ecommerce': {
                'conditions': ['retail', 'ecommerce', 'revenue > 1000000'],
                'methodology': ValuationMethodology.MULTIPLES,
                'reasoning': 'E-commerce retail businesses are suitable for market multiples'
            }
        }

    def get_industry_rules(self, industry: str) -> Optional[Dict[str, Any]]:
        """Get rules for a specific industry"""
        return self.industry_rules.get(industry.lower())

    def apply_industry_rules(
        self, 
        business_type: str, 
        industry: Optional[str], 
        revenue: Optional[Decimal],
        years_in_operation: Optional[int],
        base_methodology: ValuationMethodology
    ) -> Tuple[ValuationMethodology, float, List[str]]:
        """
        Apply industry-specific rules to refine methodology selection

        Returns:
            Tuple of (refined_methodology, confidence_adjustment, reasoning_changes)
        """
        if not industry:
            return base_methodology, Decimal('0.0'), []

        industry_rules = self.get_industry_rules(industry)
        if not industry_rules:
            return base_methodology, Decimal('0.0'), []

        refined_methodology = base_methodology
        confidence_adjustment = Decimal('0.0')
        reasoning_changes = []

        # Check preferred methodologies
        if base_methodology in industry_rules['preferred_methodologies']:
            confidence_adjustment += Decimal('0.1')
            reasoning_changes.append(f"{industry} businesses typically benefit from {base_methodology.value} analysis")

        # Check avoided methodologies
        if base_methodology in industry_rules['avoid_methodologies']:
            confidence_adjustment -= Decimal('0.2')
            reasoning_changes.append(f"{industry} businesses may not be suitable for {base_methodology.value} analysis")

            # Suggest alternative
            if industry_rules['preferred_methodologies']:
                alternative = industry_rules['preferred_methodologies'][0]
                refined_methodology = alternative
                reasoning_changes.append(f"Consider using {alternative.value} instead")

        # Apply special cases
        special_case = self._check_special_cases(business_type, industry, revenue, years_in_operation)
        if special_case:
            refined_methodology = special_case['methodology']
            confidence_adjustment += Decimal('0.15')
            reasoning_changes.append(special_case['reasoning'])

        # Apply revenue-based adjustments
        if revenue and industry_rules.get('revenue_thresholds'):
            revenue_category = self._get_revenue_category(revenue, industry_rules['revenue_thresholds'])
            if revenue_category == 'small' and base_methodology == ValuationMethodology.DCF:
                refined_methodology = ValuationMethodology.MULTIPLES
                confidence_adjustment += Decimal('0.1')
                reasoning_changes.append("Small businesses typically use simpler valuation methods")
            elif revenue_category == 'large' and base_methodology == ValuationMethodology.MULTIPLES:
                refined_methodology = ValuationMethodology.DCF
                confidence_adjustment += Decimal('0.1')
                reasoning_changes.append("Large businesses require sophisticated DCF analysis")

        return refined_methodology, confidence_adjustment, reasoning_changes

    def _check_special_cases(
        self, 
        business_type: str, 
        industry: Optional[str], 
        revenue: Optional[Decimal],
        years_in_operation: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """Check for special cases that override standard methodology selection"""

        for case_name, case_config in self.special_cases.items():
            conditions = case_config['conditions']
            matches = 0

            # Check business type condition
            if business_type.lower() in [c.lower() for c in conditions]:
                matches += 1

            # Check revenue conditions
            if revenue:
                for condition in conditions:
                    if 'revenue <' in condition:
                        threshold = int(condition.split('<')[1].strip())
                        if revenue < threshold:
                            matches += 1
                    elif 'revenue >' in condition:
                        threshold = int(condition.split('>')[1].strip())
                        if revenue > threshold:
                            matches += 1

            # Check years in operation conditions
            if years_in_operation:
                for condition in conditions:
                    if 'years <' in condition:
                        threshold = int(condition.split('<')[1].strip())
                        if years_in_operation < threshold:
                            matches += 1
                    elif 'years >' in condition:
                        threshold = int(condition.split('>')[1].strip())
                        if years_in_operation > threshold:
                            matches += 1

            # If all conditions match, return the special case
            if matches == len(conditions):
                return case_config

        return None

    def _get_revenue_category(self, revenue: Decimal, thresholds: Dict[str, int]) -> str:
        """Get revenue category based on thresholds"""
        if revenue < thresholds['small']:
            return 'small'
        elif revenue < thresholds['medium']:
            return 'medium'
        else:
            return 'large'

    def get_industry_characteristics(self, industry: str) -> Dict[str, Any]:
        """Get detailed characteristics for an industry"""
        industry_rules = self.get_industry_rules(industry)
        if not industry_rules:
            return {
                'industry': industry,
                'growth_potential': 'medium',
                'asset_intensity': 'medium',
                'revenue_predictability': 'medium',
                'key_metrics': ['revenue', 'profitability', 'market_position']
            }

        return {
            'industry': industry,
            'growth_potential': 'high' if industry_rules['growth_weighted'] else 'medium',
            'asset_intensity': industry_rules['asset_intensity'],
            'revenue_predictability': 'high' if industry_rules['asset_intensity'] == 'high' else 'medium',
            'key_metrics': industry_rules['key_factors'],
            'preferred_methodologies': [m.value for m in industry_rules['preferred_methodologies']],
            'avoid_methodologies': [m.value for m in industry_rules['avoid_methodologies']]
        }

    def validate_industry_methodology(
        self, 
        methodology: ValuationMethodology, 
        industry: str
    ) -> Dict[str, Any]:
        """Validate if a methodology is appropriate for an industry"""
        industry_rules = self.get_industry_rules(industry)
        if not industry_rules:
            return {
                'is_appropriate': True,
                'confidence': Decimal('0.7'),
                'warnings': [],
                'recommendations': []
            }

        validation_result = {
            'is_appropriate': True,
            'confidence': Decimal('0.8'),
            'warnings': [],
            'recommendations': []
        }

        # Check if methodology is preferred
        if methodology in industry_rules['preferred_methodologies']:
            validation_result['confidence'] += Decimal('0.1')
            validation_result['recommendations'].append(f"{methodology.value} is well-suited for {industry} businesses")

        # Check if methodology should be avoided
        if methodology in industry_rules['avoid_methodologies']:
            validation_result['is_appropriate'] = False
            validation_result['confidence'] -= Decimal('0.3')
            validation_result['warnings'].append(f"{methodology.value} may not be appropriate for {industry} businesses")

            # Suggest alternatives
            if industry_rules['preferred_methodologies']:
                alternatives = [m.value for m in industry_rules['preferred_methodologies']]
                validation_result['recommendations'].append(f"Consider using {', '.join(alternatives)} instead")

        validation_result['confidence'] = max(Decimal('0.0'), min(Decimal('1.0'), validation_result['confidence']))

        return validation_result