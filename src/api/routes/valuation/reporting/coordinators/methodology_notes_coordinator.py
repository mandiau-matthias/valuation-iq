"""
Methodology Notes Coordinator

Handles methodology notes generation logic.
Extracted from summary_generator.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive methodology notes
- Detailed logging
"""

from typing import Optional, TYPE_CHECKING

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.services.infrastructure.translations import ReportTranslations

logger = get_logger(__name__)


class MethodologyNotesCoordinator:
    """
    Coordinates methodology notes generation logic.
    
    Responsibilities:
    - Generate methodology notes text
    - Handle methodology downgrade transparency
    - Add DCF exclusion notes
    """
    
    def __init__(self, logger_instance=None):
        """
        Initialize methodology notes coordinator.
        
        Args:
            logger_instance: Logger instance (optional)
        """
        self.logger = logger_instance or logger
    
    def generate_methodology_notes(
        self,
        methodology: str,
        requested_methodology: Optional[str] = None,
        dcf_included: Optional[bool] = None,
        dcf_exclusion_reason: Optional[str] = None,
        t: Optional["ReportTranslations"] = None,
        locale: str = "nl",
        country_code: str = "BE",
    ) -> str:
        """
        Generate methodology notes with transparency about methodology selection

        Args:
            methodology: Actual valuation methodology used (stable internal key)
            requested_methodology: Methodology that was requested (if different from actual)
            dcf_included: Whether DCF was included in the valuation
            dcf_exclusion_reason: Reason DCF was excluded (if applicable)
            t: Optional pre-built ReportTranslations snapshot
            locale: Fallback locale when ``t`` is not provided
            country_code: Firm jurisdiction for legal-variant copy (e.g. NL overrides)

        Returns:
            Methodology notes text with transparency about selection (localized)
        """
        try:
            from src.services.infrastructure.translations import get_translations, normalize_report_locale
            _cc = str(country_code or "BE").strip().upper() or "BE"
            _t = t or get_translations(
                normalize_report_locale(locale),
                country_code=_cc,
            )

            self.logger.debug(
                f"📋 Generating methodology notes for: {methodology}",
                extra={
                    "requested_methodology": requested_methodology,
                    "dcf_included": dcf_included,
                    "has_exclusion_reason": dcf_exclusion_reason is not None,
                },
            )

            # Base notes for each methodology — localized via translations
            base_notes = {
                "DCF": _t.methodology_notes_dcf,
                "Multiples": _t.methodology_notes_multiples,
                "Market Multiples": _t.methodology_notes_multiples,
                "Asset-Based": _t.methodology_notes_asset_based,
                "Market": _t.methodology_notes_market,
                "Income": _t.methodology_notes_income,
                "Cost": _t.methodology_notes_cost,
                "Hybrid": _t.methodology_notes_hybrid,
                "Hybrid Valuation": _t.methodology_notes_hybrid,
                "STARTUP": (
                    "Startup valuation uses startup-native evidence instead of SME EBITDA "
                    "or DCF inputs: milestone progress, team strength, market context, "
                    "funding need, and the venture back-solve."
                ),
                "Startup Valuation": (
                    "Startup valuation uses startup-native evidence instead of SME EBITDA "
                    "or DCF inputs: milestone progress, team strength, market context, "
                    "funding need, and the venture back-solve."
                ),
            }

            notes = base_notes.get(methodology, _t.methodology_notes_default)

            # CRITICAL FIX: Add transparency when HYBRID was requested but downgraded to MULTIPLES
            if (
                requested_methodology
                and requested_methodology.upper() == "HYBRID"
                and methodology.upper() != "HYBRID"
            ):
                if not dcf_included and dcf_exclusion_reason:
                    notes += f" Note: HYBRID methodology was requested, but DCF was excluded. {dcf_exclusion_reason}. Using Market Multiples methodology only, which is more reliable for small businesses per academic valuation standards (Koller, Goedhart & Wessels 2020, Trugman 2017)."
                elif not dcf_included:
                    notes += " Note: HYBRID methodology was requested, but DCF was excluded due to company characteristics. Using Market Multiples methodology only, which is more reliable for small businesses per academic valuation standards (Koller, Goedhart & Wessels 2020, Trugman 2017)."

            # Add note if DCF was excluded in HYBRID methodology
            elif methodology.upper() == "HYBRID" and not dcf_included and dcf_exclusion_reason:
                notes += f" Note: DCF component was excluded from the hybrid analysis. {dcf_exclusion_reason}. The valuation uses Market Multiples methodology only."

            self.logger.debug(
                "✅ Methodology notes generated",
                extra={
                    "notes_length": len(notes),
                    "includes_downgrade_note": "HYBRID methodology was requested" in notes,
                },
            )

            return notes

        except Exception as e:
            self.logger.error(
                f"❌ Methodology notes generation failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            try:
                from src.services.infrastructure.translations import get_translations as _gt, normalize_report_locale
                _cc = str(country_code or "BE").strip().upper() or "BE"
                return _gt(
                    normalize_report_locale(locale),
                    country_code=_cc,
                ).methodology_notes_default
            except Exception:
                return "Professional valuation methodology applied."
