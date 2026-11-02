"""Value-basis and fallback presentation from the saved valuation."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from src.api.schemas.stateless_report_schemas import GenerateReportRequest
from src.services.reports.report_external_reference_context import (
    _decimal_or_zero as _decimal_or_zero,
)

from .report_bridge_projection import display_amount, optional_decimal, report_bridge
from .report_context_types import ReportMap


def _apply_enterprise_value_primary_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Pin an EV-primary report to the engine's canonical EV contract.

    The legacy report aggregator was built when the stateless response only
    exposed an equity headline. An explicit EV-primary request must never let
    the equity bridge leak back into EV-labelled formulas or ranges.
    """
    if request.headline_value_basis != "enterprise_value":
        return

    result = request.valuation_result
    if (
        result.enterprise_value_low is None
        or result.enterprise_value_mid is None
        or result.enterprise_value_high is None
    ):
        raise ValueError("enterprise-value report requires low/mid/high EV fields")

    ev_low = _decimal_or_zero(result.enterprise_value_low)
    ev_mid = _decimal_or_zero(result.enterprise_value_mid)
    ev_high = _decimal_or_zero(result.enterprise_value_high)
    eq_low = optional_decimal(result.equity_value_low, "equity low")
    eq_mid = optional_decimal(result.equity_value_mid, "equity mid")
    eq_high = optional_decimal(result.equity_value_high, "equity high")
    bridge = report_bridge(result)
    net_debt = bridge.net_debt

    context.update(
        {
            "valuation": float(ev_mid),
            "valuation_low": float(ev_low),
            "valuation_high": float(ev_high),
            "enterprise_value_mid": float(ev_mid),
            "enterprise_value_low": float(ev_low),
            "enterprise_value_high": float(ev_high),
            "equity_value": display_amount(eq_mid),
            "equity_value_mid": display_amount(eq_mid),
            "equity_value_low": display_amount(eq_low),
            "equity_value_high": display_amount(eq_high),
            "upswitch_adaptive_value": float(ev_mid),
            "valuation_band_is_meaningful": ev_low < ev_high,
            "equity_value_band_is_meaningful": (
                eq_low is not None and eq_high is not None and eq_low < eq_high
            ),
            "ev_sourced_from_engine_equity": False,
            "supports_metric_to_ev_bridge": True,
            **bridge.projection(),
        }
    )

    adaptive_method = context.get("upswitch_adaptive_method")
    if isinstance(adaptive_method, dict):
        adaptive_method = dict(adaptive_method)
        adaptive_method["value"] = str(ev_mid)
        adaptive_details = dict(cast(dict[str, object], adaptive_method.get("details") or {}))
        adaptive_details.update(
            {
                "enterprise_value_low": str(ev_low),
                "enterprise_value_mid": str(ev_mid),
                "enterprise_value_high": str(ev_high),
            }
        )
        adaptive_method["details"] = adaptive_details
        context["upswitch_adaptive_method"] = adaptive_method

    results_by_key = context.get("method_results_by_key")
    if isinstance(results_by_key, dict) and isinstance(
        results_by_key.get("upswitch_adaptive"), dict
    ):
        updated_results = dict(results_by_key)
        updated_adaptive = dict(cast(dict[str, object], results_by_key["upswitch_adaptive"]))
        updated_adaptive["value"] = str(ev_mid)
        updated_results["upswitch_adaptive"] = updated_adaptive
        context["method_results_by_key"] = updated_results

    transparency = context.get("advisor_multiple_transparency")
    if isinstance(transparency, dict):
        transparency = dict(transparency)
        if not bridge.available or net_debt is None or eq_mid is None:
            transparency["equity_bridge"] = None
            context["advisor_multiple_transparency"] = transparency
            return
        transparency["equity_bridge"] = {
            "rows": [
                {"label": "Enterprise value", "amount": str(ev_mid), "operator": None},
                {
                    "label": "Add: preliminary net cash",
                    "amount": str(abs(net_debt)),
                    "operator": "+" if net_debt < 0 else "−",
                },
                {
                    "label": "Illustrative equity value",
                    "amount": str(eq_mid),
                    "operator": "=",
                },
            ],
            "disclosures": [
                "Illustrative only; restricted cash, leases, debt-like items, normalized working capital and completion accounts remain unverified."
            ],
            "reconciles": abs((ev_mid - net_debt) - eq_mid) <= Decimal("0.01"),
        }
        context["advisor_multiple_transparency"] = transparency


def _apply_disclosed_fallback_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    multiples_results = request.valuation_result.multiples_results or {}
    is_fallback = multiples_results.get("multiples_source") == "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
    context["is_disclosed_external_market_fallback"] = is_fallback
    if not is_fallback:
        return

    base_multiple = _decimal_or_zero(context.get("base_multiple"))
    basis = _decimal_or_zero(context.get("valuation_basis_value"))
    business_type_id = str(
        multiples_results.get("business_type_id")
        or multiples_results.get("primary_business_type_id")
        or "selected-business-type"
    )
    market_key = f"{business_type_id} × {request.country_code}"
    segments = cast(
        list[object],
        cast(ReportMap, multiples_results.get("multiple_build_up") or {}).get("segments") or [],
    )
    first_segment = segments[0] if segments and isinstance(segments[0], dict) else {}
    category_label = str(
        cast(dict[str, object], first_segment).get("business_type_title") or request.industry
    )
    business_type_label = request.business_type_label or business_type_id.replace("_", " ").title()
    if business_type_id == "pharmacy" and (request.language or "nl").lower().startswith("nl"):
        # Preserve the canonical ID/label in the run while presenting the
        # correct client-facing Dutch activity label in an advisor report.
        business_type_label = "Apotheek"
    business_type_descriptor = business_type_label
    if request.nace_code:
        business_type_descriptor = f"{business_type_descriptor} · NACE {request.nace_code}"
    multiple_display = f"{base_multiple:.2f}".replace(".", ",")
    external_reference = multiples_results.get("disclosed_external_market_reference")
    external_reference = (
        dict(cast(dict[str, object], external_reference))
        if isinstance(external_reference, dict)
        else None
    )
    reference_summary = (
        str(external_reference.get("evidence_summary") or "") if external_reference else ""
    )
    reference_low = _decimal_or_zero(
        external_reference.get("range_low_multiple") if external_reference else None
    )
    reference_high = _decimal_or_zero(
        external_reference.get("range_high_multiple") if external_reference else None
    )
    has_external_reference_range = (
        reference_low > 0 and reference_high > 0 and reference_low <= reference_high
    )
    financial_metrics = request.valuation_result.financial_metrics or {}
    management_turnover_unaudited = (
        isinstance(financial_metrics, dict)
        and str(financial_metrics.get("revenue_source") or "").lower()
        == "management_workbook_unaudited"
    )
    earnings_ledger = multiples_results.get("earnings_basis_ledger")
    is_explicitly_weighted_reported_ebitda = bool(
        isinstance(earnings_ledger, dict) and earnings_ledger.get("mode") == "advisor_weighted"
    )
    current_reported_ebitda = _decimal_or_zero(
        financial_metrics.get("reported_ebitda") if isinstance(financial_metrics, dict) else None
    )

    context.update(
        {
            "has_industry_benchmarks": False,
            "has_benchmark_reference_multiple": False,
            "show_benchmark_reference_without_table": False,
            "benchmark_multiple_mid": None,
            "benchmark_multiple_low": None,
            "benchmark_multiple_high": None,
            "benchmark_sample_size": None,
            "benchmark_contract": None,
            "bridge_contract_resolved": False,
            "multiple_source": "DISCLOSED_EXTERNAL_MARKET_FALLBACK",
            "industry": business_type_label,
            "sector": business_type_label,
            "business_type_title": business_type_label,
            "cover_sub_line": business_type_label,
            "fallback_business_type_id": business_type_id,
            "fallback_business_type_label": business_type_label,
            "fallback_category_label": category_label,
            "fallback_country_code": request.country_code,
            "fallback_market_key": market_key,
            "fallback_applied_multiple": float(base_multiple),
            "disclosed_external_market_reference": external_reference,
            "fallback_reference_title": (
                str(external_reference.get("source_title") or "") if external_reference else None
            ),
            "fallback_reference_summary": reference_summary or None,
            "fallback_reference_range_low": (
                float(reference_low) if has_external_reference_range else None
            ),
            "fallback_reference_range_high": (
                float(reference_high) if has_external_reference_range else None
            ),
            # This is a disclosed external reference range, not a benchmark
            # percentile band.  Overwrite engine-derived ±20% presentation
            # bounds only for this explicit fallback path.
            "multiple_low": float(reference_low) if has_external_reference_range else None,
            "multiple_high": float(reference_high) if has_external_reference_range else None,
            "is_external_reference_range": has_external_reference_range,
            "management_turnover_unaudited": management_turnover_unaudited,
            "data_inputs": (
                [
                    "Managementomzet (niet-geauditeerd)",
                    "Gerapporteerde EBITDA (brongebonden)",
                ]
                if management_turnover_unaudited
                and (request.language or "nl").lower().startswith("nl")
                else context.get("data_inputs")
            ),
            "is_explicitly_weighted_reported_ebitda": (is_explicitly_weighted_reported_ebitda),
            # Keep the latest statutory EBITDA distinct from the multi-year
            # valuation basis.  A weighted basis must never be captioned as
            # "reported [latest year]" in a client-facing KPI card.
            "current_reported_ebitda": (
                float(current_reported_ebitda) if current_reported_ebitda > 0 else None
            ),
            "fallback_reasonableness_note": request.fallback_reasonableness_note,
            "show_size_discount_skipped_note": False,
            "limited_scope_years": len(request.valuation_result.valuation_timeline or []),
            "adaptive_methodology_justification": (
                f"Er is geen opgelost {market_key} Upswitch Index-contract. "
                "De conclusie gebruikt uitsluitend de uitdrukkelijk aanvaarde "
                f"externe marktreferentie van {multiple_display}× gerapporteerde EBITDA. "
                "Er zijn geen empirische percentielen, steekproef, vergelijkbare "
                "transacties of bedrijfsspecifieke aanpassingen toegepast; DCF "
                "draagt 0% bij."
            ),
            "methodology_statement": (
                f"De ondernemingswaarde is berekend als {multiple_display}× de gerapporteerde "
                f"EBITDA {request.reporting_year or context.get('current_year')} via de uitdrukkelijk aanvaarde "
                "externe marktreferentie. Dit is geen "
                f"{market_key} Index-contract, geen empirische benchmark en geen "
                "bewijs van vergelijkbare transacties. DCF en andere "
                "methoden dragen 0% bij aan de conclusie."
            ),
            "value_waterfall_intro_text": (
                "Van gerapporteerde EBITDA naar ondernemingswaarde en een "
                "uitsluitend illustratieve aandelenwaarde. Kas en financiële "
                "schuld komen uit de aangeleverde balans; restricted cash, leases, "
                "schuldachtige posten, genormaliseerd werkkapitaal en completion "
                "accounts moeten nog worden bevestigd."
            ),
        }
    )

    fallback_step = {
        "label": "Externe marktreferentie",
        "short_label": "Referentie",
        "kind": "base",
        "tone": "brand",
        "start_value": 0,
        "end_value": float(base_multiple),
        "multiple": float(base_multiple),
        "impact": None,
        "ev": float(base_multiple * basis),
        "ref": "†",
        "description": (
            f"No {market_key} Index contract; no empirical percentiles, "
            "sample or transaction attribution."
        ),
    }
    context["multiple_waterfall_steps"] = [fallback_step]
    context["calibration_steps"] = [fallback_step]
    context["discount_waterfall"] = [fallback_step]

    valuation_steps = context.get("valuation_waterfall_steps")
    if isinstance(valuation_steps, list) and valuation_steps:
        reported_steps = [
            dict(step) if isinstance(step, dict) else step for step in valuation_steps
        ]
        if isinstance(reported_steps[0], dict):
            reported_steps[0]["label"] = "Gerapporteerde EBITDA"
            reported_steps[0]["short_label"] = "Gerapp. EBITDA"
        context["valuation_waterfall_steps"] = reported_steps

    transparency = context.get("advisor_multiple_transparency")
    if isinstance(transparency, dict):
        transparency = dict(transparency)
        transparency.update(
            {
                "earnings_basis_rationale": (
                    "Gerapporteerde EBITDA; er zijn geen normalisaties toegepast."
                ),
                "risk_analysis_enabled": False,
                "risk_analysis_reference_only": True,
                "discount_floor_factor_percent": None,
                "discount_rows": [],
                "blend_rows": [],
                "segment_rows": [],
                "multiple_rows": [
                    {
                        "label": "Externe marktreferentie",
                        "multiple": str(base_multiple),
                        "enterprise_value": str(base_multiple * basis),
                    }
                ],
            }
        )
        transparency["benchmark_evidence"] = {
            "basis_label": "Externe marktreferentie (EV/EBITDA)",
            "business_type_title": business_type_descriptor,
            "low": external_reference.get("range_low_multiple") if external_reference else None,
            "mid": external_reference.get("applied_multiple") if external_reference else None,
            "high": external_reference.get("range_high_multiple") if external_reference else None,
            "data_source": (
                external_reference.get("source_title")
                if external_reference
                else "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
            ),
            "sample_size": None,
            "as_of": external_reference.get("source_as_of") if external_reference else None,
            "range_type": external_reference.get("range_type") if external_reference else None,
            "source_url": external_reference.get("source_url") if external_reference else None,
            "evidence_summary": (
                reference_summary
                or "Geen Upswitch Index-attributie; de band is geen empirische percentielverdeling."
            ),
        }
        previous_bridge = cast(dict[str, object], transparency.get("equity_bridge") or {})
        uses_net_cash = bool(context.get("bridge_uses_net_cash_label"))
        transparency["equity_bridge"] = {
            "rows": [
                {
                    "label": "Ondernemingswaarde (EV)",
                    "amount": str(context.get("enterprise_value_mid")),
                    "operator": None,
                },
                {
                    "label": (
                        "Toevoegen: voorlopige nettokas"
                        if uses_net_cash
                        else "Aftrek: voorlopige nettoschuld"
                    ),
                    "amount": str(context.get("bridge_net_debt_amount")),
                    "operator": "+" if uses_net_cash else "−",
                },
                {
                    "label": "Illustratieve aandelenwaarde",
                    "amount": str(context.get("equity_value")),
                    "operator": "=",
                },
            ],
            "disclosures": [
                "Uitsluitend illustratief; restricted cash, leases, schuldachtige posten, genormaliseerd werkkapitaal en completion accounts zijn nog niet geverifieerd."
            ],
            "reconciles": bool(previous_bridge.get("reconciles")),
        }
        context["advisor_multiple_transparency"] = transparency


def _apply_unweighted_lens_disclosure_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Render-only cross-check lenses, shown at 0% weight.

    Written straight onto the finalized template context on purpose. It is
    deliberately NOT routed through the aggregation dict (the legacy pricing
    path never sees it) and NOT appended to ``synthesis_contributions``: the
    displayed low/high band is derived from those rows by min/max with no
    weight filter, so a 0%-weight disclosure placed there would silently move
    the client-visible band.
    """

    lenses = list(getattr(request, "unweighted_valuation_lenses", []) or [])
    context["unweighted_valuation_lenses"] = [
        {
            "lens_id": lens.lens_id,
            "label": lens.label,
            "value": lens.value,
            "value_basis": lens.value_basis,
            "computation_note": lens.computation_note,
            "zero_weight_reason": lens.zero_weight_reason,
            "weight_pct": 0,
        }
        for lens in lenses
    ]
    context["show_unweighted_lens_disclosure"] = bool(lenses)
    if not lenses:
        return
    # "2 methodes" contradicts a report that visibly examines three lenses.
    # State both numbers: lenses examined vs comparable methods weighted.
    weighted = cast(list[object], context.get("synthesis_contributions") or [])
    locale = str(context.get("locale") or "nl").strip().lower()[:2]
    # Count LENSES, not rows: several cases of one rule of thumb are one lens.
    families = {lens.lens_family or lens.lens_id for lens in lenses}
    examined = len(weighted) + len(families)
    # This lands in a narrow stat card, so keep it short; the full framing is
    # spelled out in prose on the synthesis page.
    if locale == "fr":
        label = f"{examined} lentilles · {len(weighted)} pondérées"
    elif locale == "en":
        label = f"{examined} lenses · {len(weighted)} weighted"
    else:
        label = f"{examined} lenzen · {len(weighted)} gewogen"
    context["synthesis_method_count_label"] = label
