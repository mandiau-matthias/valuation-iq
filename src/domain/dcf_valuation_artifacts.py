"""Non-core DCF valuation artifacts.

The DCF engine should coordinate the cash-flow, WACC, terminal-value, and
result coordinators. This module owns optional diagnostics, transparency
steps, sensitivity fallbacks, and result packaging so the engine method stays
small without changing valuation math.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional, Protocol

from src.domain.dcf.coordinators.result_aggregation_coordinator import ResultAggregationCoordinator
from src.domain.dcf.coordinators.sensitivity_analysis_coordinator import (
    SensitivityAnalysisCoordinator,
)
from src.domain.dcf_types import (
    DCFConfiguration, DCFMethodology, DCFResult, TerminalValueParams, WACCComponents,
)
from src.domain.models import FinancialData
from src.utils.decimal_helpers import to_decimal


class DCFLogger(Protocol):
    def warning(self, message: str, **kwargs: object) -> None: ...

    def info(self, message: str, **kwargs: object) -> None: ...


class DCFTransparencyCollector(Protocol):
    def add_calculation_step(
        self,
        *,
        description: str,
        formula: str,
        inputs: dict[str, object],
        outputs: dict[str, object],
        explanation: str,
    ) -> None: ...

    def add_error_step(
        self,
        *,
        description: str,
        error: Exception,
        inputs: dict[str, object],
        explanation: str,
    ) -> None: ...


@dataclass(frozen=True)
class DCFRunConfig:
    projection_years: int
    sensitivity_analysis: bool
    explicit_forecasts: list[object]


@dataclass(frozen=True)
class DCFSensitivityArtifacts:
    sensitivity_wacc: dict[object, object]
    sensitivity_growth: dict[object, object]
    sensitivity_matrix_2d: Optional[dict[str, object]]


@dataclass(frozen=True)
class DCFConfidenceArtifacts:
    confidence: str
    confidence_score: Decimal
    confidence_factors: list[str]
    historical_fcf_readiness: dict[str, object]
    transparency_data: dict[str, object]


def resolve_dcf_run_config(
    *,
    financial_data: FinancialData,
    config: DCFConfiguration,
    projection_years: Optional[int],
    sensitivity_analysis: Optional[bool],
) -> DCFRunConfig:
    effective_projection_years = (
        projection_years if projection_years is not None else config.projection_years
    )
    explicit_forecasts = list(getattr(financial_data, "forecast_years", []) or [])
    if explicit_forecasts:
        effective_projection_years = len(explicit_forecasts)
    if not effective_projection_years or effective_projection_years < 1:
        effective_projection_years = 5

    return DCFRunConfig(
        projection_years=effective_projection_years,
        sensitivity_analysis=(
            sensitivity_analysis
            if sensitivity_analysis is not None
            else config.sensitivity_analysis
        ),
        explicit_forecasts=explicit_forecasts,
    )


def add_present_value_transparency(
    *,
    collector: Optional[DCFTransparencyCollector],
    fcf_values: list[Decimal],
    wacc: Decimal,
    pv_fcf_projections: list[Decimal],
    pv_terminal_value: Decimal,
) -> None:
    if collector is None:
        return
    total_pv_fcf = sum(pv_fcf_projections)
    collector.add_calculation_step(
        description="Present Value of Projected Cash Flows",
        formula=f"PV = Σ(FCF_t / (1 + WACC)^t) for t=1 to {len(fcf_values)}",
        inputs={
            "fcf_projections": [round(fcf, 2) for fcf in fcf_values],
            "wacc": round(wacc, 4),
            "projection_years": len(fcf_values),
        },
        outputs={
            "pv_fcf_values": [round(pv, 2) for pv in pv_fcf_projections],
            "total_pv_fcf": round(total_pv_fcf, 2),
            "pv_terminal_value": round(pv_terminal_value, 2),
        },
        explanation=(
            "Discounting future cash flows to present value using WACC as discount rate. "
            "This represents the time value of money principle."
        ),
    )


def add_enterprise_value_transparency(
    *,
    collector: Optional[DCFTransparencyCollector],
    financial_data: FinancialData,
    enterprise_value: Decimal,
    equity_value: Decimal,
) -> None:
    if collector is None:
        return
    current_year = financial_data.current_year
    net_debt = _resolve_net_debt(financial_data)
    collector.add_calculation_step(
        description="Enterprise Value to Equity Value Conversion",
        formula=f"Equity Value = EV - Net Debt = {enterprise_value:,.0f} - {net_debt:,.0f}",
        inputs={
            "enterprise_value": round(enterprise_value, 2),
            "total_debt": round(current_year.total_debt or Decimal("0"), 2),
            "cash": round(current_year.cash or Decimal("0"), 2),
            "net_debt": round(net_debt, 2),
        },
        outputs={"equity_value": round(equity_value, 2)},
        explanation=(
            "Adjusting enterprise value for net debt to arrive at equity value available "
            "to shareholders. Enterprise value represents value to all stakeholders; "
            "equity value is for shareholders only."
        ),
    )


def compute_implied_ev_ebitda(
    *,
    enterprise_value: Decimal,
    financial_data: FinancialData,
    fcf_projections: list[object],
    logger: DCFLogger,
) -> Optional[Decimal]:
    try:
        cross_check_ebitda = _resolve_cross_check_ebitda(
            financial_data=financial_data,
            fcf_projections=fcf_projections,
        )
        if cross_check_ebitda:
            return to_decimal(enterprise_value) / cross_check_ebitda
    except (InvalidOperation, ValueError, TypeError, ZeroDivisionError) as exc:
        logger.warning(
            "Implied EV/EBITDA cross-check skipped",
            extra={"error": str(exc), "error_type": type(exc).__name__},
        )
    return None


def compute_terminal_value_steady_state(
    *,
    fcf_projections: list[object],
    logger: DCFLogger,
) -> Optional[dict[str, object]]:
    try:
        if not fcf_projections:
            return None
        last_projection = fcf_projections[-1]
        last_capex = abs(to_decimal(getattr(last_projection, "capex", 0) or 0))
        last_da = to_decimal(getattr(last_projection, "ebitda", 0) or 0) - to_decimal(
            getattr(last_projection, "ebit", 0) or 0
        )
        if last_capex > 0 and last_da > 0:
            ratio = last_capex / last_da
            return {
                "checked": True,
                "is_steady_state": Decimal("0.85") <= ratio <= Decimal("1.15"),
                "terminal_year_capex": last_capex,
                "terminal_year_depreciation": last_da,
                "capex_to_da_ratio": ratio,
            }
        return {"checked": False, "is_steady_state": None}
    except (InvalidOperation, ValueError, TypeError, ZeroDivisionError) as exc:
        logger.warning(
            "Terminal-value steady-state check skipped",
            extra={"error": str(exc), "error_type": type(exc).__name__},
        )
        return None


def compute_dcf_sensitivity_artifacts(
    *,
    sensitivity_coordinator: SensitivityAnalysisCoordinator,
    enabled: bool,
    terminal_value_params: TerminalValueParams,
    wacc_components: WACCComponents,
    fcf_values: list[Decimal],
    projection_years: int,
    logger: DCFLogger,
) -> DCFSensitivityArtifacts:
    sensitivity_wacc: dict[object, object] = {}
    sensitivity_growth: dict[object, object] = {}
    sensitivity_matrix_2d: Optional[dict[str, object]] = None
    if not enabled:
        return DCFSensitivityArtifacts(
            sensitivity_wacc=sensitivity_wacc,
            sensitivity_growth=sensitivity_growth,
            sensitivity_matrix_2d=sensitivity_matrix_2d,
        )

    is_exit_multiple = terminal_value_params.methodology == DCFMethodology.EXIT_MULTIPLE
    exit_ebitda = to_decimal(terminal_value_params.exit_year_ebitda or 0)
    exit_multiple = to_decimal(terminal_value_params.exit_multiple or 1)
    try:
        sensitivity_results = sensitivity_coordinator.perform_enterprise_sensitivity_analysis(
            fcf_values=fcf_values,
            final_fcf=fcf_values[-1],
            base_wacc=wacc_components.wacc,
            base_growth=terminal_value_params.terminal_growth_rate,
            projection_years=projection_years,
            terminal_ebitda=exit_ebitda if is_exit_multiple else None,
            exit_multiple=exit_multiple if is_exit_multiple else None,
        )
        sensitivity_wacc = sensitivity_results.get("sensitivity_wacc", {})
        sensitivity_growth = sensitivity_results.get("sensitivity_growth", {})
    except Exception as exc:
        logger.warning(
            "1D sensitivity analysis failed; continuing without WACC/growth scenarios",
            extra={"error": str(exc), "error_type": type(exc).__name__},
            exc_info=True,
        )

    try:
        if is_exit_multiple:
            sensitivity_matrix_2d = sensitivity_coordinator.perform_exit_multiple_sensitivity_analysis(
                fcf_values=fcf_values,
                terminal_ebitda=exit_ebitda,
                base_wacc=wacc_components.wacc,
                base_exit_multiple=exit_multiple,
                projection_years=projection_years,
            )
        else:
            sensitivity_matrix_2d = sensitivity_coordinator.perform_2d_sensitivity_analysis(
                fcf_values=fcf_values,
                final_fcf=fcf_values[-1],
                base_wacc=wacc_components.wacc,
                base_growth=terminal_value_params.terminal_growth_rate,
                projection_years=projection_years,
            )
    except Exception as exc:
        logger.warning(
            "2D sensitivity matrix failed; continuing without matrix",
            extra={"error": str(exc), "error_type": type(exc).__name__},
            exc_info=True,
        )

    return DCFSensitivityArtifacts(
        sensitivity_wacc=sensitivity_wacc,
        sensitivity_growth=sensitivity_growth,
        sensitivity_matrix_2d=sensitivity_matrix_2d,
    )


def compute_confidence_artifacts(
    *,
    result_coordinator: ResultAggregationCoordinator,
    historical_fcf: object,
    fcf_projections: list[object],
    wacc_components: WACCComponents,
    logger: DCFLogger,
) -> DCFConfidenceArtifacts:
    confidence, confidence_score, confidence_factors = _assess_confidence_with_fallback(
        result_coordinator=result_coordinator,
        historical_fcf=historical_fcf,
        fcf_projections=fcf_projections,
        wacc_components=wacc_components,
        logger=logger,
    )
    return DCFConfidenceArtifacts(
        confidence=confidence,
        confidence_score=confidence_score,
        confidence_factors=confidence_factors,
        historical_fcf_readiness=build_historical_fcf_readiness(historical_fcf),
        transparency_data=_create_transparency_data_with_fallback(result_coordinator, logger),
    )


def build_historical_fcf_readiness(historical_fcf: object) -> dict[str, object]:
    historical_years_count = len(getattr(historical_fcf, "years", []) or [])
    actual_capex_years = int(getattr(historical_fcf, "actual_capex_years", 0) or 0)
    actual_tax_years = int(getattr(historical_fcf, "actual_tax_years", 0) or 0)
    actual_nwc_years = int(getattr(historical_fcf, "actual_nwc_years", 0) or 0)
    return {
        "status": _historical_fcf_readiness_status(
            historical_years_count=historical_years_count,
            actual_capex_years=actual_capex_years,
            actual_tax_years=actual_tax_years,
            actual_nwc_years=actual_nwc_years,
        ),
        "historical_years_count": historical_years_count,
        "actual_capex_years": actual_capex_years,
        "actual_tax_years": actual_tax_years,
        "actual_nwc_years": actual_nwc_years,
    }


def package_dcf_result(
    *,
    enterprise_value: Decimal,
    equity_value: Decimal,
    wacc_components: WACCComponents,
    terminal_value_params: TerminalValueParams,
    fcf_values: list[Decimal],
    pv_fcf_projections: list[Decimal],
    pv_terminal_value: Decimal,
    fcf_projections: list[object],
    sensitivity: DCFSensitivityArtifacts,
    confidence: DCFConfidenceArtifacts,
    implied_ev_ebitda: Optional[Decimal],
    terminal_value_steady_state: Optional[dict[str, object]],
    logger: DCFLogger,
) -> DCFResult:
    confidence_factors = _coerce_confidence_factors(confidence.confidence_factors)
    try:
        return _build_dcf_result(
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            wacc_components=wacc_components,
            terminal_value_params=terminal_value_params,
            fcf_values=fcf_values,
            pv_fcf_projections=pv_fcf_projections,
            pv_terminal_value=pv_terminal_value,
            sensitivity=sensitivity,
            confidence_value=confidence.confidence,
            confidence_score=confidence.confidence_score,
            confidence_factors=confidence_factors,
            historical_fcf_readiness=confidence.historical_fcf_readiness,
            transparency_data=confidence.transparency_data,
            fcf_projections=fcf_projections,
            implied_ev_ebitda=implied_ev_ebitda,
            terminal_value_steady_state=terminal_value_steady_state,
        )
    except Exception as exc:
        logger.warning(
            "DCFResult packaging failed; retrying with minimal transparency and empty sensitivities",
            extra={"error": str(exc), "error_type": type(exc).__name__},
            exc_info=True,
        )
        return _build_dcf_result(
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            wacc_components=wacc_components,
            terminal_value_params=terminal_value_params,
            fcf_values=fcf_values,
            pv_fcf_projections=pv_fcf_projections,
            pv_terminal_value=pv_terminal_value,
            sensitivity=DCFConstraints.empty_sensitivity(),
            confidence_value="medium",
            confidence_score=Decimal("0.5"),
            confidence_factors=[f"dcf_result_degraded:{type(exc).__name__}"],
            historical_fcf_readiness=confidence.historical_fcf_readiness,
            transparency_data={},
            fcf_projections=fcf_projections,
            implied_ev_ebitda=implied_ev_ebitda,
            terminal_value_steady_state=terminal_value_steady_state,
        )


def log_dcf_completion(
    *,
    logger: DCFLogger,
    enterprise_value: Decimal,
    equity_value: Decimal,
    wacc: Decimal,
    confidence: str,
) -> None:
    ev_log, eq_log, wacc_log = _format_completion_numbers(
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        wacc=wacc,
    )
    logger.info(
        "DCF valuation completed",
        enterprise_value=ev_log,
        equity_value=eq_log,
        wacc=wacc_log,
        confidence=confidence,
    )


class DCFConstraints:
    @staticmethod
    def empty_sensitivity() -> DCFSensitivityArtifacts:
        return DCFSensitivityArtifacts(
            sensitivity_wacc={},
            sensitivity_growth={},
            sensitivity_matrix_2d=None,
        )


def _resolve_net_debt(financial_data: FinancialData) -> Decimal:
    if hasattr(financial_data, "net_debt"):
        return financial_data.net_debt
    current_year = financial_data.current_year
    total_debt = current_year.total_debt if current_year.total_debt is not None else Decimal("0")
    cash = current_year.cash if current_year.cash is not None else Decimal("0")
    return total_debt - cash


def _resolve_cross_check_ebitda(
    *,
    financial_data: FinancialData,
    fcf_projections: list[object],
) -> Optional[Decimal]:
    if fcf_projections:
        first_ebitda = getattr(fcf_projections[0], "ebitda", None)
        if first_ebitda is not None and to_decimal(first_ebitda) > 0:
            return to_decimal(first_ebitda)
    cy_ebitda = getattr(financial_data.current_year, "ebitda", None)
    if cy_ebitda is not None and to_decimal(cy_ebitda) > 0:
        return to_decimal(cy_ebitda)
    return None


def _assess_confidence_with_fallback(
    *,
    result_coordinator: ResultAggregationCoordinator,
    historical_fcf: object,
    fcf_projections: list[object],
    wacc_components: WACCComponents,
    logger: DCFLogger,
) -> tuple[str, Decimal, list[str]]:
    try:
        confidence, confidence_score, confidence_factors = result_coordinator.assess_confidence(
            historical_fcf,
            fcf_projections,
            wacc_components,
        )
        return confidence, confidence_score, _coerce_confidence_factors(confidence_factors)
    except Exception as exc:
        logger.warning(
            "Confidence assessment raised; using medium defaults",
            extra={"error": str(exc), "error_type": type(exc).__name__},
            exc_info=True,
        )
        return "medium", Decimal("0.5"), [f"confidence_degraded:{type(exc).__name__}"]


def _historical_fcf_readiness_status(
    *,
    historical_years_count: int,
    actual_capex_years: int,
    actual_tax_years: int,
    actual_nwc_years: int,
) -> str:
    if (
        historical_years_count >= 2
        and actual_capex_years >= historical_years_count
        and actual_tax_years >= historical_years_count
        and actual_nwc_years >= max(0, historical_years_count - 1)
    ):
        return "imported_ready"
    if actual_capex_years > 0 or actual_tax_years > 0 or actual_nwc_years > 0:
        return "partial"
    return "manual_fallback"


def _create_transparency_data_with_fallback(
    result_coordinator: ResultAggregationCoordinator,
    logger: DCFLogger,
) -> dict[str, object]:
    try:
        return result_coordinator.create_transparency_data() or {}
    except Exception as exc:
        logger.warning(
            "Transparency data creation raised; continuing with empty dict",
            extra={"error": str(exc), "error_type": type(exc).__name__},
            exc_info=True,
        )
        return {}


def _coerce_confidence_factors(confidence_factors: object) -> list[str]:
    try:
        if not isinstance(confidence_factors, list):
            return [str(confidence_factors)]
        return [str(item) for item in confidence_factors]
    except Exception:
        return ["confidence_factors_coercion_failed"]


def _build_dcf_result(
    *,
    enterprise_value: Decimal,
    equity_value: Decimal,
    wacc_components: WACCComponents,
    terminal_value_params: TerminalValueParams,
    fcf_values: list[Decimal],
    pv_fcf_projections: list[Decimal],
    pv_terminal_value: Decimal,
    sensitivity: DCFSensitivityArtifacts,
    confidence_value: str,
    confidence_score: Decimal,
    confidence_factors: list[str],
    historical_fcf_readiness: dict[str, object],
    transparency_data: dict[str, object],
    fcf_projections: list[object],
    implied_ev_ebitda: Optional[Decimal],
    terminal_value_steady_state: Optional[dict[str, object]],
) -> DCFResult:
    return DCFResult(
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        wacc=wacc_components.wacc,
        cost_of_equity=wacc_components.cost_of_equity,
        cost_of_debt=wacc_components.cost_of_debt,
        terminal_growth_rate=terminal_value_params.terminal_growth_rate,
        fcf_projections=fcf_values,
        pv_fcf_projections=pv_fcf_projections,
        terminal_value=terminal_value_params.terminal_value,
        pv_terminal_value=pv_terminal_value,
        sensitivity_wacc=sensitivity.sensitivity_wacc,
        sensitivity_growth=sensitivity.sensitivity_growth,
        confidence=confidence_value,
        confidence_score=confidence_score,
        confidence_factors=confidence_factors,
        historical_fcf_readiness=historical_fcf_readiness,
        sensitivity_matrix_2d=sensitivity.sensitivity_matrix_2d,
        methodology="dcf_refactored",
        transparency_data=transparency_data,
        wacc_components=wacc_components,
        projection_detail=fcf_projections,
        implied_ev_ebitda=implied_ev_ebitda,
        terminal_value_steady_state=terminal_value_steady_state,
        terminal_growth_evidence=terminal_value_params.terminal_growth_evidence,
    )


def _format_completion_numbers(
    *,
    enterprise_value: Decimal,
    equity_value: Decimal,
    wacc: Decimal,
) -> tuple[str, str, str]:
    try:
        return (
            f"€{enterprise_value:,.0f}",
            f"€{equity_value:,.0f}",
            f"{wacc:.2%}",
        )
    except (InvalidOperation, ValueError, TypeError):
        return str(enterprise_value), str(equity_value), str(wacc)
