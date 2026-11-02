"""
SME Calibration Coordinator

Orchestrates SME calibration, margin premium, and growth risk adjustments for Step 2.
"""

from decimal import Decimal
from typing import Dict, Optional, Tuple

from src.api.routes.valuation.benchmark_contract_utils import (
    extract_request_resolved_benchmark_contract,
)
from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory
from src.utils.decimal_helpers import to_decimal
from src.utils.fiscal_year import get_current_filing_year
from src.utils.logging import get_logger

from ...utils.benchmark_helpers import calibrate_multiple_for_sme
from .sme_growth_history import (
    apply_growth_risk_adjustment,
    calculate_revenue_decline_indicators,
    ensure_decimal,
)

logger = get_logger(__name__)


def _ensure_decimal(val: object) -> Optional[Decimal]:
    return ensure_decimal(val)


class SMECalibrationCoordinator:
    """
    Coordinates SME calibration and adjustment operations.
    """

    def __init__(self, logger_instance=None) -> None:
        self.logger = logger_instance or logger

    def apply_sme_calibration_and_adjustments(
        self,
        request: object,
        multiples_data: Dict[str, object],
        revenue: Decimal,
        ebitda_margin: Decimal,
        business_category: Optional[BusinessTypeCategory],
    ) -> Tuple[Dict[str, object], Dict[str, object]]:
        """
        Apply SME calibration, margin premium, and growth risk adjustments.

        Args:
            request: The valuation request
            multiples_data: Multiples data dictionary
            revenue: Revenue value
            ebitda_margin: EBITDA margin
            business_category: Business type category

        Returns:
            Tuple of (updated_multiples_data, sme_calibration_data)
        """
        _DECIMAL_KEYS = [
            "ev_ebitda",
            "ev_ebitda_p10",
            "ev_ebitda_p25",
            "ev_ebitda_p50",
            "ev_ebitda_p75",
            "ev_ebitda_p90",
            "ev_revenue",
            "ev_revenue_p25",
            "ev_revenue_p50",
            "ev_revenue_p75",
        ]
        for _k in _DECIMAL_KEYS:
            if _k in multiples_data and multiples_data[_k] is not None:
                multiples_data[_k] = _ensure_decimal(multiples_data[_k])

        ev_ebitda_multiple_raw = multiples_data.get("ev_ebitda")
        ev_revenue_multiple_raw = multiples_data.get("ev_revenue")
        revenue_float = to_decimal(revenue) if revenue else Decimal("0.0")

        # Apply SME calibration
        ev_ebitda_multiple, ebitda_calibration_factor, ebitda_calibration_explanation = (
            self._calibrate_ebitda_multiple(
                ev_ebitda_multiple_raw, revenue_float, request, business_category
            )
        )

        # Write calibrated EBITDA multiple back to multiples_data immediately
        if ev_ebitda_multiple is not None:
            multiples_data["ev_ebitda"] = _ensure_decimal(ev_ebitda_multiple)
            if ebitda_calibration_factor != Decimal("1.0"):
                for key in [
                    "ev_ebitda_p10",
                    "ev_ebitda_p25",
                    "ev_ebitda_p50",
                    "ev_ebitda_p75",
                    "ev_ebitda_p90",
                ]:
                    if multiples_data.get(key) is not None:
                        multiples_data[key] = (
                            _ensure_decimal(multiples_data[key]) * ebitda_calibration_factor
                        )

        ev_revenue_multiple, revenue_calibration_factor, revenue_calibration_explanation = (
            self._calibrate_revenue_multiple(
                ev_revenue_multiple_raw, revenue_float, request, business_category
            )
        )

        # Write calibrated Revenue multiple back to multiples_data immediately
        if ev_revenue_multiple is not None:
            multiples_data["ev_revenue"] = _ensure_decimal(ev_revenue_multiple)
            if revenue_calibration_factor != Decimal("1.0"):
                for key in ["ev_revenue_p25", "ev_revenue_p50", "ev_revenue_p75"]:
                    if multiples_data.get(key) is not None:
                        multiples_data[key] = (
                            _ensure_decimal(multiples_data[key]) * revenue_calibration_factor
                        )

        # Calculate revenue decline indicators for margin premium
        revenue_cagr_for_margin, recent_yoy_decline_for_margin = (
            self._calculate_revenue_decline_indicators(request)
        )

        # Resolve industry-average margin from Titan enrichment or fallback
        industry_avg_margin = self._resolve_industry_avg_margin(request, multiples_data)

        # Apply margin premium (continuous linear function)
        ev_ebitda_multiple, ebitda_margin_premium, ebitda_margin_premium_explanation = (
            self._apply_margin_premium(
                ev_ebitda_multiple,
                ebitda_margin,
                revenue_cagr_for_margin,
                recent_yoy_decline_for_margin,
                multiples_data,
                industry_avg_margin=industry_avg_margin,
            )
        )

        # Apply growth risk adjustment (decline discount) AND growth premium
        (
            ev_ebitda_multiple,
            growth_risk_adjustment,
            growth_risk_adjustment_explanation,
            revenue_cagr,
            recent_yoy_decline,
            recent_year_adjustment,
        ) = self._apply_growth_risk_adjustment(request, ev_ebitda_multiple, multiples_data)

        # WORLD-CLASS: Extract growth stage and business type info from rationale
        # The rationale from SMEMultipleSelector includes: growth stage, business type, owner dependency, margin adjustments
        growth_stage_info = None
        business_type_info = None
        adjustment_breakdown = []

        # Parse rationale to extract structured information for HTML display
        if ebitda_calibration_explanation:
            # The rationale format: "Small SME (revenue €2,000,000) in services industry: 5.0x EBITDA per VFB Belgium (2024) / Vlerick (2023). Business type: consulting. Growth stage: startup. Growth stage adjustment (-8.3%): startup stage (higher risk) per founded year and historical data analysis. Owner dependency adjustment (-15%) per business type 'consulting'..."
            rationale_parts = ebitda_calibration_explanation.split(". ")

            for part in rationale_parts:
                if "Growth stage:" in part:
                    growth_stage_info = part.replace("Growth stage:", "").strip()
                elif "Business type:" in part:
                    business_type_info = part.replace("Business type:", "").strip()
                elif "adjustment" in part.lower() and ("%" in part or "reduction" in part.lower()):
                    adjustment_breakdown.append(part)

        # Build SME calibration data with comprehensive rationale
        sme_calibration_data = {
            "applied": revenue_float < 5_000_000,
            "revenue": revenue_float,
            "ebitda_multiple": {
                "raw": ev_ebitda_multiple_raw,
                "calibrated": (
                    ev_ebitda_multiple - ebitda_margin_premium
                    if ebitda_margin_premium > 0
                    else ev_ebitda_multiple
                ),
                "final": ev_ebitda_multiple,
                "calibration_factor": ebitda_calibration_factor,
                "margin_premium": ebitda_margin_premium,
                "margin_premium_explanation": ebitda_margin_premium_explanation,
                "growth_risk_adjustment": growth_risk_adjustment,
                "growth_risk_adjustment_explanation": growth_risk_adjustment_explanation,
                "revenue_cagr": revenue_cagr,
                "recent_yoy_decline": recent_yoy_decline,
                "recent_year_adjustment": recent_year_adjustment,
                "reduction_percentage": (
                    (1 - ebitda_calibration_factor) * 100
                    if ebitda_calibration_factor < Decimal("1.0")
                    else 0
                ),
                "explanation": ebitda_calibration_explanation,  # WORLD-CLASS: Full rationale from SMEMultipleSelector
                "rationale": ebitda_calibration_explanation,  # WORLD-CLASS: Alias for template compatibility
                "growth_stage": growth_stage_info,  # WORLD-CLASS: Growth stage (startup/growth/mature)
                "business_type": business_type_info,  # WORLD-CLASS: Business type ID
                "adjustment_breakdown": adjustment_breakdown,  # WORLD-CLASS: List of all adjustments applied
            },
            "revenue_multiple": {
                "raw": ev_revenue_multiple_raw,
                "calibrated": ev_revenue_multiple,
                "calibration_factor": revenue_calibration_factor,
                "reduction_percentage": (
                    (1 - revenue_calibration_factor) * 100
                    if revenue_calibration_factor < Decimal("1.0")
                    else 0
                ),
                "explanation": revenue_calibration_explanation,
            },
            "academic_reference": "McKinsey Valuation (2015), Duff & Phelps Valuation Handbook (2024)",
            "rationale": (
                "Database multiples (Capital IQ, Bloomberg, PitchBook) are biased toward larger companies (€50M+ revenue). "
                "For SMEs, systematic calibration required to avoid overvaluation. "
                "McKinsey standard: Multiples become reliable at €5M+ revenue."
            ),
        }

        return multiples_data, sme_calibration_data

    def _calibrate_ebitda_multiple(
        self,
        ev_ebitda_multiple_raw: Optional[Decimal],
        revenue_float: Decimal,
        request: object,
        business_category: Optional[BusinessTypeCategory],
    ) -> Tuple[Optional[Decimal], Decimal, str]:
        """
        Calibrate EBITDA multiple for SME.

        BANK-GRADE: Returns Decimal values (not float).

        UPDATED (January 2026):
        - Now extracts sme_calibration from request for PRIORITY 1 calibration
        - Priority cascade: Titan enrichment > DatabaseDrivenDefaults > Hardcoded
        """
        if ev_ebitda_multiple_raw is not None:
            if extract_request_resolved_benchmark_contract(request):
                self.logger.info(
                    "⏭️ SME EBITDA overlay skipped — resolved Upswitch Index benchmark contract is authoritative",
                    extra={"business_type_id": getattr(request, "business_type_id", None)},
                )
                return (
                    _ensure_decimal(ev_ebitda_multiple_raw),
                    Decimal("1.0"),
                    "SME overlay skipped — resolved Upswitch Index benchmark contract",
                )

            # WORLD-CLASS: Extract business_type_id and growth stage data from request
            business_type_id = getattr(request, "business_type_id", None) or getattr(
                request, "business_type", None
            )
            founded_year = getattr(request, "founding_year", None) or getattr(
                request, "founded_year", None
            )
            current_year = (
                getattr(getattr(request, "current_year_data", None), "year", None)
                or getattr(request, "current_year", None)
                or get_current_filing_year()
            )
            historical_data = None

            # PRIORITY 1: Extract sme_calibration from Titan request (database-driven multiples)
            # This contains tier-specific multiples: ev_ebitda_micro/small/medium, size_premium_*, etc.
            sme_calibration = getattr(request, "sme_calibration", None)

            if sme_calibration:
                # DEBUG: the two "SME ebitda/revenue calibration using Titan
                # enrichment" detail lines below carry the canonical signal.
                self.logger.debug(
                    "✅ [SME-CALIBRATION] Titan-provided sme_calibration found in request",
                    extra={
                        "has_ev_ebitda_micro": sme_calibration.get("ev_ebitda_micro") is not None,
                        "has_ev_ebitda_small": sme_calibration.get("ev_ebitda_small") is not None,
                        "has_ev_ebitda_medium": sme_calibration.get("ev_ebitda_medium") is not None,
                        "calibration_source": sme_calibration.get("calibration_source"),
                    },
                )

            # Extract historical data if available (from historical_years_data or similar)
            if hasattr(request, "historical_years_data") and request.historical_years_data:
                historical_data = [
                    {
                        "year": (
                            getattr(h, "year", None) or h.get("year")
                            if isinstance(h, dict)
                            else None
                        ),
                        "revenue": (
                            getattr(h, "revenue", None) or h.get("revenue")
                            if isinstance(h, dict)
                            else None
                        ),
                    }
                    for h in request.historical_years_data
                    if (getattr(h, "revenue", None) or (isinstance(h, dict) and h.get("revenue")))
                ]

            ev_ebitda_multiple, calibration_factor, explanation = calibrate_multiple_for_sme(
                database_multiple=ev_ebitda_multiple_raw,
                revenue=revenue_float,
                industry=getattr(request, "industry", "unknown"),
                business_category=business_category,
                business_type=business_type_id,  # WORLD-CLASS: Pass business type for adjustments
                founded_year=founded_year,  # WORLD-CLASS: Pass founded year for growth stage determination
                current_year=current_year,  # WORLD-CLASS: Pass current year for growth stage determination
                historical_data=historical_data,  # WORLD-CLASS: Pass historical data for growth stage determination
                sme_calibration=sme_calibration,  # PRIORITY 1: Titan-provided SME calibration from business_types DB
                country_code=getattr(request, "country_code", None),
            )
            # BANK-GRADE: calibration_factor is already Decimal from calibrate_multiple_for_sme
            return ev_ebitda_multiple, calibration_factor, explanation
        return None, Decimal("1.0"), "No EBITDA multiple available"

    def _calibrate_revenue_multiple(
        self,
        ev_revenue_multiple_raw: Optional[Decimal],
        revenue_float: Decimal,
        request: object,
        business_category: Optional[BusinessTypeCategory],
    ) -> Tuple[Optional[Decimal], Decimal, Optional[str]]:
        """
        Calibrate Revenue multiple for SME.

        BANK-GRADE: Returns Decimal values (not float).

        UPDATED (January 2026):
        - Now extracts sme_calibration from request for PRIORITY 1 calibration
        """
        if ev_revenue_multiple_raw is not None:
            if extract_request_resolved_benchmark_contract(request):
                return (
                    _ensure_decimal(ev_revenue_multiple_raw),
                    Decimal("1.0"),
                    "SME overlay skipped — resolved Upswitch Index benchmark contract",
                )

            # PRIORITY 1: Extract sme_calibration from Titan request (database-driven multiples)
            sme_calibration = getattr(request, "sme_calibration", None)

            ev_revenue_multiple, calibration_factor, explanation = calibrate_multiple_for_sme(
                database_multiple=ev_revenue_multiple_raw,
                revenue=revenue_float,
                industry=getattr(request, "industry", "unknown"),
                business_category=business_category,
                sme_calibration=sme_calibration,
                multiple_type="revenue",
                country_code=getattr(request, "country_code", None),
            )
            # BANK-GRADE: calibration_factor is already Decimal from calibrate_multiple_for_sme
            return ev_revenue_multiple, calibration_factor, explanation
        return None, Decimal("1.0"), "No Revenue multiple available"

    def _calculate_revenue_decline_indicators(
        self, request: object
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        return calculate_revenue_decline_indicators(request, logger_instance=self.logger)

    def _resolve_industry_avg_margin(
        self, request: object, multiples_data: Dict[str, object]
    ) -> Decimal:
        """
        Resolve the industry-average EBITDA margin from Titan enrichment,
        business_type_calibration, or multiples_data. Falls back to 12.5%.
        """
        # Priority 1: Titan-provided industry_benchmarks.typical_ebitda_margin
        titan_bench = getattr(request, "industry_benchmarks", None)
        if isinstance(titan_bench, dict):
            typical = titan_bench.get("typical_ebitda_margin")
            if isinstance(typical, dict):
                median = typical.get("median")
                if median is not None:
                    val = _ensure_decimal(median)
                    if val is not None and val > Decimal("0"):
                        # Stored as fraction (0.12) or percentage (12.0)
                        return val * Decimal("100") if val < Decimal("1") else val

        # Priority 2: business_type_calibration.typical_ebitda_margin
        calibration = getattr(request, "business_type_calibration", None)
        if calibration is not None:
            typical = getattr(calibration, "typical_ebitda_margin", None)
            if typical is not None:
                val = _ensure_decimal(typical)
                if val is not None and val > Decimal("0"):
                    return val * Decimal("100") if val < Decimal("1") else val

        # Priority 3: multiples_data (sometimes carries margin data)
        md_margin = multiples_data.get("avg_ebitda_margin")
        if md_margin is None:
            md_margin = multiples_data.get("industry_ebitda_margin")
        if md_margin is not None:
            val = _ensure_decimal(md_margin)
            if val is not None and val > Decimal("0"):
                return val * Decimal("100") if val < Decimal("1") else val

        return Decimal("12.5")

    def _apply_margin_premium(
        self,
        ev_ebitda_multiple: Optional[Decimal],
        ebitda_margin: Decimal,
        revenue_cagr: Optional[Decimal],
        recent_yoy_decline: Optional[Decimal],
        multiples_data: Dict[str, object],
        *,
        industry_avg_margin: Optional[Decimal] = None,
    ) -> Tuple[Optional[Decimal], Decimal, Optional[str]]:
        """
        Apply margin premium/discount using a continuous linear function.

        Replaces the previous stepped approach (0.3x at +2%, 0.6x at +4%) with
        a smooth linear premium: 0.15x per percentage point of margin excess,
        capped at 0.8x. This eliminates cliff effects at tier boundaries.

        Academic basis: Damodaran (2012), McKinsey Valuation (2020, Ch. 10).
        """
        ev_ebitda_multiple = _ensure_decimal(ev_ebitda_multiple)
        _margin = _ensure_decimal(ebitda_margin)
        ebitda_margin = _margin if _margin is not None else Decimal("0")
        if ev_ebitda_multiple is None or ebitda_margin <= 0:
            return ev_ebitda_multiple, Decimal("0.0"), None

        if industry_avg_margin is None:
            industry_avg_margin = Decimal("12.5")

        margin_excess = ebitda_margin - industry_avg_margin

        if margin_excess <= 0:
            return ev_ebitda_multiple, Decimal("0.0"), None

        # Continuous linear premium: 0.15x per pp excess, capped at 0.8x
        base_premium = min(margin_excess * Decimal("0.15"), Decimal("0.8"))

        # Detect revenue decline to attenuate premium
        is_declining = False
        decline_severity = None
        if revenue_cagr is not None and revenue_cagr < Decimal("-20.0"):
            is_declining = True
            decline_severity = "severe"
        elif revenue_cagr is not None and revenue_cagr < Decimal("-10.0"):
            is_declining = True
            decline_severity = "moderate"
        elif recent_yoy_decline is not None and recent_yoy_decline < Decimal("-20.0"):
            is_declining = True
            decline_severity = "severe"
        elif recent_yoy_decline is not None and recent_yoy_decline < Decimal("-10.0"):
            is_declining = True
            decline_severity = "moderate"

        ebitda_margin_premium = Decimal("0.0")
        ebitda_margin_premium_explanation = None

        if is_declining:
            if decline_severity == "severe":
                ebitda_margin_premium = Decimal("0.0")
                ebitda_margin_premium_explanation = (
                    f"Margin premium eliminated: {ebitda_margin:.1f}% vs {industry_avg_margin:.1f}% industry average (+{margin_excess:.1f}%), "
                    f"but revenue severely declining. High margins in declining companies may not be sustainable "
                    f"per Koller, Goedhart & Wessels (2020, Ch. 10)."
                )
            elif decline_severity == "moderate":
                ebitda_margin_premium = base_premium * Decimal("0.5")
                ebitda_margin_premium_explanation = (
                    f"Margin premium reduced 50%: +{ebitda_margin_premium:.2f}x (base {base_premium:.2f}x). "
                    f"{ebitda_margin:.1f}% margin vs {industry_avg_margin:.1f}% industry avg (+{margin_excess:.1f}pp), "
                    f"attenuated for revenue decline per Koller (2020, Ch. 10)."
                )
        else:
            ebitda_margin_premium = base_premium
            ebitda_margin_premium_explanation = (
                f"Margin premium +{ebitda_margin_premium:.2f}x: {ebitda_margin:.1f}% margin vs "
                f"{industry_avg_margin:.1f}% industry average (+{margin_excess:.1f}pp). "
                f"Continuous linear model: 0.15x per pp excess, capped at 0.8x "
                f"per Damodaran (2012) / McKinsey (2020)."
            )

        if ebitda_margin_premium > 0:
            ev_ebitda_multiple = ev_ebitda_multiple + ebitda_margin_premium
            multiples_data["ev_ebitda"] = ev_ebitda_multiple
            for key in [
                "ev_ebitda_p10",
                "ev_ebitda_p25",
                "ev_ebitda_p50",
                "ev_ebitda_p75",
                "ev_ebitda_p90",
            ]:
                if multiples_data.get(key) is not None:
                    multiples_data[key] = (
                        _ensure_decimal(multiples_data[key]) + ebitda_margin_premium
                    )

        return ev_ebitda_multiple, ebitda_margin_premium, ebitda_margin_premium_explanation

    def _apply_growth_risk_adjustment(
        self,
        request: object,
        ev_ebitda_multiple: Optional[Decimal],
        multiples_data: Dict[str, object],
    ) -> Tuple[
        Optional[Decimal], Decimal, Optional[str], Optional[Decimal], Optional[Decimal], Decimal
    ]:
        return apply_growth_risk_adjustment(
            request,
            ev_ebitda_multiple,
            multiples_data,
            logger_instance=self.logger,
        )
