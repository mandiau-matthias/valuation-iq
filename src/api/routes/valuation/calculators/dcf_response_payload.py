"""Response payload assembly for API-layer DCF valuations."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from src.utils.decimal_helpers import to_decimal

from .dcf_benchmark_reconciliation import maybe_build_dcf_standard_benchmark_reconciliation
from .dcf_implied_multiple import resolve_implied_ev_ebitda


class DCFPayloadLogger(Protocol):
    def info(self, message: str, *, extra: Mapping[str, object] | None = None) -> None: ...

    def warning(
        self,
        message: str,
        *,
        extra: Mapping[str, object] | None = None,
        exc_info: object = None,
    ) -> None: ...


class NormalizeValuationRange(Protocol):
    def __call__(
        self,
        valuation_range: object,
        equity_mid: Decimal,
        logger: DCFPayloadLogger,
        *,
        correlation_id: object = None,
        company: object = None,
    ) -> Mapping[str, Decimal]: ...


class FallbackEquityRangeBand(Protocol):
    def __call__(self, equity_value: Decimal) -> Mapping[str, Decimal]: ...


@dataclass(frozen=True)
class DCFResponsePayloadInputs:
    request: object
    dcf_result: object | None
    normalized_valuation_range: Mapping[str, Decimal]
    net_debt: object
    ebitda: object
    has_manual_override: bool
    apv_bridge: Mapping[str, object] | None
    monte_carlo_results: Mapping[str, object] | None
    enterprise_value: object
    equity_value: object
    wacc: object
    cost_of_equity: object
    cost_of_debt: object
    terminal_growth_rate: object
    terminal_value: object
    terminal_value_methodology: object
    terminal_exit_multiple: object
    pv_terminal_value: object
    mid_year_discounting: bool
    discount_periods_note: str
    wacc_buildup: object
    terminal_value_pct_of_total: object
    explicit_forecast_pct_of_total: object
    cash_flow_projections: Sequence[Decimal]
    pv_fcf_projections: Sequence[Decimal]
    projection_years: int
    sensitivity_wacc: object
    sensitivity_growth: object
    sensitivity_matrix_2d: object
    confidence: object
    confidence_score: object
    confidence_factors: object
    dcf_audit_trail: object
    market_assumptions: object
    fcf_projection_detail: object
    data_quality_warnings: object


@dataclass(frozen=True)
class DCFCompletionLogContext:
    request: object
    correlation_id: object
    revenue: object
    ebitda: object
    net_debt: object
    cash: object
    using_weighted_metrics: bool
    weighting_method: object
    wacc: object
    cost_of_equity: object
    cost_of_debt: object
    terminal_growth_rate: object
    projection_years: int
    enterprise_value: object
    equity_value: object
    terminal_value: object
    pv_terminal_value: object
    confidence: object
    confidence_score: object
    normalized_valuation_range: Mapping[str, Decimal]

    @property
    def company(self) -> object:
        return getattr(self.request, "company_name", None)

    @property
    def historical_year_count(self) -> int:
        historical_years = getattr(self.request, "historical_years_data", None)
        if isinstance(historical_years, Sequence) and not isinstance(
            historical_years, (bytes, str)
        ):
            return len(historical_years)
        return 0


def build_dcf_response_payload(inputs: DCFResponsePayloadInputs) -> dict[str, object]:
    """Build the public DCF response dict from already-computed calculator values."""
    enterprise_value_low = inputs.normalized_valuation_range["equity_value_low"] + to_decimal(
        inputs.net_debt
    )
    enterprise_value_high = inputs.normalized_valuation_range["equity_value_high"] + to_decimal(
        inputs.net_debt
    )
    sum_pv_fcf = (
        sum(inputs.pv_fcf_projections, Decimal("0")) if inputs.pv_fcf_projections else Decimal("0")
    )

    dcf_benchmark_reconciliation = maybe_build_dcf_standard_benchmark_reconciliation(
        inputs.request,
        apv_bridge=inputs.apv_bridge,
        enterprise_value=inputs.enterprise_value,
        sum_pv_fcf=sum_pv_fcf,
        terminal_value=inputs.terminal_value,
        pv_terminal_value=inputs.pv_terminal_value,
    )
    implied_ev_ebitda_value = resolve_implied_ev_ebitda(
        inputs.dcf_result,
        has_manual_override=inputs.has_manual_override,
        ebitda=inputs.ebitda,
        enterprise_value=inputs.enterprise_value,
    )

    result = {
        "methodology": "DCF",
        "enterprise_value": inputs.enterprise_value,
        "enterprise_value_mid": inputs.enterprise_value,
        "enterprise_value_low": enterprise_value_low,
        "enterprise_value_high": enterprise_value_high,
        "equity_value": inputs.equity_value,
        "equity_value_mid": inputs.equity_value,
        **inputs.normalized_valuation_range,
        "per_share_value": None,
        "wacc": inputs.wacc,
        "cost_of_equity": inputs.cost_of_equity,
        "cost_of_debt": inputs.cost_of_debt,
        "terminal_growth_rate": inputs.terminal_growth_rate,
        "terminal_value": inputs.terminal_value,
        "terminal_value_methodology": inputs.terminal_value_methodology,
        "terminal_exit_multiple": inputs.terminal_exit_multiple,
        "pv_terminal_value": inputs.pv_terminal_value,
        "mid_year_discounting": inputs.mid_year_discounting,
        "discount_periods_note": inputs.discount_periods_note,
        "academic_cost_of_equity_formula": (
            "Risicovrije rente + bèta × aandelenrisicopremie + omvangspremie + bedrijfsspecifiek risico"
        ),
        "wacc_buildup": inputs.wacc_buildup,
        "terminal_value_pct_of_total": inputs.terminal_value_pct_of_total,
        "explicit_forecast_pct_of_total": inputs.explicit_forecast_pct_of_total,
        "implied_ev_ebitda": implied_ev_ebitda_value,
        "dcf_benchmark_reconciliation": dcf_benchmark_reconciliation,
        "terminal_value_steady_state": (
            getattr(inputs.dcf_result, "terminal_value_steady_state", None)
            if inputs.dcf_result is not None
            else None
        ),
        "fcf_projections_5y": list(inputs.cash_flow_projections[:5]),
        "pv_fcf_projections_5y": list(inputs.pv_fcf_projections[:5]),
        "calculation_contract_version": "dcf_calculation.v2",
        "fcf_projections": list(inputs.cash_flow_projections),
        "pv_fcf_projections": list(inputs.pv_fcf_projections),
        "projection_years": inputs.projection_years,
        "sensitivity_wacc": inputs.sensitivity_wacc,
        "sensitivity_growth": inputs.sensitivity_growth,
        "sensitivity_matrix_2d": inputs.sensitivity_matrix_2d,
        "confidence": inputs.confidence,
        "confidence_score": inputs.confidence_score,
        "confidence_factors": inputs.confidence_factors,
        "historical_fcf_readiness": (
            getattr(inputs.dcf_result, "historical_fcf_readiness", None)
            if inputs.dcf_result is not None
            else None
        ),
        "dcf_audit_trail": inputs.dcf_audit_trail,
        "market_assumptions": inputs.market_assumptions,
        "fcf_projection_detail": inputs.fcf_projection_detail,
        "data_quality_warnings": inputs.data_quality_warnings,
    }
    if inputs.apv_bridge is not None:
        result.update(inputs.apv_bridge)

    if inputs.monte_carlo_results:
        result["monte_carlo_results"] = inputs.monte_carlo_results

    return result


def safe_normalize_dcf_valuation_range(
    valuation_range: object,
    equity_value: Decimal,
    normalize_valuation_range: NormalizeValuationRange,
    fallback_equity_range: FallbackEquityRangeBand,
    logger: DCFPayloadLogger,
    *,
    correlation_id: object,
    company: object,
) -> Mapping[str, Decimal]:
    """Normalize the valuation range with a final symmetric fallback if normalization raises."""
    try:
        return normalize_valuation_range(
            valuation_range,
            equity_value,
            logger,
            correlation_id=correlation_id,
            company=company,
        )
    except Exception as norm_exc:
        logger.warning(
            "DCF valuation_range normalization raised; using symmetric fallback band",
            extra={
                "error": str(norm_exc),
                "error_type": type(norm_exc).__name__,
                "correlation_id": correlation_id,
                "company": company,
            },
            exc_info=True,
        )
        return fallback_equity_range(equity_value)


def safe_serialize_dcf_projection_detail(
    dcf_result: object | None,
    serialize_projection_detail: Callable[[object | None], object],
    logger: DCFPayloadLogger,
    *,
    correlation_id: object,
    company: object,
) -> object | None:
    """Serialize DCF projection detail without letting optional response polish fail DCF."""
    try:
        return serialize_projection_detail(dcf_result)
    except Exception as proj_exc:
        logger.warning(
            "DCF projection detail serialization failed; omitting field",
            extra={
                "error": str(proj_exc),
                "error_type": type(proj_exc).__name__,
                "correlation_id": correlation_id,
                "company": company,
            },
            exc_info=True,
        )
        return None


def build_dcf_completion_log_context(
    inputs: DCFResponsePayloadInputs,
    *,
    correlation_id: object,
    revenue: object,
    cash: object,
    using_weighted_metrics: bool,
    weighting_method: object,
) -> DCFCompletionLogContext:
    """Build completion-log context from response inputs and upstream input metadata."""
    return DCFCompletionLogContext(
        request=inputs.request,
        correlation_id=correlation_id,
        revenue=revenue,
        ebitda=inputs.ebitda,
        net_debt=inputs.net_debt,
        cash=cash,
        using_weighted_metrics=using_weighted_metrics,
        weighting_method=weighting_method,
        wacc=inputs.wacc,
        cost_of_equity=inputs.cost_of_equity,
        cost_of_debt=inputs.cost_of_debt,
        terminal_growth_rate=inputs.terminal_growth_rate,
        projection_years=inputs.projection_years,
        enterprise_value=inputs.enterprise_value,
        equity_value=inputs.equity_value,
        terminal_value=inputs.terminal_value,
        pv_terminal_value=inputs.pv_terminal_value,
        confidence=inputs.confidence,
        confidence_score=inputs.confidence_score,
        normalized_valuation_range=inputs.normalized_valuation_range,
    )


def log_dcf_completion_summary(logger: DCFPayloadLogger, context: DCFCompletionLogContext) -> None:
    """Emit the full DCF completion audit log without letting logging failures leak."""
    try:
        logger.info(
            "📊 DCF Valuation - Calculation Complete",
            extra={
                "methodology": "DCF (Discounted Cash Flow)",
                "status": "COMPLETED",
                "inputs": {
                    "revenue": context.revenue,
                    "ebitda": context.ebitda,
                    "net_debt": context.net_debt,
                    "cash": context.cash,
                    "using_weighted_metrics": context.using_weighted_metrics,
                    "weighting_method": context.weighting_method,
                    "historical_years": context.historical_year_count,
                },
                "calculation": {
                    "formula": "Enterprise Value = Σ(PV of FCF) + PV of Terminal Value",
                    "wacc": context.wacc,
                    "cost_of_equity": context.cost_of_equity,
                    "cost_of_debt": context.cost_of_debt,
                    "terminal_growth_rate": context.terminal_growth_rate,
                    "projection_years": context.projection_years,
                },
                "outputs": {
                    "enterprise_value": context.enterprise_value,
                    "equity_value": context.equity_value,
                    "terminal_value": context.terminal_value,
                    "pv_terminal_value": context.pv_terminal_value,
                },
                "metadata": {
                    "confidence_score": context.confidence_score,
                    "confidence_level": str(context.confidence),
                    "academic_reference": "McKinsey Valuation (2015), Damodaran (2012)",
                },
            },
        )
    except Exception as log_exc:
        logger.warning(
            "DCF completion summary log skipped (non-critical)",
            extra={
                "error": str(log_exc),
                "error_type": type(log_exc).__name__,
                "correlation_id": context.correlation_id,
                "company": context.company,
            },
        )


def log_dcf_range_summary(logger: DCFPayloadLogger, context: DCFCompletionLogContext) -> None:
    """Emit the compact DCF range log without letting logging failures leak."""
    try:
        logger.info(
            "✅ DCF valuation complete",
            extra={
                "enterprise_value": context.enterprise_value,
                "equity_value": context.equity_value,
                "equity_value_low": context.normalized_valuation_range["equity_value_low"],
                "equity_value_mid": context.normalized_valuation_range["equity_value_mid"],
                "equity_value_high": context.normalized_valuation_range["equity_value_high"],
            },
        )
    except Exception as log_exc:
        logger.warning(
            "DCF valuation range log skipped (non-critical)",
            extra={
                "error": str(log_exc),
                "error_type": type(log_exc).__name__,
                "correlation_id": context.correlation_id,
                "company": context.company,
            },
        )
