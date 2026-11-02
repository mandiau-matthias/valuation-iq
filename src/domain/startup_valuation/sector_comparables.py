"""Startup sector → curated `business_types` comparables fetcher.

Bridges the engine's 8-sector startup taxonomy to the broader
``business_types`` catalogue so the founder report can cite Damodaran-
backed multiples (EV/EBITDA, EV/Revenue, P/E) alongside the Q1-2026
startup-specific anchors.

Reads from the Athena endpoint
``/api/benchmarks/v1/startup-sector-businesstypes`` (machine-key auth,
same trust boundary as the existing startup-reference fetcher) with an
in-process cache.  Falls back to an empty list on any failure — the
report renderer treats "no comparables" as "skip the comparables card",
never as a hard error.

Env-gated by the same ``ATHENA_BASE_URL`` / ``ATHENA_BENCHMARK_API_KEY``
pair as :func:`regional_data.fetch_from_athena`, so a single misconfig
disables both surfaces consistently.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import requests

from .schemas import StartupSector

_logger = logging.getLogger(__name__)

_ATHENA_BASE_URL_ENV = "ATHENA_BASE_URL"
_ATHENA_API_KEY_ENV = "ATHENA_BENCHMARK_API_KEY"
_ATHENA_TIMEOUT_SECONDS = 1.5
_ATHENA_CACHE_TTL_SECONDS = 15 * 60


def _athena_base_url() -> str | None:
    base_url = os.environ[_ATHENA_BASE_URL_ENV].rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        _logger.warning("athena_sector_comparables_invalid_base_url scheme=%s", parsed.scheme)
        return None
    return base_url


@dataclass(frozen=True)
class SectorComparableRow:
    """One curated `business_types` row, ready for report inclusion."""

    business_type_id: str
    title: str
    short_description: str | None
    industry_mapping: str | None
    multiples_source: str | None
    multiples_quality_score: Decimal | None
    ev_ebitda_median: Decimal | None
    ev_ebitda_p25: Decimal | None
    ev_ebitda_p75: Decimal | None
    ev_revenue_median: Decimal | None
    ev_revenue_p25: Decimal | None
    ev_revenue_p75: Decimal | None
    pe_ratio_median: Decimal | None
    typical_revenue_median: Decimal | None
    typical_ebitda_margin_median: Decimal | None

    def to_dict(self) -> dict[str, Any]:
        """Plain-Python representation for the report context payload."""

        def _f(v: Decimal | None) -> float | None:
            return float(v) if v is not None else None

        return {
            "business_type_id": self.business_type_id,
            "title": self.title,
            "short_description": self.short_description,
            "industry_mapping": self.industry_mapping,
            "multiples_source": self.multiples_source,
            "multiples_quality_score": _f(self.multiples_quality_score),
            "ev_ebitda_median": _f(self.ev_ebitda_median),
            "ev_ebitda_p25": _f(self.ev_ebitda_p25),
            "ev_ebitda_p75": _f(self.ev_ebitda_p75),
            "ev_revenue_median": _f(self.ev_revenue_median),
            "ev_revenue_p25": _f(self.ev_revenue_p25),
            "ev_revenue_p75": _f(self.ev_revenue_p75),
            "pe_ratio_median": _f(self.pe_ratio_median),
            "typical_revenue_median": _f(self.typical_revenue_median),
            "typical_ebitda_margin_median": _f(self.typical_ebitda_margin_median),
        }


_cache: dict[tuple[StartupSector, int], tuple[float, list[SectorComparableRow]]] = {}
_cache_lock = threading.Lock()


def _athena_enabled() -> bool:
    return bool(os.environ.get(_ATHENA_BASE_URL_ENV) and os.environ.get(_ATHENA_API_KEY_ENV))


def _cache_get(
    key: tuple[StartupSector, int],
) -> list[SectorComparableRow] | None:
    with _cache_lock:
        entry = _cache.get(key)
        if not entry:
            return None
        ts, data = entry
        if time.time() - ts > _ATHENA_CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        return data


def _cache_set(
    key: tuple[StartupSector, int],
    data: list[SectorComparableRow],
) -> None:
    with _cache_lock:
        _cache[key] = (time.time(), data)


def fetch_sector_comparables(
    sector: StartupSector,
    *,
    limit: int = 5,
) -> list[SectorComparableRow]:
    """Fetch curated `business_types` comparables for a startup sector.

    Returns an empty list — never raises — on any failure (Athena down,
    misconfigured env, malformed payload).  The report renderer renders
    a "no sector comparables available" tile rather than crashing the
    PDF when this happens.
    """

    capped = max(1, min(20, int(limit)))
    if not _athena_enabled():
        return []

    cache_key = (sector, capped)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    base_url = _athena_base_url()
    if base_url is None:
        return []
    api_key = os.environ[_ATHENA_API_KEY_ENV]
    url = f"{base_url}/api/benchmarks/v1/startup-sector-businesstypes"

    try:
        resp = requests.get(
            url,
            params={"sector": sector, "limit": capped},
            headers={"x-api-key": api_key, "accept": "application/json"},
            timeout=_ATHENA_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, TimeoutError, ValueError, OSError) as exc:
        _logger.warning("athena_sector_comparables_unavailable sector=%s err=%s", sector, exc)
        return []

    raw_rows = payload.get("rows") or []
    rows: list[SectorComparableRow] = []
    for r in raw_rows:
        try:
            rows.append(_row_from_payload(r))
        except (KeyError, ValueError, TypeError) as exc:
            _logger.warning(
                "athena_sector_comparables_skipped sector=%s id=%s err=%s",
                sector,
                r.get("id"),
                exc,
            )
            continue

    _cache_set(cache_key, rows)
    return rows


def reset_sector_comparables_cache() -> None:
    """Clear the in-process cache.  Used by tests."""
    with _cache_lock:
        _cache.clear()


def _row_from_payload(r: dict[str, Any]) -> SectorComparableRow:
    """Coerce one Athena row into a frozen ``SectorComparableRow``."""

    def _dec(key: str) -> Decimal | None:
        v = r.get(key)
        if v is None or v == "":
            return None
        return Decimal(str(v))

    return SectorComparableRow(
        business_type_id=str(r["id"]),
        title=str(r.get("title") or ""),
        short_description=(str(r["short_description"]) if r.get("short_description") else None),
        industry_mapping=(str(r["industry_mapping"]) if r.get("industry_mapping") else None),
        multiples_source=(str(r["multiples_source"]) if r.get("multiples_source") else None),
        multiples_quality_score=_dec("multiples_quality_score"),
        ev_ebitda_median=_dec("ev_ebitda_median"),
        ev_ebitda_p25=_dec("ev_ebitda_p25"),
        ev_ebitda_p75=_dec("ev_ebitda_p75"),
        ev_revenue_median=_dec("ev_revenue_median"),
        ev_revenue_p25=_dec("ev_revenue_p25"),
        ev_revenue_p75=_dec("ev_revenue_p75"),
        pe_ratio_median=_dec("pe_ratio_median"),
        typical_revenue_median=_dec("typical_revenue_median"),
        typical_ebitda_margin_median=_dec("typical_ebitda_margin_median"),
    )
