"""
Transparency Builder

Builds TransparencyData from step results and valuation data.
Handles conversion of StepOutput to CalculationStep objects.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from src.api.schemas import ValuationRequest
from src.domain.transparency import CalculationStep, MarketDataDetails, TransparencyData
from src.utils.core import format_currency
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger


class TransparencyBuilder:
    """
    Builder for TransparencyData construction.

    Responsibilities:
    - Convert StepOutput to CalculationStep objects
    - Build TransparencyData from step results
    - Generate market data details
    """

    def __init__(self, logger: Optional[ValuationLogger] = None):
        """
        Initialize transparency builder.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or ValuationLogger(self.__class__.__name__)
        self.logger.debug("✅ TransparencyBuilder initialized")

    def convert_step_output_to_calculation_step(
        self, step_output: StepOutput, step_number: int
    ) -> CalculationStep:
        """
        Convert StepOutput from CalculationTriage to CalculationStep schema.

        Delegates to StepConverter for improved maintainability.

        Args:
            step_output: StepOutput object from CalculationTriage
            step_number: Step number (0-11)

        Returns:
            CalculationStep object with all fields populated
        """
        from src.api.routes.valuation.orchestration.builders.transparency.step_converter import (
            StepConverter,
        )

        return StepConverter.convert(step_output, step_number)

    def generate_transparency_data(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, Any],
        step_results: Optional[Dict[int, StepOutput]] = None,
    ) -> Optional[TransparencyData]:
        """
        Generate TransparencyData from step results and valuation data.

        Args:
            request: Valuation request
            detailed_results: Detailed valuation results
            step_results: Optional step results dictionary

        Returns:
            TransparencyData object or None if generation fails
        """
        try:
            # Check if Step 11's transparency report is available
            multiples_results = detailed_results.get("multiples_valuation", {})
            step_11_transparency = multiples_results.get("transparency_report")

            if step_11_transparency and isinstance(step_11_transparency, dict):
                # Use Step 11's transparency report
                return self._build_from_step_11_transparency(
                    step_11_transparency, multiples_results, request
                )

            # Otherwise, build from step results
            if step_results:
                return self._build_from_step_results(step_results, detailed_results, request)

            self.logger.warning("No step results or transparency report available")
            return None

        except Exception as e:
            self.logger.error(
                "Error generating transparency data",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return None

    def _build_from_step_11_transparency(
        self,
        step_11_transparency: Dict[str, Any],
        multiples_results: Dict[str, Any],
        request: ValuationRequest,
    ) -> TransparencyData:
        """Build TransparencyData from Step 11's transparency report."""
        calculation_steps = step_11_transparency.get("calculation_steps", [])
        calculation_step_objects = []

        for step in calculation_steps:
            try:
                step_num = step.get("step")
                key_outputs = step.get("key_outputs", {})

                # Extract output value
                if step_num == 0:
                    output_value = to_decimal(key_outputs.get("quality_score", 0))
                else:
                    output_value = Decimal("0.0")
                    if isinstance(key_outputs, dict):
                        for field in [
                            "equity_value_mid",
                            "enterprise_value_mid",
                            "valuation_mid",
                            "output",
                        ]:
                            if field in key_outputs and isinstance(
                                key_outputs[field], (int, float)
                            ):
                                output_value = to_decimal(key_outputs[field])
                                break

                calc_step = CalculationStep(
                    step_number=int(step_num),
                    calculation_name=str(step.get("name", f"Step {step_num}")),
                    formula=str(step.get("description", "")),
                    inputs={},
                    output=output_value,
                    output_formatted=(
                        f"{output_value:.1f}%"
                        if step_num == 0
                        else (
                            format_currency(output_value, currency="EUR", precision=0)
                            if output_value > 0
                            else "€0"
                        )
                    ),
                    explanation=str(step.get("description", "")),
                    calculation_type=str(step.get("name", "unknown")).lower().replace(" ", "_"),
                )
                calculation_step_objects.append(calc_step)
            except Exception as step_error:
                self.logger.warning(
                    f"Failed to convert transparency step to CalculationStep: {step_error}",
                    extra={"step": step, "error": str(step_error)},
                )

        # Build MarketDataDetails
        revenue_multiple = multiples_results.get("revenue_multiple", Decimal("0.5"))
        ebitda_multiple = multiples_results.get("ebitda_multiple", Decimal("5.0"))
        data_sources = step_11_transparency.get("data_sources", [])
        data_source = "unknown"
        if data_sources:
            first_source = data_sources[0] if isinstance(data_sources, list) else data_sources
            if isinstance(first_source, dict):
                data_source = first_source.get("source", "unknown")

        market_data = MarketDataDetails(
            industry_multiples={
                "ev_ebitda_median": ebitda_multiple,
                "ev_revenue_median": revenue_multiple,
            },
            multiples_source=(
                data_source
                if data_source != "unknown"
                else multiples_results.get("data_source", "industry_defaults")
            ),
            multiples_date=date.today(),
            multiples_sample_size=multiples_results.get("comparables_count", 0) or 0,
            risk_free_rate=Decimal("2.5"),
            risk_free_rate_source="ECB 10Y Bond",
            risk_free_rate_date=date.today(),
            market_risk_premium=Decimal("7.0"),
            market_risk_premium_source="Damodaran",
            market_risk_premium_date=date.today(),
        )

        return TransparencyData(calculation_steps=calculation_step_objects, market_data=market_data)

    def _build_from_step_results(
        self,
        step_results: Dict[int, StepOutput],
        detailed_results: Dict[str, Any],
        request: ValuationRequest,
    ) -> TransparencyData:
        """Build TransparencyData from step results."""
        calculation_steps = []

        for step_number, step_output in step_results.items():
            try:
                calc_step = self.convert_step_output_to_calculation_step(step_output, step_number)
                calculation_steps.append(calc_step)
            except Exception as e:
                self.logger.warning(
                    f"Failed to convert step {step_number} to CalculationStep",
                    extra={"error": str(e), "step_number": step_number},
                )

        # Build MarketDataDetails from detailed_results
        market_data = MarketDataDetails(
            industry_multiples={
                "ev_ebitda_median": detailed_results.get("ebitda_multiple", Decimal("5.0")),
                "ev_revenue_median": detailed_results.get("revenue_multiple", Decimal("0.5")),
            },
            multiples_source=detailed_results.get("data_source", "industry_defaults"),
            multiples_date=date.today(),
            multiples_sample_size=detailed_results.get("comparables_count", 0) or 0,
            risk_free_rate=Decimal("2.5"),
            risk_free_rate_source="ECB 10Y Bond",
            risk_free_rate_date=date.today(),
            market_risk_premium=Decimal("7.0"),
            market_risk_premium_source="Damodaran",
            market_risk_premium_date=date.today(),
        )

        return TransparencyData(calculation_steps=calculation_steps, market_data=market_data)
