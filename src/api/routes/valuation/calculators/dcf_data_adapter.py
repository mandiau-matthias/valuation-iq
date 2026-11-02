"""
DCF Data Adapter

Converts ValuationRequest API schema to domain models required by DCFValuationEngineRefactored.
Provides intelligent defaults for market context and industry benchmarks.

SaaS contract: ARR/MRR can align reported revenue before forecast synthesis. NRR,
churn, and Rule of 40 adjust omni/ARR multiples, not year-by-year DCF cohorts.
"""

import uuid
from decimal import Decimal
from typing import NamedTuple, Optional

from src.api.routes.valuation.calculators.dcf_country_defaults import (
    COUNTRY_DEFAULTS as DCF_COUNTRY_DEFAULTS,
    EU_COUNTRIES as DCF_EU_COUNTRIES,
    INDUSTRY_DEFAULTS as DCF_INDUSTRY_DEFAULTS,
    resolve_country_defaults,
)
from src.api.routes.valuation.calculators.dcf_market_context_adapter import (
    build_dcf_market_context,
)
from src.api.schemas import ValuationRequest, YearDataInput
from src.api.routes.valuation.calculators.dcf_tax_policy import resolve_dcf_tax_assumption
from src.domain.asset_based_support import normalize_business_model
from src.domain.market_defaults import get_risk_free_rate, resolve_equity_risk_premium
from src.domain.models import (
    FinancialData,
    IndustryBenchmarks,
    IndustryCode,
    MarketContext,
    YearData,
)
from src.utils.adaptive_input_helpers import (
    get_business_context,
    get_business_context_decimal,
    get_business_context_percent,
    get_dcf_da_pct_override,
    get_percent_override,
    get_recurring_revenue_override,
    is_saas_context,
)
from src.utils.dcf_forecast_nwc import repair_legacy_full_revenue_nwc_change
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class _ForecastProcessingResult(NamedTuple):
    forecast_years: list[YearData]
    was_synthesized: bool


class DCFDataAdapter:
    """
    Adapter to convert ValuationRequest to domain models for DCF engine.

    Provides intelligent defaults based on:
    - Country-specific economic indicators
    - Industry-specific benchmarks
    - Global market standards

    Concurrency: each request should use a dedicated adapter instance (or only call
    ``create_*`` methods sequentially on one instance). ``create_market_context`` returns
    provenance metadata as a second value so nothing depends on mutable adapter fields.
    """

    COUNTRY_DEFAULTS = DCF_COUNTRY_DEFAULTS
    INDUSTRY_DEFAULTS = DCF_INDUSTRY_DEFAULTS
    EU_COUNTRIES = DCF_EU_COUNTRIES

    @classmethod
    def _resolve_country_defaults(cls, country_code: Optional[str]) -> dict:
        """Compatibility wrapper for the Delphi-overlaid country defaults provider."""
        return resolve_country_defaults(
            country_code,
            country_defaults=cls.COUNTRY_DEFAULTS,
        )

    def __init__(self):
        """Initialize the adapter"""
        self.logger = logger
        self.logger.debug("✅ DCFDataAdapter initialized")

    @staticmethod
    def _normalize_country_code(country_code: object) -> str:
        """Canonicalize country codes for market defaults and provenance."""
        code = str(country_code or "").strip().upper()
        return "GB" if code == "UK" else code

    def _derive_capex_ratio_from_history(self, request: ValuationRequest) -> Optional[Decimal]:
        """
        Prefer sum(capex) / sum(revenue) when historical capex is present.
        Otherwise fall back to sum(depreciation) / sum(revenue) as a maintenance-capex proxy.
        """
        current_year = getattr(request, "current_year_data", None)
        historical_years = list(getattr(request, "historical_years_data", None) or [])
        years = ([current_year] if current_year is not None else []) + historical_years
        if not years:
            return None
        capex_num = Decimal("0")
        capex_den = Decimal("0")
        depreciation_total = Decimal("0")
        revenue_total = Decimal("0")

        for year in years:
            if getattr(year, "is_forecast", False):
                continue
            revenue = getattr(year, "revenue", None)
            if revenue is None:
                continue
            revenue_decimal = to_decimal(revenue)
            if revenue_decimal <= 0:
                continue
            capex = getattr(year, "capex", None)
            if capex is not None and to_decimal(capex) > 0:
                capex_num += to_decimal(capex)
                capex_den += revenue_decimal
            depreciation = getattr(year, "depreciation", None)
            if depreciation is None:
                continue
            depreciation_decimal = to_decimal(depreciation)
            if depreciation_decimal < 0:
                continue
            revenue_total += revenue_decimal
            depreciation_total += depreciation_decimal

        if capex_den > 0 and capex_num > 0:
            return capex_num / capex_den
        if revenue_total > 0 and depreciation_total > 0:
            return depreciation_total / revenue_total
        return None

    def _convert_historical_years(self, request: ValuationRequest) -> list[YearData]:
        return [
            self._convert_year_data(year_data)
            for year_data in request.historical_years_data
            if not getattr(year_data, "is_forecast", False)
        ]

    @staticmethod
    def _resolve_recurring_revenue_percentage(request: ValuationRequest) -> Decimal:
        recurring_revenue_percentage = get_recurring_revenue_override(request)
        if recurring_revenue_percentage is not None:
            return recurring_revenue_percentage
        return getattr(request, "recurring_revenue_percentage", Decimal("0"))

    def _apply_saas_arr_to_current_year(
        self,
        *,
        request: ValuationRequest,
        current_year: YearData,
        recurring_revenue_percentage: Optional[Decimal],
    ) -> Optional[Decimal]:
        business_context = get_business_context(request)
        if not is_saas_context(
            business_context=business_context,
            business_type_id=getattr(request, "business_type_id", None),
            business_model=getattr(request, "business_model", None),
            industry=getattr(request, "industry", None),
        ):
            return None

        saas_arr = get_business_context_decimal(business_context, "saas_arr")
        saas_mrr = get_business_context_decimal(business_context, "saas_mrr")
        arr_revenue = saas_arr or (saas_mrr * Decimal("12") if saas_mrr is not None else None)
        if arr_revenue is None or arr_revenue <= 0:
            return None

        base_current_revenue = current_year.revenue
        current_year.revenue = arr_revenue
        if base_current_revenue is not None and base_current_revenue > 0:
            return arr_revenue / base_current_revenue
        if recurring_revenue_percentage is not None and recurring_revenue_percentage > 0:
            return recurring_revenue_percentage
        return None

    def _prepare_forecast_years(
        self, *, request: ValuationRequest, current_year: YearData
    ) -> _ForecastProcessingResult:
        raw_forecast_inputs = getattr(request, "forecast_years_data", None) or []
        forecast_years = [
            self._convert_year_data(year_data, is_forecast=True)
            for year_data in raw_forecast_inputs
        ]
        forecast_years = self._strip_trailing_placeholder_forecast_rows(forecast_years)

        if forecast_years and self._all_forecast_rows_non_positive(forecast_years):
            self.logger.warning(
                "⚠️ Explicit forecast_years_data are all non-positive (placeholders); "
                "using synthesized projections from business_context / DCF overrides",
                extra={"company": getattr(request, "company_name", None)},
            )
            forecast_years = []

        if forecast_years:
            self._repair_legacy_forecast_nwc_changes(
                request=request,
                current_year=current_year,
                forecast_years=forecast_years,
            )
            return _ForecastProcessingResult(forecast_years, False)

        forecast_years = self._synthesize_forecast_years(request, current_year)
        if not forecast_years and raw_forecast_inputs:
            self.logger.warning(
                "No usable forecast rows after processing forecast_years_data; "
                "synthesis returned empty (add DCF percentage overrides in business_context or "
                "non-zero revenue/EBITDA in the grid). DCF will use implicit projection from "
                "historical cash flows.",
                extra={"company": getattr(request, "company_name", None)},
            )
        return _ForecastProcessingResult(forecast_years, bool(forecast_years))

    def _ensure_historical_years(
        self,
        *,
        current_year: YearData,
        historical_years: list[YearData],
    ) -> list[YearData]:
        if historical_years:
            return historical_years

        # The request schema owns DCF admission. At this layer current_year is
        # already the admitted, closed basis fiscal year and CashFlowProjector
        # appends it exactly once. Returning an empty prior-year list avoids
        # both rejecting an admitted run and duplicating the basis observation.
        self.logger.info(
            "No prior fiscal years supplied; using the closed basis fiscal year",
            extra={"basis_year": current_year.year},
        )
        return []

    @staticmethod
    def _apply_saas_scale_ratio(
        *,
        historical_years: list[YearData],
        forecast_years: list[YearData],
        current_year: YearData,
        saas_scale_ratio: Optional[Decimal],
        forecast_was_synthesized: bool,
    ) -> None:
        if saas_scale_ratio is None or saas_scale_ratio <= 0:
            return

        for year in historical_years:
            if year is current_year:
                continue
            if year.revenue is not None and year.revenue > 0:
                year.revenue = year.revenue * saas_scale_ratio

        if forecast_was_synthesized:
            return
        for year in forecast_years:
            if year.revenue is not None and year.revenue > 0:
                year.revenue = year.revenue * saas_scale_ratio

    @staticmethod
    def _build_financial_data(
        *,
        request: ValuationRequest,
        company_id: str,
        current_year: YearData,
        historical_years: list[YearData],
        forecast_years: list[YearData],
        recurring_revenue_percentage: Decimal,
    ) -> FinancialData:
        return FinancialData(
            company_id=company_id,
            company_name=request.company_name,
            country_code=request.country_code,
            industry=request.industry,
            business_model=normalize_business_model(request.business_model),
            founding_year=request.founding_year,
            historical_years=historical_years,
            current_year=current_year,
            forecast_years=forecast_years,
            number_of_employees=request.number_of_employees,
            recurring_revenue_percentage=recurring_revenue_percentage,
            has_complete_financials=len(request.historical_years_data) > 0,
        )

    def create_financial_data(self, request: ValuationRequest) -> FinancialData:
        """
        Convert ValuationRequest to FinancialData domain model.

        Args:
            request: Valuation request from API

        Returns:
            FinancialData model for DCF engine
        """
        try:
            self.logger.info(
                "📊 Creating FinancialData from request",
                extra={
                    "company": request.company_name,
                    "industry": request.industry,
                    "has_historical": len(request.historical_years_data) > 0,
                },
            )

            company_id = f"dcf_{uuid.uuid4().hex[:12]}"
            current_year = self._convert_year_data(request.current_year_data)
            historical_years = self._convert_historical_years(request)
            recurring_revenue_percentage = self._resolve_recurring_revenue_percentage(request)
            saas_scale_ratio = self._apply_saas_arr_to_current_year(
                request=request,
                current_year=current_year,
                recurring_revenue_percentage=recurring_revenue_percentage,
            )
            forecast_result = self._prepare_forecast_years(
                request=request,
                current_year=current_year,
            )
            forecast_years = forecast_result.forecast_years
            historical_years = self._ensure_historical_years(
                current_year=current_year,
                historical_years=historical_years,
            )
            self._apply_saas_scale_ratio(
                historical_years=historical_years,
                forecast_years=forecast_years,
                current_year=current_year,
                saas_scale_ratio=saas_scale_ratio,
                forecast_was_synthesized=forecast_result.was_synthesized,
            )
            financial_data = self._build_financial_data(
                request=request,
                company_id=company_id,
                current_year=current_year,
                historical_years=historical_years,
                forecast_years=forecast_years,
                recurring_revenue_percentage=recurring_revenue_percentage,
            )

            self.logger.info(
                "✅ FinancialData created successfully",
                extra={
                    "company_id": company_id,
                    "historical_years_count": len(historical_years),
                    "current_year_revenue": current_year.revenue,
                },
            )

            return financial_data

        except Exception as e:
            self.logger.error(
                "❌ Failed to create FinancialData",
                extra={"error": str(e), "company": request.company_name},
                exc_info=True,
            )
            raise

    def create_market_context(
        self, request: ValuationRequest
    ) -> tuple[MarketContext, dict[str, object]]:
        """
        Create MarketContext with country-specific defaults.

        Args:
            request: Valuation request from API

        Returns:
            ``(market_context, provenance_metadata)``. Provenance is returned alongside the
            domain model so callers never rely on mutable adapter state (safe under concurrency
            if the same adapter instance were ever reused).
        """
        return build_dcf_market_context(
            request=request,
            logger=self.logger,
            normalize_country_code=self._normalize_country_code,
            resolve_country_defaults=self._resolve_country_defaults,
            get_risk_free_rate_fn=get_risk_free_rate,
            resolve_equity_risk_premium_fn=resolve_equity_risk_premium,
        )

    def create_industry_benchmarks(self, request: ValuationRequest) -> IndustryBenchmarks:
        """
        Create IndustryBenchmarks with industry-specific defaults.

        Args:
            request: Valuation request from API

        Returns:
            IndustryBenchmarks model for DCF engine
        """
        try:
            self.logger.info(
                "🏭 Creating IndustryBenchmarks",
                extra={"industry": request.industry, "country": request.country_code},
            )
            country_code = self._normalize_country_code(request.country_code)

            # Get industry-specific defaults
            industry_key = (
                request.industry.value
                if hasattr(request.industry, "value")
                else str(request.industry)
            )
            industry_defaults = self.INDUSTRY_DEFAULTS.get(
                industry_key, self.INDUSTRY_DEFAULTS["other"]
            )
            business_context = get_business_context(request)
            growth_override = get_percent_override(request, "dcf_revenue_growth_pct")
            ebitda_margin_override = get_percent_override(request, "dcf_ebitda_margin_pct")
            capex_override = get_percent_override(request, "dcf_capex_pct")
            da_override = get_dcf_da_pct_override(request)
            nwc_override = get_percent_override(request, "dcf_nwc_pct")
            saas_arr_growth = get_business_context_percent(business_context, "saas_arr_growth_pct")
            saas_nrr = get_business_context_percent(business_context, "saas_nrr_pct")
            saas_revenue_churn = get_business_context_percent(business_context, "saas_churn_pct")

            tax_rate = resolve_dcf_tax_assumption(request).rate

            # Determine region
            if country_code in self.EU_COUNTRIES:
                region = "EU"
            elif country_code == "US":
                region = "US"
            elif country_code == "GB":
                region = "UK"
            else:
                region = "OTHER"

            expected_growth_rate = growth_override
            if expected_growth_rate is None and is_saas_context(
                business_context=business_context,
                business_type_id=getattr(request, "business_type_id", None),
                business_model=getattr(request, "business_model", None),
                industry=getattr(request, "industry", None),
            ):
                expected_growth_rate = saas_arr_growth
                if saas_nrr is not None:
                    nrr_expansion = max(saas_nrr - Decimal("1"), Decimal("0"))
                    expected_growth_rate = (
                        max(expected_growth_rate, nrr_expansion)
                        if expected_growth_rate is not None
                        else nrr_expansion
                    )
                if saas_revenue_churn is not None and expected_growth_rate is not None:
                    expected_growth_rate = max(
                        expected_growth_rate - (saas_revenue_churn * Decimal("0.5")),
                        Decimal("0"),
                    )
            if expected_growth_rate is None:
                expected_growth_rate = industry_defaults["growth"]
            avg_ebitda_margin = (
                ebitda_margin_override
                if ebitda_margin_override is not None
                else industry_defaults["ebitda_margin"]
            )
            derived_capex_ratio = self._derive_capex_ratio_from_history(request)
            avg_capex_to_revenue = (
                capex_override
                if capex_override is not None
                else (
                    derived_capex_ratio
                    if derived_capex_ratio is not None
                    else industry_defaults["capex_to_revenue"]
                )
            )

            industry_benchmarks = IndustryBenchmarks(
                industry=request.industry,
                region=region,
                expected_growth_rate=expected_growth_rate,
                historical_growth_rate=expected_growth_rate
                * Decimal("0.9"),  # Slightly lower historical
                average_beta=industry_defaults["beta"],
                avg_tax_rate=tax_rate,
                avg_ebitda_margin=avg_ebitda_margin,
                avg_capex_to_revenue=avg_capex_to_revenue,
                avg_da_to_revenue=da_override,
                avg_nwc_to_revenue=nwc_override or Decimal("0"),
                median_ev_ebitda=industry_defaults["ev_ebitda"],
                median_ev_revenue=industry_defaults["ev_revenue"],
                data_quality="medium",
            )

            self.logger.info(
                "✅ IndustryBenchmarks created",
                extra={
                    "industry": industry_key,
                    "region": region,
                    "beta": industry_defaults["beta"],
                    "growth_rate": f"{industry_defaults['growth']*100:.1f}%",
                    "tax_rate": f"{tax_rate*100:.1f}%",
                },
            )

            return industry_benchmarks

        except Exception as e:
            self.logger.error(
                "❌ Failed to create IndustryBenchmarks",
                extra={"error": str(e), "industry": request.industry},
                exc_info=True,
            )
            raise

    def _strip_trailing_placeholder_forecast_rows(
        self, forecast_years: list[YearData]
    ) -> list[YearData]:
        """Drop trailing rows with revenue and EBITDA both <= 0 (unfilled grid cells).

        Venus/Titan often leave the outer years at zero while the user edits the first year.
        Those trailing placeholders should not extend the explicit FCF horizon with zeros.
        """
        if not forecast_years:
            return []
        original_len = len(forecast_years)
        sorted_years = sorted(forecast_years, key=lambda y: y.year)
        while sorted_years:
            last = sorted_years[-1]
            rev = to_decimal(last.revenue or 0)
            ebitda = to_decimal(last.ebitda or 0)
            explicit_fcff = getattr(last, "free_cash_flow", None)
            if rev <= 0 and ebitda <= 0 and explicit_fcff is None:
                sorted_years.pop()
            else:
                break
        if len(sorted_years) < original_len:
            self.logger.info(
                "Stripped trailing placeholder forecast rows (revenue and EBITDA both <= 0)",
                extra={"remaining": len(sorted_years), "original": original_len},
            )
        return sorted_years

    def _all_forecast_rows_non_positive(self, forecast_years: list[YearData]) -> bool:
        """True when every forecast row has revenue <= 0 and EBITDA <= 0 (placeholder grids).

        Venus/Titan often send a full horizon of forecast rows with zeros until the user fills
        the grid; those must not drive the explicit-FCF path. Cleared rows are replaced by
        :meth:`_synthesize_forecast_years` when DCF percentage overrides exist in ``business_context``.
        """
        if not forecast_years:
            return False
        for y in forecast_years:
            if getattr(y, "free_cash_flow", None) is not None:
                return False
            rev = to_decimal(y.revenue or 0)
            ebitda = to_decimal(y.ebitda or 0)
            if rev > 0 or ebitda > 0:
                return False
        return True

    def _repair_legacy_forecast_nwc_changes(
        self,
        *,
        request: ValuationRequest,
        current_year: YearData,
        forecast_years: list[YearData],
    ) -> None:
        """Repair persisted forecast rows that used full revenue for ΔNWC.

        The UI now treats ``dcf_nwc_pct`` as an NWC ratio and applies it only to
        the year-over-year revenue movement. Older auto-filled explicit rows can
        still arrive with ``nwc_change = forecast revenue * dcf_nwc_pct``; fix
        those exact rows while preserving advisor-entered manual overrides.
        """
        nwc_ratio = get_percent_override(request, "dcf_nwc_pct")
        if nwc_ratio is None:
            return

        previous_revenue = to_decimal(current_year.revenue or 0)
        repaired_count = 0
        for forecast_year in sorted(forecast_years, key=lambda y: y.year):
            revenue = to_decimal(forecast_year.revenue or 0)
            repaired_nwc_change = repair_legacy_full_revenue_nwc_change(
                supplied_nwc_change=forecast_year.nwc_change,
                revenue=revenue,
                previous_revenue=previous_revenue,
                nwc_ratio=nwc_ratio,
            )
            if repaired_nwc_change is not None:
                forecast_year.nwc_change = repaired_nwc_change
                repaired_count += 1
            if revenue > 0:
                previous_revenue = revenue

        if repaired_count:
            self.logger.info(
                "Repaired legacy DCF forecast ΔNWC rows from full-revenue percent "
                "to growth-based NWC ratio",
                extra={
                    "company": getattr(request, "company_name", None),
                    "rows": repaired_count,
                },
            )

    def _synthesize_forecast_years(
        self, request: ValuationRequest, current_year: YearData
    ) -> list[YearData]:
        """Synthesize forecast rows from DCF percentage overrides in business_context.

        Mirrors ``_generate_stateless_dcf_forecast_years`` in stateless_router but
        produces domain ``YearData`` objects so the DCF engine takes the explicit
        forecast path with properly populated revenue, EBITDA, CapEx, and NWC.
        """
        revenue_growth = get_percent_override(request, "dcf_revenue_growth_pct")
        ebitda_margin = get_percent_override(request, "dcf_ebitda_margin_pct")
        capex_ratio = get_percent_override(request, "dcf_capex_pct")
        da_ratio = get_dcf_da_pct_override(request)
        nwc_ratio = get_percent_override(request, "dcf_nwc_pct")
        if (
            revenue_growth is None
            and ebitda_margin is None
            and capex_ratio is None
            and nwc_ratio is None
        ):
            return []

        tax_rate = resolve_dcf_tax_assumption(request).rate

        base_revenue = to_decimal(current_year.revenue or 0)
        if base_revenue <= 0:
            return []

        base_ebitda = to_decimal(current_year.ebitda or 0)
        current_margin = base_ebitda / base_revenue if base_revenue > 0 else Decimal("0")

        growth_rate = revenue_growth or Decimal("0")
        target_margin = ebitda_margin if ebitda_margin is not None else current_margin
        target_capex_ratio = capex_ratio
        target_da_ratio = da_ratio
        target_nwc_ratio = nwc_ratio

        projection_years = getattr(request, "projection_years", None) or 5

        forecasts: list[YearData] = []
        projected_revenue = base_revenue
        previous_revenue = base_revenue

        for offset in range(1, projection_years + 1):
            projected_revenue = projected_revenue * (Decimal("1") + growth_rate)
            projected_ebitda = projected_revenue * target_margin
            projected_da = (
                projected_revenue * target_da_ratio if target_da_ratio is not None else None
            )
            projected_capex = (
                projected_revenue * target_capex_ratio if target_capex_ratio is not None else None
            )
            projected_nwc_change = (
                (projected_revenue - previous_revenue) * target_nwc_ratio
                if target_nwc_ratio is not None
                else None
            )

            projected_ebit = None
            projected_taxes = None
            if projected_da is not None:
                projected_ebit = projected_ebitda - projected_da
                projected_taxes = max(Decimal("0"), projected_ebit) * tax_rate

            forecasts.append(
                YearData(
                    year=current_year.year + offset,
                    revenue=projected_revenue,
                    ebitda=projected_ebitda,
                    ebit=projected_ebit,
                    depreciation=projected_da,
                    tax_expense=projected_taxes,
                    capex=projected_capex,
                    nwc_change=projected_nwc_change,
                    is_forecast=True,
                )
            )
            previous_revenue = projected_revenue

        self.logger.info(
            "Synthesized forecast rows from DCF percentage overrides",
            extra={
                "projection_years": len(forecasts),
                "growth_rate": str(growth_rate),
                "ebitda_margin": str(target_margin),
            },
        )
        return forecasts

    def _convert_year_data(
        self, year_input: YearDataInput, is_forecast: Optional[bool] = None
    ) -> YearData:
        """
        Convert YearDataInput (API schema) to YearData (domain model).

        Args:
            year_input: Year data from API request

        Returns:
            YearData domain model
        """
        return YearData(
            year=getattr(year_input, "year"),
            revenue=getattr(year_input, "revenue"),
            cogs=getattr(year_input, "cogs", None),
            gross_profit=getattr(year_input, "gross_profit", None),
            operating_expenses=getattr(year_input, "operating_expenses", None),
            ebitda=getattr(year_input, "ebitda", None),
            ebit=getattr(year_input, "ebit", None),
            depreciation=getattr(year_input, "depreciation", None),
            amortization=getattr(year_input, "amortization", None),
            interest_expense=getattr(year_input, "interest_expense", None),
            tax_expense=getattr(year_input, "tax_expense", None),
            net_income=getattr(year_input, "net_income", None),
            total_assets=getattr(year_input, "total_assets", None),
            current_assets=getattr(year_input, "current_assets", None),
            cash=getattr(year_input, "cash", None),
            accounts_receivable=getattr(year_input, "accounts_receivable", None),
            inventory=getattr(year_input, "inventory", None),
            total_liabilities=getattr(year_input, "total_liabilities", None),
            current_liabilities=getattr(year_input, "current_liabilities", None),
            total_debt=getattr(year_input, "total_debt", None),
            total_equity=getattr(year_input, "total_equity", None),
            capex=getattr(year_input, "capex", None),
            nwc_change=getattr(year_input, "nwc_change", None),
            free_cash_flow=getattr(year_input, "free_cash_flow", None),
            is_forecast=(
                is_forecast
                if is_forecast is not None
                else getattr(year_input, "is_forecast", False)
            ),
        )
