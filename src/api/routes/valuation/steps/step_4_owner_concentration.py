from decimal import Decimal


"""
Step 4: Owner Concentration Adjustment

Applies discount based on key person risk (owner/employee ratio).
CONDITIONAL: Only executes if owner and employee data is provided.
"""

from typing import Any, Dict, List, Optional

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
from src.api.routes.valuation.triage.step_registry import register_step
from src.config.decimal_constants import DecimalConstants
from src.domain.owner_concentration_adjuster import OwnerConcentrationAdjuster
from src.utils.decimal_helpers import Money, apply_discount, bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger
from src.utils.sole_trader_detector import SoleTraderDetector

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_4_owner_concentration.builders import (
    Step4ResultBuilder,
)
from src.api.routes.valuation.steps.step_4_owner_concentration.calculators import (
    Step4Calculator,
)
from src.api.routes.valuation.steps.step_4_owner_concentration.handlers import (
    Step4ErrorHandler,
)

# Import new modular components
from src.api.routes.valuation.steps.step_4_owner_concentration.orchestrators import (
    Step4Orchestrator,
)
from src.api.routes.valuation.steps.step_4_owner_concentration.validators import (
    Step4Validator,
)
from src.api.routes.valuation.steps.step_utilities import extract_owner_employee_counts

logger = get_logger(__name__)


@register_step
class Step4OwnerConcentration(CalculationStep):
    """
    Owner Concentration Adjustment Step.

    Uses OwnerConcentrationAdjuster domain class for consistent tier logic and
    business-type calibration. Aligned with Big 4 methodology.

    Risk Tiers (aligned with domain class):
    - Ratio > 0.5: CRITICAL (-20%)
    - Ratio Decimal('0.25')-0.5: HIGH (-12%)
    - Ratio Decimal('0.10')-0.25: MEDIUM (-7%)
    - Ratio < 0.10: LOW (-3%)

    Note: Step 4 calculates ratio as owners/employees (can be >Decimal('1.0')), which is
    normalized to Decimal('0.0')-Decimal('1.0') range for domain class tier lookup. Ratios >Decimal('1.0') map
    to CRITICAL tier.

    Cascading Formula: Multiple_adjusted = Multiple_before × (1 + adjustment)
    Then: EV_adjusted = Metric × Multiple_adjusted
    """

    @property
    def step_number(self) -> int:
        return 4

    @property
    def step_name(self) -> str:
        return "Owner Concentration Adjustment"

    def __init__(self, business_types_repo: Optional[object] = None):
        self.business_type_triage = BusinessTypeTriageEngine()
        # Initialize domain class adjuster for tier logic and calibration
        self.owner_adjuster = OwnerConcentrationAdjuster(business_types_repo=business_types_repo)

        # Initialize new modular components
        self.validator = Step4Validator()
        self.calculator = Step4Calculator()
        self.error_handler = Step4ErrorHandler(step_name=self.step_name)
        self.result_builder = Step4ResultBuilder()
        self.orchestrator = Step4Orchestrator(
            owner_adjuster=self.owner_adjuster,
            validator=self.validator,
            calculator=self.calculator,
            result_builder=self.result_builder,
            error_handler=self.error_handler,
            step_name=self.step_name,
        )

    @property
    def dependencies(self) -> List[int]:
        return [3]  # Depends on base EV

    def should_execute(self, input_data: StepInput) -> bool:
        """
        Only execute if owner and employee data provided AND business type requires it.

        SOLE TRADER OPTIMIZATION:
        - Sole traders should always execute (auto-apply maximum discount)
        - Don't require employee data for sole traders (always 0-1 employees)
        - Auto-detect sole traders and apply maximum owner concentration discount
        """
        request = input_data.request

        # SOLE TRADER DETECTION: Auto-detect and always execute for sole traders
        is_sole_trader = SoleTraderDetector.detect(
            business_structure=getattr(request, "business_type", None),  # May be 'sole-trader'
            business_type=getattr(request, "business_type", None),
            number_of_owners=getattr(request, "number_of_owners", None),
            number_of_employees=getattr(request, "number_of_employees", None),
            is_sole_trader=getattr(request, "is_sole_trader", None),
            business_context=getattr(request, "business_context", None),
        )

        if is_sole_trader:
            # Sole traders should always execute (auto-apply maximum discount)
            # Don't require employee data (sole traders typically have 0-1 employees)
            # DEBUG: routing decision; the Step 4 execution log carries the
            # resulting adjustment.
            logger.debug(
                "✅ Owner concentration step will execute for sole trader (auto-apply maximum discount)",
                extra={"is_sole_trader": True},
            )
            return True

        # Check data availability (for non-sole traders)
        # CRITICAL FIX: Check multiple data sources (same as execute method)
        num_owners = None
        num_employees = None

        # DIAGNOSTIC: Log request attributes
        logger.debug(
            "🔍 DIAGNOSTIC Step 4 should_execute: Checking owner/employee data sources",
            extra={
                "step_number": 4,
                "has_number_of_owners_attr": hasattr(request, "number_of_owners"),
                "has_number_of_employees_attr": hasattr(request, "number_of_employees"),
                "has_business_context_attr": hasattr(request, "business_context"),
                "has_current_year_data_attr": hasattr(request, "current_year_data"),
                "is_sole_trader": is_sole_trader,
            },
        )

        # Use shared utility from step_utilities.py to avoid duplication
        num_owners, num_employees = extract_owner_employee_counts(request)

        if num_owners is not None and num_employees is not None:
            logger.debug(
                "🔍 DIAGNOSTIC Step 4: Extracted from shared utility",
                extra={
                    "step_number": 4,
                    "num_owners": num_owners,
                    "num_employees": num_employees,
                    "source": "step_utilities.extract_owner_employee_counts",
                },
            )

        has_owner_data = num_owners is not None and num_employees is not None

        # DIAGNOSTIC: Log final decision
        logger.debug(
            "🔍 DIAGNOSTIC Step 4 should_execute: Final data check",
            extra={
                "step_number": 4,
                "num_owners": num_owners,
                "num_employees": num_employees,
                "has_owner_data": has_owner_data,
                "will_execute": has_owner_data,
            },
        )

        if not has_owner_data:
            logger.warning(
                "⚠️  Step 4 will execute with missing-data branch — owner/employee inputs absent. "
                "Letting the step run so the handler can emit a HIGH-severity quality warning "
                "instead of a silent skip.",
                extra={
                    "num_owners": num_owners,
                    "num_employees": num_employees,
                    "has_direct_attrs": hasattr(request, "number_of_owners")
                    and hasattr(request, "number_of_employees"),
                    "has_business_context": hasattr(request, "business_context"),
                    "has_current_year_data": hasattr(request, "current_year_data"),
                },
            )
            # Return True so execute() runs the orchestration and the error handler
            # produces a structured quality_warning. The handler will return SKIPPED.
            return True

        # Business-type-aware logic: Some business types have less owner dependency risk
        business_category = self.business_type_triage.get_business_type_category(
            getattr(request, "business_type_id", None),
            getattr(request, "business_model", None),
            getattr(request, "industry", None),
            category_id=getattr(request, "category_id", None),
        )

        # Large SaaS companies (>€10M) have less owner dependency risk
        if business_category and getattr(business_category, "value", None) == "saas_software":
            revenue = getattr(request.current_year_data, "revenue", 0) or 0
            if revenue > 10_000_000:
                logger.info(
                    "⏭️  Owner concentration step skipped: Large SaaS company (low owner dependency risk)",
                    extra={
                        "revenue": revenue,
                        "business_category": getattr(business_category, "value", "unknown"),
                    },
                )
                return False

        return True

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Apply owner concentration adjustment.

        Formula: Multiple_adjusted = Multiple_before × (1 + adjustment)
        Where adjustment is negative (discount) based on owner/employee ratio.

        Risk Tiers:
        - Ratio > 0.5: CRITICAL (-20%)
        - Ratio Decimal('0.25')-0.5: HIGH (-12%)
        - Ratio Decimal('0.10')-0.25: MEDIUM (-7%)
        - Ratio < 0.10: LOW (-3%)
        """
        request = input_data.request
        correlation_id = input_data.context.get("correlation_id") if input_data.context else None

        logger.info(
            "🔍 Starting Step 4: Owner Concentration Adjustment",
            extra={
                "step_number": 4,
                "step_name": self.step_name,
                "company_name": getattr(request, "company_name", "N/A"),
                "dependencies": self.dependencies,
                "available_previous_steps": list(input_data.previous_results.keys()),
                "formula": "Multiple_adjusted = Multiple_before × (1 + adjustment)",
                "correlation_id": correlation_id,
            },
        )

        # Get Step 3 results
        step3 = self.get_previous_step_result(3, input_data.previous_results)

        # Validate Step 3
        is_valid, error_msg = self.validator.validate_step3_data(step3)
        if not is_valid:
            return self.error_handler.handle_step3_missing(list(input_data.previous_results.keys()))

        logger.debug(
            "📥 Step 4 input data extracted from Step 3",
            extra={
                "step_number": 4,
                "step3_keys": list(step3.keys()) if step3 else [],
                "ev_low": step3.get("enterprise_value_low"),
                "ev_mid": step3.get("enterprise_value_mid"),
                "ev_high": step3.get("enterprise_value_high"),
            },
        )

        try:
            # Orchestrate main execution
            result_dict, metadata_dict = await self.orchestrator.orchestrate_execution(
                request=request, step3=step3, correlation_id=correlation_id
            )

            if result_dict is None:
                # Error occurred during orchestration
                error_msg = metadata_dict.get("error", "Unknown error during orchestration")
                if "Owner/employee data not available" in error_msg:
                    return self.error_handler.handle_owner_employee_data_missing()
                elif "Invalid type" in error_msg:
                    return self.error_handler.handle_invalid_type(None, None, Exception(error_msg))
                elif "negative values" in error_msg:
                    return self.error_handler.handle_negative_values(0, 0)
                elif "Invalid multiple" in error_msg:
                    return self.error_handler.handle_invalid_multiple_or_metric(0, 0)
                else:
                    return StepOutput(
                        step_number=4,
                        step_name=self.step_name,
                        status=StepStatus.FAILED,
                        result={},
                        error=error_msg,
                    )

            # Value chain logging
            logger.info(
                "🔍 Step 4: VALUE CHAIN - Owner Concentration Impact",
                extra={
                    "step_number": 4,
                    "ev_mid_before": result_dict.get("ev_change", 0)
                    + result_dict.get("enterprise_value_mid", 0),
                    "ev_mid_after": result_dict.get("enterprise_value_mid", 0),
                    "adjustment_percentage": result_dict.get("adjustment_percentage", 0),
                    "ev_change": result_dict.get("ev_change", 0),
                    "value_chain_step": 4,
                    "next_step": "Step 5 (Size Discount)",
                    "correlation_id": correlation_id,
                },
            )

            # Create StepOutput
            return StepOutput(
                step_number=4,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,
                result=result_dict,
                metadata=metadata_dict,
            )

        except Exception as e:
            logger.error(
                f"❌ Step 4 exception occurred: {str(e)}",
                extra={
                    "step_number": 4,
                    "error_type": type(e).__name__,
                    "correlation_id": correlation_id,
                },
                exc_info=True,
            )
            return StepOutput(
                step_number=4,
                step_name=self.step_name,
                status=StepStatus.FAILED,
                result={},
                error=f"Exception during execution: {str(e)}",
            )
