"""Industry display helpers for report contexts."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from src.utils.logging import get_logger

logger = get_logger(__name__)

INDUSTRY_EMOJI_KEYWORDS = {
    "bakkerij": "🥐",
    "bakery": "🥐",
    "bakker": "🥐",
    "restaurant": "🍽️",
    "food": "🍽️",
    "hospitality": "🍽️",
    "catering": "🍽️",
    "tech": "💻",
    "software": "💻",
    "it ": "💻",
    "digital": "💻",
    "saas": "☁️",
    "cloud": "☁️",
    "retail": "🛒",
    "store": "🛒",
    "shop": "🛒",
    "ecommerce": "📦",
    "e-commerce": "📦",
    "manufacturing": "🏭",
    "industrial": "🏭",
    "production": "🏭",
    "logistics": "🚚",
    "transport": "🚚",
    "shipping": "🚚",
    "healthcare": "🏥",
    "medical": "🏥",
    "pharma": "💊",
    "education": "📚",
    "training": "📚",
    "school": "📚",
    "real estate": "🏠",
    "property": "🏠",
    "finance": "💰",
    "banking": "🏦",
    "insurance": "📊",
    "construction": "🔨",
    "building": "🏗️",
    "bouw": "🔨",
    "energy": "⚡",
    "power": "⚡",
    "solar": "☀️",
    "creative": "🎨",
    "media": "🎬",
    "advertising": "📢",
    "services": "💼",
    "consulting": "💼",
    "professional": "💼",
    "general business": "💼",
    "agriculture": "🌾",
    "farm": "🌾",
}


@dataclass(frozen=True)
class BusinessTypeDisplayEntry:
    id: str
    title: str | None
    icon: str | None
    primary_nace_code: str | None


def _normalize_emoji_alias(value: str | None) -> str:
    """Normalize business type labels for stable emoji matching."""
    if not value:
        return ""
    normalized = str(value).strip().lower().replace("&", " and ")
    normalized = normalized.replace("/", " ").replace("-", " ").replace("_", " ")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


@lru_cache(maxsize=1)
def _load_db_business_type_json_entries() -> tuple[Mapping[str, object], ...]:
    """Load synced business type rows from the shipped ValuationIQ cache."""
    # Keep report labels on the same release-gated snapshot used by valuation
    # calculations.  Falling back to the legacy constants copy can produce a
    # different industry/NACE label from the calculation for newly added types.
    candidates = (
        Path(__file__).parent.parent.parent / "config" / "synced_business_types.json",
    )

    for path in candidates:
        if not path.exists():
            continue
        try:
            entries = json.loads(path.read_text())
        except Exception:
            logger.warning(
                "Failed to read synced business types for emoji map", extra={"path": str(path)}
            )
            continue
        if not isinstance(entries, list):
            continue
        return tuple(entry for entry in entries if isinstance(entry, Mapping))

    return ()


@lru_cache(maxsize=1)
def _load_db_business_type_emoji_map() -> Mapping[str, str]:
    """Load explicit emoji coverage for all synced business types."""
    db_map: dict[str, str] = {}
    for entry in _load_db_business_type_json_entries():
        emoji = _business_type_entry_icon(entry)
        if not emoji:
            continue
        for alias in _business_type_entry_emoji_aliases(entry):
            db_map[alias] = emoji
    return MappingProxyType(db_map)


def _business_type_entry_icon(entry: Mapping[str, object]) -> str | None:
    emoji = entry.get("icon")
    if not emoji or str(emoji) == "🏢":
        return None
    return str(emoji)


def _business_type_entry_emoji_aliases(entry: Mapping[str, object]) -> set[str]:
    aliases = {
        _normalize_emoji_alias(str(entry.get("id") or "")),
        _normalize_emoji_alias(str(entry.get("title") or "")),
        _normalize_emoji_alias(str(entry.get("category") or "")),
        _normalize_emoji_alias(str(entry.get("categoryId") or "")),
        _normalize_emoji_alias(str(entry.get("industryMapping") or "")),
    }
    keywords = entry.get("keywords", [])
    if isinstance(keywords, list):
        aliases.update(_normalize_emoji_alias(str(keyword)) for keyword in keywords if keyword)
    return {alias for alias in aliases if alias}


@lru_cache(maxsize=1)
def _load_db_business_type_display_entries() -> tuple[BusinessTypeDisplayEntry, ...]:
    """Load report display metadata keyed by business type and primary NACE."""
    display_entries: list[BusinessTypeDisplayEntry] = []
    for entry in _load_db_business_type_json_entries():
        business_type_id = str(entry.get("id") or "").strip()
        if not business_type_id:
            continue
        display_entries.append(
            BusinessTypeDisplayEntry(
                id=business_type_id,
                title=str(entry.get("title")) if entry.get("title") else None,
                icon=str(entry.get("icon")) if entry.get("icon") else None,
                primary_nace_code=(
                    str(entry.get("primaryNaceCode") or entry.get("primary_nace_code"))
                    if entry.get("primaryNaceCode") or entry.get("primary_nace_code")
                    else None
                ),
            )
        )
    return tuple(display_entries)


def _normalize_nace_digits(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))


def get_business_type_display_by_id(
    business_type_id: str | None,
) -> BusinessTypeDisplayEntry | None:
    """Resolve display metadata (incl. primary NACE) for a selected business type id."""
    if not business_type_id:
        return None
    wanted = str(business_type_id).strip().lower()
    if not wanted:
        return None
    for entry in _load_db_business_type_display_entries():
        if entry.id.strip().lower() == wanted:
            return entry
    return None


@dataclass(frozen=True)
class BusinessTypeNaceMismatch:
    """Outcome of cross-checking the selected business type against the registry NACE."""

    is_mismatch: bool
    selected_business_type_id: str | None
    selected_business_type_title: str | None
    selected_nace_code: str | None
    registry_nace_code: str | None
    registry_nace_description: str | None


def detect_business_type_nace_mismatch(
    *,
    business_type_id: str | None,
    registry_nace_code: str | None,
    registry_nace_description: str | None = None,
) -> BusinessTypeNaceMismatch:
    """Flag when the manually-selected business type and the registry NACE diverge.

    The comparison is at the NACE *division* level (the first two digits), which
    is the coarse macro-sector boundary — e.g. ``45`` (motor vehicles) versus
    ``90`` (creative / arts / entertainment).  A divergence here means the
    applied benchmark multiples were calibrated for a different industry than
    the company's registered activity, which a reviewer must see.  Sub-division
    differences within the same division (e.g. 45.31 vs 45.11) are NOT flagged:
    they share a benchmark macro-sector and are commonly imprecise in registries.
    """
    selected = get_business_type_display_by_id(business_type_id)
    selected_nace = selected.primary_nace_code if selected else None
    selected_division = _normalize_nace_digits(selected_nace)[:2]
    registry_division = _normalize_nace_digits(registry_nace_code)[:2]

    # Only assert a mismatch when both divisions are known and clearly differ.
    is_mismatch = bool(
        selected_division
        and registry_division
        and selected_division != registry_division
    )
    return BusinessTypeNaceMismatch(
        is_mismatch=is_mismatch,
        selected_business_type_id=business_type_id,
        selected_business_type_title=(selected.title if selected else None),
        selected_nace_code=selected_nace,
        registry_nace_code=registry_nace_code,
        registry_nace_description=registry_nace_description,
    )


def get_business_type_display_by_nace(nace_code: str | None) -> BusinessTypeDisplayEntry | None:
    """Resolve display metadata from a NACE code using the synced catalog.

    KBO and frontend payloads can send either dotted class codes (``10.71``)
    or detailed activity codes (``10711``). Exact primary-NACE matches win;
    otherwise the longest prefix relation is used, which covers detailed KBO
    activities under a published NACE class without guessing from free text.

    Ties are broken by ``id`` so the answer never depends on the order
    ``synced_business_types.json`` happens to list types in -- that file is
    rewritten wholesale by ``scripts/sync_business_types_api.py``, so array
    order is not stable across syncs. Five codes need this: 2120, 5229, 6492,
    6619 and 62011 each have two types claiming them as ``primaryNaceCode``.
    Same last-resort rule as delphi's ``_load_mappings`` and titan's
    ``selectBestNaceMapping``; see
    db/migrations/railway/20260726_business_type_tie_breaks.sql.

    NOTE: this resolves against ``primaryNaceCode``, which is the TYPE -> CODE
    direction ("which type calls this code home"). It is not the classification
    answer delphi and titan compute, and on the codes where those two were
    realigned in 2026-07 it deliberately differs -- see the module note.
    """
    digits = _normalize_nace_digits(nace_code)
    if not digits:
        return None

    exact: list[BusinessTypeDisplayEntry] = []
    candidates: list[tuple[int, BusinessTypeDisplayEntry]] = []
    for entry in _load_db_business_type_display_entries():
        primary_digits = _normalize_nace_digits(entry.primary_nace_code)
        if not primary_digits:
            continue
        if primary_digits == digits:
            exact.append(entry)
        elif digits.startswith(primary_digits) or primary_digits.startswith(digits):
            candidates.append((len(primary_digits), entry))

    if exact:
        return min(exact, key=lambda entry: entry.id)
    if not candidates:
        return None
    # Longest primary code first, then id. Python's sort is stable, so without
    # the id term equal-length candidates fell through to snapshot order.
    candidates.sort(key=lambda candidate: (-candidate[0], candidate[1].id))
    return candidates[0][1]


INDUSTRY_EMOJI_MAP = {
    _normalize_emoji_alias(key): value for key, value in INDUSTRY_EMOJI_KEYWORDS.items()
}


@lru_cache(maxsize=1)
def _get_industry_emoji_map() -> Mapping[str, str]:
    """Build the full emoji map lazily to avoid import-time file I/O."""
    return MappingProxyType(
        {
            **_load_db_business_type_emoji_map(),
            **INDUSTRY_EMOJI_MAP,
        }
    )


def get_industry_emoji(industry: str | None) -> str:
    """Get emoji for industry, falling back to a generic business icon."""
    if not industry:
        return "🏢"

    lookup_value = industry
    nace_display = get_business_type_display_by_nace(industry)
    if nace_display and nace_display.icon and nace_display.icon != "🏢":
        return nace_display.icon
    if nace_display and nace_display.title:
        lookup_value = nace_display.title

    normalized = _normalize_emoji_alias(lookup_value)
    if not normalized:
        return "🏢"

    emoji_map = _get_industry_emoji_map()

    exact_match = emoji_map.get(normalized)
    if exact_match:
        return exact_match

    normalized_tokens = normalized.split()
    for size in range(len(normalized_tokens), 0, -1):
        for start in range(0, len(normalized_tokens) - size + 1):
            candidate = " ".join(normalized_tokens[start : start + size])
            if candidate in emoji_map:
                return emoji_map[candidate]

    return "🏢"
