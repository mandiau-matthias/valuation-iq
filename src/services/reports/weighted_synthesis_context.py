"""Weighted-valuation synthesis context builder.

This module owns the report-context contract for custom user-weighted blends
such as DCF + EBITDA multiple. Keeping it out of the main aggregator makes the
report page easier to test and gives the report manifest a stable input shape.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Dict, List, Optional, Tuple, TypeAlias

from src.services.infrastructure.translations import (
    ReportTranslations,
    build_synthesis_formula_display,
    normalize_report_locale,
    resolve_synthesis_method_label,
)
from src.utils.decimal_helpers import safe_float

JsonMap: TypeAlias = Dict[str, object]
ContributionRows: TypeAlias = List[JsonMap]


def _dict_or_none(value: object) -> Optional[JsonMap]:
    if not isinstance(value, dict):
        return None
    return dict(value)


def unwrap_weighted_synthesis(weighted_valuation: object) -> Optional[JsonMap]:
    """Normalize ``weighted_valuation`` to a plain dict.

    Handles plain dicts, the aggregator's ``DictWrapper`` shape, Pydantic
    models, and dict-like objects without importing the 9k-line aggregator.
    """

    if weighted_valuation is None:
        return None
    if isinstance(weighted_valuation, dict):
        return dict(weighted_valuation)
    data = getattr(weighted_valuation, "_data", None)
    if isinstance(data, dict):
        return dict(data)
    if hasattr(weighted_valuation, "model_dump"):
        return _dict_or_none(weighted_valuation.model_dump())
    if hasattr(weighted_valuation, "get"):
        return {
            "blended_equity_value": weighted_valuation.get("blended_equity_value"),
            "valuation_range_low": weighted_valuation.get("valuation_range_low"),
            "valuation_range_high": weighted_valuation.get("valuation_range_high"),
            "enterprise_value_low": weighted_valuation.get("enterprise_value_low"),
            "enterprise_value_mid": weighted_valuation.get("enterprise_value_mid"),
            "enterprise_value_high": weighted_valuation.get("enterprise_value_high"),
            "value_basis": weighted_valuation.get("value_basis", "equity_value"),
            "contributions": weighted_valuation.get("contributions", []),
            "user_justification": weighted_valuation.get("user_justification"),
        }
    return None


def _normalize_contribution(contribution: object, t: ReportTranslations) -> JsonMap:
    if isinstance(contribution, dict):
        normalized = dict(contribution)
        normalized["label"] = resolve_synthesis_method_label(
            normalized.get("method_key"), normalized.get("label"), t
        )
        return _decorate_bridge_contribution(normalized, t)

    if hasattr(contribution, "get"):
        method_key = contribution.get("method_key")
        label = contribution.get("label")
        normalized = {
            "method_key": method_key,
            "label": resolve_synthesis_method_label(method_key, label, t),
            "equity_value": contribution.get("equity_value"),
            "equity_value_low": contribution.get("equity_value_low"),
            "equity_value_high": contribution.get("equity_value_high"),
            "enterprise_value": contribution.get("enterprise_value"),
            "enterprise_value_low": contribution.get("enterprise_value_low"),
            "enterprise_value_high": contribution.get("enterprise_value_high"),
            "weight": contribution.get("weight"),
            "weighted_contribution": contribution.get("weighted_contribution"),
            "value_basis": contribution.get("value_basis"),
            "value_before_bridge": contribution.get("value_before_bridge"),
            "bridge_adjustment": contribution.get("bridge_adjustment"),
            "bridge_adjustment_pct_of_total": contribution.get("bridge_adjustment_pct_of_total"),
            "discounting_convention": contribution.get("discounting_convention"),
            "bridge_provenance": contribution.get("bridge_provenance"),
            "benchmark_reconciliation": contribution.get("benchmark_reconciliation"),
        }
        return _decorate_bridge_contribution(normalized, t)

    method_key = getattr(contribution, "method_key", None)
    label = getattr(contribution, "label", None)
    normalized = {
        "method_key": method_key,
        "label": resolve_synthesis_method_label(method_key, label, t),
        "equity_value": getattr(contribution, "equity_value", None),
        "equity_value_low": getattr(contribution, "equity_value_low", None),
        "equity_value_high": getattr(contribution, "equity_value_high", None),
        "enterprise_value": getattr(contribution, "enterprise_value", None),
        "enterprise_value_low": getattr(contribution, "enterprise_value_low", None),
        "enterprise_value_high": getattr(contribution, "enterprise_value_high", None),
        "weight": getattr(contribution, "weight", None),
        "weighted_contribution": getattr(contribution, "weighted_contribution", None),
        "value_basis": getattr(contribution, "value_basis", None),
        "value_before_bridge": getattr(contribution, "value_before_bridge", None),
        "bridge_adjustment": getattr(contribution, "bridge_adjustment", None),
        "bridge_adjustment_pct_of_total": getattr(
            contribution, "bridge_adjustment_pct_of_total", None
        ),
        "discounting_convention": getattr(contribution, "discounting_convention", None),
        "bridge_provenance": getattr(contribution, "bridge_provenance", None),
        "benchmark_reconciliation": getattr(contribution, "benchmark_reconciliation", None),
    }
    return _decorate_bridge_contribution(normalized, t)


def _is_customer_template_apv(contribution: JsonMap) -> bool:
    provenance = contribution.get("bridge_provenance")
    if isinstance(provenance, dict):
        if provenance.get("customer_template_reconciliation") is True:
            return True
        if provenance.get("benchmark_style") == "customer_template_apv":
            return True
    benchmark_reconciliation = contribution.get("benchmark_reconciliation")
    if isinstance(benchmark_reconciliation, dict):
        reference = str(benchmark_reconciliation.get("benchmark_reference") or "").strip()
        if reference == "local_dcf_apv":
            return True
    return False


def _decorate_bridge_contribution(
    contribution: JsonMap,
    t: ReportTranslations,
) -> JsonMap:
    if contribution.get("method_key") == "dcf" and contribution.get("value_basis") == "apv":
        contribution["value_basis_label"] = t.synthesis_apv_value_basis
        contribution["bridge_adjustment_label"] = t.synthesis_apv_bridge_label
        contribution["methodology_note"] = (
            t.synthesis_apv_bridge_note
            if _is_customer_template_apv(contribution)
            else t.synthesis_apv_bridge_generic_note
        )
    elif contribution.get("value_basis") == "net_engine":
        contribution["value_basis_label"] = t.synthesis_net_engine_value_basis
        contribution["methodology_note"] = t.synthesis_net_engine_note
    elif contribution.get("value_basis") == "enterprise_value":
        contribution["value_basis_label"] = getattr(t, "cover_ev_label", "Ondernemingswaarde")
    return contribution


def _contribution_items(contributions: object) -> list[object]:
    data = getattr(contributions, "_data", None)
    if isinstance(data, dict):
        return list(data.values())
    if isinstance(contributions, dict):
        return list(contributions.values())
    if contributions is None:
        return []
    if isinstance(contributions, Iterable) and not isinstance(contributions, (str, bytes)):
        return list(contributions)
    return []


def normalize_synthesis_contributions(
    contributions: object,
    t: ReportTranslations,
) -> ContributionRows:
    """Return localized contribution rows for the synthesis table."""
    return [_normalize_contribution(c, t) for c in _contribution_items(contributions)]


def synthesis_value_bounds_from_contributions(
    contributions: ContributionRows,
    blended_value: Optional[float],
    *,
    value_basis: str = "equity_value",
) -> Tuple[Optional[float], Optional[float]]:
    """Min/max finite positive selected-basis values across synthesis rows.

    The blended midpoint is included when valid so the displayed range always
    contains the conclusion shown in the synthesis section.
    """

    vals: List[float] = []
    value_field = "enterprise_value" if value_basis == "enterprise_value" else "equity_value"
    for contribution in contributions:
        value = safe_float(contribution.get(value_field))
        if value > 0 and math.isfinite(value):
            vals.append(value)
    if len(vals) < 2:
        return None, None

    low = min(vals)
    high = max(vals)
    if blended_value is not None:
        bv = safe_float(blended_value)
        if bv > 0 and math.isfinite(bv):
            low = min(low, bv)
            high = max(high, bv)

    if not math.isfinite(low) or not math.isfinite(high) or low >= high:
        return None, None
    return low, high


def format_eur_compact(value: object) -> str:
    """Format a numeric value as a compact EUR string, e.g. ``2.150.000``."""

    number = safe_float(value)
    return f"{number:,.0f}".replace(",", ".")


def format_synthesis_method_list(labels: List[str], locale: str) -> str:
    if not labels:
        return ""
    loc = normalize_report_locale(locale)
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        joiner = " en " if loc == "nl" else " and "
        return f"{labels[0]}{joiner}{labels[1]}"
    joiner = ", en " if loc == "nl" else ", and "
    return ", ".join(labels[:-1]) + joiner + labels[-1]


def _weighted_synthesis_formula(
    *,
    data: JsonMap,
    contributions: object,
    blended_value: float,
    value_basis: str,
    t: ReportTranslations,
) -> str:
    pre_common = (
        None
        if value_basis == "enterprise_value"
        else data.get("pre_common_bridge_blended_equity_value")
    )
    formula_basis = pre_common if pre_common is not None else blended_value
    formula = str(
        build_synthesis_formula_display(
            _contribution_items(contributions),
            formula_basis,
            t,
            format_eur_compact,
            value_field=(
                "enterprise_value" if value_basis == "enterprise_value" else "equity_value"
            ),
        )
    )
    if value_basis == "enterprise_value":
        return formula
    adjustments = [
        safe_float(data.get("common_bridge_adjustment")),
        safe_float(data.get("shareholder_transaction_adjustment")),
    ]
    adjustments = [amount for amount in adjustments if abs(amount) > 0.005]
    if not adjustments:
        return formula
    for amount in adjustments:
        operator = "+" if amount >= 0 else "−"
        formula += f" {operator} €{format_eur_compact(abs(amount))}"
    return f"{formula} = €{format_eur_compact(blended_value)}"


def build_weighted_synthesis_presentation(
    *,
    contributions: Sequence[object],
    blended_value: object,
    locale: str,
) -> JsonMap:
    normalized: list[tuple[str, float]] = []
    for contribution in contributions:
        c_get = (
            contribution.get
            if isinstance(contribution, dict)
            else (lambda key, default=None: getattr(contribution, key, default))
        )
        label = str(c_get("label", c_get("method_key", "")) or "").strip()
        weight = safe_float(c_get("weight", 0) or 0)
        if not label or weight <= 0:
            continue
        normalized.append((label, weight))

    labels = [label for label, _weight in normalized]
    loc = normalize_report_locale(locale)
    method_list = format_synthesis_method_list(labels, locale)
    label_count = len(labels)
    count_suffix = (
        "methode"
        if loc == "nl" and label_count == 1
        else "methodes" if loc == "nl" else "method" if label_count == 1 else "methods"
    )
    parts = [f"{round(weight * 100):.0f}% {label}" for label, weight in normalized]
    compact_weights = " / ".join(f"{round(weight * 100):.0f}%" for _label, weight in normalized)

    if loc == "nl":
        methodology = f"gewogen synthese van {method_list}" if method_list else "gewogen synthese"
        badge = "Waarderingssynthese"
    else:
        methodology = (
            f"weighted synthesis of {method_list}" if method_list else "weighted synthesis"
        )
        badge = "Valuation synthesis"

    return {
        "synthesis_badge_label": badge,
        "synthesis_methodology_label": methodology,
        "synthesis_method_list": method_list,
        "synthesis_weight_summary": (
            " + ".join(parts) + f" = €{format_eur_compact(blended_value)}" if parts else None
        ),
        "synthesis_weight_compact": compact_weights or None,
        "synthesis_method_count_label": f"{label_count} {count_suffix}",
    }


def empty_weighted_synthesis_context() -> JsonMap:
    return {
        "has_weighted_synthesis": False,
        "synthesis_blended_value": None,
        "synthesis_justification": None,
        "synthesis_contributions": [],
        "synthesis_formula_display": None,
        "synthesis_badge_label": None,
        "synthesis_methodology_label": None,
        "synthesis_method_list": None,
        "synthesis_weight_summary": None,
        "synthesis_weight_compact": None,
        "synthesis_method_count_label": None,
        "synthesis_valuation_low": None,
        "synthesis_valuation_high": None,
        "synthesis_value_basis": None,
        "synthesis_equity_value_low": None,
        "synthesis_equity_value_mid": None,
        "synthesis_equity_value_high": None,
    }


def _positive_or_none(value: object) -> Optional[float]:
    number = float(safe_float(value))
    if number > 0 and math.isfinite(number):
        return number
    return None


def _first_present(context: JsonMap, *keys: str) -> object:
    for key in keys:
        if key in context and context[key] is not None:
            return context[key]
    return None


def _equity_to_enterprise_value(context: JsonMap, equity_value: float) -> float:
    net_debt = float(safe_float(context.get("net_debt")))
    nwc_adjustment = float(
        safe_float(_first_present(context, "nwc_adjustment", "nwc_surplus_deficit"))
    )
    tax_latency_net_impact = float(safe_float(context.get("tax_latency_net_impact")))
    return equity_value + net_debt - nwc_adjustment - tax_latency_net_impact


def promote_weighted_synthesis_headline_context(context: JsonMap) -> None:
    """Make weighted synthesis the canonical report headline when present.

    Promote either the legacy equity-weighted conclusion or an EV-first blend
    without applying the EV-to-equity bridge a second time.
    """

    if not context.get("has_weighted_synthesis"):
        return

    if context.get("dcf_ineligible_scenario"):
        # Guardrail: the headline is pinned to the market (multiples) leg because
        # the blended DCF was engine-ineligible. Do NOT promote the blend over it —
        # the synthesis renders as a clearly-labelled advisor scenario instead.
        return

    selected_value = _positive_or_none(context.get("synthesis_blended_value"))
    if selected_value is None:
        return

    context.setdefault(
        "pre_synthesis_equity_value",
        _first_present(context, "equity_value", "equity_value_mid", "valuation"),
    )
    context.setdefault("pre_synthesis_enterprise_value", context.get("valuation"))
    context.setdefault(
        "pre_synthesis_recommended_asking_price",
        context.get("recommended_asking_price"),
    )

    enterprise_primary = context.get("synthesis_value_basis") == "enterprise_value"
    enterprise_value: float
    equity_value: float
    if enterprise_primary:
        enterprise_value = selected_value
        selected_equity = _positive_or_none(context.get("synthesis_equity_value_mid"))
        if selected_equity is None:
            return
        equity_value = selected_equity
    else:
        equity_value = selected_value
        selected_enterprise = _positive_or_none(context.get("synthesis_enterprise_value_mid"))
        enterprise_value = (
            selected_enterprise
            if selected_enterprise is not None
            else _equity_to_enterprise_value(context, equity_value)
        )
    context["equity_value"] = equity_value
    context["equity_value_mid"] = equity_value
    context["valuation"] = enterprise_value
    context["enterprise_value_mid"] = enterprise_value
    if (
        context.get("methodology_used") != "WEIGHTED_SYNTHESIS"
        or _positive_or_none(context.get("recommended_asking_price")) is None
    ):
        context["recommended_asking_price"] = equity_value
    context["ev_band_source"] = "weighted_synthesis"
    context["ev_sourced_from_engine_equity"] = True
    context["supports_metric_to_ev_bridge"] = False

    selected_low = _positive_or_none(context.get("synthesis_valuation_low"))
    selected_high = _positive_or_none(context.get("synthesis_valuation_high"))
    if selected_low is not None and selected_high is not None and selected_low < selected_high:
        enterprise_low: float
        enterprise_high: float
        equity_low: Optional[float]
        equity_high: Optional[float]
        if enterprise_primary:
            enterprise_low = selected_low
            enterprise_high = selected_high
            equity_low = _positive_or_none(context.get("synthesis_equity_value_low"))
            equity_high = _positive_or_none(context.get("synthesis_equity_value_high"))
        else:
            equity_low = selected_low
            equity_high = selected_high
            selected_enterprise_low = _positive_or_none(
                context.get("synthesis_enterprise_value_low")
            )
            selected_enterprise_high = _positive_or_none(
                context.get("synthesis_enterprise_value_high")
            )
            enterprise_low = (
                selected_enterprise_low
                if selected_enterprise_low is not None
                else _equity_to_enterprise_value(context, selected_low)
            )
            enterprise_high = (
                selected_enterprise_high
                if selected_enterprise_high is not None
                else _equity_to_enterprise_value(context, selected_high)
            )
        if equity_low is not None and equity_high is not None:
            context["equity_value_low"] = equity_low
            context["equity_value_high"] = equity_high
            context["equity_value_band_is_meaningful"] = equity_low < equity_high
        context["valuation_low"] = enterprise_low
        context["valuation_high"] = enterprise_high
        context["enterprise_value_low"] = context["valuation_low"]
        context["enterprise_value_high"] = context["valuation_high"]
        context["valuation_band_is_meaningful"] = True


def build_weighted_synthesis_context(
    weighted_valuation: object,
    *,
    t: ReportTranslations,
    locale: str,
) -> JsonMap:
    """Build template context for the weighted synthesis page."""

    data = unwrap_weighted_synthesis(weighted_valuation)
    value_basis = str(data.get("value_basis") or "equity_value") if data is not None else ""
    blended_equity_value = safe_float(data.get("blended_equity_value")) if data is not None else 0.0
    blended_value = (
        safe_float(data.get("enterprise_value_mid"))
        if data is not None and value_basis == "enterprise_value"
        else blended_equity_value
    )
    if data is None or blended_value <= 0:
        return empty_weighted_synthesis_context()

    raw_contributions = data.get("contributions", [])
    localized_contributions = normalize_synthesis_contributions(raw_contributions, t)
    value_low = _positive_or_none(
        data.get("enterprise_value_low")
        if value_basis == "enterprise_value"
        else data.get("valuation_range_low")
    )
    value_high = _positive_or_none(
        data.get("enterprise_value_high")
        if value_basis == "enterprise_value"
        else data.get("valuation_range_high")
    )
    if value_low is None or value_high is None or value_low > value_high:
        value_low, value_high = synthesis_value_bounds_from_contributions(
            localized_contributions,
            blended_value,
            value_basis=value_basis,
        )

    context: JsonMap = {
        "has_weighted_synthesis": True,
        "synthesis_blended_value": blended_value,
        "synthesis_justification": data.get("user_justification"),
        "synthesis_contributions": localized_contributions,
        "synthesis_valuation_low": value_low,
        "synthesis_valuation_high": value_high,
        "synthesis_value_basis": value_basis,
        "synthesis_equity_value_low": data.get("valuation_range_low"),
        "synthesis_equity_value_mid": data.get("blended_equity_value"),
        "synthesis_equity_value_high": data.get("valuation_range_high"),
        "synthesis_enterprise_value_low": data.get("enterprise_value_low"),
        "synthesis_enterprise_value_mid": data.get("enterprise_value_mid"),
        "synthesis_enterprise_value_high": data.get("enterprise_value_high"),
        "synthesis_common_bridge_adjustment": data.get("common_bridge_adjustment"),
        "synthesis_pre_shareholder_transaction_value": data.get(
            "pre_shareholder_transaction_blended_equity_value"
        ),
        "synthesis_shareholder_transaction_adjustment": data.get(
            "shareholder_transaction_adjustment"
        ),
        "synthesis_formula_display": _weighted_synthesis_formula(
            data=data,
            contributions=raw_contributions,
            blended_value=blended_value,
            value_basis=value_basis,
            t=t,
        ),
    }
    context.update(
        build_weighted_synthesis_presentation(
            contributions=localized_contributions,
            blended_value=blended_value,
            locale=locale,
        )
    )
    return context
