"""Build founder-facing startup report defensibility rows."""

from __future__ import annotations

from typing import Protocol

from src.services.reports.startup_report_context_helpers import (
    JsonMap,
    JsonRows,
    format_eur,
    format_eur_digits,
    safe_float,
)
from src.services.reports.startup_report_translations import STARTUP_REPORT_TRANSLATIONS


class StartupTranslator(Protocol):
    """Translation callable used by startup report context builders."""

    def __call__(self, loc: str, key: str, **fmt: object) -> str:
        """Resolve a translated startup report string."""


def _dict_rows(rows: object) -> list[JsonMap]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _append_vc_rows(
    rows: JsonRows,
    *,
    loc: str,
    translate: StartupTranslator,
    vc: JsonMap,
) -> None:
    if vc.get("year5_revenue"):
        rows.append(
            {
                "label": translate(loc, "label_year5_revenue"),
                "value": format_eur(vc["year5_revenue"], loc),
            }
        )
    if vc.get("exit_revenue_multiple"):
        rows.append(
            {
                "label": translate(loc, "label_exit_revenue_multiple"),
                "value": f"{float(vc['exit_revenue_multiple']):.1f}x",
            }
        )
    if vc.get("target_roi_x"):
        rows.append(
            {
                "label": translate(loc, "label_vc_roi_target"),
                "value": f"{float(vc['target_roi_x']):.0f}x",
            }
        )
    if vc.get("investment_amount_sought"):
        rows.append(
            {
                "label": translate(loc, "label_round_to_raise"),
                "value": format_eur(vc["investment_amount_sought"], loc),
            }
        )


def _append_saas_forward_rows(
    rows: JsonRows,
    *,
    loc: str,
    translate: StartupTranslator,
    saas_forward: JsonMap,
) -> None:
    if not saas_forward.get("available"):
        return

    rows.append(
        {
            "label": translate(loc, "label_forward_arr"),
            "value": format_eur(saas_forward["forward_arr"], loc),
        }
    )
    sub = translate(
        loc,
        "label_basis_risk_discount",
        base=float(saas_forward["base_multiple"]),
        disc=(1 - float(saas_forward["risk_discount"])) * 100,
    )
    rows.append(
        {
            "label": translate(loc, "label_applied_saas_multiple"),
            "value": f"{float(saas_forward['applied_multiple']):.2f}x ({sub})",
        }
    )


def _append_berkus_rows(
    rows: JsonRows,
    *,
    loc: str,
    translate: StartupTranslator,
    berkus: JsonMap,
) -> None:
    if not berkus.get("contributions"):
        return
    active = [
        str(contribution.get("label"))
        for contribution in _dict_rows(berkus["contributions"])
        if contribution.get("label") and contribution.get("score_pct", 0) >= 60
    ]
    if active:
        rows.append(
            {
                "label": translate(loc, "label_berkus_milestones_hit"),
                "value": ", ".join(active),
            }
        )


def _pedigree_labels(founder_pedigree: JsonMap) -> tuple[list[str], list[str]]:
    applied_evidenced: list[str] = []
    applied_unevidenced: list[str] = []
    for row in _dict_rows(founder_pedigree.get("breakdown")):
        if not row.get("applied"):
            continue
        label = row.get("label") or row.get("key")
        if not label:
            continue
        label_text = str(label)
        if row.get("evidence_required") and not row.get("evidence_provided"):
            applied_unevidenced.append(label_text)
        else:
            applied_evidenced.append(label_text)
    return applied_evidenced, applied_unevidenced


def _append_founder_pedigree_rows(
    rows: JsonRows,
    *,
    loc: str,
    translate: StartupTranslator,
    founder_pedigree: JsonMap,
    pre_pedigree: JsonMap,
) -> None:
    pedigree_multiplier = safe_float(founder_pedigree.get("multiplier"))
    if not pedigree_multiplier or pedigree_multiplier == 1.0:
        return

    applied_evidenced, applied_unevidenced = _pedigree_labels(founder_pedigree)
    pedigree_value = translate(loc, "label_pedigree_value", mult=pedigree_multiplier)
    if applied_evidenced:
        pedigree_value = f"{pedigree_value} ({', '.join(applied_evidenced)})"
    rows.append(
        {
            "label": translate(loc, "label_pedigree_multiplier"),
            "value": pedigree_value,
        }
    )
    if applied_unevidenced:
        rows.append(
            {
                "label": translate(loc, "label_pedigree_unevidenced"),
                "value": translate(
                    loc,
                    "label_pedigree_unevidenced_value",
                    n=len(applied_unevidenced),
                    names=", ".join(applied_unevidenced),
                ),
            }
        )
    if pre_pedigree.get("equity_value_mid"):
        rows.append(
            {
                "label": translate(loc, "label_legblend_baseline"),
                "value": format_eur(pre_pedigree["equity_value_mid"], loc),
            }
        )


def _append_outlier_cap_rows(
    rows: JsonRows,
    *,
    loc: str,
    translate: StartupTranslator,
    outlier_policy: JsonMap,
) -> None:
    if not outlier_policy.get("any_capped"):
        return
    capped_rows = [
        row for row in _dict_rows(outlier_policy.get("cap_records")) if row.get("was_capped")
    ]
    for row in capped_rows:
        rows.append(
            {
                "label": f"{translate(loc, 'label_outlier_cap_prefix')} — {row.get('label')}",
                "value": translate(
                    loc,
                    "label_outlier_cap_value",
                    orig=format_eur_digits(row.get("original_pre_money") or 0, loc),
                    capped=format_eur_digits(row.get("capped_pre_money") or 0, loc),
                    k=float(outlier_policy.get("tukey_k") or 1.5),
                ),
            }
        )


def _append_sector_consistency_row(
    rows: JsonRows,
    *,
    loc: str,
    translate: StartupTranslator,
    sector_consistency: JsonMap,
) -> None:
    if not sector_consistency.get("saas_forward_sector_skipped"):
        return
    rows.append(
        {
            "label": translate(loc, "label_sector_consistency"),
            "value": translate(
                loc,
                "label_sector_consistency_skip",
                sector=sector_consistency.get("sector"),
            ),
        }
    )


def _append_canonical_basis_row(
    rows: JsonRows,
    *,
    loc: str,
    translate: StartupTranslator,
    canonical_basis: object,
) -> None:
    if canonical_basis:
        rows.append({"label": translate(loc, "label_headline_basis"), "value": canonical_basis})


def _append_inception_lens_rows(
    rows: JsonRows,
    *,
    loc: str,
    translate: StartupTranslator,
    inception_lens: JsonMap,
) -> None:
    lens_key = inception_lens.get("lens")
    if not lens_key or lens_key == "milestones_driven":
        return

    lens_label = inception_lens.get(f"label_{loc}") or inception_lens.get("label_en") or lens_key
    lens_mult = safe_float(inception_lens.get("multiplier"))
    lens_widen = safe_float(inception_lens.get("band_widen_pct"))
    lens_value_parts: list[str] = []
    if lens_mult:
        lens_value_parts.append(translate(loc, "label_lens_lift", mult=lens_mult))
    if lens_widen:
        lens_value_parts.append(translate(loc, "label_lens_widen", pct=lens_widen * 100))
    rows.append(
        {
            "label": translate(loc, "label_inception_lens", label=lens_label),
            "value": " · ".join(lens_value_parts) or "applied",
        }
    )
    rationale = inception_lens.get(f"rationale_{loc}") or inception_lens.get("rationale_en")
    if rationale:
        rows.append({"label": translate(loc, "label_lens_rationale"), "value": rationale})


def _localized_catalog_label(
    *,
    prefix: str,
    raw: object,
    loc: str,
    fallback_separator: str,
) -> str:
    raw_text = str(raw or "").strip()
    catalog_key = f"{prefix}_{raw_text.lower()}"
    return (
        STARTUP_REPORT_TRANSLATIONS.get(catalog_key, {}).get(loc)
        or STARTUP_REPORT_TRANSLATIONS.get(catalog_key, {}).get("nl")
        or raw_text.replace("_", fallback_separator).title()
    )


def _append_sector_stage_rows(
    rows: JsonRows,
    *,
    loc: str,
    translate: StartupTranslator,
    sector: object,
    stage: object,
) -> None:
    rows.append(
        {
            "label": translate(loc, "label_sector"),
            "value": _localized_catalog_label(
                prefix="sector",
                raw=sector,
                loc=loc,
                fallback_separator=" ",
            ),
        }
    )
    rows.append(
        {
            "label": translate(loc, "label_stage"),
            "value": _localized_catalog_label(
                prefix="stage",
                raw=stage,
                loc=loc,
                fallback_separator="-",
            ),
        }
    )


def build_startup_defensibility_rows(
    *,
    loc: str,
    translate: StartupTranslator,
    vc: JsonMap,
    saas_forward: JsonMap,
    berkus: JsonMap,
    scorecard: JsonMap,
    founder_pedigree: JsonMap,
    pre_pedigree: JsonMap,
    outlier_policy: JsonMap,
    sector_consistency: JsonMap,
    canonical_basis: object,
    inception_lens: JsonMap,
    sector: object,
    stage: object,
) -> JsonRows:
    """Return the flat founder/investor explanation rows for a startup report."""

    defensibility: JsonRows = []
    _append_vc_rows(defensibility, loc=loc, translate=translate, vc=vc)
    _append_saas_forward_rows(
        defensibility,
        loc=loc,
        translate=translate,
        saas_forward=saas_forward,
    )
    _append_berkus_rows(defensibility, loc=loc, translate=translate, berkus=berkus)
    if scorecard.get("blended_multiplier"):
        defensibility.append(
            {
                "label": translate(loc, "label_scorecard_vs_region"),
                "value": translate(
                    loc,
                    "label_scorecard_value",
                    mult=float(scorecard["blended_multiplier"]),
                ),
            }
        )
    _append_founder_pedigree_rows(
        defensibility,
        loc=loc,
        translate=translate,
        founder_pedigree=founder_pedigree,
        pre_pedigree=pre_pedigree,
    )
    _append_outlier_cap_rows(
        defensibility,
        loc=loc,
        translate=translate,
        outlier_policy=outlier_policy,
    )
    _append_sector_consistency_row(
        defensibility,
        loc=loc,
        translate=translate,
        sector_consistency=sector_consistency,
    )
    _append_canonical_basis_row(
        defensibility,
        loc=loc,
        translate=translate,
        canonical_basis=canonical_basis,
    )
    _append_inception_lens_rows(
        defensibility,
        loc=loc,
        translate=translate,
        inception_lens=inception_lens,
    )
    _append_sector_stage_rows(
        defensibility,
        loc=loc,
        translate=translate,
        sector=sector,
        stage=stage,
    )
    return defensibility
