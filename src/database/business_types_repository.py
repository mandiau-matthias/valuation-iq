"""
Business Types Repository - Stateless Cache-Backed Implementation

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (the muscle) remains stateless. In normal operation the
authoritative source is Titan enrichment. When Titan enrichment is missing,
this repository provides a deterministic secondary source using the synced
business types cache shipped with the app.

This keeps "DB-backed" call sites functional without requiring runtime DB
access, while still making degradation explicit.
"""

import json
import threading
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.database.connection import is_stateless_mode
from src.utils.country_code import normalize_iso3166_alpha2
from src.utils.decimal_helpers import optional_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BusinessTypeBenchmark:
    """Benchmark metric for a business type (ev_ebitda, ev_revenue, etc.).

    Provenance fields (audit closure 2026-05-02) carry the Delphi triage
    metadata through to the report layer so the cover-confidence chip and
    the "Source: Layer N (provider, n=K, as_of YYYY-MM)" footer can render
    truthfully. All optional — older cached payloads without these fields
    keep working unchanged.
    """

    metric_name: str
    median: Optional[Decimal] = None
    p25: Optional[Decimal] = None
    p75: Optional[Decimal] = None
    sample_size: int = 0
    # Provenance — sourced from `business_type_benchmarks.*` columns and
    # `multiples_metadata` JSONB written by Athena's publish path.
    country_basis: Optional[str] = None  # native | aggregate_clone | aggregate
    selected_layer: Optional[int] = None  # 1..7 from Delphi triage
    confidence_band: Optional[str] = None  # high | medium | low | seed
    source_alignment: Optional[str] = (
        None  # independent_confirmation | single_source | not_disclosed
    )
    freshness_band: Optional[str] = None  # fresh | recent | stale | unknown
    last_observation_at: Optional[str] = None  # ISO date of newest observation
    attribution_required: Optional[str] = None  # e.g. "Damodaran (NYU Stern)"


@dataclass
class BusinessTypeMetadata:
    """Metadata for a business type used across triage and calibration."""

    id: str
    title: str
    industry: str
    category: Optional[str] = None
    category_id: Optional[str] = None
    industry_mapping: Optional[str] = None
    owner_dependency_impact: Optional[Decimal] = None
    dcf_preference: Optional[Decimal] = None
    multiples_preference: Optional[Decimal] = None
    # 4-axis blend: asset_preference / re_yield_preference shipped in
    # the 20260502 migration. Both default None; the repository keeps
    # them optional so the cache layer + read path stay backward
    # compatible while delphi seeds the asset-anchored sectors.
    asset_preference: Optional[Decimal] = None
    re_yield_preference: Optional[Decimal] = None
    preferred_multiples: List[str] = field(default_factory=list)
    key_metrics: List[str] = field(default_factory=list)
    typical_revenue_min: Optional[Decimal] = None
    typical_revenue_max: Optional[Decimal] = None
    ev_ebitda_multiple: Optional[Decimal] = None
    ev_ebitda_multiple_p25: Optional[Decimal] = None
    ev_ebitda_multiple_p75: Optional[Decimal] = None
    ev_revenue_multiple: Optional[Decimal] = None
    ev_revenue_multiple_p25: Optional[Decimal] = None
    ev_revenue_multiple_p75: Optional[Decimal] = None
    pe_multiple: Optional[Decimal] = None
    pe_multiple_p25: Optional[Decimal] = None
    pe_multiple_p75: Optional[Decimal] = None
    multiples_metadata: Optional[Dict[str, object]] = None
    sde_calibration: Optional[Dict[str, object]] = None


# There is one generated, release-gated catalog snapshot.  Do not fall back to
# the old ``constants`` copy: that file predates catalog additions and would
# silently make supported business types disappear when the canonical artifact
# is missing from an image.  An absent canonical cache is intentionally handled
# as unavailable data below, so benchmark resolution fails closed.
_CACHE_CANDIDATES: Tuple[Path, ...] = (
    Path(__file__).resolve().parents[1] / "config" / "synced_business_types.json",
)
_LEGACY_ID_ALIASES: Dict[str, str] = {
    "accounting-firm": "accounting",
    "consulting-firm": "consulting",
    "ecommerce-platform": "ecommerce",
    "saas-platform": "saas",
    "software-development": "webdev",
    "cleaning-services": "cleaning",
    "fintech-lending-credit": "fintech-lending",
    "fintech_lending_credit": "fintech-lending",
}
_CACHE_STATE: Optional[
    Tuple[Dict[str, BusinessTypeMetadata], Dict[str, str], Dict[str, object]]
] = None
_CACHE_LOCK = threading.Lock()


def _first_present(raw_item: Dict[str, object], *keys: str) -> object:
    for key in keys:
        if key in raw_item and raw_item[key] is not None:
            return raw_item[key]
    return None


def _decimal_js_to_decimal(value: Dict[str, object]) -> Optional[Decimal]:
    chunks = value.get("d")
    if not isinstance(chunks, list) or not chunks:
        return None

    try:
        digits = str(int(chunks[0]))
        digits += "".join(f"{int(chunk):07d}" for chunk in chunks[1:])
        exponent = int(value.get("e") or 0)
        sign = Decimal("-1") if int(value.get("s") or 1) < 0 else Decimal("1")
        scale = exponent - len(digits) + 1
        return sign * Decimal(digits) * (Decimal(10) ** scale)
    except (TypeError, ValueError):
        return None


def _safe_decimal(value: object) -> Optional[Decimal]:
    if isinstance(value, dict) and {"s", "e", "d"}.issubset(value):
        return _decimal_js_to_decimal(value)
    return optional_decimal(value)


_PREFERRED_MULTIPLE_LABELS: Dict[str, str] = {
    "arr": "EV/ARR",
    "ev_arr": "EV/ARR",
    "evarr": "EV/ARR",
    "ev/arr": "EV/ARR",
    "ebitda": "EV/EBITDA",
    "ev_ebitda": "EV/EBITDA",
    "evebitda": "EV/EBITDA",
    "ev/ebitda": "EV/EBITDA",
    "ev_revenue": "EV/Revenue",
    "ev/sales": "EV/Revenue",
    "ev/revenue": "EV/Revenue",
    "ev_sales": "EV/Revenue",
    "evrevenue": "EV/Revenue",
    "revenue": "EV/Revenue",
    "sales": "EV/Revenue",
    "p/e": "P/E",
    "pe": "P/E",
    "pe_ratio": "P/E",
    "peratio": "P/E",
}


def _normalize_preferred_multiple(value: object) -> str:
    raw = str(value).strip()
    token = raw.lower().replace("-", "_").replace(" ", "_")
    return _PREFERRED_MULTIPLE_LABELS.get(token, raw)


def _normalize_identifier(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower().replace("_", "-")


def _derive_preferred_multiples(
    raw_item: Dict[str, object], category_id: Optional[str]
) -> List[str]:
    explicit = raw_item.get("preferred_multiples") or raw_item.get("preferredMultiples")
    if isinstance(explicit, list) and explicit:
        normalized: List[str] = []
        for item in explicit:
            label = _normalize_preferred_multiple(item)
            if label and label not in normalized:
                normalized.append(label)
        return normalized

    category = (category_id or "").lower()
    industry_mapping = str(raw_item.get("industryMapping") or "").lower()
    title = str(raw_item.get("title") or "").lower()

    if "saas" in title or "technology" in industry_mapping or category == "tech-digital":
        return ["EV/Revenue", "EV/EBITDA"]
    if "ecommerce" in title or category == "ecommerce-retail":
        return ["EV/Revenue", "EV/EBITDA"]
    return ["EV/EBITDA"]


def _build_sde_calibration(raw_item: Dict[str, object]) -> Optional[Dict[str, object]]:
    fields = {
        "sde_multiple_micro": raw_item.get("sde_multiple_micro"),
        "sde_multiple_small": raw_item.get("sde_multiple_small"),
        "sde_multiple_medium": raw_item.get("sde_multiple_medium"),
        "sde_multiple_p25": raw_item.get("sde_multiple_p25"),
        "sde_multiple_p75": raw_item.get("sde_multiple_p75"),
        "sde_owner_dependency_factor": raw_item.get("sde_owner_dependency_factor"),
        "sde_recurring_revenue_factor": raw_item.get("sde_recurring_revenue_factor"),
        "sde_growth_factor": raw_item.get("sde_growth_factor"),
        "sde_sample_size": raw_item.get("sde_sample_size"),
        "sde_source": raw_item.get("sde_source"),
    }
    if not any(value is not None for value in fields.values()):
        return None
    return fields


_MULTIPLE_BOUNDS: Dict[str, Tuple[Decimal, Decimal]] = {
    "ev_ebitda_multiple": (Decimal("0.5"), Decimal("40")),
    "ev_revenue_multiple": (Decimal("0.05"), Decimal("30")),
    "pe_multiple": (Decimal("1"), Decimal("60")),
}
_CLAMP_WARNING_KEYS: set[Tuple[str, Decimal, Decimal]] = set()
_CLAMP_WARNING_LOCK = threading.Lock()


def _clamp_multiple(value: Optional[Decimal], key: str) -> Optional[Decimal]:
    if value is None:
        return None
    lo, hi = _MULTIPLE_BOUNDS.get(key, (Decimal("0"), Decimal("100")))
    if value < lo or value > hi:
        warning_key = (key, lo, hi)
        with _CLAMP_WARNING_LOCK:
            should_warn = warning_key not in _CLAMP_WARNING_KEYS
            if should_warn:
                _CLAMP_WARNING_KEYS.add(warning_key)
        log = logger.info if should_warn else logger.debug
        log(
            "Multiple %s out of range (%.2f), clamping to [%.1f, %.1f]",
            key,
            value,
            lo,
            hi,
        )
        return max(lo, min(value, hi))
    return value


def _extract_distribution(
    raw_item: Dict[str, object],
    snake_key: str,
    camel_key: str,
    median_aliases: Tuple[str, ...] = (),
    p25_aliases: Tuple[str, ...] = (),
    p75_aliases: Tuple[str, ...] = (),
) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    raw_value = _first_present(raw_item, snake_key, camel_key, *median_aliases)
    median = _safe_decimal(raw_value)
    p25 = _safe_decimal(_first_present(raw_item, f"{snake_key}_p25", *p25_aliases))
    p75 = _safe_decimal(_first_present(raw_item, f"{snake_key}_p75", *p75_aliases))

    if isinstance(raw_value, dict) and not {"s", "e", "d"}.issubset(raw_value):
        median = _safe_decimal(raw_value.get("median"))
        p25 = _safe_decimal(raw_value.get("p25")) or p25
        p75 = _safe_decimal(raw_value.get("p75")) or p75

    median = _clamp_multiple(median, snake_key)
    p25 = _clamp_multiple(p25, snake_key)
    p75 = _clamp_multiple(p75, snake_key)

    return median, p25, p75


def _build_multiples_metadata(raw_item: Dict[str, object]) -> Optional[Dict[str, object]]:
    raw_metadata = raw_item.get("multiples_metadata") or raw_item.get("multiplesMetadata")
    metadata: Dict[str, object] = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}

    # The synced catalogue snapshot carries sample size and quality score as
    # top-level columns rather than inside a `multiples_metadata` blob, and
    # encodes the score with decimal.js. Fold them in so both shapes work —
    # otherwise `meta.get("sample_size")` below is always absent and every
    # benchmark reports sample_size 0.
    for key, aliases in (
        ("sample_size", ("multiples_sample_size", "multiplesSampleSize")),
        ("quality_score", ("multiples_quality_score", "multiplesQualityScore")),
    ):
        if metadata.get(key) is not None:
            continue
        for alias in aliases:
            if alias not in raw_item:
                continue
            value = _safe_decimal(raw_item.get(alias))
            if value is not None:
                metadata[key] = int(value) if key == "sample_size" else value
            break

    return metadata or None


def _build_metadata(raw_item: Dict[str, object]) -> Optional[BusinessTypeMetadata]:
    business_type_id = _normalize_identifier(raw_item.get("id"))
    if not business_type_id:
        return None

    category_id = _normalize_identifier(
        raw_item.get("category_id") or raw_item.get("categoryId") or raw_item.get("category")
    )
    industry_mapping = (
        raw_item.get("industry")
        or raw_item.get("industryMapping")
        or raw_item.get("industry_mapping")
    )
    typical_revenue = (
        raw_item.get("typicalRevenueRange") or raw_item.get("typical_revenue_range") or {}
    )
    ev_ebitda_multiple, ev_ebitda_multiple_p25, ev_ebitda_multiple_p75 = _extract_distribution(
        raw_item,
        "ev_ebitda_multiple",
        "evEbitdaMultiple",
        ("ev_ebitda_median", "evEbitdaMedian"),
        ("ev_ebitda_p25", "evEbitdaP25"),
        ("ev_ebitda_p75", "evEbitdaP75"),
    )
    ev_revenue_multiple, ev_revenue_multiple_p25, ev_revenue_multiple_p75 = _extract_distribution(
        raw_item,
        "ev_revenue_multiple",
        "evRevenueMultiple",
        ("ev_revenue_median", "evRevenueMedian"),
        ("ev_revenue_p25", "evRevenueP25"),
        ("ev_revenue_p75", "evRevenueP75"),
    )
    pe_multiple, pe_multiple_p25, pe_multiple_p75 = _extract_distribution(
        raw_item,
        "pe_multiple",
        "peMultiple",
        ("pe_ratio_median", "peRatioMedian"),
        ("pe_ratio_p25", "peRatioP25"),
        ("pe_ratio_p75", "peRatioP75"),
    )

    return BusinessTypeMetadata(
        id=business_type_id,
        title=raw_item.get("title", business_type_id),
        industry=str(industry_mapping or category_id or "services"),
        category=category_id,
        category_id=category_id,
        industry_mapping=str(industry_mapping) if industry_mapping else None,
        owner_dependency_impact=_safe_decimal(
            _first_present(raw_item, "owner_dependency_impact", "ownerDependencyImpact")
        ),
        dcf_preference=_safe_decimal(_first_present(raw_item, "dcf_preference", "dcfPreference")),
        multiples_preference=_safe_decimal(
            _first_present(raw_item, "multiples_preference", "multiplesPreference")
        ),
        # New 4-axis weight signals — both NULL until the delphi seed
        # pipeline populates them for asset-anchored sectors. Snake- and
        # camel-case keys both supported because the cached JSON snapshot
        # may come from either convention depending on the dataset version.
        asset_preference=_safe_decimal(
            _first_present(
                raw_item,
                "asset_preference",
                "assetPreference",
                "asset_methodology_preference",
                "assetMethodologyPreference",
            )
        ),
        re_yield_preference=_safe_decimal(
            _first_present(
                raw_item,
                "re_yield_preference",
                "reYieldPreference",
                "re_yield_methodology_preference",
                "reYieldMethodologyPreference",
            )
        ),
        preferred_multiples=_derive_preferred_multiples(raw_item, category_id),
        key_metrics=[
            str(metric)
            for metric in (raw_item.get("key_metrics") or raw_item.get("keyMetrics") or [])
        ],
        typical_revenue_min=_safe_decimal(typical_revenue.get("min")),
        typical_revenue_max=_safe_decimal(typical_revenue.get("max")),
        ev_ebitda_multiple=ev_ebitda_multiple,
        ev_ebitda_multiple_p25=ev_ebitda_multiple_p25,
        ev_ebitda_multiple_p75=ev_ebitda_multiple_p75,
        ev_revenue_multiple=ev_revenue_multiple,
        ev_revenue_multiple_p25=ev_revenue_multiple_p25,
        ev_revenue_multiple_p75=ev_revenue_multiple_p75,
        pe_multiple=pe_multiple,
        pe_multiple_p25=pe_multiple_p25,
        pe_multiple_p75=pe_multiple_p75,
        multiples_metadata=_build_multiples_metadata(raw_item),
        sde_calibration=_build_sde_calibration(raw_item),
    )


def _load_cache_state() -> (
    Tuple[Dict[str, BusinessTypeMetadata], Dict[str, str], Dict[str, object]]
):
    global _CACHE_STATE
    if _CACHE_STATE is not None:
        return _CACHE_STATE

    with _CACHE_LOCK:
        if _CACHE_STATE is not None:
            return _CACHE_STATE
        return _load_cache_state_locked()


def _load_cache_state_locked() -> (
    Tuple[Dict[str, BusinessTypeMetadata], Dict[str, str], Dict[str, object]]
):
    """Inner loader, called under _CACHE_LOCK exactly once."""
    global _CACHE_STATE

    cache_path = next((candidate for candidate in _CACHE_CANDIDATES if candidate.exists()), None)
    if cache_path is None:
        logger.error(
            "Synced business types cache missing",
            extra={"candidates": [str(path) for path in _CACHE_CANDIDATES]},
        )
        _CACHE_STATE = (
            {},
            {},
            {"loaded": False, "path": None, "count": 0, "errors": ["cache_missing"]},
        )
        return _CACHE_STATE

    try:
        raw_items = json.loads(cache_path.read_text())
    except Exception as exc:
        logger.error(
            "Failed to load synced business types cache",
            extra={"path": str(cache_path), "error": str(exc), "error_type": type(exc).__name__},
        )
        _CACHE_STATE = (
            {},
            {},
            {"loaded": False, "path": str(cache_path), "count": 0, "errors": [str(exc)]},
        )
        return _CACHE_STATE

    metadata_by_id: Dict[str, BusinessTypeMetadata] = {}
    alias_map: Dict[str, str] = {}
    errors: List[str] = []

    for raw_item in raw_items if isinstance(raw_items, list) else []:
        metadata = _build_metadata(raw_item)
        if metadata is None:
            errors.append("missing_id")
            continue
        metadata_by_id[metadata.id] = metadata
        alias_map[metadata.id] = metadata.id
        alias_map[_normalize_identifier(metadata.title) or metadata.id] = metadata.id
        if metadata.category_id:
            alias_map.setdefault(metadata.category_id, metadata.id)

    for alias, canonical in _LEGACY_ID_ALIASES.items():
        if canonical in metadata_by_id:
            alias_map[alias] = canonical

    diagnostics = {
        "loaded": True,
        "path": str(cache_path),
        "count": len(metadata_by_id),
        "errors": errors,
    }
    if errors:
        logger.warning(
            "Synced business types cache loaded with validation warnings",
            extra=diagnostics,
        )
    else:
        logger.debug("Synced business types cache loaded", extra=diagnostics)

    _CACHE_STATE = (metadata_by_id, alias_map, diagnostics)
    return _CACHE_STATE


class StatelessBusinessTypesRepository:
    """Cache-backed repository for stateless mode."""

    def __enter__(self) -> "StatelessBusinessTypesRepository":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        return None

    def _resolve(self, business_type_id: str) -> Optional[BusinessTypeMetadata]:
        metadata_by_id, alias_map, _ = _load_cache_state()
        normalized = _normalize_identifier(business_type_id)
        if normalized is None:
            return None
        canonical = alias_map.get(normalized, normalized)
        return metadata_by_id.get(canonical)

    async def get_business_type_by_id(self, business_type_id: str) -> Optional[Dict[str, object]]:
        business_type = self.get_business_type(business_type_id)
        if business_type is None:
            return None
        return {
            "id": business_type.id,
            "title": business_type.title,
            "industry": business_type.industry,
            "industry_mapping": business_type.industry_mapping,
            "category_id": business_type.category_id,
            "dcf_preference": business_type.dcf_preference,
            "multiples_preference": business_type.multiples_preference,
            "asset_preference": business_type.asset_preference,
            "re_yield_preference": business_type.re_yield_preference,
            "preferred_multiples": business_type.preferred_multiples,
            "owner_dependency_impact": business_type.owner_dependency_impact,
            "ev_ebitda_multiple": business_type.ev_ebitda_multiple,
            "ev_revenue_multiple": business_type.ev_revenue_multiple,
            "pe_multiple": business_type.pe_multiple,
            "multiples_metadata": business_type.multiples_metadata,
        }

    def get_benchmarks(
        self,
        business_type_id: str,
        country_code: str = "BE",
    ) -> List[BusinessTypeBenchmark]:
        business_type = self._resolve(business_type_id)
        if business_type is None:
            return []
        cc = normalize_iso3166_alpha2(country_code)
        if cc != "BE":
            logger.debug(
                "stateless_repo_no_per_country_cache",
                business_type_id=business_type_id,
                country_code=cc,
                msg="Returning aggregate benchmarks; per-country data requires Titan enrichment",
            )
        multiples = self.get_valuation_multiples(business_type_id, country_code)
        meta = business_type.multiples_metadata or {}

        # Provenance — derived from the JSONB metadata that Athena's publish
        # path stamps onto each row. Top-level keys (newer payloads) are
        # preferred; nested `meta["provenance"]` / `meta["freshness"]` dicts
        # are honored as a fallback for older payloads. All lookups are
        # null-safe so missing keys silently degrade to None.
        def _nested(meta_dict: dict, outer: str, inner: str):
            outer_val = meta_dict.get(outer)
            if isinstance(outer_val, dict):
                return outer_val.get(inner)
            return None

        prov = {
            "country_basis": meta.get("country_basis"),
            "selected_layer": (
                meta.get("selected_layer") or _nested(meta, "provenance", "selected_layer")
            ),
            "confidence_band": meta.get("confidence_band"),
            "source_alignment": meta.get("source_alignment"),
            "freshness_band": (meta.get("freshness_band") or _nested(meta, "freshness", "band")),
            "last_observation_at": meta.get("last_observation_at"),
            "attribution_required": meta.get("attribution_required"),
        }
        benchmarks: List[BusinessTypeBenchmark] = []
        for metric_name in ("ev_ebitda_multiple", "ev_revenue_multiple", "pe_multiple"):
            median = multiples.get(metric_name)
            if median is not None:
                benchmarks.append(
                    BusinessTypeBenchmark(
                        metric_name=metric_name,
                        median=median,
                        p25=getattr(business_type, f"{metric_name}_p25", None),
                        p75=getattr(business_type, f"{metric_name}_p75", None),
                        sample_size=int(meta.get("sample_size", 0) or 0),
                        country_basis=prov["country_basis"],
                        selected_layer=(
                            int(prov["selected_layer"])
                            if prov["selected_layer"] is not None
                            else None
                        ),
                        confidence_band=prov["confidence_band"],
                        source_alignment=prov["source_alignment"],
                        freshness_band=prov["freshness_band"],
                        last_observation_at=prov["last_observation_at"],
                        attribution_required=prov["attribution_required"],
                    )
                )
        return benchmarks

    def get_business_type(self, business_type_id: str) -> Optional[object]:
        return self._resolve(business_type_id)

    def get_industry_for_business_type(self, business_type_id: str) -> Optional[str]:
        business_type = self._resolve(business_type_id)
        if business_type is None:
            return None
        return business_type.industry_mapping or business_type.industry

    def get_valuation_multiples(
        self,
        business_type_id: str,
        country_code: str = "BE",
    ) -> Dict[str, object]:
        cc = normalize_iso3166_alpha2(country_code)
        if cc != "BE":
            logger.debug(
                "stateless_valuation_multiples_aggregate_only",
                business_type_id=business_type_id,
                country_code=cc,
                note="Synced cache has no per-country rows; use Titan enrichment for country-specific multiples.",
            )
        business_type = self._resolve(business_type_id)
        if business_type is None:
            return {}

        result: Dict[str, object] = {}
        if business_type.ev_ebitda_multiple is not None:
            result["ev_ebitda_multiple"] = business_type.ev_ebitda_multiple
        if business_type.ev_revenue_multiple is not None:
            result["ev_revenue_multiple"] = business_type.ev_revenue_multiple
        if business_type.pe_multiple is not None:
            result["pe_multiple"] = business_type.pe_multiple
        return result

    async def get_hybrid_weights(self, business_type_id: str) -> Optional[Dict[str, Decimal]]:
        """Legacy 2-axis blend (DCF / Multiples).

        Kept for backward compatibility with the existing
        ``hybrid_weight_calculator`` consumer. Callers that need the full
        4-axis blend (asset / yield) should use ``get_method_weights``
        below — that variant returns the same DCF / Multiples values
        plus the new asset_preference + re_yield_preference axes when
        the data team has seeded them.
        """
        business_type = self._resolve(business_type_id)
        if business_type is None:
            return None
        dcf_weight = business_type.dcf_preference
        multiples_weight = business_type.multiples_preference
        if dcf_weight is None or multiples_weight is None:
            return None
        total = dcf_weight + multiples_weight
        if total <= 0:
            return None
        return {"dcf": dcf_weight / total, "multiples": multiples_weight / total}

    async def get_method_weights(self, business_type_id: str) -> Optional[Dict[str, Decimal]]:
        """Full 4-axis method weights, renormalised across non-NULL axes.

        Returns ``{"dcf", "multiples", "asset", "re_yield"}`` summing to
        1.0, omitting any axis whose preference is NULL or 0 in the DB.
        Returns ``None`` when the business type has no preference data
        whatsoever (caller should fall through to the next priority in
        ``hybrid_weight_calculator`` — typically the hardcoded fallback
        or the profitability heuristic).

        The four-axis contract was added in the 20260502 migration to
        support asset-anchored sectors (holdings, vastgoed) where neither
        DCF nor Multiples carries the substance. Callers can introspect
        the returned dict to route the engine to the right path:

        * ``re_yield`` is the dominant axis → real-estate yield method
        * ``asset`` is the dominant axis → adjusted-NAV / asset-based
        * ``dcf`` / ``multiples`` dominate → existing flow

        Backward-compatible by design: a business type with only
        ``dcf_preference`` + ``multiples_preference`` set produces the
        same shape as the legacy ``get_hybrid_weights`` (just two keys).
        """
        business_type = self._resolve(business_type_id)
        if business_type is None:
            return None

        components = {
            "dcf": business_type.dcf_preference,
            "multiples": business_type.multiples_preference,
            "asset": business_type.asset_preference,
            "re_yield": business_type.re_yield_preference,
        }
        # Drop NULL / zero axes so the renormalisation only spans the
        # axes the data team actually expressed an opinion on.
        active = {k: v for k, v in components.items() if v is not None and v > 0}
        if not active:
            return None

        total = sum(active.values())
        if total <= 0:
            return None
        return {k: v / total for k, v in active.items()}


BusinessTypesRepository = StatelessBusinessTypesRepository


def get_business_types_repository() -> StatelessBusinessTypesRepository:
    if is_stateless_mode():
        logger.debug("Using stateless business types repository (synced cache)")
    return StatelessBusinessTypesRepository()


def get_synced_business_types_diagnostics() -> Dict[str, object]:
    """Return diagnostics for the synced business types cache."""
    _, _, diagnostics = _load_cache_state()
    return dict(diagnostics)
