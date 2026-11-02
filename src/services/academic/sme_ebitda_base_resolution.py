"""Base EV/EBITDA multiple resolution for SME calibration."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, NamedTuple, Optional

from src.services.academic.sme_business_type_lookup import synced_business_type_ev_ebitda
from src.services.academic.sme_multiple_catalog import (
    BELGIAN_SME_MULTIPLES,
    BELGIAN_SME_MULTIPLES_BY_TYPE,
    CATEGORY_TO_SME_KEY,
    TRANSACTION_SME_MULTIPLES,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from src.services.business_intelligence.database_driven_defaults import DatabaseDrivenDefaults

    DATABASE_DRIVEN_DEFAULTS_AVAILABLE = True
except ImportError:
    DATABASE_DRIVEN_DEFAULTS_AVAILABLE = False
    logger.warning("DatabaseDrivenDefaults not available - using hardcoded fallbacks")
    DatabaseDrivenDefaults = None


class SmeEbitdaBaseMultipleResolution(NamedTuple):
    """Resolved base multiple and provenance before SME adjustments."""

    base_multiple: Decimal
    source_name: str
    data_source_priority: str
    industry_norm: str


def _resolve_titan_sme_calibration(
    sme_calibration: Optional[Dict[str, Any]],
    sme_class: str,
) -> Optional[tuple[Decimal, str, str]]:
    if not sme_calibration:
        return None

    sme_key = f"ev_ebitda_{sme_class}"
    if not sme_calibration.get(sme_key):
        return None

    base_multiple = Decimal(str(sme_calibration[sme_key]))
    source_name = sme_calibration.get("calibration_source", "Titan enrichment")
    logger.debug(
        f"PRIORITY 1: Using Titan-provided SME calibration for {sme_class}",
        ev_ebitda=float(base_multiple),
        source="titan_enrichment",
        calibration_source=source_name,
    )
    return base_multiple, source_name, "titan_enrichment"


def _resolve_synced_business_type_multiple(
    business_type: Optional[str],
    country: str,
    sme_class: str,
) -> Optional[tuple[Decimal, str, str]]:
    if not business_type:
        return None

    synced_multiple = synced_business_type_ev_ebitda(business_type, country)
    if synced_multiple is None or synced_multiple <= 0:
        return None

    source_name = f"Upswitch business-types DB (type: {business_type})"
    logger.info(
        f"PRIORITY 1.5: Using synced business-types DB multiple for {business_type}/{sme_class}",
        ev_ebitda=float(synced_multiple),
        source="business_types_synced_db",
    )
    return synced_multiple, source_name, "business_types_synced_db"


def _resolve_database_category_multiple(
    business_category: Optional[str],
    sme_class: str,
) -> Optional[tuple[Decimal, str, str]]:
    if not business_category or DatabaseDrivenDefaults is None:
        return None

    db_multiples = DatabaseDrivenDefaults.get_sme_multiples_by_category(
        category_id=business_category, sme_class=sme_class
    )
    if not db_multiples or not db_multiples.get("ev_ebitda"):
        return None

    base_multiple = db_multiples["ev_ebitda"]
    source_name = f"Database (category: {business_category})"
    logger.info(
        f"PRIORITY 2: Using database SME multiple for category {business_category}/{sme_class}",
        ev_ebitda=float(base_multiple),
        source="database_category",
    )
    return base_multiple, source_name, "database_category"


def _resolve_database_industry_multiple(
    industry_norm: str,
    sme_class: str,
) -> Optional[tuple[Decimal, str, str]]:
    if DatabaseDrivenDefaults is None:
        return None

    db_multiples = DatabaseDrivenDefaults.get_sme_multiples_by_industry(
        industry=industry_norm, sme_class=sme_class
    )
    if not db_multiples or not db_multiples.get("ev_ebitda"):
        return None

    base_multiple = db_multiples["ev_ebitda"]
    source_name = f"Database (industry: {industry_norm})"
    logger.info(
        f"PRIORITY 2: Using database SME multiple for industry {industry_norm}/{sme_class}",
        ev_ebitda=float(base_multiple),
        source="database_industry",
    )
    return base_multiple, source_name, "database_industry"


def _resolve_database_default_multiple(
    *,
    business_category: Optional[str],
    industry_norm: str,
    sme_class: str,
) -> Optional[tuple[Decimal, str, str]]:
    if not (
        DATABASE_DRIVEN_DEFAULTS_AVAILABLE
        and DatabaseDrivenDefaults
        and DatabaseDrivenDefaults.is_initialized()
    ):
        return None

    return _resolve_database_category_multiple(
        business_category,
        sme_class,
    ) or _resolve_database_industry_multiple(industry_norm, sme_class)


def _resolve_sme_category_key(industry_norm: str) -> Optional[str]:
    sme_key = CATEGORY_TO_SME_KEY.get(industry_norm)
    if sme_key is not None:
        return sme_key

    for alias, canonical in CATEGORY_TO_SME_KEY.items():
        if alias in industry_norm or industry_norm in alias:
            return canonical
    return None


def _resolve_hardcoded_sme_multiple(
    *,
    industry: str,
    industry_norm: str,
    sme_class: str,
    business_type: Optional[str],
    country: str,
    use_transaction_data: bool,
) -> SmeEbitdaBaseMultipleResolution:
    if business_type and business_type in BELGIAN_SME_MULTIPLES_BY_TYPE:
        type_multiples = BELGIAN_SME_MULTIPLES_BY_TYPE[business_type]
        base_multiple = type_multiples.get(sme_class, Decimal("5.0"))
        source_name = f"Benelux SME 2.0 (type: {business_type})"
        logger.info(
            f"PRIORITY 3a: Using per-business-type Benelux SME multiple for {business_type}/{sme_class}",
            ev_ebitda=float(base_multiple),
            source="benelux_sme_by_type",
        )
        return SmeEbitdaBaseMultipleResolution(
            base_multiple=base_multiple,
            source_name=source_name,
            data_source_priority="benelux_sme_by_type",
            industry_norm=industry_norm,
        )

    if country == "Belgium" and not use_transaction_data:
        source_dataset = BELGIAN_SME_MULTIPLES
        source_name = "Benelux SME 2.0 (category)"
    else:
        source_dataset = TRANSACTION_SME_MULTIPLES
        source_name = "Pepperdine (2024) / BizComps (2024)"

    sme_key = _resolve_sme_category_key(industry_norm)
    industry_multiples = source_dataset.get(sme_key) if sme_key else None

    if industry_multiples is None:
        logger.warning(
            f"Industry '{industry}' not found in SME dataset, using 'services' as fallback"
        )
        industry_multiples = source_dataset.get(
            "services",
            {
                "micro": Decimal("4.0"),
                "small": Decimal("5.0"),
                "medium": Decimal("6.0"),
            },
        )
        industry_norm = "services"

    return SmeEbitdaBaseMultipleResolution(
        base_multiple=industry_multiples.get(sme_class, Decimal("5.0")),
        source_name=source_name,
        data_source_priority="hardcoded_fallback",
        industry_norm=industry_norm,
    )


def resolve_base_ebitda_multiple(
    *,
    industry: str,
    industry_norm: str,
    sme_class: str,
    business_type: Optional[str],
    business_category: Optional[str],
    country: str,
    use_transaction_data: bool,
    sme_calibration: Optional[Dict[str, Any]],
) -> SmeEbitdaBaseMultipleResolution:
    """Resolve the SME base multiple before bounds and qualitative adjustments."""
    resolved = (
        _resolve_titan_sme_calibration(sme_calibration, sme_class)
        or _resolve_synced_business_type_multiple(business_type, country, sme_class)
        or _resolve_database_default_multiple(
            business_category=business_category,
            industry_norm=industry_norm,
            sme_class=sme_class,
        )
    )
    if resolved:
        base_multiple, source_name, data_source_priority = resolved
        return SmeEbitdaBaseMultipleResolution(
            base_multiple=base_multiple,
            source_name=source_name,
            data_source_priority=data_source_priority,
            industry_norm=industry_norm,
        )

    fallback = _resolve_hardcoded_sme_multiple(
        industry=industry,
        industry_norm=industry_norm,
        sme_class=sme_class,
        business_type=business_type,
        country=country,
        use_transaction_data=use_transaction_data,
    )
    if DATABASE_DRIVEN_DEFAULTS_AVAILABLE:
        logger.warning(
            f"Database lookup failed, using hardcoded fallback for {fallback.industry_norm}/{sme_class}",
            ev_ebitda=float(fallback.base_multiple),
            source="hardcoded_fallback",
        )
    return fallback
