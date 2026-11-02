"""
Revenue Analysis Calculation Strategy

Calculates revenue analysis section for progressive valuation reports.

SINGLE RESPONSIBILITY: Revenue analysis calculation ONLY.

Author: UpSwitch CTO Team
Date: December 9, 2025
Status: Production Ready
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Any, TYPE_CHECKING
from decimal import Decimal

if TYPE_CHECKING:
    from src.services.progressive.business_type_info_extractor import BusinessTypeInfoExtractor
    from src.services.progressive.calculators.industry_helpers import IndustryHelpers

from src.utils.core.data_extraction_helpers import extract_revenue_from_collected_data
from src.utils.decimal_helpers import from_decimal, to_decimal
from .calculation_strategy import CalculationStrategy

# Academic provenance tracking
try:
    from src.services.academic.decorators import track_academic_provenance
    ACADEMIC_TRACKING_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Academic provenance tracking not available")
    ACADEMIC_TRACKING_AVAILABLE = False
    def track_academic_provenance(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


logger = logging.getLogger(__name__)


class RevenueAnalysisStrategy(CalculationStrategy):
    """
    Calculates revenue analysis section.
    
    SINGLE RESPONSIBILITY: Revenue analysis calculation ONLY.
    
    Revenue-based valuation using industry multiples.
    Only calculates meaningful values when revenue > 0 and industry exists.
    
    BANK-GRADE DESIGN:
    - Dependency injection for testability
    - Academic provenance tracking
    - Comprehensive validation
    - Performance monitoring
    """
    
    def __init__(
        self,
        business_type_extractor: "BusinessTypeInfoExtractor",
        industry_helpers: "IndustryHelpers",
    ):
        """
        Initialize with dependencies.
        
        Args:
            business_type_extractor: Extractor for business type information
            industry_helpers: Helpers for industry-specific calculations
        """
        self.business_type_extractor = business_type_extractor
        self.industry_helpers = industry_helpers
    
    @track_academic_provenance(
        calculation_id="revenue_analysis",
        section_name="Revenue Analysis",
        extract_inputs=lambda args, kwargs: {
            'revenue': kwargs.get('context', {}).get('collected_data', {}).get('revenue'),
            'industry': kwargs.get('context', {}).get('collected_data', {}).get('industry')
        },
        extract_outputs=lambda result: {
            'revenue': result.get('revenue'),
            'revenue_quality': result.get('revenue_quality')
        }
    )
    async def calculate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate revenue analysis section data.
        
        Args:
            context: Conversation context with collected_data
            
        Returns:
            Dictionary with revenue analysis data
            
        Raises:
            ValueError: If context is invalid
        """
        logger.info("[STRATEGY] Calculating revenue analysis")
        start_time = time.time()
        
        # Validate context
        self._validate_context(context)
        
        collected_data = context.get('collected_data', {})
        
        # WORLD-CLASS: Derive industry from business type
        industry, business_model, business_type_id, business_type_info = \
            self.business_type_extractor.derive_industry_and_business_model(collected_data)
        
        # Extract revenue
        revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)
        revenue = from_decimal(revenue_decimal) if has_revenue else 0
        
        # Only calculate if we have revenue and industry
        if has_revenue and revenue > 0 and industry:
            # Get industry multiple
            revenue_multiple = self.industry_helpers.get_revenue_multiple_for_industry(
                industry
            )
            
            # Calculate valuation
            estimated_value = revenue * revenue_multiple
            
            # Quality assessment
            revenue_quality = self._assess_revenue_quality(
                revenue_decimal, 
                business_type_info
            )
            
            # Industry benchmark
            industry_avg_revenue = self.industry_helpers.get_average_revenue_for_industry(
                industry
            )
            
            # Relative position
            relative_position = self._calculate_relative_position(
                revenue, 
                industry_avg_revenue
            )
            
            insights = [
                f"Revenue multiple: {revenue_multiple:.1f}x",
                f"Estimated value: €{estimated_value:,.0f}",
                f"Industry: {industry}",
                relative_position
            ]
            
        else:
            # No meaningful calculation possible
            revenue_multiple = 0
            estimated_value = 0
            revenue_quality = "insufficient_data"
            industry_avg_revenue = 0
            relative_position = "N/A - provide revenue data"
            insights = [
                "Provide revenue data for analysis",
                "Industry multiples will be applied when data is available"
            ]
        
        calc_time = time.time() - start_time
        logger.info(
            f"[STRATEGY] Revenue analysis complete | "
            f"time={calc_time:.3f}s | "
            f"revenue=€{revenue:,.0f}"
        )
        
        return {
            'revenue': revenue,
            'has_revenue': has_revenue,
            'revenue_multiple': revenue_multiple,
            'estimated_value': estimated_value,
            'revenue_quality': revenue_quality,
            'industry': industry,
            'business_type_id': business_type_id,
            'industry_avg_revenue': industry_avg_revenue,
            'relative_position': relative_position,
            'insights': insights,
            'confidence': 40 if has_revenue else 0,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'phase': 1
        }
    
    def _assess_revenue_quality(
        self, 
        revenue_decimal: Decimal, 
        business_type_info: Dict
    ) -> str:
        """
        Assess quality of revenue data.
        
        Args:
            revenue_decimal: Revenue value
            business_type_info: Business type information
            
        Returns:
            Quality assessment string
        """
        if revenue_decimal <= 0:
            return "no_data"
        elif revenue_decimal < to_decimal(50000):
            return "low_revenue"
        elif revenue_decimal < to_decimal(500000):
            return "moderate_revenue"
        else:
            return "high_revenue"
    
    def _calculate_relative_position(
        self, 
        revenue: float, 
        industry_avg: float
    ) -> str:
        """
        Calculate relative position vs industry average.
        
        Args:
            revenue: Company revenue
            industry_avg: Industry average revenue
            
        Returns:
            Relative position description
        """
        if industry_avg == 0:
            return "Industry average not available"
        
        ratio = revenue / industry_avg
        
        if ratio < 0.5:
            return f"Below industry average ({ratio:.1%} of avg)"
        elif ratio < 0.9:
            return f"Slightly below industry average ({ratio:.1%} of avg)"
        elif ratio < 1.1:
            return f"At industry average ({ratio:.1%} of avg)"
        elif ratio < 2.0:
            return f"Above industry average ({ratio:.1%} of avg)"
        else:
            return f"Well above industry average ({ratio:.1%} of avg)"
