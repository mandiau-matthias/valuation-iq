"""Owner-profiling report-section context builder."""

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Optional, TypeAlias

from src.domain.synthesis.owner_dependency_processor import MVP_OWNER_ADJUSTMENT_FLOOR
from src.services.progressive.coordinators.summary_generation_coordinator import (
    SummaryGenerationCoordinator,
)
from src.services.reports.protocol_adapter import coerce_json_object
from src.services.reports.report_owner_transferability_context import (
    build_transferability_profile_context,
    normalize_transferability_profile,
)

JsonMap: TypeAlias = dict[str, object]
PostDealSwapBuilder: TypeAlias = Callable[[Optional[object]], Optional[JsonMap]]
TransferabilityBuilder: TypeAlias = Callable[[object, object], Optional[JsonMap]]


def build_owner_profiling_section_context(
    response: Optional[object],
    t: object,
    *,
    is_owner_dep_methodology: bool = True,
    build_post_deal_swap_context: PostDealSwapBuilder,
    build_transferability_v2_context: TransferabilityBuilder,
) -> JsonMap:
    """Build the pro-report Owner Profiling section context (OP-6)."""
    empty: JsonMap = {
        "show_owner_profiling_section": False,
        "owner_profiling": None,
    }

    if response is None:
        return empty

    odr = getattr(response, "owner_dependency_result", None)
    if odr is None:
        return empty

    fields = _owner_dependency_fields(odr)
    score_clamped = max(0.0, min(100.0, _float_or_zero(fields["overall_score"])))
    transferability_index = max(0, min(100, int(round(100.0 - score_clamped))))
    adjustment = _decimal_or_zero(fields["valuation_adjustment"])
    raw_adjustment = _optional_decimal(fields["raw_adjustment"])
    was_capped = raw_adjustment is not None and raw_adjustment < adjustment
    cap_floor_pct = float(MVP_OWNER_ADJUSTMENT_FLOOR * Decimal("100"))
    risk_label, risk_band = _risk_label_and_band(fields["risk_level"], t)

    return {
        "show_owner_profiling_section": True,
        "owner_profiling": {
            "state": _profile_state(
                fields=fields,
                adjustment=adjustment,
                raw_adjustment=raw_adjustment,
                was_capped=was_capped,
            ),
            "overall_score": int(round(score_clamped)),
            "transferability_index": transferability_index,
            "risk_level_raw": (
                str(fields["risk_level"]).strip().upper() if fields["risk_level"] else ""
            ),
            "risk_level_label": risk_label,
            "risk_band": risk_band,
            "adjustment_pct": float(adjustment * Decimal("100")),
            "raw_adjustment_pct": (
                float(raw_adjustment * Decimal("100")) if raw_adjustment is not None else None
            ),
            "was_capped": was_capped,
            "cap_floor_pct": cap_floor_pct,
            "cap_chip_text": _cap_chip_text(t, cap_floor_pct),
            "explanation": fields["explanation"],
            "key_risks": list(fields["key_risks"])[:5],
            "recommendations": _recommendations(response, fields),
            "post_deal_swap": build_post_deal_swap_context(response),
            "transferability_v2": build_transferability_v2_context(odr, t),
        },
    }


def build_transferability_v2_context(
    odr: object,
    t: object,
) -> Optional[JsonMap]:
    """Project ``transferability_profile`` onto a flat dict for Jinja."""
    profile = normalize_transferability_profile(odr)
    if profile is None:
        return None
    return build_transferability_profile_context(profile, t)


def build_post_deal_swap_context(
    response: Optional[object],
) -> Optional[JsonMap]:
    """Project the engine's `owner_compensation_swap` onto a flat dict."""
    if response is None:
        return None
    swap = getattr(response, "owner_compensation_swap", None)
    if swap is None:
        return None

    fields = _swap_fields(swap)
    state_str = str(fields["state"] or ("applied" if fields["applied"] else "unknown"))
    if not fields["applied"] and state_str != "not_applicable":
        return None

    return {
        "applied": fields["applied"],
        "state": state_str,
        "pre_deal_equity_value": _optional_float(fields["pre_value"]),
        "post_deal_equity_value": _optional_float(fields["post_value"]),
        "owner_compensation_actual": _optional_float(fields["actual"]),
        "market_replacement_cost": _optional_float(fields["market"]),
        "effective_multiple": _optional_float(fields["multiple"]),
        "equity_delta": _optional_float(fields["equity_delta"]) or 0.0,
        "data_quality": str(fields["data_quality"] or "unknown"),
        "rationale": fields["rationale"],
    }


def _owner_dependency_fields(odr: object) -> JsonMap:
    if isinstance(odr, Mapping):
        return {
            "overall_score": odr.get("overall_score"),
            "risk_level": odr.get("risk_level"),
            "valuation_adjustment": odr.get("valuation_adjustment"),
            "raw_adjustment": odr.get("raw_adjustment"),
            "explanation": odr.get("explanation"),
            "key_risks": odr.get("key_risks") or [],
            "recommendations": odr.get("recommendations") or [],
            "transferability_profile": odr.get("transferability_profile"),
        }
    return {
        "overall_score": getattr(odr, "overall_score", None),
        "risk_level": getattr(odr, "risk_level", None),
        "valuation_adjustment": getattr(odr, "valuation_adjustment", None),
        "raw_adjustment": getattr(odr, "raw_adjustment", None),
        "explanation": getattr(odr, "explanation", None) or "",
        "key_risks": list(getattr(odr, "key_risks", None) or []),
        "recommendations": list(getattr(odr, "recommendations", None) or []),
        "transferability_profile": getattr(odr, "transferability_profile", None),
    }


def _recommendations(response: object, fields: JsonMap) -> list[str]:
    evidence_rows = _strength_factor_evidence_rows(response)
    if evidence_rows:
        evidence_backed = SummaryGenerationCoordinator().generate_strength_factor_recommendations(
            {"business_context": {"strength_factor_discount_evidence": evidence_rows}}
        )
        if evidence_backed:
            return evidence_backed[:5]
    return list(fields["recommendations"])[:5]


def _strength_factor_evidence_rows(response: object) -> list[Mapping[str, object]]:
    rows: list[Mapping[str, object]] = []
    for container in _strength_factor_containers(response):
        rows.extend(_strength_factor_rows_from_mapping(container))
    return _dedupe_mappings(rows)


def _strength_factor_containers(response: object) -> list[Mapping[str, object]]:
    containers: list[Mapping[str, object]] = []
    for key in ("multiple_build_up", "discount_build_up"):
        child = _as_mapping(_get_value(response, key))
        if child:
            containers.append(child)

    for source in (
        response,
        _get_value(response, "multiples_valuation"),
        _get_value(response, "multiples_results"),
    ):
        source_map = _as_mapping(source)
        if not source_map:
            continue
        containers.append(source_map)
        for key in ("multiple_build_up", "discount_build_up"):
            child = _as_mapping(source_map.get(key))
            if child:
                containers.append(child)
    return containers


def _strength_factor_rows_from_mapping(
    container: Mapping[str, object]
) -> list[Mapping[str, object]]:
    rows: list[Mapping[str, object]] = []

    rows.extend(_evidence_rows(container))
    for key in ("rows", "discount_waterfall", "waterfall"):
        rows.extend(_evidence_rows_from_sequence(container.get(key)))

    discounts = _as_mapping(container.get("discounts"))
    if discounts:
        rows.extend(_strength_factor_rows_from_mapping(discounts))

    return rows


def _evidence_rows_from_sequence(value: object) -> list[Mapping[str, object]]:
    rows: list[Mapping[str, object]] = []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return rows
    for item in value:
        item_map = _as_mapping(item)
        if not item_map:
            continue
        rows.extend(_evidence_rows(item_map))
    return rows


def _evidence_rows(row: Mapping[str, object]) -> list[Mapping[str, object]]:
    rows: list[Mapping[str, object]] = []
    for key in ("strength_factor_evidence", "strength_factor_discount_evidence"):
        value = row.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value:
                item_map = _as_mapping(item)
                if item_map:
                    rows.append(item_map)
        else:
            item_map = _as_mapping(value)
            if item_map:
                rows.append(item_map)

    if _is_strength_factor_row(row):
        rows.append(row)
    return rows


def _is_strength_factor_row(row: Mapping[str, object]) -> bool:
    return any(
        _has_value(row.get(key))
        for key in (
            "factor_key",
            "factorKey",
            "factor_label",
            "factorLabel",
            "improvement_action",
            "improvementAction",
            "valuation_linkage",
            "valuationLinkage",
            "discount_key",
            "discountKey",
            "multiple_discount_key",
            "multipleDiscountKey",
            "data_point_id",
            "dataPointId",
            "data_point_ids",
            "dataPointIds",
            "dataPoints",
        )
    )


def _has_value(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return value is not None


def _as_mapping(value: object) -> Mapping[str, object] | None:
    coerced = coerce_json_object(value)
    if coerced is not None:
        return coerced
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
        except Exception:
            return None
        return dumped if isinstance(dumped, Mapping) else None
    if hasattr(value, "dict"):
        try:
            dumped = value.dict()
        except Exception:
            return None
        return dumped if isinstance(dumped, Mapping) else None
    return None


def _get_value(source: object, key: str) -> object:
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _dedupe_mappings(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    deduped: list[Mapping[str, object]] = []
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(f"{item_key}={row.get(item_key)}" for item_key in sorted(row.keys()))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _profile_state(
    *,
    fields: JsonMap,
    adjustment: Decimal,
    raw_adjustment: Decimal | None,
    was_capped: bool,
) -> str:
    has_assessment = (
        fields["overall_score"] is not None
        or adjustment != Decimal("0")
        or raw_adjustment is not None
        or bool(fields["transferability_profile"])
    )
    if not has_assessment:
        return "skipped"
    return "capped" if was_capped else "pass_through"


def _risk_label_and_band(risk_level: object, t: object) -> tuple[object, str]:
    rl_upper = str(risk_level).strip().upper() if risk_level else ""
    risk_label_map = {
        "MINIMAL": (t.owner_profiling_risk_minimal, "good"),
        "LOW": (t.owner_profiling_risk_low, "neutral"),
        "MEDIUM": (t.owner_profiling_risk_medium, "neutral"),
        "HIGH": (t.owner_profiling_risk_high, "caution"),
        "CRITICAL": (t.owner_profiling_risk_critical, "warn"),
    }
    return risk_label_map.get(rl_upper, (rl_upper.title() if rl_upper else "", "neutral"))


def _cap_chip_text(t: object, cap_floor_pct: float) -> object:
    try:
        return t.owner_profiling_cap_applied_note.format(cap_pct=f"{cap_floor_pct:.0f}")
    except (KeyError, ValueError, TypeError):
        return ""


def _swap_fields(swap: object) -> JsonMap:
    if isinstance(swap, Mapping):
        return {
            "applied": bool(swap.get("applied")),
            "state": swap.get("state"),
            "pre_value": swap.get("pre_deal_equity_value"),
            "post_value": swap.get("post_deal_equity_value"),
            "actual": swap.get("owner_compensation_actual"),
            "market": swap.get("market_replacement_cost"),
            "multiple": swap.get("effective_multiple"),
            "equity_delta": swap.get("equity_delta"),
            "data_quality": swap.get("data_quality"),
            "rationale": swap.get("rationale") or "",
        }
    return {
        "applied": bool(getattr(swap, "applied", False)),
        "state": getattr(swap, "state", None),
        "pre_value": getattr(swap, "pre_deal_equity_value", None),
        "post_value": getattr(swap, "post_deal_equity_value", None),
        "actual": getattr(swap, "owner_compensation_actual", None),
        "market": getattr(swap, "market_replacement_cost", None),
        "multiple": getattr(swap, "effective_multiple", None),
        "equity_delta": getattr(swap, "equity_delta", None),
        "data_quality": getattr(swap, "data_quality", None),
        "rationale": getattr(swap, "rationale", None) or "",
    }


def _float_or_zero(value: object) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value: object) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError, ArithmeticError):
        return None


def _decimal_or_zero(value: object) -> Decimal:
    try:
        return Decimal(str(value)) if value is not None else Decimal("0")
    except (InvalidOperation, TypeError, ValueError, ArithmeticError):
        return Decimal("0")


def _optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError, ArithmeticError):
        return None
