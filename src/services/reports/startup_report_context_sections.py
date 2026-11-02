"""Focused builders for startup report context sections."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Optional

from src.services.reports.startup_report_context_helpers import (
    JsonMap,
    JsonRows,
    coerce_dict,
    pin_float_band,
    safe_float,
    safe_get,
)

TranslationCatalog = Mapping[str, Mapping[str, str]]
TranslateFn = Callable[..., str]

METHOD_ORDER = ("berkus", "scorecard", "vc", "saas_forward")
_DEFENSIBILITY_FACTOR_LABEL_KEYS = {
    "headline_coherence": "defensibility_factor_headline_coherence",
    "sector_consistency": "defensibility_factor_sector_consistency",
    "pedigree_evidence": "defensibility_factor_pedigree_evidence",
    "forward_inputs": "defensibility_factor_forward_inputs",
    "traction_signal": "defensibility_factor_traction_signal",
}


def strip_optional_text(value: object) -> str | None:
    """Return stripped text, or None when value is blank/non-text."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def extract_studio_v2_context(startup_inputs: object) -> JsonMap:
    """Extract founder-authored Studio v2 copy and evidence notes."""
    studio_v2 = coerce_dict(safe_get(startup_inputs, "studio_v2"))

    evidence_notes: dict[str, str] = {}
    evidence_notes_raw = studio_v2.get("evidence_notes")
    if isinstance(evidence_notes_raw, dict):
        for key, value in evidence_notes_raw.items():
            note = strip_optional_text(value)
            if note:
                evidence_notes[str(key)] = note

    return {
        "founder_pitch": strip_optional_text(studio_v2.get("description")),
        "exit_multiple_rationale": strip_optional_text(
            safe_get(startup_inputs, "exit_revenue_multiple_rationale")
        ),
        "evidence_notes": evidence_notes,
    }


def decorate_startup_method_evidence(
    *,
    berkus: JsonMap,
    scorecard: JsonMap,
    evidence_notes: Mapping[str, str],
    loc: str,
    translations: TranslationCatalog,
) -> tuple[JsonMap, JsonMap]:
    """Attach localized labels and founder evidence to Berkus/Scorecard rows."""

    def decorate_rows(rows: object, prefix: str) -> list[object]:
        if not isinstance(rows, list):
            return rows if isinstance(rows, list) else []

        decorated: list[object] = []
        for item in rows:
            row = dict(item) if isinstance(item, dict) else item
            if isinstance(row, dict):
                key = row.get("key")
                if isinstance(key, str):
                    localised_label = translations.get(f"{prefix}_{key}", {}).get(loc)
                    updates: JsonMap = {}
                    if localised_label:
                        updates["label"] = localised_label
                    if evidence_notes.get(key):
                        updates["evidence"] = evidence_notes[key]
                    if updates:
                        row = {**row, **updates}
            decorated.append(row)
        return decorated

    if isinstance(berkus.get("contributions"), list):
        berkus = {
            **berkus,
            "contributions": decorate_rows(berkus["contributions"], "berkus_milestone"),
        }

    if isinstance(scorecard.get("factors"), list):
        scorecard = {
            **scorecard,
            "factors": decorate_rows(scorecard["factors"], "scorecard_factor"),
        }

    return berkus, scorecard


def extract_safe_notes(cap_table: JsonMap) -> tuple[JsonRows, float]:
    """Normalize SAFE note inputs for the startup cap-table section."""
    safe_notes_raw = cap_table.get("safe_notes") or []
    safe_notes: JsonRows = []
    safe_total = 0.0

    if not isinstance(safe_notes_raw, list):
        return safe_notes, safe_total

    for note in safe_notes_raw:
        note_dict = coerce_dict(note)
        amount = float(note_dict.get("amount") or 0)
        safe_total += amount
        safe_notes.append(
            {
                "amount": amount,
                "valuation_cap": (
                    float(note_dict.get("valuation_cap") or 0)
                    if note_dict.get("valuation_cap")
                    else None
                ),
                "discount_pct": (
                    float(note_dict.get("discount_pct") or 0)
                    if note_dict.get("discount_pct")
                    else None
                ),
                "holder_label": note_dict.get("holder_label"),
            }
        )

    return safe_notes, safe_total


def fetch_sector_comparables_dicts(sector: object, limit: int = 5) -> JsonRows:
    """Fetch sector comparable rows and degrade to an empty list on failures."""
    try:
        from src.domain.startup_valuation.sector_comparables import fetch_sector_comparables

        return [row.to_dict() for row in fetch_sector_comparables(sector, limit=limit)]
    except Exception:  # noqa: BLE001 - sidecar fetch must not break report rendering
        return []


def build_vc_multiple_source(sector_comparables: JsonRows, sector: object) -> JsonMap | None:
    """Pick the first sourced EV/Revenue peer row for inline VC provenance."""
    for comparable in sector_comparables:
        median = comparable.get("ev_revenue_median")
        if median:
            return {
                "source": comparable.get("multiples_source") or "Athena Q1 2026",
                "sector_label": comparable.get("title") or sector,
                "median": float(median),
                "p25": float(comparable.get("ev_revenue_p25") or median),
                "p75": float(comparable.get("ev_revenue_p75") or median),
            }
    return None


def build_vc_oversubscribed(vc: JsonMap) -> JsonMap | None:
    """Surface a zero pre-money VC backsolve caused by an oversized ask."""
    investment_sought_raw = vc.get("investment_amount_sought")
    vc_post_money = float(vc.get("post_money") or 0)
    vc_pre_money = float(vc.get("pre_money") or 0)
    if (
        vc.get("used_investment_amount")
        and investment_sought_raw
        and vc_post_money > 0
        and vc_pre_money <= 0
    ):
        return {
            "investment_amount": float(investment_sought_raw),
            "implied_post_money": vc_post_money,
            "shortfall": float(investment_sought_raw) - vc_post_money,
        }
    return None


def build_vc_sensitivity(vc: JsonMap) -> JsonMap | None:
    """Build the 3x3 sensitivity grid for VC backsolve inputs."""
    vc_y5 = float(vc.get("year5_revenue") or 0)
    vc_mult = float(vc.get("exit_revenue_multiple") or 0)
    vc_roi = float(vc.get("target_roi_x") or 0)
    vc_round = float(vc.get("investment_amount_sought") or 0)
    if vc_y5 <= 0 or vc_mult <= 0 or vc_roi <= 0:
        return None

    y5_steps = (vc_y5 * 0.8, vc_y5, vc_y5 * 1.2)
    mult_steps = (vc_mult * 0.8, vc_mult, vc_mult * 1.2)

    def pre_money(y5: float, multiple: float) -> float:
        implied_post = (y5 * multiple) / vc_roi
        return max(0.0, implied_post - vc_round)

    return {
        "y5_low": y5_steps[0],
        "y5_mid": y5_steps[1],
        "y5_high": y5_steps[2],
        "mult_low": mult_steps[0],
        "mult_mid": mult_steps[1],
        "mult_high": mult_steps[2],
        "grid": [
            [pre_money(y5, mult_steps[0]) for y5 in y5_steps],
            [pre_money(y5, mult_steps[1]) for y5 in y5_steps],
            [pre_money(y5, mult_steps[2]) for y5 in y5_steps],
        ],
        "round_size": vc_round,
        "target_roi_x": vc_roi,
    }


def build_dilution_scenarios(
    cap_table_simulator: JsonMap | None,
    *,
    canonical_low: float,
    canonical_high: float,
) -> JsonRows:
    """Build negotiation scenarios for cap-table dilution."""
    if not (
        cap_table_simulator
        and cap_table_simulator.get("investment_amount")
        and cap_table_simulator.get("pre_money")
    ):
        return []

    sim_pre = float(cap_table_simulator.get("pre_money") or 0)
    sim_inv = float(cap_table_simulator.get("investment_amount") or 0)
    sim_pool = float(cap_table_simulator.get("option_pool_pct") or 0)
    sim_safe = float(cap_table_simulator.get("safe_dilution_pct") or 0)
    p75 = max(canonical_low * 0.25 + canonical_high * 0.75, sim_pre)

    def scenario(label_key: str, pre_money: float, investment: float, pool_pct: float) -> JsonMap:
        post_money = pre_money + investment
        investor_pct = (investment / post_money * 100.0) if post_money > 0 else 0.0
        founder_dilution = min(investor_pct + sim_safe + pool_pct, 100.0)
        return {
            "label_key": label_key,
            "pre_money": pre_money,
            "investment_amount": investment,
            "option_pool_pct": pool_pct,
            "investor_dilution_pct": investor_pct,
            "founder_dilution_pct": founder_dilution,
            "founders_remaining_pct": max(0.0, 100.0 - founder_dilution),
        }

    return [
        scenario("scenario_current", sim_pre, sim_inv, sim_pool),
        scenario("scenario_lead_at_p75", p75, sim_inv, sim_pool),
        scenario("scenario_smaller_pool", sim_pre, sim_inv, max(sim_pool - 5.0, 0.0)),
        scenario("scenario_smaller_round", sim_pre, sim_inv * 0.75, sim_pool),
    ]


def build_inception_lens_advisory(
    *,
    startup_inputs: object,
    inception_lens: JsonMap,
) -> dict[str, str] | None:
    """Recommend an inception lens when the founder has not opted in yet."""
    stage = safe_get(startup_inputs, "stage")
    sector = safe_get(startup_inputs, "sector") or "saas"
    pedigree = coerce_dict(safe_get(startup_inputs, "founder_pedigree"))
    maturity = coerce_dict(safe_get(startup_inputs, "maturity")) or {}
    has_high_pedigree = _has_high_pedigree(pedigree)

    if not _can_recommend_inception_lens(startup_inputs, inception_lens, stage):
        return None
    if _is_inception_bet_candidate(sector=sector, has_high_pedigree=has_high_pedigree):
        return {"kind": "bet"}
    if _is_momentum_candidate(maturity=maturity, has_high_pedigree=has_high_pedigree):
        return {"kind": "momentum"}
    return None


def _can_recommend_inception_lens(
    startup_inputs: object,
    inception_lens: JsonMap,
    stage: object,
) -> bool:
    current_lens_value = (inception_lens or {}).get("lens")
    return (
        current_lens_value in (None, "milestones_driven")
        and stage == "pre_seed"
        and not _has_startup_revenue(startup_inputs)
    )


def _has_startup_revenue(startup_inputs: object) -> bool:
    return bool(
        (safe_float(safe_get(startup_inputs, "mrr")) or 0) > 0
        or (safe_float(safe_get(startup_inputs, "arr")) or 0) > 0
    )


def _has_high_pedigree(pedigree: JsonMap) -> bool:
    return bool(pedigree.get("prior_exit") or pedigree.get("top_unicorn_alumnus"))


def _is_inception_bet_candidate(*, sector: object, has_high_pedigree: bool) -> bool:
    return sector in ("deeptech_ai", "biotech_healthtech") and has_high_pedigree


def _is_momentum_candidate(*, maturity: JsonMap, has_high_pedigree: bool) -> bool:
    return (
        not has_high_pedigree
        and maturity.get("management_strength") == "exceptional"
        and maturity.get("strategic_relationships") not in (None, "none", "")
    )


def localize_defensibility_score(
    defensibility_score: JsonMap,
    *,
    loc: str,
    translations: TranslationCatalog,
) -> JsonMap:
    """Localize defensibility factor labels/rationales while preserving scores."""
    if not defensibility_score:
        return defensibility_score

    factors_localized: JsonRows = []
    factors_raw = defensibility_score.get("factors") or []
    if isinstance(factors_raw, list):
        for factor in factors_raw:
            if not isinstance(factor, dict):
                continue
            factors_localized.append(
                _localized_defensibility_factor(factor, loc=loc, translations=translations)
            )

    return {**defensibility_score, "factors": factors_localized}


def _localized_defensibility_factor(
    factor: JsonMap,
    *,
    loc: str,
    translations: TranslationCatalog,
) -> JsonMap:
    factor_key = str(factor.get("key") or "")
    label = (
        _translated_defensibility_label(factor_key, loc=loc, translations=translations)
        or factor.get("label")
        or factor_key
    )
    return {
        "key": factor_key,
        "label": label,
        "score": safe_float(factor.get("score")) or 0.0,
        "rationale": _localized_defensibility_rationale(factor, loc=loc),
    }


def _translated_defensibility_label(
    factor_key: str,
    *,
    loc: str,
    translations: TranslationCatalog,
) -> str | None:
    label_key = _DEFENSIBILITY_FACTOR_LABEL_KEYS.get(factor_key)
    if not label_key:
        return None
    return translations.get(label_key, {}).get(loc)


def _localized_defensibility_rationale(factor: JsonMap, *, loc: str) -> object:
    rationale_nl = factor.get("rationale") or ""
    rationale_en = factor.get("rationale_en") or ""
    return rationale_en if loc == "en" and rationale_en else rationale_nl


def build_startup_risks_register(
    *,
    loc: str,
    translate: TranslateFn,
    vc_oversubscribed: JsonMap | None,
    outlier_policy: JsonMap,
    sector_consistency: JsonMap,
    defensibility_score: JsonMap,
    inception_lens: JsonMap,
    sector: object,
    format_eur_digits: Callable[[object, str], str],
) -> JsonRows:
    """Build the consolidated investor-objection risk register."""
    risks_register: JsonRows = []

    if vc_oversubscribed:
        risks_register.append(
            _oversubscribed_risk_row(
                loc=loc,
                translate=translate,
                vc_oversubscribed=vc_oversubscribed,
                format_eur_digits=format_eur_digits,
            )
        )

    outlier_risk = _outlier_capped_risk_row(
        loc=loc,
        translate=translate,
        outlier_policy=outlier_policy,
    )
    if outlier_risk:
        risks_register.append(outlier_risk)

    if sector_consistency.get("saas_forward_sector_skipped"):
        risks_register.append(
            _sector_mismatch_risk_row(
                loc=loc,
                translate=translate,
                sector_consistency=sector_consistency,
                sector=sector,
            )
        )

    defs_score = defensibility_score.get("score_0_10") if defensibility_score else None
    if isinstance(defs_score, (int, float)) and defs_score < 5:
        risks_register.append(
            _low_defensibility_risk_row(loc=loc, translate=translate, defs_score=defs_score)
        )

    lens_active = inception_lens.get("lens") if inception_lens else None
    if lens_active and lens_active != "milestones_driven":
        risks_register.append(
            _inception_lens_risk_row(
                loc=loc,
                translate=translate,
                inception_lens=inception_lens,
                lens_active=lens_active,
            )
        )

    return risks_register


def _oversubscribed_risk_row(
    *,
    loc: str,
    translate: TranslateFn,
    vc_oversubscribed: JsonMap,
    format_eur_digits: Callable[[object, str], str],
) -> JsonMap:
    return {
        "severity": "high",
        "id": "round_oversubscribed",
        "title": translate(loc, "risk_oversub_title"),
        "body": translate(
            loc,
            "risk_oversub_body",
            ask=format_eur_digits(vc_oversubscribed["investment_amount"], loc),
            post=format_eur_digits(vc_oversubscribed["implied_post_money"], loc),
            shortfall=format_eur_digits(vc_oversubscribed["shortfall"], loc),
        ),
        "action": translate(loc, "risk_oversub_action"),
    }


def _outlier_capped_risk_row(
    *,
    loc: str,
    translate: TranslateFn,
    outlier_policy: JsonMap,
) -> JsonMap | None:
    if not outlier_policy.get("any_capped"):
        return None
    capped_count = sum(
        1 for row in (outlier_policy.get("cap_records") or []) if row.get("was_capped")
    )
    if capped_count <= 0:
        return None

    title_key = "risk_outlier_title_one" if capped_count == 1 else "risk_outlier_title_many"
    return {
        "severity": "medium",
        "id": "outlier_capped",
        "title": translate(loc, title_key, count=capped_count),
        "body": translate(
            loc,
            "risk_outlier_body",
            median=f"{float(outlier_policy.get('median') or 0):,.0f}",
            fence=f"{float(outlier_policy.get('upper_fence') or 0):,.0f}",
        ),
        "action": translate(loc, "risk_outlier_action"),
    }


def _sector_mismatch_risk_row(
    *,
    loc: str,
    translate: TranslateFn,
    sector_consistency: JsonMap,
    sector: object,
) -> JsonMap:
    return {
        "severity": "medium",
        "id": "sector_mismatch",
        "title": translate(loc, "risk_sector_title"),
        "body": translate(
            loc,
            "risk_sector_body",
            sector=str(sector_consistency.get("sector") or sector),
        ),
        "action": translate(loc, "risk_sector_action"),
    }


def _low_defensibility_risk_row(
    *,
    loc: str,
    translate: TranslateFn,
    defs_score: object,
) -> JsonMap:
    return {
        "severity": "high",
        "id": "low_defensibility",
        "title": translate(loc, "risk_low_defs_title", score=f"{float(defs_score):.1f}"),
        "body": translate(loc, "risk_low_defs_body"),
        "action": translate(loc, "risk_low_defs_action"),
    }


def _inception_lens_risk_row(
    *,
    loc: str,
    translate: TranslateFn,
    inception_lens: JsonMap,
    lens_active: object,
) -> JsonMap:
    lens_label = (
        inception_lens.get("label_en") if loc == "en" else inception_lens.get("label_nl")
    ) or lens_active
    return {
        "severity": "info",
        "id": "inception_lens",
        "title": translate(loc, "risk_inception_title", lens=str(lens_label)),
        "body": translate(loc, "risk_inception_body"),
        "action": translate(loc, "risk_inception_action"),
    }


def normalize_advisor_cta_url(advisor_cta_url: str | None, loc: str) -> str:
    """Resolve the locale-aware advisor CTA URL and append PDF attribution."""
    cleaned = (advisor_cta_url or "").strip() or None
    if cleaned is None:
        cleaned = (
            "https://www.upswitch.app/"
            f"{loc}/client/dashboard?source=startup_report&action=invite_accountant"
        )

    if "utm_content=" not in cleaned:
        separator = "&" if "?" in cleaned else "?"
        cleaned = (
            f"{cleaned}{separator}utm_source=startup_pdf"
            f"&utm_medium=report&utm_content=one_pager"
        )

    return cleaned


def ordered_weights(raw: Mapping[str, object] | None) -> dict[str, float]:
    """Return method weights in stable consortium order."""
    if not raw:
        return {}
    floats = {key: float(value) for key, value in raw.items()}
    ordered: dict[str, float] = {}
    for key in METHOD_ORDER:
        if key in floats:
            ordered[key] = floats[key]
    for key, value in floats.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def build_founder_view(founder_view_raw: JsonMap | None) -> JsonMap | None:
    """Normalize founder-view band and weight ordering."""
    if not founder_view_raw:
        return None

    low, mid, high = pin_float_band(
        float(founder_view_raw.get("equity_value_low") or 0),
        float(founder_view_raw.get("equity_value_mid") or 0),
        float(founder_view_raw.get("equity_value_high") or 0),
    )
    return {
        "equity_value_mid": mid,
        "equity_value_low": low,
        "equity_value_high": high,
        "weights": ordered_weights(founder_view_raw.get("weights")),
        "contributors": list(founder_view_raw.get("contributors") or []),
    }


def resolve_stage_display(details: JsonMap, t_table: Mapping[str, str]) -> str:
    """Return locale-resolved startup stage display text."""
    stage_value = str(details.get("stage") or "").strip()
    stage_display = t_table.get(f"stage_{stage_value}") if stage_value else None
    if stage_display:
        return stage_display
    return stage_value.replace("_", "-").title() if stage_value else ""


def build_founder_floor_advisory(
    cap_table_simulator: JsonMap | None, safe_notes: JsonRows
) -> JsonMap | None:
    """Flag priced rounds that leave founders below the empirical floor."""
    if not (
        cap_table_simulator
        and not safe_notes
        and cap_table_simulator.get("investment_amount")
        and cap_table_simulator.get("founder_dilution_pct") is not None
    ):
        return None

    founders_pct = 100.0 - float(cap_table_simulator.get("founder_dilution_pct") or 0)
    if 0 < founders_pct < 30.0:
        return {"founders_pct": round(founders_pct, 1)}
    return None


def startup_input_float(startup_inputs: object, key: str) -> float | None:
    """Read a startup input as a float when present."""
    value = safe_get(startup_inputs, key)
    return float(value or 0) if value else None
