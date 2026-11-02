"""Canonical run, bridge and multiple projections into report context."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from src.api.schemas.stateless_report_schemas import GenerateReportRequest
from src.api.schemas.valuation_contracts import ValuationRunV2
from src.domain.method_keys import normalize_selected_method_key
from src.services.reports.report_benchmark_context import build_benchmark_provenance_snapshot
from src.services.reports.report_external_reference_context import (
    _decimal_or_zero as _decimal_or_zero,
)
from src.services.reports.stateless_priced_evidence_projection import (
    build_stateless_priced_evidence_projection,
)
from src.services.reports.valuation_assurance_status import CurrentValuationAssuranceAuthority

from .report_bridge_projection import display_amount, optional_decimal, report_bridge
from .report_context_types import ReportMap


def _apply_benchmark_provenance_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    snapshot = build_benchmark_provenance_snapshot(request.valuation_result.multiples_results)
    context["benchmark_provenance"] = snapshot
    if snapshot:
        # One immutable normalized contract backs the API context and both
        # screen/PDF template trees.
        context["benchmark_contract"] = snapshot["contract"]
        context.update(
            {
                "benchmark_multiple_low": snapshot.get("low"),
                "benchmark_multiple_mid": snapshot.get("mid"),
                "benchmark_multiple_high": snapshot.get("high"),
                "benchmark_sample_size": snapshot.get("sample_size"),
                "benchmark_data_source": snapshot.get("source"),
                "benchmark_published_at": snapshot.get("published_at"),
                "benchmark_id": snapshot.get("benchmark_id"),
                "benchmark_dataset_version_id": snapshot.get("dataset_version_id"),
                "benchmark_country_code": snapshot.get("country_code"),
                "benchmark_region_key": snapshot.get("region_key"),
                "benchmark_tier": snapshot.get("tier"),
                "benchmark_walk_step": snapshot.get("walk_step"),
                "benchmark_scope_stage": snapshot.get("scope_stage"),
                "benchmark_confidence_band": snapshot.get("confidence_band"),
                "benchmark_source_mix": snapshot.get("source_mix"),
                "benchmark_evidence_summary": snapshot.get("evidence_summary"),
                "benchmark_methodology_version": snapshot.get("methodology_version"),
                "bridge_contract_resolved": True,
            }
        )
        if snapshot.get("metric") == "ev_ebitda_multiple":
            context.update(
                {
                    "benchmark_ev_ebitda_p25": snapshot.get("low"),
                    "benchmark_ev_ebitda_p50": snapshot.get("mid"),
                    "benchmark_ev_ebitda_p75": snapshot.get("high"),
                }
            )

        # Finalization constructs the advisor appendix before this stateless
        # contract is reasserted. Refresh its evidence row from the identical
        # snapshot so API, screen and PDF cannot disagree on source or band.
        transparency = context.get("advisor_multiple_transparency")
        if isinstance(transparency, dict):
            transparency = dict(transparency)
            evidence = transparency.get("benchmark_evidence")
            evidence = dict(evidence) if isinstance(evidence, dict) else {}
            evidence.update(
                {
                    "low": snapshot.get("low"),
                    "mid": snapshot.get("mid"),
                    "high": snapshot.get("high"),
                    "sample_size": snapshot.get("sample_size"),
                    "data_source": snapshot.get("source"),
                    "as_of": snapshot.get("published_at"),
                    "region": snapshot.get("region_key") or snapshot.get("country_code"),
                    "tier": snapshot.get("tier"),
                    "scope_stage": snapshot.get("scope_stage"),
                    "source_mix": snapshot.get("source_mix"),
                    "evidence_summary": snapshot.get("evidence_summary"),
                }
            )
            transparency["benchmark_evidence"] = evidence
            context["advisor_multiple_transparency"] = transparency


def _apply_valuation_run_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Bind every report surface to the exact immutable calculation run."""
    run = request.valuation_result.valuation_run
    if run is None:
        return
    payload = cast(ReportMap, run.model_dump(mode="python"))
    context.update(
        {
            "valuation_run": payload,
            "valuation_run_id": run.run_id,
            "valuation_run_hash": run.run_hash,
            "valuation_run_schema_version": run.schema_version,
            "valuation_engine_version": run.engine_version,
            "valuation_policy_version": run.policy_version,
            "valuation_input_hash": run.input_hash,
            "valuation_evidence_hash": run.evidence_hash,
            "valuation_benchmark_hash": run.benchmark_hash,
            "valuation_calculation_hash": run.calculation_hash,
            "valuation_audit_hash": run.audit_hash,
            "valuation_range": payload.get("valuation_range"),
            "enterprise_value_range": payload.get("enterprise_value_range"),
            "value_driver_ledger": run.driver_ledger,
            "calculation_lineage": payload.get("calculation_lineage"),
        }
    )


def _apply_priced_evidence_projection_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Expose one run-bound projection to both template renderers.

    Screen and PDF share ``template_context``.  Keeping the projection here,
    after legacy aggregation/finalization, prevents either template tree from
    reconstructing monetary lines from mutable presentation fields.
    """

    if request.report_scope == "client_indicative":
        context.update(
            {
                "priced_evidence_register": None,
                "actionable_adjustment_projection": None,
                "actionable_adjustment_lines": [],
                "show_canonical_evidence_adjustments_appendix": False,
            }
        )
        return

    run = request.valuation_result.valuation_run
    if not isinstance(run, ValuationRunV2):
        context.update(
            {
                "priced_evidence_register": None,
                "actionable_adjustment_projection": None,
                "actionable_adjustment_lines": [],
                "show_canonical_evidence_adjustments_appendix": False,
            }
        )
        return
    projection = build_stateless_priced_evidence_projection(run)
    context.update(projection.as_report_context())


def _apply_canonical_balance_sheet_bridge_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Bind gross debt, cash and net debt to the canonical response inputs.

    Legacy report aggregation sometimes populated ``net_debt`` from gross debt
    when Step 7 detail was absent.  That makes a correct sealed EV/equity result
    look arithmetically inconsistent in SDE and other stateless reports.  A
    canonical run may use the committed response's balance-sheet metrics; it
    must never reconstruct this bridge from mutable report context.
    """

    result = request.valuation_result
    if result.valuation_run is None or result.enterprise_value_mid is None:
        return
    bridge = report_bridge(result)
    context.update(bridge.projection())
    if not bridge.available:
        transparency = context.get("advisor_multiple_transparency")
        if isinstance(transparency, dict):
            context["advisor_multiple_transparency"] = {
                **transparency,
                "equity_bridge": None,
            }


def _apply_canonical_multiple_build_up_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Use the sealed post-adjustment multiple and earnings basis in formulas.

    The legacy aggregator starts from the pre-discount benchmark multiple.  A
    canonical run commits the effective multiple after method-level size and
    liquidity adjustments in ``multiple_build_up``.  Using the former beside
    final EV creates a false equation in the PDF even though the headline is
    correct.  Rebind both values from the sealed run before the formula gate.
    """

    run = request.valuation_result.valuation_run
    if run is None:
        return
    multiples = run.multiples_results
    if not isinstance(multiples, dict):
        return
    build_up = multiples.get("multiple_build_up")
    if not isinstance(build_up, dict):
        return
    effective_multiple = _decimal_or_zero(build_up.get("effective_multiple"))
    earnings_basis = build_up.get("earnings_basis")
    adjusted_earnings = (
        _decimal_or_zero(earnings_basis.get("adjusted_earnings"))
        if isinstance(earnings_basis, dict)
        else Decimal("0")
    )
    if effective_multiple > 0:
        context["applied_multiple"] = float(effective_multiple)
    if adjusted_earnings > 0:
        context["valuation_basis_value"] = float(adjusted_earnings)

    # A revenue or ARR headline shares the benchmark/discount evidence with
    # the EBITDA build-up, but its formula must come from its own sealed
    # MethodResult. Never pair the EBITDA effective multiple with revenue/ARR.
    selected_method = normalize_selected_method_key(request.selected_method)
    method_results = run.method_results
    selected_result = (
        method_results.get(selected_method) if isinstance(method_results, dict) else None
    )
    if not isinstance(selected_result, dict):
        return
    selected_multiple = _decimal_or_zero(selected_result.get("multiple_used"))
    details = selected_result.get("details")
    if selected_multiple <= 0 or not isinstance(details, dict):
        return
    if selected_method == "omzet_multiple":
        revenue = _decimal_or_zero(details.get("revenue"))
        if revenue > 0:
            context.update(
                {
                    "applied_multiple": float(selected_multiple),
                    "valuation_basis_value": float(revenue),
                    "revenue": float(revenue),
                    "multiple_metric_type": "REVENUE",
                }
            )
    elif selected_method == "arr_multiple":
        arr = _decimal_or_zero(details.get("arr"))
        if arr > 0:
            context.update(
                {
                    "applied_multiple": float(selected_multiple),
                    "valuation_basis_value": float(arr),
                    "multiple_metric_type": "ARR",
                }
            )
    elif selected_method == "ebitda_multiple" and adjusted_earnings > 0:
        context.update(
            {
                "applied_multiple": float(selected_multiple),
                "valuation_basis_value": float(adjusted_earnings),
                "multiple_metric_type": "EBITDA",
            }
        )


def _apply_canonical_run_headline_context(
    context: ReportMap,
    request: GenerateReportRequest,
    assurance_authority: CurrentValuationAssuranceAuthority | None = None,
) -> None:
    """Pin report headlines to the immutable run instead of recalculating them.

    The legacy report finalizer still contains presentation-era alignment and
    asking-price rules.  Those rules may enrich legacy reports, but once a
    ``ValuationRun`` exists the API result is the monetary authority.  Reapply
    its exact equity/enterprise ranges and asking price after finalization so
    HTML, PDF, API and graph projections cannot quote different conclusions.
    """

    result = request.valuation_result
    if result.valuation_run is None:
        return

    equity_low = optional_decimal(result.equity_value_low, "equity low")
    equity_mid = optional_decimal(result.equity_value_mid, "equity mid")
    equity_high = optional_decimal(result.equity_value_high, "equity high")
    assured_band = (
        assurance_authority.envelope.audience_display_band
        if assurance_authority is not None
        else None
    )
    if assured_band is not None and assured_band.value_basis == "equity_value":
        if equity_low is None or equity_mid is None or equity_high is None:
            raise ValueError("equity display band requires a complete saved equity range")
        equity_low = Decimal(assured_band.display_low)
        equity_mid = Decimal(assured_band.display_mid)
        equity_high = Decimal(assured_band.display_high)
    context.update(
        {
            "equity_value": display_amount(equity_mid),
            "equity_value_mid": display_amount(equity_mid),
            "equity_value_low": display_amount(equity_low),
            "equity_value_high": display_amount(equity_high),
            "equity_value_band_is_meaningful": (
                equity_low is not None and equity_high is not None and equity_low < equity_high
            ),
            "recommended_asking_price_realigned": False,
        }
    )

    enterprise_low = result.enterprise_value_low
    enterprise_mid = result.enterprise_value_mid
    enterprise_high = result.enterprise_value_high
    ev_low: Decimal | None
    ev_mid: Decimal | None
    ev_high: Decimal | None
    if enterprise_low is not None and enterprise_mid is not None and enterprise_high is not None:
        ev_low = _decimal_or_zero(enterprise_low)
        ev_mid = _decimal_or_zero(enterprise_mid)
        ev_high = _decimal_or_zero(enterprise_high)
        if assured_band is not None and assured_band.value_basis == "enterprise_value":
            ev_low = Decimal(assured_band.display_low)
            ev_mid = Decimal(assured_band.display_mid)
            ev_high = Decimal(assured_band.display_high)
        context.update(
            {
                "enterprise_value_low": display_amount(ev_low),
                "enterprise_value_mid": display_amount(ev_mid),
                "enterprise_value_high": display_amount(ev_high),
                "enterprise_value_applicability": "applicable",
            }
        )
    else:
        ev_low = ev_mid = ev_high = None
        # The legacy aggregator may have derived an EV-looking scalar from a
        # supporting market method. A canonical pure-equity run must erase it
        # before HTML/PDF flags and formulas are finalized.
        context.update(
            {
                "enterprise_value": None,
                "enterprise_value_low": None,
                "enterprise_value_mid": None,
                "enterprise_value_high": None,
                "enterprise_value_applicability": "not_applicable",
                "supports_metric_to_ev_bridge": False,
                "show_ev_equity_bridge": False,
                "show_enterprise_to_equity_bridge": False,
                "has_net_debt_adjustment": False,
            }
        )

    if request.headline_value_basis == "enterprise_value":
        if ev_low is None or ev_mid is None or ev_high is None:
            raise ValueError(
                "enterprise-value report is not applicable to the selected equity-premise method"
            )
        headline_low, headline_mid, headline_high = ev_low, ev_mid, ev_high
    else:
        if equity_low is None or equity_mid is None or equity_high is None:
            raise ValueError("equity-value report requires a complete saved equity range")
        headline_low, headline_mid, headline_high = (
            equity_low,
            equity_mid,
            equity_high,
        )
    context.update(
        {
            "valuation": float(headline_mid),
            "valuation_low": float(headline_low),
            "valuation_high": float(headline_high),
            "valuation_band_is_meaningful": headline_low < headline_high,
            "ev_sourced_from_engine_equity": False,
        }
    )

    if request.show_asking_price:
        asking_price = result.recommended_asking_price
        context["recommended_asking_price"] = (
            float(_decimal_or_zero(asking_price)) if asking_price is not None else None
        )
    else:
        context["recommended_asking_price"] = None
