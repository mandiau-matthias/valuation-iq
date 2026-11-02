"""Defensibility classifier — output-time gate for sub-FULL valuations.

Wraps the existing ``services.infrastructure.report_classifier.classify_report``
(years-of-data + margin + data-quality) with three additional surfaces:

  1. **Methodology awareness**: startup / asset reports defer to their own
     confidence frameworks; running them through years-of-data heuristics
     produces false positives ("0 years of data → PRELIMINARY 40% cap"
     for a Berkus seed valuation, where 0 years is the entire premise).

  2. **Engine defensibility signals**: the years/margin classifier alone
     misses balance-missing, owner-led-zero-normalisation, formula-mismatch
     conditions that are equally damaging to a deliverable's defensibility.

  3. **Industry margin deviation**: severe sector mismatch (Three Towers:
     10% margin in 28%-typical industry) bumps the banner even on
     FULL_REPORT cases where years-of-data alone wouldn't catch it.

Output: a ``DefensibilityVerdict`` dataclass that downstream modules
(banner, asking-price gate, watermark) consume to make consistent
decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.services.defensibility.engine_signals import extract_engine_signals
from src.services.defensibility.methodology import (
    Methodology,
    detect_methodology,
    has_own_confidence_framework,
)
from src.services.defensibility.years_of_data import extract_years_of_data
from src.services.infrastructure.translations import normalize_report_locale
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DefensibilityVerdict:
    """The output-time verdict for a single valuation report.

    Frozen: passed by reference downstream; immutability prevents accidental
    drift between banner / watermark / asking-price decisions.
    """

    methodology: Methodology
    classification_value: Optional[str]  # e.g. "Valuation Analysis with Limitations"
    confidence_cap: Decimal  # [0, 1]
    cap_reason: Optional[str]
    is_full_report: bool
    auto_watermark: bool
    margin_warning: Optional[str]
    engine_signals: List[str] = field(default_factory=list)

    @property
    def has_banner(self) -> bool:
        """True when the banner should render."""
        return self.auto_watermark


@dataclass(frozen=True)
class MarginDeviationSignal:
    actual_pct: float
    typical_pct: float
    direction: str


def _safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Coerce arbitrary values to Decimal, returning ``default`` on failure."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return default


def _first_present(*values: Any, default: Any = None) -> Any:
    """Return the first value that is explicitly present, preserving zero."""
    for value in values:
        if value is not None:
            return value
    return default


def _extract_years_of_data(valuation_data: Dict[str, Any]) -> int:
    """Compatibility wrapper for the extracted years-of-data counter."""
    return extract_years_of_data(valuation_data)


def _extract_ebitda_margin(valuation_data: Dict[str, Any]) -> Decimal:
    """Compute EBITDA / revenue margin (negative if losses)."""
    if not isinstance(valuation_data, dict):
        return Decimal("0")
    ebitda_present = valuation_data.get("ebitda") is not None
    revenue = _safe_decimal(valuation_data.get("revenue"))
    ebitda = _safe_decimal(valuation_data.get("ebitda"))
    if revenue <= Decimal("0"):
        current = valuation_data.get("current_year_data") or {}
        if isinstance(current, dict):
            revenue = _safe_decimal(current.get("revenue"))
            if not ebitda_present:
                ebitda = _safe_decimal(current.get("ebitda"))
    if revenue <= Decimal("0"):
        return Decimal("0")
    return ebitda / revenue


def _industry_margin_deviation_warning(warnings_list: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(warnings_list, list):
        return None
    for warning in warnings_list:
        if not isinstance(warning, dict):
            continue
        if warning.get("type") != "industry_margin_deviation":
            continue
        severity = str(warning.get("severity") or "").lower()
        if severity in ("medium", "high"):
            return warning
    return None


def _margin_deviation_signal(warning: Dict[str, Any]) -> Optional[MarginDeviationSignal]:
    details = warning.get("details") or {}
    try:
        actual_pct = float(details.get("actual_margin_pct"))
        typical_pct = float(details.get("typical_margin_pct"))
    except (TypeError, ValueError):
        return None
    return MarginDeviationSignal(
        actual_pct=actual_pct,
        typical_pct=typical_pct,
        direction=str(details.get("direction") or "lower"),
    )


def _format_margin_warning(signal: MarginDeviationSignal, locale: str) -> str:
    loc = normalize_report_locale(locale)
    if loc == "en":
        return (
            f"EBITDA margin {signal.actual_pct:.1f}% is "
            f"{'lower' if signal.direction == 'lower' else 'higher'} "
            f"than the industry typical {signal.typical_pct:.1f}%. "
            "Confirm the sector classification and operating context "
            "before external distribution."
        )
    if loc == "fr":
        return (
            f"La marge EBITDA {signal.actual_pct:.1f}% est "
            f"{'inférieure' if signal.direction == 'lower' else 'supérieure'} "
            f"au niveau typique du secteur {signal.typical_pct:.1f} %. "
            "Confirmez la classification sectorielle et le contexte "
            "opérationnel avant toute diffusion externe."
        )
    return (
        f"EBITDA-marge {signal.actual_pct:.1f}% ligt "
        f"{'lager' if signal.direction == 'lower' else 'hoger'} "
        f"dan sectortypisch {signal.typical_pct:.1f}%. Bevestig "
        "de sectorclassificatie en de operationele "
        "context vóór externe distributie."
    )


def _extract_margin_warning(valuation_data: Any, locale: str = "nl") -> Optional[str]:
    """Pull a medium/high-severity industry margin deviation message.

    Three Towers Capital: 10% margin vs 28% typical, ``direction=lower``,
    ``severity=medium`` after the data-quality coordinator's calibration.
    Banner promotes this regardless of years-of-data classification.
    """
    if not isinstance(valuation_data, dict):
        return None
    warning = _industry_margin_deviation_warning(valuation_data.get("data_quality_warnings"))
    if warning is None:
        return None
    signal = _margin_deviation_signal(warning)
    return _format_margin_warning(signal, locale) if signal is not None else None


def _extract_engine_signals(
    valuation_data: Any, methodology: Methodology, locale: str = "nl"
) -> List[str]:
    """Compatibility wrapper around localized engine-signal composition."""
    return extract_engine_signals(
        valuation_data,
        methodology,
        locale=locale,
        safe_decimal=_safe_decimal,
        logger=logger,
    )


def classify_valuation_data(valuation_data: Any, locale: str = "nl") -> DefensibilityVerdict:
    """Output-time defensibility verdict for a valuation report.

    Methodology-aware: STARTUP and ASSET reports are not run through the
    years-of-data classifier (they have their own confidence frameworks)
    but still surface engine signals.

    Defensive: any internal failure falls back to a FULL_REPORT verdict
    with the methodology preserved — never crashes the PDF pipeline.
    """
    if not isinstance(valuation_data, dict):
        return DefensibilityVerdict(
            methodology=Methodology.UNKNOWN,
            classification_value=None,
            confidence_cap=Decimal("1.0"),
            cap_reason=None,
            is_full_report=True,
            auto_watermark=False,
            margin_warning=None,
            engine_signals=[],
        )
    methodology = detect_methodology(valuation_data)

    # Defaults — what we land on if nothing fires.
    classification_value: Optional[str] = None
    cap = Decimal("1.0")
    cap_reason: Optional[str] = None
    is_full_report = True

    if not has_own_confidence_framework(methodology):
        # Run the years-of-data + margin + data-quality classifier.
        try:
            from src.services.infrastructure.report_classifier import (
                ReportClassification,
                classify_report,
                get_confidence_cap_reason,
            )
        except Exception as e:  # pragma: no cover
            logger.warning("classify_valuation_data: import failed: %s", e)
            return DefensibilityVerdict(
                methodology=methodology,
                classification_value=None,
                confidence_cap=Decimal("1.0"),
                cap_reason=None,
                is_full_report=True,
                auto_watermark=False,
                margin_warning=None,
                engine_signals=[],
            )

        try:
            years = _extract_years_of_data(valuation_data)
            margin = _extract_ebitda_margin(valuation_data)
            dq_score = _safe_decimal(
                _first_present(
                    valuation_data.get("data_quality_score"),
                    valuation_data.get("overall_confidence_score"),
                    default=0.75,
                )
            )
            if dq_score > Decimal("1"):
                dq_score = dq_score / Decimal("100")
            classification, _limitations, cap = classify_report(
                years_of_data=years,
                ebitda_margin=margin,
                data_quality_score=dq_score,
                has_projections=bool(
                    valuation_data.get("has_dcf") or valuation_data.get("forecast_years_data")
                ),
            )
            classification_value = classification.value
            is_full_report = classification == ReportClassification.FULL_REPORT
            cap_reason = get_confidence_cap_reason(classification, years, margin) or None
        except Exception as e:
            logger.warning(
                "classify_valuation_data: classification failed",
                extra={"error_type": type(e).__name__, "error": str(e)[:200]},
            )

    # Margin and engine signals fire regardless of methodology (they're
    # separate concerns from years-of-data scope).
    margin_warning = _extract_margin_warning(valuation_data, locale=locale)
    engine_signals = _extract_engine_signals(valuation_data, methodology, locale=locale)

    auto_watermark = (not is_full_report) or bool(margin_warning) or bool(engine_signals)

    return DefensibilityVerdict(
        methodology=methodology,
        classification_value=classification_value,
        confidence_cap=cap,
        cap_reason=cap_reason,
        is_full_report=is_full_report,
        auto_watermark=auto_watermark,
        margin_warning=margin_warning,
        engine_signals=engine_signals,
    )
