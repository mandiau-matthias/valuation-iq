"""
Executive Summary Builders

Extracted from executive_summary_transformer.py to reduce complexity.
These builders handle individual sections of the executive summary.

I18N: Each ``build*`` accepts an optional ``t: ReportTranslations`` and
``locale``.  If ``t`` is not provided, builders fall back to a fresh
``get_translations()`` snapshot.  All user-visible strings are produced
through ``_t.<field>`` (or ``_t.<field>.format(...)`` for templates) so
that the resulting template_data dicts already carry localized text by
the time Jinja sees them — no English leaks into Dutch reports.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING

from src.services.infrastructure.report_confidence import confidence_score_percent

if TYPE_CHECKING:
    from src.services.interfaces.request_response_protocol import (
        ValuationRequestProtocol,
        ValuationResponseProtocol,
    )
    from src.services.infrastructure.translations import ReportTranslations


def _resolve_translations(
    t: Optional["ReportTranslations"],
    locale: str,
    country_code: str = "BE",
) -> "ReportTranslations":
    """Return a translations snapshot, defaulting to NL when locale missing."""
    if t is not None:
        return t
    from src.services.infrastructure.translations import get_translations, normalize_report_locale

    _cc = str(country_code or "BE").strip().upper() or "BE"
    return get_translations(
        normalize_report_locale(locale),
        country_code=_cc,
    )


class PrimaryMethodBuilder:
    """Builds primary method determination and explanation."""

    @staticmethod
    def build(
        response: "ValuationResponseProtocol",
        request: "ValuationRequestProtocol",
        get_ebitda_value_func,
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
        country_code: str = "BE",
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Determine primary valuation method and explanation.

        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            get_ebitda_value_func: Function to get EBITDA value
            t: Optional pre-built ReportTranslations snapshot
            locale: Fallback locale when ``t`` is not provided

        Returns:
            Tuple of (primary_method, primary_method_explanation), localized.
        """
        _t = _resolve_translations(t, locale, country_code)
        multiples = response.multiples_valuation
        dcf = response.dcf_valuation

        primary_method: Optional[str] = None
        primary_method_explanation: Optional[str] = None

        if multiples and response.multiples_weight > 0.5:
            if multiples.ebitda_multiple and multiples.ebitda_multiple > 0:
                primary_method = _t.transformer_method_label_ebitda_multiple
                ebitda_value = get_ebitda_value_func(response, request)
                if ebitda_value is not None:
                    primary_method_explanation = _t.transformer_primary_ebitda_with_value.format(
                        value=f"{ebitda_value:,.0f}"
                    )
                else:
                    primary_method_explanation = _t.transformer_primary_ebitda_no_value
            elif multiples.revenue_multiple and multiples.revenue_multiple > 0:
                primary_method = _t.transformer_method_label_revenue_multiple
                primary_method_explanation = _t.transformer_primary_revenue
        elif dcf and response.dcf_weight > 0.5:
            primary_method = _t.transformer_method_label_dcf
            primary_method_explanation = _t.transformer_primary_dcf

        return primary_method, primary_method_explanation


class MethodologyDescriptionBuilder:
    """Builds methodology description."""

    @staticmethod
    def build(
        response: "ValuationResponseProtocol",
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
        country_code: str = "BE",
    ) -> str:
        """
        Build methodology description.

        Args:
            response: ValuationResponse with calculation results
            t: Optional pre-built ReportTranslations snapshot
            locale: Fallback locale when ``t`` is not provided

        Returns:
            Methodology description string (localized).
        """
        _t = _resolve_translations(t, locale, country_code)

        # Free-form notes from the engine win when present (already localized
        # upstream by the methodology notes coordinator).
        if response.methodology_notes:
            return response.methodology_notes

        if response.dcf_weight > 0 and response.multiples_weight > 0:
            return _t.transformer_methodology_desc_hybrid.format(
                multiples_pct=f"{response.multiples_weight*100:.0f}",
                dcf_pct=f"{response.dcf_weight*100:.0f}",
            )
        if response.multiples_weight > 0:
            return _t.transformer_methodology_desc_multiples
        if response.dcf_weight > 0:
            return _t.transformer_methodology_desc_dcf

        return _t.transformer_methodology_desc_default


class NoticeBuilder:
    """Builds various notices for the executive summary."""

    @staticmethod
    def build_dcf_exclusion_notice(response: "ValuationResponseProtocol") -> Optional[str]:
        """Build DCF exclusion notice (raw passthrough — already localized upstream)."""
        return response.dcf_exclusion_reason if response.dcf_exclusion_reason else None

    @staticmethod
    def build_methodology_downgrade_notice(response: "ValuationResponseProtocol") -> Optional[str]:
        """Build methodology downgrade notice (raw passthrough — already localized upstream)."""
        return response.methodology_downgrade_reason if response.methodology_downgrade_reason else None

    @staticmethod
    def build_sme_calibration_notice(
        response: "ValuationResponseProtocol",
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
        country_code: str = "BE",
    ) -> Optional[str]:
        """Build SME calibration notice."""
        multiples = response.multiples_valuation
        if multiples and hasattr(multiples, 'sme_calibration_applied') and multiples.sme_calibration_applied:
            _t = _resolve_translations(t, locale, country_code)
            return _t.transformer_sme_calibration_notice
        return None

    @staticmethod
    def build_range_methodology_explanation(
        response: "ValuationResponseProtocol",
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
        country_code: str = "BE",
    ) -> Optional[str]:
        """Build range methodology explanation."""
        if not response.range_methodology:
            return None

        _t = _resolve_translations(t, locale, country_code)
        if response.range_methodology == 'multiple_dispersion':
            return _t.transformer_range_methodology_dispersion
        if response.range_methodology == 'confidence_spread':
            confidence_score_pct = confidence_score_percent(response.confidence_score, default=0)
            spread = 100 - confidence_score_pct
            return _t.transformer_range_methodology_confidence.format(spread=spread)
        return None


class BusinessOverviewBuilder:
    """Builds business overview section."""

    @staticmethod
    def build(
        response: "ValuationResponseProtocol",
        request: "ValuationRequestProtocol",
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
        country_code: str = "BE",
    ) -> str:
        """
        Build business overview.

        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            t: Optional pre-built ReportTranslations snapshot
            locale: Fallback locale when ``t`` is not provided

        Returns:
            Business overview string (localized).
        """
        if response.valuation_summary:
            return response.valuation_summary

        _t = _resolve_translations(t, locale, country_code)
        industry = request.industry if request.industry else _t.transformer_company_overview_industry_default
        country = request.country_code if request.country_code else _t.transformer_company_overview_country_default
        return _t.transformer_company_overview_template.format(
            company=response.company_name,
            industry=industry,
            country=country,
        )


class FinancialHighlightsBuilder:
    """Builds financial highlights section."""

    @staticmethod
    def build(
        response: "ValuationResponseProtocol",
        request: "ValuationRequestProtocol",
        get_ebitda_value_func,
        logger,
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
        country_code: str = "BE",
    ) -> str:
        """
        Build financial highlights.

        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            get_ebitda_value_func: Function to get EBITDA value
            logger: Logger instance
            t: Optional pre-built ReportTranslations snapshot
            locale: Fallback locale when ``t`` is not provided

        Returns:
            Financial highlights string (localized).
        """
        _t = _resolve_translations(t, locale, country_code)

        try:
            equity_low = (
                response.equity_value_low
                if hasattr(response, 'equity_value_low') and response.equity_value_low is not None
                else 0
            )
            equity_high = (
                response.equity_value_high
                if hasattr(response, 'equity_value_high') and response.equity_value_high is not None
                else 0
            )
            equity_mid = (
                response.equity_value_mid
                if hasattr(response, 'equity_value_mid') and response.equity_value_mid is not None
                else 0
            )

            financial_highlights = _t.transformer_fin_highlights_range.format(
                low=f"{equity_low:,.0f}",
                high=f"{equity_high:,.0f}",
                mid=f"{equity_mid:,.0f}",
            )
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(
                "Could not format equity values in financial highlights",
                extra={'error_type': type(e).__name__, 'error': str(e)},
                exc_info=False,
            )
            financial_highlights = _t.transformer_fin_highlights_range_unavailable

        ebitda_value = get_ebitda_value_func(response, request)
        if ebitda_value is not None:
            financial_highlights += _t.transformer_fin_highlights_ebitda_suffix.format(
                value=f"{ebitda_value:,.0f}"
            )

        if request.current_year_data and request.current_year_data.revenue:
            financial_highlights += _t.transformer_fin_highlights_revenue_suffix.format(
                value=f"{request.current_year_data.revenue:,.0f}"
            )

        return financial_highlights
