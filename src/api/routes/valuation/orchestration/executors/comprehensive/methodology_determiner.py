"""
Methodology Determiner

Determines the appropriate valuation methodology based on request preferences,
context, and DCF eligibility rules (Small Firm Effect).
"""

from typing import Optional, Tuple

from src.api.routes.valuation.orchestration.executors.comprehensive.methodology_decision_policy import (
    build_financial_context,
    build_methodology_preference,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.methodology_decision_policy import (
    extract_activity_code as _extract_activity_code,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.methodology_decision_policy import (
    normalize_activity_code as _normalize_activity_code,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.methodology_decision_policy import (
    normalize_methodology_token as _normalize_methodology_token,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.methodology_decision_policy import (
    resolve_asset_routing,
    resolve_final_methodology,
)
from src.api.schemas import ValuationRequest
from src.domain.dcf_policy import user_explicitly_configured_dcf
from src.utils.valuation_logger import ValuationLogger

# Academic provenance tracking
try:
    from src.services.academic.calculation_provenance_tracker import get_current_tracker

    ACADEMIC_TRACKING_AVAILABLE = True
except ImportError:
    ACADEMIC_TRACKING_AVAILABLE = False
    get_current_tracker = lambda: None


def _dcf_decision_note(should_calculate_dcf: bool, exclusion_reason: Optional[str]) -> str:
    if should_calculate_dcf:
        return "DCF allowed for this request"
    return (
        "DCF excluded — Small Firm Effect / Koller-Goedhart-Wessels guardrails: "
        f"{exclusion_reason or 'see exclusion reason'}"
    )


def _log_dcf_execution_decision(
    logger: ValuationLogger,
    request: ValuationRequest,
    preference: object,
    *,
    raw_request_methodology: object,
    should_calculate_dcf: bool,
    dcf_exclusion_reason: Optional[str],
    user_explicit_dcf_intent: bool,
) -> None:
    current_year_data = getattr(request, "current_year_data", None)
    logger.info(
        "🔍 DCF Execution Decision",
        extra={
            "should_calculate_dcf": should_calculate_dcf,
            "dcf_exclusion_reason": dcf_exclusion_reason,
            "revenue": getattr(current_year_data, "revenue", None),
            "use_dcf_effective": getattr(preference, "use_dcf", None),
            "effective_methodology": getattr(preference, "request_methodology", None),
            "raw_request_methodology": raw_request_methodology,
            "selected_method": getattr(preference, "selected_method", None),
            "user_explicit_dcf": user_explicit_dcf_intent,
            "note": _dcf_decision_note(should_calculate_dcf, dcf_exclusion_reason),
        },
    )


def _track_methodology_selection(
    logger: ValuationLogger,
    request: ValuationRequest,
    *,
    use_dcf: object,
    use_multiples: object,
    should_calculate_dcf: bool,
    dcf_exclusion_reason: Optional[str],
    selected_methodology: object,
    downgrade_reason: Optional[str],
) -> None:
    if not ACADEMIC_TRACKING_AVAILABLE:
        return
    tracker = get_current_tracker()
    if not tracker:
        return
    try:
        tracker.record_calculation(
            calculation_id="methodology_determination",
            inputs={
                "revenue": (
                    request.current_year_data.revenue if request.current_year_data else None
                ),
                "use_dcf": use_dcf,
                "use_multiples": use_multiples,
                "dcf_excluded": not should_calculate_dcf,
                "exclusion_reason": dcf_exclusion_reason,
            },
            outputs={
                "methodology": selected_methodology,
                "downgrade_reason": downgrade_reason,
            },
            section_name="Methodology Selection",
            step_number=0,
        )
        logger.debug("Tracked methodology determination in academic provenance")
    except (AttributeError, KeyError, TypeError, ValueError, ImportError) as e:
        logger.warning(
            f"Failed to track methodology determination: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )


def _log_final_methodology_branch(
    logger: ValuationLogger,
    *,
    final_branch: str,
    methodology: object,
    methodology_downgrade_reason: Optional[str],
    preference: object,
    dcf_exclusion_reason: Optional[str],
) -> None:
    use_dcf = getattr(preference, "use_dcf", None)
    use_multiples = getattr(preference, "use_multiples", None)
    if final_branch == "forced_hybrid":
        logger.info(
            f"✅ FORCING HYBRID METHODOLOGY | "
            f"use_dcf={use_dcf} | "
            f"use_multiples={use_multiples} | "
            f"WILL CALCULATE DYNAMIC WEIGHTS"
        )
        return
    if final_branch == "dcf_excluded_to_multiples":
        logger.info(
            f"⚠️ DCF EXCLUDED - FORCING MULTIPLES ONLY | "
            f"use_dcf={use_dcf} (ignored) | "
            f"use_multiples={use_multiples} | "
            f"exclusion_reason={dcf_exclusion_reason} | "
            f"downgrade_reason_set={methodology_downgrade_reason is not None}"
        )
        _log_preset_hybrid_exclusion(logger, preference, dcf_exclusion_reason)
        return
    if final_branch == "context_methodology":
        logger.debug("🔍 DIAGNOSTIC: Using context methodology", extra={"methodology": methodology})
        return
    if final_branch == "request_methodology":
        logger.debug(
            "🔍 DIAGNOSTIC: Using request.methodology field",
            extra={"methodology": methodology},
        )
        return
    if final_branch == "inferred_from_flags":
        logger.debug(
            "🔍 DIAGNOSTIC: Inferred methodology from flags",
            extra={
                "methodology": methodology,
                "use_dcf": use_dcf,
                "use_multiples": use_multiples,
            },
        )


def _log_preset_hybrid_exclusion(
    logger: ValuationLogger,
    preference: object,
    dcf_exclusion_reason: Optional[str],
) -> None:
    if (
        getattr(preference, "is_single_method_override", False)
        or getattr(preference, "user_weights", None)
        or getattr(preference, "selected_method_key", "") not in ("", "upswitch_adaptive")
    ):
        return
    logger.info(
        "📊 effective_execution: MULTIPLES_ONLY "
        "(Path 1 Upswitch Adaptive — preset hybrid weights not applied; DCF excluded)",
        extra={
            "selected_method": getattr(preference, "selected_method", None),
            "dcf_exclusion_reason": dcf_exclusion_reason,
        },
    )


def _log_final_methodology(
    logger: ValuationLogger,
    *,
    methodology: object,
    preference: object,
    raw_request_methodology: object,
    should_calculate_dcf: bool,
    methodology_downgrade_reason: Optional[str],
) -> None:
    logger.info(
        f"📊 Methodology: {methodology}",
        extra={
            "determined_methodology": methodology,
            "raw_request_methodology": raw_request_methodology,
            "selected_method": getattr(preference, "selected_method", None),
            "effective_use_dcf": getattr(preference, "use_dcf", None),
            "effective_use_multiples": getattr(preference, "use_multiples", None),
            "dcf_eligible": should_calculate_dcf,
            "will_execute_hybrid": methodology == "HYBRID",
            "downgrade_reason": methodology_downgrade_reason,
        },
    )


class MethodologyDeterminer:
    """
    Determines valuation methodology based on request and context.

    Methodology Selection Priority:
    1. Zero-revenue + sufficient balance sheet → ASSET_BASED
    2. Explicit or context asset-based selection → ASSET_BASED
    3. Both use_dcf and use_multiples True → HYBRID (if DCF allowed)
    4. Context methodology
    5. Explicit request.methodology field
    6. Infer from use_dcf/use_multiples flags
    """

    def __init__(self, dcf_executor, logger: Optional[ValuationLogger] = None):
        """
        Initialize methodology determiner.

        Args:
            dcf_executor: DCFExecutor instance for eligibility checking
            logger: Optional logger instance
        """
        self.dcf_executor = dcf_executor
        self.logger = logger or ValuationLogger(self.__class__.__name__)

    def determine_methodology(
        self, request: ValuationRequest, context: Optional[dict[str, object]] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Determine valuation methodology.

        Args:
            request: Valuation request
            context: Optional processing context

        Returns:
            Tuple of (methodology, methodology_downgrade_reason)
            - methodology: "HYBRID", "DCF", "MULTIPLES", etc.
            - methodology_downgrade_reason: Optional reason if methodology was downgraded
        """
        preference = build_methodology_preference(request)
        use_dcf = preference.use_dcf
        use_multiples = preference.use_multiples
        request_methodology = preference.request_methodology
        context_methodology = context.get("methodology") if context else None
        selected_method = preference.selected_method
        user_explicit_dcf_intent = user_explicitly_configured_dcf(request)

        if preference.path_log_extra is None:
            self.logger.info(preference.path_log_message)
        else:
            self.logger.info(preference.path_log_message, extra=preference.path_log_extra)

        requested_methodology_token = _normalize_methodology_token(request_methodology)
        context_methodology_token = _normalize_methodology_token(context_methodology)
        financial_context = build_financial_context(request, context)
        raw_request_methodology = getattr(request, "methodology", None)

        self.logger.debug(
            "🔍 DIAGNOSTIC: Methodology determination",
            extra={
                "context_methodology": context_methodology,
                "raw_request_methodology": raw_request_methodology,
                "effective_request_methodology": request_methodology,
                "selected_method": selected_method,
                "use_dcf": use_dcf,
                "use_multiples": use_multiples,
                "has_context": context is not None,
            },
        )

        # Check DCF exclusion BEFORE methodology selection (Small Firm Effect)
        # This prevents forcing HYBRID when DCF should be excluded
        should_calculate_dcf_precheck, dcf_exclusion_reason_precheck = (
            self.dcf_executor.should_calculate_dcf(request)
        )

        _log_dcf_execution_decision(
            self.logger,
            request,
            preference,
            raw_request_methodology=raw_request_methodology,
            should_calculate_dcf=should_calculate_dcf_precheck,
            dcf_exclusion_reason=dcf_exclusion_reason_precheck,
            user_explicit_dcf_intent=user_explicit_dcf_intent,
        )

        if getattr(preference, "selected_method_key", None) == "startup_valuation":
            methodology = "STARTUP"
            methodology_downgrade_reason = None
            self.logger.info(
                "📊 Methodology: STARTUP",
                extra={
                    "determined_methodology": methodology,
                    "selected_method": getattr(preference, "selected_method", None),
                    "effective_use_dcf": getattr(preference, "use_dcf", None),
                    "effective_use_multiples": getattr(preference, "use_multiples", None),
                    "dcf_eligible": should_calculate_dcf_precheck,
                    "will_execute_hybrid": False,
                    "downgrade_reason": methodology_downgrade_reason,
                    "reason": "startup_valuation is a standalone founder method",
                },
            )
            _track_methodology_selection(
                self.logger,
                request,
                use_dcf=use_dcf,
                use_multiples=use_multiples,
                should_calculate_dcf=should_calculate_dcf_precheck,
                dcf_exclusion_reason=dcf_exclusion_reason_precheck,
                selected_methodology=methodology,
                downgrade_reason=methodology_downgrade_reason,
            )
            return methodology, methodology_downgrade_reason

        asset_routing = resolve_asset_routing(
            financial_context,
            requested_methodology_token=requested_methodology_token,
            context_methodology_token=context_methodology_token,
        )
        if asset_routing.passthrough_log is not None:
            self.logger.info(
                asset_routing.passthrough_log.message,
                extra=asset_routing.passthrough_log.extra,
            )
        if asset_routing.decision is not None:
            methodology = asset_routing.decision.methodology
            methodology_downgrade_reason = asset_routing.decision.downgrade_reason
            self.logger.info(
                asset_routing.decision.log_message,
                extra=asset_routing.decision.log_extra,
            )
            _track_methodology_selection(
                self.logger,
                request,
                use_dcf=use_dcf,
                use_multiples=use_multiples,
                should_calculate_dcf=should_calculate_dcf_precheck,
                dcf_exclusion_reason=dcf_exclusion_reason_precheck,
                selected_methodology=methodology,
                downgrade_reason=methodology_downgrade_reason,
            )
            return methodology, methodology_downgrade_reason

        # Priority 0.5: Explicit user DCF intent overrides revenue guardrails.
        # Uses the shared dcf_policy module (single source of truth for all
        # intent signals: selected_method, user_configured_dcf, dcf_input_mode,
        # forecast_years_data, and the full business_context DCF field set).
        if not should_calculate_dcf_precheck and user_explicit_dcf_intent:
            self.logger.info(
                "✅ User explicitly configured DCF — overriding revenue guardrails → HYBRID",
                extra={
                    "selected_method": getattr(request, "selected_method", None),
                    "user_configured_dcf": getattr(request, "user_configured_dcf", None),
                },
            )
            should_calculate_dcf_precheck = True
            dcf_exclusion_reason_precheck = None

        final_decision = resolve_final_methodology(
            preference,
            context_methodology=context_methodology,
            requested_methodology_token=requested_methodology_token,
            should_calculate_dcf=should_calculate_dcf_precheck,
            dcf_exclusion_reason=dcf_exclusion_reason_precheck,
        )
        methodology = final_decision.methodology
        methodology_downgrade_reason = final_decision.downgrade_reason

        _log_final_methodology_branch(
            self.logger,
            final_branch=final_decision.branch,
            methodology=methodology,
            methodology_downgrade_reason=methodology_downgrade_reason,
            preference=preference,
            dcf_exclusion_reason=dcf_exclusion_reason_precheck,
        )
        _log_final_methodology(
            self.logger,
            methodology=methodology,
            preference=preference,
            raw_request_methodology=raw_request_methodology,
            should_calculate_dcf=should_calculate_dcf_precheck,
            methodology_downgrade_reason=methodology_downgrade_reason,
        )

        _track_methodology_selection(
            self.logger,
            request,
            use_dcf=use_dcf,
            use_multiples=use_multiples,
            should_calculate_dcf=should_calculate_dcf_precheck,
            dcf_exclusion_reason=dcf_exclusion_reason_precheck,
            selected_methodology=methodology,
            downgrade_reason=methodology_downgrade_reason,
        )

        return methodology, methodology_downgrade_reason
