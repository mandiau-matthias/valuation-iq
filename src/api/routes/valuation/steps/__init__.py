"""
Modular calculation steps for the valuation engine.

This package contains the 12-step modular calculation system (Steps 0-11)
that replaces the monolithic MultiplesCalculator.calculate() method.

Steps are automatically registered when imported.
"""

from decimal import Decimal

# Import all step implementations to trigger registration
# Note: step_0_data_quality is both a file and a directory, so import from the file explicitly
from src.api.routes.valuation.steps.step_0_data_quality import Step0DataQuality
# Note: step_2_5_multiple_calibration is both a file and a directory, import from file explicitly
from src.api.routes.valuation.steps.step_2_5_multiple_calibration import Step25MultipleCalibration
from src.utils.decimal_helpers import from_decimal, to_decimal

from .base_step import CalculationStep, StepInput, StepOutput, StepStatus

from . import step_1_input_validation
from . import step_2_benchmarking
from . import step_2_7_sde_calculation
from . import step_3_base_ev
from . import step_4_owner_concentration
from . import step_4_5_revenue_trend
from . import step_5_size_discount
from . import step_6_liquidity_discount
from . import step_7_ev_to_equity
from . import step_8_ownership_adjustment
from . import step_9_confidence_score
from . import step_10_range_methodology
from . import step_11_final_synthesis

from .step_1_input_validation import Step1InputValidation
from .step_2_benchmarking import Step2Benchmarking
from .step_2_7_sde_calculation import Step27SDECalculation
from .step_3_base_ev import Step3BaseEV
from .step_4_owner_concentration import Step4OwnerConcentration
from .step_4_5_revenue_trend import Step45RevenueTrend
from .step_5_size_discount import Step5SizeDiscount
from .step_6_liquidity_discount import Step6LiquidityDiscount
from .step_7_ev_to_equity import Step7EVToEquity
from .step_8_ownership_adjustment import Step8OwnershipAdjustment
from .step_9_confidence_score import Step9ConfidenceScore
from .step_10_range_methodology import Step10RangeMethodology
from .step_11_final_synthesis import Step11FinalSynthesis

__all__ = [
    # Base classes
    "CalculationStep",
    "StepInput",
    "StepOutput",
    "StepStatus",
    # Step implementations
    "Step0DataQuality",
    "Step1InputValidation",
    "Step2Benchmarking",
    "Step27SDECalculation",
    "Step3BaseEV",
    "Step4OwnerConcentration",
    "Step45RevenueTrend",
    "Step5SizeDiscount",
    "Step6LiquidityDiscount",
    "Step7EVToEquity",
    "Step8OwnershipAdjustment",
    "Step9ConfidenceScore",
    "Step10RangeMethodology",
    "Step11FinalSynthesis",
]
