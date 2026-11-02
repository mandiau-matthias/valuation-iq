"""Helpers that build the liquidation-specific report context.

Sibling to ``startup_report_context.py``. When the active method is
``liquidation_analysis`` the master report template uses dedicated
liquidation pages instead of the SME going-concern pages. This module
turns the omni-calc ``MethodResult.details`` payload into the flat
``liquidation_report`` block the templates consume.

Design parallels with startup
-----------------------------
- Bilingual via a small explicit translation dict (no Babel for a
  handful of strings).
- ``build_liquidation_context()`` returns ``None`` when the method is
  not ``liquidation_analysis`` or did not run successfully — the master
  template then falls back to the SME flow unchanged.
- All locale-specific copy lives in :data:`LIQUIDATION_REPORT_TRANSLATIONS`;
  templates read ``liquidation_report.t.<key>`` and never carry
  inline locale strings.

Why this is its own track
-------------------------
Liquidation is a downside scenario — the floor an owner could realistically
recover if the business cannot be sold as a going concern. Rendering it
inside the SME multi-method synthesis would be an apples-to-oranges error
(asset-recovery floor competing with multiples / DCF). A dedicated report
keeps the narrative honest: orderly + forced scenarios side-by-side,
book-equity reference, scope_note explicitly flagging that the MVP
subtracts liabilities at book value (no insolvency priority waterfall).
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import TypeAlias, cast

from src.services.reports.liquidation_report_enrichment import (
    enrich_liquidation_detail_blocks,
    translate_liquidation_report_text,
)

# ``CASCADE_TIER_LABELS_EN`` is re-exported here for liquidation report consumers/tests.
from src.services.reports.liquidation_report_translations import (  # noqa: F401
    CASCADE_TIER_LABELS_EN,
    LIQUIDATION_REPORT_TRANSLATIONS,
)

JsonMap: TypeAlias = dict[str, object]


def _pin_float_band(
    low: float | None, mid: float | None, high: float | None
) -> tuple[float | None, float | None, float | None]:
    """Display a coherent supplied band; never repair or reprice its endpoints."""
    if mid is None or low is None or high is None or not 0 <= low <= mid <= high:
        return None, mid, None
    return low, mid, high


def _t(loc: str, key: str) -> str:
    """Resolve ``key`` for ``loc`` with NL fallback and `[key]` placeholder."""
    return translate_liquidation_report_text(loc, key)


def _coerce_dict(obj: object) -> JsonMap:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return cast(JsonMap, obj)
    if isinstance(obj, Mapping):
        return cast(JsonMap, dict(obj))
    # DictWrapper (main_report_data_aggregator) is a protocol-bridge whose
    # __getattr__ returns None for missing keys, so hasattr(obj, "model_dump")
    # is True with a non-callable value. Prefer the underlying dict.
    underlying = getattr(obj, "_data", None)
    if isinstance(underlying, dict):
        return cast(JsonMap, underlying)
    md = getattr(obj, "model_dump", None)
    if callable(md):
        dumped = md(mode="json")
        if isinstance(dumped, dict):
            return cast(JsonMap, dumped)
    return {}


def _safe_float(value: object) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
        return parsed if isfinite(parsed) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _extract_liquidation_method(valuation_results: object) -> JsonMap | None:
    """Return the ``liquidation_analysis`` MethodResult as a plain dict."""
    if not valuation_results:
        return None
    candidate: object | None = None
    if isinstance(valuation_results, Mapping):
        candidate = valuation_results.get("liquidation_analysis")
    else:
        candidate = getattr(valuation_results, "liquidation_analysis", None)
        getter = getattr(valuation_results, "get", None)
        if candidate is None and callable(getter):
            candidate = getter("liquidation_analysis")
    if candidate is None:
        return None
    return _coerce_dict(candidate)


def _liquidation_locale(locale: str) -> str:
    return "en" if str(locale or "").strip().lower().startswith("en") else "nl"


def _liquidation_details(method: JsonMap) -> tuple[JsonMap, JsonMap, JsonMap]:
    details = _coerce_dict(method.get("details"))
    return details, _coerce_dict(details.get("orderly")), _coerce_dict(details.get("forced"))


def _liquidation_headline(
    *,
    method: JsonMap,
    orderly: JsonMap,
) -> tuple[float | None, float | None, float | None]:
    headline_equity = _safe_float(method.get("value"))
    if headline_equity is None:
        headline_equity = _safe_float(orderly.get("equity_value"))
    # Use bounds from the authoritative method when supplied. Only borrow
    # scenario bounds when the headline is exactly that scenario's midpoint.
    if "value_low" in method or "value_high" in method:
        low = _safe_float(method.get("value_low"))
        high = _safe_float(method.get("value_high"))
    elif headline_equity == _safe_float(orderly.get("equity_value")):
        low = _safe_float(orderly.get("value_low"))
        high = _safe_float(orderly.get("value_high"))
    else:
        low = high = None
    return _pin_float_band(low, headline_equity, high)


def _liquidation_translation_table(locale: str) -> JsonMap:
    return {key: _t(locale, key) for key in LIQUIDATION_REPORT_TRANSLATIONS}


def _liquidation_header_context(
    *,
    loc: str,
    method: JsonMap,
    details: JsonMap,
    orderly: JsonMap,
    forced: JsonMap,
    headline_low: float | None,
    headline_equity: float | None,
    headline_high: float | None,
) -> JsonMap:
    return {
        "locale": loc,
        "label": method.get("label") or "Liquidatiewaarde",
        "headline_equity": headline_equity,
        "value_low": headline_low,
        "value_high": headline_high,
        "orderly": orderly,
        "forced": forced,
        "book_equity": _safe_float(details.get("book_equity")),
        "ownership_multiplier": _safe_float(details.get("ownership_multiplier")) or 1.0,
        "would_be_insolvent_orderly": bool(orderly.get("would_be_insolvent")),
        "would_be_insolvent_forced": bool(forced.get("would_be_insolvent")),
    }


def _liquidation_detail_context(detail_blocks: JsonMap, details: JsonMap) -> JsonMap:
    return {
        "premise": detail_blocks.get("premise"),
        "distress": detail_blocks.get("distress"),
        "asset_schedule": detail_blocks.get("asset_schedule"),
        "expected_equity_value": None,
        "going_concern_proxy_equity": (
            _safe_float(details.get("going_concern_proxy_equity"))
            if details.get("going_concern_comparison_status")
            == "caller_supplied_equity_requires_review"
            else None
        ),
        "priority_cascade_orderly": detail_blocks.get("priority_cascade_orderly"),
        "priority_cascade_forced": detail_blocks.get("priority_cascade_forced"),
        "tax_leakage_orderly": detail_blocks.get("tax_leakage_orderly"),
        "tax_leakage_forced": detail_blocks.get("tax_leakage_forced"),
        "wind_down_orderly": detail_blocks.get("wind_down_orderly"),
        "wind_down_forced": detail_blocks.get("wind_down_forced"),
        "disposal_schedule_pv_orderly": detail_blocks.get("disposal_schedule_pv_orderly"),
        "disposal_schedule_pv_forced": detail_blocks.get("disposal_schedule_pv_forced"),
        "sensitivity": detail_blocks.get("sensitivity"),
        "premise_reconciliation": detail_blocks.get("premise_reconciliation"),
        "disclosure": detail_blocks.get("disclosure"),
        "statement_of_affairs": detail_blocks.get("statement_of_affairs"),
        "replacement_cost": detail_blocks.get("replacement_cost"),
        "audit_trail": detail_blocks.get("audit_trail"),
        "sufficiency_memo_orderly": detail_blocks.get("sufficiency_memo_orderly"),
        "sufficiency_memo_forced": detail_blocks.get("sufficiency_memo_forced"),
        "creditor_letters_orderly": detail_blocks.get("creditor_letters_orderly"),
        "creditor_letters_forced": detail_blocks.get("creditor_letters_forced"),
        "strategic_buyer_scenarios": detail_blocks.get("strategic_buyer_scenarios"),
    }


def _liquidation_shareholder_context(details: JsonMap) -> JsonMap:
    return {
        "net_equity_to_shareholders_orderly": _safe_float(
            details.get("net_equity_to_shareholders_orderly")
        ),
        "net_equity_to_shareholders_forced": _safe_float(
            details.get("net_equity_to_shareholders_forced")
        ),
        "sources": list(details.get("sources") or []),
        "scope_note": details.get("scope_note") or "",
    }


def build_liquidation_context(
    *,
    selected_method: str | None,
    valuation_results: object,
    locale: str = "nl",
    country_code: str | None = None,
) -> JsonMap | None:
    """Build the ``liquidation_report`` context block consumed by the templates.

    Returns ``None`` when the active method is not ``liquidation_analysis``
    or when the engine did not produce a usable scenario block — the
    master template then falls back to the SME flow unchanged. Same
    contract as :func:`build_startup_context`.
    """
    if str(selected_method or "").strip().lower() != "liquidation_analysis":
        return None
    if country_code is not None and str(country_code).strip().upper() != "BE":
        # France and Ireland deliberately remain unsupported until their
        # priority, tax-leakage and jurisdiction-disclosure implementations
        # receive qualified review. Never render a Belgian waterfall merely
        # because a stale/malformed method payload happens to be present.
        return None

    loc = _liquidation_locale(locale)
    method = _extract_liquidation_method(valuation_results)
    if not method or not method.get("available"):
        return None

    details, orderly, forced = _liquidation_details(method)

    # If both scenarios are missing the payload is unusable — fall back
    # to SME flow rather than render a blank report.
    if not orderly and not forced:
        return None

    detail_blocks = enrich_liquidation_detail_blocks(details, loc)
    _hdl_low, headline_equity, _hdl_high = _liquidation_headline(
        method=method,
        orderly=orderly,
    )

    return {
        **_liquidation_header_context(
            loc=loc,
            method=method,
            details=details,
            orderly=orderly,
            forced=forced,
            headline_low=_hdl_low,
            headline_equity=headline_equity,
            headline_high=_hdl_high,
        ),
        **_liquidation_detail_context(detail_blocks, details),
        **_liquidation_shareholder_context(details),
        "t": _liquidation_translation_table(loc),
    }
