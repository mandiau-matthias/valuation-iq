"""
Metrics Builder Module

Builds financial metrics dictionaries for valuation responses.

RESPONSIBILITIES:
- Build financial metrics from request and results
- Calculate derived metrics
- Format metrics for API responses

REFACTORING NOTE:
Extracted from valuation_orchestrator.py to isolate metrics building logic.
"""

from decimal import Decimal

from src.api.routes.valuation.shared.historical_years import historical_years_in_chronological_order
from src.api.schemas import ValuationRequest
from src.domain.revenue_growth import revenue_growth
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Earnings basis labels for `ebitda_margin`. Step 2 stamps the SAME two strings
# onto the margin-deviation warning (step_2_orchestrator.py), derived from the
# same Step 1 flag — keep them in sync or the two numbers stop being provably
# the same measurement.
WEIGHTED_MARGIN_BASIS = "step_1_weighted_earnings_basis"
REPORTED_MARGIN_BASIS = "current_year_reported"


class MetricsBuilder:
    """
    Builds financial metrics dictionaries

    Features:
    - Extract financial metrics
    - Calculate ratios and multiples
    - Format for API responses
    """

    def __init__(self):
        """Initialize metrics builder"""
        self.logger = logger
        self.logger.debug("✅ MetricsBuilder initialized")

    def build_financial_metrics(
        self, request: ValuationRequest, results: dict[str, object]
    ) -> dict[str, object]:
        """
        Build financial metrics dictionary

        Args:
            request: Valuation request
            results: Valuation results

        Returns:
            Dictionary of financial metrics
        """
        try:
            self.logger.debug("📊 Building financial metrics")

            revenue = request.current_year_data.revenue or 0
            ebitda = request.current_year_data.ebitda or 0
            equity_value = results.get("equity_value", 0)
            historical_years = historical_years_in_chronological_order(
                request.historical_years_data
            )

            latest_growth = revenue_growth(request.current_year_data, historical_years)
            three_year_growth = revenue_growth(
                request.current_year_data, historical_years, horizon="three_year"
            )
            # ONE RUN, ONE MARGIN. Step 1 is the margin authority: it divides the
            # McKinsey-weighted EBITDA (the basis the multiple is actually applied
            # to) by current-year revenue. Recomputing here from raw current-year
            # EBITDA published a SECOND, different margin in the same payload —
            # financial_metrics said 2.58% while the Step 2 warning said 3.17%.
            reported_ebitda_margin = self._calculate_ebitda_margin(revenue=revenue, ebitda=ebitda)
            canonical = self._step1_ebitda_margin(results)
            if canonical is not None:
                ebitda_margin, ebitda_margin_basis = canonical
            else:
                ebitda_margin = reported_ebitda_margin
                ebitda_margin_basis = REPORTED_MARGIN_BASIS
            financial_health_score, financial_health_description = (
                self._financial_health_from_margin(ebitda_margin)
            )
            enterprise_value = results.get("enterprise_value", 0)

            metrics = self._build_base_metrics(
                revenue=revenue,
                ebitda=ebitda,
                ebitda_margin=ebitda_margin,
                reported_ebitda_margin=reported_ebitda_margin,
                ebitda_margin_basis=ebitda_margin_basis,
                enterprise_value=enterprise_value,
                equity_value=equity_value,
                revenue_growth=latest_growth.rate,
                revenue_cagr_3y=three_year_growth.rate,
                financial_health_score=financial_health_score,
                financial_health_description=financial_health_description,
            )
            metrics["revenue_growth_evidence"] = latest_growth.to_payload()
            metrics["revenue_cagr_3y_evidence"] = three_year_growth.to_payload()
            self._add_optional_balance_metrics(metrics, request.current_year_data)
            self._add_ratio_metrics(metrics, request)

            self.logger.debug(
                "✅ Financial metrics built",
                extra={"metric_count": len(metrics), "revenue": revenue, "ebitda": ebitda},
            )

            return metrics

        except Exception as e:
            return self._fallback_metrics(request, results, e)

    def _calculate_ebitda_margin(self, *, revenue: Decimal, ebitda: Decimal) -> Decimal:
        if revenue <= 0:
            return Decimal("0.0")

        ebitda_margin_raw = ebitda / revenue
        return min(Decimal("1.0"), max(Decimal("0.0"), ebitda_margin_raw))

    def _step1_ebitda_margin(self, results: dict[str, object]) -> tuple[Decimal, str] | None:
        """Read Step 1's canonical EBITDA margin as a (fraction, basis) pair.

        Step 1 stores a PERCENT (e.g. Decimal("3.17")); `financial_metrics`
        publishes a FRACTION (0.0317). Converting here is what stops one
        response carrying two different numbers both named `ebitda_margin`.
        The basis label is derived from Step 1's own `using_weighted_metrics`
        flag — the same flag Step 2 reads — so the two producers cannot
        disagree about what they measured.

        Returns None when Step 1 did not run (e.g. DCF-only), so the caller
        falls back to the current-year computation.

        Note this path is deliberately NOT clamped to [0, 1]: a loss-making
        company should report its real negative margin rather than a
        cosmetic 0.0%.
        """
        multiples = results.get("multiples_valuation")
        if not isinstance(multiples, dict):
            return None
        step_results = multiples.get("_step_results")
        if not isinstance(step_results, dict):
            return None
        step1_data = getattr(step_results.get(1), "result", None)
        if not isinstance(step1_data, dict):
            return None
        raw_margin = step1_data.get("ebitda_margin")
        if raw_margin is None:
            return None
        try:
            margin_pct = Decimal(str(raw_margin))
        except (ArithmeticError, TypeError, ValueError):
            return None
        if not margin_pct.is_finite():
            return None

        basis = (
            WEIGHTED_MARGIN_BASIS
            if step1_data.get("using_weighted_metrics")
            else REPORTED_MARGIN_BASIS
        )
        return margin_pct / Decimal("100"), basis

    def _financial_health_from_margin(self, ebitda_margin: Decimal) -> tuple[int, str]:
        if ebitda_margin > Decimal("0.20"):
            return 90, "Excellent"
        if ebitda_margin > Decimal("0.10"):
            return 75, "Good"
        if ebitda_margin > Decimal("0"):
            return 60, "Moderate"
        return 40, "Poor"

    def _build_base_metrics(
        self,
        *,
        revenue: Decimal,
        ebitda: Decimal,
        ebitda_margin: Decimal,
        reported_ebitda_margin: Decimal | None = None,
        ebitda_margin_basis: str = REPORTED_MARGIN_BASIS,
        enterprise_value: Decimal,
        equity_value: Decimal,
        revenue_growth: Decimal | None,
        revenue_cagr_3y: Decimal | None,
        financial_health_score: int,
        financial_health_description: str,
    ) -> dict[str, object]:
        return {
            "revenue": revenue,
            "ebitda": ebitda,
            "ebitda_margin": ebitda_margin,
            "ebitda_margin_basis": ebitda_margin_basis,
            # The raw current-year ratio, kept so a payload written before the
            # canonical margin was adopted can still be reconciled with one
            # written after.
            "reported_ebitda_margin": (
                reported_ebitda_margin if reported_ebitda_margin is not None else ebitda_margin
            ),
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "ev_revenue_multiple": (enterprise_value / revenue) if revenue > 0 else 0,
            "ev_ebitda_multiple": (enterprise_value / ebitda) if ebitda > 0 else 0,
            "revenue_growth": revenue_growth,
            "revenue_cagr_3y": revenue_cagr_3y,
            "financial_health_score": financial_health_score,
            "financial_health_description": financial_health_description,
        }

    def _add_optional_balance_metrics(
        self, metrics: dict[str, object], current_year_data: object
    ) -> None:
        if hasattr(current_year_data, "total_assets"):
            metrics["total_assets"] = getattr(current_year_data, "total_assets") or 0

        if hasattr(current_year_data, "total_debt"):
            metrics["total_debt"] = getattr(current_year_data, "total_debt") or 0

    # Ratios the response schema declares but this builder never computed. They
    # were null on every v1 report — 12 of 19 on the first paying advisor's —
    # while a "financial health score" was still printed from what remained.
    # The domain calculator has always known how; it was simply never asked.
    _RATIO_KEYS = (
        "gross_margin",
        "ebit_margin",
        "net_margin",
        "return_on_assets",
        "return_on_equity",
        "current_ratio",
        "quick_ratio",
        "cash_ratio",
        "debt_to_equity",
        "debt_to_assets",
        "interest_coverage",
        "asset_turnover",
        "receivables_turnover",
        "inventory_turnover",
        "altman_z_score",
        "ebitda_growth",
    )

    def _domain_financial_data(self, request: ValuationRequest):
        """The domain ``FinancialData`` for this request, or ``None`` when the
        request is too thin to convert. Lazy import: the adapter package imports
        this module's neighbours."""
        from src.api.routes.valuation.calculators.dcf_data_adapter import DCFDataAdapter

        return DCFDataAdapter().create_financial_data(request)

    def _add_ratio_metrics(self, metrics: dict[str, object], request: ValuationRequest) -> None:
        """Fill ratio keys the builder left empty from the domain calculator.

        The builder stays the authority for ``ebitda_margin`` / ``revenue_growth``
        (Step 1's weighted basis); this only adds what is still ``None``. Each
        ratio is ``None`` in the calculator too when its inputs are absent, so a
        thin request gains nothing and loses nothing.
        """
        try:
            financial_data = self._domain_financial_data(request)
        except Exception as exc:  # noqa: BLE001 - a thin request must never fail the run
            logger.info("Ratio metrics skipped: request not convertible", extra={"error": str(exc)})
            return
        if financial_data is None:
            return
        try:
            from src.domain.financial_metrics import FinancialMetricsCalculator

            computed = FinancialMetricsCalculator(financial_data).calculate_all_metrics()
        except Exception as exc:  # noqa: BLE001
            logger.info("Ratio metrics skipped: calculator failed", extra={"error": str(exc)})
            return
        for key in self._RATIO_KEYS:
            if metrics.get(key) is not None:
                continue
            value = getattr(computed, key, None)
            if value is not None:
                metrics[key] = value

    def _fallback_metrics(
        self,
        request: ValuationRequest,
        results: dict[str, object],
        error: Exception,
    ) -> dict[str, object]:
        self.logger.error(
            "❌ Metrics building failed",
            extra={"error": str(error), "error_type": type(error).__name__},
            exc_info=True,
        )
        # Return partial results with error flags instead of empty dict
        # so the frontend can display available metrics and show errors gracefully.
        return {
            "revenue": request.current_year_data.revenue or 0,
            "ebitda": request.current_year_data.ebitda or 0,
            "ebitda_margin": Decimal("0.0"),
            "ebitda_margin_basis": REPORTED_MARGIN_BASIS,
            "reported_ebitda_margin": Decimal("0.0"),
            "enterprise_value": results.get("enterprise_value", 0),
            "equity_value": results.get("equity_value", 0),
            "ev_revenue_multiple": 0,
            "ev_ebitda_multiple": 0,
            "revenue_growth": None,
            "revenue_cagr_3y": None,
            "financial_health_score": 50,
            "financial_health_description": "Unknown",
            "calculation_errors": [f"Metrics calculation failed: {str(error)}"],
        }
