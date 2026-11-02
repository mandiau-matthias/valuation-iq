"""Suppress the asking-price negotiation buffer for sub-FULL reports.

The standard ``get_asking_price_markup`` returns 5–10% based on confidence
level. For LIMITED_SCOPE / PRELIMINARY reports — and for methodologies
that don't support a buffer concept (asset-based, startup) — recommending
"+8% strategic buffer" implies the valuation is precise enough to anchor
a tight negotiation. That contradicts the limited-scope caveat.

Three Towers Capital regression: rendered "Voorgestelde Vraagprijs €666K
(+8%)" attached to a 75%-confidence-capped headline. Post-fix the
recommendation collapses to the equity midpoint with an explicit reason.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.services.defensibility.classifier import (
    DefensibilityVerdict,
    classify_valuation_data,
)
from src.services.defensibility.methodology import (
    Methodology,
    supports_asking_price_buffer,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _model_dump_safe(obj: Any) -> Any:
    """Coerce a Pydantic model (or list of them) to a dict shape; passthrough otherwise."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_model_dump_safe(item) for item in obj]
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump()
        except (TypeError, ValueError):
            return None
    return obj


def build_engine_side_gate_input(
    request: Any,
    response: Any,
) -> Dict[str, Any]:
    """Construct the minimal ``valuation_data``-shaped dict the gate's classifier needs.

    Mirrors ``_build_defensibility_input`` (reports.py) but pulls from the
    engine-side Pydantic ``request``/``response`` objects available during
    ``/calculate``'s html_report path. Used by the dual report renderer so
    the buffer-suppression behaviour is identical to /render and /pdf.
    """
    current_year_dict = _model_dump_safe(getattr(request, "current_year_data", None)) or {}
    historical_dict = _model_dump_safe(getattr(request, "historical_years_data", None)) or []

    data_quality_warnings: List[Any] = []
    response_warnings = getattr(response, "data_quality_warnings", None)
    if isinstance(response_warnings, list):
        data_quality_warnings = list(response_warnings)

    detailed_results = getattr(response, "detailed_results", None)
    if not isinstance(detailed_results, dict):
        detailed_results = {}

    metadata = getattr(request, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}

    revenue: Optional[Any] = current_year_dict.get("revenue") if isinstance(current_year_dict, dict) else None
    ebitda: Optional[Any] = current_year_dict.get("ebitda") if isinstance(current_year_dict, dict) else None

    return {
        "current_year_data": current_year_dict,
        "historical_years_data": historical_dict,
        "revenue": revenue,
        "ebitda": ebitda,
        "data_quality_warnings": data_quality_warnings,
        "detailed_results": detailed_results,
        "metadata": metadata,
        "country_code": getattr(request, "country_code", None),
        "industry": getattr(request, "industry", None),
        "business_model": getattr(request, "business_model", None),
        "methodology": getattr(request, "methodology", None),
        "owner_managers": getattr(request, "owner_managers", None),
        "total_employees": getattr(request, "total_employees", None),
    }


def _coerce_decimal(value: Any) -> Decimal:
    """Defensive Decimal coercion; returns 0 on failure."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return Decimal("0")


def apply_asking_price_gate(
    context: Dict[str, Any],
    valuation_data: Dict[str, Any],
    *,
    verdict: DefensibilityVerdict | None = None,
) -> None:
    """Override ``recommended_asking_price`` for sub-FULL classifications.

    Mutates ``context`` in place. Defensive: any failure leaves context
    unchanged.

    Triggers (any of):
      - Classification ≠ FULL_REPORT
      - Methodology does not support a buffer concept (asset / startup)

    When the override fires, ``context`` gets:
      - ``recommended_asking_price`` ← ``equity_value`` (midpoint, no buffer)
      - ``recommended_asking_price_buffer_suppressed`` = True
      - ``recommended_asking_price_buffer_reason`` (human-readable)
    """
    try:
        v = verdict or classify_valuation_data(valuation_data)
    except Exception:
        return

    # Decide whether the gate fires.
    methodology_unsupported = not supports_asking_price_buffer(v.methodology)
    sub_full = (not v.is_full_report) and v.classification_value is not None

    if not (methodology_unsupported or sub_full):
        return

    # Pull the equity value to collapse the recommendation to. On a
    # consolidated dossier with a booked minority interest (advisor F08) the
    # seller can only sell their own stake, so collapse to the seller-
    # attributable equity — never back up to the full consolidated equity.
    # This gate runs AFTER the aggregator's minority re-anchor (renderer /
    # reports route), so without this guard a sub-FULL / asset / startup
    # classification would silently re-inflate the ask past the minority.
    equity = context.get("equity_value")
    if equity is None:
        return
    equity_dec = _coerce_decimal(equity)
    if equity_dec <= 0:
        return

    collapse_to = equity_dec
    seller_eq = context.get("minority_seller_equity")
    if seller_eq is not None:
        seller_eq_dec = _coerce_decimal(seller_eq)
        if 0 < seller_eq_dec < collapse_to:
            collapse_to = seller_eq_dec

    prior = context.get("recommended_asking_price")
    context["recommended_asking_price"] = float(collapse_to)
    context["recommended_asking_price_buffer_suppressed"] = True

    if methodology_unsupported:
        if v.methodology == Methodology.ASSET:
            reason = (
                "Negotiation buffer suppressed: asset-based valuations "
                "represent a value floor, not a negotiation anchor."
            )
        elif v.methodology == Methodology.STARTUP:
            reason = (
                "Negotiation buffer suppressed: startup valuations already "
                "report a wide range; an additional buffer would double-count "
                "uncertainty."
            )
        else:
            reason = (
                "Negotiation buffer suppressed: this methodology does not "
                "support a single-point negotiation buffer."
            )
    else:
        cap_pct = int(v.confidence_cap * Decimal("100"))
        cls = v.classification_value or "limited scope"
        reason = (
            f"Negotiation buffer suppressed: report is {cls.lower()}; "
            f"confidence cap {cap_pct}% does not support a tight buffer."
        )
    context["recommended_asking_price_buffer_reason"] = reason

    logger.info(
        "Asking-price buffer suppressed",
        extra={
            "methodology": v.methodology.value,
            "classification": v.classification_value,
            "confidence_cap": float(v.confidence_cap),
            "previous_recommended_asking_price": prior,
            "new_recommended_asking_price": float(equity_dec),
            "reason_kind": "methodology" if methodology_unsupported else "scope",
        },
    )
