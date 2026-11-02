"""Calibration and valuation-waterfall stage for main report aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from src.services.infrastructure.translations import ReportTranslations
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.reports.report_calibration_waterfall import (
    build_calibration_steps,
    build_multiple_waterfall_steps,
    build_valuation_waterfall_steps,
    inject_sme_calibration_into_waterfall,
    localize_discount_waterfall_for_locale,
)
from src.utils.decimal_helpers import safe_decimal_or_zero as safe_decimal
from src.utils.decimal_helpers import safe_float as to_float

JsonMap = dict[str, object]
JsonRows = list[JsonMap]
ValuationRequest = ValuationRequestProtocol
ValuationResponse = ValuationResponseProtocol
_MULTIPLE_RECONCILIATION_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class MainReportWaterfallContext:
    calibration_steps: JsonRows
    multiple_waterfall_steps: JsonRows
    valuation_waterfall_steps: JsonRows
    supports_metric_to_ev_bridge: bool
    show_size_discount_skipped_note: bool
    show_benchmark_reference_without_table: bool


def should_render_metric_to_ev_bridge(
    *,
    is_hybrid_methodology: bool,
    is_dcf_only_methodology: bool,
    is_asset_anchored: bool,
    has_weighted_synthesis_payload: bool,
    engine_synthesis_equity_anchored: bool,
) -> bool:
    """Return whether the report may honestly show ``metric x multiple = EV``."""
    return (
        not is_hybrid_methodology
        and not is_dcf_only_methodology
        and not is_asset_anchored
        and not has_weighted_synthesis_payload
        and not engine_synthesis_equity_anchored
    )


def _get(container: object, key: object) -> object:
    """Read ``key`` from a mapping OR an attribute bag (``StepOutput``, namespaces)."""
    if isinstance(container, Mapping):
        return container.get(key)
    if isinstance(key, str):
        return getattr(container, key, None)
    return None


def _step_result(response: object, step_number: int) -> Mapping[str, object]:
    """The ``result`` mapping of one pipeline step, or ``{}`` when absent.

    Two shapes exist for the same data and the report is built from the FIRST:

    * in-engine, at render time, ``detailed_results["step_results"]`` maps the
      step number as an ``int`` to a ``StepOutput`` *object* whose ``.result`` is
      the dict;
    * serialised, the keys are strings and the step is a plain dict.

    The first version of this reader only understood the serialised shape, so at
    render time it returned ``{}`` and every "prefer Step 7" branch silently fell
    back to the raw-cell rebuild — which is exactly the contradiction it was
    written to remove. Both shapes are accepted now.
    """
    detailed = _get(response, "detailed_results")
    step_results = _get(detailed, "step_results") if detailed is not None else None
    if step_results is None:
        return {}
    step = _get(step_results, step_number)
    if step is None:
        step = _get(step_results, str(step_number))
    if step is None:
        return {}
    result = _get(step, "result")
    if isinstance(result, Mapping):
        return result
    dump = getattr(result, "model_dump", None)
    if callable(dump):
        dumped = dump()
        return dumped if isinstance(dumped, Mapping) else {}
    return {}


def _terminal_waterfall_multiple(waterfall: object) -> Decimal | None:
    if not isinstance(waterfall, list):
        return None

    for row in reversed(waterfall):
        if not isinstance(row, Mapping):
            continue
        for key in ("multiple", "multiple_after_mid", "multiple_after", "end_value"):
            if key in row:
                value = safe_decimal(row.get(key))
                if value > Decimal("0"):
                    return value
    return None


def _waterfall_reconciles_to_applied_multiple(
    waterfall: object,
    applied_multiple: Decimal,
) -> bool:
    terminal_multiple = _terminal_waterfall_multiple(waterfall)
    if terminal_multiple is None:
        return False
    return abs(terminal_multiple - applied_multiple) <= _MULTIPLE_RECONCILIATION_TOLERANCE


def build_main_report_waterfall_context(
    *,
    response: ValuationResponse,
    request: ValuationRequest | None,
    step_data: JsonMap,
    formula_metric_value: object,
    multiple_context: Mapping[str, object],
    base_multiple: Decimal,
    display_multiple: Decimal,
    enterprise_value_mid: Decimal,
    net_debt_from_steps: Decimal,
    tax_latency_net_impact_decimal: Decimal,
    balance_sheet_adjustments: JsonRows,
    equity_value: Decimal | None,
    locale: str,
    translations: ReportTranslations,
    benchmark_disclosure: object,
    is_hybrid_methodology: bool,
    is_dcf_only_methodology: bool,
    is_asset_anchored: bool,
    has_weighted_synthesis_payload: bool,
    engine_synthesis_equity_anchored: bool,
    ebitda_basis_labels: tuple[str, str] | None = None,
) -> MainReportWaterfallContext:
    """Build calibrated multiple and EUR valuation waterfall rows.

    ``ebitda_basis_labels`` — ``(label, short_label)`` for the earnings-basis bar.
    The cover already derives an honest name for the basis the run priced
    ("genormaliseerd" only with applied adjustments, "(gewogen)" only on a
    multi-year weighted basis); passing it here keeps the waterfall from calling
    a 5-year weighted average of reported EBITDA "Genormaliseerde EBITDA", which
    it did on the first paying advisor's report.
    """
    metric_for_waterfall = to_float(formula_metric_value)
    if step_data.get("discount_waterfall"):
        step_data["discount_waterfall"] = inject_sme_calibration_into_waterfall(
            step_data["discount_waterfall"],
            step_data,
            metric_for_waterfall,
            translations,
        )
        step_data["discount_waterfall"] = localize_discount_waterfall_for_locale(
            step_data["discount_waterfall"], locale, translations
        )

    metric_type = str(multiple_context["metric_type"])
    calibration_steps = build_calibration_steps(
        metric_value=safe_decimal(formula_metric_value),
        metric_type=metric_type,
        base_multiple=base_multiple,
        final_multiple=display_multiple,
        response=response,
        step_data=step_data,
        t=translations,
    )
    # The Step-11 discount waterfall terminates on the POST-discount pipeline
    # multiple. When the headline multiple was recomputed onto a different EV
    # rail the rows describe discounts the headline never took, so they are
    # dropped rather than shown against a contradicting headline. That discard
    # used to be silent, which made VR-2026-9712 (headline 3.85x against a
    # waterfall terminating at 2.64x) invisible in the payload — the rows simply
    # vanished. Record the residual so the divergence is observable even though
    # the rows still go.
    discount_waterfall = step_data.get("discount_waterfall")
    if discount_waterfall and not _waterfall_reconciles_to_applied_multiple(
        discount_waterfall,
        display_multiple,
    ):
        step_data["discount_waterfall_rail_residual"] = {
            "waterfall_terminal_multiple": _terminal_waterfall_multiple(discount_waterfall),
            "headline_multiple": display_multiple,
            "reason": "headline multiple recomputed on a different EV rail",
        }
        step_data["discount_waterfall"] = []
    supports_metric_to_ev_bridge = should_render_metric_to_ev_bridge(
        is_hybrid_methodology=is_hybrid_methodology,
        is_dcf_only_methodology=is_dcf_only_methodology,
        is_asset_anchored=is_asset_anchored,
        has_weighted_synthesis_payload=has_weighted_synthesis_payload,
        engine_synthesis_equity_anchored=engine_synthesis_equity_anchored,
    )
    multiple_waterfall_source = step_data.get("discount_waterfall") or calibration_steps
    multiple_waterfall_steps = build_multiple_waterfall_steps(
        multiple_waterfall_source if isinstance(multiple_waterfall_source, list) else [],
        display_multiple,
        translations,
    )
    # The EV→equity bridge inputs live on STEP 7's result, not in the multiples
    # step bag. Reading them from `step_data` found nothing, so the EUR waterfall
    # drew the full cash balance (+€314,966) and then printed an equity equal to
    # EV — because Step 7 had, correctly, retained all of it as operating cash
    # (excess_cash = 0). Prefer Step 7's own figures when the run has them.
    step7 = _step_result(response, 7)
    bridge = {
        "total_debt": step7.get("total_debt", step_data.get("total_debt", 0)),
        "cash": step7.get("cash", step_data.get("cash", 0)),
        "excess_cash": step7.get("excess_cash", step_data.get("excess_cash", 0)),
        "exemption_applied": step7.get("exemption_applied", step_data.get("exemption_applied")),
        # Step 7's net debt is the one the equity was actually derived from — it
        # already excludes operating cash under the exemption. The aggregator's
        # `net_debt_from_steps` is rebuilt from the raw cells (debt − full cash),
        # so on a debt-free company it read −EUR 314,966 and drew a "Netto kas"
        # row the equity then contradicted.
        "net_debt": step7.get("net_debt", net_debt_from_steps),
    }
    valuation_waterfall_steps = build_valuation_waterfall_steps(
        valuation_basis_value=safe_decimal(formula_metric_value),
        metric_type=metric_type,
        applied_multiple=display_multiple,
        enterprise_value_mid=enterprise_value_mid,
        total_debt=safe_decimal(bridge["total_debt"]),
        cash_balance=safe_decimal(bridge["cash"]),
        excess_cash=safe_decimal(bridge["excess_cash"]),
        exemption_applied=bool(bridge["exemption_applied"]),
        net_debt=safe_decimal(bridge["net_debt"]),
        tax_latency_net_impact=tax_latency_net_impact_decimal,
        balance_sheet_adjustments=balance_sheet_adjustments,
        nwc_surplus_deficit=safe_decimal(step_data.get("nwc_surplus_deficit", 0)),
        equity_value=equity_value,
        include_metric_bridge=supports_metric_to_ev_bridge,
        t=translations,
        basis_labels=ebitda_basis_labels,
    )

    return MainReportWaterfallContext(
        calibration_steps=calibration_steps,
        multiple_waterfall_steps=multiple_waterfall_steps,
        valuation_waterfall_steps=valuation_waterfall_steps,
        supports_metric_to_ev_bridge=supports_metric_to_ev_bridge,
        show_size_discount_skipped_note=getattr(
            benchmark_disclosure, "show_size_discount_skipped_note"
        ),
        show_benchmark_reference_without_table=getattr(
            benchmark_disclosure, "show_benchmark_reference_without_table"
        ),
    )
