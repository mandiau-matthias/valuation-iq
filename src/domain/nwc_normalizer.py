"""
Net Working Capital (NWC) Normalizer

M&A-grade NWC normalization for the Enterprise Value to Equity Value bridge.
Calculates target (normalised) NWC and compares it to actual NWC to identify
surplus or deficit working capital that adjusts the equity value.

Methodology:
1. For each of the last 3 years, compute:
   NWC = (Current Assets - Cash) - (Current Liabilities - Short-Term Debt)
2. Express NWC as a percentage of revenue for each year.
3. Average the ratios to derive the "NWC peg" (target NWC %).
4. Compare actual (latest year) NWC to the target.
5. Surplus NWC adds to equity value; deficit subtracts.

Also computes DSO and DPO as diagnostic metrics.

Academic basis:
- Koller, Goedhart & Wessels (2020): Working capital normalization in M&A
- Rosenbaum & Pearl (2013): Investment Banking, Ch. 3 (EV-to-Equity Bridge)
- IBBA / M&A Source: Standard closing adjustment methodology
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _safe(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        value = to_decimal(val)
        return value if value.is_finite() else None
    except Exception:
        logger.debug("NWC _safe: could not convert %r to Decimal", val)
        return None


@dataclass
class NWCYearMetrics:
    """NWC metrics for a single year."""

    year: int
    revenue: Decimal
    current_assets: Decimal
    cash: Decimal
    current_liabilities: Decimal
    short_term_debt: Decimal
    accounts_receivable: Optional[Decimal]
    accounts_payable: Optional[Decimal]
    inventory: Optional[Decimal]
    cogs: Optional[Decimal]

    @property
    def operating_current_assets(self) -> Decimal:
        return self.current_assets - self.cash

    @property
    def operating_current_liabilities(self) -> Decimal:
        return self.current_liabilities - self.short_term_debt

    @property
    def nwc(self) -> Decimal:
        return self.operating_current_assets - self.operating_current_liabilities

    @property
    def nwc_pct_of_revenue(self) -> Optional[Decimal]:
        if self.revenue > Decimal("0"):
            return (self.nwc / self.revenue) * Decimal("100")
        return None

    @property
    def dso(self) -> Optional[Decimal]:
        """Days Sales Outstanding = (Receivables / Revenue) * 365"""
        if self.accounts_receivable is not None and self.revenue > Decimal("0"):
            return (self.accounts_receivable / self.revenue) * Decimal("365")
        return None

    @property
    def dpo(self) -> Optional[Decimal]:
        """Days Payable Outstanding = (Payables / COGS) * 365"""
        if self.accounts_payable is not None and self.cogs and self.cogs > Decimal("0"):
            return (self.accounts_payable / self.cogs) * Decimal("365")
        return None


@dataclass
class NWCNormalizationResult:
    """Result of NWC normalization analysis."""

    target_nwc_pct: Decimal
    target_nwc_absolute: Decimal
    actual_nwc: Decimal
    actual_nwc_pct: Decimal
    surplus_deficit: Decimal  # positive = surplus (adds to equity), negative = deficit
    is_surplus: bool
    latest_revenue: Decimal
    years_analyzed: int
    yearly_metrics: List[Dict[str, Any]] = field(default_factory=list)
    dso_latest: Optional[Decimal] = None
    dpo_latest: Optional[Decimal] = None
    dso_average: Optional[Decimal] = None
    dpo_average: Optional[Decimal] = None
    historical_years_used: int = 0
    short_term_debt_assumed_zero: bool = False
    payables_missing_for_dpo: bool = False
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_nwc_pct": round(float(self.target_nwc_pct), 2),
            "target_nwc_absolute": round(float(self.target_nwc_absolute), 2),
            "actual_nwc": round(float(self.actual_nwc), 2),
            "actual_nwc_pct": round(float(self.actual_nwc_pct), 2),
            "surplus_deficit": round(float(self.surplus_deficit), 2),
            "is_surplus": self.is_surplus,
            "latest_revenue": round(float(self.latest_revenue), 2),
            "years_analyzed": self.years_analyzed,
            "dso_latest": round(float(self.dso_latest), 1) if self.dso_latest is not None else None,
            "dpo_latest": round(float(self.dpo_latest), 1) if self.dpo_latest is not None else None,
            "dso_average": (
                round(float(self.dso_average), 1) if self.dso_average is not None else None
            ),
            "dpo_average": (
                round(float(self.dpo_average), 1) if self.dpo_average is not None else None
            ),
            "historical_years_used": self.historical_years_used,
            "short_term_debt_assumed_zero": self.short_term_debt_assumed_zero,
            "payables_missing_for_dpo": self.payables_missing_for_dpo,
            "yearly_metrics": self.yearly_metrics,
            "explanation": self.explanation,
        }


class NWCNormalizer:
    """
    Calculates normalised Net Working Capital and the surplus/deficit
    adjustment for the EV-to-Equity bridge.
    """

    MIN_HISTORICAL_YEARS = 2

    def normalize(
        self,
        historical_years: List[Any],
        current_year: Optional[Any] = None,
    ) -> Optional[NWCNormalizationResult]:
        """
        Run full NWC normalization analysis.

        Args:
            historical_years: Year data objects (oldest first), must have balance sheet fields.
            current_year: Optional current/latest year data.

        Returns:
            NWCNormalizationResult or None if insufficient data.
        """
        # A fiscal year is one observation. Reordered imports and duplicated
        # evidence must not change the peg; conflicting restatements require
        # an upstream admission decision instead of last-write-wins selection.
        by_year: dict[int, NWCYearMetrics] = {}
        for metric in self._extract_year_metrics(list(historical_years)):
            previous = by_year.get(metric.year)
            if previous is not None and previous != metric:
                return None
            by_year[metric.year] = metric
        if current_year is None:
            actual_metrics_list = [by_year[max(by_year)]] if by_year else []
        else:
            actual_metrics_list = self._extract_year_metrics([current_year])
        actual_year = actual_metrics_list[0].year if actual_metrics_list else 0
        historical_metrics = [by_year[year] for year in sorted(by_year) if year < actual_year][-3:]

        if len(historical_metrics) < self.MIN_HISTORICAL_YEARS or not actual_metrics_list:
            logger.debug(
                "Insufficient balance sheet data for NWC normalization",
                historical_years_with_data=len(historical_metrics),
                min_required=self.MIN_HISTORICAL_YEARS,
            )
            return None

        actual_metrics = actual_metrics_list[-1]

        # Calculate NWC % of revenue for each year
        nwc_pcts: List[Decimal] = []
        yearly_output: List[Dict[str, Any]] = []
        dso_values: List[Decimal] = []
        dpo_values: List[Decimal] = []
        short_term_debt_assumed_zero = False
        payables_missing_for_dpo = False

        actual_year_id = actual_metrics.year

        for m in historical_metrics:
            pct = m.nwc_pct_of_revenue
            if pct is not None:
                nwc_pcts.append(pct)
            if m.dso is not None:
                dso_values.append(m.dso)
            if m.dpo is not None:
                dpo_values.append(m.dpo)
            elif m.accounts_payable is None:
                payables_missing_for_dpo = True

            is_actual = m.year == actual_year_id and current_year is None
            if is_actual:
                continue

            yearly_output.append(
                {
                    "year": m.year,
                    "nwc": round(float(m.nwc), 2),
                    "nwc_pct_of_revenue": round(float(pct), 2) if pct is not None else None,
                    "operating_current_assets": round(float(m.operating_current_assets), 2),
                    "operating_current_liabilities": round(
                        float(m.operating_current_liabilities), 2
                    ),
                    "dso": round(float(m.dso), 1) if m.dso is not None else None,
                    "dpo": round(float(m.dpo), 1) if m.dpo is not None else None,
                }
            )

        actual_pct = (
            actual_metrics.nwc_pct_of_revenue
            if actual_metrics.nwc_pct_of_revenue is not None
            else Decimal("0")
        )
        if actual_metrics.accounts_payable is None:
            payables_missing_for_dpo = True
        yearly_output.append(
            {
                "year": actual_metrics.year,
                "nwc": round(float(actual_metrics.nwc), 2),
                "nwc_pct_of_revenue": (
                    round(float(actual_pct), 2) if actual_pct is not None else None
                ),
                "operating_current_assets": round(
                    float(actual_metrics.operating_current_assets), 2
                ),
                "operating_current_liabilities": round(
                    float(actual_metrics.operating_current_liabilities), 2
                ),
                "dso": (
                    round(float(actual_metrics.dso), 1) if actual_metrics.dso is not None else None
                ),
                "dpo": (
                    round(float(actual_metrics.dpo), 1) if actual_metrics.dpo is not None else None
                ),
                "is_actual_comparison_year": True,
            }
        )

        if not nwc_pcts:
            return None

        # Target NWC % = average of historical NWC/Revenue ratios
        target_pct = sum(nwc_pcts) / Decimal(str(len(nwc_pcts)))

        # Actual comparison year metrics
        actual_nwc = actual_metrics.nwc
        latest_revenue = actual_metrics.revenue

        # Target NWC in absolute terms
        target_absolute = (target_pct / Decimal("100")) * latest_revenue

        # Surplus/deficit
        surplus = actual_nwc - target_absolute

        # DSO/DPO averages
        dso_avg = sum(dso_values) / Decimal(str(len(dso_values))) if dso_values else None
        dpo_avg = sum(dpo_values) / Decimal(str(len(dpo_values))) if dpo_values else None

        if surplus > Decimal("0"):
            direction = "surplus"
            explanation = (
                f"Actual NWC ({actual_nwc:,.0f}, {actual_pct:.1f}% of revenue) exceeds "
                f"target NWC ({target_absolute:,.0f}, {target_pct:.1f}% of revenue) by "
                f"{surplus:,.0f}. This surplus working capital adds to equity value. "
                f"Based on {len(nwc_pcts)} historical-year average as an indicative peg; an agreed completion-accounts definition takes precedence "
                f"(Rosenbaum & Pearl 2013, Koller 2020)."
            )
        elif surplus < Decimal("0"):
            direction = "deficit"
            explanation = (
                f"Actual NWC ({actual_nwc:,.0f}, {actual_pct:.1f}% of revenue) is below "
                f"target NWC ({target_absolute:,.0f}, {target_pct:.1f}% of revenue) by "
                f"{abs(surplus):,.0f}. This working capital deficit reduces equity value. "
                f"Based on {len(nwc_pcts)} historical-year average as an indicative peg; an agreed completion-accounts definition takes precedence "
                f"(Rosenbaum & Pearl 2013, Koller 2020)."
            )
        else:
            direction = "neutral"
            explanation = (
                f"Actual NWC matches target NWC ({target_pct:.1f}% of revenue). "
                f"No equity bridge adjustment needed."
            )

        if short_term_debt_assumed_zero:
            explanation += " Short-term debt was not provided for one or more years, so operating current liabilities were conservatively approximated from current liabilities."
        if payables_missing_for_dpo:
            explanation += (
                " DPO is only reported when accounts payable and COGS are both available."
            )

        logger.info(
            f"NWC normalization complete: {direction}",
            target_pct=float(target_pct),
            actual_pct=float(actual_pct),
            surplus=float(surplus),
            years_analyzed=len(nwc_pcts),
        )

        return NWCNormalizationResult(
            target_nwc_pct=target_pct,
            target_nwc_absolute=target_absolute,
            actual_nwc=actual_nwc,
            actual_nwc_pct=actual_pct,
            surplus_deficit=surplus,
            is_surplus=surplus > Decimal("0"),
            latest_revenue=latest_revenue,
            years_analyzed=len(nwc_pcts),
            yearly_metrics=yearly_output,
            dso_latest=actual_metrics.dso,
            dpo_latest=actual_metrics.dpo,
            dso_average=dso_avg,
            dpo_average=dpo_avg,
            historical_years_used=len(nwc_pcts),
            short_term_debt_assumed_zero=short_term_debt_assumed_zero,
            payables_missing_for_dpo=payables_missing_for_dpo,
            explanation=explanation,
        )

    def _extract_year_metrics(self, all_years: List[Any]) -> List[NWCYearMetrics]:
        """Extract NWC-relevant fields from year data objects."""
        results: List[NWCYearMetrics] = []

        for yd in all_years:
            year = _safe_attr(yd, "year")
            revenue = _safe_attr(yd, "revenue")
            current_assets = _safe_attr(yd, "current_assets")
            current_liabilities = _safe_attr(yd, "current_liabilities")
            cash = _safe_attr(yd, "cash")

            required = {
                "revenue": _safe(revenue),
                "current_assets": _safe(current_assets),
                "cash": _safe(cash),
                "current_liabilities": _safe(current_liabilities),
                "short_term_debt": _safe(_safe_attr(yd, "short_term_debt")),
            }
            if year is None or any(value is None for value in required.values()):
                continue
            required = {key: value for key, value in required.items() if value is not None}
            # Missing cash/debt is not zero. Invalid balance-sheet containment
            # is not repaired by flooring operating liabilities.
            if (
                required["revenue"] <= 0
                or required["cash"] < 0
                or required["short_term_debt"] < 0
                or required["cash"] > required["current_assets"]
                or required["short_term_debt"] > required["current_liabilities"]
            ):
                continue

            results.append(
                NWCYearMetrics(
                    year=int(year),
                    **required,
                    accounts_receivable=_safe(_safe_attr(yd, "accounts_receivable")),
                    accounts_payable=_safe(_safe_attr(yd, "accounts_payable")),
                    inventory=_safe(_safe_attr(yd, "inventory")),
                    cogs=_safe(_safe_attr(yd, "cogs")),
                )
            )

        return results


def _safe_attr(obj: Any, attr: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(attr)
    return getattr(obj, attr, None)
