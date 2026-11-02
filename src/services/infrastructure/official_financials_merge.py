"""
Official filing trust merge helpers for report aggregation.

**Scope:** Used only by ``MainReportDataAggregator`` when building server-rendered
HTML/PDF report context (synchronous, single request thread). No shared mutable
state across requests, no client/browser concurrency — "SSR" report pipeline only.

**Ordering (later overlays earlier):**
1. ``response.official_financials`` then ``request.official_financials`` (candidates)
2. Top-level ``official_variance_analysis`` / ``official_verification_badge`` on request, then response
3. ``response.report_context`` (persisted snapshot) last

Separation of concerns: numeric filing fields vs trust dicts stay in the aggregator;
this module only implements deterministic dict overlay rules.
"""

from __future__ import annotations

from typing import cast

TrustPayload = dict[str, object]


def _as_trust_payload(value: object) -> TrustPayload | None:
    if not isinstance(value, dict):
        return None
    return cast(TrustPayload, value)


def overlay_trust_dict(
    prior: object,
    incoming: object,
) -> TrustPayload | None:
    """
    Shallow merge: *incoming* overlays *prior*; keys on *incoming* win on collision.

    ``incoming`` may be ``None`` to mean "no new data" (``prior`` unchanged).
    """
    prior_payload = _as_trust_payload(prior)
    incoming_payload = _as_trust_payload(incoming)
    if incoming_payload is None:
        return prior_payload
    if prior_payload is None:
        return dict(incoming_payload)
    return {**prior_payload, **incoming_payload}


def merge_nested_and_root_trust(
    nested: object,
    root_sibling: object,
) -> TrustPayload | None:
    """
    Combine nested payload (e.g. ``official_financials["variance_analysis"]``) with
    a sibling key on the same object (e.g. ``official_variance_analysis``).
    Root sibling overlays nested keys on collision.
    """
    nested_payload = _as_trust_payload(nested)
    root_payload = _as_trust_payload(root_sibling)
    if nested_payload is not None and root_payload is not None:
        return {**nested_payload, **root_payload}
    if root_payload is not None:
        return dict(root_payload)
    if nested_payload is not None:
        return dict(nested_payload)
    return None


def apply_trust_overlay(
    prior: object,
    nested: object,
    root_sibling: object,
) -> TrustPayload | None:
    """Merge nested + root for one payload, then overlay onto *prior* (cross-candidate merge)."""
    merged = merge_nested_and_root_trust(nested, root_sibling)
    return overlay_trust_dict(prior, merged)
