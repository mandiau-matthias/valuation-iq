"""Stage-aware transparent calculation breakdown context builder (BET-463).

Renders the honest, stage-graded view of how the headline range (and, from the
defensible tier onward, the point estimate) was derived. Fed by the
``stage_aware_breakdown`` payload Titan attaches to ``valuation_data`` before
calling ``/api/v1/reports/render``.

Honest-rendering invariants this builder preserves (the template formats the
numbers; this builder only decorates / coerces):

* ``display == "band_only"`` (indicative / public): the headline carries the
  band only — ``point`` is ``None`` and the template must not print a point.
* ``display == "point_and_band"`` (defensible / attested): point + band.
* The methods list is passed through **in payload order** (already
  weight-descending). Numeric values stay raw; ``value``/``contribution`` of
  ``None`` render as an em-dash in the template.
* ``reconciles_to_headline`` gates the reconciliation claim — when ``False`` the
  template shows a neutral "indicative blend" note instead. Never fabricated.

Mirrors ``report_sellability_context`` (same report-map coercion + gating
pattern) so the dict-backed render payload (``DictWrapper``) and a typed model
both flow through unchanged.
"""

from __future__ import annotations

from typing import Protocol

from src.services.reports.report_map_coercion import ReportMap, as_report_map, mapping_rows

# Whitelist of stage / tier / display tokens we recognise. Unknown tokens are
# preserved verbatim (forward-compatible: a new stage from Titan still renders)
# but the known set documents the contract.
_KNOWN_STAGES = frozenset({"public", "financials", "profiled", "listed", "deal_ready"})
_KNOWN_TIERS = frozenset({"indicative", "defensible", "attested"})
_KNOWN_DISPLAYS = frozenset({"band_only", "point_and_band"})


class StageAwareBreakdownTranslations(Protocol):
    stage_breakdown_section_title: str
    stage_breakdown_section_subtitle: str
    stage_breakdown_stage_label: str
    stage_breakdown_tier_label: str
    stage_breakdown_methods_heading: str
    stage_breakdown_weight_heading: str
    stage_breakdown_contribution_heading: str
    stage_breakdown_rationale_label: str
    stage_breakdown_caveats_label: str
    stage_breakdown_provenance_label: str
    stage_breakdown_reconciles_note: str
    stage_breakdown_indicative_blend_note: str
    stage_breakdown_no_data: str


def _opt_float(value: object) -> float | None:
    """Coerce to float, preserving ``None`` (the honest 'no value' marker)."""
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def _empty_stage_aware_breakdown_context() -> ReportMap:
    return {
        "show_stage_aware_breakdown_section": False,
        "stage_aware_breakdown": None,
    }


def _normalised_display(value: object) -> object:
    if value in _KNOWN_DISPLAYS:
        return value
    return "band_only"


def _headline_context(payload: ReportMap, *, display: object) -> ReportMap:
    headline_map = as_report_map(payload.get("headline")) or {}
    point = _opt_float(headline_map.get("point"))
    if display == "band_only":
        point = None
    return {
        "point": point,
        "low": _opt_float(headline_map.get("low")),
        "high": _opt_float(headline_map.get("high")),
    }


def _decorated_method_rows(payload: ReportMap) -> list[ReportMap]:
    decorated_methods: list[ReportMap] = []
    for method in mapping_rows(payload.get("methods")):
        weight = _opt_float(method.get("weight"))
        decorated_methods.append(
            {
                **method,
                "key": method.get("key"),
                "label": method.get("label") or method.get("key"),
                # Keep weight raw (0..1); the template applies locale-aware %
                # formatting. ``weight_pct`` is the clamped mirror for bar widths.
                "weight": weight,
                "weight_pct": _weight_pct(weight),
                "value": _opt_float(method.get("value")),
                "contribution": _opt_float(method.get("contribution")),
            }
        )
    return decorated_methods


def _weight_pct(weight: float | None) -> float | None:
    if weight is None:
        return None
    return max(0.0, min(100.0, weight * 100.0))


def _clean_optional_text(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if value is not None:
        return str(value).strip() or None
    return None


def _translation_context(t: StageAwareBreakdownTranslations) -> ReportMap:
    return {
        "section_title": t.stage_breakdown_section_title,
        "section_subtitle": t.stage_breakdown_section_subtitle,
        "stage_label": t.stage_breakdown_stage_label,
        "tier_label_heading": t.stage_breakdown_tier_label,
        "methods_heading": t.stage_breakdown_methods_heading,
        "weight_heading": t.stage_breakdown_weight_heading,
        "contribution_heading": t.stage_breakdown_contribution_heading,
        "rationale_label": t.stage_breakdown_rationale_label,
        "caveats_label": t.stage_breakdown_caveats_label,
        "provenance_label": t.stage_breakdown_provenance_label,
        "reconciles_note": t.stage_breakdown_reconciles_note,
        "indicative_blend_note": t.stage_breakdown_indicative_blend_note,
        "no_data": t.stage_breakdown_no_data,
    }


def build_stage_aware_breakdown_context(
    response: object | None,
    t: StageAwareBreakdownTranslations,
) -> ReportMap:
    """Build the transparent calculation breakdown section context (BET-463).

    Returns ``show_stage_aware_breakdown_section: bool`` plus a flat
    ``stage_aware_breakdown`` dict ready for the Jinja partial. The section is
    suppressed (byte-identical no-op) whenever the payload is absent, so legacy
    reports render unchanged.

    Number formatting stays in the template so the same context drives HTML and
    PDF without duplicating format logic here.
    """
    if response is None:
        return _empty_stage_aware_breakdown_context()

    raw = getattr(response, "stage_aware_breakdown", None)
    payload = as_report_map(raw)
    if payload is None:
        return _empty_stage_aware_breakdown_context()

    stage = payload.get("stage")
    tier = payload.get("tier")
    # Honest default: when display is unrecognised / missing, fall back to the
    # most conservative mode (band only) rather than risk printing a point we
    # were not authorised to show.
    display = _normalised_display(payload.get("display"))
    tier_label = _clean_optional_text(payload.get("tier_label"))

    return {
        "show_stage_aware_breakdown_section": True,
        "stage_aware_breakdown": {
            # Stage / tier pass through verbatim (forward-compatible). The
            # known sets gate the boolean flags below, not the raw labels.
            "stage": stage,
            "stage_is_known": stage in _KNOWN_STAGES,
            "tier": tier,
            "tier_is_known": tier in _KNOWN_TIERS,
            "tier_label": tier_label,
            "display": display,
            "headline": _headline_context(payload, display=display),
            "methods": _decorated_method_rows(payload),
            "selection_rationale": _clean_optional_text(payload.get("selection_rationale")),
            "benchmark_provenance_ids": _str_list(payload.get("benchmark_provenance_ids")),
            "caveats": _str_list(payload.get("caveats")),
            "reconciles_to_headline": bool(payload.get("reconciles_to_headline")),
            "reconciliation_delta": _opt_float(payload.get("reconciliation_delta")),
            # Localised chrome — kept on the payload so the template needs no
            # second translations object beyond ``t``.
            **_translation_context(t),
        },
    }
