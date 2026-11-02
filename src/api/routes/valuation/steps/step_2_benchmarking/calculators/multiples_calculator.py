"""
Multiples Calculator for Step 2 Benchmarking

This module calculates multiples and determines the primary valuation method
(EBITDA vs Revenue) following McKinsey/Bain standards.

NOTE: This is DIFFERENT from `src/api/routes/valuation/calculators/multiples_calculator.py`
which is the main valuation calculator. This is Step 2's internal multiples calculator.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Dict, Iterable, Optional, Tuple

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory
from src.domain.valuation_contract import normalize_method_key
from src.utils.decimal_helpers import to_decimal
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)

EBITDA_METHOD = "EV/EBITDA"
REVENUE_METHOD = "EV/Revenue"
MIN_RELIABLE_EBITDA_MARGIN = Decimal("3")
LOW_MARGIN_WARNING_THRESHOLD = Decimal("5")
SAAS_REVENUE_MARGIN_THRESHOLD = Decimal("15")
ECOMMERCE_REVENUE_MARGIN_THRESHOLD = Decimal("10")
HIGH_GROWTH_RATE_THRESHOLD = Decimal("30")

REVENUE_SELECTION_KEYS = frozenset(("omzet_multiple", "revenue_multiple", "arr_multiple"))
EBITDA_SELECTION_KEYS = frozenset(("ebitda_multiple",))
REVENUE_PREFERENCE_KEYS = frozenset(("revenue", "ev_revenue", "ev/revenue"))
EBITDA_PREFERENCE_KEYS = frozenset(("ebitda", "ev_ebitda", "ev/ebitda"))


def _has_profitable_ebitda(ebitda: Optional[Decimal]) -> bool:
    return ebitda is not None and ebitda > 0


def _has_reliable_ebitda(
    ebitda: Optional[Decimal],
    ebitda_margin: Decimal,
) -> bool:
    return _has_profitable_ebitda(ebitda) and ebitda_margin >= MIN_RELIABLE_EBITDA_MARGIN


def _normalise_preferred_multiple_tokens(preferred_multiples: object) -> set[str]:
    if isinstance(preferred_multiples, str):
        values: Iterable[object] = (preferred_multiples,)
    else:
        try:
            values = iter(preferred_multiples)
        except TypeError:
            values = (preferred_multiples,)

    return {
        str(value).strip().lower().replace("-", "_").replace(" ", "_")
        for value in values
        if value is not None and str(value).strip()
    }


def _is_revenue_method_name(method_lower: str) -> bool:
    return "revenue" in method_lower


def _is_ebitda_method_name(method_lower: str) -> bool:
    return "ebitda" in method_lower


def _revenue_primary_method_reason(
    ebitda: Optional[Decimal],
    ebitda_margin: Decimal,
) -> str:
    if ebitda is None or ebitda <= 0:
        return "Revenue multiple selected - company is loss-making (EBITDA ≤ 0)"
    if ebitda_margin < MIN_RELIABLE_EBITDA_MARGIN:
        return (
            f"Revenue multiple selected - EBITDA margin too low ({ebitda_margin:.1f}% "
            "< 3% threshold, unreliable for valuation)"
        )
    if ebitda_margin >= MIN_RELIABLE_EBITDA_MARGIN:
        return (
            "Revenue multiple selected - revenue-driven industry "
            f"(growth-stage SaaS/marketplace, margin {ebitda_margin:.1f}%)"
        )
    return "Revenue multiple selected (company profitability profile)"


def _ebitda_primary_method_reason(ebitda_margin: Decimal) -> str:
    if ebitda_margin >= MIN_RELIABLE_EBITDA_MARGIN and ebitda_margin < LOW_MARGIN_WARNING_THRESHOLD:
        return (
            "EBITDA multiple selected - profitable company "
            f"(margin {ebitda_margin:.1f}%, low margin warning applies)"
        )
    if ebitda_margin >= LOW_MARGIN_WARNING_THRESHOLD:
        return (
            "EBITDA multiple selected - profitable company "
            f"(margin {ebitda_margin:.1f}%, McKinsey/Bain standard)"
        )
    return "EBITDA multiple selected (profitable company)"


def _saas_revenue_driven_reason(
    ebitda: Optional[Decimal],
    ebitda_margin: Decimal,
    growth_rate: Optional[Decimal],
) -> Tuple[bool, str]:
    if not _has_profitable_ebitda(ebitda):
        return (
            True,
            "SaaS pre-profit growth stage - revenue scale prioritized over current profitability",
        )

    if (
        ebitda_margin < SAAS_REVENUE_MARGIN_THRESHOLD
        and growth_rate
        and to_decimal(growth_rate) > HIGH_GROWTH_RATE_THRESHOLD
    ):
        return (
            True,
            f"SaaS growth stage (margin {ebitda_margin:.1f}%, growth {growth_rate:.1f}%) - revenue scale prioritized",
        )

    if ebitda_margin < SAAS_REVENUE_MARGIN_THRESHOLD:
        return (
            True,
            f"SaaS with low margin ({ebitda_margin:.1f}%) - likely in growth/investment phase",
        )

    return (
        False,
        f"SaaS with healthy margin ({ebitda_margin:.1f}% ≥15%) - EBITDA multiple appropriate",
    )


def _ecommerce_revenue_driven_reason(
    ebitda_margin: Decimal,
) -> Tuple[bool, str]:
    if ebitda_margin < ECOMMERCE_REVENUE_MARGIN_THRESHOLD:
        return (
            True,
            f"E-commerce/Marketplace with low margin ({ebitda_margin:.1f}%) - GMV/platform model, revenue quality matters",
        )

    return (
        False,
        f"E-commerce/Marketplace with healthy margin ({ebitda_margin:.1f}% ≥10%) - EBITDA multiple appropriate",
    )


class MultiplesCalculator:
    """
    Calculates multiples and determines primary valuation method for Step 2.

    Implements EBITDA-First Methodology (McKinsey/Bain 2025):
    - EBITDA multiple is default for ALL profitable companies (margin ≥3%)
    - Revenue multiples only used for: loss-making, very low margins (<3%), or revenue-driven industries
    - Company size does NOT affect methodology choice - profitability drives value

    Dependencies:
    - BusinessTypeTriageEngine (for business category)
    - MethodologyEligibilityDecider (optional, for methodology decisions)
    """

    def __init__(self, business_type_triage=None):
        """
        Initialize MultiplesCalculator.

        Args:
            business_type_triage: BusinessTypeTriageEngine instance (optional)
        """
        self.business_type_triage = business_type_triage
        self.logger = logger

    def is_revenue_driven_industry(
        self,
        business_category: BusinessTypeCategory,
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
        revenue: Optional[Decimal] = None,
        growth_rate: Optional[Decimal] = None,
    ) -> Tuple[bool, str]:
        """
        Determine if business should use Revenue multiple despite positive EBITDA.

        **CRITICAL (2025 Enhancement):** Tightened criteria - only true revenue-driven industries
        with low margins qualify. Profitable companies (margin ≥3%) should use EBITDA regardless.

        This implements McKinsey/Bain standards for revenue-driven industries where
        top-line growth is valued over current profitability, BUT only when profitability is low.

        **Tightened Criteria:**
        - SaaS: Only if margin <15% AND (loss-making OR high growth >30%)
        - E-commerce/Marketplace: Only if margin <10%
        - All other industries: Never revenue-driven

        Args:
            business_category: Business category (SaaS, E-commerce, etc.)
            ebitda: Company EBITDA (can be negative, zero, or positive)
            ebitda_margin: EBITDA margin percentage
            revenue: Company revenue (optional, for growth analysis)
            growth_rate: YoY revenue growth rate (optional, for growth-stage logic)

        Returns:
            tuple: (is_revenue_driven, reason)
                - is_revenue_driven: True if should use Revenue multiple
                - reason: Human-readable explanation

        Examples:
            >>> calculator = MultiplesCalculator()
            >>> is_revenue, reason = calculator.is_revenue_driven_industry(
            ...     BusinessTypeCategory.SAAS_SOFTWARE, None, Decimal('0.0')
            ... )
            >>> print(f"Revenue-driven: {is_revenue}, Reason: {reason}")
        """
        if business_category == BusinessTypeCategory.SAAS_SOFTWARE:
            return _saas_revenue_driven_reason(ebitda, ebitda_margin, growth_rate)

        if business_category == BusinessTypeCategory.ECOMMERCE:
            return _ecommerce_revenue_driven_reason(ebitda_margin)

        return (False, "")

    def _method_from_user_selection(
        self,
        user_selected_method: Optional[str],
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
        revenue: Optional[Decimal],
    ) -> Optional[str]:
        if not user_selected_method:
            return None

        selected_method = normalize_method_key(user_selected_method)
        if selected_method in REVENUE_SELECTION_KEYS:
            self.logger.info(
                f"✅ Revenue multiple selected - user explicitly chose '{user_selected_method}'",
                extra={
                    "user_selected_method": user_selected_method,
                    "ebitda": ebitda,
                    "ebitda_margin": ebitda_margin,
                    "revenue": revenue,
                    "reason": "User intent overrides EBITDA-First engine logic",
                },
            )
            return REVENUE_METHOD

        if selected_method not in EBITDA_SELECTION_KEYS:
            return None

        if _has_profitable_ebitda(ebitda):
            self.logger.info(
                f"✅ EBITDA multiple selected - user explicitly chose '{user_selected_method}' "
                f"(margin {ebitda_margin:.1f}%, bypassing industry heuristics)",
                extra={
                    "user_selected_method": user_selected_method,
                    "ebitda": ebitda,
                    "ebitda_margin": ebitda_margin,
                    "revenue": revenue,
                    "reason": "User intent overrides industry-specific engine logic (SaaS/E-commerce margin thresholds bypassed)",
                },
            )
            return EBITDA_METHOD

        self.logger.warning(
            f"⚠️ User chose '{user_selected_method}' but EBITDA is non-positive "
            f"({ebitda}) — cannot apply EBITDA multiple to non-positive earnings, "
            f"falling through to engine auto-selection",
            extra={
                "user_selected_method": user_selected_method,
                "ebitda": ebitda,
                "ebitda_margin": ebitda_margin,
                "revenue": revenue,
                "reason": "EBITDA ≤ 0: mathematically impossible to apply EBITDA multiple",
            },
        )
        return None

    def _method_from_revenue_driven_industry(
        self,
        business_category: Optional[BusinessTypeCategory],
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
        revenue: Optional[Decimal],
        growth_rate: Optional[Decimal],
    ) -> Optional[str]:
        if not business_category or not _has_profitable_ebitda(ebitda):
            return None

        is_revenue_driven, revenue_driven_reason = self.is_revenue_driven_industry(
            business_category, ebitda, ebitda_margin, revenue, growth_rate
        )
        if not is_revenue_driven:
            return None

        self.logger.info(
            f"✅ Revenue multiple selected - revenue-driven industry override "
            f"({getattr(business_category, 'value', 'unknown')}, margin {ebitda_margin:.1f}%)",
            extra={
                "business_category": getattr(business_category, "value", "unknown"),
                "ebitda": ebitda,
                "ebitda_margin": ebitda_margin,
                "revenue": revenue,
                "growth_rate": growth_rate,
                "reason": revenue_driven_reason,
                "methodology": "Industry-specific (SaaS/E-commerce M&A standard)",
            },
        )
        return REVENUE_METHOD

    def _method_from_ebitda_first(
        self,
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
        revenue: Optional[Decimal],
    ) -> Optional[str]:
        if not _has_reliable_ebitda(ebitda, ebitda_margin):
            return None

        # DEBUG: the canonical "✅ SME ebitda calibration using Titan
        # enrichment: …" rationale line carries the full reasoning.
        self.logger.debug(
            f"✅ EBITDA multiple selected - profitable company (margin {ebitda_margin:.1f}%, EBITDA €{ebitda:,.0f})",
            extra={
                "ebitda": ebitda,
                "ebitda_margin": ebitda_margin,
                "revenue": revenue,
                "reason": "EBITDA-First Methodology: Profitable companies always use EBITDA",
                "methodology": "EBITDA-First (McKinsey/Bain 2025)",
                "low_margin_warning": ebitda_margin < LOW_MARGIN_WARNING_THRESHOLD,
            },
        )
        return EBITDA_METHOD

    def _preferred_multiples_from_payload(
        self,
        valuation_preferences: Optional[Dict],
    ) -> object:
        if isinstance(valuation_preferences, dict):
            return valuation_preferences.get("preferred_multiples")
        return None

    def _preferred_multiples_from_metadata_service(
        self,
        valuation_preferences: Optional[Dict],
    ) -> object:
        try:
            from src.services.business_type_metadata_service import (
                get_business_type_metadata_service,
            )

            metadata_service = get_business_type_metadata_service()
            if metadata_service:
                return metadata_service.get_preferred_multiples(valuation_preferences)
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            logger.debug("Preferred multiples from metadata_service unavailable: %s", exc)
        return None

    def _preferred_multiples_from_repository(self, business_type_id: str) -> object:
        try:
            from src.database.business_types_repository import get_business_types_repository

            with get_business_types_repository() as repo:
                business_type = repo.get_business_type(business_type_id)
                return (
                    getattr(business_type, "preferred_multiples", None) if business_type else None
                )
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            logger.debug("Preferred multiples from DB repo unavailable: %s", exc)
        return None

    def _resolve_preferred_multiples(
        self,
        business_type_id: Optional[str],
        valuation_preferences: Optional[Dict],
    ) -> object:
        preferred_multiples = self._preferred_multiples_from_payload(valuation_preferences)
        if preferred_multiples or not business_type_id:
            return preferred_multiples

        preferred_multiples = self._preferred_multiples_from_metadata_service(valuation_preferences)
        if preferred_multiples:
            return preferred_multiples

        return self._preferred_multiples_from_repository(business_type_id)

    def _method_from_preferred_multiples(
        self,
        preferred_multiples: object,
        business_type_id: Optional[str],
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
    ) -> Optional[str]:
        preferred_keys = _normalise_preferred_multiple_tokens(preferred_multiples)
        if not preferred_keys:
            return None

        if preferred_keys & REVENUE_PREFERENCE_KEYS:
            if not _has_reliable_ebitda(ebitda, ebitda_margin):
                self.logger.info(
                    f"Using preferred multiple: EV/Revenue for {business_type_id}",
                    extra={
                        "preferred_multiples": preferred_multiples,
                        "ebitda": ebitda,
                        "ebitda_margin": ebitda_margin,
                        "reason": "Preference honored (EBITDA not profitable)",
                    },
                )
                return REVENUE_METHOD

            self.logger.warning(
                "Preferred multiples suggest Revenue but EBITDA is profitable - using EBITDA instead",
                extra={
                    "preferred_multiples": preferred_multiples,
                    "ebitda": ebitda,
                    "ebitda_margin": ebitda_margin,
                    "reason": "EBITDA-First Methodology overrides preference",
                },
            )
            return None

        if preferred_keys & EBITDA_PREFERENCE_KEYS and _has_reliable_ebitda(ebitda, ebitda_margin):
            self.logger.info(
                f"Using preferred multiple: EV/EBITDA for {business_type_id}",
                extra={"preferred_multiples": preferred_multiples},
            )
            return EBITDA_METHOD

        return None

    def _fallback_primary_method(
        self,
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
        revenue: Optional[Decimal],
    ) -> str:
        if ebitda is None or ebitda <= 0:
            self.logger.info(
                "Using Revenue multiple - company is loss-making or EBITDA unavailable",
                extra={
                    "ebitda": ebitda,
                    "revenue": revenue,
                    "reason": "Loss-making companies valued on revenue scale",
                },
            )
            return REVENUE_METHOD

        if ebitda_margin < MIN_RELIABLE_EBITDA_MARGIN:
            self.logger.info(
                f"Using Revenue multiple - EBITDA margin too low ({ebitda_margin:.1f}%)",
                extra={
                    "ebitda": ebitda,
                    "ebitda_margin": ebitda_margin,
                    "revenue": revenue,
                    "reason": "Margins <3% are too volatile for reliable EBITDA valuation",
                },
            )
            return REVENUE_METHOD

        self.logger.info(
            f"Using EBITDA multiple - profitable company (margin {ebitda_margin:.1f}%)",
            extra={
                "ebitda": ebitda,
                "ebitda_margin": ebitda_margin,
                "revenue": revenue,
                "reason": "EBITDA multiple is standard for profitable companies (McKinsey/Bain)",
                "low_margin_warning": ebitda_margin < LOW_MARGIN_WARNING_THRESHOLD,
            },
        )
        return EBITDA_METHOD

    def determine_primary_method(
        self,
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
        revenue: Optional[Decimal] = None,
        business_type_id: Optional[str] = None,
        business_category: Optional[BusinessTypeCategory] = None,
        growth_rate: Optional[Decimal] = None,
        valuation_preferences: Optional[Dict] = None,
        user_selected_method: Optional[str] = None,
    ) -> str:
        """
        Determine which multiple should be primary.

        McKinsey/Bain Standard (2025): EBITDA multiple is default for ALL profitable companies.
        Revenue multiples only used for: loss-making, very low margins (<3%), or revenue-driven industries.

        **CRITICAL ENHANCEMENT (2025):** EBITDA-First Methodology
        - If EBITDA > 0 and margin ≥3%, ALWAYS use EBITDA regardless of company size
        - Company size does NOT affect methodology choice - profitability drives value
        - Database preferred_multiples override ONLY if EBITDA is not available/profitable

        Priority Cascade:
        0.  User explicitly selected method → ALWAYS honor user intent (overrides engine guardrails)
            - revenue/omzet/arr_multiple → EV/Revenue
            - ebitda_multiple (EBITDA > 0) → EV/EBITDA (bypasses industry margin thresholds)
            - ebitda_multiple (EBITDA ≤ 0) → fall through (can't multiply non-positive earnings)
        0.5 Revenue-driven industry (SaaS <15% margin, E-commerce <10% margin) → Revenue
        1.  EBITDA > 0 and margin ≥3% → EBITDA (for non-revenue-driven industries)
        2.  Database preferred_multiples (if EBITDA not available/profitable)
        3.  EBITDA ≤ 0 → Revenue multiple (loss-making)
        4.  EBITDA margin < 3% → Revenue multiple (barely profitable, unreliable)
        5.  Default: EBITDA multiple

        Args:
            ebitda: Company EBITDA (optional)
            ebitda_margin: EBITDA margin percentage
            revenue: Company revenue (optional)
            business_type_id: Business type ID string (optional)
            business_category: BusinessTypeCategory enum value (optional)
            growth_rate: YoY revenue growth rate (optional)
            user_selected_method: Explicit user method selection from the UI (optional)

        Returns:
            'EV/EBITDA' or 'EV/Revenue'

        Examples:
            >>> calculator = MultiplesCalculator()
            >>> method = calculator.determine_primary_method(100000, Decimal('10.0'))
            >>> print(f"Primary method: {method}")  # 'EV/EBITDA'
        """
        user_method = self._method_from_user_selection(
            user_selected_method,
            ebitda,
            ebitda_margin,
            revenue,
        )
        if user_method:
            return user_method

        industry_method = self._method_from_revenue_driven_industry(
            business_category,
            ebitda,
            ebitda_margin,
            revenue,
            growth_rate,
        )
        if industry_method:
            return industry_method

        ebitda_first_method = self._method_from_ebitda_first(
            ebitda,
            ebitda_margin,
            revenue,
        )
        if ebitda_first_method:
            return ebitda_first_method

        preferred_multiples = self._resolve_preferred_multiples(
            business_type_id,
            valuation_preferences,
        )
        preferred_method = self._method_from_preferred_multiples(
            preferred_multiples,
            business_type_id,
            ebitda,
            ebitda_margin,
        )
        if preferred_method:
            return preferred_method

        return self._fallback_primary_method(ebitda, ebitda_margin, revenue)

    def get_primary_method_reason(
        self,
        primary_method: str,
        revenue: Optional[Decimal] = None,
        ebitda: Optional[Decimal] = None,
        ebitda_margin: Decimal = Decimal("0.0"),
    ) -> str:
        """
        Return a human-readable explanation for why a particular primary method was selected.

        McKinsey/Bain Standard (2025): Reflects new EBITDA-first methodology.

        Args:
            primary_method: The primary method string ('EV/Revenue', 'EV/EBITDA', 'revenue_multiple', or 'ebitda_multiple')
            revenue: Company revenue (optional, for context)
            ebitda: Company EBITDA (optional, for profitability check)
            ebitda_margin: EBITDA margin percentage (for profitability check)

        Returns:
            Human-readable explanation string reflecting the actual logic path taken

        Examples:
            >>> calculator = MultiplesCalculator()
            >>> reason = calculator.get_primary_method_reason('EV/EBITDA', ebitda=100000, ebitda_margin=Decimal('10.0'))
            >>> print(reason)  # "EBITDA multiple selected - profitable company (margin 10.0%, McKinsey/Bain standard)"
        """
        method_lower = primary_method.lower() if primary_method else ""

        if _is_revenue_method_name(method_lower):
            return _revenue_primary_method_reason(ebitda, ebitda_margin)

        if _is_ebitda_method_name(method_lower):
            return _ebitda_primary_method_reason(ebitda_margin)

        return "Multiple selected based on company profitability profile"
