"""Defensibility gate — output-time guards against silent over-confidence.

Three Towers Capital regression family. The valuation engine produces
mathematically correct numbers but the report can still ship a
production-grade visual on insufficient inputs (N=2y, owner-led, no
normalisations, no balance, low-margin sector mismatch). This package
defines the *output-time* gate that catches that failure mode.

Public surface:

  - ``classify_valuation_data(valuation_data)``: years × margin × engine-signal
    classifier. Returns ``DefensibilityVerdict`` with cap, banner, and
    auto-watermark intent.

  - ``methodology.detect_methodology(valuation_data)``: returns a
    ``Methodology`` enum (STARTUP, ASSET, SDE, DCF, HYBRID, MULTIPLES,
    UNKNOWN). Used to skip-or-defer classification for methodologies
    with their own confidence frameworks (startup, asset).

  - ``banner.build_defensibility_banner(verdict, locale)``: i18n banner
    HTML — Dutch and English.

  - ``asking_price_gate.apply_to_context(context, valuation_data)``:
    suppress the negotiation buffer when the report cannot defensibly
    anchor a tight band.

  - ``reference_formatter.format_valuation_reference(uuid, date)``:
    UUID → ``VAL-YYYY-XXXX`` so the public-facing ID looks finished.

Modular design intentions:
  - Each module owns one concern (classifier / banner / asking-price /
    formatter / methodology). Adding a new defensibility check should not
    require touching ``reports.py``.
  - Methodology-aware: every gate consults
    ``methodology.detect_methodology`` so startup / asset paths get the
    right (different) treatment than SME-DCF/multiples.
  - i18n-first: text-bearing modules accept ``locale`` and ship NL+EN.
"""

from src.services.defensibility.classifier import (
    DefensibilityVerdict,
    classify_valuation_data,
)
from src.services.defensibility.methodology import (
    Methodology,
    detect_methodology,
)
from src.services.defensibility.banner import (
    DEFENSIBILITY_BANNER_DIV_PREFIX,
    build_defensibility_banner,
)
from src.services.defensibility.asking_price_gate import (
    apply_asking_price_gate,
    build_engine_side_gate_input,
)
from src.services.defensibility.reference_formatter import (
    format_valuation_reference,
)
from src.services.defensibility.scoring import (
    CompositeScore,
    ScoreBand,
    ScorePillar,
    compute_academic_score,
    compute_icp_score,
)
from src.services.defensibility.warnings import (
    DefensibilityWarning,
    WarningSeverity,
    collect_warnings,
)
from src.services.defensibility.report import (
    DefensibilityReport,
    OverridePrompt,
    SubmitGate,
    SubmitRecommendation,
    build_defensibility_report,
)

__all__ = [
    # Existing surface — backwards compatible
    "DefensibilityVerdict",
    "Methodology",
    "apply_asking_price_gate",
    "build_engine_side_gate_input",
    "build_defensibility_banner",
    "DEFENSIBILITY_BANNER_DIV_PREFIX",
    "classify_valuation_data",
    "detect_methodology",
    "format_valuation_reference",
    # New structured surface
    "CompositeScore",
    "ScoreBand",
    "ScorePillar",
    "compute_academic_score",
    "compute_icp_score",
    "DefensibilityWarning",
    "WarningSeverity",
    "collect_warnings",
    "DefensibilityReport",
    "OverridePrompt",
    "SubmitGate",
    "SubmitRecommendation",
    "build_defensibility_report",
]
