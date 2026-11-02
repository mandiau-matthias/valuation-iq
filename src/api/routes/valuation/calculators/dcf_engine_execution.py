"""Full DCF engine execution for the API calculator."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from src.api.schemas import ValuationRequest
from src.domain.dcf_engine import DCFValuationEngineRefactored
from src.domain.dcf_types import DCFConfiguration, WACCComponents
from src.utils.adaptive_input_helpers import get_customer_concentration_override
from src.utils.transparency_collector import TransparencyCollector

from .dcf_calculation_inputs import resolve_adapter_projection_years
from .dcf_data_adapter import DCFDataAdapter
from .dcf_market_assumptions import build_dcf_market_assumptions
from .dcf_pipeline_logging import dcf_pipeline_breadcrumb
from .dcf_result_shaping import (
    build_dcf_audit_trail,
    confidence_factors_from_engine,
    confidence_level_from_engine,
    confidence_score_from_engine,
    full_dcf_projection_vectors,
)
from .dcf_size_premium_resolver import resolve_size_premium_for_dcf_engine

RuntimePayload = dict[str, object]


@dataclass(frozen=True)
class DCFEngineExecution:
    dcf_result: object
    enterprise_value: Decimal
    equity_value: Decimal
    wacc: Decimal
    cost_of_equity: Decimal
    cost_of_debt: Decimal
    terminal_growth_rate: Decimal
    terminal_value: Decimal
    pv_terminal_value: Decimal
    cash_flow_projections: list[Decimal]
    pv_fcf_projections: list[Decimal]
    sensitivity_wacc: dict[str, Decimal]
    sensitivity_growth: dict[str, Decimal]
    confidence: object
    confidence_score: int
    confidence_factors: dict[str, object]
    dcf_audit_trail: object
    market_assumptions: RuntimePayload
    wacc_components: WACCComponents | None
    projection_years: int


def run_full_dcf_engine(
    request: ValuationRequest,
    *,
    logger: object,
    correlation_id: object,
    mid_year_discounting: bool,
    tax_rate_provenance_builder: Callable[[object], dict[str, object] | None],
    extract_has_audit: Callable[[ValuationRequest], bool | None],
    extract_owner_dependency_score: Callable[[ValuationRequest], Decimal | None],
    coerce_engine_sensitivity_1d_map: Callable[[object], dict[str, Decimal]],
    data_adapter_factory: Callable[[], DCFDataAdapter] = DCFDataAdapter,
) -> DCFEngineExecution:
    """Run the full domain DCF engine and shape its result for API orchestration."""
    company = getattr(request, "company_name", None)
    logger.debug(
        "📦 Creating DCF data adapter", extra={"note": "Adapter converts request to domain models"}
    )
    adapter = data_adapter_factory()

    logger.info(
        "📊 Converting request to domain models",
        extra={"models": ["FinancialData", "MarketContext", "IndustryBenchmarks"]},
    )
    financial_data = adapter.create_financial_data(request)
    projection_years = resolve_adapter_projection_years(
        getattr(financial_data, "forecast_years", None) or [],
        getattr(request, "projection_years", None),
    )
    logger.info(
        "🚀 Initializing full DCF engine",
        extra={
            "methodology": "DCF (Discounted Cash Flow)",
            "projection_years": projection_years,
            "sensitivity_analysis": True,
            "mid_year_discounting": mid_year_discounting,
        },
    )
    market_context, market_context_metadata = adapter.create_market_context(request)
    industry_benchmarks = adapter.create_industry_benchmarks(request)

    logger.info(
        "✅ Domain models created",
        extra={
            "company_id": financial_data.company_id,
            "bond_yield": f"{market_context.government_bond_yield*100:.2f}%",
            "industry_beta": industry_benchmarks.average_beta,
            "expected_growth": f"{industry_benchmarks.expected_growth_rate*100:.1f}%",
            "market_risk_premium": f"{market_context.equity_risk_premium*100:.2f}%",
        },
    )
    logger.info(
        "⚙️  Initializing DCF engine",
        extra={"note": "DCF engine will calculate WACC, project cash flows, and terminal value"},
    )

    revenue_for_size = Decimal(str(request.current_year_data.revenue or 0))
    sme_calibration = getattr(request, "sme_calibration", None)
    size_premium, _size_premium_source = resolve_size_premium_for_dcf_engine(
        revenue=revenue_for_size,
        sme_calibration=sme_calibration if isinstance(sme_calibration, dict) else None,
        logger=logger,
    )

    transparency_collector = TransparencyCollector()
    dcf_engine = DCFValuationEngineRefactored(
        financial_data=financial_data,
        market_context=market_context,
        industry_benchmarks=industry_benchmarks,
        config=DCFConfiguration(mid_year_discounting=mid_year_discounting),
        transparency_collector=transparency_collector,
        size_premium=size_premium,
        customer_concentration=get_customer_concentration_override(request),
        industry=getattr(request, "industry", None),
        has_audit=extract_has_audit(request),
        owner_dependency_score=extract_owner_dependency_score(request),
    )

    logger.info(
        "📈 Calculating DCF valuation",
        extra={
            "projection_years": projection_years,
            "sensitivity_analysis": True,
            "formula": "Enterprise Value = Σ(PV of FCF) + PV of Terminal Value",
            "note": "Terminal value uses Gordon Growth Model",
            "correlation_id": correlation_id,
        },
    )
    dcf_pipeline_breadcrumb(
        logger,
        stage="dcf_engine",
        phase="before_calculate_dcf_valuation",
        correlation_id=correlation_id,
        company=company,
        projection_years=projection_years,
    )
    dcf_result = dcf_engine.calculate_dcf_valuation(
        projection_years=projection_years,
        sensitivity_analysis=True,
    )
    dcf_pipeline_breadcrumb(
        logger,
        stage="dcf_engine",
        phase="after_calculate_dcf_valuation",
        correlation_id=correlation_id,
        company=company,
    )

    market_assumptions = build_dcf_market_assumptions(
        request,
        market_context,
        market_context_metadata,
        logger=logger,
        tax_rate_provenance_builder=tax_rate_provenance_builder,
    )
    dcf_pipeline_breadcrumb(
        logger,
        stage="market_assumptions",
        phase="built",
        correlation_id=correlation_id,
        company=company,
    )

    enterprise_value = dcf_result.enterprise_value
    equity_value = dcf_result.equity_value
    wacc = dcf_result.wacc
    cost_of_equity = dcf_result.cost_of_equity
    cost_of_debt = dcf_result.cost_of_debt
    terminal_growth_rate = dcf_result.terminal_growth_rate
    terminal_value = dcf_result.terminal_value
    pv_terminal_value = dcf_result.pv_terminal_value

    _log_engine_summary(
        logger,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        wacc=wacc,
        cost_of_equity=cost_of_equity,
        cost_of_debt=cost_of_debt,
        terminal_growth_rate=terminal_growth_rate,
        terminal_value=terminal_value,
        pv_terminal_value=pv_terminal_value,
        correlation_id=correlation_id,
        company=company,
    )

    cash_flow_projections, pv_fcf_projections = full_dcf_projection_vectors(dcf_result)
    dcf_pipeline_breadcrumb(
        logger,
        stage="dcf_audit_trail",
        phase="before_build",
        correlation_id=correlation_id,
        company=company,
    )
    dcf_audit_trail = _build_audit_trail(
        logger,
        transparency_collector,
        correlation_id=correlation_id,
        company=company,
    )
    dcf_pipeline_breadcrumb(
        logger,
        stage="dcf_audit_trail",
        phase="after_build",
        correlation_id=correlation_id,
        company=company,
    )

    return DCFEngineExecution(
        dcf_result=dcf_result,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        wacc=wacc,
        cost_of_equity=cost_of_equity,
        cost_of_debt=cost_of_debt,
        terminal_growth_rate=terminal_growth_rate,
        terminal_value=terminal_value,
        pv_terminal_value=pv_terminal_value,
        cash_flow_projections=cash_flow_projections,
        pv_fcf_projections=pv_fcf_projections,
        sensitivity_wacc=coerce_engine_sensitivity_1d_map(
            getattr(dcf_result, "sensitivity_wacc", None)
        ),
        sensitivity_growth=coerce_engine_sensitivity_1d_map(
            getattr(dcf_result, "sensitivity_growth", None)
        ),
        confidence=confidence_level_from_engine(getattr(dcf_result, "confidence", None)),
        confidence_score=confidence_score_from_engine(
            getattr(dcf_result, "confidence_score", None)
        ),
        confidence_factors=confidence_factors_from_engine(
            getattr(dcf_result, "confidence_factors", None)
        ),
        dcf_audit_trail=dcf_audit_trail,
        market_assumptions=market_assumptions,
        wacc_components=getattr(dcf_result, "wacc_components", None),
        projection_years=projection_years,
    )


def _log_engine_summary(
    logger: object,
    *,
    enterprise_value: Decimal,
    equity_value: Decimal,
    wacc: Decimal,
    cost_of_equity: Decimal,
    cost_of_debt: Decimal,
    terminal_growth_rate: Decimal,
    terminal_value: Decimal,
    pv_terminal_value: Decimal,
    correlation_id: object,
    company: object,
) -> None:
    try:
        logger.info(
            "✅ DCF calculation complete",
            extra={
                "enterprise_value": enterprise_value,
                "equity_value": equity_value,
                "wacc": f"{wacc*100:.2f}%",
                "cost_of_equity": f"{cost_of_equity*100:.2f}%",
                "cost_of_debt": f"{cost_of_debt*100:.2f}%" if cost_of_debt else None,
                "terminal_growth_rate": f"{terminal_growth_rate*100:.2f}%",
                "terminal_value": terminal_value,
                "pv_terminal_value": pv_terminal_value,
            },
        )
        logger.info(
            "✅ Full DCF calculation complete",
            extra={
                "enterprise_value": f"€{enterprise_value:,.0f}",
                "equity_value": f"€{equity_value:,.0f}",
                "wacc": f"{wacc*100:.2f}%",
                "terminal_growth": f"{terminal_growth_rate*100:.2f}%",
                "correlation_id": correlation_id,
            },
        )
    except Exception as log_exc:
        logger.warning(
            "DCF engine summary log skipped (non-critical)",
            extra={
                "error": str(log_exc),
                "error_type": type(log_exc).__name__,
                "correlation_id": correlation_id,
                "company": company,
            },
        )


def _build_audit_trail(
    logger: object,
    transparency_collector: TransparencyCollector,
    *,
    correlation_id: object,
    company: object,
) -> object:
    try:
        return build_dcf_audit_trail(transparency_collector)
    except Exception as audit_exc:
        logger.warning(
            "DCF audit trail build failed; continuing without trail",
            extra={
                "error": str(audit_exc),
                "error_type": type(audit_exc).__name__,
                "correlation_id": correlation_id,
                "company": company,
            },
            exc_info=True,
        )
        return {
            "step_count": 0,
            "source_count": 0,
            "steps": [],
            "sources": [],
            "degraded": True,
            "degraded_reason": f"{type(audit_exc).__name__}: {audit_exc}",
        }
