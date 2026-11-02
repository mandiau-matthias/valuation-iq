"""
Owner-profiling response wiring helpers (OWNER-PROFILING-1 OP-4c).

Both `builders/response_builder.py` and
`executors/comprehensive/response_builder.py` previously hardcoded
`owner_profiling = None` and never wrote `owner_dependency_result` /
`owner_dependency_adjustment`. This module gives both call sites a single,
robust helper to extract whatever the synthesizer produced from
`detailed_results` and project it onto the response dict.

Robustness notes:
- The synthesizer may stash its result under different keys depending on the
  execution path (`synthesized_valuation`, `multiples_valuation`, or directly
  on `detailed_results`). The lookup tries each.
- We explicitly do NOT raise when the engine result is missing — the
  per-business 12-factor pipeline is still being rolled out (Mercury wizard
  ships in Sprint 2). Until factors are sent, `owner_dependency_factors=None`
  in the processor returns `(None, 0.0, ...)` and the helper just yields
  `(None, Decimal("0.0"))`.
- The helper preserves the **capped** `valuation_adjustment` and exposes the
  uncapped figure via the result's `raw_adjustment` field. Per SPIKE-1 §5.4
  the raw figure must NOT leak to clients without the "cap applied" framing;
  enforcement of that contract lives in the renderer, not here.

See: docs/product/features/active-development/owner-profiling-mvp.md §3.4.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.services.reports.protocol_adapter import coerce_json_object


def _coerce_owner_dependency_payload(candidate: Any) -> Optional[Dict[str, Any]]:
    """Return a JSON-serialisable dict for the owner-dependency result, or None.

    Handles three callers in practice:
    - a Pydantic `OwnerDependencyResult` (attribute `model_dump`)
    - a plain dict already projected upstream
    - None / sentinel values
    """
    return coerce_json_object(candidate)


def _coerce_adjustment(value: Any) -> Decimal:
    """Decimal-coerce the adjustment, falling back to 0.0 on bad input.

    Bad input here means: a Pydantic field validator at the response schema
    boundary will reject anything outside `[-0.40, 0.00]`. We absorb noise so
    a malformed upstream value does NOT take down response building; the
    result is simply "no adjustment applied" plus a log line at the call site.
    """
    if value is None:
        return Decimal("0.0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:  # pragma: no cover — Decimal coercion is permissive
        return Decimal("0.0")


def extract_owner_dependency_payload(
    detailed_results: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Decimal]:
    """Extract `(owner_dependency_result, owner_dependency_adjustment)` for the response.

    Order of precedence:
    1. Direct keys on `detailed_results` (e.g. when the orchestrator forwards
       the synthesizer output verbatim).
    2. A `synthesized_valuation` Pydantic object on `detailed_results`.
    3. A `multiples_valuation` payload that carries the fields (legacy path —
       see `comprehensive_valuation_orchestrator.py:316`).

    Returns a tuple suitable for `response_dict["owner_dependency_result"]`
    and `response_dict["owner_dependency_adjustment"]` assignment. Both
    nullable: `(None, Decimal("0.0"))` is the "no assessment" answer.
    """
    if not isinstance(detailed_results, dict):
        return None, Decimal("0.0")

    # 1. Direct keys (synthesizer may have already populated these).
    direct_result = detailed_results.get("owner_dependency_result")
    direct_adjustment = detailed_results.get("owner_dependency_adjustment")
    if direct_result is not None or direct_adjustment is not None:
        return (
            _coerce_owner_dependency_payload(direct_result),
            _coerce_adjustment(direct_adjustment),
        )

    # 2. Whole synthesized result object.
    synthesized = detailed_results.get("synthesized_valuation")
    if synthesized is not None:
        return (
            _coerce_owner_dependency_payload(
                getattr(synthesized, "owner_dependency_result", None)
            ),
            _coerce_adjustment(getattr(synthesized, "owner_dependency_adjustment", None)),
        )

    # 3. Legacy: multiples_valuation may carry the fields.
    multiples = detailed_results.get("multiples_valuation")
    if multiples is not None:
        # Multiples may be a dict OR a Pydantic model.
        if isinstance(multiples, dict):
            mr = multiples.get("owner_dependency_result")
            ma = multiples.get("owner_dependency_adjustment")
        else:
            mr = getattr(multiples, "owner_dependency_result", None)
            ma = getattr(multiples, "owner_dependency_adjustment", None)
        if mr is not None or ma is not None:
            return (
                _coerce_owner_dependency_payload(mr),
                _coerce_adjustment(ma),
            )

    return None, Decimal("0.0")


def extract_owner_risk_ledger(
    detailed_results: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Extract the M&A-grade Owner Risk Ledger for the response.

    The ledger is built post-synthesis on `SynthesizedValuation.owner_risk_ledger`
    by `synthesizer._build_owner_risk_ledger_safely`. Same precedence as the
    owner-dependency extractor (direct key → synthesized_valuation object →
    legacy multiples). Always returns a JSON-serialisable dict (or None) so
    the response schema's `Optional[Dict[str, Any]]` field validates cleanly
    and Mercury / PDF renderers consume verbatim.

    The ledger is *pure presentation metadata* — it does not affect any
    computed value — so a missing or malformed ledger NEVER raises here.
    Renderers degrade by skipping the section.
    """
    if not isinstance(detailed_results, dict):
        return None

    # 1. Direct key.
    direct = detailed_results.get("owner_risk_ledger")
    if direct is not None:
        return coerce_json_object(direct)

    # 2. SynthesizedValuation object.
    synthesized = detailed_results.get("synthesized_valuation")
    if synthesized is not None:
        candidate = getattr(synthesized, "owner_risk_ledger", None)
        if candidate is not None:
            return coerce_json_object(candidate)

    # 3. Legacy: multiples_valuation.
    multiples = detailed_results.get("multiples_valuation")
    if multiples is not None:
        if isinstance(multiples, dict):
            candidate = multiples.get("owner_risk_ledger")
        else:
            candidate = getattr(multiples, "owner_risk_ledger", None)
        if candidate is not None:
            return coerce_json_object(candidate)

    return None
