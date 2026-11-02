"""
Unified DCF Policy — Single Source of Truth

Centralises the "should we run DCF?" decision so that DCFExecutor,
MethodologyEligibilityDecider, and MethodologyDeterminer all share
the same user-intent detection and business_context key list.

Before this module, three files maintained near-identical copies of
the intent-detection logic with drifting key lists. This module
eliminates that duplication.
"""

from collections.abc import Mapping, Sized

DCF_BUSINESS_CONTEXT_KEYS: tuple[str, ...] = (
    "dcf_wacc_pct",
    "dcf_terminal_growth_pct",
    "dcf_exit_multiple",
    "dcf_capex_pct",
    "dcf_da_pct",
    "dcf_nwc_pct",
    "dcf_tax_rate_pct",
    "dcf_revenue_growth_pct",
    "dcf_ebitda_margin_pct",
)


def user_explicitly_configured_dcf(request: object) -> bool:
    """
    Detect explicit user intent to run DCF, regardless of revenue guardrails.

    A single signal is sufficient:
    - ``selected_method`` contains 'dcf'  (Adaptive Valuation UI)
    - ``user_configured_dcf`` flag set by the frontend (explicit advisor intent)
    - ``dcf_input_mode`` is ``fcff_only``  (direct FCFF entry)
    - ``user_weights`` assigns weight to DCF (Waarderingssynthese)
    - ``business_context`` exit multiple, year-end discounting, or tax-shield schedule
    """
    selected = getattr(request, "selected_method", None)
    if selected and "dcf" in str(selected).lower():
        return True

    if getattr(request, "user_configured_dcf", False):
        return True

    if getattr(request, "dcf_input_mode", None) == "fcff_only":
        return True

    user_weights = getattr(request, "user_weights", None)
    if isinstance(user_weights, Mapping):
        for key, raw in user_weights.items():
            try:
                weight = float(raw)
            except (TypeError, ValueError):
                continue
            if "dcf" in str(key).lower() and weight > 0:
                return True

    bc = getattr(request, "business_context", None)
    if isinstance(bc, Mapping):
        if bc.get("dcf_exit_multiple") is not None:
            return True
        if bc.get("dcf_discounting_convention") == "year_end":
            return True
        shields = bc.get("dcf_tax_shield_projections")
        if isinstance(shields, Sized) and len(shields) > 0:
            return True

    return False


def dcf_history_exclusion_reason(request: object) -> str | None:
    """Apply Step 0's existing minimum of two historical actuals to every path."""
    historical = [year for year in (getattr(request, "historical_years_data", None) or [])
                  if getattr(year, "is_forecast", False) is not True]
    if len(historical) < 2:
        return f"Historical data {len(historical)} years below 2 years minimum"
    return None
