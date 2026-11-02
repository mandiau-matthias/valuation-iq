"""
Shared resolution of WACC **size premium** for DCF (`DCFValuationEngineRefactored`).

Used by ``DCFCalculator`` (sessioned valuations) and ``stateless_router._calculate_dcf``
so both paths honour Titan ``sme_calibration`` when present, then fall back to the
Duff & Phelps interpolated curve in ``market_defaults.get_size_premium``.

Lazy-imports academics inside the resolver body so tests can monkeypatch
``market_defaults.get_size_premium`` after imports.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Mapping, Optional

if TYPE_CHECKING:
    import logging


def resolve_size_premium_for_dcf_engine(
    *,
    revenue: Decimal,
    sme_calibration: Optional[Mapping[str, object]],
    logger: Optional["logging.Logger"] = None,
) -> tuple[Decimal, str]:
    """Return `(size_premium_decimal, provenance_hint)`.

    Precedence mirrors ``dcf_calculator.DCFCalculator``:
      1. ``sme_calibration`` → ``DatabaseDrivenDefaults`` + ``SMEMultipleSelector``.
      2. Academic interpolated tiers (Duff & Phelps style).
    """
    revenue = Decimal(str(revenue or 0))
    size_premium: Optional[Decimal] = None
    source_hint = "none"

    if sme_calibration and isinstance(sme_calibration, dict):
        from src.services.academic.sme_multiple_selector import SMEMultipleSelector
        from src.services.business_intelligence.database_driven_defaults import (
            DatabaseDrivenDefaults,
        )

        DatabaseDrivenDefaults.initialize(dict(sme_calibration))
        sme_class = SMEMultipleSelector.classify_sme(revenue)
        candidate = DatabaseDrivenDefaults.get_size_premium(sme_class)
        if candidate is not None:
            size_premium = Decimal(str(candidate))
            source_hint = f"sme_calibration:{sme_class}"

    if size_premium is None:
        from src.domain.market_defaults import get_size_premium as _academic_size_premium

        size_premium, tier_label = _academic_size_premium(revenue)
        source_hint = f"duff_phelps:{tier_label}"

    if logger is not None:
        logger.info(
            "📐 DCF size premium resolved",
            extra={
                "size_premium": float(size_premium) if size_premium is not None else None,
                "source": source_hint,
                "revenue": float(revenue),
            },
        )

    return Decimal(str(size_premium)), source_hint
