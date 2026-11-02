"""Response dictionary assembly stages for comprehensive valuations."""

from __future__ import annotations

from src.api.response_currency import response_currency

from datetime import date

from src.api.routes.valuation.benchmark_contract_utils import derive_data_tier_v1
from src.api.routes.valuation.orchestration.builders.owner_profiling_response import (
    extract_owner_dependency_payload,
    extract_owner_risk_ledger,
)
from src.api.routes.valuation.orchestration.builders.post_deal_swap import compute_post_deal_swap
from src.api.routes.valuation.orchestration.executors.comprehensive.response_field_enrichment import (
    build_official_field_metadata,
    official_snapshot_is_healthy,
    resolve_methodology_name,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_value_context import (
    PreparedResponseValues,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_warning_aggregation import (
    aggregate_quality_warnings,
    ensure_method_substitution_warning,
)
from src.services.infrastructure.translations import localize_data_quality_warnings
from src.services.reports.consolidation_report_context import build_consolidation_report_context
from src.services.reports.valuation_presentation import derive_valuation_presentation


def build_base_response_dict(
    *,
    request: object,
    valuation_id: str,
    values: PreparedResponseValues,
    financial_metrics: object,
) -> dict[str, object]:
    return {
        "valuation_id": valuation_id,
        "company_name": getattr(request, "company_name", None),
        "valuation_date": date.today(),
        "currency": response_currency(request),
        "equity_value_low": values.equity_value_low,
        "equity_value_mid": values.equity_value_mid,
        "equity_value_high": values.equity_value_high,
        "recommended_asking_price": values.recommended_asking_price,
        "recommended_asking_multiple": values.recommended_asking_multiple,
        "recommended_asking_price_markup_pct": values.markup_pct,
        "recommended_asking_price_markup_source": values.markup_source,
        "recommended_asking_price_markup_reasoning": values.markup_reasoning,
        "dcf_weight": values.dcf_weight,
        "multiples_weight": values.multiples_weight,
        "financial_metrics": financial_metrics,
        "overall_confidence": values.confidence_level,
        "confidence_score": values.clamped_confidence_score,
        "current_year_data": values.current_year_data,
        "official_financials": getattr(request, "official_financials", None),
        "official_variance_analysis": getattr(request, "official_variance_analysis", None),
        "official_verification_badge": getattr(request, "official_verification_badge", None),
    }


def attach_consolidation_fields(
    response_dict: dict[str, object],
    *,
    request: object,
    detailed_results: dict[str, object],
) -> None:
    consolidation_result = detailed_results.get("holdings_consolidation")
    if not isinstance(consolidation_result, dict):
        return

    consolidation_context = consolidation_result.get("report_context")
    if not isinstance(consolidation_context, dict):
        consolidation_context = build_consolidation_report_context(
            consolidation_result,
            locale=str(getattr(request, "locale", None) or "nl"),
        )
    response_dict["holdings_consolidation"] = consolidation_result
    response_dict["consolidation_mode"] = consolidation_result.get("consolidation_mode")
    response_dict["subsidiary_run_ids"] = list(consolidation_result.get("subsidiary_run_ids") or [])
    response_dict["report_context"] = dict(consolidation_context)


def presentation_qualifiers(
    *,
    data_tier: str,
    official_financials: object,
    overall_confidence: object,
) -> list[str]:
    """Claims the confidence label must NOT make on this run.

    ``data_tier`` is value-free by design: "defensible" only says a resolved
    benchmark contract backs the multiples. It says nothing about whether the
    official filing cross-check succeeded or what the engine thinks of its own
    inputs. Left alone, the label printed *"Defensible estimate — grounded in your
    financials"* on a report whose NBB enrichment had failed and whose own
    ``overall_confidence`` was "low" — to an accountant, who reads all three.
    The tier is kept; the label stops claiming what the run did not earn.
    """
    qualifiers: list[str] = []
    if not official_snapshot_is_healthy(official_financials):
        qualifiers.append("official filing cross-check unavailable")
    if data_tier == "defensible" and str(overall_confidence or "").strip().lower() == "low":
        qualifiers.append("low engine confidence — see data quality warnings")
    return qualifiers


def attach_presentation_fields(response_dict: dict[str, object], request: object) -> None:
    data_tier, data_tier_rationale = derive_data_tier_v1(request)
    presentation = derive_valuation_presentation(data_tier)
    qualifiers = presentation_qualifiers(
        data_tier=data_tier,
        official_financials=getattr(request, "official_financials", None),
        overall_confidence=response_dict.get("overall_confidence"),
    )
    confidence_label = presentation.confidence_label
    if qualifiers:
        confidence_label = f"{confidence_label}; " + "; ".join(qualifiers)
    response_dict["data_tier"] = data_tier
    response_dict["data_tier_rationale"] = data_tier_rationale
    response_dict["valuation_method_label"] = presentation.method_label
    response_dict["confidence_label"] = confidence_label
    response_dict["confidence_label_qualifiers"] = qualifiers
    response_dict["present_point_estimate"] = presentation.present_point_estimate
    response_dict["valuation_disclaimer"] = presentation.disclaimer

    field_metadata = build_official_field_metadata(request)
    if field_metadata is not None:
        response_dict["field_metadata"] = field_metadata


def attach_methodology_label(
    response_dict: dict[str, object],
    *,
    methodology: str,
    values: PreparedResponseValues,
    logger: object,
) -> str:
    methodology_name = resolve_methodology_name(
        methodology=methodology,
        dcf_weight=response_dict["dcf_weight"],
        multiples_weight=response_dict["multiples_weight"],
        requested_dcf_only=values.requested_dcf_only,
        raw_dcf_result=values.raw_dcf_result,
    )
    response_dict["methodology"] = methodology_name
    logger.debug(
        "Methodology set",
        extra={
            "methodology": methodology_name,
            "dcf_weight": float(response_dict["dcf_weight"]),
            "multiples_weight": float(response_dict["multiples_weight"]),
        },
    )
    return methodology_name


def log_current_year_diagnostics(
    response_dict: dict[str, object],
    *,
    request: object,
    logger: object,
) -> None:
    current_year_data = response_dict.get("current_year_data", {})
    current_year_revenue = (
        current_year_data.get("revenue") if isinstance(current_year_data, dict) else None
    )
    current_year_ebitda = (
        current_year_data.get("ebitda") if isinstance(current_year_data, dict) else None
    )
    logger.debug(
        "📊 Current year data included in response (DIAGNOSTIC)",
        extra={
            "current_year_data_source": "extracted_from_step1_or_request",
            "current_year_data_type": type(current_year_data).__name__,
            "revenue": current_year_revenue,
            "ebitda": current_year_ebitda,
            "revenue_valid": current_year_revenue and current_year_revenue > 0,
            "ebitda_valid": (
                current_year_ebitda is not None and current_year_ebitda > 0
                if current_year_ebitda
                else False
            ),
            "has_request_current_year_data": bool(getattr(request, "current_year_data", None)),
            "request_revenue": _request_current_year_value(request, "revenue"),
        },
    )
    logger.debug(
        "Current year data prepared",
        extra={
            "current_year_data": response_dict.get("current_year_data"),
            "revenue": current_year_revenue,
            "ebitda": current_year_ebitda,
        },
    )


def _request_current_year_value(request: object, field_name: str) -> object:
    current_year_data = getattr(request, "current_year_data", None)
    return getattr(current_year_data, field_name, None) if current_year_data else None


def attach_nested_valuations(
    response_dict: dict[str, object],
    *,
    response_builder: object,
    detailed_results: dict[str, object],
    logger: object,
) -> None:
    dcf_valuation = response_builder.safe_create_dcf_valuation(
        detailed_results.get("dcf_valuation")
    )
    response_dict["dcf_valuation"] = dcf_valuation
    logger.debug(
        "DCF valuation created",
        extra={"dcf_valuation_exists": dcf_valuation is not None},
    )

    multiples_valuation = response_builder.safe_create_multiples_valuation(
        detailed_results.get("multiples_valuation")
    )
    response_dict["multiples_valuation"] = multiples_valuation
    logger.debug(
        "Multiples valuation created",
        extra={"multiples_valuation_exists": multiples_valuation is not None},
    )


def attach_optional_owner_fields(
    response_dict: dict[str, object],
    detailed_results: dict[str, object],
) -> None:
    response_dict["mcp_insights"] = None
    response_dict["owner_profiling"] = None
    owner_dep_result, owner_dep_adjustment = extract_owner_dependency_payload(detailed_results)
    response_dict["owner_dependency_result"] = owner_dep_result
    response_dict["owner_dependency_adjustment"] = owner_dep_adjustment
    response_dict["owner_risk_ledger"] = extract_owner_risk_ledger(detailed_results)
    response_dict["business_type_intelligence"] = None
    response_dict["monte_carlo_results"] = None


def attach_post_deal_swap(
    response_dict: dict[str, object],
    *,
    detailed_results: dict[str, object],
    request: object,
    methodology: str,
    logger: object,
) -> None:
    try:
        equity_value_mid = response_dict.get("equity_value_mid")
        if equity_value_mid is None:
            response_dict["owner_compensation_swap"] = None
            response_dict["post_deal_equity_value"] = None
            return

        swap = compute_post_deal_swap(
            detailed_results,
            pre_deal_equity_mid=equity_value_mid,
            pre_deal_equity_low=response_dict.get("equity_value_low"),
            pre_deal_equity_high=response_dict.get("equity_value_high"),
            locale=getattr(request, "locale", None),
            methodology=methodology,
            request=request,
        )
        response_dict["owner_compensation_swap"] = swap
        response_dict["post_deal_equity_value"] = swap.get("post_deal_equity_value")
    except Exception as swap_error:
        logger.warning(
            "Comprehensive post-deal swap failed; falling back to no-swap",
            extra={
                "error": str(swap_error),
                "error_type": type(swap_error).__name__,
            },
            exc_info=True,
        )
        response_dict["owner_compensation_swap"] = None
        response_dict["post_deal_equity_value"] = response_dict.get("equity_value_mid")


def attach_quality_warnings(
    response_dict: dict[str, object],
    *,
    detailed_results: dict[str, object],
    request: object,
    substitution_payload: object,
    logger: object,
) -> None:
    try:
        aggregated = aggregate_quality_warnings(detailed_results)
        aggregated = ensure_method_substitution_warning(
            aggregated,
            substitution_payload if isinstance(substitution_payload, dict) else None,
        )
        _add_integrity_warnings(aggregated, getattr(request, "metadata", None))
        response_dict["data_quality_warnings"] = _localized_quality_warnings(
            aggregated,
            request=request,
            logger=logger,
        )
    except Exception as agg_error:
        logger.warning(
            "data_quality_warnings aggregation failed (non-blocking)",
            extra={"error": str(agg_error), "error_type": type(agg_error).__name__},
        )
        response_dict["data_quality_warnings"] = []


def _add_integrity_warnings(
    aggregated: list[dict[str, object]],
    request_metadata: object,
) -> None:
    if not isinstance(request_metadata, dict):
        return
    pre_validation_warnings = request_metadata.get("_integrity_warnings")
    if not isinstance(pre_validation_warnings, list) or not pre_validation_warnings:
        return

    seen_keys = {
        (warning.get("type"), warning.get("step_number"), warning.get("message"))
        for warning in aggregated
        if isinstance(warning, dict)
    }
    for warning in pre_validation_warnings:
        if not isinstance(warning, dict):
            continue
        key = (warning.get("type"), warning.get("step_number"), warning.get("message"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        aggregated.append(dict(warning))


def _localized_quality_warnings(
    aggregated: list[dict[str, object]],
    *,
    request: object,
    logger: object,
) -> object:
    try:
        return localize_data_quality_warnings(
            aggregated,
            getattr(request, "locale", None),
            getattr(request, "country_code", None) or "BE",
        )
    except Exception as loc_error:
        logger.warning(
            "data_quality_warnings localization failed (non-blocking)",
            extra={
                "error": str(loc_error),
                "error_type": type(loc_error).__name__,
            },
        )
        return aggregated
