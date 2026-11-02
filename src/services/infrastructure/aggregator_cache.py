"""
In-process LRU+TTL cache for MainReportDataAggregator output.

Mercury typically calls /render then /pdf within seconds, and a single
valuation cycle has been observed to produce 5 aggregator passes for one
report (1 during /calculate, then 2 /render + 2 /pdf passes within ~60s).
Each pass rebuilds ~250 context keys, fetches KBO data, and resolves
Delphi benchmarks — strictly redundant when the inputs have not changed.

This module memoises ``aggregate_from_valuation_data(input, locale)`` and
``aggregate(response, request, locale)`` per worker, with a short TTL so
stale data risk during the render→pdf flow is negligible.

Constraints honoured:
- TTL of 60 seconds (short enough that the render→pdf window is the only
  realistic hit zone).
- Bounded size (maxsize=128) — never grows unbounded under burst load.
- In-process per worker (STATELESS_MODE has no Redis).
- Returns a deep copy on every hit so the caller can mutate the dict
  freely (``_build_report_context`` does this heavily).
- Failures are NOT cached: if the aggregator raises, nothing is stored.

Observability: DEBUG logs ``aggregator cache HIT`` / ``aggregator cache MISS``
with the cache key prefix so the render→pdf pattern can be verified in
production.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Hashable, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Keys stripped before hashing the aggregation input — these are heavy
# pre-rendered HTML blobs that ``aggregate_from_valuation_data`` itself
# already discards (see main_report_data_aggregator.py around the
# ``_skip`` set), so they must not contribute to the cache key.
_HASH_SKIP_KEYS = frozenset({"html_report", "pdf_html_report"})

_DEFAULT_MAXSIZE = 128
_DEFAULT_TTL_SECONDS = 60.0


class _LRUTTLCache:
    """Thread-safe LRU cache with per-entry TTL.

    cachetools is not currently a dependency of valuation-iq, so this
    minimal implementation stands in for ``cachetools.TTLCache``. It uses
    an ``OrderedDict`` for LRU ordering and lazy-evicts on get/set.
    """

    def __init__(self, maxsize: int = _DEFAULT_MAXSIZE, ttl: float = _DEFAULT_TTL_SECONDS):
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: "OrderedDict[Any, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Any) -> Optional[Any]:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            ts, val = entry
            if time.monotonic() - ts > self.ttl:
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return val

    def set(self, key: Any, val: Any) -> None:
        with self._lock:
            now = time.monotonic()
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (now, val)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_valuation_data_cache = _LRUTTLCache()
_aggregate_cache = _LRUTTLCache()
_singleflight_locks: dict[Hashable, threading.Lock] = {}
_singleflight_guard = threading.Lock()


def _acquire_singleflight_lock(key: Hashable) -> tuple[bool, threading.Lock]:
    """Return ``(is_leader, lock)`` for a per-key in-process compute gate."""
    with _singleflight_guard:
        lock = _singleflight_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            lock.acquire()
            _singleflight_locks[key] = lock
            return True, lock
        return False, lock


def _release_singleflight_lock(key: Hashable, lock: threading.Lock) -> None:
    with _singleflight_guard:
        if _singleflight_locks.get(key) is lock:
            _singleflight_locks.pop(key, None)
    lock.release()


def _wait_for_singleflight(lock: threading.Lock) -> None:
    with lock:
        return


def _stable_json_default(value: object) -> str:
    """Coerce non-JSON-native scalars to a deterministic string form."""
    try:
        return str(value)
    except Exception:  # pragma: no cover — last-ditch safety
        return repr(value)


def _content_hash(payload: dict) -> str:
    """Compute a deterministic content hash over the aggregation input.

    Strips heavy pre-rendered HTML keys before hashing — the aggregator
    itself discards them, so they must not invalidate the cache.
    """
    stripped = {k: v for k, v in payload.items() if k not in _HASH_SKIP_KEYS}
    try:
        serialized = json.dumps(
            stripped, sort_keys=True, default=_stable_json_default, separators=(",", ":")
        )
    except (TypeError, ValueError):
        return ""
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_locale(locale: Optional[str]) -> str:
    if not isinstance(locale, str):
        return "nl"
    return locale.strip().lower() or "nl"


def _normalize_method(selected_method: object) -> str:
    if not isinstance(selected_method, str):
        return ""
    return selected_method.strip().lower()


def _log_key_prefix(report_id: object) -> str:
    if isinstance(report_id, str) and report_id:
        return report_id[:8]
    return "unknown"


def cached_aggregate_from_valuation_data(
    aggregation_input: dict,
    locale: str,
    *,
    report_id: Optional[str],
    selected_method: Optional[str],
    compute: Callable[[], dict],
) -> dict:
    """Memoise ``aggregator.aggregate_from_valuation_data`` output.

    Args:
        aggregation_input: Exact dict the aggregator would be called with.
            Used to build the content-hash component of the cache key.
        locale: Locale string ("nl" / "en"); normalised before keying.
        report_id: Stable report identifier; included in the key so two
            distinct reports never collide on content hash alone.
        selected_method: User-selected method; normalised before keying.
        compute: Zero-arg callable that produces the aggregator output on
            a cache miss. Called only on miss.

    Returns:
        A fresh deep copy of the aggregator output. The caller may mutate
        it freely without corrupting the cache.
    """
    rid = _log_key_prefix(report_id)
    loc = _normalize_locale(locale)
    method = _normalize_method(selected_method)
    content = _content_hash(aggregation_input)

    if not content:
        # Hash failed (unserialisable payload) — bypass the cache. Better
        # to recompute than risk a false hit.
        logger.debug(
            "aggregator cache BYPASS (unhashable input)",
            extra={"report_id": rid, "locale": loc, "selected_method": method},
        )
        return compute()

    key = ("vd", report_id or "", loc, method, content)
    hit = _valuation_data_cache.get(key)
    if hit is not None:
        logger.debug(
            "aggregator cache HIT",
            extra={
                "report_id": rid,
                "locale": loc,
                "selected_method": method,
                "content_hash": content[:12],
                "cache": "aggregate_from_valuation_data",
            },
        )
        return copy.deepcopy(hit)

    is_leader, singleflight_lock = _acquire_singleflight_lock(key)
    if not is_leader:
        _wait_for_singleflight(singleflight_lock)
        hit = _valuation_data_cache.get(key)
        if hit is not None:
            logger.debug(
                "aggregator cache HIT after singleflight wait",
                extra={
                    "report_id": rid,
                    "locale": loc,
                    "selected_method": method,
                    "content_hash": content[:12],
                    "cache": "aggregate_from_valuation_data",
                },
            )
            return copy.deepcopy(hit)
        # The leader failed or returned a non-cacheable result. This caller
        # becomes the next leader instead of stampeding with all followers.
        return cached_aggregate_from_valuation_data(
            aggregation_input,
            locale,
            report_id=report_id,
            selected_method=selected_method,
            compute=compute,
        )

    logger.debug(
        "aggregator cache MISS",
        extra={
            "report_id": rid,
            "locale": loc,
            "selected_method": method,
            "content_hash": content[:12],
            "cache": "aggregate_from_valuation_data",
        },
    )
    try:
        fresh = compute()
        if isinstance(fresh, dict):
            # Store a deep copy so subsequent caller mutations of ``fresh`` do
            # not corrupt the cached snapshot.
            _valuation_data_cache.set(key, copy.deepcopy(fresh))
        return fresh
    finally:
        _release_singleflight_lock(key, singleflight_lock)


def cached_aggregate(
    response: object,
    request: object,
    locale: str,
    *,
    compute: Callable[[], dict],
) -> dict:
    """Memoise ``aggregator.aggregate(response, request, locale)`` output.

    Keyed on ``(id(response), id(request), valuation_id, locale)``. Within a
    single /calculate pipeline the same response/request objects are passed
    to multiple report-generation methods, so id() is a cheap and reliable
    handle — but ONLY when paired with a stable ``valuation_id``.

    id() is unique only among *live* objects, so within the 60s TTL a freed
    response can be replaced by a *different* one at the same address. Keying on
    id() alone would then return another company's cached context — a
    cross-customer data leak. We therefore REQUIRE a stable valuation_id and
    bypass the cache entirely when one is absent, rather than degrade to
    id()-only keying.
    """
    loc = _normalize_locale(locale)
    valuation_id = getattr(response, "valuation_id", None)
    if not isinstance(valuation_id, (str, int)):
        valuation_id = None

    # No stable identity → never risk an id()-recycle collision; compute fresh.
    if valuation_id is None:
        logger.debug(
            "aggregator cache BYPASS (no valuation_id)",
            extra={"locale": loc, "cache": "aggregate"},
        )
        return compute()

    key = ("agg", id(response), id(request), valuation_id, loc)
    rid = _log_key_prefix(valuation_id)

    hit = _aggregate_cache.get(key)
    if hit is not None:
        logger.debug(
            "aggregator cache HIT",
            extra={
                "report_id": rid,
                "locale": loc,
                "cache": "aggregate",
            },
        )
        return copy.deepcopy(hit)

    is_leader, singleflight_lock = _acquire_singleflight_lock(key)
    if not is_leader:
        _wait_for_singleflight(singleflight_lock)
        hit = _aggregate_cache.get(key)
        if hit is not None:
            logger.debug(
                "aggregator cache HIT after singleflight wait",
                extra={
                    "report_id": rid,
                    "locale": loc,
                    "cache": "aggregate",
                },
            )
            return copy.deepcopy(hit)
        # The leader failed or returned a non-cacheable result. This caller
        # becomes the next leader instead of stampeding with all followers.
        return cached_aggregate(response, request, locale, compute=compute)

    logger.debug(
        "aggregator cache MISS",
        extra={
            "report_id": rid,
            "locale": loc,
            "cache": "aggregate",
        },
    )
    try:
        fresh = compute()
        if isinstance(fresh, dict):
            _aggregate_cache.set(key, copy.deepcopy(fresh))
        return fresh
    finally:
        _release_singleflight_lock(key, singleflight_lock)


def clear_aggregator_caches() -> None:
    """Reset both caches — intended for tests."""
    _valuation_data_cache.clear()
    _aggregate_cache.clear()
    with _singleflight_guard:
        _singleflight_locks.clear()
