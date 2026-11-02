"""
DCF Executor

Executes DCF (Discounted Cash Flow) valuation methodology.
Handles DCF eligibility determination and execution orchestration.
"""

import json
from collections import OrderedDict
from decimal import Decimal
from threading import Lock
from typing import Any, Dict, Optional, Tuple

from src.api.routes.valuation.shared.historical_years import oldest_historical_year
from src.api.schemas import ValuationRequest
from src.domain.dcf_policy import dcf_history_exclusion_reason, user_explicitly_configured_dcf
from src.utils.decimal_helpers import to_decimal
from src.utils.valuation_logger import ValuationLogger

from .methodology_executor import MethodologyExecutor

# Per-process FIFO cache of DCF eligibility verdicts keyed on request content.
# `should_calculate_dcf` is called at least twice per /calculate
# (MethodologyDeterminer + the comprehensive orchestrator immediately after),
# each time re-evaluating identical revenue thresholds and emitting an
# identical "DCF excluded: ..." INFO log line. Memoising silences the
# duplicate log AND saves a (small but non-zero) recomputation cost.
_DCF_ELIGIBILITY_CACHE_MAX = 32
_dcf_eligibility_cache: "OrderedDict[str, Tuple[bool, Optional[str]]]" = OrderedDict()
_dcf_eligibility_lock = Lock()


def _request_cache_key(request: ValuationRequest) -> str:
    """Build a stable cache key; object ids can be reused within long test runs."""
    try:
        payload = request.model_dump(mode="json")
    except Exception:
        payload = {
            "revenue": str(getattr(getattr(request, "current_year_data", None), "revenue", "")),
            "historical_years_data": [
                {
                    "year": getattr(year, "year", None),
                    "revenue": str(getattr(year, "revenue", "")),
                    "is_forecast": bool(getattr(year, "is_forecast", False)),
                }
                for year in (getattr(request, "historical_years_data", []) or [])
            ],
            "recurring_revenue_percentage": str(
                getattr(request, "recurring_revenue_percentage", "")
            ),
            "selected_method": str(getattr(request, "selected_method", "")),
            "methodology": str(getattr(request, "methodology", "")),
            "business_context": str(getattr(request, "business_context", "")),
            "user_configured_dcf": str(getattr(request, "user_configured_dcf", "")),
        }
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def _dcf_eligibility_cache_get(key: str) -> Optional[Tuple[bool, Optional[str]]]:
    with _dcf_eligibility_lock:
        value = _dcf_eligibility_cache.get(key)
        if value is not None:
            _dcf_eligibility_cache.move_to_end(key)
        return value


def _dcf_eligibility_cache_put(key: str, value: Tuple[bool, Optional[str]]) -> None:
    with _dcf_eligibility_lock:
        _dcf_eligibility_cache[key] = value
        _dcf_eligibility_cache.move_to_end(key)
        while len(_dcf_eligibility_cache) > _DCF_ELIGIBILITY_CACHE_MAX:
            _dcf_eligibility_cache.popitem(last=False)


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return to_decimal(value)
    except (TypeError, ValueError):
        return None


def _actual_historical_years(request: ValuationRequest) -> list[object]:
    return [
        year
        for year in (getattr(request, "historical_years_data", []) or [])
        if not getattr(year, "is_forecast", False)
    ]


def _oldest_historical_revenue(
    historical_years_data: list[object],
    *,
    fallback_to_first: bool,
) -> Decimal | None:
    oldest_year = oldest_historical_year(historical_years_data)
    if oldest_year is not None and hasattr(oldest_year, "revenue"):
        return _decimal_or_none(getattr(oldest_year, "revenue", None))
    if fallback_to_first and historical_years_data:
        return _decimal_or_none(getattr(historical_years_data[0], "revenue", 0) or 0)
    return None


def _recurring_revenue_fraction(request: ValuationRequest) -> Decimal:
    recurring = getattr(request, "recurring_revenue_percentage", None)
    recurring_decimal = _decimal_or_none(recurring)
    if recurring_decimal is None:
        return Decimal("0")
    if recurring_decimal > 1:
        return recurring_decimal / Decimal("100")
    return recurring_decimal


def _is_simple_high_growth(
    *,
    revenue: Decimal,
    historical_years_data: list[object],
    threshold: Decimal,
) -> bool:
    oldest_revenue = _oldest_historical_revenue(
        historical_years_data,
        fallback_to_first=True,
    )
    if oldest_revenue is None or oldest_revenue <= 0:
        return False
    growth_rate = (revenue - oldest_revenue) / oldest_revenue
    return growth_rate > threshold


def _is_cagr_high_growth(
    *,
    revenue: Decimal,
    historical_years_data: list[object],
    threshold: Decimal,
) -> bool:
    oldest_revenue = _oldest_historical_revenue(
        historical_years_data,
        fallback_to_first=False,
    )
    if oldest_revenue is None or oldest_revenue <= 0 or revenue <= 0:
        return False
    years = len(historical_years_data) + 1
    ratio = float(revenue / oldest_revenue)
    cagr = ratio ** (1.0 / years) - 1.0
    return cagr > float(threshold)


def _small_company_exception_signals(
    *,
    request: ValuationRequest,
    revenue: Decimal,
    recurring_threshold: Decimal,
    growth_threshold: Decimal,
    use_cagr_growth: bool,
) -> tuple[bool, bool]:
    historical_years_data = _actual_historical_years(request)
    if use_cagr_growth:
        is_high_growth = _is_cagr_high_growth(
            revenue=revenue,
            historical_years_data=historical_years_data,
            threshold=growth_threshold,
        )
    else:
        is_high_growth = _is_simple_high_growth(
            revenue=revenue,
            historical_years_data=historical_years_data,
            threshold=growth_threshold,
        )
    is_recurring_model = _recurring_revenue_fraction(request) > recurring_threshold
    return is_high_growth, is_recurring_model


class DCFExecutor(MethodologyExecutor):
    """
    Executor for DCF valuation methodology.

    Responsibilities:
    - Determine DCF eligibility based on company characteristics
    - Execute DCF calculation via DCFCalculator
    - Handle DCF-specific error cases
    """

    def __init__(self, dcf_calculator, logger: Optional[ValuationLogger] = None):
        """
        Initialize DCF executor.

        Args:
            dcf_calculator: DCFCalculator instance
            logger: Optional logger instance
        """
        super().__init__(logger)
        self.dcf_calculator = dcf_calculator
        self.logger.debug("✅ DCFExecutor initialized")

    @staticmethod
    def _user_explicitly_configured_dcf(request: ValuationRequest) -> bool:
        """Delegate to the single-source-of-truth in ``dcf_policy``."""
        return user_explicitly_configured_dcf(request)

    def should_calculate_dcf(self, request: ValuationRequest) -> Tuple[bool, Optional[str]]:
        """
        Determine if DCF should be calculated based on company characteristics.

        Per-request memoised by request content so the second and later calls
        in one /calculate return the cached verdict without re-logging the
        precheck. Object identity is intentionally not used: Python can reuse
        ``id(request)`` for a later valuation in a long-running process.

        When the user explicitly configured DCF parameters (WACC, terminal growth,
        forecast years, etc.), their intent is respected and revenue thresholds are
        bypassed.  Otherwise, the Small Firm Effect heuristics apply:

        Per academic valuation standards (Koller, Goedhart & Wessels 2020):
        - <€1M: Exclude DCF (Multiples only)
        - €1M-€5M: Exclude DCF (Multiples primary)
        - €5M-€10M: Conditional DCF (Hybrid, Multiples 60%, DCF 40%)
        - ≥€10M: Allow DCF as primary

        Args:
            request: Valuation request

        Returns:
            Tuple of (should_calculate, exclusion_reason)
        """
        from src.services.reports.forecast_admission import ForecastEvidenceError, optional_verified_forecast

        # Never let an eligibility-cache hit bypass current source verification
        # or a revoked signing key. An absent claim permits an indicative scenario.
        try:
            optional_verified_forecast(request)
        except ForecastEvidenceError as exc:
            return False, str(exc)
        cache_key = _request_cache_key(request)
        cached = _dcf_eligibility_cache_get(cache_key)
        if cached is not None:
            return cached

        result = self._compute_should_calculate_dcf(request)
        _dcf_eligibility_cache_put(cache_key, result)
        return result

    def _compute_should_calculate_dcf(
        self, request: ValuationRequest
    ) -> Tuple[bool, Optional[str]]:
        """Uncached implementation; ``should_calculate_dcf`` is the caching wrapper."""
        if self._user_explicitly_configured_dcf(request):
            self.logger.info(
                "✅ DCF allowed: user explicitly configured DCF parameters — "
                "revenue thresholds bypassed per selected_method / business_context contract"
            )
            return True, None

        history_exclusion = dcf_history_exclusion_reason(request)
        if history_exclusion:
            return False, history_exclusion

        revenue = request.current_year_data.revenue

        # Exclude DCF for micro-companies (<€100K)
        if revenue < 100_000:
            self.logger.info(f"⚠️ DCF excluded: Revenue €{revenue:,.0f} below €100K threshold")
            return False, "Revenue below €100K threshold (DCF not reliable for micro-businesses)"

        # Conditional DCF for very small companies (€100K-€1M)
        # Only allow if exceptional circumstances (high-growth or recurring revenue model)
        if revenue < 1_000_000:
            is_high_growth, is_recurring_model = _small_company_exception_signals(
                request=request,
                revenue=to_decimal(revenue),
                recurring_threshold=Decimal("0.70"),
                growth_threshold=Decimal("0.50"),
                use_cagr_growth=False,
            )

            if is_high_growth or is_recurring_model:
                self.logger.info(
                    f"✅ DCF allowed for small company (€{revenue:,.0f}): high-growth={is_high_growth}, recurring={is_recurring_model}"
                )
                return True, None  # DCF allowed for exceptional cases
            else:
                self.logger.info(
                    f"⚠️ DCF excluded: Revenue €{revenue:,.0f} below €1M with standard profile"
                )
                return (
                    False,
                    "Revenue below €1M with standard growth/revenue profile (Multiples more reliable)",
                )

        # For small companies (€1M-€5M): allow DCF in hybrid mode if high growth or recurring revenue
        # Per academic valuation standards, high-growth SMEs benefit from DCF even at smaller scale
        # (Damodaran 2012: growth-stage companies need DCF to capture future value creation)
        if revenue < 5_000_000:
            is_high_growth, is_recurring_model = _small_company_exception_signals(
                request=request,
                revenue=to_decimal(revenue),
                recurring_threshold=Decimal("0.50"),
                growth_threshold=Decimal("0.20"),
                use_cagr_growth=True,
            )

            if is_high_growth or is_recurring_model:
                self.logger.info(
                    f"✅ DCF allowed for €1M-€5M company (€{revenue:,.0f}): "
                    f"high-growth={is_high_growth}, recurring={is_recurring_model} "
                    f"(Hybrid approach, Multiples primary)"
                )
                return True, None
            else:
                self.logger.info(
                    f"⚠️ DCF excluded: Revenue €{revenue:,.0f} below €5M with standard profile (McKinsey standard)"
                )
                return (
                    False,
                    f"Revenue €{revenue:,.0f} below €5M threshold with standard growth profile "
                    f"(Multiples more accurate per Koller, Goedhart & Wessels 2020, Trugman 2017)",
                )

        # Conditional DCF for mid-size companies (€5M-€10M)
        # Allow DCF but will use Hybrid approach with lower weight (Multiples 60%, DCF 40%)
        if revenue < 10_000_000:
            self.logger.info(
                f"✅ DCF allowed: Revenue €{revenue:,.0f} in €5M-€10M range (Hybrid approach, Multiples primary)"
            )
            return True, None  # Conditional - will use Hybrid with lower DCF weight

        # Allow DCF for larger companies (≥€10M)
        self.logger.info(f"✅ DCF allowed: Revenue €{revenue:,.0f} ≥€10M (DCF suitable)")
        return True, None

    async def execute(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute DCF valuation.

        Args:
            request: Valuation request
            context: Optional processing context

        Returns:
            Dictionary with DCF valuation results
        """
        self.validate_request(request)

        try:
            self.logger.info("📊 Executing DCF valuation")

            # Check eligibility
            should_calculate, exclusion_reason = self.should_calculate_dcf(request)
            if not should_calculate:
                raise ValueError(f"DCF not eligible: {exclusion_reason}")

            # Execute DCF calculation
            dcf_results = await self.dcf_calculator.calculate(request, context)

            # Structure results
            detailed_results = dcf_results.copy()
            detailed_results["dcf_valuation"] = dcf_results

            self.logger.info(
                "✅ DCF valuation completed",
                extra={
                    "enterprise_value": detailed_results.get("enterprise_value"),
                    "equity_value": detailed_results.get("equity_value"),
                },
            )

            return detailed_results

        except Exception as e:
            self.handle_execution_error(e, request, context)
            raise
