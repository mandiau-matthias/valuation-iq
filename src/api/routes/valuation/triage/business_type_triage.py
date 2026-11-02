"""
Business Type Triage Logic

This module provides business-type-specific triage logic to determine which
calculation steps should execute based on business characteristics and data availability.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from src.database.business_types_repository import BusinessTypeMetadata

from src.api.routes.valuation.triage.business_type_category_resolver import (
    map_industry_text_to_category,
    resolve_business_type_category,
)
from src.api.routes.valuation.triage.business_type_taxonomy import (
    INDUSTRY_CATEGORY_FALLBACKS,
    INDUSTRY_TEXT_CATEGORY_RULES,
    BusinessTypeCategory,
    StepExecutionRule,
)
from src.api.routes.valuation.triage.business_type_triage_config import (
    build_business_type_categories,
    build_category_id_to_enum,
    build_liquidity_discount_adjustments,
    build_size_discount_adjustments,
    build_step_execution_rules,
)
from src.api.routes.valuation.triage.methodology_selection import (
    REVENUE_THRESHOLD_MEDIUM,
    REVENUE_THRESHOLD_MICRO,
    REVENUE_THRESHOLD_SMALL,
    MethodologyDecision,
    ValuationMethodology,
    _calculate_asset_based_suitability,
    _calculate_dcf_suitability,
    _calculate_ebitda_suitability,
    _calculate_sde_suitability,
    _request_owner_count,
    _request_revenue,
    select_business_type_methodology,
)
from src.api.routes.valuation.triage.step_execution_policy import (
    check_conditional_asset_based,
    check_conditional_business_type,
    check_conditional_data,
    check_conditional_sde,
    check_conditional_size,
)
from src.api.schemas import ValuationRequest
from src.errors import ConfigurationError, DatabaseError, ValidationError
from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "BusinessTypeCategory",
    "BusinessTypeTriageEngine",
    "MethodologyDecision",
    "REVENUE_THRESHOLD_MICRO",
    "REVENUE_THRESHOLD_MEDIUM",
    "REVENUE_THRESHOLD_SMALL",
    "StepExecutionRule",
    "ValuationMethodology",
    "_calculate_asset_based_suitability",
    "_calculate_dcf_suitability",
    "_calculate_ebitda_suitability",
    "_calculate_sde_suitability",
    "_request_owner_count",
    "_request_revenue",
    "select_business_type_methodology",
]

# Metrics import (optional - Prometheus may not be available)
try:
    from src.api.routes.valuation.metrics import business_type_industry_derivations

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("⚠️ Prometheus metrics not available for business type triage")


class BusinessTypeTriageEngine:
    """
    Business-type-aware triage engine that determines step execution rules
    based on business characteristics and data availability.

    This engine provides intelligent routing for different business types:
    - SaaS/Software: Higher multiples, less owner dependency focus
    - Professional Services: Owner dependency critical
    - Retail/Food: Revenue-based, location-dependent
    - Manufacturing: Asset-heavy, EBITDA-focused
    - Construction: Project-based, volatile cash flows
    """

    BUSINESS_TYPE_CATEGORIES: Dict[str, BusinessTypeCategory] = build_business_type_categories(
        BusinessTypeCategory
    )
    STEP_EXECUTION_RULES: Dict[BusinessTypeCategory, Dict[float, StepExecutionRule]] = (
        build_step_execution_rules(BusinessTypeCategory, StepExecutionRule)
    )
    SIZE_DISCOUNT_ADJUSTMENTS: Dict[BusinessTypeCategory, Dict[str, Decimal]] = (
        build_size_discount_adjustments(BusinessTypeCategory)
    )
    LIQUIDITY_DISCOUNT_ADJUSTMENTS: Dict[BusinessTypeCategory, Dict[str, Decimal]] = (
        build_liquidity_discount_adjustments(BusinessTypeCategory)
    )
    CATEGORY_ID_TO_ENUM: Dict[str, BusinessTypeCategory] = build_category_id_to_enum(
        BusinessTypeCategory
    )

    def __init__(self):
        self.logger = logger
        # Lazy import to avoid circular dependencies
        self._metadata_service = None

    def _get_metadata_service(self):
        """Lazy load metadata service to avoid circular dependencies."""
        if self._metadata_service is None:
            try:
                from src.services.business_type_metadata_service import (
                    get_business_type_metadata_service,
                )

                self._metadata_service = get_business_type_metadata_service()
            except (ConfigurationError, ImportError, AttributeError, ValueError, TypeError) as e:
                self.logger.warning(
                    f"Could not load metadata service: {e}", extra={"error_type": type(e).__name__}
                )
                return None
        return self._metadata_service

    def get_business_type_metadata(
        self,
        business_type_id: Optional[str],
        business_model: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> Optional["BusinessTypeMetadata"]:
        """
        Get full business type metadata from database.

        Uses BusinessTypeMetadataService for caching and fallbacks.

        Args:
            business_type_id: Business type ID
            business_model: Optional business model (for fallback)
            industry: Optional industry (for fallback)

        Returns:
            BusinessTypeMetadata or None if not found
        """
        metadata_service = self._get_metadata_service()
        if metadata_service:
            return metadata_service.get_business_type_metadata(business_type_id)
        return None

    def get_business_type_category(
        self,
        business_type_id: Optional[str],
        business_model: Optional[str],
        industry: Optional[str],
        category_id: Optional[str] = None,
    ) -> BusinessTypeCategory:
        """
        Determine business type category (CALCULATOR FLOW - EXACT MATCH).

        ✅ EXACT MATCH: This flow receives pre-validated business_type_id from form/dropdown.
        ❌ NO FUZZY: business_type_id is exact UUID, database lookup is exact (not fuzzy).

        The business_type_id comes from:
        - Manual flow: Dropdown selection (pre-validated)
        - Conversational flow: Already validated by BusinessTypeRegistryHandler

        Priority (all EXACT lookups, no fuzzy matching):
        0. category_id (from Titan enrichment - HIGHEST PRIORITY, database-sourced)
        1. business_type_id (exact match in static mapping)
        2. business_type_id (exact database lookup via industry field - PRIMARY)
        3. business_type_id (exact database lookup via industry_mapping - SECONDARY)
        4. business_type_id (exact database lookup via sector - TERTIARY)
        5. business_model (fallback match)
        6. industry (fallback category match)
        7. OTHER (fallback)

        This method is robust and handles:
        - All current business type catalog from database (exact lookup)
        - Manual flow business types (pre-validated UUID)
        - Conversational flow business types (pre-validated by fuzzy handler)
        - Unknown business types (graceful fallback to OTHER)
        """
        return resolve_business_type_category(
            business_type_id=business_type_id,
            business_model=business_model,
            industry=industry,
            category_id=category_id,
            category_id_to_enum=self.CATEGORY_ID_TO_ENUM,
            business_type_categories=self.BUSINESS_TYPE_CATEGORIES,
            industry_category_fallbacks=INDUSTRY_CATEGORY_FALLBACKS,
            map_industry_to_category=lambda industry_text: map_industry_text_to_category(
                industry_text,
                INDUSTRY_TEXT_CATEGORY_RULES,
            ),
            logger=self.logger,
            derivation_metric=(business_type_industry_derivations if METRICS_AVAILABLE else None),
            other_category=BusinessTypeCategory.OTHER,
        )

    def should_execute_step(
        self,
        step_number: int,
        request: ValuationRequest,
        previous_results: Dict[int, Any],
        rule: StepExecutionRule,
    ) -> bool:
        """
        Determine if a step should execute based on execution rule.

        This method provides robust, business-type-aware conditional execution logic
        that handles edge cases and missing data gracefully.

        Args:
            step_number: The step number (0-10)
            request: The valuation request
            previous_results: Results from previous steps
            rule: The execution rule for this step

        Returns:
            True if step should execute, False otherwise
        """
        try:
            if rule == StepExecutionRule.ALWAYS:
                return True

            if rule == StepExecutionRule.NEVER:
                return False

            if rule == StepExecutionRule.CONDITIONAL_DATA:
                return self._check_conditional_data(step_number, request, previous_results)

            if rule == StepExecutionRule.CONDITIONAL_BUSINESS_TYPE:
                return self._check_conditional_business_type(step_number, request, previous_results)

            if rule == StepExecutionRule.CONDITIONAL_SIZE:
                return self._check_conditional_size(step_number, request, previous_results)

            if rule == StepExecutionRule.CONDITIONAL_SDE:
                return self._check_conditional_sde(step_number, request, previous_results)

            if rule == StepExecutionRule.CONDITIONAL_ASSET_BASED:
                return self._check_conditional_asset_based(step_number, request, previous_results)

            # Default: execute (fail-safe)
            logger.warning(
                f"Unknown execution rule for step {step_number}, defaulting to execute",
                extra={"step_number": step_number, "rule": rule.value},
            )
            return True

        except (ValidationError, ValueError, TypeError, AttributeError, KeyError) as e:
            # Fail-safe: log error but allow execution to continue
            logger.error(
                f"Error in should_execute_step for step {step_number}: {e}",
                extra={
                    "step_number": step_number,
                    "rule": rule.value,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            # Default to True to avoid blocking execution
            return True

    def _request_category(self, request: ValuationRequest) -> BusinessTypeCategory:
        return self.get_business_type_category(
            getattr(request, "business_type_id", None),
            getattr(request, "business_model", None),
            getattr(request, "industry", None),
            category_id=getattr(request, "category_id", None),
        )

    def _check_conditional_data(
        self, step_number: int, request: ValuationRequest, previous_results: Dict[int, Any]
    ) -> bool:
        return check_conditional_data(
            step_number,
            request,
            previous_results,
            logger=self.logger,
        )

    def _check_conditional_business_type(
        self, step_number: int, request: ValuationRequest, previous_results: Dict[int, Any]
    ) -> bool:
        return check_conditional_business_type(
            step_number,
            request,
            previous_results,
            category_resolver=lambda: self._request_category(request),
            logger=self.logger,
        )

    def _check_conditional_size(
        self, step_number: int, request: ValuationRequest, previous_results: Dict[int, Any]
    ) -> bool:
        return check_conditional_size(
            step_number,
            request,
            previous_results,
            logger=self.logger,
        )

    def _check_conditional_sde(
        self, step_number: float, request: ValuationRequest, previous_results: Dict[int, Any]
    ) -> bool:
        return check_conditional_sde(
            step_number,
            request,
            previous_results,
            category_resolver=lambda: self._request_category(request),
            logger=self.logger,
        )

    def _check_conditional_asset_based(
        self, step_number: float, request: ValuationRequest, previous_results: Dict[int, Any]
    ) -> bool:
        return check_conditional_asset_based(
            step_number,
            request,
            previous_results,
            category_resolver=lambda: self._request_category(request),
            logger=self.logger,
        )

    def select_methodology(
        self,
        request: ValuationRequest,
    ) -> MethodologyDecision:
        """Select the optimal valuation methodology based on business characteristics."""
        category = self.get_business_type_category(
            getattr(request, "business_type_id", None),
            getattr(request, "business_model", None),
            getattr(request, "industry", None),
            category_id=getattr(request, "category_id", None),
        )
        return select_business_type_methodology(request=request, category=category)

    def get_step_execution_rule(
        self, step_number: int, request: ValuationRequest
    ) -> StepExecutionRule:
        """
        Get the execution rule for a specific step based on business type.

        Args:
            step_number: The step number (0-10)
            request: The valuation request

        Returns:
            StepExecutionRule for this step
        """
        category = self.get_business_type_category(
            getattr(request, "business_type_id", None),
            getattr(request, "business_model", None),
            getattr(request, "industry", None),
            category_id=getattr(request, "category_id", None),
        )

        rules = self.STEP_EXECUTION_RULES.get(
            category, self.STEP_EXECUTION_RULES[BusinessTypeCategory.OTHER]
        )
        return rules.get(step_number, StepExecutionRule.ALWAYS)

    def get_size_discount_adjustment(
        self,
        business_type_category: BusinessTypeCategory,
        revenue: Decimal,
        business_type_id: Optional[str] = None,
        valuation_preferences: Optional[Dict[str, Any]] = None,
    ) -> Decimal:
        """
        Get business-type-specific size discount adjustment multiplier.

        Args:
            business_type_category: The business type category
            revenue: Company revenue
            business_type_id: Optional business type ID for database lookup
            valuation_preferences: Titan-enriched valuation preferences dict

        Returns:
            Multiplier to apply to base size discount (Decimal('1.0') = no adjustment)
        """
        adjustments = self.SIZE_DISCOUNT_ADJUSTMENTS.get(business_type_category, None)

        if adjustments is None and (valuation_preferences or business_type_id):
            try:
                metadata_service = self._get_metadata_service()
                if metadata_service:
                    calibration_data = (
                        valuation_preferences if isinstance(valuation_preferences, dict) else None
                    )
                    owner_impact = metadata_service.get_owner_dependency_impact(calibration_data)
                    # Higher owner dependency = higher size discount
                    # Formula: 1.0 + (owner_impact - 0.5) * 0.2
                    # owner_impact 0.0 → multiplier 0.9 (less discount)
                    # owner_impact 0.5 → multiplier 1.0 (standard)
                    # owner_impact 1.0 → multiplier 1.1 (more discount)
                    calculated_multiplier = Decimal("1.0") + (
                        owner_impact - Decimal("0.5")
                    ) * Decimal("0.2")

                    # Determine size tier
                    if revenue < 1_000_000:
                        multiplier = calculated_multiplier
                    elif revenue < 5_000_000:
                        multiplier = Decimal("1.0") + (
                            calculated_multiplier - Decimal("1.0")
                        ) * Decimal(
                            "0.5"
                        )  # Less adjustment for small
                    else:
                        multiplier = Decimal("1.0")  # No adjustment for mid+

                    self.logger.debug(
                        f"Size discount adjustment calculated from database: {business_type_id} → {multiplier:.2f}",
                        extra={
                            "business_type_id": business_type_id,
                            "owner_dependency_impact": owner_impact,
                            "calculated_multiplier": multiplier,
                            "revenue": revenue,
                        },
                    )
                    return multiplier
            except (DatabaseError, ValueError, TypeError, AttributeError, KeyError) as e:
                self.logger.debug(
                    f"Database lookup failed for business_type size: {e}",
                    extra={"business_type_id": business_type_id, "error_type": type(e).__name__},
                )

        # Use static mapping (or default if not found)
        if adjustments is None:
            adjustments = {
                "micro_multiplier": Decimal("1.0"),
                "small_multiplier": Decimal("1.0"),
                "mid_multiplier": Decimal("1.0"),
            }

        if revenue < 1_000_000:
            return adjustments.get("micro_multiplier", Decimal("1.0"))
        elif revenue < 5_000_000:
            return adjustments.get("small_multiplier", Decimal("1.0"))
        else:
            return adjustments.get("mid_multiplier", Decimal("1.0"))

    def get_liquidity_discount_base(self, business_type_category: BusinessTypeCategory) -> Decimal:
        """
        Get business-type-specific base liquidity discount.

        Args:
            business_type_category: The business type category

        Returns:
            Base liquidity discount percentage (negative value)
        """
        adjustments = self.LIQUIDITY_DISCOUNT_ADJUSTMENTS.get(
            business_type_category,
            {"base_discount": -Decimal("0.15"), "high_margin_bonus": Decimal("0.02")},
        )
        return adjustments.get("base_discount", -Decimal("0.15"))

    def get_liquidity_discount_margin_bonus(
        self, business_type_category: BusinessTypeCategory
    ) -> Decimal:
        """
        Get business-type-specific margin bonus for liquidity discount.

        Args:
            business_type_category: The business type category

        Returns:
            Margin bonus percentage (positive value)
        """
        adjustments = self.LIQUIDITY_DISCOUNT_ADJUSTMENTS.get(
            business_type_category,
            {"base_discount": -Decimal("0.15"), "high_margin_bonus": Decimal("0.02")},
        )
        return adjustments.get("high_margin_bonus", Decimal("0.02"))
