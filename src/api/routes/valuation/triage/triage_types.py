"""
Types and enums for the triage system.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from src.utils.decimal_helpers import from_decimal, to_decimal


class TriageReason(Enum):
    """Reasons for triage decisions"""

    DATA_QUALITY_LOW = "data_quality_low"
    DATA_QUALITY_HIGH = "data_quality_high"
    COMPANY_TOO_SMALL = "company_too_small"
    INSUFFICIENT_HISTORICAL_DATA = "insufficient_historical_data"
    MISSING_OWNER_DATA = "missing_owner_data"
    MISSING_BALANCE_SHEET = "missing_balance_sheet"
    INSUFFICIENT_COMPARABLES = "insufficient_comparables"
    ALWAYS_EXECUTE = "always_execute"
    DEPENDENCY_NOT_MET = "dependency_not_met"


@dataclass
class TriageDecision:
    """
    Decision from the triage system about methodology selection.

    Attributes:
        use_dcf: Whether to use DCF methodology
        use_multiples: Whether to use Multiples methodology
        multiples_primary: Whether multiples is the primary method
        reason: Reason for the decision
        data_quality_score: Overall data quality score (0-100)
    """

    use_dcf: bool
    use_multiples: bool
    multiples_primary: bool
    reason: TriageReason
    data_quality_score: Optional[int] = None
