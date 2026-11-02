"""Report-section wrapper mixin for ``MainReportDataAggregator``.

These methods preserve the aggregator's private API while keeping the main
aggregation orchestrator small enough to reason about. They mostly delegate to
focused report context builders under ``src.services.reports``.
"""

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
from src.services.reports.main_report_quality_calibration_mixin import (
    MainReportQualityCalibrationMixin,
)
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


def _methodology_multiple_metric_label(
    translations: ReportTranslations,
    metric_type: str,
) -> str:
    if metric_type == "REVENUE":
        return translations.report_multiple_suffix_ev_revenue
    return translations.report_multiple_suffix_ev_ebitda


def _primary_methodology_narrative(
    response: ValuationResponse,
    *,
    translations: ReportTranslations,
    multiples_metric_label: str,
    is_yield: bool,
    is_asset: bool,
) -> str | None:
    if is_yield:
        return translations.methodology_narrative_yield
    if is_asset:
        return translations.methodology_narrative_asset
    if response.multiples_valuation:
        return translations.methodology_narrative_multiples.format(metric=multiples_metric_label)
    return None


def _dcf_methodology_narrative(
    response: ValuationResponse,
    *,
    translations: ReportTranslations,
    has_true_dcf: bool,
    is_hybrid: bool,
) -> str | None:
    if not (has_true_dcf and response.dcf_valuation):
        return None
    if not response.multiples_valuation:
        return translations.methodology_narrative_dcf_primary
    if is_hybrid:
        return translations.methodology_narrative_dcf_weighted
    return translations.methodology_narrative_dcf_addon


def _has_normalization_details(response: ValuationResponse) -> bool:
    detailed_results = getattr(response, "detailed_results", None)
    return bool(
        detailed_results
        and hasattr(detailed_results, "get")
        and callable(detailed_results.get)
        and detailed_results.get("normalization")
    )


def _include_owner_dependency_narrative(
    response: ValuationResponse,
    *,
    is_asset: bool,
    is_yield: bool,
) -> bool:
    return bool(getattr(response, "owner_dependency_result", None) and not (is_asset or is_yield))


class MainReportSectionMixin(MainReportQualityCalibrationMixin):
    def _get_methodology_statement(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        metric_type: str = "EBITDA",
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
    ) -> Optional[str]:
        """
        Generate methodology statement based on valuation approach used.
        Copy is centralized in ``ReportTranslations`` (nl/en).
        """
        _t = self._translations_or_fallback(locale, request, t)
        methodology_parts: list[str] = []
        multiples_metric_label = _methodology_multiple_metric_label(_t, metric_type)

        is_yield = self._is_yield_methodology(response)
        is_asset = self._is_asset_methodology(response)
        is_hybrid = self._is_hybrid_methodology(response)
        has_true_dcf = self._is_dcf_only_methodology(response) or is_hybrid

        primary_narrative = _primary_methodology_narrative(
            response,
            translations=_t,
            multiples_metric_label=multiples_metric_label,
            is_yield=is_yield,
            is_asset=is_asset,
        )
        if primary_narrative:
            methodology_parts.append(primary_narrative)

        dcf_narrative = _dcf_methodology_narrative(
            response,
            translations=_t,
            has_true_dcf=has_true_dcf,
            is_hybrid=is_hybrid,
        )
        if dcf_narrative:
            methodology_parts.append(dcf_narrative)

        if _has_normalization_details(response):
            methodology_parts.append(_t.methodology_narrative_normalization)
        if _include_owner_dependency_narrative(
            response,
            is_asset=is_asset,
            is_yield=is_yield,
        ):
            methodology_parts.append(_t.methodology_narrative_owner_dependency)
        return (
            " ".join(methodology_parts)
            if methodology_parts
            else _t.methodology_narrative_fallback.format(metric=multiples_metric_label)
        )

    def _get_valuation_methodology(
        self,
        response: ValuationResponse,
        locale: str = "nl",
    ) -> str:
        """Get the primary valuation methodology used (English key for template comparisons).

        Order matters: asset / yield are explicit overrides keyed off the
        ``methodology`` field directly, *before* the multiples/DCF fall-through.
        Otherwise the presence of an industry-benchmark multiples block would
        force balance-sheet-driven valuations into "Market Multiples".
        """
        if self._is_yield_methodology(response):
            return "Real Estate Yield"
        if self._is_asset_methodology(response):
            return "Asset-Based"
        has_true_dcf = self._is_dcf_only_methodology(response) or self._is_hybrid_methodology(
            response
        )
        if response.multiples_valuation and response.dcf_valuation and has_true_dcf:
            return "Hybrid (Multiples + DCF)"
        elif response.dcf_valuation and has_true_dcf:
            return "DCF Analysis"
        elif response.multiples_valuation:
            return "Market Multiples"
        else:
            return "Market Multiples"

    def _get_valuation_methodology_display(
        self,
        response: ValuationResponse,
        metric_type: str = "EBITDA",
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> str:
        """Get the localized display name for the valuation methodology."""
        _t = self._translations_or_fallback(locale, request, t)
        mult_disp = (
            _t.val_method_display_multiples_revenue
            if metric_type == "REVENUE"
            else _t.val_method_display_multiples_ebitda
        )
        # Asset-anchored methodologies surface a distinct display label so
        # the cover doesn't read "EV/EBITDA" on a balance-sheet-driven
        # valuation. Same precedence rule as ``_get_valuation_methodology``.
        if self._is_yield_methodology(response):
            return _t.val_method_display_yield
        if self._is_asset_methodology(response):
            return _t.val_method_display_asset
        has_true_dcf = self._is_dcf_only_methodology(response) or self._is_hybrid_methodology(
            response
        )
        if response.multiples_valuation and response.dcf_valuation and has_true_dcf:
            return _t.val_method_display_hybrid
        if response.dcf_valuation and has_true_dcf:
            return _t.val_method_display_dcf
        if response.multiples_valuation:
            return mult_disp
        return mult_disp

    # DCF METHODOLOGY DATA EXTRACTION

    def _extract_dcf_data(
        self,
        response: ValuationResponse,
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> JsonMap:
        """Delegates to ``report_sections.dcf_section.build_dcf_context``."""
        from src.services.infrastructure.report_sections.dcf_section import build_dcf_context

        if not (self._is_dcf_only_methodology(response) or self._is_hybrid_methodology(response)):
            return {"has_dcf": False}

        _cc = self._country_code_from_request(request)
        result = build_dcf_context(response, locale=locale, t=t, country_code=_cc)
        if not result.get("has_dcf"):
            self.logger.info(
                "DCF data not present in valuation response — has_dcf=False",
                extra={
                    "has_attr": hasattr(response, "dcf_valuation"),
                    "dcf_valuation_type": type(getattr(response, "dcf_valuation", None)).__name__,
                },
            )
        return result

    def _extract_report_intelligence(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        locale: str,
        t: Optional[ReportTranslations] = None,
    ) -> JsonMap:
        return build_report_intelligence_context(
            response=response,
            request=request,
            t=self._translations_or_fallback(locale, request, t),
        )

    # SDE METHODOLOGY DATA EXTRACTION

    def _extract_sde_data(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
    ) -> JsonMap:
        """Extract SDE-specific valuation data for micro-SMEs.

        SDE (Seller's Discretionary Earnings) = EBITDA + Owner salary normalization.
        Used primarily for owner-operated micro-businesses.
        """
        t = self._translations_or_fallback(locale, request, t)
        ebitda, _, _ = self._extract_ebitda(response, request)
        return build_sde_methodology_context(
            response=response,
            request=request,
            t=t,
            ebitda=ebitda,
            normalization_result=self._get_normalization_result(response),
            logger=self.logger,
        )

    def _extract_sde_cross_check(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        sde_data: JsonMap,
        t: ReportTranslations,
    ) -> JsonMap:
        """Surface SDE × multiple as a co-equal cross-check for owner-led micro-SMEs.

        Fires when the company qualifies (≤€2M revenue OR ≤10 FTE with ≥1
        owner-manager) AND the engine actually produced an SDE calculation
        in Step 2.7. When SDE is already the primary methodology, the
        existing valuation_synthesis page handles presentation; we suppress
        the cross-check to avoid double-rendering.

        Three Towers Capital regression: Step 2.7 logged
        ``Database-driven SDE multiple: 2.20x`` but the seller-facing report
        only mentioned SDE in a footnote. For a 1-owner / 5-FTE consultancy
        SDE is the second-most-important method an M&A advisor would use,
        so surfacing it as an explicit cross-check is defensibility-critical.
        """
        if sde_data.get("is_sde_methodology"):
            return {"show_sde_cross_check": False}

        revenue = self._get_revenue(response, request)
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
        ebitda, _, _ = self._extract_ebitda(response, request)
        return build_sde_cross_check_context(
            response=response,
            sde_data=sde_data,
            revenue=revenue,
            owners=owners,
            employees=employees,
            ebitda=ebitda,
        )

    # TAX LATENCIES EXTRACTION

    def _tax_latency_rows_from_balance_sheet_adjustments(self, raw_bs: list) -> list:
        """Build PDF tax latency rows from balance_sheet_adjustments (Venus BSA path)."""
        return build_tax_latency_rows_from_balance_sheet_adjustments(raw_bs)

    def _extract_tax_latencies(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        step_data: JsonMap,
    ) -> list:
        """
        Extract tax latency data from Step 7 results or request payload.
        Returns list of dicts for the PDF template.
        """
        return resolve_tax_latencies(request=request, step_data=step_data)

    def _extract_balance_sheet_adjustments(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        step_data: JsonMap,
    ) -> list:
        """
        Extract balance sheet adjustments from Step 7 results or request payload.
        Returns list of dicts for the PDF template's equity bridge table.
        """
        return resolve_balance_sheet_adjustments(request=request, step_data=step_data)

    def _compact_waterfall_label(
        self,
        label: str,
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> str:
        return compact_waterfall_label(
            label,
            self._translations_or_fallback(locale, request, t),
        )

    def _compact_balance_sheet_adjustment_label(
        self,
        label: str,
        category: str,
        ordinal: int,
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> str:
        return compact_balance_sheet_adjustment_label(
            label,
            category,
            ordinal,
            self._translations_or_fallback(locale, request, t),
        )

    def _build_multiple_waterfall_steps(
        self,
        calibration_steps: JsonRows,
        applied_multiple: Decimal,
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> JsonRows:
        return build_multiple_waterfall_steps(
            calibration_steps,
            applied_multiple,
            self._translations_or_fallback(locale, request, t),
        )

    def _build_valuation_waterfall_steps(
        self,
        valuation_basis_value: Decimal,
        metric_type: str,
        applied_multiple: Decimal,
        enterprise_value_mid: Decimal,
        total_debt: Decimal,
        cash_balance: Decimal,
        excess_cash: Decimal,
        exemption_applied: bool,
        net_debt: Decimal,
        tax_latency_net_impact: Decimal,
        balance_sheet_adjustments: JsonRows,
        nwc_surplus_deficit: Decimal = Decimal("0"),
        equity_value: Decimal = Decimal("0"),
        include_metric_bridge: bool = True,
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> JsonRows:
        return build_valuation_waterfall_steps(
            valuation_basis_value,
            metric_type,
            applied_multiple,
            enterprise_value_mid,
            total_debt,
            cash_balance,
            excess_cash,
            exemption_applied,
            net_debt,
            tax_latency_net_impact,
            balance_sheet_adjustments,
            self._translations_or_fallback(locale, request, t),
            nwc_surplus_deficit=nwc_surplus_deficit,
            equity_value=equity_value,
            include_metric_bridge=include_metric_bridge,
        )

    # HYBRID METHODOLOGY DATA EXTRACTION

    def _extract_hybrid_weights(
        self,
        response: ValuationResponse,
        locale: str = "nl",
        t: Optional[ReportTranslations] = None,
        request: Optional[ValuationRequest] = None,
    ) -> JsonMap:
        """Extract methodology weights for Hybrid (Multiples + DCF) approach.

        Delegates to ``report_sections.hybrid_section.build_hybrid_context``
        which uses the canonical contract.  There is no hidden 70/30 default.
        """
        from src.services.infrastructure.report_sections.hybrid_section import build_hybrid_context

        _cc = self._country_code_from_request(request)
        result = build_hybrid_context(response, locale=locale, t=t, country_code=_cc)
        self.logger.debug(
            "Hybrid weight extraction",
            extra={"is_hybrid": result.get("is_hybrid", False)},
        )
        return result

    # ACCOUNTANT BRANDING

    def _get_accountant_name(self, request: Optional[ValuationRequest]) -> Optional[str]:
        """Get accountant firm name from request metadata."""
        return resolve_accountant_name(request)

    def _get_accountant_logo(self, request: Optional[ValuationRequest]) -> Optional[str]:
        """Get accountant logo URL from request metadata."""
        return resolve_accountant_logo(request)

    def _get_request_metadata(self, request: Optional[ValuationRequest]) -> Optional[JsonMap]:
        """Return request metadata only when it is a mapping."""
        return resolve_request_metadata(request)

    def _build_preparer_ebitda_override_footnote(
        self,
        request: Optional[ValuationRequest],
        locale: str,
    ) -> Optional[str]:
        """PDF/HTML footnote when Titan metadata includes preparer EV/EBITDA adjustment."""
        metadata = self._get_request_metadata(request)
        return build_preparer_ebitda_override_footnote(
            metadata,
            locale,
            self._country_code_from_request(request),
        )

    def _get_metadata_bool(
        self, request: Optional[ValuationRequest], key: str, default: bool = False
    ) -> bool:
        """Get a boolean value from request metadata with a default fallback."""
        return resolve_metadata_bool(request, key, default)

    def _get_metadata_str(self, request: Optional[ValuationRequest], key: str) -> Optional[str]:
        """Get a string value from request metadata."""
        return resolve_metadata_str(request, key)

    def _get_metadata_float(self, request: Optional[ValuationRequest], key: str) -> Optional[float]:
        """Get a float value from request metadata."""
        return resolve_metadata_float(request, key)

    # FISCAL REFERENCE (Belgian meerwaardebelasting)

    def _get_latest_closed_fiscal_year_data(
        self,
        request: Optional[ValuationRequest],
    ) -> object | None:
        """Return the most recent *closed* fiscal year with EBITDA data.

        Belgian law (Art. 102, § 4 WIB 92) requires the EBITDA of the *laatst
        afgesloten boekjaar*.  In UpSwitch's Venus flow the base year
        (= most recent closed year, e.g. 2024) lives on ``current_year_data``
        while older years live on ``historical_years_data``.  We include
        ``current_year_data`` as a candidate **only** when its year is at or
        before the filing-safe year, so that not-yet-closed periods do not get
        reported as the latest closed books before the product cutoff.
        """
        return latest_closed_fiscal_year_data(
            request,
            display_current_year_resolver=lambda current_request: resolve_display_current_year(
                request=current_request
            ),
        )

    def _get_fiscal_ebitda(
        self,
        request: Optional[ValuationRequest],
        sustainable_ebitda: Decimal,
        locale: str = "nl",
    ) -> Decimal:
        """EBITDA for fiscal forfaitaire formula: last closed book year only.

        Belgian law (Art. 102, § 4 WIB 92) requires 'EBITDA van het laatst afgesloten
        boekjaar' — a single year, NOT the multi-year weighted average.

        Fallback cascade:
        1. Most recent year's normalized EBITDA from multi-year table
        2. Most recent year's reported (raw) EBITDA from multi-year table
        3. current_year_data.ebitda from the request (single-year source)
        4. sustainable_ebitda (weighted average — last resort only)
        """
        return resolve_fiscal_ebitda(
            request,
            sustainable_ebitda,
            derive_normalized_ebitda=self._derive_normalized_ebitda,
            latest_closed_fiscal_year_resolver=self._get_latest_closed_fiscal_year_data,
        )

    def _get_fiscal_reported_ebitda(
        self,
        request: Optional[ValuationRequest],
    ) -> Optional[Decimal]:
        """Statutaire (reported) EBITDA of the laatst afgesloten boekjaar.

        Used by the fiscal annex page to surface any gap with a normalised
        figure that may have been applied upstream (Art. 102, § 4 WIB 92 expects
        the EBITDA *of the last closed fiscal year*, not management
        normalisations). Returns ``None`` when no clean reported figure can
        be reconstructed — callers should treat the value used as already
        statutaire and skip the disclosure row.

        Resolution order (reported-only — never returns a post-normalisation
        figure as if it were statutaire):
          1. ``ebitda_normalization_metadata.reported_ebitda`` (canonical pre-
             normalisation tag set by the request normaliser).
          2. ``year_data.ebitda`` raw, **only when** ``ebitda_normalized`` is
             False — otherwise that field is the post-normalisation value
             and would understate / overstate the legal anchor.
        """
        return resolve_fiscal_reported_ebitda(
            request,
            latest_closed_fiscal_year_resolver=self._get_latest_closed_fiscal_year_data,
        )

    def _user_selected_fiscal_4x(self, request: Optional[ValuationRequest]) -> bool:
        """True when the run explicitly selected ``fiscal_4x`` (e.g. Venus method picker).

        Branding may still set ``metadata.show_fiscal_reference`` alone; this path
        ensures choosing the fiscal reference methodology also requests the annex
        in the adaptive main report. ``fiscal_section`` continues to enforce BE-only
        and closed-year data guards.
        """
        return user_selected_fiscal_4x(request)

    def _build_fiscal_reference(
        self,
        request: Optional[ValuationRequest],
        fiscal_ebitda: Decimal,
        fiscal_reported_ebitda: Optional[Decimal] = None,
    ) -> JsonMap:
        """Delegates to ``report_sections.fiscal_section.build_fiscal_reference_context``.

        Enriches the metadata dict passed downstream with the resolved
        real-estate carve-out state so the fiscal annex declares whether
        the EBITDA basis was already adjusted for excluded property.
        """
        return build_fiscal_reference_report_context(
            request=request,
            fiscal_ebitda=fiscal_ebitda,
            fiscal_reported_ebitda=fiscal_reported_ebitda,
            latest_closed_fiscal_year_resolver=self._get_latest_closed_fiscal_year_data,
            country_code_resolver=self._country_code_from_request,
        )
