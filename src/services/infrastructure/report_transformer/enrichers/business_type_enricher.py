"""
Business Type Enricher

WHAT: Enriches business type data with metadata and characteristics
WHY: Separates business type enrichment logic (SRP compliance), fixes DRY violation
HOW: Looks up metadata, calculates characteristics, provides defaults

SINGLE RESPONSIBILITY: Business type enrichment ONLY

DRY FIX: This service eliminates duplicate business type logic from:
- ReportTransformerOrchestrator.transform_valuation_response (lines 192-337)
- ReportTransformerOrchestrator.transform_for_info_tab (lines 440-493)
"""

from typing import Dict, Any, Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BusinessTypeEnricher:
    """
    Enriches business type data with metadata and characteristics.
    
    SINGLE RESPONSIBILITY: Business type enrichment ONLY
    
    This service:
    - Looks up business type metadata (title, icon)
    - Calculates business type characteristics (multiples preference, owner dependency, EBITDA margin)
    - Provides sensible defaults when data unavailable
    
    NO extraction, NO validation, NO transformation - pure enrichment only.
    
    DRY COMPLIANCE: Eliminates 150+ lines of duplicate code from orchestrator.
    """
    
    def __init__(self):
        """Initialize business type enricher."""
        self.logger = logger
        
        # Default icon
        self.default_icon = '🏢'
        
        # Default characteristics (used when lookup fails)
        self.default_characteristics = {
            'multiples_preference': 0.85,
            'owner_dependency_impact': 0.5,
            'typical_ebitda_margin_median': 0.15,
        }
    
    def enrich_business_type(
        self,
        business_type_id: Optional[str],
        request_business_type: Optional[str] = None,
        company_name: Optional[str] = None,
        valuation_preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Enrich business type with metadata lookup.
        
        Args:
            business_type_id: Business type identifier
            request_business_type: Business type from request (fallback)
            company_name: Company name (for logging)
            valuation_preferences: Titan-enriched valuation preferences dict
        
        Returns:
            Dict with enriched business type data:
            - business_type: Authoritative display name
            - business_type_id: Business type ID
            - business_type_icon: Icon emoji
        """
        enriched = {
            'business_type': request_business_type,
            'business_type_id': business_type_id,
            'business_type_icon': self.default_icon
        }
        
        if not business_type_id:
            self.logger.warning(
                "No business_type_id provided, using defaults",
                extra={'company_name': company_name}
            )
            return enriched
        
        try:
            from src.services.business_type_metadata_service import get_business_type_metadata_service
            metadata_service = get_business_type_metadata_service()
            calibration_data = valuation_preferences if isinstance(valuation_preferences, dict) else None
            metadata = metadata_service.get_business_type_metadata(calibration_data)
            
            if metadata and metadata.id:
                if metadata.title:
                    enriched['business_type'] = metadata.title
                    self.logger.debug(
                        "Looked up business type display name from metadata",
                        extra={
                            'business_type_id': business_type_id,
                            'business_type_title': enriched['business_type'],
                            'request_business_type': request_business_type,
                            'company_name': company_name
                        }
                    )
                if hasattr(metadata, 'icon') and metadata.icon:
                    enriched['business_type_icon'] = metadata.icon

            if not enriched['business_type']:
                enriched['business_type'] = business_type_id.replace('_', ' ').title()
                self.logger.warning(
                    "Business type metadata not found, using ID as display name",
                    extra={
                        'business_type_id': business_type_id,
                        'fallback_display_name': enriched['business_type'],
                        'company_name': company_name
                    }
                )
        
        except Exception as e:
            if not enriched['business_type']:
                enriched['business_type'] = business_type_id.replace('_', ' ').title() if business_type_id else None
            self.logger.warning(
                "Error looking up business type metadata, using fallback",
                extra={
                    'business_type_id': business_type_id,
                    'fallback_display_name': enriched['business_type'],
                    'error': str(e),
                    'company_name': company_name
                }
            )
        
        return enriched
    
    def get_business_type_characteristics(
        self,
        business_type_id: Optional[str],
        company_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get business type characteristics for template rendering.
        
        WHAT: Calculates characteristics (multiples preference, owner dependency, EBITDA margin)
        WHY: Templates need these values for SME Expert boxes and calculations
        HOW: Uses BusinessTypeAnalyzer, provides sensible defaults
        
        Args:
            business_type_id: Business type identifier
            company_name: Company name (for logging)
        
        Returns:
            Dict with business type characteristics:
            - multiples_preference: Multiple methodology preference (0-1)
            - owner_dependency_impact: Owner dependency risk (0-1)
            - typical_ebitda_margin_median: Typical EBITDA margin (0-1)
            - business_type: Business type name
            - category: Business category
            - optimal_methodology: Optimal valuation methodology
        
        Business Rules:
        - SaaS/Software: High multiples preference (0.90), low owner dependency (0.35), high margins (0.25)
        - Restaurants/Food: Medium multiples (0.85), high owner dependency (0.65), low margins (0.10)
        - Default: Moderate values (0.85, 0.5, 0.15)
        
        Example:
            >>> enricher = BusinessTypeEnricher()
            >>> chars = enricher.get_business_type_characteristics('restaurant')
            >>> print(chars['multiples_preference'])  # 0.85
            >>> print(chars['owner_dependency_impact'])  # 0.65
        """
        # Default characteristics
        characteristics = self.default_characteristics.copy()
        
        if not business_type_id:
            self.logger.warning(
                "No business_type_id provided, using default characteristics",
                extra={'company_name': company_name}
            )
            return characteristics
        
        try:
            from src.services.business_intelligence.analysis.business_type_analyzer import BusinessTypeAnalyzer
            analyzer = BusinessTypeAnalyzer()
            analyzer_characteristics = analyzer.get_business_type_characteristics(business_type_id)
            
            # Calculate multiples_preference based on optimal_methodology
            multiples_preference = 0.85  # Default high preference
            if hasattr(analyzer_characteristics, 'optimal_methodology'):
                optimal_method = str(analyzer_characteristics.optimal_methodology).lower()
                if 'multiple' in optimal_method or 'market' in optimal_method:
                    multiples_preference = 0.90
                elif 'dcf' in optimal_method or 'cash' in optimal_method:
                    multiples_preference = 0.60
                elif 'hybrid' in optimal_method:
                    multiples_preference = 0.75
            
            # Calculate owner_dependency_impact based on business type
            owner_dependency_impact = 0.5  # Default medium
            if business_type_id in ['restaurant', 'cafe', 'coffee_shop', 'brewery']:
                owner_dependency_impact = 0.65  # Higher for food service
            elif business_type_id in ['saas', 'software', 'ecommerce']:
                owner_dependency_impact = 0.35  # Lower for tech
            
            # Get typical EBITDA margin
            typical_ebitda_margin_median = 0.15  # Default 15%
            if business_type_id == 'restaurant':
                typical_ebitda_margin_median = 0.10  # Restaurants typically 10%
            elif business_type_id in ['saas', 'software']:
                typical_ebitda_margin_median = 0.25  # SaaS typically higher
            
            # Build characteristics dict
            characteristics = {
                'multiples_preference': multiples_preference,
                'owner_dependency_impact': owner_dependency_impact,
                'typical_ebitda_margin_median': typical_ebitda_margin_median,
                'business_type': getattr(analyzer_characteristics, 'business_type', business_type_id),
                'category': getattr(analyzer_characteristics, 'category', None),
                'optimal_methodology': str(getattr(analyzer_characteristics, 'optimal_methodology', 'MULTIPLES')),
            }
            
            self.logger.debug(
                "Business type characteristics calculated",
                extra={
                    'business_type_id': business_type_id,
                    'multiples_preference': multiples_preference,
                    'owner_dependency_impact': owner_dependency_impact,
                    'company_name': company_name
                }
            )
        
        except Exception as e:
            self.logger.warning(
                "Failed to get business_type_characteristics, using defaults",
                extra={
                    'business_type_id': business_type_id,
                    'error': str(e),
                    'company_name': company_name
                }
            )
            # characteristics already has defaults
        
        return characteristics
    
    def enrich_full_business_type_data(
        self,
        business_type_id: Optional[str],
        request_business_type: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich full business type data (metadata + characteristics).
        
        WHAT: Combines metadata lookup and characteristics calculation
        WHY: Convenience method for complete enrichment
        HOW: Calls both enrichment methods and merges results
        
        Args:
            business_type_id: Business type identifier
            request_business_type: Business type from request (fallback)
            company_name: Company name (for logging)
        
        Returns:
            Dict with complete business type data:
            - business_type: Display name
            - business_type_id: ID
            - business_type_icon: Icon
            - business_type_characteristics: Full characteristics dict
        
        Example:
            >>> enricher = BusinessTypeEnricher()
            >>> full = enricher.enrich_full_business_type_data('restaurant')
            >>> print(full['business_type'])  # "Restaurant"
            >>> print(full['business_type_characteristics']['multiples_preference'])  # 0.85
        """
        # Get metadata enrichment
        enriched = self.enrich_business_type(
            business_type_id=business_type_id,
            request_business_type=request_business_type,
            company_name=company_name
        )
        
        # Get characteristics
        characteristics = self.get_business_type_characteristics(
            business_type_id=business_type_id,
            company_name=company_name
        )
        
        # Add characteristics to enriched data
        enriched['business_type_characteristics'] = characteristics
        
        self.logger.info(
            "Full business type data enriched",
            extra={
                'business_type_id': business_type_id,
                'business_type': enriched['business_type'],
                'has_characteristics': True,
                'company_name': company_name
            }
        )
        
        return enriched
