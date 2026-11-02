"""Client presentation options for saved calculation reports."""

from __future__ import annotations

from decimal import Decimal

from src.api.schemas.stateless_report_schemas import GenerateReportRequest

from .report_context_types import ReportMap


def _apply_report_option_gates(context: ReportMap, request: GenerateReportRequest) -> None:
    context["include_ebitda_normalization_page"] = request.include_ebitda_normalization_page
    context["show_transaction_readiness_section"] = bool(
        context.get("show_transaction_readiness_section")
        and request.include_transaction_readiness_section
    )
    context["show_business_growth_maturity_section"] = bool(
        context.get("show_business_growth_maturity_section")
        and request.include_business_growth_maturity_section
    )
    context["show_growth_multiple_sensitivity"] = bool(
        context.get("show_growth_multiple_sensitivity")
        and request.include_growth_multiple_sensitivity
    )
    context["suppress_sde_cross_check"] = not request.include_sde_cross_check
    if not request.include_generic_next_steps:
        context["show_limited_scope_advisory_panel"] = False
    if not request.include_sde_cross_check:
        context["show_sde_cross_check"] = False
        context["has_sde_page"] = False
    if not request.include_attestation_page:
        context["has_attestation_page"] = False


def _apply_client_presentation_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Apply advisor wording without altering an executed valuation contract.

    The fields in this function are deliberately display-only.  Monetary values,
    method selection, benchmark flags and fallback disclosures are always
    assembled before this function runs and remain untouched.
    """
    context["suppress_engine_product_name"] = request.suppress_engine_product_name
    context["report_scope"] = request.report_scope
    context["is_sealed_advisor_memorandum"] = bool(
        request.report_scope == "advisor_memorandum" and request.publication_intent == "final"
    )
    if context["is_sealed_advisor_memorandum"]:
        # These are separately commissioned transaction-advisory work products,
        # not valuation evidence. Keep them out even when a legacy valuation
        # payload carried the corresponding display flags forward.
        context["show_sellability_section"] = False
        context["show_transaction_readiness_section"] = False
        context["show_business_growth_maturity_section"] = False
        context["has_nav_deal_structure"] = False
    context["engagement_scope"] = (
        request.engagement_scope.model_dump(mode="json")
        if request.engagement_scope is not None
        else None
    )
    context["registry_snapshot"] = (
        request.registry_snapshot.model_dump(mode="json")
        if request.registry_snapshot is not None
        else None
    )
    context["report_assurance_level"] = request.report_assurance_level
    context["scope_prohibits_customer_persistence"] = request.report_scope == "client_indicative"
    context["scope_prohibits_t4"] = request.report_scope in {
        "client_indicative",
        "automated_indicative",
    }
    context["client_delivery_verdict"] = (
        "Approved for client delivery — indicative/as-reported"
        if request.report_scope == "client_indicative"
        else None
    )
    context["client_presentation_method_label"] = request.client_presentation_method_label
    context["show_weighted_synthesis_range_on_cover"] = (
        request.show_weighted_synthesis_range_on_cover
    )
    context["client_presentation_methodology_statement"] = (
        request.client_presentation_methodology_statement
    )
    if request.client_presentation_method_label:
        context["valuation_methodology_display"] = request.client_presentation_method_label
        context["primary_method_label"] = request.client_presentation_method_label
    if request.client_presentation_methodology_statement:
        context["methodology_statement"] = request.client_presentation_methodology_statement
    if request.report_scope == "client_indicative":
        weighted = request.valuation_result.weighted_valuation
        if weighted is not None:
            weights = {
                str(row.method_key): round(float(row.weight) * 100)
                for row in weighted.contributions
                if float(row.weight) > 0
            }
            market_weight = weights.get("ebitda_multiple")
            dcf_weight = weights.get("dcf")
            if market_weight is not None and dcf_weight is not None:
                language = (request.language or "nl").lower()
                market_label = (
                    "marché"
                    if language.startswith("fr")
                    else "market" if language.startswith("en") else "markt"
                )
                context["synthesis_weight_compact"] = (
                    f"{market_weight}% {market_label} + {dcf_weight}% DCF"
                )
        # Generic buyer-package readiness is an internal workflow surface.  A
        # finished limited-scope client valuation must not expose internal
        # evidence tokens, scores or contradictory distribution gates.
        context["show_transaction_readiness_section"] = False
        _suppress_client_internal_method_artifacts(context, request)


def _suppress_client_internal_method_artifacts(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Expose only selected synthesis legs and the governed direct WACC."""

    result = request.valuation_result
    weighted = result.weighted_valuation
    allowed_method_keys = {
        str(row.method_key)
        for row in (weighted.contributions if weighted is not None else [])
        if float(row.weight) > 0
    }
    raw_results = context.get("method_results_by_key")
    if isinstance(raw_results, dict) and allowed_method_keys:
        context["method_results_by_key"] = {
            key: value for key, value in raw_results.items() if str(key) in allowed_method_keys
        }
    # The synthesis label is the product-facing methodology. Never render the
    # adaptive intermediate page or its legacy product label beside a 70/30
    # weighted report.
    context["has_upswitch_adaptive_page"] = False
    context["upswitch_adaptive_method"] = None
    context["upswitch_adaptive_value"] = None
    context["valuation_method_label"] = request.client_presentation_method_label

    dcf = result.dcf_results if isinstance(result.dcf_results, dict) else None
    contract = dcf.get("wacc_evidence_contract") if dcf else None
    if isinstance(contract, dict):
        direct_wacc = Decimal(str(contract["value_pct"])) / Decimal("100")
        context["dcf_wacc"] = float(direct_wacc)
        context["dcf_wacc_buildup"] = {
            "mode": "direct_sector_wacc",
            "wacc": direct_wacc,
            "wacc_override_applied": True,
            "component_buildup_applicable": False,
            "wacc_evidence_contract": contract,
        }
        context.pop("engine_wacc", None)
        context.pop("engine_cost_of_equity", None)
