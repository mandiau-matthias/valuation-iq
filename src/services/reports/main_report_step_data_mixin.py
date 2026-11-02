"""12-step calculation extraction for the main report aggregator."""

from typing import Dict, Optional

from src.services.infrastructure.translations import ReportTranslations
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.reports.report_balance_data_context import (
    get_detailed_step_result_result,
    step7_extraction_diagnostics,
)
from src.services.reports.step_data_context import (
    apply_ebitda_pipeline_fallback_waterfall,
    apply_step7_detailed_result,
    apply_step_specific_data,
    calculation_steps_from_transparency,
    hydrate_discount_context_from_detailed_results,
)
from src.services.reports.step_data_context import (
    extract_pipeline_from_detailed_results as resolve_pipeline_from_detailed_results,
)
from src.services.reports.step_data_context import (
    fill_balance_sheet_step_data_from_current_year as apply_current_year_balance_sheet_step_data,
)
from src.services.reports.step_data_context import (
    hydrate_pipeline_from_top_level_response as apply_top_level_pipeline_step_data,
)
from src.services.reports.step_data_context import (
    initial_step_data,
    multiples_steps_from_raw_steps,
    record_calculation_step,
)

ValuationResponse = ValuationResponseProtocol
ValuationRequest = ValuationRequestProtocol


class MainReportStepDataMixin:
    """Extract and hydrate report step data without owning full report assembly."""

    def _extract_step_data(
        self,
        response: ValuationResponse,
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> Dict[str, object]:
        _t = self._translations_or_fallback(locale, request, t)
        step_data = initial_step_data()

        transparency = getattr(response, "transparency", None)
        if not transparency:
            self.logger.debug("No transparency data available for step extraction")
            self._hydrate_step_data_from_reduced_response(response, step_data)
            return step_data

        step_data["has_transparency"] = True
        steps_raw = calculation_steps_from_transparency(transparency)

        if not steps_raw:
            self.logger.debug(
                "No calculation_steps in transparency data; hydrating from "
                "detailed_results.step_results"
            )
            self._hydrate_step_data_from_reduced_response(response, step_data)
            return step_data

        try:
            multiples_steps = multiples_steps_from_raw_steps(steps_raw)

            if isinstance(multiples_steps, list) and multiples_steps:
                step_data["step_count"] = len(multiples_steps)
                for i, step in enumerate(multiples_steps):
                    step_num = record_calculation_step(
                        step_data,
                        step,
                        i,
                        calc_step_names=_t.calc_step_names,
                        calc_step_generic=_t.calc_step_generic,
                    )
                    if step_num is None:
                        continue
                    self._extract_step_specific_data(step_num, step, step_data, locale)

            # DEBUG: plumbing acknowledgement. The actual rendered step
            # provenance shows on the report itself; counter is dev-facing.
            self.logger.debug(
                f"✅ Extracted {step_data['step_count']} calculation steps "
                f"({step_data['completed_count']} completed)",
                extra={
                    "has_step_0": 0 in step_data["steps"],
                    "has_step_11": 11 in step_data["steps"],
                    "data_quality_score": step_data["data_quality_score"],
                },
            )
        except Exception as e:
            self.logger.error(f"Error extracting step data: {e}", exc_info=True)

        self._apply_detailed_results_pipeline_fallback(response, step_data)
        self._apply_step7_bridge_or_balance_sheet_fallback(response, step_data)

        return step_data

    def _hydrate_step_data_from_reduced_response(
        self,
        response: ValuationResponse,
        step_data: Dict[str, object],
    ) -> None:
        self._hydrate_pipeline_from_top_level_response(response, step_data)
        self._fill_balance_sheet_step_data_from_current_year(response, step_data)
        # The comprehensive engine path frequently ships an EMPTY
        # ``transparency.calculation_steps`` and serialises its authoritative
        # step trail into ``detailed_results.step_results`` instead. Pull the
        # size/liquidity discount AND the Step-7 net-debt / total-debt / cash
        # from there so the multiples EV→equity bridge renders the engine's
        # REAL components. Without this, ``size_discount_percentage`` stays 0 —
        # which makes the EV-formula aligner inflate the reported EV to the
        # GROSS ``metric × market multiple`` and then back-derive a phantom
        # net-debt from the EV/Equity gap (wrong magnitude, sometimes wrong
        # sign, with no debt/cash breakdown and a "confirm before external use"
        # warning). Asset/yield paths are unaffected: their EV is balance-sheet
        # anchored and the formula aligner is policy-disabled for them.
        hydrate_discount_context_from_detailed_results(response, step_data)
        self._apply_step7_bridge_or_balance_sheet_fallback(response, step_data)

    def _apply_detailed_results_pipeline_fallback(
        self,
        response: ValuationResponse,
        step_data: Dict[str, object],
    ) -> None:
        current_pipeline = step_data.get("multiple_pipeline")
        has_canonical_pipeline = bool(
            isinstance(current_pipeline, dict) and current_pipeline.get("discount_waterfall")
        )
        if has_canonical_pipeline:
            return

        pipeline_from_dr = self._extract_pipeline_from_detailed_results(response, step_data)
        if not pipeline_from_dr:
            return
        step_data["multiple_pipeline"] = pipeline_from_dr
        if isinstance(pipeline_from_dr, dict):
            apply_ebitda_pipeline_fallback_waterfall(pipeline_from_dr, step_data)

    def _apply_step7_bridge_or_balance_sheet_fallback(
        self,
        response: ValuationResponse,
        step_data: Dict[str, object],
    ) -> None:
        step_7_result = get_detailed_step_result_result(response, 7)
        if step_7_result:
            apply_step7_detailed_result(step_7_result, step_data)
            return

        self.logger.warning(
            "Step 7 result not found via _get_detailed_step_result_result; "
            "net_debt/total_debt/cash may be missing (defensive derivation will fill the gap)",
            extra=step7_extraction_diagnostics(response),
        )
        self._fill_balance_sheet_step_data_from_current_year(response, step_data)

    def _hydrate_pipeline_from_top_level_response(
        self,
        response: ValuationResponse,
        step_data: Dict[str, object],
    ) -> None:
        apply_top_level_pipeline_step_data(response, step_data)

    def _fill_balance_sheet_step_data_from_current_year(
        self,
        response: ValuationResponse,
        step_data: Dict[str, object],
    ) -> None:
        apply_current_year_balance_sheet_step_data(response, step_data)

    def _extract_pipeline_from_detailed_results(
        self,
        response: ValuationResponse,
        step_data: Optional[Dict[str, object]] = None,
    ) -> Optional[Dict[str, object]]:
        pipeline = resolve_pipeline_from_detailed_results(response, step_data)
        if pipeline:
            # DEBUG: pipeline-recovery breadcrumb (fires on every aggregation).
            self.logger.debug(
                "🔍 [AGGREGATOR] Pipeline recovered from detailed_results",
                extra={
                    "initial_multiple_mid": str(pipeline.get("initial_multiple_mid")),
                    "final_multiple_mid": str(
                        pipeline.get("final_multiple_mid")
                        if pipeline.get("final_multiple_mid") is not None
                        else pipeline.get("final_multiple")
                    ),
                    "metric_type": pipeline.get("metric_type"),
                },
            )
            return pipeline

        return None

    def _extract_step_specific_data(
        self,
        step_number: int,
        step: Dict[str, object],
        step_data: Dict[str, object],
        locale: str = "nl",
    ) -> None:
        t = self._translations_or_fallback(locale, None, None)
        apply_step_specific_data(
            step_number,
            step,
            step_data,
            unknown_stage_label=t.report_unknown_stage_label,
        )
