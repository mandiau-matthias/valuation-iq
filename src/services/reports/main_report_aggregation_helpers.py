"""Compatibility helpers for ``MainReportDataAggregator``.

These methods remain private API on the aggregator for older tests and callers,
but their implementation lives here so the main aggregator module stays focused
on building the report context.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from src.services.infrastructure.translations import ReportTranslations
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.reports.ebitda_extraction_context import extract_ebitda_values
from src.services.reports.ebitda_normalization import (
    compute_explicit_total_adjustments as resolve_explicit_total_adjustments,
)
from src.services.reports.ebitda_normalization import current_year_normalization_metadata
from src.services.reports.ebitda_normalization import (
    current_year_is_ebitda_normalized as resolve_current_year_is_ebitda_normalized,
)
from src.services.reports.ebitda_normalization import (
    derive_normalized_ebitda as resolve_normalized_ebitda,
)
from src.services.reports.ebitda_normalization import (
    summarize_proposed_adjustments as resolve_proposed_adjustments,
)
from src.services.reports.ebitda_normalization import (
    has_explicit_normalization_metadata as has_explicit_ebitda_normalization_metadata,
)
from src.services.reports.ebitda_normalization import (
    latest_year_normalized_for_display as resolve_latest_year_normalized_for_display,
)
from src.services.reports.ebitda_normalization import normalization_result_from_response
from src.services.reports.ebitda_normalization import (
    sum_signed_adjustments as sum_signed_ebitda_adjustments,
)
from src.services.reports.enterprise_value_context import deterministic_ev_range
from src.services.reports.enterprise_value_context import (
    extract_enterprise_value_range as resolve_enterprise_value_range,
)
from src.services.reports.method_page_context import promote_upswitch_adaptive_context
from src.services.reports.multiple_extraction_context import (
    base_multiple_value,
    build_multiple_report_context,
    extract_multiple_values,
)
from src.services.reports.official_financials_context import build_official_financials_context
from src.services.reports.official_variance_context import (
    build_official_variance_comparison_rows as build_official_variance_rows,
)
from src.services.reports.protocol_adapter import DictWrapper, _attr
from src.services.reports.report_balance_data_context import (
    get_detailed_step_result_result,
    has_balance_data,
    is_meaningful_balance_value,
    request_has_balance_inputs,
    step7_extraction_diagnostics,
    step_results_have_balance_inputs,
)
from src.services.reports.report_company_metrics_context import (
    get_employee_count as resolve_employee_count,
)
from src.services.reports.report_company_metrics_context import get_industry as resolve_industry
from src.services.reports.report_company_metrics_context import get_revenue as resolve_revenue
from src.services.reports.report_completeness_score import calculate_report_completeness_score
from src.services.reports.weighted_synthesis_context import (
    build_weighted_synthesis_presentation,
    format_eur_compact,
    format_synthesis_method_list,
    synthesis_value_bounds_from_contributions,
    unwrap_weighted_synthesis,
)

ValuationResponse = ValuationResponseProtocol
ValuationRequest = ValuationRequestProtocol


class MainReportAggregationHelpersMixin:
    def _get_official_financials_data(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest] = None,
    ) -> Dict[str, object]:
        """Compatibility facade for the modular official-filing context builder."""
        return build_official_financials_context(response, request)

    def _build_official_variance_comparison_rows(
        self,
        official_financials: Dict[str, object],
        user_revenue: Optional[float],
        user_ebitda: Optional[float],
        translations: object,
    ) -> list[dict[str, object]]:
        """Compatibility facade for the modular official-variance row builder."""
        return build_official_variance_rows(
            official_financials,
            user_revenue,
            user_ebitda,
            translations,
        )

    def _validate_context(
        self,
        context: Dict[str, object],
        t: Optional[ReportTranslations] = None,
    ) -> Tuple[List[str], List[str]]:
        from src.services.infrastructure.report_sections.validation import validate_report_context

        return validate_report_context(context, t=t)

    def _promote_upswitch_adaptive_from_valuation_results(
        self,
        response: ValuationResponse,
        context: Dict[str, object],
        locale: Optional[str] = None,
    ) -> None:
        promote_upswitch_adaptive_context(
            context,
            valuation_results=getattr(response, "valuation_results", None) or {},
            dcf_weight=_attr(response, "dcf_weight", None),
            multiples_weight=_attr(response, "multiples_weight", None),
            locale=locale,
        )

    @staticmethod
    def _unwrap_synthesis(weighted_valuation: object) -> Optional[Dict[str, object]]:
        return unwrap_weighted_synthesis(weighted_valuation)

    @staticmethod
    def _synthesis_value_bounds_from_contributions(
        contributions: List[Dict[str, object]],
        blended_value: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        return synthesis_value_bounds_from_contributions(contributions, blended_value)

    @staticmethod
    def _format_eur_compact(value: object) -> str:
        return format_eur_compact(value)

    @staticmethod
    def _format_synthesis_method_list(labels: List[str], locale: str) -> str:
        return format_synthesis_method_list(labels, locale)

    def _build_weighted_synthesis_presentation(
        self,
        *,
        contributions: List[object],
        blended_value: object,
        locale: str,
    ) -> Dict[str, object]:
        return build_weighted_synthesis_presentation(
            contributions=contributions,
            blended_value=blended_value,
            locale=locale,
        )

    def _calculate_completeness_score(self, context: Dict[str, object]) -> int:
        return calculate_report_completeness_score(context)

    def _extract_ebitda(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        step_data: Optional[Dict[str, object]] = None,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        return extract_ebitda_values(
            response=response,
            request=request,
            step_data=step_data,
            normalization=self._get_normalization_result(response),
            current_year_metadata=self._get_current_year_normalization_metadata(request),
        )

    def _get_latest_year_normalized_for_display(
        self,
        request: Optional[ValuationRequest],
        reported_ebitda: Decimal,
        cached_multi: Optional[List[Dict[str, object]]] = None,
    ) -> Decimal:
        multi = (
            cached_multi
            if cached_multi is not None
            else self._build_multi_year_data(request, locale="nl")
        )
        return resolve_latest_year_normalized_for_display(
            request=request,
            reported_ebitda=reported_ebitda,
            multi_year_data=multi,
            normalized_key="normalized_ebitda",
        )

    def _compute_explicit_total_adjustments(
        self,
        request: Optional[ValuationRequest],
        response: ValuationResponse,
        reported_ebitda: Decimal,
        latest_year_normalized: Decimal,
    ) -> Decimal:
        return resolve_explicit_total_adjustments(
            request=request,
            normalization=self._get_normalization_result(response),
            reported_ebitda=reported_ebitda,
            latest_year_normalized=latest_year_normalized,
        )

    def _should_show_ebitda_weighting_footnote(
        self,
        sustainable_ebitda: Decimal,
        latest_year_normalized: Decimal,
        explicit_total_adjustments: Decimal,
        cached_multi: Optional[List[Dict[str, object]]] = None,
    ) -> bool:
        if not cached_multi or len(cached_multi) < 2:
            return False
        return abs(sustainable_ebitda - latest_year_normalized) > Decimal("0.01")

    @staticmethod
    def _multi_year_basis_has_normalizations(
        cached_multi: Optional[List[Dict[str, object]]] = None,
    ) -> bool:
        """True when the weighted multi-year basis embeds per-year normalizations.

        The owner-comp pending note's default body claims that "reported EBITDA
        is used as the valuation basis without normalisation" — accurate only
        when the base year has €0 adjustments AND no other weighted year carries
        an applied normalization. When a prior year carries a real add-back that
        flows into the weighted basis (e.g. a +€117,600 owner add-back two years
        back), that claim contradicts the report's own multi-year table. This
        flag lets the normalization page swap in an honest body for that case.
        """
        if not cached_multi:
            return False
        for row in cached_multi:
            if not isinstance(row, dict):
                continue
            try:
                weight = float(row.get("weight") or 0)
                adjustment_total = float(row.get("adjustment_total") or 0)
            except (TypeError, ValueError):
                continue
            if weight > 0 and bool(row.get("has_adjustments")) and adjustment_total != 0:
                return True
        return False

    def _should_show_owner_comp_pending_note(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        total_adjustments: Decimal,
    ) -> bool:
        if total_adjustments != Decimal("0"):
            return False

        owners = self._extract_int_attr(
            request,
            ("number_of_owners", "owner_managers", "owners_count"),
            default=1,
        )
        employees = self._extract_int_attr(
            request,
            ("number_of_employees", "employee_count", "employees", "fte_count", "total_employees"),
            default=None,
        )
        if employees is None:
            employees = self._get_employee_count(response, request)

        if owners is None or owners < 1:
            return False
        if employees is None:
            revenue = self._get_revenue(response, request)
            if revenue and revenue >= Decimal("2000000"):
                return False
            return True
        return employees <= 10

    def _summarize_proposed_adjustments(
        self,
        request: Optional[ValuationRequest],
        response: ValuationResponse,
    ) -> Tuple[Decimal, int]:
        """Return ``(signed_total, count)`` of NON-applied normalization candidates.

        Mirrors the source selection used by ``build_main_ebitda_adjustments``
        (prefer explicit request metadata, else the response normalization
        payload) so the "candidates detected but not applied — advisor review
        required" note reflects exactly what was filtered out of the bridge.
        """
        normalization = self._get_normalization_result(response)
        current_year_meta = self._get_current_year_normalization_metadata(request)
        normalized_flag = resolve_current_year_is_ebitda_normalized(request)
        metadata_adjustments = (
            current_year_meta.get("adjustments")
            if isinstance(current_year_meta, dict)
            else None
        )
        if has_explicit_ebitda_normalization_metadata(
            current_year_meta, normalized_flag
        ) and isinstance(metadata_adjustments, list):
            return resolve_proposed_adjustments(metadata_adjustments)
        response_adjustments = (
            normalization.get("adjustments") if isinstance(normalization, dict) else None
        )
        return resolve_proposed_adjustments(response_adjustments)

    @staticmethod
    def _extract_int_attr(
        request: Optional[ValuationRequest],
        attr_names: Tuple[str, ...],
        default: Optional[int] = None,
    ) -> Optional[int]:
        if request is None:
            return default
        for name in attr_names:
            if hasattr(request, name):
                val = getattr(request, name)
                if val is None:
                    continue
                try:
                    return int(val)
                except (TypeError, ValueError):
                    continue
        return default

    def _get_normalization_result(self, response: ValuationResponse) -> Dict[str, object]:
        return normalization_result_from_response(response)

    def _get_current_year_normalization_metadata(
        self,
        request: Optional[ValuationRequest],
    ) -> Dict[str, object]:
        return current_year_normalization_metadata(request)

    def _sum_signed_adjustments(self, adjustments: object) -> Decimal:
        return sum_signed_ebitda_adjustments(adjustments)

    def _has_explicit_normalization_metadata(
        self,
        normalization_meta: Optional[Dict[str, object]],
        normalized_flag: bool = False,
    ) -> bool:
        return has_explicit_ebitda_normalization_metadata(
            normalization_meta,
            normalized_flag,
        )

    def _derive_normalized_ebitda(
        self,
        reported_ebitda: Decimal,
        normalization_meta: Optional[Dict[str, object]],
        normalized_flag: bool = False,
    ) -> Optional[Decimal]:
        return resolve_normalized_ebitda(
            reported_ebitda,
            normalization_meta,
            normalized_flag,
        )

    def _is_generic_sector_label(self, sector_label: object) -> bool:
        if not sector_label or not isinstance(sector_label, str):
            return False

        normalized = sector_label.replace("_", " ").replace("-", " ").strip().lower()
        return normalized in {
            "other",
            "service",
            "services",
            "retail",
            "retail service",
            "retail services",
            "general service",
            "general services",
        }

    def _extract_multiple(
        self,
        response: ValuationResponse,
        benchmark_ev_ebitda: Optional[Decimal] = None,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        fallback_ebitda, _, _ = self._extract_ebitda(response, None)
        return extract_multiple_values(
            response=response,
            benchmark_ev_ebitda=benchmark_ev_ebitda,
            fallback_ebitda=fallback_ebitda,
        )

    def _extract_multiple_context(
        self,
        response: ValuationResponse,
        step_data: Dict[str, object],
        industry_benchmarks: Dict[str, object],
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> Dict[str, object]:
        fallback_ebitda, _, _ = self._extract_ebitda(response, None)
        return build_multiple_report_context(
            response=response,
            step_data=step_data,
            industry_benchmarks=industry_benchmarks,
            t=self._translations_or_fallback(locale, request, t),
            is_hybrid=self._is_hybrid_methodology(response),
            fallback_ebitda=fallback_ebitda,
        )

    def _extract_enterprise_value_range(
        self,
        response: ValuationResponse,
        step_data: Dict[str, object],
        equity_value_low: Decimal,
        equity_value_mid: Decimal,
        equity_value_high: Decimal,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        return resolve_enterprise_value_range(
            response=response,
            step_data=step_data,
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
            is_hybrid=self._is_hybrid_methodology(response),
            is_dcf_only=self._is_dcf_only_methodology(response),
            is_asset_anchored=self._is_asset_anchored_methodology(response),
            logger=self.logger,
        )

    def _calculate_deterministic_ev_range(
        self, ev_mid: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal]:
        return deterministic_ev_range(ev_mid)

    def _get_base_multiple(
        self,
        response: ValuationResponse,
        benchmark_ev_ebitda: Optional[Decimal] = None,
    ) -> Decimal:
        applied, _, _ = self._extract_multiple(response, benchmark_ev_ebitda)
        return base_multiple_value(response=response, applied_multiple=applied)

    def _get_industry(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> Optional[str]:
        return resolve_industry(response, request)

    def _get_revenue(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> Decimal:
        return resolve_revenue(response, request)

    def _has_balance_data(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> bool:
        return has_balance_data(
            response,
            request,
            metadata_bool_resolver=self._get_metadata_bool,
        )

    @staticmethod
    def _is_meaningful_balance_value(value: object) -> bool:
        return is_meaningful_balance_value(value)

    def _request_has_balance_inputs(self, request: Optional[ValuationRequest]) -> bool:
        return request_has_balance_inputs(request)

    def _step_results_have_balance_inputs(self, response: ValuationResponse) -> bool:
        return step_results_have_balance_inputs(response)

    def _step7_extraction_diagnostics(self, response: ValuationResponse) -> Dict[str, object]:
        return step7_extraction_diagnostics(response)

    def _get_detailed_step_result_result(
        self, response: ValuationResponse, step_number: int
    ) -> Optional[Dict[str, object]]:
        result = get_detailed_step_result_result(response, step_number)
        if isinstance(result, DictWrapper):
            return result._data
        return result

    def _get_employee_count(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> Optional[int]:
        return resolve_employee_count(response, request)
