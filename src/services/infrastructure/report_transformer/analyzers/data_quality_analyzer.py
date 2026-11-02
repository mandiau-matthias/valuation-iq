"""
Data Quality Analyzer

WHAT: Analyzes data quality and determines limitations/strategies
WHY: Separates data quality analysis logic (SRP compliance)
HOW: Analyzes historical data availability, EBITDA status, generates disclosures

SINGLE RESPONSIBILITY: Data quality analysis ONLY
"""

from decimal import Decimal
from typing import Dict, Any, Optional, TYPE_CHECKING
from src.utils.logging import get_logger
from src.services.infrastructure.report_confidence import confidence_score_percent

if TYPE_CHECKING:
    from src.api.schemas import ValuationRequest, ValuationResponse

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)

logger = get_logger(__name__)


class DataQualityAnalyzer:
    """
    Analyzes data quality for valuation reports.
    
    SINGLE RESPONSIBILITY: Data quality analysis ONLY
    
    This service:
    - Analyzes data limitations
    - Determines negative EBITDA strategy
    - Calculates years of historical data
    - Generates data limitation disclosures
    
    NO extraction, NO transformation, NO validation - pure analysis only.
    """
    
    def __init__(self):
        """Initialize data quality analyzer."""
        self.logger = logger
    
    def analyze_data_limitations(
        self,
        request: ValuationRequestProtocol,
        response: ValuationResponseProtocol
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze data limitations and generate disclosure.
        
        WHAT: Determines if historical data is insufficient
        WHY: Reports need to disclose data limitations to users
        HOW: Checks years_of_data, generates disclosure if <3 years
        
        Args:
            request: ValuationRequest
            response: ValuationResponse
        
        Returns:
            Data limitation disclosure dict or None if sufficient data:
            - message: Human-readable limitation message
            - impacts: List of impact statements
            - confidence_cap: Capped confidence score
            - confidence_cap_reason: Reason for capping
        
        Business Rules:
        - <3 years of data = limited
        - Caps confidence score at 75% for limited data
        """
        years_of_data = self.calculate_years_of_data(request)
        confidence_score_pct = confidence_score_percent(response.confidence_score)
        
        if years_of_data < 3:
            disclosure = {
                'message': f"Only {years_of_data} year(s) of historical data available. This limits trend analysis and normalization capabilities.",
                'impacts': [
                    "Limited ability to identify historical trends",
                    "Reduced confidence in normalized metrics",
                    "Greater reliance on industry benchmarks"
                ],
                'confidence_cap': min(confidence_score_pct, Decimal("75")) if confidence_score_pct is not None else None,
                'confidence_cap_reason': "Limited historical data constrains confidence score"
            }
            
            self.logger.info(
                "Data limitation disclosure generated",
                extra={
                    'years_of_data': years_of_data,
                    'confidence_cap': disclosure['confidence_cap']
                }
            )
            
            return disclosure
        
        return None
    
    def determine_negative_ebitda_strategy(self, request: ValuationRequestProtocol) -> Optional[str]:
        """
        Determine strategy for negative EBITDA cases.
        
        WHAT: Determines how to value companies with negative EBITDA
        WHY: Templates need to know which valuation approach to use
        HOW: Checks EBITDA sign, revenue availability
        
        Args:
            request: ValuationRequest
        
        Returns:
            Strategy string or None:
            - 'revenue_multiples': Use revenue multiples (EBITDA negative, revenue positive)
            - 'high_risk': High risk case (both negative)
            - None: EBITDA is positive
        
        Business Rules:
        - Negative EBITDA + Positive Revenue = Use revenue multiples
        - Negative EBITDA + Negative/Zero Revenue = High risk
        """
        # Extract EBITDA and revenue
        ebitda = None
        revenue = None
        
        if hasattr(request, 'current_year_data') and request.current_year_data:
            ebitda = getattr(request.current_year_data, 'ebitda', None)
            revenue = getattr(request.current_year_data, 'revenue', None)
        
        # Determine strategy
        if ebitda and ebitda < 0:
            if revenue and revenue > 0:
                self.logger.info(
                    "Negative EBITDA strategy: revenue multiples",
                    extra={'ebitda': str(ebitda), 'revenue': str(revenue)}
                )
                return 'revenue_multiples'
            else:
                self.logger.warning(
                    "Negative EBITDA strategy: high risk",
                    extra={'ebitda': str(ebitda), 'revenue': str(revenue) if revenue else None}
                )
                return 'high_risk'
        
        return None
    
    def calculate_years_of_data(self, request: ValuationRequestProtocol) -> int:
        """
        Calculate number of years of historical data.
        
        Args:
            request: ValuationRequest
        
        Returns:
            Number of historical years (0 if none)
        """
        historical_years_data = getattr(request, 'historical_years_data', [])
        years_of_data = len(historical_years_data) if historical_years_data else 0
        
        self.logger.debug(
            "Years of historical data calculated",
            extra={'years_of_data': years_of_data}
        )
        
        return years_of_data
