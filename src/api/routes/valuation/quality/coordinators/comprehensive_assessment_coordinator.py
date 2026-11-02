"""
Comprehensive Assessment Coordinator

Handles comprehensive assessment logic (data completeness, financial health, market data quality).
Extracted from confidence_scorer.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive assessments
- Detailed logging
"""

from decimal import Decimal
from typing import Optional

from src.api.schemas import ValuationRequest
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ComprehensiveAssessmentCoordinator:
    """
    Coordinates comprehensive assessment logic.
    
    Responsibilities:
    - Assess data completeness
    - Assess financial health
    - Assess market data quality
    """
    
    def __init__(self, logger_instance=None):
        """
        Initialize comprehensive assessment coordinator.
        
        Args:
            logger_instance: Logger instance (optional)
        """
        self.logger = logger_instance or logger
    
    async def assess_data_completeness(self, request: ValuationRequest) -> Decimal:
        """
        Assess data completeness.
        
        Args:
            request: Valuation request
            
        Returns:
            Completeness score (Decimal('0.0') to Decimal('1.0'))
        """
        try:
            self.logger.info("📋 Assessing data completeness")

            score = Decimal("0.5")  # Base score
            required_fields = [
                "revenue",
                "ebitda",
                "total_assets",
                "total_debt",
                "cash",
                "employee_count",
                "founded_year",
            ]

            fields_present = 0
            for field in required_fields:
                if hasattr(request.current_year_data, field):
                    value = getattr(request.current_year_data, field, None)
                    if value is not None and value > 0:
                        fields_present += 1

            completeness = Decimal(fields_present) / Decimal(len(required_fields))
            score = Decimal("0.5") + (completeness * Decimal("0.5"))

            self.logger.info(
                f"✅ Data completeness: {completeness*100:.0f}%",
                extra={
                    "fields_present": fields_present,
                    "total_fields": len(required_fields),
                    "completeness": completeness,
                    "score": score,
                },
            )

            return score

        except Exception as e:
            self.logger.error(
                f"❌ Data completeness assessment failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return Decimal("0.5")
    
    async def assess_financial_health(self, request: ValuationRequest) -> Decimal:
        """
        Assess financial health.
        
        Args:
            request: Valuation request
            
        Returns:
            Health score (Decimal('0.0') to Decimal('1.0'))
        """
        try:
            self.logger.info("💪 Assessing financial health")

            revenue = request.current_year_data.revenue or 0
            ebitda = request.current_year_data.ebitda or 0

            if revenue == 0:
                self.logger.warning("⚠️ Zero revenue, low health score")
                return Decimal("0.3")

            margin = ebitda / revenue if revenue > 0 else 0

            # Score based on profitability
            if margin > 0.2:
                score = Decimal("0.9")
                health = "excellent"
            elif margin > 0.1:
                score = Decimal("0.75")
                health = "good"
            elif margin > 0:
                score = Decimal("0.6")
                health = "moderate"
            else:
                score = Decimal("0.4")
                health = "poor"

            self.logger.info(
                f"✅ Financial health: {health}",
                extra={
                    "revenue": revenue,
                    "ebitda": ebitda,
                    "margin": margin,
                    "score": score,
                },
            )

            return score

        except Exception as e:
            self.logger.error(
                f"❌ Financial health assessment failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return Decimal("0.6")
    
    async def assess_market_data_quality(self, request: ValuationRequest) -> Decimal:
        """
        Assess market data quality.
        
        Args:
            request: Valuation request
            
        Returns:
            Market data quality score (Decimal('0.0') to Decimal('1.0'))
        """
        try:
            self.logger.info("📈 Assessing market data quality")

            # ValuationRequest has ev_ebitda_multiple, ev_revenue_multiple, pe_ratio (dicts), not market_data
            ev_ebitda = getattr(request, "ev_ebitda_multiple", None)
            pe = getattr(request, "pe_ratio", None)
            has_ev_ebitda = ev_ebitda is not None and (
                (isinstance(ev_ebitda, dict) and ev_ebitda.get("median") is not None)
                or (not isinstance(ev_ebitda, dict) and ev_ebitda is not None)
            )
            has_pe_ratio = pe is not None and (
                (isinstance(pe, dict) and pe.get("median") is not None)
                or (not isinstance(pe, dict) and pe is not None)
            )
            comparables = getattr(request, "comparables", None) or []
            has_comparables = len(comparables) > 0

            quality_factors = [has_ev_ebitda, has_pe_ratio, has_comparables]
            quality_score = sum(quality_factors) / len(quality_factors)

            self.logger.info(
                f"✅ Market data quality: {quality_score*100:.0f}%",
                extra={
                    "has_ev_ebitda": has_ev_ebitda,
                    "has_pe_ratio": has_pe_ratio,
                    "has_comparables": has_comparables,
                    "quality_score": quality_score,
                },
            )

            return Decimal(str(quality_score))

        except Exception as e:
            self.logger.error(
                f"❌ Market data quality assessment failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return Decimal("0.5")

