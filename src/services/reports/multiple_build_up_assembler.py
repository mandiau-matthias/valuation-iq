"""Assemble the canonical typed multiple build-up (BET-520).

Pure functions that map the pieces already computed by the stateless engine
(adjusted-EBITDA ledger, SOTP segments, discount stack, benchmark provenance,
override audit, EV->equity bridge inputs) into one typed `MultipleBuildUp`.

No recomputation happens here — this is assembly only, so the PDF, the UI, and
the live comparison all read the same object with no divergent math.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Optional

from src.api.schemas.multiple_build_up import (
    AddBackLine,
    AdvisorOverride,
    DiscountLine,
    DiscountStack,
    EarningsBasisBuildUp,
    EquityBridge,
    EquityBridgeLine,
    MultipleBuildUp,
    MultipleTypeBlend,
    MultipleTypeBlendRow,
    SegmentProvenance,
)
from src.domain.multiples.advisor_controls import normalize_earnings_basis
from src.services.reports.earnings_basis_projection import PROJECTION_VERSION


def _dec(value: object) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _int(value: object) -> Optional[int]:
    parsed = _dec(value)
    return int(parsed) if parsed is not None else None


def _provenance(benchmark_provenance: Mapping[str, object] | None) -> dict[str, object]:
    """Flatten the fields the segment provenance needs from a benchmark contract."""
    prov = benchmark_provenance if isinstance(benchmark_provenance, Mapping) else {}
    return {
        "source_tier": prov.get("tier") or prov.get("source_tier") or prov.get("data_tier"),
        "observation_count": _int(
            prov.get("sample_size")
            or prov.get("observation_count")
            or prov.get("observations")
            or prov.get("n")
        ),
        "as_of": prov.get("published_at") or prov.get("as_of") or prov.get("value_as_of"),
        "confidence": prov.get("confidence") or prov.get("confidence_level"),
    }


def _earnings_basis_build_up(
    *,
    basis: str,
    rationale: str | None,
    reported_earnings: Decimal | None,
    adjusted_earnings: Decimal | None,
    add_back_ledger: Mapping[str, object] | None,
) -> EarningsBasisBuildUp:
    ledger = add_back_ledger if isinstance(add_back_ledger, Mapping) else {}
    add_backs = _add_back_lines(ledger.get("adjustments"))
    reported, adjusted = _earnings_values(
        ledger=ledger,
        reported_earnings=reported_earnings,
        adjusted_earnings=adjusted_earnings,
    )
    total = _total_adjustments(ledger, reported, adjusted)

    # A row may only read as "applied" if the priced basis actually moved.
    # The upstream ledger stamps `applied` from the client's own status, so an
    # ungoverned add-back could otherwise be listed as applied next to an
    # unchanged valuation — the owner sees a credit the number never received.
    canonical_projection = ledger.get("version") == PROJECTION_VERSION
    if not canonical_projection and total is not None and total == Decimal("0"):
        add_backs = [
            (
                line.model_copy(update={"applied": False, "status": "scenario_only_unpriced"})
                if line.applied
                else line
            )
            for line in add_backs
        ]

    return EarningsBasisBuildUp(
        projection_version=(
            PROJECTION_VERSION if canonical_projection else "earnings_basis_build_up.v1"
        ),
        basis=normalize_earnings_basis(basis),
        rationale=rationale,
        reported_earnings=reported,
        adjusted_earnings=adjusted,
        total_adjustments=total or Decimal("0"),
        add_backs=add_backs,
        is_adjusted=bool(total) or (canonical_projection and any(r.applied for r in add_backs)),
        applied_adjustment_count=sum(1 for r in add_backs if r.applied),
        pending_adjustment_count=sum(1 for r in add_backs if not r.applied),
        source=ledger.get("source") if ledger else None,
    )


def _add_back_lines(rows_raw: object) -> list[AddBackLine]:
    if not isinstance(rows_raw, Sequence):
        return []

    return [_add_back_line(raw) for raw in rows_raw if isinstance(raw, Mapping)]


def _add_back_line(raw: Mapping[str, object]) -> AddBackLine:
    return AddBackLine(
        label=str(raw.get("label") or "Adjustment"),
        category=str(raw.get("category") or "other"),
        amount=_dec(raw.get("amount")) or Decimal("0"),
        type=str(raw.get("type") or "add"),
        signed_amount=_dec(raw.get("signed_amount")) or Decimal("0"),
        rationale=raw.get("rationale"),
        source=raw.get("source"),
        status=str(raw.get("status") or "applied"),
        # Evidence-first: an add-back is shown as applied only when the priced
        # ledger says so. Defaulting to True marked ungoverned client rows as
        # applied on the report while the valuation priced without them.
        applied=bool(raw.get("applied", False)),
        fiscal_year=_int(raw.get("fiscal_year")),
        annual_signed_amount=_dec(raw.get("annual_signed_amount")),
        weight=_dec(raw.get("weight")),
        decision_id=raw.get("decision_id"),
        evidence_id=raw.get("evidence_id"),
        rule_version=raw.get("rule_version"),
        currency=raw.get("currency"),
        decided_by=raw.get("decided_by"),
        decided_at=str(raw["decided_at"]) if raw.get("decided_at") is not None else None,
    )


def _earnings_values(
    *,
    ledger: Mapping[str, object],
    reported_earnings: Decimal | None,
    adjusted_earnings: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    reported = (
        reported_earnings if reported_earnings is not None else _dec(ledger.get("reported_ebitda"))
    )
    adjusted = (
        adjusted_earnings if adjusted_earnings is not None else _dec(ledger.get("adjusted_ebitda"))
    )
    return reported, adjusted


def _total_adjustments(
    ledger: Mapping[str, object],
    reported: Decimal | None,
    adjusted: Decimal | None,
) -> Decimal | None:
    """Total the adjustments that were actually *priced*, not those claimed.

    ``ledger["total_adjustments"]`` is caller-supplied: it states what the
    client believes was normalised. The governed earnings basis decides what
    may price (see `stateless_earnings_basis`), and an ungoverned add-back is
    deliberately scenario-only. Preferring the claim would print a credit the
    valuation never received, so the priced difference wins whenever it is
    known and the claim is only a fallback for callers that supply no basis.
    """
    if reported is not None and adjusted is not None:
        return adjusted - reported
    return _dec(ledger.get("total_adjustments"))


def _segments(
    segment_valuation: Mapping[str, object] | None,
    *,
    primary_basis: str,
    primary_meta: Mapping[str, object] | None,
    benchmark_provenance: Mapping[str, object] | None,
    primary_multiple: Decimal | None,
    primary_p25: Decimal | None,
    primary_median: Decimal | None,
    primary_p75: Decimal | None,
    primary_enterprise_value: Decimal | None,
    primary_is_override: bool,
) -> tuple[list[SegmentProvenance], Optional[str], bool]:
    prov = _provenance(benchmark_provenance)
    meta = primary_meta if isinstance(primary_meta, Mapping) else {}

    raw_segments = (
        segment_valuation.get("segments") if isinstance(segment_valuation, Mapping) else None
    )
    if isinstance(raw_segments, Sequence) and raw_segments:
        out: list[SegmentProvenance] = []
        for raw in raw_segments:
            if not isinstance(raw, Mapping):
                continue
            out.append(
                SegmentProvenance(
                    index=_int(raw.get("index")) or len(out),
                    business_type_id=raw.get("business_type_id"),
                    business_type_title=raw.get("business_type_title"),
                    nace_code=raw.get("nace_code"),
                    basis=normalize_earnings_basis(raw.get("basis")),
                    earnings=_dec(raw.get("earnings")),
                    multiple=_dec(raw.get("multiple")),
                    enterprise_value=_dec(raw.get("enterprise_value")),
                    weight=_dec(raw.get("weight")),
                    source_tier=prov["source_tier"],
                    observation_count=prov["observation_count"],
                    as_of=prov["as_of"],
                    confidence=prov["confidence"],
                    is_advisor_override=bool(raw.get("is_advisor_override")),
                )
            )
        mode = (
            str(segment_valuation.get("mode")) if isinstance(segment_valuation, Mapping) else None
        )
        return out, mode, len(out) > 1

    # Single-segment path: synthesize one provenance row from the primary benchmark.
    single = SegmentProvenance(
        index=0,
        business_type_id=meta.get("business_type_id"),
        business_type_title=meta.get("business_type_title") or meta.get("title"),
        nace_code=meta.get("nace_code"),
        basis=normalize_earnings_basis(primary_basis),
        earnings=None,
        multiple=primary_multiple,
        enterprise_value=primary_enterprise_value,
        weight=Decimal("1"),
        source_tier=prov["source_tier"],
        observation_count=prov["observation_count"],
        multiple_p25=primary_p25,
        multiple_median=primary_median,
        multiple_p75=primary_p75,
        as_of=prov["as_of"],
        confidence=prov["confidence"],
        is_advisor_override=primary_is_override,
    )
    return [single], "single_segment", False


def _discount_stack(discount_build_up: Mapping[str, object] | None) -> DiscountStack:
    stack = discount_build_up if isinstance(discount_build_up, Mapping) else {}
    return DiscountStack(
        enabled=bool(stack.get("enabled", True)),
        composition=str(stack.get("composition") or "multiplicative"),
        floor_factor=_dec(stack.get("floor_factor")) or Decimal("0.45"),
        pre_floor_factor=_dec(stack.get("pre_floor_factor")),
        floor_applied=bool(stack.get("floor_applied", False)),
        total_adjustment_factor=_dec(stack.get("total_adjustment_factor")) or Decimal("1"),
        total_adjustment=_dec(stack.get("total_adjustment")) or Decimal("0"),
        rows=_discount_lines(stack.get("rows")),
        owner_concentration_policy=stack.get("owner_concentration_policy"),
        owner_concentration_policy_reason=stack.get("owner_concentration_policy_reason"),
        strength_factor_policy=stack.get("strength_factor_policy"),
        strength_factor_evidence=[
            dict(item)
            for item in stack.get("strength_factor_evidence", [])
            if isinstance(item, Mapping)
        ],
    )


def _discount_lines(rows_raw: object) -> list[DiscountLine]:
    if not isinstance(rows_raw, Sequence):
        return []

    return [_discount_line(raw) for raw in rows_raw if isinstance(raw, Mapping)]


def _discount_line(raw: Mapping[str, object]) -> DiscountLine:
    strength_evidence = _strength_factor_evidence(
        raw.get("strength_factor_evidence") or raw.get("strength_factor_discount_evidence")
    )
    return DiscountLine(
        key=str(raw.get("key") or "discount"),
        label=str(raw.get("label") or "Discount"),
        parameter=_dec(raw.get("model_adjustment")) or Decimal("0"),
        advisor_weight=_dec(raw.get("advisor_weight")) or Decimal("1"),
        magnitude=_dec(raw.get("effective_adjustment")) or Decimal("0"),
        factor_before=_dec(raw.get("factor_before")),
        factor_after=_dec(raw.get("factor_after")),
        rationale=raw.get("rationale"),
        source=raw.get("source"),
        multiple_discount_key=_first_text(
            raw.get("multiple_discount_key"),
            raw.get("multipleDiscountKey"),
            raw.get("discount_key"),
            raw.get("discountKey"),
            *(item.get("multiple_discount_key") for item in strength_evidence),
            *(item.get("multipleDiscountKey") for item in strength_evidence),
            *(item.get("discount_key") for item in strength_evidence),
            *(item.get("discountKey") for item in strength_evidence),
        ),
        strength_factor_multiple_discount_keys=_unique_text(
            _strength_factor_multiple_discount_key_values(strength_evidence)
        ),
        strength_factor_keys=_unique_text(_strength_factor_key_values(strength_evidence)),
        strength_factor_mapped_inputs=_unique_text(
            _strength_factor_mapped_input_values(strength_evidence)
        ),
        strength_factor_valuation_effects=_unique_text(
            _strength_factor_valuation_effect_values(strength_evidence)
        ),
        strength_factor_captured_input_ids=_unique_text(
            _strength_factor_captured_input_values(strength_evidence)
        ),
        strength_factor_data_point_ids=_unique_text(
            _strength_factor_data_point_values(strength_evidence)
        ),
        strength_factor_evidence_count=int(
            raw.get("strength_factor_evidence_count") or len(strength_evidence)
        ),
        enabled=bool(raw.get("enabled", True)),
    )


def _strength_factor_evidence(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strength_factor_key_values(
    evidence: Sequence[Mapping[str, object]],
) -> Iterable[object]:
    for item in evidence:
        yield item.get("factor_key")
        yield item.get("factorKey")


def _strength_factor_multiple_discount_key_values(
    evidence: Sequence[Mapping[str, object]],
) -> Iterable[object]:
    for item in evidence:
        yield item.get("multiple_discount_key")
        yield item.get("multipleDiscountKey")


def _strength_factor_mapped_input_values(
    evidence: Sequence[Mapping[str, object]],
) -> Iterable[object]:
    for item in evidence:
        yield item.get("mapped_subjective_input")
        yield item.get("mappedSubjectiveInput")
        yield item.get("maps_to_subjective_input")
        yield item.get("mapsToSubjectiveInput")


def _strength_factor_valuation_effect_values(
    evidence: Sequence[Mapping[str, object]],
) -> Iterable[object]:
    for item in evidence:
        yield item.get("valuation_effect")
        yield item.get("valuationEffect")
        yield item.get("effect")


def _strength_factor_captured_input_values(
    evidence: Sequence[Mapping[str, object]],
) -> Iterable[object]:
    for item in evidence:
        yield item.get("captured_input_id")
        yield item.get("capturedInputId")


def _strength_factor_data_point_values(
    evidence: Sequence[Mapping[str, object]],
) -> Iterable[object]:
    for item in evidence:
        yield item.get("data_point_id")
        yield item.get("dataPointId")
        for key in ("data_point_ids", "dataPointIds"):
            values = item.get(key)
            if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
                yield from values
            else:
                yield values
        points = item.get("dataPoints")
        if isinstance(points, Sequence) and not isinstance(points, (str, bytes)):
            for point in points:
                if not isinstance(point, Mapping):
                    continue
                yield point.get("dataPointId")
                yield point.get("data_point_id")
                yield point.get("questionId")
                yield point.get("question_id")


def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _unique_text(values: Iterable[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        trimmed = value.strip()
        if not trimmed or trimmed in seen:
            continue
        seen.add(trimmed)
        out.append(trimmed)
    return out


def build_equity_bridge(
    *,
    enterprise_value: Decimal | None,
    total_debt: Decimal,
    cash: Decimal,
    nwc_normalization: Mapping[str, object] | None,
    real_estate_surplus: Decimal,
    bridge_adjustments: Mapping[str, object] | None = None,
    equity_value: Decimal | None,
    show_bridge: bool = True,
) -> EquityBridge:
    """Itemized EV -> net debt -> NWC -> surplus -> equity bridge (BET-534).

    Debt and cash are shown as separate legs (itemized net debt), never a single
    opaque figure, and missing balance-sheet inputs are disclosed honestly
    rather than back-derived from the equity gap.
    """
    if enterprise_value is None:
        return _suppressed_equity_bridge(equity_value)

    net_debt = (total_debt or Decimal("0")) - (cash or Decimal("0"))
    lines = _debt_cash_bridge_lines(total_debt=total_debt, cash=cash)
    nwc_status, nwc_note, nwc_lines = _nwc_bridge_components(nwc_normalization)
    lines.extend(nwc_lines)
    surplus_line = _surplus_asset_bridge_line(real_estate_surplus)
    if surplus_line is not None:
        lines.append(surplus_line)
    lines.extend(_explicit_adjustment_bridge_lines(bridge_adjustments))

    return EquityBridge(
        enterprise_value=enterprise_value,
        lines=lines,
        equity_value=equity_value,
        net_debt=net_debt,
        nwc_status=nwc_status,
        nwc_note=nwc_note,
        is_phantom_suppressed=False,
        notes=[] if show_bridge else ["EV->equity bridge hidden by presentation toggle."],
    )


def _suppressed_equity_bridge(equity_value: Decimal | None) -> EquityBridge:
    return EquityBridge(
        enterprise_value=None,
        equity_value=equity_value,
        nwc_status="not_assessed",
        is_phantom_suppressed=True,
        notes=["EV->equity bridge suppressed: no enterprise value on this path."],
    )


def _debt_cash_bridge_lines(
    *,
    total_debt: Decimal,
    cash: Decimal,
) -> list[EquityBridgeLine]:
    lines: list[EquityBridgeLine] = []
    if total_debt and total_debt != Decimal("0"):
        lines.append(
            EquityBridgeLine(
                key="total_debt",
                label="Less: total debt",
                amount=total_debt,
                operator="-",
                kind="debt",
            )
        )
    if cash and cash != Decimal("0"):
        lines.append(
            EquityBridgeLine(
                key="cash",
                label="Add: cash & equivalents",
                amount=cash,
                operator="+",
                kind="cash",
            )
        )
    return lines


def _nwc_bridge_components(
    nwc_normalization: Mapping[str, object] | None,
) -> tuple[str, str | None, list[EquityBridgeLine]]:
    nwc = nwc_normalization if isinstance(nwc_normalization, Mapping) else None
    nwc_status = "not_assessed"
    nwc_note: str | None = "Net working capital not assessed - no balance sheet."
    if nwc is None or not nwc.get("available", True) or nwc.get("computation_error"):
        return nwc_status, nwc_note, []

    surplus_deficit = _dec(nwc.get("surplus_deficit"))
    nwc_status = "assessed"
    nwc_note = nwc.get("methodology") or nwc.get("note")
    line = _nwc_bridge_line(surplus_deficit, nwc_note)
    return (
        nwc_status,
        nwc_note if isinstance(nwc_note, str) else None,
        ([line] if line is not None else []),
    )


def _nwc_bridge_line(
    surplus_deficit: Decimal | None,
    nwc_note: object,
) -> EquityBridgeLine | None:
    if surplus_deficit is None or surplus_deficit == Decimal("0"):
        return None
    return EquityBridgeLine(
        key="nwc_normalization",
        label="NWC normalization (actual vs normal)",
        amount=abs(surplus_deficit),
        operator="+" if surplus_deficit >= 0 else "-",
        kind="nwc",
        detail=nwc_note if isinstance(nwc_note, str) else None,
    )


def _surplus_asset_bridge_line(real_estate_surplus: Decimal) -> EquityBridgeLine | None:
    if real_estate_surplus and real_estate_surplus != Decimal("0"):
        return EquityBridgeLine(
            key="surplus_assets",
            label="Add: surplus / non-operating assets",
            amount=abs(real_estate_surplus),
            operator="+" if real_estate_surplus >= 0 else "-",
            kind="surplus",
        )
    return None


def _explicit_adjustment_bridge_lines(
    bridge_adjustments: Mapping[str, object] | None,
) -> list[EquityBridgeLine]:
    if not isinstance(bridge_adjustments, Mapping):
        return []
    raw_rows = bridge_adjustments.get("rows")
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        return []

    lines: list[EquityBridgeLine] = []
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, Mapping) or not raw.get("applied", True):
            continue
        signed_amount = _dec(raw.get("signed_amount"))
        if signed_amount is None or signed_amount == Decimal("0"):
            continue
        lines.append(
            EquityBridgeLine(
                key=str(raw.get("key") or f"bridge_adjustment_{index + 1}"),
                label=str(raw.get("label") or "Equity bridge adjustment"),
                amount=abs(signed_amount),
                operator="+" if signed_amount >= 0 else "-",
                kind=str(raw.get("category") or "adjustment"),
                detail=(
                    str(raw.get("description")) if raw.get("description") is not None else None
                ),
            )
        )
    return lines


def _multiple_type_blend(blend: Mapping[str, object] | None) -> Optional[MultipleTypeBlend]:
    if not isinstance(blend, Mapping) or not blend:
        return None
    return MultipleTypeBlend(
        source=str(blend.get("source") or "sector_aware_default"),
        model_source=str(blend.get("model_source") or "sector_aware_default"),
        weighted_enterprise_value=_dec(blend.get("weighted_enterprise_value")) or Decimal("0"),
        rows=_multiple_type_blend_rows(blend.get("rows")),
    )


def _multiple_type_blend_rows(rows_raw: object) -> list[MultipleTypeBlendRow]:
    if not isinstance(rows_raw, Sequence):
        return []

    return [_multiple_type_blend_row(raw) for raw in rows_raw if isinstance(raw, Mapping)]


def _multiple_type_blend_row(raw: Mapping[str, object]) -> MultipleTypeBlendRow:
    return MultipleTypeBlendRow(
        key=str(raw.get("key") or "ev_ebitda"),
        label=str(raw.get("label") or "EV/EBITDA"),
        enterprise_value=_dec(raw.get("enterprise_value")) or Decimal("0"),
        weight=_dec(raw.get("weight")) or Decimal("0"),
        model_weight=_dec(raw.get("model_weight")) or Decimal("0"),
        advisor_delta=_dec(raw.get("advisor_delta")) or Decimal("0"),
        contribution=_dec(raw.get("contribution")) or Decimal("0"),
        included=bool(raw.get("included", True)),
    )


def _advisor_override(advisor_override: Mapping[str, object] | None) -> Optional[AdvisorOverride]:
    if not isinstance(advisor_override, Mapping) or not advisor_override:
        return None
    model_value = _dec(advisor_override.get("model_effective_multiple"))
    advisor_value = _dec(advisor_override.get("advisor_effective_multiple"))
    delta = _dec(advisor_override.get("delta_multiple"))
    if delta is None and model_value is not None and advisor_value is not None:
        delta = advisor_value - model_value
    return AdvisorOverride(
        kind=str(advisor_override.get("kind") or "effective_multiple"),
        model_value=model_value,
        advisor_value=advisor_value,
        delta=delta,
        note=advisor_override.get("note"),
        out_of_band=bool(advisor_override.get("out_of_band", False)),
        index_protected=bool(advisor_override.get("index_protected", True)),
        advisor_id=advisor_override.get("advisor_id"),
        timestamp=advisor_override.get("timestamp"),
    )


def assemble_multiple_build_up(
    *,
    basis: str,
    basis_rationale: str | None,
    reported_earnings: Decimal | None,
    adjusted_earnings: Decimal | None,
    add_back_ledger: Mapping[str, object] | None,
    segment_valuation: Mapping[str, object] | None,
    primary_basis: str,
    primary_meta: Mapping[str, object] | None,
    benchmark_provenance: Mapping[str, object] | None,
    primary_multiple: Decimal | None,
    primary_p25: Decimal | None,
    primary_median: Decimal | None,
    primary_p75: Decimal | None,
    discount_build_up: Mapping[str, object] | None,
    multiple_type_blend: Mapping[str, object] | None,
    advisor_override: Mapping[str, object] | None,
    risk_analysis_enabled: bool,
    equity_bridge: EquityBridge,
    effective_multiple: Decimal | None,
    enterprise_value: Decimal | None,
    equity_value: Decimal | None,
    band_low: Decimal | None,
    band_high: Decimal | None,
    primary_is_override: bool = False,
    tier: str = "firm",
    priced_earnings_basis: EarningsBasisBuildUp | None = None,
) -> MultipleBuildUp:
    """Assemble the one canonical typed build-up from already-computed pieces."""
    segments, segment_mode, is_multi = _segments(
        segment_valuation,
        primary_basis=primary_basis,
        primary_meta=primary_meta,
        benchmark_provenance=benchmark_provenance,
        primary_multiple=primary_multiple,
        primary_p25=primary_p25,
        primary_median=primary_median,
        primary_p75=primary_p75,
        primary_enterprise_value=enterprise_value,
        primary_is_override=primary_is_override,
    )

    return MultipleBuildUp(
        tier=tier,
        # Stateless callers supply a projection of authenticated, deduplicated
        # decisions. Legacy client ledgers retain the conservative fallback.
        earnings_basis=(
            priced_earnings_basis
            if priced_earnings_basis is not None
            else _earnings_basis_build_up(
                basis=basis,
                rationale=basis_rationale,
                reported_earnings=reported_earnings,
                adjusted_earnings=adjusted_earnings,
                add_back_ledger=add_back_ledger,
            )
        ),
        segments=segments,
        is_multi_segment=is_multi,
        segment_mode=segment_mode,
        multiple_type_blend=_multiple_type_blend(multiple_type_blend),
        discounts=_discount_stack(discount_build_up),
        advisor_override=_advisor_override(advisor_override),
        risk_analysis_enabled=risk_analysis_enabled,
        risk_analysis_reference_only=not risk_analysis_enabled,
        equity_bridge=equity_bridge,
        adjusted_earnings=adjusted_earnings,
        effective_multiple=effective_multiple,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        band_low=band_low,
        band_high=band_high,
    )
