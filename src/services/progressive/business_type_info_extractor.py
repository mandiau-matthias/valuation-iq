"""
Business Type Info Extractor

Responsibility: Extract business type information from database.

Single Responsibility: Business type information extraction only.
"""

from typing import Dict, Any, Optional, Tuple
from src.utils.logging import get_logger
from src.utils.exceptions import (
    ValuationEngineError,
    ExternalServiceError,
    DataValidationError,
)

logger = get_logger(__name__)


class BusinessTypeInfoExtractor:
    """
    Extracts business type information from database.
    
    Single Responsibility: Business type info extraction only.
    """

    def __init__(self):
        """Initialize extractor"""
        self.logger = logger
        self._business_type_service = None
        
        # Initialize business type service (optional dependency)
        try:
            from src.services.business_intelligence.integration.business_type_database_service import (
                get_business_type_database_service,
            )

            self._business_type_service = get_business_type_database_service()
            self.logger.info("Business type database service initialized")
        except ImportError:
            self.logger.warning("BusinessTypeDatabaseService not available - business type integration disabled")

    def get_business_type_info(self, business_type_id: str) -> Dict[str, Any]:
        """
        Get industry and business_model from business_type_id via database.
        
        Args:
            business_type_id: Business type ID
            
        Returns:
            Dictionary with industry, business_model, and characteristics
        """
        if not business_type_id or not self._business_type_service:
            return {
                'industry': None,
                'business_model': None,
                'characteristics': {}
            }
        
        try:
            # Runtime import for actual usage (acceptable for adapter pattern)
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
            
            # Runtime import with fallback
            try:
                from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
                triage_engine = BusinessTypeTriageEngine()
                business_category = triage_engine.get_business_type_category(
                    business_type_id, None, None
                )
            except ImportError:
                self.logger.warning("BusinessTypeTriageEngine not available")
                return {
                    'industry': None,
                    'business_model': None,
                    'characteristics': {}
                }
            
            # Map category to industry
            category_to_industry = {
                'saas_software': 'technology',
                'ecommerce': 'ecommerce',
                'professional_services': 'services',
                'retail_food': 'retail',
                'manufacturing': 'manufacturing',
                'construction': 'construction',
                'healthcare': 'healthcare',
                'financial_services': 'finance',
                'real_estate': 'real_estate',
                'transportation': 'transportation',
            }
            
            industry = category_to_industry.get(
                business_category.value if business_category else None,
                'other'
            )
            
            return {
                'industry': industry,
                'business_model': business_category.value if business_category else None,
                'characteristics': {}
            }
        except (AttributeError, KeyError, TypeError) as e:
            # Handle data structure errors gracefully
            self.logger.warning(f"Failed to get business type info (data structure error): {e}")
            return {
                'industry': None,
                'business_model': None,
                'characteristics': {}
            }
        except (ExternalServiceError, DataValidationError) as e:
            # Re-raise specific errors
            self.logger.error(f"Failed to get business type info: {e}", exc_info=True)
            raise
        except ValuationEngineError as e:
            # Re-raise valuation engine errors
            raise

    def derive_industry_and_business_model(
        self,
        collected_data: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """
        Derive industry and business_model from collected data.
        
        Args:
            collected_data: Collected data dictionary
            
        Returns:
            Tuple of (industry, business_model, business_type_id, business_type_info)
        """
        # Try business_type_id first
        business_type_id = collected_data.get('business_type_id')
        if business_type_id:
            info = self.get_business_type_info(business_type_id)
            return (
                info.get('industry'),
                info.get('business_model'),
                business_type_id,
                info
            )
        
        # Fallback to business_type string
        business_type = collected_data.get('business_type')
        if business_type:
            info = self.get_business_type_info(business_type)
            return (
                info.get('industry'),
                info.get('business_model'),
                business_type,
                info
            )
        
        # Fallback to direct industry/business_model fields
        industry = collected_data.get('industry')
        business_model = collected_data.get('business_model')
        
        return (industry, business_model, None, None)
