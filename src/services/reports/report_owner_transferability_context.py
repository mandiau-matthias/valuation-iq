"""Transferability v2 report-context projection helpers."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TypeAlias, cast

from src.services.reports.report_owner_transferability_labels import (
    CITATION_DISPLAY_INDEX as _CITATION_DISPLAY_INDEX,
)
from src.services.reports.report_owner_transferability_labels import (
    METHOD_CITATION_IDS as _METHOD_CITATION_IDS,
)
from src.services.reports.report_owner_transferability_labels import (
    METHOD_LABEL_T_KEYS as _METHOD_LABEL_T_KEYS,
)
from src.services.reports.report_owner_transferability_labels import (
    METHOD_RATIONALE_T_KEYS as _METHOD_RATIONALE_T_KEYS,
)
from src.services.reports.report_owner_transferability_labels import (
    citation_id_for as _citation_id_for,
)
from src.services.reports.report_owner_transferability_labels import (
    infer_equity_from_rationale as _infer_equity_from_rationale,
)
from src.services.reports.report_owner_transferability_labels import (
    localise_cascade as _localise_cascade,
)
from src.services.reports.report_owner_transferability_labels import (
    localize_buyer_archetype as _localize_buyer_archetype,
)
from src.services.reports.report_owner_transferability_labels import (
    localize_buyer_rationale as _localize_buyer_rationale,
)
from src.services.reports.report_owner_transferability_labels import (
    localize_gap_summary as _localize_gap_summary,
)
from src.services.reports.report_owner_transferability_labels import (
    localize_sme_segment as _localize_sme_segment,
)
from src.services.reports.report_owner_transferability_labels import (
    localize_subfactor_label as _localize_subfactor_label,
)

JsonMap: TypeAlias = dict[str, object]
StringMap: TypeAlias = dict[str, str]

_LAYER_ORDER = ("decomposition", "buyer_profile", "incidence", "severity")
_LAYER_T_KEYS = {
    "decomposition": "owner_profiling_methodology_layer_decomposition",
    "buyer_profile": "owner_profiling_methodology_layer_buyer_profile",
    "incidence": "owner_profiling_methodology_layer_incidence",
    "severity": "owner_profiling_methodology_layer_severity",
}


@dataclass(frozen=True)
class _LocalizedTransferability:
    archetype: object
    archetype_label: object
    sme_segment: object
    buyer_rationale: object
    weakest_label: object
    gap_summary: object


@dataclass(frozen=True)
class _CitationContext:
    rows: list[JsonMap]
    groups: list[JsonMap]


def normalize_transferability_profile(odr: object) -> Mapping[str, object] | None:
    if odr is None:
        return None
    raw_profile = odr.get("transferability_profile") if isinstance(odr, Mapping) else None
    if raw_profile is None and not isinstance(odr, Mapping):
        raw_profile = getattr(odr, "transferability_profile", None)
    if not raw_profile:
        return None
    if isinstance(raw_profile, Mapping):
        return cast(Mapping[str, object], raw_profile)
    try:
        dumped = raw_profile.model_dump()
    except (AttributeError, TypeError):
        return None
    return cast(Mapping[str, object], dumped) if isinstance(dumped, Mapping) else None


def build_transferability_profile_context(
    profile: Mapping[str, object],
    t: object,
) -> JsonMap:
    decomposition = _mapping_or_empty(profile.get("decomposition"))
    sub_factors = _sequence_or_empty(decomposition.get("sub_factors"))
    buyer_profile = _mapping_or_empty(profile.get("buyer_profile"))
    gap = _mapping_or_empty(profile.get("gap"))
    method_incidence = _sequence_or_empty(profile.get("method_incidence"))
    cascade = _sequence_or_empty(profile.get("narrative_cascade"))
    cascade_data = _sequence_or_empty(profile.get("cascade_data"))
    confidence = _mapping_or_empty(profile.get("confidence"))
    citations = _sequence_or_empty(profile.get("methodology_citations"))

    localized = _localized_transferability(
        buyer_profile=buyer_profile,
        decomposition=decomposition,
        gap=gap,
        t=t,
    )
    citation_context = _citation_context(citations=citations, t=t)
    return {
        "decomposition": {
            "sub_factors": _sub_factor_rows(sub_factors=sub_factors, t=t),
            "weakest_key": decomposition.get("weakest_key"),
            "strongest_key": decomposition.get("strongest_key"),
        },
        "buyer_profile": _buyer_profile_context(
            buyer_profile=buyer_profile,
            localized=localized,
        ),
        "gap": _gap_context(gap=gap, summary=localized.gap_summary),
        "narrative_cascade": _narrative_cascade(
            cascade=cascade,
            cascade_data=cascade_data,
            gap=gap,
            localized=localized,
            t=t,
        ),
        "method_incidence": _method_rows(method_incidence=method_incidence, t=t),
        "blended_applied_pct": _pct_float(profile.get("blended_applied_pct")),
        "confidence": _confidence_context(confidence),
        "methodology_citations": citation_context.rows,
        "methodology_citation_groups": citation_context.groups,
    }


def _localized_transferability(
    *,
    buyer_profile: Mapping[str, object],
    decomposition: Mapping[str, object],
    gap: Mapping[str, object],
    t: object,
) -> _LocalizedTransferability:
    archetype = buyer_profile.get("archetype")
    equity_for_rationale = _infer_equity_from_rationale(buyer_profile.get("rationale"))
    return _LocalizedTransferability(
        archetype=archetype,
        archetype_label=_localize_buyer_archetype(archetype, t),
        sme_segment=_localize_sme_segment(archetype, buyer_profile.get("eu_sme_segment"), t),
        buyer_rationale=_localize_buyer_rationale(archetype, equity_for_rationale, t)
        or buyer_profile.get("rationale")
        or "",
        weakest_label=_localize_subfactor_label(decomposition.get("weakest_key"), None, t),
        gap_summary=_localize_gap_summary(gap, t) or gap.get("gap_summary") or "",
    )


def _buyer_profile_context(
    *,
    buyer_profile: Mapping[str, object],
    localized: _LocalizedTransferability,
) -> JsonMap:
    return {
        "archetype": buyer_profile.get("archetype"),
        "archetype_label": localized.archetype_label,
        "expected_hours_per_week": buyer_profile.get("expected_hours_per_week"),
        "expected_skill_match": buyer_profile.get("expected_skill_match"),
        "is_advisor_override": bool(buyer_profile.get("is_advisor_override")),
        "rationale": localized.buyer_rationale,
        "eu_sme_segment": localized.sme_segment,
    }


def _gap_context(*, gap: Mapping[str, object], summary: object) -> JsonMap:
    return {
        "owner_hours_per_week": gap.get("owner_hours_per_week"),
        "buyer_hours_per_week": gap.get("buyer_hours_per_week"),
        "hours_gap": gap.get("hours_gap"),
        "owner_skill_score": _rounded_int(gap.get("owner_skill_score")),
        "buyer_skill_score": _rounded_int(gap.get("buyer_skill_score")),
        "skill_gap": _rounded_int(gap.get("skill_gap")),
        "severity": gap.get("severity") or "minimal",
        "severity_tier": _int_or_default(gap.get("severity_tier"), default=1),
        "summary": summary,
    }


def _narrative_cascade(
    *,
    cascade: Sequence[object],
    cascade_data: Sequence[object],
    gap: Mapping[str, object],
    localized: _LocalizedTransferability,
    t: object,
) -> list[object]:
    localized_data = [
        _localized_cascade_line(line=line, localized=localized) for line in cascade_data
    ]
    localized_cascade = _localise_cascade(localized_data, gap, t)
    return list(localized_cascade or cascade)


def _localized_cascade_line(
    *,
    line: object,
    localized: _LocalizedTransferability,
) -> object:
    if not isinstance(line, Mapping):
        return line
    new_line = dict(line)
    new_fields = dict(new_line.get("fields") or {})
    key = new_line.get("key")
    if key == "buyer":
        new_fields["buyer_archetype"] = localized.archetype_label
    elif key == "owner":
        _localize_owner_cascade_fields(new_fields, localized)
    new_line["fields"] = new_fields
    return new_line


def _localize_owner_cascade_fields(
    fields: dict[object, object],
    localized: _LocalizedTransferability,
) -> None:
    if localized.weakest_label:
        fields["weakest_label_lower"] = str(localized.weakest_label).lower()
    raw_score = fields.get("weakest_score")
    if raw_score is not None:
        rounded = _rounded_int(raw_score)
        fields["weakest_score"] = rounded


def _sub_factor_rows(*, sub_factors: Sequence[object], t: object) -> list[JsonMap]:
    rows: list[JsonMap] = []
    for sf in sub_factors:
        if not isinstance(sf, Mapping):
            continue
        score = _clamped_score(sf.get("score"))
        rows.append(
            {
                "key": sf.get("key"),
                "label": _localize_subfactor_label(sf.get("key"), sf.get("label"), t),
                "score": score,
                "band": sf.get("band") or "neutral",
                "contributing_factors": list(sf.get("contributing_factors") or []),
            }
        )
    return rows


def _method_rows(*, method_incidence: Sequence[object], t: object) -> list[JsonMap]:
    rows: list[JsonMap] = []
    for incidence in method_incidence:
        if isinstance(incidence, Mapping):
            rows.append(_method_row(incidence=incidence, t=t))
    return rows


def _method_row(*, incidence: Mapping[object, object], t: object) -> JsonMap:
    method_id = incidence.get("method") or ""
    coefficient = _float_or_zero(incidence.get("coefficient"))
    citation_ids = list(_METHOD_CITATION_IDS.get(str(method_id), []))
    return {
        "method": method_id,
        "label": _method_label(method_id=method_id, incidence=incidence, t=t),
        "coefficient": coefficient,
        "applied_pct": _pct_float(incidence.get("applied_pct")),
        "rationale": _method_rationale(method_id=method_id, incidence=incidence, t=t),
        "skips": coefficient == 0,
        "citation_markers": [
            _CITATION_DISPLAY_INDEX[cid] for cid in citation_ids if cid in _CITATION_DISPLAY_INDEX
        ],
    }


def _method_label(*, method_id: object, incidence: Mapping[object, object], t: object) -> object:
    label_attr = _METHOD_LABEL_T_KEYS.get(str(method_id))
    return (
        (getattr(t, label_attr, None) if label_attr else None)
        or incidence.get("label")
        or str(method_id).replace("_", " ").title()
    )


def _method_rationale(
    *,
    method_id: object,
    incidence: Mapping[object, object],
    t: object,
) -> object:
    rationale_attr = _METHOD_RATIONALE_T_KEYS.get(str(method_id))
    return (
        (getattr(t, rationale_attr, None) if rationale_attr else None)
        or incidence.get("rationale")
        or ""
    )


def _citation_context(*, citations: Sequence[object], t: object) -> _CitationContext:
    grouped = _citations_by_layer(citations)
    return _CitationContext(
        rows=_citation_rows(citations),
        groups=_citation_groups(grouped=grouped, t=t),
    )


def _citations_by_layer(citations: Sequence[object]) -> dict[str, list[StringMap]]:
    grouped: dict[str, list[StringMap]] = {}
    for citation in citations:
        if not isinstance(citation, Mapping):
            continue
        layer = str(citation.get("layer") or "other")
        citation_text = str(citation.get("citation") or "")
        cid = _citation_id_for(citation_text)
        marker = _CITATION_DISPLAY_INDEX.get(cid) if cid else None
        grouped.setdefault(layer, []).append(
            {
                "citation": citation_text,
                "application": str(citation.get("application") or ""),
                "marker": marker or "",
                "id": cid or "",
            }
        )
    return grouped


def _citation_groups(*, grouped: dict[str, list[StringMap]], t: object) -> list[JsonMap]:
    groups: list[JsonMap] = []
    emitted: set[str] = set()
    for layer in _LAYER_ORDER:
        if layer in grouped:
            groups.append(_citation_group(layer=layer, citations=grouped[layer], t=t))
            emitted.add(layer)
    for layer, citations in grouped.items():
        if layer not in emitted:
            groups.append(_citation_group(layer=layer, citations=citations, t=t))
    return groups


def _citation_group(*, layer: str, citations: list[StringMap], t: object) -> JsonMap:
    t_key = _LAYER_T_KEYS.get(layer)
    label = (getattr(t, t_key, None) if t_key else None) or layer.replace("_", " ").title()
    return {"layer": layer, "label": label, "citations": citations}


def _citation_rows(citations: Sequence[object]) -> list[JsonMap]:
    rows: list[JsonMap] = []
    for citation in citations:
        if not isinstance(citation, Mapping):
            continue
        rows.append(
            {
                "layer": citation.get("layer") or "",
                "citation": citation.get("citation") or "",
                "application": citation.get("application") or "",
            }
        )
    return rows


def _confidence_context(confidence: Mapping[str, object]) -> JsonMap:
    tier = str(confidence.get("tier") or "medium").lower()
    return {
        "tier": tier,
        "band": {"high": "good", "medium": "neutral", "low": "caution"}.get(tier, "neutral"),
        "coverage_pct": _int_or_default(confidence.get("coverage_pct"), default=0),
        "rationale": confidence.get("rationale") or "",
        "cap_binding": bool(confidence.get("cap_binding")),
    }


def _mapping_or_empty(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else {}


def _sequence_or_empty(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return cast(Sequence[object], value)
    return ()


def _pct_float(value: object) -> float:
    try:
        return float(Decimal(str(value or 0)) * Decimal("100"))
    except (InvalidOperation, TypeError, ValueError, ArithmeticError):
        return 0.0


def _float_or_zero(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _rounded_int(value: object) -> int:
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _int_or_default(value: object, *, default: int) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _clamped_score(value: object) -> int:
    return int(round(max(0.0, min(100.0, _float_or_zero(value)))))
