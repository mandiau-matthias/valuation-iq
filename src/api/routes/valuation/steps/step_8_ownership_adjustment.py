"""
Step 7.5: Ownership Adjustment

Applies ownership percentage and control/minority adjustments to equity value.
Formula: Adjusted Equity Value = Equity Value × Ownership Percentage × (1 + Control Premium / - Minority Discount)

This step applies:
- Ownership percentage multiplier (e.g., 50% shares = 0.5x)
- Control premium for majority stakes (>50%): +10% to +30%
- Minority discount for minority stakes (<50%): -15% to -30%
- Deadlock risk discount for 50% ownership: -5% to -10%

Uses ControlMinorityAdjuster domain class for consistent tier logic and
business-type calibration following academic valuation standards (Koller, Goedhart & Wessels 2020, Pratt & Niculita 2008).
"""

from decimal import Decimal
from typing import List, Optional

from src.api.routes.valuation.triage.step_registry import register_step
from src.utils.core.data_extraction_helpers import extract_owner_employee_counts_from_request
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_8_ownership_adjustment.handlers.step_8_error_handler import (
    Step8ErrorHandler,
)
from src.api.routes.valuation.steps.step_8_ownership_adjustment.orchestrators.step_8_orchestrator import (
    Step8Orchestrator,
)

logger = get_logger(__name__)


@register_step
class Step8OwnershipAdjustment(CalculationStep):
    """
    Ownership Adjustment Step.

    Applies ownership percentage and control/minority adjustments to equity value.
    Uses ControlMinorityAdjuster domain class for consistent tier logic and
    business-type calibration. Aligned with academic valuation standards (Koller, Goedhart & Wessels 2020, Pratt & Niculita 2008).

    Adjustment Types:
    - Control Premium (>50%): +10% to +30% (majority control, operational control)
    - Minority Discount (<50%): -15% to -30% (no control, limited influence)
    - Deadlock Discount (50%): -5% to -10% (equal control, deadlock risk)

    Formula: Adjusted Equity = Equity × (Shares % / 100) × (1 + Adjustment)
    """

    def __init__(self, business_types_repo: Optional[object] = None):
        """Initialize Step 8 with orchestrator and error handler."""
        super().__init__()
        self.business_types_repo = business_types_repo
        self.orchestrator = Step8Orchestrator(self.step_name, business_types_repo)
        self.error_handler = Step8ErrorHandler(self.step_name)

    @property
    def step_number(self) -> int:
        return 8  # Step 8: Ownership Adjustment (after Step 7, before old Step 8)

    @property
    def step_name(self) -> str:
        return "Ownership Adjustment"

    @property
    def dependencies(self) -> List[int]:
        return [7]  # Depends on Step 7 (EV to Equity Conversion)
    
    @property
    def optional_dependencies(self) -> List[int]:
        """Optional dependencies that allow fallback execution."""
        return [6]  # Step 6 EV can be used as fallback when Step 7 fails

    def should_execute(self, input_data: StepInput) -> bool:
        """
        Only execute if:
        1. Business is a company (not sole trader)
        2. Shares for sale is provided and < 100%

        Sole traders always have 100% ownership, so no adjustment needed.
        If shares_for_sale is 100%, no adjustment needed (full control, no premium/discount).
        """
        request = input_data.request

        # Check if sole trader (always 100% ownership, no adjustment needed)
        from src.utils.sole_trader_detector import SoleTraderDetector

        # Use unified utility for owner/employee extraction
        num_owners, num_employees = extract_owner_employee_counts_from_request(request)
        
        is_sole_trader = SoleTraderDetector.detect(
            business_structure=getattr(request, "business_type", None),
            business_type=getattr(request, "business_type", None),
            number_of_owners=num_owners,
            number_of_employees=num_employees,
            is_sole_trader=getattr(request, "is_sole_trader", None),
            business_context=getattr(request, "business_context", None),
        )

        if is_sole_trader:
            # DEBUG: "⏭️ Step 8 skipped by step logic" at the step
            # orchestrator level carries the canonical INFO.
            logger.debug(
                "Skipping ownership adjustment: sole trader (always 100% ownership)",
                extra={"is_sole_trader": True},
            )
            return False

        # Check if shares_for_sale is provided
        shares_for_sale = getattr(request, "shares_for_sale", None)
        if shares_for_sale is None:
            logger.info(
                "Skipping ownership adjustment: shares_for_sale not provided (assuming 100%)",
                extra={"shares_for_sale": None},
            )
            return False

        # Check if shares_for_sale is 100% (no adjustment needed)
        if shares_for_sale >= 100.0:
            logger.info(
                "Skipping ownership adjustment: shares_for_sale is 100% (full control, no premium/discount)",
                extra={"shares_for_sale": shares_for_sale},
            )
            return False

        # Execute if shares_for_sale is provided and < 100%
        logger.info("Ownership adjustment will execute", extra={"shares_for_sale": shares_for_sale})
        return True

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Apply ownership percentage and control/minority adjustments to equity value.

        Formula: Adjusted Equity = Equity × (Shares % / 100) × (1 + Adjustment % / 100)
        Where Adjustment is:
        - Control Premium (>50%): +10% to +30%
        - Minority Discount (<50%): -15% to -30%
        - Deadlock Discount (50%): -5% to -10%
        """
        request = input_data.request
        context = input_data.context or {}
        correlation_id = context.get("correlation_id")

        logger.info(
            "🔍 Starting Step 8: Ownership Adjustment",
            extra={
                "step_number": 8,
                "step_name": self.step_name,
                "company_name": getattr(request, "company_name", "N/A"),
                "formula": "Adjusted Equity = Equity × (Shares % / 100) × (1 + Adjustment %)",
                "available_previous_steps": list(input_data.previous_results.keys()),
            },
        )

        # Get equity value from Step 7, fallback to Step 6 EV if Step 7 fails
        step7_output = input_data.previous_results.get(7)
        step6_output = input_data.previous_results.get(6)
        
        if not step7_output or step7_output.status != StepStatus.COMPLETED:
            # CRITICAL FIX: Use Step 6 EV values as fallback when Step 7 fails
            if step6_output and step6_output.status == StepStatus.COMPLETED:
                step6_result = step6_output.result if step6_output.result else {}
                ev_low = step6_result.get("enterprise_value_low")
                ev_mid = step6_result.get("enterprise_value_mid")
                ev_high = step6_result.get("enterprise_value_high")
                
                # BANK-GRADE: Use is not None check to preserve zero values (zero is a valid valuation)
                if ev_mid is not None:
                    logger.warning(
                        "⚠️ Step 7 unavailable, using Step 6 EV as equity approximation for Step 8",
                        extra={
                            "step_number": 8,
                            "step7_status": step7_output.status.value if step7_output else "not_found",
                            "step6_ev_mid": ev_mid,
                            "fallback_reason": "Step 7 failed, using Step 6 EV as equity approximation",
                        },
                    )
                    # BANK-GRADE FIX: Use `is not None` checks to preserve zero values
                    # The `or` operator incorrectly treats 0 as falsy, which would replace
                    # legitimate zero valuations with calculated estimates
                    equity_value_low = (
                        ev_low if ev_low is not None else ev_mid * Decimal("0.8")
                    )
                    equity_value_high = (
                        ev_high if ev_high is not None else ev_mid * Decimal("1.2")
                    )
                    # Create a Step 7-like result structure from Step 6 EV values
                    step7_like_result = {
                        "equity_value_low": equity_value_low,
                        "equity_value_mid": ev_mid,
                        "equity_value_high": equity_value_high,
                        "fallback_from_step6": True,
                        "note": "Using Step 6 EV as equity approximation (Step 7 failed)",
                    }
                    # Delegate to orchestrator with Step 6 EV values
                    return await self.orchestrator.orchestrate_execution(
                        request, step7_like_result, correlation_id
                    )
            
            # No fallback available - return error
            return self.error_handler.handle_missing_step7(
                step7_output.status.value if step7_output else None,
                list(input_data.previous_results.keys()),
            )

        # Delegate to orchestrator
        return await self.orchestrator.orchestrate_execution(
            request, step7_output.result, correlation_id
        )
