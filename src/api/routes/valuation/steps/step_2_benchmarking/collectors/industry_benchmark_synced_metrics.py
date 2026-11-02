"""Synced business-types DB metric helpers for Step 2 benchmarks."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional

from src.api.business_type_mix import normalize_business_type_mix_fields
from src.utils.country_code import normalize_iso3166_alpha2
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


def _synced_business_type_metrics(
    business_type_id: Optional[str], country_code: Optional[str]
) -> Dict[str, object]:
    """Build EV/EBITDA, EV/Revenue and P/E metric distributions for a business
    type from the synced business-types DB snapshot (the local cache of the
    business_types database).

    Returns a Titan-enrichment-shaped dict (``{"ev_ebitda": {"median","p25",
    "p75"}, ...}``) so the engine can USE the DB whenever it is available, even
    when Titan did not push enrichment. Returns ``{}`` and NEVER raises when the
    snapshot is missing/corrupt or the type is unknown, so report generation
    degrades gracefully to the existing fallbacks instead of failing.
    """
    if not business_type_id:
        return {}
    try:
        from src.database.business_types_repository import get_business_types_repository

        cc = normalize_iso3166_alpha2(str(country_code).strip() if country_code else None) or "BE"
        with get_business_types_repository() as repo:
            benchmarks = repo.get_benchmarks(str(business_type_id), cc)
    except Exception as exc:  # never let a DB hiccup break a valuation
        logger.debug(
            "Synced business-types DB unavailable for collector; using next fallback",
            extra={"business_type_id": business_type_id, "error": str(exc)},
        )
        return {}

    out: Dict[str, object] = {}
    key_map = {
        "ev_ebitda_multiple": "ev_ebitda",
        "ev_revenue_multiple": "ev_revenue",
        "pe_multiple": "pe_ratio",
    }
    for bm in benchmarks or []:
        target = key_map.get(getattr(bm, "metric_name", ""))
        if target is None or bm.median is None:
            continue
        try:
            median = float(bm.median)
        except (TypeError, ValueError):
            continue
        dist: Dict[str, object] = {"median": median}
        # Attach the band only when internally consistent (p25 ≤ median ≤ p75) —
        # some legacy cache rows carry malformed percentiles we must not ship.
        try:
            p25 = float(bm.p25) if bm.p25 is not None else None
            p75 = float(bm.p75) if bm.p75 is not None else None
            if p25 is not None and p75 is not None and p25 <= median <= p75:
                dist["p25"] = p25
                dist["p75"] = p75
        except (TypeError, ValueError):
            pass
        out[target] = dist
    return out


def _normalized_business_type_mix_from_request(request: object) -> List[Dict[str, object]]:
    """Return an explicit weighted business-type mix from a request, if present."""
    try:
        _, mix, _ = normalize_business_type_mix_fields(
            business_type_mix=getattr(request, "business_type_mix", None),
            business_type_segments=getattr(request, "business_type_segments", None),
            business_type_weights=getattr(request, "business_type_weights", None),
            business_type_id=None,
        )
    except ValueError:
        return []
    return mix or []


def _safe_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _weighted_distribution(
    weighted_distributions: List[tuple[Decimal, Dict[str, object]]],
) -> Dict[str, object]:
    out: Dict[str, object] = {}
    for field in ("median", "p10", "p25", "p75", "p90"):
        weighted = Decimal("0")
        weight_total = Decimal("0")
        for weight, distribution in weighted_distributions:
            value = _safe_decimal(distribution.get(field))
            if value is None:
                continue
            weighted += value * weight
            weight_total += weight
        if weight_total > 0:
            value = weighted / weight_total
            out[field] = float(value.quantize(Decimal("0.0001")))
    return out


def _synced_business_type_mix_metrics(
    business_type_mix: List[Dict[str, object]],
    country_code: Optional[str],
) -> Dict[str, object]:
    """Blend synced business-types DB metrics for an explicit weighted mix.

    The mix path deliberately requires every positive-weight segment to resolve
    before returning a composite. Falling back to the primary type would make a
    custom 60/40 profile behave like a single-type company, which is exactly the
    ambiguity the weighted contract is meant to remove.
    """
    if len(business_type_mix) <= 1:
        return {}

    segment_metrics: List[tuple[Decimal, Dict[str, object]]] = []
    for segment in business_type_mix:
        business_type_id = str(segment.get("business_type_id") or "").strip()
        weight = _safe_decimal(segment.get("weight"))
        if not business_type_id or weight is None or weight <= 0:
            continue
        metrics = _synced_business_type_metrics(business_type_id, country_code)
        if not metrics.get("ev_ebitda"):
            return {}
        segment_metrics.append((weight / Decimal("100"), metrics))

    if len(segment_metrics) != len(business_type_mix):
        return {}

    out: Dict[str, object] = {}
    for metric_name in ("ev_ebitda", "ev_revenue", "pe_ratio"):
        distributions = []
        for weight, metrics in segment_metrics:
            distribution = metrics.get(metric_name)
            if not isinstance(distribution, dict) or distribution.get("median") is None:
                distributions = []
                break
            distributions.append((weight, distribution))
        if distributions:
            blended = _weighted_distribution(distributions)
            if blended.get("median") is not None:
                out[metric_name] = blended
    if out:
        out["business_type_mix"] = business_type_mix
    return out
