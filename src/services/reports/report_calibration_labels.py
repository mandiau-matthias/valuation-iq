"""Locale and chart-label helpers for calibration waterfalls."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from src.services.infrastructure.translations import ReportTranslations, normalize_report_locale

JsonMap = dict[str, object]
LocalizedWaterfallRow = tuple[str, str]

# NOTE: the engine emits a SIGNED percentage (e.g. "-18.0%" for a downward
# revenue-trend adjustment). The capture group MUST accept an optional leading
# sign so localized reports do not silently leak the raw English description.
_REVENUE_TREND_ADJ_EN_RE = re.compile(
    r"^Revenue\s+Trend\s+Adjustment:\s*"
    r"([+-]?[0-9]+(?:[.,][0-9]+)?)\s*%\s+applied\s+to\s+multiple\s*$",
    re.IGNORECASE,
)

_WATERFALL_LOCALISED_LOCALES = ("nl", "fr")


def _copy_waterfall_row(row: Mapping[str, object]) -> JsonMap:
    copied = dict(row)
    evidence = copied.get("strength_factor_discount_evidence")
    if evidence is not None and "strength_factor_evidence" not in copied:
        copied["strength_factor_evidence"] = evidence
    return copied


def localize_discount_waterfall_for_locale(
    waterfall: Sequence[Mapping[str, object]],
    locale: str,
    t: ReportTranslations,
) -> list[JsonMap]:
    """Translate engine-emitted Step 11 discount waterfall copy to report locale."""
    norm_locale = normalize_report_locale(locale)
    if norm_locale not in _WATERFALL_LOCALISED_LOCALES or not waterfall:
        return [_copy_waterfall_row(row) for row in waterfall]
    out: list[JsonMap] = []
    for row in waterfall:
        label = str(row.get("label") or "")
        desc = str(row.get("description") or "")
        new_label, new_desc = localize_waterfall_row(label, desc, t, norm_locale)
        new_row = _copy_waterfall_row(row)
        new_row["label"] = new_label
        new_row["description"] = new_desc
        out.append(new_row)
    return out


def localize_waterfall_row(
    label: str,
    description: str,
    t: ReportTranslations,
    locale: str = "nl",
) -> tuple[str, str]:
    """Translate a single waterfall row when the engine emitted English copy."""
    raw_label, raw_desc = label, description
    low_label = label.strip().lower()
    low_desc = description.strip().lower()
    norm_locale = normalize_report_locale(locale)

    for localized in (
        _zero_discount_row(low_desc, t),
        _base_multiple_row(low_label, low_desc, raw_desc, t),
        _discount_label_row(low_label, raw_desc, t, norm_locale),
        _revenue_trend_row(low_label, description, raw_desc, t),
        _owner_concentration_row(low_label, t),
    ):
        if localized is not None:
            return localized

    return raw_label, raw_desc


def _zero_discount_row(low_desc: str, t: ReportTranslations) -> LocalizedWaterfallRow | None:
    if "size discount: 0%" in low_desc and "step 2 calibration" in low_desc:
        return t.ledger_dw_size_discount, t.ledger_dw_size_discount_note_zero
    if "liquidity discount: 0%" in low_desc:
        return t.ledger_dw_liquidity_discount, t.ledger_dw_liquidity_discount_note_zero
    return None


def _base_multiple_row(
    low_label: str,
    low_desc: str,
    raw_desc: str,
    t: ReportTranslations,
) -> LocalizedWaterfallRow | None:
    if not low_label.startswith("base multiple"):
        return None
    return t.ledger_dw_base_multiple_step3, _base_multiple_description(low_desc, raw_desc, t)


def _base_multiple_description(
    low_desc: str,
    raw_desc: str,
    t: ReportTranslations,
) -> str:
    if "initial " not in low_desc or "multiple from industry comparables" not in low_desc:
        return raw_desc
    if "revenue" in low_desc:
        return t.ledger_dw_initial_multiple_desc_revenue
    if "sde" in low_desc:
        return t.ledger_dw_initial_multiple_desc_sde
    return t.ledger_dw_initial_multiple_desc_ebitda


def _discount_label_row(
    low_label: str,
    raw_desc: str,
    t: ReportTranslations,
    norm_locale: str,
) -> LocalizedWaterfallRow | None:
    if low_label == "size discount":
        return t.ledger_dw_size_discount, _localise_size_discount_desc(raw_desc, t, norm_locale)
    if low_label == "liquidity discount":
        return t.ledger_dw_liquidity_discount, _localise_liquidity_discount_desc(raw_desc, t)
    return None


def _revenue_trend_row(
    low_label: str,
    description: str,
    raw_desc: str,
    t: ReportTranslations,
) -> LocalizedWaterfallRow | None:
    if low_label != "revenue trend":
        return None
    match = _REVENUE_TREND_ADJ_EN_RE.match(description.strip())
    if match:
        pct_s = match.group(1).strip().replace(".", ",")
        return (
            t.ledger_dw_revenue_trend,
            t.ledger_dw_revenue_trend_adjust_template.format(pct=pct_s),
        )
    return t.ledger_dw_revenue_trend, raw_desc or t.ledger_dw_revenue_trend_desc


def _owner_concentration_row(
    low_label: str,
    t: ReportTranslations,
) -> LocalizedWaterfallRow | None:
    if "owner concentration" in low_label or low_label.startswith("structural owner"):
        return t.ledger_dw_owner_concentration, t.ledger_dw_owner_concentration_note
    return None


def localize_waterfall_row_nl(
    label: str,
    description: str,
    t: ReportTranslations,
) -> tuple[str, str]:
    """Backward-compatible NL wrapper around the locale-aware row localizer."""
    return localize_waterfall_row(label, description, t, "nl")


_SIZE_DISCOUNT_TIER_RE = re.compile(
    r"Size\s+Discount:\s*([^()]+?)\s*"
    r"(?:\(([^)]+)\)\s*)?"
    r"(?:\(reduced\s+(\d+)\s*%[^)]*\))?\s*"
    r"company\s+discount\s+applied\s+to\s+multiple",
    re.IGNORECASE,
)

_LIQUIDITY_DISCOUNT_PRIVATE_RE = re.compile(
    r"Liquidity\s+Discount:\s*Private\s+company\s+illiquidity\s+discount\s+applied\s+to\s+multiple",
    re.IGNORECASE,
)

_SIZE_TIER_NL = {
    "micro": "Micro (<€1M)",
    "small": "Klein (€1M-€2M)",
    "small-medium": "Klein-middelgroot (€1M-€2M)",
    "medium": "Middelgroot (€2M-€10M)",
    "large": "Groot (>€10M)",
}

_SIZE_TIER_FR = {
    "micro": "Micro (<€1M)",
    "small": "Petite (€1M-€2M)",
    "small-medium": "Petite-moyenne (€1M-€2M)",
    "medium": "Moyenne (€2M-€10M)",
    "large": "Grande (>€10M)",
}

_SIZE_TIER_EN = {
    "micro": "Micro (<€1M)",
    "small": "Small (€1M-€2M)",
    "small-medium": "Small-medium (€1M-€2M)",
    "medium": "Medium (€2M-€10M)",
    "large": "Large (>€10M)",
}

_SIZE_TIER_BY_LOCALE = {"nl": _SIZE_TIER_NL, "fr": _SIZE_TIER_FR, "en": _SIZE_TIER_EN}

_COMPACT_TRANSLATION_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("consensus", "mediaan", "median"), "wf_compact_market_median"),
    (("kmo", "sme calibration"), "wf_compact_sme_calib"),
    (("sleutelpersoon", "key person"), "wf_compact_key_person"),
    (("size", "micro", "discount", "taille"), "wf_compact_size"),
    (("other adjustment", "overige aanpassing"), "wf_compact_other_adj"),
)

_BASE_MULTIPLE_LABELS: tuple[tuple[str, str], ...] = (
    ("basismultiple", "Basismultiple"),
    ("multiple de base", "Multiple de base"),
    ("base multiple", "Base multiple"),
)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _compact_translated_label(normalized: str, t: ReportTranslations) -> str | None:
    if "database" in normalized and "p50" in normalized:
        return str(t.wf_compact_database_p50)
    if "liquid" in normalized or "dlom" in normalized:
        return "DLOM"
    for needles, translation_key in _COMPACT_TRANSLATION_RULES:
        if _contains_any(normalized, needles):
            return str(getattr(t, translation_key))
    return None


def _compact_base_multiple_label(normalized: str) -> str | None:
    for needle, compact_label in _BASE_MULTIPLE_LABELS:
        if needle in normalized:
            return compact_label
    return None


def _compact_owner_concentration_label(normalized: str) -> str | None:
    if "eigenaarsconcentratie" not in normalized and "owner concentration" not in normalized:
        return None
    return "Eig.-concentratie" if "eigenaars" in normalized else "Owner concentr."


def _localise_size_discount_desc(raw_desc: str, t: ReportTranslations, locale: str = "nl") -> str:
    """Translate engine-emitted English size-discount descriptions."""
    if not raw_desc:
        return t.ledger_dw_size_discount
    match = _SIZE_DISCOUNT_TIER_RE.search(raw_desc)
    if not match:
        return raw_desc
    tier_raw = (match.group(1) or "").strip()
    tier_key = tier_raw.lower()
    tier_map = _SIZE_TIER_BY_LOCALE.get(normalize_report_locale(locale), _SIZE_TIER_NL)
    tier_localised = tier_map.get(tier_key, tier_raw)
    reduction = match.group(3)
    suffix = ""
    if reduction:
        suffix = t.ledger_dw_size_discount_halved_suffix_template.format(reduction=reduction)
    return t.ledger_dw_size_discount_segment_template.format(tier=tier_localised, suffix=suffix)


def _localise_liquidity_discount_desc(raw_desc: str, t: ReportTranslations) -> str:
    """Translate engine-emitted English liquidity-discount descriptions."""
    if not raw_desc:
        return t.ledger_dw_liquidity_discount
    if _LIQUIDITY_DISCOUNT_PRIVATE_RE.search(raw_desc):
        return t.ledger_dw_liquidity_discount_private_desc
    return raw_desc


def compact_waterfall_label(label: str, t: ReportTranslations) -> str:
    """Return short, legible labels for SVG waterfall charts."""
    text = str(label or "").strip()
    if not text:
        return ""

    normalized = text.lower()
    compact = (
        _compact_translated_label(normalized, t)
        or _compact_base_multiple_label(normalized)
        or _compact_owner_concentration_label(normalized)
    )
    if compact:
        return compact
    if len(text) <= 18:
        return text
    return f"{text[:16].rstrip()}…"


def compact_balance_sheet_adjustment_label(
    label: str,
    category: str,
    ordinal: int,
    t: ReportTranslations,
) -> str:
    """Return ultra-compact labels for dense balance-sheet adjustment bridges."""
    category_key = str(category or "other").lower()
    mapping: dict[str, str] = {
        "debt": str(t.wf_bs_debt),
        "asset": str(t.wf_bs_asset),
        "provision": str(t.wf_bs_provision),
        "tax": str(t.wf_bs_tax),
        "cash": str(t.wf_bs_cash),
        "working_capital": str(t.wf_bs_working_capital),
        "other": str(t.wf_bs_other),
    }
    base = mapping.get(category_key, str(t.wf_bs_other))
    if ordinal > 1:
        return f"{base} {ordinal}"
    compact = compact_waterfall_label(label, t)
    if len(compact) <= 10:
        return compact
    return base
