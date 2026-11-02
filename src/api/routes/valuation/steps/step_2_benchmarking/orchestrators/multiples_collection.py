"""
Multiples collection support for Step 2 benchmarking.
"""

from __future__ import annotations

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory


async def collect_multiples(
    *,
    request,
    ebitda,
    ebitda_margin,
    business_category: BusinessTypeCategory | None,
    comparables_data: dict,
    correlation_id: str | None,
    industry_benchmark_collector,
    market_data_collector,
    logger,
) -> tuple[dict, dict]:
    multiples_data = await industry_benchmark_collector.select_multiples(
        request,
        ebitda,
        ebitda_margin,
        business_category,
        comparables_data,
        correlation_id=correlation_id,
        market_data_collector=market_data_collector,
    )

    if multiples_data and isinstance(multiples_data, dict):
        multiples_data_backup = multiples_data.copy()
        logger.debug(
            "Step 2: Created multiples_data_backup after database lookup",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "backup_keys": list(multiples_data_backup.keys()),
                "backup_data_source": multiples_data_backup.get("data_source"),
                "backup_ev_ebitda": (
                    str(multiples_data_backup.get("ev_ebitda"))
                    if multiples_data_backup.get("ev_ebitda") is not None
                    else None
                ),
                "backup_ev_revenue": (
                    str(multiples_data_backup.get("ev_revenue"))
                    if multiples_data_backup.get("ev_revenue") is not None
                    else None
                ),
            },
        )
    else:
        multiples_data_backup = {}

    return multiples_data, multiples_data_backup
