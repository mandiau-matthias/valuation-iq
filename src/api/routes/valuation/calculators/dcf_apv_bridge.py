"""Adjusted Present Value bridge for explicit DCF tax-shield schedules."""

from __future__ import annotations

from src.config.local_reference_data import reference_table
from decimal import Decimal
from typing import Optional

from src.domain.dcf.apv_inputs import explicit_rate, finite_amount, unlevered_base_contract
from src.domain.dcf.manual_assumption_validation import require_positive_discount_rate
from src.utils.adaptive_input_helpers import (
    get_business_context,
    get_dcf_tax_shield_projection_overrides,
)
from src.utils.decimal_helpers import to_decimal

from .dcf_manual_overrides import discount_to_present

_APV_DOUBLE_COUNTING_GUARD = (
    "Debt tax shields may be added only to an explicitly unlevered FCFF base; "
    "a WACC-based DCF already embeds the financing tax benefit."
)
_APV_REQUIRED_INPUTS = [
    "fcff_projection_schedule",
    "discount_rate",
    "terminal_growth_or_exit_multiple",
    "explicit_debt_tax_shield_schedule",
    "explicit_unlevered_base_discount_rate",
    "discounting_convention",
]
_BENCHMARK_TOLERANCE = Decimal("0.000001")
_USER_BENCHMARK_EXPECTED = {k: Decimal(str(v)) for k, v in reference_table("dcf-apv").items()}


def _clean_string(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_apv_input_source(request: object) -> str:
    context = get_business_context(request)
    for key in (
        "apv_input_source",
        "dcf_tax_shield_source",
        "dcf_input_source",
        "financial_data_source",
        "_financial_data_source",
    ):
        value = _clean_string(context.get(key))
        if value:
            return value

    official_financials = getattr(request, "official_financials", None) or context.get(
        "official_financials"
    )
    if isinstance(official_financials, dict):
        provider = (
            _clean_string(official_financials.get("provider"))
            or _clean_string(official_financials.get("source"))
            or _clean_string(official_financials.get("data_source"))
        )
        if provider:
            return f"integration:{provider}"

    input_mode = _clean_string(getattr(request, "dcf_input_mode", None)) or _clean_string(
        context.get("dcf_input_mode")
    )
    if input_mode == "fcff_only":
        return "manual_fcff_schedule"

    return "explicit_request_payload"


def _resolve_apv_input_channel(source: str) -> str:
    normalized = source.lower().replace("-", "_").replace(" ", "_")
    if normalized in {"ai", "assistant", "ai_assistant"} or normalized.startswith("ai_"):
        return "ai_assistant"
    if normalized.startswith("integration:") or normalized in {
        "silverfin",
        "yuki",
        "exact",
        "quickbooks",
        "xero",
        "nbb",
        "kvk",
        "kbo",
    }:
        return "integration"
    if normalized in {"manual", "manual_fcff_schedule", "explicit_request_payload"}:
        return "manual"
    return "explicit_payload"


def _resolve_apv_input_mode(request: object) -> str:
    context = get_business_context(request)
    return (
        _clean_string(getattr(request, "dcf_input_mode", None))
        or _clean_string(context.get("dcf_input_mode"))
        or "dcf"
    )


def _resolve_apv_benchmark_reference(request: object) -> Optional[str]:
    context = get_business_context(request)
    explicit = _clean_string(
        context.get("apv_benchmark_reference")
        or context.get("dcf_benchmark_reference")
        or context.get("dcf_benchmark_case")
    )
    if explicit:
        return explicit
    return None


def _resolve_unlevered_base_contract(
    request: object,
    *,
    discount_rate: Decimal,
) -> tuple[bool, str, Optional[Decimal]]:
    return unlevered_base_contract(get_business_context(request), discount_rate)


def _benchmark_row(metric: str, actual: Optional[Decimal], expected: Decimal) -> dict[str, object]:
    if actual is None:
        return {
            "metric": metric,
            "expected": expected,
            "actual": None,
            "delta": None,
            "tolerance": _BENCHMARK_TOLERANCE,
            "passed": False,
        }
    delta = actual - expected
    return {
        "metric": metric,
        "expected": expected,
        "actual": actual,
        "delta": delta,
        "tolerance": _BENCHMARK_TOLERANCE,
        "passed": abs(delta) <= _BENCHMARK_TOLERANCE,
    }


def _build_apv_benchmark_reconciliation(
    *,
    benchmark_reference: Optional[str],
    dcf_enterprise_value: Decimal,
    apv_tax_shield_value: Decimal,
    apv_enterprise_value: Decimal,
    apv_equity_value: Optional[Decimal],
) -> Optional[dict[str, object]]:
    if benchmark_reference != "local_dcf_apv" or not _USER_BENCHMARK_EXPECTED:
        return None

    rows = [
        _benchmark_row(
            "dcf_enterprise_value",
            dcf_enterprise_value,
            _USER_BENCHMARK_EXPECTED["dcf_enterprise_value"],
        ),
        _benchmark_row(
            "apv_tax_shield_value",
            apv_tax_shield_value,
            _USER_BENCHMARK_EXPECTED["apv_tax_shield_value"],
        ),
        _benchmark_row(
            "apv_enterprise_value",
            apv_enterprise_value,
            _USER_BENCHMARK_EXPECTED["apv_enterprise_value"],
        ),
    ]
    if apv_equity_value is not None:
        rows.append(
            _benchmark_row(
                "apv_equity_value",
                apv_equity_value,
                _USER_BENCHMARK_EXPECTED["apv_equity_value"],
            )
        )
    matched = all(bool(row["passed"]) for row in rows)
    max_abs_delta = max(
        (abs(row["delta"]) for row in rows if isinstance(row.get("delta"), Decimal)),
        default=Decimal("0"),
    )
    return {
        "benchmark_reference": benchmark_reference,
        "benchmark_name": "User-supplied DCF reference",
        "status": "matched" if matched else "drift",
        "tolerance": _BENCHMARK_TOLERANCE,
        "max_abs_delta": max_abs_delta,
        "rows": rows,
    }


def calculate_apv_tax_shield_bridge(
    request: object,
    *,
    enterprise_value: Decimal,
    equity_value: Optional[Decimal] = None,
    discount_rate: Decimal,
    mid_year_discounting: bool = True,
) -> Optional[dict[str, object]]:
    """Bridge operating DCF value to APV when explicit tax shields are supplied.

    A tax-shield schedule is priced only when the request explicitly proves
    that the FCFF base was discounted at an unlevered required return. Under a
    normal after-tax WACC base the schedule remains disclosure-only, because
    adding it would double-count the financing tax benefit.
    """
    tax_shields = get_dcf_tax_shield_projection_overrides(request)
    if not tax_shields:
        return None

    discount_rate = finite_amount(discount_rate, "base discount rate")
    require_positive_discount_rate(discount_rate)
    shield_rate = explicit_rate(get_business_context(request), "apv_tax_shield_discount_rate")
    shield_rate_source = (
        "explicit_tax_shield_rate" if shield_rate is not None else "base_rate_assumption"
    )
    shield_rate = shield_rate if shield_rate is not None else discount_rate

    def _discount_period(index: int) -> Decimal:
        period = Decimal(str(index))
        return period - Decimal("0.5") if mid_year_discounting else period

    pv_tax_shields = [
        discount_to_present(value, shield_rate, _discount_period(index))
        for index, value in enumerate(tax_shields, start=1)
    ]
    tax_shield_value = sum(pv_tax_shields, Decimal("0"))
    base_enterprise = finite_amount(enterprise_value, "enterprise value")
    pricing_eligible, base_rate_kind, unlevered_rate = _resolve_unlevered_base_contract(
        request,
        discount_rate=to_decimal(discount_rate),
    )
    apv_enterprise = base_enterprise + tax_shield_value if pricing_eligible else base_enterprise
    discounting_convention = "mid_year" if mid_year_discounting else "year_end"

    base_equity: Optional[Decimal]
    apv_equity: Optional[Decimal]
    if equity_value is None:
        base_equity = None
        apv_equity = None
    else:
        base_equity = finite_amount(equity_value, "equity value")
        apv_equity = base_equity + tax_shield_value if pricing_eligible else base_equity

    benchmark_reference = _resolve_apv_benchmark_reference(request)
    is_customer_template_reconciliation = benchmark_reference == "local_dcf_apv"
    input_source = _resolve_apv_input_source(request)
    input_channel = _resolve_apv_input_channel(input_source)
    benchmark_reconciliation = (
        _build_apv_benchmark_reconciliation(
            benchmark_reference=benchmark_reference,
            dcf_enterprise_value=base_enterprise,
            apv_tax_shield_value=tax_shield_value,
            apv_enterprise_value=apv_enterprise,
            apv_equity_value=apv_equity,
        )
        if pricing_eligible
        else None
    )

    result = {
        "apv_contract_version": "apv_tax_shield.v2",
        "apv_tax_shield_projections": tax_shields,
        "apv_tax_shield_pv": pv_tax_shields,
        "apv_methodology": (
            "adjusted_present_value_tax_shield"
            if pricing_eligible
            else "tax_shield_disclosure_under_wacc"
        ),
        "apv_discount_rate": shield_rate,
        "apv_discounting_convention": discounting_convention,
        "apv_tax_shield_projections_5y": tax_shields[:5],
        "apv_tax_shield_pv_5y": pv_tax_shields[:5],
        "apv_tax_shield_value": tax_shield_value,
        "apv_tax_shield_pct_of_total": (
            (tax_shield_value / apv_enterprise) * Decimal("100")
            if pricing_eligible and apv_enterprise
            else Decimal("0")
        ),
        "dcf_enterprise_value_before_apv": base_enterprise,
        "dcf_equity_value_before_apv": base_equity,
        "apv_enterprise_value": apv_enterprise,
        "apv_equity_value": apv_equity,
        "apv_bridge_provenance": {
            "basis": "explicit_tax_shield_schedule",
            "benchmark_style": (
                "customer_template_apv"
                if is_customer_template_reconciliation
                else (
                    "governed_unlevered_apv"
                    if pricing_eligible
                    else "tax_shield_disclosure_under_wacc"
                )
            ),
            "customer_template_reconciliation": is_customer_template_reconciliation,
            "cash_flow_stream": "debt_tax_shields",
            "projection_count": len(tax_shields),
            "discounting_convention": discounting_convention,
            "discount_rate": shield_rate,
            "discount_rate_source": shield_rate_source,
            "base_discount_rate": discount_rate,
            "tax_utilization_verified": False,
            "financing_distress_costs_assessed": False,
            "input_mode": _resolve_apv_input_mode(request),
            "input_source": input_source,
            "input_channel": input_channel,
            "included_in_dcf_value": pricing_eligible,
            "pricing_status": (
                "priced_on_unlevered_base"
                if pricing_eligible
                else "disclosure_only_wacc_double_counting_guard"
            ),
            "base_discount_rate_kind": base_rate_kind or "wacc_after_tax",
            "explicit_unlevered_discount_rate": unlevered_rate,
            "separate_weighting_method": False,
            "double_counting_guard": _APV_DOUBLE_COUNTING_GUARD,
            "required_inputs": list(_APV_REQUIRED_INPUTS),
            **({"benchmark_reference": benchmark_reference} if benchmark_reference else {}),
            "value_before_bridge": base_enterprise,
            "bridge_adjustment": tax_shield_value if pricing_eligible else Decimal("0"),
            "value_after_bridge": apv_enterprise,
        },
    }
    if benchmark_reconciliation is not None:
        result["apv_benchmark_reconciliation"] = benchmark_reconciliation
    return result


def apply_apv_bridge_result(
    apv_bridge: dict[str, object],
    current_equity_value: Decimal,
    dcf_audit_trail: object,
) -> tuple[Decimal, Decimal]:
    """Apply APV bridge values and copy bridge evidence into the DCF audit trail."""
    if isinstance(dcf_audit_trail, dict):
        for key in ("apv_bridge_provenance", "apv_benchmark_reconciliation"):
            value = apv_bridge.get(key)
            if isinstance(value, dict):
                dcf_audit_trail[key] = value

    apv_equity_value = apv_bridge.get("apv_equity_value")
    return (
        to_decimal(apv_bridge["apv_enterprise_value"]),
        to_decimal(apv_equity_value) if apv_equity_value is not None else current_equity_value,
    )
