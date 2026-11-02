"""
Response Builder for Comprehensive Valuation

Builds response dictionary with basic fields, DCF/Multiples valuations,
and summary components for comprehensive valuation orchestrator.
"""

from decimal import Decimal
from typing import Dict, List, Optional

from src.api.routes.valuation.orchestration.executors.comprehensive.response_data_sources import (
    build_response_data_sources,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_dcf_bridge import (
    canonicalize_dcf_only_bridge,
    decimal_from_dict,
    is_requested_dcf_only,
    requested_method_signal,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_dict_assembly import (
    attach_consolidation_fields,
    attach_methodology_label,
    attach_nested_valuations,
    attach_optional_owner_fields,
    attach_post_deal_swap,
    attach_presentation_fields,
    attach_quality_warnings,
    build_base_response_dict,
    log_current_year_diagnostics,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_methodology_substitution import (
    extract_methodology_substitution_payload,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_pipeline_details import (
    attach_multiples_pipeline_details,
    attach_multiples_prompt_payloads,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_summary_components import (
    attach_summary_components,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_value_context import (
    prepare_response_values,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_warning_aggregation import (
    aggregate_quality_warnings,
    ensure_method_substitution_warning,
)
from src.api.schemas import FinancialMetricsResponse, ValuationRequest
from src.utils.valuation_logger import ValuationLogger


class ResponseBuilder:
    """
    Builds response dictionary for comprehensive valuation.

    Responsibilities:
    - Construct basic response fields
    - Build DCF and Multiples valuation responses
    - Generate summary components
    - Validate response data quality
    """

    def __init__(
        self,
        response_builder,  # Existing ResponseBuilder from orchestration/builders
        summary_generator,
        confidence_scorer,
        logger: Optional[ValuationLogger] = None,
    ):
        """
        Initialize comprehensive response builder.

        Args:
            response_builder: Existing ResponseBuilder instance
            summary_generator: SummaryGenerator instance
            confidence_scorer: ConfidenceScorer instance
            logger: Optional logger instance
        """
        self.response_builder = response_builder
        self.summary_generator = summary_generator
        self.confidence_scorer = confidence_scorer
        self.logger = logger or ValuationLogger(self.__class__.__name__)

    def build_response_dict(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, object],
        valuation_id: str,
        methodology: str,
        equity_value_low: Decimal,
        equity_value_mid: Decimal,
        equity_value_high: Decimal,
        confidence_score: Decimal,
        financial_metrics: FinancialMetricsResponse,
        methodology_downgrade_reason: Optional[str],
        dcf_exclusion_reason_precheck: Optional[str],
        correlation_id: str,
    ) -> Dict[str, object]:
        """
        Build response dictionary with all fields.

        Args:
            request: Valuation request
            detailed_results: Detailed valuation results
            valuation_id: Valuation ID
            methodology: Determined methodology
            equity_value_low: Low equity value
            equity_value_mid: Mid equity value
            equity_value_high: High equity value
            confidence_score: Confidence score
            financial_metrics: Financial metrics response
            methodology_downgrade_reason: Optional methodology downgrade reason
            dcf_exclusion_reason_precheck: Optional DCF exclusion reason
            correlation_id: Correlation ID

        Returns:
            Response dictionary
        """
        # BANK-GRADE: Structured logging for response building
        self.logger.debug(
            "🔍 Building ValuationResponse",
            extra={
                "valuation_id": valuation_id,
                "equity_value_mid": equity_value_mid,
                "confidence_score": confidence_score,
            },
        )

        values = prepare_response_values(
            request=request,
            detailed_results=detailed_results,
            methodology=methodology,
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
            confidence_score=confidence_score,
            response_builder=self.response_builder,
            confidence_scorer=self.confidence_scorer,
            logger=self.logger,
        )

        response_dict = build_base_response_dict(
            request=request,
            valuation_id=valuation_id,
            values=values,
            financial_metrics=financial_metrics,
        )
        attach_consolidation_fields(
            response_dict,
            request=request,
            detailed_results=detailed_results,
        )

        substitution_payload = self._extract_methodology_substitution_payload(
            detailed_results,
            methodology_downgrade_reason,
            values.requested_methodology_raw,
        )
        if substitution_payload:
            response_dict["methodology_substitution"] = substitution_payload

        response_dict["data_sources"] = self._build_data_sources(request, detailed_results)
        attach_presentation_fields(response_dict, request)
        attach_methodology_label(
            response_dict,
            methodology=values.methodology,
            values=values,
            logger=self.logger,
        )
        log_current_year_diagnostics(response_dict, request=request, logger=self.logger)
        self.logger.debug(
            "Response basic fields prepared", extra={"fields": list(response_dict.keys())}
        )

        attach_nested_valuations(
            response_dict,
            response_builder=self.response_builder,
            detailed_results=detailed_results,
            logger=self.logger,
        )
        attach_multiples_pipeline_details(
            response_dict,
            detailed_results,
            correlation_id=correlation_id,
            logger=self.logger,
        )

        attach_summary_components(
            response_dict,
            summary_generator=self.summary_generator,
            logger=self.logger,
            request=request,
            detailed_results=detailed_results,
            methodology=values.methodology,
            methodology_downgrade_reason=methodology_downgrade_reason,
            dcf_exclusion_reason_precheck=dcf_exclusion_reason_precheck,
        )

        attach_optional_owner_fields(response_dict, detailed_results)
        attach_post_deal_swap(
            response_dict,
            detailed_results=detailed_results,
            request=request,
            methodology=values.methodology,
            logger=self.logger,
        )
        attach_multiples_prompt_payloads(response_dict, detailed_results)
        attach_quality_warnings(
            response_dict,
            detailed_results=detailed_results,
            request=request,
            substitution_payload=substitution_payload,
            logger=self.logger,
        )

        return response_dict

    @staticmethod
    def _extract_methodology_substitution_payload(
        detailed_results: Dict[str, object],
        methodology_downgrade_reason: Optional[str],
        requested_methodology: Optional[object] = None,
    ) -> Optional[Dict[str, object]]:
        return extract_methodology_substitution_payload(
            detailed_results,
            methodology_downgrade_reason,
            requested_methodology,
        )

    @staticmethod
    def _ensure_method_substitution_warning(
        warnings: List[Dict[str, object]],
        substitution_payload: Optional[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        return ensure_method_substitution_warning(warnings, substitution_payload)

    @staticmethod
    def _canonicalize_dcf_only_bridge(
        raw_dcf_result: Dict[str, object],
        net_debt: Decimal,
    ) -> Optional[Dict[str, object]]:
        return canonicalize_dcf_only_bridge(raw_dcf_result, net_debt)

    @staticmethod
    def _is_requested_dcf_only(methodology: object) -> bool:
        return is_requested_dcf_only(methodology)

    @staticmethod
    def _requested_method_signal(request: object) -> object:
        return requested_method_signal(request)

    @staticmethod
    def _decimal_from_dict(data: Dict[str, object], key: str) -> Optional[Decimal]:
        return decimal_from_dict(data, key)

    @staticmethod
    def _aggregate_quality_warnings(detailed_results: Dict[str, object]) -> List[Dict[str, object]]:
        return aggregate_quality_warnings(detailed_results)

    def _build_data_sources(
        self, request: ValuationRequest, detailed_results: Dict[str, object]
    ) -> Dict[str, object]:
        return build_response_data_sources(request, detailed_results, logger=self.logger)
