"""
Calculation Steps Builder

WHAT: Builds 12-step calculation journey with caching
WHY: Separates calculation steps building logic (SRP compliance)
HOW: Delegates to build_12_step_calculation_journey, adds caching and enrichment

SINGLE RESPONSIBILITY: Calculation steps building and caching ONLY
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
import time
import threading
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.api.schemas import ValuationRequest, ValuationResponse

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.infrastructure.step_data_builder import build_12_step_calculation_journey

logger = get_logger(__name__)


class CalculationStepsBuilder:
    """
    Builds 12-step calculation journey with caching and enrichment.
    
    SINGLE RESPONSIBILITY: Calculation steps building and caching ONLY
    
    This service:
    - Builds 12-step calculation journey
    - Caches results for performance
    - Enriches steps with business type characteristics
    - Handles errors with placeholder steps
    
    NO extraction, NO validation, NO transformation - pure building only.
    """
    
    def __init__(self, cache_size_limit: int = 50):
        """
        Initialize calculation steps builder.
        
        Args:
            cache_size_limit: Maximum number of cached calculation step sets
        """
        self.logger = logger
        self.cache_size_limit = cache_size_limit
        
        self._calculation_steps_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()
    
    def build_calculation_steps(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> List[Dict[str, Any]]:
        """
        Build 12-step calculation journey with caching.
        
        WHAT: Creates 12-step journey from response data
        WHY: Templates need step-by-step calculation breakdown
        HOW: Uses build_12_step_calculation_journey, caches valid results
        
        Args:
            response: ValuationResponse
            request: ValuationRequest
        
        Returns:
            List of 12 calculation steps (dicts with step data)
        
        Business Rules:
        - Cache valid results (12 steps)
        - Don't cache invalid results
        - Use placeholder steps if building fails
        - FIFO cache eviction when full
        """
        cache_key = f"{id(response)}_{id(request)}"
        
        with self._cache_lock:
            if cache_key in self._calculation_steps_cache:
                calculation_steps = self._calculation_steps_cache[cache_key]
                self.logger.info(
                    "Using cached calculation steps",
                    extra={
                        'cache_key': cache_key,
                        'steps_count': len(calculation_steps) if calculation_steps else 0,
                        'cache_size': len(self._calculation_steps_cache),
                        'source': 'cache',
                    }
                )
                return calculation_steps
        
        # Build new calculation steps
        self.logger.info(
            "🔍 [BUG-FIX-VERIFICATION] Building new calculation steps (not in cache)",
            extra={
                'cache_key': cache_key,
                'cache_size_before': len(self._calculation_steps_cache),
                'cache_size_limit': self.cache_size_limit,
            }
        )
        
        try:
            calculation_steps = build_12_step_calculation_journey(response, request)
            
            # Validate calculation steps
            steps_count = len(calculation_steps) if calculation_steps else 0
            is_valid = calculation_steps and steps_count == 12
            
            self.logger.info(
                "🔍 [BUG-FIX-VERIFICATION] Validation check for calculation steps",
                extra={
                    'company_name': response.company_name,
                    'valuation_id': response.valuation_id,
                    'steps_count': steps_count,
                    'expected_count': 12,
                    'is_valid': is_valid,
                    'calculation_steps_is_none': calculation_steps is None,
                    'calculation_steps_is_empty': calculation_steps == [] if calculation_steps else False,
                }
            )
            
            if not is_valid:
                self.logger.warning(
                    "⚠️ [BUG-FIX-VERIFICATION] build_12_step_calculation_journey returned invalid result - WILL NOT CACHE",
                    extra={
                        'company_name': response.company_name,
                        'valuation_id': response.valuation_id,
                        'steps_count': steps_count,
                        'expected_count': 12,
                        'validation_failed': True,
                        'will_skip_cache': True,
                    }
                )
                return calculation_steps or []
            
            # Cache valid results
            self._cache_steps(cache_key, calculation_steps)
            
            return calculation_steps
        
        except Exception as journey_error:
            self.logger.error(
                "❌ Failed to build 12-step calculation journey",
                extra={
                    'company_name': response.company_name,
                    'valuation_id': response.valuation_id,
                    'error_type': type(journey_error).__name__,
                    'error_message': str(journey_error),
                },
                exc_info=True
            )
            
            # Create placeholder steps
            return self._create_placeholder_steps()
    
    def enrich_steps_with_characteristics(
        self,
        calculation_steps: List[Dict[str, Any]],
        business_type_characteristics: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich calculation steps with business type characteristics.
        
        WHAT: Adds business_type_characteristics to each step's outputs
        WHY: Templates need these characteristics without UndefinedError
        HOW: Merges characteristics into step outputs, preserves existing values
        
        Args:
            calculation_steps: List of calculation steps
            business_type_characteristics: Business type characteristics dict
        
        Returns:
            Enriched calculation steps
        
        Business Rules:
        - Only enrich if both steps and characteristics provided
        - Preserve existing characteristics if present
        - Merge to add missing values
        """
        if not calculation_steps or not business_type_characteristics:
            return calculation_steps
        
        for step in calculation_steps:
            if isinstance(step, dict) and 'outputs' in step:
                if not isinstance(step['outputs'], dict):
                    step['outputs'] = {}
                
                # Merge business_type_characteristics into step outputs
                if 'business_type_characteristics' not in step['outputs'] or not step['outputs'].get('business_type_characteristics'):
                    step['outputs']['business_type_characteristics'] = business_type_characteristics.copy()
                else:
                    # Merge to preserve existing values while adding missing ones
                    existing = step['outputs']['business_type_characteristics']
                    if isinstance(existing, dict):
                        step['outputs']['business_type_characteristics'] = {
                            **business_type_characteristics,
                            **existing  # Existing values take precedence
                        }
                    else:
                        step['outputs']['business_type_characteristics'] = business_type_characteristics.copy()
        
        self.logger.debug(
            "Steps enriched with business type characteristics",
            extra={'steps_count': len(calculation_steps)}
        )
        
        return calculation_steps
    
    def _cache_steps(self, cache_key: str, calculation_steps: List[Dict[str, Any]]):
        """
        Cache calculation steps with FIFO eviction.
        
        Args:
            cache_key: Cache key
            calculation_steps: Steps to cache
        """
        with self._cache_lock:
            cache_size_before = len(self._calculation_steps_cache)
            
            if cache_size_before >= self.cache_size_limit:
                oldest_key = next(iter(self._calculation_steps_cache))
                del self._calculation_steps_cache[oldest_key]
                self.logger.debug(
                    "Removed oldest cache entry (FIFO)",
                    extra={
                        'oldest_key': oldest_key,
                        'cache_size_before_removal': cache_size_before,
                        'cache_size_limit': self.cache_size_limit,
                    }
                )
            
            self._calculation_steps_cache[cache_key] = calculation_steps
            cache_size_after = len(self._calculation_steps_cache)
        
        self.logger.info(
            "✅ [BUG-FIX-VERIFICATION] Cached valid calculation steps",
            extra={
                'cache_key': cache_key,
                'steps_count': len(calculation_steps),
                'cache_size_before': cache_size_before,
                'cache_size_after': cache_size_after,
                'validation_passed': True,
                'cached': True,
            }
        )
    
    def _create_placeholder_steps(self) -> List[Dict[str, Any]]:
        """
        Create placeholder steps when building fails.
        
        Returns:
            List of 12 placeholder steps
        """
        from src.services.infrastructure.step_data_builder.step_placeholder_creator import StepPlaceholderCreator
        
        calculation_steps = [StepPlaceholderCreator.create_placeholder(i) for i in range(12)]
        
        self.logger.warning(
            "Created placeholder steps due to journey building failure",
            extra={'steps_count': len(calculation_steps)}
        )
        
        return calculation_steps
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Cache stats dict with size, limit, hit rate
        """
        with self._cache_lock:
            return {
                'cache_size': len(self._calculation_steps_cache),
                'cache_limit': self.cache_size_limit,
                'cache_keys': list(self._calculation_steps_cache.keys())
            }
    
    def clear_cache(self):
        """Clear the calculation steps cache."""
        with self._cache_lock:
            self._calculation_steps_cache.clear()
        self.logger.info("Calculation steps cache cleared")
