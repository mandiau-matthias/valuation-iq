"""Safety-net report payload helpers for post-processing."""

from __future__ import annotations

from typing import Dict


def valuation_data_for_safety_net(response: object) -> Dict[str, object]:
    """Return a best-effort serializable valuation payload for safety-net rendering."""
    try:
        if hasattr(response, "model_dump"):
            return response.model_dump(exclude_none=False)
        if hasattr(response, "dict"):
            return response.dict(exclude_none=False)
        return dict(getattr(response, "__dict__", {}) or {})
    except Exception:
        return {}


def merge_safety_net_context(
    existing_context: object,
    safety_context: object,
) -> object:
    """Merge safety-net context into an existing report context when possible."""
    safety_ctx = safety_context or {}
    existing_ctx = existing_context or {}
    if isinstance(existing_ctx, dict) and existing_ctx:
        merged_ctx = dict(existing_ctx)
        if isinstance(safety_ctx, dict):
            merged_ctx.update(safety_ctx)
        return merged_ctx
    return safety_ctx


def apply_safety_net_payload(response: object, safety: dict[str, object]) -> None:
    """Apply safety-net report outputs to a valuation response object."""
    response.html_report = None
    response.pdf_html_report = safety.get("pdf_html_report")
    response.report_context = merge_safety_net_context(
        getattr(response, "report_context", None),
        safety.get("report_context"),
    )
