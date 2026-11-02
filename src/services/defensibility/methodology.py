"""Methodology detection — single source of truth across the gate.

Different valuation methodologies have different confidence frameworks. This
detector lets the rest of the defensibility package make smart skip/defer
decisions instead of one-size-fits-all classification:

  - **STARTUP**: pre-revenue / pre-traction. Berkus + Scorecard + VC method
    have their own confidence weighting (founder pedigree, traction, exit
    story). The years-of-data classifier would always say PRELIMINARY for
    these — defer to the method.

  - **ASSET**: NAV / book-value methodology. Balance sheet IS the input;
    the EBITDA-margin / years-of-data heuristics don't apply. Skip the
    asking-price buffer (asset value is a floor, not a negotiation anchor).

  - **LIQUIDATION**: orderly + forced wind-down scenarios. Like ASSET in
    that the balance sheet is the input — but it's a downside lens, not
    a going-concern equity estimate. Same gate behaviour as ASSET (own
    confidence framework, no asking-price buffer).

  - **SDE**: Seller's Discretionary Earnings — owner-operator micro-SMEs.
    Same heuristics as MULTIPLES but on a different metric. Apply the gate.

  - **DCF**: Discounted Cash Flow. The Three Towers Capital regression case.

  - **HYBRID**: Multiples + DCF blended. The bridge-suppression guard must
    fire here too (methodology-drift risk between the two paths).

  - **MULTIPLES**: EV/EBITDA or EV/Revenue market-multiple. Apply the gate.

  - **UNKNOWN**: defensive default. Apply the conservative gate.
"""

from __future__ import annotations

from enum import Enum

JsonMap = dict[str, object]


class Methodology(Enum):
    """Top-level valuation methodology buckets."""

    STARTUP = "startup"
    ASSET = "asset"
    LIQUIDATION = "liquidation"
    SDE = "sde"
    DCF = "dcf"
    HYBRID = "hybrid"
    MULTIPLES = "multiples"
    UNKNOWN = "unknown"


def _normalise_methodology_string(value: object) -> str:
    """Lowercase + strip the ``methodology`` field."""
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


_METHODOLOGY_STRING_RULES: tuple[tuple[Methodology, tuple[str, ...]], ...] = (
    (Methodology.STARTUP, ("startup", "berkus", "scorecard")),
    # Liquidation must be checked before the generic "asset" branch because
    # the engine label is asset-anchored but routes to a different track.
    (Methodology.LIQUIDATION, ("liquidat", "liquidatie")),
    (Methodology.HYBRID, ("hybrid",)),
    (Methodology.DCF, ("dcf", "discounted cash")),
    (Methodology.SDE, ("sde", "seller")),
    (Methodology.ASSET, ("asset", "nav", "book value", "boekwaarde")),
    (Methodology.MULTIPLES, ("multiple", "ev/ebitda", "ev/revenue", "market")),
)


def _has_dict_payload(valuation_data: JsonMap, key: str) -> bool:
    return isinstance(valuation_data.get(key), dict)


def _methodology_from_report_flags(
    valuation_data: JsonMap,
) -> Methodology | None:
    if valuation_data.get("is_startup_valuation_report") is True or _has_dict_payload(
        valuation_data, "startup_report"
    ):
        return Methodology.STARTUP
    if valuation_data.get("is_liquidation_report") is True or _has_dict_payload(
        valuation_data, "liquidation_report"
    ):
        return Methodology.LIQUIDATION
    return None


def _methodology_from_persisted_flags(
    valuation_data: JsonMap,
) -> Methodology | None:
    if valuation_data.get("is_asset_methodology") is True:
        return Methodology.ASSET
    if valuation_data.get("is_sde_methodology") is True:
        return Methodology.SDE
    return None


def _methodology_from_string(value: object) -> Methodology | None:
    methodology = _normalise_methodology_string(value)
    if not methodology:
        return None
    for candidate, needles in _METHODOLOGY_STRING_RULES:
        if any(needle in methodology for needle in needles):
            return candidate
    return None


def _methodology_from_value_surfaces(
    valuation_data: JsonMap,
) -> Methodology | None:
    if valuation_data.get("dcf_valuation"):
        return Methodology.DCF
    if valuation_data.get("multiples_valuation"):
        return Methodology.MULTIPLES
    return None


def detect_methodology(valuation_data: object) -> Methodology:
    """Detect the top-level methodology from raw ``valuation_data``.

    Inspection order (first match wins):
      1. Explicit ``is_startup_valuation_report`` flag or ``startup_report``
         dict — these come from the Studio v2 wizard and are authoritative.
      2. Explicit ``is_asset_methodology`` / ``is_sde_methodology`` flags
         when present (set by the aggregator on the persisted context).
      3. The ``methodology`` string — keyword match in priority order:
         hybrid (must beat plain DCF) → DCF → SDE → asset/NAV → multiples.
      4. Fallback: ``UNKNOWN``.

    Defensive: never raises. Returns ``UNKNOWN`` on malformed input.
    """
    if not isinstance(valuation_data, dict):
        return Methodology.UNKNOWN

    for detected in (
        _methodology_from_report_flags(valuation_data),
        _methodology_from_persisted_flags(valuation_data),
        _methodology_from_string(valuation_data.get("methodology")),
        _methodology_from_value_surfaces(valuation_data),
    ):
        if detected is not None:
            return detected

    return Methodology.UNKNOWN


def has_own_confidence_framework(methodology: Methodology) -> bool:
    """True if the methodology defines its own confidence/uncertainty model.

    Used by the years-of-data + margin classifier to skip its work when the
    methodology already handles defensibility natively. Example: a Berkus
    pre-seed valuation will always be N=0y; that's not a defensibility
    failure, it's the entire premise of the method.
    """
    return methodology in (
        Methodology.STARTUP,
        Methodology.ASSET,
        Methodology.LIQUIDATION,
    )


def supports_asking_price_buffer(methodology: Methodology) -> bool:
    """True if a "+8% strategic buffer" makes sense for this methodology.

    Asset-based valuations are floors (replacement cost / NAV) — adding a
    negotiation buffer above that misrepresents the methodology. Startup
    valuations already report a wide range; further buffer is double-counting
    uncertainty. Liquidation analysis is a downside scenario by definition;
    a +8% buffer on a wind-down floor is nonsensical.
    """
    return methodology not in (
        Methodology.STARTUP,
        Methodology.ASSET,
        Methodology.LIQUIDATION,
    )
