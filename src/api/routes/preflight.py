"""Preflight HTTP route — Phase 1a of the defensibility-by-default plan.

Accepts an in-progress valuation_data dict (from the Mercury wizard or any
caller that holds the wizard state) and returns the **structured
defensibility report** without running the engine or producing a PDF.

Why this exists:
    The engine's full ``/calculate`` produces the full ``defensibility_report``
    on the response, but it also runs the multiples lookup, DCF compute,
    and PDF render — costly and not needed when the wizard just wants to
    know "would the engine complain about this?". The preflight surfaces:

      * input-shape warnings (BALANCE_SHEET_MISSING, OWNER_NORMALIZATION_ZERO,
        OWNER_PROFILE_SKIPPED, OWNER_PROFILE_CAP_BOUND, THIN_HISTORICAL_DATA),
      * SaaS input plausibility (validate_saas_inputs flags collapsed into
        SAAS_INPUT_VALIDATION_ERROR / _WARNING),
      * the academic + ICP scores,
      * override prompts + submit_gate recommendation,

    in a single round-trip. Engine-derived warnings (formula_mismatch,
    DCF forecast assumption warnings, methodology_downgrade) only appear
    once the user runs the full ``/calculate`` — those need the engine
    output to detect.

Co-pilot wire (Phase 3 follow-up): Mercury's ``EngineCoPilot`` calls this
on every meaningful wizard transition, then merges the structured
warnings with the FE-derived ``StudioIssue`` list. The result: the AI
assistant has the engine's complaints in scope and can act on them
*before* Submit.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from src.services.defensibility import (
    Methodology,
    build_defensibility_report,
    detect_methodology,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------


class PreflightRequest(BaseModel):
    """Flexible preflight payload — accepts any valuation_data shape.

    The Mercury wizard ships partial state; the BFF doesn't have to
    massage it into the full ValuationRequest schema. Detection is
    tolerant of missing fields by design.
    """

    model_config = ConfigDict(extra="allow")

    # The body of the wizard state — same keys the engine reads.
    # Accept arbitrary extras so the BFF can forward as-is.
    valuation_data: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "The in-progress valuation input dict. Should contain at least "
            "methodology, country_code, business_type_id, current_year_data, "
            "owner_managers, total_employees, and any optional fields the "
            "wizard has filled in (saas_input_validation business_context, "
            "owner_dependency_result, etc.)."
        ),
    )
    locale: Literal["nl", "en"] = Field(
        default="nl",
        description="Report locale for messages and remediation strings.",
    )
    run_saas_validation: bool = Field(
        default=True,
        description=(
            "Run validate_saas_inputs against valuation_data.business_context "
            "if present and merge the flags into valuation_data so they are "
            "picked up as typed warnings."
        ),
    )


class PreflightResponse(BaseModel):
    """Structured preflight envelope — same shape as the relevant slice of
    the full ``/calculate`` response, minus the engine output.

    Keys are stable; a contract test in
    ``tests/preflight/test_preflight_route.py`` pins them so renames are
    coordinated changes.
    """

    methodology: str = Field(
        description="Detected methodology — one of the Methodology enum values."
    )
    defensibility_report: Dict[str, Any] = Field(
        description=(
            "The DefensibilityReport.to_serializable() payload. Includes "
            "warnings, override_prompts, submit_gate, academic, icp."
        ),
    )
    saas_validation: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Raw validate_saas_inputs report when run_saas_validation=True "
            "and a business_context was present. None otherwise."
        ),
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


def _maybe_run_saas_validation(
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Invoke validate_saas_inputs against any business_context on the
    payload. Mutates ``data`` in-place by appending the flags to
    ``data["saas_input_validation"]`` so collect_warnings picks them up.

    Returns the raw validation report payload (for surfacing to the
    Co-pilot's Issue rail), or None when no SaaS context is present.
    """
    business_context = data.get("business_context")
    if not isinstance(business_context, dict) or not business_context:
        return None
    # Skip if no SaaS keys are present — pure non-SaaS payloads shouldn't
    # invoke a SaaS validator (it would always return an empty report).
    saas_keys = {
        "saas_arr",
        "saas_mrr",
        "saas_nrr_pct",
        "saas_churn_pct",
        "saas_customer_churn_pct",
        "saas_gross_margin_pct",
        "saas_customer_concentration_pct",
        "saas_expansion_revenue_pct",
        "saas_arr_growth_pct",
    }
    if not (saas_keys & set(business_context.keys())):
        return None
    try:
        from decimal import Decimal

        from src.domain.saas_input_validation import validate_saas_inputs

        revenue = data.get("revenue")
        try:
            revenue_dec = Decimal(str(revenue)) if revenue is not None else None
        except Exception:
            revenue_dec = None

        report = validate_saas_inputs(
            business_context=business_context,
            revenue=revenue_dec,
        )
    except Exception as e:
        logger.warning(
            "preflight: saas validation failed",
            extra={"error_type": type(e).__name__, "error": str(e)[:200]},
        )
        return None

    # Merge flags into payload so collect_warnings → SAAS_INPUT_VALIDATION_*
    # constructors fire on the typed warning surface.
    flag_payloads = [
        {
            "field": f.field,
            "code": f.code,
            "issue": f.code,
            "severity": f.severity,
            "message": f.message,
            "value": f.value,
            "expected": f.expected,
        }
        for f in report.flags
    ]
    if flag_payloads:
        existing = data.get("saas_input_validation")
        if isinstance(existing, list):
            existing.extend(flag_payloads)
        else:
            data["saas_input_validation"] = flag_payloads
    return {
        "flags": flag_payloads,
        "has_errors": report.has_errors,
        "has_warnings": report.has_warnings,
    }


@router.post(
    "/preflight/defensibility",
    response_model=PreflightResponse,
    summary="Preflight defensibility check (no engine, no PDF)",
    description=(
        "Phase 1a of the defensibility-by-default plan. Runs the structured "
        "warning detector on a partial valuation_data payload and returns "
        "the same defensibility_report envelope the full /calculate "
        "produces — without running the engine or rendering a PDF. "
        "Engine-derived warnings (formula_mismatch, DCF forecast, "
        "methodology_downgrade) only appear after a real /calculate."
    ),
)
def post_valuations_preflight(request: PreflightRequest) -> PreflightResponse:
    # Defensive copy so callers' state isn't mutated if they reuse the dict.
    data: Dict[str, Any] = dict(request.valuation_data or {})

    saas_payload: Optional[Dict[str, Any]] = None
    if request.run_saas_validation:
        saas_payload = _maybe_run_saas_validation(data)

    # detect_methodology is defensive; build_defensibility_report wraps
    # everything inside its own try/except. We still wrap to convert any
    # truly-unexpected error into a degraded-but-present payload — the
    # preflight must never 500 the wizard.
    try:
        methodology: Methodology = detect_methodology(data)
    except Exception as e:
        logger.warning(
            "preflight: methodology detection failed",
            extra={"error_type": type(e).__name__, "error": str(e)[:200]},
        )
        methodology = Methodology.UNKNOWN

    try:
        report = build_defensibility_report(data, locale=request.locale)
        defensibility_payload = report.to_serializable()
    except Exception as e:
        logger.exception(
            "preflight: build_defensibility_report failed",
            extra={"error_type": type(e).__name__, "error": str(e)[:200]},
        )
        # Degraded fallback — the preflight returns a minimal envelope so
        # the wizard's gate logic still has a structured shape to read.
        defensibility_payload = {
            "methodology": methodology.value,
            "academic": {"score": 0, "band": "insufficient", "pillars": []},
            "icp": {"score": 0, "band": "insufficient", "pillars": []},
            "warnings": [],
            "override_prompts": [],
            "submit_gate": {
                "recommendation": "warn",
                "reasons_en": ["Preflight evaluation degraded — retry."],
                "reasons_nl": ["Preflight-evaluatie gedegradeerd — probeer opnieuw."],
                "reasons_fr": ["La vérification préalable n’a pas abouti. Réessayez."],
            },
            "auto_watermark": True,
            "confidence_cap": 1.0,
            "is_full_report": False,
        }

    return PreflightResponse(
        methodology=methodology.value,
        defensibility_report=defensibility_payload,
        saas_validation=saas_payload,
    )
