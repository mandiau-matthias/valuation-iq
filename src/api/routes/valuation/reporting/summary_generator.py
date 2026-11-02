"""
Summary Generator Module

Generates valuation summaries, key factors, risk factors, and recommendations.

RESPONSIBILITIES:
- Generate valuation summary text
- Extract key value drivers
- Identify risk factors
- Create methodology notes
- Generate recommendations

REFACTORING NOTE:
Extracted from valuation_orchestrator.py to isolate reporting logic.
"""

from typing import Any, Dict, List, Optional

from src.api.schemas import ValuationRequest
from src.api.routes.valuation.reporting.coordinators import (
    MethodologyNotesCoordinator,
    RiskFactorsExtractionCoordinator,
    SummaryGenerationCoordinator,
    ValueDriversExtractionCoordinator,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SummaryGenerator:
    """
    Generates valuation summaries and insights

    Features:
    - Summary text generation
    - Key value drivers extraction
    - Risk factor identification
    - Methodology notes
    """

    def __init__(self):
        """Initialize summary generator"""
        self.logger = logger
        
        # Initialize coordinators
        self.summary_generation_coordinator = SummaryGenerationCoordinator(self.logger)
        self.value_drivers_extraction_coordinator = ValueDriversExtractionCoordinator(self.logger)
        self.risk_factors_extraction_coordinator = RiskFactorsExtractionCoordinator(self.logger)
        self.methodology_notes_coordinator = MethodologyNotesCoordinator(self.logger)
        
        self.logger.debug("✅ SummaryGenerator initialized")

    def generate_summary(self, request: ValuationRequest, results: Dict[str, Any]) -> str:
        """
        Generate valuation summary.

        Delegates to SummaryGenerationCoordinator.

        Args:
            request: Valuation request
            results: Valuation results

        Returns:
            Summary text
        """
        return self.summary_generation_coordinator.generate_summary(request, results)

    def extract_value_drivers(
        self, request: ValuationRequest, results: Dict[str, Any]
    ) -> List[str]:
        """
        Extract key value drivers.

        Delegates to ValueDriversExtractionCoordinator.

        Priority:
        1. Use synthesizer data if available (quantitative, sophisticated)
        2. Calculate from financial metrics (quantitative)
        3. Fallback to basic logic

        Args:
            request: Valuation request
            results: Valuation results

        Returns:
            List of value driver descriptions
        """
        return self.value_drivers_extraction_coordinator.extract_value_drivers(request, results)

    def extract_risk_factors(self, request: ValuationRequest, results: Dict[str, Any]) -> List[str]:
        """
        Extract risk factors.

        Delegates to RiskFactorsExtractionCoordinator.

        Priority:
        1. Use synthesizer data if available (quantitative, sophisticated)
        2. Calculate from financial metrics and methodology divergence (quantitative)
        3. Fallback to basic logic (quantitative where possible)

        Args:
            request: Valuation request
            results: Valuation results

        Returns:
            List of risk factor descriptions
        """
        return self.risk_factors_extraction_coordinator.extract_risk_factors(request, results)

    def generate_methodology_notes(
        self,
        methodology: str,
        requested_methodology: Optional[str] = None,
        dcf_included: Optional[bool] = None,
        dcf_exclusion_reason: Optional[str] = None,
        locale: str = "nl",
        country_code: str = "BE",
    ) -> str:
        """
        Generate methodology notes with transparency about methodology selection.

        Delegates to MethodologyNotesCoordinator.

        Args:
            methodology: Actual valuation methodology used
            requested_methodology: Methodology that was requested (if different from actual)
            dcf_included: Whether DCF was included in the valuation
            dcf_exclusion_reason: Reason DCF was excluded (if applicable)
            locale: BCP-47-ish language tag (en*/nl*)
            country_code: Firm jurisdiction for translation variants

        Returns:
            Methodology notes text with transparency about selection
        """
        return self.methodology_notes_coordinator.generate_methodology_notes(
            methodology,
            requested_methodology,
            dcf_included,
            dcf_exclusion_reason,
            locale=locale,
            country_code=country_code,
        )
