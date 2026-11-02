"""DCF-eligibility headline guardrail.

When an advisor force-includes a DCF leg in a weighted synthesis on a business
the engine's own eligibility gate rejected (revenue below the method threshold
and/or insufficient historical years), the blended value is not a defensible
*primary* headline — it can sit multiples above the market evidence purely on a
forecast the engine declined to run.

This module owns the pure detection used by the report headline layer to pin the
headline to the standalone market (multiples) leg and surface the blend as a
clearly-labelled advisor scenario instead. Detection is deliberately
fail-safe: when the eligibility signal is absent the guardrail does NOT fire, so
a legitimate hybrid (eligible DCF) keeps the blended headline unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Optional


def _items(contributions: object) -> list[object]:
    data = getattr(contributions, "_data", None)
    if isinstance(data, dict):
        return list(data.values())
    if isinstance(contributions, Mapping):
        return list(contributions.values())
    if isinstance(contributions, (list, tuple)):
        return list(contributions)
    return []


def _get(obj: object, key: str) -> object:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _is_dcf_method_key(value: object) -> bool:
    return str(value or "").strip().lower() in {"dcf", "discounted_cash_flow", "dcf_valuation"}


def _positive_weight(value: object) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def synthesis_includes_dcf_leg(weighted_synthesis_payload: object) -> bool:
    """True when the weighted synthesis carries a DCF contribution with weight > 0."""
    if not weighted_synthesis_payload:
        return False
    contributions = _get(weighted_synthesis_payload, "contributions")
    for contribution in _items(contributions):
        if _is_dcf_method_key(_get(contribution, "method_key")) and _positive_weight(
            _get(contribution, "weight")
        ):
            return True
    return False


# The engine excludes the DCF below this revenue for SME profiles (Koller/Trugman):
# "Revenue below €5M threshold (DCF not reliable for small companies)". Used as a
# documented fallback ONLY when the structured eligibility verdict is unreachable.
DCF_REVENUE_FLOOR = 5_000_000


def _verdict_says_ineligible(obj: object) -> Optional[str]:
    """Read a DCF-ineligibility verdict off one result object, if present.

    A hybrid that FORCE-RAN the DCF reports ``dcf_exclusion_reason: null`` at the
    top level (the DCF was not "excluded" — it executed). The engine's actual
    eligibility verdict for the profile lives one level down, on the multiples-leg
    step-0 result (``dcf_eligible: False`` + the revenue/history reason). So this
    is applied to the response AND its multiples sub-result.
    """
    if obj is None:
        return None
    reason = _get(obj, "dcf_exclusion_reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    if _get(obj, "dcf_eligible") is False:
        return "DCF not eligible for this profile"
    detailed = _get(obj, "detailed_results")
    if isinstance(detailed, Mapping):
        detail_reason = detailed.get("dcf_exclusion_reason")
        if isinstance(detail_reason, str) and detail_reason.strip():
            return detail_reason.strip()
        if detailed.get("dcf_eligible") is False:
            return "DCF not eligible for this profile"
    return None


def dcf_excluded_reason(response: object) -> Optional[str]:
    """Return the engine's DCF-ineligibility reason if one is present, else None.

    Checks every surface the verdict is known to land on, in priority order, so the
    guardrail still fires on a force-run hybrid (where the top-level reason is null):
      * top-level ``methodology_downgrade_reason`` (engine swapped methods);
      * the response itself (``dcf_exclusion_reason`` / ``dcf_eligible is False``);
      * the multiples-leg sub-result, where Step-0 records the real verdict —
        ``multiples_valuation`` then ``multiples_results``.
    """
    reason = _get(response, "methodology_downgrade_reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()

    for surface in (response, _get(response, "multiples_valuation"), _get(response, "multiples_results")):
        verdict = _verdict_says_ineligible(surface)
        if verdict is not None:
            return verdict
    return None


def _to_float(value: object) -> Optional[float]:
    try:
        return float(value)  # tolerates Decimal/str/int
    except (TypeError, ValueError):
        return None


def _explicitly_eligible(response: object) -> bool:
    """True when the engine explicitly recorded ``dcf_eligible: True`` anywhere.

    Lets a business-type with a lower DCF revenue threshold (eligible below €5M)
    keep its blended headline — the revenue-floor fallback must never override an
    affirmative eligibility verdict.
    """
    for surface in (response, _get(response, "multiples_valuation"), _get(response, "multiples_results")):
        if surface is None:
            continue
        if _get(surface, "dcf_eligible") is True:
            return True
        detailed = _get(surface, "detailed_results")
        if isinstance(detailed, Mapping) and detailed.get("dcf_eligible") is True:
            return True

    # A governed advisor dossier can explicitly clear the DCF leg in the
    # calculation run even when the generic SME multiples pre-check retains its
    # default revenue-floor verdict.  The method-mix verdict is the more specific
    # decision for that calculation and must therefore take precedence over the
    # report-layer fallback heuristic.
    valuation_run = _get(response, "valuation_run")
    method_mix = _get(valuation_run, "method_mix")
    for method in _items(method_mix):
        method_key = _get(method, "method") or _get(method, "method_key")
        if _is_dcf_method_key(method_key) and _get(method, "eligible") is True:
            return True
    return False


def _revenue_below_dcf_floor(response: object) -> bool:
    """Documented fallback: the analysed revenue is below the engine's DCF floor.

    Only consulted when the structured eligibility verdict is unreachable. Reads
    the revenue off the response's known carriers; returns False (fail-safe) if no
    revenue is found rather than guessing.
    """
    for carrier_key in (None, "financial_metrics", "normalized_financials", "company_financials"):
        carrier = response if carrier_key is None else _get(response, carrier_key)
        if carrier is None:
            continue
        revenue = _to_float(_get(carrier, "revenue"))
        if revenue is not None and revenue > 0:
            return revenue < DCF_REVENUE_FLOOR
    return False


def is_dcf_ineligible_forced_blend(
    response: object,
    weighted_synthesis_payload: object,
) -> bool:
    """True when a weighted synthesis blends in a DCF the engine deemed ineligible.

    Requires:
      1. a weighted-synthesis payload (a blend exists),
      2. a DCF leg with positive weight in that blend, and
      3. an ineligibility signal — the engine's structured verdict (preferred,
         business-type-aware) OR, as a documented fallback, revenue below the DCF
         floor.

    Fail-safe: no DCF leg or no ineligibility signal -> ``False`` -> headline
    untouched (a legitimate, eligible hybrid keeps its blended headline).
    """
    if not weighted_synthesis_payload:
        return False
    if not synthesis_includes_dcf_leg(weighted_synthesis_payload):
        return False
    if dcf_excluded_reason(response) is not None:
        return True
    if _explicitly_eligible(response):
        # Engine affirmatively cleared the DCF (e.g. a lower-threshold profile) —
        # respect it; the revenue floor must not demote a legitimate hybrid.
        return False
    return _revenue_below_dcf_floor(response)
