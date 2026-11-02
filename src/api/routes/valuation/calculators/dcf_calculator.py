"""DCF valuation calculator with Monte Carlo simulation support.

Extracted from valuation_orchestrator.py to isolate DCF calculation logic.
"""

from decimal import Decimal
from typing import Dict, Optional, TypeAlias

from src.api.schemas import ValuationRequest
from src.domain.models import ConfidenceLevel
from src.services.academic.calculation_provenance_tracker import record_calculation_safe
from src.utils.adaptive_input_helpers import get_dcf_mid_year_discounting
from src.utils.decimal_helpers import to_decimal
from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    DCFCalculationError,
    MarketDataError,
    ValidationError,
)
from src.utils.exceptions import ValuationRangeError as RangeCalculationError
from src.utils.logging import get_logger

from .dcf_apv_bridge import apply_apv_bridge_result, calculate_apv_tax_shield_bridge
from .dcf_apv_sensitivity import apply_apv_sensitivity_basis
from .dcf_calculation_inputs import (
    apply_positive_dcf_value_floors,
    normalize_projection_years,
    resolve_dcf_input_metrics,
    resolve_terminal_ebitda_for_sensitivity,
)
from .dcf_calculator_helpers import DCFCalculatorHelpers
from .dcf_data_adapter import DCFDataAdapter
from .dcf_engine_execution import run_full_dcf_engine
from .dcf_manual_overrides import has_manual_dcf_overrides
from .dcf_pipeline_logging import dcf_pipeline_breadcrumb as _dcf_pipeline_breadcrumb
from .dcf_policy_context import (
    apply_manual_wacc_override_to_buildup,
    overlay_user_capm_on_wacc_buildup,
)
from .dcf_post_engine_warnings import extend_post_engine_dcf_warnings
from .dcf_range_simulation import (
    calculate_deterministic_range,
    calculate_probabilistic_range,
    run_monte_carlo_simulation,
)
from .dcf_response_payload import (
    DCFResponsePayloadInputs,
    build_dcf_completion_log_context,
    build_dcf_response_payload,
    log_dcf_completion_summary,
    log_dcf_range_summary,
    safe_normalize_dcf_valuation_range,
    safe_serialize_dcf_projection_detail,
)
from .dcf_sensitivity_merge import merge_rebuilt_dcf_sensitivity_payload

logger = get_logger(__name__)

RuntimePayload: TypeAlias = Dict[str, object]


class DCFCalculator(DCFCalculatorHelpers):
    """Stateless DCF calculator with Monte Carlo and response-shaping support."""

    def __init__(self):
        self.logger = logger
        self.logger.debug("✅ DCFCalculator initialized")

    async def calculate(
        self, request: ValuationRequest, context: Optional[RuntimePayload] = None
    ) -> RuntimePayload:
        """Apply the same indicative and verified policy on both dispatch paths."""
        from src.services.reports.forecast_admission import optional_verified_forecast
        from src.services.reports.forecast_output_policy import label_forecast_output

        forecast = optional_verified_forecast(request)
        calculated = await self._calculate_diagnostic(request, context)
        return label_forecast_output(calculated, forecast)

    async def _calculate_diagnostic(
        self, request: ValuationRequest, context: Optional[RuntimePayload] = None
    ) -> RuntimePayload:
        """
        Calculate DCF valuation

        Args:
            request: Valuation request with financial data
            context: Optional calculation context

        Returns:
            Dictionary with DCF valuation results
        """
        try:
            context_data: RuntimePayload = context if isinstance(context, dict) else {}
            correlation_id = None
            if context_data:
                correlation_id = context_data.get("correlation_id")
            if correlation_id is None:
                correlation_id = getattr(request, "correlation_id", None)
            self.logger.info(
                "🎯 Starting DCF valuation",
                extra={
                    "company": request.company_name,
                    "revenue": request.current_year_data.revenue,
                    "has_monte_carlo": (
                        context_data.get("use_monte_carlo", False) if context_data else False
                    ),
                    "correlation_id": correlation_id,
                },
            )

            input_metrics = resolve_dcf_input_metrics(request, context_data)
            revenue = input_metrics.revenue
            ebitda = input_metrics.ebitda
            using_weighted = input_metrics.using_weighted_metrics
            weighting_method = input_metrics.weighting_method

            net_debt = getattr(request.current_year_data, "total_debt", 0) or Decimal("0.0")
            cash = getattr(request.current_year_data, "cash", 0) or Decimal("0.0")

            self.logger.info(
                "💰 DCF input parameters",
                extra={
                    "revenue": revenue,
                    "ebitda": ebitda,
                    "net_debt": net_debt,
                    "cash": cash,
                    "historical_years": len(request.historical_years_data),
                    "using_weighted_metrics": using_weighted,
                    "weighting_method": weighting_method,
                },
            )

            # Initialize variables to avoid UnboundLocalError
            enterprise_value = Decimal("0.0")
            equity_value = Decimal("0.0")
            wacc = Decimal("0.10")
            cost_of_equity = Decimal("0.12")
            cost_of_debt = Decimal("0.05")
            terminal_growth_rate = Decimal("0.03")
            terminal_value = Decimal("0.0")
            pv_terminal_value = Decimal("0.0")
            cash_flow_projections = []
            pv_fcf_projections = []
            sensitivity_wacc = {}
            sensitivity_growth = {}
            confidence = ConfidenceLevel.MEDIUM
            confidence_score = 50
            confidence_factors = {}
            dcf_result = None
            dcf_audit_trail = None
            market_assumptions: RuntimePayload = {}
            wacc_components = None
            # Default before full DCF path; inner try overwrites from adapter/request.
            # Simplified fallbacks must never hit UnboundLocalError on projection_years.
            projection_years = normalize_projection_years(
                getattr(request, "projection_years", None)
            )
            mid_year_discounting = get_dcf_mid_year_discounting(request)

            # DCF values may only come from the full FCFF engine. If that engine
            # cannot complete, fail the method explicitly so the caller can
            # exclude or downgrade it without publishing a non-DCF substitute.
            try:
                engine_execution = run_full_dcf_engine(
                    request,
                    logger=self.logger,
                    correlation_id=correlation_id,
                    mid_year_discounting=mid_year_discounting,
                    tax_rate_provenance_builder=self._build_tax_rate_provenance,
                    extract_has_audit=self._extract_has_audit,
                    extract_owner_dependency_score=self._extract_owner_dependency_score,
                    coerce_engine_sensitivity_1d_map=self._coerce_engine_sensitivity_1d_map,
                    data_adapter_factory=DCFDataAdapter,
                )
                dcf_result = engine_execution.dcf_result
                enterprise_value = engine_execution.enterprise_value
                equity_value = engine_execution.equity_value
                wacc = engine_execution.wacc
                cost_of_equity = engine_execution.cost_of_equity
                cost_of_debt = engine_execution.cost_of_debt
                terminal_growth_rate = engine_execution.terminal_growth_rate
                terminal_value = engine_execution.terminal_value
                pv_terminal_value = engine_execution.pv_terminal_value
                cash_flow_projections = engine_execution.cash_flow_projections
                pv_fcf_projections = engine_execution.pv_fcf_projections
                sensitivity_wacc = engine_execution.sensitivity_wacc
                sensitivity_growth = engine_execution.sensitivity_growth
                confidence = engine_execution.confidence
                confidence_score = engine_execution.confidence_score
                confidence_factors = engine_execution.confidence_factors
                dcf_audit_trail = engine_execution.dcf_audit_trail
                market_assumptions = engine_execution.market_assumptions
                wacc_components = engine_execution.wacc_components
                projection_years = engine_execution.projection_years

            except DCFCalculationError:
                # Preserve an already-classified engine failure and its context.
                raise
            except Exception as e:
                self.logger.warning(
                    "Full DCF engine failed; no substitute valuation was produced",
                    extra={
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "company": request.company_name,
                        "correlation_id": correlation_id,
                        "fallback_value_produced": False,
                    },
                    exc_info=True,
                )
                raise DCFCalculationError(
                    "Full DCF calculation failed; no substitute valuation was produced: "
                    f"{type(e).__name__}: {e}",
                    step="dcf_engine",
                    context={
                        "company": request.company_name,
                        "correlation_id": correlation_id,
                        "source_error_type": type(e).__name__,
                        "no_fallback_value": True,
                    },
                ) from e

            engine_pv_fcf = list(pv_fcf_projections)
            _dcf_pipeline_breadcrumb(
                self.logger,
                stage="manual_dcf_overrides",
                phase="before",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            # Defaults so a failed unpack (override raises) never leaves these unbound downstream.
            terminal_value_methodology = "gordon_growth"
            terminal_exit_multiple: Decimal | None = None
            try:
                (
                    enterprise_value,
                    equity_value,
                    wacc,
                    terminal_growth_rate,
                    terminal_value,
                    pv_terminal_value,
                    override_pv_fcf,
                    terminal_value_methodology,
                    terminal_exit_multiple,
                ) = self._apply_manual_dcf_overrides(
                    request,
                    enterprise_value=enterprise_value,
                    equity_value=equity_value,
                    wacc=wacc,
                    terminal_growth_rate=terminal_growth_rate,
                    terminal_value=terminal_value,
                    pv_terminal_value=pv_terminal_value,
                    cash_flow_projections=cash_flow_projections,
                    net_debt=to_decimal(net_debt),
                    cash=to_decimal(cash),
                    mid_year_discounting=mid_year_discounting,
                )
            except DataQualityError:
                # Invalid admitted financial assumptions cannot fall back to an
                # unrelated base valuation while appearing to honor an override.
                raise
            except Exception as ov_exc:
                self.logger.warning(
                    "Manual DCF overrides failed; continuing with pre-override outputs",
                    extra={
                        "error": str(ov_exc),
                        "error_type": type(ov_exc).__name__,
                        "correlation_id": correlation_id,
                        "company": getattr(request, "company_name", None),
                    },
                    exc_info=True,
                )
                override_pv_fcf = list(pv_fcf_projections)
            _dcf_pipeline_breadcrumb(
                self.logger,
                stage="manual_dcf_overrides",
                phase="after",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            has_manual_override = has_manual_dcf_overrides(request)
            pv_fcf_projections = override_pv_fcf if has_manual_override else engine_pv_fcf
            apv_bridge = calculate_apv_tax_shield_bridge(
                request,
                enterprise_value=enterprise_value,
                equity_value=equity_value,
                discount_rate=wacc,
                mid_year_discounting=mid_year_discounting,
            )
            if apv_bridge is not None:
                enterprise_value, equity_value = apply_apv_bridge_result(
                    apv_bridge,
                    equity_value,
                    dcf_audit_trail,
                )
                self.logger.info(
                    "Applied APV tax-shield bridge to DCF result",
                    extra={
                        "tax_shield_value": float(apv_bridge["apv_tax_shield_value"]),
                        "apv_enterprise_value": float(apv_bridge["apv_enterprise_value"]),
                        "mid_year_discounting": mid_year_discounting,
                        "company": getattr(request, "company_name", None),
                        "correlation_id": correlation_id,
                    },
                )
            terminal_ebitda = resolve_terminal_ebitda_for_sensitivity(
                request,
                self._safe_optional_decimal,
            )

            prior_sensitivity_wacc = sensitivity_wacc
            prior_sensitivity_growth = sensitivity_growth
            engine_matrix_2d = (
                getattr(dcf_result, "sensitivity_matrix_2d", None)
                if dcf_result is not None
                else None
            )

            _dcf_pipeline_breadcrumb(
                self.logger,
                stage="sensitivity_payload",
                phase="before",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            sensitivity_wacc, sensitivity_growth, sensitivity_matrix_2d = (
                merge_rebuilt_dcf_sensitivity_payload(
                    build=lambda: self._build_dcf_sensitivity_payload(
                        fcf_values=[
                            d
                            for d in (
                                self._safe_optional_decimal(v)
                                for v in cash_flow_projections
                                if v is not None
                            )
                            if d is not None
                        ],
                        wacc=self._safe_monte_carlo_decimal(wacc, Decimal("0.10")),
                        terminal_growth_rate=self._safe_monte_carlo_decimal(
                            terminal_growth_rate, Decimal("0.03")
                        ),
                        terminal_value=self._safe_monte_carlo_decimal(terminal_value, Decimal("0")),
                        terminal_value_methodology=terminal_value_methodology,
                        terminal_exit_multiple=terminal_exit_multiple,
                        terminal_ebitda=terminal_ebitda,
                        mid_year_discounting=mid_year_discounting,
                    ),
                    sanitize_matrix_2d=self._sanitize_sensitivity_matrix_2d,
                    sensitivity_values_are_finite=self._sensitivity_scenario_values_are_finite,
                    prior_wacc=prior_sensitivity_wacc,
                    prior_growth=prior_sensitivity_growth,
                    engine_matrix_2d=engine_matrix_2d,
                    logger=self.logger,
                    correlation_id=correlation_id,
                    company=getattr(request, "company_name", None),
                )
            )

            sensitivity_wacc, sensitivity_growth, sensitivity_matrix_2d = (
                apply_apv_sensitivity_basis(
                    apv_bridge,
                    sensitivity_wacc,
                    sensitivity_growth,
                    sensitivity_matrix_2d,
                    base_rate=wacc,
                )
            )

            _dcf_pipeline_breadcrumb(
                self.logger,
                stage="sensitivity_payload",
                phase="after",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            wacc_buildup = None
            try:
                wacc_buildup = self._build_wacc_buildup(wacc_components)
                wacc_buildup = overlay_user_capm_on_wacc_buildup(wacc_buildup, request)
                if has_manual_override:
                    wacc_buildup = apply_manual_wacc_override_to_buildup(wacc_buildup, wacc)
            except Exception as wb_exc:
                self.logger.warning(
                    "WACC buildup / manual override shaping failed; continuing without buildup",
                    extra={
                        "error": str(wb_exc),
                        "error_type": type(wb_exc).__name__,
                        "correlation_id": correlation_id,
                        "company": getattr(request, "company_name", None),
                    },
                    exc_info=True,
                )
                wacc_buildup = None

            if (
                has_manual_override
                and wacc_buildup is not None
                and wacc_buildup.get("cost_of_equity") is not None
            ):
                try:
                    cost_of_equity = to_decimal(wacc_buildup["cost_of_equity"])
                except (ValueError, TypeError, ArithmeticError):
                    pass

            try:
                terminal_value_pct_of_total, explicit_forecast_pct_of_total = (
                    self._calculate_terminal_value_split(pv_fcf_projections, pv_terminal_value)
                )
            except Exception as split_exc:
                self.logger.warning(
                    "Terminal value split calculation failed; omitting percentages",
                    extra={
                        "error": str(split_exc),
                        "error_type": type(split_exc).__name__,
                        "correlation_id": correlation_id,
                        "company": getattr(request, "company_name", None),
                    },
                    exc_info=True,
                )
                terminal_value_pct_of_total, explicit_forecast_pct_of_total = None, None
            mid_year_note = (
                "Explicit period cash flows discounted at mid-year points (0.5, 1.5, ...); "
                "terminal value present value at (n-0.5)."
                if mid_year_discounting
                else (
                    "Explicit period cash flows discounted at year-end points (1, 2, ...); "
                    "terminal value present value at n."
                )
            )

            # Non-positive EV/equity breaks range spread and ValuationValidator (> 0 required).
            _pre_floor_enterprise_value = enterprise_value
            _pre_floor_equity_value = equity_value
            positive_values = apply_positive_dcf_value_floors(
                enterprise_value=enterprise_value,
                equity_value=equity_value,
                logger=self.logger,
                company=getattr(request, "company_name", None),
            )
            enterprise_value = positive_values.enterprise_value
            equity_value = positive_values.equity_value
            # A floored result means the DCF resolved to a non-positive value. It stays
            # renderable on the standalone DCF page, but it is NOT a usable valuation and
            # must be excluded from the hybrid blend (see HybridMethodologyOrchestrator).
            dcf_value_floored = (
                enterprise_value != _pre_floor_enterprise_value
                or equity_value != _pre_floor_equity_value
            )

            # Seed range before MC vs deterministic branches overwrite it.
            valuation_range = self._fallback_equity_range_band(equity_value)

            # Check if Monte Carlo simulation is requested
            monte_carlo_results = None
            use_monte_carlo = context_data.get("use_monte_carlo", False) if context_data else False

            if use_monte_carlo:
                _dcf_pipeline_breadcrumb(
                    self.logger,
                    stage="valuation_range",
                    phase="before_monte_carlo",
                    correlation_id=correlation_id,
                    company=getattr(request, "company_name", None),
                )
                self.logger.info("🎲 Running Monte Carlo simulation")
                base_fcf_mc = (
                    self._safe_monte_carlo_optional_fcf(cash_flow_projections[0])
                    if cash_flow_projections
                    else None
                )
                monte_carlo_results = await self._run_monte_carlo_simulation(
                    request,
                    base_fcf_override=base_fcf_mc,
                    base_wacc_override=self._safe_monte_carlo_decimal(wacc, Decimal("0.10")),
                    base_growth_override=self._safe_monte_carlo_decimal(
                        terminal_growth_rate, Decimal("0.03")
                    ),
                )

                try:
                    valuation_range = await self._calculate_probabilistic_range(
                        equity_value, monte_carlo_results
                    )
                except Exception as range_exc:
                    self.logger.warning(
                        "Probabilistic range failed; using symmetric fallback band",
                        extra={
                            "error": str(range_exc),
                            "error_type": type(range_exc).__name__,
                            "correlation_id": correlation_id,
                            "company": getattr(request, "company_name", None),
                        },
                        exc_info=True,
                    )
                    valuation_range = self._fallback_equity_range_band(equity_value)

                try:
                    self.logger.info(
                        "✅ Monte Carlo simulation complete",
                        extra={
                            k: monte_carlo_results.get(k) for k in ("p10", "p50", "p90", "std_dev")
                        },
                    )
                except Exception as mc_log_exc:
                    self.logger.warning(
                        "Monte Carlo completion logging skipped",
                        extra={
                            "error": str(mc_log_exc),
                            "error_type": type(mc_log_exc).__name__,
                            "correlation_id": correlation_id,
                            "company": getattr(request, "company_name", None),
                        },
                    )
            else:
                _dcf_pipeline_breadcrumb(
                    self.logger,
                    stage="valuation_range",
                    phase="before_deterministic",
                    correlation_id=correlation_id,
                    company=getattr(request, "company_name", None),
                )
                # Use deterministic range
                self.logger.info("📊 Using deterministic range calculation")
                try:
                    valuation_range = await self._calculate_deterministic_range(equity_value)
                except Exception as range_exc:
                    self.logger.warning(
                        "Deterministic range failed; using symmetric fallback band",
                        extra={
                            "error": str(range_exc),
                            "error_type": type(range_exc).__name__,
                            "correlation_id": correlation_id,
                            "company": getattr(request, "company_name", None),
                        },
                        exc_info=True,
                    )
                    valuation_range = self._fallback_equity_range_band(equity_value)

            _dcf_pipeline_breadcrumb(
                self.logger,
                stage="valuation_range",
                phase="after",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            normalized_valuation_range = safe_normalize_dcf_valuation_range(
                valuation_range,
                equity_value,
                self._normalize_valuation_range_for_response,
                self._fallback_equity_range_band,
                self.logger,
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            _dcf_pipeline_breadcrumb(
                self.logger,
                stage="dcf_response",
                phase="before_build",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            fcf_projection_detail = safe_serialize_dcf_projection_detail(
                dcf_result,
                self._serialize_projection_detail,
                self.logger,
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            forecast_assumption_warnings = extend_post_engine_dcf_warnings(
                self._build_forecast_assumption_warnings(request),
                terminal_value_pct_of_total=terminal_value_pct_of_total,
                explicit_forecast_pct_of_total=explicit_forecast_pct_of_total,
                wacc=wacc,
                cost_of_equity=cost_of_equity,
            )

            payload_inputs = DCFResponsePayloadInputs(
                request=request,
                dcf_result=dcf_result,
                normalized_valuation_range=normalized_valuation_range,
                net_debt=net_debt,
                ebitda=ebitda,
                has_manual_override=has_manual_override,
                apv_bridge=apv_bridge,
                monte_carlo_results=monte_carlo_results,
                enterprise_value=enterprise_value,
                equity_value=equity_value,
                wacc=wacc,
                cost_of_equity=cost_of_equity,
                cost_of_debt=cost_of_debt,
                terminal_growth_rate=terminal_growth_rate,
                terminal_value=terminal_value,
                terminal_value_methodology=terminal_value_methodology,
                terminal_exit_multiple=terminal_exit_multiple,
                pv_terminal_value=pv_terminal_value,
                mid_year_discounting=mid_year_discounting,
                discount_periods_note=mid_year_note,
                wacc_buildup=wacc_buildup,
                terminal_value_pct_of_total=terminal_value_pct_of_total,
                explicit_forecast_pct_of_total=explicit_forecast_pct_of_total,
                cash_flow_projections=cash_flow_projections,
                pv_fcf_projections=pv_fcf_projections,
                projection_years=projection_years,
                sensitivity_wacc=sensitivity_wacc,
                sensitivity_growth=sensitivity_growth,
                sensitivity_matrix_2d=sensitivity_matrix_2d,
                confidence=confidence,
                confidence_score=confidence_score,
                confidence_factors=confidence_factors,
                dcf_audit_trail=dcf_audit_trail,
                market_assumptions=market_assumptions,
                fcf_projection_detail=fcf_projection_detail,
                data_quality_warnings=forecast_assumption_warnings,
            )
            result = build_dcf_response_payload(payload_inputs)
            if isinstance(result, dict):
                result["dcf_value_floored"] = dcf_value_floored

            _dcf_pipeline_breadcrumb(
                self.logger,
                stage="dcf_response",
                phase="after_build",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            log_context = build_dcf_completion_log_context(
                payload_inputs,
                correlation_id=correlation_id,
                revenue=revenue,
                cash=cash,
                using_weighted_metrics=using_weighted,
                weighting_method=weighting_method,
            )
            log_dcf_completion_summary(self.logger, log_context)
            log_dcf_range_summary(self.logger, log_context)

            # Academic provenance: rule `dcf_wacc_range` enforces
            # 8% - 25% per Damodaran (2012) / Ibbotson (2024) / Koller (2020).
            if wacc is not None and wacc > 0:
                record_calculation_safe(
                    "dcf_wacc",
                    float(wacc),
                    section_name="DCF Valuation",
                    inputs={
                        "cost_of_equity": float(cost_of_equity) if cost_of_equity else None,
                        "cost_of_debt": float(cost_of_debt) if cost_of_debt else None,
                    },
                )

            return result

        except (CalculationError, DataQualityError, ValidationError, MarketDataError):
            raise
        except Exception as e:
            self.logger.error(
                "❌ DCF valuation failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "company": request.company_name,
                },
                exc_info=True,
            )
            raise DCFCalculationError(
                f"Failed to calculate DCF valuation: {e}",
                step="dcf_valuation",
                calculation_type="DCF Valuation",
                context={"company": request.company_name},
            ) from e

    async def _run_monte_carlo_simulation(
        self,
        request: ValuationRequest,
        *,
        base_fcf_override: Optional[Decimal] = None,
        base_wacc_override: Optional[Decimal] = None,
        base_growth_override: Optional[Decimal] = None,
    ) -> RuntimePayload:
        return await run_monte_carlo_simulation(
            request,
            logger=self.logger,
            base_fcf_override=base_fcf_override,
            base_wacc_override=base_wacc_override,
            base_growth_override=base_growth_override,
        )

    async def _calculate_probabilistic_range(
        self, equity_value: Decimal, monte_carlo_results: RuntimePayload
    ) -> Dict[str, Decimal]:
        return await calculate_probabilistic_range(
            equity_value,
            monte_carlo_results,
            logger=self.logger,
        )

    async def _calculate_deterministic_range(self, equity_value: Decimal) -> Dict[str, Decimal]:
        return await calculate_deterministic_range(equity_value, logger=self.logger)
