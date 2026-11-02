"""Market context (BET-627, the value-up "M&A-landscape" half of BET-606 Phase 4).

The engine's ``mcp_insights`` slot was a ``None`` stub. This builds the first REAL,
DEFENSIBLE market-health signal set from data already resolved into the valuation — the
``benchmark_contract`` (the comp set the price is anchored on) plus the computed
owner-dependency discount and data tier. It is then persisted in the valuation result and
surfaced on the value-up curve.

THE BRAND OATH. Every populated field is measured, never invented. The two signals that
would need data we do not yet have — the sector-multiple TREND (needs index benchmark
vintages) and DEAL VELOCITY (needs validated ``transaction_observations``
aggregation) — are returned as an explicit ``insufficient_data`` status with a reason,
NOT a fabricated number. The shape is stable so those can be populated later without a
consumer change.

Pure + dependency-free (stdlib only, accepts plain mappings) so it unit-tests in isolation
and the response assembly just resolves the contract and calls it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Optional

SCHEMA_VERSION = "market_context_v1"

# Comp-set depth → market liquidity. SME benchmark sets are small; these thresholds match
# the honesty of the confidence bands (a handful of comps is genuinely "illiquid").
_LIQUIDITY_ACTIVE_MIN = 20
_LIQUIDITY_THIN_MIN = 10

# Benchmark recency → is the market basis current? A benchmark older than ~2 quarters may
# miss a regime shift, so we flag it rather than silently pricing on stale comps.
_RECENCY_CURRENT_MAX_DAYS = 90
_RECENCY_AGING_MAX_DAYS = 180

# Owner-dependency discount → transferability / M&A-readiness. Mirrors the engine risk
# ledger's owner-dependency band (a 20%+ key-man discount is a serious buyer red flag).
_READINESS_LOW_MIN = 0.20
_READINESS_MODERATE_MIN = 0.10

_INSUFFICIENT_TREND = {
    "status": "insufficient_data",
    "reason": (
        "Sector-multiple trend needs multiple benchmark vintages over time "
        "(index dataset_versions) — not yet wired."
    ),
}
_INSUFFICIENT_VELOCITY = {
    "status": "insufficient_data",
    "reason": (
        "Deal velocity needs validated transaction observations aggregated by sector "
        "— not yet wired."
    ),
}


def build_market_context(
    benchmark_contract: Optional[Mapping[str, object]],
    *,
    owner_dependency_adjustment: object = None,
    data_tier: object = None,
    now: Optional[datetime] = None,
) -> Optional[dict[str, object]]:
    """Build the defensible market-context block, or ``None`` when there is nothing to say.

    ``None`` (mirroring the engine-risk-ledger extractor) when neither a benchmark contract
    nor an owner-dependency signal is present — so the caller leaves the field unset rather
    than emitting an empty husk.
    """
    contract = (
        benchmark_contract
        if isinstance(benchmark_contract, Mapping) and benchmark_contract
        else None
    )
    owner_discount = _normalise_fraction(owner_dependency_adjustment)

    if contract is None and owner_discount is None:
        return None

    reference = now or datetime.now(timezone.utc)

    return {
        "schema_version": SCHEMA_VERSION,
        "liquidity": _liquidity(contract),
        "benchmark_recency": _benchmark_recency(contract, reference),
        "coverage": _coverage(contract),
        "transferability": _transferability(owner_discount),
        "sector_cycle": _sector_cycle(contract),
        "deal_activity": dict(_INSUFFICIENT_VELOCITY),
        "confidence_band": (
            _string(contract, ("confidence_band", "confidenceBand")) if contract else None
        ),
        "data_tier": _string_value(data_tier),
        "source": "valuation_engine",
    }


def _sector_cycle(contract: Optional[Mapping[str, object]]) -> dict[str, object]:
    """The sector-multiple trend (BET-628) when the index resolved one onto the benchmark
    contract; else the honest insufficient-data status. The trend is a plain dict
    (``status='measured'`` + direction / magnitude_pct / from→to / points / confidence)
    computed upstream from the series' published vintages — read defensively here."""
    if contract:
        trend = contract.get("multiple_trend") or contract.get("multipleTrend")
        if isinstance(trend, Mapping) and str(trend.get("status")) == "measured":
            return dict(trend)
    return dict(_INSUFFICIENT_TREND)


def _liquidity(contract: Optional[Mapping[str, object]]) -> dict[str, object]:
    if contract is None:
        return {"tier": None, "observation_count": None, "source_mix": None}
    count = _int(contract, ("sample_size", "sampleSize", "observation_count", "observationCount"))
    if count is None or count <= 0:
        tier = None
    elif count >= _LIQUIDITY_ACTIVE_MIN:
        tier = "active"
    elif count >= _LIQUIDITY_THIN_MIN:
        tier = "thin"
    else:
        tier = "illiquid"
    source_mix = contract.get("source_mix")
    if not isinstance(source_mix, Mapping) or not source_mix:
        source_mix = None
    else:
        source_mix = dict(source_mix)
    return {"tier": tier, "observation_count": count, "source_mix": source_mix}


def _benchmark_recency(
    contract: Optional[Mapping[str, object]], now: datetime
) -> dict[str, object]:
    if contract is None:
        return {"as_of": None, "age_days": None, "freshness": None}
    as_of_raw = _string(contract, ("published_at", "publishedAt", "as_of", "asOf"))
    published = _parse_iso(as_of_raw)
    if published is None:
        return {"as_of": as_of_raw, "age_days": None, "freshness": None}
    age_days = (now - published).days
    if age_days < 0:
        age_days = 0
    if age_days <= _RECENCY_CURRENT_MAX_DAYS:
        freshness = "current"
    elif age_days <= _RECENCY_AGING_MAX_DAYS:
        freshness = "aging"
    else:
        freshness = "stale"
    return {"as_of": as_of_raw, "age_days": age_days, "freshness": freshness}


def _coverage(contract: Optional[Mapping[str, object]]) -> dict[str, object]:
    if contract is None:
        return {"tier": None, "is_borrowed": None, "region_key": None, "scope_stage": None}
    tier = _string(contract, ("tier",))
    explicit_borrowed = contract.get("is_borrowed")
    if isinstance(explicit_borrowed, bool):
        is_borrowed = explicit_borrowed
    elif tier is not None:
        is_borrowed = tier.lower() == "borrowed"
    else:
        is_borrowed = None
    return {
        "tier": tier,
        "is_borrowed": is_borrowed,
        "region_key": _string(contract, ("region_key", "regionKey")),
        "scope_stage": _string(contract, ("scope_stage", "scopeStage")),
    }


def _transferability(owner_discount: Optional[float]) -> dict[str, object]:
    if owner_discount is None:
        return {"owner_dependency_discount_pct": None, "readiness": None}
    if owner_discount >= _READINESS_LOW_MIN:
        readiness = "low"
    elif owner_discount >= _READINESS_MODERATE_MIN:
        readiness = "moderate"
    else:
        readiness = "high"
    return {
        "owner_dependency_discount_pct": round(owner_discount * 100, 1),
        "readiness": readiness,
    }


# --- defensive coercion helpers (mirrors the Titan extractor pattern) ---------------------


def _normalise_fraction(value: object) -> Optional[float]:
    """A discount as a positive fraction. Accepts -0.20 / 0.20 / 20 (percent-points)."""
    number = _to_float(value)
    if number is None:
        return None
    magnitude = abs(number)
    # A zero discount is "not assessed" on this path (the stateless engine doesn't run the
    # 12-factor owner-dependency model), not a genuine "no key-man risk" — so emit no signal
    # rather than a misleading "high readiness".
    if magnitude == 0:
        return None
    return magnitude / 100 if magnitude > 1 else magnitude


def _to_float(value: object) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if _is_finite(float(value)) else None
    if isinstance(value, str) and value.strip():
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if _is_finite(parsed) else None
    return None


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def _int(contract: Mapping[str, object], keys: tuple[str, ...]) -> Optional[int]:
    for key in keys:
        number = _to_float(contract.get(key))
        if number is not None:
            return int(number)
    return None


def _string(contract: Mapping[str, object], keys: tuple[str, ...]) -> Optional[str]:
    for key in keys:
        value = contract.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _string_value(value: object) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        # Date-only or unrecognised → try the leading date.
        try:
            parsed = datetime.fromisoformat(text[:10])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
