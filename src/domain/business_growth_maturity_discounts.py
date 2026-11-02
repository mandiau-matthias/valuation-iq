"""Discount evidence policy for business growth maturity stages."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from src.domain.business_growth_maturity import STAGE_ORDER, build_business_growth_maturity_context

JsonMap = dict[str, object]


@dataclass(frozen=True)
class GrowthMaturityDiscountPolicy:
    factor_key: str
    factor_label: str
    discount_key: str
    multiple_discount_key: str
    mapped_subjective_input: str
    valuation_effect: str
    engine_driver: str
    adjustment: Decimal
    rationale: str


STAGE_DISCOUNT_POLICY: dict[str, GrowthMaturityDiscountPolicy] = {
    "garage": GrowthMaturityDiscountPolicy(
        factor_key="growth_maturity_stage",
        factor_label="Micro-stage growth maturity",
        discount_key="liquidity_discount",
        multiple_discount_key="transferability_risk_band",
        mapped_subjective_input="transferability",
        valuation_effect="multiple_discount",
        engine_driver="growth_maturity_stage",
        adjustment=Decimal("-0.025"),
        rationale=(
            "Micro-stage companies carry early transferability risk beyond the revenue-size "
            "discount until demand, delivery, and financial cadence are repeatable."
        ),
    ),
    "family": GrowthMaturityDiscountPolicy(
        factor_key="growth_maturity_stage",
        factor_label="Owner-led growth maturity",
        discount_key="liquidity_discount",
        multiple_discount_key="management_depth_discount",
        mapped_subjective_input="management_depth",
        valuation_effect="multiple_discount",
        engine_driver="growth_maturity_stage",
        adjustment=Decimal("-0.015"),
        rationale=(
            "Family-stage companies are beginning to delegate, but buyer transferability "
            "still depends on documented roles, routines, and non-owner delivery."
        ),
    ),
    "village": GrowthMaturityDiscountPolicy(
        factor_key="growth_maturity_stage",
        factor_label="Emerging-team growth maturity",
        discount_key="liquidity_discount",
        multiple_discount_key="operating_quality_discount",
        mapped_subjective_input="operating_quality",
        valuation_effect="multiple_discount",
        engine_driver="growth_maturity_stage",
        adjustment=Decimal("-0.005"),
        rationale=(
            "Village-stage companies need weekly operating cadence, CRM hygiene, and "
            "function ownership before the company is fully transferable."
        ),
    ),
    "city": GrowthMaturityDiscountPolicy(
        factor_key="growth_maturity_stage",
        factor_label="Scaled-SME growth maturity",
        discount_key="growth_premium",
        multiple_discount_key="growth_trend_discount",
        mapped_subjective_input="management_depth",
        valuation_effect="multiple_premium",
        engine_driver="growth_maturity_stage",
        adjustment=Decimal("0.010"),
        rationale=(
            "City-stage companies with matched revenue and team maturity earn a modest "
            "maturity premium for second-line management and buyer-grade operating data."
        ),
    ),
    "metropolis": GrowthMaturityDiscountPolicy(
        factor_key="growth_maturity_stage",
        factor_label="Enterprise-scale growth maturity",
        discount_key="growth_premium",
        multiple_discount_key="growth_trend_discount",
        mapped_subjective_input="management_depth",
        valuation_effect="multiple_premium",
        engine_driver="growth_maturity_stage",
        adjustment=Decimal("0.015"),
        rationale=(
            "Metropolis-stage companies with matched revenue and team maturity earn a "
            "maturity premium for board-grade governance and scalable management systems."
        ),
    ),
}

ALIGNMENT_DISCOUNT_POLICY: dict[str, GrowthMaturityDiscountPolicy] = {
    "revenue_ahead_of_team": GrowthMaturityDiscountPolicy(
        factor_key="growth_maturity_alignment",
        factor_label="Revenue ahead of team maturity",
        discount_key="liquidity_discount",
        multiple_discount_key="management_depth_discount",
        mapped_subjective_input="management_depth",
        valuation_effect="multiple_discount",
        engine_driver="growth_maturity_alignment",
        adjustment=Decimal("-0.030"),
        rationale=(
            "Revenue has outgrown team capacity; valuation should reflect extra "
            "transferability risk until delegation and operating cadence catch up."
        ),
    ),
    "team_ahead_of_revenue": GrowthMaturityDiscountPolicy(
        factor_key="growth_maturity_alignment",
        factor_label="Team maturity ahead of revenue",
        discount_key="revenue_trend",
        multiple_discount_key="growth_trend_discount",
        mapped_subjective_input="revenue_trend",
        valuation_effect="multiple_discount",
        engine_driver="growth_maturity_alignment",
        adjustment=Decimal("-0.025"),
        rationale=(
            "Team capacity is ahead of revenue; valuation should reflect commercial "
            "efficiency risk until pipeline conversion and utilization improve."
        ),
    ),
}


def build_business_growth_maturity_discount_adjustments(
    maturity_context: Mapping[str, object] | None = None,
    *,
    revenue: object = None,
    team_size: object = None,
) -> list[JsonMap]:
    """Build first-class discount evidence from growth maturity stage data.

    Size is already handled by the revenue-size discount curve. This policy only
    adjusts operating maturity, transferability, and growth-quality rows, and it
    requires both revenue and team-stage evidence before changing valuation math.
    """
    maturity = _resolve_maturity_context(
        maturity_context,
        revenue=revenue,
        team_size=team_size,
    )
    if not _has_complete_stage_evidence(maturity):
        return []

    effective_stage = _valid_stage(maturity.get("effective_stage"))
    alignment = _text(maturity.get("alignment"))
    rows: list[JsonMap] = []

    if effective_stage:
        stage_policy = STAGE_DISCOUNT_POLICY.get(effective_stage)
        if stage_policy is not None:
            rows.append(_policy_row(stage_policy, maturity, row_key=effective_stage))

    alignment_policy = ALIGNMENT_DISCOUNT_POLICY.get(alignment)
    if alignment_policy is not None:
        rows.append(_policy_row(alignment_policy, maturity, row_key=alignment))

    return rows


def _resolve_maturity_context(
    maturity_context: Mapping[str, object] | None,
    *,
    revenue: object,
    team_size: object,
) -> JsonMap:
    if isinstance(maturity_context, Mapping):
        normalized = _normalize_embedded_maturity_context(maturity_context)
        if _has_complete_stage_evidence(normalized):
            return normalized
        data_points = _mapping(
            maturity_context.get("data_points") or maturity_context.get("dataPoints")
        )
        revenue = (
            revenue
            if revenue is not None
            else _first_mapping_value(
                data_points,
                ("annual_revenue", "annualRevenue", "revenue"),
            )
        )
        team_size = (
            team_size
            if team_size is not None
            else _first_mapping_value(
                data_points,
                ("employee_count", "employeeCount", "team_size", "teamSize"),
            )
        )
    return build_business_growth_maturity_context(revenue=revenue, team_size=team_size)


def _normalize_embedded_maturity_context(maturity: Mapping[str, object]) -> JsonMap:
    normalized = dict(maturity)
    revenue_stage = _valid_stage(_first_mapping_value(maturity, ("revenue_stage", "revenueStage")))
    team_stage = _valid_stage(_first_mapping_value(maturity, ("team_stage", "teamStage")))
    effective_stage = _valid_stage(
        _first_mapping_value(maturity, ("effective_stage", "effectiveStage"))
    )

    if revenue_stage is not None:
        normalized["revenue_stage"] = revenue_stage
    if team_stage is not None:
        normalized["team_stage"] = team_stage
    if effective_stage is None and revenue_stage is not None and team_stage is not None:
        effective_stage = min(
            (revenue_stage, team_stage),
            key=lambda stage: STAGE_ORDER.index(stage),
        )
    if effective_stage is None:
        effective_stage = _valid_stage(_first_mapping_value(maturity, ("stage", "stageKey")))
    if effective_stage is not None:
        normalized["effective_stage"] = effective_stage

    alignment = _normalize_alignment(
        _first_mapping_value(maturity, ("alignment", "signal_alignment", "signalAlignment")),
        revenue_stage=revenue_stage,
        team_stage=team_stage,
    )
    normalized["alignment"] = alignment
    return normalized


def _normalize_alignment(
    value: object,
    *,
    revenue_stage: str | None,
    team_stage: str | None,
) -> str:
    if revenue_stage is not None and team_stage is not None:
        revenue_index = STAGE_ORDER.index(revenue_stage)
        team_index = STAGE_ORDER.index(team_stage)
        if revenue_index > team_index:
            return "revenue_ahead_of_team"
        if revenue_index < team_index:
            return "team_ahead_of_revenue"
        return "balanced"

    alignment = _text(value)
    if alignment in {"balanced", "revenue_ahead_of_team", "team_ahead_of_revenue"}:
        return alignment
    if alignment in {"partial_data", "insufficient_data", "explicit_only"}:
        return alignment
    return "partial_data"


def _has_complete_stage_evidence(maturity: Mapping[str, object]) -> bool:
    return bool(
        _valid_stage(maturity.get("revenue_stage"))
        and _valid_stage(maturity.get("team_stage"))
        and _valid_stage(maturity.get("effective_stage"))
        and _text(maturity.get("alignment")) != "partial_data"
    )


def _policy_row(
    policy: GrowthMaturityDiscountPolicy,
    maturity: Mapping[str, object],
    *,
    row_key: str,
) -> JsonMap:
    return {
        "factor_key": policy.factor_key,
        "factor_label": policy.factor_label,
        "discount_key": policy.discount_key,
        "multiple_discount_key": policy.multiple_discount_key,
        "mapped_subjective_input": policy.mapped_subjective_input,
        "valuation_effect": policy.valuation_effect,
        "engine_driver": policy.engine_driver,
        "adjustment": policy.adjustment,
        "source": "business_growth_maturity_policy",
        "captured_input_id": _public_data_point_id(f"business_growth_maturity.{row_key}"),
        "data_point_ids": _data_point_ids(maturity),
        "revenue_stage": _public_stage_key(maturity.get("revenue_stage")),
        "team_stage": _public_stage_key(maturity.get("team_stage")),
        "effective_stage": _public_stage_key(maturity.get("effective_stage")),
        "alignment": _text(maturity.get("alignment")),
        "rationale": policy.rationale,
    }


def _data_point_ids(maturity: Mapping[str, object]) -> list[str]:
    ids = [
        "business_growth_maturity.revenue_stage",
        "business_growth_maturity.team_stage",
        "business_growth_maturity.effective_stage",
        "business_growth_maturity.alignment",
    ]
    ids.extend(_stage_challenge_data_point_ids(maturity))
    ids = [_public_data_point_id(item) for item in ids]
    return list(dict.fromkeys(ids))[:8]


def _stage_challenge_data_point_ids(maturity: Mapping[str, object]) -> list[str]:
    rows = maturity.get("stage_challenges")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return []

    effective_stage = _text(maturity.get("effective_stage"))
    data_point_ids: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_stage = _text(row.get("stage"))
        if row_stage and row_stage != effective_stage:
            continue
        for item in _text_list(row.get("data_point_ids")):
            data_point_ids.append(item)
        if len(data_point_ids) >= 4:
            break
    return data_point_ids


def _valid_stage(value: object) -> str | None:
    stage = _text(value)
    return stage if stage in STAGE_ORDER else None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _first_mapping_value(mapping: Mapping[str, object], keys: Sequence[str]) -> object:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return None


def _text(value: object) -> str:
    return str(value or "").strip()


def _public_data_point_id(value: str) -> str:
    return value.replace("business_growth_maturity.garage", "business_growth_maturity.micro_stage")


def _public_stage_key(value: object) -> str:
    stage = _text(value)
    if stage == "garage":
        return "micro_stage"
    return stage


def _text_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]
