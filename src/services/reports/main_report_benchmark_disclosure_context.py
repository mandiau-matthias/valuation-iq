"""Benchmark disclosure gates for main report aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from src.utils.decimal_helpers import safe_decimal_or_zero

JsonMap = dict[str, object]


@dataclass(frozen=True)
class MainReportBenchmarkDisclosureContext:
    has_benchmark_reference_multiple: bool
    show_size_discount_skipped_note: bool
    show_benchmark_reference_without_table: bool


def _has_benchmark_reference_multiple(
    *,
    multiple_context: Mapping[str, object],
    base_multiple: object,
) -> bool:
    return safe_decimal_or_zero(multiple_context.get("benchmark_multiple_mid")) > Decimal(
        "0"
    ) or safe_decimal_or_zero(base_multiple) > Decimal("0")


def _disclosure_rows(step_data: Mapping[str, object]) -> list[object]:
    return list(step_data.get("discount_waterfall") or []) + list(
        step_data.get("multiple_pipeline") or []
    )


def _row_label(row: JsonMap) -> str:
    return str(
        row.get("stage_name")
        or row.get("label")
        or row.get("step_name")
        or row.get("category")
        or ""
    ).lower()


def _row_delta(row: JsonMap) -> Decimal:
    return safe_decimal_or_zero(
        row.get("adjustment")
        or row.get("impact")
        or row.get("discount")
        or row.get("discount_percentage")
        or 0
    )


def _row_has_size_discount(row: object) -> bool:
    return isinstance(row, dict) and "size" in _row_label(row) and _row_delta(row) != Decimal("0")


def _has_explicit_size_discount(step_data: Mapping[str, object]) -> bool:
    if safe_decimal_or_zero(step_data.get("size_discount_percentage", 0.0)) != Decimal("0"):
        return True
    return any(_row_has_size_discount(row) for row in _disclosure_rows(step_data))


def _is_sme_revenue_scale(revenue_value: Decimal) -> bool:
    return Decimal("0") < revenue_value <= Decimal("5000000")


def _show_size_discount_skipped_note(
    *,
    step_data: Mapping[str, object],
    base_multiple: object,
    revenue_value: Decimal,
    is_dcf_only: bool,
    is_asset_anchored: bool,
) -> bool:
    return (
        not is_dcf_only
        and not is_asset_anchored
        and safe_decimal_or_zero(base_multiple) > Decimal("0")
        and _is_sme_revenue_scale(revenue_value)
        and not _has_explicit_size_discount(step_data)
    )


def _show_benchmark_reference_without_table(
    *,
    has_industry_benchmarks: bool,
    has_benchmark_reference_multiple: bool,
    is_dcf_only: bool,
    is_asset_anchored: bool,
) -> bool:
    return (
        not has_industry_benchmarks
        and has_benchmark_reference_multiple
        and not is_dcf_only
        and not is_asset_anchored
    )


def build_main_report_benchmark_disclosure_context(
    *,
    step_data: Mapping[str, object],
    multiple_context: Mapping[str, object],
    base_multiple: object,
    revenue_value: Decimal,
    has_industry_benchmarks: bool,
    is_dcf_only: bool,
    is_asset_anchored: bool,
) -> MainReportBenchmarkDisclosureContext:
    """Build report disclosure gates for benchmark and size-discount context."""
    has_benchmark_reference_multiple = _has_benchmark_reference_multiple(
        multiple_context=multiple_context,
        base_multiple=base_multiple,
    )
    return MainReportBenchmarkDisclosureContext(
        has_benchmark_reference_multiple=has_benchmark_reference_multiple,
        show_size_discount_skipped_note=_show_size_discount_skipped_note(
            step_data=step_data,
            base_multiple=base_multiple,
            revenue_value=revenue_value,
            is_dcf_only=is_dcf_only,
            is_asset_anchored=is_asset_anchored,
        ),
        show_benchmark_reference_without_table=_show_benchmark_reference_without_table(
            has_industry_benchmarks=has_industry_benchmarks,
            has_benchmark_reference_multiple=has_benchmark_reference_multiple,
            is_dcf_only=is_dcf_only,
            is_asset_anchored=is_asset_anchored,
        ),
    )
