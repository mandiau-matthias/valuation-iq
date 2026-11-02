"""Aggregate valuation response and request data into the main report context."""

from decimal import Decimal
from threading import Lock
from typing import Optional

from src.services.infrastructure.main_report_source_context import (
    _first_present_attr,
    build_main_report_source_context,
)
from src.services.infrastructure.main_report_valuation_alignment_context import (
    build_main_report_valuation_alignment_context,
)
from src.services.infrastructure.translations import get_translations
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.reports.advisor_override_context import build_method_override_context
from src.services.reports.business_display_context import build_business_display_context
from src.services.reports.business_label_localization import (
    BUSINESS_TYPE_TRANSLATIONS_NL,
    localize_business_label,
)
from src.services.reports.company_registry_context import build_registry_report_context
from src.services.reports.ev_equity_bridge_context import (
    build_ev_equity_bridge_context,
    build_ev_equity_bridge_report_context,
)
from src.services.reports.main_report_additional_section_context import (
    build_main_report_additional_section_contexts,
)
from src.services.reports.main_report_advisor_reference_context import (
    build_main_report_advisor_reference_context,
)
from src.services.reports.main_report_aggregation_finalization import (
    apply_and_finalize_main_report_context,
)
from src.services.reports.main_report_aggregation_helpers import MainReportAggregationHelpersMixin
from src.services.reports.main_report_benchmark_source_label import (
    localized_honest_benchmark_source_label,
    should_force_range_for_thin_benchmark,
)
from src.services.reports.main_report_context_helpers import MainReportContextHelpersMixin
from src.services.reports.main_report_contracts import MainReportContext
from src.services.reports.main_report_current_year_context import build_current_year_data_context
from src.services.reports.main_report_dict_input import aggregate_main_report_from_valuation_data
from src.services.reports.main_report_official_financials_flat_context import (
    build_main_report_official_financials_flat_context,
)
from src.services.reports.main_report_official_financials_mixin import (
    MainReportOfficialFinancialsMixin,
)
from src.services.reports.main_report_section_mixin import MainReportSectionMixin
from src.services.reports.main_report_step_data_mixin import MainReportStepDataMixin
from src.services.reports.main_report_value_summary_context import (
    build_main_report_headline_context,
    build_main_report_multiple_context,
)
from src.services.reports.main_report_waterfall_context import build_main_report_waterfall_context
from src.services.reports.method_divergence_caveat import build_method_divergence_caveat
from src.services.reports.protocol_adapter import (
    DictWrapper,
    _sanitize_market_data_source_display,
    coerce_json_object,
)
from src.services.reports.report_benchmark_context import build_benchmark_report_context
from src.services.reports.report_branding_context import build_report_branding_context
from src.services.reports.report_bridge_helpers import (
    build_bridge_residual_context,
    compute_ev_equity_bridge_residual,
)
from src.services.reports.report_industry_display import get_industry_emoji
from src.services.reports.report_warning_context import build_report_warning_context
from src.services.reports.revenue_quality_context import build_revenue_quality_context
from src.services.reports.valuation_band_context import finalize_valuation_bands
from src.utils.decimal_helpers import pin_band_monotone
from src.utils.decimal_helpers import safe_decimal_or_zero as _canonical_safe_decimal
from src.utils.decimal_helpers import safe_float as _canonical_safe_float
from src.utils.logging import get_logger

ValuationResponse = ValuationResponseProtocol
ValuationRequest = ValuationRequestProtocol
logger = get_logger(__name__)

to_float = _canonical_safe_float
safe_decimal = _canonical_safe_decimal

_COVER_EBITDA_BASIS_WORDS = {
    "nl": ("Genormaliseerde EBITDA", "Gerapporteerde EBITDA", " (gewogen)"),
    "en": ("Normalized EBITDA", "Reported EBITDA", " (weighted)"),
    "fr": ("EBITDA normalise", "EBITDA declare", " (pondere)"),
}


def _cover_ebitda_basis_label(
    *,
    total_adjustments: Decimal,
    is_weighted_basis: bool,
    locale: Optional[str],
) -> str:
    """Name the earnings basis the cover actually priced.

    Two independent claims live in this label and each must be earned:
    "genormaliseerd" requires a non-zero applied adjustment total, and
    "(gewogen)" requires the multi-year weighted average to be the valuation
    basis rather than the latest year alone.
    """
    language = (locale or "nl").strip().lower()[:2]
    normalized_word, reported_word, weighted_suffix = _COVER_EBITDA_BASIS_WORDS.get(
        language, _COVER_EBITDA_BASIS_WORDS["nl"]
    )
    base = normalized_word if total_adjustments != Decimal("0") else reported_word
    return f"{base}{weighted_suffix}" if is_weighted_basis else base


_SHORT_EBITDA_BASIS_WORDS = (
    ("Genormaliseerde", "Norm."),
    ("Gerapporteerde", "Gerapp."),
    ("Normalized", "Norm."),
    ("Reported", "Rep."),
    ("EBITDA normalise", "EBITDA norm."),
    ("EBITDA declare", "EBITDA decl."),
)


def _short_ebitda_basis_label(label: str) -> str:
    """Chart-width form of :func:`_cover_ebitda_basis_label` (drops the weighting
    suffix, abbreviates the adjective) so the waterfall bar and the cover name
    the same basis."""
    short = label
    for _normalized, _reported, suffix in _COVER_EBITDA_BASIS_WORDS.values():
        short = short.replace(suffix, "")
    for long_word, short_word in _SHORT_EBITDA_BASIS_WORDS:
        if short.startswith(long_word):
            return short_word + short[len(long_word) :]
    return short


_DISCOUNT_CONTEXT_KEYS = {
    "owner_concentration": "owner_concentration_discount",
    "size": "size_discount",
    "liquidity": "liquidity_discount",
}


def _attr_or_key(container: object, name: str) -> object:
    if isinstance(container, dict):
        return container.get(name)
    return getattr(container, name, None)


def _discount_fractions_from_build_up(response: object) -> dict[str, float]:
    """The Step 4 / 5 / 6 discount fractions the headline multiple actually carries.

    The discount-methodology addendum recomputes its "applied multiple" from the
    context keys ``owner_concentration_discount`` / ``liquidity_discount`` /
    ``size_discount``. Nothing populated them for the main report, so it printed
    the BASE multiple as "after discounts", the pre-discount product as
    "enterprise value", and "no company-specific adjustment was quantified" —
    directly under a waterfall showing three. The engine's own build-up is the
    authority; read it.
    """
    multiples = _attr_or_key(response, "multiples_valuation")
    build_up = _attr_or_key(multiples, "multiple_build_up") if multiples is not None else None
    stages = _attr_or_key(build_up, "stages") if build_up is not None else None
    if not isinstance(stages, list):
        return {}
    fractions: dict[str, float] = {}
    for stage in stages:
        key = _DISCOUNT_CONTEXT_KEYS.get(str(_attr_or_key(stage, "discount_type") or ""))
        if key is None:
            continue
        pct = to_float(_attr_or_key(stage, "discount_percentage"))
        if pct is None:
            continue
        fractions[key] = abs(pct) / 100.0
    return fractions

__all__ = [
    "MainReportDataAggregator",
    "DictWrapper",
    "_first_present_attr",
    "_sanitize_market_data_source_display",
    "build_bridge_residual_context",
    "compute_ev_equity_bridge_residual",
    "BUSINESS_TYPE_TRANSLATIONS_NL",
    "get_industry_emoji",
    "get_main_report_aggregator",
    "localize_business_label",
    "pin_band_monotone",
]


class MainReportDataAggregator(
    MainReportContextHelpersMixin,
    MainReportStepDataMixin,
    MainReportAggregationHelpersMixin,
    MainReportSectionMixin,
    MainReportOfficialFinancialsMixin,
):
    """Bank-grade data aggregator for the main report template context."""

    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def aggregate_from_valuation_data(
        self,
        valuation_data: dict[str, object],
        locale: str = "nl",
    ) -> MainReportContext:
        return aggregate_main_report_from_valuation_data(
            valuation_data=valuation_data,
            locale=locale,
            aggregate=self.aggregate,
            logger=self.logger,
        )

    def aggregate(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest] = None,
        locale: Optional[str] = None,
    ) -> MainReportContext:
        """Aggregate response/request data into the main report template context.

        i18n: one immutable ``ReportTranslations`` snapshot per aggregation; templates
        receive the same ``t`` through the render layer for server-side HTML/PDF.
        """
        # DEBUG: aggregator entry breadcrumb. The "Data aggregation complete"
        # INFO and the calling AUDIT line are the canonical exits.
        self.logger.debug(
            f"🔍 [AGGREGATOR] Aggregating data for {getattr(response, 'company_name', 'unknown')}",
            extra={"valuation_id": getattr(response, "valuation_id", None)},
        )

        locale = locale or getattr(request, "report_locale", None) or getattr(request, "locale", None) or "nl"
        source = build_main_report_source_context(self, response, request, locale)
        _report_loc = source.report_locale
        locale = _report_loc
        _report_country = source.report_country
        _report_t = source.translations
        step_data = source.step_data
        business_type_id = source.business_type_id
        nace_code = source.nace_code
        industry_benchmarks = source.industry_benchmarks
        registration_number = source.registration_number
        kbo_data = source.kbo_data
        official_financials = source.official_financials
        sustainable_ebitda = source.sustainable_ebitda
        reported_ebitda = source.reported_ebitda
        revenue_value = source.revenue_value
        latest_year = source.latest_year
        _cached_multi_year = source.multi_year_data
        consolidation_report_context = source.consolidation_report_context
        latest_year_normalized_ebitda = source.latest_year_normalized_ebitda
        total_adjustments = source.total_adjustments
        proposed_adjustments_total = source.proposed_adjustments_total
        proposed_adjustments_count = source.proposed_adjustments_count
        multiple_context = source.multiple_context
        applied_multiple = source.applied_multiple
        base_multiple = source.base_multiple
        implied_ebitda_multiple_context = source.implied_ebitda_multiple_context

        # Keep the waterfall anchored to the SME-calibrated Step 3 multiple.

        valuation_alignment = build_main_report_valuation_alignment_context(
            self,
            response=response,
            request=request,
            source=source,
            bridge_context_builder=build_ev_equity_bridge_context,
        )
        _is_dcf_only = valuation_alignment.is_dcf_only
        _is_asset_anchored = valuation_alignment.is_asset_anchored
        _has_weighted_synthesis_payload = valuation_alignment.has_weighted_synthesis_payload
        _dcf_ineligible_scenario = valuation_alignment.dcf_ineligible_forced_blend
        _is_hybrid_method = valuation_alignment.is_hybrid_method
        has_balance_data = valuation_alignment.has_balance_data
        enterprise_value_low = valuation_alignment.enterprise_value_low
        enterprise_value_mid = valuation_alignment.enterprise_value_mid
        enterprise_value_high = valuation_alignment.enterprise_value_high
        equity_value_low = valuation_alignment.equity_value_low
        equity_value = valuation_alignment.equity_value
        equity_value_high = valuation_alignment.equity_value_high
        formula_metric_value = valuation_alignment.formula_metric_value
        multiple_low = valuation_alignment.multiple_low
        multiple_high = valuation_alignment.multiple_high
        display_multiple = valuation_alignment.display_multiple
        _pre_synthesis_multiple = valuation_alignment.pre_synthesis_multiple
        _applied_multiple_rail = valuation_alignment.applied_multiple_rail
        _engine_synthesis_equity_anchored = valuation_alignment.engine_synthesis_equity_anchored

        # Min-sample floor: a benchmark resting on ≤3 comparables (or a
        # Damodaran country-baseline proxy, inherently n≈1) cannot defensibly
        # support a false-precision POINT headline. When thin, surfaces lead
        # with the low–high RANGE instead (the central estimate stays available
        # in the method detail). Policy lives in benchmark_source_label.
        _thin_benchmark_force_range = should_force_range_for_thin_benchmark(
            sample_size=industry_benchmarks.get("sample_size"),
            benchmark_contract=industry_benchmarks.get("benchmark_contract"),
        )
        # DCF↔market method-divergence caveat: when a hybrid blends two legs that
        # disagree materially (one ≥ 2× the other) the headline is forecast-
        # sensitive and the reader must see it. Same trigger as the QA invariant
        # `dcf_market_cross_method_divergence`; surfaced here as a printed notice.
        _method_divergence_caveat = (
            build_method_divergence_caveat(
                getattr(response, "dcf_valuation", None),
                getattr(response, "multiples_valuation", None),
                getattr(response, "dcf_weight", None),
                locale,
            )
            if _is_hybrid_method
            else None
        )
        total_discount = valuation_alignment.total_discount
        benchmark_disclosure = valuation_alignment.benchmark_disclosure
        has_benchmark_reference_multiple = valuation_alignment.has_benchmark_reference_multiple
        bridge_context = valuation_alignment.bridge_context
        net_debt_from_steps = valuation_alignment.net_debt_from_steps
        aligned_recommended_asking_price = valuation_alignment.aligned_recommended_asking_price
        asking_price_realigned = valuation_alignment.asking_price_realigned
        show_ev_equity_bridge = valuation_alignment.show_ev_equity_bridge
        show_enterprise_to_equity_bridge = valuation_alignment.show_enterprise_to_equity_bridge
        has_net_debt_adjustment = valuation_alignment.has_net_debt_adjustment
        bridge_net_debt_operator = valuation_alignment.bridge_net_debt_operator
        bridge_net_debt_amount = valuation_alignment.bridge_net_debt_amount
        _resolved_tax_latencies = valuation_alignment.tax_latencies
        _resolved_tax_latency_net_impact = valuation_alignment.tax_latency_net_impact
        tax_latency_net_impact_decimal = valuation_alignment.tax_latency_net_impact_decimal
        _bs_adjustments = valuation_alignment.balance_sheet_adjustments
        _nwc_signed = valuation_alignment.nwc_signed
        _displayed_net_debt = valuation_alignment.displayed_net_debt
        bridge_residual = valuation_alignment.bridge_residual
        show_bridge_cash_split = valuation_alignment.show_bridge_cash_split
        _bridge_cash_total = valuation_alignment.bridge_cash_total
        _bridge_excess_cash = valuation_alignment.bridge_excess_cash
        _bridge_ib_debt = valuation_alignment.bridge_ib_debt
        _bridge_operating_cash_held = valuation_alignment.bridge_operating_cash_held

        country_code = _report_country

        business_display = build_business_display_context(
            industry=self._get_industry(response, request),
            business_type_id=business_type_id,
            nace_code=nace_code,
            industry_benchmarks=industry_benchmarks,
            locale=locale,
        )
        display_industry = business_display.industry
        display_business_type_title = business_display.business_type_title
        display_business_type_icon = business_display.business_type_icon
        display_sector = business_display.sector

        # Pre-compute fiscal reference data so total_pages stays consistent
        # even if the fiscal calculation encounters an error and falls back.
        # Use last closed book year EBITDA only (law: laatst afgesloten boekjaar),
        # not multi-year weighted average.
        fiscal_ebitda = self._get_fiscal_ebitda(request, sustainable_ebitda, locale)
        fiscal_reported_ebitda = self._get_fiscal_reported_ebitda(request)
        fiscal_ref_data = self._build_fiscal_reference(
            request, fiscal_ebitda, fiscal_reported_ebitda
        )

        _prep_footnote = self._build_preparer_ebitda_override_footnote(request, locale)
        _prep_footnote_title = (
            get_translations(_report_loc, country_code=_report_country).disc_preparer_override_title
            if _prep_footnote
            else None
        )

        is_hybrid_methodology = _is_hybrid_method
        is_dcf_only_methodology = _is_dcf_only
        # One name for the earnings basis, shared by the cover and the waterfall.
        _ebitda_basis_label = _cover_ebitda_basis_label(
            total_adjustments=total_adjustments,
            is_weighted_basis=self._should_show_ebitda_weighting_footnote(
                sustainable_ebitda,
                latest_year_normalized_ebitda,
                total_adjustments,
                _cached_multi_year,
            ),
            locale=locale,
        )
        waterfall_context = build_main_report_waterfall_context(
            response=response,
            request=request,
            step_data=step_data,
            ebitda_basis_labels=(
                _ebitda_basis_label,
                _short_ebitda_basis_label(_ebitda_basis_label),
            ),
            formula_metric_value=formula_metric_value,
            multiple_context=multiple_context,
            base_multiple=base_multiple,
            display_multiple=display_multiple,
            enterprise_value_mid=enterprise_value_mid,
            net_debt_from_steps=net_debt_from_steps,
            tax_latency_net_impact_decimal=tax_latency_net_impact_decimal,
            balance_sheet_adjustments=_bs_adjustments,
            equity_value=equity_value,
            locale=locale,
            translations=_report_t,
            benchmark_disclosure=benchmark_disclosure,
            is_hybrid_methodology=is_hybrid_methodology,
            is_dcf_only_methodology=is_dcf_only_methodology,
            is_asset_anchored=_is_asset_anchored,
            has_weighted_synthesis_payload=_has_weighted_synthesis_payload,
            engine_synthesis_equity_anchored=_engine_synthesis_equity_anchored,
        )
        calibration_steps = waterfall_context.calibration_steps
        multiple_waterfall_steps = waterfall_context.multiple_waterfall_steps
        valuation_waterfall_steps = waterfall_context.valuation_waterfall_steps
        supports_metric_to_ev_bridge = waterfall_context.supports_metric_to_ev_bridge
        show_size_discount_skipped_note = waterfall_context.show_size_discount_skipped_note
        show_benchmark_reference_without_table = (
            waterfall_context.show_benchmark_reference_without_table
        )

        _assessed_data_quality = self._assess_data_quality(response, request, locale, _report_t)

        report_warning_context = build_report_warning_context(
            response=response,
            step_data=step_data,
            fiscal_integrity_warnings=fiscal_ref_data.get("fiscal_integrity_warnings"),
            locale=locale,
            translations=_report_t,
        )

        _is_owner_dep_methodology_for_op = not is_dcf_only_methodology and not _is_asset_anchored
        additional_sections = build_main_report_additional_section_contexts(
            response=response,
            translations=_report_t,
            step_data=step_data,
            is_owner_dep_methodology=_is_owner_dep_methodology_for_op,
            is_asset_anchored=_is_asset_anchored,
            request=request,
            locale=_report_loc,
        )

        band_context = finalize_valuation_bands(
            response=response,
            step_data=step_data,
            enterprise_value_low=enterprise_value_low,
            enterprise_value_mid=enterprise_value_mid,
            enterprise_value_high=enterprise_value_high,
            equity_value_low=equity_value_low,
            equity_value=equity_value,
            equity_value_high=equity_value_high,
            logger=self.logger,
        )
        enterprise_value_low = band_context.enterprise_value_low
        enterprise_value_mid = band_context.enterprise_value_mid
        enterprise_value_high = band_context.enterprise_value_high
        equity_value_low = band_context.equity_value_low
        equity_value = band_context.equity_value
        equity_value_high = band_context.equity_value_high
        _ev_band_is_meaningful = band_context.ev_band_is_meaningful
        _equity_band_is_meaningful = band_context.equity_band_is_meaningful
        equity_value_assumed_equal_ev_due_to_missing_balance = False

        # FINAL bridge residual (panel B6): equity/EV can be overridden after
        # the first residual computation (the weighted synthesis lands through
        # the band/step-11 context above), so the earlier value can mix stages
        # — synthesis-level EV against pre-synthesis equity printed a phantom
        # −€4,75M 'reconciliation' row on a bridge that foots. Recompute from
        # the FINAL values actually injected into the template, against the
        # DISPLAYED net-debt line.
        bridge_residual = compute_ev_equity_bridge_residual(
            enterprise_value_mid=enterprise_value_mid,
            equity_value=equity_value,
            net_debt=_displayed_net_debt,
            tax_latency_net_impact=tax_latency_net_impact_decimal,
            balance_sheet_adjustments=_bs_adjustments,
            nwc_surplus_deficit=_nwc_signed,
        )

        advisor_reference_context = build_main_report_advisor_reference_context(
            response=response,
            request=request,
            applied_multiple=applied_multiple,
            multi_year_data=_cached_multi_year,
            locale=locale,
            report_locale=_report_loc,
            request_metadata=self._get_request_metadata(request),
            step_data=step_data,
        )
        request_metadata = advisor_reference_context.request_metadata
        report_reference_context = advisor_reference_context.report_reference
        advisor_multiple_calibration = advisor_reference_context.advisor_multiple_calibration
        raw_weighting_mode = advisor_reference_context.raw_weighting_mode
        advisor_historical_ebitda_weighting = (
            advisor_reference_context.advisor_historical_ebitda_weighting
        )
        advisor_real_estate_treatment = advisor_reference_context.advisor_real_estate_treatment
        _confidence_score_pct = advisor_reference_context.confidence_score_pct

        # Build the complete context
        context = {
            # ═══════════════════════════════════════════════════════════════
            # CORE IDENTIFICATION
            # ═══════════════════════════════════════════════════════════════
            **build_main_report_headline_context(
                response=response,
                report_reference=report_reference_context,
                translations=_report_t,
                latest_year=latest_year,
                enterprise_value_low=enterprise_value_low,
                enterprise_value_mid=enterprise_value_mid,
                enterprise_value_high=enterprise_value_high,
                equity_value_low=equity_value_low,
                equity_value=equity_value,
                equity_value_high=equity_value_high,
                dcf_ineligible_scenario=_dcf_ineligible_scenario,
                ev_band_is_meaningful=_ev_band_is_meaningful,
                equity_band_is_meaningful=_equity_band_is_meaningful,
                thin_benchmark_force_range=_thin_benchmark_force_range,
                method_divergence_caveat=_method_divergence_caveat,
                step_data=step_data,
                engine_synthesis_equity_anchored=_engine_synthesis_equity_anchored,
                aligned_recommended_asking_price=aligned_recommended_asking_price,
                asking_price_realigned=asking_price_realigned,
            ),
            # ═══════════════════════════════════════════════════════════════
            # VALUATION RESULTS (raw values for Jinja2 filters)
            # ═══════════════════════════════════════════════════════════════
            # ═══════════════════════════════════════════════════════════════
            # EBITDA DATA
            # ═══════════════════════════════════════════════════════════════
            "sustainable_ebitda": to_float(sustainable_ebitda),
            "reported_ebitda": to_float(reported_ebitda),
            "latest_normalized_ebitda": to_float(latest_year_normalized_ebitda),
            "valuation_basis_ebitda": to_float(sustainable_ebitda),
            "total_adjustments": to_float(total_adjustments),
            # Twelve template sites and the transaction-readiness context branch on
            # this flag to say "Gerapporteerde" instead of "Genormaliseerde". Nothing
            # set it for the main report, so every one of those branches was dead
            # and a run with EUR 0 of adjustments still called its basis normalised.
            # Same rule as the cover label: no applied adjustment ⇒ reported basis.
            "headline_ebitda_is_reported": total_adjustments == Decimal("0"),
            **_discount_fractions_from_build_up(response),
            # Detected-but-not-applied normalization candidates (advisor review
            # required). Drives an honest note + keeps the €0 "Totale
            # aanpassingen" line from reading as a clean ledger when Hermes
            # actually surfaced related-party / owner-comp candidates.
            "normalization_candidate_count": proposed_adjustments_count,
            "normalization_candidate_total": to_float(proposed_adjustments_total),
            "show_normalization_candidates_note": (
                proposed_adjustments_count > 0 and total_adjustments == Decimal("0")
            ),
            "show_ebitda_weighting_footnote": self._should_show_ebitda_weighting_footnote(
                sustainable_ebitda,
                latest_year_normalized_ebitda,
                total_adjustments,
                _cached_multi_year,
            ),
            # Single source of truth for the earnings-basis label shown on the
            # cover and executive tiles. The catalog string
            # ``cover_ebitda_label`` asserts BOTH "genormaliseerd" and
            # "(gewogen)"; a run with €0 adjustments valued off the latest year
            # alone is neither, and a cover that claims a normalized basis
            # contradicts a report whose own body says the EBITDA is reported
            # as filed. Derive the two words from the run instead of relying on
            # per-template ``elif`` chains that silently fall through.
            "cover_ebitda_basis_label": _cover_ebitda_basis_label(
                total_adjustments=total_adjustments,
                is_weighted_basis=self._should_show_ebitda_weighting_footnote(
                    sustainable_ebitda,
                    latest_year_normalized_ebitda,
                    total_adjustments,
                    _cached_multi_year,
                ),
                locale=locale,
            ),
            # Owner-led pending-normalisation prompt: surfaces a callout above
            # the bridge when no normalisations were entered and the company
            # profile (≥1 owner-manager, ≤10 FTE) makes owner-comp adjustment
            # the dominant defensibility risk. Three Towers Capital regression.
            "show_owner_comp_pending_note": self._should_show_owner_comp_pending_note(
                response, request, total_adjustments
            ),
            # True when the weighted multi-year basis embeds prior-year
            # normalizations. The owner-comp pending note's default body claims
            # the reported EBITDA is used "without normalisation" — accurate only
            # when no weighted year carries an applied adjustment. This flag lets
            # the normalization page render an honest body that acknowledges the
            # embedded normalizations, so the page never contradicts its own
            # multi-year table (Restaurant Upswitch audit, June 2026).
            "multi_year_basis_has_normalizations": (
                self._multi_year_basis_has_normalizations(_cached_multi_year)
            ),
            # Engine warnings accumulated during aggregation (formula
            # mismatch, derived net-debt, phantom-bridge suppressed). Exposed
            # so the defensibility classifier can read them out of
            # ``valuation_data.engine_warnings`` during the next /pdf cycle,
            # and so templates can render an in-page integrity panel near
            # the disclaimers if non-empty. Always a list (possibly empty).
            "engine_warnings": list(step_data.get("_engine_warnings", []) or []),
            # ═══════════════════════════════════════════════════════════════
            # MULTIPLE DATA
            # ═══════════════════════════════════════════════════════════════
            **build_main_report_multiple_context(
                response=response,
                multiple_context=multiple_context,
                implied_ebitda_multiple_context=implied_ebitda_multiple_context,
                formula_metric_value=formula_metric_value,
                display_multiple=display_multiple,
                pre_synthesis_multiple=_pre_synthesis_multiple,
                applied_multiple_rail=_applied_multiple_rail,
                base_multiple=base_multiple,
                multiple_low=multiple_low,
                multiple_high=multiple_high,
                total_discount=total_discount,
                has_benchmark_reference_multiple=has_benchmark_reference_multiple,
                show_benchmark_reference_without_table=show_benchmark_reference_without_table,
                show_size_discount_skipped_note=show_size_discount_skipped_note,
                locale=_report_loc,
            ),
            # ═══════════════════════════════════════════════════════════════
            # INDUSTRY & COMPANY CONTEXT
            # ═══════════════════════════════════════════════════════════════
            "industry": display_industry,
            # Use same icon as business_type for consistency (cover background + badge)
            "industry_emoji": display_business_type_icon,
            "revenue": to_float(revenue_value),
            "has_balance_data": has_balance_data,
            "equity_value_assumed_equal_ev_due_to_missing_balance": (
                equity_value_assumed_equal_ev_due_to_missing_balance
            ),
            **build_main_report_official_financials_flat_context(
                official_financials=official_financials,
                user_revenue=revenue_value,
                user_reported_ebitda=reported_ebitda,
                translations=_report_t,
            ),
            # ═══════════════════════════════════════════════════════════════
            # ADDITIONAL COMPANY CONTEXT (Phase 4)
            # ═══════════════════════════════════════════════════════════════
            "employee_count": self._get_employee_count(response, request),
            "methodology_statement": self._get_methodology_statement(
                response,
                request,
                multiple_context["metric_type"],
                locale,
                _report_t,
            ),
            "valuation_methodology": self._get_valuation_methodology(response, locale),
            "valuation_methodology_display": self._get_valuation_methodology_display(
                response,
                multiple_context["metric_type"],
                locale,
                _report_t,
                request,
            ),
            # ═══════════════════════════════════════════════════════════════
            # ACCOUNTANT BRANDING & REPORT SETTINGS
            # ═══════════════════════════════════════════════════════════════
            **build_report_branding_context(
                request=request,
                country_code=self._country_code_from_request(request),
                preparer_ebitda_override_title=_prep_footnote_title,
                preparer_ebitda_override_footnote=_prep_footnote,
            ),
            # ═══════════════════════════════════════════════════════════════
            # FISCAL REFERENCE (Belgian meerwaardebelasting)
            # ═══════════════════════════════════════════════════════════════
            **fiscal_ref_data,
            # ═══════════════════════════════════════════════════════════════
            # METHOD OVERRIDE (accountant manual method selection)
            # ═══════════════════════════════════════════════════════════════
            **build_method_override_context(request),
            "advisor_multiple_calibration": advisor_multiple_calibration,
            "advisor_historical_ebitda_weighting": advisor_historical_ebitda_weighting,
            "advisor_real_estate_treatment": advisor_real_estate_treatment,
            "historical_ebitda_weighting_mode": raw_weighting_mode,
            "has_custom_historical_ebitda_weighting": advisor_historical_ebitda_weighting
            is not None,
            "total_pages": None,  # computed via compute_total_pages after all flags are known
            # ═══════════════════════════════════════════════════════════════
            # DATA QUALITY INDICATORS
            # ═══════════════════════════════════════════════════════════════
            "data_quality_level": _assessed_data_quality,
            "data_inputs": self._get_data_inputs(
                response,
                request,
                _report_t,
                include_comparable_transactions=(
                    not show_benchmark_reference_without_table
                    and safe_decimal(step_data.get("comparables_found", 0)) <= Decimal("0")
                ),
            ),
            # ═══════════════════════════════════════════════════════════════
            # EBITDA ADJUSTMENTS (for Page 3)
            # ═══════════════════════════════════════════════════════════════
            "ebitda_adjustments": self._build_adjustments(
                response,
                request,
                reported_ebitda,
                latest_year_normalized_ebitda,
                locale,
                _report_t,
            ),
            # ═══════════════════════════════════════════════════════════════
            # MULTI-YEAR EBITDA (for Page 3)
            # ═══════════════════════════════════════════════════════════════
            "multi_year_ebitda": _cached_multi_year,
            "weighted_ebitda_total": to_float(
                sum(row["weighted_ebitda"] for row in _cached_multi_year)
                if _cached_multi_year
                else sustainable_ebitda
            ),
            # EBITDA volatility summary — surfaces a spread/ratio chip on
            # Page 1 + cover when normalised EBITDA varies ≥ 3× across the
            # displayed years (or a loss year is present). Yuki/Metaalbewerking
            # audit: a 3.6× spread was hidden by the McKinsey weighting.
            "ebitda_volatility": self._compute_ebitda_volatility(_cached_multi_year, _report_t),
            # Data-quality flag: consecutive years with identical revenue AND EBITDA
            # (a duplicated book year) that would silently double-count in the basis.
            "duplicate_consecutive_years": self._detect_duplicate_years(_cached_multi_year),
            # Count of high-severity engine warnings routed to EngineCoPilot.
            # The cover surfaces this as a "N signals to review" chip so a
            # reviewer cannot share the PDF without knowing warnings exist —
            # even when the in-body callout is suppressed (assistant-first UX).
            "high_severity_warning_count": (
                len(report_warning_context.localized_high_severity_warnings)
                if report_warning_context.localized_high_severity_warnings
                else 0
            ),
            # ═══════════════════════════════════════════════════════════════
            # CALIBRATION STEPS (for Page 4)
            # ═══════════════════════════════════════════════════════════════
            "calibration_steps": calibration_steps,
            "multiple_waterfall_steps": multiple_waterfall_steps,
            "valuation_waterfall_steps": valuation_waterfall_steps,
            "supports_metric_to_ev_bridge": supports_metric_to_ev_bridge,
            "value_waterfall_intro_text": (
                _report_t.calib_value_waterfall_intro_balance_provided
                if _is_asset_anchored and has_balance_data
                else (
                    _report_t.calib_value_waterfall_intro_ev_focus
                    if not supports_metric_to_ev_bridge
                    else None
                )
            ),
            # ═══════════════════════════════════════════════════════════════
            # 12-STEP CALCULATION DATA (Phase 1 - Bank-Grade)
            # ═══════════════════════════════════════════════════════════════
            "step_data": step_data,
            # Named extractions for template convenience
            "data_quality_score": step_data.get("data_quality_score"),
            "quality_level": self._map_quality_level_display(
                step_data.get("quality_level") or _assessed_data_quality,
                locale,
                _report_t,
                request,
            ),
            "quality_warnings": report_warning_context.translated_quality_warnings,
            # Launch-ready defensibility: show Page-1 callouts for integrity
            # warnings only. This preserves clean-report UX for non-integrity
            # quality hints while making methodology substitutions and other
            # must-disclose limitations impossible to miss in the report.
            "report_quality_warnings_high": (
                report_warning_context.localized_high_severity_warnings
            ),
            **consolidation_report_context,
            "high_severity_callout_title": _report_t.high_severity_callout_title,
            "high_severity_callout_lead": report_warning_context.high_severity_callout_lead,
            "show_quality_warnings_callout": report_warning_context.show_integrity_callout,
            # Assistant-first UX: by default high-severity warnings are routed to
            # the Venus AI assistant rail, not rendered inside the report body.
            # Per-report override for stricter workflows is still possible via
            # request.metadata.render_quality_warnings_in_report=true.
            "render_quality_warnings_in_report": self._get_metadata_bool(
                request, "render_quality_warnings_in_report", False
            ),
            "method_substitution_disclosure": (
                report_warning_context.method_substitution_disclosure
            ),
            # Pass-5: working-capital disclosure on the EV→Equity callout.
            # Pre-built localized sentence so the template stays declarative.
            "nwc_disclosure_text": self._format_nwc_disclosure(response, _report_t),
            "comparables": step_data.get("comparables_list", []),
            "comparables_count": step_data.get("comparables_found", 0),
            "recommended_methodology": step_data.get("recommended_methodology"),
            "owner_dependency_risk_level": step_data.get("owner_dependency_risk_level"),
            "owner_dependency_adjustment": step_data.get("owner_dependency_adjustment", 0.0),
            "size_tier": step_data.get("size_tier"),
            "size_discount_percentage": step_data.get("size_discount_percentage", 0.0),
            "performance_discount_percentage": step_data.get("total_discount_percentage", 0.0),
            "margin_bonus": step_data.get("margin_bonus", 0.0),
            "growth_bonus": step_data.get("growth_bonus", 0.0),
            "overall_confidence_score": _confidence_score_pct,
            "confidence_score": _confidence_score_pct,
            # Legacy validator / template compat: expose valuation_range dict alongside
            # the new flat valuation/valuation_low/valuation_high fields so that both
            # the ReportDataValidator and any Jinja2 templates using valuation_range.mid
            # continue to work regardless of which path built the context.
            "valuation_range": {
                "low": to_float(enterprise_value_low),
                "mid": to_float(enterprise_value_mid),
                "high": to_float(enterprise_value_high),
            },
            "methodology": self._get_valuation_methodology(response, locale),
            "is_asset_anchored_methodology": _is_asset_anchored,
            "is_asset_methodology": _is_asset_anchored,
            "is_nav_methodology": self._is_asset_methodology(response),
            "is_yield_methodology": self._is_yield_methodology(response),
            "current_year_data": build_current_year_data_context(
                response=response,
                request=request,
            ),
            "factor_scores": step_data.get("factor_scores", {}),
            **additional_sections.cover_owner_profiling,
            **additional_sections.owner_profiling_section,
            **additional_sections.sellability_section,
            **additional_sections.stage_aware_breakdown,
            **additional_sections.business_growth_maturity,
            # M&A-grade Owner Risk Ledger — single auditable record of
            # structural (multiple-side) + behavioural (equity-side)
            # owner-risk discounts. Built by `synthesizer._build_owner_
            # risk_ledger_safely` and surfaced on the response. The
            # aggregator dumps the typed Pydantic model to a dict so
            # Jinja's attribute-access syntax (`ledger.entries`,
            # `ledger.audit_quality`) works without requiring the
            # template engine to import Pydantic.
            "owner_risk_ledger": coerce_json_object(getattr(response, "owner_risk_ledger", None)),
            "discount_waterfall": step_data.get("discount_waterfall", []),
            "multiple_pipeline": step_data.get("multiple_pipeline", []),
            **build_ev_equity_bridge_report_context(
                step_data=step_data,
                request=request,
                enterprise_value_mid=enterprise_value_mid,
                enterprise_value_low=enterprise_value_low,
                enterprise_value_high=enterprise_value_high,
                net_debt=net_debt_from_steps,
                show_ev_equity_bridge=show_ev_equity_bridge,
                show_enterprise_to_equity_bridge=show_enterprise_to_equity_bridge,
                has_net_debt_adjustment=has_net_debt_adjustment,
                bridge_net_debt_amount=bridge_net_debt_amount,
                bridge_net_debt_operator=bridge_net_debt_operator,
                bridge_residual=bridge_residual,
                tax_latencies=_resolved_tax_latencies,
                tax_latency_net_impact=_resolved_tax_latency_net_impact,
                balance_sheet_adjustments=_bs_adjustments,
            ),
            **build_benchmark_report_context(
                industry_benchmarks=industry_benchmarks,
                business_type_id=business_type_id,
                business_type_title=display_business_type_title,
                business_type_icon=display_business_type_icon,
                sector=display_sector,
                nace_code=nace_code,
                benchmark_data_source_label=localized_honest_benchmark_source_label(
                    industry_benchmarks.get("data_source"),
                    industry_benchmarks.get("benchmark_contract"),
                    _report_loc,
                ),
                neutral_benchmark_source_label=_report_t.report_benchmark_source_neutral,
            ),
            **build_registry_report_context(
                country_code=country_code,
                registration_number=registration_number,
                kbo_data=kbo_data,
                business_type_id=business_type_id,
                kvk_registration_label=_report_t.report_registration_number_label_kvk,
                kbo_registration_label=_report_t.report_registration_number_label_kbo,
                kvk_registry_name=_report_t.report_registry_short_kvk,
                kbo_registry_name=_report_t.report_registry_short_kbo,
            ),
            "academic_validation_issues": list(
                getattr(response, "academic_validation_issues", None) or []
            ),
            **build_revenue_quality_context(
                request=request,
                latest_revenue=revenue_value,
                locale=locale,
            ),
        }

        return apply_and_finalize_main_report_context(
            context,
            aggregator=self,
            response=response,
            request=request,
            request_metadata=request_metadata,
            locale=locale,
            report_locale=_report_loc,
            translations=_report_t,
            show_bridge_cash_split=show_bridge_cash_split,
            bridge_cash_total=_bridge_cash_total,
            bridge_operating_cash_held=_bridge_operating_cash_held,
            bridge_excess_cash=_bridge_excess_cash,
            bridge_ib_debt=_bridge_ib_debt,
        )


_aggregator_instance: Optional[MainReportDataAggregator] = None
_aggregator_lock = Lock()


def get_main_report_aggregator() -> MainReportDataAggregator:
    """Get or create the MainReportDataAggregator singleton."""
    global _aggregator_instance
    if _aggregator_instance is None:
        with _aggregator_lock:
            if _aggregator_instance is None:
                _aggregator_instance = MainReportDataAggregator()
    return _aggregator_instance
