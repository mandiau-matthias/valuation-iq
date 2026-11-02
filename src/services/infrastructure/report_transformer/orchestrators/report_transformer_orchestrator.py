"""Report transformer facade for accountant-view template data."""

from __future__ import annotations

import time

from src.services.infrastructure.transformers import (
    AppendicesTransformer,
    CompanyOverviewTransformer,
    DescriptionTransformer,
    ExecutiveSummaryTransformer,
    FinancialAnalysisTransformer,
    InformationSourcesTransformer,
    ValuationConclusionTransformer,
    ValuationMethodologyTransformer,
)
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)

from ..builders import AdjustmentsBuilder, BasicDataBuilder
from ..converters import MultiplesConverter, PipelineConverter
from ..validators import StepOutputValidator
from .accountant_view_transform import (
    build_base_template_data,
    build_translation_context,
    ensure_required_sections,
    log_transform_complete,
    log_transform_start,
    populate_calculation_steps,
    populate_valuation_waterfall,
    transform_report_sections,
    validate_transform_inputs,
)


class ReportTransformerOrchestrator:
    """
    Orchestrates valuation data transformation for report generation.

    The transformation rules live in dedicated accountant-view helpers; this
    class keeps the legacy public API stable while remaining a small facade.
    """

    def __init__(self) -> None:
        self.step_validator = StepOutputValidator()
        self.pipeline_converter = PipelineConverter()
        self.multiples_converter = MultiplesConverter()
        self.basic_builder = BasicDataBuilder()
        self.adjustments_builder = AdjustmentsBuilder()

        self.transformers = {
            "description": DescriptionTransformer(),
            "information_sources": InformationSourcesTransformer(),
            "executive_summary": ExecutiveSummaryTransformer(),
            "company_overview": CompanyOverviewTransformer(),
            "financial_analysis": FinancialAnalysisTransformer(),
            "valuation_methodology": ValuationMethodologyTransformer(),
            "valuation_conclusion": ValuationConclusionTransformer(),
            "appendices": AppendicesTransformer(),
        }

    def transform_valuation_response(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
    ) -> dict[str, object]:
        """Transform a valuation response into accountant-view template data."""
        start_time = time.time()
        validate_transform_inputs(response, request)
        log_transform_start(response)

        translation_context = build_translation_context(request)
        transformed_sections = transform_report_sections(
            transformers=self.transformers,
            response=response,
            request=request,
            translation_context=translation_context,
        )
        template_data = build_base_template_data(
            response=response,
            request=request,
            transformed_sections=transformed_sections,
            basic_builder=self.basic_builder,
            translation_context=translation_context,
        )
        populate_calculation_steps(template_data, response, request)
        populate_valuation_waterfall(template_data, response, request)
        missing_sections = ensure_required_sections(
            template_data,
            getattr(response, "company_name", None),
        )

        log_transform_complete(
            response=response,
            duration_seconds=time.time() - start_time,
            transformed_sections=transformed_sections,
            template_data=template_data,
            missing_sections=missing_sections,
        )

        return template_data
