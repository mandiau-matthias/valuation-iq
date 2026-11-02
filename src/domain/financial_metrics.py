"""
Financial Metrics Calculator.

Calculates comprehensive financial ratios and KPIs for business valuation,
including profitability, liquidity, leverage, efficiency, and risk metrics.

Based on:
- CFA Institute financial analysis standards
- Traditional financial ratio analysis
- Altman Z-Score for bankruptcy prediction
"""

from decimal import Decimal
from typing import List, Optional

from src.domain.models import FinancialData, FinancialMetrics, YearData
from src.domain.revenue_growth import revenue_growth
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FinancialMetricsCalculator:
    """
    Calculate comprehensive financial metrics from business financial data.

    This calculator implements industry-standard financial ratio analysis
    used by Big 4 advisory firms and institutional investors.
    """

    def __init__(self, financial_data: FinancialData):
        """
        Initialize calculator with business financial data.

        Args:
            financial_data: Complete financial data for the business
        """
        self.financial_data = financial_data
        self.current_year = financial_data.current_year
        self.historical_years = sorted(
            (
                year
                for year in financial_data.historical_years
                if not getattr(year, "is_forecast", False)
            ),
            key=lambda year: getattr(year, "year", 0),
        )

    def calculate_all_metrics(self) -> FinancialMetrics:
        """
        Calculate all financial metrics and ratios.

        Returns:
            FinancialMetrics object with all calculated ratios
        """
        logger.info(
            "Calculating financial metrics",
            company=self.financial_data.company_name,
            year=self.current_year.year,
        )

        ebitda_margin_decimal = self._calculate_ebitda_margin()
        revenue_growth_decimal = self._calculate_revenue_growth()

        metrics = FinancialMetrics(
            # Profitability ratios
            gross_margin=self._calculate_gross_margin(),
            ebitda_margin=from_decimal(ebitda_margin_decimal),
            ebit_margin=self._calculate_ebit_margin(),
            net_margin=self._calculate_net_margin(),
            return_on_assets=self._calculate_roa(),
            return_on_equity=self._calculate_roe(),
            # Liquidity ratios
            current_ratio=self._calculate_current_ratio(),
            quick_ratio=self._calculate_quick_ratio(),
            cash_ratio=self._calculate_cash_ratio(),
            # Leverage ratios
            debt_to_equity=self._calculate_debt_to_equity(),
            debt_to_assets=self._calculate_debt_to_assets(),
            interest_coverage=self._calculate_interest_coverage(),
            # Efficiency ratios
            asset_turnover=self._calculate_asset_turnover(),
            receivables_turnover=self._calculate_receivables_turnover(),
            inventory_turnover=self._calculate_inventory_turnover(),
            # Growth metrics
            revenue_growth=from_decimal(revenue_growth_decimal),
            revenue_cagr_3y=self._calculate_revenue_cagr(),
            ebitda_growth=self._calculate_ebitda_growth(),
            # Risk metrics
            altman_z_score=self._calculate_altman_z_score(),
            financial_health_score=self._calculate_financial_health_score(),
            # Owner concentration metrics
            owner_fte_ratio=self._calculate_owner_fte_ratio(),
        )

        logger.info(
            "Financial metrics calculated",
            ebitda_margin=f"{metrics.ebitda_margin:.2%}",
            revenue_growth=f"{metrics.revenue_growth:.2%}",
            health_score=metrics.financial_health_score,
        )

        return metrics

    # === PROFITABILITY RATIOS ===

    def _calculate_gross_margin(self) -> Optional[Decimal]:
        """Calculate gross profit margin."""
        if self.current_year.gross_profit is None:
            return None
        gross_profit_decimal = to_decimal(self.current_year.gross_profit)
        revenue_decimal = to_decimal(self.current_year.revenue)
        if revenue_decimal == 0:
            return None
        return from_decimal(bank_round(gross_profit_decimal / revenue_decimal, 4))

    def _calculate_ebitda_margin(self) -> Decimal:
        """Calculate EBITDA margin."""
        ebitda_decimal = to_decimal(self.current_year.ebitda)
        revenue_decimal = to_decimal(self.current_year.revenue)
        if revenue_decimal == 0:
            return Decimal("0.0")
        return bank_round(ebitda_decimal / revenue_decimal, 4)

    def _calculate_ebit_margin(self) -> Optional[Decimal]:
        """Calculate EBIT margin."""
        if self.current_year.ebit is None:
            return None
        ebit_decimal = to_decimal(self.current_year.ebit)
        revenue_decimal = to_decimal(self.current_year.revenue)
        if revenue_decimal == 0:
            return None
        return from_decimal(bank_round(ebit_decimal / revenue_decimal, 4))

    def _calculate_net_margin(self) -> Optional[Decimal]:
        """Calculate net profit margin."""
        if self.current_year.net_income is None:
            return None
        net_income_decimal = to_decimal(self.current_year.net_income)
        revenue_decimal = to_decimal(self.current_year.revenue)
        if revenue_decimal == 0:
            return None
        return from_decimal(bank_round(net_income_decimal / revenue_decimal, 4))

    def _calculate_roa(self) -> Optional[Decimal]:
        """
        Calculate Return on Assets (ROA).
        ROA = Net Income / Total Assets
        """
        if self.current_year.net_income is None or self.current_year.total_assets is None:
            return None
        net_income_decimal = to_decimal(self.current_year.net_income)
        total_assets_decimal = to_decimal(self.current_year.total_assets)
        if total_assets_decimal == 0:
            return None
        return from_decimal(bank_round(net_income_decimal / total_assets_decimal, 4))

    def _calculate_roe(self) -> Optional[Decimal]:
        """
        Calculate Return on Equity (ROE).
        ROE = Net Income / Total Equity
        """
        if self.current_year.net_income is None or self.current_year.total_equity is None:
            return None
        net_income_decimal = to_decimal(self.current_year.net_income)
        total_equity_decimal = to_decimal(self.current_year.total_equity)
        if total_equity_decimal <= 0:
            return None
        return from_decimal(bank_round(net_income_decimal / total_equity_decimal, 4))

    # === LIQUIDITY RATIOS ===

    def _calculate_current_ratio(self) -> Optional[Decimal]:
        """
        Calculate Current Ratio.
        Current Ratio = Current Assets / Current Liabilities
        """
        if (
            self.current_year.current_assets is None
            or self.current_year.current_liabilities is None
        ):
            return None
        current_assets_decimal = to_decimal(self.current_year.current_assets)
        current_liabilities_decimal = to_decimal(self.current_year.current_liabilities)
        if current_liabilities_decimal <= 0:
            return None
        return from_decimal(bank_round(current_assets_decimal / current_liabilities_decimal, 4))

    def _calculate_quick_ratio(self) -> Optional[Decimal]:
        """
        Calculate Quick Ratio (Acid Test).
        Quick Ratio = (Current Assets - Inventory) / Current Liabilities
        """
        if (
            self.current_year.current_assets is None
            or self.current_year.current_liabilities is None
        ):
            return None
        current_assets_decimal = to_decimal(self.current_year.current_assets)
        current_liabilities_decimal = to_decimal(self.current_year.current_liabilities)
        if current_liabilities_decimal <= 0:
            return None
        inventory_decimal = to_decimal(self.current_year.inventory or 0)
        quick_assets = current_assets_decimal - inventory_decimal
        return from_decimal(bank_round(quick_assets / current_liabilities_decimal, 4))

    def _calculate_cash_ratio(self) -> Optional[Decimal]:
        """
        Calculate Cash Ratio.
        Cash Ratio = Cash / Current Liabilities
        """
        if self.current_year.cash is None or self.current_year.current_liabilities is None:
            return None
        cash_decimal = to_decimal(self.current_year.cash)
        current_liabilities_decimal = to_decimal(self.current_year.current_liabilities)
        if current_liabilities_decimal <= 0:
            return None
        return from_decimal(bank_round(cash_decimal / current_liabilities_decimal, 4))

    # === LEVERAGE RATIOS ===

    def _calculate_debt_to_equity(self) -> Optional[Decimal]:
        """
        Calculate Debt-to-Equity Ratio.
        D/E = Total Debt / Total Equity
        """
        if self.current_year.total_debt is None or self.current_year.total_equity is None:
            return None
        total_debt_decimal = to_decimal(self.current_year.total_debt)
        total_equity_decimal = to_decimal(self.current_year.total_equity)
        if total_equity_decimal <= 0:
            return None
        return from_decimal(bank_round(total_debt_decimal / total_equity_decimal, 4))

    def _calculate_debt_to_assets(self) -> Optional[Decimal]:
        """
        Calculate Debt-to-Assets Ratio.
        D/A = Total Debt / Total Assets
        """
        if self.current_year.total_debt is None or self.current_year.total_assets is None:
            return None
        total_debt_decimal = to_decimal(self.current_year.total_debt)
        total_assets_decimal = to_decimal(self.current_year.total_assets)
        if total_assets_decimal <= 0:
            return None
        return from_decimal(bank_round(total_debt_decimal / total_assets_decimal, 4))

    def _calculate_interest_coverage(self) -> Optional[Decimal]:
        """
        Calculate Interest Coverage Ratio.
        Interest Coverage = EBIT / Interest Expense
        """
        if self.current_year.ebit is None or self.current_year.interest_expense is None:
            return None
        ebit_decimal = to_decimal(self.current_year.ebit)
        interest_expense_decimal = to_decimal(self.current_year.interest_expense)
        if interest_expense_decimal <= 0:
            return None
        return from_decimal(bank_round(ebit_decimal / interest_expense_decimal, 4))

    # === EFFICIENCY RATIOS ===

    def _calculate_asset_turnover(self) -> Optional[Decimal]:
        """
        Calculate Asset Turnover Ratio.
        Asset Turnover = Revenue / Total Assets
        """
        if self.current_year.total_assets is None:
            return None
        revenue_decimal = to_decimal(self.current_year.revenue)
        total_assets_decimal = to_decimal(self.current_year.total_assets)
        if total_assets_decimal <= 0:
            return None
        return from_decimal(bank_round(revenue_decimal / total_assets_decimal, 4))

    def _calculate_receivables_turnover(self) -> Optional[Decimal]:
        """
        Calculate Receivables Turnover (days).
        Receivables Turnover = (Accounts Receivable / Revenue) * 365
        """
        if self.current_year.accounts_receivable is None:
            return None
        accounts_receivable_decimal = to_decimal(self.current_year.accounts_receivable)
        revenue_decimal = to_decimal(self.current_year.revenue)
        if revenue_decimal == 0:
            return None
        return from_decimal(
            bank_round((accounts_receivable_decimal / revenue_decimal) * Decimal("365"), 2)
        )

    def _calculate_inventory_turnover(self) -> Optional[Decimal]:
        """
        Calculate Inventory Turnover (days).
        Inventory Turnover = (Inventory / COGS) * 365
        """
        if self.current_year.inventory is None or self.current_year.cogs is None:
            return None
        inventory_decimal = to_decimal(self.current_year.inventory)
        cogs_decimal = to_decimal(self.current_year.cogs)
        if cogs_decimal <= 0:
            return None
        return from_decimal(bank_round((inventory_decimal / cogs_decimal) * Decimal("365"), 2))

    # === GROWTH METRICS ===

    def _calculate_revenue_growth(self) -> Decimal:
        """Annualized revenue change over the latest comparable fiscal endpoints."""
        growth = revenue_growth(self.current_year, self.historical_years).rate
        return bank_round(growth, 4) if growth is not None else Decimal("0")

    def _calculate_revenue_cagr(self) -> Optional[Decimal]:
        """Exactly three elapsed fiscal years, as the public metric name promises."""
        growth = revenue_growth(self.current_year, self.historical_years, horizon="three_year").rate
        return bank_round(growth, 4) if growth is not None else None

    def _calculate_ebitda_growth(self) -> Optional[Decimal]:
        """Calculate year-over-year EBITDA growth."""
        if len(self.historical_years) == 0:
            return None

        previous_year = self.historical_years[-1]
        current_ebitda_decimal = to_decimal(self.current_year.ebitda)
        previous_ebitda_decimal = to_decimal(previous_year.ebitda)
        if previous_ebitda_decimal == 0:
            return None

        growth = (current_ebitda_decimal - previous_ebitda_decimal) / abs(previous_ebitda_decimal)
        return from_decimal(bank_round(growth, 4))

    # === RISK METRICS ===

    def _calculate_altman_z_score(self) -> Optional[Decimal]:
        """
        Calculate Altman Z-Score for bankruptcy prediction.

        Z-Score = Decimal('1.2')*X1 + Decimal('1.4')*X2 + Decimal('3.3')*X3 + Decimal('0.6')*X4 + Decimal('1.0')*X5

        Where:
        X1 = Working Capital / Total Assets
        X2 = Retained Earnings / Total Assets
        X3 = EBIT / Total Assets
        X4 = Market Value of Equity / Total Liabilities (use book value for private companies)
        X5 = Revenue / Total Assets

        Interpretation:
        - Z > 2.99: Safe zone (low bankruptcy risk)
        - Decimal('1.81') < Z < 2.99: Grey zone (moderate risk)
        - Z < 1.81: Distress zone (high bankruptcy risk)
        """
        if (
            self.current_year.total_assets is None
            or self.current_year.total_assets <= 0
            or self.current_year.total_liabilities is None
            or self.current_year.total_equity is None
        ):
            return None

        total_assets_decimal = to_decimal(self.current_year.total_assets)
        total_equity_decimal = to_decimal(self.current_year.total_equity)
        total_liabilities_decimal = to_decimal(self.current_year.total_liabilities)

        # X1: Working Capital / Total Assets
        if (
            self.current_year.current_assets is not None
            and self.current_year.current_liabilities is not None
        ):
            current_assets_decimal = to_decimal(self.current_year.current_assets)
            current_liabilities_decimal = to_decimal(self.current_year.current_liabilities)
            working_capital = current_assets_decimal - current_liabilities_decimal
            x1 = working_capital / total_assets_decimal
        else:
            x1 = Decimal("0.0")

        # X2: Retained Earnings / Total Assets (approximate with total equity)
        x2 = total_equity_decimal / total_assets_decimal

        # X3: EBIT / Total Assets
        if self.current_year.ebit is not None:
            ebit_decimal = to_decimal(self.current_year.ebit)
            x3 = ebit_decimal / total_assets_decimal
        else:
            # Approximate EBIT with EBITDA
            ebitda_decimal = to_decimal(self.current_year.ebitda)
            x3 = ebitda_decimal / total_assets_decimal

        # X4: Book Value of Equity / Total Liabilities (for private companies)
        if total_liabilities_decimal > 0:
            x4 = total_equity_decimal / total_liabilities_decimal
        else:
            x4 = Decimal("10.0")  # Very high if no liabilities

        # X5: Revenue / Total Assets
        revenue_decimal = to_decimal(self.current_year.revenue)
        x5 = revenue_decimal / total_assets_decimal

        # Calculate Z-Score
        z_score = (
            Decimal("1.2") * x1
            + Decimal("1.4") * x2
            + Decimal("3.3") * x3
            + Decimal("0.6") * x4
            + Decimal("1.0") * x5
        )

        logger.debug(
            "Altman Z-Score calculated",
            z_score=f"{from_decimal(bank_round(z_score, 2)):.2f}",
            x1=f"{from_decimal(bank_round(x1, 3)):.3f}",
            x2=f"{from_decimal(bank_round(x2, 3)):.3f}",
            x3=f"{from_decimal(bank_round(x3, 3)):.3f}",
            x4=f"{from_decimal(bank_round(x4, 3)):.3f}",
            x5=f"{from_decimal(bank_round(x5, 3)):.3f}",
        )

        return from_decimal(bank_round(z_score, 2))

    def _calculate_financial_health_score(self) -> int:
        """
        Calculate overall financial health score (0-100).

        This composite score considers:
        - Profitability (30%)
        - Liquidity (20%)
        - Leverage (20%)
        - Growth (20%)
        - Altman Z-Score (10%)
        """
        score = 0

        # Profitability score (0-30 points)
        ebitda_margin_decimal = self._calculate_ebitda_margin()
        if ebitda_margin_decimal > Decimal("0.30"):
            score += 30
        elif ebitda_margin_decimal > Decimal("0.20"):
            score += 25
        elif ebitda_margin_decimal > Decimal("0.10"):
            score += 20
        elif ebitda_margin_decimal > Decimal("0.05"):
            score += 15
        elif ebitda_margin_decimal > Decimal("0"):
            score += 10
        else:
            score += 0  # Negative EBITDA

        # Liquidity score (0-20 points)
        current_ratio = self._calculate_current_ratio()
        if current_ratio is not None:
            current_ratio_decimal = to_decimal(current_ratio)
            if current_ratio_decimal > Decimal("2.0"):
                score += 20
            elif current_ratio_decimal > Decimal("1.5"):
                score += 15
            elif current_ratio_decimal > Decimal("1.0"):
                score += 10
            else:
                score += 5
        else:
            score += 10  # Neutral if data unavailable

        # Leverage score (0-20 points)
        debt_to_equity = self._calculate_debt_to_equity()
        if debt_to_equity is not None:
            debt_to_equity_decimal = to_decimal(debt_to_equity)
            if debt_to_equity_decimal < Decimal("0.5"):
                score += 20
            elif debt_to_equity_decimal < Decimal("1.0"):
                score += 15
            elif debt_to_equity_decimal < Decimal("2.0"):
                score += 10
            else:
                score += 5
        else:
            score += 10  # Neutral if data unavailable

        # Growth score (0-20 points)
        revenue_growth_decimal = self._calculate_revenue_growth()
        if revenue_growth_decimal > Decimal("0.30"):
            score += 20
        elif revenue_growth_decimal > Decimal("0.20"):
            score += 17
        elif revenue_growth_decimal > Decimal("0.10"):
            score += 14
        elif revenue_growth_decimal > Decimal("0.05"):
            score += 11
        elif revenue_growth_decimal > Decimal("0"):
            score += 8
        else:
            score += 3  # Negative growth

        # Altman Z-Score (0-10 points)
        z_score = self._calculate_altman_z_score()
        if z_score is not None:
            z_score_decimal = to_decimal(z_score)
            if z_score_decimal > Decimal("2.99"):
                score += 10
            elif z_score_decimal > Decimal("1.81"):
                score += 6
            else:
                score += 2
        else:
            score += 5  # Neutral if data unavailable

        logger.info(
            "Financial health score calculated",
            score=score,
            ebitda_margin=f"{from_decimal(ebitda_margin_decimal):.2%}",
            revenue_growth=f"{from_decimal(revenue_growth_decimal):.2%}",
        )

        return min(score, 100)  # Cap at 100

    # === OWNER CONCENTRATION METRICS ===

    def _calculate_owner_fte_ratio(self) -> Optional[Decimal]:
        """
        Calculate owner to FTE ratio.

        This metric quantifies management concentration risk by measuring
        the ratio of operational owners to total employees.

        Formula: owner_fte_ratio = number_of_owners / max(number_of_employees, 1)

        Returns:
            Owner/FTE ratio (Decimal('0.0') to Decimal('1.0')), or None if data not available
        """
        if (
            self.financial_data.number_of_owners is None
            or self.financial_data.number_of_employees is None
        ):
            # If either field is missing, return None
            # Default of 1 owner will be used at the schema level
            return None

        # Prevent division by zero; minimum 1 employee
        employees = max(self.financial_data.number_of_employees, 1)
        owners_decimal = to_decimal(self.financial_data.number_of_owners)
        employees_decimal = to_decimal(employees)
        ratio = owners_decimal / employees_decimal

        # Clamp to valid range [0.0, 1.0]
        ratio = max(Decimal("0.0"), min(Decimal("1.0"), ratio))

        logger.debug(
            "Owner/FTE ratio calculated",
            owners=self.financial_data.number_of_owners,
            employees=employees,
            ratio=from_decimal(bank_round(ratio, 3)),
        )

        return from_decimal(bank_round(ratio, 4))

    # === UTILITY METHODS ===

    def get_financial_health_description(self, score: int) -> str:
        """
        Get human-readable description of financial health.

        Args:
            score: Financial health score (0-100)

        Returns:
            Description string
        """
        if score >= 80:
            return "Excellent - Strong financial position with robust profitability and low risk"
        elif score >= 65:
            return "Good - Solid financial health with positive trends"
        elif score >= 50:
            return "Fair - Adequate financial position with some areas for improvement"
        elif score >= 35:
            return "Weak - Financial challenges present, requires attention"
        else:
            return "Poor - Significant financial distress, high risk"
