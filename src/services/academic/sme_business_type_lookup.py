"""
Synced business-type lookup helpers for SME calibration.

These helpers are deliberately fail-soft: missing snapshots or repository
errors must not break valuation generation.
"""

from decimal import Decimal
from typing import Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


def synced_owner_dependency_impact(business_type: Optional[str]) -> Optional[Decimal]:
    """Resolve owner-dependency impact from the synced business-types snapshot."""
    if not business_type:
        return None

    try:
        from src.database.business_types_repository import get_business_types_repository

        with get_business_types_repository() as repo:
            metadata = repo.get_business_type(str(business_type))

        value = getattr(metadata, "owner_dependency_impact", None)
        if value is None:
            return None

        resolved = Decimal(str(value))
        return resolved if Decimal("0") <= resolved <= Decimal("1") else None
    except Exception as exc:
        logger.debug(
            "Synced owner-dependency lookup unavailable; no adjustment",
            business_type=str(business_type),
            error=str(exc),
        )
        return None


def synced_business_type_ev_ebitda(
    business_type: Optional[str], country: str = "Belgium"
) -> Optional[Decimal]:
    """Resolve EV/EBITDA from the synced business-types snapshot."""
    if not business_type:
        return None

    try:
        from src.database.business_types_repository import get_business_types_repository

        with get_business_types_repository() as repo:
            multiples = repo.get_valuation_multiples(str(business_type), "BE")

        value = multiples.get("ev_ebitda_multiple") if isinstance(multiples, dict) else None
        if value is None:
            return None

        resolved = Decimal(str(value))
        return resolved if resolved > 0 else None
    except Exception as exc:
        logger.debug(
            "Synced business-types DB lookup unavailable; using next fallback",
            business_type=str(business_type),
            country=country,
            error=str(exc),
        )
        return None
