"""
Multiple pipeline assembly helpers.

Keeps Step 11 pipeline state transitions testable and out of the coordinator.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Protocol, cast

from src.api.routes.valuation.steps.step_11_synthesis.builders.coordinators.types import (
    GetPreviousStepResultFunc,
    MultiplePipeline,
    PreviousResults,
)
from src.api.routes.valuation.steps.strength_factor_discount_adjustments import (
    strength_factor_discount_lineage_payload,
)
from src.errors import ValidationError
from src.utils.decimal_helpers import pin_band_monotone, to_decimal

from .validation import BankGradeValidator

PIPELINE_STEP_NUMBERS = (4, 4.5, 5, 6)


class PipelineLogger(Protocol):
    def debug(self, message: str, **kwargs: object) -> None: ...

    def warning(self, message: str, **kwargs: object) -> None: ...


@dataclass(frozen=True)
class PipelineMultiples:
    low: Decimal
    mid: Decimal
    high: Decimal


@dataclass
class PipelineContext:
    initial_low: Optional[Decimal]
    initial_mid: Decimal
    initial_high: Optional[Decimal]
    metric_type: object
    metric_value: Decimal
    current: PipelineMultiples
    stages: list[dict[str, object]] = field(default_factory=list)
    discount_waterfall: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class PipelineStepRecord:
    next_multiples: PipelineMultiples
    waterfall_step: Optional[dict[str, object]]
    pipeline_stage: Optional[dict[str, object]] = None
    step_name: object = None
    discount_percentage: object = None
    multiple_before_mid: object = None
    multiple_after_mid: object = None


def first_present(mapping: Mapping[str, object], *keys: str, default: object = None) -> object:
    """Return the first present, non-None value while preserving explicit zeroes."""
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def build_pipeline_context(step3: Mapping[str, object]) -> Optional[PipelineContext]:
    initial_multiple_low = BankGradeValidator.ensure_decimal(
        first_present(step3, "initial_multiple_low", "multiple_p25"),
        "initial_multiple_low",
        None,
    )
    initial_multiple_mid = BankGradeValidator.ensure_decimal(
        first_present(step3, "initial_multiple_mid", "multiple_p50"),
        "initial_multiple_mid",
        None,
    )
    initial_multiple_high = BankGradeValidator.ensure_decimal(
        first_present(step3, "initial_multiple_high", "multiple_p75"),
        "initial_multiple_high",
        None,
    )
    metric_value = BankGradeValidator.ensure_decimal(
        step3.get("primary_metric_value"),
        "primary_metric_value",
        None,
    )

    if initial_multiple_mid is None or initial_multiple_mid == Decimal("0"):
        return None
    if metric_value is None:
        return None

    current = PipelineMultiples(
        low=initial_multiple_low if initial_multiple_low is not None else initial_multiple_mid,
        mid=initial_multiple_mid,
        high=(initial_multiple_high if initial_multiple_high is not None else initial_multiple_mid),
    )
    context = PipelineContext(
        initial_low=initial_multiple_low,
        initial_mid=initial_multiple_mid,
        initial_high=initial_multiple_high,
        metric_type=step3.get("primary_metric", "EBITDA"),
        metric_value=metric_value,
        current=current,
    )
    context.discount_waterfall.append(_initial_waterfall_step(context))
    return context


def collect_pipeline_steps(
    context: PipelineContext,
    previous_results: PreviousResults,
    get_previous_step_result_func: GetPreviousStepResultFunc,
    logger: PipelineLogger,
) -> None:
    for step_num in PIPELINE_STEP_NUMBERS:
        step_result = get_previous_step_result_func(step_num, previous_results)
        record = _build_step_record(step_num, step_result, context.current)
        if record is None:
            continue

        if record.pipeline_stage is not None:
            context.stages.append(record.pipeline_stage)
        if record.waterfall_step is not None:
            context.discount_waterfall.append(record.waterfall_step)

        context.current = record.next_multiples
        _log_stage_collection(logger, step_num, record)


def build_pipeline_result(
    context: PipelineContext,
    logger: PipelineLogger,
) -> MultiplePipeline:
    if not context.stages:
        logger.warning(
            "⚠️ Step 11: No pipeline stages collected from Steps 4-6 (incl. 4.5)",
            extra={"step_number": 11},
        )
        return _pipeline_dict(context, context.current, Decimal("0.0"))

    final_multiples = _final_pipeline_multiples(context, logger)
    total_reduction_pct = _total_reduction_percentage(
        context.initial_mid,
        final_multiples.mid,
        logger,
    )
    return _pipeline_dict(context, final_multiples, total_reduction_pct)


def _initial_waterfall_step(context: PipelineContext) -> dict[str, object]:
    return {
        "step": "Initial",
        "step_name": "Base Multiple (Step 3)",
        "multiple_before_low": None,
        "multiple_before_mid": None,
        "multiple_before_high": None,
        "multiple_after_low": context.current.low,
        "multiple_after_mid": context.current.mid,
        "multiple_after_high": context.current.high,
        "discount_percentage": Decimal("0.0"),
        "description": (f"Initial {context.metric_type} multiple from industry comparables"),
    }


def _build_step_record(
    step_num: int | float,
    step_result: Optional[Mapping[str, object]],
    current: PipelineMultiples,
) -> Optional[PipelineStepRecord]:
    if not step_result and step_num in (5, 6):
        return _missing_discount_step_record(step_num, current)
    if not step_result:
        return None
    if step_num == 4.5:
        return _revenue_trend_step_record(step_result, current)
    if "pipeline_stage" in step_result:
        return _existing_pipeline_stage_record(step_num, step_result, current)
    if step_num in (5, 6):
        return _fallback_discount_step_record(step_num, step_result, current)
    return None


def _missing_discount_step_record(
    step_num: int | float,
    current: PipelineMultiples,
) -> PipelineStepRecord:
    step_name = "Size Discount" if step_num == 5 else "Liquidity Discount"
    description = (
        "Size discount: 0% (included in Step 2 calibration for SMEs)"
        if step_num == 5
        else "Liquidity discount: 0% (captured in Steps 2+4 for SMEs)"
    )
    return PipelineStepRecord(
        next_multiples=current,
        waterfall_step=_waterfall_step(
            step_num=step_num,
            step_name=step_name,
            before=current,
            after=current,
            discount_percentage=Decimal("0.0"),
            description=description,
        ),
    )


def _revenue_trend_step_record(
    step_result: Mapping[str, object],
    current: PipelineMultiples,
) -> Optional[PipelineStepRecord]:
    multiple_before_raw = step_result.get("multiple_before")
    multiple_after_raw = first_present(step_result, "multiple_after", "adjusted_multiple")
    if multiple_before_raw is None or multiple_after_raw is None:
        return None

    multiple_before_mid = to_decimal(multiple_before_raw)
    multiple_after_mid = to_decimal(multiple_after_raw)
    discount_pct_raw = step_result.get("revenue_trend_adjustment_percentage")
    discount_pct = to_decimal(discount_pct_raw) if discount_pct_raw is not None else Decimal("0.0")
    ratio = multiple_after_mid / multiple_before_mid if multiple_before_mid > 0 else Decimal("1.0")
    after = PipelineMultiples(
        low=current.low * ratio,
        mid=multiple_after_mid,
        high=current.high * ratio,
    )
    before = PipelineMultiples(
        low=current.low,
        mid=multiple_before_mid,
        high=current.high,
    )
    pipeline_stage = {
        "step_number": 4.5,
        "step_name": "Revenue Trend",
        "discount_type": "revenue_trend",
        "discount_percentage": discount_pct,
        "multiple_before_low": before.low,
        "multiple_before_mid": before.mid,
        "multiple_before_high": before.high,
        "multiple_after_low": after.low,
        "multiple_after_mid": after.mid,
        "multiple_after_high": after.high,
        "description": (f"Revenue Trend Adjustment: {discount_pct:.1f}% applied to multiple"),
    }
    return _stage_record(4.5, pipeline_stage, before, after, discount_pct)


def _existing_pipeline_stage_record(
    step_num: int | float,
    step_result: Mapping[str, object],
    current: PipelineMultiples,
) -> PipelineStepRecord:
    pipeline_stage = _stage_mapping(step_result["pipeline_stage"])
    before = PipelineMultiples(
        low=_decimal_stage_value(pipeline_stage, "multiple_before_low", current.low),
        mid=_decimal_stage_value(pipeline_stage, "multiple_before_mid", current.mid),
        high=_decimal_stage_value(pipeline_stage, "multiple_before_high", current.high),
    )
    after = PipelineMultiples(
        low=_decimal_stage_value(pipeline_stage, "multiple_after_low", current.low),
        mid=_decimal_stage_value(pipeline_stage, "multiple_after_mid", current.mid),
        high=_decimal_stage_value(pipeline_stage, "multiple_after_high", current.high),
    )
    discount_pct = pipeline_stage.get("discount_percentage", Decimal("0.0"))
    return _stage_record(step_num, pipeline_stage, before, after, discount_pct)


def _fallback_discount_step_record(
    step_num: int | float,
    step_result: Mapping[str, object],
    current: PipelineMultiples,
) -> PipelineStepRecord:
    mult_before_raw = step_result.get("multiple_before_mid")
    mult_before = to_decimal(mult_before_raw) if mult_before_raw is not None else current.mid
    mult_after_raw = first_present(
        step_result,
        "multiple_after_mid",
        "current_multiple_mid",
        default=current.mid,
    )
    mult_after = to_decimal(mult_after_raw)
    discount_pct = _fallback_discount_percentage(step_num, step_result)
    ratio = mult_after / mult_before if mult_before and mult_before > 0 else Decimal("1.0")
    before = PipelineMultiples(low=current.low, mid=mult_before, high=current.high)
    after = PipelineMultiples(
        low=current.low * ratio,
        mid=mult_after,
        high=current.high * ratio,
    )
    step_name = "Size Discount" if step_num == 5 else "Liquidity Discount"
    pipeline_stage = {
        "step_number": step_num,
        "step_name": step_name,
        "discount_percentage": discount_pct,
        "multiple_before_mid": mult_before,
        "multiple_after_mid": mult_after,
        "description": step_result.get("size_discount_note")
        or step_result.get("explanation", f"Step {step_num} applied"),
    }
    pipeline_stage.update(strength_factor_discount_lineage_payload(step_result))
    return _stage_record(step_num, pipeline_stage, before, after, discount_pct)


def _fallback_discount_percentage(
    step_num: int | float,
    step_result: Mapping[str, object],
) -> Decimal:
    keys = (
        (
            "discount_applied_to_multiple",
            "size_discount_percentage",
            "size_discount",
            "total_discount_percentage",
        )
        if step_num == 5
        else (
            "discount_applied_to_multiple",
            "liquidity_discount_percentage",
            "total_discount_percentage",
            "liquidity_discount",
        )
    )
    discount_pct = to_decimal(first_present(step_result, *keys, default=0))
    if abs(float(discount_pct)) > 1:
        return discount_pct / Decimal("100")
    return discount_pct


def _stage_record(
    step_num: int | float,
    pipeline_stage: dict[str, object],
    before: PipelineMultiples,
    after: PipelineMultiples,
    discount_pct: object,
) -> PipelineStepRecord:
    step_name = pipeline_stage.get("step_name", f"Step {step_num}")
    waterfall_step = _waterfall_step(
        step_num=step_num,
        step_name=step_name,
        before=before,
        after=after,
        discount_percentage=discount_pct,
        description=pipeline_stage.get("description", f"{step_name} discount applied"),
    )
    waterfall_step.update(strength_factor_discount_lineage_payload(pipeline_stage))
    return PipelineStepRecord(
        pipeline_stage=pipeline_stage,
        next_multiples=after,
        waterfall_step=waterfall_step,
        step_name=step_name,
        discount_percentage=discount_pct,
        multiple_before_mid=before.mid,
        multiple_after_mid=after.mid,
    )


def _waterfall_step(
    *,
    step_num: int | float,
    step_name: object,
    before: PipelineMultiples,
    after: PipelineMultiples,
    discount_percentage: object,
    description: object,
) -> dict[str, object]:
    return {
        "step": step_num,
        "step_name": step_name,
        "multiple_before_low": before.low,
        "multiple_before_mid": before.mid,
        "multiple_before_high": before.high,
        "multiple_after_low": after.low,
        "multiple_after_mid": after.mid,
        "multiple_after_high": after.high,
        "discount_percentage": discount_percentage,
        "description": description,
        "model_adjustment": discount_percentage,
        "effective_adjustment": discount_percentage,
        "factor_before": before.mid,
        "factor_after": after.mid,
        "rationale": description,
    }


def _stage_mapping(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(cast(Mapping[str, object], value))
    raise TypeError(f"pipeline_stage must be mapping, got {type(value).__name__}")


def _decimal_stage_value(
    stage: Mapping[str, object],
    key: str,
    fallback: Decimal,
) -> Decimal:
    value = stage.get(key)
    return to_decimal(value) if value is not None else fallback


def _final_pipeline_multiples(
    context: PipelineContext,
    logger: PipelineLogger,
) -> PipelineMultiples:
    final_stage = context.stages[-1]
    final_low = final_stage.get("multiple_after_low", context.current.low)
    final_mid = final_stage.get("multiple_after_mid", context.current.mid)
    final_high = final_stage.get("multiple_after_high", context.current.high)
    return _pin_final_band(
        low=to_decimal(final_low),
        mid=to_decimal(final_mid),
        high=to_decimal(final_high),
        logger=logger,
    )


def _pin_final_band(
    *,
    low: Decimal,
    mid: Decimal,
    high: Decimal,
    logger: PipelineLogger,
) -> PipelineMultiples:
    pinned_low, pinned_mid, pinned_high = pin_band_monotone(low, mid, high)
    if pinned_low != low or pinned_high != high:
        logger.warning(
            "step_11_pipeline_band_pinned",
            extra={
                "step_number": 11,
                "before_low": str(low),
                "before_mid": str(mid),
                "before_high": str(high),
                "after_low": str(pinned_low),
                "after_mid": str(pinned_mid),
                "after_high": str(pinned_high),
                "reason": "calibration stages produced non-monotone band",
            },
        )
    return PipelineMultiples(low=pinned_low, mid=pinned_mid, high=pinned_high)


def _total_reduction_percentage(
    initial_mid: Decimal,
    final_mid: Decimal,
    logger: PipelineLogger,
) -> Decimal:
    if not initial_mid or initial_mid <= 0:
        logger.warning(
            "⚠️ Cannot calculate total reduction - initial_multiple_mid is zero or None",
            extra={"step_number": 11, "initial_multiple_mid": str(initial_mid)},
        )
        return Decimal("0.0")

    reduction_decimal = (final_mid - initial_mid) / initial_mid
    total_reduction_pct = reduction_decimal * Decimal("100.0")
    try:
        BankGradeValidator.validate_percentage(
            reduction_decimal,
            "total_reduction",
            allow_negative=True,
            min_value=Decimal("-1.0"),
            max_value=Decimal("1.0"),
        )
    except ValidationError as error:
        logger.warning(
            f"⚠️ Total reduction percentage validation warning: {error}",
            extra={
                "step_number": 11,
                "reduction_pct": str(total_reduction_pct),
                "initial_multiple": str(initial_mid),
                "final_multiple": str(final_mid),
            },
        )
    return total_reduction_pct


def _pipeline_dict(
    context: PipelineContext,
    final_multiples: PipelineMultiples,
    total_reduction_pct: Decimal,
) -> MultiplePipeline:
    return cast(
        MultiplePipeline,
        {
            "initial_multiple_low": context.initial_low,
            "initial_multiple_mid": context.initial_mid,
            "initial_multiple_high": context.initial_high,
            "final_multiple_low": final_multiples.low,
            "final_multiple_mid": final_multiples.mid,
            "final_multiple_high": final_multiples.high,
            "total_reduction_percentage": total_reduction_pct,
            "metric_type": context.metric_type,
            "metric_value": context.metric_value,
            "stages": context.stages,
            "discount_waterfall": context.discount_waterfall,
        },
    )


def _log_stage_collection(
    logger: PipelineLogger,
    step_num: int | float,
    record: PipelineStepRecord,
) -> None:
    if record.pipeline_stage is None:
        return
    logger.debug(
        f"✓ Step 11: Collected pipeline stage from Step {step_num}",
        extra={
            "step_number": 11,
            "source_step": step_num,
            "stage_name": record.step_name,
            "discount_pct": record.discount_percentage,
            "multiple_before": record.multiple_before_mid,
            "multiple_after": record.multiple_after_mid,
        },
    )
