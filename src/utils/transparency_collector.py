"""
Transparency Collector

Central utility to collect all transparency data during valuation calculations.
Manages both data sources and calculation steps in a thread-safe manner.

ARCHITECTURE:
- Combined tracking of data sources and calculation steps
- Thread-safe operations for concurrent valuations
- Integration with existing logging infrastructure
- Export to transparency models for API responses

USAGE:
    collector = TransparencyCollector()

    # Track data sources
    collector.track_source(
        name="Risk-Free Rate",
        value=0.025,
        source="ECB API",
        confidence=95.0
    )

    # Track calculation steps
    collector.add_calculation_step(
        description="Cost of Equity (CAPM)",
        formula="Re = Rf + β × (Rm - Rf)",
        inputs={"risk_free_rate": 0.025, "beta": 1.2},
        outputs={"cost_of_equity": 0.121},
        explanation="Using CAPM to determine required return"
    )

    # Get transparency data
    transparency = collector.get_transparency_data(
        confidence_breakdown=confidence_obj,
        range_methodology=range_obj
    )
"""

from decimal import Decimal
from threading import RLock
from typing import Any, Dict, List, Optional

from src.domain.owner_models.transparency import (
    CalculationStep,
    ComparableCompany,
    ConfidenceBreakdown,
    DataSource,
    RangeMethodology,
    TransparencyData,
)
from src.utils.data_source_tracker import DataSourceTracker
from src.utils.decimal_helpers import from_decimal, to_decimal


class TransparencyCollector:
    """
    Central collector for all transparency data during valuation

    This class provides a unified interface for collecting data sources,
    calculation steps, and other transparency information during the
    valuation process. It's thread-safe and designed to work with the
    existing logging infrastructure.

    Attributes:
        data_tracker: DataSourceTracker for external data sources
        calculation_steps: List of calculation steps
        _lock: Thread lock for safe concurrent access
        _step_counter: Auto-incrementing step number
    """

    def __init__(self):
        """Initialize the transparency collector"""
        self.data_tracker = DataSourceTracker()
        self.calculation_steps: List[CalculationStep] = []
        self.comparable_companies: List[ComparableCompany] = []
        self._lock = RLock()  # Use RLock for reentrant locking (prevents deadlock)
        self._step_counter = 0

    # Data Source Methods (delegate to DataSourceTracker)

    def track_source(self, *args, **kwargs) -> DataSource:
        """Track a data source (delegates to DataSourceTracker)"""
        return self.data_tracker.track_source(*args, **kwargs)

    def track_api_call(self, *args, **kwargs) -> DataSource:
        """Track an API call (delegates to DataSourceTracker)"""
        return self.data_tracker.track_api_call(*args, **kwargs)

    def track_database_fetch(self, *args, **kwargs) -> DataSource:
        """Track a database fetch (delegates to DataSourceTracker)"""
        return self.data_tracker.track_database_fetch(*args, **kwargs)

    def track_calculation_input(self, *args, **kwargs) -> DataSource:
        """Track a user input (delegates to DataSourceTracker)"""
        return self.data_tracker.track_calculation_input(*args, **kwargs)

    def track_default_value(self, *args, **kwargs) -> DataSource:
        """Track a default value (delegates to DataSourceTracker)"""
        return self.data_tracker.track_default_value(*args, **kwargs)

    # Calculation Step Methods

    def add_calculation_step(
        self,
        description: str,
        formula: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        explanation: str,
        step_number: Optional[int] = None,
    ) -> CalculationStep:
        """
        Add a calculation step to the transparency data

        Args:
            description: Human-readable step description
            formula: Mathematical formula or algorithm description
            inputs: Dict of input values
            outputs: Dict of output values
            explanation: Academic/business explanation
            step_number: Optional custom step number (auto-increments if None)

        Returns:
            The created CalculationStep object
        """
        with self._lock:
            if step_number is None:
                self._step_counter += 1
                step_number = self._step_counter

            step = CalculationStep(
                step_number=step_number,
                description=description,
                formula=formula,
                inputs=inputs,
                outputs=outputs,
                explanation=explanation,
            )
            self.calculation_steps.append(step)
            return step

    def add_error_step(
        self,
        description: str,
        error: Exception,
        inputs: Dict[str, Any],
        explanation: Optional[str] = None,
    ) -> CalculationStep:
        """
        Add a calculation step that failed with an error

        Args:
            description: Description of what failed
            error: The exception that occurred
            inputs: Input values that caused the failure
            explanation: Optional explanation of the error

        Returns:
            The created CalculationStep object with ERROR formula
        """
        error_explanation = explanation or f"Failed: {str(error)}"

        return self.add_calculation_step(
            description=f"{description} - FAILED",
            formula="ERROR",
            inputs={**inputs, "error": str(error), "error_type": type(error).__name__},
            outputs={},
            explanation=error_explanation,
        )

    # Comparable Company Methods

    def add_comparable_company(
        self,
        name: str,
        country: str,
        revenue: Decimal,
        similarity_score: Decimal,
        source: str,
        ebitda_multiple: Optional[Decimal] = None,
        revenue_multiple: Optional[Decimal] = None,
    ) -> ComparableCompany:
        """
        Add a comparable company to the transparency data

        Args:
            name: Company name
            country: Country code
            revenue: Annual revenue
            similarity_score: 0-100 similarity score
            source: Data source
            ebitda_multiple: Optional EV/EBITDA multiple
            revenue_multiple: Optional EV/Revenue multiple

        Returns:
            The created ComparableCompany object
        """
        with self._lock:
            company = ComparableCompany(
                name=name,
                country=country,
                revenue=revenue,
                ebitda_multiple=ebitda_multiple,
                revenue_multiple=revenue_multiple,
                similarity_score=similarity_score,
                source=source,
            )
            self.comparable_companies.append(company)
            return company

    def add_comparable_companies_batch(
        self, companies: List[Dict[str, Any]]
    ) -> List[ComparableCompany]:
        """
        Add multiple comparable companies at once

        Args:
            companies: List of dicts with company data

        Returns:
            List of created ComparableCompany objects
        """
        result = []
        for company_data in companies:
            company = self.add_comparable_company(**company_data)
            result.append(company)
        return result

    # Retrieval Methods

    def get_data_sources(self) -> List[DataSource]:
        """Get all tracked data sources"""
        return self.data_tracker.get_sources()

    def get_calculation_steps(self) -> List[CalculationStep]:
        """Get all calculation steps"""
        with self._lock:
            return self.calculation_steps.copy()

    def get_comparable_companies(self) -> Optional[List[ComparableCompany]]:
        """Get comparable companies (None if empty)"""
        with self._lock:
            return self.comparable_companies.copy() if self.comparable_companies else None

    def get_transparency_data(
        self, confidence_breakdown: ConfidenceBreakdown, range_methodology: RangeMethodology
    ) -> TransparencyData:
        """
        Build complete TransparencyData object

        Args:
            confidence_breakdown: 8-factor confidence breakdown
            range_methodology: Range calculation methodology

        Returns:
            Complete TransparencyData object
        """
        with self._lock:
            return TransparencyData(
                data_sources=self.get_data_sources(),
                calculation_steps=self.get_calculation_steps(),
                comparable_companies=self.get_comparable_companies(),
                confidence_breakdown=confidence_breakdown,
                range_methodology=range_methodology,
            )

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of collected transparency data

        Returns:
            Dict with statistics about collected data
        """
        with self._lock:
            return {
                "data_sources": len(self.data_tracker),
                "calculation_steps": len(self.calculation_steps),
                "comparable_companies": len(self.comparable_companies),
                "average_data_confidence": self.data_tracker.get_average_confidence(),
                "data_source_summary": self.data_tracker.get_source_summary(),
            }

    def clear(self):
        """Clear all collected data"""
        with self._lock:
            self.data_tracker.clear()
            self.calculation_steps.clear()
            self.comparable_companies.clear()
            self._step_counter = 0

    def __repr__(self) -> str:
        """String representation of collector"""
        return (
            f"TransparencyCollector("
            f"sources={len(self.data_tracker)}, "
            f"steps={len(self.calculation_steps)}, "
            f"comparables={len(self.comparable_companies)})"
        )
