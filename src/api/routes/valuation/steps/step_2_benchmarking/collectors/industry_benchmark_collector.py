"""
Industry Benchmark Collector for Step 2 Benchmarking

This module collects industry benchmarks from multiple sources using a priority cascade.
Titan/Upswitch Index enrichment is the trusted runtime path for valuation multiples;
generic fallbacks require explicit caller opt-in.

FOUNDATION:
- Upswitch Index benchmark contract
- Local SME market calibration
- Published transaction, listing, and partner-contribution evidence where available

Author: Upswitch Engineering Team
Date: January 2026
Status: Production Ready (Database-Driven Defaults)
"""

from decimal import Decimal
from typing import Dict, Optional

from fastapi import HTTPException, status

from src.api.routes.valuation.benchmark_contract_utils import as_mapping as _as_mapping
from src.api.routes.valuation.benchmark_contract_utils import (
    missing_required_benchmark_provenance as _missing_required_benchmark_provenance_for_raw_contract,
)
from src.api.routes.valuation.benchmark_contract_utils import (
    normalize_benchmark_contract as _normalize_benchmark_contract,
)
from src.api.routes.valuation.benchmark_contract_utils import (
    request_allows_untrusted_multiples_fallback as _request_allows_untrusted_multiples_fallback,
)
from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory
from src.utils.country_code import normalize_iso3166_alpha2
from src.utils.data_flow_tracer import get_tracer
from src.utils.decimal_helpers import to_decimal
from src.utils.valuation_logger import ValuationLogger

# Import data source formatter
from ..utils.data_source_formatter import DataSourceFormatter
from .industry_benchmark_database_selection import apply_database_benchmark_selection
from .industry_benchmark_default_selection import apply_default_benchmark_selection
from .industry_benchmark_defaults import BUSINESS_TYPE_DEFAULTS, INDUSTRY_DEFAULTS
from .industry_benchmark_fallbacks import (
    build_fallback_multiples,
    category_id_for_business_type_category,
    hardcoded_category_defaults,
    normalize_industry_key,
)
from .industry_benchmark_market_selection import apply_market_data_benchmark_selection
from .industry_benchmark_percentiles import build_multiples_percentiles
from .industry_benchmark_selection_result import build_selected_multiples_result
from .industry_benchmark_synced_metrics import (
    _normalized_business_type_mix_from_request,
    _synced_business_type_metrics,
    _synced_business_type_mix_metrics,
)
from .industry_benchmark_titan_selection import apply_titan_benchmark_selection

# Import database-driven defaults service (optional - deleted in Brain & Muscle architecture)
try:
    from src.services.business_intelligence.database_driven_defaults import DatabaseDrivenDefaults

    DATABASE_DRIVEN_DEFAULTS_AVAILABLE = True
except ImportError:
    DATABASE_DRIVEN_DEFAULTS_AVAILABLE = False
    DatabaseDrivenDefaults = None  # type: ignore[misc, assignment]

logger = ValuationLogger(__name__)


def _benchmark_unavailable_exception(
    *,
    business_type_id: Optional[str],
    country_code: Optional[str],
    reason: str,
    benchmark_contract: Optional[Dict[str, object]] = None,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "BENCHMARK_UNAVAILABLE",
            "message": (
                "No trusted benchmark contract is available for this business type "
                "and country. The valuation engine will not silently use unlabeled "
                "generic international or hardcoded multiples."
            ),
            "business_type_id": business_type_id,
            "country_code": country_code,
            "reason": reason,
            "benchmark_contract": benchmark_contract or None,
            "remediation": (
                "Select a business type/country with a resolved benchmark "
                "contract, provide advisor-approved evidence, or explicitly set "
                "allow_untrusted_multiples_fallback=true to run a disclosed fallback."
            ),
        },
    )


class IndustryBenchmarkCollector:
    """
    Collects industry benchmarks from multiple sources using priority cascade.

    Priority Order:
    0. Titan-provided resolved benchmark contract — HIGHEST
    1. Explicitly disclosed fallback paths only when caller opts in
    2. Legacy/cache/external/default sources for non-concrete or opted-in requests

    Dependencies:
    - multiples_adapter: BusinessTypeMultiplesAdapter for DB-driven multiples
    - fmp_adapter: FMPAdapter for real-time market data (optional)
    - cache_service: MarketDataCacheService for cached data (optional)
    - market_data_collector: MarketDataCollector for FMP/cache operations (optional)
    """

    def __init__(
        self,
        multiples_adapter=None,
        fmp_adapter=None,
        cache_service=None,
        market_data_collector=None,
        business_rules: Optional[Dict[str, object]] = None,
    ):
        """
        Initialize IndustryBenchmarkCollector.

        Args:
            multiples_adapter: BusinessTypeMultiplesAdapter for DB-driven multiples
            fmp_adapter: FMPAdapter for real-time market data (optional)
            cache_service: MarketDataCacheService for cached data (optional)
            market_data_collector: MarketDataCollector for FMP/cache operations (optional)
            business_rules: Business rules configuration (optional)
        """
        self.multiples_adapter = multiples_adapter
        self.fmp_adapter = fmp_adapter
        self.cache_service = cache_service
        self.market_data_collector = market_data_collector
        self.business_rules = business_rules or {}
        self.logger = logger

    def get_category_defaults(self, category: BusinessTypeCategory) -> Optional[Dict[str, Decimal]]:
        """
        Get default multiples based on business category.

        Priority:
        1. Database-driven category defaults (aggregated from business_types DB)
        2. Hardcoded category defaults (legacy fallback)

        Args:
            category: BusinessTypeCategory enum value

        Returns:
            Dict with ev_ebitda, ev_revenue, pe or None if category not found
        """
        if category is None:
            return None

        # Try database-driven defaults first (if available - deleted in Brain & Muscle)
        category_id = category_id_for_business_type_category(category)
        if category_id and DATABASE_DRIVEN_DEFAULTS_AVAILABLE and DatabaseDrivenDefaults:
            db_defaults = DatabaseDrivenDefaults.get_category_defaults(category_id)
            if db_defaults and db_defaults.get("ev_ebitda"):
                self.logger.debug(
                    f"Using database-driven category defaults for {category.value}",
                    extra={
                        "category": category.value,
                        "category_id": category_id,
                        "ev_ebitda": db_defaults.get("ev_ebitda"),
                        "source": "database_aggregate",
                    },
                )
                return db_defaults

        # Fall back to hardcoded category defaults (legacy). These values are kept for
        # backward compatibility when database is unavailable.
        defaults = hardcoded_category_defaults(category)
        if defaults:
            self.logger.debug(
                f"Using hardcoded category defaults for {category.value} (database unavailable)",
                extra={"category": category.value, "source": "hardcoded"},
            )
        return defaults

    def get_fallback_multiples(
        self,
        business_category: Optional[BusinessTypeCategory],
        industry: Optional[str],
        business_type_id: Optional[str],
    ) -> Dict[str, Decimal]:
        """
        Calculate proper fallback multiples based on business_category/industry/business_type_id.

        This ensures Step 2 always returns correct multiples even when Step 1 fails or exceptions occur.
        Follows the same priority cascade as select_multiples but simplified for fallback scenarios.

        Priority:
        1. Business type defaults (if business_type_id matches)
        2. Business category defaults (if business_category available)
        3. Industry defaults (if industry available)
        4. Generic defaults (last resort)

        Args:
            business_category: BusinessTypeCategory enum value (optional)
            industry: Industry identifier (optional)
            business_type_id: Business type ID string (optional)

        Returns:
            Dict with ev_ebitda, ev_revenue, pe, and data_source
        """
        return build_fallback_multiples(
            business_category=business_category,
            industry=industry,
            business_type_id=business_type_id,
            category_defaults_resolver=self.get_category_defaults,
        )

    async def select_multiples(
        self,
        request,
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
        business_category: BusinessTypeCategory,
        comparables_data: Optional[Dict[str, object]] = None,
        correlation_id: Optional[str] = None,
        market_data_collector=None,
    ) -> Dict[str, object]:
        """
        Select multiples through the Titan/Upswitch Index benchmark contract.

        Valuation-grade path:
        0. Titan enrichment carrying a resolved benchmark contract.

        Disclosed fallback path:
        External/cache/default market-data branches are only usable when the
        request explicitly sets allow_untrusted_multiples_fallback=true.

        Args:
            request: ValuationRequest object
            ebitda: Company EBITDA (optional)
            ebitda_margin: EBITDA margin percentage
            business_category: BusinessTypeCategory enum value
            comparables_data: Optional comparables data with percentiles
            correlation_id: Correlation ID for logging
            market_data_collector: MarketDataCollector instance (optional)

        Returns:
            Dict with ev_ebitda, ev_revenue, pe_ratio, percentiles, and data_source
        """
        ev_ebitda_ratio = None
        revenue_multiple = None
        pe_ratio = Decimal("15.0")
        data_source = "unknown"
        data_source_details = {}

        business_type_id = getattr(request, "business_type_id", None)
        business_type_mix = _normalized_business_type_mix_from_request(request)
        industry = getattr(request, "industry", None)
        cache_business_type = None

        # Align with Titan: country for DB fallback multiples (default BE)
        _cc = getattr(request, "country_code", None)
        if not _cc:
            _fd = getattr(request, "financial_data", None)
            if _fd is not None:
                if isinstance(_fd, dict):
                    _cc = _fd.get("country_code")
                else:
                    _cc = getattr(_fd, "country_code", None)
        request_country_code = normalize_iso3166_alpha2(
            str(_cc).strip() if _cc is not None else None
        )

        if business_type_id:
            try:
                from src.database.business_types_repository import get_business_types_repository

                with get_business_types_repository() as repo:
                    cache_business_type = repo.get_business_type(business_type_id)
            except Exception as e:
                logger.warning(
                    "Failed to fetch business_type from repo for '%s': %s",
                    business_type_id,
                    e,
                )
                cache_business_type = None

        # Get correlation_id if not provided
        if correlation_id is None:
            correlation_id = getattr(request, "_correlation_id", None) or getattr(
                request, "correlation_id", None
            )

        # Check for Titan-provided enrichment data
        titan_ev_ebitda = getattr(request, "ev_ebitda_multiple", None)
        titan_ev_revenue = getattr(request, "ev_revenue_multiple", None)
        titan_pe_ratio = getattr(request, "pe_ratio", None)
        titan_multiples_metadata = getattr(request, "multiples_metadata", None)
        titan_multiples_mapping = _as_mapping(titan_multiples_metadata)
        benchmark_contract_raw = titan_multiples_mapping.get(
            "benchmark_contract"
        ) or titan_multiples_mapping.get("benchmarkContract")
        benchmark_contract = _as_mapping(benchmark_contract_raw)
        normalized_benchmark_contract = (
            _normalize_benchmark_contract(benchmark_contract) if benchmark_contract else {}
        )
        benchmark_contract_status = benchmark_contract.get("status")
        contract_metrics = normalized_benchmark_contract.get("metrics", {})

        def metric_distribution(metric_name: str) -> Optional[Dict[str, object]]:
            metric = (
                contract_metrics.get(metric_name) if isinstance(contract_metrics, dict) else None
            )
            if not isinstance(metric, dict) or metric.get("median") is None:
                return None
            return {
                "median": metric.get("median"),
                "p10": metric.get("p10"),
                "p25": metric.get("p25"),
                "p75": metric.get("p75"),
                "p90": metric.get("p90"),
            }

        if titan_ev_ebitda is None and benchmark_contract_status == "resolved":
            titan_ev_ebitda = metric_distribution("ev_ebitda")
        if titan_ev_revenue is None and benchmark_contract_status == "resolved":
            titan_ev_revenue = metric_distribution("ev_revenue")
        if titan_pe_ratio is None and benchmark_contract_status == "resolved":
            titan_pe_ratio = metric_distribution("pe_ratio")

        has_titan_enrichment = titan_ev_ebitda is not None or titan_ev_revenue is not None
        allow_untrusted_multiples_fallback = _request_allows_untrusted_multiples_fallback(request)

        # ====================================================================
        # SYNCED BUSINESS-TYPES DB — "use the DB whenever it is available"
        # When Titan did not push enrichment but the business type resolves in
        # the local business_types DB snapshot, USE its curated multiples. This
        # is the same DB the public multiples surface reads — a first-class
        # source, NOT an untrusted guess — so it is preferred over any hardcoded
        # default and satisfies the benchmark gates without allow_untrusted.
        # Absent/corrupt snapshot → metrics is {} → existing fallbacks run
        # (report generation never fails just because the DB was unreachable).
        # ====================================================================
        used_synced_business_types_db = False
        used_synced_business_type_mix_db = False
        if not has_titan_enrichment and business_type_id:
            if len(business_type_mix) > 1:
                synced_metrics = _synced_business_type_mix_metrics(
                    business_type_mix, request_country_code
                )
                used_synced_business_type_mix_db = bool(synced_metrics.get("ev_ebitda"))
            else:
                synced_metrics = _synced_business_type_metrics(
                    business_type_id, request_country_code
                )
            if synced_metrics.get("ev_ebitda"):
                titan_ev_ebitda = synced_metrics.get("ev_ebitda")
                if titan_ev_revenue is None:
                    titan_ev_revenue = synced_metrics.get("ev_revenue")
                if titan_pe_ratio is None:
                    titan_pe_ratio = synced_metrics.get("pe_ratio")
                has_titan_enrichment = True
                used_synced_business_types_db = True
                self.logger.info(
                    "🗄️ Using synced business-types DB multiples (live Titan enrichment absent)",
                    extra={
                        "business_type_id": business_type_id,
                        "business_type_mix": (
                            business_type_mix if used_synced_business_type_mix_db else None
                        ),
                        "source": "business_types_synced_db",
                        "ev_ebitda": titan_ev_ebitda,
                        "correlation_id": correlation_id,
                    },
                )

        self.logger.debug(
            "🔍 _select_multiples() START - Initial state",
            extra={
                "business_type_id": business_type_id,
                "industry": industry,
                "ebitda_margin": ebitda_margin,
                "business_category": (
                    (
                        business_category.value
                        if hasattr(business_category, "value")
                        else str(business_category)
                    )
                    if business_category
                    else None
                ),
                "initial_ev_ebitda": ev_ebitda_ratio,
                "initial_revenue_multiple": revenue_multiple,
                "correlation_id": correlation_id,
                "has_titan_enrichment": has_titan_enrichment,
                "priority_note": (
                    "Resolved Upswitch Index contract first; external/cache/default "
                    "fallbacks require explicit untrusted fallback consent"
                ),
            },
        )

        # ============================================================================
        # CRITICAL VALIDATION: Check for missing Titan enrichment
        # ============================================================================
        # When a business_type_id is provided but Titan enrichment is missing,
        # this indicates a data pipeline issue. The valuation will fall back to
        # generic defaults which may not match the benchmark contract.
        # ============================================================================
        if business_type_id and not has_titan_enrichment:
            self.logger.error(
                f"🔴 ENRICHMENT_MISSING: business_type_id '{business_type_id}' provided but "
                f"no resolved Titan/benchmark contract was received. Refusing "
                f"silent fallback multiples.",
                extra={
                    "business_type_id": business_type_id,
                    "industry": industry,
                    "business_category": (
                        (
                            business_category.value
                            if hasattr(business_category, "value")
                            else str(business_category)
                        )
                        if business_category
                        else None
                    ),
                    "correlation_id": correlation_id,
                    "severity": "CRITICAL",
                    "action_required": "Investigate why Titan did not enrich this business type",
                    "expected_source": "business_types database via Titan API",
                    "fallback_risk": "Hardcoded defaults may produce incorrect valuation",
                    "cache_business_type_found": cache_business_type is not None,
                },
            )
            if not allow_untrusted_multiples_fallback:
                raise _benchmark_unavailable_exception(
                    business_type_id=business_type_id,
                    country_code=request_country_code,
                    reason="missing_titan_enrichment",
                    benchmark_contract=benchmark_contract,
                )

        if (
            not business_type_id
            and not has_titan_enrichment
            and not allow_untrusted_multiples_fallback
        ):
            self.logger.error(
                "No business_type_id or resolved benchmark contract was provided; refusing generic multiples fallback",
                extra={
                    "industry": industry,
                    "country_code": request_country_code,
                    "correlation_id": correlation_id,
                },
            )
            raise _benchmark_unavailable_exception(
                business_type_id=None,
                country_code=request_country_code,
                reason="missing_business_type_or_benchmark_contract",
                benchmark_contract=benchmark_contract,
            )

        if (
            has_titan_enrichment
            and benchmark_contract_status != "resolved"
            and not allow_untrusted_multiples_fallback
            and not used_synced_business_types_db
        ):
            reason = (
                str(benchmark_contract_status)
                if benchmark_contract_status
                else "missing_benchmark_contract"
            )
            self.logger.error(
                "Trusted benchmark contract is missing or unavailable; refusing generic multiples fallback",
                extra={
                    "business_type_id": business_type_id,
                    "country_code": request_country_code,
                    "benchmark_contract_status": benchmark_contract_status,
                    "correlation_id": correlation_id,
                },
            )
            raise _benchmark_unavailable_exception(
                business_type_id=business_type_id,
                country_code=request_country_code,
                reason=reason,
                benchmark_contract=normalized_benchmark_contract or benchmark_contract,
            )

        if (
            has_titan_enrichment
            and benchmark_contract_status == "resolved"
            and not allow_untrusted_multiples_fallback
        ):
            missing_provenance = _missing_required_benchmark_provenance_for_raw_contract(
                benchmark_contract
            )
            if missing_provenance:
                self.logger.error(
                    "Resolved benchmark contract is missing required valuation provenance",
                    extra={
                        "business_type_id": business_type_id,
                        "country_code": request_country_code,
                        "missing_provenance": missing_provenance,
                        "correlation_id": correlation_id,
                    },
                )
                raise _benchmark_unavailable_exception(
                    business_type_id=business_type_id,
                    country_code=request_country_code,
                    reason="incomplete_benchmark_provenance",
                    benchmark_contract={
                        **normalized_benchmark_contract,
                        "missing_required_fields": missing_provenance,
                    },
                )

        # Add data flow tracer checkpoint
        try:
            tracer = get_tracer()
            tracer.checkpoint(
                "_select_multiples_start",
                revenue_multiple=revenue_multiple,
                ev_ebitda_ratio=ev_ebitda_ratio,
                context={
                    "business_type_id": business_type_id,
                    "industry": industry,
                    "business_category": (
                        (
                            business_category.value
                            if hasattr(business_category, "value")
                            else str(business_category)
                        )
                        if business_category
                        else None
                    ),
                    "has_titan_enrichment": has_titan_enrichment,
                },
                notes="Starting multiples selection with priority cascade (Titan enrichment first)",
            )
        except Exception:
            pass  # Tracer is optional

        titan_selection = apply_titan_benchmark_selection(
            has_titan_enrichment=has_titan_enrichment,
            titan_ev_ebitda=titan_ev_ebitda,
            titan_ev_revenue=titan_ev_revenue,
            titan_pe_ratio=titan_pe_ratio,
            titan_multiples_metadata=titan_multiples_metadata,
            used_synced_business_types_db=used_synced_business_types_db,
            used_synced_business_type_mix_db=used_synced_business_type_mix_db,
            business_type_id=business_type_id,
            business_type_mix=business_type_mix,
            correlation_id=correlation_id,
            normalized_benchmark_contract=normalized_benchmark_contract,
            ev_ebitda_ratio=ev_ebitda_ratio,
            revenue_multiple=revenue_multiple,
            pe_ratio=pe_ratio,
            data_source=data_source,
            data_source_details=data_source_details,
            comparables_data=comparables_data,
            logger=self.logger,
        )
        ev_ebitda_ratio = titan_selection.ev_ebitda_ratio
        revenue_multiple = titan_selection.revenue_multiple
        pe_ratio = titan_selection.pe_ratio
        data_source = titan_selection.data_source
        data_source_details = titan_selection.data_source_details
        comparables_data = titan_selection.comparables_data

        if (
            has_titan_enrichment
            and data_source != "titan_enrichment"
            and not allow_untrusted_multiples_fallback
        ):
            self.logger.error(
                "Titan enrichment was present but did not contain a usable multiple; refusing secondary/generic fallback",
                extra={
                    "business_type_id": business_type_id,
                    "country_code": request_country_code,
                    "has_titan_enrichment": has_titan_enrichment,
                    "benchmark_contract_status": benchmark_contract_status,
                    "correlation_id": correlation_id,
                },
            )
            raise _benchmark_unavailable_exception(
                business_type_id=business_type_id,
                country_code=request_country_code,
                reason="titan_enrichment_without_usable_multiple",
                benchmark_contract=benchmark_contract,
            )

        database_selection = await apply_database_benchmark_selection(
            data_source=data_source,
            business_type_id=business_type_id,
            multiples_adapter=self.multiples_adapter,
            request_country_code=request_country_code,
            correlation_id=correlation_id,
            ev_ebitda_ratio=ev_ebitda_ratio,
            revenue_multiple=revenue_multiple,
            pe_ratio=pe_ratio,
            data_source_details=data_source_details,
            logger=self.logger,
        )
        ev_ebitda_ratio = database_selection.ev_ebitda_ratio
        revenue_multiple = database_selection.revenue_multiple
        pe_ratio = database_selection.pe_ratio
        data_source = database_selection.data_source
        data_source_details = database_selection.data_source_details

        market_selection = await apply_market_data_benchmark_selection(
            data_source=data_source,
            market_data_collector=market_data_collector,
            allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
            request=request,
            industry=industry,
            ev_ebitda_ratio=ev_ebitda_ratio,
            revenue_multiple=revenue_multiple,
            pe_ratio=pe_ratio,
            data_source_details=data_source_details,
            logger=self.logger,
        )
        ev_ebitda_ratio = market_selection.ev_ebitda_ratio
        revenue_multiple = market_selection.revenue_multiple
        pe_ratio = market_selection.pe_ratio
        data_source = market_selection.data_source
        data_source_details = market_selection.data_source_details

        default_selection = apply_default_benchmark_selection(
            ev_ebitda_ratio=ev_ebitda_ratio,
            revenue_multiple=revenue_multiple,
            pe_ratio=pe_ratio,
            data_source=data_source,
            data_source_details=data_source_details,
            business_type_id=business_type_id,
            business_category=business_category,
            request=request,
            industry=industry,
            correlation_id=correlation_id,
            request_country_code=request_country_code,
            allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
            business_rules=self.business_rules,
            database_defaults_available=DATABASE_DRIVEN_DEFAULTS_AVAILABLE,
            database_defaults=DatabaseDrivenDefaults,
            category_defaults_resolver=self.get_category_defaults,
            benchmark_unavailable_exception=_benchmark_unavailable_exception,
            benchmark_contract=benchmark_contract,
            has_titan_enrichment=has_titan_enrichment,
            logger=self.logger,
        )
        ev_ebitda_ratio = default_selection.ev_ebitda_ratio
        revenue_multiple = default_selection.revenue_multiple
        pe_ratio = default_selection.pe_ratio
        data_source = default_selection.data_source
        data_source_details = default_selection.data_source_details
        percentiles = build_multiples_percentiles(
            ev_ebitda_ratio=ev_ebitda_ratio,
            revenue_multiple=revenue_multiple,
            comparables_data=comparables_data,
        )
        return build_selected_multiples_result(
            ev_ebitda_ratio=ev_ebitda_ratio,
            revenue_multiple=revenue_multiple,
            pe_ratio=pe_ratio,
            percentiles=percentiles,
            data_source=data_source,
            data_source_details=data_source_details,
            business_type_id=business_type_id,
            correlation_id=correlation_id,
            request_country_code=request_country_code,
            industry=industry,
            has_titan_enrichment=has_titan_enrichment,
            cache_business_type_found=cache_business_type is not None,
            normalized_benchmark_contract=normalized_benchmark_contract,
            logger=self.logger,
        )
