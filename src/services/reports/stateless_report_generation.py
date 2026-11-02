"""Response assembly for the stateless generate-report endpoint."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Mapping

from fastapi import HTTPException, status

from src.api.schemas.stateless_api import GenerateReportRequest, GenerateReportResponse
from src.api.schemas.valuation_contracts import ValuationRunV2
from src.services.infrastructure.report_confidence import confidence_score_percent
from src.services.reports.report_assurance import report_assurance_projection
from src.services.reports.report_benchmark_context import build_benchmark_provenance_snapshot
from src.services.reports.stateless_calculation import utc_now_iso
from src.services.reports.stateless_priced_evidence_projection import (
    build_stateless_priced_evidence_projection,
)
from src.services.reports.stateless_report_manifest import (
    REPORT_TEMPLATE_VERSION,
    ReportContractUnavailable,
    ReportPublicationBlocked,
    build_report_manifest,
    enforce_final_publication,
    report_artifact_digests,
)
from src.services.reports.stateless_report_outputs import generate_stateless_report_outputs
from src.services.reports.valuation_assurance_status import CurrentValuationAssuranceAuthority
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _method_result(result: object, key: str) -> object | None:
    valuation_results = getattr(result, "valuation_results", None)
    if not isinstance(valuation_results, dict):
        return None
    return valuation_results.get(key)


def _method_details(result: object, key: str) -> dict[str, object]:
    method = _method_result(result, key)
    details = getattr(method, "details", None)
    return details if isinstance(details, dict) else {}


def _method_available(result: object, key: str) -> bool | None:
    method = _method_result(result, key)
    if method is None:
        return None
    return bool(getattr(method, "available", False))


def _adaptive_methodology_display(result: object) -> str:
    details = _method_details(result, "upswitch_adaptive")
    primary_basis = str(details.get("primary_basis") or "").strip().lower()
    if primary_basis == "market":
        return "Upswitch Adaptive - market approach"
    if primary_basis == "asset_based":
        return "Upswitch Adaptive - asset-based valuation"
    return str(getattr(result, "methodology_used", "") or "")


def _is_adaptive_multiples_only_result(result: object) -> bool:
    details = _method_details(result, "upswitch_adaptive")
    return str(details.get("primary_basis") or "").strip().lower() == "market"


def _is_disclosed_external_market_fallback(result: object) -> bool:
    multiples_results = getattr(result, "multiples_results", None)
    return bool(
        isinstance(multiples_results, dict)
        and multiples_results.get("multiples_source") == "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
    )


def _fallback_report_copy(request: GenerateReportRequest) -> dict[str, str]:
    multiples_results = request.valuation_result.multiples_results or {}
    business_type_id = str(
        multiples_results.get("business_type_id")
        or multiples_results.get("primary_business_type_id")
        or ""
    ).strip()
    buildup = multiples_results.get("multiple_build_up")
    segments = buildup.get("segments") if isinstance(buildup, dict) else None
    first_segment = segments[0] if isinstance(segments, list) and segments else None
    segment_title = (
        first_segment.get("business_type_title") if isinstance(first_segment, dict) else None
    )
    category_label = str(
        segment_title
        or request.business_type_label
        or request.industry
        or business_type_id.replace("_", " ").title()
        or "selected business type"
    )
    market_label = (
        business_type_id.replace("_", " ").title() if business_type_id else category_label
    )
    market_key = f"{market_label} × {request.country_code}"
    locale = (request.language or "nl").lower()
    if locale == "fr":
        return {
            "method_label": f"Référence externe {category_label} divulguée (EV/EBITDA)",
            "justification": (
                f"Référence externe {category_label} explicitement acceptée; aucun contrat "
                f"Index {market_key} résolu; DCF et les autres méthodes contribuent 0 %."
            ),
            "disclaimer": (
                "Estimation indicative fondée sur une référence externe "
                f"{category_label} divulguée; aucun contrat Index {market_key}, percentile "
                "empirique ou preuve de transaction."
            ),
        }
    if locale == "en":
        return {
            "method_label": f"Disclosed external {category_label} fallback (EV/EBITDA)",
            "justification": (
                f"Explicitly accepted external {category_label} fallback; no resolved "
                f"{market_key} Index contract; DCF and all other methods contribute 0%."
            ),
            "disclaimer": (
                f"Indicative estimate using a disclosed external {category_label} "
                f"fallback; no {market_key} Index contract, empirical percentiles, "
                "or transaction evidence."
            ),
        }
    return {
        "method_label": f"Disclosed externe {category_label}-fallback (EV/EBITDA)",
        "justification": (
            f"Uitdrukkelijk aanvaarde externe {category_label}-fallback; geen opgelost "
            f"{market_key} Index-contract; DCF en alle andere methoden dragen 0% bij."
        ),
        "disclaimer": (
            f"Indicatieve schatting met een disclosed externe {category_label}-fallback; "
            f"geen {market_key} Index-contract, empirische percentielen of transactiebewijs."
        ),
    }


def _headline_band(
    request: GenerateReportRequest,
    assurance_authority: CurrentValuationAssuranceAuthority | None = None,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if assurance_authority is not None:
        band = assurance_authority.envelope.audience_display_band
        if band.value_basis != getattr(request, "headline_value_basis", "equity_value"):
            raise ValueError("assured audience band does not match headline value basis")
        return Decimal(band.display_low), Decimal(band.display_mid), Decimal(band.display_high)
    result = request.valuation_result
    if getattr(request, "headline_value_basis", "equity_value") == "enterprise_value":
        low = result.enterprise_value_low
        mid = result.enterprise_value_mid
        high = result.enterprise_value_high
        if low is None or mid is None or high is None:
            raise ValueError("enterprise-value headline requires enterprise_value_low/mid/high")
        return low, mid, high
    return result.equity_value_low, result.equity_value_mid, result.equity_value_high


def build_stateless_report_data(
    request: GenerateReportRequest,
    *,
    generated_at: str | None = None,
    report_manifest: object = None,
    verified_assurance_authority: CurrentValuationAssuranceAuthority | None = None,
) -> dict[str, object] | None:
    """Build the optional report_data payload returned to Titan."""
    if not request.include_report_data:
        return None

    result = request.valuation_result
    methodology_display = getattr(
        request, "client_presentation_method_label", None
    ) or _adaptive_methodology_display(result)
    adaptive_details = _method_details(result, "upswitch_adaptive")
    is_adaptive_multiples_only = _is_adaptive_multiples_only_result(result)
    rd_ebitda_d = (
        Decimal(str(result.financial_metrics.get("ebitda", 0)))
        if result.financial_metrics
        else Decimal("0")
    )
    rd_ev_d = (
        Decimal(str(result.enterprise_value_mid)) if result.enterprise_value_mid else Decimal("0")
    )
    rd_effective_d = (
        (rd_ev_d / rd_ebitda_d)
        if rd_ebitda_d > 0 and rd_ev_d > 0
        else (Decimal(str(result.recommended_multiple)) if result.recommended_multiple else None)
    )
    headline_low, headline_mid, headline_high = _headline_band(
        request, verified_assurance_authority
    )
    benchmark_provenance = build_benchmark_provenance_snapshot(result.multiples_results)
    is_disclosed_fallback = _is_disclosed_external_market_fallback(result)
    fallback_copy = _fallback_report_copy(request) if is_disclosed_fallback else None
    valuation_run = (
        result.valuation_run.model_dump(mode="json") if result.valuation_run is not None else None
    )
    priced_projection_context = (
        build_stateless_priced_evidence_projection(result.valuation_run).as_report_context()
        if isinstance(result.valuation_run, ValuationRunV2)
        else {
            "priced_evidence_register": None,
            "actionable_adjustment_projection": None,
            "actionable_adjustment_lines": [],
            "show_canonical_evidence_adjustments_appendix": False,
        }
    )
    risk_factors = list(dict.fromkeys([*result.risk_factors, *request.additional_risk_factors]))
    if len(risk_factors) > 1:
        risk_factors = [
            risk
            for risk in risk_factors
            if str(risk).strip().lower() != "no major risk factors identified"
        ]

    run_source_citations = valuation_run.get("source_citations", []) if valuation_run else []
    manifest_payload = (
        report_manifest.model_dump(mode="json")
        if hasattr(report_manifest, "model_dump")
        else dict(report_manifest) if isinstance(report_manifest, Mapping) else None
    )
    resolved_report_id = (
        str(manifest_payload.get("report_id"))
        if manifest_payload and manifest_payload.get("report_id")
        else request.report_id
    )
    is_canonical_v2 = bool(
        valuation_run and valuation_run.get("schema_version") == "valuation_run.v2"
    )
    assurance_projection = report_assurance_projection(
        result.valuation_run,
        locale=request.language,
        report_scope=request.report_scope,
        assurance_authority=verified_assurance_authority,
    )
    render_contract = {
        "schema_version": "report_render_contract.v1",
        "company_name": request.company_name,
        "report_id": resolved_report_id,
        "valuation_id": result.valuation_id,
        "locale": request.language,
        "selected_method": request.selected_method,
        "headline_value_basis": request.headline_value_basis,
        "show_asking_price": request.show_asking_price,
        "equity_bridge_is_illustrative": request.equity_bridge_is_illustrative,
        "include_ebitda_normalization_page": request.include_ebitda_normalization_page,
        "include_transaction_readiness_section": request.include_transaction_readiness_section,
        "include_business_growth_maturity_section": (
            request.include_business_growth_maturity_section
        ),
        "include_growth_multiple_sensitivity": request.include_growth_multiple_sensitivity,
        "include_sde_cross_check": request.include_sde_cross_check,
        "include_attestation_page": request.include_attestation_page,
        "include_generic_next_steps": request.include_generic_next_steps,
        "fallback_reasonableness_note": request.fallback_reasonableness_note,
        "client_presentation_method_label": request.client_presentation_method_label,
        "client_presentation_methodology_statement": (
            request.client_presentation_methodology_statement
        ),
        "suppress_engine_product_name": request.suppress_engine_product_name,
        "show_weighted_synthesis_range_on_cover": (request.show_weighted_synthesis_range_on_cover),
        "report_scope": request.report_scope,
        "automatic_release_policy": (
            {
                "private_save_allowed": True,
                "export_allowed": True,
                "advisor_acceptance_required": False,
                "certification_claim": False,
            }
            if request.report_scope == "automated_indicative"
            else None
        ),
        "scope_prohibits_customer_persistence": request.report_scope == "client_indicative",
        "scope_prohibits_t4": request.report_scope in {"client_indicative", "automated_indicative"},
        "branding": request.branding.model_dump(mode="json") if request.branding else None,
        "legacy_watermark": not is_canonical_v2,
        "allow_non_share_ready_preview": False,
        "allow_degenerate_preview": False,
        "allow_non_share_ready_pdf": False,
    }

    payload = {
        "id": result.valuation_id,
        "report_id": resolved_report_id,
        "company_name": request.company_name,
        "generated_at": generated_at or utc_now_iso(),
        "valuation": float(headline_mid) if headline_mid is not None else None,
        "valuation_low": float(headline_low) if headline_low is not None else None,
        "valuation_high": float(headline_high) if headline_high is not None else None,
        "value_basis": request.headline_value_basis,
        "ebitda": float(rd_ebitda_d),
        "multiple": float(rd_effective_d) if rd_effective_d is not None else None,
        "industry": request.industry,
        "revenue": (
            float(Decimal(str(result.financial_metrics.get("revenue", 0))))
            if result.financial_metrics
            else 0
        ),
        "employee_count": request.number_of_employees,
        "founded_year": request.founding_year,
        "country_code": request.country_code,
        "methodology": methodology_display,
        "methodology_used": result.methodology_used,
        "valuation_methodology_display": methodology_display,
        "primary_method_label": methodology_display,
        "adaptive_primary_basis": adaptive_details.get("primary_basis"),
        "adaptive_methodology_justification": (
            fallback_copy["justification"]
            if fallback_copy
            else adaptive_details.get("methodology_justification")
        ),
        "methodology_statement": request.client_presentation_methodology_statement,
        "dcf_method_available": _method_available(result, "dcf"),
        "is_adaptive_multiples_only": is_adaptive_multiples_only,
        "adaptive_presentation_dcf_weight": (
            0.0 if is_adaptive_multiples_only else float(result.dcf_weight)
        ),
        "adaptive_presentation_multiples_weight": (
            1.0 if is_adaptive_multiples_only else float(result.multiples_weight)
        ),
        "confidence_level": result.confidence_level,
        "confidence_score": confidence_score_percent(result.confidence_score),
        # Honest presentation contract (BET-435) — keyed off the BET-434 data_tier.
        # Additive: surfaces (Titan cards / the report) honor `present_point_estimate`
        # to headline the range, not a false-precision point, for indicative valuations.
        "data_tier": result.data_tier,
        "data_tier_rationale": result.data_tier_rationale,
        "valuation_method_label": (
            fallback_copy["method_label"] if fallback_copy else result.valuation_method_label
        ),
        "confidence_label": result.confidence_label,
        "present_point_estimate": result.present_point_estimate,
        "valuation_disclaimer": (
            fallback_copy["disclaimer"] if fallback_copy else result.valuation_disclaimer
        ),
        "risk_factors": risk_factors[:10],
        "source_references": run_source_citations or request.source_references,
        "benchmark_provenance": benchmark_provenance,
        "benchmark_contract": (
            benchmark_provenance.get("contract") if benchmark_provenance else None
        ),
        "valuation_run": valuation_run,
        "valuation_run_id": valuation_run.get("run_id") if valuation_run else None,
        "valuation_run_hash": valuation_run.get("run_hash") if valuation_run else None,
        "value_driver_ledger": (
            result.value_driver_ledger
            or (valuation_run.get("driver_ledger") if valuation_run else None)
        ),
        "calculation_lineage": (
            valuation_run.get("calculation_lineage") if valuation_run else None
        ),
        "value_drivers": [] if is_disclosed_fallback else result.key_value_drivers,
        "fallback_source": (
            "DISCLOSED_EXTERNAL_MARKET_FALLBACK" if is_disclosed_fallback else None
        ),
        "dcf_historical_fcf_readiness": (
            result.dcf_results.get("historical_fcf_readiness") if result.dcf_results else None
        ),
        "negative_ebitda_resolution": (
            result.negative_ebitda_resolution.model_dump(mode="json")
            if result.negative_ebitda_resolution is not None
            else None
        ),
        "branding": request.branding.model_dump() if request.branding else None,
        "render_contract": render_contract,
        "client_delivery_verdict": (
            "Approved for client delivery — indicative/as-reported"
            if request.report_scope == "client_indicative"
            else None
        ),
        "report_manifest": manifest_payload,
        **priced_projection_context,
        **assurance_projection,
    }
    if request.report_scope == "automated_indicative":
        from src.services.reports.automated_indicative_policy import automatic_report_context

        run = result.valuation_run
        if not isinstance(run, ValuationRunV2):
            raise ValueError("Automatic numeric report requires valuation_run.v2")
        band = (
            run.enterprise_value_range
            if request.headline_value_basis == "enterprise_value"
            else run.valuation_range
        )
        if band is None:
            raise ValueError("Requested saved range is unavailable")
        payload.update(automatic_report_context(request.language))
        payload.update(
            {
                "valuation": str(band.mid),
                "valuation_low": str(band.low),
                "valuation_high": str(band.high),
                "currency": run.currency,
                "ebitda": run.financial_metrics.get("ebitda"),
                "revenue": run.financial_metrics.get("revenue"),
                "multiple": run.response_snapshot.get("recommended_multiple"),
                "earnings_basis_ledger": run.response_snapshot.get("earnings_basis_ledger"),
                "equity_bridge_adjustments": run.response_snapshot.get("equity_bridge_adjustments"),
                "method_results": run.method_results,
                "method_mix": run.method_mix,
                "automatic_release_policy": render_contract["automatic_release_policy"],
            }
        )
    return payload


async def generate_stateless_report_response(
    request: GenerateReportRequest,
) -> GenerateReportResponse:
    """Generate report artifacts and assemble the API response."""
    start_time = time.time()
    generated_at = utc_now_iso()

    logger.info(
        "Stateless generate-report request received",
        extra={
            "valuation_id": request.valuation_result.valuation_id,
            "include_pdf": request.include_pdf,
            "include_html": request.include_html,
            "language": request.language,
        },
    )

    try:
        verified_assurance_authority = None
        assurance_status_warning = None
        if request.valuation_assurance_envelope is not None:
            from src.services.reports.valuation_assurance_status import (
                ValuationAssuranceStatusUnavailable,
                verify_current_valuation_assurance,
            )

            run = request.valuation_result.valuation_run
            assert isinstance(run, ValuationRunV2)
            assert request.valuation_assurance_envelope_id is not None
            try:
                verified_assurance_authority = await verify_current_valuation_assurance(
                    envelope_id=request.valuation_assurance_envelope_id,
                    envelope=request.valuation_assurance_envelope,
                    run=run,
                )
            except ValuationAssuranceStatusUnavailable as exc:
                assurance_status_warning = str(exc)
                logger.warning(
                    "Titan valuation assurance is not current; rendering uncertified",
                    extra={
                        "valuation_id": request.valuation_result.valuation_id,
                        "run_hash": run.run_hash,
                        "reason": assurance_status_warning,
                    },
                )
        report_manifest = None
        try:
            report_manifest = build_report_manifest(
                request=request,
                generated_at=generated_at,
                verified_assurance_authority=verified_assurance_authority,
            )
            run = request.valuation_result.valuation_run
            if run is not None:
                enforce_final_publication(
                    report_manifest,
                    run=run,
                    assurance_authority=verified_assurance_authority,
                )
        except ReportContractUnavailable:
            resolution = request.valuation_result.negative_ebitda_resolution
            is_non_numeric_recovery_assessment = bool(
                resolution is not None
                and resolution.status == "no_going_concern_range"
                and resolution.primary_method is None
            )
            if request.publication_intent == "final" and not is_non_numeric_recovery_assessment:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "REPORT_CONTRACT_UNAVAILABLE",
                        "message": "Final report generation requires valuation_run.v2.",
                    },
                )

        report_data = build_stateless_report_data(
            request,
            generated_at=generated_at,
            report_manifest=report_manifest,
            verified_assurance_authority=verified_assurance_authority,
        )
        locale = request.language or "nl"
        report_outputs = await generate_stateless_report_outputs(
            request,
            locale=locale,
            verified_assurance_authority=verified_assurance_authority,
        )
        # Rendering can outlive Titan's five-second current-head proof. Recheck
        # after HTML/PDF construction so a revocation or supersession during
        # rendering cannot leave a certified artifact in the response. A draft
        # is re-rendered visibly uncertified; a final is blocked below.
        if verified_assurance_authority is not None:
            from src.services.reports.valuation_assurance_status import (
                ValuationAssuranceStatusUnavailable,
                verify_current_valuation_assurance,
            )

            run = request.valuation_result.valuation_run
            assert isinstance(run, ValuationRunV2)
            assert request.valuation_assurance_envelope is not None
            assert request.valuation_assurance_envelope_id is not None
            try:
                verified_assurance_authority = await verify_current_valuation_assurance(
                    envelope_id=request.valuation_assurance_envelope_id,
                    envelope=request.valuation_assurance_envelope,
                    run=run,
                )
            except ValuationAssuranceStatusUnavailable as exc:
                assurance_status_warning = str(exc)
                verified_assurance_authority = None
                logger.warning(
                    "Titan valuation assurance changed during report rendering",
                    extra={
                        "valuation_id": request.valuation_result.valuation_id,
                        "run_hash": run.run_hash,
                        "reason": assurance_status_warning,
                    },
                )
                if request.publication_intent != "final":
                    report_manifest = build_report_manifest(
                        request=request,
                        generated_at=generated_at,
                    )
                    report_data = build_stateless_report_data(
                        request,
                        generated_at=generated_at,
                        report_manifest=report_manifest,
                    )
                    report_outputs = await generate_stateless_report_outputs(
                        request,
                        locale=locale,
                    )
        generation_warnings = list(report_outputs.generation_warnings)
        if assurance_status_warning:
            generation_warnings.append(
                "Titan current assurance was unavailable; artifact is canonical_uncertified."
            )

        if report_manifest is not None:
            report_manifest = build_report_manifest(
                request=request,
                generated_at=generated_at,
                verified_assurance_authority=verified_assurance_authority,
                artifact_digests=report_artifact_digests(
                    html_report=report_outputs.html_report,
                    pdf_base64=report_outputs.pdf_base64,
                    report_payload=report_data,
                ),
                generation_warnings=generation_warnings,
                artifacts_finalized=True,
            )
            if report_data is not None:
                report_data["report_manifest"] = report_manifest.model_dump(mode="json")
            run = request.valuation_result.valuation_run
            if run is not None:
                enforce_final_publication(
                    report_manifest,
                    run=run,
                    assurance_authority=verified_assurance_authority,
                    require_artifacts=True,
                )

        elapsed_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "Stateless generate-report completed",
            extra={
                "valuation_id": request.valuation_result.valuation_id,
                "has_html": report_outputs.html_report is not None,
                "has_pdf": report_outputs.pdf_base64 is not None,
                "elapsed_ms": elapsed_ms,
            },
        )

        return GenerateReportResponse(
            valuation_id=request.valuation_result.valuation_id,
            generated_at=generated_at,
            html_report=report_outputs.html_report,
            pdf_base64=report_outputs.pdf_base64,
            report_data=report_data,
            generation_time_ms=elapsed_ms,
            template_version=REPORT_TEMPLATE_VERSION,
            report_manifest=report_manifest,
            generation_warnings=generation_warnings or None,
        )

    except ReportPublicationBlocked as exc:
        manifest = exc.manifest
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "REPORT_PUBLICATION_BLOCKED",
                "message": "The valuation may only be generated as a diagnostic or review draft.",
                "publication_status": manifest.publication_status,
                "reviewer_requirement": manifest.reviewer_requirement,
                "review_points": manifest.review_points,
                "manifest_id": manifest.manifest_id,
            },
        ) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Stateless generate-report failed",
            extra={
                "valuation_id": request.valuation_result.valuation_id,
                "error": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed. Please try again or contact support.",
        )
