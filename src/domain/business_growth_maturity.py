"""Business growth maturity stages for SME operating strategy."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from src.domain.business_growth_maturity_actions import STAGE_ACTIONS

JsonMap = dict[str, object]

STAGE_ORDER = ("garage", "family", "village", "town", "city", "metropolis")
_STAGE_INDEX = {stage: index for index, stage in enumerate(STAGE_ORDER)}
_PUBLIC_STAGE_LABELS = {
    "garage": "Micro",
    "family": "Owner-led",
    "village": "Emerging team",
    "town": "Structured SME",
    "city": "Scaled SME",
    "metropolis": "Enterprise-scale",
}


@dataclass(frozen=True)
class StageBand:
    key: str
    min_value: Decimal | int
    max_value: Decimal | int | None
    label: str

    def contains(self, value: Decimal | int) -> bool:
        if value < self.min_value:
            return False
        return self.max_value is None or value < self.max_value


REVENUE_STAGE_BANDS: tuple[StageBand, ...] = (
    StageBand("garage", Decimal("0"), Decimal("100000"), "Below EUR 100k revenue"),
    StageBand("family", Decimal("100000"), Decimal("500000"), "EUR 100k to 500k revenue"),
    StageBand("village", Decimal("500000"), Decimal("1000000"), "EUR 500k to 1m revenue"),
    StageBand("town", Decimal("1000000"), Decimal("2000000"), "EUR 1m to 2m revenue"),
    StageBand("city", Decimal("2000000"), Decimal("5000000"), "EUR 2m to 5m revenue"),
    StageBand("metropolis", Decimal("5000000"), None, "EUR 5m+ revenue"),
)

TEAM_STAGE_BANDS: tuple[StageBand, ...] = (
    StageBand("garage", 0, 2, "0 to 1 FTE"),
    StageBand("family", 2, 6, "2 to 5 FTE"),
    StageBand("village", 6, 16, "6 to 15 FTE"),
    StageBand("town", 16, 51, "16 to 50 FTE"),
    StageBand("city", 51, 201, "51 to 200 FTE"),
    StageBand("metropolis", 201, None, "201+ FTE"),
)


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _classify(value: Decimal | int | None, bands: Iterable[StageBand]) -> str | None:
    if value is None:
        return None
    for band in bands:
        if band.contains(value):
            return band.key
    return None


def classify_revenue_stage(revenue: object) -> str | None:
    """Classify annual revenue into a garage-to-metropolis maturity stage."""
    return _classify(_decimal_or_none(revenue), REVENUE_STAGE_BANDS)


def classify_team_size_stage(team_size: object) -> str | None:
    """Classify FTE/team size into a garage-to-metropolis maturity stage."""
    return _classify(_int_or_none(team_size), TEAM_STAGE_BANDS)


def _stage_label(stage: str | None) -> str | None:
    return _PUBLIC_STAGE_LABELS.get(stage, stage.replace("_", " ").title()) if stage else None


def _band_label(stage: str | None, bands: Iterable[StageBand]) -> str | None:
    if stage is None:
        return None
    for band in bands:
        if band.key == stage:
            return band.label
    return None


def _next_stage(stage: str | None) -> str | None:
    if stage is None:
        return None
    index = _STAGE_INDEX[stage]
    return STAGE_ORDER[index + 1] if index + 1 < len(STAGE_ORDER) else None


def _effective_stage(revenue_stage: str | None, team_stage: str | None) -> str | None:
    if revenue_stage is None:
        return team_stage
    if team_stage is None:
        return revenue_stage
    return min((revenue_stage, team_stage), key=lambda stage: _STAGE_INDEX[stage])


def _alignment(revenue_stage: str | None, team_stage: str | None) -> str:
    if revenue_stage is None or team_stage is None:
        return "partial_data"
    revenue_index = _STAGE_INDEX[revenue_stage]
    team_index = _STAGE_INDEX[team_stage]
    if revenue_index == team_index:
        return "balanced"
    if revenue_index > team_index:
        return "revenue_ahead_of_team"
    return "team_ahead_of_revenue"


def _alignment_challenges(alignment: str) -> list[JsonMap]:
    if alignment == "revenue_ahead_of_team":
        return [
            {
                "key": "team_capacity_lags_revenue",
                "category": "team_capacity",
                "challenge": "Revenue maturity is ahead of team capacity.",
                "todo": "Prioritize delegation, hiring capacity, and operating cadence before adding more complexity.",
                "data_point_ids": [
                    "business_growth_maturity.revenue_stage",
                    "business_growth_maturity.team_stage",
                    "business_growth_maturity.alignment",
                ],
            }
        ]
    if alignment == "team_ahead_of_revenue":
        return [
            {
                "key": "team_capacity_ahead_of_revenue",
                "category": "commercial_efficiency",
                "challenge": "Team capacity is ahead of the current revenue base.",
                "todo": "Refocus roles on pipeline conversion, utilization, and margin recovery.",
                "data_point_ids": [
                    "business_growth_maturity.revenue_stage",
                    "business_growth_maturity.team_stage",
                    "business_growth_maturity.alignment",
                ],
            }
        ]
    return []


def _alignment_label(alignment: str) -> str:
    return {
        "balanced": "Revenue and team are aligned",
        "revenue_ahead_of_team": "Revenue is ahead of team capacity",
        "team_ahead_of_revenue": "Team capacity is ahead of revenue",
        "partial_data": "Partial maturity data",
    }.get(alignment, "Partial maturity data")


def _alignment_summary(alignment: str) -> str:
    return {
        "balanced": (
            "Revenue scale and team capacity point to the same maturity stage; "
            "focus on the next-stage operating system."
        ),
        "revenue_ahead_of_team": (
            "The revenue base has outgrown the current team model; strengthen "
            "delegation, hiring capacity, and operating cadence before adding complexity."
        ),
        "team_ahead_of_revenue": (
            "The team footprint is ahead of the current revenue base; tighten pipeline "
            "conversion, utilization, and margin recovery."
        ),
        "partial_data": (
            "Only one maturity input is available; confirm both revenue and team size "
            "before treating the roadmap as complete."
        ),
    }.get(alignment, "Confirm the missing maturity inputs before finalizing the roadmap.")


def _stage_challenges(stage: str | None) -> list[JsonMap]:
    if stage is None:
        return []
    return [
        {
            "stage": stage,
            "key": action.key,
            "category": action.category,
            "challenge": action.challenge,
            "todo": action.todo,
            "data_point_ids": list(action.data_point_ids),
        }
        for action in STAGE_ACTIONS[stage]
    ]


def _stage_ladder(
    *,
    revenue_stage: str | None,
    team_stage: str | None,
    effective_stage: str | None,
    next_stage: str | None,
) -> list[JsonMap]:
    return [
        {
            "stage": stage,
            "label": _stage_label(stage),
            "is_revenue_stage": stage == revenue_stage,
            "is_team_stage": stage == team_stage,
            "is_effective_stage": stage == effective_stage,
            "is_next_stage": stage == next_stage,
        }
        for stage in STAGE_ORDER
    ]


def build_business_growth_maturity_context(
    *,
    revenue: object,
    team_size: object,
) -> JsonMap:
    """Build the strategy maturity context from revenue and team size."""
    revenue_stage = classify_revenue_stage(revenue)
    team_stage = classify_team_size_stage(team_size)
    effective_stage = _effective_stage(revenue_stage, team_stage)
    next_stage = _next_stage(effective_stage)
    alignment = _alignment(revenue_stage, team_stage)
    challenges = [*_stage_challenges(effective_stage), *_alignment_challenges(alignment)]
    return {
        "revenue": _decimal_or_none(revenue),
        "team_size": _int_or_none(team_size),
        "revenue_stage": revenue_stage,
        "team_stage": team_stage,
        "effective_stage": effective_stage,
        "next_stage": next_stage,
        "revenue_stage_label": _stage_label(revenue_stage),
        "team_stage_label": _stage_label(team_stage),
        "effective_stage_label": _stage_label(effective_stage),
        "next_stage_label": _stage_label(next_stage),
        "revenue_band_label": _band_label(revenue_stage, REVENUE_STAGE_BANDS),
        "team_band_label": _band_label(team_stage, TEAM_STAGE_BANDS),
        "alignment": alignment,
        "alignment_label": _alignment_label(alignment),
        "alignment_summary": _alignment_summary(alignment),
        "stage_ladder": _stage_ladder(
            revenue_stage=revenue_stage,
            team_stage=team_stage,
            effective_stage=effective_stage,
            next_stage=next_stage,
        ),
        "stage_challenges": challenges,
        "todos": [str(row["todo"]) for row in challenges],
    }
