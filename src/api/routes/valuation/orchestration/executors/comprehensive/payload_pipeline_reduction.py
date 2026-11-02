"""Compact multiple-pipeline extraction for reduced valuation payloads."""

from __future__ import annotations

from typing import Dict, Optional


def as_dict(value: object) -> Optional[Dict[str, object]]:
    """Best-effort object-to-dict coercion for mixed Pydantic/DictWrapper payloads."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "_data") and isinstance(getattr(value, "_data"), dict):
        return dict(getattr(value, "_data"))
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            dumped = value.dict()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    return None


def first_present(*values: object) -> object:
    """Return the first explicitly present value, preserving zero."""
    for value in values:
        if value is not None:
            return value
    return None


def _pipeline_from_step_11(response: object) -> Optional[Dict[str, object]]:
    transparency = getattr(response, "transparency", None)
    steps_raw = getattr(transparency, "calculation_steps", None) if transparency else None
    steps = as_dict(steps_raw)
    multiples_steps = steps.get("multiples", []) if isinstance(steps, dict) else steps_raw
    if not isinstance(multiples_steps, list):
        return None

    for step in multiples_steps:
        step_dict = as_dict(step)
        if not step_dict or step_dict.get("step") not in (11, 11.0, "11"):
            continue
        result_dict = as_dict(step_dict.get("result"))
        pipeline = result_dict.get("multiple_pipeline") if result_dict else None
        if isinstance(pipeline, dict):
            return pipeline
    return None


def _discount_waterfall(pipeline_raw: Dict[str, object]) -> list[dict[str, object]]:
    discount_waterfall = pipeline_raw.get("discount_waterfall")
    if isinstance(discount_waterfall, list):
        return discount_waterfall

    stages = pipeline_raw.get("stages")
    if not isinstance(stages, list):
        return []

    waterfall: list[dict[str, object]] = []
    for idx, stage in enumerate(stages):
        stage_dict = as_dict(stage)
        if not stage_dict:
            continue
        waterfall.append(
            {
                "step": stage_dict.get("discount_type") or f"stage_{idx}",
                "step_name": stage_dict.get("step_name") or f"Stage {idx + 1}",
                "multiple_before_mid": stage_dict.get("multiple_before"),
                "multiple_after_mid": stage_dict.get("multiple_after"),
                "description": stage_dict.get("explanation", ""),
            }
        )
    return waterfall


def extract_minimal_multiple_pipeline(response: object) -> Optional[Dict[str, object]]:
    """Keep a compact canonical pipeline for report aggregation after payload reduction."""
    pipeline_raw = as_dict(getattr(response, "multiple_pipeline", None))
    if not pipeline_raw:
        pipeline_raw = _pipeline_from_step_11(response)
    if not isinstance(pipeline_raw, dict):
        return None

    final_mid = first_present(
        pipeline_raw.get("final_multiple_mid"),
        pipeline_raw.get("final_multiple"),
    )
    if final_mid in (None, 0, "0", "0.0"):
        return None

    return {
        "metric_type": str(pipeline_raw.get("metric_type") or "EBITDA").upper(),
        "metric_value": pipeline_raw.get("metric_value"),
        "initial_multiple_mid": first_present(
            pipeline_raw.get("initial_multiple_mid"),
            pipeline_raw.get("initial_multiple"),
        ),
        "final_multiple_low": first_present(pipeline_raw.get("final_multiple_low"), final_mid),
        "final_multiple_mid": final_mid,
        "final_multiple_high": first_present(pipeline_raw.get("final_multiple_high"), final_mid),
        "discount_waterfall": _discount_waterfall(pipeline_raw),
    }
