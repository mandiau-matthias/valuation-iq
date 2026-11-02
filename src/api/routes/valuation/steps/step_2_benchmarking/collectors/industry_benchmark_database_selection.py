"""Database adapter multiple selection for Step 2 benchmarks."""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass
from decimal import Decimal
from functools import partial
from typing import Dict, Optional, Protocol

from src.utils.decimal_helpers import to_decimal

from ..utils.data_source_formatter import DataSourceFormatter


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def error(self, msg: str, *args: object, **kwargs: object) -> object: ...


class MultiplesAdapterLike(Protocol):
    def get_multiples_dict(
        self, business_type_id: str, country_code: Optional[str]
    ) -> Dict[str, object]: ...


# Country names for the report's market-context line. The business-type
# benchmarks are calibrated per country, so this must never be hardcoded.
_SME_MARKET_LABELS = {
    "BE": "Belgian",
    "NL": "Dutch",
    "FR": "French",
    "DE": "German",
    "AT": "Austrian",
    "CH": "Swiss",
    "LU": "Luxembourg",
    "GB": "UK",
    "IE": "Irish",
    "ES": "Spanish",
    "IT": "Italian",
    "PT": "Portuguese",
    "DK": "Danish",
    "SE": "Swedish",
    "NO": "Norwegian",
    "FI": "Finnish",
}


def _regional_market(country_code: Optional[str]) -> str:
    label = _SME_MARKET_LABELS.get((country_code or "").strip().upper())
    return f"{label} SME market" if label else "European SME market"


@dataclass(frozen=True)
class DatabaseBenchmarkSelection:
    ev_ebitda_ratio: Optional[Decimal]
    revenue_multiple: Optional[Decimal]
    pe_ratio: Decimal
    data_source: str
    data_source_details: Dict[str, object]


async def apply_database_benchmark_selection(
    *,
    data_source: str,
    business_type_id: Optional[str],
    multiples_adapter: Optional[MultiplesAdapterLike],
    request_country_code: Optional[str],
    correlation_id: Optional[str],
    ev_ebitda_ratio: Optional[Decimal],
    revenue_multiple: Optional[Decimal],
    pe_ratio: Decimal,
    data_source_details: Dict[str, object],
    logger: LoggerLike,
) -> DatabaseBenchmarkSelection:
    """Use business-type DB multiples when Titan did not already resolve the source."""
    if data_source == "titan_enrichment" or not business_type_id or not multiples_adapter:
        return DatabaseBenchmarkSelection(
            ev_ebitda_ratio=ev_ebitda_ratio,
            revenue_multiple=revenue_multiple,
            pe_ratio=pe_ratio,
            data_source=data_source,
            data_source_details=data_source_details,
        )

    logger.info(
        f"PRIORITY 0: Attempting DB lookup for business_type_id: {business_type_id} "
        "(Titan enrichment not available)",
        extra={
            "business_type_id": business_type_id,
            "country_code": request_country_code,
            "correlation_id": correlation_id,
            "priority": "SECONDARY - Direct DB lookup when Titan enrichment unavailable",
            "has_adapter": multiples_adapter is not None,
        },
    )
    try:
        bt_multiples = await _fetch_business_type_multiples(
            multiples_adapter=multiples_adapter,
            business_type_id=business_type_id,
            request_country_code=request_country_code,
            correlation_id=correlation_id,
            logger=logger,
        )
        if not bt_multiples:
            return DatabaseBenchmarkSelection(
                ev_ebitda_ratio=ev_ebitda_ratio,
                revenue_multiple=revenue_multiple,
                pe_ratio=pe_ratio,
                data_source=data_source,
                data_source_details=data_source_details,
            )

        raw_ebitda = bt_multiples.get("ev_ebitda")
        raw_revenue = bt_multiples.get("ev_revenue")
        raw_pe = bt_multiples.get("pe")
        db_ev_ebitda = to_decimal(raw_ebitda) if raw_ebitda is not None else None
        db_ev_revenue = to_decimal(raw_revenue) if raw_revenue is not None else None
        db_pe = to_decimal(raw_pe) if raw_pe is not None else Decimal("15.0")

        if not _has_valid_database_multiple(db_ev_ebitda, db_ev_revenue):
            return DatabaseBenchmarkSelection(
                ev_ebitda_ratio=ev_ebitda_ratio,
                revenue_multiple=revenue_multiple,
                pe_ratio=pe_ratio,
                data_source=data_source,
                data_source_details=data_source_details,
            )

        if db_ev_ebitda is not None and db_ev_ebitda > 0:
            ev_ebitda_ratio = db_ev_ebitda
        if db_ev_revenue is not None and db_ev_revenue > 0:
            revenue_multiple = db_ev_revenue
        if db_pe is not None and db_pe > 0:
            pe_ratio = db_pe

        data_source = "business_type_db"
        provenance = _fetch_provenance(
            multiples_adapter=multiples_adapter,
            business_type_id=business_type_id,
            request_country_code=request_country_code,
            logger=logger,
        )
        data_source_details = {
            "business_type_id": business_type_id,
            "source": "database",
            "business_type_db_status": "resolved",
            # Which Delphi triage layer priced this multiple, over how many
            # observations, how fresh, and any required attribution. Without
            # this the report states a number it cannot defend.
            "benchmark_provenance": provenance,
            "ev_ebitda": ev_ebitda_ratio,
            "ev_revenue": revenue_multiple,
            "pe": pe_ratio,
            "correlation_id": correlation_id,
            "priority": "HIGHEST",
            "academic_sources": DataSourceFormatter.get_academic_sources_for_data_source(
                "business_type_db"
            ),
            "academic_citations": DataSourceFormatter.format_academic_citations("business_type_db"),
            "source_explanation": DataSourceFormatter.generate_source_explanation(
                "business_type_db",
                business_type_id,
                {"business_type_id": business_type_id},
            ),
            "regional_market": _regional_market(request_country_code),
            "calibration_methodology": (
                "Business-type-specific calibration per Trugman (2017) and Coulon (2021)"
            ),
        }
        logger.info(
            f"SUCCESS: DB multiples retrieved and used (PRIORITY 0) for {business_type_id}",
            extra={
                "business_type_id": business_type_id,
                "ev_ebitda": ev_ebitda_ratio,
                "ev_revenue": revenue_multiple,
                "pe": pe_ratio,
                "data_source": "business_type_db",
                "correlation_id": correlation_id,
            },
        )
    except Exception as error:
        logger.error(
            f"DB lookup failed for {business_type_id}: {error}",
            extra={
                "business_type_id": business_type_id,
                "error": str(error),
                "error_type": type(error).__name__,
                "correlation_id": correlation_id,
            },
            exc_info=True,
        )
        # Degrading to a weaker evidence layer is a disclosable fact, not just
        # a log line. Without this the report reads identically whether the
        # business-type benchmarks were consulted or silently unavailable.
        data_source_details = {
            **data_source_details,
            "business_type_db_status": "unavailable",
            "business_type_db_error": type(error).__name__,
        }

    return DatabaseBenchmarkSelection(
        ev_ebitda_ratio=ev_ebitda_ratio,
        revenue_multiple=revenue_multiple,
        pe_ratio=pe_ratio,
        data_source=data_source,
        data_source_details=data_source_details,
    )


def _fetch_provenance(
    *,
    multiples_adapter: MultiplesAdapterLike,
    business_type_id: str,
    request_country_code: Optional[str],
    logger: LoggerLike,
) -> Dict[str, object]:
    """Read the Delphi triage record for a resolved DB multiple.

    Resolved defensively: adapters and test doubles that only implement
    `get_multiples_dict` stay valid, and a provenance miss must never
    invalidate a multiple that was already resolved.
    """
    fetch = getattr(multiples_adapter, "get_multiples_provenance", None)
    if not callable(fetch):
        return {}
    try:
        return fetch(business_type_id, request_country_code) or {}
    except Exception as error:  # noqa: BLE001 - provenance is never load-bearing
        logger.error(
            f"Provenance lookup failed for {business_type_id}: {error}",
            extra={"business_type_id": business_type_id, "error_type": type(error).__name__},
        )
        return {}


async def _fetch_business_type_multiples(
    *,
    multiples_adapter: MultiplesAdapterLike,
    business_type_id: str,
    request_country_code: Optional[str],
    correlation_id: Optional[str],
    logger: LoggerLike,
) -> Dict[str, object]:
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    partial(
                        multiples_adapter.get_multiples_dict,
                        business_type_id,
                        request_country_code,
                    ),
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"DB lookup timeout for {business_type_id} (exceeded 5 seconds)",
                extra={
                    "business_type_id": business_type_id,
                    "country_code": request_country_code,
                    "correlation_id": correlation_id,
                    "timeout_seconds": 5.0,
                },
            )
            return {}


def _has_valid_database_multiple(
    db_ev_ebitda: Optional[Decimal], db_ev_revenue: Optional[Decimal]
) -> bool:
    return (db_ev_ebitda is not None and db_ev_ebitda > 0) or (
        db_ev_revenue is not None and db_ev_revenue > 0
    )
