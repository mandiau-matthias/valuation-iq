"""
Utility functions for Step 2 Benchmarking.

This module contains helper functions for benchmark calculations,
data formatting, and common operations.

REFACTORED (December 2025):
- Removed old hardcoded calibration logic (130+ lines)
- Now uses SMEMultipleSelector as single source of truth
- Academic-based SME multiples (VFB Belgium, Vlerick, Pepperdine)
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory
from src.utils.core import ensure_float  # Unified utility
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)

# ensure_float is now imported from src.utils.core (unified utility library)

COUNTRY_NAME_BY_CODE = {
    "BE": "Belgium",
    "NL": "Netherlands",
    "LU": "Luxembourg",
    "DE": "Germany",
    "AT": "Austria",
    "CH": "Switzerland",
    "FR": "France",
    "ES": "Spain",
    "PT": "Portugal",
    "IT": "Italy",
}


def map_industry_to_sector(industry: str) -> str:
    """
    Map industry to FMP sector.

    Args:
        industry: Industry identifier

    Returns:
        FMP sector name
    """
    industry_lower = industry.lower()

    # Map common industries to FMP sectors
    if any(x in industry_lower for x in ["technology", "software", "saas", "tech"]):
        return "technology"
    elif any(x in industry_lower for x in ["ecommerce", "retail", "online"]):
        return "ecommerce"
    elif any(x in industry_lower for x in ["manufacturing", "industrial"]):
        return "manufacturing"
    elif any(x in industry_lower for x in ["healthcare", "medical"]):
        return "healthcare"
    elif any(x in industry_lower for x in ["finance", "fintech", "banking"]):
        return "finance"
    elif any(x in industry_lower for x in ["services", "consulting", "professional"]):
        return "services"
    else:
        return "technology"  # Default fallback


def calibrate_multiple_for_sme(
    database_multiple: Decimal,
    revenue: Decimal,
    industry: str,
    business_category: BusinessTypeCategory,
    is_revenue_driven_func=None,
    business_type: Optional[str] = None,
    founded_year: Optional[int] = None,
    current_year: Optional[int] = None,
    historical_data: Optional[List[Dict[str, Any]]] = None,
    sme_calibration: Optional[Dict[str, Any]] = None,
    multiple_type: str = "ebitda",
    country_code: Optional[str] = None,
) -> Tuple[Decimal, Decimal, str]:
    """
    Calibrate database multiples using SME academic sources.
    
    REFACTORED (December 2025):
    - Removed old hardcoded calibration logic (130+ lines)
    - Now uses SMEMultipleSelector as single source of truth
    - Academic sources: VFB Belgium (2024), Vlerick (2023), Pepperdine (2024), Trugman (2017)
    
    UPDATED (January 2026):
    - Added sme_calibration parameter for Titan-provided database-driven multiples
    - Priority cascade: Titan enrichment > DatabaseDrivenDefaults > Hardcoded
    
    This function is the SINGLE ENTRY POINT for SME multiple calibration in Step 2.
    All SME calibration goes through SMEMultipleSelector (academic-based).

    Args:
        database_multiple: Raw multiple from database (e.g., 12.0x for software)
        revenue: Company revenue
        industry: Industry identifier
        business_category: Business type category
        is_revenue_driven_func: Optional function to check if industry is revenue-driven (deprecated, kept for compatibility)
        business_type: Optional business type ID for business-type-specific adjustments
        founded_year: Optional founded year for growth stage determination
        current_year: Optional current year for growth stage determination
        historical_data: Optional historical data for growth stage determination
        sme_calibration: Optional Titan-provided SME calibration from business_types DB (PRIORITY 1)
            Contains: ev_ebitda_micro/small/medium, ev_revenue_micro/small/medium,
            size_premium_micro/small/medium, liquidity_discount, calibration_source
        country_code: Optional ISO country code so calibration can use the same geography logic as the benchmark backbone

    Returns:
        Tuple of (calibrated_multiple, calibration_factor, explanation)
        
    Raises:
        ImportError: If SMEMultipleSelector is not available (hard dependency)
    """
    from src.config.decimal_constants import DecimalConstants

    # SMEMultipleSelector is now a HARD DEPENDENCY (no fallback)
    try:
        from src.services.academic.sme_multiple_selector import get_sme_selector
    except ImportError as e:
        logger.error(
            "❌ SMEMultipleSelector not available - SME calibration requires academic sources",
            extra={
                "step_number": 2,
                "error": str(e),
                "revenue": float(revenue),
                "industry": industry
            }
        )
        raise ImportError(
            "SME academic sources required for calibration. Install academic services.") from e
    
    selector = get_sme_selector()
    sme_class = selector.classify_sme(revenue)
    
    # For large companies (€5M+ revenue), database multiples are appropriate
    # No calibration needed per academic valuation standards (Koller, Goedhart & Wessels 2020)
    if revenue >= to_decimal(DecimalConstants.SME_CALIBRATION_THRESHOLD):
        logger.info(
            "✅ No SME calibration needed (revenue ≥€5M - database multiples appropriate)",
            extra={
                "step_number": 2,
                "revenue": float(revenue),
                "database_multiple": float(database_multiple),
                "calibrated_multiple": float(database_multiple),
                "calibration_factor": 1.0,
            },
        )
        # BANK-GRADE: Return Decimal values
        return (
            database_multiple,
            Decimal('1.0'),
            "No calibration (€5M+ revenue - database multiples appropriate per academic valuation standards - Koller, Goedhart & Wessels 2020)",
        )
    
    # For SMEs (<€5M), use academic-based multiples
    if sme_class in ['micro', 'small', 'medium']:
        if multiple_type == "revenue":
            # Revenue multiples use a separate lookup with appropriate bounds
            sme_multiple, rationale = selector.get_sme_revenue_multiple(
                revenue=revenue,
                industry=industry,
            )
            
            # Enforce revenue-specific bounds from SME_MULTIPLE_BOUNDS
            bounds = selector.SME_MULTIPLE_BOUNDS.get(sme_class, {})
            rev_min = bounds.get('revenue_min', Decimal('0.2'))
            rev_max = bounds.get('revenue_max', Decimal('3.0'))
            if sme_multiple < rev_min:
                sme_multiple = rev_min
            elif sme_multiple > rev_max:
                sme_multiple = rev_max
        else:
            # EBITDA multiples use the full priority cascade
            calibration_country = COUNTRY_NAME_BY_CODE.get(
                (country_code or "").strip().upper(),
                "Belgium",
            )
            sme_multiple, _sources, rationale = selector.get_sme_ebitda_multiple(
                revenue=revenue,
                industry=industry,
                business_type=business_type,
                business_category=business_category.value if business_category else None,
                country=calibration_country,
                founded_year=founded_year,
                current_year=current_year,
                historical_data=historical_data,
                sme_calibration=sme_calibration,
            )
        
        calibration_factor = (
            sme_multiple / database_multiple 
            if database_multiple > Decimal('0') 
            else Decimal('1.0')
        )
        
        explanation = (
            f"SME academic {multiple_type} multiple ({float(sme_multiple):.2f}x) from academic sources. "
            f"Database multiple ({float(database_multiple):.2f}x) calibrated for {sme_class} SME "
            f"(revenue: €{float(revenue):,.0f}). {rationale}"
        )
        
        data_source = "titan_enrichment" if sme_calibration else "academic_fallback"
        
        logger.info(
            f"✅ SME {multiple_type} calibration using {'Titan enrichment' if sme_calibration else 'academic sources'}: {rationale}",
            extra={
                "step_number": 2,
                "revenue": float(revenue),
                "sme_class": sme_class,
                "multiple_type": multiple_type,
                "database_multiple": float(database_multiple),
                "sme_multiple": float(sme_multiple),
                "calibration_factor": float(calibration_factor),
                "reduction_pct": float((Decimal('1.0') - calibration_factor) * Decimal('100')),
                "data_source": data_source,
                "titan_calibration_provided": sme_calibration is not None,
            },
        )
        
        return (
            sme_multiple,
            calibration_factor,
            explanation
        )
    
    # Fallback for large companies (shouldn't reach here due to threshold check above)
    logger.warning(
        "⚠️ Large company detected but below threshold - using database multiple",
        extra={
            "step_number": 2,
            "revenue": float(revenue),
            "sme_class": sme_class,
            "database_multiple": float(database_multiple),
        }
    )
    # BANK-GRADE: Return Decimal values
    return (
        database_multiple,
        Decimal('1.0'),
        f"Large company ({sme_class}) - database multiple appropriate"
    )
