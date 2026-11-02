"""
Canonical Valuation Contract — Single Source of Truth

This module defines the authoritative contracts for valuation outputs that
flow from the calculation engine through to the report and PDF.  Every
consumer (report aggregator, PDF builder, frontend) MUST read weights and
method results through these helpers instead of inventing its own defaults.

Authoritative type locations (re-exported here for discoverability):
  - MethodResult, WeightedValuationResult, WeightedMethodContribution
        → src.api.schemas.stateless_api
  - WeightResult (DCF/multiples blend from HybridWeightCalculator)
        → src.domain.hybrid_types

Rules enforced by this module:
  1. Methodology weights (DCF vs multiples) are read from the response
     object that the calculation engine produced.  There is NO hidden
     70/30 default.  If weights cannot be determined, is_hybrid is False.
  2. Business-type calibration comes from the request payload
     (stateless mode) or from Titan enrichment.  DB-backed lookups in
     ValuationIQ are a cache/fallback, never the primary source.
  3. Per-method results use the MethodResult envelope.  The 10 canonical
     method keys are listed in CANONICAL_METHOD_KEYS.
"""

from collections.abc import Mapping
from typing import Optional, TypedDict

from src.api.schemas.method_details import (
    AdaptiveDetails,
    AdjustedNavDetails,
    ArrMultipleDetails,
    DcfDetails,
    EbitdaMultipleDetails,
    Fiscal4xDetails,
    MethodDetails,
    OmzetMultipleDetails,
    SdeMultipleDetails,
)
from src.api.schemas.stateless_api import (
    MethodResult,
    WeightedMethodContribution,
    WeightedValuationResult,
)
from src.domain.hybrid_types import WeightResult
from src.domain.method_keys import (
    CANONICAL_METHOD_KEYS,
    DISTINCT_METHOD_COUNT,
    METHOD_KEY_ALIASES,
    NON_COMBINABLE_METHOD_KEYS,
    REVENUE_METHOD_KEYS,
    normalize_method_key,
)
from src.utils.decimal_helpers import optional_decimal

__all__ = [
    "CANONICAL_METHOD_KEYS",
    "DISTINCT_METHOD_COUNT",
    "NON_COMBINABLE_METHOD_KEYS",
    "MethodResult",
    "MethodDetails",
    "AdaptiveDetails",
    "EbitdaMultipleDetails",
    "DcfDetails",
    "SdeMultipleDetails",
    "OmzetMultipleDetails",
    "ArrMultipleDetails",
    "AdjustedNavDetails",
    "Fiscal4xDetails",
    "WeightedMethodContribution",
    "WeightedValuationResult",
    "WeightResult",
    "METHOD_KEY_ALIASES",
    "REVENUE_METHOD_KEYS",
    "normalize_method_key",
    "resolve_effective_method_key",
    "method_key_matches",
    "is_sde_method_key",
    "is_asset_method_key",
    "methodology_indicates_sde",
    "extract_methodology_weights",
    "extract_methodology_weights_from_dict",
]

_safe_decimal = optional_decimal


class MethodologyWeights(TypedDict):
    is_hybrid: bool
    dcf_weight: float | None
    multiples_weight: float | None


def _empty_methodology_weights() -> MethodologyWeights:
    return {"is_hybrid": False, "dcf_weight": None, "multiples_weight": None}


def _methodology_weights_from_values(
    dcf_weight: object,
    multiples_weight: object,
) -> MethodologyWeights | None:
    dcf_w = _safe_decimal(dcf_weight)
    mult_w = _safe_decimal(multiples_weight)
    if dcf_w is None or mult_w is None:
        return None
    return {
        "is_hybrid": dcf_w > 0 and mult_w > 0,
        "dcf_weight": float(dcf_w),
        "multiples_weight": float(mult_w),
    }


def _methodology_weights_from_mapping(
    data: Mapping[str, object],
    *,
    dcf_key: str,
    multiples_key: str,
) -> MethodologyWeights | None:
    return _methodology_weights_from_values(data.get(dcf_key), data.get(multiples_key))


def _nested_methodology_weights_from_mapping(
    data: Mapping[str, object],
) -> MethodologyWeights | None:
    methodology_weights = data.get("methodology_weights")
    if not isinstance(methodology_weights, Mapping):
        return None
    return _methodology_weights_from_mapping(
        methodology_weights,
        dcf_key="dcf",
        multiples_key="multiples",
    )


def resolve_effective_method_key(*method_keys: object) -> str:
    """Return the first non-empty canonical method key from *method_keys*."""
    for method_key in method_keys:
        normalized = normalize_method_key(method_key)
        if normalized:
            return normalized
    return ""


def method_key_matches(method_key: object, *candidates: str) -> bool:
    """Return True when *method_key* resolves to any canonical candidate."""
    normalized = normalize_method_key(method_key)
    return any(normalized == normalize_method_key(candidate) for candidate in candidates)


def is_sde_method_key(method_key: object) -> bool:
    """Return True when *method_key* resolves to the canonical SDE key."""
    return method_key_matches(method_key, "sde_multiple")


def is_asset_method_key(method_key: object) -> bool:
    """Return True when *method_key* resolves to an asset-based method."""
    return method_key_matches(method_key, "adjusted_nav", "fiscal_4x", "liquidation_analysis")


def methodology_indicates_sde(methodology: object) -> bool:
    """Detect SDE methodology labels from canonical keys or human-readable labels."""
    if is_sde_method_key(methodology):
        return True
    return "SDE" in str(methodology or "").upper()


def extract_methodology_weights(
    response: object,
) -> MethodologyWeights:
    """Extract hybrid methodology weights from a ValuationResponse.

    Priority cascade (mirrors the calculation engine, never invents defaults):
      1. ``response.dcf_weight`` / ``response.multiples_weight``
         (set by the response builder from the HybridWeightCalculator output)
      2. ``response.detailed_results['methodology_weights']``
         (legacy path from business-intelligence modules)

    Returns a dict suitable for merging into the report template context::

        {
            "is_hybrid": bool,
            "dcf_weight": float | None,
            "multiples_weight": float | None,
        }

    When weights cannot be determined, or when either weight is zero,
    ``is_hybrid`` is ``False`` and the caller must not render a hybrid
    breakdown.  Weights are still returned (as floats) when present but
    non-hybrid, so callers can inspect them for diagnostics.

    **Pass-9 report copy:** full main-report templates use
    ``context["is_adaptive_only_path"]`` (from ``adaptive_report_gates``) for
    the Upswitch Adaptive *presentation lens* — not this dict's ``is_hybrid`` —
    so SME-default adaptive runs keep one narrative even when one engine
    weight is zero.  The ``is_hybrid`` flag here remains authoritative for
    numeric blend displays (e.g. "% multiples + % DCF" breakdown lines).
    """
    has_multiples = bool(getattr(response, "multiples_valuation", None))
    has_dcf = bool(getattr(response, "dcf_valuation", None))

    if not (has_multiples and has_dcf):
        return _empty_methodology_weights()

    direct_weights = _methodology_weights_from_values(
        getattr(response, "dcf_weight", None),
        getattr(response, "multiples_weight", None),
    )
    if direct_weights is not None:
        return direct_weights

    detailed = getattr(response, "detailed_results", None)
    if isinstance(detailed, Mapping):
        nested_weights = _nested_methodology_weights_from_mapping(detailed)
        if nested_weights is not None:
            return nested_weights

    return _empty_methodology_weights()


def extract_methodology_weights_from_dict(
    valuation_data: Mapping[str, object],
) -> MethodologyWeights:
    """Extract hybrid methodology weights from a Titan JSON dict.

    Used by the PDF endpoint when Titan sends ``valuation_data`` as a raw
    dict instead of a Pydantic model.  Same priority cascade as
    :func:`extract_methodology_weights` but operates on plain dicts.
    Pass-9 main-report presentation uses ``is_adaptive_only_path``, not
    this function's ``is_hybrid`` (see that function's docstring).
    """
    has_multiples = bool(valuation_data.get("multiples_valuation"))
    has_dcf = bool(valuation_data.get("dcf_valuation"))

    if not (has_multiples and has_dcf):
        return _empty_methodology_weights()

    direct_weights = _methodology_weights_from_mapping(
        valuation_data,
        dcf_key="dcf_weight",
        multiples_key="multiples_weight",
    )
    if direct_weights is not None:
        return direct_weights

    details = valuation_data.get("details")
    if isinstance(details, dict):
        detail_weights = _methodology_weights_from_mapping(
            details,
            dcf_key="dcf_weight",
            multiples_key="multiples_weight",
        )
        if detail_weights is not None:
            return detail_weights

    for candidate in (valuation_data, details or {}):
        if isinstance(candidate, dict):
            nested_weights = _nested_methodology_weights_from_mapping(candidate)
            if nested_weights is not None:
                return nested_weights

    return _empty_methodology_weights()
