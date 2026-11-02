"""
Step 2.7 SDE Calculator

Core SDE calculation logic wrapped for step execution.
Uses the SDEEngine from domain layer.
"""

from decimal import Decimal
from typing import Any, Dict, NamedTuple, Optional, Tuple

from src.domain.models import FinancialData, YearData
from src.domain.sde_engine import SDEComponents, SDEEngine, SDEValuationResult
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class _SDEAdjustmentBuckets(NamedTuple):
    owner_salary: Decimal
    owner_benefits: Decimal
    owner_perks: Decimal
    non_recurring: Decimal
    non_operating: Decimal
    other_addbacks: Decimal


def _resolve_base_ebitda(
    ebitda: Decimal,
    ebitda_normalization_metadata: Optional[dict[str, object]],
) -> Decimal:
    base_ebitda = ebitda
    if not ebitda_normalization_metadata:
        return base_ebitda

    reported_ebitda = to_decimal(ebitda_normalization_metadata.get("reported_ebitda") or ebitda)
    normalized_ebitda = ebitda_normalization_metadata.get("normalized_ebitda")
    if normalized_ebitda is not None and to_decimal(normalized_ebitda) == ebitda:
        return reported_ebitda
    return base_ebitda


def _benchmark_adjustment_buckets(business_size: str) -> _SDEAdjustmentBuckets:
    from src.config.belgian_salary_benchmarks import OWNER_COMPENSATION_BY_SIZE

    owner_compensation = OWNER_COMPENSATION_BY_SIZE
    comp = owner_compensation.get(business_size, owner_compensation["small"])
    return _SDEAdjustmentBuckets(
        owner_salary=comp["salary"],
        owner_benefits=comp["benefits"],
        owner_perks=comp["perks"],
        non_recurring=Decimal("0"),
        non_operating=Decimal("0"),
        other_addbacks=Decimal("0"),
    )


def _metadata_adjustment_buckets(adjustments: list[dict[str, object]]) -> _SDEAdjustmentBuckets:
    owner_salary = Decimal("0")
    owner_benefits = Decimal("0")
    owner_perks = Decimal("0")
    non_recurring = Decimal("0")
    non_operating = Decimal("0")
    other_addbacks = Decimal("0")

    for adj in adjustments:
        adj_type = adj.get("adjustment_type") or adj.get("category") or ""
        amount = to_decimal(adj.get("amount") or 0)

        if adj_type == "non_recurring_revenue":
            non_operating += amount
            continue
        if not adj.get("is_addback", True):
            continue
        if adj_type == "owner_compensation_adjustment":
            owner_salary += amount
        elif adj_type == "personal_expenses":
            owner_perks += amount
        elif adj_type == "family_expenses":
            owner_benefits += amount
        elif adj_type in ("one_time_expenses", "non_recurring_costs"):
            non_recurring += amount
        else:
            other_addbacks += amount

    return _SDEAdjustmentBuckets(
        owner_salary=owner_salary,
        owner_benefits=owner_benefits,
        owner_perks=owner_perks,
        non_recurring=non_recurring,
        non_operating=non_operating,
        other_addbacks=other_addbacks,
    )


def _resolve_adjustment_buckets(
    *,
    business_size: str,
    ebitda_normalization_metadata: Optional[dict[str, object]],
) -> _SDEAdjustmentBuckets:
    if ebitda_normalization_metadata and ebitda_normalization_metadata.get("adjustments"):
        return _metadata_adjustment_buckets(ebitda_normalization_metadata["adjustments"])
    return _benchmark_adjustment_buckets(business_size)


class Step27SDECalculator:
    """
    Calculates SDE and SDE-based valuation.

    Wraps the SDEEngine from domain layer for step execution.
    """

    def __init__(self):
        """Initialize the SDE calculator."""
        self.logger = logger

    def classify_business_size(self, revenue: Decimal) -> str:
        """
        Classify business size based on revenue.

        Args:
            revenue: Annual revenue in EUR

        Returns:
            Size classification: 'micro', 'small', 'lower_middle', or 'large'
        """
        if revenue < Decimal("500000"):
            return "micro"
        elif revenue < Decimal("2000000"):
            return "small"
        elif revenue < Decimal("5000000"):
            return "lower_middle"
        else:
            return "large"

    def is_sde_appropriate(
        self,
        revenue: Decimal,
        num_owners: int,
        business_category: str,
    ) -> Tuple[bool, str]:
        """
        Determine if SDE methodology is appropriate.

        Args:
            revenue: Annual revenue
            num_owners: Number of owners
            business_category: Business type category

        Returns:
            Tuple of (is_appropriate, reason)
        """
        business_size = self.classify_business_size(revenue)

        # Large businesses should use EBITDA
        if business_size == "large":
            return (
                False,
                f"Revenue EUR {from_decimal(revenue):,.0f} exceeds EUR 5M - use EBITDA multiples",
            )

        # Micro businesses are always SDE appropriate
        if business_size == "micro":
            return (
                True,
                f"Micro business (EUR {from_decimal(revenue):,.0f}) - SDE is standard methodology",
            )

        # Small and lower middle market - check owner count
        if num_owners <= 3:
            return (
                True,
                f"Owner-operated ({num_owners} owners) with EUR {from_decimal(revenue):,.0f} revenue",
            )

        # Many owners - SDE less appropriate
        if num_owners > 5:
            return False, f"Many owners ({num_owners}) - EBITDA multiples may be more appropriate"

        # Moderate owner count - context dependent
        return (
            True,
            f"{num_owners} owners with EUR {from_decimal(revenue):,.0f} - SDE applicable with caveats",
        )

    def extract_sde_inputs(
        self,
        step1_result: Dict[str, Any],
        request: Any,
    ) -> Tuple[Decimal, Decimal, Optional[Decimal]]:
        """
        Extract inputs needed for SDE calculation from step 1 result and request.

        Args:
            step1_result: Result from Step 1
            request: Valuation request

        Returns:
            Tuple of (revenue, ebitda, net_income)
        """
        current_year = getattr(request, "current_year_data", None)
        current_revenue = (
            to_decimal(getattr(current_year, "revenue", 0) or 0) if current_year else Decimal("0")
        )
        current_ebitda = (
            to_decimal(getattr(current_year, "ebitda", 0) or 0) if current_year else Decimal("0")
        )

        revenue = (
            current_revenue if current_revenue > 0 else to_decimal(step1_result.get("revenue") or 0)
        )
        ebitda = (
            current_ebitda if current_ebitda != 0 else to_decimal(step1_result.get("ebitda") or 0)
        )

        net_income = None
        if current_year:
            raw_ni = getattr(current_year, "net_income", None)
            net_income = to_decimal(raw_ni) if raw_ni is not None else None

        return revenue, ebitda, net_income

    def calculate_sde_from_ebitda(
        self,
        ebitda: Decimal,
        revenue: Decimal,
        business_size: str,
        ebitda_normalization_metadata: Optional[Dict[str, Any]] = None,
    ) -> SDEComponents:
        """
        Calculate SDE when full breakdown is not available.

        If Titan normalization metadata is available, use those adjustments.
        Otherwise, estimate owner compensation based on business size.

        Args:
            ebitda: EBITDA value
            revenue: Revenue for benchmarking
            business_size: Business size tier
            ebitda_normalization_metadata: Normalization metadata from Venus/Titan

        Returns:
            SDEComponents with breakdown
        """
        base_ebitda = _resolve_base_ebitda(ebitda, ebitda_normalization_metadata)
        buckets = _resolve_adjustment_buckets(
            business_size=business_size,
            ebitda_normalization_metadata=ebitda_normalization_metadata,
        )
        total_sde = (
            base_ebitda
            + buckets.owner_salary
            + buckets.owner_benefits
            + buckets.owner_perks
            + buckets.non_recurring
            + buckets.other_addbacks
            - buckets.non_operating
        )

        return SDEComponents(
            net_income=base_ebitda,
            owner_salary=buckets.owner_salary,
            owner_benefits=buckets.owner_benefits,
            owner_perks=buckets.owner_perks,
            depreciation=Decimal("0"),
            amortization=Decimal("0"),
            interest_expense=Decimal("0"),
            non_recurring_expenses=buckets.non_recurring,
            non_operating_income=buckets.non_operating,
            other_addbacks=buckets.other_addbacks,
            total_sde=total_sde,
        )

    def get_sde_multiple(
        self,
        industry: str,
        business_size: str,
        sde_calibration: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Decimal, Decimal, Decimal, str]:
        """
        Get SDE multiple with P25/P75 range.

        Priority:
        1. Titan's sde_calibration (database-driven)
        2. Hardcoded fallback tables

        Args:
            industry: Business industry
            business_size: Business size tier
            sde_calibration: SDE calibration data from Titan

        Returns:
            Tuple of (multiple_median, multiple_p25, multiple_p75, data_source)
        """
        # Priority 1: Database-driven from Titan
        if sde_calibration:
            size_field_map = {
                "micro": "sde_multiple_micro",
                "small": "sde_multiple_small",
                "lower_middle": "sde_multiple_medium",
                "medium": "sde_multiple_medium",
            }
            field_name = size_field_map.get(business_size, "sde_multiple_small")

            multiple = sde_calibration.get(field_name)
            if multiple is not None:
                multiple = to_decimal(multiple)
                _raw_p25 = sde_calibration.get("sde_multiple_p25")
                _raw_p75 = sde_calibration.get("sde_multiple_p75")
                p25 = to_decimal(_raw_p25) if _raw_p25 is not None else multiple * Decimal("0.85")
                p75 = to_decimal(_raw_p75) if _raw_p75 is not None else multiple * Decimal("1.15")
                source = sde_calibration.get("sde_source", "database")

                self.logger.debug(
                    f"Using database-driven SDE multiple: {from_decimal(multiple)}x",
                    extra={
                        "industry": industry,
                        "business_size": business_size,
                        "source": source,
                    },
                )
                return multiple, p25, p75, source

        # Priority 2: Industry-aware fallback via SDE_MULTIPLES_BY_INDUSTRY
        from src.domain.sde_engine import SDE_MULTIPLES_BY_INDUSTRY

        industry_norm = (industry or "").lower().strip().replace(" ", "-")
        industry_multiples = SDE_MULTIPLES_BY_INDUSTRY.get(
            industry_norm,
            SDE_MULTIPLES_BY_INDUSTRY.get("services", SDE_MULTIPLES_BY_INDUSTRY.get("other", {})),
        )
        multiple = industry_multiples.get(business_size, Decimal("2.0"))
        p25 = multiple * Decimal("0.80")
        p75 = multiple * Decimal("1.20")

        self.logger.info(
            f"Using fallback SDE multiple: {from_decimal(multiple)}x",
            extra={
                "industry": industry,
                "business_size": business_size,
                "source": "hardcoded_bizbuysell_2024",
            },
        )

        return multiple, p25, p75, "hardcoded_bizbuysell_2024"

    def calculate_sde_valuation(
        self,
        sde: Decimal,
        multiple: Decimal,
        multiple_p25: Decimal,
        multiple_p75: Decimal,
        adjustments: Optional[Dict[str, Decimal]] = None,
    ) -> Tuple[Decimal, Decimal, Decimal, Dict[str, float]]:
        """
        Calculate SDE-based enterprise value with range.

        Args:
            sde: Seller's Discretionary Earnings
            multiple: SDE multiple (median)
            multiple_p25: 25th percentile multiple
            multiple_p75: 75th percentile multiple
            adjustments: Optional adjustments to apply

        Returns:
            Tuple of (value_mid, value_low, value_high, adjustments_dict)
        """
        # Base values
        value_low = sde * multiple_p25
        value_mid = sde * multiple
        value_high = sde * multiple_p75

        # Apply adjustments
        adjustment_dict = {}
        total_adjustment = Decimal("1.0")

        if adjustments:
            for name, factor in adjustments.items():
                adjustment_dict[name] = from_decimal(factor)
                total_adjustment *= Decimal("1") + factor

        # Apply adjustments
        value_low = bank_round(value_low * total_adjustment, 2)
        value_mid = bank_round(value_mid * total_adjustment, 2)
        value_high = bank_round(value_high * total_adjustment, 2)

        return value_mid, value_low, value_high, adjustment_dict
