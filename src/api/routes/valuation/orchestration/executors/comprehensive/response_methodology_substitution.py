"""Methodology-substitution payload policy for comprehensive responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.api.routes.valuation.orchestration.executors.comprehensive.methodology_determiner import (
    _normalize_methodology_token,
)


@dataclass(frozen=True)
class SubstitutionRoute:
    requested_methodology: str
    executed_methodology: str
    reason_code: str


def _explicit_payload(
    substitution: object,
    methodology_downgrade_reason: Optional[str],
) -> Optional[dict[str, object]]:
    if isinstance(substitution, dict):
        payload = dict(substitution)
        missing_fields = payload.get("missing_fields")
        payload["missing_fields"] = (
            list(missing_fields) if isinstance(missing_fields, (list, tuple, set)) else []
        )
        payload.setdefault("details", {})
        payload.setdefault("reason", methodology_downgrade_reason)
        return payload
    return None


def _infer_execution_route(
    detailed_results: dict[str, object],
    fallback_reason: object,
    requested_token: Optional[str],
) -> SubstitutionRoute:
    if fallback_reason:
        return SubstitutionRoute(
            requested_methodology="ASSET_BASED",
            executed_methodology="MULTIPLES",
            reason_code="NAV_UNAVAILABLE",
        )

    asset_executed = not fallback_reason and not detailed_results.get("multiples_valuation")
    executed_method_raw = str(detailed_results.get("methodology") or "").upper()
    yield_executed = (not fallback_reason) and executed_method_raw == "REAL_ESTATE_YIELD"
    return SubstitutionRoute(
        requested_methodology=requested_token or "MULTIPLES",
        executed_methodology=_executed_methodology(asset_executed, yield_executed),
        reason_code=_reason_code(requested_token, asset_executed, yield_executed),
    )


def _executed_methodology(asset_executed: bool, yield_executed: bool) -> str:
    if yield_executed:
        return "REAL_ESTATE_YIELD"
    return "ASSET_BASED" if asset_executed else "MULTIPLES"


def _reason_code(
    requested_token: Optional[str],
    asset_executed: bool,
    yield_executed: bool,
) -> str:
    if yield_executed:
        return "YIELD_ROUTED"
    if asset_executed:
        return "ASSET_ROUTED"
    if requested_token == "HYBRID":
        return "DCF_EXCLUDED"
    if requested_token == "DCF":
        return "DCF_INFEASIBLE"
    if requested_token == "ASSET_BASED":
        return "NAV_UNAVAILABLE"
    return "METHOD_DOWNGRADED"


def extract_methodology_substitution_payload(
    detailed_results: dict[str, object],
    methodology_downgrade_reason: Optional[str],
    requested_methodology: Optional[object] = None,
) -> Optional[dict[str, object]]:
    """Return the canonical methodology-substitution disclosure payload."""
    if not isinstance(detailed_results, dict):
        return None

    explicit_payload = _explicit_payload(
        detailed_results.get("methodology_substitution"),
        methodology_downgrade_reason,
    )
    if explicit_payload is not None:
        return explicit_payload

    fallback_reason = detailed_results.get("asset_based_fallback_reason")
    if not fallback_reason and not methodology_downgrade_reason:
        return None

    route = _infer_execution_route(
        detailed_results,
        fallback_reason,
        _normalize_methodology_token(requested_methodology),
    )

    return {
        "requested_methodology": route.requested_methodology,
        "executed_methodology": route.executed_methodology,
        "reason": fallback_reason or methodology_downgrade_reason,
        "reason_code": route.reason_code,
        "missing_fields": [],
        "remediation": None,
        "details": {},
    }
