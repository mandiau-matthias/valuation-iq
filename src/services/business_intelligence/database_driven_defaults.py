"""
Database-Driven Defaults for SME Valuation Parameters

Provides database-first access to SME calibration data (size premiums,
multiples, etc.) from the Titan business_types table. Falls back to
hardcoded academic defaults when the database is not available.

Uses ContextVar for per-request isolation to prevent cross-request
data leakage under asyncio concurrency. Code that runs in a **thread pool**
without copied context should not rely on this storage; keep SME calibration
on the asyncio task or pass calibration explicitly.

Sources (fallback values):
- Duff & Phelps (2024): "Cost of Capital Navigator" - Size premiums
- Ibbotson (2024): SBBI Yearbook - Small stock premium data
"""

from contextvars import ContextVar
from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)

_calibration_ctx: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "database_driven_defaults_calibration", default=None
)


class DatabaseDrivenDefaults:
    """
    Per-request calibration data from Titan, stored in a ContextVar
    for async-safe isolation between concurrent requests.

    Lifecycle:
        1. Titan sends ``sme_calibration`` dict in the valuation request.
        2. Early in the request pipeline, call ``initialize(sme_calibration)``.
        3. Downstream consumers call ``get_size_premium(sme_class)`` etc.
        4. After the request, call ``reset()`` to clear per-request state.
    """

    _FALLBACK_SIZE_PREMIUMS: Dict[str, Decimal] = {
        "micro": Decimal("0.08"),
        "small": Decimal("0.06"),
        "medium": Decimal("0.04"),
        "large": Decimal("0.02"),
    }

    @classmethod
    def initialize(cls, sme_calibration: Optional[Dict[str, Any]]) -> None:
        """Load calibration data from the Titan request payload."""
        if sme_calibration:
            _calibration_ctx.set(dict(sme_calibration))
            # DEBUG: per-request init notice; the "PRIORITY 1: Using
            # Titan-provided SME calibration" line already announces the
            # calibration source.
            logger.debug(
                "DatabaseDrivenDefaults initialized from Titan sme_calibration",
                extra={"keys": list(sme_calibration.keys())},
            )
        else:
            _calibration_ctx.set(None)

    @classmethod
    def is_initialized(cls) -> bool:
        return _calibration_ctx.get() is not None

    @classmethod
    def reset(cls) -> None:
        """Clear per-request state."""
        _calibration_ctx.set(None)

    @classmethod
    def _get_calibration(cls) -> Dict[str, Any]:
        return _calibration_ctx.get() or {}

    @classmethod
    def get_size_premium(cls, sme_class: str) -> Decimal:
        """
        Return the WACC size premium for the given SME class.

        Priority:
            1. Database value from ``sme_calibration``
            2. Hardcoded Duff & Phelps 2024 fallback

        Args:
            sme_class: One of 'micro', 'small', 'medium', 'large'

        Returns:
            Size premium as a Decimal fraction (e.g. 0.06 = 6 %).
        """
        cal = cls._get_calibration()
        if cal:
            field_map = {
                "micro": "size_premium_micro",
                "small": "size_premium_small",
                "medium": "size_premium_medium",
                "lower_middle": "size_premium_medium",
                "large": None,
            }
            field = field_map.get(sme_class)
            if field:
                value = cal.get(field)
                if value is not None:
                    return Decimal(str(value))

        return cls._FALLBACK_SIZE_PREMIUMS.get(sme_class, Decimal("0.05"))

    @classmethod
    def get_business_type_defaults(cls, business_type_id: str) -> Optional[Dict[str, Any]]:
        """
        Return multiples defaults from Titan-provided sme_calibration data.

        The sme_calibration dict carries tier-specific multiples
        (ev_ebitda_micro/small/medium, ev_revenue_micro/small/medium).
        We pick the first available tier in order small -> medium -> micro
        as a reasonable midpoint for Belgian SMEs.

        Args:
            business_type_id: Business type identifier (unused for lookup,
                              but kept for interface compatibility).

        Returns:
            Dict with ``ev_ebitda``, ``ev_revenue``, ``pe`` keys, or ``None``
            if no calibration data is available.
        """
        cal = cls._get_calibration()
        if not cal:
            return None

        ev_ebitda = None
        for key in ("ev_ebitda_small", "ev_ebitda_medium", "ev_ebitda_micro"):
            val = cal.get(key)
            if val is not None:
                ev_ebitda = Decimal(str(val))
                break

        ev_revenue = None
        for key in ("ev_revenue_small", "ev_revenue_medium", "ev_revenue_micro"):
            val = cal.get(key)
            if val is not None:
                ev_revenue = Decimal(str(val))
                break

        if ev_ebitda is None and ev_revenue is None:
            return None

        result: Dict[str, Any] = {}
        if ev_ebitda is not None:
            result["ev_ebitda"] = ev_ebitda
        if ev_revenue is not None:
            result["ev_revenue"] = ev_revenue
        result["pe"] = Decimal("15.0")

        logger.info(
            "DatabaseDrivenDefaults.get_business_type_defaults: returning calibration data",
            extra={
                "business_type_id": business_type_id,
                "ev_ebitda": str(ev_ebitda),
                "ev_revenue": str(ev_revenue),
            },
        )
        return result

    @classmethod
    def get_category_defaults(cls, category_id: str) -> Optional[Dict[str, Any]]:
        """
        Return category-level multiples defaults from sme_calibration data.

        Re-uses the same tier-based lookup as ``get_business_type_defaults``
        because sme_calibration is already business-type-specific (Titan
        enriches per business type, not per category).

        Args:
            category_id: Category identifier.

        Returns:
            Dict with ``ev_ebitda``, ``ev_revenue``, ``pe`` keys, or ``None``.
        """
        return cls.get_business_type_defaults(category_id)

    @classmethod
    def get_sme_multiples_by_industry(
        cls, industry: str, sme_class: str
    ) -> Optional[Dict[str, Any]]:
        """
        Return SME multiples for a given industry and size class.

        Uses the same tier-based lookup as ``get_business_type_defaults``
        because sme_calibration is already business-type-specific. The
        ``industry`` parameter is accepted for interface compatibility but
        the lookup is driven by the ``sme_class`` tier keys in the
        calibration data.

        Args:
            industry: Industry identifier (for logging/compatibility).
            sme_class: One of 'micro', 'small', 'medium', 'large'.

        Returns:
            Dict with ``ev_ebitda``, ``ev_revenue`` keys, or ``None``.
        """
        cal = cls._get_calibration()
        if not cal:
            return None

        ev_ebitda_key = f"ev_ebitda_{sme_class}"
        ev_revenue_key = f"ev_revenue_{sme_class}"

        ev_ebitda_val = cal.get(ev_ebitda_key)
        ev_revenue_val = cal.get(ev_revenue_key)

        if ev_ebitda_val is None and ev_revenue_val is None:
            return cls.get_business_type_defaults(industry)

        result: Dict[str, Any] = {}
        if ev_ebitda_val is not None:
            result["ev_ebitda"] = Decimal(str(ev_ebitda_val))
        if ev_revenue_val is not None:
            result["ev_revenue"] = Decimal(str(ev_revenue_val))

        return result if result else None

    @classmethod
    def get_sme_multiples_by_category(
        cls, category_id: str, sme_class: str
    ) -> Optional[Dict[str, Any]]:
        """
        Return SME multiples for a given category and size class.

        Delegates to ``get_sme_multiples_by_industry`` since sme_calibration
        data is business-type-specific rather than category-specific.

        Args:
            category_id: Category identifier.
            sme_class: One of 'micro', 'small', 'medium', 'large'.

        Returns:
            Dict with ``ev_ebitda``, ``ev_revenue`` keys, or ``None``.
        """
        return cls.get_sme_multiples_by_industry(category_id, sme_class)

    @classmethod
    def get_industry_defaults(cls, industry: str) -> Optional[Dict[str, Any]]:
        """
        Return industry-level multiples defaults.

        Delegates to ``get_business_type_defaults`` for compatibility with
        callers that use the industry-based lookup interface.

        Args:
            industry: Industry identifier.

        Returns:
            Dict with ``ev_ebitda``, ``ev_revenue``, ``pe`` keys, or ``None``.
        """
        return cls.get_business_type_defaults(industry)

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Return diagnostic stats for observability."""
        cal = cls._get_calibration()
        return {
            "initialized": cal is not None,
            "calibration_keys": list(cal.keys()) if cal else [],
        }
