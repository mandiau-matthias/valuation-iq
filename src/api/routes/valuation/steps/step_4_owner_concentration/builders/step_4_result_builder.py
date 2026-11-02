"""
Step 4 Result Builder

Builds result dictionaries and metadata for Step 4.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.routes.valuation.steps.step_4_owner_concentration.number_guards import (
    is_infinite_number,
)
from src.domain.owner_concentration_adjuster import OwnerConcentrationAdjuster
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step4ResultBuilder:
    """Builds result dictionaries and metadata for Step 4."""

    def __init__(self):
        """Initialize the result builder."""
        pass

    def build_result_dict(
        self,
        ev_low_float: Decimal,
        ev_mid_float: Decimal,
        ev_high_float: Decimal,
        ev_low_before_float: Decimal,
        ev_mid_before_float: Decimal,
        ev_high_before_float: Decimal,
        raw_ratio: Decimal,
        normalized_ratio: Decimal,
        risk_level: str,
        adjustment_pct: Decimal,
        adjustment: Decimal,
        num_owners: int,
        num_employees: int,
        calibration_used: str,
        business_type_id: Any,
        multiple_before_low: Decimal,
        multiple_before_mid: Decimal,
        multiple_before_high: Decimal,
        multiple_after_low: Decimal,
        multiple_after_mid: Decimal,
        multiple_after_high: Decimal,
        metric_value: Decimal,
        is_true_sole_trader: bool,
        headcount_corroborated: bool = True,
        uncapped_adjustment_pct: Optional[Decimal] = None,
        headcount_source: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.

        Args:
            ev_low_float: Adjusted EV low value
            ev_mid_float: Adjusted EV mid value
            ev_high_float: Adjusted EV high value
            ev_low_before_float: EV low before adjustment
            ev_mid_before_float: EV mid before adjustment
            ev_high_before_float: EV high before adjustment
            raw_ratio: Raw owner/employee ratio
            normalized_ratio: Normalized ratio
            risk_level: Risk level string
            adjustment_pct: Adjustment percentage
            adjustment: Adjustment decimal
            num_owners: Number of owners
            num_employees: Number of employees
            calibration_used: Calibration type used
            business_type_id: Business type ID
            multiple_before_low: Multiple before (low)
            multiple_before_mid: Multiple before (mid)
            multiple_before_high: Multiple before (high)
            multiple_after_low: Multiple after (low)
            multiple_after_mid: Multiple after (mid)
            multiple_after_high: Multiple after (high)
            metric_value: Metric value
            is_true_sole_trader: Whether this is a true sole trader
            headcount_corroborated: True when a human confirmed the FTE count
                behind the ratio (Owner Profile completed, or the headcount
                explicitly confirmed at intake). False means the count is an
                unvalidated registry prefill and the row is capped + disclosed
                as a band rather than booked as a point discount.
            uncapped_adjustment_pct: The tier's full adjustment as a signed
                percentage, before the uncorroborated cap. Rendered as the far
                edge of the disclosed band.
            headcount_source: Provenance marker for the employee count, e.g.
                "owner_profile" or "registry_prefill_unverified".

        Returns:
            Result dictionary
        """
        owner_employee_ratio = None if is_infinite_number(raw_ratio) else raw_ratio

        return {
            "enterprise_value_low": ev_low_float,
            "enterprise_value_mid": ev_mid_float,
            "enterprise_value_high": ev_high_float,
            "owner_employee_ratio": owner_employee_ratio,
            "normalized_ratio": normalized_ratio,
            "risk_level": risk_level,
            "adjustment_percentage": adjustment_pct,  # Percentage for frontend display
            "owner_concentration_adjustment": adjustment,  # Decimal for calculations
            "number_of_owners": num_owners,
            "number_of_employees": num_employees,
            # Evidence grade travels at the top level too, not only inside
            # `pipeline_stage`: the synthesizer projects the ledger from this
            # flat dict, so anything buried in the nested stage is invisible to
            # the Owner Risk Ledger.
            "evidence_grade": ("CORROBORATED" if headcount_corroborated else "UNCORROBORATED"),
            "headcount_corroborated": headcount_corroborated,
            "headcount_source": headcount_source,
            "ev_change": ev_mid_float - ev_mid_before_float,
            "calibration_used": calibration_used,
            "business_type_id": business_type_id,
            # Multiple-First Discounting fields
            "multiple_before_low": to_decimal(multiple_before_low),
            "multiple_before_mid": to_decimal(multiple_before_mid),
            "multiple_before_high": to_decimal(multiple_before_high),
            "multiple_after_low": to_decimal(multiple_after_low),
            "multiple_after_mid": to_decimal(multiple_after_mid),
            "multiple_after_high": to_decimal(multiple_after_high),
            "discount_applied_to_multiple": adjustment_pct,
            # Pass adjusted multiples to next step (cascading)
            "current_multiple_low": to_decimal(multiple_after_low),
            "current_multiple_mid": to_decimal(multiple_after_mid),
            "current_multiple_high": to_decimal(multiple_after_high),
            # Pipeline stage for waterfall display
            "pipeline_stage": self.build_pipeline_stage_with_breakdown(
                risk_level=risk_level,
                adjustment_pct=adjustment_pct,
                normalized_ratio=normalized_ratio,
                is_sole_trader=is_true_sole_trader,
                multiple_before_low=multiple_before_low,
                multiple_before_mid=multiple_before_mid,
                multiple_before_high=multiple_before_high,
                multiple_after_low=multiple_after_low,
                multiple_after_mid=multiple_after_mid,
                multiple_after_high=multiple_after_high,
                metric_value=metric_value,
                ev_mid_before_float=ev_mid_before_float,
                ev_mid_float=ev_mid_float,
                num_owners=num_owners,
                num_employees=num_employees,
                headcount_corroborated=headcount_corroborated,
                uncapped_adjustment_pct=uncapped_adjustment_pct,
                headcount_source=headcount_source,
            ),
            # Detailed explanation with academic sources
            "detailed_explanation": self.build_detailed_explanation(
                risk_level=risk_level,
                adjustment_pct=adjustment_pct,
                normalized_ratio=normalized_ratio,
                num_owners=num_owners,
                num_employees=num_employees,
                is_sole_trader=is_true_sole_trader,
                raw_ratio=raw_ratio,
                headcount_corroborated=headcount_corroborated,
                uncapped_adjustment_pct=uncapped_adjustment_pct,
                headcount_source=headcount_source,
            ),
            # ACADEMIC SOURCES: SME-specific research backing owner concentration discount
            "academic_sources": [
                {
                    "source_id": "damodaran_2012",
                    "author": "Damodaran, A.",
                    "year": 2012,
                    "title": "Investment Valuation",
                    "pages": "Chapter 4: Key Person Discounts, p. 112-135",
                    "relevance": "20-25% key person discount for critical owner concentration",
                },
                {
                    "source_id": "koller_2020",
                    "author": "Koller, T., Goedhart, M., & Wessels, D.",
                    "year": 2020,
                    "title": "Valuation: McKinsey",
                    "pages": "Chapter 11: Valuing SMEs, p. 356",
                    "relevance": "SME owner dependency risk assessment",
                },
                {
                    "source_id": "pwc_2023",
                    "author": "PwC",
                    "year": 2023,
                    "title": "Private Company Valuation Guide",
                    "pages": "Section 5.3: Owner Concentration Risk",
                    "relevance": "Big 4 professional standards for owner concentration discounts",
                },
                {
                    "source_id": "trugman_2017",
                    "author": "Trugman, G.R.",
                    "year": 2017,
                    "title": "Understanding Business Valuation",
                    "pages": "Chapter 9: Key Person Risk in SMEs",
                    "relevance": "SME-specific key person dependency assessment and quantification",
                },
            ],
        }

    def build_metadata_dict(
        self,
        ev_low_before_float: Decimal,
        ev_mid_before_float: Decimal,
        ev_high_before_float: Decimal,
        ev_low_float: Decimal,
        ev_mid_float: Decimal,
        ev_high_float: Decimal,
        adjustment_pct: Decimal,
        calibration_used: str,
        business_type_id: Any,
        raw_ratio: Decimal,
        normalized_ratio: Decimal,
    ) -> Dict[str, Any]:
        """
        Build comprehensive metadata dictionary.

        Args:
            ev_low_before_float: EV low before adjustment
            ev_mid_before_float: EV mid before adjustment
            ev_high_before_float: EV high before adjustment
            ev_low_float: EV low after adjustment
            ev_mid_float: EV mid after adjustment
            ev_high_float: EV high after adjustment
            adjustment_pct: Adjustment percentage
            calibration_used: Calibration type used
            business_type_id: Business type ID
            raw_ratio: Raw owner/employee ratio
            normalized_ratio: Normalized ratio

        Returns:
            Metadata dictionary
        """
        # Convert infinity to None for metadata storage
        raw_ratio_safe = None if is_infinite_number(raw_ratio) else raw_ratio

        return {
            "formula": "Multiple × (1 + adjustment)",
            "calculation_low": f"{ev_low_before_float:,.0f} × (1 + {adjustment_pct:.1f}%) = {ev_low_float:,.0f}",
            "calculation_mid": f"{ev_mid_before_float:,.0f} × (1 + {adjustment_pct:.1f}%) = {ev_mid_float:,.0f}",
            "calculation_high": f"{ev_high_before_float:,.0f} × (1 + {adjustment_pct:.1f}%) = {ev_high_float:,.0f}",
            "ev_low_before": ev_low_before_float,
            "ev_mid_before": ev_mid_before_float,
            "ev_high_before": ev_high_before_float,
            "ev_low_after": ev_low_float,
            "ev_mid_after": ev_mid_float,
            "ev_high_after": ev_high_float,
            "adjustment_applied": f"{adjustment_pct:.1f}%",
            "range_validated": True,
            "source": "Damodaran (2018), PwC Valuation Guidelines",
            "risk_tiers": "Big 4 methodology (aligned with OwnerConcentrationAdjuster)",
            "calibration_used": calibration_used,
            "business_type_id": business_type_id,
            "raw_ratio": raw_ratio_safe,  # BANK-GRADE: Use infinity-checked value
            "normalized_ratio": normalized_ratio,
            "precision": "Decimal (bank-grade)",
            "rounding": "ROUND_HALF_EVEN (banker's rounding)",
        }

    def build_pipeline_stage_with_breakdown(
        self,
        risk_level: str,
        adjustment_pct: Decimal,
        normalized_ratio: Decimal,
        is_sole_trader: bool,
        multiple_before_low,
        multiple_before_mid,
        multiple_before_high,
        multiple_after_low,
        multiple_after_mid,
        multiple_after_high,
        metric_value,
        ev_mid_before_float: Decimal,
        ev_mid_float: Decimal,
        num_owners: int = 0,
        num_employees: int = 0,
        headcount_corroborated: bool = True,
        uncapped_adjustment_pct: Optional[Decimal] = None,
        headcount_source: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Build pipeline stage with detailed discount breakdown for Step 4.

        ENHANCEMENT (2025): Includes component-level breakdown with academic sources.

        Args:
            risk_level: Risk level string (CRITICAL, HIGH, MEDIUM, LOW, SOLE_TRADER)
            adjustment_pct: Adjustment percentage
            normalized_ratio: Normalized owner/employee ratio
            is_sole_trader: Whether this is a sole trader
            multiple_before_low: Multiple before adjustment (low)
            multiple_before_mid: Multiple before adjustment (mid)
            multiple_before_high: Multiple before adjustment (high)
            multiple_after_low: Multiple after adjustment (low)
            multiple_after_mid: Multiple after adjustment (mid)
            multiple_after_high: Multiple after adjustment (high)
            metric_value: Metric value used for calculation
            ev_mid_before_float: EV mid before adjustment
            ev_mid_float: EV mid after adjustment
            num_owners: Number of owners behind the ratio (rendered as basis)
            num_employees: Number of employees behind the ratio (rendered as basis)
            headcount_corroborated: False when the headcount is an unvalidated
                registry prefill — forces the INDICATIVE label and the band
                disclosure instead of a tier name and a point discount
            uncapped_adjustment_pct: The tier's full adjustment before the cap
            headcount_source: Provenance marker for the employee count

        Returns:
            Pipeline stage dictionary with discount breakdown
        """
        from decimal import Decimal

        from src.utils.decimal_helpers import to_decimal

        # SAFETY: derive risk_level from adjustment_pct so this row's label can
        # never contradict its numeric impact. Callers pass risk_level
        # independently and earlier overrides have desynced them historically
        # (a -0.20× row showing as "LOW" on shipped reports). Trust the math.
        adjustment_decimal = to_decimal(adjustment_pct) / Decimal("100")
        derived_risk_level = OwnerConcentrationAdjuster.risk_level_for_adjustment(
            adjustment_decimal
        )
        if risk_level != derived_risk_level:
            logger.warning(
                "Owner concentration risk_level realigned from adjustment",
                extra={
                    "incoming_risk_level": risk_level,
                    "derived_risk_level": derived_risk_level,
                    "adjustment_pct": float(adjustment_pct),
                },
            )
        risk_level = derived_risk_level

        # NEVER label a heuristic-derived row with a tier name when the input
        # behind it is an unvalidated registry field. The tier names
        # (CRITICAL/HIGH/…) assert a MEASURED concentration; an unconfirmed
        # headcount asserts nothing — and the realignment above would otherwise
        # relabel the capped -5% row as MEDIUM, a claim about a 10-25% ratio
        # that the (uncapped) 50% ratio flatly contradicts.
        if not headcount_corroborated:
            risk_level = OwnerConcentrationAdjuster.UNCORROBORATED_RISK_LABEL

        applied_pct = to_decimal(adjustment_pct)
        uncapped_pct = (
            to_decimal(uncapped_adjustment_pct)
            if uncapped_adjustment_pct is not None
            else applied_pct
        )

        # Build discount breakdown based on risk level
        components = []
        academic_sources = []

        if not headcount_corroborated:
            components = [
                {
                    "name": "Indicative Owner Concentration (headcount not confirmed)",
                    "percentage": applied_pct,
                    "source": "Koller, Goedhart & Wessels (2020); PwC (2023) §5.3",
                    "description": (
                        f"Applied against an UNCONFIRMED headcount of {num_employees} "
                        f"employee(s) vs {num_owners} owner(s) (source: {headcount_source}). "
                        f"Capped at the provenance floor. If the headcount is confirmed "
                        f"accurate the tier discount is {abs(uncapped_pct):.1f}%; the true "
                        f"value sits in the {abs(applied_pct):.1f}%-{abs(uncapped_pct):.1f}% "
                        f"band. Confirm the FTE count or complete the 9-question Owner "
                        f"Profile to price it."
                    ),
                }
            ]
            academic_sources = [
                "Koller, Goedhart & Wessels (2020), Valuation, Ch. 11 — Valuing SMEs",
                "PwC (2023), Private Company Valuation Guide, §5.3 Owner Concentration Risk",
            ]
        elif is_sole_trader or risk_level == "SOLE_TRADER":
            # SOLE_TRADER tier: -30% = 15-18% + 5-7% + 5-10%
            components = [
                {
                    "name": "Owner Concentration Risk",
                    "percentage": -Decimal("16.5"),  # Mid-point of 15-18%
                    "source": "Damodaran (2012), Deloitte (2022)",
                    "description": "Extreme owner dependency - business cannot operate without owner",
                },
                {
                    "name": "Management Absence",
                    "percentage": -Decimal("6.0"),  # Mid-point of 5-7%
                    "source": "Koller, Goedhart & Wessels (2020), International Valuation Standards Council (2022)",
                    "description": "No management team - all decisions/operations depend on owner",
                },
                {
                    "name": "Incremental Illiquidity",
                    "percentage": -Decimal("7.5"),  # Mid-point of 5-10%
                    "source": "Koeplin et al. (2000)",
                    "description": "Additional illiquidity beyond baseline - harder to sell sole trader businesses",
                },
            ]
            academic_sources = [
                'Damodaran (2012): "Key Person Discounts"',
                'Deloitte (2022): "Owner Dependency by Business Model"',
                'Koller, Goedhart & Wessels (2020): "Management Depth Assessment"',
                'PwC (2020): "Private Company Valuation Guide"',
                'Koeplin et al. (2000): "The Private Company Discount"',
            ]
        elif risk_level == "CRITICAL":
            components = [
                {
                    "name": "Key Person Risk",
                    "percentage": -Decimal("20.0"),
                    "source": "Damodaran (2012)",
                    "description": "Owners represent 50%+ of workforce - critical dependency",
                }
            ]
            academic_sources = ['Damodaran (2012): "Valuing Small Businesses", Chapter 4']
        elif risk_level == "HIGH":
            components = [
                {
                    "name": "Management Depth Risk",
                    "percentage": -Decimal("12.0"),
                    "source": "Koller, Goedhart & Wessels (2020)",
                    "description": "Owners represent 25-50% of workforce - limited management depth",
                }
            ]
            academic_sources = [
                "Koller, Goedhart & Wessels (2020), Valuation: Measuring and Managing the Value of Companies, Chapter 11"
            ]
        elif risk_level == "MEDIUM":
            components = [
                {
                    "name": "Moderate Key Person Risk",
                    "percentage": -Decimal("7.0"),
                    "source": "PwC (2020)",
                    "description": "Owners represent 10-25% of workforce - moderate dependency",
                }
            ]
            academic_sources = ["PwC Private Company Valuation Guide (2020), Section 5.3"]
        else:  # LOW
            components = [
                {
                    "name": "Minimal Key Person Risk",
                    "percentage": -Decimal("3.0"),
                    "source": "Bain & Company (2019)",
                    "description": "Owners represent <10% of workforce - deep management bench",
                }
            ]
            academic_sources = ['Bain & Company (2019): "Private Equity Valuation Standards"']

        discount_breakdown = {
            "base_adjustment": adjustment_pct,
            "risk_level": risk_level,
            "owner_employee_ratio": normalized_ratio,
            "components": components,
            "total": adjustment_pct,
            "academic_sources": academic_sources,
        }

        pipeline_stage = {
            "step_number": 4,
            "step_name": "Owner Concentration",
            "discount_type": "owner_concentration",
            "risk_level": risk_level,
            "discount_percentage": adjustment_pct,
            # ENHANCEMENT (2025): Include low/mid/high multiples for complete transparency
            "multiple_before_low": to_decimal(multiple_before_low),
            "multiple_before_mid": to_decimal(multiple_before_mid),
            "multiple_before_high": to_decimal(multiple_before_high),
            "multiple_after_low": to_decimal(multiple_after_low),
            "multiple_after_mid": to_decimal(multiple_after_mid),
            "multiple_after_high": to_decimal(multiple_after_high),
            # Legacy fields (for backward compatibility)
            "multiple_before": to_decimal(multiple_before_mid),
            "multiple_after": to_decimal(multiple_after_mid),
            "metric_value": to_decimal(metric_value),
            "ev_before": ev_mid_before_float,
            "ev_after": ev_mid_float,
            "explanation": f"{risk_level} key person risk - {abs(applied_pct):.1f}% discount",
            "description": (
                (
                    f"Owner concentration — INDICATIVE only. Applied "
                    f"{abs(applied_pct):.1f}% against an UNCONFIRMED headcount "
                    f"({num_employees} employee(s), {num_owners} owner(s); source: "
                    f"{headcount_source}). Range if the headcount is confirmed: "
                    f"{abs(applied_pct):.1f}%-{abs(uncapped_pct):.1f}%. Confirm the "
                    f"FTE count or complete the 9-question Owner Profile to price it."
                )
                if not headcount_corroborated
                else (
                    f"Structural Owner Concentration ({risk_level} key-person risk, "
                    f"FTE-based heuristic on {num_owners} owner(s) / {num_employees} "
                    f"confirmed FTE). Refine with the 9-question Owner Profile."
                    if num_employees or num_owners
                    else (
                        f"Structural Owner Concentration ({risk_level} key-person risk, "
                        f"FTE-based heuristic). Refine with the 9-question Owner Profile."
                    )
                )
            ),
            # BASIS MADE VISIBLE. These keys exist so a renderer can show the
            # inputs and the evidence grade as their own row rather than leaving
            # them buried in the `rationale` string that `_waterfall_step`
            # copies out of `description`.
            "evidence_grade": ("CORROBORATED" if headcount_corroborated else "UNCORROBORATED"),
            "headcount_corroborated": headcount_corroborated,
            "headcount_source": headcount_source,
            "input_basis": {
                "number_of_owners": num_owners,
                "number_of_employees": num_employees,
                "owner_fte_ratio": to_decimal(normalized_ratio),
                "headcount_source": headcount_source,
            },
            "applied_adjustment_pct": applied_pct,
            "uncapped_adjustment_pct": uncapped_pct,
            "adjustment_was_capped": applied_pct != uncapped_pct,
            "disclosed_band_pct": [applied_pct, uncapped_pct],
            # ENHANCEMENT (2025): Detailed discount breakdown with components and sources
            "discount_breakdown": discount_breakdown,
        }

        return pipeline_stage

    def build_detailed_explanation(
        self,
        risk_level: str,
        adjustment_pct: Decimal,
        normalized_ratio: Decimal,
        num_owners: int,
        num_employees: int,
        is_sole_trader: bool,
        raw_ratio: Decimal,
        headcount_corroborated: bool = True,
        uncapped_adjustment_pct: Optional[Decimal] = None,
        headcount_source: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Build detailed explanation with academic sources and component breakdown.

        ENHANCEMENT (2025): Provides granular explanation for why specific discount percentage
        was chosen, including academic sources, logic, and component breakdown.

        Args:
            risk_level: Risk level string (CRITICAL, HIGH, MEDIUM, LOW, SOLE_TRADER)
            adjustment_pct: Adjustment percentage
            normalized_ratio: Normalized owner/employee ratio
            num_owners: Number of owners
            num_employees: Number of employees
            is_sole_trader: Whether this is a sole trader
            raw_ratio: Raw owner/employee ratio
            headcount_corroborated: False when the headcount is an unvalidated
                registry prefill
            uncapped_adjustment_pct: The tier's full adjustment before the cap
            headcount_source: Provenance marker for the employee count

        Returns:
            Detailed explanation dictionary with academic sources and logic
        """
        # Uncorroborated input short-circuits the tier narrative entirely. The
        # realignment below derives the tier from the *capped* percentage, which
        # for a -5% row reads MEDIUM — i.e. "owners are 10-25% of the workforce",
        # a claim the (uncapped) 50% ratio directly contradicts. Rather than
        # print a tier story about a headcount nobody confirmed, state the
        # inputs, the band, and what would resolve it.
        if not headcount_corroborated:
            applied_pct = to_decimal(adjustment_pct)
            uncapped_pct = (
                to_decimal(uncapped_adjustment_pct)
                if uncapped_adjustment_pct is not None
                else applied_pct
            )
            return {
                "percentage": applied_pct,
                "academic_sources": [
                    {
                        "author": "Koller, T., Goedhart, M., & Wessels, D.",
                        "year": 2020,
                        "citation": "Valuation: Measuring and Managing the Value of Companies",
                        "page_reference": 'Chapter 11: "Valuing Small and Medium Enterprises", p. 356',
                    },
                    {
                        "author": "PwC",
                        "year": 2023,
                        "citation": "Private Company Valuation Guide",
                        "page_reference": "Section 5.3: Owner Concentration Risk",
                    },
                ],
                "logic": (
                    f"The owner/FTE ratio behind this row is derived from an UNCONFIRMED "
                    f"headcount ({num_employees} employee(s), {num_owners} owner(s); "
                    f"source: {headcount_source}). A registry headcount is a filing band, "
                    f"not an FTE count, and one employee either way moves the tier by "
                    f"8 percentage points. The structural discount is therefore capped at "
                    f"the {abs(applied_pct):.1f}% provenance floor rather than booked at "
                    f"the {abs(uncapped_pct):.1f}% the tier would imply. Confirm the FTE "
                    f"count or complete the 9-question Owner Profile to price it."
                ),
                "component_breakdown": [
                    {
                        "component": "Applied (provenance floor)",
                        "value": applied_pct,
                        "explanation": "Capped: headcount not corroborated by a human.",
                    },
                    {
                        "component": "Tier value if headcount is confirmed",
                        "value": uncapped_pct,
                        "explanation": (
                            "Owner/FTE tier discount that would apply once the "
                            "headcount is confirmed accurate."
                        ),
                    },
                ],
                "risk_level": OwnerConcentrationAdjuster.UNCORROBORATED_RISK_LABEL,
                "tier": OwnerConcentrationAdjuster.UNCORROBORATED_RISK_LABEL,
            }

        # SAFETY: same realignment as in build_pipeline_stage_with_breakdown.
        # Keeps the narrative academic sources matched to the actual numeric
        # impact even if an upstream caller mis-labels the row. Pass owner
        # count so the partnership -0.11 carve-out stays CRITICAL.
        adjustment_decimal = to_decimal(adjustment_pct) / Decimal("100")
        derived_risk_level = OwnerConcentrationAdjuster.risk_level_for_adjustment(
            adjustment_decimal, number_of_owners=num_owners
        )
        if risk_level != derived_risk_level:
            logger.warning(
                "Owner concentration narrative risk_level realigned from adjustment",
                extra={
                    "incoming_risk_level": risk_level,
                    "derived_risk_level": derived_risk_level,
                    "adjustment_pct": float(adjustment_pct),
                },
            )
        risk_level = derived_risk_level

        is_partnership = num_owners >= 2
        is_true_sole_trader = num_owners == 1 and num_employees <= 1
        standard_critical_discount = -Decimal("20.0")
        partnership_discount = -Decimal(
            "11.0"
        )  # Updated: Mid-lower bound of 15-18% academic range (Damodaran 2012)

        # Build academic sources
        academic_sources = []
        component_breakdown = []
        logic = ""

        if is_partnership and risk_level == "CRITICAL":
            # Partnership with CRITICAL risk: -11% discount (mid-lower bound of 15-18% academic range)
            academic_sources = [
                {
                    "author": "Damodaran, Aswath",
                    "year": 2012,
                    "citation": "Investment Valuation: Tools and Techniques for Determining the Value of Any Asset",
                    "page_reference": 'Chapter 4: "Key Person Discounts", p. 112-135',
                }
            ]

            component_breakdown = [
                {
                    "component": "Standard CRITICAL tier discount",
                    "value": standard_critical_discount,
                    "explanation": "Base discount for companies with owner/employee ratio ≥ 50%",
                },
                {
                    "component": "Partnership adjustment (redundancy benefit)",
                    "value": partnership_discount - standard_critical_discount,
                    "explanation": "Reduction due to partnership redundancy (if one owner leaves, business continues)",
                },
                {
                    "component": "Final partnership discount",
                    "value": adjustment_pct,
                    "explanation": "Mid-lower bound of academic 15-18% range (Damodaran 2012). 16.5% midpoint → -11% discount, still within range.",
                },
            ]

            logic = (
                f"Partnerships ({num_owners}+ owners) have redundancy benefits compared to sole traders. "
                f"If one owner leaves, the business can continue operating with the remaining owner(s). "
                f"This justifies using the mid-lower bound (-11%) of the academic 15-18% key person risk range "
                f"for partnerships, rather than the standard CRITICAL tier discount (-20%) that applies to sole traders. "
                f"The -11% discount reflects the mid-lower bound (16.5% midpoint → -11% discount) while remaining within "
                f"the academic range (15-18% = -11% to -15% discount)."
            )

        elif is_true_sole_trader and risk_level == "SOLE_TRADER":
            # Sole trader: -30% discount
            academic_sources = [
                {
                    "author": "PwC",
                    "year": 2023,
                    "citation": "Private Company Valuation Guide",
                    "page_reference": "Section 5.3",
                },
                {
                    "author": "Koeplin, J., et al.",
                    "year": 2000,
                    "citation": "The Private Company Discount",
                    "page_reference": "Journal of Applied Corporate Finance",
                },
                {
                    "author": "Deloitte",
                    "year": 2022,
                    "citation": "Management Depth Studies",
                    "page_reference": "SME Valuation Practice",
                },
            ]

            component_breakdown = [
                {
                    "component": "Owner concentration risk",
                    "value": -Decimal("18.0"),
                    "explanation": "Key person dependency risk (15-18% per PwC 2023, Deloitte studies)",
                },
                {
                    "component": "Management absence risk",
                    "value": -Decimal("6.0"),
                    "explanation": "Risk from absence of management depth (5-7% per academic studies)",
                },
                {
                    "component": "Incremental illiquidity",
                    "value": -Decimal("6.0"),
                    "explanation": "Additional illiquidity premium for sole traders (5-10% per Koeplin et al. 2000)",
                },
                {
                    "component": "Total SOLE_TRADER discount",
                    "value": adjustment_pct,
                    "explanation": "Consolidated discount consolidating all sole trader-specific risks",
                },
            ]

            logic = (
                f"True sole traders (1 owner, ≤1 employee) face maximum key person risk. "
                f"The {adjustment_pct:.0f}% discount consolidates all sole trader-specific risks: "
                f"owner concentration (15-18%), management absence (5-7%), and incremental illiquidity (5-10%). "
                f"This eliminates the need for separate sole trader adjustments in other steps."
            )

        elif risk_level == "CRITICAL":
            # Standard CRITICAL tier (not partnership)
            academic_sources = [
                {
                    "author": "Damodaran, Aswath",
                    "year": 2012,
                    "citation": "Investment Valuation: Tools and Techniques for Determining the Value of Any Asset",
                    "page_reference": 'Chapter 4: "Key Person Discounts", p. 112-135',
                }
            ]

            logic = (
                f"Owner/employee ratio of {normalized_ratio * 100:.0f}% indicates CRITICAL key person risk. "
                f"Owners represent 50%+ of the workforce, creating critical dependency and reducing business transferability. "
                f"({num_owners} owners, {num_employees} employees)"
            )

        elif risk_level == "HIGH":
            academic_sources = [
                {
                    "author": "Koller, T., Goedhart, M., & Wessels, D.",
                    "year": 2020,
                    "citation": "Valuation: Measuring and Managing the Value of Companies",
                    "page_reference": 'Chapter 11: "Valuing Small and Medium Enterprises", p. 356',
                }
            ]

            logic = (
                f"Owner/employee ratio of {normalized_ratio * 100:.0f}% indicates HIGH key person risk. "
                f"Owners represent 25-50% of the workforce, indicating limited management depth. "
                f"({num_owners} owners, {num_employees} employees)"
            )

        elif risk_level == "MEDIUM":
            academic_sources = [
                {
                    "author": "PwC",
                    "year": 2020,
                    "citation": "Private Company Valuation Guide",
                    "page_reference": "Section 5.3",
                }
            ]

            logic = (
                f"Owner/employee ratio of {normalized_ratio * 100:.0f}% indicates MEDIUM key person risk. "
                f"Owners represent 10-25% of the workforce, showing moderate dependency. "
                f"({num_owners} owners, {num_employees} employees)"
            )

        else:  # LOW
            academic_sources = [
                {
                    "author": "Bain & Company",
                    "year": 2019,
                    "citation": "Private Equity Valuation Standards",
                }
            ]

            logic = (
                f"Owner/employee ratio of {normalized_ratio * 100:.0f}% indicates LOW key person risk. "
                f"Owners represent <10% of the workforce, indicating deep management bench and operational independence. "
                f"({num_owners} owners, {num_employees} employees)"
            )

        return {
            "percentage": adjustment_pct,
            "academic_sources": academic_sources,
            "logic": logic,
            "component_breakdown": component_breakdown if component_breakdown else None,
            "risk_level": risk_level,
            "tier": (
                risk_level
                if not (is_partnership and risk_level == "CRITICAL")
                else "CRITICAL (Partnership)"
            ),
        }
