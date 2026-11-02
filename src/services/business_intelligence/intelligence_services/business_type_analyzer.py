"""
Business Type Analyzer Service

BANK-GRADE SRP-COMPLIANT: Business type analysis and classification ONLY

WHAT: Analyzes business characteristics and classifies business types
WHY: Single responsibility - focused business type analysis
HOW: Uses business data to determine type, industry, and characteristics

SINGLE RESPONSIBILITY: Business type analysis and classification
- Business type classification
- Industry categorization  
- Characteristics assessment

EXTRACTED FROM: BusinessTypeIntelligenceService (780 lines)
COMPLIANCE: Bank-Grade Excellence Framework - SRP Phase 1
"""

from typing import Dict, Any, Optional
from decimal import Decimal
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal
from ..analysis.business_analyzer import BusinessAnalyzer

logger = get_logger(__name__)


class BusinessTypeAnalyzer:
    """
    BANK-GRADE SRP-COMPLIANT: Business type analysis and classification.
    
    SINGLE RESPONSIBILITY: Analyze and classify business types ONLY.
    
    This service focuses solely on understanding business characteristics
    and determining the most appropriate business type and industry classification.
    
    Design Pattern: Service Pattern
    - Separates analysis logic from other intelligence operations
    - Enables independent testing and optimization
    - Allows extending with new classification algorithms
    
    Responsibilities:
    - Business type classification
    - Industry categorization
    - Business characteristics assessment
    - Complexity determination
    """
    
    def __init__(self):
        """
        Initialize business type analyzer.
        
        SRP: Focused on business type analysis only
        """
        self.business_analyzer = BusinessAnalyzer()
        self.logger = logger
        
        self.logger.info("✅ [BUSINESS-TYPE-ANALYZER] BusinessTypeAnalyzer initialized (SRP-compliant)")
    
    async def analyze_business_type(
        self,
        business_type: str,
        user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze business type and extract characteristics.
        
        SRP: Only analyzes business characteristics, doesn't make methodology decisions.
        
        Args:
            business_type: Business type identifier (e.g., 'restaurant', 'saas')
            user_data: Business data including revenue, employees, industry
            
        Returns:
            Dict containing:
            - characteristics: Business characteristics
            - metrics: Calculated business metrics
            - adjustments: Business-specific adjustments
            - config: Business type configuration
            - key_factors: Key factors influencing analysis
            - growth_potential: Growth potential score
            - owner_dependency: Owner dependency score
        """
        self.logger.info(
            f"🔍 [BUSINESS-TYPE-ANALYZER] Analyzing business type: {business_type}",
            extra={
                'business_type': business_type,
                'user_data_keys': list(user_data.keys())
            }
        )
        
        # Use BusinessAnalyzer for core analysis
        business_analysis = await self.business_analyzer.analyze_business_characteristics(
            business_type,
            user_data
        )
        
        self.logger.info(
            f"✅ [BUSINESS-TYPE-ANALYZER] Analysis complete for {business_type}",
            extra={
                'business_type': business_type,
                'characteristics': business_analysis.get('characteristics', {})
            }
        )
        
        return business_analysis
    
    async def classify_industry(
        self,
        business_type: str,
        industry_indicators: Dict[str, Any]
    ) -> str:
        """
        Classify business into industry category.
        
        SRP: Only classification, doesn't analyze or make decisions.
        
        Args:
            business_type: Business type identifier
            industry_indicators: Indicators for industry classification
            
        Returns:
            Industry category (e.g., 'Technology', 'Food & Beverage')
        """
        self.logger.info(
            f"🔍 [BUSINESS-TYPE-ANALYZER] Classifying industry for {business_type}",
            extra={'business_type': business_type}
        )
        
        # Industry mapping based on business type
        industry_map = {
            # Technology
            'saas': 'Technology',
            'software': 'Technology',
            'webdev': 'Technology',
            'itsupport': 'Technology',
            'b2b_saas': 'Technology',
            'mobile-app': 'Technology',
            'ecommerce': 'Technology',
            
            # Food & Beverage
            'restaurant': 'Food & Beverage',
            'catering': 'Food & Beverage',
            'bakery': 'Food & Beverage',
            'coffee-shop': 'Food & Beverage',
            'food-truck': 'Food & Beverage',
            
            # Professional Services
            'consulting': 'Professional Services',
            'legal': 'Professional Services',
            'accounting': 'Professional Services',
            'marketing': 'Professional Services',
            
            # Healthcare
            'healthcare': 'Health & Medical',
            'dental': 'Health & Medical',
            'veterinary': 'Health & Medical',
            
            # Retail
            'retail': 'Retail & E-commerce',
            'fashion': 'Retail & E-commerce',
            'jewelry': 'Retail & E-commerce',
        }
        
        industry = industry_map.get(business_type, 'Other')
        
        self.logger.info(
            f"✅ [BUSINESS-TYPE-ANALYZER] Industry classified: {industry}",
            extra={'business_type': business_type, 'industry': industry}
        )
        
        return industry
    
    def determine_business_characteristics(
        self,
        business_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine business characteristics from data.
        
        SRP: Only extracts characteristics, doesn't make decisions.
        
        Args:
            business_data: Raw business data
            
        Returns:
            Dict of business characteristics including:
            - revenue_level: Low, Medium, High
            - employee_count_level: Small, Medium, Large
            - complexity: Low, Medium, High
            - growth_stage: Startup, Growth, Mature
        """
        self.logger.info(
            "🔍 [BUSINESS-TYPE-ANALYZER] Determining business characteristics",
            extra={'data_keys': list(business_data.keys())}
        )
        
        revenue = to_decimal(business_data.get('revenue', 0))
        employees = to_decimal(business_data.get('employees', 0))
        founded_year = business_data.get('founded_year', 2020)
        
        # Revenue level
        if revenue < Decimal('100000'):
            revenue_level = 'Low'
        elif revenue < Decimal('1000000'):
            revenue_level = 'Medium'
        else:
            revenue_level = 'High'
        
        # Employee count level
        if employees < 5:
            employee_level = 'Small'
        elif employees < 50:
            employee_level = 'Medium'
        else:
            employee_level = 'Large'
        
        # Complexity (based on revenue and employees)
        complexity_score = (
            (Decimal('0.6') if revenue_level == 'High' else Decimal('0.3') if revenue_level == 'Medium' else Decimal('0.1')) +
            (Decimal('0.4') if employee_level == 'Large' else Decimal('0.2') if employee_level == 'Medium' else Decimal('0.1'))
        )
        
        if complexity_score > Decimal('0.7'):
            complexity = 'High'
        elif complexity_score > Decimal('0.4'):
            complexity = 'Medium'
        else:
            complexity = 'Low'
        
        # Growth stage (based on company age)
        from datetime import datetime
        company_age = datetime.now().year - founded_year
        
        if company_age < 3:
            growth_stage = 'Startup'
        elif company_age < 10:
            growth_stage = 'Growth'
        else:
            growth_stage = 'Mature'
        
        characteristics = {
            'revenue_level': revenue_level,
            'employee_count_level': employee_level,
            'complexity': complexity,
            'complexity_score': complexity_score,
            'growth_stage': growth_stage,
            'company_age': company_age,
            'revenue': revenue,
            'employees': employees
        }
        
        self.logger.info(
            "✅ [BUSINESS-TYPE-ANALYZER] Characteristics determined",
            extra={'characteristics': characteristics}
        )
        
        return characteristics
    
    async def get_business_type_info(self, business_type: str) -> Dict[str, Any]:
        """
        Get comprehensive information about a business type.
        
        SRP: Only retrieves information, doesn't analyze or process.
        
        Args:
            business_type: Business type identifier
            
        Returns:
            Dict containing business type information
        """
        self.logger.info(
            f"🔍 [BUSINESS-TYPE-ANALYZER] Getting info for {business_type}",
            extra={'business_type': business_type}
        )
        
        # Delegate to BusinessAnalyzer
        info = await self.business_analyzer.get_business_type_info(business_type)
        
        return info
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.
        
        Returns:
            Dict containing:
            - service_name: Name of this service
            - responsibility: Single responsibility description
            - status: Operational status
        """
        return {
            'service_name': 'BusinessTypeAnalyzer',
            'responsibility': 'Business type analysis and classification',
            'status': 'operational',
            'srp_compliant': True
        }
