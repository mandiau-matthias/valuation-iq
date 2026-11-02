"""Country data service — Phase 3.

Runtime authority for per-country macro indicators (statutory CIT, 10y bond
yield, GDP growth, inflation, currency). Data lives in Delphi
(`country_contextual_factors`); this service warms an in-memory cache from
``GET /api/v1/country-context`` at FastAPI startup and serves synchronous
reads for the DCF / multiples / latency hot paths.

Why not async-on-demand: the DCF data adapter walks every year × scenario
combination synchronously and the multiples calculator is called inside a
tight nested loop. Round-tripping to Delphi for each call would 10x the
request budget. Country macros change monthly at most — an in-memory cache
refreshed at boot (and once an hour during operation) is plenty.

Contract: when the cache is cold, doesn't have a row for the requested
country, or Delphi returned no data, all sync getters return ``None`` and
callers fall through to the static bootstrap dict in
``dcf_data_adapter.COUNTRY_DEFAULTS``. The bootstrap values mirror the
Phase 2 / migration 071 seed exactly so swapping reads is value-preserving.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional

import aiohttp

from src.config.countries import SUPPORTED_COUNTRY_CODES, normalize_country_code
from src.utils.percent_to_decimal import percentage_points_to_decimal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CountryContextSnapshot:
    """Frozen snapshot of one country's contextual factors as fetched from Delphi.

    Rates are percentage points per Delphi's country-context API contract.
    Callers convert to decimal fractions explicitly, never by magnitude.
    """

    country: str
    as_of_date: str
    currency_code: Optional[str]
    gdp_growth_1y: Optional[float]
    gdp_growth_forecast_2y: Optional[float]
    inflation_hicp: Optional[float]
    risk_free_rate_10y: Optional[float]
    corporate_tax_statutory: Optional[float]
    last_updated: str = field(default="")

    @classmethod
    def from_delphi_payload(cls, raw: dict) -> "CountryContextSnapshot":
        return cls(
            country=str(raw.get("country", "")).upper(),
            as_of_date=str(raw.get("as_of_date") or ""),
            currency_code=raw.get("currency_code"),
            gdp_growth_1y=_safe_float(raw.get("gdp_growth_1y")),
            gdp_growth_forecast_2y=_safe_float(raw.get("gdp_growth_forecast_2y")),
            inflation_hicp=_safe_float(raw.get("inflation_hicp")),
            risk_free_rate_10y=_safe_float(raw.get("risk_free_rate_10y")),
            corporate_tax_statutory=_safe_float(raw.get("corporate_tax_statutory")),
            last_updated=str(raw.get("last_updated") or ""),
        )


def _safe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)  # accepts int / Decimal / numeric string
    except (TypeError, ValueError):
        return None


class CountryDataService:
    """In-memory cache of Delphi's per-country macro factors.

    Thread-safe via a single lock around the cache swap. The cache is
    populated atomically (build a new dict, then swap reference) so concurrent
    reads never see a half-built cache.

    Use the module-level :func:`get_country_data_service` accessor to obtain
    the singleton — DI not threaded through every caller because the existing
    DCFDataAdapter, comparable_companies_collector, etc. are not DI-aware.
    """

    _DEFAULT_TIMEOUT_SECONDS = 8.0

    def __init__(
        self,
        delphi_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self._delphi_base_url = (
            delphi_base_url or os.getenv("DELPHI_API_URL") or os.getenv("DELPHI_BASE_URL") or ""
        ).rstrip("/")
        self._api_key = api_key or os.getenv("DELPHI_API_KEY") or ""
        self._timeout = aiohttp.ClientTimeout(
            total=timeout_seconds or self._DEFAULT_TIMEOUT_SECONDS
        )
        self._cache: Dict[str, CountryContextSnapshot] = {}
        self._last_refresh_at: Optional[datetime] = None
        self._lock = threading.Lock()
        self._refresh_lock = asyncio.Lock()

    # ─── Sync read API (the hot-path lookups) ──────────────────────────────

    def get(self, country_code: object) -> Optional[CountryContextSnapshot]:
        """Return the cached snapshot for `country_code` or ``None`` on miss."""
        if not isinstance(country_code, str):
            return None
        key = country_code.strip().upper()
        if key == "UK":
            key = "GB"
        if len(key) != 2:
            return None
        with self._lock:
            return self._cache.get(key)

    def get_corporate_tax_statutory(self, country_code: object) -> Optional[float]:
        """Statutory CIT in **percent** (matches the legacy hardcoded shape)."""
        snap = self.get(country_code)
        return snap.corporate_tax_statutory if snap else None

    def get_risk_free_rate_10y(self, country_code: object) -> Optional[float]:
        """10y sovereign yield as **decimal** (e.g. 0.025 for 2.5%).

        Delphi stores the value as a percent (2.50). The DCF adapter expects
        a decimal so we convert at the boundary, matching how the bootstrap
        dict already encodes it.
        """
        snap = self.get(country_code)
        if snap is None or snap.risk_free_rate_10y is None:
            return None
        return percentage_points_to_decimal(snap.risk_free_rate_10y)

    def get_gdp_growth(self, country_code: object) -> Optional[float]:
        """Long-term GDP growth as decimal. Prefers the 2y forecast over
        the backward-looking 1y print, matching the original hardcoded values
        which were forward-looking IMF WEO estimates."""
        snap = self.get(country_code)
        if snap is None:
            return None
        chosen = (
            snap.gdp_growth_forecast_2y
            if snap.gdp_growth_forecast_2y is not None
            else snap.gdp_growth_1y
        )
        if chosen is None:
            return None
        return percentage_points_to_decimal(chosen)

    def get_inflation(self, country_code: object) -> Optional[float]:
        """HICP inflation as decimal (0.02 for 2%)."""
        snap = self.get(country_code)
        if snap is None or snap.inflation_hicp is None:
            return None
        return percentage_points_to_decimal(snap.inflation_hicp)

    def get_currency_code(self, country_code: object) -> Optional[str]:
        snap = self.get(country_code)
        return snap.currency_code if snap else None

    # ─── Lifecycle / refresh ───────────────────────────────────────────────

    def is_configured(self) -> bool:
        return bool(self._delphi_base_url)

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def last_refresh_at(self) -> Optional[datetime]:
        with self._lock:
            return self._last_refresh_at

    async def refresh(self) -> int:
        """Pull all 16 supported countries from Delphi.

        Returns the number of rows loaded. Never raises — failures are logged
        and the existing cache (if any) is preserved so a transient Delphi
        outage doesn't blow up an in-flight request.
        """
        async with self._refresh_lock:
            return await self._refresh_locked()

    async def _refresh_locked(self) -> int:
        if not self._delphi_base_url:
            # DEBUG: fallback-mode is expected in stateless deployments without
            # Delphi. The "✅ CountryDataService warmed at startup" line carries
            # the result (already at DEBUG).
            logger.debug(
                "CountryDataService.refresh: DELPHI_API_URL not set, skipping (operating in fallback mode)"
            )
            return 0

        url = f"{self._delphi_base_url}/api/v1/country-context"
        params = [("countries", code) for code in SUPPORTED_COUNTRY_CODES]
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status >= 400:
                        body_preview = (await resp.text())[:200]
                        logger.warning(
                            "CountryDataService.refresh: Delphi returned %s — %s",
                            resp.status,
                            body_preview,
                        )
                        return 0
                    payload = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning(
                "CountryDataService.refresh: Delphi unreachable (%s) — keeping previous cache (size=%d)",
                exc,
                self.size(),
            )
            return 0

        rows = payload.get("countries") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            logger.warning(
                "CountryDataService.refresh: unexpected payload shape (%s)", type(payload).__name__
            )
            return 0

        next_cache: Dict[str, CountryContextSnapshot] = {}
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            snap = CountryContextSnapshot.from_delphi_payload(raw)
            if snap.country and len(snap.country) == 2:
                next_cache[snap.country] = snap

        with self._lock:
            self._cache = next_cache
            self._last_refresh_at = datetime.now(timezone.utc)

        logger.info(
            "CountryDataService.refresh: loaded %d/%d country rows from Delphi",
            len(next_cache),
            len(SUPPORTED_COUNTRY_CODES),
        )
        return len(next_cache)

    # ─── Test seam ─────────────────────────────────────────────────────────

    def _seed_for_test(self, snapshots: Dict[str, CountryContextSnapshot]) -> None:
        with self._lock:
            self._cache = dict(snapshots)
            self._last_refresh_at = datetime.now(timezone.utc)

    def _clear_for_test(self) -> None:
        with self._lock:
            self._cache = {}
            self._last_refresh_at = None


# ─── Module-level singleton accessor ───────────────────────────────────────

_singleton: Optional[CountryDataService] = None
_singleton_lock = threading.Lock()


def get_country_data_service() -> CountryDataService:
    """Return the process-wide singleton, constructing on first use.

    The singleton can be replaced via :func:`set_country_data_service` (used
    by tests so they don't accidentally hit Delphi on real network sockets).
    """
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = CountryDataService()
    return _singleton


def set_country_data_service(service: Optional[CountryDataService]) -> None:
    """Test-only setter. Pass ``None`` to reset to default-constructed."""
    global _singleton
    with _singleton_lock:
        _singleton = service
