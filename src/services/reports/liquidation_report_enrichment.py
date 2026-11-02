"""Pure enrichment helpers for liquidation report template blocks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeAlias

from src.services.reports.liquidation_report_translations import (
    CASCADE_TIER_LABELS_EN,
    LIQUIDATION_REPORT_TRANSLATIONS,
)

JsonMap: TypeAlias = dict[str, object]


def translate_liquidation_report_text(loc: str, key: str) -> str:
    """Resolve ``key`` for ``loc`` with NL fallback and ``[key]`` placeholder."""
    entry = LIQUIDATION_REPORT_TRANSLATIONS.get(key)
    if not entry:
        return f"[{key}]"
    return entry.get(loc) or entry.get("nl") or f"[{key}]"


def _localized_text(loc: str, key: str) -> str | None:
    entry = LIQUIDATION_REPORT_TRANSLATIONS.get(key)
    if not entry:
        return None
    return entry.get(loc) or entry.get("nl")


def _copy_block(block: object) -> JsonMap | None:
    if not block or not isinstance(block, Mapping):
        return None
    return dict(block)


def _copy_items(value: object) -> list[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) if isinstance(item, Mapping) else item for item in value]


def _copy_dict_items(value: object) -> list[JsonMap]:
    return [item for item in _copy_items(value) if isinstance(item, dict)]


def _with_asset_class_labels(block: object, loc: str) -> JsonMap | None:
    enriched = _copy_block(block)
    if not enriched:
        return None
    lines = []
    for line in _copy_items(enriched.get("lines")):
        if isinstance(line, dict):
            class_code = line.get("asset_class") or ""
            line["class_label"] = translate_liquidation_report_text(
                loc, f"schedule_class_{class_code}"
            )
        lines.append(line)
    enriched["lines"] = lines
    return enriched


def enrich_premise_block(block: object, loc: str) -> JsonMap | None:
    premise = _copy_block(block)
    if not premise:
        return None
    premise["probability_of_distress"] = None
    premise["going_concern_weight"] = None
    premise["liquidation_weight"] = None
    primary_code = premise.get("primary") or "going_concern"
    if premise.get("trigger") == "balance_sheet_insolvent":
        primary_code = "orderly_liquidation"
        premise["primary"] = primary_code
        premise["secondary"] = "going_concern"
    secondary_code = premise.get("secondary") or "orderly_liquidation"
    trigger_code = premise.get("trigger") or "default_going_concern"
    premise["primary_code"] = primary_code
    premise["secondary_code"] = secondary_code
    premise["primary_label"] = translate_liquidation_report_text(
        loc, f"premise_value_{primary_code}"
    )
    premise["secondary_label"] = translate_liquidation_report_text(
        loc, f"premise_value_{secondary_code}"
    )
    premise["trigger_label"] = translate_liquidation_report_text(
        loc, f"premise_trigger_{trigger_code}"
    )
    premise["rationale"] = translate_liquidation_report_text(
        loc, "premise_review_" + str(trigger_code)
    )
    premise["sources"] = ["IVSC Standards Glossary — premise of value and forced sale"]
    return premise


def enrich_distress_block(block: object, loc: str) -> JsonMap | None:
    distress = _copy_block(block)
    if not distress:
        return None
    # Legacy scores could default missing inputs to zero. Never republish them.
    if distress.get("model_version") != "altman-z-double-prime.complete-inputs.v2":
        distress.update(available=False, z_double_prime=None, ratios=None, zone="undetermined")
    distress["probability_of_distress"] = None
    distress["rationale"] = translate_liquidation_report_text(
        loc, "distress_screen_scope" if distress.get("available") else "distress_missing_scope"
    )
    distress["warnings"] = []
    distress["sources"] = ["Altman (2000) — Z'' financial screen"]
    zone_code = distress.get("zone") or "undetermined"
    distress["zone_code"] = zone_code
    distress["zone_label"] = translate_liquidation_report_text(loc, f"distress_zone_{zone_code}")
    return distress


def enrich_cascade_block(block: object, loc: str) -> JsonMap | None:
    cascade = _copy_block(block)
    if not cascade:
        return None
    tiers = []
    for tier in _copy_items(cascade.get("tiers")):
        if isinstance(tier, dict) and loc == "en":
            code = tier.get("code") or ""
            label_en = CASCADE_TIER_LABELS_EN.get(code) if code else None
            if label_en:
                tier["label"] = label_en
        tiers.append(tier)
    cascade["tiers"] = tiers
    juris = cascade.get("jurisdiction", "BE")
    cascade["subtitle"] = translate_liquidation_report_text(
        loc, f"cascade_section_subtitle_{str(juris).lower()}"
    )
    return cascade


def enrich_tax_block(block: object, loc: str) -> JsonMap | None:
    tax = _copy_block(block)
    if not tax:
        return None
    lines = []
    for line in _copy_items(tax.get("lines")):
        if isinstance(line, dict):
            code = line.get("code") or ""
            localized = _localized_text(loc, f"tax_line_label_{code}") if code else None
            if localized:
                line["label"] = localized
        lines.append(line)
    tax["lines"] = lines
    juris = tax.get("jurisdiction", "BE")
    tax["subtitle"] = translate_liquidation_report_text(
        loc, f"tax_section_subtitle_{str(juris).lower()}"
    )
    return tax


def enrich_wind_down_block(block: object, loc: str) -> JsonMap | None:
    wind_down = _copy_block(block)
    if not wind_down:
        return None
    lines = []
    for line in _copy_items(wind_down.get("lines")):
        if isinstance(line, dict):
            component = line.get("component") or ""
            params = line.get("label_params") or {}
            localized_template = (
                _localized_text(loc, f"wind_down_line_label_{component}") if component else None
            )
            if localized_template:
                try:
                    line["label"] = localized_template.format(**params)
                except (KeyError, IndexError, ValueError):
                    pass
        lines.append(line)
    wind_down["lines"] = lines
    return wind_down


def enrich_reconciliation_block(block: object, loc: str) -> JsonMap | None:
    reconciliation = _copy_block(block)
    if not reconciliation:
        return None
    rec_code = reconciliation.get("recommendation") or "indeterminate"
    reconciliation["recommendation_label"] = translate_liquidation_report_text(
        loc, f"reconciliation_recommendation_{rec_code}"
    )
    reconciliation["going_concern_defensible"] = None
    reconciliation["defensible_label"] = translate_liquidation_report_text(
        loc, "reconciliation_requires_review"
    )
    reconciliation["rationale"] = translate_liquidation_report_text(loc, "reconciliation_scope")
    reconciliation["sources"] = ["IVSC Standards Glossary — premise of value"]
    return reconciliation


def _enrich_fair_value_hierarchy(value: object, loc: str) -> list[object]:
    fair_value_hierarchy = []
    for entry in _copy_items(value):
        if isinstance(entry, dict):
            level = entry.get("level") or "level_3"
            entry["level_label"] = translate_liquidation_report_text(loc, f"disclosure_fv_{level}")
            code = entry.get("code") or ""
            if code:
                label = _localized_text(loc, f"disclosure_fv_item_{code}")
                rationale = _localized_text(loc, f"disclosure_fv_rationale_{code}")
                if label:
                    entry["item_label"] = label
                if rationale:
                    entry["rationale"] = rationale
        fair_value_hierarchy.append(entry)
    return fair_value_hierarchy


def _localize_default_disclosure_list(
    disclosure: JsonMap, loc: str, field_name: str, key_prefix: str
) -> None:
    existing = disclosure.get(field_name) or []
    if not existing:
        return
    translated: list[str] = []
    for idx, _item in enumerate(existing):
        localized = _localized_text(loc, f"{key_prefix}.{idx}")
        if not localized:
            return
        translated.append(localized)
    disclosure[field_name] = tuple(translated)


def _localize_default_disclosure_string(
    disclosure: JsonMap, loc: str, field_name: str, key: str
) -> None:
    existing = disclosure.get(field_name)
    if not isinstance(existing, str) or not existing:
        return
    entry = LIQUIDATION_REPORT_TRANSLATIONS.get(key)
    if not entry:
        return
    localized = entry.get(loc) or entry.get("nl")
    if localized and existing.strip() == (entry.get("en") or "").strip():
        disclosure[field_name] = localized


def enrich_disclosure_block(block: object, loc: str) -> JsonMap | None:
    disclosure = _copy_block(block)
    if not disclosure:
        return None

    fair_value_hierarchy = _enrich_fair_value_hierarchy(disclosure.get("fair_value_hierarchy"), loc)
    if fair_value_hierarchy:
        disclosure["fair_value_hierarchy"] = fair_value_hierarchy

    _localize_default_disclosure_list(
        disclosure, loc, "limitations", "disclosure_default_limitations"
    )
    _localize_default_disclosure_list(
        disclosure, loc, "out_of_scope", "disclosure_default_out_of_scope"
    )
    _localize_default_disclosure_list(
        disclosure, loc, "assumptions", "disclosure_default_assumptions"
    )
    _localize_default_disclosure_string(
        disclosure, loc, "independence_statement", "disclosure_default_independence_statement"
    )
    _localize_default_disclosure_string(
        disclosure, loc, "conflicts_disclosure", "disclosure_default_conflicts_disclosure"
    )
    return disclosure


def _enrich_soa_cascade_tier_params(code: str, loc: str, params: JsonMap) -> JsonMap:
    if code != "deduction_cascade_tier" or loc != "en":
        return params
    tier_code = params.get("tier_code") or ""
    label_en = CASCADE_TIER_LABELS_EN.get(tier_code)
    if label_en:
        params = dict(params)
        params["tier_label"] = label_en
    return params


def _enrich_soa_tax_params(code: str, loc: str, params: JsonMap) -> JsonMap:
    if code != "deduction_tax_leakage" or loc != "en":
        return params
    tax_fallback = str(params.get("tax_label") or "")
    if tax_fallback.startswith("Belastinglekkage (BE"):
        params = dict(params)
        params["tax_label"] = LIQUIDATION_REPORT_TRANSLATIONS["soa_tax_label_be"]["en"]
    elif tax_fallback.startswith("Belastinglekkage (NL"):
        params = dict(params)
        params["tax_label"] = LIQUIDATION_REPORT_TRANSLATIONS["soa_tax_label_nl"]["en"]
    return params


def _enrich_soa_scenario_params(code: str, loc: str, params: JsonMap) -> JsonMap:
    if code != "gross_assets_at_fmv":
        return params
    scenario = str(params.get("scenario") or "")
    scenario_key = None
    if scenario.lower().startswith("geordend"):
        scenario_key = "soa_scenario_orderly_label"
    elif scenario.lower().startswith("gedwongen"):
        scenario_key = "soa_scenario_forced_label"
    localized = _localized_text(loc, scenario_key) if scenario_key else None
    if localized:
        params = dict(params)
        params["scenario"] = localized
    return params


def _format_localized_template(template: str | None, params: object) -> str | None:
    if not template:
        return None
    try:
        return template.format(**(params if isinstance(params, Mapping) else {}))
    except (KeyError, IndexError, ValueError):
        return None


def _apply_soa_label_and_rationale(step: JsonMap, loc: str, code: str) -> None:
    label = _format_localized_template(
        _localized_text(loc, f"soa_waterfall_label_{code}"),
        step.get("label_params") or {},
    )
    if label:
        step["label"] = label

    rationale = _localized_text(loc, f"soa_waterfall_rationale_{code}")
    if rationale:
        step["rationale"] = rationale


def _enrich_statement_of_affairs_step(step: object, loc: str) -> object:
    if not isinstance(step, Mapping):
        return step

    enriched = dict(step)
    code = str(enriched.get("step_code") or "")
    if not code:
        return enriched

    params = dict(enriched.get("label_params") or {})
    original_params = dict(params)
    params = _enrich_soa_cascade_tier_params(code, loc, params)
    params = _enrich_soa_tax_params(code, loc, params)
    params = _enrich_soa_scenario_params(code, loc, params)
    if params != original_params or code == "deduction_cascade_tier":
        enriched["label_params"] = params

    _apply_soa_label_and_rationale(enriched, loc, code)
    return enriched


def enrich_statement_of_affairs_block(block: object, loc: str) -> JsonMap | None:
    statement = _copy_block(block)
    if not statement:
        return None

    for scenario_key in ("waterfall_orderly", "waterfall_forced"):
        statement[scenario_key] = [
            _enrich_statement_of_affairs_step(step, loc)
            for step in _copy_items(statement.get(scenario_key))
        ]

    root_rationale = _localized_text(loc, "soa_root_rationale")
    if root_rationale:
        statement["rationale"] = root_rationale

    band = _copy_block(statement.get("band"))
    if band:
        band_rationale = _localized_text(loc, "soa_band_rationale")
        if band_rationale:
            band["rationale"] = band_rationale
        statement["band"] = band

    return statement


def enrich_sufficiency_block(block: object, loc: str) -> JsonMap | None:
    sufficiency = _copy_block(block)
    if not sufficiency:
        return None
    verdicts = []
    for verdict in _copy_dict_items(sufficiency.get("verdicts")):
        verdict["verdict_label"] = translate_liquidation_report_text(
            loc, f"sufficiency_verdict_{verdict.get('verdict', 'uncovered')}"
        )
        if loc == "en":
            code = verdict.get("code") or ""
            label_en = CASCADE_TIER_LABELS_EN.get(code) if code else None
            if label_en:
                verdict["label"] = label_en
        verdicts.append(verdict)
    sufficiency["verdicts"] = verdicts
    return sufficiency


def enrich_creditor_letter_pack(block: object, loc: str) -> JsonMap | None:
    letter_pack = _copy_block(block)
    if not letter_pack:
        return None
    letters = []
    for letter in _copy_dict_items(letter_pack.get("letters")):
        letter["urgency_label"] = translate_liquidation_report_text(
            loc, f"creditor_letters_urgency_{letter.get('urgency', 'standard')}"
        )
        letters.append(letter)
    letter_pack["letters"] = letters
    return letter_pack


def enrich_buyer_scenarios_block(block: object, loc: str) -> JsonMap | None:
    buyer_scenarios = _copy_block(block)
    if not buyer_scenarios:
        return None
    scenarios = []
    for scenario in _copy_dict_items(buyer_scenarios.get("scenarios")):
        scenario["label"] = scenario.get("label_en") if loc == "en" else scenario.get("label_nl")
        scenario["rationale"] = (
            scenario.get("rationale_en") if loc == "en" else scenario.get("rationale_nl")
        )
        scenarios.append(scenario)
    buyer_scenarios["scenarios"] = scenarios
    return buyer_scenarios


def enrich_sensitivity_block(block: object, loc: str) -> JsonMap | None:
    sensitivity = _copy_block(block)
    if not sensitivity:
        return None

    tornado = []
    for bar in _copy_dict_items(sensitivity.get("tornado")):
        driver_name = bar.get("driver_name") or ""
        localized = (
            _localized_text(loc, f"sensitivity_driver_{driver_name}") if driver_name else None
        )
        if localized:
            bar["label"] = localized
        tornado.append(bar)
    if tornado:
        sensitivity["tornado"] = tornado

    drivers = []
    for driver in _copy_dict_items(sensitivity.get("drivers")):
        driver_name = driver.get("name") or ""
        localized = (
            _localized_text(loc, f"sensitivity_driver_{driver_name}") if driver_name else None
        )
        if localized:
            driver["label"] = localized
        drivers.append(driver)
    if drivers:
        sensitivity["drivers"] = drivers

    return sensitivity


def enrich_audit_trail_block(block: object) -> JsonMap | None:
    audit_trail = _copy_block(block)
    if not audit_trail:
        return None
    run_id = audit_trail.get("run_id") or ""
    effective_date = audit_trail.get("effective_date") or ""
    if run_id and effective_date:
        audit_trail["short_run_id"] = f"{str(effective_date).replace('-', '')}-{str(run_id)[:8]}"
    payload_hash = audit_trail.get("payload_hash") or ""
    if payload_hash:
        audit_trail["payload_hash_short"] = str(payload_hash)[:12]
    return audit_trail


def enrich_liquidation_detail_blocks(details: Mapping[str, object], loc: str) -> JsonMap:
    """Return localized copies of the detail blocks used by liquidation templates."""
    distress = enrich_distress_block(details.get("distress"), loc)
    premise = _copy_block(details.get("premise"))
    if (
        premise
        and premise.get("trigger") == "distress_score"
        and not (distress and distress.get("available"))
    ):
        premise.update(
            primary="going_concern",
            secondary="orderly_liquidation",
            trigger="default_going_concern",
        )
    return {
        "premise": enrich_premise_block(premise, loc),
        "distress": distress,
        "asset_schedule": _with_asset_class_labels(details.get("asset_schedule"), loc),
        "priority_cascade_orderly": enrich_cascade_block(
            details.get("priority_cascade_orderly"), loc
        ),
        "priority_cascade_forced": enrich_cascade_block(
            details.get("priority_cascade_forced"), loc
        ),
        "tax_leakage_orderly": enrich_tax_block(details.get("tax_leakage_orderly"), loc),
        "tax_leakage_forced": enrich_tax_block(details.get("tax_leakage_forced"), loc),
        "wind_down_orderly": enrich_wind_down_block(details.get("wind_down_orderly"), loc),
        "wind_down_forced": enrich_wind_down_block(details.get("wind_down_forced"), loc),
        "disposal_schedule_pv_orderly": _with_asset_class_labels(
            details.get("disposal_schedule_pv_orderly"), loc
        ),
        "disposal_schedule_pv_forced": _with_asset_class_labels(
            details.get("disposal_schedule_pv_forced"), loc
        ),
        "sensitivity": enrich_sensitivity_block(details.get("sensitivity"), loc),
        "premise_reconciliation": enrich_reconciliation_block(
            details.get("premise_reconciliation"), loc
        ),
        "disclosure": enrich_disclosure_block(details.get("disclosure"), loc),
        "replacement_cost": _with_asset_class_labels(details.get("replacement_cost"), loc),
        "statement_of_affairs": enrich_statement_of_affairs_block(
            details.get("statement_of_affairs"), loc
        ),
        "audit_trail": enrich_audit_trail_block(details.get("audit_trail")),
        "sufficiency_memo_orderly": enrich_sufficiency_block(
            details.get("sufficiency_memo_orderly"), loc
        ),
        "sufficiency_memo_forced": enrich_sufficiency_block(
            details.get("sufficiency_memo_forced"), loc
        ),
        "creditor_letters_orderly": enrich_creditor_letter_pack(
            details.get("creditor_letters_orderly"), loc
        ),
        "creditor_letters_forced": enrich_creditor_letter_pack(
            details.get("creditor_letters_forced"), loc
        ),
        "strategic_buyer_scenarios": enrich_buyer_scenarios_block(
            details.get("strategic_buyer_scenarios"), loc
        ),
    }
