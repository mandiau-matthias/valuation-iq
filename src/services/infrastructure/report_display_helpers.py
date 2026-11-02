"""Report display helpers that depend on translation fields but not translation data."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, SupportsFloat, SupportsIndex, cast

if TYPE_CHECKING:
    from src.services.infrastructure.translations import ReportTranslations


def _field_value(contribution: object, key: str, default: object = None) -> object:
    if isinstance(contribution, Mapping):
        return contribution.get(key, default)
    return getattr(contribution, key, default)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        floatable = cast(str | bytes | bytearray | SupportsFloat | SupportsIndex, value)
        return float(floatable)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class EbitdaAdjustmentLabels:
    """Localized strings for the EBITDA normalization table (main + simplified reports)."""

    reported_ebitda_year: str
    normalized_ebitda_year: str
    adj_fallback: str
    submitted_metadata: str
    total_normalization_label: str
    auto_desc_count_template: str
    auto_desc_aggregate: str


def resolve_synthesis_method_label(
    method_key: Optional[str],
    original_label: Optional[str],
    t: "ReportTranslations",
) -> str:
    """
    Map engine method_key to a locale-consistent label for the synthesis table.

    Falls back to ``original_label`` (from the calculation engine) when unknown.
    """
    if not method_key:
        return original_label or ""
    mk = method_key.strip().lower()
    ol = (original_label or "").lower()
    if mk == "upswitch_adaptive" and "balans" in ol:
        return str(t.synthesis_method_upswitch_adaptive_balance_sheet)
    mapping: dict[str, str] = {
        "ebitda_multiple": str(t.synthesis_method_ebitda_multiple),
        "dcf": str(t.synthesis_method_dcf),
        "sde_multiple": str(t.synthesis_method_sde),
        "omzet_multiple": str(t.synthesis_method_revenue),
        "revenue_multiple": str(t.synthesis_method_revenue),
        "arr_multiple": str(t.synthesis_method_arr),
        "adjusted_nav": str(t.synthesis_method_adjusted_nav),
        "fiscal_4x": str(t.synthesis_method_fiscal_4x),
        "upswitch_adaptive": str(t.synthesis_method_upswitch_adaptive),
    }
    if mk in mapping:
        return mapping[mk]
    return original_label or method_key


def build_synthesis_formula_display(
    contributions: list[object],
    blended_equity_value: object,
    t: "ReportTranslations",
    format_eur_compact: Callable[[object], str],
    *,
    value_field: str = "equity_value",
) -> str:
    """Build the weighted-formula line, e.g. ``(€1.000.000 × 50%) + … = €…``."""
    parts: list[str] = []
    for c in contributions:
        ev = _field_value(c, value_field, 0)
        w = _safe_float(_field_value(c, "weight", 0))
        amt = f"€{format_eur_compact(ev)}"
        pct = round(w * 100)
        parts.append(str(t.synthesis_formula_term_template).format(amount=amt, pct=pct))
    blended_str = f"€{format_eur_compact(blended_equity_value)}"
    suffix = str(t.synthesis_formula_result_template).format(amount=blended_str)
    if not parts:
        return suffix
    return str(t.synthesis_formula_plus).join(parts) + suffix


def resolve_ebitda_adjustment_labels(
    locale: str,
    t: "ReportTranslations",
) -> EbitdaAdjustmentLabels:
    """
    Resolve EBITDA adjustment labels for nl/en via ``t``, or French literals when ``locale`` is fr-*.
    """
    loc = str(locale or "").strip().lower()
    if loc.startswith("fr"):
        return EbitdaAdjustmentLabels(
            reported_ebitda_year="EBITDA declare par l'entreprise ({year})",
            normalized_ebitda_year="EBITDA normalise ({year})",
            adj_fallback="Ajustement",
            submitted_metadata="Metadonnees fournies",
            total_normalization_label="Total des ajustements de normalisation",
            auto_desc_count_template=(
                "{count} ajustement(s) de normalisation issus des metadonnees fournies"
            ),
            auto_desc_aggregate="Delta de normalisation issu des metadonnees fournies",
        )
    return EbitdaAdjustmentLabels(
        reported_ebitda_year=t.adj_reported_ebitda_year,
        normalized_ebitda_year=t.adj_normalized_ebitda_year,
        adj_fallback=t.adj_fallback_label,
        submitted_metadata=t.adj_submitted_metadata,
        total_normalization_label=t.adj_total_normalization_label,
        auto_desc_count_template=t.adj_auto_desc_count_template,
        auto_desc_aggregate=t.adj_auto_desc_aggregate,
    )
