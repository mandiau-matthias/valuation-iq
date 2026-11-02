"""
Alternative Valuation Executor for Comprehensive Valuation Orchestrator

Handles execution of alternative valuation methodologies (asset-based, market, income, cost).
"""

from decimal import Decimal
from typing import Dict, Optional

from src.api.schemas import ValuationRequest
from src.config.valuation_constants import get_asking_price_markup
from src.domain.asset_based_support import calculate_adjusted_nav_payload
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger


class AssetBasedUnavailableError(ValueError):
    """Adjusted NAV cannot be used for this request, but the engine is otherwise healthy."""

    def __init__(self, payload: Dict[str, object] | str):
        if isinstance(payload, dict):
            reason = str(payload.get("unavailable_reason") or "Adjusted NAV unavailable")
            super().__init__(reason)
            self.payload: Dict[str, object] = dict(payload)
        else:
            reason = str(payload)
            super().__init__(reason)
            self.payload = {
                "unavailable_reason": reason,
                "unavailable_code": "NAV_UNAVAILABLE",
                "missing_fields": [],
                "remediation": None,
                "details": {},
            }

    def to_metadata(self) -> Dict[str, object]:
        return {
            "reason": str(self.payload.get("unavailable_reason") or str(self)),
            "code": self.payload.get("unavailable_code"),
            "missing_fields": list(self.payload.get("missing_fields") or []),
            "remediation": self.payload.get("remediation"),
            "details": dict(self.payload.get("details") or {}),
        }


class RealEstateYieldUnavailableError(ValueError):
    """Income-capitalisation (rent ÷ cap-rate) cannot be used for this request;
    the executor falls back to Asset-Based (NAV) — the engine is otherwise healthy."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason

    def to_metadata(self) -> Dict[str, object]:
        return {
            "reason": self.reason,
            "code": "YIELD_UNAVAILABLE",
            "missing_fields": [],
            "remediation": None,
            "details": {},
        }


def _property_type_for(industry: Optional[str]):
    """Resolve a PropertyType from the industry/business-type tag.

    No NACE→PropertyType registry exists yet; this is a conservative resolver
    that maps the common Belgian patrimonium tags to a cap-rate band. Generic
    vastgoed / mixed real estate → MIXED_USE (5–7%). A future business-type DB
    seed can override the cap-rate band per sector via RealEstateYieldInputs.
    """
    from src.domain.real_estate_yield import PropertyType

    ind = (industry or "").strip().lower()
    if "retail" in ind or "winkel" in ind:
        return PropertyType.RETAIL_HIGH_STREET
    if "office" in ind or "kantoor" in ind:
        return PropertyType.OFFICE_SECONDARY
    if any(t in ind for t in ("industrial", "logistic", "warehouse", "magazijn")):
        return PropertyType.INDUSTRIAL_LOGISTICS
    if any(t in ind for t in ("residential", "housing", "woning", "huisvesting")):
        return PropertyType.RESIDENTIAL
    # real_estate_holding / vastgoed / patrimony / property / default
    return PropertyType.MIXED_USE


class AlternativeValuationExecutor:
    """Executes alternative valuation methodologies."""

    def __init__(self, logger: ValuationLogger):
        """
        Initialize the alternative valuation executor.

        Args:
            logger: Logger instance
        """
        self.logger = logger

    async def execute_asset_based_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, object]]
    ) -> Dict[str, object]:
        """Execute asset-based valuation using the shared adjusted NAV engine."""
        self.logger.info("📊 Executing asset-based valuation")
        shares_for_sale = getattr(request, "shares_for_sale", None)
        ownership_multiplier = Decimal("1")
        if shares_for_sale is not None:
            shares_decimal = to_decimal(shares_for_sale)
            if shares_decimal < Decimal("100"):
                ownership_multiplier = shares_decimal / Decimal("100")
        payload = calculate_adjusted_nav_payload(
            company_name=request.company_name,
            industry=request.industry,
            business_model=getattr(request, "business_model", None),
            founding_year=getattr(request, "founding_year", None),
            reporting_year=getattr(request.current_year_data, "year", None),
            revenue=getattr(request.current_year_data, "revenue", 0),
            ebitda=getattr(request.current_year_data, "ebitda", 0),
            ownership_multiplier=ownership_multiplier,
            country_code=getattr(request, "country_code", "BE"),
            balance_sheet={
                "total_assets": getattr(request.current_year_data, "total_assets", None),
                "current_assets": getattr(request.current_year_data, "current_assets", None),
                "cash": getattr(request.current_year_data, "cash", None),
                "accounts_receivable": getattr(
                    request.current_year_data, "accounts_receivable", None
                ),
                "inventory": getattr(request.current_year_data, "inventory", None),
                "total_liabilities": getattr(request.current_year_data, "total_liabilities", None),
                "current_liabilities": getattr(
                    request.current_year_data, "current_liabilities", None
                ),
                "total_debt": getattr(request.current_year_data, "total_debt", None),
                "total_equity": getattr(request.current_year_data, "total_equity", None),
            },
            business_context=getattr(request, "business_context", None),
        )
        if not payload["available"]:
            raise AssetBasedUnavailableError(payload)

        confidence_level = str(payload.get("confidence_level") or "MEDIUM").lower()
        # Pass-5: respect advisor-configured override on the asset-based path too.
        recommended_asking_price = (
            payload["equity_value"]
            * get_asking_price_markup(
                confidence_level,
                advisor_override_pct=getattr(request, "asking_price_buffer_pct", None),
            )
        ).quantize(Decimal("0.01"))

        return {
            "methodology": "ASSET_BASED",
            "methodology_label": payload.get("methodology_label"),
            "enterprise_value": payload["enterprise_value"],
            "equity_value": payload["equity_value"],
            "equity_value_low": payload["equity_value_low"],
            "equity_value_mid": payload["equity_value"],
            "equity_value_high": payload["equity_value_high"],
            "step_11_asking_price": recommended_asking_price,
            "asset_based_details": payload["details"],
            "asset_based_evidence": True,
            "confidence_level": payload.get("confidence_level"),
            "per_share_value": None,
        }

    async def execute_real_estate_yield_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, object]]
    ) -> Dict[str, object]:
        """Income-capitalisation valuation for a property entity: net rent ÷
        cap-rate (engine ``real_estate_yield`` model), with the book NAV as a
        downside floor and an EV→equity net-debt bridge. Mirrors the
        asset-based contract (top-level ``equity_value_*`` + a details block) so
        the value flows through ValueExtractor / response_builder unchanged.
        """
        from src.domain.real_estate_yield import RealEstateYieldInputs, value_real_estate_by_yield

        self.logger.info("📊 Executing real-estate yield valuation")
        cy = request.current_year_data
        revenue = to_decimal(getattr(cy, "revenue", 0) or 0)
        ebitda = to_decimal(getattr(cy, "ebitda", 0) or 0)
        opex_raw = getattr(cy, "operating_expenses", None)
        cogs_raw = getattr(cy, "cogs", None)
        # Net operating income (NOI) is the income-capitalisation input.
        #   1. EBITDA — for a property entity EBITDA == rental income minus ALL
        #      property operating costs before D&A, i.e. NOI by construction
        #      (operating-only: no financial income, COGS included). Audit
        #      2026-06-10 F12: the old revenue−opex basis capitalised €8.007 of
        #      intercompany INTEREST at the property cap-rate (+€137K of fake
        #      vastgoed-marktwaarde) and skipped €1.732 of COGS, because the
        #      upstream `revenue` field carries 75x financial income;
        #   2. else revenue − COGS − operating_expenses when opex is supplied;
        #   3. else revenue as a last resort.
        if ebitda > 0:
            net_rent = ebitda
            net_rent_basis = "ebitda_noi"
        elif opex_raw is not None:
            net_rent = revenue - to_decimal(opex_raw) - to_decimal(cogs_raw or 0)
            net_rent_basis = "revenue_minus_cogs_opex"
        else:
            net_rent = revenue
            net_rent_basis = "revenue_gross"
        if net_rent <= 0:
            raise RealEstateYieldUnavailableError(
                "Net operating income (net rent) is not positive; income-"
                "capitalisation requires a positive sustainable rent. Falling back "
                "to the balance-sheet NAV."
            )
        total_assets = to_decimal(getattr(cy, "total_assets", 0) or 0)
        total_liabilities = to_decimal(getattr(cy, "total_liabilities", 0) or 0)
        nav_book = total_assets - total_liabilities
        net_debt = to_decimal(getattr(cy, "total_debt", 0) or 0) - to_decimal(
            getattr(cy, "cash", 0) or 0
        )

        # Audit 2026-06-10 F13: the NAV floor used to be applied at the EV
        # level inside the domain model — but nav_book (TA − TL) is an EQUITY
        # quantity that already contains the cash; flooring the property EV
        # with it and then re-bridging (eq = EV − net_debt, net debt negative
        # = net cash) double-counted the cash on every floored leg (+3,3% on
        # the conservative scenario) and printed entity book equity in a
        # "vastgoed-marktwaarde" column. The income EVs stay pure
        # income-capitalisation values; the floor is applied like-for-like at
        # the EQUITY level below.
        result = value_real_estate_by_yield(
            RealEstateYieldInputs(
                net_annual_rent=net_rent,
                property_type=_property_type_for(getattr(request, "industry", None)),
                nav_book_value=None,
            )
        )
        if not result.applicable or result.enterprise_value_mid is None:
            raise RealEstateYieldUnavailableError(
                result.skip_reason or "Real-estate yield model not applicable for this entity."
            )

        ev_low, ev_mid, ev_high = (
            result.enterprise_value_low,
            result.enterprise_value_mid,
            result.enterprise_value_high,
        )
        eq_low = (ev_low - net_debt).quantize(Decimal("0.01"))
        eq_mid = (ev_mid - net_debt).quantize(Decimal("0.01"))
        eq_high = (ev_high - net_debt).quantize(Decimal("0.01"))

        # Equity-level NAV floor: a buyer of the shares will not pay less than
        # the book equity of the entity (conservative downside anchor). Track
        # which legs the floor binds so the report can label it honestly.
        nav_equity_floor = nav_book if nav_book > 0 else None
        equity_floor_applied = {"low": False, "mid": False, "high": False}
        if nav_equity_floor is not None:
            if eq_low < nav_equity_floor:
                eq_low = nav_equity_floor
                equity_floor_applied["low"] = True
            if eq_mid < nav_equity_floor:
                eq_mid = nav_equity_floor
                equity_floor_applied["mid"] = True
            if eq_high < nav_equity_floor:
                eq_high = nav_equity_floor
                equity_floor_applied["high"] = True

        # Robustness guard: when in-place rent is far below what the property is
        # worth (e.g. owner-occupied, vacant, or below-market leases), the income
        # approach understates value and net debt can push the income-implied
        # equity to zero or below. A property entity must never headline a
        # non-positive equity off thin rent — defer to the balance-sheet NAV
        # (Asset-Based), which the dispatcher runs as the yield→NAV fallback. The
        # NAV-floored band still anchors the downside on the genuine-rent path.
        if eq_mid <= 0:
            raise RealEstateYieldUnavailableError(
                f"Income-capitalisation equity (€{eq_mid:,.0f}) is non-positive after the "
                f"net-debt bridge (EV €{ev_mid:,.0f} − net debt €{net_debt:,.0f}); in-place "
                "rent is too thin to anchor value. Deferring to the adjusted NAV."
            )

        confidence_level = str(result.confidence or "medium").upper()
        recommended_asking_price = (
            eq_mid
            * get_asking_price_markup(
                confidence_level.lower(),
                advisor_override_pct=getattr(request, "asking_price_buffer_pct", None),
            )
        ).quantize(Decimal("0.01"))

        return {
            "methodology": "REAL_ESTATE_YIELD",
            "methodology_label": "Vastgoed yield (income capitalisation)",
            "enterprise_value": ev_mid,
            "equity_value": eq_mid,
            "equity_value_low": eq_low,
            "equity_value_mid": eq_mid,
            "equity_value_high": eq_high,
            "step_11_asking_price": recommended_asking_price,
            "real_estate_yield_details": {
                "net_annual_rent": net_rent,
                "net_rent_basis": net_rent_basis,
                "cap_rate_low": result.cap_rate_low,
                "cap_rate_high": result.cap_rate_high,
                "property_type": result.property_type,
                "nav_book_value": nav_book,
                # Floor semantics (F13): applied at the EQUITY level (book
                # equity vs equity legs), never at the property-EV level.
                "nav_floor_level": "equity",
                "nav_floor_applied": any(equity_floor_applied.values()),
                "equity_floor_applied": equity_floor_applied,
                "enterprise_value_low": ev_low,
                "enterprise_value_mid": ev_mid,
                "enterprise_value_high": ev_high,
                "net_debt": net_debt,
                "rationale": result.rationale,
            },
            "real_estate_yield_evidence": True,
            "confidence_level": confidence_level,
            "per_share_value": None,
        }

    async def execute_market_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, object]]
    ) -> Dict[str, object]:
        """Execute market valuation (placeholder)"""
        self.logger.info("📊 Executing market valuation")
        from src.domain.range_calculator import ValuationRangeCalculator

        equity_value = request.current_year_data.revenue * Decimal("1.8")
        range_calc = ValuationRangeCalculator()
        valuation_range = range_calc.calculate_range(equity_value, "medium")

        return {
            "methodology": "Market",
            "enterprise_value": equity_value * Decimal("1.1"),
            "equity_value": equity_value,
            **valuation_range,
            "per_share_value": None,
        }

    async def execute_income_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, object]]
    ) -> Dict[str, object]:
        """Execute income valuation (placeholder)"""
        self.logger.info("📊 Executing income valuation")
        from src.domain.range_calculator import ValuationRangeCalculator

        net_income = getattr(request.current_year_data, "net_income", None)
        if net_income is None:
            net_income = request.current_year_data.ebitda * Decimal("0.6")
        equity_value = net_income * Decimal("8.0")

        range_calc = ValuationRangeCalculator()
        valuation_range = range_calc.calculate_range(equity_value, "medium")

        return {
            "methodology": "Income",
            "enterprise_value": equity_value * Decimal("1.1"),
            "equity_value": equity_value,
            **valuation_range,
            "per_share_value": None,
        }

    async def execute_cost_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, object]]
    ) -> Dict[str, object]:
        """Execute cost valuation (placeholder)"""
        self.logger.info("📊 Executing cost valuation")
        from src.domain.range_calculator import ValuationRangeCalculator

        total_assets = getattr(request.current_year_data, "total_assets", None)
        if total_assets is None:
            total_assets = request.current_year_data.revenue * Decimal("1.5")
        equity_value = total_assets * Decimal("0.9")

        range_calc = ValuationRangeCalculator()
        valuation_range = range_calc.calculate_range(equity_value, "low")

        return {
            "methodology": "Cost",
            "enterprise_value": equity_value,
            "equity_value": equity_value,
            **valuation_range,
            "per_share_value": None,
        }

    async def generate_valuation_report(
        self,
        valuation_id: str,
        request: ValuationRequest,
        detailed_results: Dict[str, object],
        context: Optional[Dict[str, object]],
    ) -> Optional[str]:
        """Generate valuation report URL (placeholder)"""
        self.logger.debug("📄 Generating valuation report")
        # Placeholder - return None for now
        return None
