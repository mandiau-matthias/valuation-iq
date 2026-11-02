"""Localized engine-signal composition for the defensibility classifier."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Protocol

from src.config.countries import country_confidence_tier, currency_for_country, is_non_eur_country
from src.services.defensibility.methodology import Methodology
from src.services.infrastructure.translations import normalize_report_locale


class DecimalParser(Protocol):
    """Converter dependency injected by classifier for compatibility tests."""

    def __call__(self, value: object, default: Decimal = Decimal("0")) -> Decimal:
        """Return a Decimal value or the provided default."""


class EngineSignalLogger(Protocol):
    """Small logger protocol; only the exception path needs injection."""

    def exception(self, msg: str, *args: object, **kwargs: object) -> None:
        """Log an exception with optional structured context."""


_ENGINE_WARNING_NL_BY_KEY: dict[str, str] = {
    "phantom_bridge_suppressed": (
        "EV→Equity-brug onderdrukt omdat de verkoper geen balansgegevens "
        "heeft verstrekt; het rapport toont EV ≡ Equity."
    ),
}


@dataclass(frozen=True)
class _SignalLocale:
    """Normalized locale switch for defensive message rendering."""

    loc: str

    @classmethod
    def from_raw(cls, locale: str) -> "_SignalLocale":
        return cls(loc=normalize_report_locale(locale))

    def choose(self, *, en: str, fr: str, nl: str) -> str:
        if self.loc == "en":
            return en
        if self.loc == "fr":
            return fr
        return nl


_OWNER_NORMALIZATION_METHODS = {
    Methodology.MULTIPLES,
    Methodology.DCF,
    Methodology.HYBRID,
    Methodology.SDE,
    Methodology.UNKNOWN,
}

_OWNER_PROFILE_METHODS = {
    Methodology.MULTIPLES,
    Methodology.HYBRID,
    Methodology.SDE,
    Methodology.UNKNOWN,
}


def _country_confidence_signal(country_code: Optional[str], locale: str) -> Optional[str]:
    """Render a defensibility line for non-BE/NL countries."""
    if not isinstance(country_code, str) or not country_code.strip():
        return None
    tier = country_confidence_tier(country_code)
    if tier == "high":
        return None
    loc = normalize_report_locale(locale)
    en = loc == "en"
    fr = loc == "fr"
    code = country_code.strip().upper()
    currency = currency_for_country(code)
    non_eur_clause = ""
    if is_non_eur_country(code):
        if en:
            non_eur_clause = (
                f" Statutory currency is {currency}; this report is "
                "expressed in EUR for engine consistency."
            )
        elif fr:
            non_eur_clause = (
                f" La devise légale est {currency}; ce rapport est exprimé "
                "en EUR pour cohérence avec le moteur."
            )
        else:
            non_eur_clause = (
                f" Wettelijke valuta is {currency}; dit rapport is voor "
                "consistentie van de motor uitgedrukt in EUR."
            )
    if tier == "medium":
        if en:
            return (
                f"Country: {code}. Engine applies the explicit "
                f"per-country tax rate; SME-rate refinements specific to "
                "Belgium are not modelled for this jurisdiction. Have a "
                "local accountant validate before external use."
                f"{non_eur_clause}"
            )
        if fr:
            return (
                f"Pays : {code}. Le moteur applique le taux d'impôt explicite "
                "du pays; les affinages de taux PME propres à la Belgique ne "
                "sont pas modélisés pour cette juridiction. Faites valider par "
                f"un comptable local avant usage externe.{non_eur_clause}"
            )
        return (
            f"Land: {code}. De motor gebruikt het expliciete "
            "landenbelastingtarief; SME-regimes specifiek voor België "
            "worden voor dit land niet gemodelleerd. Laat valideren door "
            "een lokale accountant vóór extern gebruik."
            f"{non_eur_clause}"
        )
    if en:
        return (
            f"Country: {code}. Engine uses statutory tax-rate fallback "
            "and BENELUX-shaped peer benchmarks. This report is "
            "preliminary for the non-Benelux jurisdiction; an accountant "
            "review is required before stakeholder distribution."
            f"{non_eur_clause}"
        )
    if fr:
        return (
            f"Pays : {code}. Le moteur utilise un taux d'impôt légal de "
            "repli et des benchmarks de pairs de forme BENELUX. Ce rapport "
            "est préliminaire pour la juridiction non-Benelux; une revue par "
            f"un comptable est requise avant diffusion aux parties prenantes.{non_eur_clause}"
        )
    return (
        f"Land: {code}. De motor gebruikt het wettelijke "
        "belastingtarief als terugval en BENELUX-georiënteerde peer-"
        "benchmarks. Dit rapport is voorlopig voor de niet-Benelux-"
        "jurisdictie; beoordeling door een accountant is vereist vóór "
        "verdeling aan stakeholders."
        f"{non_eur_clause}"
    )


def _metadata(valuation_data: dict) -> dict:
    metadata = valuation_data.get("metadata") or {}
    return metadata if isinstance(metadata, dict) else {}


def _country_code_from_payload(valuation_data: dict) -> Optional[str]:
    country_raw = valuation_data.get("country_code")
    if country_raw is None:
        country_raw = _metadata(valuation_data).get("country_code")
    return country_raw if isinstance(country_raw, str) else None


def _balance_sheet_is_meaningful(
    valuation_data: dict,
    *,
    safe_decimal: DecimalParser,
) -> bool:
    cur = valuation_data.get("current_year_data") or {}
    cash_raw = cur.get("cash") if isinstance(cur, dict) else None
    debt_raw = cur.get("total_debt") if isinstance(cur, dict) else None
    cash_val = safe_decimal(cash_raw) if cash_raw is not None else None
    debt_val = safe_decimal(debt_raw) if debt_raw is not None else None
    return bool(_metadata(valuation_data).get("balance_sheet_provided")) or (
        (cash_val is not None and abs(cash_val) > Decimal("0"))
        or (debt_val is not None and abs(debt_val) > Decimal("0"))
    )


def _balance_sheet_missing_message(locale: _SignalLocale) -> str:
    return locale.choose(
        en=(
            "No balance sheet data provided — net debt assumed to "
            "be zero; working capital and cash flow adjustments at "
            "handover must be determined separately."
        ),
        fr=(
            "Aucune donnée de bilan fournie — dette nette supposée "
            "nulle; les ajustements de fonds de roulement et de flux "
            "de trésorerie au transfert doivent être déterminés "
            "séparément."
        ),
        nl=(
            "Geen balansgegevens verstrekt — netto-schuld 0 verondersteld; "
            "werkkapitaal- en kasstroomcorrecties bij overdracht moeten "
            "afzonderlijk worden vastgesteld."
        ),
    )


def _append_balance_sheet_signal(
    msgs: list[str],
    valuation_data: dict,
    methodology: Methodology,
    locale: _SignalLocale,
    *,
    safe_decimal: DecimalParser,
) -> None:
    if methodology == Methodology.STARTUP:
        return
    if not _balance_sheet_is_meaningful(valuation_data, safe_decimal=safe_decimal):
        msgs.append(_balance_sheet_missing_message(locale))


def _owner_employee_counts(
    valuation_data: dict,
    *,
    safe_decimal: DecimalParser,
) -> tuple[Decimal, Decimal]:
    metadata = _metadata(valuation_data)
    owners = safe_decimal(valuation_data.get("owner_managers") or metadata.get("owner_managers"))
    ftes = safe_decimal(valuation_data.get("total_employees") or metadata.get("total_employees"))
    return owners, ftes


def _is_owner_led_small_business(
    valuation_data: dict,
    *,
    safe_decimal: DecimalParser,
) -> bool:
    owners, ftes = _owner_employee_counts(valuation_data, safe_decimal=safe_decimal)
    return owners >= Decimal("1") and Decimal("0") < ftes <= Decimal("10")


def _owner_normalization_missing_message(locale: _SignalLocale) -> str:
    return locale.choose(
        en=(
            "No normalised EBITDA adjustments entered for an "
            "owner-led business. Market-rate owner compensation "
            "and one-time items must be manually confirmed before "
            "external distribution."
        ),
        fr=(
            "Aucun ajustement d'EBITDA normalisé n'a été saisi "
            "pour une entreprise dirigée par son propriétaire. "
            "La rémunération de marché du propriétaire et les "
            "éléments ponctuels doivent être confirmés manuellement "
            "avant toute diffusion externe."
        ),
        nl=(
            "Geen genormaliseerde EBITDA-aanpassingen ingevoerd voor "
            "een eigenaar-geleide onderneming. Marktconforme "
            "eigenaarsvergoeding en eenmalige posten dienen handmatig "
            "te worden bevestigd vóór externe distributie."
        ),
    )


def _append_owner_normalization_signal(
    msgs: list[str],
    valuation_data: dict,
    methodology: Methodology,
    locale: _SignalLocale,
    *,
    safe_decimal: DecimalParser,
) -> None:
    if methodology not in _OWNER_NORMALIZATION_METHODS:
        return
    if safe_decimal(valuation_data.get("total_adjustments")) != Decimal("0"):
        return
    if _is_owner_led_small_business(valuation_data, safe_decimal=safe_decimal):
        msgs.append(_owner_normalization_missing_message(locale))


def _engine_warning_entries(valuation_data: dict) -> list:
    eng_warnings = valuation_data.get("engine_warnings")
    if not isinstance(eng_warnings, list):
        dr = valuation_data.get("detailed_results")
        eng_warnings = dr.get("engine_warnings") if isinstance(dr, dict) else None
    return eng_warnings if isinstance(eng_warnings, list) else []


def _localized_engine_warning(warning: dict, locale: _SignalLocale) -> Optional[str]:
    key = warning.get("key") if isinstance(warning.get("key"), str) else ""
    msg_en = warning.get("message") or warning.get("text") or ""
    msg_nl_inline = (
        warning.get("message_nl") if isinstance(warning.get("message_nl"), str) else None
    )
    msg_fr_inline = (
        warning.get("message_fr") if isinstance(warning.get("message_fr"), str) else None
    )
    if locale.loc == "en":
        msg = msg_en
    elif locale.loc == "fr":
        msg = msg_fr_inline or msg_en
    else:
        msg = msg_nl_inline or _ENGINE_WARNING_NL_BY_KEY.get(key) or msg_en
    return msg.strip() if isinstance(msg, str) and msg.strip() else None


def _append_engine_warnings(
    msgs: list[str],
    valuation_data: dict,
    locale: _SignalLocale,
) -> None:
    for warning in _engine_warning_entries(valuation_data):
        if not isinstance(warning, dict):
            continue
        msg = _localized_engine_warning(warning, locale)
        if msg:
            msgs.append(msg)


def _owner_dependency_cap_line(
    *,
    risk_level: str,
    cap_pct: int,
    raw_pct: int,
    locale: _SignalLocale,
) -> str:
    return locale.choose(
        en=(
            f"Owner Profiling: {risk_level} dependency, "
            f"{cap_pct}% MVP cap applied (uncapped engine "
            f"signal {raw_pct}%). Validate with an "
            "advisor before external use."
        ),
        fr=(
            f"Owner Profiling : dépendance {risk_level}, "
            f"plafond MVP de {cap_pct} % appliqué (signal "
            f"moteur non plafonné {raw_pct} %). Faites "
            "valider par un conseiller avant usage externe."
        ),
        nl=(
            f"Owner Profiling: {risk_level} afhankelijkheid, "
            f"MVP-cap van {cap_pct}% toegepast (ongekapt "
            f"motorsignaal {raw_pct}%). Laat valideren door "
            "een adviseur vóór extern gebruik."
        ),
    )


def _owner_dependency_cap_message(
    valuation_data: dict,
    locale: _SignalLocale,
    *,
    safe_decimal: DecimalParser,
) -> Optional[str]:
    odr = valuation_data.get("owner_dependency_result")
    if not isinstance(odr, dict):
        return None
    try:
        applied = odr.get("valuation_adjustment")
        raw = odr.get("raw_adjustment")
        if applied is None or raw is None:
            return None
        applied_dec = safe_decimal(applied)
        raw_dec = safe_decimal(raw)
        if raw_dec >= applied_dec:
            return None
        risk_level = str(odr.get("risk_level") or "").strip().upper() or "HIGH"
        cap_pct = abs(int(round(float(applied_dec) * 100)))
        raw_pct = abs(int(round(float(raw_dec) * 100)))
        return _owner_dependency_cap_line(
            risk_level=risk_level,
            cap_pct=cap_pct,
            raw_pct=raw_pct,
            locale=locale,
        )
    except (TypeError, ValueError, ArithmeticError):
        return None


def _owner_profile_missing_message(locale: _SignalLocale) -> str:
    return locale.choose(
        en=(
            "Owner Profile not completed — equity adjustment "
            "defaulted to 0%; transferability risk has not been "
            "quantified for this report."
        ),
        fr=(
            "Profil propriétaire non complété — l'ajustement des "
            "capitaux propres est resté à 0 %; le risque de "
            "transférabilité n'a pas été quantifié pour ce rapport."
        ),
        nl=(
            "Eigenaarsprofiel niet ingevuld — aandelenwaarde-aanpassing "
            "ingesteld op 0%; overdraagbaarheidsrisico is voor "
            "dit rapport niet gekwantificeerd."
        ),
    )


def _append_owner_profile_signal(
    msgs: list[str],
    valuation_data: dict,
    methodology: Methodology,
    locale: _SignalLocale,
    *,
    safe_decimal: DecimalParser,
) -> None:
    cap_message = _owner_dependency_cap_message(
        valuation_data,
        locale,
        safe_decimal=safe_decimal,
    )
    if cap_message:
        msgs.append(cap_message)
        return
    if isinstance(valuation_data.get("owner_dependency_result"), dict):
        return
    if methodology not in _OWNER_PROFILE_METHODS:
        return
    if _is_owner_led_small_business(valuation_data, safe_decimal=safe_decimal):
        msgs.append(_owner_profile_missing_message(locale))


def _methodology_label(methodology: Methodology) -> str:
    return methodology.value if hasattr(methodology, "value") else str(methodology)


def _engine_integrity_error_message(locale: _SignalLocale) -> str:
    return locale.choose(
        en=(
            "Engine integrity signals could not be fully evaluated for "
            "this report. Engineering has been alerted; the headline "
            "number remains valid."
        ),
        fr=(
            "Les signaux d'intégrité du moteur n'ont pas pu être "
            "entièrement évalués pour ce rapport. Engineering a été "
            "alerté; le chiffre principal reste valide."
        ),
        nl=(
            "Motor-integriteitssignalen konden voor dit rapport niet "
            "volledig worden geëvalueerd. Engineering is op de hoogte "
            "gebracht; het hoofdgetal blijft geldig."
        ),
    )


def _append_extraction_failure(
    msgs: list[str],
    *,
    exc: Exception,
    methodology: Methodology,
    locale: str,
    logger: EngineSignalLogger,
) -> None:
    logger.exception(
        "engine_signals extraction failed mid-pipeline",
        extra={
            "error_type": type(exc).__name__,
            "error": str(exc)[:200],
            "methodology": _methodology_label(methodology),
            "msgs_collected": len(msgs),
            "locale": locale,
        },
    )
    msgs.append(_engine_integrity_error_message(_SignalLocale.from_raw(locale)))


def extract_engine_signals(
    valuation_data: object,
    methodology: Methodology,
    locale: str,
    *,
    safe_decimal: DecimalParser,
    logger: EngineSignalLogger,
) -> list[str]:
    """Pull per-report defensibility messages directly from valuation data."""
    if not isinstance(valuation_data, dict):
        return []
    msgs: list[str] = []
    signal_locale = _SignalLocale.from_raw(locale)

    country_signal = _country_confidence_signal(
        _country_code_from_payload(valuation_data),
        locale=locale,
    )
    if country_signal:
        msgs.append(country_signal)

    try:
        _append_balance_sheet_signal(
            msgs,
            valuation_data,
            methodology,
            signal_locale,
            safe_decimal=safe_decimal,
        )
        _append_owner_normalization_signal(
            msgs,
            valuation_data,
            methodology,
            signal_locale,
            safe_decimal=safe_decimal,
        )
        _append_engine_warnings(msgs, valuation_data, signal_locale)
        _append_owner_profile_signal(
            msgs,
            valuation_data,
            methodology,
            signal_locale,
            safe_decimal=safe_decimal,
        )
    except Exception as exc:
        _append_extraction_failure(
            msgs,
            exc=exc,
            methodology=methodology,
            locale=locale,
            logger=logger,
        )
        return msgs
    return msgs
