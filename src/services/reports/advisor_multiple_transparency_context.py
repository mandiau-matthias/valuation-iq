"""Report context for advisor multiple transparency appendices."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from src.services.reports.advisor_multiple_transparency_enrichment import (
    enrich_advisor_multiple_transparency_context,
)
from src.services.reports.advisor_multiple_transparency_enrichment import (
    enrich_discount_impacts as _enrich_discount_impacts,
)
from src.services.reports.business_label_localization import localize_business_label
from src.services.reports.protocol_adapter import coerce_json_object

from src.services.reports.equity_bridge_localization import localize_equity_bridge
from src.services.reports.multiple_row_localization import localize_multiple_rows

JsonMap = dict[str, object]


@dataclass(frozen=True)
class AdvisorTransparencySources:
    multiple_build_up: JsonMap | None
    discount_build_up: JsonMap | None
    multiple_type_blend: JsonMap | None
    segment_valuation: JsonMap | None
    is_ssot: bool
    earnings_basis_obj: JsonMap | None
    earnings_basis: object | None
    discount_source: JsonMap | None
    blend_source: JsonMap | None
    segment_source: JsonMap | None
    multiple_rows: list[JsonMap]


def _get_value(source: object, key: str) -> object | None:
    if source is None:
        return None
    if isinstance(source, Mapping):
        return source.get(key)
    getter = getattr(source, "get", None)
    if callable(getter):
        value = getter(key, None)
        if value is not None:
            return value
    return getattr(source, key, None)


def _plain(value: object) -> object:
    mapping = coerce_json_object(value)
    if mapping is not None:
        return {str(key): _plain(nested) for key, nested in mapping.items()}
    if isinstance(value, Mapping):
        return {str(key): _plain(nested) for key, nested in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain(item) for item in value]
    return value


def _as_mapping(value: object) -> JsonMap | None:
    plain = _plain(value)
    return plain if isinstance(plain, dict) else None


def _as_list(value: object) -> list[object]:
    plain = _plain(value)
    return list(plain) if isinstance(plain, list) else []


def _text_list(value: object) -> list[str]:
    raw_values = _as_list(value)
    if not raw_values:
        raw_values = [value] if value is not None and value != "" else []

    values: list[str] = []
    for item in raw_values:
        text = str(item).strip() if item is not None else ""
        if text:
            values.append(text)
    return list(dict.fromkeys(values))


def _first_text(*values: object) -> str | None:
    for value in values:
        for item in _text_list(value):
            return item
    return None


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _percent(value: object) -> Decimal | None:
    parsed = _decimal(value)
    if parsed is None:
        return None
    if abs(parsed) <= Decimal("2"):
        return parsed * Decimal("100")
    return parsed


def _first_mapping(sources: Sequence[object], key: str) -> JsonMap | None:
    for source in sources:
        value = _as_mapping(_get_value(source, key))
        if value:
            return value
    return None


def _first_scalar(sources: Sequence[object], key: str) -> object | None:
    for source in sources:
        value = _get_value(source, key)
        if value is not None and value != "":
            return value
    return None


def _label(row: Mapping[str, object], fallback: str) -> str:
    for explicit_key in ("label", "stage_name", "name"):
        explicit = row.get(explicit_key)
        if explicit:
            return str(explicit).strip()
    raw = row.get("key") or fallback
    return str(raw).replace("_", " ").strip().title()


def _multiple_row_has_data(row: JsonMap) -> bool:
    """A build-up row earns a printed line if it carries a number or an
    advisor-authored note.

    The build-up columns are numeric (Multiple / Impact / EV); a stage that
    arrives with only a fallback "Step N" label and null values renders as a row
    of em-dashes, which reads as a broken/empty appendix. Skip those, but keep
    any row that carries an explicit rationale/source/override note.
    """
    if row.get("rationale") or row.get("source") or row.get("override_note"):
        return True
    return any(
        row.get(key) is not None
        for key in (
            "multiple",
            "model_multiple",
            "advisor_multiple",
            "adjustment",
            "enterprise_value",
        )
    )


def _build_multiple_rows(multiple_build_up: JsonMap | None) -> list[JsonMap]:
    if not multiple_build_up:
        return []

    rows: list[JsonMap] = []
    for index, raw_row in enumerate(_as_list(multiple_build_up.get("stages"))):
        row = _as_mapping(raw_row)
        if not row:
            continue
        stage_row = _multiple_stage_row(row, fallback_label=f"Step {index + 1}")
        if _multiple_row_has_data(stage_row):
            rows.append(stage_row)

    if rows:
        return rows
    return _initial_final_multiple_rows(multiple_build_up)


def _multiple_stage_row(row: JsonMap, *, fallback_label: str) -> JsonMap:
    model_multiple = _decimal(row.get("model_multiple"))
    advisor_multiple = _decimal(row.get("advisor_multiple") or row.get("override_multiple"))
    # Only surface an "Advisor-adjusted" line for a REAL override: a non-zero value
    # that actually differs from the model multiple. Otherwise the appendix prints
    # "Advisor-adjusted: 0x vs 0x" — placeholder noise on the no-advisor SSOT path.
    if (
        advisor_multiple is None
        or advisor_multiple == Decimal("0")
        or advisor_multiple == model_multiple
    ):
        advisor_multiple = None
    return {
        "label": _label(row, fallback_label),
        "multiple": _decimal(row.get("multiple_value") or row.get("multiple")),
        "model_multiple": model_multiple,
        "advisor_multiple": advisor_multiple,
        "adjustment": _decimal(row.get("adjustment")),
        "enterprise_value": _decimal(row.get("ev_value") or row.get("enterprise_value")),
        "rationale": row.get("rationale") or row.get("reason"),
        "source": row.get("source") or row.get("data_source"),
        "override_note": row.get("override_note") or row.get("advisor_note"),
    }


def _initial_final_multiple_rows(multiple_build_up: JsonMap) -> list[JsonMap]:
    initial = _decimal(multiple_build_up.get("initial_multiple"))
    final = _decimal(multiple_build_up.get("final_multiple"))
    rows: list[JsonMap] = []
    if initial is not None:
        rows.append(
            {
                "label": "Reference multiple",
                "multiple": initial,
                # Explicit None (not absent) so the template's
                # `advisor_multiple is not none` guard evaluates correctly and
                # does not render a phantom "Advisor-adjusted: 0x vs 0x" line.
                "model_multiple": None,
                "advisor_multiple": None,
                "adjustment": None,
                "enterprise_value": None,
            }
        )
    if final is not None:
        rows.append(
            {
                "label": "Applied multiple",
                "multiple": final,
                "model_multiple": None,
                "advisor_multiple": None,
                "adjustment": None if initial is None else final - initial,
                "enterprise_value": None,
            }
        )
    return rows


def _discount_row_has_data(row: JsonMap) -> bool:
    """A discount row earns a printed line if it carries a number or an
    advisor-authored note. A reference-only qualitative discount (rationale, no
    numeric impact) is intentional and kept; a label-only placeholder is not.
    """
    if row.get("rationale") or row.get("source"):
        return True
    return any(
        row.get(key) is not None
        for key in (
            "model_adjustment_percent",
            "advisor_weight_percent",
            "effective_adjustment_percent",
            "factor_before",
            "factor_after",
            "euro_impact",
        )
    )


def _build_discount_rows(
    discount_build_up: JsonMap | None,
    multiple_build_up: JsonMap | None,
) -> list[JsonMap]:
    rows: list[JsonMap] = []
    for index, raw_row in enumerate(_discount_source_rows(discount_build_up, multiple_build_up)):
        row = _as_mapping(raw_row)
        if not row:
            continue
        composition = (discount_build_up or {}).get("composition")
        # The step pipeline publishes percentage points, whereas the stateless
        # multiplicative stack publishes ratios. Magnitude cannot distinguish
        # a 1.5% pipeline discount from a ratio: honor the producer contract.
        percentage_points = composition == "step_pipeline" or (
            composition != "multiplicative"
            and "discount_percentage" in row
            and "multiple_before_mid" in row
        )
        discount_row = _discount_row(
            row,
            fallback_label=f"Discount {index + 1}",
            percentage_points=percentage_points,
        )
        if _discount_row_has_data(discount_row):
            rows.append(discount_row)
    return rows


def _discount_source_rows(
    discount_build_up: JsonMap | None,
    multiple_build_up: JsonMap | None,
) -> list[object]:
    if discount_build_up:
        rows = _as_list(discount_build_up.get("rows")) or _as_list(
            discount_build_up.get("waterfall")
        )
        if rows:
            return rows
    if multiple_build_up:
        return _as_list(multiple_build_up.get("discount_waterfall"))
    return []


def _discount_row(row: JsonMap, *, fallback_label: str, percentage_points: bool = False) -> JsonMap:
    adjustment_percent = _decimal if percentage_points else _percent
    model_adjustment = row.get("model_adjustment")
    if model_adjustment is None:
        model_adjustment = row.get("adjustment")
    factor_after = row.get("factor_after")
    if factor_after is None:
        factor_after = row.get("multiple_value")
    strength_factor_evidence = _strength_factor_evidence_rows(row)
    multiple_discount_key = _first_text(
        row.get("multiple_discount_key"),
        row.get("multipleDiscountKey"),
        row.get("discount_key"),
        row.get("discountKey"),
        _strength_factor_evidence_values(
            strength_factor_evidence,
            "multiple_discount_key",
            "multipleDiscountKey",
            "discount_key",
            "discountKey",
        ),
    )
    return {
        "label": str(row.get("step_name") or _label(row, fallback_label)),
        "factor_unit": "multiple" if row.get("multiple_before_mid") is not None else "factor",
        "model_adjustment_percent": adjustment_percent(model_adjustment),
        "advisor_weight_percent": _percent(row.get("advisor_weight")),
        "effective_adjustment_percent": adjustment_percent(row.get("effective_adjustment")),
        "factor_before": _decimal(row.get("factor_before")),
        "factor_after": _decimal(factor_after),
        "euro_impact": None,
        "impact_basis": None,
        "rationale": row.get("rationale") or row.get("reason") or row.get("explanation"),
        "source": row.get("source") or row.get("data_source") or row.get("provenance"),
        "multiple_discount_key": multiple_discount_key,
        "strength_factor_multiple_discount_keys": _strength_factor_row_values(
            row,
            strength_factor_evidence,
            "strength_factor_multiple_discount_keys",
            "multiple_discount_key",
            "multipleDiscountKey",
        ),
        "strength_factor_keys": _strength_factor_row_values(
            row,
            strength_factor_evidence,
            "strength_factor_keys",
            "factor_key",
            "factorKey",
        ),
        "strength_factor_mapped_inputs": _strength_factor_row_values(
            row,
            strength_factor_evidence,
            "strength_factor_mapped_inputs",
            "mapped_subjective_input",
            "mappedSubjectiveInput",
            "maps_to_subjective_input",
            "mapsToSubjectiveInput",
        ),
        "strength_factor_valuation_effects": _strength_factor_row_values(
            row,
            strength_factor_evidence,
            "strength_factor_valuation_effects",
            "valuation_effect",
            "valuationEffect",
            "effect",
        ),
        "strength_factor_captured_input_ids": _strength_factor_row_values(
            row,
            strength_factor_evidence,
            "strength_factor_captured_input_ids",
            "captured_input_id",
            "capturedInputId",
        ),
        "strength_factor_data_point_ids": _strength_factor_data_point_ids(
            row,
            strength_factor_evidence,
        ),
        "strength_factor_evidence_count": _strength_factor_evidence_count(
            row,
            strength_factor_evidence,
        ),
        "enabled": bool(row.get("enabled", True)),
    }


def _strength_factor_evidence_rows(row: JsonMap) -> list[JsonMap]:
    evidence_rows: list[JsonMap] = []
    for key in ("strength_factor_evidence", "strength_factor_discount_evidence"):
        for raw_item in _as_list(row.get(key)):
            item = _as_mapping(raw_item)
            if item and item not in evidence_rows:
                evidence_rows.append(item)
    return evidence_rows


def _strength_factor_evidence_values(
    evidence_rows: Sequence[Mapping[str, object]],
    *keys: str,
) -> list[str]:
    values: list[str] = []
    for evidence in evidence_rows:
        for key in keys:
            values.extend(_text_list(evidence.get(key)))
    return list(dict.fromkeys(values))


def _strength_factor_row_values(
    row: JsonMap,
    evidence_rows: Sequence[Mapping[str, object]],
    direct_key: str,
    *evidence_keys: str,
) -> list[str]:
    direct = _text_list(row.get(direct_key))
    if direct:
        return direct
    return _strength_factor_evidence_values(evidence_rows, *evidence_keys)


def _strength_factor_data_point_ids(
    row: JsonMap,
    evidence_rows: Sequence[Mapping[str, object]],
) -> list[str]:
    direct = _text_list(row.get("strength_factor_data_point_ids"))
    if direct:
        return direct

    values = _strength_factor_evidence_values(
        evidence_rows,
        "data_point_id",
        "dataPointId",
        "data_point_ids",
        "dataPointIds",
    )
    for evidence in evidence_rows:
        for point in _as_list(evidence.get("dataPoints")):
            if not isinstance(point, Mapping):
                continue
            values.extend(
                _text_list(
                    point.get("dataPointId")
                    or point.get("data_point_id")
                    or point.get("questionId")
                    or point.get("question_id")
                )
            )
    return list(dict.fromkeys(values))


def _strength_factor_evidence_count(
    row: JsonMap,
    evidence_rows: Sequence[Mapping[str, object]],
) -> int:
    explicit = _decimal(row.get("strength_factor_evidence_count"))
    if explicit is not None:
        return int(explicit)
    return len(evidence_rows)


def _bridge_row(label: str, amount: Decimal | None, operator: str | None = None) -> JsonMap:
    return {
        "label": label,
        "amount": amount,
        "operator": operator,
    }


def _build_blend_rows(multiple_type_blend: JsonMap | None) -> list[JsonMap]:
    if not multiple_type_blend:
        return []
    rows: list[JsonMap] = []
    for index, raw_row in enumerate(_as_list(multiple_type_blend.get("rows"))):
        row = _as_mapping(raw_row)
        if not row:
            continue
        rows.append(
            {
                "label": _label(row, f"Method {index + 1}"),
                "weight_percent": _percent(row.get("weight")),
                "enterprise_value": _decimal(row.get("enterprise_value")),
                "contribution": _decimal(row.get("contribution")),
                "included": bool(row.get("included", True)),
            }
        )
    return rows


def _build_segment_rows(segment_valuation: JsonMap | None, *, locale: str = "nl") -> list[JsonMap]:
    if not segment_valuation:
        return []
    rows: list[JsonMap] = []
    for index, raw_row in enumerate(_as_list(segment_valuation.get("segments"))):
        row = _as_mapping(raw_row)
        if not row:
            continue
        raw_label = (
            row.get("business_type_title")
            or row.get("business_type_id")
            or row.get("nace_code")
            or f"Segment {index + 1}"
        )
        rows.append(
            {
                "label": str(localize_business_label(str(raw_label), locale) or raw_label),
                "basis": row.get("basis"),
                "earnings": _decimal(row.get("earnings")),
                "multiple": _decimal(row.get("multiple")),
                "enterprise_value": _decimal(row.get("enterprise_value")),
                "weight_percent": _percent(row.get("weight")),
            }
        )
    return rows


def _is_ssot_v2(multiple_build_up: JsonMap | None) -> bool:
    """Detect the canonical typed build-up (BET-520, v2)."""
    if not multiple_build_up:
        return False
    return str(multiple_build_up.get("version") or "").startswith("multiple_build_up_v2") or bool(
        multiple_build_up.get("equity_bridge") or multiple_build_up.get("discounts")
    )


def _build_add_back_rows(earnings_basis: JsonMap | None) -> list[JsonMap]:
    """Reported -> adjusted EBITDA ledger rows (BET-533)."""
    if not earnings_basis:
        return []
    rows: list[JsonMap] = []
    for raw in _as_list(earnings_basis.get("add_backs")):
        row = _as_mapping(raw)
        if not row:
            continue
        rows.append(
            {
                "label": row.get("label") or "Adjustment",
                "category": row.get("category"),
                "amount": _decimal(row.get("signed_amount") or row.get("amount")),
                "rationale": row.get("rationale"),
                "source": row.get("source"),
                "applied": bool(row.get("applied", True)),
                "status": row.get("status"),
            }
        )
    return rows


def _build_ssot_equity_bridge(bridge: JsonMap | None) -> JsonMap:
    """Itemized EV->equity bridge rows from the typed SSOT (BET-534)."""
    if not bridge:
        return {"rows": [], "disclosures": [], "reconciles": False}
    enterprise_value = _decimal(bridge.get("enterprise_value"))
    equity_value = _decimal(bridge.get("equity_value"))
    return {
        "rows": _ssot_equity_bridge_rows(bridge, enterprise_value, equity_value),
        "disclosures": _ssot_equity_bridge_disclosures(bridge),
        "reconciles": enterprise_value is not None and equity_value is not None,
        "net_debt": _decimal(bridge.get("net_debt")),
        "nwc_status": bridge.get("nwc_status"),
    }


def _ssot_equity_bridge_rows(
    bridge: JsonMap,
    enterprise_value: Decimal | None,
    equity_value: Decimal | None,
) -> list[JsonMap]:
    rows: list[JsonMap] = []
    if enterprise_value is not None:
        rows.append(_bridge_row("Enterprise value", enterprise_value))
    for raw in _as_list(bridge.get("lines")):
        row = _ssot_equity_bridge_line_row(raw)
        if row is not None:
            rows.append(row)
    if equity_value is not None:
        rows.append(_bridge_row("Equity value", equity_value, "="))
    return rows


def _ssot_equity_bridge_line_row(raw_line: object) -> JsonMap | None:
    line = _as_mapping(raw_line)
    if not line:
        return None
    amount = _decimal(line.get("amount"))
    if amount is None or amount == Decimal("0"):
        return None
    return _bridge_row(str(line.get("label") or "Adjustment"), amount, line.get("operator"))


def _ssot_equity_bridge_disclosures(bridge: JsonMap) -> list[str]:
    disclosures: list[str] = []
    if bridge.get("is_phantom_suppressed"):
        disclosures.append("EV-to-equity bridge suppressed: no enterprise value on this path.")
    elif str(bridge.get("nwc_status")) == "not_assessed":
        disclosures.append("NWC normalization and surplus assets not assessed - no balance sheet.")
    for note in _as_list(bridge.get("notes")):
        if isinstance(note, str) and note:
            disclosures.append(note)
    return disclosures


def _build_ssot_multiple_rows(multiple_build_up: JsonMap) -> list[JsonMap]:
    """Model -> advisor multiple ladder from the typed SSOT (BET-522)."""
    rows: list[JsonMap] = []
    override = _as_mapping(multiple_build_up.get("advisor_override"))
    if override:
        model_value = _decimal(override.get("model_value"))
        advisor_value = _decimal(override.get("advisor_value"))
        if model_value is not None:
            rows.append({"label": "Upswitch model multiple", "multiple": model_value})
        if advisor_value is not None:
            rows.append(
                {
                    "label": "Advisor-adjusted multiple",
                    "multiple": advisor_value,
                    "model_multiple": model_value,
                    "advisor_multiple": advisor_value,
                    "adjustment": _decimal(override.get("delta")),
                    "override_note": override.get("note"),
                }
            )
    effective = _decimal(multiple_build_up.get("effective_multiple"))
    if effective is not None:
        rows.append(
            {
                "label": "Effective multiple (after discounts)",
                "multiple": effective,
                "enterprise_value": _decimal(multiple_build_up.get("enterprise_value")),
            }
        )
    return rows


def _resolve_earnings_basis(
    *,
    sources: Sequence[object],
    multiple_build_up: JsonMap | None,
    is_ssot: bool,
) -> tuple[JsonMap | None, object | None]:
    earnings_basis_obj = (
        _as_mapping((multiple_build_up or {}).get("earnings_basis")) if is_ssot else None
    )
    legacy_earnings_basis = None if is_ssot else (multiple_build_up or {}).get("earnings_basis")
    earnings_basis = (
        _first_scalar(sources, "earnings_basis")
        or (earnings_basis_obj or {}).get("basis")
        or legacy_earnings_basis
        or (multiple_build_up or {}).get("metric_type")
    )
    return earnings_basis_obj, earnings_basis


def _ssot_segment_source(
    multiple_build_up: JsonMap,
    fallback_segment_valuation: JsonMap | None,
) -> JsonMap | None:
    segment_list = _as_list(multiple_build_up.get("segments"))
    if not segment_list:
        return fallback_segment_valuation
    return {
        "segments": segment_list,
        "mode": multiple_build_up.get("segment_mode"),
    }


def _resolve_appendix_source_set(response: object) -> AdvisorTransparencySources:
    multiples = _get_value(response, "multiples_valuation")
    multiples_results = _get_value(response, "multiples_results")
    sources = [multiples, multiples_results, response]

    multiple_build_up = _first_mapping(sources, "multiple_build_up")
    discount_build_up = _first_mapping(sources, "discount_build_up")
    multiple_type_blend = _first_mapping(sources, "multiple_type_blend")
    segment_valuation = _first_mapping(sources, "segment_valuation")
    is_ssot = _is_ssot_v2(multiple_build_up)
    earnings_basis_obj, earnings_basis = _resolve_earnings_basis(
        sources=sources,
        multiple_build_up=multiple_build_up,
        is_ssot=is_ssot,
    )

    if not is_ssot:
        return AdvisorTransparencySources(
            multiple_build_up=multiple_build_up,
            discount_build_up=discount_build_up,
            multiple_type_blend=multiple_type_blend,
            segment_valuation=segment_valuation,
            is_ssot=False,
            earnings_basis_obj=earnings_basis_obj,
            earnings_basis=earnings_basis,
            discount_source=discount_build_up,
            blend_source=multiple_type_blend,
            segment_source=segment_valuation,
            multiple_rows=_build_multiple_rows(multiple_build_up),
        )

    typed_build_up = multiple_build_up or {}
    return AdvisorTransparencySources(
        multiple_build_up=multiple_build_up,
        discount_build_up=discount_build_up,
        multiple_type_blend=multiple_type_blend,
        segment_valuation=segment_valuation,
        is_ssot=True,
        earnings_basis_obj=earnings_basis_obj,
        earnings_basis=earnings_basis,
        discount_source=_as_mapping(typed_build_up.get("discounts")) or discount_build_up,
        blend_source=_as_mapping(typed_build_up.get("multiple_type_blend")) or multiple_type_blend,
        segment_source=_ssot_segment_source(typed_build_up, segment_valuation),
        multiple_rows=_build_ssot_multiple_rows(typed_build_up)
        or _build_multiple_rows(multiple_build_up),
    )


def _build_advisor_transparency_appendix(
    *,
    sources: AdvisorTransparencySources,
    discount_rows: list[JsonMap],
    blend_rows: list[JsonMap],
    segment_rows: list[JsonMap],
    add_back_rows: list[JsonMap],
) -> JsonMap:
    multiple_build_up = sources.multiple_build_up or {}
    earnings_basis_obj = sources.earnings_basis_obj or {}
    discount_source = sources.discount_source or {}
    segment_source = sources.segment_source or {}
    return {
        "earnings_basis": str(sources.earnings_basis) if sources.earnings_basis else None,
        "earnings_basis_rationale": earnings_basis_obj.get("rationale"),
        "reported_earnings": _decimal(earnings_basis_obj.get("reported_earnings")),
        "adjusted_earnings": _decimal(earnings_basis_obj.get("adjusted_earnings")),
        "discount_earnings": _decimal(multiple_build_up.get("metric_value")),
        "add_back_rows": add_back_rows,
        "source": multiple_build_up.get("source"),
        "multiple_rows": sources.multiple_rows,
        "discount_rows": discount_rows,
        "blend_rows": blend_rows,
        "segment_rows": segment_rows,
        "segment_mode": segment_source.get("mode"),
        "requires_segment_earnings": bool(segment_source.get("requires_segment_earnings")),
        "discount_composition": discount_source.get("composition"),
        "discount_floor_factor_percent": _percent(discount_source.get("floor_factor")),
        "risk_analysis_enabled": (
            multiple_build_up.get("risk_analysis_enabled")
            if sources.is_ssot
            else discount_source.get("enabled")
        ),
        "risk_analysis_reference_only": bool(multiple_build_up.get("risk_analysis_reference_only")),
    }


def _append_ssot_equity_bridge(
    *,
    appendix: JsonMap,
    multiple_build_up: JsonMap | None,
    is_ssot: bool,
) -> None:
    if not is_ssot:
        return
    typed_build_up = multiple_build_up or {}
    equity_bridge = _build_ssot_equity_bridge(_as_mapping(typed_build_up.get("equity_bridge")))
    appendix["equity_bridge"] = equity_bridge
    appendix["has_equity_bridge_rows"] = bool(equity_bridge.get("rows"))
    _enrich_discount_impacts(appendix, _decimal(typed_build_up.get("enterprise_value")))


def _should_show_advisor_transparency_appendix(
    *,
    sources: AdvisorTransparencySources,
    discount_rows: list[JsonMap],
    blend_rows: list[JsonMap],
    segment_rows: list[JsonMap],
    add_back_rows: list[JsonMap],
) -> bool:
    return any(
        (
            sources.multiple_rows,
            discount_rows,
            blend_rows,
            segment_rows,
            sources.earnings_basis,
            add_back_rows,
        )
    )


def build_advisor_multiple_transparency_context(response: object, *, locale: str = "nl") -> JsonMap:
    """Expose the multiples SSOT in a small template-friendly appendix shape.

    Prefers the canonical typed build-up (BET-520 v2): the multiple ladder,
    add-back ledger, per-segment rows, discount stack, blend, and the itemized
    EV->equity bridge are all read from that one object — no divergent math.
    """
    sources = _resolve_appendix_source_set(response)
    discount_rows = _build_discount_rows(sources.discount_source, sources.multiple_build_up)
    blend_rows = _build_blend_rows(sources.blend_source)
    segment_rows = _build_segment_rows(sources.segment_source, locale=locale)
    add_back_rows = _build_add_back_rows(sources.earnings_basis_obj)
    appendix = _build_advisor_transparency_appendix(
        sources=sources,
        discount_rows=discount_rows,
        blend_rows=blend_rows,
        segment_rows=segment_rows,
        add_back_rows=add_back_rows,
    )
    _append_ssot_equity_bridge(
        appendix=appendix,
        multiple_build_up=sources.multiple_build_up,
        is_ssot=sources.is_ssot,
    )
    if isinstance(appendix.get("equity_bridge"), dict):
        appendix["equity_bridge"] = localize_equity_bridge(appendix["equity_bridge"], locale)
    appendix["multiple_rows"] = localize_multiple_rows(sources.multiple_rows, locale)
    show = _should_show_advisor_transparency_appendix(
        sources=sources,
        discount_rows=discount_rows,
        blend_rows=blend_rows,
        segment_rows=segment_rows,
        add_back_rows=add_back_rows,
    )
    return {
        "show_advisor_multiple_transparency_appendix": show,
        "advisor_multiple_transparency": appendix,
    }
