"""Helpers that build the startup-specific report context.

Lives next to the other ``services.reports`` context builders so the
template payload for the venture path is assembled in one obvious place
(KISS / SRP).  The main report data aggregator calls
:func:`build_startup_context` after the SME context is finalised — when
``selected_method == 'startup_valuation'`` the master template uses the
startup pages instead of the SME pages.

Localisation
------------
The startup report templates are trilingual (NL + EN + FR) and must respect
the founder's report locale.  Until April 2026 the templates were
hard-coded Dutch — fine for Belgian KBO founders, broken for Wintercircus
campaigns and any English-speaking founder.

Rather than introduce Babel / gettext for a handful of strings, the
startup copy catalog lives in ``startup_report_translations`` and is
exposed to every startup Jinja page as ``startup_report.t.<key>``.  The
dict is the single source of truth — templates never carry locale-specific
copy inline.

"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal, Mapping, Optional

from src.services.reports.startup_report_context_assembly import (
    StartupReportContextParts,
    assemble_startup_report_context,
    build_startup_translation_table,
)
from src.services.reports.startup_report_context_helpers import JsonMap, JsonRows
from src.services.reports.startup_report_context_helpers import coerce_dict as _coerce_dict
from src.services.reports.startup_report_context_helpers import (
    extract_startup_method as _extract_startup_method,
)
from src.services.reports.startup_report_context_helpers import (
    format_eur_digits as _format_eur_digits,
)
from src.services.reports.startup_report_context_helpers import pin_float_band as _pin_float_band
from src.services.reports.startup_report_context_helpers import safe_float as _safe_float
from src.services.reports.startup_report_context_helpers import safe_get as _safe_get
from src.services.reports.startup_report_context_sections import (
    build_dilution_scenarios,
    build_founder_view,
    build_inception_lens_advisory,
    build_startup_risks_register,
    build_vc_multiple_source,
    build_vc_oversubscribed,
    build_vc_sensitivity,
    decorate_startup_method_evidence,
    extract_safe_notes,
    extract_studio_v2_context,
    fetch_sector_comparables_dicts,
    localize_defensibility_score,
    normalize_advisor_cta_url,
    resolve_stage_display,
)
from src.services.reports.startup_report_defensibility_context import (
    build_startup_defensibility_rows,
)
from src.services.reports.startup_report_translations import STARTUP_REPORT_TRANSLATIONS

StartupReportLocale = Literal["nl", "en", "fr"]


@dataclass(frozen=True)
class StartupMethodContext:
    method: JsonMap
    details: JsonMap
    berkus: JsonMap
    scorecard: JsonMap
    vc: JsonMap
    saas_forward: JsonMap
    weights: JsonMap
    regional: JsonMap
    founder_pedigree: JsonMap
    inception_lens: JsonMap
    pre_pedigree: JsonMap
    canonical: JsonMap
    outlier_policy: JsonMap
    defensibility_score: JsonMap
    sector_consistency: JsonMap


@dataclass(frozen=True)
class StartupStudioContext:
    founder_pitch: object
    exit_multiple_rationale: object
    evidence_notes: JsonMap


@dataclass(frozen=True)
class StartupHeadlineContext:
    pre_money: float
    canonical_low: float
    canonical_high: float
    canonical_basis: object


@dataclass(frozen=True)
class StartupCapTableEconomics:
    cap_table: JsonMap
    pre_money_target_f: Optional[float]
    option_pool_pct: float
    safe_notes: object
    safe_total: float
    estimated_post_money: float
    founder_dilution_pct: float


def _normalize_startup_report_locale(locale: str | None) -> StartupReportLocale:
    """Clamp startup report copy to the locales covered by the catalog."""

    lowered = str(locale or "nl").strip().lower()
    if lowered.startswith("en"):
        return "en"
    if lowered.startswith("fr"):
        return "fr"
    return "nl"


def _t(loc: str, key: str, **fmt: object) -> str:
    """Resolve ``key`` for ``loc``, falling back to NL if the locale is missing.

    Format kwargs are passed through ``str.format`` so callers can
    interpolate cap-table numbers, sector names, etc.  Missing keys
    return the key itself in square brackets — visible enough that the
    gap shows up in QA, defensible enough that the report still renders.
    """
    entry = STARTUP_REPORT_TRANSLATIONS.get(key)
    if not entry:
        return f"[{key}]"
    template = entry.get(loc) or entry.get("nl") or f"[{key}]"
    if not fmt:
        return template
    try:
        return template.format(**fmt)
    except (KeyError, IndexError, ValueError):
        return template


def _pct(value: object) -> float:
    """Clamp percentage-like simulator values for chart geometry."""
    out = _safe_float(value) or 0.0
    if not math.isfinite(out):
        return 0.0
    return min(max(out, 0.0), 100.0)


def _build_share_distribution_segments(
    cap_table_simulator: Optional[JsonMap],
    t_table: Mapping[str, str],
) -> JsonRows:
    """Build normalized cap-table chart segments that always fill 100%.

    The engine normally emits internally consistent percentages. This
    function still treats chart geometry as hostile-input territory:
    negative values become 0, over-100 values are capped, and non-founder
    slices are scaled down if a stale payload adds up beyond 100.
    """
    if not cap_table_simulator:
        return []

    option_pool_pct = _pct(cap_table_simulator.get("option_pool_pct"))
    safe_pct = _pct(cap_table_simulator.get("safe_dilution_pct"))

    investor_value = cap_table_simulator.get("investor_dilution_pct")
    if investor_value is None:
        investor_value = cap_table_simulator.get("dilution_pct")
    investor_pct = _pct(investor_value)

    if investor_pct <= 0:
        founder_dilution_pct = _pct(cap_table_simulator.get("founder_dilution_pct"))
        investor_pct = max(0.0, founder_dilution_pct - option_pool_pct - safe_pct)

    non_founder_total = option_pool_pct + safe_pct + investor_pct
    if non_founder_total > 100.0:
        scale = 100.0 / non_founder_total
        option_pool_pct *= scale
        safe_pct *= scale
        investor_pct *= scale
        founders_pct = 0.0
    else:
        founders_pct = 100.0 - non_founder_total

    raw_segments = [
        ("founders", t_table.get("founders", "Founders"), founders_pct, "#10b981"),
        ("option_pool", t_table.get("option_pool", "Option pool"), option_pool_pct, "#f59e0b"),
        ("safe_converters", t_table.get("safe_converters", "SAFE converters"), safe_pct, "#64748b"),
        ("new_investor", t_table.get("new_investor", "New investor"), investor_pct, "#2a8a82"),
    ]
    return [
        {
            "key": key,
            "label": label,
            "pct": round(pct, 4),
            "color": color,
            "show_inside_label": pct >= 8.0,
        }
        for key, label, pct, color in raw_segments
        if pct > 0
    ]


def _is_startup_valuation_method(selected_method: Optional[str]) -> bool:
    return str(selected_method or "").strip().lower() == "startup_valuation"


def _resolve_startup_method_context(valuation_results: object) -> Optional[StartupMethodContext]:
    method = _extract_startup_method(valuation_results)
    if not method or not method.get("available"):
        return None

    details = _coerce_dict(method.get("details"))
    return StartupMethodContext(
        method=method,
        details=details,
        berkus=_coerce_dict(details.get("berkus")),
        scorecard=_coerce_dict(details.get("scorecard")),
        vc=_coerce_dict(details.get("vc")),
        saas_forward=_coerce_dict(details.get("saas_forward")),
        weights=_coerce_dict(details.get("weights")),
        regional=_coerce_dict(details.get("regional_reference")),
        founder_pedigree=_coerce_dict(details.get("founder_pedigree")),
        inception_lens=_coerce_dict(details.get("inception_lens")),
        pre_pedigree=_coerce_dict(details.get("pre_pedigree")),
        canonical=_coerce_dict(details.get("canonical")),
        outlier_policy=_coerce_dict(details.get("outlier_policy")),
        defensibility_score=_coerce_dict(details.get("defensibility")),
        sector_consistency=_coerce_dict(details.get("sector_consistency")),
    )


def _resolve_studio_context(startup_inputs: object) -> StartupStudioContext:
    studio_v2_context = extract_studio_v2_context(startup_inputs)
    evidence_notes_raw = studio_v2_context["evidence_notes"]
    return StartupStudioContext(
        founder_pitch=studio_v2_context["founder_pitch"],
        exit_multiple_rationale=studio_v2_context["exit_multiple_rationale"],
        evidence_notes=evidence_notes_raw if isinstance(evidence_notes_raw, dict) else {},
    )


def _decorate_method_evidence(
    method_context: StartupMethodContext,
    *,
    studio_context: StartupStudioContext,
    loc: StartupReportLocale,
) -> StartupMethodContext:
    berkus, scorecard = decorate_startup_method_evidence(
        berkus=method_context.berkus,
        scorecard=method_context.scorecard,
        evidence_notes=studio_context.evidence_notes,
        loc=loc,
        translations=STARTUP_REPORT_TRANSLATIONS,
    )
    return replace(method_context, berkus=berkus, scorecard=scorecard)


def _resolve_canonical_basis(canonical: JsonMap, loc: StartupReportLocale) -> object:
    canonical_basis_key = canonical.get("basis_key") or ""
    if canonical_basis_key in STARTUP_REPORT_TRANSLATIONS:
        return _t(loc, str(canonical_basis_key))
    return canonical.get("basis") or ""


def _resolve_startup_headline(
    *,
    method_context: StartupMethodContext,
    loc: StartupReportLocale,
) -> StartupHeadlineContext:
    details = method_context.details
    canonical = method_context.canonical
    pre_money = float(
        method_context.method.get("value")
        or canonical.get("pre_money_mid")
        or details.get("equity_value_mid")
        or 0
    )
    canonical_low = _safe_float(canonical.get("pre_money_low")) or float(
        details.get("equity_value_low") or 0
    )
    canonical_high = _safe_float(canonical.get("pre_money_high")) or float(
        details.get("equity_value_high") or 0
    )
    canonical_low, pre_money, canonical_high = _pin_float_band(
        canonical_low,
        pre_money,
        canonical_high,
    )
    return StartupHeadlineContext(
        pre_money=pre_money,
        canonical_low=canonical_low,
        canonical_high=canonical_high,
        canonical_basis=_resolve_canonical_basis(canonical, loc),
    )


def _resolve_cap_table_economics(
    *,
    cap_table: JsonMap,
    pre_money: float,
) -> StartupCapTableEconomics:
    safe_notes, safe_total = extract_safe_notes(cap_table)
    pre_money_target_f = _safe_float(cap_table.get("pre_money_target"))
    option_pool_pct = float(_safe_float(cap_table.get("option_pool_pct")) or 0)
    new_round_post_money = pre_money_target_f or pre_money
    estimated_post_money = new_round_post_money + safe_total
    founder_dilution_pct = (
        option_pool_pct + (safe_total / estimated_post_money * 100.0)
        if estimated_post_money
        else 0.0
    )
    return StartupCapTableEconomics(
        cap_table=cap_table,
        pre_money_target_f=pre_money_target_f,
        option_pool_pct=option_pool_pct,
        safe_notes=safe_notes,
        safe_total=safe_total,
        estimated_post_money=estimated_post_money,
        founder_dilution_pct=founder_dilution_pct,
    )


def _build_startup_defensibility(
    *,
    loc: StartupReportLocale,
    method_context: StartupMethodContext,
    sector: object,
    canonical_basis: object,
) -> object:
    return build_startup_defensibility_rows(
        loc=loc,
        translate=_t,
        vc=method_context.vc,
        saas_forward=method_context.saas_forward,
        berkus=method_context.berkus,
        scorecard=method_context.scorecard,
        founder_pedigree=method_context.founder_pedigree,
        pre_pedigree=method_context.pre_pedigree,
        outlier_policy=method_context.outlier_policy,
        sector_consistency=method_context.sector_consistency,
        canonical_basis=canonical_basis,
        inception_lens=method_context.inception_lens,
        sector=sector,
        stage=method_context.details.get("stage"),
    )


def build_startup_context(
    *,
    selected_method: Optional[str],
    valuation_results: object,
    startup_inputs: object = None,
    advisor_cta_url: Optional[str] = None,
    locale: str = "nl",
) -> Optional[JsonMap]:
    """Build the ``startup_report`` context block consumed by the templates.

    Returns ``None`` when the active method is not ``startup_valuation`` or
    when the engine did not produce a usable startup leg — the master
    template then falls back to the SME flow unchanged.

    ``advisor_cta_url`` is optional; when provided it overrides the
    template fallback for the "invite my accountant" partial.  The caller
    is responsible for picking a locale-aware Mercury URL — ValuationIQ
    has no notion of host or locale.

    ``locale`` controls the language of every server-built label and
    every templated string the startup pages render. Accepts ``"nl"``,
    ``"en"`` or ``"fr"``; anything else falls through to ``"nl"`` (the
    historical default). The caller should pass the already-normalised
    report locale produced by ``normalize_report_locale`` so this function
    rarely has to re-decode user-supplied locale tags.
    """
    if not _is_startup_valuation_method(selected_method):
        return None

    loc = _normalize_startup_report_locale(locale)
    method_context = _resolve_startup_method_context(valuation_results)
    if method_context is None:
        return None

    cap_table = _coerce_dict(_safe_get(startup_inputs, "cap_table"))
    studio_context = _resolve_studio_context(startup_inputs)
    method_context = _decorate_method_evidence(
        method_context,
        studio_context=studio_context,
        loc=loc,
    )
    headline = _resolve_startup_headline(
        method_context=method_context,
        loc=loc,
    )
    cap_table_economics = _resolve_cap_table_economics(
        cap_table=cap_table,
        pre_money=headline.pre_money,
    )

    sector = _safe_get(startup_inputs, "sector") or "saas"
    sector_comparables = fetch_sector_comparables_dicts(sector, limit=5)
    vc_multiple_source = build_vc_multiple_source(sector_comparables, sector)
    defensibility = _build_startup_defensibility(
        loc=loc,
        method_context=method_context,
        sector=sector,
        canonical_basis=headline.canonical_basis,
    )

    vc_oversubscribed = build_vc_oversubscribed(method_context.vc)
    vc_sensitivity = build_vc_sensitivity(method_context.vc)
    cap_table_simulator: Optional[JsonMap] = method_context.details.get("cap_table_simulator")
    dilution_scenarios = build_dilution_scenarios(
        cap_table_simulator,
        canonical_low=headline.canonical_low,
        canonical_high=headline.canonical_high,
    )
    inception_lens_advisory = build_inception_lens_advisory(
        startup_inputs=startup_inputs,
        inception_lens=method_context.inception_lens,
    )
    localized_defensibility_score = localize_defensibility_score(
        method_context.defensibility_score,
        loc=loc,
        translations=STARTUP_REPORT_TRANSLATIONS,
    )
    risks_register = build_startup_risks_register(
        loc=loc,
        translate=_t,
        vc_oversubscribed=vc_oversubscribed,
        outlier_policy=method_context.outlier_policy,
        sector_consistency=method_context.sector_consistency,
        defensibility_score=localized_defensibility_score,
        inception_lens=method_context.inception_lens,
        sector=sector,
        format_eur_digits=_format_eur_digits,
    )

    cleaned_advisor_cta_url = normalize_advisor_cta_url(advisor_cta_url, loc)
    founder_view = build_founder_view(method_context.details.get("founder_view") or None)
    t_table = build_startup_translation_table(loc)
    share_distribution_segments = _build_share_distribution_segments(cap_table_simulator, t_table)
    stage_display = resolve_stage_display(method_context.details, t_table)

    return assemble_startup_report_context(
        StartupReportContextParts(
            loc=loc,
            details=method_context.details,
            startup_inputs=startup_inputs,
            stage_display=stage_display,
            sector=sector,
            cleaned_advisor_cta_url=cleaned_advisor_cta_url,
            founder_pitch=studio_context.founder_pitch,
            exit_multiple_rationale=studio_context.exit_multiple_rationale,
            headline_mid=headline.pre_money,
            canonical_low=headline.canonical_low,
            canonical_high=headline.canonical_high,
            canonical_basis=headline.canonical_basis,
            weights=method_context.weights,
            founder_view=founder_view,
            outlier_policy=method_context.outlier_policy,
            defensibility_score=localized_defensibility_score,
            sector_consistency=method_context.sector_consistency,
            berkus=method_context.berkus,
            scorecard=method_context.scorecard,
            vc=method_context.vc,
            saas_forward=method_context.saas_forward,
            defensibility=defensibility,
            regional=method_context.regional,
            sector_comparables=sector_comparables,
            cap_table=cap_table_economics.cap_table,
            pre_money_target_f=cap_table_economics.pre_money_target_f,
            option_pool_pct=cap_table_economics.option_pool_pct,
            safe_notes=cap_table_economics.safe_notes,
            safe_total=cap_table_economics.safe_total,
            estimated_post_money=cap_table_economics.estimated_post_money,
            founder_dilution_pct=cap_table_economics.founder_dilution_pct,
            cap_table_simulator=cap_table_simulator,
            share_distribution_segments=share_distribution_segments,
            dilution_scenarios=dilution_scenarios,
            inception_lens_advisory=inception_lens_advisory,
            vc_oversubscribed=vc_oversubscribed,
            vc_sensitivity=vc_sensitivity,
            vc_multiple_source=vc_multiple_source,
            risks_register=risks_register,
        )
    )
