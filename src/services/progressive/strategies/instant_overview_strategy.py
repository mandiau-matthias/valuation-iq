"""
Instant Overview Calculation Strategy

Calculates instant overview section for progressive valuation reports.

SINGLE RESPONSIBILITY: Instant overview calculation ONLY.

Author: UpSwitch CTO Team
Date: December 9, 2025
Status: Production Ready
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.progressive.section_calculations.coordinators import DataCompletenessCoordinator
    from src.services.progressive.business_type_info_extractor import BusinessTypeInfoExtractor

from src.utils.core.data_extraction_helpers import extract_revenue_from_collected_data
from src.utils.decimal_helpers import from_decimal
from .calculation_strategy import CalculationStrategy

# Academic provenance tracking
try:
    from src.services.academic.decorators import track_academic_provenance
    ACADEMIC_TRACKING_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Academic provenance tracking not available")
    ACADEMIC_TRACKING_AVAILABLE = False
    # Create no-op decorator if import fails
    def track_academic_provenance(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


logger = logging.getLogger(__name__)


class InstantOverviewStrategy(CalculationStrategy):
    """
    Calculates instant overview section.
    
    SINGLE RESPONSIBILITY: Instant overview calculation ONLY.
    
    Shows company name, industry, preliminary value range, and data completeness.
    This is the first section users see (<500ms target).
    
    BANK-GRADE DESIGN:
    - Dependency injection for testability
    - Academic provenance tracking
    - Comprehensive logging
    - Performance monitoring
    """
    
    def __init__(
        self,
        completeness_coordinator: "DataCompletenessCoordinator",
        business_type_extractor: "BusinessTypeInfoExtractor",
    ):
        """
        Initialize with dependencies.
        
        Args:
            completeness_coordinator: Coordinator for data completeness calculations
            business_type_extractor: Extractor for business type information
        """
        self.completeness_coordinator = completeness_coordinator
        self.business_type_extractor = business_type_extractor
    
    @track_academic_provenance(
        calculation_id="instant_overview",
        section_name="Instant Overview",
        extract_inputs=lambda args, kwargs: {
            'company_name': kwargs.get('context', {}).get('collected_data', {}).get('company_name'),
            'industry': kwargs.get('context', {}).get('collected_data', {}).get('industry'),
            'revenue': kwargs.get('context', {}).get('collected_data', {}).get('revenue')
        },
        extract_outputs=lambda result: {
            'data_completeness': result.get('data_completeness'),
            'has_valuation_estimate': result.get('has_valuation_estimate')
        }
    )
    async def calculate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate instant overview section data.
        
        Args:
            context: Conversation context with collected_data
            
        Returns:
            Dictionary with instant overview data for template rendering
            
        Raises:
            ValueError: If context is invalid
        """
        logger.info("[STRATEGY] Calculating instant overview")
        start_time = time.time()
        
        # Validate context
        self._validate_context(context)
        
        collected_data = context.get('collected_data', {})
        
        # WORLD-CLASS: Derive industry and business_model from business_type_id
        industry, business_model, business_type_id, _ = \
            self.business_type_extractor.derive_industry_and_business_model(collected_data)
        
        # Extract basic info
        company_name = collected_data.get('company_name', 'Your Business')
        country = collected_data.get('country', 'Belgium')
        
        # Calculate data completeness using coordinator
        completeness_data = self.completeness_coordinator.calculate_data_completeness(
            collected_data
        )
        data_completeness = completeness_data['data_completeness']
        collected_count = completeness_data['data_collected']
        
        # Generate preliminary value estimate using coordinator
        estimate_data = self.completeness_coordinator.generate_preliminary_estimate(
            collected_data
        )
        estimated_value_low = estimate_data['estimated_value_low']
        estimated_value_mid = estimate_data['estimated_value_mid']
        estimated_value_high = estimate_data['estimated_value_high']
        has_valuation_estimate = estimate_data['has_valuation_estimate']
        
        # Extract revenue for quick insights
        revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)
        
        # Build quick insights
        quick_insights = self._build_quick_insights(
            has_revenue=has_revenue,
            revenue_decimal=revenue_decimal,
            industry=industry,
            business_type_id=business_type_id,
            has_valuation_estimate=has_valuation_estimate,
            collected_count=collected_count
        )
        
        calc_time = time.time() - start_time
        logger.info(
            f"[STRATEGY] Instant overview complete | "
            f"time={calc_time:.3f}s | "
            f"completeness={data_completeness}%"
        )
        
        return {
            'company_name': company_name,
            'industry': industry,
            'country': country,
            'estimated_value_low': estimated_value_low,
            'estimated_value_mid': estimated_value_mid,
            'estimated_value_high': estimated_value_high,
            'has_valuation_estimate': has_valuation_estimate,
            'data_completeness': data_completeness,
            'data_collected': collected_count,
            'data_total': completeness_data.get('data_total', 10),
            'business_type_id': business_type_id,
            'business_model': business_model,
            'quick_insights': quick_insights,
            'confidence': 30,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'phase': 1
        }
    
    def _build_quick_insights(
        self,
        has_revenue: bool,
        revenue_decimal,
        industry: str,
        business_type_id: str,
        has_valuation_estimate: bool,
        collected_count: int
    ) -> list:
        """
        Build quick insights list.
        
        Args:
            has_revenue: Whether revenue data is available
            revenue_decimal: Revenue value (Decimal)
            industry: Industry name
            business_type_id: Business type identifier
            has_valuation_estimate: Whether valuation estimate is available
            collected_count: Number of data points collected
            
        Returns:
            List of quick insight strings
        """
        insights = []
        
        if has_revenue:
            insights.append(
                f"Revenue: €{from_decimal(revenue_decimal, precision=0):,.0f}"
            )
        if industry:
            insights.append(f"Industry: {industry}")
        if business_type_id:
            insights.append(f"Business Type: {business_type_id}")
        if not has_valuation_estimate:
            insights.append(
                "Provide revenue data to see your estimated valuation range"
            )
        elif collected_count >= 3:
            insights.append("Sufficient data for preliminary estimate")
        
        return insights
