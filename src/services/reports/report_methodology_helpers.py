"""Report methodology classification helpers.

Keep these policy predicates outside the main report aggregator so DCF,
asset, yield, and hybrid gates use one shared interpretation.
"""

from __future__ import annotations

import re
from decimal import Decimal

from src.domain.valuation_contract import extract_methodology_weights
from src.services.reports.protocol_adapter import _attr
from src.utils.decimal_helpers import safe_decimal_or_zero


def is_hybrid_methodology(response: object) -> bool:
    """True only when both valuation legs and weights are present."""
    return extract_methodology_weights(response).get("is_hybrid") is True


def _executed_methodology_token(response: object) -> str:
    """Read methodology_substitution.executed_methodology (dict or model)."""
    msub = _attr(response, "methodology_substitution", None)
    if isinstance(msub, dict):
        return str(msub.get("executed_methodology") or "")
    if msub is not None:
        return str(_attr(msub, "executed_methodology", "") or "")
    return ""


def normalised_methodology(response: object) -> str:
    """Snake-case normalised methodology string for report gating.

    Falls back to ``methodology_substitution.executed_methodology`` when the
    top-level ``methodology`` field is unset. The live ValuationOrchestrator
    leaves ``response.methodology`` None for asset-routed cases and signals the
    executed method via the substitution payload; without this fallback the
    holding / real-estate dossiers were classified as multiples (0,00× multiple,
    "EV = EBITDA × Multiple" framing) instead of asset/NAV.
    """
    raw = str(_attr(response, "methodology", "") or "").strip().lower()
    if not raw:
        raw = _executed_methodology_token(response).strip().lower()
    return raw.replace("-", "_").replace(" ", "_")


def is_asset_methodology(response: object) -> bool:
    """Detect asset-based / NAV-anchored reports.

    Accepts both the canonical executed token (``ASSET_BASED`` →
    ``asset_based``) and the human-friendly display label the response_builder
    may emit (``Asset-Based Valuation (Adjusted NAV)`` → ``asset_based_…``), so
    the gate is robust to whichever form reaches it.
    """
    norm = normalised_methodology(response)
    if norm in {
        "asset",
        "asset_based",
        "asset_based_valuation",
        "adjusted_nav",
        "nav",
        "substantiewaardering",
    }:
        return True
    return norm.startswith("asset_based") or "adjusted_nav" in norm


def is_yield_methodology(response: object) -> bool:
    """Detect real-estate yield-based reports.

    Accepts the canonical executed token (``REAL_ESTATE_YIELD`` →
    ``real_estate_yield``) as well as the display label
    (``Real Estate Yield (Income Capitalisation)`` →
    ``real_estate_yield_(income_capitalisation)``).
    """
    norm = normalised_methodology(response)
    if norm in {
        "yield",
        "real_estate_yield",
        "vastgoed_yield",
    }:
        return True
    return norm.startswith("real_estate_yield") or "income_capitalisation" in norm


def is_asset_anchored_methodology(response: object) -> bool:
    """True when the balance sheet, not P&L multiples, carries substance."""
    return is_asset_methodology(response) or is_yield_methodology(response)


def is_dcf_only_methodology(response: object) -> bool:
    """Detect true DCF-only reports without substring false positives."""
    if is_hybrid_methodology(response):
        return False

    raw_methodology = str(_attr(response, "methodology", "") or "").strip()
    normalized = raw_methodology.lower()
    snake = normalized.replace("-", "_").replace(" ", "_")
    explicit_dcf_alias = (
        snake in {"dcf", "dcf_analysis", "discounted_cash_flow"}
        or bool(re.fullmatch(r"discounted cash flow(?:\s*\(dcf\))?", normalized))
        or bool(re.fullmatch(r"discounted_cash_flow_?\(?dcf\)?", snake))
    )
    if explicit_dcf_alias:
        return True

    dcf_weight = safe_decimal_or_zero(_attr(response, "dcf_weight", 0))
    multiples_weight = safe_decimal_or_zero(_attr(response, "multiples_weight", 0))
    return (
        _attr(response, "dcf_valuation", None) is not None
        and dcf_weight > Decimal("0")
        and multiples_weight == Decimal("0")
    )
