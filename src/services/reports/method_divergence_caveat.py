"""Client-facing caveat for a DCF↔market method divergence on a hybrid headline.

The QA invariant ``dcf_market_cross_method_divergence``
(``ma_invariant_checks.py``) DETECTS the divergence (logged + persisted on the
result); this module SURFACES it in the report PDF as a reader-facing notice. Same
trigger — one leg more than ``max_divergence`` above the other (default 100% ⇒ the
larger leg is ≥2× the smaller) — so the QA layer and the printed report agree.

Why it matters (IJsjes VAL-2026-C24F): a 73%-weighted DCF leg (€978K, implying
~10.9× EV/EBITDA on fallback forecast assumptions) blended with a €315K market leg
printed a €786K headline ~3× the market value, with no flag. The headline honours
the advisor's weights — but the reader must see that the two methods disagree and
that the figure is therefore forecast-sensitive.

Pure + framework-free: the predicate and the localized copy unit-test without the
renderer. The builder returns copy ALREADY resolved for the report locale, so the
template only renders ``title`` / ``body``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

_DEFAULT_MAX_DIVERGENCE = Decimal("1.0")  # 100% — larger leg ≥ 2× smaller


def _dec(value: object) -> Optional[Decimal]:
    try:
        return Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return None


def _leg_ev(leg: object) -> Optional[Decimal]:
    """Enterprise value of a leg (DCF / multiples) — attribute or mapping."""
    if leg is None:
        return None
    raw = leg.get("enterprise_value") if isinstance(leg, dict) else getattr(leg, "enterprise_value", None)
    return _dec(raw)


def _resolved_max_divergence(max_divergence: Optional[Decimal]) -> Decimal:
    if max_divergence is not None:
        return max_divergence
    try:
        from src.config import get_settings

        return Decimal(str(get_settings().ma_invariant_dcf_market_max_divergence))
    except Exception:
        return _DEFAULT_MAX_DIVERGENCE


def should_flag_method_divergence(
    dcf_ev: object,
    multiples_ev: object,
    max_divergence: Optional[Decimal] = None,
) -> bool:
    """True when the two legs diverge beyond tolerance (a genuine blend only).

    Reuses the QA invariant's threshold (``ma_invariant_dcf_market_max_divergence``)
    by default so the printed caveat fires exactly when the invariant does.
    """
    dcf = _dec(dcf_ev)
    mkt = _dec(multiples_ev)
    if dcf is None or mkt is None or dcf <= 0 or mkt <= 0:
        return False
    smaller = min(dcf, mkt)
    return (abs(dcf - mkt) / smaller) > _resolved_max_divergence(max_divergence)


def _loc(locale: object) -> str:
    code = str(locale or "nl").strip().lower()[:2]
    return code if code in ("en", "nl", "fr") else "nl"


def _fmt_ratio(ratio: Decimal, loc: str) -> str:
    text = f"{ratio:.1f}×"
    return text.replace(".", ",") if loc in ("nl", "fr") else text


def _fmt_weight(weight: Optional[Decimal]) -> Optional[str]:
    if weight is None:
        return None
    pct = weight * Decimal("100") if weight <= Decimal("1") else weight
    return f"{pct:.0f}%"


_TITLE = {
    "en": "Method divergence — the DCF and market approaches disagree",
    "nl": "Methodedivergentie — DCF en marktbenadering verschillen sterk",
    "fr": "Divergence de méthode — le DCF et l’approche de marché s’écartent",
}


def _body(loc: str, ratio_text: str, weight_text: Optional[str]) -> str:
    if loc == "en":
        weight_clause = (
            f", and the headline weights DCF at {weight_text}" if weight_text else ""
        )
        return (
            "The blended headline combines two methods that disagree materially: the DCF "
            f"leg is about {ratio_text} the market-multiple leg. The DCF rests on forecast "
            "assumptions (growth, margin, terminal value) the historical record may not yet "
            f"support{weight_clause}. Treat the figure as forecast-sensitive — weight toward "
            "the market approach, or validate the forecast and benchmark, before relying on "
            "it for a transaction."
        )
    if loc == "fr":
        weight_clause = (
            f", et la valeur principale pondère le DCF à {weight_text}" if weight_text else ""
        )
        return (
            "La valeur principale combinée associe deux méthodes qui divergent sensiblement : "
            f"la jambe DCF représente environ {ratio_text} la jambe multiple de marché. Le DCF "
            "repose sur des hypothèses prévisionnelles (croissance, marge, valeur terminale) que "
            f"l’historique peut ne pas encore étayer{weight_clause}. Considérez le chiffre comme "
            "sensible aux prévisions — pondérez vers l’approche de marché, ou validez les "
            "prévisions et le benchmark, avant de vous y fier pour une transaction."
        )
    weight_clause = (
        f", en de hoofdwaarde weegt DCF op {weight_text}" if weight_text else ""
    )
    return (
        "De gemengde hoofdwaarde combineert twee methodes die sterk verschillen: het DCF-been "
        f"is ongeveer {ratio_text} het markt-multiple-been. De DCF berust op prognose-aannames "
        "(groei, marge, terminale waarde) die de historiek mogelijk nog niet ondersteunt"
        f"{weight_clause}. Behandel het getal als prognosegevoelig — weeg richting de "
        "marktbenadering, of valideer de prognose en de benchmark, voordat u erop vertrouwt "
        "voor een transactie."
    )


def build_method_divergence_caveat(
    dcf_leg: object,
    multiples_leg: object,
    dcf_weight: object,
    locale: object,
    max_divergence: Optional[Decimal] = None,
) -> Optional[dict]:
    """Localized notice dict for a divergent hybrid, or ``None`` when in tolerance.

    ``dcf_leg`` / ``multiples_leg`` are the per-leg objects (``response.dcf_valuation``
    / ``response.multiples_valuation``) — attribute- or mapping-shaped. Returns
    ``{title, body, ratio, dcf_enterprise_value, multiples_enterprise_value,
    dcf_weight_pct}`` already resolved for ``locale``.
    """
    dcf_ev = _leg_ev(dcf_leg)
    mkt_ev = _leg_ev(multiples_leg)
    if not should_flag_method_divergence(dcf_ev, mkt_ev, max_divergence):
        return None
    assert dcf_ev is not None and mkt_ev is not None  # guaranteed by the predicate
    higher, lower = (dcf_ev, mkt_ev) if dcf_ev >= mkt_ev else (mkt_ev, dcf_ev)
    ratio = higher / lower
    loc = _loc(locale)
    weight_text = _fmt_weight(_dec(dcf_weight))
    return {
        "title": _TITLE[loc],
        "body": _body(loc, _fmt_ratio(ratio, loc), weight_text),
        "ratio": float(ratio),
        "dcf_enterprise_value": float(dcf_ev),
        "multiples_enterprise_value": float(mkt_ev),
        "dcf_weight_pct": weight_text,
    }
