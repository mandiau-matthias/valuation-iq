"""
SimplifiedReportTransformer - Transforms ValuationResponse to template data.

This transformer builds the context dictionary for the simplified 5-page
Jinja2 report template (main_report.html).

Design Principles:
- Single responsibility: Only transforms data, no rendering
- Clear data mapping: Each field has a documented source
- Defensive programming: Handles missing data gracefully
- Currency formatting: Uses Belgian/European locale (€)

Architecture:
    ValuationResponse + ValuationRequest
                |
                v
    SimplifiedReportTransformer.transform()
                |
                v
    TemplateContext (Jinja template context)
                |
                v
    Jinja2 render(main_report.html, context)
"""

import logging
from decimal import Decimal
from threading import Lock
from typing import Optional, Tuple

from src.api.schemas import ValuationRequest, ValuationResponse
from src.services.infrastructure import simplified_report_adaptive_context as adaptive_context
from src.services.infrastructure import simplified_report_calibration_context as calibration_context
from src.services.infrastructure.simplified_report_ebitda_context import extract_simplified_ebitda
from src.services.infrastructure.simplified_report_formatting import (
    format_currency,
    format_currency_exact,
    format_date_dutch,
    format_multiple,
    format_valuation_reference,
    safe_decimal,
)
from src.services.infrastructure.simplified_report_metric_context import (
    build_metric_presentation_context,
)
from src.services.infrastructure.simplified_report_request_context import (
    get_accountant_email,
    get_accountant_logo,
    get_accountant_name,
    get_accountant_phone,
    get_industry,
    get_industry_emoji,
    get_request_metadata,
    get_revenue,
)
from src.services.infrastructure.simplified_report_types import (
    AdjustmentData,
    CalibrationStep,
    JsonObject,
    JsonRows,
    SensitivityRow,
    TemplateContext,
)
from src.services.infrastructure.translations import (
    get_translations,
    normalize_report_locale,
    resolve_ebitda_adjustment_labels,
)
from src.services.reports.discussion_phase_signoff import build_discussion_signoff_line
from src.services.reports.ebitda_adjustments_context import build_simplified_ebitda_adjustments
from src.services.reports.ebitda_normalization import (
    compute_explicit_total_adjustments as resolve_explicit_total_adjustments,
)
from src.services.reports.ebitda_normalization import current_year_normalization_metadata
from src.services.reports.ebitda_normalization import (
    derive_normalized_ebitda as resolve_normalized_ebitda,
)
from src.services.reports.ebitda_normalization import (
    has_explicit_normalization_metadata as has_explicit_ebitda_normalization_metadata,
)
from src.services.reports.ebitda_normalization import (
    latest_year_normalized_for_display as resolve_latest_year_normalized_for_display,
)
from src.services.reports.ebitda_normalization import normalization_result_from_detailed_results
from src.services.reports.ebitda_normalization import (
    sum_signed_adjustments as sum_signed_ebitda_adjustments,
)
from src.services.reports.multi_year_ebitda_context import build_simplified_multi_year_ebitda_data
from src.services.reports.simplified_report_value_bridge import (
    build_simplified_report_value_bridge,
    get_simplified_enterprise_value,
    has_simplified_balance_inputs,
)
from src.utils.fiscal_year import resolve_display_current_year

logger = logging.getLogger(__name__)


_MISSING = object()


def _first_present_attr(obj: object, *names: str) -> object | None:
    for name in names:
        value = getattr(obj, name, _MISSING)
        if value is not _MISSING and value is not None:
            return value
    return None


# =============================================================================
# MAIN TRANSFORMER CLASS
# =============================================================================


class SimplifiedReportTransformer:
    """
    Transforms ValuationResponse + ValuationRequest into template context.

    Usage:
        transformer = SimplifiedReportTransformer()
        context = transformer.transform(response, request)
        html = jinja_env.get_template('main_report.html').render(**context)
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @staticmethod
    def _coerce_adaptive_result_dict(adaptive: object) -> Optional[JsonObject]:
        """Compatibility wrapper for adaptive result normalization tests."""
        return adaptive_context.coerce_adaptive_result_dict(adaptive)

    def _extract_upswitch_adaptive_value_for_gate(self, response: ValuationResponse) -> object:
        """Compatibility wrapper for adaptive page gate tests."""
        return adaptive_context.extract_upswitch_adaptive_value_for_gate(response)

    def _infer_sde_gate_hints(
        self,
        request: Optional[ValuationRequest],
        response: ValuationResponse,
    ) -> Tuple[str, str]:
        """Compatibility wrapper for SDE adaptive gate hinting."""
        return adaptive_context.infer_sde_gate_hints(request, response)

    def _build_adaptive_gate_context(
        self,
        request: Optional[ValuationRequest],
        response: ValuationResponse,
    ) -> TemplateContext:
        """Compatibility wrapper for adaptive gate context assembly."""
        return adaptive_context.build_adaptive_gate_context(request, response)

    def _resolve_presentation_metric_type(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        *,
        base_metric_type: str,
    ) -> str:
        """Compatibility wrapper for simplified report metric presentation."""
        return adaptive_context.resolve_presentation_metric_type(
            response,
            request,
            base_metric_type=base_metric_type,
        )

    @staticmethod
    def _sde_method_row(response: ValuationResponse) -> Optional[JsonObject]:
        """Compatibility wrapper for SDE omni result row extraction."""
        return adaptive_context.sde_method_row(response)

    def _extract_sde_basis(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> Decimal:
        """Compatibility wrapper for simplified report SDE basis extraction."""
        return adaptive_context.extract_sde_basis(response, request)

    def _user_weights_for_adaptive_gates(self, request: Optional[ValuationRequest]) -> object:
        """Compatibility wrapper for adaptive gate weight coercion."""
        return adaptive_context.user_weights_for_adaptive_gates(request)

    def _resolve_methodology_description(
        self,
        *,
        metric_type: str,
        request: Optional[ValuationRequest],
        response: ValuationResponse,
    ) -> Tuple[str, bool, bool]:
        """Compatibility wrapper for methodology copy and adaptive page flags."""
        return adaptive_context.resolve_methodology_description(
            metric_type=metric_type,
            request=request,
            response=response,
        )

    @staticmethod
    def _get_normalization_dict(detailed_results) -> dict:
        """Resolve the normalization sub-dict from detailed_results, trying multiple known keys."""
        return normalization_result_from_detailed_results(detailed_results)

    def transform(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest] = None,
    ) -> TemplateContext:
        """
        Transform response and request into template context.

        Args:
            response: Complete valuation response
            request: Original valuation request (for historical data)

        Returns:
            Dictionary with all fields needed for main_report.html
        """
        self.logger.info(
            f"Transforming report data for {response.company_name}",
            extra={"valuation_id": response.valuation_id},
        )

        # Extract core values (sustainable may be weighted; separate latest-year for display)
        ebitda, reported_ebitda, normalized_ebitda = self._extract_ebitda(response, request)
        multi_year = self._build_multi_year_data(request)
        latest_year_normalized = self._get_latest_year_normalized_for_display(
            request, reported_ebitda or Decimal("0"), multi_year
        )
        explicit_adjustments = self._compute_explicit_total_adjustments(
            request, response, reported_ebitda or Decimal("0"), latest_year_normalized
        )
        revenue = get_revenue(response, request)
        base_metric_type = self._determine_metric_type(response)
        metric_type = self._resolve_presentation_metric_type(
            response,
            request,
            base_metric_type=base_metric_type,
        )
        metric_context = build_metric_presentation_context(
            request=request,
            ebitda=ebitda,
            revenue=revenue,
            multi_year=multi_year,
            metric_type=metric_type,
            sde_basis=(
                self._extract_sde_basis(response, request) if metric_type == "SDE" else None
            ),
            request_locale=self._get_request_locale(request),
        )
        ebitda = metric_context.ebitda
        metric_type = metric_context.metric_type
        metric_value = metric_context.metric_value
        ebitda_formatted_for_display = metric_context.ebitda_formatted_for_display
        metric_basis_label = metric_context.metric_basis_label
        multiple_display_label = metric_context.multiple_display_label
        use_weighted_for_valuation = metric_context.use_weighted_for_valuation
        (
            methodology_description,
            has_upswitch_adaptive_page,
            is_adaptive_only_path,
        ) = self._resolve_methodology_description(
            metric_type=metric_type,
            request=request,
            response=response,
        )
        multiple, multiple_low, multiple_high = self._extract_multiple(response, metric_type)
        base_multiple = self._get_base_multiple(response, metric_type)

        value_bridge = build_simplified_report_value_bridge(
            response=response,
            request=request,
            metric_value=metric_value,
            multiple=multiple,
            multiple_low=multiple_low,
            multiple_high=multiple_high,
            get_request_locale=self._get_request_locale,
            logger=self.logger,
        )
        valuation_mid = value_bridge.valuation_mid
        valuation_low = value_bridge.valuation_low
        valuation_high = value_bridge.valuation_high
        multiple_low = value_bridge.multiple_low
        multiple_high = value_bridge.multiple_high
        equity_value = value_bridge.equity_value
        has_net_debt_adjustment = value_bridge.has_net_debt_adjustment
        bridge_net_debt_amount = value_bridge.bridge_net_debt_amount
        bridge_net_debt_operator = value_bridge.bridge_net_debt_operator
        bridge_uses_net_cash_label = value_bridge.bridge_uses_net_cash_label
        has_weighted_synthesis = value_bridge.has_weighted_synthesis
        synthesis_formula_display = value_bridge.synthesis_formula_display

        discussion_signoff_line = self._build_discussion_signoff_line(response, request)

        # Build context
        context = {
            # Core identification
            "valuation_id": response.valuation_id,
            "valuation_id_display": format_valuation_reference(
                getattr(response, "valuation_id", None),
                getattr(response, "valuation_date", None),
            ),
            "company_name": response.company_name,
            "generated_at": format_date_dutch(response.valuation_date),
            "current_year": self._get_current_year(response, request),
            # Valuation results
            "valuation": valuation_mid,
            "valuation_value_basis": value_bridge.value_basis,
            "formula_reconciles": value_bridge.formula_reconciles,
            "valuation_formatted": format_currency(valuation_mid),
            "valuation_low": valuation_low,
            "valuation_low_formatted": format_currency(valuation_low, show_decimals=True),
            "valuation_high": valuation_high,
            "valuation_high_formatted": format_currency(valuation_high, show_decimals=True),
            # EBITDA data
            "ebitda": ebitda,
            "ebitda_formatted": ebitda_formatted_for_display,
            "reported_ebitda": reported_ebitda,
            "reported_ebitda_formatted": format_currency(reported_ebitda),
            "latest_normalized_ebitda": latest_year_normalized,
            "latest_normalized_ebitda_formatted": format_currency(latest_year_normalized),
            "valuation_basis_ebitda": ebitda,
            # Multiple data
            "multiple": format_multiple(multiple),
            "multiple_low": format_multiple(multiple_low, decimals=1),
            "multiple_high": format_multiple(multiple_high, decimals=1),
            "base_multiple": format_multiple(base_multiple),
            "multiple_metric_type": metric_type,
            "metric_basis_label": metric_basis_label,
            "metric_basis_value": metric_value,
            "metric_basis_value_formatted": format_currency(metric_value),
            "multiple_display_label": multiple_display_label,
            "valuation_methodology_description": methodology_description,
            "has_upswitch_adaptive_page": has_upswitch_adaptive_page,
            "is_adaptive_only_path": is_adaptive_only_path,
            "has_weighted_synthesis": has_weighted_synthesis,
            "synthesis_formula_display": synthesis_formula_display,
            # Discounts
            "total_discount": format_multiple(
                (multiple - base_multiple) if multiple and base_multiple else Decimal("0"),
                decimals=2,
            ),
            # Industry/Company context
            "industry": get_industry(response, request),
            "industry_emoji": get_industry_emoji(response, request),
            "discussion_signoff_line": discussion_signoff_line,
            "revenue": revenue,
            "revenue_formatted": format_currency(revenue),
            # Accountant branding
            "accountant_firm_name": get_accountant_name(request),
            "accountant_logo_url": get_accountant_logo(request),
            "accountant_email": get_accountant_email(request),
            "accountant_phone": get_accountant_phone(request),
            # EBITDA adjustments
            "ebitda_adjustments": self._build_adjustments(
                response, request, reported_ebitda, latest_year_normalized
            ),
            "total_adjustments": explicit_adjustments,
            "total_adjustments_formatted": format_currency(explicit_adjustments),
            # Multi-year EBITDA
            "multi_year_ebitda": multi_year,
            "weighted_total_formatted": self._calculate_weighted_total_from_data(multi_year),
            "use_weighted_for_valuation": use_weighted_for_valuation,
            # Sensitivity analysis
            "sensitivity_multiple_low": format_multiple(
                multiple_low, decimals=2
            ),
            "sensitivity_multiple_high": format_multiple(
                multiple_high, decimals=2
            ),
            "sensitivity_table": self._build_sensitivity_table(
                metric_value, metric_type, multiple, multiple_low, multiple_high
            ) if value_bridge.formula_reconciles and multiple_low is not None and multiple_high is not None else [],
            # Calibration steps
            "calibration_steps": self._build_calibration_steps(
                metric_value, metric_type, base_multiple, multiple, response
            ) if value_bridge.formula_reconciles else [],
            # EV → Equity bridge (conclusion row)
            "enterprise_value_mid": value_bridge.enterprise_value_mid,
            "equity_value": equity_value,
            "has_net_debt_adjustment": has_net_debt_adjustment,
            "bridge_net_debt_amount": bridge_net_debt_amount,
            "bridge_net_debt_operator": bridge_net_debt_operator,
            "bridge_uses_net_cash_label": bridge_uses_net_cash_label,
            "bridge_evidence_status": value_bridge.bridge_evidence_status,
            "bridge_reconciliation_delta_formatted": format_currency(
                value_bridge.bridge_reconciliation_delta, show_decimals=True
            ),
        }

        self.logger.debug(
            f"Transform complete for {response.company_name}",
            extra={"context_keys": list(context.keys())},
        )

        return context

    def _build_discussion_signoff_line(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> str:
        request_metadata = get_request_metadata(request) or {}
        response_metadata = getattr(response, "metadata", None)
        if isinstance(response_metadata, dict):
            request_metadata = {**response_metadata, **request_metadata}
        discussion_locale = normalize_report_locale(self._get_request_locale(request))
        return build_discussion_signoff_line(request_metadata, discussion_locale)

    def _determine_metric_type(self, response: ValuationResponse) -> str:
        """Determine whether the simplified report should use revenue or EBITDA."""
        if response.multiples_valuation:
            primary_method = str(
                getattr(response.multiples_valuation, "primary_method", "") or ""
            ).upper()
            if "REVENUE" in primary_method:
                return "REVENUE"
        return "EBITDA"

    # =========================================================================
    # DATA EXTRACTION METHODS
    # =========================================================================

    def _extract_ebitda(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> Tuple[Decimal, Optional[Decimal], Optional[Decimal]]:
        """Compatibility wrapper for simplified EBITDA context extraction."""
        return extract_simplified_ebitda(response, request)

    def _get_current_year(
        self, response: ValuationResponse, request: Optional[ValuationRequest]
    ) -> int:
        """Resolve the accountant-facing current year from request/response data."""
        return resolve_display_current_year(request=request, response=response)

    def _get_current_year_normalization_metadata(
        self,
        request: Optional[ValuationRequest],
    ) -> JsonObject:
        """Get request-side normalization metadata for the current year."""
        return current_year_normalization_metadata(request)

    def _get_request_locale(self, request: Optional[ValuationRequest]) -> str:
        """Resolve locale from either legacy locale or stateless language fields."""
        locale = None
        if request is not None:
            locale = getattr(request, "locale", None) or getattr(request, "language", None)
        return locale if locale in {"nl", "en", "fr"} else "nl"

    def _sum_signed_adjustments(self, adjustments: object) -> Decimal:
        """Sum normalization adjustments while preserving add/subtract direction."""
        return sum_signed_ebitda_adjustments(adjustments)

    def _has_explicit_normalization_metadata(
        self,
        normalization_meta: Optional[JsonObject],
        normalized_flag: bool = False,
    ) -> bool:
        """Return True when metadata reflects a real normalization action."""
        return has_explicit_ebitda_normalization_metadata(
            normalization_meta,
            normalized_flag,
        )

    def _derive_normalized_ebitda(
        self,
        reported_ebitda: Decimal,
        normalization_meta: Optional[JsonObject],
        normalized_flag: bool = False,
    ) -> Optional[Decimal]:
        """Resolve normalized EBITDA from explicit values, totals, or raw adjustments."""
        return resolve_normalized_ebitda(
            reported_ebitda,
            normalization_meta,
            normalized_flag,
        )

    def _compute_explicit_total_adjustments(
        self,
        request: Optional[ValuationRequest],
        response: ValuationResponse,
        reported_ebitda: Decimal,
        latest_year_normalized: Decimal,
    ) -> Decimal:
        """User-only normalization total; excludes multi-year weighting effects."""
        return resolve_explicit_total_adjustments(
            request=request,
            normalization=self._get_normalization_dict(response.detailed_results),
            reported_ebitda=reported_ebitda,
            latest_year_normalized=latest_year_normalized,
        )

    def _get_latest_year_normalized_for_display(
        self,
        request: Optional[ValuationRequest],
        reported_ebitda: Decimal,
        cached_multi: Optional[JsonRows] = None,
    ) -> Decimal:
        """Latest fiscal year normalized EBITDA (single-year), not the weighted valuation basis."""
        multi = cached_multi if cached_multi is not None else self._build_multi_year_data(request)
        return resolve_latest_year_normalized_for_display(
            request=request,
            reported_ebitda=reported_ebitda,
            multi_year_data=multi,
            normalized_key="normalized",
        )

    def _extract_multiple(
        self,
        response: ValuationResponse,
        metric_type: str,
    ) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """
        Extract multiple values from response.

        Returns:
            (multiple, multiple_low, multiple_high)
        """
        multiple: Optional[Decimal] = None
        multiple_low: Optional[Decimal] = None
        multiple_high: Optional[Decimal] = None

        if metric_type == "SDE":
            row = self._sde_method_row(response)
            if row and row.get("available", True) is not False:
                mu = row.get("multiple_used")
                if mu is not None:
                    multiple = safe_decimal(mu)
                details = row.get("details") if isinstance(row.get("details"), dict) else {}
                if details.get("sde_multiple_p25") is not None:
                    multiple_low = safe_decimal(details["sde_multiple_p25"])
                if details.get("sde_multiple_p75") is not None:
                    multiple_high = safe_decimal(details["sde_multiple_p75"])
                if multiple is not None:
                    return multiple, multiple_low, multiple_high

        if response.multiples_valuation:
            mv = response.multiples_valuation
            if metric_type == "REVENUE":
                multiple = _first_present_attr(mv, "revenue_multiple", "ev_revenue_multiple")
                multiple_low = _first_present_attr(mv, "p25_revenue_multiple", "ev_revenue_p25")
                multiple_high = _first_present_attr(mv, "p75_revenue_multiple", "ev_revenue_p75")
            else:
                multiple = mv.ebitda_multiple
                multiple_low = mv.p25_ebitda_multiple
                multiple_high = mv.p75_ebitda_multiple

        # Fallback: calculate from EV / selected metric (NOT equity/metric — EV multiple = EV/metric)
        if multiple is None:
            if metric_type == "SDE":
                metric_value = self._extract_sde_basis(response, None)
            else:
                metric_value = (
                    get_revenue(response, None)
                    if metric_type == "REVENUE"
                    else self._extract_ebitda(response, None)[0]
                )
            ev = self._get_enterprise_value(response)
            if metric_value and metric_value > 0 and ev and ev > 0:
                multiple = ev / metric_value

        return multiple, multiple_low, multiple_high

    def _has_balance_inputs(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> bool:
        """Compatibility wrapper for simplified report bridge tests."""
        return has_simplified_balance_inputs(response, request)

    def _get_enterprise_value(self, response: ValuationResponse) -> Optional[Decimal]:
        """Compatibility wrapper for simplified report bridge tests."""
        return get_simplified_enterprise_value(response)

    def _get_base_multiple(self, response: ValuationResponse, metric_type: str) -> Decimal:
        """Get the base/market median multiple before discounts."""
        if metric_type == "SDE":
            row = self._sde_method_row(response)
            if row:
                details = row.get("details") if isinstance(row.get("details"), dict) else {}
                for key in ("sde_base_multiple", "base_multiple", "median_sde_multiple"):
                    b = details.get(key)
                    if b is not None:
                        return safe_decimal(b)
                mu = row.get("multiple_used")
                if mu is not None:
                    return safe_decimal(mu)
            m, _, _ = self._extract_multiple(response, metric_type)
            return m if m is not None else Decimal("2.2")

        if response.multiples_valuation:
            if metric_type == "REVENUE":
                base_revenue = _first_present_attr(
                    response.multiples_valuation,
                    "p50_revenue_multiple",
                    "ev_revenue_p50",
                )
                if base_revenue is not None:
                    return base_revenue
            elif response.multiples_valuation.p50_ebitda_multiple is not None:
                return response.multiples_valuation.p50_ebitda_multiple

        # Otherwise, use the applied multiple as base (no discounts visible)
        multiple, _, _ = self._extract_multiple(response, metric_type)
        return (
            multiple
            if multiple is not None
            else (Decimal("1.0") if metric_type == "REVENUE" else Decimal("4.0"))
        )

    # =========================================================================
    # ADJUSTMENT & NORMALIZATION METHODS
    # =========================================================================

    def _build_adjustments(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
        reported_ebitda: Optional[Decimal],
        normalized_ebitda: Optional[Decimal],
    ) -> JsonRows:
        """Build EBITDA adjustments list for template."""
        current_year = self._get_current_year(response, request)
        current_year_meta = self._get_current_year_normalization_metadata(request)
        country_code = (getattr(request, "country_code", None) or "BE") if request else "BE"
        country_code = str(country_code).strip().upper() or "BE"
        locale = self._get_request_locale(request)
        _report_loc = normalize_report_locale(locale)
        _t = get_translations(_report_loc, country_code=country_code)
        _adj = resolve_ebitda_adjustment_labels(locale, _t)
        normalization = self._get_normalization_dict(response.detailed_results)

        return build_simplified_ebitda_adjustments(
            request=request,
            reported_ebitda=reported_ebitda,
            normalized_ebitda=normalized_ebitda,
            locale=locale,
            labels=_adj,
            current_year=current_year,
            country_code=country_code,
            normalization=normalization,
            current_year_metadata=current_year_meta,
            format_currency=format_currency_exact,
        )

    def _build_multi_year_data(
        self,
        request: Optional[ValuationRequest],
    ) -> JsonRows:
        """Build multi-year EBITDA data from request."""
        if not request:
            return []

        country_code = getattr(request, "country_code", None) or "BE"
        country_code = str(country_code).strip().upper() or "BE"
        locale = self._get_request_locale(request)
        report_locale = normalize_report_locale(locale)
        translations = get_translations(report_locale, country_code=country_code)
        effective_report_year = resolve_display_current_year(request=request)
        return build_simplified_multi_year_ebitda_data(
            request=request,
            locale=locale,
            translations=translations,
            effective_report_year=effective_report_year,
            format_currency=format_currency,
            format_currency_exact=format_currency_exact,
        )

    @staticmethod
    def _row_decimal(row: JsonObject, key: str) -> Decimal:
        """Read a Decimal-valued report row field without widening row types."""
        return safe_decimal(row.get(key))

    def _get_weighted_total_numeric(
        self,
        request: Optional[ValuationRequest],
    ) -> Decimal:
        """Return numeric weighted total of multi-year EBITDA, or Decimal('0') if empty."""
        multi_year = self._build_multi_year_data(request)
        if not multi_year:
            return Decimal("0")
        return sum(self._row_decimal(row, "weighted") for row in multi_year)

    def _calculate_weighted_total(
        self,
        request: Optional[ValuationRequest],
    ) -> str:
        """Calculate weighted total of multi-year EBITDA."""
        multi_year = self._build_multi_year_data(request)
        return self._calculate_weighted_total_from_data(multi_year)

    def _calculate_weighted_total_from_data(
        self,
        multi_year: JsonRows,
    ) -> str:
        """Format weighted total from pre-built multi-year data."""
        if not multi_year:
            return "—"
        total = sum(self._row_decimal(row, "weighted") for row in multi_year)
        return format_currency_exact(total)

    # =========================================================================
    # SENSITIVITY & CALIBRATION METHODS
    # =========================================================================

    def _build_sensitivity_table(
        self,
        metric_value: Decimal,
        metric_type: str,
        multiple: Optional[Decimal],
        multiple_low: Optional[Decimal],
        multiple_high: Optional[Decimal],
    ) -> JsonRows:
        """Compatibility wrapper for simplified report sensitivity rows."""
        return calibration_context.build_sensitivity_table(
            metric_value,
            metric_type,
            multiple,
            multiple_low,
            multiple_high,
        )

    def _build_calibration_steps(
        self,
        metric_value: Decimal,
        metric_type: str,
        base_multiple: Decimal,
        final_multiple: Optional[Decimal],
        response: ValuationResponse,
    ) -> JsonRows:
        """Compatibility wrapper for simplified report calibration rows."""
        return calibration_context.build_calibration_steps(
            metric_value,
            metric_type,
            base_multiple,
            final_multiple,
            response,
        )

    def _extract_size_discount_for_calibration(self, response: ValuationResponse) -> Decimal:
        """Compatibility wrapper for simplified ledger size-discount parsing."""
        return calibration_context.extract_size_discount_for_calibration(response)


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_transformer_instance: Optional[SimplifiedReportTransformer] = None
_transformer_lock = Lock()


def get_simplified_report_transformer() -> SimplifiedReportTransformer:
    """Get or create the SimplifiedReportTransformer singleton."""
    global _transformer_instance
    if _transformer_instance is None:
        with _transformer_lock:
            if _transformer_instance is None:
                _transformer_instance = SimplifiedReportTransformer()
    return _transformer_instance
