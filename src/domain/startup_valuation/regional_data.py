"""Regional reference data for startup valuation.

Provide local, appropriately licensed regional and sector inputs in VALUATIONIQ_REFERENCE_DIR.

Thread-safety
-------------
Module-level lookup tables are wrapped in :class:`types.MappingProxyType`
so callers cannot mutate them — every helper returns a frozen dataclass
or a fresh dict.  Safe to call concurrently from FastAPI workers without
locks.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlparse

import requests
from src.config.local_reference_data import reference_table

from .schemas import StartupSector, StartupStage

_logger = logging.getLogger(__name__)


def _athena_base_url() -> str | None:
    base_url = os.environ[_ATHENA_BASE_URL_ENV].rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        _logger.warning("athena_benchmarks_invalid_base_url scheme=%s", parsed.scheme)
        return None
    return base_url


@dataclass(frozen=True)
class RegionalReferenceData:
    """Reference inputs for the Scorecard and VC methods, per region/stage."""

    region_code: str
    stage: StartupStage

    average_pre_money: Decimal
    """Average pre-money valuation of recently funded startups in this
    region/stage (Scorecard anchor, in EUR)."""

    berkus_max_per_milestone: Decimal
    """Maximum value attributed to each of the 5 Berkus milestones
    (in EUR).  Bill Payne's original Berkus method caps the total at
    €2.5M; we use €500k per milestone as the canonical default."""

    comparable_exit_revenue_multiple: Decimal
    """Median EV/Revenue exit multiple observed for comparable Year-5
    venture-backed exits in this region/stage."""

    default_target_roi_x: Decimal
    """Default cash-on-cash return target VCs require for this stage
    (10x for Series A, 20x for Seed, 30x for Pre-seed)."""

    default_dilution_pct: Decimal
    """Default cumulative founder dilution assumption from this stage
    through exit (used by the VC Method when not supplied)."""

    default_yoy_growth_factor: Decimal
    """Default annual YoY growth multiplier used to extrapolate ARR
    forward 5 years when the founder hasn't supplied an explicit Y5
    projection (e.g. ``Decimal("3.0")`` ⇒ 200% YoY)."""

    source: str = "User-supplied local startup references"
    """Human-readable source label for the benchmark row."""

    methodology_version: str = "static-fallback-2026q1"
    published_at: str | None = None
    geography_scope: str = "country"
    geography_label: str | None = None
    sample_size: int | None = None
    evidence_quality: str = "local_market_average"
    benchmark_source_type: str = "local_market_average"
    source_url: str | None = None
    source_observed_at: str | None = None


# --- Static lookup table ----------------------------------------------------
#
# Source: Atomico "State of European Tech 2024" + Dealroom Benelux 2024
# rounds.  Conservative midpoints to avoid optimism bias.
# Numbers are EUR.

_RAW_REGIONAL_DATA = reference_table("startup-regions")

# Benelux fallback (NL, LU) reuses BE numbers for now.  Listed
# explicitly so a future swap can replace any one country independently
# without changing the call-sites.




def _build_region_table() -> Mapping[str, Mapping[StartupStage, RegionalReferenceData]]:
    """Materialise the raw seed dict into immutable :class:`MappingProxyType`s."""
    out: dict[str, Mapping[StartupStage, RegionalReferenceData]] = {}
    for region_code, stages in _RAW_REGIONAL_DATA.items():
        bucket: dict[StartupStage, RegionalReferenceData] = {}
        for stage, values in stages.items():
            bucket[stage] = RegionalReferenceData(
                region_code=region_code,
                stage=stage,
                average_pre_money=Decimal(values["average_pre_money"]),
                berkus_max_per_milestone=Decimal(values["berkus_max_per_milestone"]),
                comparable_exit_revenue_multiple=Decimal(
                    values["comparable_exit_revenue_multiple"]
                ),
                default_target_roi_x=Decimal(values["default_target_roi_x"]),
                default_dilution_pct=Decimal(values["default_dilution_pct"]),
                default_yoy_growth_factor=Decimal(values["default_yoy_growth_factor"]),
            )
        out[region_code] = MappingProxyType(bucket)
    return MappingProxyType(out)


_REGIONAL_DATA: Mapping[str, Mapping[StartupStage, RegionalReferenceData]] = _build_region_table()
"""Frozen per-country, per-stage reference table.

Backed by :class:`types.MappingProxyType` so accidental mutation raises
:class:`TypeError` at the call site instead of silently corrupting the
shared dataset.
"""

_DEFAULT_REGION_CODE: str = "BE"


# ---------------------------------------------------------------------------
# Sector overrides for the static fallback
# ---------------------------------------------------------------------------
#
# Mirrors the per-sector rows in
# ``db/migrations/20260421120000_create_startup_valuation_benchmarks.sql``.
# When Athena is reachable, the live feed serves these numbers per
# (region, stage, sector); when it is not, this overlay keeps the engine
# producing sector-aware anchors instead of collapsing every founder to the
# sector-blind median.  Without it, a SaaS pre-seed and a biotech pre-seed
# would both report €1.5M with a 5× exit multiple in degraded mode — the
# 24-row sector seed in the DB would be silently wasted.
#
# Only the fields that vary by sector in the migration are listed here;
# every other ``RegionalReferenceData`` field falls through to the
# region/stage row in ``_RAW_REGIONAL_DATA``.

_SECTOR_OVERRIDES_RAW = reference_table("startup-sectors")


def _apply_sector_overrides(
    base: RegionalReferenceData, sector: StartupSector
) -> RegionalReferenceData:
    """Return a new ``RegionalReferenceData`` with per-sector overrides applied.

    Falls back to ``base`` unchanged when the sector is not in the overlay
    (defensive — keeps the engine running if the migration adds a sector
    we haven't mirrored yet).
    """
    overrides = _SECTOR_OVERRIDES_RAW.get(base.stage, {}).get(sector)
    if not overrides:
        return base
    return RegionalReferenceData(
        region_code=base.region_code,
        stage=base.stage,
        average_pre_money=Decimal(overrides.get("average_pre_money", str(base.average_pre_money))),
        berkus_max_per_milestone=base.berkus_max_per_milestone,
        comparable_exit_revenue_multiple=Decimal(
            overrides.get(
                "comparable_exit_revenue_multiple",
                str(base.comparable_exit_revenue_multiple),
            )
        ),
        default_target_roi_x=base.default_target_roi_x,
        default_dilution_pct=base.default_dilution_pct,
        default_yoy_growth_factor=Decimal(
            overrides.get("default_yoy_growth_factor", str(base.default_yoy_growth_factor))
        ),
        source=base.source,
        methodology_version=base.methodology_version,
        published_at=base.published_at,
        geography_scope=base.geography_scope,
        geography_label=base.geography_label,
        sample_size=base.sample_size,
        evidence_quality=base.evidence_quality,
        benchmark_source_type=base.benchmark_source_type,
        source_url=base.source_url,
        source_observed_at=base.source_observed_at,
    )


def get_regional_reference_data(
    country_code: str,
    stage: StartupStage,
    sector: StartupSector | None = None,
) -> RegionalReferenceData:
    """Return the reference dataset for a given country / stage / sector.

    First consults the Athena MDM live feed (when ``ATHENA_BASE_URL`` and
    ``ATHENA_BENCHMARK_API_KEY`` are configured) and falls back to the
    static dictionary above on any error.  Falls back to Belgium when the
    country is not known (designed so the engine never crashes on an
    unfamiliar ISO code).

    When ``sector`` is provided and Athena is unreachable, the static
    region/stage row is enriched with ``_SECTOR_OVERRIDES_RAW`` so
    degraded-mode anchors track the migration's per-sector seed instead
    of collapsing to the sector-blind median.  Calling without a sector
    preserves the historical sector-blind behaviour (used by call-sites
    that haven't been threaded yet, e.g. internal benchmarking scripts).
    """
    code = (country_code or _DEFAULT_REGION_CODE).upper()

    live = fetch_from_athena(code, stage, sector=sector)
    if live is not None:
        return live

    region = _REGIONAL_DATA.get(code)
    if region is None or stage not in region:
        raise ValueError(f"Supply {code}/{stage} in startup-regions.json (VALUATIONIQ_REFERENCE_DIR)")
    base = region[stage]
    if sector is None:
        return base
    return _apply_sector_overrides(base, sector)


# ---------------------------------------------------------------------------
# Athena MDM live feed
# ---------------------------------------------------------------------------

_ATHENA_BASE_URL_ENV = "ATHENA_BASE_URL"
_ATHENA_API_KEY_ENV = "ATHENA_BENCHMARK_API_KEY"
_ATHENA_TIMEOUT_SECONDS = 1.5
_ATHENA_CACHE_TTL_SECONDS = 15 * 60

# Cache key is (region, stage, sector_or_None).  The previous (region, stage)
# tuple silently returned the first cached sector for every subsequent sector
# query — a SaaS lookup followed by a biotech lookup would yield SaaS numbers.
_AthenaCacheKey = tuple[str, StartupStage, StartupSector | None]
_athena_cache: dict[_AthenaCacheKey, tuple[float, RegionalReferenceData]] = {}
_athena_cache_lock = threading.Lock()


def _athena_enabled() -> bool:
    return bool(os.environ.get(_ATHENA_BASE_URL_ENV) and os.environ.get(_ATHENA_API_KEY_ENV))


def _athena_cache_get(key: _AthenaCacheKey) -> RegionalReferenceData | None:
    with _athena_cache_lock:
        entry = _athena_cache.get(key)
        if not entry:
            return None
        ts, data = entry
        if time.time() - ts > _ATHENA_CACHE_TTL_SECONDS:
            _athena_cache.pop(key, None)
            return None
        return data


def _athena_cache_set(key: _AthenaCacheKey, data: RegionalReferenceData) -> None:
    with _athena_cache_lock:
        _athena_cache[key] = (time.time(), data)


def fetch_from_athena(
    country_code: str,
    stage: StartupStage,
    *,
    sector: StartupSector | None = None,
) -> RegionalReferenceData | None:
    """Fetch live benchmarks from the Athena MDM endpoint.

    Returns ``None`` (no exception) on any failure so the caller can fall
    back to the static dict.  Env-gated by ``ATHENA_BASE_URL`` and
    ``ATHENA_BENCHMARK_API_KEY``.

    The result is memoised in-process for ``_ATHENA_CACHE_TTL_SECONDS``
    so a single request that triggers all 9 valuation methods only hits
    Athena once per (region, stage, sector) tuple.
    """
    if not _athena_enabled():
        return None

    code = (country_code or _DEFAULT_REGION_CODE).upper()
    cache_key: _AthenaCacheKey = (code, stage, sector)
    cached = _athena_cache_get(cache_key)
    if cached is not None:
        return cached

    base_url = _athena_base_url()
    if base_url is None:
        return None
    api_key = os.environ[_ATHENA_API_KEY_ENV]

    params = {"region": code, "stage": stage}
    if sector:
        params["sector"] = sector
    url = f"{base_url}/api/benchmarks/v1/startup-reference"

    try:
        resp = requests.get(
            url,
            params=params,
            headers={"x-api-key": api_key, "accept": "application/json"},
            timeout=_ATHENA_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, TimeoutError, ValueError, OSError) as exc:
        _logger.warning("athena_benchmarks_unavailable region=%s stage=%s err=%s", code, stage, exc)
        return None

    rows = payload.get("rows") or []
    if not rows:
        return None

    # Prefer the row matching the requested sector; otherwise take the
    # first row (Athena returns the regional median when sector is empty).
    row = next(
        (r for r in rows if not sector or r.get("sector") == sector),
        rows[0],
    )

    try:
        data = RegionalReferenceData(
            region_code=code,
            stage=stage,
            average_pre_money=Decimal(str(row["average_pre_money_eur"])),
            berkus_max_per_milestone=Decimal(str(row["berkus_max_per_milestone_eur"])),
            comparable_exit_revenue_multiple=Decimal(
                str(
                    (row.get("exit_multiple_low", 0) + row.get("exit_multiple_high", 0)) / 2
                    or row.get("exit_multiple_low", 6)
                )
            ),
            default_target_roi_x=Decimal(str(row["default_target_roi_x"])),
            default_dilution_pct=Decimal(str(row["default_dilution_pct"])),
            default_yoy_growth_factor=Decimal(str(row["default_yoy_growth_factor"])),
            source=str(row.get("source") or "Athena startup benchmark"),
            methodology_version=str(row.get("methodology_version") or "athena"),
            published_at=str(row["published_at"]) if row.get("published_at") else None,
            geography_scope=str(row.get("geography_scope") or "country"),
            geography_label=(str(row["geography_label"]) if row.get("geography_label") else None),
            sample_size=int(row["sample_size"]) if row.get("sample_size") is not None else None,
            evidence_quality=str(row.get("evidence_quality") or "local_market_average"),
            benchmark_source_type=str(row.get("benchmark_source_type") or "local_market_average"),
            source_url=str(row["source_url"]) if row.get("source_url") else None,
            source_observed_at=(
                str(row["source_observed_at"]) if row.get("source_observed_at") else None
            ),
        )
    except (KeyError, ValueError, TypeError) as exc:
        _logger.warning("athena_benchmarks_malformed region=%s stage=%s err=%s", code, stage, exc)
        return None

    _athena_cache_set(cache_key, data)
    return data


def reset_athena_cache() -> None:
    """Clear the in-process Athena cache.  Used by tests."""
    with _athena_cache_lock:
        _athena_cache.clear()


# ---------------------------------------------------------------------------
# Sector smart defaults
# ---------------------------------------------------------------------------
#
# Source: Atomico SoEU 2024 + PitchBook EMEA Tech Reports (2024–2025).  These
# are *exit* EV/Revenue medians for venture-backed European exits in each
# vertical.  When the founder picks a sector we use these to pre-fill the VC
# Method's ``exit_revenue_multiple`` and to anchor the SaaS Forward leg.
#
# Numbers are intentionally conservative midpoints — the consortium wants
# defaults that survive cross-examination from a sceptical angel.


@dataclass(frozen=True)
class SectorDefaults:
    """Smart-default bundle for one sector."""

    sector: StartupSector
    label: str
    """Human-readable label used in the UI dropdown."""
    exit_revenue_multiple: Decimal
    """Default ``exit_revenue_multiple`` injected into the VC Method when
    the founder hasn't supplied one."""
    typical_year5_revenue_pre_seed: Decimal
    """Conservative Y5 ARR target for an early-stage company in this
    sector (used to seed the VC method when the founder hasn't yet run
    a 5-year financial model)."""
    notes: str
    """One-line rationale shown in the UI tooltip."""


_SECTOR_DEFAULTS = MappingProxyType({
    key: SectorDefaults(
        sector=key, label=row["label"],
        exit_revenue_multiple=Decimal(str(row["exit_revenue_multiple"])),
        typical_year5_revenue_pre_seed=Decimal(str(row["typical_year5_revenue_pre_seed"])),
        notes=row.get("notes", "User-supplied local assumptions"),
    ) for key, row in reference_table("startup-sector-defaults").items()
})


def get_sector_defaults(sector: StartupSector) -> SectorDefaults:
    """Return the :class:`SectorDefaults` bundle for a given sector."""
    if sector not in _SECTOR_DEFAULTS:
        raise ValueError(f"Supply {sector} in startup-sector-defaults.json")
    return _SECTOR_DEFAULTS[sector]


def list_sector_defaults() -> list[SectorDefaults]:
    """Return all sector defaults in display order (used by UI dropdown)."""
    return list(_SECTOR_DEFAULTS.values())
