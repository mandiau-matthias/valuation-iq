"""Step-data recovery helpers for report aggregation."""

from collections.abc import Callable, Sequence, Sized
from decimal import Decimal
from typing import Protocol, TypeAlias, cast

from src.services.reports.protocol_adapter import DictWrapper, _attr, _unwrap
from src.utils.decimal_helpers import safe_decimal_or_zero, safe_float

JsonMap: TypeAlias = dict[str, object]
StepData: TypeAlias = dict[str, object]
StepApplier: TypeAlias = Callable[[JsonMap, StepData], None]

_STEP_WATERFALL_LINEAGE_KEYS = (
    "model_adjustment",
    "effective_adjustment",
    "factor_before",
    "factor_after",
    "rationale",
    "source",
    "multiple_discount_key",
    "discount_key",
    "strength_factor_discount_key",
    "strength_factor_discount_adjustment",
    "strength_factor_discount_before",
    "strength_factor_discount_after",
    "strength_factor_discount_evidence",
    "strength_factor_evidence",
    "strength_factor_policy",
    "strength_factor_evidence_count",
    "strength_factor_multiple_discount_keys",
    "strength_factor_keys",
    "strength_factor_mapped_inputs",
    "strength_factor_valuation_effects",
    "strength_factor_captured_input_ids",
    "strength_factor_data_point_ids",
)


class Gettable(Protocol):
    def get(self, key: object, default: object = None) -> object: ...


def _as_map(value: object) -> JsonMap | None:
    if isinstance(value, DictWrapper):
        value = _unwrap(value)
    elif hasattr(value, "model_dump"):
        try:
            value = value.model_dump()
        except Exception:
            return None
    elif hasattr(value, "dict"):
        try:
            value = value.dict()
        except Exception:
            return None
    return cast(JsonMap, value) if isinstance(value, dict) else None


def _as_gettable(value: object) -> Gettable | None:
    unwrapped = _unwrap(value) if isinstance(value, DictWrapper) else value
    get_method = getattr(unwrapped, "get", None)
    if unwrapped and callable(get_method):
        return cast(Gettable, unwrapped)
    return None


def _sized_len(value: object) -> int:
    return len(value) if isinstance(value, Sized) else 0


def _first_present(mapping: JsonMap, *keys: str, default: object = None) -> object:
    """Return first present non-None value while preserving explicit zeroes."""
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _steps_map(step_data: StepData) -> dict[object, JsonMap]:
    steps = step_data.get("steps")
    if not isinstance(steps, dict):
        steps = {}
        step_data["steps"] = steps
    return cast(dict[object, JsonMap], steps)


def _normalize_step_status(status: object) -> str:
    if hasattr(status, "value"):
        status = getattr(status, "value")
    if status is None:
        return "unknown"

    status_text = str(status).strip().lower()
    if status_text.startswith("stepstatus."):
        status_text = status_text.rsplit(".", 1)[-1]
    return status_text or "unknown"


def initial_step_data() -> StepData:
    """Return the default report step-data context."""
    return {
        "steps": {},
        "step_count": 0,
        "completed_count": 0,
        "has_transparency": False,
        "data_quality_score": None,
        "quality_level": None,
        "quality_warnings": [],
        "comparables_list": [],
        "comparables_found": 0,
        "recommended_methodology": None,
        "owner_dependency_risk_level": None,
        "owner_dependency_adjustment": 0.0,
        "size_tier": None,
        "size_discount_percentage": 0.0,
        "total_discount_percentage": 0.0,
        "margin_bonus": 0.0,
        "growth_bonus": 0.0,
        "overall_confidence_score": None,
        "factor_scores": {},
        "transparency_report": {},
        "multiple_pipeline": [],
        "discount_waterfall": [],
        "sme_database_multiple_raw": None,
        "sme_calibration_factor": None,
        "net_debt": 0.0,
        "total_debt": 0.0,
        "cash": 0.0,
        "excess_cash": 0.0,
        "exemption_applied": False,
        "tax_latencies": [],
        "tax_latency_total": 0.0,
        "tax_latency_count": 0,
        "balance_sheet_adjustments": [],
    }


def calculation_steps_from_transparency(transparency: object) -> object | None:
    """Resolve raw calculation steps from supported transparency shapes."""
    if hasattr(transparency, "calculation_steps") and transparency.calculation_steps:
        return transparency.calculation_steps

    if hasattr(transparency, "transparency_report") and transparency.transparency_report:
        transparency_report = transparency.transparency_report
        if hasattr(transparency_report, "_data"):
            transparency_report = (
                transparency_report._data
                if isinstance(getattr(transparency_report, "_data"), dict)
                else {}
            )
        elif _as_gettable(transparency_report):
            pass
        else:
            transparency_report = {}
        if isinstance(transparency_report, dict):
            return transparency_report.get("calculation_steps")
    return None


def multiples_steps_from_raw_steps(steps_raw: object) -> object | None:
    """Normalize raw calculation_steps into the multiples/flat step list."""
    steps = steps_raw
    if hasattr(steps, "_data") and isinstance(getattr(steps, "_data", None), dict):
        steps = steps._data
    elif hasattr(steps, "model_dump"):
        steps = steps.model_dump()
    elif hasattr(steps, "dict"):
        steps = steps.dict()

    if isinstance(steps, dict):
        return steps.get("multiples", [])
    if isinstance(steps, list):
        return steps
    return None


def record_calculation_step(
    step_data: StepData,
    step: object,
    index: int,
    *,
    calc_step_names: Sequence[object],
    calc_step_generic: str,
) -> int | float | None:
    """Store raw step metadata and return the normalized step number."""
    step_map = _calculation_step_map(step)
    if step_map is None:
        return None

    step_num = _calculation_step_number(step_map, index)
    status = _normalize_step_status(step_map.get("status"))
    _steps_map(step_data)[step_num] = _calculation_step_payload(
        step_map,
        step_num=step_num,
        status=status,
        calc_step_names=calc_step_names,
        calc_step_generic=calc_step_generic,
    )
    if status == "completed":
        _increment_completed_count(step_data)
    return step_num


def _calculation_step_map(step: object) -> JsonMap | None:
    # In /calculate path the response is in-memory Pydantic. In /render & /pdf paths
    # the same data arrived via JSON. Normalize both so completed_count and steps map
    # populate either way.
    return _as_map(step)


def _calculation_step_number(step: JsonMap, index: int) -> int | float:
    step_num = step.get("step")
    if step_num is None:
        step_num = step.get("step_number", index)
    if isinstance(step_num, (int, float)):
        return step_num
    return index


def _calculation_step_fallback_name(
    step_num: int | float,
    *,
    calc_step_names: Sequence[object],
    calc_step_generic: str,
) -> str:
    if isinstance(step_num, int) and 0 <= step_num < len(calc_step_names):
        return str(calc_step_names[step_num])
    return calc_step_generic.format(n=step_num)


def _calculation_step_payload(
    step: JsonMap,
    *,
    step_num: int | float,
    status: str,
    calc_step_names: Sequence[object],
    calc_step_generic: str,
) -> JsonMap:
    fallback_name = _calculation_step_fallback_name(
        step_num,
        calc_step_names=calc_step_names,
        calc_step_generic=calc_step_generic,
    )
    return {
        "step_number": step_num,
        "step_name": step.get("name") or step.get("step_name") or fallback_name,
        "status": status,
        "result": step.get("result", {}),
        "metadata": step.get("metadata", {}),
        "inputs": step.get("inputs", {}),
        "outputs": step.get("outputs", {}),
    }


def _increment_completed_count(step_data: StepData) -> None:
    step_data["completed_count"] = int(step_data.get("completed_count") or 0) + 1


def _pipeline_dict(raw_pipeline: object) -> JsonMap | None:
    if raw_pipeline is None:
        return None
    return _as_map(raw_pipeline)


def hydrate_pipeline_from_top_level_response(response: object, step_data: StepData) -> None:
    """Recover canonical multiple_pipeline when transparency steps were reduced."""
    pipeline = _pipeline_dict(_attr(response, "multiple_pipeline", None))
    if pipeline is None:
        return

    final_mid = safe_decimal_or_zero(
        _first_present(pipeline, "final_multiple_mid", "final_multiple")
    )
    if final_mid <= Decimal("0"):
        return

    if pipeline.get("final_multiple_mid") is None and pipeline.get("final_multiple") is not None:
        pipeline["final_multiple_mid"] = pipeline.get("final_multiple")
    if (
        pipeline.get("initial_multiple_mid") is None
        and pipeline.get("initial_multiple") is not None
    ):
        pipeline["initial_multiple_mid"] = pipeline.get("initial_multiple")
    if pipeline.get("final_multiple_low") is None:
        pipeline["final_multiple_low"] = pipeline.get("final_multiple_mid")
    if pipeline.get("final_multiple_high") is None:
        pipeline["final_multiple_high"] = pipeline.get("final_multiple_mid")
    if not isinstance(pipeline.get("discount_waterfall"), list):
        pipeline["discount_waterfall"] = []

    step_data["multiple_pipeline"] = pipeline


def fill_balance_sheet_step_data_from_current_year(
    response: object,
    step_data: StepData,
) -> None:
    """Populate bridge fields from current_year_data when Step 7 is absent."""
    current_year_data = _attr(response, "current_year_data", None)
    if current_year_data is None:
        return

    total_debt = safe_decimal_or_zero(_attr(current_year_data, "total_debt", 0))
    cash = safe_decimal_or_zero(_attr(current_year_data, "cash", 0))
    if total_debt == Decimal("0") and cash == Decimal("0"):
        return

    if safe_decimal_or_zero(step_data.get("total_debt", 0)) == Decimal("0"):
        step_data["total_debt"] = safe_float(total_debt)
    if safe_decimal_or_zero(step_data.get("cash", 0)) == Decimal("0"):
        step_data["cash"] = safe_float(cash)
    if safe_decimal_or_zero(step_data.get("net_debt", 0)) == Decimal("0"):
        step_data["net_debt"] = safe_float(total_debt - cash)


def _step_results_from_detailed_results(response: object) -> Gettable | None:
    detailed_results_gettable = _as_gettable(getattr(response, "detailed_results", None))
    if not detailed_results_gettable:
        return None

    step_results = detailed_results_gettable.get("step_results")
    step_results_gettable = _as_gettable(step_results)
    if step_results_gettable:
        return step_results_gettable

    multiples_valuation = detailed_results_gettable.get("multiples_valuation")
    multiples_valuation_gettable = _as_gettable(multiples_valuation)
    if multiples_valuation_gettable:
        step_results = multiples_valuation_gettable.get("_step_results")
        step_results_gettable = _as_gettable(step_results)
        if step_results_gettable:
            return step_results_gettable
    return None


def _result_from_step_output(step_output: object) -> Gettable | None:
    result = getattr(step_output, "result", None)
    step_output_gettable = _as_gettable(step_output)
    if result is None and step_output_gettable:
        result = step_output_gettable.get("result")
    return _as_gettable(result)


def _step_output(step_results: Gettable, *keys: object) -> object | None:
    for key in keys:
        output = step_results.get(key)
        if output is not None:
            return output
    return None


def _populate_sme_calibration_from_step_results(
    step_results: Gettable,
    step_data: StepData,
) -> None:
    if step_data.get("sme_database_multiple_raw") is not None:
        return

    step2_out = _step_output(step_results, 2, 2.0, "2")
    if not step2_out:
        return

    step2_result = _as_map(_result_from_step_output(step2_out))
    if step2_result is None:
        return

    ebitda_multiple = step2_result.get("ebitda_multiple") or {}
    ebitda_multiple_map = _as_map(ebitda_multiple)
    if ebitda_multiple_map is None:
        return

    raw_multiple = ebitda_multiple_map.get("raw")
    calibration_factor = ebitda_multiple_map.get("calibration_factor")
    if raw_multiple is not None:
        step_data["sme_database_multiple_raw"] = safe_float(raw_multiple)
    if calibration_factor is not None:
        step_data["sme_calibration_factor"] = safe_float(calibration_factor)


def _populate_discount_step_data(step_num: int, result: JsonMap, step_data: StepData) -> None:
    if step_num == 4:
        adjustment = result.get("adjustment_percentage")
        if adjustment is None:
            adjustment = result.get("owner_concentration_adjustment")
        step_data["owner_dependency_adjustment"] = safe_float(
            adjustment if adjustment is not None else 0
        )
        step_data["owner_dependency_risk_level"] = result.get("risk_level")
    elif step_num == 5:
        size_discount = result.get("size_discount_percentage")
        if size_discount is None:
            size_discount = result.get("size_discount")
        step_data["size_discount_percentage"] = safe_float(
            size_discount if size_discount is not None else 0
        )
        step_data["size_tier"] = result.get("size_tier")
    elif step_num == 6:
        total_discount = result.get("total_discount_percentage")
        if total_discount is None:
            total_discount = result.get("total_adjustment")
        step_data["total_discount_percentage"] = safe_float(
            total_discount if total_discount is not None else 0
        )


def _populate_discount_context_from_step_results(
    step_results: Gettable,
    step_data: StepData,
) -> None:
    for step_num in (4, 5, 6):
        step_out = _step_output(step_results, step_num, float(step_num))
        if not step_out:
            continue
        result = _result_from_step_output(step_out)
        result_map = _as_map(result)
        if result_map is not None:
            _populate_discount_step_data(step_num, result_map, step_data)


def hydrate_discount_context_from_detailed_results(
    response: object,
    step_data: StepData,
) -> None:
    """Populate owner/size/liquidity discount context from the authoritative
    ``detailed_results.step_results`` when the transparency calc-trail is absent.

    On the comprehensive engine path ``transparency.calculation_steps`` is often
    empty (the step trail is serialised into ``detailed_results.step_results``).
    Without this, ``size_discount_percentage`` stays 0 and the EV-formula
    aligner inflates the reported EV to the GROSS ``metric × market multiple``
    — which then back-derives a phantom net-debt from the EV/Equity gap. Pulling
    the discount context here keeps the reported EV at the engine's real
    post-discount value and renders the gross→net bridge honestly.
    """
    step_results = _step_results_from_detailed_results(response)
    if step_results:
        _populate_discount_context_from_step_results(step_results, step_data)


def extract_pipeline_from_detailed_results(
    response: object,
    step_data: StepData | None = None,
) -> JsonMap | None:
    """Extract a canonical multiple pipeline from detailed_results fallbacks."""
    step_results = _step_results_from_detailed_results(response)
    if not step_results:
        return None

    step_11_output = _step_output(step_results, 11, 11.0, "11")
    if not step_11_output:
        return None

    result = _result_from_step_output(step_11_output)
    if not result:
        return None

    pipeline = _pipeline_dict(result.get("multiple_pipeline"))
    if not pipeline:
        return None

    if step_data is not None:
        _populate_sme_calibration_from_step_results(step_results, step_data)
        _populate_discount_context_from_step_results(step_results, step_data)

    selected_final_multiple = _first_present(pipeline, "final_multiple_mid", "final_multiple")
    if safe_decimal_or_zero(selected_final_multiple) > Decimal("0"):
        return pipeline

    return None


def _combined_step_data(step: JsonMap) -> JsonMap:
    result = _as_map(step.get("result")) or {}
    outputs = _as_map(step.get("outputs")) or {}
    return {**result, **outputs}


def _nested_inputs(data: JsonMap) -> JsonMap:
    return _as_map(data.get("inputs")) or {}


def _step_waterfall_lineage_payload(entry: JsonMap) -> JsonMap:
    payload: JsonMap = {}
    for key in _STEP_WATERFALL_LINEAGE_KEYS:
        value = entry.get(key)
        if value is not None:
            payload[key] = value

    evidence = payload.get("strength_factor_discount_evidence")
    if evidence is not None and "strength_factor_evidence" not in entry:
        payload["strength_factor_evidence"] = evidence

    return payload


def _waterfall_from_pipeline(
    raw_pipeline: JsonMap,
    *,
    allowed_metric_types: tuple[str, ...],
) -> list[JsonMap]:
    pipeline_metric_type = str(raw_pipeline.get("metric_type", "EBITDA")).upper()
    if (
        not raw_pipeline.get("discount_waterfall")
        or pipeline_metric_type not in allowed_metric_types
    ):
        return []

    source_waterfall = raw_pipeline["discount_waterfall"]
    if not isinstance(source_waterfall, list):
        return []
    metric_value = safe_float(_first_present(raw_pipeline, "metric_value", default=0))
    waterfall: list[JsonMap] = []
    for index, entry in enumerate(source_waterfall):
        if not isinstance(entry, dict):
            continue
        entry_map = cast(JsonMap, entry)
        after_mid = safe_float(entry.get("multiple_after_mid") or 0)
        before_mid = safe_float(entry.get("multiple_before_mid") or 0)
        impact = (after_mid - before_mid) if before_mid else None
        ev = (metric_value * after_mid) if metric_value and after_mid else 0
        row = {
            "label": entry_map.get("step_name") or entry_map.get("step", f"Step {index}"),
            "multiple": after_mid,
            "impact": impact,
            "ev": ev,
            "ref": "",
            "description": entry_map.get("description", ""),
        }
        row.update(_step_waterfall_lineage_payload(entry_map))
        waterfall.append(row)
    return waterfall


def _apply_step_11_dict_pipeline(
    raw_pipeline: JsonMap,
    step_data: StepData,
) -> None:
    waterfall = _waterfall_from_pipeline(raw_pipeline, allowed_metric_types=("EBITDA", "REVENUE"))
    if waterfall:
        step_data["discount_waterfall"] = waterfall


def apply_ebitda_pipeline_fallback_waterfall(
    pipeline: JsonMap,
    step_data: StepData,
) -> None:
    """Populate fallback waterfall from a detailed-results EBITDA pipeline."""
    waterfall = _waterfall_from_pipeline(pipeline, allowed_metric_types=("EBITDA",))
    if waterfall:
        step_data["discount_waterfall"] = waterfall


def _apply_step_11_list_pipeline(
    raw_pipeline: object,
    step_data: StepData,
    unknown_stage_label: str,
) -> None:
    if not isinstance(raw_pipeline, list) or len(raw_pipeline) <= 0:
        return

    waterfall: list[JsonMap] = []
    for stage in raw_pipeline:
        if isinstance(stage, dict):
            stage_map = cast(JsonMap, stage)
            waterfall.append(
                {
                    "label": stage_map.get("stage_name")
                    or stage_map.get("name")
                    or unknown_stage_label,
                    "multiple": safe_float(
                        _first_present(stage_map, "multiple_value", "multiple", default=0)
                    ),
                    "adjustment": safe_float(
                        _first_present(stage_map, "adjustment", "delta", default=0)
                    ),
                    "ev": safe_float(_first_present(stage_map, "ev_value", "ev", default=0)),
                }
            )
    step_data["discount_waterfall"] = waterfall


def _apply_step_0_quality(data: JsonMap, step_data: StepData) -> None:
    step_data["data_quality_score"] = _first_present(data, "data_quality_score", "quality_score")
    step_data["quality_level"] = data.get("quality_level") or data.get("data_quality_level")
    step_data["quality_warnings"] = data.get("warnings", []) or data.get("quality_warnings", [])


def _apply_step_2_comparables(data: JsonMap, step_data: StepData) -> None:
    comparables = data.get("comparables_list", []) or data.get("comparables", [])
    step_data["comparables_list"] = comparables
    step_data["comparables_found"] = data.get("comparables_found", 0) or _sized_len(comparables)
    step_data["recommended_methodology"] = data.get("recommended_methodology") or data.get(
        "methodology"
    )

    ebitda_multiple = _as_map(data.get("ebitda_multiple")) or {}
    if ebitda_multiple:
        raw_multiple = ebitda_multiple.get("raw")
        calibration_factor = ebitda_multiple.get("calibration_factor")
        if raw_multiple is not None:
            step_data["sme_database_multiple_raw"] = safe_float(raw_multiple)
        if calibration_factor is not None:
            step_data["sme_calibration_factor"] = safe_float(calibration_factor)


def _apply_step_4_owner_dependency(data: JsonMap, step_data: StepData) -> None:
    step_data["owner_dependency_risk_level"] = data.get("risk_level") or data.get(
        "owner_risk_level"
    )
    step_data["owner_dependency_adjustment"] = safe_float(
        _first_present(data, "adjustment_percentage", "owner_adjustment", default=0)
    )


def _apply_step_5_size_discount(data: JsonMap, step_data: StepData) -> None:
    step_data["size_tier"] = data.get("size_tier") or data.get("company_size_tier")
    step_data["size_discount_percentage"] = safe_float(
        _first_present(data, "size_discount_percentage", "size_discount", default=0)
    )


def _apply_step_6_performance(data: JsonMap, step_data: StepData) -> None:
    total_discount = data.get("total_discount_percentage")
    if total_discount is None:
        total_discount = data.get("total_adjustment")
    step_data["total_discount_percentage"] = safe_float(
        total_discount if total_discount is not None else 0
    )
    margin_bonus = data.get("margin_bonus")
    step_data["margin_bonus"] = safe_float(margin_bonus if margin_bonus is not None else 0)
    growth_bonus = data.get("growth_bonus")
    step_data["growth_bonus"] = safe_float(growth_bonus if growth_bonus is not None else 0)


def _apply_step_7_bridge(data: JsonMap, step_data: StepData) -> None:
    inputs = _nested_inputs(data)
    net_debt = data.get("net_debt")
    if net_debt is None:
        net_debt = inputs.get("net_debt")
    step_data["net_debt"] = safe_float(net_debt if net_debt is not None else 0)

    total_debt = data.get("total_debt")
    if total_debt is None:
        total_debt = inputs.get("total_debt")
    step_data["total_debt"] = safe_float(total_debt if total_debt is not None else 0)

    cash = data.get("cash")
    if cash is None:
        cash = inputs.get("cash")
    step_data["cash"] = safe_float(cash if cash is not None else 0)

    excess_cash = data.get("excess_cash")
    if excess_cash is None:
        excess_cash = inputs.get("excess_cash")
    step_data["excess_cash"] = safe_float(excess_cash if excess_cash is not None else 0)
    step_data["exemption_applied"] = bool(
        data.get("exemption_applied") or inputs.get("exemption_applied") or False
    )
    tax_latencies = data.get("tax_latencies")
    if tax_latencies:
        step_data["tax_latencies"] = tax_latencies
        step_data["tax_latency_total"] = safe_float(data.get("tax_latency_total", 0))
        step_data["tax_latency_count"] = _sized_len(tax_latencies)


def _apply_step_9_confidence(data: JsonMap, step_data: StepData) -> None:
    step_data["overall_confidence_score"] = _first_present(
        data, "overall_confidence_score", "confidence_score"
    )
    step_data["factor_scores"] = data.get("factor_scores", {}) or data.get("confidence_factors", {})


def _apply_step_11_pipeline(
    data: JsonMap,
    step_data: StepData,
    unknown_stage_label: str,
) -> None:
    step_data["transparency_report"] = data.get("transparency_report", {})
    raw_pipeline = data.get("multiple_pipeline", {}) or data.get("pipeline_stages", {})
    step_data["multiple_pipeline"] = raw_pipeline

    if isinstance(raw_pipeline, dict):
        _apply_step_11_dict_pipeline(cast(JsonMap, raw_pipeline), step_data)
    else:
        _apply_step_11_list_pipeline(raw_pipeline, step_data, unknown_stage_label)


_STEP_DATA_APPLIERS: dict[int, StepApplier] = {
    0: _apply_step_0_quality,
    2: _apply_step_2_comparables,
    4: _apply_step_4_owner_dependency,
    5: _apply_step_5_size_discount,
    6: _apply_step_6_performance,
    7: _apply_step_7_bridge,
    9: _apply_step_9_confidence,
}


def apply_step_specific_data(
    step_number: object,
    step: JsonMap,
    step_data: StepData,
    *,
    unknown_stage_label: str,
) -> None:
    """Map one calculation step into named report context fields."""
    # During /calculate, ``step`` arrives as an in-memory CalculationStep
    # Pydantic model rather than the JSON dict shape seen by /render and /pdf.
    # ``_combined_step_data`` calls ``.get()`` directly, so without this
    # normalisation every Three Towers-class calculation logged
    # "Error extracting step data: 'CalculationStep' object has no attribute
    # 'get'" and silently fell back to the detailed-results recovery path.
    if not isinstance(step, dict):
        if hasattr(step, "model_dump"):
            step = step.model_dump()
        elif hasattr(step, "_data") and isinstance(getattr(step, "_data", None), dict):
            step = step._data
        elif hasattr(step, "dict") and callable(getattr(step, "dict")):
            step = step.dict()
        else:
            return
    data = _combined_step_data(step)
    if step_number == 11:
        _apply_step_11_pipeline(data, step_data, unknown_stage_label)
        return

    applier = _STEP_DATA_APPLIERS.get(cast(int, step_number))
    if applier is not None:
        applier(data, step_data)


def apply_step7_detailed_result(step_7_result: JsonMap, step_data: StepData) -> None:
    """Overlay detailed Step 7 bridge fields onto report step_data."""
    if step_7_result.get("net_debt") is not None:
        step_data["net_debt"] = safe_float(step_7_result.get("net_debt"))
    if step_7_result.get("total_debt") is not None:
        step_data["total_debt"] = safe_float(step_7_result.get("total_debt"))
    if step_7_result.get("cash") is not None:
        step_data["cash"] = safe_float(step_7_result.get("cash"))
    if step_7_result.get("excess_cash") is not None:
        step_data["excess_cash"] = safe_float(step_7_result.get("excess_cash"))
    if step_7_result.get("exemption_applied") is not None:
        step_data["exemption_applied"] = bool(step_7_result.get("exemption_applied"))
    tax_latencies = step_7_result.get("tax_latencies")
    if tax_latencies:
        step_data["tax_latencies"] = tax_latencies
        step_data["tax_latency_total"] = safe_float(step_7_result.get("tax_latency_total", 0))
        step_data["tax_latency_count"] = _sized_len(tax_latencies)
    if step_7_result.get("balance_sheet_adjustments"):
        step_data["balance_sheet_adjustments"] = step_7_result["balance_sheet_adjustments"]
    if step_7_result.get("nwc_surplus_deficit") is not None:
        step_data["nwc_surplus_deficit"] = safe_float(step_7_result.get("nwc_surplus_deficit"))
