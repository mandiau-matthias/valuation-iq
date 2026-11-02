"""
Hybrid Weight Calculator

Calculates DCF and Multiples weights for hybrid valuation using priority cascade:
1. business_context preferences (frontend override)
2. Database query (business_type_id UUID)
3. Hardcoded dictionary (string IDs)
4. Profitability-based default (47/53 or 53/47)

Then applies:
- Growth adjustments (high growth → favor multiples)
- Constraint ranges (business-type: 20-80%, default: 40-60%)
- Revenue-based enforcement (McKinsey standards for <€10M)
- Normalization (ensure weights sum to Decimal('1.0'))

@author UpSwitch CTO Team
@version 1.0.0
@date November 2025
"""

from decimal import Decimal
from typing import Optional, Tuple
from uuid import UUID

from src.domain.hybrid_types import MethodologyDecision, WeightResult
from src.domain.hybrid_weight_adjustments import HybridWeightAdjustmentService
from src.domain.interfaces.repository_protocol import BusinessTypesRepositoryProtocol
from src.domain.interfaces.request_protocol import ValuationRequestProtocol
from src.errors.error_types import ValidationError
from src.utils.decimal_helpers import to_decimal
from src.utils.exceptions import DatabaseError, DataQualityError, DCFCalculationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


def is_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _extract_advisor_blend_weights(
    request: object,
) -> Optional[Tuple[Decimal, Decimal]]:
    """Return a normalized ``(dcf_weight, multiples_weight)`` from an explicit
    advisor ``user_weights`` blend, or ``None``.

    Only returns a split when BOTH a DCF weight and at least one multiples-family
    weight are present — a genuine blend. Single-method selections (DCF-only or one
    multiples method) are routed by the methodology determiner, not here. DCF-family
    keys match ``dcf``; everything else (ebitda_multiple, revenue_multiple,
    sde_multiple, omzet_multiple, ev_ebitda, …) sums into the multiples leg.
    """
    user_weights = getattr(request, "user_weights", None)
    if not isinstance(user_weights, dict) or not user_weights:
        return None
    dcf_w = Decimal("0")
    mult_w = Decimal("0")
    for key, raw in user_weights.items():
        try:
            weight = Decimal(str(raw))
        except (ArithmeticError, ValueError, TypeError):
            continue
        if weight <= 0:
            continue
        if "dcf" in str(key).lower():
            dcf_w += weight
        else:
            mult_w += weight
    total = dcf_w + mult_w
    if total <= 0 or dcf_w <= 0 or mult_w <= 0:
        return None
    return (dcf_w / total, mult_w / total)


class HybridWeightCalculator:
    """
    Calculates DCF/Multiples weights with priority cascade and growth adjustments.

    Priority cascade (from ValuationOrchestrator logic):
    1. business_context preferences (frontend explicit choice)
    2. Database query (business_type_id UUID lookup)
    3. Hardcoded dictionary (string-based business_type_id)
    4. Profitability-based default (47/53 or 53/47)

    Then applies adjustments:
    - Growth profile adjustment
    - Constraint enforcement (20-80% or 40-60%)
    - Revenue-based enforcement (McKinsey standards)
    - Final normalization
    """

    # Hardcoded weights fallback (extracted from ValuationOrchestrator lines 1059-1085)
    HARDCODED_FALLBACK = {
        "bakery": {"dcf": Decimal("0.30"), "multiples": Decimal("0.70")},
        "restaurant": {"dcf": Decimal("0.35"), "multiples": Decimal("0.65")},
        "saas-platform": {"dcf": Decimal("0.30"), "multiples": Decimal("0.70")},
        "software-development": {"dcf": Decimal("0.30"), "multiples": Decimal("0.70")},
        "ecommerce-platform": {"dcf": Decimal("0.35"), "multiples": Decimal("0.65")},
        "ecommerce": {"dcf": Decimal("0.35"), "multiples": Decimal("0.65")},
        "construction": {"dcf": Decimal("0.40"), "multiples": Decimal("0.60")},
        "consulting-firm": {"dcf": Decimal("0.45"), "multiples": Decimal("0.55")},
        "marketing-agency": {"dcf": Decimal("0.45"), "multiples": Decimal("0.55")},
        "accounting-firm": {"dcf": Decimal("0.45"), "multiples": Decimal("0.55")},
        "legal-services": {"dcf": Decimal("0.40"), "multiples": Decimal("0.60")},
        "manufacturing-industrial": {"dcf": Decimal("0.45"), "multiples": Decimal("0.55")},
        "manufacturing": {"dcf": Decimal("0.50"), "multiples": Decimal("0.50")},
        "healthcare-services": {"dcf": Decimal("0.45"), "multiples": Decimal("0.55")},
        "healthcare": {"dcf": Decimal("0.50"), "multiples": Decimal("0.50")},
        "retail-store": {"dcf": Decimal("0.40"), "multiples": Decimal("0.60")},
        "retail": {"dcf": Decimal("0.40"), "multiples": Decimal("0.60")},
        "real-estate-services": {"dcf": Decimal("0.40"), "multiples": Decimal("0.60")},
        "logistics": {"dcf": Decimal("0.45"), "multiples": Decimal("0.55")},
        "transportation": {"dcf": Decimal("0.45"), "multiples": Decimal("0.55")},
        "fintech": {"dcf": Decimal("0.25"), "multiples": Decimal("0.75")},
        "fintech-lending": {"dcf": Decimal("0.25"), "multiples": Decimal("0.75")},
        "spa": {"dcf": Decimal("0.45"), "multiples": Decimal("0.55")},
        "fitness-studio": {"dcf": Decimal("0.40"), "multiples": Decimal("0.60")},
        "engineering": {"dcf": Decimal("0.50"), "multiples": Decimal("0.50")},
        "webdev": {"dcf": Decimal("0.35"), "multiples": Decimal("0.65")},
    }

    def __init__(
        self,
        business_types_repo: Optional[BusinessTypesRepositoryProtocol] = None,
    ):
        """
        Initialize weight calculator.

        Args:
            business_types_repo: Repository for database weight queries (optional)
        """
        self.logger = get_logger(__name__)
        self.weight_adjustments = HybridWeightAdjustmentService(self.logger)
        if business_types_repo is not None:
            self.business_types_repo = business_types_repo
        else:
            try:
                from src.database.business_types_repository import get_business_types_repository

                self.business_types_repo = get_business_types_repository()
            except Exception:
                self.logger.warning(
                    "Failed to initialize business_types_repo — DB-backed hybrid weights unavailable",
                    exc_info=True,
                )
                self.business_types_repo = None

    async def calculate_weights(
        self, request: ValuationRequestProtocol, methodology_decision: MethodologyDecision
    ) -> WeightResult:
        """
        Calculate DCF/Multiples weights with priority cascade and adjustments.

        Args:
            request: Valuation request
            methodology_decision: Methodology eligibility decision

        Returns:
            WeightResult with final weights and metadata
        """
        self.logger.info(
            "🎯 Starting weight calculation",
            extra={"company": request.company_name, "methodology": methodology_decision.value},
        )

        # Handle Multiples-only case
        if methodology_decision == MethodologyDecision.MULTIPLES_ONLY:
            self.logger.info("✅ Multiples-only: DCF=0%, Multiples=100%")
            return WeightResult(
                dcf_weight=Decimal("0.0"),
                multiples_weight=Decimal("1.0"),
                source="methodology_decision",
                adjustments_applied=["multiples_only"],
                rationale="DCF excluded by methodology decision",
                base_dcf_weight=Decimal("0.0"),
                base_multiples_weight=Decimal("1.0"),
            )

        # Advisor-explicit custom weighting (Waarderingssynthese). When the advisor
        # set an explicit DCF/Multiples blend, the engine BODY must use exactly that
        # split — the same weighting the cover synthesis honors — so the report shows
        # ONE number. Previously ``user_weights`` never reached the engine weighting,
        # so the body used the business-type default (e.g. bakery ≈27/73) while the
        # cover used the advisor's 70/30 (VAL-2026 two-brain). Honor it verbatim,
        # bypassing the business-type cascade, growth tilt, constraints, and revenue
        # guardrail — the advisor's deliberate choice is authoritative (the <€2.5M
        # guardrail is already exempted for explicit intent in _apply_revenue_enforcement).
        advisor_blend = _extract_advisor_blend_weights(request)
        if advisor_blend is not None:
            adv_dcf, adv_mult = advisor_blend
            self.logger.info(
                "🎯 Advisor-explicit user_weights honored as engine base weights "
                "(body == cover synthesis)",
                extra={
                    "dcf_weight": float(adv_dcf),
                    "multiples_weight": float(adv_mult),
                },
            )
            return WeightResult(
                dcf_weight=adv_dcf,
                multiples_weight=adv_mult,
                source="user_weights",
                adjustments_applied=["advisor_explicit_weights"],
                rationale=(
                    f"Advisor-specified weighting → DCF: {adv_dcf:.0%}, "
                    f"Multiples: {adv_mult:.0%}"
                ),
                base_dcf_weight=adv_dcf,
                base_multiples_weight=adv_mult,
            )

        # Get base weights using priority cascade
        self.logger.debug(
            "🔍 Getting base weights using priority cascade",
            extra={
                "priority_order": [
                    "1. business_context preferences (frontend override)",
                    "2. Database query (business_type_id UUID)",
                    "3. Hardcoded dictionary (string IDs)",
                    "4. Profitability-based default (47/53 or 53/47)",
                ]
            },
        )

        base_weights, weight_source = await self._get_base_weights(request)

        # Store original base weights
        base_dcf_weight = base_weights["dcf"]
        base_multiples_weight = base_weights["multiples"]

        self.logger.info(
            "✅ Base weights determined",
            extra={
                "weight_source": weight_source,
                "base_dcf_weight": base_dcf_weight,
                "base_multiples_weight": base_multiples_weight,
                "base_sum": base_dcf_weight + base_multiples_weight,
            },
        )

        # Initialize working weights
        dcf_weight = base_weights["dcf"]
        multiples_weight = base_weights["multiples"]
        adjustments_applied = []

        # Determine constraint ranges based on weight source
        if weight_source in [
            "titan_enrichment",
            "business_context",
            "repository",
            "hardcoded_dict",
        ]:
            # Business-type weights: softer constraints to preserve specificity
            # titan_enrichment = from Delphi/business_types DB via Titan (HIGHEST priority)
            min_weight, max_weight = Decimal("0.20"), Decimal("0.80")
            self.logger.debug(
                "📐 Using business-type constraints (20-80%)",
                extra={
                    "weight_source": weight_source,
                    "rationale": "Softer constraints to preserve business-type specificity",
                    "is_titan_enrichment": weight_source == "titan_enrichment",
                },
            )
        else:
            # Default weights: tighter constraints
            min_weight, max_weight = Decimal("0.40"), Decimal("0.60")
            self.logger.debug(
                "📐 Using default constraints (40-60%)",
                extra={
                    "weight_source": weight_source,
                    "rationale": "Tighter constraints for default weights",
                },
            )

        # Apply growth adjustments
        self.logger.debug(
            "📈 Applying growth profile adjustments",
            extra={"note": "High growth → favor multiples, Declining → favor DCF"},
        )

        dcf_weight_before_growth = dcf_weight
        multiples_weight_before_growth = multiples_weight

        dcf_weight, multiples_weight, growth_adjustments = self._apply_growth_adjustments(
            request, dcf_weight, multiples_weight, weight_source, min_weight, max_weight
        )
        adjustments_applied.extend(growth_adjustments)

        if growth_adjustments:
            self.logger.info(
                "✅ Growth adjustments applied",
                extra={
                    "dcf_weight_before": dcf_weight_before_growth,
                    "dcf_weight_after": dcf_weight,
                    "multiples_weight_before": multiples_weight_before_growth,
                    "multiples_weight_after": multiples_weight,
                    "adjustments": growth_adjustments,
                },
            )

        # Apply constraints
        dcf_weight_before_constraints = dcf_weight
        multiples_weight_before_constraints = multiples_weight

        dcf_weight = max(min_weight, min(max_weight, dcf_weight))
        multiples_weight = max(min_weight, min(max_weight, multiples_weight))

        if growth_adjustments:
            adjustments_applied.append(f"constraints_{min_weight:.0%}-{max_weight:.0%}")

        if (
            dcf_weight != dcf_weight_before_constraints
            or multiples_weight != multiples_weight_before_constraints
        ):
            self.logger.debug(
                "✅ Constraints applied",
                extra={
                    "dcf_weight_before": dcf_weight_before_constraints,
                    "dcf_weight_after": dcf_weight,
                    "multiples_weight_before": multiples_weight_before_constraints,
                    "multiples_weight_after": multiples_weight,
                    "constraint_range": f"{min_weight:.0%}-{max_weight:.0%}",
                },
            )

        # Apply revenue-based enforcement (McKinsey standards)
        self.logger.debug(
            "💰 Applying revenue-based enforcement (McKinsey standards)",
            extra={
                "revenue": request.current_year_data.revenue,
                "note": "Revenue < €10M: DCF weight capped per McKinsey standards",
            },
        )

        dcf_weight_before_revenue = dcf_weight
        multiples_weight_before_revenue = multiples_weight

        dcf_weight, multiples_weight, revenue_enforcement = self._apply_revenue_enforcement(
            request, dcf_weight, multiples_weight, methodology_decision
        )
        if revenue_enforcement:
            adjustments_applied.append(revenue_enforcement)
            self.logger.info(
                "✅ Revenue-based enforcement applied",
                extra={
                    "dcf_weight_before": dcf_weight_before_revenue,
                    "dcf_weight_after": dcf_weight,
                    "multiples_weight_before": multiples_weight_before_revenue,
                    "multiples_weight_after": multiples_weight,
                    "enforcement": revenue_enforcement,
                },
            )

        # Normalize to ensure sum = 1.0
        self.logger.debug(
            "⚖️  Normalizing weights to ensure sum = 1.0",
            extra={
                "dcf_weight_before": dcf_weight,
                "multiples_weight_before": multiples_weight,
                "sum_before": dcf_weight + multiples_weight,
            },
        )

        dcf_weight_before_norm = dcf_weight
        multiples_weight_before_norm = multiples_weight

        dcf_weight, multiples_weight = self._normalize_weights(dcf_weight, multiples_weight)
        adjustments_applied.append("normalized")

        if dcf_weight != dcf_weight_before_norm or multiples_weight != multiples_weight_before_norm:
            self.logger.debug(
                "✅ Weights normalized",
                extra={
                    "dcf_weight_before": dcf_weight_before_norm,
                    "dcf_weight_after": dcf_weight,
                    "multiples_weight_before": multiples_weight_before_norm,
                    "multiples_weight_after": multiples_weight,
                    "sum_after": dcf_weight + multiples_weight,
                },
            )

        # Build rationale
        rationale = self._build_rationale(
            weight_source, base_dcf_weight, dcf_weight, multiples_weight, adjustments_applied
        )

        # ============================================================================
        # BANK-GRADE LOGGING: Methodology weight source summary
        # ============================================================================
        source_priority_label = {
            "titan_enrichment": "TITAN (Priority 0 - HIGHEST)",
            "business_context": "Frontend Preferences (Priority 1)",
            "repository": "Synced Cache Repository (Priority 2)",
            "hardcoded_dict": "Hardcoded Dictionary (Priority 3)",
            "profitability_default": "Profitability Default (Priority 4)",
            "methodology_decision": "Methodology Decision Override",
        }.get(weight_source, f"Unknown ({weight_source})")

        self.logger.info(
            f"✅ METHODOLOGY WEIGHTS COMPLETE - Source: {source_priority_label}",
            extra={
                "dcf_weight": round(dcf_weight, 3),
                "multiples_weight": round(multiples_weight, 3),
                "source": weight_source,
                "source_priority": source_priority_label,
                "is_titan_source": weight_source == "titan_enrichment",
                "adjustments_count": len(adjustments_applied),
                "adjustments_applied": adjustments_applied,
                "base_dcf_weight": base_dcf_weight,
                "base_multiples_weight": base_multiples_weight,
                "final_sum": dcf_weight + multiples_weight,
                "rationale": rationale,
            },
        )

        return WeightResult(
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            source=weight_source,
            adjustments_applied=adjustments_applied,
            rationale=rationale,
            base_dcf_weight=base_dcf_weight,
            base_multiples_weight=base_multiples_weight,
        )

    async def _get_base_weights(
        self, request: ValuationRequestProtocol
    ) -> Tuple[dict[str, Decimal], str]:
        """
        Get base weights using priority cascade.

        Priority:
        0. Titan-provided valuation_preferences (HIGHEST - from business_types DB via Titan)
        1. business_context preferences (frontend override)
        2. Database query (business_type_id UUID)
        3. Hardcoded dictionary (string IDs)
        4. Profitability-based default

        Returns:
            Tuple of (weights_dict, source_string)
        """
        business_context = request.business_context or {}
        business_type_id = request.business_type_id or business_context.get("business_type_id")
        revenue = request.current_year_data.revenue or Decimal("0")
        ebitda = request.current_year_data.ebitda or Decimal("0")

        # ==========================================================================
        # PRIORITY 0: Titan-provided valuation_preferences (HIGHEST PRIORITY)
        # ==========================================================================
        # When Titan enriches the request with business type data from Delphi,
        # it includes valuation_preferences with dcf_preference and multiples_preference.
        # These are the authoritative weights from the business_types database.
        # ==========================================================================
        titan_prefs = getattr(request, "valuation_preferences", None)
        if titan_prefs and isinstance(titan_prefs, dict):
            dcf_pref = titan_prefs.get("dcf_preference")
            multiples_pref = titan_prefs.get("multiples_preference")

            # Both preferences must be present, valid, and numeric
            if dcf_pref is not None and multiples_pref is not None:
                try:
                    dcf_weight = to_decimal(dcf_pref)
                    multiples_weight = to_decimal(multiples_pref)
                except (ValueError, TypeError, ArithmeticError):
                    self.logger.debug(
                        "Titan preferences are non-numeric, skipping Priority 0",
                        extra={"dcf_preference": dcf_pref, "multiples_preference": multiples_pref},
                    )
                    dcf_weight = None
                    multiples_weight = None

                if dcf_weight is not None and multiples_weight is not None:
                    # Ensure they sum to 1.0 (normalize if needed)
                    total = dcf_weight + multiples_weight
                    if total > 0:
                        if abs(total - Decimal("1.0")) > Decimal("0.01"):
                            dcf_weight = dcf_weight / total
                            multiples_weight = multiples_weight / total

                        self.logger.info(
                            "🎯 PRIORITY 0: Using TITAN-PROVIDED valuation preferences (from Upswitch Index/business-type policy)",
                            extra={
                                "business_type_id": business_type_id,
                                "dcf_preference": dcf_pref,
                                "multiples_preference": multiples_pref,
                                "dcf_weight": dcf_weight,
                                "multiples_weight": multiples_weight,
                                "source": "titan_enrichment",
                                "owner_dependency_impact": titan_prefs.get(
                                    "owner_dependency_impact"
                                ),
                                "preferred_multiples": titan_prefs.get("preferred_multiples"),
                                "primary_model": titan_prefs.get("primary_model"),
                            },
                        )
                        return {
                            "dcf": dcf_weight,
                            "multiples": multiples_weight,
                        }, "titan_enrichment"

        # Priority 1: business_context preferences (frontend explicit choice)
        if business_context and "preferences" in business_context:
            prefs = business_context["preferences"]
            dcf_pref_val = prefs.get("dcf_weight")
            mult_pref_val = prefs.get("multiples_weight")
            if dcf_pref_val is not None and mult_pref_val is not None:
                dcf_dec = to_decimal(dcf_pref_val)
                mult_dec = to_decimal(mult_pref_val)
                if dcf_dec < Decimal("0"):
                    dcf_dec = Decimal("0")
                if mult_dec < Decimal("0"):
                    mult_dec = Decimal("0")
                pref_total = dcf_dec + mult_dec
                if pref_total > Decimal("0") and abs(pref_total - Decimal("1")) > Decimal("0.01"):
                    dcf_dec = (dcf_dec / pref_total).quantize(Decimal("0.0001"))
                    mult_dec = Decimal("1") - dcf_dec
                elif pref_total <= Decimal("0"):
                    dcf_dec = Decimal("0.3")
                    mult_dec = Decimal("0.7")
                self.logger.info(
                    "Priority 1: Using business_context preferences (validated)",
                    extra={
                        "dcf_weight": float(dcf_dec),
                        "multiples_weight": float(mult_dec),
                        "raw_dcf": dcf_pref_val,
                        "raw_mult": mult_pref_val,
                    },
                )
                return {
                    "dcf": dcf_dec,
                    "multiples": mult_dec,
                }, "business_context"

        # Priority 2: Repository-backed business type weights (cache-backed in stateless mode)
        if business_type_id and self.business_types_repo:
            try:
                weights_dict = await self.business_types_repo.get_hybrid_weights(business_type_id)

                if weights_dict:
                    dcf_w = weights_dict.get("dcf")
                    mult_w = weights_dict.get("multiples")
                    if dcf_w is not None and mult_w is not None:
                        self.logger.info(
                            "🎯 Priority 2: Using repository-backed business type weights",
                            extra={
                                "business_type_id": business_type_id,
                                "dcf_weight": dcf_w,
                                "multiples_weight": mult_w,
                                "source": "repository",
                            },
                        )
                        return {"dcf": dcf_w, "multiples": mult_w}, "repository"
            except (DatabaseError, DataQualityError, ValidationError):
                raise  # Re-raise specific errors
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                self.logger.warning(
                    f"Repository weight lookup failed: {e}",
                    extra={"error_type": type(e).__name__, "error": str(e)},
                )
            except DCFCalculationError as e:
                self.logger.warning(
                    f"Unexpected error in repository weight lookup: {e}",
                    extra={"error_type": type(e).__name__, "error": str(e)},
                )

        # Priority 3: Hardcoded dictionary (string-based business_type_id)
        if business_type_id and not is_uuid(business_type_id):
            if business_type_id in self.HARDCODED_FALLBACK:
                weights = self.HARDCODED_FALLBACK[business_type_id]
                self.logger.info(
                    "🎯 Priority 3: Using hardcoded weights",
                    extra={
                        "business_type_id": business_type_id,
                        "dcf_weight": weights["dcf"],
                        "multiples_weight": weights["multiples"],
                    },
                )
                return weights, "hardcoded_dict"

        # Priority 4: Profitability-based default
        if ebitda > 0 and revenue > 0:
            # Profitable companies: slight preference for multiples
            dcf_weight = Decimal("0.47")
            multiples_weight = Decimal("0.53")
        else:
            # Unprofitable companies: favor DCF slightly
            dcf_weight = Decimal("0.53")
            multiples_weight = Decimal("0.47")

        self.logger.info(
            "🎯 Priority 4: Using profitability default",
            extra={
                "dcf_weight": dcf_weight,
                "multiples_weight": multiples_weight,
                "is_profitable": ebitda > 0,
            },
        )

        return {"dcf": dcf_weight, "multiples": multiples_weight}, "profitability_default"

    def _apply_growth_adjustments(
        self,
        request: ValuationRequestProtocol,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        weight_source: str,
        min_weight: Decimal,
        max_weight: Decimal,
    ) -> Tuple[Decimal, Decimal, list]:
        return self.weight_adjustments.apply_growth_adjustments(
            request, dcf_weight, multiples_weight, weight_source, min_weight, max_weight
        )

    def _apply_revenue_enforcement(
        self,
        request: ValuationRequestProtocol,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        methodology_decision: MethodologyDecision,
    ) -> Tuple[Decimal, Decimal, Optional[str]]:
        return self.weight_adjustments.apply_revenue_enforcement(
            request, dcf_weight, multiples_weight, methodology_decision
        )

    def _normalize_weights(
        self, dcf_weight: Decimal, multiples_weight: Decimal
    ) -> Tuple[Decimal, Decimal]:
        return self.weight_adjustments.normalize_weights(dcf_weight, multiples_weight)

    def _build_rationale(
        self,
        weight_source: str,
        base_dcf: Decimal,
        final_dcf: Decimal,
        final_multiples: Decimal,
        adjustments: list,
    ) -> str:
        return self.weight_adjustments.build_rationale(
            weight_source, base_dcf, final_dcf, final_multiples, adjustments
        )
