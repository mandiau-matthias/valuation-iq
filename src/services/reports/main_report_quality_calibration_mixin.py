"""Quality, owner-section, EBITDA, and calibration facades for main reports."""


from __future__ import annotations

from decimal import Decimal
from typing import Optional, TypeAlias

from src.services.infrastructure.translations import (
    ReportTranslations,
    get_translations,
    normalize_report_locale,
    resolve_ebitda_adjustment_labels,
)
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.reports.balance_sheet_adjustment_context import (
    extract_balance_sheet_adjustments as resolve_balance_sheet_adjustments,
)
from src.services.reports.balance_sheet_adjustment_context import (
    extract_tax_latencies as resolve_tax_latencies,
)
from src.services.reports.balance_sheet_adjustment_context import (
    tax_latency_rows_from_balance_sheet_adjustments as build_tax_latency_rows_from_balance_sheet_adjustments,
)
from src.services.reports.ebitda_adjustments_context import build_main_ebitda_adjustments
from src.services.reports.fiscal_ebitda_reference import fiscal_ebitda as resolve_fiscal_ebitda
from src.services.reports.fiscal_ebitda_reference import (
    fiscal_reported_ebitda as resolve_fiscal_reported_ebitda,
)
from src.services.reports.fiscal_method_selection import user_selected_fiscal_4x
from src.services.reports.fiscal_reference_context import build_fiscal_reference_report_context
from src.services.reports.fiscal_year_data import latest_closed_fiscal_year_data
from src.services.reports.multi_year_ebitda_context import build_main_multi_year_ebitda_data
from src.services.reports.preparer_override_footnote import build_preparer_ebitda_override_footnote
from src.services.reports.report_calibration_waterfall import (
    build_calibration_steps,
    build_multiple_waterfall_steps,
    build_valuation_waterfall_steps,
    compact_balance_sheet_adjustment_label,
    compact_waterfall_label,
    inject_sme_calibration_into_waterfall,
    localize_discount_waterfall_for_locale,
    localize_waterfall_row_nl,
)
from src.services.reports.report_financial_story import (
    compute_ebitda_volatility,
    detect_duplicate_consecutive_years,
    format_nwc_disclosure,
)
from src.services.reports.report_intelligence_context import build_report_intelligence_context
from src.services.reports.report_metadata_access import (
    get_accountant_logo as resolve_accountant_logo,
)
from src.services.reports.report_metadata_access import (
    get_accountant_name as resolve_accountant_name,
)
from src.services.reports.report_metadata_access import get_metadata_bool as resolve_metadata_bool
from src.services.reports.report_metadata_access import get_metadata_float as resolve_metadata_float
from src.services.reports.report_metadata_access import get_metadata_str as resolve_metadata_str
from src.services.reports.report_metadata_access import (
    get_request_metadata as resolve_request_metadata,
)
from src.services.reports.report_owner_profiling_cover import (
    build_cover_owner_profiling_cover,
    build_cover_v2_chip_context,
)
from src.services.reports.report_owner_profiling_section import (
    build_owner_profiling_section_context,
    build_post_deal_swap_context,
    build_transferability_v2_context,
)
from src.services.reports.report_quality_warnings import (
    extract_high_severity_warnings,
    extract_method_substitution_disclosure,
    format_high_severity_callout_lead,
    format_methodology_for_disclosure,
    has_integrity_warnings,
    localize_warnings,
    map_quality_level_display,
    translate_quality_warnings,
)
from src.services.reports.report_sellability_context import build_sellability_section_context
from src.services.reports.report_stage_aware_breakdown_context import (
    build_stage_aware_breakdown_context,
)
from src.services.reports.sde_methodology_context import (
    build_sde_cross_check_context,
    build_sde_methodology_context,
)
from src.utils.fiscal_year import resolve_display_current_year

ValuationResponse = ValuationResponseProtocol
ValuationRequest = ValuationRequestProtocol
JsonMap: TypeAlias = dict[str, object]
JsonRows: TypeAlias = list[JsonMap]




class MainReportQualityCalibrationMixin:
    def _assess_data_quality(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
    ) -> str:
        """
        Assess data quality level for confidence indicator.

        Returns localized labels from ``ReportTranslations`` (nl/en).
        """
        _t = self._translations_or_fallback(locale, request, t)
        score = 0

        # Core financials
        if self._get_revenue(response, request) > 0:
            score += 1

        ebitda, reported, _ = self._extract_ebitda(response, request, None)
        if ebitda > 0:
            score += 1

        latest_display = self._get_latest_year_normalized_for_display(request, reported)
        explicit_adj = self._compute_explicit_total_adjustments(
            request, response, reported, latest_display
        )
        # Normalization performed (explicit user adjustments only — not weighting-only gaps)
        if explicit_adj != Decimal("0"):
            score += 1

        # Multiple comparables available — but only credit this point when the
        # benchmark is statistically usable. An n=1 / thin / proxy benchmark still
        # populates p25/p75, so crediting it here inflated "Datadekking" to
        # "Gemiddeld" on runs the engine itself rated LOW (it emits a HIGH-severity
        # `thin_comparables_proxy` warning). Tie the coverage point to that same
        # signal so the badge can no longer contradict the engine's own verdict.
        if response.multiples_valuation and not self._has_thin_comparables_signal(response):
            mv = response.multiples_valuation
            if mv.p25_ebitda_multiple and mv.p75_ebitda_multiple:
                score += 1

        if score >= 4:
            return _t.data_quality_band_high
        if score >= 3:
            return _t.data_quality_band_medium
        return _t.exec_indicative_label

    @staticmethod
    def _has_thin_comparables_signal(response: ValuationResponse) -> bool:
        """True when the engine flagged the benchmark as thin/proxy.

        Step 2 emits a HIGH-severity ``thin_comparables_proxy`` data-quality
        warning when the resolved benchmark is statistically weak (e.g. n<=3 or a
        non-defendable proxy). The data-coverage score must not credit a
        "comparables" point in that case, otherwise the "Datadekking" badge reads
        "Gemiddeld" on a run the engine itself scored LOW.
        """
        warnings = getattr(response, "data_quality_warnings", None) or []
        for warning in warnings:
            if not isinstance(warning, dict):
                continue
            warning_type = warning.get("type")
            if isinstance(warning_type, str) and "thin_comparable" in warning_type:
                return True
        return False

    def _translate_quality_warnings(self, warnings: list[object], locale: str = "nl") -> JsonRows:
        return translate_quality_warnings(warnings, locale)

    @staticmethod
    def _localize_warnings(
        warnings: JsonRows,
        t: ReportTranslations,
    ) -> JsonRows:
        """
        Pass-9: thin wrapper around the shared
        `translations._TYPED_WARNING_TO_TRANSLATION_KEYS` catalog. The
        canonical localizer (`localize_data_quality_warnings`) is now
        applied earlier — at response-builder time — so the raw
        `data_quality_warnings` payload reaching Venus is already in the
        correct locale. This method stays for callers that already hold a
        `ReportTranslations` instance (no need to re-resolve from a locale
        string), but the mapping is unified.
        """
        return localize_warnings(warnings, t)

    @staticmethod
    def _build_cover_owner_profiling_cover(
        response: Optional[ValuationResponse],
        t: ReportTranslations,
        step_data: JsonMap,
    ) -> JsonMap:
        return build_cover_owner_profiling_cover(response, t, step_data)

    @staticmethod
    def _build_cover_v2_chip_context(odr: object, t: object) -> Optional[JsonMap]:
        return build_cover_v2_chip_context(odr, t)

    @staticmethod
    def _build_sellability_section_context(
        response: Optional["ValuationResponse"],  # type: ignore[name-defined]
        t: "ReportTranslations",  # type: ignore[name-defined]
        *,
        is_owner_dep_methodology: bool = True,
        request: Optional[object] = None,
    ) -> JsonMap:
        return build_sellability_section_context(
            response,
            t,
            is_owner_dep_methodology=is_owner_dep_methodology,
            request=request,
        )

    @staticmethod
    def _build_stage_aware_breakdown_section_context(
        response: Optional["ValuationResponse"],  # type: ignore[name-defined]
        t: "ReportTranslations",  # type: ignore[name-defined]
    ) -> JsonMap:
        # BET-463 — transparent calculation breakdown. Reads the
        # `stage_aware_breakdown` payload Titan attaches; returns a
        # suppressed no-op when the payload is absent so legacy reports
        # render byte-identically.
        return build_stage_aware_breakdown_context(response, t)

    @staticmethod
    def _build_owner_profiling_section_context(
        response: Optional[ValuationResponse],
        t: ReportTranslations,
        *,
        is_owner_dep_methodology: bool = True,
    ) -> JsonMap:
        return build_owner_profiling_section_context(
            response,
            t,
            is_owner_dep_methodology=is_owner_dep_methodology,
            build_post_deal_swap_context=build_post_deal_swap_context,
            build_transferability_v2_context=build_transferability_v2_context,
        )

    @staticmethod
    def _build_transferability_v2_context(
        odr: object,
        t: object,
    ) -> Optional[JsonMap]:
        return build_transferability_v2_context(odr, t)

    @staticmethod
    def _build_post_deal_swap_context(
        response: Optional[ValuationResponse],
    ) -> Optional[JsonMap]:
        return build_post_deal_swap_context(response)

    @staticmethod
    def _format_nwc_disclosure(
        response: Optional[ValuationResponse],
        t: ReportTranslations,
    ) -> str:
        return format_nwc_disclosure(response, t)

    @staticmethod
    def _format_high_severity_callout_lead(
        t: ReportTranslations,
        warnings: JsonRows,
    ) -> str:
        return format_high_severity_callout_lead(t, warnings)

    @staticmethod
    def _has_integrity_warnings(warnings: JsonRows) -> bool:
        return has_integrity_warnings(warnings)

    @staticmethod
    def _format_methodology_for_disclosure(methodology: object, locale: str) -> str:
        return format_methodology_for_disclosure(methodology, locale)

    @classmethod
    def _extract_method_substitution_disclosure(
        cls,
        response: Optional["ValuationResponse"],
        high_severity_warnings: JsonRows,
        locale: str,
    ) -> Optional[JsonMap]:
        return extract_method_substitution_disclosure(response, high_severity_warnings, locale)

    @staticmethod
    def _extract_high_severity_warnings(
        response: Optional[ValuationResponse],
        step_data: Optional[JsonMap],
        extra_warnings: Optional[JsonRows] = None,
    ) -> JsonRows:
        return extract_high_severity_warnings(response, step_data, extra_warnings)

    def _map_quality_level_display(
        self,
        raw: Optional[str],
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> str:
        """
        Map step's raw quality_level (HIGH/MEDIUM/LOW/CRITICAL) to locale-aware display.
        If already in display form (Hoog, High, etc.), return as-is.
        """
        _t = self._translations_or_fallback(locale, request, t)
        return map_quality_level_display(raw, _t)

    def _get_data_inputs(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        t: ReportTranslations,
        *,
        include_comparable_transactions: bool = True,
    ) -> list[str]:
        """Get list of data inputs that were available (localized labels)."""
        inputs = []

        if self._get_revenue(response, request) > 0:
            inputs.append(t.exec_revenue_label)

        ebitda, reported, _ = self._extract_ebitda(response, request, None)
        if ebitda > 0:
            inputs.append(t.dcf_row_ebitda)

        latest_display = self._get_latest_year_normalized_for_display(request, reported)
        explicit_adj = self._compute_explicit_total_adjustments(
            request, response, reported, latest_display
        )
        if explicit_adj != Decimal("0"):
            inputs.append(t.data_inputs_normalizations_label)

        if response.multiples_valuation and include_comparable_transactions:
            inputs.append(t.data_inputs_comparable_transactions_label)

        return inputs

    # EBITDA ADJUSTMENTS BUILDER

    def _build_adjustments(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        reported_ebitda: Decimal,
        normalized_ebitda: Decimal,
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
    ) -> JsonRows:
        """Build EBITDA adjustments list for template."""
        _t = self._translations_or_fallback(locale, request, t)
        _adj = resolve_ebitda_adjustment_labels(locale, _t)
        current_year = self._resolve_display_current_year(request)
        country_code = self._country_code_from_request(request)
        normalization = self._get_normalization_result(response)
        current_year_meta = self._get_current_year_normalization_metadata(request)
        return build_main_ebitda_adjustments(
            request=request,
            reported_ebitda=reported_ebitda,
            normalized_ebitda=normalized_ebitda,
            locale=locale,
            labels=_adj,
            current_year=current_year,
            country_code=country_code,
            normalization=normalization,
            current_year_metadata=current_year_meta,
            logger=self.logger,
        )

    # MULTI-YEAR EBITDA BUILDER

    def _build_multi_year_data(
        self,
        request: Optional[ValuationRequest],
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
    ) -> JsonRows:
        """Build multi-year EBITDA data from request."""
        if not request:
            return []

        _report_loc = normalize_report_locale(locale)
        _report_cc = self._country_code_from_request(request)
        _t = t or get_translations(_report_loc, country_code=_report_cc)
        current_year = self._resolve_display_current_year(request)
        current_year_meta = self._get_current_year_normalization_metadata(request)
        return build_main_multi_year_ebitda_data(
            request=request,
            locale=locale,
            translations=_t,
            current_year=current_year,
            country_code=_report_cc,
            current_year_metadata=current_year_meta,
            request_metadata=self._get_request_metadata(request) or {},
        )

    @staticmethod
    def _compute_ebitda_volatility(
        multi_year: JsonRows,
        t: ReportTranslations,
    ) -> Optional[JsonMap]:
        return compute_ebitda_volatility(multi_year, t)

    @staticmethod
    def _detect_duplicate_years(multi_year: JsonRows) -> Optional[JsonMap]:
        return detect_duplicate_consecutive_years(multi_year)

    # CALIBRATION STEPS BUILDER

    def _localize_discount_waterfall_for_locale(
        self,
        waterfall: JsonRows,
        locale: str,
        t: ReportTranslations,
    ) -> JsonRows:
        return localize_discount_waterfall_for_locale(waterfall, locale, t)

    def _localize_waterfall_row_nl(
        self,
        label: str,
        description: str,
        _t: ReportTranslations,
    ) -> tuple[str, str]:
        return localize_waterfall_row_nl(label, description, _t)

    def _inject_sme_calibration_into_waterfall(
        self,
        waterfall: JsonRows,
        step_data: Optional[JsonMap],
        metric_value: float,
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> JsonRows:
        """
        Prepend an explicit SME calibration step to a discount_waterfall that
        starts from the post-calibration baseline.  When calibration was applied
        in Step 2 the raw database multiple (pre-calibration) becomes the true
        baseline, and the calibration reduction is shown as a distinct step.
        """
        _t = self._translations_or_fallback(locale, request, t)
        return inject_sme_calibration_into_waterfall(waterfall, step_data, metric_value, _t)

    def _build_calibration_steps(
        self,
        metric_value: Decimal,
        metric_type: str,
        base_multiple: Decimal,
        final_multiple: Decimal,
        response: ValuationResponse,
        step_data: Optional[JsonMap] = None,
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> JsonRows:
        """
        Fallback calibration steps builder when discount_waterfall from Step 11
        pipeline is unavailable. Converts percentage adjustments from Steps 4-6
        into multiplicative multiple impacts (Hitchner 2017).

        When SME calibration was applied in Step 2, the waterfall starts from
        the raw database multiple and explicitly shows the calibration reduction
        before applying discount steps (Koller, Goedhart & Wessels 2020).

        For break-even or zero-revenue businesses, returns a minimal step
        instead of empty to avoid blank "Volledige Berekening" section.
        """
        _t = self._translations_or_fallback(locale, request, t)
        return build_calibration_steps(
            metric_value=metric_value,
            metric_type=metric_type,
            base_multiple=base_multiple,
            final_multiple=final_multiple,
            response=response,
            step_data=step_data,
            t=_t,
        )
