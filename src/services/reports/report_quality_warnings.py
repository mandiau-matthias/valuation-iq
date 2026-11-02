"""Report quality-warning and method-substitution context helpers."""

from collections.abc import Mapping, Sequence
from typing import Protocol

from src.services.reports.protocol_adapter import _attr, _unwrap

JsonMap = dict[str, object]


class HighSeverityTranslations(Protocol):
    high_severity_callout_lead_singular: str
    high_severity_callout_lead_plural: str


class QualityLevelTranslations(Protocol):
    exec_indicative_label: str
    data_quality_band_high: str
    data_quality_band_medium: str
    data_quality_band_low: str
    data_quality_band_critical: str


def _as_json_map(value: object) -> JsonMap | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def format_high_severity_callout_lead(
    t: HighSeverityTranslations,
    warnings: Sequence[Mapping[str, object]],
) -> str:
    """Render the localized lead sentence for the Page 1 high-severity callout."""
    count = len(warnings)
    if count == 0:
        return ""
    if count == 1:
        return t.high_severity_callout_lead_singular
    return t.high_severity_callout_lead_plural.format(count=count)


def has_integrity_warnings(warnings: Sequence[Mapping[str, object]] | None) -> bool:
    """True iff at least one warning is a must-disclose integrity flag."""
    from src.domain.report_integrity import is_integrity_warning

    return any(is_integrity_warning(w) for w in (warnings or []))


def format_methodology_for_disclosure(methodology: object, locale: str) -> str:
    key = str(methodology or "").strip().upper()
    labels_en = {
        "ASSET_BASED": "Adjusted NAV (Asset-Based)",
        "MULTIPLES": "Market Multiples",
        "DCF": "Discounted Cash Flow (DCF)",
        "HYBRID": "Hybrid",
        "SDE": "Seller's Discretionary Earnings (SDE)",
        "REAL_ESTATE_YIELD": "Real-estate yield (rent ÷ cap-rate)",
    }
    labels_nl = {
        "ASSET_BASED": "Gecorrigeerde NAV (intrinsieke waarde)",
        "MULTIPLES": "Marktmultiples",
        "DCF": "Discounted Cash Flow (DCF)",
        "HYBRID": "Hybride",
        "SDE": "SDE-methode (discretionaire winst)",
        "REAL_ESTATE_YIELD": "Vastgoed yield (huur ÷ cap-rate)",
    }
    labels_fr = {
        "ASSET_BASED": "VNI ajustée (approche patrimoniale)",
        "MULTIPLES": "Multiples de marché",
        "DCF": "Discounted Cash Flow (DCF)",
        "HYBRID": "Hybride",
        "SDE": "Bénéfice discrétionnaire du vendeur (SDE)",
        "REAL_ESTATE_YIELD": "Rendement immobilier (loyer ÷ cap-rate)",
    }
    loc = str(locale or "nl").lower()
    if loc.startswith("nl"):
        labels = labels_nl
    elif loc.startswith("fr"):
        labels = labels_fr
    else:
        labels = labels_en
    return labels.get(key) or str(methodology or "Unknown")


def _substitution_payload_from_response(response: object | None) -> JsonMap | None:
    response_payload: object = _unwrap(_attr(response, "methodology_substitution", None))
    return _as_json_map(response_payload)


def _substitution_payload_from_warning(warning: Mapping[str, object]) -> JsonMap | None:
    if warning.get("type") != "method_substitution":
        return None
    details_payload: object = _unwrap(warning.get("details"))
    details = _as_json_map(details_payload)
    if details is None:
        return None
    nested = details.get("substitution")
    nested_map = _as_json_map(nested)
    if nested_map is not None:
        return nested_map
    return {
        "requested_methodology": details.get("requested_method"),
        "executed_methodology": details.get("executed_method"),
        "reason": details.get("engine_reason"),
        "reason_code": details.get("reason_code"),
        "missing_fields": details.get("missing_fields") or [],
        "remediation": details.get("remediation"),
    }


def _substitution_payload_from_warnings(
    high_severity_warnings: Sequence[Mapping[str, object]],
) -> JsonMap | None:
    for warning in high_severity_warnings or []:
        substitution_payload = _substitution_payload_from_warning(warning)
        if substitution_payload is not None:
            return substitution_payload
    return None


def _resolve_substitution_payload(
    response: object | None,
    high_severity_warnings: Sequence[Mapping[str, object]],
) -> JsonMap | None:
    return _substitution_payload_from_response(response) or _substitution_payload_from_warnings(
        high_severity_warnings
    )


def _substitution_methods(substitution_payload: JsonMap) -> tuple[object, object] | None:
    requested = substitution_payload.get("requested_methodology") or substitution_payload.get(
        "requested_method"
    )
    executed = substitution_payload.get("executed_methodology") or substitution_payload.get(
        "executed_method"
    )
    if not requested or not executed:
        return None
    return requested, executed


def _substitution_missing_fields(substitution_payload: JsonMap) -> list[object]:
    missing_fields = substitution_payload.get("missing_fields")
    return missing_fields if isinstance(missing_fields, list) else []


def _strip_false_hybrid_preface(reason: object, requested: object) -> object:
    requested_upper = str(requested).upper()
    if not (
        isinstance(reason, str)
        and "HYBRID methodology was requested" in reason
        and requested_upper != "HYBRID"
    ):
        return reason
    stripped = reason.split("HYBRID methodology was requested, but DCF was excluded.", 1)
    if len(stripped) != 2:
        return reason
    return (stripped[0].rstrip() + " " + stripped[1].lstrip()).strip()


def _locale_flags(locale: str) -> tuple[bool, bool]:
    normalized_locale = str(locale or "nl").lower()
    return normalized_locale.startswith("nl"), normalized_locale.startswith("fr")


def _english_legacy_standards_reason(reason: str) -> str:
    legacy_standards_claim = (
        "This approach is more reliable for small businesses and aligns with "
        "Big "
        "4 and NA"
        "CVA valuation standards."
    )
    return reason.replace(
        legacy_standards_claim,
        "This approach is more reliable for small businesses and aligns with commonly applied SME valuation practice for indicative M&A valuations.",
    )


def _localized_substitution_reason(reason: object, locale: str) -> object:
    is_nl, is_fr = _locale_flags(locale)
    if not isinstance(reason, str) or not reason.strip():
        return reason
    if is_nl:
        return _localise_substitution_reason_to_nl(reason)
    if is_fr:
        return _localise_substitution_reason_to_fr(reason)
    return _english_legacy_standards_reason(reason)


def _is_engineering_decision(reason_code: object) -> bool:
    return reason_code in (
        "DCF_EXCLUDED",
        "DCF_INFEASIBLE",
        "ASSET_ROUTED",
        "YIELD_ROUTED",
    )


def _method_substitution_title_and_lead(reason_code: object, locale: str) -> tuple[str, str]:
    is_nl, is_fr = _locale_flags(locale)
    if _is_engineering_decision(reason_code):
        if is_nl:
            return (
                "Methodologie aangepast aan dit profiel",
                (
                    "De waarderingsmethode is afgestemd op het bedrijfsprofiel. "
                    "Hieronder staat welke methode is uitgevoerd en waarom."
                ),
            )
        if is_fr:
            return (
                "Méthodologie adaptée à ce profil",
                (
                    "La méthodologie de valorisation a été adaptée au profil de l'entreprise. "
                    "Ci-dessous : quelle méthode a été appliquée et pourquoi."
                ),
            )
        return (
            "Methodology tuned to this profile",
            (
                "The valuation methodology was tuned to the business profile. "
                "Below: which method ran and why."
            ),
        )
    if is_nl:
        return (
            "Methodologiewijziging",
            "De gevraagde waarderingsmethode kon niet worden uitgevoerd.",
        )
    if is_fr:
        return (
            "Changement de méthodologie",
            "La méthodologie de valorisation demandée n'a pas pu être appliquée.",
        )
    return (
        "Methodology substitution",
        "The requested valuation methodology could not be executed.",
    )


def extract_method_substitution_disclosure(
    response: object | None,
    high_severity_warnings: Sequence[Mapping[str, object]],
    locale: str,
) -> JsonMap | None:
    substitution_payload = _resolve_substitution_payload(response, high_severity_warnings)
    if substitution_payload is None:
        return None

    methods = _substitution_methods(substitution_payload)
    if methods is None:
        return None
    requested, executed = methods

    reason = substitution_payload.get("reason") or substitution_payload.get("engine_reason")
    missing_fields = _substitution_missing_fields(substitution_payload)
    reason = _strip_false_hybrid_preface(reason, requested)
    reason = _localized_substitution_reason(reason, locale)

    reason_code = substitution_payload.get("reason_code")
    title, lead = _method_substitution_title_and_lead(reason_code, locale)

    return {
        "requested_method": str(requested),
        "executed_method": str(executed),
        "requested_method_display": format_methodology_for_disclosure(requested, locale),
        "executed_method_display": format_methodology_for_disclosure(executed, locale),
        "reason": reason,
        "reason_code": reason_code,
        "missing_fields": missing_fields,
        "remediation": substitution_payload.get("remediation"),
        "title": title,
        "lead": lead,
    }


# Pattern-driven NL translation of the engine's English substitution rationales.
# Order matters — the first pattern that matches wins.  Pattern → (regex,
# Dutch template) where {currency} is the matched euro value.  Patterns are
# matched against the *original* English reason; if no pattern fits the
# original string is returned unchanged.
import re as _re

_SUBSTITUTION_REASON_NL_PATTERNS: tuple[tuple[_re.Pattern[str], str], ...] = (
    (
        _re.compile(
            r"Revenue\s+(€[\d,]+)\s+below\s+€?5M\s+threshold\s+with\s+standard\s+growth\s+profile.*?"
            r"(?:per Koller,?\s*Goedhart\s*&?\s*Wessels\s*2020[,\s]*Trugman\s*2017)?\)?\.\s*"
            r"We used Market Multiples methodology only\..*?"
            r"This approach is more reliable for small businesses and aligns with Big\s*4 and NA\s*CVA valuation standards\.?",
            _re.IGNORECASE | _re.DOTALL,
        ),
        (
            "Omzet {currency} ligt onder de DCF-drempel van €5M bij een standaard groeiprofiel; "
            "voor deze omvang zijn marktmultiples nauwkeuriger (Koller, Goedhart & Wessels 2020, "
            "Trugman 2017). Daarom is alleen de marktbenadering toegepast — dit sluit aan bij "
            "gangbare MKB-waarderingspraktijk voor indicatieve M&A-waarderingen."
        ),
    ),
    (
        _re.compile(
            r"Revenue\s+(€[\d,]+)\s+below\s+€?5M\s+threshold",
            _re.IGNORECASE,
        ),
        "Omzet {currency} ligt onder de €5M-drempel voor DCF.",
    ),
    (
        _re.compile(
            r"NAV unavailable.*?fall(?:ing|s)?\s+back to multiples",
            _re.IGNORECASE | _re.DOTALL,
        ),
        "Gecorrigeerde NAV-gegevens onvoldoende; daarom is teruggevallen op marktmultiples.",
    ),
    (
        # Panel minor (Case D1): the asset-heavy substitution rationale leaked the
        # English engine reason into the NL "Reden:" line. The English text remains
        # the canonical audit/Sentry key; only the reader-facing render localises.
        _re.compile(
            r"Asset-heavy balance sheet detected.*?"
            r"value flows from the underlying NAV rather than operating multiples\.?",
            _re.IGNORECASE | _re.DOTALL,
        ),
        (
            "Activumzware balans gedetecteerd: het boekhoudkundig eigen vermogen bedraagt "
            "minstens 5× de EBITDA van het lopende jaar en de vaste activa overschrijden 60% "
            "van de totale activa. Daarom is de substantiewaardering (NAV) toegepast — de waarde "
            "vloeit voort uit de onderliggende NAV in plaats van operationele multiples."
        ),
    ),
)


def _localise_substitution_reason_to_nl(reason: str) -> str:
    """Translate well-known English engine-rationale strings to Dutch.

    Used for both the ``method_substitution_disclosure.reason`` callout on
    the executive summary AND the ``adaptive_methodology_justification``
    paragraph on the Upswitch Adaptive page — the engine emits the same
    template in both fields, so a single pattern-driven translator covers
    both leaks.

    Returns the reason unchanged if no pattern matches — so a brand-new
    rationale emitted by the engine still surfaces (in English), instead of
    being silently dropped.
    """
    for pattern, nl_template in _SUBSTITUTION_REASON_NL_PATTERNS:
        match = pattern.search(reason)
        if match:
            # The captured euro value carries the upstream English comma grouping
            # ("€2,130,092"); render it nl-BE (period thousands) for the Dutch reason.
            kwargs = {"currency": match.group(1).replace(",", ".")} if match.groups() else {}
            try:
                return nl_template.format(**kwargs)
            except (KeyError, IndexError):  # pragma: no cover — template/regex drift
                return nl_template
    return reason


# French mirror of ``_SUBSTITUTION_REASON_NL_PATTERNS``. Same English-regex keys
# (the engine writes English into the audit trail regardless of report locale),
# mapped to French reader-facing copy. Keeps FR reports free of leaked English/
# Dutch rationale strings.
_SUBSTITUTION_REASON_FR_PATTERNS: tuple[tuple[_re.Pattern[str], str], ...] = (
    (
        _re.compile(
            r"Revenue\s+(€[\d,]+)\s+below\s+€?5M\s+threshold\s+with\s+standard\s+growth\s+profile.*?"
            r"(?:per Koller,?\s*Goedhart\s*&?\s*Wessels\s*2020[,\s]*Trugman\s*2017)?\)?\.\s*"
            r"We used Market Multiples methodology only\..*?"
            r"This approach is more reliable for small businesses and aligns with Big\s*4 and NA\s*CVA valuation standards\.?",
            _re.IGNORECASE | _re.DOTALL,
        ),
        (
            "Le chiffre d'affaires {currency} est inférieur au seuil DCF de €5M avec un profil de "
            "croissance standard ; pour cette taille, les multiples de marché sont plus fiables "
            "(Koller, Goedhart & Wessels 2020, Trugman 2017). Seule l'approche de marché a donc été "
            "appliquée — conforme à la pratique courante de valorisation des PME pour des estimations "
            "indicatives en M&A."
        ),
    ),
    (
        _re.compile(
            r"Revenue\s+(€[\d,]+)\s+below\s+€?5M\s+threshold",
            _re.IGNORECASE,
        ),
        "Le chiffre d'affaires {currency} est inférieur au seuil DCF de €5M.",
    ),
    (
        _re.compile(
            r"NAV unavailable.*?fall(?:ing|s)?\s+back to multiples",
            _re.IGNORECASE | _re.DOTALL,
        ),
        "Données de NAV ajustée insuffisantes ; repli sur les multiples de marché.",
    ),
    (
        _re.compile(
            r"Asset-heavy balance sheet detected.*?"
            r"value flows from the underlying NAV rather than operating multiples\.?",
            _re.IGNORECASE | _re.DOTALL,
        ),
        (
            "Bilan à forte intensité d'actifs détecté : les capitaux propres comptables représentent "
            "au moins 5× l'EBITDA de l'exercice en cours et les actifs immobilisés dépassent 60% du "
            "total du bilan. La valorisation par l'actif (NAV) a donc été appliquée — la valeur découle "
            "de la NAV sous-jacente plutôt que des multiples opérationnels."
        ),
    ),
    (
        # Real-estate yield route — the engine hardcodes this rationale in DUTCH
        # (methodology_determiner.py), so a FR report leaks Dutch without this.
        _re.compile(
            r"Vastgoedvennootschap gedetecteerd.*?" r"niet operationele EBITDA-multiples\.?",
            _re.IGNORECASE | _re.DOTALL,
        ),
        (
            "Société immobilière détectée. Nous appliquons la méthode de capitalisation des revenus "
            "— le loyer net durable divisé par un taux de capitalisation conforme au marché, avec la "
            "NAV comptable comme plancher — car pour une société immobilière le rendement locatif est "
            "le principal facteur de valeur, et non les multiples d'EBITDA opérationnels."
        ),
    ),
    (
        # Real-estate yield fallback (English, valuation_executor.py).
        _re.compile(
            r"Real-Estate Yield methodology was selected, but income-capitalisation\s+"
            r"data was insufficient\.\s*Falling back to Asset-Based methodology\.?",
            _re.IGNORECASE | _re.DOTALL,
        ),
        (
            "La méthode du rendement immobilier a été retenue, mais les données de capitalisation des "
            "revenus étaient insuffisantes. Repli sur la méthode par l'actif (NAV)."
        ),
    ),
)


def _localise_substitution_reason_to_fr(reason: str) -> str:
    """Translate well-known English engine-rationale strings to French.

    Mirrors :func:`_localise_substitution_reason_to_nl`. Returns the reason
    unchanged when no pattern matches, so a brand-new rationale still surfaces
    instead of being silently dropped.
    """
    for pattern, fr_template in _SUBSTITUTION_REASON_FR_PATTERNS:
        match = pattern.search(reason)
        if match:
            # Render the captured euro value fr-BE (space thousands) — but only for
            # templates that actually consume {currency}; some patterns capture a
            # non-currency group (or nothing) and their template takes no kwargs.
            kwargs = {}
            if match.groups() and "{currency}" in fr_template:
                kwargs = {"currency": (match.group(1) or "").replace(",", " ")}
            try:
                return fr_template.format(**kwargs)
            except (KeyError, IndexError):  # pragma: no cover — template/regex drift
                return fr_template
    return reason


def extract_high_severity_warnings(
    response: object | None,
    step_data: Mapping[str, object] | None,
    extra_warnings: Sequence[Mapping[str, object]] | None = None,
) -> list[JsonMap]:
    """Surface only high-severity warnings for the Page 1 callout."""
    candidates: list[object] = []
    try:
        response_warnings = getattr(response, "data_quality_warnings", None) if response else None
        if isinstance(response_warnings, list):
            candidates.extend(response_warnings)
    except Exception:
        pass

    if not candidates and isinstance(step_data, dict):
        legacy = step_data.get("quality_warnings")
        if isinstance(legacy, list):
            candidates.extend(legacy)

    if extra_warnings:
        candidates.extend(extra_warnings)

    result: list[JsonMap] = []
    seen: set[tuple[object, object]] = set()
    for warning in candidates:
        warning_map = _as_json_map(warning)
        if warning_map is None:
            continue
        severity = str(warning_map.get("severity") or "").lower()
        if severity != "high":
            continue
        key = (warning_map.get("type"), warning_map.get("message"))
        if key in seen:
            continue
        seen.add(key)
        result.append(warning_map)
        if len(result) >= 5:
            break
    return result


def translate_quality_warnings(
    warnings: Sequence[object] | None,
    locale: str = "nl",
) -> list[JsonMap]:
    """Translate raw quality warning payloads to the report locale.

    Accepts both dict warnings (``{"code": ..., "message": ...}``) and bare
    strings.  String warnings used to bypass the translator entirely and the
    NL report ended up showing the raw English on the disclaimers page
    ("Datakwaliteit Opmerkingen: Multi-year data not available").  Wrapping
    strings into a synthetic dict before calling the translator lets the
    catalog's message-text fallback localise them too.
    """
    from src.services.infrastructure.translations import translate_quality_warning

    result: list[JsonMap] = []
    for warning in warnings or []:
        warning_map = _as_json_map(warning)
        if warning_map is None:
            warning_map = {"message": str(warning)}
        result.append(translate_quality_warning(warning_map, locale))
    return result


def localize_warnings(
    warnings: Sequence[Mapping[str, object]] | None,
    t: object,
) -> list[JsonMap]:
    """Apply typed warning translation keys with an already-resolved translation bundle."""
    from src.services.infrastructure.warning_translations import (
        localize_typed_data_quality_warnings,
    )

    return [
        entry_map
        for entry in localize_typed_data_quality_warnings(warnings, t)
        if (entry_map := _as_json_map(entry)) is not None
    ]


def map_quality_level_display(raw: str | None, t: QualityLevelTranslations) -> str:
    """Map raw quality levels to locale-aware display labels."""
    if not raw:
        return t.exec_indicative_label
    upper = str(raw).upper()
    if upper == "HIGH":
        return t.data_quality_band_high
    if upper == "MEDIUM":
        return t.data_quality_band_medium
    if upper == "LOW":
        return t.data_quality_band_low
    if upper == "CRITICAL":
        return t.data_quality_band_critical
    return raw
