"""Stage logging helpers for the comprehensive valuation orchestrator."""


def comp_stage_log(
    logger: object,
    *,
    stage: str,
    phase: str,
    correlation_id: object,
    company: object = None,
    **extra: object,
) -> None:
    """Emit sparse debug breadcrumbs for post-methodology pipeline stages."""
    debug = getattr(logger, "debug", None)
    if not callable(debug):
        return
    debug(
        f"comprehensive_valuation_stage [{stage}|{phase}]",
        extra={
            "comp_stage": stage,
            "comp_phase": phase,
            "correlation_id": correlation_id,
            "company": company,
            **extra,
        },
    )
