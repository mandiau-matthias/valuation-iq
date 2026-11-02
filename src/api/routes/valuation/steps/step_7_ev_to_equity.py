"""
from decimal import Decimal
Step 7: EV to Equity Conversion

Converts Enterprise Value to Equity Value by adjusting for net debt.
Formula: Equity Value = EV - Net Debt (where Net Debt = Total Debt - Cash)

This step uses the EquityValueConverter domain class for consistent conversion logic,
comprehensive validation, and edge case handling following McKinsey/Bain standards.
"""

from typing import List

from src.api.routes.valuation.triage.step_registry import register_step
from src.utils.logging import get_logger

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_7_ev_to_equity.handlers.step_7_error_handler import (
    Step7ErrorHandler,
)
from src.api.routes.valuation.steps.step_7_ev_to_equity.orchestrators.step_7_orchestrator import (
    Step7Orchestrator,
)

logger = get_logger(__name__)


@register_step
class Step7EVToEquity(CalculationStep):
    """
    Enterprise Value to Equity Value Conversion Step.

    Formula: Equity Value = Enterprise Value - Net Debt
    Where: Net Debt = Total Debt - Cash and Cash Equivalents

    Uses EquityValueConverter domain class for:
    - Balance sheet data extraction and validation
    - Net debt calculation
    - EV to equity conversion
    - Range validation (low < mid < high)
    - Edge case handling (negative equity, high debt, cash-rich scenarios)

    If balance sheet data unavailable, assumes net debt = 0
    """

    def __init__(self):
        """Initialize Step 7 with orchestrator and error handler."""
        super().__init__()
        self.orchestrator = Step7Orchestrator(self.step_name)
        self.error_handler = Step7ErrorHandler(self.step_name)

    @property
    def step_number(self) -> int:
        return 7

    @property
    def step_name(self) -> str:
        return "EV to Equity Conversion"

    @property
    def dependencies(self) -> List[int]:
        # Require Step 3 (base EV) as minimum
        # Steps 4-6 are optional (fallback logic handles missing steps)
        return [3]

    def should_execute(self, input_data: StepInput) -> bool:
        return True  # Always convert EV to equity

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Convert EV to equity value using domain class.

        Formula: Equity Value = Enterprise Value - Net Debt
        Where: Net Debt = Total Debt - Cash (or Total Debt - Excess Cash if exemption applied)

        Operating Cash Exemption (for small companies):
        - Operating Cash = Revenue × Operating Cash % (business-type specific)
        - Excess Cash = Total Cash - Operating Cash
        - Net Debt = Total Debt - Excess Cash (exemption) or Total Debt - Total Cash (standard)
        """
        request = input_data.request

        logger.info(
            "🔍 Starting Step 7: EV to Equity Conversion",
            extra={
                "step_number": 7,
                "step_name": self.step_name,
                "company_name": getattr(request, "company_name", "N/A"),
                "formula": "Equity Value = Enterprise Value - Net Debt",
                "net_debt_formula": "Net Debt = Total Debt - Cash (or Total Debt - Excess Cash if exemption)",
                "available_previous_steps": list(input_data.previous_results.keys()),
            },
        )

        # Delegate to orchestrator
        correlation_id = input_data.context.get("correlation_id") if input_data.context else None
        return await self.orchestrator.orchestrate_execution(
            request, input_data.previous_results, correlation_id
        )
