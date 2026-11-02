"""Defensibility banner — i18n HTML for sub-FULL_REPORT classifications.

On SME reports the banner is embedded on the **disclaimers page** (end of the
report) via Jinja (``defensibility_scope_banner_html``) so the cover stays
uncluttered; screen and PDF twins stay in sync. The PLG diagonal watermark
(free tier) is applied separately in ``/pdf``.

Three locales (NL, EN, FR); unknown locales fall back to NL.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from html import escape
from typing import Iterable, Optional, Union

# Mirrors ``main_report/pages/disclaimers.html`` and
# ``main_report_pdf/pages/disclaimers.html``: ``_inject_watermark`` replaces
# this comment with scope HTML on the disclaimer page, never on the cover.
DEFENSIBILITY_BANNER_INJECT_ANCHOR = "<!--upswitch-defensibility-banner-inject-->"

# Match the opening tag of an embedded scope banner (Jinja or inject), including
# single-quoted ``class=`` variants — ``in html`` on the raw prefix misses those.
_DEFENSIBILITY_BANNER_OPEN_TAG_RE = re.compile(
    r'<div\s+class\s*=\s*["\']upswitch-defensibility-banner["\']',
    re.IGNORECASE,
)


def defensibility_banner_div_count(html: str) -> int:
    """Count embedded scope-banner roots in HTML (0 if none)."""
    if not html:
        return 0
    return len(_DEFENSIBILITY_BANNER_OPEN_TAG_RE.findall(html))


def strip_defensibility_banner_inject_anchor(html: str) -> str:
    """Remove any leftover injection anchor comments from final HTML.

    Templates keep the anchor for ``_inject_watermark``; when the scope banner is
    already rendered from Jinja (or no injection ran), the comment must not
    survive into WeasyPrint output.
    """
    if not html or DEFENSIBILITY_BANNER_INJECT_ANCHOR not in html:
        return html
    return html.replace(DEFENSIBILITY_BANNER_INJECT_ANCHOR, "")


_TEXTS = {
    "nl": {
        "title": "Indicatieve conceptschatting",
        "scope_intro": "{scope} — {reason}",
        "scope_intro_no_reason": "{scope}",
        "confidence_cap_line": "Vertrouwensplafond: {pct}%.",
        "footer": (
            "Niet bestemd voor formele transactie- of fiscale doeleinden "
            "zonder aanvullende validatie."
        ),
        "scope_labels": {
            "Business Valuation Report": "Volledig waarderingsrapport",
            "Valuation Analysis with Limitations": "Waarderingsanalyse met beperkingen",
            "Preliminary Indication of Value": "Voorlopige indicatie van waarde",
            "Special Purpose Valuation": "Speciale-doeleinden waardering",
        },
        "default_reason": "beperkte scope",
        # Engine-signal translations live here so the banner is always NL/EN
        # consistent even when the upstream signal was English.
        "translate_signal": lambda s: s,
    },
    "en": {
        "title": "Indicative draft estimate",
        "scope_intro": "{scope} — {reason}",
        "scope_intro_no_reason": "{scope}",
        "confidence_cap_line": "Confidence ceiling: {pct}%.",
        "footer": (
            "Not intended for formal transaction or tax purposes without " "additional validation."
        ),
        "scope_labels": {
            "Business Valuation Report": "Full Valuation Report",
            "Valuation Analysis with Limitations": "Valuation Analysis with Limitations",
            "Preliminary Indication of Value": "Preliminary Indication of Value",
            "Special Purpose Valuation": "Special Purpose Valuation",
        },
        "default_reason": "limited scope",
        "translate_signal": lambda s: _translate_signal_to_en(s),
    },
    "fr": {
        "title": "Estimation indicative préliminaire",
        "scope_intro": "{scope} — {reason}",
        "scope_intro_no_reason": "{scope}",
        "confidence_cap_line": "Plafond de confiance : {pct} %.",
        "footer": (
            "Non destiné à des fins transactionnelles ou fiscales formelles "
            "sans validation complémentaire."
        ),
        "scope_labels": {
            "Business Valuation Report": "Rapport de valorisation complet",
            "Valuation Analysis with Limitations": ("Analyse de valorisation avec limitations"),
            "Preliminary Indication of Value": "Indication préliminaire de valeur",
            "Special Purpose Valuation": "Valorisation à usage spécifique",
        },
        "default_reason": "portée limitée",
        "translate_signal": lambda s: _translate_signal_to_fr(s),
    },
}


# Cap-reason strings come from ``report_classifier.get_confidence_cap_reason``
# which returns English. Translate the known phrasings into NL so a Dutch
# banner doesn't surface mixed-language text. Unknown phrasings fall through
# unchanged (better to show English than to drop the rationale).
_EN_TO_NL_CAP_REASON_MAP = {
    "Insufficient historical data for reliable trend analysis": (
        "Onvoldoende historische gegevens voor een betrouwbare trendanalyse"
    ),
    "Material going concern uncertainty and sustained operating losses": (
        "Materiële continuïteitsonzekerheid en aanhoudende operationele verliezen"
    ),
    "Limited historical period constrains trend identification and normalization": (
        "Beperkte historische periode beperkt trendidentificatie en normalisatie"
    ),
    "Significant operating losses increase valuation uncertainty": (
        "Aanhoudende operationele verliezen verhogen de waarderingsonzekerheid"
    ),
}

_EN_TO_FR_CAP_REASON_MAP = {
    "Insufficient historical data for reliable trend analysis": (
        "Données historiques insuffisantes pour une analyse de tendance fiable"
    ),
    "Material going concern uncertainty and sustained operating losses": (
        "Incertitude significative sur la continuité d'exploitation et pertes "
        "opérationnelles persistantes"
    ),
    "Limited historical period constrains trend identification and normalization": (
        "Période historique limitée, ce qui restreint l'identification des tendances "
        "et la normalisation"
    ),
    "Significant operating losses increase valuation uncertainty": (
        "Des pertes opérationnelles importantes augmentent l'incertitude de valorisation"
    ),
}


def _localize_cap_reason(reason: Optional[str], locale_key: str) -> Optional[str]:
    """Translate the English cap_reason into the active report locale."""
    if not reason or locale_key == "en":
        return reason
    if locale_key == "fr":
        return _EN_TO_FR_CAP_REASON_MAP.get(reason, reason)
    return _EN_TO_NL_CAP_REASON_MAP.get(reason, reason)


_NL_TO_EN_SIGNAL_MAP = {
    "Geen balansgegevens verstrekt": "No balance sheet data provided",
    "netto-schuld 0 verondersteld": "net debt assumed to be zero",
    (
        "werkkapitaal- en kasstroomcorrecties bij overdracht moeten "
        "afzonderlijk worden vastgesteld"
    ): ("working capital and cash flow adjustments at handover must be " "determined separately"),
    (
        "Geen genormaliseerde EBITDA-aanpassingen ingevoerd voor "
        "een eigenaar-geleide onderneming"
    ): "No normalised EBITDA adjustments entered for an owner-led business",
    (
        "Marktconforme eigenaarsvergoeding en eenmalige posten dienen handmatig "
        "te worden bevestigd vóór externe distributie"
    ): (
        "Market-rate owner compensation and one-time items must be manually "
        "confirmed before external distribution"
    ),
    "EBITDA-marge": "EBITDA margin",
    "ligt lager dan sectortypisch": "is lower than the industry typical",
    "ligt hoger dan sectortypisch": "is higher than the industry typical",
    "Bevestig de sectorclassificatie en de operationele context vóór externe "
    "distributie": (
        "Confirm the sector classification and operating context before external " "distribution"
    ),
}


def _translate_signal_to_en(nl_text: str) -> str:
    """Best-effort NL → EN translation for engine signals.

    Falls back to the NL text unchanged when no match is found — better to
    show a Dutch sentence than to drop the signal entirely.
    """
    out = nl_text
    for nl, en in _NL_TO_EN_SIGNAL_MAP.items():
        if nl in out:
            out = out.replace(nl, en)
    return out


_SIGNAL_TO_FR_MAP = {
    "No balance sheet data provided": "Aucune donnée de bilan fournie",
    "Geen balansgegevens verstrekt": "Aucune donnée de bilan fournie",
    "net debt assumed to be zero": "dette nette supposée nulle",
    "netto-schuld 0 verondersteld": "dette nette supposée nulle",
    ("working capital and cash flow adjustments at handover must be " "determined separately"): (
        "les ajustements de fonds de roulement et de flux de trésorerie au transfert "
        "doivent être déterminés séparément"
    ),
    (
        "werkkapitaal- en kasstroomcorrecties bij overdracht moeten afzonderlijk "
        "worden vastgesteld"
    ): (
        "les ajustements de fonds de roulement et de flux de trésorerie au transfert "
        "doivent être déterminés séparément"
    ),
    (
        "Formula basis metric aligned to EV/applied multiple because the transported "
        "metric diverged from the valuation output."
    ): (
        "La métrique de base de la formule a été alignée sur EV / multiple appliqué "
        "car la métrique transmise divergeait du résultat de valorisation."
    ),
    (
        "Basismetric voor de formule uitgelijnd op EV/toegepaste multiple omdat de "
        "meegegeven metric afweek van de waarderingsoutput."
    ): (
        "La métrique de base de la formule a été alignée sur EV / multiple appliqué "
        "car la métrique transmise divergeait du résultat de valorisation."
    ),
    "No normalised EBITDA adjustments entered for an owner-led business": (
        "Aucun ajustement d'EBITDA normalisé n'a été saisi pour une entreprise "
        "dirigée par son propriétaire"
    ),
    (
        "Geen genormaliseerde EBITDA-aanpassingen ingevoerd voor een "
        "eigenaar-geleide onderneming"
    ): (
        "Aucun ajustement d'EBITDA normalisé n'a été saisi pour une entreprise "
        "dirigée par son propriétaire"
    ),
    (
        "Market-rate owner compensation and one-time items must be manually "
        "confirmed before external distribution"
    ): (
        "La rémunération de marché du propriétaire et les éléments ponctuels doivent "
        "être confirmés manuellement avant toute diffusion externe"
    ),
    (
        "Marktconforme eigenaarsvergoeding en eenmalige posten dienen handmatig te "
        "worden bevestigd vóór externe distributie"
    ): (
        "La rémunération de marché du propriétaire et les éléments ponctuels doivent "
        "être confirmés manuellement avant toute diffusion externe"
    ),
    "EBITDA margin": "Marge EBITDA",
    "EBITDA-marge": "Marge EBITDA",
    "is lower than the industry typical": "est inférieure au niveau typique du secteur",
    "ligt lager dan sectortypisch": "est inférieure au niveau typique du secteur",
    "is higher than the industry typical": "est supérieure au niveau typique du secteur",
    "ligt hoger dan sectortypisch": "est supérieure au niveau typique du secteur",
    "Confirm the sector classification and operating context before external distribution": (
        "Confirmez la classification sectorielle et le contexte opérationnel avant "
        "toute diffusion externe"
    ),
    "Bevestig de sectorclassificatie en de operationele context vóór externe distributie": (
        "Confirmez la classification sectorielle et le contexte opérationnel avant "
        "toute diffusion externe"
    ),
}


def _translate_signal_to_fr(text: str) -> str:
    """Best-effort EN/NL → FR translation for banner signals."""
    out = text
    for source, fr in _SIGNAL_TO_FR_MAP.items():
        if source in out:
            out = out.replace(source, fr)
    return out


# Opening tag prefix — use for ``in html`` probes (class-spaced from attributes).
DEFENSIBILITY_BANNER_DIV_PREFIX = '<div class="upswitch-defensibility-banner"'


def _resolve_locale(locale: Optional[str]) -> str:
    """Normalise locale to a supported key. Falls back to ``nl``."""
    if not isinstance(locale, str):
        return "nl"
    key = locale.strip().lower().split("-", 1)[0]
    return key if key in _TEXTS else "nl"


ConfidenceCapInput = Union[Decimal, float, int, str, None]


def _coerce_confidence_cap(value: ConfidenceCapInput) -> Decimal:
    """Finite ratio in ``[0, 1]`` for banner percent lines.

    Accepts Decimals, floats, ints, numeric strings. Values above ``1.0`` up
    to ``100`` divide by 100 (``75`` → ``0.75``). Values barely above ``1.0``
    from float noise clamp to ``1``. ``> 100`` clamps to ``1``. Non-finite
    and garbage inputs become ``0``.
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        cap = value
    else:
        try:
            cap = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError, ArithmeticError):
            return Decimal("0")
    if not cap.is_finite():
        return Decimal("0")
    if cap < 0:
        return Decimal("0")
    # Ratio should be ≤ 1; tolerate float ULP overshoot before applying
    # “whole-number percent” heuristics (otherwise 1.0+ε would become ~1%).
    if cap > Decimal("1"):
        if cap <= Decimal("1.000001"):
            return Decimal("1")
        if cap <= Decimal("100"):
            cap = cap / Decimal("100")
        else:
            return Decimal("1")
    return cap


def build_defensibility_banner(
    *,
    classification_value: Optional[str],
    confidence_cap: ConfidenceCapInput = None,
    cap_reason: Optional[str],
    margin_warning: Optional[str] = None,
    engine_signals: Optional[Union[str, Iterable[str]]] = None,
    locale: str = "nl",
    is_full_report: bool = False,
    show_confidence_cap: bool = False,
) -> str:
    """Build the defensibility banner HTML.

    Args:
        classification_value: ``ReportClassification.value`` (e.g.
            "Valuation Analysis with Limitations"). May be ``None`` when
            the classifier short-circuited but engine signals still fired.
        confidence_cap: Ratio ``[0, 1]`` (or ``None``). Values ``> 1`` up to
            ``100`` are divided by 100 (percent-style payload). Values
            infinitesimally above ``1.0`` (float noise) clamp to ``1``.
        cap_reason: Human-readable cap rationale (NL or EN). When ``None``
            the locale-default ("beperkte scope" / "limited scope") is used.
        margin_warning: Optional EBITDA-margin-deviation line.
        engine_signals: Additional caveat lines (``str`` sequence). A single
            ``str`` counts as one line (not character-split). ``bytes`` items
            are decoded as UTF-8 (replace errors). Other non-string entries are
            skipped.
        locale: ``"nl"``, ``"en"`` or ``"fr"``. Unknown values fall back to NL.
        is_full_report: When True, the cap-line is skipped (only engine /
            margin signals carry weight). Three Towers Capital fires
            cap-line because it's LIMITED_SCOPE; a 4-year FULL_REPORT with
            severe margin deviation hides the cap line.
        show_confidence_cap: When False (default) the numeric confidence
            ceiling sentence ("Vertrouwensplafond: X%" / "Confidence
            ceiling: X%") is omitted. Client-facing reports suppress it: a
            bare engine-confidence percentage reads as doubt to a seller and
            adds nothing to the advisor↔client conversation. The scope /
            limitations language and the engine signals still carry the
            defensibility weight. Set True only for internal / QA banners.

    Returns:
        Self-contained HTML string. No CSS injected (the page CSS already
        declares ``.upswitch-defensibility-banner``).
    """
    L = _TEXTS[_resolve_locale(locale)]
    parts = [f"{DEFENSIBILITY_BANNER_DIV_PREFIX}>"]
    title = escape(L["title"], quote=False)
    parts.append(f'<span class="ud-title">{title}</span>')

    body_lines: list[str] = []
    if not is_full_report and classification_value:
        scope_label = L["scope_labels"].get(classification_value, classification_value)
        localized_reason = _localize_cap_reason(cap_reason, _resolve_locale(locale))
        reason = localized_reason or L["default_reason"]
        scope_text = L["scope_intro"].format(
            scope=escape(str(scope_label), quote=False),
            reason=escape(str(reason), quote=False),
        )
        if show_confidence_cap:
            cap_dec = _coerce_confidence_cap(confidence_cap)
            cap_pct = max(0, min(100, int(cap_dec * Decimal("100"))))
            cap_line = L["confidence_cap_line"].format(pct=cap_pct)
            body_lines.append(f"{scope_text}. {cap_line}")
        else:
            body_lines.append(f"{scope_text}.")

    if isinstance(margin_warning, str) and margin_warning.strip():
        body_lines.append(escape(L["translate_signal"](margin_warning.strip()), quote=False))

    if engine_signals is not None:
        seq: Iterable[str]
        if isinstance(engine_signals, str):
            seq = (engine_signals,)
        else:
            seq = engine_signals
        for s in seq:
            if isinstance(s, str) and s.strip():
                body_lines.append(escape(L["translate_signal"](s.strip()), quote=False))
            elif isinstance(s, (bytes, bytearray)):
                dec = bytes(s).decode("utf-8", errors="replace").strip()
                if dec:
                    body_lines.append(escape(L["translate_signal"](dec), quote=False))

    body_lines.append(escape(L["footer"], quote=False))
    parts.append('<span class="ud-body">' + " ".join(body_lines) + "</span>")
    parts.append("</div>")
    return "".join(parts)


def watermark_text(locale: str = "nl") -> str:
    """The diagonal watermark phrase. Uppercased per locale convention."""
    locale_key = _resolve_locale(locale)
    if locale_key == "en":
        return "INDICATIVE DRAFT ESTIMATE"
    if locale_key == "fr":
        return "ESTIMATION INDICATIVE PRÉLIMINAIRE"
    return "INDICATIEVE CONCEPTSCHATTING"


def watermark_footer(locale: str = "nl") -> str:
    """The thin footer line under the watermark."""
    locale_key = _resolve_locale(locale)
    if locale_key == "en":
        return (
            "Indicative estimate with limited scope &mdash; not intended "
            "for formal transaction or tax purposes without additional validation."
        )
    if locale_key == "fr":
        return (
            "Estimation indicative à portée limitée &mdash; non destinée à des "
            "fins transactionnelles ou fiscales formelles sans validation "
            "complémentaire."
        )
    return (
        "Indicatieve schatting met beperkte scope &mdash; niet bestemd "
        "voor formele transactie- of fiscale doeleinden zonder aanvullende validatie."
    )
