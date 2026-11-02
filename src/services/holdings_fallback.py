"""Trusted standalone disclosure emitted when Titan cannot assemble a group."""

from __future__ import annotations

from collections.abc import Mapping


def standalone_holdings_fallback(business_context: object) -> dict[str, object] | None:
    context = business_context if isinstance(business_context, Mapping) else {}
    raw = context.get("holdings_fallback_v1")
    if not isinstance(raw, Mapping):
        return None
    if (
        raw.get("contract_version") != "holdings_fallback.v1"
        or raw.get("authority") != "titan"
        or raw.get("status") != "standalone"
        or raw.get("owner_message_key") != "group_valuation_inputs_incomplete"
    ):
        return None
    stage = raw.get("stage")
    reason = raw.get("advisor_reason_code")
    if stage not in {"selection", "governance", "binding"}:
        return None
    if not isinstance(reason, str) or not reason or len(reason) > 100:
        return None
    return {
        "applied": False,
        "mode": "standalone",
        "consolidation_mode": "standalone",
        "entity_count": 1,
        "subsidiary_count": 0,
        "subsidiary_run_ids": [],
        "eliminations": {},
        "elimination_provenance": {},
        "calculation_authority": "valuation_iq",
        "fallback_disclosure": {
            "message_key": "group_valuation_inputs_incomplete",
            "stage": stage,
            "advisor_reason_code": reason,
        },
    }


__all__ = ["standalone_holdings_fallback"]
