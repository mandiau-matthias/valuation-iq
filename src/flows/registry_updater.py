from src.utils.exceptions import APIError, CacheError, CalculationError

"""
Registry Data Update Flows for Upswitch
Automated updates for company registry data with intelligent caching

Features:
- Weekly registry data refresh
- Popular company updates (daily)
- Cache warming for frequently requested companies
- Data quality monitoring
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

from src.config import get_settings
from src.registry.titan_kbo_client import TitanKBOClient, TitanRegistryUnavailable
from src.services.market.market_cache_service import MarketDataCacheService, CacheDataType
from src.database.redis_client import initialize_redis

logger = get_logger(__name__)


@task(name="update_company_registry", retries=3, retry_delay_seconds=30)
async def update_company_registry(company_numbers: List[str]) -> Dict[str, Any]:
    """Refresh cached Belgian registry identity through Titan."""
    task_logger = get_run_logger()
    task_logger.info(f"Updating registry data for {len(company_numbers)} companies")

    try:
        titan_kbo = TitanKBOClient(get_settings().titan_api_url)
        results = {}

        for company_number in company_numbers:
            try:
                data = await titan_kbo.get_company_details(company_number)
                if data is None:
                    task_logger.info("Titan KBO company not found: %s", company_number)
                    continue

                results[company_number] = {
                    'company_number': company_number,
                    'data': data,
                    'updated_at': datetime.utcnow().isoformat(),
                    'source': 'titan_kbo'
                }

            except (CalculationError, TitanRegistryUnavailable) as e:
                task_logger.warning(f"Failed to update {company_number}: {e}")
                continue

        task_logger.info(f"Updated {len(results)}/{len(company_numbers)} companies")
        return results

    except CacheError as e:
        task_logger.error(f"Error updating registry data: {e}")
        raise


@task(name="cache_registry_data", retries=2, retry_delay_seconds=10)
async def cache_registry_data(registry_data: Dict[str, Any]) -> Dict[str, bool]:
    """Store registry data in cache"""
    task_logger = get_run_logger()
    task_logger.info("Caching registry data")

    try:
        redis_client = await initialize_redis()
        cache_service = MarketDataCacheService(
            redis_client=redis_client.get_client()
        )

        results = {}

        for company_number, value in registry_data.items():
            try:
                await cache_service.get_or_fetch(
                    data_type=CacheDataType.COMPANY_FINANCIALS,
                    primary_key=company_number,
                    fetch_function=lambda: value['data'],
                    force_refresh=True
                )
                results[company_number] = True
            except APIError as e:
                task_logger.error(f"Failed to cache {company_number}: {e}")
                results[company_number] = False

        task_logger.info(f"Cached {sum(results.values())}/{len(results)} companies")
        return results

    except CacheError as e:
        task_logger.error(f"Error caching registry data: {e}")
        raise


@flow(
    name="weekly_registry_update",
    description="Weekly cache refresh through Titan's KBO registry",
    task_runner=ConcurrentTaskRunner() if PREFECT_AVAILABLE else None,
    retries=1
)
async def weekly_registry_update(company_numbers: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Weekly registry data update flow
    Run via cron: 0 3 * * 0 (3 AM every Sunday)
    """
    flow_logger = get_run_logger()
    flow_logger.info("Starting weekly registry update")

    # Default to popular companies if none provided
    if company_numbers is None:
        company_numbers = []  # Get from database of frequently requested companies

    try:
        # Phase 1: Collect registry data
        flow_logger.info("Phase 1: Collecting registry data")
        registry_data = await update_company_registry(company_numbers)

        # Phase 2: Cache data
        flow_logger.info("Phase 2: Caching registry data")
        cache_results = await cache_registry_data(registry_data)

        results = {
            'update_date': datetime.utcnow().isoformat(),
            'companies_processed': len(registry_data),
            'cache_results': cache_results,
            'pipeline_status': 'SUCCESS' if all(cache_results.values()) else 'PARTIAL',
            'completion_timestamp': datetime.utcnow().isoformat()
        }

        flow_logger.info(f"Weekly registry update completed: {results['pipeline_status']}")
        return results

    except APIError as e:
        flow_logger.error(f"Weekly registry update failed: {e}")
        raise


@flow(name="update_popular_companies", description="Daily update for frequently requested companies")
async def update_popular_companies() -> Dict[str, Any]:
    """
    Daily update for popular companies
    Run via cron: 0 4 * * * (4 AM daily)
    """
    flow_logger = get_run_logger()
    flow_logger.info("Starting popular companies update")

    try:
        # Get top 100 frequently requested companies from analytics
        # TODO: Implement analytics tracking
        popular_companies = []  # Placeholder

        if not popular_companies:
            flow_logger.info("No popular companies to update")
            return {
                'pipeline_status': 'SKIPPED',
                'reason': 'No popular companies identified',
                'completion_timestamp': datetime.utcnow().isoformat()
            }

        results = await weekly_registry_update(popular_companies)
        return results

    except CacheError as e:
        flow_logger.error(f"Popular companies update failed: {e}")
        raise


@flow(name="registry_cache_warming", description="Warm cache for specific companies")
async def registry_cache_warming(company_numbers: List[str]) -> Dict[str, Any]:
    """
    Warm cache for specific companies
    Use for: Pre-launch data loading, post-deployment cache warming
    """
    flow_logger = get_run_logger()
    flow_logger.info(f"Warming cache for {len(company_numbers)} companies")

    try:
        results = await weekly_registry_update(company_numbers)
        return results

    except CacheError as e:
        flow_logger.error(f"Cache warming failed: {e}")
        raise


def get_weekly_update_deployment():
    """Get deployment configuration for weekly registry update"""
    if not PREFECT_AVAILABLE:
        logger.warning("Prefect not installed - deployment configuration not available")
        return None

    from prefect.deployments import Deployment
    from prefect.server.schemas.schedules import CronSchedule

    deployment = Deployment.build_from_flow(
        flow=weekly_registry_update,
        name="weekly-registry-update",
        schedule=CronSchedule(cron="0 3 * * 0"),  # 3 AM every Sunday
        work_queue_name="registry-data",
        description="Weekly refresh of company registry data",
        tags=["production", "weekly", "registry", "upswitch"],
        parameters={},
    )

    return deployment


if __name__ == "__main__":
    import asyncio

    async def test_registry_update():
        """Test registry update flow"""
        logger.info("Testing registry update...")
        try:
            result = await weekly_registry_update(
                company_numbers=['0123456789']  # Test company number
            )
            logger.info(f"Update result: {result}")
        except Exception as e:
            logger.error(f"Update failed: {e}"
)

    asyncio.run(test_registry_update())
