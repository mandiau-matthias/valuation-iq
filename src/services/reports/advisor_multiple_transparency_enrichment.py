"""Post-processing enrichment for advisor multiple transparency appendices."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

from src.domain.method_keys import normalize_selected_method_key

from src.services.reports.equity_bridge_localization import localize_equity_bridge
from src.services.reports.multiple_row_localization import localize_multiple_rows

JsonMap = dict[str, object]

_MARKET_MULTIPLE_METHOD_KEYS = frozenset(
    {
        "ebitda_multiple",
        "omzet_multiple",
        "arr_multiple",
        "sde_multiple",
        "real_estate_yield",
    }
)
_NON_MARKET_METHOD_KEYS = frozenset(
    {
        "dcf",
        "adjusted_nav",
        "holding_sotp",
        "startup_valuation",
        "fiscal_4x",
        "liquidation_analysis",
    }
)

_DISCOUNT_NUMERIC_FIELDS = (
    "model_adjustment_percent",
    "advisor_weight_percent",
    "effective_adjustment_percent",
    "factor_before",
    "factor_after",
    "euro_impact",
)


def _as_mapping(value: object) -> JsonMap | None:
    if isinstance(value, Mapping):
        return {str(key): nested for key, nested in value.items()}
    return None


def _as_list(value: object) -> list[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _normalize_discount_row_numbers(row: JsonMap) -> None:
    """Keep persisted JSON rows render-safe after Decimal values round-trip as strings."""
    for key in _DISCOUNT_NUMERIC_FIELDS:
        if key in row:
            row[key] = _decimal(row.get(key))


def _has_value(value: object) -> bool:
    return value is not None and value != ""


def _first_context_value(context: Mapping[str, object], *keys: str) -> object | None:
    for key in keys:
        value = context.get(key)
        if _has_value(value):
            return value
    return None


def _positive_adaptive_market_weight(context: Mapping[str, object]) -> bool | None:
    """Return the governed adaptive market-leg state when it is disclosed.

    ``None`` means the legacy context did not expose a weight.  Zero is a real
    exclusion and must not be collapsed into that unknown state.
    """

    for key in (
        "adaptive_presentation_multiples_weight",
        "adaptive_multiples_weight",
        "multiples_weight",
    ):
        if key not in context or context.get(key) in (None, ""):
            continue
        weight = _decimal(context.get(key))
        return bool(weight is not None and weight > Decimal("0"))
    return None


def _priced_market_multiple_contributed(context: Mapping[str, object]) -> bool:
    """Fail closed unless the selected conclusion contains a market leg.

    The report aggregator computes candidate multiples even for a pure DCF or
    asset conclusion.  Those candidates are not priced methods and must never
    activate the multiple-evidence/discount appendices.  Canonical selected
    methods take precedence; the numeric multiple fallback is retained only
    for older report contexts that have no method identity at all.
    """

    selected_method = normalize_selected_method_key(context.get("selected_method"))
    if context.get("is_dcf_only_methodology") or selected_method in _NON_MARKET_METHOD_KEYS:
        return False
    if selected_method in _MARKET_MULTIPLE_METHOD_KEYS:
        return True
    if selected_method in {"upswitch_adaptive", "upswitch_adaptive_multiples_only"} or context.get(
        "has_weighted_synthesis"
    ):
        adaptive_market_weight = _positive_adaptive_market_weight(context)
        if adaptive_market_weight is not None:
            return adaptive_market_weight

    applied_multiple = _decimal(context.get("applied_multiple"))
    return bool(applied_multiple is not None and applied_multiple > Decimal("0"))


def _apply_multiple_appendix_gates(context: JsonMap, *, show: bool) -> None:
    context["show_advisor_multiple_transparency_appendix"] = show
    context["show_multiple_evidence_appendix"] = show
    context["show_discount_methodology_appendix"] = show


def _build_benchmark_evidence(context: Mapping[str, object]) -> JsonMap:
    low = _decimal(
        _first_context_value(context, "benchmark_multiple_low", "benchmark_ev_ebitda_p25")
    )
    mid = _decimal(
        _first_context_value(context, "benchmark_multiple_mid", "benchmark_ev_ebitda_p50")
    )
    high = _decimal(
        _first_context_value(context, "benchmark_multiple_high", "benchmark_ev_ebitda_p75")
    )
    revenue_mid = _decimal(context.get("benchmark_ev_revenue_median"))
    if mid is None and revenue_mid is not None:
        mid = revenue_mid

    evidence = {
        "basis_label": _first_context_value(
            context,
            "benchmark_multiple_label",
            "multiple_display_label",
            "multiple_metric_type",
        ),
        "business_type_title": context.get("business_type_title"),
        "nace_code": context.get("nace_code"),
        "sector": context.get("sector"),
        "low": low,
        "mid": mid,
        "high": high,
        "sample_size": context.get("benchmark_sample_size"),
        "data_source": context.get("benchmark_data_source"),
        "as_of": context.get("benchmark_published_at"),
        "region": context.get("benchmark_region_key") or context.get("benchmark_country_code"),
        "tier": context.get("benchmark_tier"),
        "scope_stage": context.get("benchmark_scope_stage"),
        "source_mix": context.get("benchmark_source_mix"),
        "evidence_summary": context.get("benchmark_evidence_summary"),
    }
    return {key: value for key, value in evidence.items() if _has_value(value)}


def _bridge_row(label: str, amount: Decimal | None, operator: str | None = None) -> JsonMap:
    return {
        "label": label,
        "amount": amount,
        "operator": operator,
    }


def _append_signed_bridge_row(
    rows: list[JsonMap],
    *,
    label: str,
    amount: Decimal | None,
) -> None:
    if amount is None or amount == Decimal("0"):
        return
    rows.append(_bridge_row(label, abs(amount), "+" if amount >= 0 else "-"))


def _append_net_debt_bridge_row(rows: list[JsonMap], context: Mapping[str, object]) -> None:
    if not (
        context.get("has_net_debt_adjustment") and _has_value(context.get("bridge_net_debt_amount"))
    ):
        return
    amount = _decimal(context.get("bridge_net_debt_amount"))
    if amount is None or amount == Decimal("0"):
        return
    operator = str(context.get("bridge_net_debt_operator") or "-")
    rows.append(
        _bridge_row(
            "Net cash" if operator == "+" else "Net debt",
            abs(amount),
            "+" if operator == "+" else "-",
        )
    )


def _balance_adjustment_label(adjustment: JsonMap) -> str:
    label = str(adjustment.get("label") or adjustment.get("category") or "Balance adjustment")
    if adjustment.get("account_code"):
        return f"{label} ({adjustment['account_code']})"
    return label


def _balance_adjustment_signed_amount(adjustment: JsonMap) -> Decimal | None:
    amount = _decimal(adjustment.get("amount"))
    if amount is None or amount == Decimal("0"):
        return None
    adjustment_type = str(adjustment.get("type") or "add").lower()
    if adjustment_type in {"subtract", "deduct", "minus"}:
        return -abs(amount)
    return abs(amount)


def _append_balance_adjustment_rows(rows: list[JsonMap], context: Mapping[str, object]) -> None:
    adjustments = context.get("balance_sheet_adjustments")
    if not isinstance(adjustments, Sequence) or isinstance(adjustments, (str, bytes, bytearray)):
        return
    for raw_adjustment in adjustments:
        adjustment = _as_mapping(raw_adjustment)
        if not adjustment:
            continue
        signed = _balance_adjustment_signed_amount(adjustment)
        if signed is None:
            continue
        _append_signed_bridge_row(
            rows,
            label=_balance_adjustment_label(adjustment),
            amount=signed,
        )


def _append_residual_bridge_row(rows: list[JsonMap], context: Mapping[str, object]) -> None:
    if not context.get("has_bridge_residual"):
        return
    residual = _decimal(context.get("bridge_residual_amount"))
    if residual is None or residual == Decimal("0"):
        return
    operator = str(context.get("bridge_residual_operator") or "+")
    rows.append(
        _bridge_row(
            str(context.get("bridge_residual_label") or "Reconciliation item"),
            abs(residual),
            "+" if operator == "+" else "-",
        )
    )


def _equity_bridge_disclosures(context: Mapping[str, object]) -> list[str]:
    if not context.get("has_balance_data"):
        return ["NWC normalization and surplus assets not assessed - no balance sheet."]
    if not context.get("show_ev_equity_bridge"):
        return ["No EV-to-equity adjustment was required by the available balance data."]
    if not _decimal(context.get("bridge_nwc_adjustment")):
        return ["NWC normalization not assessed separately in the supplied balance data."]
    return []


def _build_equity_bridge(context: Mapping[str, object]) -> JsonMap:
    rows: list[JsonMap] = []
    enterprise_value = _decimal(context.get("enterprise_value_mid"))
    equity_value = _decimal(context.get("equity_value"))

    if enterprise_value is not None:
        rows.append(_bridge_row("Enterprise value", enterprise_value))

    _append_net_debt_bridge_row(rows, context)
    _append_signed_bridge_row(
        rows,
        label="Tax latencies",
        amount=_decimal(context.get("tax_latency_net_impact")),
    )
    _append_balance_adjustment_rows(rows, context)
    _append_signed_bridge_row(
        rows,
        label="Normalised working capital",
        amount=_decimal(context.get("bridge_nwc_adjustment")),
    )
    _append_residual_bridge_row(rows, context)

    if equity_value is not None:
        rows.append(_bridge_row("Equity value", equity_value, "="))

    return {
        "rows": rows,
        "disclosures": _equity_bridge_disclosures(context),
        "reconciles": enterprise_value is not None and equity_value is not None,
    }


def enrich_discount_impacts(
    appendix: JsonMap,
    enterprise_value_mid: Decimal | None,
) -> None:
    earnings = _decimal(appendix.get("discount_earnings"))
    for row in appendix.get("discount_rows") or []:
        if not isinstance(row, dict):
            continue
        _normalize_discount_row_numbers(row)
        row.setdefault("euro_impact", None)
        row.setdefault("impact_basis", None)
        before = _decimal(row.get("factor_before"))
        after = _decimal(row.get("factor_after"))
        if before is not None and after is not None:
            is_multiple = row.get("factor_unit") == "multiple"
            basis = earnings if is_multiple else enterprise_value_mid
            row["euro_impact"] = (
                (basis * (after - before)).quantize(Decimal("0.01")) if basis is not None else None
            )
            row["impact_basis"] = (
                ("multiple_delta" if is_multiple else "factor_delta") if basis is not None else None
            )
            continue
        if enterprise_value_mid is None:
            continue
        effective_pct = _decimal(row.get("effective_adjustment_percent"))
        if effective_pct is not None:
            row["euro_impact"] = (enterprise_value_mid * effective_pct / Decimal("100")).quantize(
                Decimal("0.01")
            )
            row["impact_basis"] = "effective_percent"


def _reconcile_undiscounted_multiple_rows(
    appendix: JsonMap,
    applied_multiple: Decimal | None,
) -> None:
    if applied_multiple is None or applied_multiple <= Decimal("0"):
        return
    if _as_list(appendix.get("discount_rows")):
        return

    rows = _as_list(appendix.get("multiple_rows"))
    if not rows:
        return
    row_maps = [_as_mapping(row) for row in rows]
    if any(not row for row in row_maps):
        return
    typed_rows = [row for row in row_maps if row is not None]
    if any(
        row.get("advisor_multiple") is not None or row.get("override_note") for row in typed_rows
    ):
        return

    reference = next(
        (
            _decimal(row.get("multiple"))
            for row in typed_rows
            if str(row.get("label") or "").lower().startswith("reference")
        ),
        None,
    )
    reconciled = False
    for row in typed_rows:
        label = str(row.get("label") or "").lower()
        if not (label.startswith("applied") or label.startswith("effective")):
            continue
        row["multiple"] = applied_multiple
        row["adjustment"] = (
            (applied_multiple - reference).quantize(Decimal("0.01"))
            if reference is not None
            else None
        )
        reconciled = True

    if reconciled:
        appendix["multiple_rows"] = typed_rows


def enrich_advisor_multiple_transparency_context(context: JsonMap) -> None:
    """Attach final report evidence to the multiples transparency appendix."""

    appendix = _as_mapping(context.get("advisor_multiple_transparency")) or {}
    benchmark_evidence = _build_benchmark_evidence(context)
    equity_bridge = localize_equity_bridge(
        _build_equity_bridge(context), str(context.get("locale") or "nl")
    )

    if benchmark_evidence:
        appendix["benchmark_evidence"] = benchmark_evidence
    appendix["equity_bridge"] = equity_bridge
    appendix["has_equity_bridge_rows"] = bool(equity_bridge.get("rows"))

    enrich_discount_impacts(appendix, _decimal(context.get("enterprise_value_mid")))

    applied_multiple = _decimal(context.get("applied_multiple"))
    _reconcile_undiscounted_multiple_rows(appendix, applied_multiple)
    appendix["multiple_rows"] = localize_multiple_rows(
        _as_list(appendix.get("multiple_rows")), str(context.get("locale") or "nl")
    )
    has_multiple_method = applied_multiple is not None and applied_multiple > Decimal("0")
    show = bool(
        _priced_market_multiple_contributed(context)
        and (context.get("show_advisor_multiple_transparency_appendix") or has_multiple_method)
    )
    context["advisor_multiple_transparency"] = appendix
    _apply_multiple_appendix_gates(context, show=show)
