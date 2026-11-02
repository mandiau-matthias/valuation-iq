from src.utils.exceptions import DataQualityError, DataValidationError

"""
Data Quality Monitoring Flows
Monitor and validate data quality across all pipelines

Features:
- Data freshness checks
- API health monitoring
- Quality score calculation
- Automated alerting
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import asyncio

try:
    from prefect import flow, task, get_run_logger
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

from src.services.market.market_cache_service import MarketDataCacheService
from src.database.redis_client import initialize_redis

logger = get_logger(__name__)


@task(name="check_cache_freshness", retries=2)
async def check_cache_freshness() -> Dict[str, Any]:
    """Check freshness of cached data"""
    task_logger = get_run_logger()
    task_logger.info("Checking cache freshness")

    try:
        redis_client = await initialize_redis()
        cache_service = MarketDataCacheService(
            redis_client=redis_client.get_client()
        )

        stats = await cache_service.get_stats()

        freshness = {
            'cache_hit_rate': stats.get('hit_rate', 0),
            'total_entries': stats.get('total_entries', 0),
            'stale_entries': 0,  # TODO: Implement stale detection
            'last_refresh': stats.get('last_refresh', 'unknown'),
            'status': 'HEALTHY' if stats.get('hit_rate', 0) > 0.5 else 'DEGRADED'
        }

        return freshness

    except DataValidationError as e:
        task_logger.error(f"Cache freshness check failed: {e}")
        return {'status': 'ERROR', 'error': str(e)}


@task(name="monitor_api_endpoints", retries=2)
async def monitor_api_endpoints() -> Dict[str, Any]:
    """Monitor health of external API endpoints"""
    task_logger = get_run_logger()
    task_logger.info("Monitoring API endpoints")

    endpoints = {
        'fmp': 'https://financialmodelingprep.com',
        'oecd': 'https://stats.oecd.org',
        'ecb': 'https://data.ecb.europa.eu',
        # Belgian registry readiness is Titan-owned. Never probe KBO directly
        # from ValuationIQ.
        'titan_kbo': f"{get_settings().titan_api_url.rstrip('/')}/health/kbo"
    }

    results = {}

    for name, url in endpoints.items():
        try:
            # TODO: Implement actual health check
            results[name] = {
                'status': 'UP',
                'response_time_ms': 0,
                'last_check': datetime.utcnow().isoformat()
            }
        except DataValidationError as e:
            results[name] = {
                'status': 'DOWN',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }

    overall_health = 'HEALTHY' if all(r['status'] == 'UP' for r in results.values()) else 'DEGRADED'

    return {
        'endpoints': results,
        'overall_status': overall_health,
        'checked_at': datetime.utcnow().isoformat()
    }


@task(name="calculate_quality_score", retries=1)
async def calculate_quality_score(
    cache_freshness: Dict[str, Any],
    api_health: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate overall data quality score"""
    task_logger = get_run_logger()
    task_logger.info("Calculating data quality score")

    try:
        # Calculate quality score (0-100)
        cache_score = 50 if cache_freshness.get('status') == 'HEALTHY' else 25
        api_score = 50 if api_health.get('overall_status') == 'HEALTHY' else 25

        total_score = cache_score + api_score

        quality = {
            'overall_score': total_score,
            'cache_contribution': cache_score,
            'api_contribution': api_score,
            'status': 'GOOD' if total_score >= 75 else 'DEGRADED' if total_score >= 50 else 'CRITICAL',
            'calculated_at': datetime.utcnow().isoformat()
        }

        return quality

    except DataValidationError as e:
        task_logger.error(f"Quality score calculation failed: {e}")
        return {'status': 'ERROR', 'error': str(e)}


@flow(
    name="validate_data_quality",
    description="Validate data quality across all pipelines"
)
async def validate_data_quality() -> Dict[str, Any]:
    """
    Main data quality validation flow
    Run every 1 hour via cron: 0 * * * *
    """
    flow_logger = get_run_logger()
    flow_logger.info("Starting data quality validation")

    try:
        # Phase 1: Check cache freshness
        flow_logger.info("Phase 1: Checking cache freshness")
        cache_freshness = await check_cache_freshness()

        # Phase 2: Monitor API health
        flow_logger.info("Phase 2: Monitoring API endpoints")
        api_health = await monitor_api_endpoints()

        # Phase 3: Calculate quality score
        flow_logger.info("Phase 3: Calculating quality score")
        quality_score = await calculate_quality_score(cache_freshness, api_health)

        results = {
            'validation_timestamp': datetime.utcnow().isoformat(),
            'cache_freshness': cache_freshness,
            'api_health': api_health,
            'quality_score': quality_score,
            'pipeline_status': 'SUCCESS' if quality_score['status'] in ['GOOD', 'DEGRADED'] else 'FAILED'
        }

        flow_logger.info(f"Data quality validation completed: {results['pipeline_status']}")
        return results

    except DataValidationError as e:
        flow_logger.error(f"Data quality validation failed: {e}")
        raise


@flow(name="monitor_api_health", description="Monitor health of external APIs")
async def monitor_api_health() -> Dict[str, Any]:
    """
    Monitor API health
    Run every 5 minutes via cron: */5 * * * *
    """
    flow_logger = get_run_logger()
    flow_logger.info("Starting API health monitoring")

    try:
        api_health = await monitor_api_endpoints()
        return api_health

    except DataQualityError as e:
        flow_logger.error(f"API health monitoring failed: {e}")
        raise


@flow(name="generate_quality_report", description="Generate daily data quality report")
async def generate_quality_report() -> Dict[str, Any]:
    """
    Generate daily quality report
    Run daily at 6 AM via cron: 0 6 * * *
    """
    flow_logger = get_run_logger()
    flow_logger.info("Generating daily quality report")

    try:
        # Run full validation
        validation_results = await validate_data_quality()

        # Generate report
        report = {
            'report_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'validation_results': validation_results,
            'summary': {
                'overall_status': validation_results['quality_score']['status'],
                'cache_status': validation_results['cache_freshness']['status'],
                'api_status': validation_results['api_health']['overall_status'],
                'quality_score': validation_results['quality_score']['overall_score']
            },
            'generated_at': datetime.utcnow().isoformat()
        }

        flow_logger.info(f"Quality report generated: {report['summary']['overall_status']}")
        return report

    except DataValidationError as e:
        flow_logger.error(f"Quality report generation failed: {e}")
        raise


def get_quality_monitoring_deployment():
    """Get deployment configuration for quality monitoring"""
    if not PREFECT_AVAILABLE:
        logger.warning("Prefect not installed - deployment configuration not available")
        return None

    from prefect.deployments import Deployment
    from prefect.server.schemas.schedules import CronSchedule

    deployment = Deployment.build_from_flow(
        flow=validate_data_quality,
        name="data-quality-monitoring",
        schedule=CronSchedule(cron="0 * * * *"),  # Every hour
        work_queue_name="monitoring",
        description="Hourly data quality validation",
        tags=["production", "monitoring", "quality", "upswitch"],
        parameters={},
    )

    return deployment


if __name__ == "__main__":
    import asyncio

    async def test_quality_monitoring():
        """Test quality monitoring flow"""
        logger.info("Testing quality monitoring...")
        try:
            result = await validate_data_quality()
            logger.info(f"Quality validation result: {result}")
        except DataValidationError as e:
            logger.error(f"Quality validation failed: {e}")

    asyncio.run(test_quality_monitoring())
