from src.errors.error_types import MarketDataError
from src.utils.exceptions import CalculationError, DataQualityError, DCFCalculationError

"""
Discount Rate Calculator

This module handles WACC calculation and all discount rate components
for DCF valuation, including CAPM, cost of debt, and capital structure analysis.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from .dcf_types import (
    DEFAULT_DCF_CONFIG,
    CAPMComponents,
    DCFConfiguration,
    DebtStructure,
    FamaFrenchComponents,
    ForwardWaccEvidence,
    WACCComponents,
)
from .discount_rate_equity import (
    adjust_beta_for_leverage as calculate_adjusted_beta_for_leverage,
    calculate_cost_of_equity,
    calculate_fama_french_cost_of_equity,
    calculate_market_risk_premium,
    calculate_unlevered_beta,
    estimate_beta,
    estimate_hml_beta,
    estimate_risk_free_rate,
    estimate_smb_beta,
    validate_wacc_components,
)
from .market_defaults import calculate_company_specific_risk
from .models import FinancialData, IndustryBenchmarks, MarketContext

logger = get_logger(__name__)

FALLBACK_EQUITY_WEIGHT = Decimal("0.70")
FALLBACK_DEBT_WEIGHT = Decimal("0.30")
_RATE_PRECISION = 6


def _rate(value: Decimal) -> Decimal:
    """Commit a rate/weight without applying the currency rounding default."""

    return from_decimal(value, precision=_RATE_PRECISION)


@dataclass(frozen=True)
class CapitalStructureDecision:
    equity_weight: Decimal
    debt_weight: Decimal
    source: str
    fallback: bool
    confidence: str
    fallback_reason: str | None = None
    warnings: tuple[str, ...] = ()


class DiscountRateCalculator:
    """
    Discount rate calculation service for DCF valuation

    Handles:
    - WACC calculation (Weighted Average Cost of Capital)
    - Cost of equity using CAPM
    - Cost of debt calculation
    - Beta estimation and adjustments
    - Risk-free rate determination
    - Market risk premium calculation
    - Tax shield calculations
    """

    def __init__(
        self,
        config: Optional[DCFConfiguration] = None,
        force_modeled_capital_structure: bool = False,
    ):
        """Initialize the discount rate calculator

        `force_modeled_capital_structure` pins the WACC weighting to the
        disclosed 70/30 modeled default. Public Adaptive sets it so the applied
        structure matches the one its signed resolution already declared; every
        other caller keeps inferring the structure from the balance sheet.
        """
        self.logger = logger
        self.config = config or DEFAULT_DCF_CONFIG
        self.force_modeled_capital_structure = force_modeled_capital_structure

        self.logger.info("DiscountRateCalculator initialized")

    def calculate_wacc(
        self,
        financial_data: FinancialData,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
        size_premium: Optional[Decimal] = None,
        customer_concentration: Optional[Decimal] = None,
        industry: Optional[str] = None,
        has_audit: Optional[bool] = None,
        owner_dependency_score: Optional[Decimal] = None,
    ) -> WACCComponents:
        """
        Calculate Weighted Average Cost of Capital (WACC).

        WACC = (E/V) * Re + (D/V) * Rd * (1 - Tc)

        For SMEs a Duff & Phelps / Ibbotson size premium is added to the
        cost of equity before computing WACC, reflecting the empirically
        observed higher required return for smaller companies.

        Args:
            financial_data: Company financial data
            market_context: Market context
            industry_benchmarks: Industry benchmarks
            size_premium: Optional SME size premium (e.g. Decimal("0.06") = 6 %)
            customer_concentration: Top-customer concentration (0-1)
            industry: Industry / NACE category
            has_audit: Whether financials are audited
            owner_dependency_score: Owner dependency risk score (0-1)

        Returns:
            WACCComponents with all calculation details
        """
        try:
            self.logger.info("Calculating WACC")

            size_premium_decimal = (
                to_decimal(size_premium) if size_premium is not None else Decimal("0")
            )

            # Calculate cost of equity using CAPM
            capm_components = self._calculate_cost_of_equity(
                market_context,
                industry_benchmarks,
                financial_data,
            )

            # Resolve the capital structure once for every WACC component.
            # In particular, incomplete leverage evidence must not select the
            # canonical 70/30 weighting while the cost-of-debt spread silently
            # prices a contradictory 100% debt ratio.
            current_year = financial_data.current_year
            raw_total_debt = current_year.total_debt
            raw_total_equity = current_year.total_equity
            total_debt = to_decimal(raw_total_debt or 0)
            total_equity = to_decimal(raw_total_equity or 0)
            capital_structure = self._resolve_capital_structure(
                raw_total_debt=raw_total_debt,
                raw_total_equity=raw_total_equity,
                total_debt=total_debt,
                total_equity=total_equity,
            )

            # Calculate cost of debt from the same observed/fallback leverage
            # decision used by the WACC weighting below.
            debt_structure = self._calculate_cost_of_debt(
                financial_data,
                market_context,
                industry_benchmarks,
                capital_structure=capital_structure,
            )

            company_specific_risk_decimal, company_specific_breakdown = (
                calculate_company_specific_risk(
                    is_profitable=to_decimal(financial_data.current_year.ebitda or 0)
                    >= Decimal("0"),
                    has_audit=has_audit,
                    customer_concentration_pct=customer_concentration,
                    industry=industry or getattr(industry_benchmarks, "industry", None),
                    owner_dependency_score=owner_dependency_score,
                )
            )

            # Apply size premium and company-specific risk to cost of equity
            cost_of_equity_decimal = (
                to_decimal(capm_components.cost_of_equity)
                + size_premium_decimal
                + company_specific_risk_decimal
            )

            if size_premium_decimal > 0 or company_specific_risk_decimal > 0:
                self.logger.info(
                    "Applied SME risk buildup to cost of equity",
                    extra={
                        "capm_cost_of_equity": f"{capm_components.cost_of_equity:.2%}",
                        "size_premium": f"{size_premium_decimal:.2%}",
                        "company_specific_risk": f"{company_specific_risk_decimal:.2%}",
                        "adjusted_cost_of_equity": f"{cost_of_equity_decimal:.2%}",
                        "risk_breakdown": company_specific_breakdown,
                        "source": "Duff & Phelps (2024) / Ibbotson SBBI / company-specific buildup",
                    },
                )

            if capital_structure.fallback:
                # This is an expected, explicitly disclosed public-data path,
                # not an operator incident. The evidence envelope and warning
                # code below remain authoritative; keep per-calculation logging
                # at debug level so large public batches do not amplify logs.
                self.logger.debug(
                    "WACC capital structure fallback applied",
                    extra={
                        "source": capital_structure.source,
                        "fallback_reason": capital_structure.fallback_reason,
                        "equity_weight": str(capital_structure.equity_weight),
                        "debt_weight": str(capital_structure.debt_weight),
                    },
                )

            # If no debt, WACC = Cost of Equity (incl. size premium), clamped to config bounds
            if capital_structure.debt_weight == 0:
                min_wacc = to_decimal(self.config.wacc_range[0])
                max_wacc = to_decimal(self.config.wacc_range[1])
                clamped_coe = max(min_wacc, min(cost_of_equity_decimal, max_wacc))
                wacc_components = WACCComponents(
                    cost_of_equity=_rate(cost_of_equity_decimal),
                    cost_of_debt=debt_structure.cost_of_debt,
                    equity_weight=Decimal("1.0"),
                    debt_weight=Decimal("0.0"),
                    tax_rate=_rate(to_decimal(industry_benchmarks.avg_tax_rate)),
                    wacc=_rate(clamped_coe),
                    beta=capm_components.beta,
                    risk_free_rate=capm_components.risk_free_rate,
                    market_risk_premium=capm_components.market_risk_premium,
                    debt_yield=debt_structure.debt_yield,
                    tax_shield=Decimal("0.0"),
                    size_premium=_rate(size_premium_decimal),
                    company_specific_risk=_rate(company_specific_risk_decimal),
                    evidence=self._build_forward_wacc_evidence(
                        capital_structure=capital_structure,
                        observed_total_debt=total_debt,
                        observed_total_equity=total_equity,
                        capm_components=capm_components,
                        size_premium=size_premium_decimal,
                        company_specific_risk=company_specific_risk_decimal,
                    ),
                )
            else:
                equity_weight_decimal = capital_structure.equity_weight
                debt_weight_decimal = capital_structure.debt_weight

                # Calculate tax shield
                tax_rate = to_decimal(industry_benchmarks.avg_tax_rate)
                cost_of_debt_decimal = to_decimal(debt_structure.cost_of_debt)
                tax_shield_decimal = debt_weight_decimal * cost_of_debt_decimal * tax_rate

                # WACC formula (cost_of_equity already includes size premium)
                wacc = (
                    equity_weight_decimal * cost_of_equity_decimal
                    + debt_weight_decimal * cost_of_debt_decimal * (Decimal("1") - tax_rate)
                )

                # Sanity check: WACC should be within reasonable bounds
                min_wacc = to_decimal(self.config.wacc_range[0])
                max_wacc = to_decimal(self.config.wacc_range[1])
                wacc = max(min_wacc, min(wacc, max_wacc))

                wacc_components = WACCComponents(
                    cost_of_equity=_rate(cost_of_equity_decimal),
                    cost_of_debt=debt_structure.cost_of_debt,
                    equity_weight=_rate(equity_weight_decimal),
                    debt_weight=_rate(debt_weight_decimal),
                    tax_rate=_rate(tax_rate),
                    wacc=_rate(wacc),
                    beta=capm_components.beta,
                    risk_free_rate=capm_components.risk_free_rate,
                    market_risk_premium=capm_components.market_risk_premium,
                    debt_yield=debt_structure.debt_yield,
                    tax_shield=_rate(tax_shield_decimal),
                    size_premium=_rate(size_premium_decimal),
                    company_specific_risk=_rate(company_specific_risk_decimal),
                    evidence=self._build_forward_wacc_evidence(
                        capital_structure=capital_structure,
                        observed_total_debt=total_debt,
                        observed_total_equity=total_equity,
                        capm_components=capm_components,
                        size_premium=size_premium_decimal,
                        company_specific_risk=company_specific_risk_decimal,
                    ),
                )

            self.logger.info(
                "WACC calculated",
                wacc=f"{wacc_components.wacc:.2%}",
                cost_of_equity=f"{wacc_components.cost_of_equity:.2%}",
                cost_of_debt=f"{wacc_components.cost_of_debt:.2%}",
                equity_weight=f"{wacc_components.equity_weight:.1%}",
                debt_weight=f"{wacc_components.debt_weight:.1%}",
                size_premium=f"{size_premium_decimal:.2%}" if size_premium_decimal else "N/A",
                company_specific_risk=(
                    f"{company_specific_risk_decimal:.2%}"
                    if company_specific_risk_decimal
                    else "N/A"
                ),
            )

            return wacc_components

        except DCFCalculationError:
            raise
        except (CalculationError, MarketDataError, DataQualityError):
            raise
        except (ValueError, TypeError, ZeroDivisionError, AttributeError) as e:
            self.logger.error(
                f"WACC calculation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise DCFCalculationError(
                f"Failed to calculate WACC: {e}",
                step="wacc_calculation",
                calculation_type="WACC Calculation",
                context={
                    "company": getattr(financial_data, "company_name", None),
                    "error_type": type(e).__name__,
                },
            ) from e

    def _resolve_capital_structure(
        self,
        *,
        raw_total_debt: object,
        raw_total_equity: object,
        total_debt: Decimal,
        total_equity: Decimal,
    ) -> CapitalStructureDecision:
        # Public Adaptive declares its capital structure in the signed modeled-DCF
        # resolution BEFORE this runs, and declares the 70/30 modeled default
        # whenever the public inputs lack a source-bound debt leg — which is every
        # abbreviated filing, since those never disclose debt. If the calculator
        # then infers its own structure from whatever debt value happens to reach
        # it, policy and evidence disagree and `_modeled_dcf_wacc_reconciles`
        # fails closed on the weight comparison. Honour the declaration instead:
        # for a public modeled run the standard structure IS the disclosed answer.
        if raw_total_debt is None or raw_total_equity is None:
            # Already the disclosed default, and for a more specific reason.
            return self._fallback_capital_structure("missing_balance_sheet_leverage")
        if getattr(self, "force_modeled_capital_structure", False):
            return self._fallback_capital_structure("public_modeled_default_capital_structure")
        if total_debt < 0 or total_equity < 0:
            return self._fallback_capital_structure("invalid_negative_balance_sheet_leverage")
        if total_debt == 0 and total_equity > 0:
            return CapitalStructureDecision(
                equity_weight=Decimal("1.0"),
                debt_weight=Decimal("0.0"),
                source="observed_no_debt_balance_sheet",
                fallback=False,
                confidence="high",
            )
        total_value = total_equity + total_debt
        if total_debt > 0 and total_equity > 0 and total_value > 0:
            equity_weight = max(Decimal("0"), min(total_equity / total_value, Decimal("1")))
            return CapitalStructureDecision(
                equity_weight=equity_weight,
                debt_weight=Decimal("1") - equity_weight,
                source="observed_balance_sheet",
                fallback=False,
                confidence="high",
            )
        return self._fallback_capital_structure("unusable_balance_sheet_leverage")

    def _fallback_capital_structure(self, reason: str) -> CapitalStructureDecision:
        return CapitalStructureDecision(
            equity_weight=FALLBACK_EQUITY_WEIGHT,
            debt_weight=FALLBACK_DEBT_WEIGHT,
            source="fallback_70_30_equity_debt",
            fallback=True,
            confidence="low",
            fallback_reason=reason,
            warnings=("capital_structure_fallback_70_30",),
        )

    def _build_forward_wacc_evidence(
        self,
        *,
        capital_structure: CapitalStructureDecision,
        observed_total_debt: Decimal,
        observed_total_equity: Decimal,
        capm_components: CAPMComponents,
        size_premium: Decimal,
        company_specific_risk: Decimal,
    ) -> ForwardWaccEvidence:
        return ForwardWaccEvidence(
            capital_structure_source=capital_structure.source,
            capital_structure_fallback=capital_structure.fallback,
            confidence=capital_structure.confidence,
            equity_weight=_rate(capital_structure.equity_weight),
            debt_weight=_rate(capital_structure.debt_weight),
            observed_total_debt=from_decimal(observed_total_debt),
            observed_total_equity=from_decimal(observed_total_equity),
            fallback_reason=capital_structure.fallback_reason,
            beta_source=capm_components.beta_source,
            size_premium_source=("advisor_or_titan_size_premium" if size_premium > 0 else None),
            company_specific_risk_source=(
                "company_specific_risk_buildup" if company_specific_risk > 0 else None
            ),
            warnings=capital_structure.warnings,
        )

    def _calculate_cost_of_equity(
        self,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
        financial_data: Optional[FinancialData] = None,
    ) -> CAPMComponents:
        return calculate_cost_of_equity(
            config=self.config,
            market_context=market_context,
            industry_benchmarks=industry_benchmarks,
            financial_data=financial_data,
            estimate_beta=self._estimate_beta,
            calculate_fama_french_cost_of_equity=self._calculate_fama_french_cost_of_equity,
            logger=self.logger,
        )

    def _calculate_fama_french_cost_of_equity(
        self, market_context: MarketContext, industry_benchmarks: IndustryBenchmarks
    ) -> FamaFrenchComponents:
        return calculate_fama_french_cost_of_equity(
            config=self.config,
            market_context=market_context,
            industry_benchmarks=industry_benchmarks,
            estimate_beta=self._estimate_beta,
            estimate_smb_beta=self._estimate_smb_beta,
            estimate_hml_beta=self._estimate_hml_beta,
            logger=self.logger,
        )

    def _estimate_smb_beta(self, industry_benchmarks: IndustryBenchmarks) -> Decimal:
        return estimate_smb_beta(industry_benchmarks)

    def _estimate_hml_beta(self, industry_benchmarks: IndustryBenchmarks) -> Decimal:
        return estimate_hml_beta(industry_benchmarks)

    def _estimate_beta(
        self,
        industry_benchmarks: IndustryBenchmarks,
        financial_data: Optional[FinancialData] = None,
    ) -> Decimal:
        return estimate_beta(
            config=self.config,
            industry_benchmarks=industry_benchmarks,
            financial_data=financial_data,
            adjust_beta_for_leverage=self.adjust_beta_for_leverage,
            logger=self.logger,
        )

    def _calculate_cost_of_debt(
        self,
        financial_data: FinancialData,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
        *,
        capital_structure: CapitalStructureDecision | None = None,
    ) -> DebtStructure:
        """Calculate cost of debt and debt structure"""
        try:
            current_year = financial_data.current_year
            total_debt = to_decimal(current_year.total_debt or 0)
            short_term_debt = to_decimal(current_year.short_term_debt or 0)
            # `long_term_debt` is not a field on the canonical YearData
            # schema (only `short_term_debt` + `total_debt` are modelled —
            # see domain/models.py:441-442). The previous direct attribute
            # access threw `AttributeError` on every DCF run, was caught by
            # the broad except below, and silently flipped the engine to a
            # 5% fixed cost-of-debt fallback. Derive it instead so the
            # WACC reflects the actual debt mix when provided, and falls
            # back to zero only when no balance data is present.
            ltd_attr = getattr(current_year, "long_term_debt", None)
            if ltd_attr is not None:
                long_term_debt = to_decimal(ltd_attr or 0)
            else:
                long_term_debt = max(total_debt - short_term_debt, Decimal("0"))

            # Estimate debt yield based on market conditions
            base_rate = to_decimal(
                getattr(market_context, "risk_free_rate", None)
                or market_context.government_bond_yield
            )

            # Calculate leverage ratio
            total_equity = to_decimal(current_year.total_equity or 0)
            total_capital = total_equity + total_debt
            leverage_ratio = (
                capital_structure.debt_weight
                if capital_structure is not None
                else (total_debt / total_capital if total_capital > 0 else Decimal("0"))
            )

            if leverage_ratio > Decimal("0.6"):
                credit_spread = Decimal("0.04")
            elif leverage_ratio > Decimal("0.3"):
                credit_spread = Decimal("0.03")
            else:
                credit_spread = Decimal("0.02")

            debt_yield = base_rate + credit_spread

            cost_of_debt = max(debt_yield, Decimal("0.02"))

            # Tax shield
            tax_rate = to_decimal(industry_benchmarks.avg_tax_rate)
            tax_shield = cost_of_debt * tax_rate

            return DebtStructure(
                total_debt=from_decimal(total_debt),
                short_term_debt=from_decimal(short_term_debt),
                long_term_debt=from_decimal(long_term_debt),
                debt_yield=_rate(debt_yield),
                credit_rating=None,  # Would be determined by credit analysis
                cost_of_debt=_rate(cost_of_debt),
                tax_shield=_rate(tax_shield),
                leverage_ratio=_rate(leverage_ratio),
            )

        except (ValueError, TypeError, ZeroDivisionError, AttributeError) as e:
            self.logger.error(
                f"Cost of debt calculation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            # Return default debt structure rather than raising, as this is a fallback
            return DebtStructure(
                total_debt=0,
                short_term_debt=0,
                long_term_debt=0,
                debt_yield=Decimal("0.05"),
                credit_rating=None,
                cost_of_debt=Decimal("0.05"),
                tax_shield=Decimal("0.0"),
                leverage_ratio=Decimal("0.0"),
            )
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error in cost of debt calculation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            return DebtStructure(
                total_debt=0,
                short_term_debt=0,
                long_term_debt=0,
                debt_yield=Decimal("0.05"),
                credit_rating=None,
                cost_of_debt=Decimal("0.05"),
                tax_shield=Decimal("0.0"),
                leverage_ratio=Decimal("0.0"),
            )

    def adjust_beta_for_leverage(
        self, unlevered_beta: Decimal, debt_to_equity: Decimal, tax_rate: Decimal
    ) -> Decimal:
        return calculate_adjusted_beta_for_leverage(
            unlevered_beta=unlevered_beta,
            debt_to_equity=debt_to_equity,
            tax_rate=tax_rate,
            logger=self.logger,
        )

    def calculate_unlevered_beta(
        self, levered_beta: Decimal, debt_to_equity: Decimal, tax_rate: Decimal
    ) -> Decimal:
        return calculate_unlevered_beta(
            levered_beta=levered_beta,
            debt_to_equity=debt_to_equity,
            tax_rate=tax_rate,
            logger=self.logger,
        )

    def estimate_risk_free_rate(
        self, market_context: MarketContext, maturity: str = "10_year"
    ) -> Decimal:
        return estimate_risk_free_rate(
            market_context=market_context,
            maturity=maturity,
            logger=self.logger,
        )

    def calculate_market_risk_premium(
        self, market_context: MarketContext, historical_period: str = "long_term"
    ) -> Decimal:
        return calculate_market_risk_premium(
            market_context=market_context,
            historical_period=historical_period,
            logger=self.logger,
        )

    def validate_wacc_components(self, wacc_components: WACCComponents) -> bool:
        return validate_wacc_components(
            config=self.config,
            wacc_components=wacc_components,
            logger=self.logger,
        )
