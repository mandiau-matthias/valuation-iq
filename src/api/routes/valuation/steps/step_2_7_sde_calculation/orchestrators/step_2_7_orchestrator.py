"""
Step 2.7 Orchestrator

Orchestrates the SDE (Seller's Discretionary Earnings) calculation step.

This step calculates SDE-based valuation for small, owner-operated businesses.
Integrates with Venus normalization data and Titan's database-driven multiples.

ACADEMIC FOUNDATION:
- Trugman (2017): "Understanding Business Valuation"
- West & Jones (2012): "Handbook of Business Valuation"
- BizBuySell (2024): Market Report
- Pepperdine (2024): Private Capital Markets

@author UpSwitch CTO Team
@date January 2026
"""

import time
from decimal import Decimal
from typing import Any, Dict, Optional

from src.domain.sde_engine import SDEComponents
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus
from ..builders.sde_bridge_builder import build_sde_bridge
from ..builders.step_2_7_result_builder import Step27ResultBuilder
from ..calculators.step_2_7_sde_calculator import Step27SDECalculator
from ..handlers.step_2_7_error_handler import Step27ErrorHandler

logger = get_logger(__name__)


class Step27Orchestrator:
    """
    Orchestrates the SDE calculation step.

    Responsibilities:
    1. Determine SDE appropriateness based on business characteristics
    2. Calculate SDE from financials (using Venus normalization if available)
    3. Apply industry-specific SDE multiple (from Titan database)
    4. Calculate SDE-based enterprise value with range
    """

    def __init__(self, step_name: str = "SDE Calculation"):
        """
        Initialize the orchestrator.

        Args:
            step_name: Display name for the step
        """
        self.step_name = step_name
        self.step_number = 2.7
        self.error_handler = Step27ErrorHandler(step_name)
        self.calculator = Step27SDECalculator()
        self.result_builder = Step27ResultBuilder(step_name)

    async def orchestrate_execution(
        self,
        request: Any,
        step1_result: Dict[str, Any],
        step2_result: Dict[str, Any],
        correlation_id: Optional[str] = None,
        execution_start_time: Optional[float] = None,
    ) -> StepOutput:
        """
        Orchestrate the SDE calculation execution.

        Args:
            request: Valuation request with business data
            step1_result: Result from Step 1 (Input Validation)
            step2_result: Result from Step 2 (Benchmarking)
            correlation_id: Correlation ID for tracing
            execution_start_time: Start time for execution tracking

        Returns:
            StepOutput with SDE calculation results
        """
        start_time = execution_start_time or time.time()

        # DEBUG: per-step entry breadcrumb; "Step 2.7: SDE Calculation Complete"
        # below is the canonical exit.
        logger.debug(
            "🔍 Step 2.7: Starting SDE Calculation",
            extra={
                "step_number": self.step_number,
                "correlation_id": correlation_id,
            },
        )

        try:
            # Extract inputs
            revenue, ebitda, net_income = self.calculator.extract_sde_inputs(step1_result, request)

            # Get number of owners
            num_owners = 1
            if hasattr(request, "number_of_owners") and request.number_of_owners:
                num_owners = request.number_of_owners
            elif hasattr(request, "business_context"):
                business_context = request.business_context or {}
                num_owners = business_context.get("number_of_owners", 1)

            # Get industry
            industry = getattr(request, "industry", "services")
            if hasattr(request, "business_type_id"):
                industry = request.business_type_id or industry

            # Check if SDE is appropriate
            business_size = self.calculator.classify_business_size(revenue)
            category = getattr(request, "category_id", "other")

            is_appropriate, reason = self.calculator.is_sde_appropriate(
                revenue, num_owners, category
            )

            # If not appropriate, skip step
            if not is_appropriate:
                return self.error_handler.handle_not_applicable(reason, from_decimal(revenue))

            # Check for required data
            if ebitda <= 0:
                return self.error_handler.handle_missing_data(["ebitda"])

            # Get normalization metadata from Titan/Venus
            ebitda_normalization_metadata = None
            titan_normalization_used = False
            if hasattr(request, "current_year_data") and request.current_year_data:
                ebitda_normalization_metadata = getattr(
                    request.current_year_data, "ebitda_normalization_metadata", None
                )
                if ebitda_normalization_metadata:
                    titan_normalization_used = True

            # Calculate SDE
            sde_components = self.calculator.calculate_sde_from_ebitda(
                ebitda,
                revenue,
                business_size,
                ebitda_normalization_metadata,
            )

            # When the user explicitly provided an owner salary add-back
            # via the Venus SDE panel, use it instead of the benchmark
            # estimate so the engine result matches the preview.
            explicit_addback = to_decimal(getattr(request, "owner_salary_addback", None) or 0)
            if explicit_addback > 0:
                sde_components = SDEComponents(
                    net_income=sde_components.net_income,
                    owner_salary=explicit_addback,
                    owner_benefits=Decimal("0"),
                    owner_perks=Decimal("0"),
                    depreciation=sde_components.depreciation,
                    amortization=sde_components.amortization,
                    interest_expense=sde_components.interest_expense,
                    non_recurring_expenses=sde_components.non_recurring_expenses,
                    non_operating_income=sde_components.non_operating_income,
                    total_sde=ebitda + explicit_addback,
                )

            sde = sde_components.total_sde

            # Handle negative SDE
            if sde <= 0:
                return self.error_handler.handle_negative_sde(from_decimal(sde))

            # Get SDE calibration from Titan (database-driven multiples)
            sde_calibration = getattr(request, "sde_calibration", None)
            database_multiples_used = sde_calibration is not None

            # Get SDE multiple (the *base* multiple — the SDE channel below
            # is the single source of truth for the post-cascade applied
            # multiple, owner-concentration / size / DLOM / Belgian-premium
            # adjustments, and the percentile range).
            base_multiple, base_p25, base_p75, data_source = self.calculator.get_sde_multiple(
                industry,
                business_size,
                sde_calibration,
            )

            country_code = getattr(request, "country_code", "BE")

            # Optional engine-supplied owner concentration tier. The channel
            # falls back to a default derived from num_owners when absent.
            owner_concentration_override = (
                getattr(request, "owner_concentration_tier", None)
                or (sde_calibration or {}).get("sde_owner_concentration_tier")
                or None
            )

            # Belgian market premium override — preserves the existing
            # Belgian +5 % anchor when the country code is BE.
            be_premium_override = None
            if country_code != "BE":
                # Non-BE: no Belgian premium.
                be_premium_override = Decimal("0")

            # Run the SDE channel — produces the applied multiple, EV /
            # equity ranges, and the calibration cascade waterfall.
            from src.services.reports.sde_channel import SdeChannelInputs, build_sde_channel

            # ── Wire debt and cash from the request when available ──
            # The SDE channel computes BOTH enterprise_value and equity_value
            # internally, but only if it knows the net debt position. Passing
            # zero hardcoded would make ``equity_value == enterprise_value``,
            # which is fine for sole-traders but materially wrong for any
            # business with debt. Pull from the request balance sheet when
            # present; fall back to zero with a high-signal warning so we
            # can spot debt-bearing valuations using the wrong unit.
            sde_total_debt = to_decimal(getattr(request, "total_debt", 0) or 0)
            sde_cash = to_decimal(getattr(request, "cash", 0) or 0)
            if sde_total_debt > 0 or sde_cash > 0:
                logger.info(
                    "Step 2.7: SDE channel using request-provided net debt position",
                    extra={
                        "step_number": 2.7,
                        "total_debt": from_decimal(sde_total_debt),
                        "cash": from_decimal(sde_cash),
                        "net_debt": from_decimal(sde_total_debt - sde_cash),
                    },
                )
            channel = build_sde_channel(
                SdeChannelInputs(
                    sde_value=sde,
                    sde_base_multiple=base_multiple,
                    revenue=revenue,
                    total_debt=sde_total_debt,
                    cash=sde_cash,
                    nwc_adjustment=Decimal("0"),
                    owner_salary_addback=(
                        explicit_addback if explicit_addback > 0 else sde_components.owner_salary
                    ),
                    owner_salary_estimate=sde_components.owner_salary,
                    owner_salary_source=("trial_balance" if explicit_addback > 0 else "estimate"),
                    owner_role=str(getattr(request, "owner_role", "working") or "working"),
                    num_owners=int(num_owners or 1),
                    business_size=business_size,
                    country_code=country_code or "BE",
                    industry=industry or "",
                    business_type_id=getattr(request, "business_type_id", "") or "",
                    sde_multiple_p25=base_p25,
                    sde_multiple_p75=base_p75,
                    owner_concentration_tier_override=owner_concentration_override,
                    belgian_market_premium_override=be_premium_override,
                )
            )

            # Channel-derived headline values.  These are the canonical
            # numbers stored in the result_dict so the report aggregator,
            # omni-calc, and template all read the same multiple and EV.
            applied_multiple = to_decimal(channel.sde_applied_multiple)
            multiple_p25 = to_decimal(channel.sde_multiple_p25)
            multiple_p75 = to_decimal(channel.sde_multiple_p75)
            value_mid = to_decimal(channel.enterprise_value)
            value_low = to_decimal(channel.enterprise_value_low)
            value_high = to_decimal(channel.enterprise_value_high)

            # Adjustment ledger for the result_dict (back-compat with
            # existing transparency consumers that read this dict).
            adjustment_dict = {
                "belgian_market_premium": channel.belgian_market_premium,
                "owner_concentration_adjustment": channel.owner_concentration_adjustment,
                "size_discount_adjustment": channel.size_discount_adjustment,
                "liquidity_discount_adjustment": channel.liquidity_discount_adjustment,
            }
            multiple = applied_multiple

            # Calculate execution time
            execution_time_ms = (time.time() - float(start_time)) * 1000

            # Build component dict for transparency
            sde_components_dict = {
                "net_income": from_decimal(sde_components.net_income),
                "owner_salary": from_decimal(sde_components.owner_salary),
                "owner_benefits": from_decimal(sde_components.owner_benefits),
                "owner_perks": from_decimal(sde_components.owner_perks),
                "depreciation": from_decimal(sde_components.depreciation),
                "amortization": from_decimal(sde_components.amortization),
                "interest_expense": from_decimal(sde_components.interest_expense),
                "non_recurring_expenses": from_decimal(sde_components.non_recurring_expenses),
                "non_operating_income": from_decimal(sde_components.non_operating_income),
                "total_sde": from_decimal(sde_components.total_sde),
            }

            # Reported Net Profit → SDE ladder (audit trail). Each step shows
            # the running cumulative so an accountant or buyer can verify the
            # reconciliation line-by-line.
            sde_bridge = self._build_sde_bridge(
                sde_components=sde_components_dict,
                ebitda=from_decimal(ebitda),
                explicit_addback=from_decimal(explicit_addback),
                owner_role=getattr(request, "owner_role", None),
            )

            # Determine confidence
            confidence = 0.7  # Base confidence
            if titan_normalization_used:
                confidence += 0.1  # Higher confidence with user normalization
            if database_multiples_used:
                confidence += 0.1  # Higher confidence with database multiples
            if business_size == "micro":
                confidence += 0.05  # SDE is standard for micro

            # Log completion
            logger.info(
                "✅ Step 2.7: SDE Calculation Complete",
                extra={
                    "step_number": self.step_number,
                    "sde": from_decimal(sde),
                    "sde_multiple": from_decimal(multiple),
                    "sde_valuation": from_decimal(value_mid),
                    "business_size": business_size,
                    "data_source": data_source,
                    "execution_time_ms": round(execution_time_ms, 2),
                },
            )

            # Build result
            result_dict = self.result_builder.build_result_dict(
                sde=from_decimal(sde),
                sde_multiple=from_decimal(multiple),
                sde_valuation=from_decimal(value_mid),
                sde_valuation_low=from_decimal(value_low),
                sde_valuation_high=from_decimal(value_high),
                sde_components=sde_components_dict,
                industry=industry,
                business_size=business_size,
                adjustments=adjustment_dict,
                data_source=data_source,
            )
            if isinstance(result_dict, dict):
                result_dict["sde_bridge"] = sde_bridge
                if getattr(request, "owner_role", None) in {"working", "passive"}:
                    result_dict["owner_role"] = request.owner_role
                # Channel data — drives the SDE-specific waterfall in the
                # report and is the authoritative source for omni-calc /
                # template / aggregator. The base multiple is the raw DB
                # number; the applied multiple is post-cascade.
                result_dict["sde_base_multiple"] = float(base_multiple)
                result_dict["sde_applied_multiple"] = channel.sde_applied_multiple
                result_dict["sde_calibration_steps"] = channel.calibration_steps
                result_dict["sde_owner_concentration_tier"] = channel.owner_concentration_tier
                result_dict["sde_country_code"] = country_code or "BE"

            # Build metadata
            metadata_dict = self.result_builder.build_metadata_dict(
                sde=from_decimal(sde),
                sde_components=sde_components_dict,
                sde_multiple=from_decimal(multiple),
                sde_multiple_p25=from_decimal(multiple_p25),
                sde_multiple_p75=from_decimal(multiple_p75),
                industry=industry,
                business_size=business_size,
                data_source=data_source,
                confidence=confidence,
                execution_time_ms=round(execution_time_ms, 2),
                titan_normalization_used=titan_normalization_used,
                database_multiples_used=database_multiples_used,
            )

            return StepOutput(
                step_number=self.step_number,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,
                execution_time_ms=round(execution_time_ms, 2),
                result=result_dict,
                metadata=metadata_dict,
            )

        except Exception as e:
            logger.error(
                f"❌ Step 2.7: Error during SDE calculation: {e}",
                extra={
                    "step_number": self.step_number,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return self.error_handler.handle_calculation_error(e)

    @staticmethod
    def _build_sde_bridge(
        *,
        sde_components: dict,
        ebitda: float,
        explicit_addback: float,
        owner_role: Optional[str] = None,
    ) -> list:
        """Reported Net Profit → SDE bridge ladder (audit trail).

        Returns an ordered list of {label, amount, running_total, sign}
        rows so the UI can render a transparent reconciliation. The math
        follows the canonical SDE recipe:

            Net Income
          + Interest
          + Taxes (subsumed into normalised EBITDA)
          + D&A
          + Owner compensation (salary/benefits/perks)
          + Non-recurring expenses
          - Non-operating income
          = SDE
        """
        return build_sde_bridge(
            sde_components=sde_components,
            ebitda=ebitda,
            explicit_addback=explicit_addback,
            owner_role=owner_role,
        )
