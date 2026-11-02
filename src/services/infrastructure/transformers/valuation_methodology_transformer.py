"""
Valuation Methodology Transformer

Builds the valuation methodologies section of the valuation report.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest
    from src.services.infrastructure.translations import ReportTranslations

from src.services.infrastructure.exceptions import DataTransformationError
from src.services.infrastructure.report_confidence import confidence_score_percent
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.utils.decimal_helpers import pin_band_monotone

from .base_transformer import BaseTransformer


def _get_value(source: object, key: str, default: object = None) -> object:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _country_code_from_request(request: ValuationRequestProtocol) -> str:
    return str(getattr(request, "country_code", None) or "BE").strip().upper() or "BE"


def _resolve_translations(
    request: ValuationRequestProtocol,
    t: Optional["ReportTranslations"],
    locale: str,
) -> "ReportTranslations":
    if t is not None:
        return t

    from src.services.infrastructure.translations import get_translations, normalize_report_locale

    return get_translations(
        normalize_report_locale(locale),
        country_code=_country_code_from_request(request),
    )


def _has_current_year_revenue(request: ValuationRequestProtocol) -> bool:
    current_year_data = getattr(request, "current_year_data", None)
    return bool(current_year_data and getattr(current_year_data, "revenue", None))


def _confidence_level(confidence_score_pct: Decimal) -> str:
    if confidence_score_pct > 70:
        return "High"
    if confidence_score_pct > 50:
        return "Medium"
    return "Low"


def _build_multiples_overview_method(
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    t: "ReportTranslations",
    confidence_score_pct: Decimal,
    ebitda_value: Optional[Decimal],
) -> Optional[dict[str, object]]:
    if not response.multiples_valuation or response.multiples_weight <= 0:
        return None

    return {
        "name": t.transformer_method_label_market_multiples,
        "data_availability": (
            "High" if ebitda_value is not None or _has_current_year_revenue(request) else "Medium"
        ),
        "confidence_level": _confidence_level(confidence_score_pct),
        "weight": response.multiples_weight,
    }


def _build_dcf_overview_method(
    response: ValuationResponseProtocol,
    t: "ReportTranslations",
) -> Optional[dict[str, object]]:
    if not response.dcf_valuation or response.dcf_weight <= 0:
        return None

    return {
        "name": t.transformer_method_label_dcf,
        "data_availability": "Medium",
        "confidence_level": "Medium",
        "weight": response.dcf_weight,
    }


def _build_overview(
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    t: "ReportTranslations",
    confidence_score_pct: Decimal,
    ebitda_value: Optional[Decimal],
) -> dict[str, object]:
    methods = [
        method
        for method in (
            _build_multiples_overview_method(
                response,
                request,
                t,
                confidence_score_pct,
                ebitda_value,
            ),
            _build_dcf_overview_method(response, t),
        )
        if method is not None
    ]
    overview: dict[str, object] = {
        "description": response.methodology_notes or t.transformer_methodology_desc_default,
        "methods": methods,
    }

    if response.dcf_exclusion_reason:
        overview["dcf_exclusion_notice"] = response.dcf_exclusion_reason

    return overview


def _select_multiples_metric(
    multiples: object,
    ebitda_value: Optional[Decimal],
) -> tuple[str, object]:
    ebitda_multiple = _get_value(multiples, "ebitda_multiple")
    if ebitda_multiple and ebitda_multiple > 0 and ebitda_value is not None:
        return "EBITDA", ebitda_multiple
    return "Revenue", _get_value(multiples, "revenue_multiple")


def _stage_value(stage: object, key: str, default: object = None) -> object:
    return _get_value(stage, key, default)


def _build_waterfall_step(
    stage: object,
    current_multiple: object,
    t: "ReportTranslations",
) -> tuple[dict[str, object], object]:
    step_name = _stage_value(stage, "step_name", "Unknown")
    explanation = _stage_value(stage, "explanation")
    multiple_after = _stage_value(stage, "multiple_after")
    ev_after = _stage_value(stage, "ev_after")
    discount_percentage = _stage_value(stage, "discount_percentage")

    return (
        {
            "step_number": _stage_value(stage, "step_number"),
            "step_name": step_name,
            "multiple_before": current_multiple,
            "multiple_after": multiple_after,
            "discount_percentage": discount_percentage,
            "adjustment_percentage": discount_percentage,
            "enterprise_value": ev_after,
            "explanation": explanation
            or t.transformer_waterfall_step_default.format(step_name=step_name),
        },
        multiple_after if multiple_after is not None else current_multiple,
    )


def _build_discount_waterfall(
    multiple_pipeline: object,
    t: "ReportTranslations",
) -> Optional[dict[str, object]]:
    stages = _get_value(multiple_pipeline, "stages")
    if not multiple_pipeline or not stages:
        return None

    initial_multiple = _get_value(multiple_pipeline, "initial_multiple")
    metric_value = _get_value(multiple_pipeline, "metric_value")
    final_multiple = _get_value(multiple_pipeline, "final_multiple")
    current_multiple = initial_multiple
    waterfall_steps = []

    for stage in stages:
        step, current_multiple = _build_waterfall_step(stage, current_multiple, t)
        waterfall_steps.append(step)

    return {
        "waterfall_steps": waterfall_steps,
        "summary": {
            "base_enterprise_value": initial_multiple * metric_value,
            "total_reduction": (initial_multiple - final_multiple) * metric_value,
            "total_discount_percentage": (
                (initial_multiple - final_multiple) / initial_multiple * 100
                if initial_multiple > 0
                else 0
            ),
        },
    }


def _build_comparables_analysis(
    multiples: object,
    t: "ReportTranslations",
) -> Optional[dict[str, object]]:
    comparables_count = _get_value(multiples, "comparables_count")
    if not comparables_count:
        return None

    return {
        "count": comparables_count,
        "note": t.transformer_comparables_count_note.format(count=comparables_count),
        "has_comparables": True,
    }


def _build_multiples_breakdown(
    response: ValuationResponseProtocol,
    t: "ReportTranslations",
    ebitda_value: Optional[Decimal],
) -> Optional[dict[str, object]]:
    multiples = response.multiples_valuation
    if not multiples:
        return None

    metric_name, base_multiple = _select_multiples_metric(multiples, ebitda_value)
    primary_method = (
        t.transformer_method_label_ebitda_multiple
        if metric_name == "EBITDA"
        else t.transformer_method_label_revenue_multiple
    )
    pinned_low, pinned_mid, pinned_high = pin_band_monotone(
        response.equity_value_low,
        response.equity_value_mid,
        response.equity_value_high,
    )

    return {
        "primary_method": primary_method,
        "primary_method_explanation": t.transformer_primary_method_default.format(
            method=primary_method
        ),
        "metric_name": metric_name,
        "base_multiple": base_multiple,
        "discount_waterfall": _build_discount_waterfall(
            response.multiple_pipeline,
            t,
        ),
        "comparables_analysis": _build_comparables_analysis(multiples, t),
        "valuation_range": {
            "low": pinned_low,
            "mid": pinned_mid,
            "high": pinned_high,
        },
    }


def _build_dcf_breakdown(
    response: ValuationResponseProtocol,
) -> Optional[dict[str, object]]:
    dcf = response.dcf_valuation
    if not dcf or response.dcf_weight <= 0:
        return None

    return {
        "enterprise_value": getattr(dcf, "enterprise_value", None),
        "equity_value": getattr(dcf, "equity_value", None),
        "wacc": getattr(dcf, "wacc", None),
        "terminal_value": getattr(dcf, "terminal_value", None),
    }


def _build_method_synthesis(
    response: ValuationResponseProtocol,
    t: "ReportTranslations",
) -> dict[str, object]:
    methods = []
    if response.multiples_valuation and response.multiples_weight > 0:
        methods.append(
            {
                "name": t.transformer_method_label_market_multiples,
                "value": response.equity_value_mid,
                "weight": response.multiples_weight,
                "weighted_value": response.equity_value_mid * response.multiples_weight,
            }
        )

    if response.dcf_valuation and response.dcf_weight > 0:
        dcf_value = getattr(response.dcf_valuation, "equity_value", response.equity_value_mid)
        methods.append(
            {
                "name": t.transformer_method_label_dcf,
                "value": dcf_value,
                "weight": response.dcf_weight,
                "weighted_value": dcf_value * response.dcf_weight,
            }
        )

    is_multiple_dispersion = response.range_methodology == "multiple_dispersion"
    range_methodology = (
        {
            "is_multiple_dispersion": is_multiple_dispersion,
            "explanation": (
                t.transformer_range_methodology_dispersion_short
                if is_multiple_dispersion
                else t.transformer_range_methodology_confidence_short
            ),
            "note": (
                t.transformer_range_methodology_dispersion_note
                if is_multiple_dispersion
                else t.transformer_range_methodology_confidence_note
            ),
        }
        if response.range_methodology
        else None
    )

    return {
        "methods": methods,
        "weighted_average": response.equity_value_mid,
        "final_range": f"€{response.equity_value_low:,.0f} - €{response.equity_value_high:,.0f}",
        "range_methodology": range_methodology,
    }


class ValuationMethodologyTransformer(BaseTransformer):
    """Transformer for valuation methodologies section."""

    def transform(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
    ) -> Dict[str, Any]:
        """
        Build valuation methodologies section.

        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            t: Optional pre-built ReportTranslations snapshot
            locale: Fallback locale when ``t`` is not provided

        Returns:
            Dictionary with valuation methodologies data for template rendering

        Raises:
            MissingDataError: If required data is missing
            DataTransformationError: If transformation fails
        """
        self._validate_inputs(response, request)
        translations = _resolve_translations(request, t, locale)

        self.logger.debug(
            "Building valuation methodologies section",
            extra={
                "company_name": response.company_name,
                "valuation_id": response.valuation_id,
                "multiples_weight": response.multiples_weight,
                "dcf_weight": response.dcf_weight,
            },
        )
        confidence_score_pct = confidence_score_percent(response.confidence_score, Decimal("0"))
        ebitda_value = (
            self.get_ebitda_value(response, request) if response.multiples_valuation else None
        )
        overview = _build_overview(
            response,
            request,
            translations,
            confidence_score_pct,
            ebitda_value,
        )
        multiples_breakdown = _build_multiples_breakdown(
            response,
            translations,
            ebitda_value,
        )
        dcf_breakdown = _build_dcf_breakdown(response)
        method_synthesis = _build_method_synthesis(response, translations)

        try:
            result = {
                "overview": overview,
                "multiples_breakdown": multiples_breakdown,
                "dcf_breakdown": dcf_breakdown,
                "method_synthesis": method_synthesis,
            }

            self.logger.debug(
                "Valuation methodologies section built successfully",
                extra={
                    "company_name": response.company_name,
                    "methods_count": len(overview.get("methods", [])),
                },
            )

            return result
        except (AttributeError, TypeError, KeyError, ValueError) as e:
            self.logger.error(
                "Error building valuation methodologies section",
                extra={
                    "company_name": getattr(response, "company_name", "Unknown"),
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise DataTransformationError(
                f"Failed to build valuation methodologies: {e}",
                company_name=getattr(response, "company_name", None),
            ) from e
