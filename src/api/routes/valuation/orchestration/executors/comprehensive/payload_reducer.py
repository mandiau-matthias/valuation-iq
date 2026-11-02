"""
Payload Reducer for Comprehensive Valuation

Reduces response payload size by removing detailed calculation data
when comprehensive HTML reports are available.
"""

import json
import time
from typing import Optional

from src.api.routes.valuation.orchestration.executors.comprehensive.payload_pipeline_reduction import (
    extract_minimal_multiple_pipeline,
)
from src.api.schemas import DCFValuationResponse, MultiplesValuationResponse, ValuationResponse
from src.utils.valuation_logger import ValuationLogger


class PayloadReducer:
    """
    Reduces response payload size.

    Responsibilities:
    - Remove detailed calculation_steps from transparency
    - Reduce multiples_valuation to summary only
    - Reduce dcf_valuation to summary only
    - Calculate payload savings
    """

    def __init__(self, logger: Optional[ValuationLogger] = None):
        """
        Initialize payload reducer.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or ValuationLogger(self.__class__.__name__)

    def _extract_minimal_multiple_pipeline(self, response: ValuationResponse):
        """Keep a compact canonical pipeline for report aggregation after payload reduction."""
        return extract_minimal_multiple_pipeline(response)

    @staticmethod
    def _serialized_payload_size(response: ValuationResponse) -> int:
        try:
            response_dict = response.model_dump(exclude_none=False)
            return len(json.dumps(response_dict, default=str))
        except Exception:
            return 0

    def _compact_transparency_steps(
        self,
        *,
        response: ValuationResponse,
        minimal_pipeline: object,
        request_company_name: str,
        correlation_id: str,
    ) -> None:
        transparency = getattr(response, "transparency", None)
        if not transparency or not hasattr(transparency, "calculation_steps"):
            return
        if not transparency.calculation_steps:
            return

        if minimal_pipeline:
            transparency.calculation_steps = [
                {
                    "step": 11,
                    "status": "completed",
                    "result": {"multiple_pipeline": minimal_pipeline},
                }
            ]
            self.logger.info(
                "✅ Reduced transparency calculation_steps to compact canonical pipeline",
                extra={"company": request_company_name, "correlation_id": correlation_id},
            )
            return

        transparency.calculation_steps = {}
        self.logger.debug(
            "✅ Removed detailed calculation_steps from transparency (contained in html_report)",
            extra={"company": request_company_name, "correlation_id": correlation_id},
        )

    def _log_payload_reduction_complete(
        self,
        *,
        request_company_name: str,
        correlation_id: str,
        original_payload_size: int,
        reduced_payload_size: int,
        reduction_duration_seconds: float,
    ) -> None:
        payload_savings = (
            original_payload_size - reduced_payload_size
            if original_payload_size > 0 and reduced_payload_size > 0
            else 0
        )
        payload_savings_percent = (
            (payload_savings / original_payload_size * 100) if original_payload_size > 0 else 0
        )
        self.logger.debug(
            "✅ Payload reduction complete",
            extra={
                "company": request_company_name,
                "correlation_id": correlation_id,
                "original_payload_size_kb": (
                    round(original_payload_size / 1024, 2) if original_payload_size > 0 else None
                ),
                "reduced_payload_size_kb": (
                    round(reduced_payload_size / 1024, 2) if reduced_payload_size > 0 else None
                ),
                "payload_savings_kb": (
                    round(payload_savings / 1024, 2) if payload_savings > 0 else None
                ),
                "payload_savings_percent": (
                    round(payload_savings_percent, 1) if payload_savings_percent > 0 else None
                ),
                "reduction_duration_seconds": round(reduction_duration_seconds, 3),
            },
        )

    def reduce_payload(
        self, response: ValuationResponse, request_company_name: str, correlation_id: str
    ) -> ValuationResponse:
        """
        Reduce payload size by removing detailed data when HTML reports are available.

        Args:
            response: Valuation response
            request_company_name: Company name
            correlation_id: Correlation ID

        Returns:
            Response with reduced payload
        """
        # Only reduce payload if html_report is present
        if not (response.html_report and len(response.html_report) > 0):
            return response

        payload_reduction_start = time.time()

        try:
            minimal_pipeline = self._extract_minimal_multiple_pipeline(response)
            original_payload_size = self._serialized_payload_size(response)

            # Remove detailed calculation_steps from transparency (contained in HTML report)
            self._compact_transparency_steps(
                response=response,
                minimal_pipeline=minimal_pipeline,
                request_company_name=request_company_name,
                correlation_id=correlation_id,
            )

            # Reduce multiples_valuation to summary only
            if response.multiples_valuation:
                original_multiples = response.multiples_valuation

                response.multiples_valuation = MultiplesValuationResponse(
                    enterprise_value=original_multiples.enterprise_value,
                    equity_value=original_multiples.equity_value,
                    equity_value_low=original_multiples.equity_value_low,
                    equity_value_mid=original_multiples.equity_value_mid,
                    equity_value_high=original_multiples.equity_value_high,
                    ev_ebitda_valuation=original_multiples.ev_ebitda_valuation,
                    ev_revenue_valuation=original_multiples.ev_revenue_valuation,
                    pe_valuation=original_multiples.pe_valuation,
                    ebitda_multiple=original_multiples.ebitda_multiple,
                    revenue_multiple=original_multiples.revenue_multiple,
                    pe_multiple=original_multiples.pe_multiple,
                    p10_ebitda_multiple=getattr(original_multiples, "p10_ebitda_multiple", None),
                    p25_ebitda_multiple=original_multiples.p25_ebitda_multiple,
                    p50_ebitda_multiple=original_multiples.p50_ebitda_multiple,
                    p75_ebitda_multiple=original_multiples.p75_ebitda_multiple,
                    p90_ebitda_multiple=getattr(original_multiples, "p90_ebitda_multiple", None),
                    p25_revenue_multiple=original_multiples.p25_revenue_multiple,
                    p50_revenue_multiple=original_multiples.p50_revenue_multiple,
                    p75_revenue_multiple=original_multiples.p75_revenue_multiple,
                    primary_method=original_multiples.primary_method,
                    earnings_basis=getattr(original_multiples, "earnings_basis", None),
                    data_source=original_multiples.data_source,
                    comparables_count=original_multiples.comparables_count,
                    comparables_quality=original_multiples.comparables_quality,
                    base_value=original_multiples.base_value,
                    size_discount=original_multiples.size_discount,
                    liquidity_discount=original_multiples.liquidity_discount,
                    country_adjustment=original_multiples.country_adjustment,
                    growth_premium=original_multiples.growth_premium,
                    total_adjustment=original_multiples.total_adjustment,
                    adjusted_equity_value=original_multiples.adjusted_equity_value,
                    confidence=original_multiples.confidence,
                    confidence_score=original_multiples.confidence_score,
                    owner_concentration=(
                        original_multiples.owner_concentration
                        if hasattr(original_multiples, "owner_concentration")
                        else None
                    ),
                    multiple_type_blend=getattr(original_multiples, "multiple_type_blend", None),
                    discount_build_up=getattr(original_multiples, "discount_build_up", None),
                    multiple_build_up=getattr(original_multiples, "multiple_build_up", None),
                    advisor_override_governance=getattr(
                        original_multiples, "advisor_override_governance", None
                    ),
                    segment_valuation=getattr(original_multiples, "segment_valuation", None),
                )
                self.logger.debug(
                    "✅ Reduced multiples_valuation to summary only (detailed breakdown in html_report)",
                    extra={"company": request_company_name, "correlation_id": correlation_id},
                )

            # Reduce dcf_valuation to summary only
            if response.dcf_valuation:
                original_dcf = response.dcf_valuation

                response.dcf_valuation = DCFValuationResponse(
                    enterprise_value=original_dcf.enterprise_value,
                    enterprise_value_low=getattr(original_dcf, "enterprise_value_low", None),
                    enterprise_value_mid=getattr(original_dcf, "enterprise_value_mid", None),
                    enterprise_value_high=getattr(original_dcf, "enterprise_value_high", None),
                    equity_value=original_dcf.equity_value,
                    equity_value_low=getattr(original_dcf, "equity_value_low", None),
                    equity_value_mid=getattr(original_dcf, "equity_value_mid", None),
                    equity_value_high=getattr(original_dcf, "equity_value_high", None),
                    wacc=original_dcf.wacc,
                    cost_of_equity=original_dcf.cost_of_equity,
                    cost_of_debt=original_dcf.cost_of_debt,
                    terminal_growth_rate=original_dcf.terminal_growth_rate,
                    terminal_value=original_dcf.terminal_value,
                    terminal_value_methodology=original_dcf.terminal_value_methodology,
                    terminal_exit_multiple=original_dcf.terminal_exit_multiple,
                    pv_terminal_value=original_dcf.pv_terminal_value,
                    mid_year_discounting=getattr(original_dcf, "mid_year_discounting", True),
                    discount_periods_note=getattr(original_dcf, "discount_periods_note", None),
                    academic_cost_of_equity_formula=getattr(
                        original_dcf, "academic_cost_of_equity_formula", None
                    ),
                    wacc_buildup=getattr(original_dcf, "wacc_buildup", None),
                    terminal_value_pct_of_total=getattr(
                        original_dcf, "terminal_value_pct_of_total", None
                    ),
                    explicit_forecast_pct_of_total=getattr(
                        original_dcf, "explicit_forecast_pct_of_total", None
                    ),
                    fcf_projections_5y=original_dcf.fcf_projections_5y,
                    pv_fcf_projections_5y=original_dcf.pv_fcf_projections_5y,
                    calculation_contract_version=original_dcf.calculation_contract_version,
                    fcf_projections=original_dcf.fcf_projections,
                    pv_fcf_projections=original_dcf.pv_fcf_projections,
                    sensitivity_wacc=original_dcf.sensitivity_wacc,
                    sensitivity_growth=original_dcf.sensitivity_growth,
                    sensitivity_matrix_2d=original_dcf.sensitivity_matrix_2d,
                    confidence=original_dcf.confidence,
                    confidence_score=original_dcf.confidence_score,
                    confidence_factors=original_dcf.confidence_factors,
                    historical_fcf_readiness=original_dcf.historical_fcf_readiness,
                    dcf_audit_trail=getattr(original_dcf, "dcf_audit_trail", None),
                    apv_contract_version=original_dcf.apv_contract_version,
                    apv_tax_shield_projections=original_dcf.apv_tax_shield_projections,
                    apv_tax_shield_pv=original_dcf.apv_tax_shield_pv,
                    dcf_enterprise_value_before_apv=original_dcf.dcf_enterprise_value_before_apv,
                    dcf_equity_value_before_apv=original_dcf.dcf_equity_value_before_apv,
                    apv_methodology=original_dcf.apv_methodology,
                    apv_discount_rate=original_dcf.apv_discount_rate,
                    apv_discounting_convention=original_dcf.apv_discounting_convention,
                    apv_tax_shield_value=original_dcf.apv_tax_shield_value,
                    apv_tax_shield_pct_of_total=original_dcf.apv_tax_shield_pct_of_total,
                    apv_enterprise_value=original_dcf.apv_enterprise_value,
                    apv_equity_value=original_dcf.apv_equity_value,
                    apv_tax_shield_projections_5y=original_dcf.apv_tax_shield_projections_5y,
                    apv_tax_shield_pv_5y=original_dcf.apv_tax_shield_pv_5y,
                    apv_bridge_provenance=original_dcf.apv_bridge_provenance,
                    apv_benchmark_reconciliation=original_dcf.apv_benchmark_reconciliation,
                )
                self.logger.info(
                    "✅ Reduced dcf_valuation to summary only (detailed breakdown in html_report)",
                    extra={"company": request_company_name, "correlation_id": correlation_id},
                )

            # Preserve canonical multiple_pipeline in compact responses so report
            # aggregation can stay on Step-11-consistent EV/metric values.
            if response.multiple_pipeline:
                self.logger.info(
                    "✅ Preserved multiple_pipeline for downstream report consistency",
                    extra={"company": request_company_name, "correlation_id": correlation_id},
                )

            reduced_payload_size = self._serialized_payload_size(response)
            self._log_payload_reduction_complete(
                request_company_name=request_company_name,
                correlation_id=correlation_id,
                original_payload_size=original_payload_size,
                reduced_payload_size=reduced_payload_size,
                reduction_duration_seconds=time.time() - payload_reduction_start,
            )

        except Exception as payload_reduction_error:
            self.logger.warning(
                "⚠️ Payload reduction failed (non-critical)",
                extra={
                    "company": request_company_name,
                    "correlation_id": correlation_id,
                    "error_type": type(payload_reduction_error).__name__,
                    "error_message": str(payload_reduction_error),
                },
                exc_info=True,
            )

        return response
