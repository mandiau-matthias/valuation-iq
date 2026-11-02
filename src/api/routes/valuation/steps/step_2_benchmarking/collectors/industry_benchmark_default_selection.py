"""Disclosed default and final-validation selection for Step 2 benchmarks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Dict, Optional, Protocol

from fastapi import HTTPException

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory
from src.utils.decimal_helpers import to_decimal

from .industry_benchmark_defaults import BUSINESS_TYPE_DEFAULTS, INDUSTRY_DEFAULTS
from .industry_benchmark_fallbacks import normalize_industry_key


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def error(self, msg: str, *args: object, **kwargs: object) -> object: ...


CategoryDefaultsResolver = Callable[[BusinessTypeCategory], Optional[Dict[str, Decimal]]]
BenchmarkUnavailableBuilder = Callable[..., HTTPException]


@dataclass(frozen=True)
class DefaultBenchmarkSelection:
    ev_ebitda_ratio: Optional[Decimal]
    revenue_multiple: Optional[Decimal]
    pe_ratio: Decimal
    data_source: str
    data_source_details: Dict[str, object]


def _missing_or_nonpositive(value: Optional[Decimal]) -> bool:
    return not value or value <= 0


def _needs_default_multiples(selection: DefaultBenchmarkSelection) -> bool:
    return _missing_or_nonpositive(selection.ev_ebitda_ratio) or _missing_or_nonpositive(
        selection.revenue_multiple
    )


def _database_business_type_selection(
    *,
    selection: DefaultBenchmarkSelection,
    business_type_id: str,
    database_defaults_available: bool,
    database_defaults: object,
    correlation_id: Optional[str],
    logger: LoggerLike,
) -> Optional[DefaultBenchmarkSelection]:
    db_defaults = (
        database_defaults.get_business_type_defaults(business_type_id)
        if database_defaults_available and database_defaults
        else None
    )
    if not db_defaults:
        return None

    ev_ebitda_ratio = db_defaults.get("ev_ebitda")
    revenue_multiple = db_defaults.get("ev_revenue")
    pe_ratio = db_defaults.get("pe", Decimal("15.0"))
    logger.info(
        f"✅ Using DATABASE-DRIVEN defaults for '{business_type_id}' (loaded at startup)",
        extra={
            "business_type_id": business_type_id,
            "ev_ebitda": ev_ebitda_ratio,
            "ev_revenue": revenue_multiple,
            "pe": pe_ratio,
            "correlation_id": correlation_id,
            "source": "database_startup_cache",
        },
    )
    return replace(
        selection,
        ev_ebitda_ratio=ev_ebitda_ratio,
        revenue_multiple=revenue_multiple,
        pe_ratio=pe_ratio,
        data_source="database_driven_default",
        data_source_details={
            "business_type_id": business_type_id,
            "source": "database_startup_cache",
            "note": "Legacy synced defaults loaded at startup",
        },
    )


def _hardcoded_business_type_selection(
    *,
    selection: DefaultBenchmarkSelection,
    business_type_id: str,
    correlation_id: Optional[str],
    logger: LoggerLike,
) -> Optional[DefaultBenchmarkSelection]:
    bt_defaults = BUSINESS_TYPE_DEFAULTS.get(business_type_id)
    if not bt_defaults:
        return None

    ev_ebitda_ratio = bt_defaults["ev_ebitda"]
    revenue_multiple = bt_defaults.get("ev_revenue")
    pe_ratio = bt_defaults.get("pe", Decimal("15.0"))
    logger.warning(
        f"⚠️ FALLBACK: Using HARDCODED defaults for '{business_type_id}' - "
        f"Not found in database startup cache. Values may not match the benchmark contract!",
        extra={
            "business_type_id": business_type_id,
            "ev_ebitda": ev_ebitda_ratio,
            "ev_revenue": revenue_multiple,
            "pe": pe_ratio,
            "correlation_id": correlation_id,
            "fallback_severity": "MEDIUM",
        },
    )
    return replace(
        selection,
        ev_ebitda_ratio=ev_ebitda_ratio,
        revenue_multiple=revenue_multiple,
        pe_ratio=pe_ratio,
        data_source="hardcoded_business_type",
        data_source_details={
            "business_type_id": business_type_id,
            "source": "hardcoded_defaults",
            "warning": "Using legacy hardcoded fallback - consider updating database",
        },
    )


def _database_category_selection(
    *,
    selection: DefaultBenchmarkSelection,
    request: object,
    database_defaults_available: bool,
    database_defaults: object,
    correlation_id: Optional[str],
    logger: LoggerLike,
) -> Optional[DefaultBenchmarkSelection]:
    category_id = getattr(request, "category_id", None) if request else None
    if not (category_id and database_defaults_available and database_defaults):
        return None

    cat_defaults = database_defaults.get_category_defaults(category_id)
    if not cat_defaults:
        return None

    ev_ebitda_ratio = cat_defaults.get("ev_ebitda")
    revenue_multiple = cat_defaults.get("ev_revenue")
    pe_ratio = cat_defaults.get("pe", Decimal("15.0"))
    logger.info(
        f"✅ Using DATABASE category defaults for '{category_id}'",
        extra={
            "category_id": category_id,
            "ev_ebitda": ev_ebitda_ratio,
            "ev_revenue": revenue_multiple,
            "correlation_id": correlation_id,
        },
    )
    return replace(
        selection,
        ev_ebitda_ratio=ev_ebitda_ratio,
        revenue_multiple=revenue_multiple,
        pe_ratio=pe_ratio,
        data_source="database_category_default",
        data_source_details={
            "category_id": category_id,
            "source": "database_category_aggregate",
            "business_types_count": cat_defaults.get("business_types_count"),
        },
    )


def _hardcoded_category_selection(
    *,
    selection: DefaultBenchmarkSelection,
    business_type_id: str,
    business_category: BusinessTypeCategory,
    category_defaults_resolver: CategoryDefaultsResolver,
    correlation_id: Optional[str],
    logger: LoggerLike,
) -> Optional[DefaultBenchmarkSelection]:
    category_defaults = category_defaults_resolver(business_category)
    if not category_defaults:
        return None

    ev_ebitda_ratio = category_defaults.get("ev_ebitda")
    revenue_multiple = category_defaults.get("ev_revenue")
    pe_ratio = category_defaults.get("pe", Decimal("15.0"))
    business_category_value = (
        getattr(business_category, "value", "unknown") if business_category else "unknown"
    )
    logger.warning(
        f"⚠️ FALLBACK: Using hardcoded category defaults for {business_category_value} "
        f"(business_type_id '{business_type_id}' not found in database or hardcoded defaults)",
        extra={
            "business_type_id": business_type_id,
            "business_category": business_category_value,
            "ev_ebitda": ev_ebitda_ratio,
            "ev_revenue": revenue_multiple,
            "correlation_id": correlation_id,
        },
    )
    return replace(
        selection,
        ev_ebitda_ratio=ev_ebitda_ratio,
        revenue_multiple=revenue_multiple,
        pe_ratio=pe_ratio,
        data_source="hardcoded_category_default",
        data_source_details={
            "business_category": business_category_value,
            "source": "hardcoded_category_defaults",
            "warning": "Using legacy hardcoded category fallback",
        },
    )


def _apply_business_type_default_selection(
    *,
    selection: DefaultBenchmarkSelection,
    business_type_id: Optional[str],
    business_category: BusinessTypeCategory,
    request: object,
    database_defaults_available: bool,
    database_defaults: object,
    category_defaults_resolver: CategoryDefaultsResolver,
    correlation_id: Optional[str],
    logger: LoggerLike,
) -> DefaultBenchmarkSelection:
    if not (_needs_default_multiples(selection) and business_type_id):
        return selection

    resolved = _database_business_type_selection(
        selection=selection,
        business_type_id=business_type_id,
        database_defaults_available=database_defaults_available,
        database_defaults=database_defaults,
        correlation_id=correlation_id,
        logger=logger,
    ) or _hardcoded_business_type_selection(
        selection=selection,
        business_type_id=business_type_id,
        correlation_id=correlation_id,
        logger=logger,
    )
    if resolved:
        return resolved

    selection = (
        _database_category_selection(
            selection=selection,
            request=request,
            database_defaults_available=database_defaults_available,
            database_defaults=database_defaults,
            correlation_id=correlation_id,
            logger=logger,
        )
        or selection
    )
    if not _missing_or_nonpositive(selection.ev_ebitda_ratio):
        return selection

    return (
        _hardcoded_category_selection(
            selection=selection,
            business_type_id=business_type_id,
            business_category=business_category,
            category_defaults_resolver=category_defaults_resolver,
            correlation_id=correlation_id,
            logger=logger,
        )
        or selection
    )


def _apply_industry_rules_selection(
    *,
    selection: DefaultBenchmarkSelection,
    industry: Optional[str],
    business_rules: Dict[str, object],
    logger: LoggerLike,
) -> DefaultBenchmarkSelection:
    if not (_missing_or_nonpositive(selection.ev_ebitda_ratio) and industry):
        return selection

    industry_key = normalize_industry_key(industry)
    industry_rules = business_rules.get("industry_multiples", {})
    industry_multiples = industry_rules.get(industry, {}) or (
        industry_rules.get(industry_key, {}) if industry_key else {}
    )
    if not industry_multiples:
        return selection

    raw_ebitda = industry_multiples.get("ebitda_multiple")
    raw_revenue = industry_multiples.get("revenue_multiple")
    logger.info(f"✓ Using industry rules for {industry_key or industry}")
    return replace(
        selection,
        ev_ebitda_ratio=to_decimal(raw_ebitda) if raw_ebitda is not None else None,
        revenue_multiple=to_decimal(raw_revenue) if raw_revenue is not None else None,
        data_source="industry_rules",
        data_source_details={
            "industry": industry,
            "normalized_industry": industry_key,
            "source": "business_rules",
        },
    )


def _database_industry_selection(
    *,
    selection: DefaultBenchmarkSelection,
    industry: str,
    industry_lower: str,
    database_defaults_available: bool,
    database_defaults: object,
    correlation_id: Optional[str],
    logger: LoggerLike,
) -> Optional[DefaultBenchmarkSelection]:
    db_industry_defaults = (
        database_defaults.get_industry_defaults(industry_lower)
        if database_defaults_available and database_defaults
        else None
    )
    if not db_industry_defaults or not db_industry_defaults.get("ev_ebitda"):
        return None

    ev_ebitda_ratio = to_decimal(db_industry_defaults.get("ev_ebitda"))
    raw_revenue = db_industry_defaults.get("ev_revenue")
    revenue_multiple = (
        to_decimal(raw_revenue) if raw_revenue is not None else ev_ebitda_ratio * Decimal("0.12")
    )
    pe_ratio = to_decimal(db_industry_defaults.get("pe", Decimal("15.0")))
    logger.info(
        f"✅ Using DATABASE industry defaults for '{industry_lower}' "
        f"(aggregated from {db_industry_defaults.get('business_types_count', 0)} types)",
        extra={
            "industry": industry_lower,
            "ev_ebitda": ev_ebitda_ratio,
            "ev_revenue": revenue_multiple,
            "correlation_id": correlation_id,
        },
    )
    return replace(
        selection,
        ev_ebitda_ratio=ev_ebitda_ratio,
        revenue_multiple=revenue_multiple,
        pe_ratio=pe_ratio,
        data_source="database_industry_default",
        data_source_details={
            "industry": industry_lower,
            "raw_industry": industry,
            "source": "database_industry_aggregate",
            "business_types_count": db_industry_defaults.get("business_types_count"),
            "note": "Aggregated from legacy synced business-type defaults",
        },
    )


def _hardcoded_industry_selection(
    *,
    selection: DefaultBenchmarkSelection,
    industry: str,
    industry_lower: str,
    business_type_id: Optional[str],
    correlation_id: Optional[str],
    logger: LoggerLike,
) -> DefaultBenchmarkSelection:
    defaults = INDUSTRY_DEFAULTS.get(
        industry_lower, {"ev_ebitda": Decimal("5.0"), "pe": Decimal("13.0")}
    )
    ev_ebitda_ratio = defaults.get("ev_ebitda", Decimal("5.0"))
    pe_ratio = defaults.get("pe", Decimal("15.0"))
    logger.warning(
        f"⚠️ FALLBACK: Using HARDCODED industry defaults for '{industry_lower}' - "
        f"Not found in database aggregate",
        extra={
            "industry": industry_lower,
            "ev_ebitda": ev_ebitda_ratio,
            "pe": pe_ratio,
            "business_type_id": business_type_id,
            "correlation_id": correlation_id,
            "fallback_severity": "LOW",
        },
    )
    return replace(
        selection,
        ev_ebitda_ratio=ev_ebitda_ratio,
        pe_ratio=pe_ratio,
        data_source="hardcoded_industry",
        data_source_details={
            "industry": industry_lower,
            "raw_industry": industry,
            "source": "hardcoded_industry_defaults",
            "warning": "Using legacy hardcoded industry fallback",
        },
    )


def _apply_industry_default_selection(
    *,
    selection: DefaultBenchmarkSelection,
    industry: Optional[str],
    business_type_id: Optional[str],
    database_defaults_available: bool,
    database_defaults: object,
    correlation_id: Optional[str],
    logger: LoggerLike,
) -> DefaultBenchmarkSelection:
    if not (_missing_or_nonpositive(selection.ev_ebitda_ratio) and industry):
        return selection

    industry_lower = normalize_industry_key(industry) or industry.lower()
    return _database_industry_selection(
        selection=selection,
        industry=industry,
        industry_lower=industry_lower,
        database_defaults_available=database_defaults_available,
        database_defaults=database_defaults,
        correlation_id=correlation_id,
        logger=logger,
    ) or _hardcoded_industry_selection(
        selection=selection,
        industry=industry,
        industry_lower=industry_lower,
        business_type_id=business_type_id,
        correlation_id=correlation_id,
        logger=logger,
    )


def _apply_generic_ebitda_fallback(
    *,
    selection: DefaultBenchmarkSelection,
    business_type_id: Optional[str],
    industry: Optional[str],
    request_country_code: Optional[str],
    business_category: BusinessTypeCategory,
    correlation_id: Optional[str],
    has_titan_enrichment: bool,
    logger: LoggerLike,
) -> DefaultBenchmarkSelection:
    if selection.ev_ebitda_ratio is not None:
        return selection

    logger.error(
        "🔴 CRITICAL FALLBACK: Using generic 8.0x EBITDA multiple - "
        "ALL data sources failed! This valuation may be inaccurate.",
        extra={
            "source": "generic_fallback",
            "reason": "no_matching_business_type",
            "business_type_id": business_type_id,
            "industry": industry,
            "country_code": (request_country_code or "unknown").upper(),
            "business_category": (
                getattr(business_category, "value", "unknown") if business_category else None
            ),
            "correlation_id": correlation_id,
            "fallback_severity": "CRITICAL",
            "has_titan_enrichment": has_titan_enrichment,
            "action_required": (
                "P0: Investigate why all of (Titan PRIORITY-1, DB PRIORITY-0, "
                "FMP PRIORITY-1, cache PRIORITY-2, calibration PRIORITY-4, "
                "industry rules PRIORITY-5/6) failed for this "
                "(business_type, country) cell. Check the Upswitch Index corpus, "
                "Titan enrichment cache TTL, and synced_business_types.json."
            ),
        },
    )
    return replace(
        selection,
        ev_ebitda_ratio=Decimal("8.0"),
        data_source="hardcoded_default",
        data_source_details={
            "source": "generic_fallback",
            "warning": "CRITICAL: Generic 8.0x fallback used - investigate data pipeline",
        },
    )


def _apply_revenue_multiple_fallback(
    *,
    selection: DefaultBenchmarkSelection,
    business_category: BusinessTypeCategory,
    category_defaults_resolver: CategoryDefaultsResolver,
    allow_untrusted_multiples_fallback: bool,
    logger: LoggerLike,
) -> DefaultBenchmarkSelection:
    if selection.revenue_multiple is not None or not allow_untrusted_multiples_fallback:
        return selection

    if business_category:
        category_defaults = category_defaults_resolver(business_category)
        if category_defaults and category_defaults.get("ev_revenue"):
            revenue_multiple = category_defaults.get("ev_revenue")
            logger.info(
                f"Using category default revenue multiple: {revenue_multiple}",
                extra={"business_category": getattr(business_category, "value", "unknown")},
            )
            return replace(selection, revenue_multiple=revenue_multiple)

        revenue_multiple = selection.ev_ebitda_ratio * Decimal("0.12")
        logger.info(
            f"Estimated revenue multiple from EBITDA multiple: {revenue_multiple}",
            extra={
                "ev_ebitda_ratio": selection.ev_ebitda_ratio,
                "estimation_method": "ebitda_multiple × 0.12",
            },
        )
        return replace(selection, revenue_multiple=revenue_multiple)

    logger.warning(
        "DISCLOSED FALLBACK: Revenue multiple not found, using untrusted 1.0x fallback",
        extra={"source": "disclosed_untrusted_fallback"},
    )
    return replace(selection, revenue_multiple=Decimal("1.0"))


def _validate_final_selection(
    *,
    selection: DefaultBenchmarkSelection,
    allow_untrusted_multiples_fallback: bool,
    business_type_id: Optional[str],
    request_country_code: Optional[str],
    benchmark_unavailable_exception: BenchmarkUnavailableBuilder,
    benchmark_contract: Optional[Dict[str, object]],
    logger: LoggerLike,
) -> DefaultBenchmarkSelection:
    if _missing_or_nonpositive(selection.ev_ebitda_ratio):
        if not allow_untrusted_multiples_fallback:
            raise benchmark_unavailable_exception(
                business_type_id=business_type_id,
                country_code=request_country_code,
                reason="no_usable_ev_ebitda_multiple",
                benchmark_contract=benchmark_contract,
            )
        logger.error(
            f"DISCLOSED FALLBACK: Invalid EV/EBITDA multiple detected: {selection.ev_ebitda_ratio}, using untrusted 8.0x fallback",
            extra={"original_value": selection.ev_ebitda_ratio, "fallback_value": 8.0},
        )
        selection = replace(selection, ev_ebitda_ratio=Decimal("8.0"))

    if _missing_or_nonpositive(selection.revenue_multiple):
        if not allow_untrusted_multiples_fallback:
            raise benchmark_unavailable_exception(
                business_type_id=business_type_id,
                country_code=request_country_code,
                reason="no_usable_ev_revenue_multiple",
                benchmark_contract=benchmark_contract,
            )
        logger.error(
            f"DISCLOSED FALLBACK: Invalid revenue multiple detected: {selection.revenue_multiple}, using untrusted 1.0x fallback",
            extra={"original_value": selection.revenue_multiple, "fallback_value": 1.0},
        )
        selection = replace(selection, revenue_multiple=Decimal("1.0"))

    return selection


def apply_default_benchmark_selection(
    *,
    ev_ebitda_ratio: Optional[Decimal],
    revenue_multiple: Optional[Decimal],
    pe_ratio: Decimal,
    data_source: str,
    data_source_details: Dict[str, object],
    business_type_id: Optional[str],
    business_category: BusinessTypeCategory,
    request: object,
    industry: Optional[str],
    correlation_id: Optional[str],
    request_country_code: Optional[str],
    allow_untrusted_multiples_fallback: bool,
    business_rules: Dict[str, object],
    database_defaults_available: bool,
    database_defaults: object,
    category_defaults_resolver: CategoryDefaultsResolver,
    benchmark_unavailable_exception: BenchmarkUnavailableBuilder,
    benchmark_contract: Optional[Dict[str, object]],
    logger: LoggerLike,
    has_titan_enrichment: bool = False,
) -> DefaultBenchmarkSelection:
    """Apply disclosed legacy defaults and final validation after primary sources fail."""
    selection = DefaultBenchmarkSelection(
        ev_ebitda_ratio=ev_ebitda_ratio,
        revenue_multiple=revenue_multiple,
        pe_ratio=pe_ratio,
        data_source=data_source,
        data_source_details=data_source_details,
    )
    selection = _apply_business_type_default_selection(
        selection=selection,
        business_type_id=business_type_id,
        business_category=business_category,
        request=request,
        database_defaults_available=database_defaults_available,
        database_defaults=database_defaults,
        category_defaults_resolver=category_defaults_resolver,
        correlation_id=correlation_id,
        logger=logger,
    )
    selection = _apply_industry_rules_selection(
        selection=selection,
        industry=industry,
        business_rules=business_rules,
        logger=logger,
    )
    selection = _apply_industry_default_selection(
        selection=selection,
        industry=industry,
        business_type_id=business_type_id,
        database_defaults_available=database_defaults_available,
        database_defaults=database_defaults,
        correlation_id=correlation_id,
        logger=logger,
    )
    selection = _apply_generic_ebitda_fallback(
        selection=selection,
        business_type_id=business_type_id,
        industry=industry,
        request_country_code=request_country_code,
        business_category=business_category,
        correlation_id=correlation_id,
        has_titan_enrichment=has_titan_enrichment,
        logger=logger,
    )
    selection = _apply_revenue_multiple_fallback(
        selection=selection,
        business_category=business_category,
        category_defaults_resolver=category_defaults_resolver,
        allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
        logger=logger,
    )
    return _validate_final_selection(
        selection=selection,
        allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
        business_type_id=business_type_id,
        request_country_code=request_country_code,
        benchmark_unavailable_exception=benchmark_unavailable_exception,
        benchmark_contract=benchmark_contract,
        logger=logger,
    )
