"""Titan normalization metadata helpers for SDE calculations."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from src.utils.decimal_helpers import to_decimal


@dataclass(frozen=True)
class TitanSDEAdjustmentBuckets:
    owner_salary: Decimal = Decimal("0")
    owner_benefits: Decimal = Decimal("0")
    owner_perks: Decimal = Decimal("0")
    non_recurring: Decimal = Decimal("0")
    non_operating: Decimal = Decimal("0")
    other_addbacks: Decimal = Decimal("0")


def bucket_titan_sde_adjustments(adjustments: object) -> TitanSDEAdjustmentBuckets:
    if not isinstance(adjustments, Iterable) or isinstance(adjustments, (str, bytes)):
        return TitanSDEAdjustmentBuckets()

    buckets = TitanSDEAdjustmentBuckets()
    for adjustment in adjustments:
        if isinstance(adjustment, Mapping):
            buckets = _apply_titan_adjustment(buckets, adjustment)
    return buckets


def _apply_titan_adjustment(
    buckets: TitanSDEAdjustmentBuckets,
    adjustment: Mapping[object, object],
) -> TitanSDEAdjustmentBuckets:
    adjustment_type = adjustment.get("adjustment_type") or adjustment.get("category") or ""
    amount = to_decimal(adjustment.get("amount") or 0)

    if adjustment_type == "non_recurring_revenue":
        return _replace_bucket(buckets, non_operating=buckets.non_operating + amount)

    if adjustment.get("is_addback", True) is not True:
        return buckets

    if adjustment_type == "owner_compensation_adjustment":
        return _replace_bucket(buckets, owner_salary=buckets.owner_salary + amount)
    if adjustment_type == "personal_expenses":
        return _replace_bucket(buckets, owner_perks=buckets.owner_perks + amount)
    if adjustment_type == "family_expenses":
        return _replace_bucket(buckets, owner_benefits=buckets.owner_benefits + amount)
    if adjustment_type in ("one_time_expenses", "non_recurring_costs"):
        return _replace_bucket(buckets, non_recurring=buckets.non_recurring + amount)

    return _replace_bucket(buckets, other_addbacks=buckets.other_addbacks + amount)


def _replace_bucket(
    buckets: TitanSDEAdjustmentBuckets,
    *,
    owner_salary: Decimal | None = None,
    owner_benefits: Decimal | None = None,
    owner_perks: Decimal | None = None,
    non_recurring: Decimal | None = None,
    non_operating: Decimal | None = None,
    other_addbacks: Decimal | None = None,
) -> TitanSDEAdjustmentBuckets:
    return TitanSDEAdjustmentBuckets(
        owner_salary=owner_salary if owner_salary is not None else buckets.owner_salary,
        owner_benefits=(owner_benefits if owner_benefits is not None else buckets.owner_benefits),
        owner_perks=owner_perks if owner_perks is not None else buckets.owner_perks,
        non_recurring=non_recurring if non_recurring is not None else buckets.non_recurring,
        non_operating=non_operating if non_operating is not None else buckets.non_operating,
        other_addbacks=(other_addbacks if other_addbacks is not None else buckets.other_addbacks),
    )
