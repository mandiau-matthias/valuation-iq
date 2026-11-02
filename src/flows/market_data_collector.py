from src.utils.exceptions import APIError, CacheError, ConfigurationError, ExternalServiceError, MultiplesCalculationError, ValuationRangeError

"""
Market Data Collection Flows for Upswitch
Adapted from Ilara Aphrodite's Prefect patterns

Automates collection of PUBLIC market data:
- Industry multiples (FMP)
- Economic indicators (OECD, ECB)
- Exchange rates
- Sector benchmarks

ALL data is PUBLIC and cached using Ilara pattern.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asyncio

try:
    from prefect import flow, task, get_run_logger
    from prefect.task_runners import ConcurrentTaskRunner
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    # Fallback decorators
    def flow(**kwargs):
        def decorator(func):
            return func
        return decorator
    def task(**kwargs):
        def decorator(func):
            return func
        return decorator
    def get_run_logger():
        from src.utils.logging import get_logger
        return logging.getLogger(__name__)

from src.utils.logging import get_logger

from src.adapters.fmp_adapter import FMPAdapter
from src.adapters.oecd_adapter import OECDAdapter
from src.adapters.ecb_adapter import ECBAdapter
from src.services.market.market_cache_service import MarketDataCacheService, CacheDataType
from src.database.redis_client import initialize_redis

logger = get_logger(__name__)


# =============================================================================
# DATA COLLECTION TASKS (Ilara Pattern)
# =============================================================================

@task(name="collect_industry_multiples", retries=3, retry_delay_seconds=30)
async def collect_industry_multiples(industries: List[str], countries: List[str]) -> Dict[str, Any]:
    """
    Collect industry multiples from FMP
    Adapted from Ilara's collect_google_trends_raw
    """
    task_logger = get_run_logger()
    task_logger.info(f"Collecting industry multiples for {len(industries)} industries")

    try:
        fmp_adapter = FMPAdapter()
        results = {}

        for industry in industries:
            for country in countries:
                try:
                    data = await fmp_adapter.get_industry_multiples(
                        industry=industry,
                        country=country
                    )

                    key = f"{industry}_{country}"
                    results[key] = {
                        'industry': industry,
                        'country': country,
                        'data': data,
                        'collected_at': datetime.utcnow().isoformat(),
                        'source': 'fmp'
                    }

                    # Rate limiting
                    await asyncio.sleep(1)

                except MultiplesCalculationError as e:
                    task_logger.warning(f"Failed to collect multiples for {industry}/{country}: {e}")
                    continue

        task_logger.info(f"Collected {len(results)} industry multiple datasets")
        return results

    except MultiplesCalculationError as e:
        task_logger.error(f"Error in industry multiples collection: {e}")
        raise


@task(name="collect_economic_indicators", retries=3, retry_delay_seconds=30)
async def collect_economic_indicators(countries: List[str]) -> Dict[str, Any]:
    """
    Collect economic indicators from OECD
    Adapted from Ilara's collect_youtube_trends_raw
    """
    task_logger = get_run_logger()
    task_logger.info(f"Collecting economic indicators for {len(countries)} countries")

    try:
        oecd_adapter = OECDAdapter()
        results = {}

        for country in countries:
            try:
                data = await oecd_adapter.get_economic_indicators(
                    country=country
                )

                results[country] = {
                    'country': country,
                    'data': data,
                    'collected_at': datetime.utcnow().isoformat(),
                    'source': 'oecd'
                }

                # Rate limiting
                await asyncio.sleep(2)

            except Exception as e:
                task_logger.warning(f"Failed to collect indicators for {country}: {e}")
                continue

        task_logger.info(f"Collected economic indicators for {len(results)} countries")
        return results

    except Exception as e:
        task_logger.error(f"Error in economic indicators collection: {e}")
        raise


@task(name="collect_interest_rates", retries=3, retry_delay_seconds=30)
async def collect_interest_rates(countries: List[str]) -> Dict[str, Any]:
    """Collect interest rates from ECB"""
    task_logger = get_run_logger()
    task_logger.info(f"Collecting interest rates for {len(countries)} countries")

    try:
        ecb_adapter = ECBAdapter()
        results = {}

        for country in countries:
            try:
                data = await ecb_adapter.get_interest_rates(
                    country=country
                )

                results[country] = {
                    'country': country,
                    'data': data,
                    'collected_at': datetime.utcnow().isoformat(),
                    'source': 'ecb'
                }

                await asyncio.sleep(1)

            except Exception as e:
                task_logger.warning(f"Failed to collect rates for {country}: {e}")
                continue

        task_logger.info(f"Collected interest rates for {len(results)} countries")
        return results

    except CacheError as e:
        task_logger.error(f"Error in interest rates collection: {e}")
        raise


@task(name="store_in_cache", retries=2, retry_delay_seconds=10)
async def store_in_cache(
    industry_data: Dict[str, Any],
    economic_data: Dict[str, Any],
    rates_data: Dict[str, Any]
) -> Dict[str, bool]:
    """
    Store collected data in cache
    Adapted from Ilara's store_raw_data
    """
    task_logger = get_run_logger()
    task_logger.info("Storing collected data in cache")

    try:
        # Initialize Redis and cache service
        redis_client = await initialize_redis()
        cache_service = MarketDataCacheService(
            redis_client=redis_client.get_client()
        )

        results = {}

        # Store industry multiples
        for key, value in industry_data.items():
            try:
                await cache_service.get_or_fetch(
                    data_type=CacheDataType.INDUSTRY_MULTIPLES,
                    primary_key=value['industry'],
                    fetch_function=lambda: value['data'],
                    query_params={'country': value['country']},
                    force_refresh=True
                )
                results[f"industry_{key}"] = True
            except MultiplesCalculationError as e:
                task_logger.error(f"Failed to cache {key}: {e}")
                results[f"industry_{key}"] = False

        # Store economic indicators
        for country, value in economic_data.items():
            try:
                await cache_service.get_or_fetch(
                    data_type=CacheDataType.ECONOMIC_INDICATORS,
                    primary_key=country,
                    fetch_function=lambda: value['data'],
                    force_refresh=True
                )
                results[f"economic_{country}"] = True
            except APIError as e:
                task_logger.error(f"Failed to cache economic data for {country}: {e}")
                results[f"economic_{country}"] = False

        # Store interest rates
        for country, value in rates_data.items():
            try:
                await cache_service.get_or_fetch(
                    data_type=CacheDataType.ECONOMIC_INDICATORS,
                    primary_key=f"{country}_rates",
                    fetch_function=lambda: value['data'],
                    force_refresh=True
                )
                results[f"rates_{country}"] = True
            except APIError as e:
                task_logger.error(f"Failed to cache rates for {country}: {e}")
                results[f"rates_{country}"] = False

        task_logger.info(f"Cached {sum(results.values())}/{len(results)} datasets")
        return results

    except CacheError as e:
        task_logger.error(f"Error storing data in cache: {e}")
        raise


# =============================================================================
# MAIN COLLECTION FLOWS (Ilara Pattern)
# =============================================================================

@flow(
    name="daily_market_data_collection",
    description="Daily market data collection pipeline (Ilara Aphrodite pattern)",
    task_runner=ConcurrentTaskRunner() if PREFECT_AVAILABLE else None,
    retries=1,
    retry_delay_seconds=300
)
async def daily_market_data_collection(
    industries: Optional[List[str]] = None,
    countries: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Main daily market data collection flow
    Adapted from Ilara's daily_trend_collection

    Pipeline:
    1. Collect market data from multiple sources (parallel)
    2. Store in cache with 7-day TTL
    3. Validate data quality
    """
    flow_logger = get_run_logger()
    flow_logger.info("Starting daily market data collection")

    # Default industries and countries
    if industries is None:
        industries = ['technology', 'healthcare', 'finance', 'manufacturing', 'retail']
    if countries is None:
        countries = ['BE', 'NL', 'DE', 'FR', 'UK']

    collection_date = datetime.utcnow()

    try:
        # PHASE 1: Parallel Data Collection (Ilara pattern)
        flow_logger.info("Phase 1: Collecting data from sources")

        industry_future = collect_industry_multiples(industries, countries)
        economic_future = collect_economic_indicators(countries)
        rates_future = collect_interest_rates(countries)

        # Wait for all collections
        industry_data = await industry_future
        economic_data = await economic_future
        rates_data = await rates_future

        # PHASE 2: Store in Cache
        flow_logger.info("Phase 2: Storing data in cache")

        cache_results = await store_in_cache(industry_data, economic_data, rates_data)

        # PHASE 3: Validate Quality
        flow_logger.info("Phase 3: Validating data quality")

        quality_metrics = {
            'total_collected': len(industry_data) + len(economic_data) + len(rates_data),
            'successfully_cached': sum(cache_results.values()),
            'cache_failures': len(cache_results) - sum(cache_results.values()),
            'collection_date': collection_date.isoformat()
        }

        # Compile results
        results = {
            'collection_date': collection_date.isoformat(),
            'data_collected': {
                'industry_multiples': len(industry_data),
                'economic_indicators': len(economic_data),
                'interest_rates': len(rates_data)
            },
            'cache_results': cache_results,
            'quality_metrics': quality_metrics,
            'pipeline_status': 'SUCCESS' if quality_metrics['cache_failures'] == 0 else 'PARTIAL',
            'completion_timestamp': datetime.utcnow().isoformat()
        }

        flow_logger.info(f"Daily market data collection completed: {results['pipeline_status']}")
        return results

    except MultiplesCalculationError as e:
        flow_logger.error(f"Daily market data collection failed: {e}")
        raise


@flow(
    name="multi_source_collection",
    description="Collect from multiple data sources in parallel",
    task_runner=ConcurrentTaskRunner() if PREFECT_AVAILABLE else None
)
async def multi_source_collection(
    sources: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Collect from multiple data sources
    Adapted from Ilara's multi_niche_collection
    """
    flow_logger = get_run_logger()

    if sources is None:
        sources = ['fmp', 'oecd', 'ecb']

    flow_logger.info(f"Starting multi-source collection: {sources}")

    try:
        # Run collection for each source
        results = await daily_market_data_collection()

        return {
            'sources_processed': sources,
            'results': results,
            'overall_status': results.get('pipeline_status', 'UNKNOWN'),
            'completion_timestamp': datetime.utcnow().isoformat()
        }

    except ExternalServiceError as e:
        flow_logger.error(f"Multi-source collection failed: {e}")
        raise


@flow(
    name="scheduled_market_refresh",
    description="Scheduled daily market data refresh",
    task_runner=ConcurrentTaskRunner() if PREFECT_AVAILABLE else None
)
async def scheduled_market_refresh() -> Dict[str, Any]:
    """
    Scheduled daily collection
    Adapted from Ilara's scheduled_daily_collection

    Run via cron: 0 2 * * * (2 AM daily)
    """
    flow_logger = get_run_logger()
    flow_logger.info("Starting scheduled market data refresh")

    try:
        results = await daily_market_data_collection()

        if results['pipeline_status'] == 'SUCCESS':
            flow_logger.info("Scheduled refresh completed successfully")
        else:
            flow_logger.warning(f"Scheduled refresh completed with issues: {results['pipeline_status']}")

        return results

    except ValuationRangeError as e:
        flow_logger.error(f"Scheduled refresh failed: {e}")
        raise


@flow(name="backfill_market_data", description="Backfill market data for date range")
async def backfill_market_data(
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """
    Backfill market data
    Adapted from Ilara's backfill_trends
    """
    flow_logger = get_run_logger()
    flow_logger.info(f"Starting backfill from {start_date} to {end_date}")

    try:
        current_date = start_date
        backfill_results = {}

        while current_date <= end_date:
            flow_logger.info(f"Backfilling data for {current_date.strftime('%Y-%m-%d')}")

            try:
                result = await daily_market_data_collection()
                backfill_results[current_date.strftime('%Y-%m-%d')] = result

                await asyncio.sleep(10)

            except ExternalServiceError as e:
                flow_logger.error(f"Backfill failed for {current_date}: {e}")
                backfill_results[current_date.strftime('%Y-%m-%d')] = {
                    'pipeline_status': 'FAILED',
                    'error': str(e)
                }

            current_date += timedelta(days=1)

        overall_results = {
            'backfill_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_days': (end_date - start_date).days + 1
            },
            'successful_days': len([r for r in backfill_results.values() if r.get('pipeline_status') == 'SUCCESS']),
            'failed_days': len([r for r in backfill_results.values() if r.get('pipeline_status') == 'FAILED']),
            'daily_results': backfill_results,
            'completion_timestamp': datetime.utcnow().isoformat()
        }

        flow_logger.info(f"Backfill completed: {overall_results['successful_days']}/{overall_results['backfill_period']['total_days']} days successful")
        return overall_results

    except ConfigurationError as e:
        flow_logger.error(f"Backfill operation failed: {e}")
        raise


# =============================================================================
# DEPLOYMENT CONFIGURATION
# =============================================================================

def get_daily_collection_deployment():
    """
    Get deployment configuration for daily market data collection
    Run: prefect deployment apply
    """
    if not PREFECT_AVAILABLE:
        logger.warning("Prefect not installed - deployment configuration not available")
        return None

    from prefect.deployments import Deployment
    from prefect.server.schemas.schedules import CronSchedule

    deployment = Deployment.build_from_flow(
        flow=scheduled_market_refresh,
        name="daily-market-data-refresh",
        schedule=CronSchedule(cron="0 2 * * *"),  # 2 AM daily
        work_queue_name="market-data",
        description="Daily market data collection - runs at 2 AM UTC",
        tags=["production", "daily", "market-data", "upswitch"],
        parameters={},
    )

    return deployment


if __name__ == "__main__":
    # For local testing
    import asyncio

    async def test_collection():
        """Test market data collection flow"""
        logger.info("Testing market data collection...")
        try:
            result = await daily_market_data_collection(
                industries=['technology'],
                countries=['BE']
            )
            logger.info(f"Collection result: {result}")
        except ExternalServiceError as e:
            logger.error(f"Collection failed: {e}")

    asyncio.run(test_collection())
