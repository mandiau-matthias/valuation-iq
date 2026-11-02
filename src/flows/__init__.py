"""
Prefect Flows for Upswitch Valuation Engine
Adapted from Ilara Aphrodite's proven data collection patterns

Automated data collection and processing:
- Market data refresh (daily)
- Registry data updates (weekly)
- Cache warming (on-demand)
- Data quality monitoring
"""

from .market_data_collector import (
    daily_market_data_collection,
    multi_source_collection,
    scheduled_market_refresh,
    backfill_market_data
)

from .registry_updater import (
    weekly_registry_update,
    update_popular_companies,
    registry_cache_warming
)

from .data_quality import (
    validate_data_quality,
    monitor_api_health,
    generate_quality_report
)

__all__ = [
    # Market data flows
    'daily_market_data_collection',
    'multi_source_collection',
    'scheduled_market_refresh',
    'backfill_market_data',

    # Registry flows
    'weekly_registry_update',
    'update_popular_companies',
    'registry_cache_warming',

    # Data quality
    'validate_data_quality',
    'monitor_api_health',
    'generate_quality_report',
]
