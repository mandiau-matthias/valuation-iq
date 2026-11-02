"""
SME Multiple Selector

Selects appropriate valuation multiples based on SME academic sources.
Uses SME-specific research (Trugman, Coulon, VFB Belgium, Pepperdine)
instead of large company defaults.

WORLD-CLASS BUSINESS TYPE INTEGRATION:
- Integrates with the governed business-type catalog
- Uses business-type-specific characteristics
- Applies owner dependency adjustments
- Uses business-type-specific margin adjustments

Author: Upswitch AI + Claude Sonnet 4.5
Date: December 2, 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.services.academic import sme_ebitda_selection_policy
from src.services.academic.sme_business_type_lookup import (
    synced_business_type_ev_ebitda,
    synced_owner_dependency_impact,
)
from src.services.academic.sme_growth_stage import determine_growth_stage as resolve_growth_stage
from src.services.academic.sme_growth_stage import has_multi_year_profitable_history
from src.services.academic.sme_multiple_catalog import (
    BELGIAN_SME_MULTIPLES,
    BELGIAN_SME_MULTIPLES_BY_TYPE,
    BENELUX_REGIONAL_ADJUSTMENTS,
    CATEGORY_TO_SME_KEY,
    EBITDA_MAX_INDUSTRY_OVERRIDES,
    MEDIUM_SME_THRESHOLD,
    MICRO_SME_THRESHOLD,
    SMALL_SME_THRESHOLD,
    SME_MULTIPLE_BOUNDS,
    SME_REVENUE_MULTIPLES,
    TRANSACTION_SME_MULTIPLES,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Import Prometheus metrics for SME calibration tracking
try:
    from src.api.routes.valuation.metrics import sme_size_premium_source_counter

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("Prometheus metrics not available - SME calibration metrics disabled")

# Try to import DatabaseDrivenDefaults for database-first approach
try:
    from src.services.business_intelligence.database_driven_defaults import DatabaseDrivenDefaults

    DATABASE_DRIVEN_DEFAULTS_AVAILABLE = True
except ImportError:
    DATABASE_DRIVEN_DEFAULTS_AVAILABLE = False
    logger.warning("DatabaseDrivenDefaults not available - using hardcoded fallbacks")
    DatabaseDrivenDefaults = None  # For type checking

# Try to import business type service (optional dependency)
try:
    from src.services.business_intelligence.integration.business_type_database_service import (
        get_business_type_database_service,
    )

    BUSINESS_TYPE_SERVICE_AVAILABLE = True
except ImportError:
    BUSINESS_TYPE_SERVICE_AVAILABLE = False
    logger.warning("BusinessTypeDatabaseService not available - business type integration disabled")
    get_business_type_database_service = None  # For type checking


class SMEMultipleSelector:
    """
    Selects SME-appropriate valuation multiples based on academic research.

    Sources:
    - Trugman (2017): AICPA SME valuation standard
    - Coulon (2021): European SME specialist
    - VFB Belgium (2024): Belgian market data
    - Pepperdine (2024): SME transaction database
    - BizComps (2024): SME comparables
    """

    # Static calibration policy lives outside the selector so this class stays
    # focused on selection logic. Class attributes are kept as compatibility
    # aliases for existing tests and callers.
    MICRO_SME_THRESHOLD = MICRO_SME_THRESHOLD
    SMALL_SME_THRESHOLD = SMALL_SME_THRESHOLD
    MEDIUM_SME_THRESHOLD = MEDIUM_SME_THRESHOLD
    SME_MULTIPLE_BOUNDS = SME_MULTIPLE_BOUNDS
    EBITDA_MAX_INDUSTRY_OVERRIDES = EBITDA_MAX_INDUSTRY_OVERRIDES
    CATEGORY_TO_SME_KEY = CATEGORY_TO_SME_KEY
    BELGIAN_SME_MULTIPLES_BY_TYPE = BELGIAN_SME_MULTIPLES_BY_TYPE
    BELGIAN_SME_MULTIPLES = BELGIAN_SME_MULTIPLES
    BENELUX_REGIONAL_ADJUSTMENTS = BENELUX_REGIONAL_ADJUSTMENTS
    TRANSACTION_SME_MULTIPLES = TRANSACTION_SME_MULTIPLES
    SME_REVENUE_MULTIPLES = SME_REVENUE_MULTIPLES

    @classmethod
    def classify_sme(cls, revenue: Decimal) -> str:
        """Classify company as micro, small, medium, or large by revenue."""
        from src.services.academic.sme_size import classify_sme

        return classify_sme(revenue)

    @classmethod
    def determine_growth_stage(
        cls,
        founded_year: Optional[int] = None,
        current_year: Optional[int] = None,
        historical_data: Optional[List[Dict[str, Any]]] = None,
        revenue: Optional[Decimal] = None,
    ) -> Tuple[str, Decimal]:
        """Compatibility wrapper for the extracted growth-stage classifier."""
        return resolve_growth_stage(
            founded_year=founded_year,
            current_year=current_year,
            historical_data=historical_data,
            revenue=revenue,
        )

    @staticmethod
    def _has_multi_year_profitable_history(
        historical_data: Optional[List[Dict[str, Any]]],
    ) -> bool:
        """Compatibility wrapper for the extracted profitability signal."""
        return has_multi_year_profitable_history(historical_data)

    @classmethod
    def _synced_owner_dependency_impact(cls, business_type: Optional[str]) -> Optional[Decimal]:
        """Compatibility wrapper for synced owner-dependency lookup."""
        return synced_owner_dependency_impact(business_type)

    @classmethod
    def _synced_business_type_ev_ebitda(
        cls, business_type: Optional[str], country: str = "Belgium"
    ) -> Optional[Decimal]:
        """Compatibility wrapper for synced business-type EV/EBITDA lookup."""
        return synced_business_type_ev_ebitda(business_type, country)

    @classmethod
    def get_sme_ebitda_multiple(
        cls,
        revenue: Decimal,
        industry: str,
        business_type: Optional[str] = None,
        business_category: Optional[str] = None,
        country: str = "Belgium",
        use_transaction_data: bool = False,
        ebitda: Optional[Decimal] = None,  # For margin-based adjustments
        founded_year: Optional[int] = None,  # WORLD-CLASS: For growth stage determination
        current_year: Optional[int] = None,  # WORLD-CLASS: For growth stage determination
        historical_data: Optional[
            List[Dict[str, Any]]
        ] = None,  # WORLD-CLASS: For growth stage determination
        sme_calibration: Optional[
            Dict[str, Any]
        ] = None,  # PRIORITY 1: Titan-provided SME calibration
    ) -> Tuple[Decimal, str, str]:
        """
        Get SME-appropriate EBITDA multiple based on academic sources.

        Returns:
            Tuple of (multiple, sources, rationale)

        WORLD-CLASS BUSINESS TYPE INTEGRATION:
        - Uses business type characteristics from the governed catalog
        - Applies owner dependency adjustments
        - Uses business-type-specific margin adjustments
        - Aligns with methodology preferences

        Methodology:
        1. Classify SME size (micro/small/medium)
        2. Select source (Belgian market vs transaction database)
        3. Apply industry-specific multiple from academic research
        4. Apply business-type-specific adjustments (if business_type provided)

        Args:
            revenue: Annual revenue in euros
            industry: Industry type
            business_type: Optional business type ID (e.g., 'consulting', 'saas', 'restaurant')
            business_category: Optional business category (e.g., 'professional_services', 'saas_software')
            country: Country (affects source selection)
            use_transaction_data: If True, use conservative transaction multiples
            ebitda: Optional EBITDA for margin-based adjustments

        Returns:
            Tuple of (multiple, rationale)
            - multiple: Decimal EBITDA multiple (adjusted for business type if provided)
            - rationale: Explanation string including business type adjustments
        """
        # Classify SME
        sme_class = cls.classify_sme(revenue)

        if sme_class == "large":
            # Use traditional large company multiples
            logger.info(f"Company is large (revenue €{revenue:,.0f}), using standard multiples")
            return (
                Decimal("8.0"),
                "Damodaran (2012) / McKinsey (2020)",
                "Large company - standard multiples",
            )

        # Normalize industry
        industry_norm = industry.lower().strip()

        resolution = sme_ebitda_selection_policy.resolve_base_ebitda_multiple_for_selector(
            industry=industry,
            industry_norm=industry_norm,
            sme_class=sme_class,
            business_type=business_type,
            business_category=business_category,
            country=country,
            use_transaction_data=use_transaction_data,
            sme_calibration=sme_calibration,
            database_defaults=DatabaseDrivenDefaults,
            database_defaults_available=DATABASE_DRIVEN_DEFAULTS_AVAILABLE,
        )
        base_multiple = resolution.base_multiple
        source_name = resolution.source_name
        data_source_priority = resolution.data_source_priority
        industry_norm = resolution.industry_norm

        # ============================================================================
        # PROMETHEUS METRICS: Track data source for monitoring
        # ============================================================================
        sme_ebitda_selection_policy.record_sme_calibration_metrics(
            sme_class=sme_class,
            industry_norm=industry_norm,
            data_source_priority=data_source_priority,
            metrics_available=METRICS_AVAILABLE,
            database_defaults_available=DATABASE_DRIVEN_DEFAULTS_AVAILABLE,
        )
        multiple = sme_ebitda_selection_policy.clamp_to_academic_bounds(
            multiple=base_multiple,
            sme_class=sme_class,
            industry_norm=industry_norm,
            metrics_available=METRICS_AVAILABLE,
        )

        # WORLD-CLASS: Apply growth stage adjustments (startup/growth/mature)
        growth_stage, growth_adjustment_factor = cls.determine_growth_stage(
            founded_year=founded_year,
            current_year=current_year,
            historical_data=historical_data,
            revenue=revenue,
        )

        growth_adjustment = sme_ebitda_selection_policy.apply_growth_stage_adjustment(
            multiple=multiple,
            base_multiple=base_multiple,
            growth_stage=growth_stage,
            growth_adjustment_factor=growth_adjustment_factor,
        )
        business_type_adjustment = sme_ebitda_selection_policy.apply_business_type_adjustments(
            multiple=growth_adjustment.multiple,
            business_type=business_type,
            revenue=revenue,
            ebitda=ebitda,
            sme_calibration=sme_calibration,
            business_type_service_available=BUSINESS_TYPE_SERVICE_AVAILABLE,
            business_type_service_factory=get_business_type_database_service,
            owner_dependency_resolver=cls._synced_owner_dependency_impact,
        )
        multiple = business_type_adjustment.multiple
        adjustment_rationales = growth_adjustment.rationales + business_type_adjustment.rationales
        rationale = sme_ebitda_selection_policy.build_sme_ebitda_rationale(
            sme_class=sme_class,
            revenue=revenue,
            industry_norm=industry_norm,
            base_multiple=base_multiple,
            source_name=source_name,
            business_type=business_type,
            growth_stage=growth_stage,
            adjustment_rationales=adjustment_rationales,
            multiple=multiple,
        )

        # DEBUG: dup of "✅ SME ebitda calibration using Titan enrichment: …" detail.
        logger.debug(
            f"Selected SME EBITDA multiple",
            revenue=float(revenue),
            industry=industry_norm,
            sme_class=sme_class,
            business_type=business_type,
            base_multiple=float(base_multiple),
            final_multiple=float(multiple),
            adjustments_applied=len(adjustment_rationales),
            source=source_name,
        )

        sme_ebitda_selection_policy.record_ebitda_multiple_provenance(
            revenue=revenue,
            industry_norm=industry_norm,
            sme_class=sme_class,
            business_type=business_type,
            growth_stage=growth_stage,
            base_multiple=base_multiple,
            adjustment_count=len(adjustment_rationales),
            multiple=multiple,
            source_name=source_name,
        )

        # Return multiple, sources, and rationale
        sources = source_name  # Single source name for now
        return multiple, sources, rationale

    @classmethod
    def get_sme_revenue_multiple(cls, revenue: Decimal, industry: str) -> Tuple[Decimal, str]:
        """
        Get SME-appropriate revenue multiple based on academic sources.

        Sources: Trugman (2017), West (2012)

        Args:
            revenue: Annual revenue in euros
            industry: Industry type

        Returns:
            Tuple of (multiple, source_rationale)
        """
        sme_class = cls.classify_sme(revenue)

        if sme_class == "large":
            return Decimal("1.5"), "Large company - standard multiples"

        # Normalize industry
        industry_norm = industry.lower().strip()

        # ============================================================================
        # DATABASE-FIRST APPROACH: Try DatabaseDrivenDefaults before hardcoded values
        # ============================================================================
        multiple = None

        if DATABASE_DRIVEN_DEFAULTS_AVAILABLE and DatabaseDrivenDefaults.is_initialized():
            db_multiples = DatabaseDrivenDefaults.get_sme_multiples_by_industry(
                industry=industry_norm, sme_class=sme_class
            )
            if db_multiples and db_multiples.get("ev_revenue"):
                multiple = db_multiples["ev_revenue"]
                logger.debug(
                    f"Using database SME revenue multiple for {industry_norm}/{sme_class}",
                    ev_revenue=float(multiple),
                    source="database",
                )

        # ============================================================================
        # FALLBACK: Use hardcoded academic sources if database unavailable
        # ============================================================================
        if multiple is None:
            sme_key = cls.CATEGORY_TO_SME_KEY.get(industry_norm)
            if sme_key is None:
                for alias, canonical in cls.CATEGORY_TO_SME_KEY.items():
                    if alias in industry_norm or industry_norm in alias:
                        sme_key = canonical
                        break

            industry_multiples = cls.SME_REVENUE_MULTIPLES.get(sme_key) if sme_key else None

            if industry_multiples is None:
                logger.warning(
                    f"Industry '{industry}' not found, using 'services' revenue multiple"
                )
                industry_multiples = cls.SME_REVENUE_MULTIPLES.get(
                    "services",
                    {"micro": Decimal("0.8"), "small": Decimal("1.0"), "medium": Decimal("1.2")},
                )
                industry_norm = "services"

            # Get multiple for SME class
            multiple = industry_multiples.get(sme_class, Decimal("1.0"))

        rationale = (
            f"{sme_class.capitalize()} SME (revenue \u20ac{revenue:,.0f}) "
            f"in {industry_norm} industry: "
            f"{multiple}x revenue per Trugman (2017) / West (2012)"
        )

        # DEBUG: dup of "✅ SME revenue calibration using Titan enrichment: …" detail.
        logger.debug(
            f"Selected SME revenue multiple",
            revenue=float(revenue),
            industry=industry_norm,
            sme_class=sme_class,
            multiple=float(multiple),
        )

        return multiple, rationale

    @classmethod
    def get_sme_discount_rate(
        cls,
        revenue: Decimal,
        ebitda: Optional[Decimal] = None,
        has_audit: Optional[bool] = None,
        customer_concentration: Optional[Decimal] = None,
        industry: Optional[str] = None,
        owner_dependency_score: Optional[Decimal] = None,
    ) -> Tuple[Decimal, str]:
        """
        Get SME-appropriate discount rate (WACC) based on academic sources.

        Sources: Trugman (2017), Officer (2007), Duff & Phelps (2024)

        SME WACC = Risk-free rate + Equity risk premium + Size premium + Company-specific risk

        Args:
            revenue: Annual revenue in euros
            ebitda: EBITDA (optional, for profitability assessment)
            has_audit: Whether company has audited financials
            customer_concentration: Top-customer concentration as decimal (0-1)
            industry: Industry / NACE category label
            owner_dependency_score: Owner dependency score as decimal (0-1)

        Returns:
            Tuple of (wacc_decimal, source_rationale)
        """
        from src.domain.market_defaults import (
            calculate_company_specific_risk,
            get_default_equity_risk_premium,
            get_risk_free_rate,
        )
        from src.domain.market_defaults import get_size_premium as get_size_premium_interpolated

        sme_class = cls.classify_sme(revenue)
        country_code = "BE"

        # Risk-free rate: live lookup with monthly-updated fallback
        risk_free, rf_source = get_risk_free_rate(country_code)

        # Equity risk premium: country-specific (Damodaran annual update)
        equity_risk = get_default_equity_risk_premium(country_code)

        # Size premium: 7-tier interpolation (Duff & Phelps / Ibbotson 2024)
        # Try database first, then interpolated tiers
        size_premium = None
        size_premium_source = None

        if DATABASE_DRIVEN_DEFAULTS_AVAILABLE and DatabaseDrivenDefaults.is_initialized():
            size_premium = DatabaseDrivenDefaults.get_size_premium(sme_class)
            size_premium_source = "database"
            logger.debug(f"Using database size premium for {sme_class}: {float(size_premium):.2%}")

        if size_premium is None:
            size_premium, tier_label = get_size_premium_interpolated(revenue)
            size_premium_source = f"duff_phelps_interpolated ({tier_label})"

        if METRICS_AVAILABLE:
            try:
                sme_size_premium_source_counter.labels(
                    source=size_premium_source, sme_class=sme_class
                ).inc()
            except Exception:
                pass

        # Company-specific risk: dynamic buildup
        company_risk, risk_breakdown = calculate_company_specific_risk(
            is_profitable=(ebitda is None or ebitda >= Decimal("0")),
            has_audit=has_audit,
            customer_concentration_pct=customer_concentration,
            industry=industry,
            owner_dependency_score=owner_dependency_score,
        )

        wacc = risk_free + equity_risk + size_premium + company_risk

        breakdown_lines = [
            f"Risk-free rate ({rf_source}): {risk_free*100:.1f}%",
            f"Equity risk premium (Damodaran 2025, {country_code}): {equity_risk*100:.1f}%",
            f"Size premium ({size_premium_source}): {size_premium*100:.1f}%",
        ]
        for item in risk_breakdown:
            breakdown_lines.append(f"  {item['factor']}: +{item['premium']*100:.1f}%")
        breakdown_lines.append(f"Total WACC: {wacc*100:.1f}%")

        rationale = (
            f"{sme_class.capitalize()} SME WACC buildup: "
            + " | ".join(breakdown_lines)
            + " per Trugman (2017) / Duff & Phelps (2024)"
        )

        logger.info(
            f"Calculated SME WACC (dynamic buildup)",
            revenue=float(revenue),
            sme_class=sme_class,
            wacc=float(wacc),
            risk_free=float(risk_free),
            equity_risk_premium=float(equity_risk),
            size_premium=float(size_premium),
            company_risk=float(company_risk),
            rf_source=rf_source,
        )

        return wacc, rationale


# Singleton instance
_sme_selector = SMEMultipleSelector()


def get_sme_selector() -> SMEMultipleSelector:
    """Get singleton SME multiple selector instance"""
    return _sme_selector
