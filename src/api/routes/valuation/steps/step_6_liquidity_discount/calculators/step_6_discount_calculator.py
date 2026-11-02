"""
Step 6 Discount Calculator

Calculates liquidity discounts and extracts supporting data.
"""

from decimal import Decimal
from typing import Optional

from src.api.routes.valuation.shared.historical_years import oldest_and_newest_historical_years
from src.config.decimal_constants import DecimalConstants
from src.utils.adaptive_input_helpers import (
    get_contract_backlog_override,
    get_customer_concentration_amount_override,
    get_customer_concentration_override,
    get_recurring_revenue_amount_override,
    get_recurring_revenue_override,
)
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step6DiscountCalculator:
    """Calculates liquidity discounts for Step 6."""

    def check_sme_calibration(self, step2_result: Optional[dict]) -> tuple[bool, float]:
        """
        Check if Step 2 SME calibration was applied.

        Resolved Upswitch Index benchmark contracts use local or borrowed SME
        evidence and may already carry partial illiquidity calibration. Legacy
        cache/default/fallback lanes must not receive that trust automatically.

        Args:
            step2_result: Step 2 result dictionary

        Returns:
            Tuple of (sme_calibration_applied, sme_calibration_factor)
        """
        if not step2_result:
            logger.debug("No Step 2 result - SME calibration not applied")
            return False, Decimal("1.0")

        # Check explicit sme_calibration flag first
        sme_calibration_data = step2_result.get("sme_calibration", {})
        sme_calibration_applied = sme_calibration_data.get("applied", False)

        data_source = step2_result.get("data_source", "")
        benchmark_contract = step2_result.get("benchmark_provenance") or step2_result.get(
            "benchmark_contract"
        )
        if data_source in ("titan_enrichment", "delphi-resolved-benchmark") or isinstance(
            benchmark_contract, dict
        ):
            sme_calibration_applied = True
            logger.debug(
                "SME calibration detected via resolved benchmark contract",
                extra={
                    "data_source": data_source,
                    "reason": "resolved Upswitch Index benchmark contract includes SME evidence",
                    "step_6_action": "Apply reduced residual discount",
                },
            )

        # Get calibration factor from EBITDA multiple (primary method)
        ebitda_calibration = sme_calibration_data.get("ebitda_multiple", {})
        if ebitda_calibration:
            sme_calibration_factor = ebitda_calibration.get("calibration_factor", Decimal("1.0"))
        # Fallback to revenue multiple if EBITDA calibration not available
        elif sme_calibration_data.get("revenue_multiple"):
            revenue_calibration = sme_calibration_data.get("revenue_multiple", {})
            sme_calibration_factor = revenue_calibration.get("calibration_factor", Decimal("1.0"))
        else:
            sme_calibration_factor = Decimal("1.0")

        logger.debug(
            "SME calibration check completed",
            extra={
                "sme_calibration_applied": sme_calibration_applied,
                "sme_calibration_factor": float(sme_calibration_factor),
                "data_source": data_source,
            },
        )

        return sme_calibration_applied, sme_calibration_factor

    def should_skip_for_sme(self, sme_calibration_applied: bool, revenue: Decimal) -> bool:
        """
        Determine if Step 6 should be skipped for SME.

        Returns False: SMEs always receive a (potentially reduced) liquidity
        discount. The SME calibration in Step 2 adjusts for database multiple
        inflation but does not fully capture illiquidity risk per Koeplin et al.
        (2000) and Silber (1991) restricted stock studies.
        """
        return False

    def get_sme_discount_reduction_factor(
        self, sme_calibration_applied: bool, revenue: Decimal
    ) -> Decimal:
        """
        Determine the reduction factor for SME liquidity discount.

        When the base multiple is SME/private-comp-calibrated (companies < €5M),
        the liquidity discount is reduced to a 25% residual to avoid double-
        counting the marketability haircut already embedded in those multiples.

        De-stack (2026-05): private micro-KMO transaction multiples are struck
        between private parties and therefore already reflect most of the
        illiquidity; only a residual marketability haircut remains.

        Academic basis:
        - Koeplin et al. (2000): 20-30% private company discounts
        - Private-transaction SME multiples already price in most illiquidity
        - Residual 25% discount keeps a marketability haircut without double-counting

        Returns:
            Decimal("0.25") for SMEs with calibration, Decimal("1.00") otherwise
        """
        if sme_calibration_applied and revenue < 5_000_000:
            return Decimal("0.25")
        return Decimal("1.00")

    def calculate_growth_rate(self, request: object) -> Optional[Decimal]:
        """
        Calculate revenue growth rate (CAGR) from historical data.

        Args:
            request: Valuation request with historical_years_data

        Returns:
            Growth rate as percentage (e.g., Decimal('0.15') for 15%), or None if insufficient data
        """
        if not hasattr(request, "historical_years_data") or not request.historical_years_data:
            return None

        historical = request.historical_years_data
        if len(historical) < 2:
            return None

        oldest_year, newest_year = oldest_and_newest_historical_years(historical)
        oldest_revenue = oldest_year.revenue if hasattr(oldest_year, "revenue") else None
        newest_revenue = newest_year.revenue if hasattr(newest_year, "revenue") else None

        if not oldest_revenue or not newest_revenue or oldest_revenue <= 0:
            return None

        oldest_year_value = getattr(oldest_year, "year", None)
        newest_year_value = getattr(newest_year, "year", None)
        try:
            year_span = int(newest_year_value) - int(oldest_year_value)
        except (TypeError, ValueError):
            year_span = 0
        years = year_span if year_span > 0 else len(historical) - 1

        try:
            cagr = (newest_revenue / oldest_revenue) ** (Decimal("1.0") / years) - Decimal("1.0")
            return cagr * Decimal("100.0")  # Convert to percentage
        except (ValueError, ZeroDivisionError, OverflowError):
            return None

    def extract_recurring_revenue_pct(
        self, request: object, revenue: Optional[Decimal] = None
    ) -> Optional[Decimal]:
        """
        Extract recurring revenue percentage from request.

        Args:
            request: Valuation request

        Returns:
            Recurring revenue as percentage (0-100), or None if not available
        """
        # Try direct percentage first
        if hasattr(request, "current_year_data") and request.current_year_data:
            if hasattr(request.current_year_data, "recurring_revenue_percentage"):
                pct = request.current_year_data.recurring_revenue_percentage
                if pct is not None:
                    whole_pct = self._as_whole_percent(to_decimal(pct))
                    if whole_pct > 0:
                        return whole_pct

        # Try calculating from recurring_revenue and revenue
        if hasattr(request, "current_year_data") and request.current_year_data:
            recurring_revenue = None
            revenue = None

            for attr in ["recurring_revenue", "recurring_revenue_amount"]:
                if hasattr(request.current_year_data, attr):
                    recurring_revenue = getattr(request.current_year_data, attr)
                    if recurring_revenue is not None:
                        break

            if hasattr(request.current_year_data, "revenue"):
                revenue = request.current_year_data.revenue

            if recurring_revenue is not None and revenue is not None and revenue > 0:
                try:
                    pct = (recurring_revenue / revenue) * Decimal("100.0")
                    whole_pct = self._as_whole_percent(to_decimal(pct))
                    if whole_pct > 0:
                        return whole_pct
                except (ValueError, ZeroDivisionError, TypeError):
                    pass

        # Try request-level / business-context attributes. This intentionally
        # lets a positive rev_recurring_pct override the schema default 0.0.
        pct = get_recurring_revenue_override(request)
        if pct is not None:
            whole_pct = self._as_whole_percent(to_decimal(pct))
            if whole_pct > 0:
                return whole_pct

        recurring_amount = get_recurring_revenue_amount_override(request)
        derived_pct = self._pct_from_amount(recurring_amount, revenue)
        if derived_pct is not None:
            return derived_pct

        return None

    def _as_whole_percent(self, value: Decimal) -> Decimal:
        """Accept both request fractions (0.40) and UI percents (40)."""
        pct = to_decimal(value)
        if abs(pct) <= Decimal("1"):
            return pct * Decimal("100")
        return pct

    def _pct_from_amount(
        self, amount: Optional[Decimal], revenue: Optional[Decimal]
    ) -> Optional[Decimal]:
        amount_decimal = to_decimal(amount) if amount is not None else Decimal("0")
        revenue_decimal = to_decimal(revenue) if revenue is not None else Decimal("0")
        if amount_decimal <= 0 or revenue_decimal <= 0:
            return None
        return min((amount_decimal / revenue_decimal) * Decimal("100"), Decimal("100"))

    def extract_customer_concentration_pct(
        self, request: object, revenue: Optional[Decimal] = None
    ) -> Optional[Decimal]:
        """Extract top-client concentration as a whole percent for Step 6."""
        concentration = get_customer_concentration_override(request)
        if concentration is not None:
            whole_pct = self._as_whole_percent(concentration)
            if whole_pct > 0:
                return whole_pct
        return self._pct_from_amount(
            get_customer_concentration_amount_override(request),
            revenue,
        )

    def extract_contract_backlog_months(
        self, request: object, revenue: Decimal
    ) -> Optional[Decimal]:
        """Extract contracted backlog as months of latest revenue."""
        backlog = get_contract_backlog_override(request)
        revenue = to_decimal(revenue)
        if backlog is None or backlog <= 0 or revenue <= 0:
            return None
        return (to_decimal(backlog) / revenue) * Decimal("12")

    def clamp_discount(self, total_discount: Decimal, step6_skipped_for_sme: bool) -> Decimal:
        """
        Clamp discount to bounds.

        Args:
            total_discount: Total discount value
            step6_skipped_for_sme: Whether Step 6 was skipped for SME

        Returns:
            Clamped discount value
        """
        if step6_skipped_for_sme:
            return to_decimal("0.00")

        DISCOUNT_FLOOR = to_decimal(DecimalConstants.LIQUIDITY_DISCOUNT_FLOOR)
        DISCOUNT_CEILING = to_decimal(DecimalConstants.LIQUIDITY_DISCOUNT_CEILING)

        total_discount_before_clamp = total_discount

        # If discount is 0 or positive, force it to minimum -10%
        if total_discount >= to_decimal("0"):
            logger.warning(
                "⚠️ CRITICAL: Liquidity discount is 0% or positive, applying minimum -10% discount",
                extra={
                    "step_number": 6,
                    "discount_before_clamp": to_decimal(total_discount_before_clamp),
                    "applied_minimum": DISCOUNT_CEILING,
                },
            )
            return to_decimal(str(DISCOUNT_CEILING))
        else:
            # Clamp to bounds: ensure discount is between -30% and -10%
            clamped = max(
                to_decimal(str(DISCOUNT_FLOOR)),
                min(to_decimal(str(DISCOUNT_CEILING)), total_discount),
            )
            if clamped != total_discount_before_clamp:
                logger.info(
                    "✅ Liquidity discount clamped to bounds",
                    extra={
                        "step_number": 6,
                        "discount_before_clamp": to_decimal(total_discount_before_clamp),
                        "discount_after_clamp": to_decimal(clamped),
                        "floor": DISCOUNT_FLOOR,
                        "ceiling": DISCOUNT_CEILING,
                    },
                )
            return clamped
