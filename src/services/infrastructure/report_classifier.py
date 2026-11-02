"""
Report Classification System

Determines report type and limitations based on data availability and quality,
following professional valuation standards (USPAP, IVS, ASA).
"""

from enum import Enum
from typing import List, Tuple
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class ReportClassification(Enum):
    """Report classification based on data availability and scope."""
    FULL_REPORT = "Business Valuation Report"
    LIMITED_SCOPE = "Valuation Analysis with Limitations"
    PRELIMINARY = "Preliminary Indication of Value"
    SPECIAL_PURPOSE = "Special Purpose Valuation"


def classify_report(
    years_of_data: int,
    ebitda_margin: Decimal,
    data_quality_score: Decimal,
    has_projections: bool = False
) -> Tuple[ReportClassification, List[str], float]:
    """
    Classify report and determine limitations based on data availability.

    Professional Standards Reference:
    - USPAP Standards 9 & 10: Require disclosure of scope limitations
    - IVS 105: Valuation approaches require sufficient data
    - ASA BVS-VII: Minimum data requirements for comprehensive valuations

    Args:
        years_of_data: Number of years of historical financial data
        ebitda_margin: Current EBITDA margin (negative if losses)
        data_quality_score: Overall data quality score (0-1)
        has_projections: Whether management projections are available

    Returns:
        Tuple of (classification, list_of_limitations, confidence_cap)

    Logic:
    - <1 year data: PRELIMINARY (40% confidence cap)
    - 1-2 years OR ebitda < -10%: LIMITED_SCOPE (60-75% cap)
    - Ebitda < -20%: SPECIAL_PURPOSE (special handling required)
    - 3+ years AND ebitda > -10%: FULL_REPORT (no artificial cap)
    """

    limitations = []
    confidence_cap = Decimal('1.0')  # No cap by default

    # Primary classification based on data availability
    if years_of_data < 1:
        classification = ReportClassification.PRELIMINARY
        limitations.append("Less than one year of operating history available")
        confidence_cap = Decimal('0.40')
        logger.debug("Report classified as PRELIMINARY: <1 year of data")

    elif years_of_data < 3:
        classification = ReportClassification.LIMITED_SCOPE
        limitations.append(f"Only {years_of_data} year(s) of historical data available")
        confidence_cap = Decimal('0.60') if years_of_data < 2 else Decimal('0.75')
        logger.debug(f"Report classified as LIMITED_SCOPE: {years_of_data} years of data")

    else:
        # 3+ years of data - full report possible
        classification = ReportClassification.FULL_REPORT
        confidence_cap = Decimal('1.0')
        logger.debug(f"Report classified as FULL_REPORT: {years_of_data} years of data")

    # Adjust classification based on profitability
    if ebitda_margin < -0.20:  # >20% negative margin
        # Severe losses - special purpose valuation
        classification = ReportClassification.SPECIAL_PURPOSE
        limitations.append("Material going concern uncertainty due to sustained losses")
        confidence_cap = min(confidence_cap, Decimal('0.50'))  # Further cap
        logger.warning(f"Classification downgraded to SPECIAL_PURPOSE: EBITDA margin {ebitda_margin:.1%}")

    elif ebitda_margin < -0.10:  # 10-20% negative margin
        # Significant losses - limited scope at minimum
        if classification == ReportClassification.FULL_REPORT:
            classification = ReportClassification.LIMITED_SCOPE
        limitations.append("Significant operating losses - High risk valuation with wide ranges")
        confidence_cap = min(confidence_cap, Decimal('0.65'))
        logger.warning(f"Classification adjusted for negative EBITDA: margin {ebitda_margin:.1%}")

    elif ebitda_margin < 0:  # 0-10% negative margin
        # Marginally negative - note but don't necessarily downgrade
        limitations.append("Negative EBITDA margin - Revenue multiples used as primary method")
        logger.debug(f"Negative EBITDA noted: margin {ebitda_margin:.1%}")

    # Adjust for data quality if very low
    if data_quality_score < 0.50:
        if classification == ReportClassification.FULL_REPORT:
            classification = ReportClassification.LIMITED_SCOPE
        limitations.append("Data quality concerns limit reliability of conclusions")
        confidence_cap = min(confidence_cap, Decimal('0.60'))
        logger.warning(f"Classification adjusted for low data quality: {data_quality_score:.1%}")

    # Note if projections are missing (doesn't downgrade but is a limitation)
    if not has_projections and years_of_data >= 3:
        limitations.append("Management projections not available - valuation based on historical data only")

    return classification, limitations, confidence_cap


def get_confidence_cap_reason(
    classification: ReportClassification,
    years_of_data: int,
    ebitda_margin: Decimal
) -> str:
    """
    Get human-readable explanation for confidence cap.

    Args:
        classification: Report classification
        years_of_data: Number of years of data
        ebitda_margin: EBITDA margin

    Returns:
        Explanation string for the confidence cap
    """

    if classification == ReportClassification.PRELIMINARY:
        return "Insufficient historical data for reliable trend analysis"

    elif classification == ReportClassification.SPECIAL_PURPOSE:
        return "Material going concern uncertainty and sustained operating losses"

    elif years_of_data < 3:
        return "Limited historical period constrains trend identification and normalization"

    elif ebitda_margin < -0.10:
        return "Significant operating losses increase valuation uncertainty"

    else:
        return None  # No cap


def get_valuation_range_width(
    classification: ReportClassification,
    years_of_data: int,
    data_quality_score: Decimal
) -> Decimal:
    """
    Determine appropriate valuation range width based on data limitations.

    Professional Practice:
    - Standard range: ±15-20% from midpoint
    - Limited data: ±25-30%
    - Preliminary: ±40%+

    Args:
        classification: Report classification
        years_of_data: Number of years of data
        data_quality_score: Data quality score

    Returns:
        Range width as decimal (e.g., Decimal('0.40') for ±40%)
    """

    if classification == ReportClassification.PRELIMINARY:
        return Decimal('0.40')  # ±40%

    elif classification == ReportClassification.SPECIAL_PURPOSE:
        return Decimal('0.45')  # ±45%

    elif classification == ReportClassification.LIMITED_SCOPE:
        if years_of_data < 2:
            return Decimal('0.35')  # ±35%
        else:
            return Decimal('0.30')  # ±30%

    else:  # FULL_REPORT
        if data_quality_score < 0.70:
            return Decimal('0.25')  # ±25%
        else:
            return Decimal('0.20')  # ±20% (standard)
