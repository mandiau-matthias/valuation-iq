"""Valuation alignment preparation for main report aggregation."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Protocol

from src.services.infrastructure.main_report_source_context import MainReportSourceContext
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.reports.ev_equity_bridge_context import (
    BridgeContextBuilder,
    prepare_ev_equity_bridge_context,
)
from src.services.reports.dcf_eligibility_guardrail import is_dcf_ineligible_forced_blend
from src.services.reports.formula_alignment_context import align_formula_context
from src.services.reports.main_report_benchmark_disclosure_context import (
    build_main_report_benchmark_disclosure_context,
)
from src.services.reports.report_headline_valuation_alignment import align_report_headline_valuation
from src.utils.decimal_helpers import safe_decimal_or_zero as safe_decimal

ValuationResponse = ValuationResponseProtocol
ValuationRequest = ValuationRequestProtocol


class MainReportValuationAggregator(Protocol):
    logger: object

    def _is_dcf_only_methodology(self, response): ...

    def _is_asset_anchored_methodology(self, response): ...

    def _unwrap_synthesis(self, payload): ...

    def _is_hybrid_methodology(self, response): ...

    def _has_balance_data(self, response, request): ...


@dataclass
class MainReportValuationAlignmentContext:
    """Aligned valuation facts for main report context assembly."""

    is_dcf_only: bool
    is_asset_anchored: bool
    has_weighted_synthesis_payload: bool
    dcf_ineligible_forced_blend: bool
    is_hybrid_method: bool
    has_balance_data: bool
    enterprise_value_low: Decimal
    enterprise_value_mid: Decimal
    enterprise_value_high: Decimal
    equity_value_low: Decimal | None
    equity_value: Decimal | None
    equity_value_high: Decimal | None
    formula_metric_value: Decimal
    multiple_low: Decimal
    multiple_high: Decimal
    display_multiple: Decimal
    pre_synthesis_multiple: Decimal
    #: Rail ``display_multiple`` and the multiple band sit on — see
    #: ``ReportHeadlineValuationAlignment.applied_multiple_rail``.
    applied_multiple_rail: str
    engine_synthesis_equity_anchored: bool
    total_discount: Decimal
    has_industry_benchmarks: bool
    benchmark_disclosure: object
    has_benchmark_reference_multiple: bool
    bridge_context: object
    net_debt_from_steps: Decimal | None
    aligned_recommended_asking_price: Decimal | None
    asking_price_realigned: bool
    show_ev_equity_bridge: bool
    show_enterprise_to_equity_bridge: bool
    has_net_debt_adjustment: bool
    bridge_net_debt_operator: object
    bridge_net_debt_amount: Decimal
    tax_latencies: object
    tax_latency_net_impact: object
    tax_latency_net_impact_decimal: Decimal
    balance_sheet_adjustments: object
    nwc_signed: Decimal
    displayed_net_debt: Decimal
    bridge_residual: Decimal
    show_bridge_cash_split: bool
    bridge_cash_total: Decimal
    bridge_excess_cash: Decimal
    bridge_ib_debt: Decimal
    bridge_operating_cash_held: Decimal


def build_main_report_valuation_alignment_context(
    aggregator: MainReportValuationAggregator,
    *,
    response: ValuationResponse,
    request: Optional[ValuationRequest],
    source: MainReportSourceContext,
    bridge_context_builder: BridgeContextBuilder | None = None,
) -> MainReportValuationAlignmentContext:
    """Align formula, headline, benchmark, and bridge valuation facts."""
    step_data = source.step_data
    multiple_context = source.multiple_context

    is_dcf_only = aggregator._is_dcf_only_methodology(response)
    is_asset_anchored = aggregator._is_asset_anchored_methodology(response)
    weighted_synthesis_payload = aggregator._unwrap_synthesis(
        getattr(response, "weighted_valuation", None)
    )
    _has_weighted_synthesis_payload = bool(weighted_synthesis_payload) and safe_decimal(
        weighted_synthesis_payload.get("blended_equity_value")
    ) > Decimal("0")
    # Guardrail: when the blend includes a DCF leg the engine deemed ineligible
    # (forced in below the revenue/history threshold), drop synthesis from the
    # headline path so the alignment pins to the market leg; the blend is surfaced
    # downstream as a labelled advisor scenario.
    dcf_ineligible_forced_blend = (
        _has_weighted_synthesis_payload
        and is_dcf_ineligible_forced_blend(response, weighted_synthesis_payload)
    )
    has_weighted_synthesis_payload = (
        _has_weighted_synthesis_payload and not dcf_ineligible_forced_blend
    )

    formula_alignment = align_formula_context(
        step_data=step_data,
        multiple_context=multiple_context,
        revenue_value=source.revenue_value,
        sustainable_ebitda=source.sustainable_ebitda,
        enterprise_value_low=source.enterprise_value_low,
        enterprise_value_mid=source.enterprise_value_mid,
        enterprise_value_high=source.enterprise_value_high,
        applied_multiple=source.applied_multiple,
        multiple_low=source.multiple_low,
        multiple_high=source.multiple_high,
        is_dcf_only=is_dcf_only,
        is_asset_anchored=is_asset_anchored,
        is_weighted_synthesis=has_weighted_synthesis_payload,
        logger=aggregator.logger,
    )

    is_hybrid_method = aggregator._is_hybrid_methodology(response)
    has_balance_data = aggregator._has_balance_data(response, request)
    headline_alignment = align_report_headline_valuation(
        response=response,
        step_data=step_data,
        multiple_context=multiple_context,
        revenue_value=source.revenue_value,
        sustainable_ebitda=source.sustainable_ebitda,
        enterprise_value_low=formula_alignment.enterprise_value_low,
        enterprise_value_mid=formula_alignment.enterprise_value_mid,
        enterprise_value_high=formula_alignment.enterprise_value_high,
        equity_value_low=source.equity_value_low,
        equity_value=source.equity_value,
        equity_value_high=source.equity_value_high,
        formula_metric_value=formula_alignment.metric_value,
        applied_multiple=safe_decimal(source.applied_multiple),
        multiple_low=safe_decimal(source.multiple_low),
        multiple_high=safe_decimal(source.multiple_high),
        is_dcf_only=is_dcf_only,
        is_asset_anchored=is_asset_anchored,
        has_weighted_synthesis_payload=has_weighted_synthesis_payload,
        is_hybrid_method=is_hybrid_method,
        has_balance_data=has_balance_data,
        dcf_ineligible_forced_blend=dcf_ineligible_forced_blend,
        logger=aggregator.logger,
    )

    total_discount = headline_alignment.display_multiple - safe_decimal(source.base_multiple)
    has_industry_benchmarks = bool(source.industry_benchmarks.get("has_benchmarks", False))
    benchmark_disclosure = build_main_report_benchmark_disclosure_context(
        step_data=step_data,
        multiple_context=multiple_context,
        base_multiple=source.base_multiple,
        revenue_value=source.revenue_value,
        has_industry_benchmarks=has_industry_benchmarks,
        is_dcf_only=is_dcf_only,
        is_asset_anchored=is_asset_anchored,
    )

    bridge_preparation = prepare_ev_equity_bridge_context(
        response=response,
        request=request,
        step_data=step_data,
        enterprise_value_mid=headline_alignment.enterprise_value_mid,
        equity_value_low=headline_alignment.equity_value_low,
        equity_value=headline_alignment.equity_value,
        equity_value_high=headline_alignment.equity_value_high,
        has_balance_data=has_balance_data,
        is_dcf_only=is_dcf_only,
        logger=aggregator.logger,
        bridge_context_builder=bridge_context_builder,
    )

    return MainReportValuationAlignmentContext(
        is_dcf_only=is_dcf_only,
        is_asset_anchored=is_asset_anchored,
        has_weighted_synthesis_payload=has_weighted_synthesis_payload,
        dcf_ineligible_forced_blend=dcf_ineligible_forced_blend,
        is_hybrid_method=is_hybrid_method,
        has_balance_data=has_balance_data,
        enterprise_value_low=headline_alignment.enterprise_value_low,
        enterprise_value_mid=headline_alignment.enterprise_value_mid,
        enterprise_value_high=headline_alignment.enterprise_value_high,
        equity_value_low=bridge_preparation.equity_value_low,
        equity_value=bridge_preparation.equity_value,
        equity_value_high=bridge_preparation.equity_value_high,
        formula_metric_value=headline_alignment.formula_metric_value,
        multiple_low=headline_alignment.multiple_low,
        multiple_high=headline_alignment.multiple_high,
        display_multiple=headline_alignment.display_multiple,
        pre_synthesis_multiple=headline_alignment.pre_synthesis_multiple,
        applied_multiple_rail=headline_alignment.applied_multiple_rail,
        engine_synthesis_equity_anchored=headline_alignment.engine_synthesis_equity_anchored,
        total_discount=total_discount,
        has_industry_benchmarks=has_industry_benchmarks,
        benchmark_disclosure=benchmark_disclosure,
        has_benchmark_reference_multiple=benchmark_disclosure.has_benchmark_reference_multiple,
        bridge_context=bridge_preparation.bridge_context,
        net_debt_from_steps=bridge_preparation.net_debt_from_steps,
        aligned_recommended_asking_price=bridge_preparation.aligned_recommended_asking_price,
        asking_price_realigned=bridge_preparation.asking_price_realigned,
        show_ev_equity_bridge=bridge_preparation.show_ev_equity_bridge,
        show_enterprise_to_equity_bridge=bridge_preparation.show_enterprise_to_equity_bridge,
        has_net_debt_adjustment=bridge_preparation.has_net_debt_adjustment,
        bridge_net_debt_operator=bridge_preparation.bridge_net_debt_operator,
        bridge_net_debt_amount=bridge_preparation.bridge_net_debt_amount,
        tax_latencies=bridge_preparation.tax_latencies,
        tax_latency_net_impact=bridge_preparation.tax_latency_net_impact,
        tax_latency_net_impact_decimal=bridge_preparation.tax_latency_net_impact_decimal,
        balance_sheet_adjustments=bridge_preparation.balance_sheet_adjustments,
        nwc_signed=bridge_preparation.nwc_signed,
        displayed_net_debt=bridge_preparation.displayed_net_debt,
        bridge_residual=bridge_preparation.bridge_residual,
        show_bridge_cash_split=bridge_preparation.show_bridge_cash_split,
        bridge_cash_total=bridge_preparation.bridge_cash_total,
        bridge_excess_cash=bridge_preparation.bridge_excess_cash,
        bridge_ib_debt=bridge_preparation.bridge_ib_debt,
        bridge_operating_cash_held=bridge_preparation.bridge_operating_cash_held,
    )
