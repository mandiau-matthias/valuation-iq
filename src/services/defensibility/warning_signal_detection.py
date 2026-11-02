"""Signal detection helpers for structured defensibility warnings."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, TypeAlias

from src.services.defensibility.methodology import Methodology

JsonMap: TypeAlias = dict[str, object]


def _safe_decimal(value: object, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return default


def _balance_sheet_missing(valuation_data: JsonMap, methodology: Methodology) -> bool:
    if methodology == Methodology.STARTUP:
        return False
    cur = valuation_data.get("current_year_data") or {}
    if not isinstance(cur, dict):
        return False
    cash = _safe_decimal(cur.get("cash"))
    debt = _safe_decimal(cur.get("total_debt"))
    metadata = valuation_data.get("metadata") or {}
    bs_flag = bool(metadata.get("balance_sheet_provided")) if isinstance(metadata, dict) else False
    return not (bs_flag or cash != 0 or debt != 0)


def _owner_normalization_zero(valuation_data: JsonMap, methodology: Methodology) -> bool:
    if methodology not in (
        Methodology.MULTIPLES,
        Methodology.DCF,
        Methodology.HYBRID,
        Methodology.SDE,
        Methodology.UNKNOWN,
    ):
        return False
    total_adj = _safe_decimal(valuation_data.get("total_adjustments"))
    if total_adj != Decimal("0"):
        return False
    metadata = valuation_data.get("metadata") or {}
    owners = _safe_decimal(
        valuation_data.get("owner_managers")
        or (metadata.get("owner_managers") if isinstance(metadata, dict) else None)
    )
    ftes = _safe_decimal(
        valuation_data.get("total_employees")
        or (metadata.get("total_employees") if isinstance(metadata, dict) else None)
    )
    return owners >= Decimal("1") and Decimal("0") < ftes <= Decimal("10")


def _owner_profile_skipped(valuation_data: JsonMap, methodology: Methodology) -> bool:
    if methodology not in (
        Methodology.MULTIPLES,
        Methodology.HYBRID,
        Methodology.SDE,
        Methodology.UNKNOWN,
    ):
        return False
    odr = valuation_data.get("owner_dependency_result")
    if isinstance(odr, dict):
        return False  # completed - different signal handles cap-bound
    metadata = valuation_data.get("metadata") or {}
    owners = _safe_decimal(
        valuation_data.get("owner_managers")
        or (metadata.get("owner_managers") if isinstance(metadata, dict) else None)
    )
    ftes = _safe_decimal(
        valuation_data.get("total_employees")
        or (metadata.get("total_employees") if isinstance(metadata, dict) else None)
    )
    return owners >= Decimal("1") and Decimal("0") < ftes <= Decimal("10")


def _owner_profile_cap_bound(valuation_data: JsonMap) -> bool:
    odr = valuation_data.get("owner_dependency_result")
    if not isinstance(odr, dict):
        return False
    applied = odr.get("valuation_adjustment")
    raw = odr.get("raw_adjustment")
    if applied is None or raw is None:
        return False
    try:
        return _safe_decimal(raw) < _safe_decimal(applied)
    except (ValueError, ArithmeticError):
        return False


def resolve_years_of_data(valuation_data: JsonMap) -> int:
    """Canonical "how many fiscal years does this valuation stand on".

    ONE implementation. There used to be three near-identical copies — here, in
    `scoring._years_of_data` and in `warnings._w_thin_historical` — and all three
    shared the same defect: they returned early on
    `len(historical_years_data) + (1 if current_year_data else 0)`, so a payload
    carrying `current_year_data` but no history list scored 1 and never consulted
    the counts recorded elsewhere.

    Titan persists exactly that shape. A six-year Silverfin import was therefore
    graded as "1 year of historical data", which cost the Academic pillar enough
    to push submit_gate to BLOCK_SOFT — and BLOCK_SOFT is what makes
    `/api/v1/reports/pdf` answer 422 `pdf_blocked_not_share_ready`. The first
    paying advisor experienced that as "PDF export doesn't work".
    """
    hist = valuation_data.get("historical_years_data") or []
    if not isinstance(hist, list):
        hist = []
    has_current = bool(valuation_data.get("current_year_data"))
    direct_years = len(hist) + (1 if has_current else 0)
    if hist:
        return direct_years

    def _to_int(value: object) -> Optional[int]:
        if value is None or isinstance(value, bool):
            return None
        try:
            iv = int(value)
        except (TypeError, ValueError):
            return None
        return iv if iv >= 0 else None

    def _extract(container: JsonMap) -> Optional[int]:
        years = _to_int(container.get("years_of_data"))
        if years is None:
            years = _to_int(container.get("data_years"))
        if years is not None and years > 0:
            return years
        hist_count = _to_int(container.get("historical_years_count"))
        if hist_count is not None:
            return hist_count + (1 if has_current else 0)
        return None

    detailed = valuation_data.get("detailed_results")
    containers: list = [valuation_data]
    if isinstance(detailed, dict):
        containers.append(detailed)
        # The engine's own answer lives in step 0's data-quality breakdown, two
        # levels deeper than anything above looks.
        step_results = detailed.get("step_results")
        if isinstance(step_results, dict):
            for step in step_results.values():
                if not isinstance(step, dict):
                    continue
                result = step.get("result")
                if not isinstance(result, dict):
                    continue
                breakdown = result.get("score_breakdown")
                if isinstance(breakdown, dict):
                    containers.append(breakdown)

    best = 0
    for container in containers:
        if not isinstance(container, dict):
            continue
        years = _extract(container)
        if years is not None and years > best:
            best = years

    return max(best, direct_years)


def _thin_historical(valuation_data: JsonMap, methodology: Methodology) -> bool:
    if methodology == Methodology.STARTUP:
        return False
    years = resolve_years_of_data(valuation_data)
    # No usable signal at all is still thin.
    return years < 3


def _synthetic_percentiles(valuation_data: JsonMap, methodology: Methodology) -> bool:
    if methodology in (Methodology.STARTUP, Methodology.ASSET):
        return False
    detailed = valuation_data.get("detailed_results")
    if not isinstance(detailed, dict):
        detailed = valuation_data
    src = detailed.get("ev_ebitda_percentile_source") or ""
    return isinstance(src, str) and src.startswith("synthetic")


def _generic_multiple_fallback(valuation_data: JsonMap) -> bool:
    """Step 2 PRIORITY 7 - the CRITICAL last-resort 8.0x EBITDA."""
    detailed = valuation_data.get("detailed_results")
    if not isinstance(detailed, dict):
        detailed = valuation_data
    return detailed.get("data_source") == "hardcoded_default"


def _industry_margin_deviation_raw(
    valuation_data: JsonMap,
) -> Optional[JsonMap]:
    """Surface the medium/high industry_margin_deviation entry, if any.

    Mirrors :func:`classifier._extract_margin_warning` (banner) so the typed
    warning fires for the same Three Towers shape that triggers the legacy
    banner copy.
    """
    warnings_list = valuation_data.get("data_quality_warnings") or []
    if not isinstance(warnings_list, list):
        return None
    for w in warnings_list:
        if not isinstance(w, dict):
            continue
        if w.get("type") != "industry_margin_deviation":
            continue
        sev = str(w.get("severity") or "").lower()
        if sev in ("medium", "high"):
            return w
    return None


def _methodology_downgrade(valuation_data: JsonMap) -> Optional[str]:
    """Return the downgrade reason string if the engine fell back, else None.

    Two surfaces emit this signal:
      * `methodology_downgrade_reason` - top-level field set by the
        comprehensive response builder when the engine swapped methods.
      * `detailed_results.dcf_exclusion_reason` - DCF was excluded; report
        falls back to multiples-only.
    """
    reason = valuation_data.get("methodology_downgrade_reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    detailed = valuation_data.get("detailed_results")
    if isinstance(detailed, dict):
        dcf_reason = detailed.get("dcf_exclusion_reason")
        if isinstance(dcf_reason, str) and dcf_reason.strip():
            return dcf_reason.strip()
    return None


def _engine_warnings_by_key(
    valuation_data: JsonMap,
) -> dict[str, JsonMap]:
    """Index aggregator-emitted ``engine_warnings`` by key, latest wins.

    Aggregator stash shape (``main_report_data_aggregator.py:2258, 2334, 2364``):
    ``{"key": str, "severity": str, "message": str}``. We keep the index
    lazy: callers only build the typed warning if the key is present.
    """
    eng = valuation_data.get("engine_warnings")
    if not isinstance(eng, list):
        detailed = valuation_data.get("detailed_results")
        eng = detailed.get("engine_warnings") if isinstance(detailed, dict) else None
    out: dict[str, JsonMap] = {}
    if isinstance(eng, list):
        for w in eng:
            if not isinstance(w, dict):
                continue
            key = w.get("key")
            if isinstance(key, str) and key.strip():
                out[key.strip()] = w
    return out


def _validation_flag_lists_from_payload(payload: JsonMap) -> list[object]:
    flags: list[object] = []
    for key in ("saas_input_validation", "saas_validation_flags"):
        value = payload.get(key)
        if isinstance(value, list):
            flags.extend(value)
    return flags


def _arr_validation_flags(valuation_data: JsonMap) -> list[object]:
    arr = valuation_data.get("arr_multiple")
    if not isinstance(arr, dict):
        return []
    details = arr.get("details") or {}
    if not isinstance(details, dict):
        return []
    flags = details.get("validation_flags")
    return list(flags) if isinstance(flags, list) else []


def _saas_validation_candidates(valuation_data: JsonMap) -> list[object]:
    candidates = _validation_flag_lists_from_payload(valuation_data)
    detailed = valuation_data.get("detailed_results")
    if isinstance(detailed, dict):
        candidates.extend(_validation_flag_lists_from_payload(detailed))
    candidates.extend(_arr_validation_flags(valuation_data))
    return candidates


def _bucket_saas_validation_flags(candidates: list[object]) -> dict[str, list[JsonMap]]:
    buckets: dict[str, list[JsonMap]] = {"error": [], "warning": []}
    for flag in candidates:
        if not isinstance(flag, dict):
            continue
        severity = str(flag.get("severity") or "").strip().lower()
        if severity in buckets:
            buckets[severity].append(flag)
    return buckets


def _saas_validation_buckets(
    valuation_data: JsonMap,
) -> dict[str, list[JsonMap]]:
    """Return SaaS validation flags grouped into ``error`` and ``warning``.

    Source paths checked (in order of likelihood):
      * ``saas_input_validation`` - top-level list when the orchestrator
        promotes it onto the response.
      * ``detailed_results.saas_input_validation`` - when nested.
      * ``arr_multiple.details.validation_flags`` - per-method placement.

    Each flag is the dict shape produced by
    :class:`SaasValidationFlag.to_triage_dict` - ``{field, issue, severity,
    value, benchmark}`` - but legacy ``{field, code, severity, message}``
    is also accepted.
    """
    return _bucket_saas_validation_flags(_saas_validation_candidates(valuation_data))


def _dcf_forecast_warnings_by_type(
    valuation_data: JsonMap,
) -> dict[str, JsonMap]:
    """Index DCF forecast warnings on ``dcf_valuation.data_quality_warnings``.

    Picks the highest-severity entry per ``type`` so we never emit
    two typed warnings for the same forecast issue (the DCF calculator can
    push multiple ``limited_historical_data`` entries during fallback).
    """
    sev_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    out: dict[str, JsonMap] = {}
    candidates: list[object] = []
    dcf = valuation_data.get("dcf_valuation")
    if isinstance(dcf, dict):
        v = dcf.get("data_quality_warnings")
        if isinstance(v, list):
            candidates.extend(v)
    detailed = valuation_data.get("detailed_results")
    if isinstance(detailed, dict):
        dcf2 = detailed.get("dcf_valuation")
        if isinstance(dcf2, dict):
            v = dcf2.get("data_quality_warnings")
            if isinstance(v, list):
                candidates.extend(v)
    for w in candidates:
        if not isinstance(w, dict):
            continue
        t = w.get("type")
        if not isinstance(t, str) or not t.strip():
            continue
        existing = out.get(t)
        if existing is None:
            out[t] = w
            continue
        cur_rank = sev_rank.get(str(w.get("severity") or "").lower(), -1)
        prev_rank = sev_rank.get(str(existing.get("severity") or "").lower(), -1)
        if cur_rank > prev_rank:
            out[t] = w
    return out
