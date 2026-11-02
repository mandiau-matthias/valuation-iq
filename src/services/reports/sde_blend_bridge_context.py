"""Disclose an executed earnings-method blend separately from balance-sheet items."""

from decimal import Decimal

from src.utils.decimal_helpers import safe_decimal_or_zero


def _matches_earnings_rounding(
    context: dict[str, object], *, headline: Decimal, market_leg: Decimal, residual: Decimal
) -> bool:
    """Admit only a proven cent-rounded earnings projection, not an unexplained gap."""
    if (
        not context.get("supports_metric_to_ev_bridge")
        or context.get("multiple_metric_type") != "EBITDA"
    ):
        return False
    metric = safe_decimal_or_zero(context.get("valuation_basis_value"))
    weighted = safe_decimal_or_zero(context.get("weighted_ebitda_total"))
    multiple = safe_decimal_or_zero(context.get("bridge_applied_multiple"))
    displayed_ev = safe_decimal_or_zero(context.get("enterprise_value_mid"))
    values = (metric, weighted, multiple, displayed_ev)
    if any(not value.is_finite() or value <= 0 for value in values):
        return False
    half_cent = Decimal("0.005")
    # The displayed metric can be rounded to cents before multiplication while
    # Step 11 retains the unrounded weighted earnings. Verify both EV identities.
    if (
        abs(metric - weighted) > half_cent
        or abs(metric * multiple - displayed_ev) > half_cent
        or abs(weighted * multiple - market_leg) > half_cent
    ):
        return False
    rounding_delta = (metric - weighted) * multiple
    return abs((headline - market_leg) - (residual + rounding_delta)) <= half_cent


def apply_sde_blend_bridge_context(context: dict[str, object], *, locale: str) -> None:
    context.pop("bridge_residual_label", None)
    if not context.get("sde_blend_applied") or not context.get("has_bridge_residual"):
        return
    residual = safe_decimal_or_zero(context.get("bridge_residual"))
    headline = safe_decimal_or_zero(context.get("sde_blend_headline_ev"))
    market_leg = safe_decimal_or_zero(context.get("ebitda_blend_leg_ev"))
    # Classify only the exact executed synthesis delta. An unrelated remaining
    # discrepancy must remain a visible reconciliation diagnostic.
    if abs((headline - market_leg) - residual) > Decimal("0.01") and not _matches_earnings_rounding(
        context, headline=headline, market_leg=market_leg, residual=residual
    ):
        return
    labels = {
        "en": (
            "SDE synthesis adjustment",
            "The final equity value includes the disclosed EBITDA/SDE weighting. Balance-sheet adjustments are applied only where supplied; missing debt and cash remain unverified.",
        ),
        "fr": (
            "Ajustement de synthèse SDE",
            "La valeur finale des capitaux propres inclut la pondération EBITDA/SDE présentée. Les ajustements de bilan ne sont appliqués que s’ils sont fournis ; la dette et la trésorerie manquantes restent non vérifiées.",
        ),
        "nl": (
            "SDE-synthesecorrectie",
            "De uiteindelijke aandelenwaarde omvat de toegelichte EBITDA/SDE-weging. Balanscorrecties worden alleen toegepast indien aangeleverd; ontbrekende schuld en kasmiddelen blijven ongeverifieerd.",
        ),
    }
    label, intro = labels.get(locale.lower()[:2], labels["nl"])
    context["bridge_residual_label"] = label
    context["value_waterfall_intro_text"] = intro
    steps = context.get("valuation_waterfall_steps")
    if not isinstance(steps, list) or any(
        isinstance(s, dict) and s.get("source") == "sde_synthesis" for s in steps
    ):
        return
    if not steps or not isinstance(steps[-1], dict) or steps[-1].get("kind") != "total":
        return
    end = safe_decimal_or_zero(context.get("equity_value"))
    context["valuation_waterfall_steps"] = [
        *steps[:-1],
        {
            "source": "sde_synthesis",
            "kind": "decrease" if residual < 0 else "increase",
            "tone": "negative" if residual < 0 else "positive",
            "label": label,
            "short_label": "SDE",
            "start_value": float(end - residual),
            "end_value": float(end),
            "delta_value": float(residual),
            "annotation": None,
        },
        steps[-1],
    ]
