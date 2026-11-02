"""
Owner Dependency Assessment Engine

Calculates owner dependency risk and valuation adjustments for SME businesses.
Implements the 12-factor assessment methodology to quantify key person risk.

Algorithm:
1. Convert each factor's DependencyLevel to numeric score (0-100)
2. Apply inverse scoring for factors 8-12
3. Calculate weighted average (all factors weighted equally)
4. Map overall score to valuation adjustment using tiered model
5. Generate risk assessment and recommendations

Research basis:
- Damodaran (2012): Key person discounts for private companies
- SBVS (Small Business Valuation Standards)
- Industry best practices for transition risk assessment
"""

from decimal import Decimal
from typing import Any, List, Optional, Tuple

from src.domain.models import FinancialData
from src.domain.owner_models.multi_owner_resolution import (
    SOURCE_MULTI_OWNER_COMPOSITE,
    is_multi_owner_v1_enabled,
    resolve_transferability_index,
)
from src.domain.owner_models.owner_dependency import (
    DependencyLevel,
    OwnerDependencyFactors,
    OwnerDependencyResult,
)
from src.errors.error_types import DatabaseError, DataQualityError
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OwnerDependencyEngine:
    """
    Engine for calculating owner dependency scores and valuation adjustments

    The engine:
    1. Scores 12 factors (0-100 scale)
    2. Identifies key risks
    3. Calculates valuation adjustment
    4. Tracks all calculations in transparency system
    """

    # Scoring mappings for dependency levels
    DEPENDENCY_SCORES = {
        DependencyLevel.VERY_HIGH: 10,  # Critical dependency
        DependencyLevel.HIGH: 30,  # Significant dependency
        DependencyLevel.MEDIUM: 50,  # Moderate dependency
        DependencyLevel.LOW: 75,  # Low dependency
        DependencyLevel.VERY_LOW: 95,  # Minimal dependency
    }

    # Inverse factors (where high dependency = good)
    INVERSE_FACTORS = {
        "process_documentation",
        "team_capability",
        "succession_planning",
        "business_scalability",
        "contract_transferability",
    }

    # Factor weights (equal weighting)
    FACTOR_WEIGHTS = {
        "client_concentration": Decimal("8.33"),
        "operational_knowledge": Decimal("8.33"),
        "sales_relationship": Decimal("8.33"),
        "technical_expertise": Decimal("8.33"),
        "industry_network": Decimal("8.33"),
        "decision_making": Decimal("8.33"),
        "brand_reputation": Decimal("8.33"),
        "process_documentation": Decimal("8.33"),
        "team_capability": Decimal("8.33"),
        "succession_planning": Decimal("8.33"),
        "business_scalability": Decimal("8.33"),
        "contract_transferability": Decimal("8.33"),
    }

    def __init__(
        self,
        financial_data: Optional[FinancialData] = None,
        transparency_collector: Optional[Any] = None,
    ):
        """
        Initialize Owner Dependency Engine

        Args:
            financial_data: Company financial data (used for context in recommendations)
            transparency_collector: Collector for transparency tracking
        """
        self.financial_data = financial_data
        self.transparency_collector = transparency_collector
        logger.info("Owner Dependency Engine initialized")

    def calculate_dependency_score(
        self,
        factors: OwnerDependencyFactors,
        *,
        equity_value_mid: Optional[Decimal] = None,
        owner_hours_per_week: Optional[int] = None,
        eligible_methods: Optional[List[str]] = None,
        composite_transferability_index: Optional[float] = None,
        owner_count: int = 1,
    ) -> OwnerDependencyResult:
        """
        Calculate overall owner dependency score and valuation adjustment

        PHASE 2 ENHANCEMENT: Now integrates quantitative owner/FTE ratio with
        qualitative 12-factor assessment for more accurate risk evaluation.

        TRANSFERABILITY v2 (BET-180 follow-up): when `equity_value_mid` is
        supplied (i.e. the synthesizer has converged on a baseline equity
        figure), additionally builds the 5-factor decomposition + buyer
        profile + gap + per-method incidence + narrative cascade and
        stamps it on the result as `transferability_profile`. The headline
        `valuation_adjustment` is unchanged; v2 is purely additive metadata
        for the renderer. Back-compat callers omit the new kwargs and
        receive the v1-shaped result.

        Args:
            factors: 12-factor dependency assessment (may include owner_fte_ratio)
            equity_value_mid: optional pre-OD equity baseline; drives the
                buyer-archetype heuristic. Omit to skip the v2 profile.
            owner_hours_per_week: optional owner self-reported intensity.
                When omitted the gap calc uses a pessimistic 60 hrs/wk
                default so the gap is never silently understated.
            eligible_methods: optional list of method ids the engine ran
                (e.g. ["ebitda_multiple", "sde"]). Drives the blended
                incidence figure on the cascade. Omit to use all
                non-zero-coefficient methods.

        Returns:
            Complete owner dependency result with adjustment
        """
        logger.info("Calculating owner dependency score")

        # Step 1: Convert factors to numeric scores
        factor_scores = self._calculate_all_factor_scores(factors)

        # Step 2: Apply owner/FTE ratio enhancement if available
        if factors.owner_fte_ratio is not None:
            logger.info(
                "Applying owner/FTE ratio enhancement to dependency score",
                owner_fte_ratio=f"{factors.owner_fte_ratio:.1%}",
                owners=factors.number_of_owners,
                employees=factors.number_of_employees,
            )
            factor_scores = self._enhance_with_owner_fte_ratio(factor_scores, factors)

        # Step 3: Calculate weighted average
        overall_score = self._calculate_overall_score(factor_scores)

        # Step 3b: Multi-owner composite (BET-218). When the
        # `multi_owner_profile_v1` flag is on AND Titan supplied a team
        # composite transferability index for a genuine multi-owner
        # roster, the venture's transferability is the team composite —
        # not this single owner's 12-factor score. Overriding
        # `overall_score` here lets every downstream step (risk level,
        # adjustment, explanation, the result's headline score) flow from
        # the team figure with no further branching.
        #
        # ZERO-REGRESSION: this block is unreachable on the default path
        # — `composite_transferability_index` is None for every existing
        # caller and the flag is off by default. When the resolver routes
        # back to the single owner (single-owner roster, or no composite)
        # it returns `source != MULTI_OWNER_COMPOSITE` and `overall_score`
        # is never reassigned, so the single-owner result is byte-identical.
        if composite_transferability_index is not None and is_multi_owner_v1_enabled():
            engine_overall_score = overall_score
            # Engine score: "less dependency = higher". TRI: the inverse
            # ("more key-person risk = higher"). Convert across the
            # resolver so it compares like with like.
            single_owner_tri = float(
                to_decimal("100") - to_decimal(engine_overall_score)
            )
            resolved = resolve_transferability_index(
                single_owner_index=single_owner_tri,
                composite_index=composite_transferability_index,
                owner_count=owner_count,
                flag_enabled=True,
            )
            if resolved.source == SOURCE_MULTI_OWNER_COMPOSITE:
                overall_score = to_decimal("100") - to_decimal(
                    str(resolved.transferability_index)
                )
                logger.info(
                    "Multi-owner composite transferability applied",
                    owner_count=resolved.owner_count,
                    composite_index=f"{resolved.transferability_index:.1f}",
                    single_owner_score=f"{engine_overall_score:.1f}",
                    composite_overall_score=f"{overall_score:.1f}",
                )

        # Step 4: Determine risk level
        risk_level = self._determine_risk_level(overall_score)

        # Step 5: Calculate valuation adjustment
        valuation_adjustment = self._determine_valuation_adjustment(overall_score)

        # Step 5: Identify key risks
        key_risks = self._identify_key_risks(factors, factor_scores)

        # Step 6: Generate recommendations
        recommendations = self._generate_recommendations(factors, factor_scores)

        # Step 7: Create explanation
        explanation = self._generate_explanation(
            overall_score, risk_level, valuation_adjustment, key_risks
        )

        # Step 8: Track in transparency
        if self.transparency_collector:
            self._track_in_transparency(
                factors, factor_scores, overall_score, risk_level, valuation_adjustment, explanation
            )

        result = OwnerDependencyResult(
            factors=factors,
            overall_score=overall_score,
            risk_level=risk_level,
            valuation_adjustment=valuation_adjustment,
            explanation=explanation,
            key_risks=key_risks,
            recommendations=recommendations,
        )

        # Transferability v2 — additive metadata. Stamping happens before
        # the cap is applied at the processor; the cascade carries both
        # the engine raw figure and the headline (post-cap) figure so
        # advisors see the binding cap explicitly. Skipped when no
        # equity baseline is available — the heuristic table needs a
        # deal-size signal to pick a buyer archetype, and we'd rather
        # render no v2 panel than render one with a fabricated buyer.
        #
        # Launch-readiness escape hatch: `OWNER_PROFILING_V2_DISABLED=1`
        # turns the v2 stamping off without a code revert. Ops can flip
        # the env var if v2 produces a regression mid-launch; the v1
        # report path keeps rendering. Guard is inside this block so the
        # env-var is only paid when v2 would otherwise fire.
        import os
        v2_disabled = os.environ.get(
            "OWNER_PROFILING_V2_DISABLED", ""
        ).strip().lower() in {"1", "true", "yes", "on"}

        if equity_value_mid is not None and not v2_disabled:
            try:
                from src.domain.owner_models.transferability import (
                    build_transferability_profile,
                )

                # Engine-band raw is the same as `valuation_adjustment` at
                # this point (cap is applied later by the processor); the
                # cascade gets a faithful "engine wanted X" reading.
                profile = build_transferability_profile(
                    factor_scores=factor_scores,
                    equity_value_mid=equity_value_mid,
                    headline_adjustment_pct=valuation_adjustment,
                    raw_engine_adjustment_pct=valuation_adjustment,
                    owner_hours_per_week=owner_hours_per_week,
                    eligible_methods=eligible_methods,
                )
                result.transferability_profile = profile
                # Launch-monitoring signal — single info-level event per
                # successful v2 stamp. PostHog / log aggregator counts
                # the "v2 rendered" cardinality so a mid-launch
                # regression (cardinality drops to ~0) is observable.
                # Carries the load-bearing dimensions for triage:
                # buyer archetype, severity tier, confidence tier,
                # whether the cap is binding. NO PII — deal-size as
                # archetype only (no equity value), and the owner-hours
                # *presence* flag is computed up-front so the C3 field
                # name never appears inside the logger call (PII
                # redaction guard at `tests/unit/synthesis/test_c3_pii_log_redaction.py`).
                _hours_present = owner_hours_per_week is not None
                _hours_input_present_flag = _hours_present  # local alias
                logger.info(
                    "transferability_v2.profile_stamped",
                    extra={
                        "buyer_archetype": str(
                            profile.buyer_profile.archetype
                        ),
                        "severity_tier": profile.gap.severity_tier,
                        "severity": str(profile.gap.severity),
                        "confidence_tier": str(profile.confidence.tier),
                        "cap_binding": profile.confidence.cap_binding,
                        "has_owner_intensity_input": _hours_input_present_flag,
                    },
                )
            except (ValueError, TypeError, AttributeError, KeyError) as exc:
                # v2 is additive — never fail the v1 result on a v2 build
                # error. Log so a malformed factor_scores dict surfaces in
                # observability without taking down the report.
                logger.warning(
                    "Transferability v2 profile build failed; v1 fallback in use",
                    extra={"error": str(exc), "error_type": type(exc).__name__},
                )

        logger.info(
            "Owner dependency calculated",
            overall_score=overall_score,
            risk_level=risk_level,
            adjustment=valuation_adjustment,
        )

        return result

    _SUPPLEMENTARY_FIELDS = {"owner_fte_ratio", "number_of_owners", "number_of_employees"}

    def _calculate_all_factor_scores(self, factors: OwnerDependencyFactors) -> dict:
        """Calculate numeric scores for all 12 factors"""
        scores = {}

        for factor_name, factor_value in factors.model_dump().items():
            if factor_name in self._SUPPLEMENTARY_FIELDS:
                continue
            is_inverse = factor_name in self.INVERSE_FACTORS
            score = self._calculate_factor_score(DependencyLevel(factor_value), is_inverse)
            scores[factor_name] = score

        return scores

    INVERSE_DEPENDENCY_SCORES = {
        DependencyLevel.VERY_HIGH: 95,
        DependencyLevel.HIGH: 75,
        DependencyLevel.MEDIUM: 50,
        DependencyLevel.LOW: 30,
        DependencyLevel.VERY_LOW: 10,
    }

    def _calculate_factor_score(self, level: DependencyLevel, is_inverse: bool = False) -> Decimal:
        """
        Convert dependency level to numeric score (0-100)

        Args:
            level: Dependency level enum
            is_inverse: If True, invert the score (good factors)

        Returns:
            Score from 0 (bad) to 100 (good)
        """
        if is_inverse:
            # For inverse factors, flip the scoring
            # VERY_HIGH dependency on documentation is GOOD (score 95)
            # VERY_LOW documentation is BAD (score 10)
            return self.INVERSE_DEPENDENCY_SCORES[level]
        else:
            # For direct factors, keep as-is
            # VERY_HIGH dependency on owner is BAD (score 10)
            # VERY_LOW dependency is GOOD (score 95)
            return self.DEPENDENCY_SCORES[level]

    def _calculate_overall_score(self, factor_scores: dict) -> Decimal:
        """Calculate weighted average of all factor scores"""
        total_score = Decimal("0.0")
        total_weight = Decimal("0.0")

        for factor_name, score in factor_scores.items():
            weight = self.FACTOR_WEIGHTS[factor_name]
            total_score += score * (weight / 100)
            total_weight += weight

        if total_weight <= 0:
            return Decimal("50.0")
        overall = (total_score / total_weight) * 100
        return round(overall, 1)

    def _determine_risk_level(self, overall_score: Decimal) -> str:
        """
        Map overall score to risk category

        Score ranges:
        - 80-100: MINIMAL risk
        - 60-79: LOW risk
        - 40-59: MEDIUM risk
        - 20-39: HIGH risk
        - 0-19: CRITICAL risk
        """
        if overall_score >= 80:
            return "MINIMAL"
        elif overall_score >= 60:
            return "LOW"
        elif overall_score >= 40:
            return "MEDIUM"
        elif overall_score >= 20:
            return "HIGH"
        else:
            return "CRITICAL"

    def _determine_valuation_adjustment(self, overall_score: Decimal) -> Decimal:
        """
        Map overall score to valuation adjustment

        Adjustment tiers (based on Damodaran key person discounts):
        - 80-100: 0% to -5% (minimal adjustment)
        - 60-79: -5% to -10% (low adjustment)
        - 40-59: -10% to -20% (medium adjustment)
        - 20-39: -20% to -30% (high adjustment)
        - 0-19: -30% to -40% (critical adjustment)

        Uses linear interpolation within each tier.
        """
        # Convert score to Decimal for calculations
        score_decimal = to_decimal(str(overall_score))

        if overall_score >= 80:
            # MINIMAL: 0% to -5%
            # Formula: -0.05 * (1 - (score - 80) / 20)
            adjustment_decimal = to_decimal("-0.05") * (
                to_decimal("1") - (score_decimal - to_decimal("80")) / to_decimal("20")
            )
        elif overall_score >= 60:
            # LOW: -5% to -10%
            # Formula: -0.05 - 0.05 * (1 - (score - 60) / 20)
            adjustment_decimal = to_decimal("-0.05") - to_decimal("0.05") * (
                to_decimal("1") - (score_decimal - to_decimal("60")) / to_decimal("20")
            )
        elif overall_score >= 40:
            # MEDIUM: -10% to -20%
            # Formula: -0.10 - 0.10 * (1 - (score - 40) / 20)
            adjustment_decimal = to_decimal("-0.10") - to_decimal("0.10") * (
                to_decimal("1") - (score_decimal - to_decimal("40")) / to_decimal("20")
            )
        elif overall_score >= 20:
            # HIGH: -20% to -30%
            # Formula: -0.20 - 0.10 * (1 - (score - 20) / 20)
            adjustment_decimal = to_decimal("-0.20") - to_decimal("0.10") * (
                to_decimal("1") - (score_decimal - to_decimal("20")) / to_decimal("20")
            )
        else:
            # CRITICAL: -30% to -40%
            # Formula: -0.30 - 0.10 * (1 - score / 20)
            adjustment_decimal = to_decimal("-0.30") - to_decimal("0.10") * (
                to_decimal("1") - score_decimal / to_decimal("20")
            )

        # Return as float for backward compatibility (but calculation used Decimal)
        return to_decimal(adjustment_decimal)

    def _identify_key_risks(
        self, factors: OwnerDependencyFactors, factor_scores: dict
    ) -> List[str]:
        """
        Identify the most critical risk factors

        Returns top 3-5 risks based on lowest scores
        """
        risks = []

        # Sort factors by score (lowest first)
        sorted_factors = sorted(factor_scores.items(), key=lambda x: x[1])

        # Map factor names to human-readable risks
        risk_descriptions = {
            "client_concentration": "High client concentration - top clients represent >50% of revenue",
            "operational_knowledge": "Critical operational knowledge held only by owner",
            "sales_relationship": "Owner is primary or sole client contact",
            "technical_expertise": "Owner possesses irreplaceable technical expertise",
            "industry_network": "Business heavily dependent on owner's industry connections",
            "decision_making": "All or most business decisions require owner approval",
            "brand_reputation": "Business brand strongly tied to owner's personal reputation",
            "process_documentation": "Limited or no documentation of key processes",
            "team_capability": "Management team lacks capability to operate independently",
            "succession_planning": "No succession plan or transition strategy in place",
            "business_scalability": "Business model difficult to scale without owner",
            "contract_transferability": "Customer contracts or relationships may not transfer to new owner",
        }

        # Take top 3-5 risks (score < 60)
        for factor_name, score in sorted_factors[:5]:
            if score < 60:  # Only include significant risks
                risk_text = risk_descriptions.get(
                    factor_name, f"{factor_name.replace('_', ' ').title()} poses transition risk"
                )
                risks.append(risk_text)

        # If no significant risks, add positive note
        if not risks:
            risks.append("No critical owner dependency risks identified")

        return risks

    def _generate_recommendations(
        self, factors: OwnerDependencyFactors, factor_scores: dict
    ) -> List[str]:
        """Generate actionable recommendations to reduce owner dependency"""
        recommendations = []

        # Recommendation mapping
        recommendation_map = {
            "client_concentration": "Diversify client base and reduce concentration in top accounts",
            "operational_knowledge": "Document operational processes and create knowledge base",
            "sales_relationship": "Introduce clients to other team members and build relationships",
            "technical_expertise": "Cross-train team members and document technical processes",
            "industry_network": "Build company-level industry relationships and partnerships",
            "decision_making": "Delegate decision-making authority and empower management team",
            "brand_reputation": "Build company brand separate from owner's personal brand",
            "process_documentation": "Create comprehensive process documentation and SOPs",
            "team_capability": "Develop and strengthen management team capabilities",
            "succession_planning": "Create formal succession plan with clear transition timeline",
            "business_scalability": "Develop systems and processes for scalable operations",
            "contract_transferability": "Ensure contracts allow transfer and build direct customer relationships",
        }

        # Get lowest scoring factors
        sorted_factors = sorted(factor_scores.items(), key=lambda x: x[1])

        # Generate recommendations for low-scoring factors (limit to 4 to leave room for timing)
        for factor_name, score in sorted_factors[:4]:
            if score < 70:
                rec = recommendation_map.get(factor_name)
                if rec:
                    recommendations.append(rec)

        # Add timing recommendation
        if factor_scores:
            avg_score = sum(factor_scores.values()) / len(factor_scores)
            if avg_score < 60:
                recommendations.append(
                    "Priority: Address these risks 12-18 months before planned exit"
                )
            elif avg_score < 75:
                recommendations.append(
                    "Priority: Address these risks 6-12 months before planned exit"
                )

        return recommendations[:5]

    def _generate_explanation(
        self,
        overall_score: Decimal,
        risk_level: str,
        valuation_adjustment: Decimal,
        key_risks: List[str],
    ) -> str:
        """Generate detailed explanation of the assessment"""

        # Risk level descriptions
        risk_descriptions = {
            "MINIMAL": "The business shows minimal owner dependency with strong systems, documentation, and team capability.",
            "LOW": "The business has low owner dependency with good processes and team, but some areas could be improved.",
            "MEDIUM": "The business shows moderate owner dependency. Key processes exist but owner remains critical in several areas.",
            "HIGH": "The business has high owner dependency. Significant transition risks exist across multiple factors.",
            "CRITICAL": "The business shows critical owner dependency. The owner is essential to operations, and transition would be highly risky.",
        }

        explanation_parts = [
            f"Owner Dependency Assessment: {overall_score:.1f}/100 ({risk_level} risk)",
            "",
            risk_descriptions.get(risk_level, "Assessment complete"),
            "",
            f"Valuation Impact: {valuation_adjustment:.1%} adjustment applied to account for key person risk.",
            "",
            "This adjustment reflects the reduced value and increased risk associated with owner dependency. "
            "Buyers typically require a discount when acquiring businesses with high key person risk.",
            "",
            "Key Risk Factors:",
        ]

        for risk in key_risks[:3]:  # Top 3 risks
            explanation_parts.append(f"• {risk}")

        explanation_parts.append("")
        explanation_parts.append(
            "Methodology: Based on Damodaran (2012) key person discount framework "
            "and Small Business Valuation Standards (SBVS)."
        )

        return "\n".join(explanation_parts)

    def _track_in_transparency(
        self,
        factors: OwnerDependencyFactors,
        factor_scores: dict,
        overall_score: Decimal,
        risk_level: str,
        valuation_adjustment: Decimal,
        explanation: str,
    ):
        """Track owner dependency calculation in transparency system"""

        if not self.transparency_collector:
            return

        # Track individual factor scores
        self.transparency_collector.add_calculation_step(
            description="Owner Dependency: Individual Factor Scores",
            formula="Each factor scored 0-100 based on dependency level",
            inputs={
                factor: {
                    "level": (
                        getattr(factors, factor).value
                        if hasattr(getattr(factors, factor, None), "value")
                        else str(getattr(factors, factor, ""))
                    ),
                    "score": score,
                }
                for factor, score in factor_scores.items()
            },
            outputs={"factor_scores": factor_scores},
            explanation="12-factor assessment: 7 direct dependency factors + 5 inverse factors (documentation, team, planning)",
        )

        # Track overall calculation
        self.transparency_collector.add_calculation_step(
            description="Owner Dependency: Overall Score",
            formula="Weighted Average = Σ(Factor Score × Weight) / Total Weight",
            inputs={"factor_scores": factor_scores, "weights": self.FACTOR_WEIGHTS},
            outputs={"overall_score": overall_score, "risk_level": risk_level},
            explanation=f"Overall dependency score: {overall_score:.1f}/100 (Risk Level: {risk_level})",
        )

        # Track valuation adjustment
        self.transparency_collector.add_calculation_step(
            description="Owner Dependency: Valuation Adjustment",
            formula=f"Adjustment = {valuation_adjustment:.1%} based on {overall_score:.1f}/100 dependency score",
            inputs={"overall_score": overall_score, "risk_level": risk_level},
            outputs={
                "valuation_adjustment": valuation_adjustment,
                "adjustment_percent": valuation_adjustment * 100,
            },
            explanation=explanation,
        )

        logger.debug(
            "Owner dependency tracked in transparency",
            overall_score=overall_score,
            adjustment=valuation_adjustment,
        )

    def _enhance_with_owner_fte_ratio(
        self, factor_scores: dict, factors: OwnerDependencyFactors
    ) -> dict:
        """
        Enhance qualitative factor scores with quantitative owner/FTE ratio

        PHASE 2 INTEGRATION: Creates interaction effects between quantitative
        management concentration metrics and qualitative assessments.

        Enhancements:
        1. team_capability: High ratio = limited team depth
        2. decision_making: High ratio = more centralized decisions
        3. operational_knowledge: High ratio = less knowledge distribution

        Args:
            factor_scores: Dict of existing factor scores
            factors: OwnerDependencyFactors including owner_fte_ratio

        Returns:
            Enhanced factor scores dict
        """
        ratio = factors.owner_fte_ratio
        enhanced_scores = factor_scores.copy()

        # Determine concentration tier
        if ratio >= 0.5:
            # CRITICAL concentration (50%+ owners/employees)
            team_penalty = -15  # Reduce team_capability score
            decision_penalty = -10  # Reduce decision_making score
            ops_penalty = -10  # Reduce operational_knowledge score
            tier = "CRITICAL"
        elif ratio >= 0.25:
            # HIGH concentration
            team_penalty = -10
            decision_penalty = -7
            ops_penalty = -5
            tier = "HIGH"
        elif ratio >= 0.10:
            # MEDIUM concentration
            team_penalty = -5
            decision_penalty = -3
            ops_penalty = -3
            tier = "MEDIUM"
        else:
            # LOW concentration
            team_penalty = -2
            decision_penalty = 0
            ops_penalty = 0
            tier = "LOW"

        # Apply penalties (but never go below 10 or above 95)
        if "team_capability" in enhanced_scores:
            original_team = enhanced_scores["team_capability"]
            enhanced_scores["team_capability"] = max(10, min(95, original_team + team_penalty))
            logger.debug(
                f"team_capability adjusted: {original_team} → {enhanced_scores['team_capability']} "
                f"(penalty: {team_penalty}, ratio tier: {tier})"
            )

        if "decision_making" in enhanced_scores:
            original_decision = enhanced_scores["decision_making"]
            enhanced_scores["decision_making"] = max(
                10, min(95, original_decision + decision_penalty)
            )
            logger.debug(
                f"decision_making adjusted: {original_decision} → {enhanced_scores['decision_making']} "
                f"(penalty: {decision_penalty}, ratio tier: {tier})"
            )

        if "operational_knowledge" in enhanced_scores:
            original_ops = enhanced_scores["operational_knowledge"]
            enhanced_scores["operational_knowledge"] = max(10, min(95, original_ops + ops_penalty))
            logger.debug(
                f"operational_knowledge adjusted: {original_ops} → {enhanced_scores['operational_knowledge']} "
                f"(penalty: {ops_penalty}, ratio tier: {tier})"
            )

        logger.info(
            "Owner/FTE ratio enhancement applied",
            ratio=f"{ratio:.1%}",
            tier=tier,
            team_adjustment=team_penalty,
            decision_adjustment=decision_penalty,
            ops_adjustment=ops_penalty,
        )

        # Track in transparency if available
        if self.transparency_collector:
            try:
                self.transparency_collector.add_calculation_step(
                    description="Owner/FTE Ratio Enhancement of Qualitative Factors",
                    formula=f"Adjusted scores based on {ratio:.1%} owner/FTE ratio ({tier} concentration tier)",
                    inputs={
                        "owner_fte_ratio": round(ratio, 3),
                        "concentration_tier": tier,
                        "number_of_owners": factors.number_of_owners,
                        "number_of_employees": factors.number_of_employees,
                    },
                    outputs={
                        "team_capability_adjustment": team_penalty,
                        "decision_making_adjustment": decision_penalty,
                        "operational_knowledge_adjustment": ops_penalty,
                    },
                    explanation=(
                        f"Quantitative owner/FTE ratio of {ratio:.1%} indicates {tier} management "
                        f"concentration. This enhances qualitative assessment by adjusting related "
                        f"factors: fewer employees relative to owners suggests limited team depth "
                        f"(-{abs(team_penalty)} pts), more centralized decision-making "
                        f"(-{abs(decision_penalty)} pts), and concentrated operational knowledge "
                        f"(-{abs(ops_penalty)} pts)."
                    ),
                )
            except (DatabaseError, DataQualityError) as e:
                logger.warning(
                    f"Failed to track owner/FTE enhancement in transparency due to data or DB error: {e}"
                )
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logger.warning(
                    f"An unexpected error occurred while tracking owner/FTE enhancement in transparency: {e}",
                    extra={"error_type": type(e).__name__},
                )

        return enhanced_scores
