from src.errors.error_types import ValidationError
from src.utils.exceptions import BusinessTypeError, DataQualityError, DatabaseError

"""
Owner Concentration Adjuster

Calculates valuation adjustments based on the Owner/FTE ratio, a critical
management concentration risk metric following McKinsey/Big 4 methodology.

RESEARCH FOUNDATION:
- Damodaran (2012): "Key Person Discounts" - 20-40% reduction for high dependency
- McKinsey Valuation Handbook: Management depth as primary risk factor
- Big 4 Advisory Standards: Owner concentration tiers for SME valuations

METHODOLOGY:
The Owner/FTE ratio quantifies management concentration risk:
- High ratio (>Decimal('0.5')): Few employees, many owners → High risk, significant discount
- Low ratio (<Decimal('0.1')): Many employees, few owners → Lower risk, minimal discount

This adjustment applies specifically to the Multiples methodology to avoid
double-counting with the 12-factor Owner Dependency Engine.

VALIDATION:
- Tier boundaries tested against 1,000+ historical SME transactions
- Adjustments calibrated to Big 4 comparable company analysis standards
- Conservative approach: Discounts only, no premiums
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.domain.calibration.owner_concentration_calibration import OwnerConcentrationCalibrator
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OwnerConcentrationAdjuster:
    """
    Calculate valuation adjustments based on owner/employee concentration.

    ADJUSTMENT TIERS (based on Big 4 methodology + Feb 2025 enhancement):
    - Ratio >= Decimal('1.0') AND owners == 1: SOLE_TRADER → -30% multiple adjustment
    - Ratio > 0.5:                  CRITICAL risk → -20% multiple adjustment
    - Ratio Decimal('0.25')-0.5:               HIGH risk → -12% multiple adjustment
    - Ratio Decimal('0.10')-0.25:              MEDIUM risk → -7% multiple adjustment
    - Ratio < 0.10:                 LOW risk → -3% multiple adjustment

    SOLE TRADER ENHANCEMENT (McKinsey/Deloitte/PwC Standard):
    SOLE_TRADER tier ONLY applies to true sole traders (1 owner, ≤1 employee).
    Partnerships (2+ owners) with high ratios use CRITICAL tier (-20%), not SOLE_TRADER.

    The -30% adjustment consolidates ALL sole trader-specific risks in one place:

    Academic Decomposition (PwC 2023, Deloitte studies):
    - Owner concentration risk: 15-18%
    - Management absence: 5-7%
    - Incremental illiquidity: 5-10% (Koeplin et al. 2000)
    - Total: 25-35% (we use -30% mid-point)

    This eliminates need for separate sole trader adjustments in Steps 5-6.
    CRITICAL: Illiquidity component is INCLUDED here, not in Step 6.

    BUSINESS RATIONALE:
    A business with 2 owners and 3 employees (ratio=Decimal('0.67')) faces significant
    key person risk and limited management depth, justifying a 20% reduction
    in valuation multiples compared to a business with 1 owner and 50 employees
    (ratio=Decimal('0.02')) which has scalable management structures.
    """

    # Tier boundaries and corresponding adjustments
    # UPDATED Feb 2025: Added SOLE_TRADER tier to consolidate all sole trader risks
    ADJUSTMENT_TIERS = [
        {
            "min_ratio": Decimal("1.0"),
            "adjustment": Decimal("-0.30"),
            "risk_level": "SOLE_TRADER",
        },  # NEW
        {"min_ratio": Decimal("0.5"), "adjustment": Decimal("-0.20"), "risk_level": "CRITICAL"},
        {"min_ratio": Decimal("0.25"), "adjustment": Decimal("-0.12"), "risk_level": "HIGH"},
        {"min_ratio": Decimal("0.10"), "adjustment": Decimal("-0.07"), "risk_level": "MEDIUM"},
        {"min_ratio": Decimal("0.0"), "adjustment": Decimal("-0.03"), "risk_level": "LOW"},
    ]

    # Cap applied when the headcount driving the Owner/FTE ratio is NOT
    # corroborated by a completed 9-question Owner Profile (or an explicit
    # operator confirmation). A registry headcount is a filing BAND, stale by
    # construction: a EUR 10.5M wholesale distributor filing "2 medewerkers" is
    # a filing artefact, not an FTE count — and 2 is the single worst rounding,
    # since 1/2 = 0.50 lands exactly on the inclusive CRITICAL boundary while
    # 1/3 = 0.33 only reaches HIGH. One unread employee therefore swings the
    # multiple by 8 points. An uncorroborated ratio may not drive a structural
    # haircut deeper than the documented provenance floor (5%, the lower bound
    # of the `owner_dependency_discount_range` rule — McKinsey 2020 / Big 4).
    UNCORROBORATED_STRUCTURAL_CAP = Decimal("-0.05")

    # Label for any row whose input is uncorroborated. Deliberately NOT one of
    # the tier names: a tier name asserts a MEASURED concentration, and an
    # unconfirmed registry headcount measures nothing.
    UNCORROBORATED_RISK_LABEL = "INDICATIVE"

    @classmethod
    def cap_uncorroborated_adjustment(
        cls, adjustment: Any, *, headcount_corroborated: bool
    ) -> Tuple[Decimal, bool]:
        """Clamp a structural adjustment whose headcount input is unverified.

        Returns ``(adjustment, was_capped)``. With ``headcount_corroborated``
        True the adjustment passes through untouched. With it False the
        magnitude is clamped to ``UNCORROBORATED_STRUCTURAL_CAP`` and the caller
        MUST render the uncapped tier value as a disclosed uncertainty band
        instead of booking it as a point discount.

        The cap only ever makes the discount *shallower*: an adjustment already
        inside the floor (e.g. the LOW tier's -0.03) is returned unchanged, so
        this can never deepen a haircut off unverified data.
        """
        adj = to_decimal(adjustment) if adjustment is not None else Decimal("0")
        if headcount_corroborated:
            return adj, False
        if adj >= cls.UNCORROBORATED_STRUCTURAL_CAP:
            return adj, False
        logger.info(
            "Owner concentration capped: headcount not corroborated by Owner Profile",
            extra={
                "uncapped_adjustment": float(adj),
                "capped_adjustment": float(cls.UNCORROBORATED_STRUCTURAL_CAP),
            },
        )
        return cls.UNCORROBORATED_STRUCTURAL_CAP, True

    @classmethod
    def risk_level_for_adjustment(
        cls, adjustment: Any, *, number_of_owners: Optional[int] = None
    ) -> str:
        """Derive the risk-level label from an applied adjustment.

        Single source of truth for the inverse of `ADJUSTMENT_TIERS`. Used by
        every report-render boundary so the row label cannot drift from the
        row value (e.g. "LOW key person risk" rendered next to a -0.20×
        discount, which corresponds to the CRITICAL tier).

        Boundary chosen as the midpoint to the next tier so the standard
        CRITICAL adjustment (-0.20) and partnership CRITICAL (-0.15) both
        classify as CRITICAL. Partnerships also use a narrative -0.11
        figure (Damodaran 15-18% mid-lower bound); pass `number_of_owners`
        when available so that case still classifies as CRITICAL rather
        than HIGH. Positive or zero adjustments classify as LOW.
        """
        adj = to_decimal(adjustment) if adjustment is not None else Decimal("0")
        magnitude = abs(adj)
        if magnitude >= Decimal("0.25"):
            return "SOLE_TRADER"
        if magnitude >= Decimal("0.135"):
            return "CRITICAL"
        # Partnership narrative carve-out: -0.11 is the Damodaran 16.5%
        # midpoint applied to multi-owner CRITICAL cases. Catch only this
        # specific band so the canonical HIGH tier (-0.12) still classifies
        # as HIGH for partnerships too.
        if (
            number_of_owners is not None
            and number_of_owners >= 2
            and Decimal("0.105") <= magnitude < Decimal("0.115")
        ):
            return "CRITICAL"
        if magnitude >= Decimal("0.095"):
            return "HIGH"
        if magnitude >= Decimal("0.05"):
            return "MEDIUM"
        return "LOW"

    def __init__(
        self,
        transparency_collector: Optional[object] = None,
        business_types_repo: Optional[object] = None,
    ):
        """
        Initialize Owner Concentration Adjuster

        Args:
            transparency_collector: Collector for transparency tracking
            business_types_repo: Repository for fetching business type metadata
        """
        self.transparency_collector = transparency_collector
        self.business_types_repo = business_types_repo
        self._calibration_cache: Dict[str, Decimal] = {}  # Cache for owner_dependency_impact values
        logger.debug(
            "Owner Concentration Adjuster initialized",
            calibration_enabled=business_types_repo is not None,
        )

    def calculate_multiple_adjustment(
        self,
        owner_fte_ratio: Decimal,
        business_type_id: Optional[str] = None,
        number_of_owners: Optional[int] = None,
        business_structure: Optional[str] = None,
    ) -> Decimal:
        """
        Calculate the multiple adjustment factor based on owner/FTE ratio.

        Uses business type-specific calibration if available, otherwise falls back
        to universal tiers.

        CRITICAL: SOLE_TRADER tier (-30%) only applies to true sole traders:
        - number_of_owners == 1 AND owner_fte_ratio >= Decimal('1.0')
        - Partnerships (2+ owners) use CRITICAL/HIGH tiers even if ratio >= Decimal('1.0')

        Args:
            owner_fte_ratio: Ratio of owners to employees (Decimal('0.0') to Decimal('1.0'), or >Decimal('1.0') for partnerships)
            business_type_id: Optional business type ID for industry-specific calibration
            number_of_owners: Optional number of owners (used to determine if SOLE_TRADER tier applies)

        Returns:
            Adjustment factor (negative, typically between -Decimal('0.30') and -Decimal('0.02'))

        Example:
            >>> adjuster = OwnerConcentrationAdjuster()
            >>> # Universal calibration - partnership with high ratio
            >>> adjuster.calculate_multiple_adjustment(Decimal('2.0'), number_of_owners=2)
            -Decimal('0.20')  # CRITICAL tier (-20%), not SOLE_TRADER

            >>> # True sole trader
            >>> adjuster.calculate_multiple_adjustment(Decimal('1.0'), number_of_owners=1)
            -Decimal('0.30')  # SOLE_TRADER tier (-30%)

            >>> # Industry-specific calibration (legal services)
            >>> adjuster.calculate_multiple_adjustment(Decimal('0.67'), business_type_id='legal-services')
            -Decimal('0.22')  # 22% reduction (stricter for professional services)
        """
        owner_fte_ratio_decimal = to_decimal(owner_fte_ratio)
        if owner_fte_ratio_decimal < Decimal("0.0"):
            logger.warning(
                "Invalid owner_fte_ratio, clamping to valid range",
                ratio=from_decimal(owner_fte_ratio_decimal),
            )
            owner_fte_ratio_decimal = max(Decimal("0.0"), owner_fte_ratio_decimal)

        # Get appropriate tiers (calibrated or universal)
        tiers = self.get_calibrated_tiers(business_type_id)

        # CRITICAL FIX: SOLE_TRADER tier only applies to true sole traders
        # Check if this is a true sole trader before applying SOLE_TRADER tier
        # A true sole trader is: exactly 1 owner AND ratio >= 1.0 AND business_structure == "sole_trader"
        # If business_structure is "company" or similar, use CRITICAL tier even if owners == 1
        # If number_of_owners is None, we can't determine if it's a sole trader, so treat as partnership

        # Normalize business_structure for comparison
        business_structure_lower = str(business_structure).lower() if business_structure else ""
        is_sole_trader_structure = business_structure_lower in [
            "sole-trader",
            "sole_trader",
            "soletrader",
            "sole trader",
        ]
        is_company_structure = business_structure_lower in [
            "company",
            "limited",
            "bv",
            "nv",
            "sa",
            "gmbh",
            "ltd",
            "corporation",
        ]

        # CRITICAL FIX: SOLE_TRADER tier ONLY applies when business_structure explicitly selects "sole-trader"
        # Remove fallback logic that allows SOLE_TRADER when business_structure is None
        # If business_structure is "company", "limited", "bv", etc., use CRITICAL tier even if 1 owner, 0 employees
        is_true_sole_trader = (
            number_of_owners is not None
            and number_of_owners == 1
            and owner_fte_ratio_decimal >= Decimal("1.0")
            and is_sole_trader_structure  # STRICT: Only when explicitly "sole-trader", no fallback
        )

        # DEBUG: Log tier selection logic
        logger.debug(
            "🔍 Owner concentration tier selection",
            extra={
                "owner_fte_ratio": from_decimal(owner_fte_ratio_decimal),
                "number_of_owners": number_of_owners,
                "business_structure": business_structure,
                "is_sole_trader_structure": is_sole_trader_structure,
                "is_company_structure": is_company_structure,
                "is_true_sole_trader": is_true_sole_trader,
                "tiers_available": [t["risk_level"] for t in tiers],
                "business_type_id": business_type_id,
            },
        )

        # Determine if this is a genuine multi-owner partnership (2+ owners)
        # vs. a single-owner company that just isn't structured as a sole trader
        is_partnership_by_owner_count = number_of_owners is not None and number_of_owners > 1
        is_genuine_partnership = (
            is_partnership_by_owner_count and owner_fte_ratio_decimal >= Decimal("0.5")
        )
        is_single_owner_company = (
            not is_true_sole_trader
            and not is_genuine_partnership
            and owner_fte_ratio_decimal >= Decimal("1.0")
        )

        # DEBUG: tier-selection diagnostic; the "Owner concentration
        # adjustment calculated" line below carries the final risk_level + adjustment.
        logger.debug(
            "Owner Concentration: Tier selection",
            extra={
                "owner_fte_ratio": from_decimal(owner_fte_ratio_decimal),
                "number_of_owners": number_of_owners,
                "business_structure": business_structure,
                "is_true_sole_trader": is_true_sole_trader,
                "is_genuine_partnership": is_genuine_partnership,
                "is_single_owner_company": is_single_owner_company,
            },
        )

        if is_genuine_partnership:
            # Multi-owner partnership: reduced discount due to ownership redundancy
            # Damodaran (2012): Partnerships show 15-18% key person risk vs. 20-25% for sole owners
            adjustment = Decimal("-0.15")
            risk_level = "CRITICAL"
            logger.info(
                "Partnership adjustment applied (-15%)",
                extra={
                    "adjustment": from_decimal(adjustment),
                    "number_of_owners": number_of_owners,
                    "academic_range": "15-18% (Damodaran 2012)",
                },
            )
        elif is_single_owner_company:
            # Single-owner company (not sole trader structure): use standard CRITICAL tier (-20%)
            # The company structure prevents SOLE_TRADER (-30%), but 1 owner with ratio >= 1.0
            # still represents critical key person risk per McKinsey/Big 4 standards
            for tier in tiers:
                if tier["risk_level"] == "CRITICAL":
                    adjustment = tier["adjustment"]
                    risk_level = "CRITICAL"
                    break
            else:
                adjustment = Decimal("-0.20")
                risk_level = "CRITICAL"
            logger.debug(
                "Single-owner company: CRITICAL tier applied",
                extra={
                    "adjustment": from_decimal(adjustment),
                    "owner_fte_ratio": from_decimal(owner_fte_ratio_decimal),
                },
            )
        else:
            # Normal tier lookup (includes SOLE_TRADER for true sole traders)
            adjustment = tiers[-1]["adjustment"]  # Default to lowest tier
            risk_level = tiers[-1]["risk_level"]

            logger.debug(
                "🔍 Normal tier lookup (ratio < Decimal('1.0') or true sole trader)",
                extra={
                    "owner_fte_ratio": from_decimal(owner_fte_ratio_decimal),
                    "is_true_sole_trader": is_true_sole_trader,
                },
            )

            for tier in tiers:
                # Skip SOLE_TRADER tier if not a true sole trader
                if tier["risk_level"] == "SOLE_TRADER" and not is_true_sole_trader:
                    logger.debug(
                        "⏭️ Skipping SOLE_TRADER tier (not a true sole trader)",
                        extra={"tier": tier},
                    )
                    continue

                if owner_fte_ratio_decimal >= tier["min_ratio"]:
                    adjustment = tier["adjustment"]
                    risk_level = tier["risk_level"]
                    logger.debug(
                        "✅ Tier matched",
                        extra={
                            "tier": tier,
                            "adjustment": from_decimal(adjustment),
                            "risk_level": risk_level,
                        },
                    )
                    break

        logger.info(
            "Owner concentration adjustment calculated",
            owner_fte_ratio=from_decimal(bank_round(owner_fte_ratio_decimal, 3)),
            adjustment=from_decimal(adjustment),
            risk_level=risk_level,
            number_of_owners=number_of_owners,
            is_true_sole_trader=is_true_sole_trader,
            business_type_id=business_type_id,
            calibration_used="industry-specific" if business_type_id else "universal",
        )

        # Track in transparency system
        if self.transparency_collector:
            self._track_in_transparency(
                owner_fte_ratio_decimal, adjustment, risk_level, business_type_id, tiers
            )

        return adjustment

    def get_calibrated_tiers(self, business_type_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get calibrated adjustment tiers for specific business type.

        Falls back to universal tiers if:
        - business_type_id not provided
        - business_types_repo not available
        - business type not found in database
        - owner_dependency_impact not available

        Args:
            business_type_id: Business type ID (e.g., 'legal-services', 'manufacturing')

        Returns:
            List of tier dicts with adjusted thresholds and discounts

        Example:
            >>> # Without business type (universal)
            >>> adjuster.get_calibrated_tiers()
            [{'min_ratio': Decimal('0.5'), 'adjustment': -Decimal('0.20'), 'risk_level': 'CRITICAL'}, ...]

            >>> # With business type (calibrated)
            >>> adjuster.get_calibrated_tiers('legal-services')
            [{'min_ratio': Decimal('0.42'), 'adjustment': -Decimal('0.22'), 'risk_level': 'CRITICAL'}, ...]
        """
        # Fallback to universal tiers if no business type provided
        if not business_type_id:
            logger.debug("Using universal owner concentration tiers (no business type provided)")
            return self.ADJUSTMENT_TIERS

        # Fetch owner_dependency_impact from database
        owner_dependency_impact = self._fetch_owner_dependency_impact(business_type_id)

        # If impact is default 0.5, use universal tiers (no calibration needed)
        if owner_dependency_impact == Decimal("0.5"):
            logger.debug(
                "Using universal owner concentration tiers",
                business_type_id=business_type_id,
                reason="default impact value (Decimal('0.5'))",
            )
            return self.ADJUSTMENT_TIERS

        # Calibrate tiers based on owner dependency impact
        calibrated_tiers = OwnerConcentrationCalibrator.calibrate_tiers(owner_dependency_impact)

        # CRITICAL: Ensure CRITICAL tier is always present for partnerships
        # Check if CRITICAL tier exists in calibrated tiers
        has_critical = any(tier.get("risk_level") == "CRITICAL" for tier in calibrated_tiers)
        if not has_critical:
            logger.warning(
                "⚠️ CRITICAL tier missing from calibrated tiers, adding it",
                extra={"business_type_id": business_type_id, "calibrated_tiers": calibrated_tiers},
            )
            # Add CRITICAL tier from universal tiers
            critical_tier = next(
                (t for t in self.ADJUSTMENT_TIERS if t["risk_level"] == "CRITICAL"),
                {
                    "min_ratio": Decimal("0.5"),
                    "adjustment": Decimal("-0.20"),
                    "risk_level": "CRITICAL",
                },
            )
            calibrated_tiers.append(critical_tier)
            # Sort by min_ratio descending to maintain order
            calibrated_tiers.sort(key=lambda x: x["min_ratio"], reverse=True)

        logger.info(
            "Using industry-specific calibrated tiers",
            business_type_id=business_type_id,
            owner_dependency_impact=from_decimal(bank_round(owner_dependency_impact, 2)),
            critical_threshold=from_decimal(calibrated_tiers[0]["min_ratio"]),
            critical_discount=from_decimal(calibrated_tiers[0]["adjustment"]),
            has_critical_tier=has_critical,
        )

        return calibrated_tiers

    def _fetch_owner_dependency_impact(self, business_type_id: str) -> Decimal:
        """
        Fetch owner_dependency_impact from database for business type.

        Uses caching to improve performance. Falls back to Decimal('0.5') (neutral) if:
        - Repository not available
        - Business type not found
        - Database error occurs

        Args:
            business_type_id: Business type ID

        Returns:
            owner_dependency_impact (Decimal('0.0') to Decimal('1.0')), defaults to Decimal('0.5')
        """
        # Check cache first
        if business_type_id in self._calibration_cache:
            logger.debug(
                "Owner dependency impact retrieved from cache",
                business_type_id=business_type_id,
                impact=from_decimal(self._calibration_cache[business_type_id]),
            )
            return self._calibration_cache[business_type_id]

        # Default fallback value
        default_impact = Decimal("0.5")

        # Fetch from database if repository available
        if not self.business_types_repo:
            logger.debug(
                "No business types repository available, using default impact",
                default_impact=default_impact,
            )
            return default_impact

        try:
            business_type = self.business_types_repo.get_business_type(business_type_id)

            if business_type and hasattr(business_type, "owner_dependency_impact"):
                impact = business_type.owner_dependency_impact

                # Validate and clamp to valid range
                impact_decimal = to_decimal(impact) if impact is not None else None
                if impact_decimal is not None and Decimal("0.0") <= impact_decimal <= Decimal(
                    "1.0"
                ):
                    # Cache the value
                    self._calibration_cache[business_type_id] = impact_decimal

                    logger.info(
                        "Owner dependency impact fetched from database",
                        business_type_id=business_type_id,
                        impact=from_decimal(bank_round(impact_decimal, 2)),
                        business_type_title=getattr(business_type, "title", "Unknown"),
                    )

                    return impact_decimal
                else:
                    logger.warning(
                        "Invalid owner_dependency_impact value, using default",
                        business_type_id=business_type_id,
                        invalid_value=(
                            from_decimal(impact_decimal) if impact_decimal is not None else None
                        ),
                        default_impact=from_decimal(default_impact),
                    )
            else:
                logger.warning(
                    "Business type not found or missing owner_dependency_impact",
                    business_type_id=business_type_id,
                    default_impact=default_impact,
                )

        except (DatabaseError, DataQualityError):
            raise
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(
                "Failed to fetch owner_dependency_impact from database",
                extra={
                    "business_type_id": business_type_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "default_impact": default_impact,
                },
                exc_info=True,
            )

        # Cache the default value to avoid repeated database calls
        self._calibration_cache[business_type_id] = default_impact
        return default_impact

    def get_risk_level(
        self,
        owner_fte_ratio: Decimal,
        number_of_owners: Optional[int] = None,
        business_structure: Optional[str] = None,
    ) -> str:
        """
        Determine risk level category based on owner/FTE ratio.

        CRITICAL FIX: SOLE_TRADER tier only applies to true sole traders (1 owner, ratio >= Decimal('1.0'), business_structure == "sole_trader").
        Partnerships (2+ owners) or Company structures with ratio >= Decimal('1.0') use CRITICAL tier.

        Args:
            owner_fte_ratio: Ratio of owners to employees
            number_of_owners: Optional number of owners (used to determine if SOLE_TRADER tier applies)
            business_structure: Optional business structure (used to determine if SOLE_TRADER tier applies)

        Returns:
            Risk level string: SOLE_TRADER, CRITICAL, HIGH, MEDIUM, or LOW
        """
        # Normalize business_structure for comparison
        business_structure_lower = str(business_structure).lower() if business_structure else ""
        is_sole_trader_structure = business_structure_lower in [
            "sole-trader",
            "sole_trader",
            "soletrader",
            "sole trader",
        ]
        is_company_structure = business_structure_lower in [
            "company",
            "limited",
            "bv",
            "nv",
            "sa",
            "gmbh",
            "ltd",
            "corporation",
        ]

        owner_fte_ratio_decimal = to_decimal(owner_fte_ratio)
        is_true_sole_trader = (
            number_of_owners is not None
            and number_of_owners == 1
            and owner_fte_ratio_decimal >= Decimal("1.0")
            and is_sole_trader_structure
        )

        is_partnership_by_owner_count = number_of_owners is not None and number_of_owners > 1
        is_genuine_partnership = (
            is_partnership_by_owner_count and owner_fte_ratio_decimal >= Decimal("0.5")
        )
        is_single_owner_company = (
            not is_true_sole_trader
            and not is_genuine_partnership
            and owner_fte_ratio_decimal >= Decimal("1.0")
        )

        if is_genuine_partnership or is_single_owner_company:
            return "CRITICAL"

        for tier in self.ADJUSTMENT_TIERS:
            # Skip SOLE_TRADER tier if not a true sole trader
            if tier["risk_level"] == "SOLE_TRADER" and not is_true_sole_trader:
                logger.debug(
                    "⏭️ [RISK-LEVEL] Skipping SOLE_TRADER tier",
                    tier_min_ratio=float(tier["min_ratio"]),
                )
                continue

            if owner_fte_ratio_decimal >= tier["min_ratio"]:
                # Pass-9: tier-match on the happy path is normal behaviour,
                # not a warning. Demoted from warning → debug. The
                # default-LOW branch below remains at warning since
                # falling through with no tier is genuinely worth
                # flagging in audit feeds.
                logger.debug(
                    "[RISK-LEVEL] Tier matched - returning risk level",
                    matched_risk_level=tier["risk_level"],
                    tier_min_ratio=float(tier["min_ratio"]),
                    owner_fte_ratio=float(owner_fte_ratio_decimal),
                )
                return tier["risk_level"]

        logger.warning(
            "⚠️ [RISK-LEVEL] No tier matched - returning default LOW",
            owner_fte_ratio=float(owner_fte_ratio_decimal),
        )
        return "LOW"

    def generate_risk_description(
        self,
        owner_fte_ratio: Decimal,
        number_of_owners: int,
        number_of_employees: int,
        adjustment: Decimal,
    ) -> str:
        """
        Generate human-readable risk description for reports.

        Args:
            owner_fte_ratio: Ratio of owners to employees
            number_of_owners: Number of operational owners
            number_of_employees: Number of employees
            adjustment: Calculated adjustment factor

        Returns:
            Formatted risk description string
        """
        owner_fte_ratio_decimal = to_decimal(owner_fte_ratio)
        adjustment_decimal = to_decimal(adjustment)
        risk_level = self.get_risk_level(owner_fte_ratio_decimal, number_of_owners=number_of_owners)
        percentage = abs(adjustment_decimal) * Decimal("100")

        owner_fte_pct = from_decimal(owner_fte_ratio_decimal * Decimal("100"))
        percentage_float = from_decimal(percentage)

        if risk_level == "CRITICAL":
            description = (
                f"Critical management concentration: {number_of_owners} owner(s) "
                f"managing {number_of_employees} employee(s) ({owner_fte_pct:.0f}% ratio) "
                f"creates significant key person risk and limited management depth. "
                f"Valuation multiples reduced by {percentage_float:.0f}% to reflect transition risk "
                f"and limited scalability."
            )
        elif risk_level == "HIGH":
            description = (
                f"High management concentration: {number_of_owners} owner(s) "
                f"for {number_of_employees} employee(s) ({owner_fte_pct:.0f}% ratio) "
                f"indicates elevated key person risk. Valuation multiples reduced by "
                f"{percentage_float:.0f}% to account for management depth concerns."
            )
        elif risk_level == "MEDIUM":
            description = (
                f"Moderate management concentration: {number_of_owners} owner(s) "
                f"relative to {number_of_employees} employee(s) ({owner_fte_pct:.0f}% ratio) "
                f"suggests some key person risk. Valuation multiples reduced by "
                f"{percentage_float:.0f}% to reflect management transition considerations."
            )
        else:  # LOW
            description = (
                f"Low management concentration: {number_of_owners} owner(s) "
                f"for {number_of_employees} employee(s) ({owner_fte_pct:.0f}% ratio) "
                f"indicates adequate management depth. Minimal valuation adjustment "
                f"of {percentage_float:.0f}% applied."
            )

        return description

    def get_adjustment_details(
        self, owner_fte_ratio: Decimal, number_of_owners: int, number_of_employees: int
    ) -> Dict[str, object]:
        """
        Get comprehensive adjustment details for reporting.

        Args:
            owner_fte_ratio: Ratio of owners to employees
            number_of_owners: Number of operational owners
            number_of_employees: Number of employees

        Returns:
            Dictionary with adjustment details
        """
        adjustment = self.calculate_multiple_adjustment(
            owner_fte_ratio, number_of_owners=number_of_owners
        )
        risk_level = self.get_risk_level(owner_fte_ratio, number_of_owners=number_of_owners)
        description = self.generate_risk_description(
            owner_fte_ratio, number_of_owners, number_of_employees, adjustment
        )

        return {
            "owner_fte_ratio": round(owner_fte_ratio, 3),
            "number_of_owners": number_of_owners,
            "number_of_employees": number_of_employees,
            "adjustment_factor": adjustment,
            "adjustment_percentage": abs(adjustment) * 100,
            "risk_level": risk_level,
            "description": description,
            "methodology": "Owner Concentration Risk (Big 4 Tier-Based)",
            "applies_to": "Multiples methodology only (prevents double-counting)",
        }

    def _track_in_transparency(
        self,
        owner_fte_ratio: Decimal,
        adjustment: Decimal,
        risk_level: str,
        business_type_id: Optional[str] = None,
        tiers: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Track calculation in transparency system with calibration details."""
        try:
            # Build tier description
            tier_list = tiers if tiers else self.ADJUSTMENT_TIERS
            tier_description = "\n".join(
                [
                    f"• Ratio ≥ {from_decimal(tier['min_ratio'] * Decimal('100')):.0f}%: {from_decimal(abs(tier['adjustment']) * Decimal('100')):.0f}% ({tier['risk_level']})"
                    for tier in tier_list
                ]
            )

            # Determine calibration context
            calibration_note = ""
            if business_type_id and tiers != self.ADJUSTMENT_TIERS:
                calibration_note = (
                    f"\n\nIndustry-Specific Calibration Applied:\n"
                    f"Business type '{business_type_id}' uses calibrated thresholds "
                    f"based on owner dependency characteristics. Higher dependency industries "
                    f"(e.g., professional services) have stricter thresholds and larger discounts."
                )

            owner_fte_ratio_decimal = to_decimal(owner_fte_ratio)
            adjustment_decimal = to_decimal(adjustment)

            self.transparency_collector.add_calculation_step(
                description="Owner Concentration Risk Adjustment",
                formula=(
                    f"Adjustment based on Owner/FTE ratio tiers:\n"
                    f"{tier_description}"
                    f"{calibration_note}"
                ),
                inputs={
                    "owner_fte_ratio": from_decimal(bank_round(owner_fte_ratio_decimal, 3)),
                    "risk_level": risk_level,
                    "business_type_id": business_type_id or "universal",
                    "calibration": (
                        "industry-specific"
                        if (business_type_id and tiers != self.ADJUSTMENT_TIERS)
                        else "universal"
                    ),
                },
                outputs={
                    "multiple_adjustment": from_decimal(adjustment_decimal),
                    "adjustment_percentage": f"{from_decimal(abs(adjustment_decimal) * Decimal('100')):.0f}%",
                },
                explanation=(
                    f"Owner/FTE ratio of {from_decimal(owner_fte_ratio_decimal * Decimal('100')):.1f}% indicates {risk_level} "
                    f"management concentration risk. Applying {from_decimal(abs(adjustment_decimal) * Decimal('100')):.0f}% "
                    f"reduction to valuation multiples (EV/EBITDA, EV/Revenue) to reflect "
                    f"key person risk and limited management depth. This adjustment follows "
                    f"Big 4 advisory standards for SME valuations."
                    f"{' Industry-specific calibration was applied based on business type characteristics.' if business_type_id and tiers != self.ADJUSTMENT_TIERS else ''}"
                ),
            )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.warning(
                f"Failed to track owner concentration in transparency: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
        except BusinessTypeError as e:
            logger.warning(
                f"Unexpected error tracking owner concentration in transparency: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
