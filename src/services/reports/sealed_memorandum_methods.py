"""Typed, calculation-free presentation rows for memorandum method packs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Callable

from src.services.reports.report_benchmark_contracts import (
    normalize_benchmark_contract,
)

Display = Callable[[object, str], str]


def _map(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[object]:
    return (
        list(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
        else []
    )


def _number(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _field(
    field_id: str,
    label: str,
    value: object,
    kind: str,
    display: Display,
) -> dict[str, object] | None:
    if value is None or value == "":
        return None
    return {
        "field_id": field_id,
        "label": label,
        "raw": str(value),
        "display": display(value, kind),
    }


def _fields(*values: dict[str, object] | None) -> list[dict[str, object]]:
    return [value for value in values if value is not None]


def _first(mapping: Mapping[str, object], *keys: str) -> object | None:
    """Return the first present value without treating a valid zero as absent."""

    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _cell(
    field_id: str,
    value: object,
    kind: str,
    display: Display,
) -> dict[str, str]:
    return {
        "field_id": field_id,
        "display": display(value, kind),
    }


def _table(
    title: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[dict[str, str]]],
) -> dict[str, object] | None:
    materialized = [list(row) for row in rows]
    if not materialized:
        return None
    return {"title": title, "headers": list(headers), "rows": materialized}


def _tables(*values: dict[str, object] | None) -> list[dict[str, object]]:
    return [value for value in values if value is not None]


def _market_page(
    context: Mapping[str, object], copy: Mapping[str, str], display: Display
) -> dict[str, object]:
    metric = str(context.get("multiple_metric_type") or "EBITDA").upper()
    basis = context.get("revenue") if metric == "REVENUE" else context.get("sustainable_ebitda")
    contract = normalize_benchmark_contract(context.get("benchmark_contract"))
    primary = str(contract.get("primary_metric") or metric)
    metric_payload = _map(_map(contract.get("metrics")).get(primary))
    primary_label = primary.replace("_", "/").upper()
    confidence_raw = str(contract.get("confidence_band") or "").strip().lower()
    confidence_label = copy.get(confidence_raw, confidence_raw)
    benchmark_rows = _fields(
        _field("benchmark.metric", copy["metric"], primary_label, "text", display),
        _field(
            "benchmark.sample_size",
            copy["observations"],
            contract.get("sample_size"),
            "integer",
            display,
        ),
        _field(
            "benchmark.confidence",
            copy["confidence"],
            confidence_label,
            "text",
            display,
        ),
        _field(
            "benchmark.p25",
            "P25",
            metric_payload.get("p25", context.get("multiple_low")),
            "multiple",
            display,
        ),
        _field(
            "benchmark.median",
            "P50",
            metric_payload.get("median", context.get("benchmark_multiple_mid")),
            "multiple",
            display,
        ),
        _field(
            "benchmark.p75",
            "P75",
            metric_payload.get("p75", context.get("multiple_high")),
            "multiple",
            display,
        ),
    )
    provenance = " · ".join(
        str(value)
        for value in (
            contract.get("dataset_version_id"),
            contract.get("country_code"),
            contract.get("source_primary_nace_code"),
            contract.get("published_at"),
        )
        if value not in (None, "")
    )
    return {
        "method_id": "market",
        "title": copy["market_method"]
        if metric != "REVENUE"
        else copy["revenue_market_method"],
        "eligibility": copy["eligible"],
        "eligibility_reason": copy["market_reason"],
        "rows": _fields(
            _field("method.market.metric_basis", copy["metric"], basis, "currency", display),
            _field(
                "method.market.applied_multiple",
                copy["multiple"],
                context.get("applied_multiple"),
                "multiple",
                display,
            ),
            _field(
                "method.market.enterprise_value",
                copy["enterprise_value"],
                context.get("ev_revenue_enterprise_value")
                if metric == "REVENUE"
                else context.get("ev_ebitda_enterprise_value", context.get("enterprise_value_mid")),
                "currency",
                display,
            ),
        ),
        "benchmark_rows": benchmark_rows,
        "benchmark_classification": copy["borrowed"]
        if contract.get("is_borrowed") is True
        else copy["direct"],
        "provenance": provenance,
        "notes": [],
    }


def _dcf_page(
    context: Mapping[str, object], copy: Mapping[str, str], display: Display
) -> dict[str, object]:
    sealed = _map(context.get("sealed_display"))
    dcf = _map(sealed.get("dcf"))
    projections: list[dict[str, object]] = []
    for index, raw in enumerate(_list(dcf.get("projection_rows"))):
        row = _map(raw)
        projections.append(
            {
                "year": display(row.get("year"), "text"),
                "revenue": display(row.get("revenue"), "currency"),
                "ebitda": display(row.get("ebitda"), "currency"),
                "fcff": display(row.get("free_cash_flow"), "currency"),
                "pv_fcff": display(row.get("present_value_free_cash_flow"), "currency"),
                "field_ids": {
                    "revenue": f"method.dcf.projection.{index}.revenue",
                    "ebitda": f"method.dcf.projection.{index}.ebitda",
                    "fcff": f"method.dcf.projection.{index}.fcff",
                    "pv_fcff": f"method.dcf.projection.{index}.pv_fcff",
                },
            }
        )
    buildup = _map(context.get("dcf_wacc_buildup"))
    sensitivity = _map(context.get("dcf_sensitivity_matrix_2d"))
    sensitivity_matrix = _map(sensitivity.get("matrix"))
    sensitivity_rows: list[list[dict[str, str]]] = []
    for row_index, (wacc, raw_values) in enumerate(sensitivity_matrix.items()):
        for column_index, (growth, value) in enumerate(_map(raw_values).items()):
            sensitivity_rows.append(
                [
                    _cell(
                        f"method.dcf.sensitivity.{row_index}.{column_index}.wacc",
                        wacc,
                        "percent_ratio",
                        display,
                    ),
                    _cell(
                        f"method.dcf.sensitivity.{row_index}.{column_index}.growth",
                        growth,
                        "percent_ratio",
                        display,
                    ),
                    _cell(
                        f"method.dcf.sensitivity.{row_index}.{column_index}.ev",
                        value,
                        "currency",
                        display,
                    ),
                ]
            )
    return {
        "method_id": "dcf",
        "title": copy["dcf_method"],
        "eligibility": copy["eligible"],
        "eligibility_reason": copy["dcf_reason"],
        "rows": _fields(
            _field("method.dcf.wacc", copy["wacc"], context.get("dcf_wacc"), "percent_ratio", display),
            _field(
                "method.dcf.cost_of_equity",
                copy["cost_of_equity"],
                _first(buildup, "cost_of_equity")
                or context.get("dcf_cost_of_equity"),
                "percent_ratio",
                display,
            ),
            _field(
                "method.dcf.cost_of_debt",
                copy["cost_of_debt"],
                _first(buildup, "cost_of_debt")
                or context.get("dcf_cost_of_debt"),
                "percent_ratio",
                display,
            ),
            _field(
                "method.dcf.terminal_growth",
                copy["terminal_growth"],
                context.get("dcf_terminal_growth_rate"),
                "percent_ratio",
                display,
            ),
            _field(
                "method.dcf.terminal_method",
                copy["terminal_method"],
                context.get("dcf_terminal_value_methodology"),
                "text",
                display,
            ),
            _field(
                "method.dcf.discount_convention",
                copy["discount_convention"],
                context.get("dcf_discount_periods_note")
                or (
                    copy["mid_year"]
                    if context.get("dcf_mid_year_discounting") is True
                    else copy["year_end"]
                ),
                "text",
                display,
            ),
            _field("method.dcf.pv_explicit", "PV FCFF", dcf.get("pv_explicit"), "currency", display),
            _field("method.dcf.pv_terminal", "PV terminal", dcf.get("pv_terminal"), "currency", display),
            _field(
                "method.dcf.terminal_value_share",
                copy["terminal_share"],
                dcf.get("terminal_value_pct"),
                "percent",
                display,
            ),
            _field(
                "method.dcf.enterprise_value",
                copy["enterprise_value"],
                dcf.get("enterprise_value"),
                "currency",
                display,
            ),
        ),
        "projection_rows": projections,
        "detail_tables": _tables(
            _table(
                copy["sensitivity_matrix"],
                (copy["wacc"], copy["terminal_growth"], copy["enterprise_value"]),
                sensitivity_rows,
            )
        ),
        "benchmark_rows": [],
        "notes": [copy["terminal_share_warning"]]
        if (_number(dcf.get("terminal_value_pct")) or Decimal("0")) >= Decimal("60")
        else [],
    }


def _sde_page(
    context: Mapping[str, object], copy: Mapping[str, str], display: Display
) -> dict[str, object]:
    component_rows: list[list[dict[str, str]]] = []
    for index, raw in enumerate(_list(context.get("sde_components"))):
        component = _map(raw)
        component_rows.append(
            [
                _cell(
                    f"method.sde.component.{index}.label",
                    _first(component, "label", "name", "component") or "—",
                    "text",
                    display,
                ),
                _cell(
                    f"method.sde.component.{index}.amount",
                    _first(component, "amount", "value"),
                    "signed_currency",
                    display,
                ),
            ]
        )
    replacement_cost = (
        context.get("sde_replacement_owner_compensation")
        or context.get("replacement_owner_compensation")
        or context.get("owner_replacement_compensation")
    )
    return {
        "method_id": "sde",
        "title": copy["sde"],
        "eligibility": copy["eligible"],
        "eligibility_reason": copy["sde_reason"],
        "rows": _fields(
            _field("method.sde.earnings", copy["sde"], context.get("sde_value"), "currency", display),
            _field(
                "method.sde.owner_remuneration",
                copy["owner_remuneration"],
                context.get("sde_owner_salary"),
                "currency",
                display,
            ),
            _field(
                "method.sde.replacement_cost",
                copy["replacement_cost"],
                replacement_cost,
                "currency",
                display,
            ),
            _field("method.sde.multiple", copy["multiple"], context.get("sde_multiple"), "multiple", display),
            _field(
                "method.sde.enterprise_value",
                copy["enterprise_value"],
                context.get("ev_sde_enterprise_value"),
                "currency",
                display,
            ),
        ),
        "benchmark_rows": [],
        "detail_tables": _tables(
            _table(
                copy["sde_bridge"],
                (copy["component"], copy["amount"]),
                component_rows,
            )
        ),
        "notes": [copy["owner_premise"], copy["replacement_cost_disclosure"]],
    }


def _revenue_page(
    context: Mapping[str, object], copy: Mapping[str, str], display: Display
) -> dict[str, object]:
    startup = _map(context.get("startup_report"))
    traction = _map(startup.get("traction"))
    revenue = context.get("revenue") or traction.get("arr") or traction.get("mrr")
    multiple = context.get("revenue_multiple_applied") or context.get("applied_multiple")
    return {
        "method_id": "revenue_startup",
        "title": copy["revenue_startup_method"],
        "eligibility": copy["eligible"],
        "eligibility_reason": copy["revenue_reason"],
        "rows": _fields(
            _field("method.revenue.arr", "ARR", traction.get("arr"), "currency", display),
            _field("method.revenue.mrr", "MRR", traction.get("mrr"), "currency", display),
            _field("method.revenue.metric", copy["revenue"], revenue, "currency", display),
            _field("method.revenue.growth", copy["growth"], traction.get("mrr_growth_rate_pct"), "percent", display),
            _field("method.revenue.retention", copy["retention"], traction.get("net_revenue_retention_pct"), "percent", display),
            _field("method.revenue.churn", copy["churn"], traction.get("monthly_churn_pct"), "percent", display),
            _field("method.revenue.gross_margin", copy["gross_margin"], traction.get("gross_margin_pct"), "percent", display),
            _field("method.revenue.multiple", copy["multiple"], multiple, "multiple", display),
            _field(
                "method.revenue.enterprise_value",
                copy["enterprise_value"],
                context.get("ev_revenue_enterprise_value", context.get("enterprise_value_mid")),
                "currency",
                display,
            ),
            _field("method.revenue.burn", copy["monthly_burn"], traction.get("burn_rate_monthly"), "currency", display),
            _field("method.revenue.runway", copy["runway"], traction.get("runway_months"), "months", display),
            _field("method.revenue.stage", copy["stage"], startup.get("stage"), "text", display),
            _field(
                "method.revenue.dilution",
                copy["dilution"],
                _first(_map(startup.get("dilution_scenario")), "dilution_pct", "percentage"),
                "percent",
                display,
            ),
        ),
        "benchmark_rows": [],
        "detail_tables": [],
        "notes": [],
    }


def _nav_page(
    context: Mapping[str, object], copy: Mapping[str, str], display: Display
) -> dict[str, object]:
    sealed = _map(context.get("sealed_display"))
    nav = _map(sealed.get("nav"))
    audit = _map(context.get("nav_audit_trail"))
    asset_rows: list[list[dict[str, str]]] = []
    explicit_assets = _list(context.get("nav_asset_schedule"))
    for index, raw in enumerate(explicit_assets):
        asset = _map(raw)
        asset_rows.append(
            [
                _cell(
                    f"method.nav.asset.{index}.name",
                    _first(asset, "asset_name", "asset_class", "name") or "—",
                    "text",
                    display,
                ),
                _cell(
                    f"method.nav.asset.{index}.book",
                    _first(asset, "book_value", "tax_book_value"),
                    "currency",
                    display,
                ),
                _cell(
                    f"method.nav.asset.{index}.market",
                    _first(asset, "market_value", "appraisal_value", "economic_value"),
                    "currency",
                    display,
                ),
                _cell(
                    f"method.nav.asset.{index}.latent_tax",
                    _first(asset, "latent_tax", "deferred_tax"),
                    "currency",
                    display,
                ),
            ]
        )
    if not asset_rows:
        for index, key in enumerate(("real_estate_revaluation", "equipment_revaluation")):
            asset = _map(audit.get(key))
            if not asset:
                continue
            asset_rows.append(
                [
                    _cell(f"method.nav.asset.{index}.name", copy[key], "text", display),
                    _cell(
                        f"method.nav.asset.{index}.book",
                        _first(asset, "book_value", "tax_book_value"),
                        "currency",
                        display,
                    ),
                    _cell(
                        f"method.nav.asset.{index}.market",
                        _first(asset, "appraisal_value", "economic_book_value"),
                        "currency",
                        display,
                    ),
                    _cell(
                        f"method.nav.asset.{index}.latent_tax",
                        _first(asset, "deferred_tax", "latent_tax"),
                        "currency",
                        display,
                    ),
                ]
            )
    return {
        "method_id": "adjusted_nav",
        "title": copy["corrected_nav"],
        "eligibility": copy["eligible"],
        "eligibility_reason": copy["nav_reason"],
        "rows": _fields(
            _field("method.adjusted_nav.book_equity", copy["book_equity"], nav.get("book_equity"), "currency", display),
            _field("method.adjusted_nav.revaluation_uplift", copy["revaluation"], nav.get("uplift"), "signed_currency", display),
            _field("method.adjusted_nav.corrected_value", copy["corrected_nav"], nav.get("corrected_value"), "currency", display),
            _field("method.adjusted_nav.ownership", copy["ownership"], nav.get("ownership_pct"), "percent", display),
        ),
        "benchmark_rows": [],
        "detail_tables": _tables(
            _table(
                copy["asset_schedule"],
                (copy["asset"], copy["book_value"], copy["market_value"], copy["latent_tax"]),
                asset_rows,
            )
        ),
        "notes": [copy["nav_no_double_counting"]],
    }


def _sotp_page(
    context: Mapping[str, object], copy: Mapping[str, str], display: Display
) -> dict[str, object]:
    holding = _map(context.get("holding_sotp"))
    entities = _list(
        holding.get("entity_rows")
        or holding.get("entities")
        or holding.get("components")
        or holding.get("segments")
    )
    rows: list[dict[str, object]] = []
    entity_rows: list[list[dict[str, str]]] = []
    for index, raw in enumerate(entities):
        entity = _map(raw)
        name = entity.get("name") or entity.get("entity_name") or entity.get("label") or f"{copy['entity']} {index + 1}"
        value = _first(
            entity,
            "equity_value_mid_contribution",
            "equity_value",
            "value",
            "enterprise_value_mid_contribution",
            "enterprise_value",
        )
        field = _field(f"method.sotp.entity.{index}.value", str(name), value, "currency", display)
        if field:
            rows.append(field)
        entity_rows.append(
            [
                _cell(f"method.sotp.entity.{index}.name", name, "text", display),
                _cell(
                    f"method.sotp.entity.{index}.method",
                    _first(entity, "method", "valuation_method") or "—",
                    "text",
                    display,
                ),
                _cell(
                    f"method.sotp.entity.{index}.currency",
                    _first(entity, "currency") or holding.get("currency") or "—",
                    "text",
                    display,
                ),
                _cell(
                    f"method.sotp.entity.{index}.ownership",
                    _first(entity, "ownership_pct", "ownership_percentage"),
                    "percent",
                    display,
                ),
                _cell(
                    f"method.sotp.entity.{index}.equity",
                    value,
                    "currency",
                    display,
                ),
            ]
        )
    rows.extend(
        _fields(
            _field("method.sotp.intercompany_eliminations", copy["intercompany"], holding.get("intercompany_eliminations"), "signed_currency", display),
            _field("method.sotp.non_operating_assets", copy["non_operating_assets"], holding.get("non_operating_assets"), "signed_currency", display),
            _field("method.sotp.holding_discount", copy["holding_discount"], holding.get("holding_discount_pct"), "percent", display),
            _field("method.sotp.equity_value", copy["equity_value"], context.get("equity_value_mid"), "currency", display),
        )
    )
    return {
        "method_id": "holding_sotp",
        "title": copy["sotp"],
        "eligibility": copy["eligible"],
        "eligibility_reason": copy["sotp_reason"],
        "rows": rows,
        "benchmark_rows": [],
        "detail_tables": _tables(
            _table(
                copy["entity_schedule"],
                (copy["entity"], copy["method"], copy["currency"], copy["ownership"], copy["equity_value"]),
                entity_rows,
            )
        ),
        "notes": [copy["holding_discount_once"]],
    }


def _liquidation_page(
    context: Mapping[str, object], copy: Mapping[str, str], display: Display
) -> dict[str, object]:
    liquidation = _map(context.get("liquidation_report"))
    premise = _map(liquidation.get("premise"))
    statement = _map(liquidation.get("statement_of_affairs"))
    asset_schedule = _map(liquidation.get("asset_schedule"))
    asset_rows: list[list[dict[str, str]]] = []
    for index, raw in enumerate(_list(asset_schedule.get("lines"))):
        asset = _map(raw)
        asset_rows.append(
            [
                _cell(
                    f"method.liquidation.asset.{index}.class",
                    _first(asset, "class_label", "asset_class", "name") or "—",
                    "text",
                    display,
                ),
                _cell(
                    f"method.liquidation.asset.{index}.book",
                    _first(asset, "book_value", "carrying_value"),
                    "currency",
                    display,
                ),
                _cell(
                    f"method.liquidation.asset.{index}.orderly",
                    _first(asset, "orderly_recoverable_value", "recoverable_value"),
                    "currency",
                    display,
                ),
                _cell(
                    f"method.liquidation.asset.{index}.forced",
                    _first(asset, "forced_recoverable_value"),
                    "currency",
                    display,
                ),
            ]
        )
    return {
        "method_id": "liquidation",
        "title": copy["liquidation"],
        "eligibility": copy["eligible"],
        "eligibility_reason": copy["liquidation_reason"],
        "rows": _fields(
            _field("method.liquidation.premise", copy["premise"], premise.get("basis") or premise.get("name"), "text", display),
            _field("method.liquidation.orderly_value", copy["orderly_realization"], statement.get("orderly_equity") or liquidation.get("orderly_equity_value"), "currency", display),
            _field("method.liquidation.forced_value", copy["forced_realization"], statement.get("forced_equity") or liquidation.get("forced_equity_value"), "currency", display),
            _field("method.liquidation.headline_equity", copy["equity_value"], liquidation.get("headline_equity") or context.get("equity_value_mid"), "currency", display),
        ),
        "benchmark_rows": [],
        "detail_tables": _tables(
            _table(
                copy["asset_realization_schedule"],
                (copy["asset"], copy["book_value"], copy["orderly_realization"], copy["forced_realization"]),
                asset_rows,
            )
        ),
        "notes": [copy["liquidation_not_going_concern"]],
    }


def build_method_pages(
    context: Mapping[str, object], copy: Mapping[str, str], display: Display
) -> list[dict[str, object]]:
    raw_sections = _list(
        context.get("sme_report_sections") or context.get("sealed_report_sections")
    )
    section_ids = {str(_map(section).get("id") or "") for section in raw_sections}
    pages: list[dict[str, object]] = []
    if context.get("is_liquidation_report"):
        return [_liquidation_page(context, copy, display)]
    if context.get("is_startup_valuation_report"):
        return [_revenue_page(context, copy, display)]
    if {"upswitch_adaptive", "ebitda_multiple"}.intersection(section_ids):
        pages.append(_market_page(context, copy, display))
    if "dcf" in section_ids:
        pages.append(_dcf_page(context, copy, display))
    if "sde" in section_ids:
        pages.append(_sde_page(context, copy, display))
    if {"revenue_multiple", "saas_appendix"}.intersection(section_ids):
        pages.append(_revenue_page(context, copy, display))
    if "adjusted_nav" in section_ids:
        pages.append(_nav_page(context, copy, display))
    if "holding_sotp" in section_ids:
        pages.append(_sotp_page(context, copy, display))
    return pages
