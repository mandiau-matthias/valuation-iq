"""
Trial Balance Anomaly Scanner

Statistical anomaly detection on P&L line items across multiple years.
Identifies one-off or abnormal cost spikes that may warrant normalization,
enabling the UI to prompt the user before calculating EBITDA-based valuations.

This module scans Belgian MAR (Minimum Algemeen Rekeningenstelsel) accounts:
- Account 60: Purchases / goods (maps to COGS)
- Account 61: Services & diverse goods (maps to operating_expenses)
- Account 62: Remuneration / personnel costs (maps to personnel_costs)
- Account 63: Depreciation & amortization (maps to depreciation + amortization)
- Account 64: Other operating costs (maps to other_operating_costs)

The scanner normalises each cost line as a percentage of revenue, then flags
years where the ratio deviates by more than a configurable number of standard
deviations (default: 2.0) from the historical mean.

Separate from the existing AnomalyDetector (validation/anomaly_detector.py)
which validates valuation *outputs*. This module analyses financial *inputs*.
"""

import statistics
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger
from src.utils.decimal_helpers import optional_decimal

logger = get_logger(__name__)


@dataclass
class AnomalyFlag:
    """A single detected anomaly on a cost account."""

    anomaly_detected: bool
    account: str
    account_label: str
    year: int
    actual_pct_of_revenue: float
    historical_mean_pct: float
    historical_std_pct: float
    z_score: float
    confidence: float
    direction: str  # "spike" or "dip"
    suggested_normalization: Optional[float] = None
    explanation: str = ""


@dataclass
class ScanResult:
    """Aggregate result of scanning all accounts across all years."""

    anomaly_flags: List[AnomalyFlag] = field(default_factory=list)
    accounts_scanned: int = 0
    years_scanned: int = 0
    supported_accounts: List[str] = field(default_factory=list)
    unsupported_accounts: List[str] = field(default_factory=list)

    @property
    def has_anomalies(self) -> bool:
        return len(self.anomaly_flags) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_anomalies": self.has_anomalies,
            "anomaly_count": len(self.anomaly_flags),
            "accounts_scanned": self.accounts_scanned,
            "years_scanned": self.years_scanned,
            "supported_accounts": self.supported_accounts,
            "unsupported_accounts": self.unsupported_accounts,
            "anomaly_flags": [
                {
                    "anomaly_detected": f.anomaly_detected,
                    "account": f.account,
                    "account_label": f.account_label,
                    "year": f.year,
                    "actual_pct_of_revenue": round(f.actual_pct_of_revenue, 2),
                    "historical_mean_pct": round(f.historical_mean_pct, 2),
                    "z_score": round(f.z_score, 2),
                    "confidence": round(f.confidence, 2),
                    "direction": f.direction,
                    "suggested_normalization": (
                        round(f.suggested_normalization, 2)
                        if f.suggested_normalization is not None
                        else None
                    ),
                    "explanation": f.explanation,
                }
                for f in self.anomaly_flags
            ],
        }


# MAR account mapping: account code -> (field_name on year data, human label)
MAR_ACCOUNT_MAP: Dict[str, tuple] = {
    "60": ("cogs", "Aankopen / Handelsgoederen"),
    "61": ("operating_expenses", "Diensten en diverse goederen"),
    "62": ("personnel_costs", "Bezoldigingen en sociale lasten"),
    "63": ("depreciation", "Afschrijvingen en waardeverminderingen"),
    "64": ("other_operating_costs", "Andere bedrijfskosten"),
}

SUPPORTED_MAR_ACCOUNTS = {"60", "61", "63"}
UNSUPPORTED_MAR_ACCOUNTS = {"62", "64"}

# Fallback compound fields for account 63 (depreciation + amortization)
_DEPRECIATION_FIELDS = ("depreciation", "amortization")


def _extract_account_value(year_data: Any, field_name: str) -> Optional[Decimal]:
    """Extract a numeric value from year data by field name."""
    if field_name == "depreciation":
        if isinstance(year_data, dict):
            dep = _safe_decimal(year_data.get("depreciation"))
            amo = _safe_decimal(year_data.get("amortization"))
        else:
            dep = _safe_decimal(getattr(year_data, "depreciation", None))
            amo = _safe_decimal(getattr(year_data, "amortization", None))
        if dep is None and amo is None:
            return None
        return (dep or Decimal("0")) + (amo or Decimal("0"))

    val = getattr(year_data, field_name, None)
    if val is None and isinstance(year_data, dict):
        val = year_data.get(field_name)
    return _safe_decimal(val)


_safe_decimal = optional_decimal


class TrialBalanceAnomalyScanner:
    """
    Scans historical P&L data for statistically abnormal cost spikes/dips.

    Usage:
        scanner = TrialBalanceAnomalyScanner(z_threshold=2.0)
        result = scanner.scan(historical_years, current_year)
    """

    def __init__(self, z_threshold: float = 2.0, min_years: int = 3):
        self.z_threshold = z_threshold
        self.min_years = min_years

    def scan(
        self,
        historical_years: List[Any],
        current_year: Optional[Any] = None,
        accounts: Optional[List[str]] = None,
    ) -> ScanResult:
        """
        Scan all configured MAR accounts across historical + current year data.

        Args:
            historical_years: List of year data objects (oldest first).
            current_year: Optional current/latest year data.
            accounts: Optional list of account codes to scan (default: all).

        Returns:
            ScanResult with any detected anomalies.
        """
        historical_only = list(historical_years)
        latest_year = current_year if current_year is not None else (historical_only[-1] if historical_only else None)
        baseline_years = historical_only if current_year is not None else historical_only[:-1]

        if latest_year is None or len(baseline_years) < max(2, self.min_years - 1):
            logger.debug(
                "Insufficient years for anomaly scan",
                years_available=len(historical_only) + (1 if current_year is not None else 0),
                min_required=self.min_years,
            )
            return ScanResult(years_scanned=len(historical_only) + (1 if current_year is not None else 0))

        target_accounts = accounts or sorted(SUPPORTED_MAR_ACCOUNTS)
        requested_accounts = [account for account in target_accounts if account in MAR_ACCOUNT_MAP]
        supported_accounts = [account for account in requested_accounts if account in SUPPORTED_MAR_ACCOUNTS]
        unsupported_accounts = [account for account in requested_accounts if account not in SUPPORTED_MAR_ACCOUNTS]
        result = ScanResult(
            years_scanned=len(historical_only) + (1 if current_year is not None else 0),
            supported_accounts=supported_accounts,
            unsupported_accounts=unsupported_accounts,
        )

        for account_code in supported_accounts:
            if account_code not in MAR_ACCOUNT_MAP:
                continue
            field_name, label = MAR_ACCOUNT_MAP[account_code]
            flags = self._scan_single_account(
                account_code, field_name, label, baseline_years, latest_year
            )
            result.anomaly_flags.extend(flags)
            result.accounts_scanned += 1

        if result.has_anomalies:
            logger.info(
                "Trial balance anomalies detected",
                anomaly_count=len(result.anomaly_flags),
                accounts_flagged=[f.account for f in result.anomaly_flags],
            )

        return result

    def _scan_single_account(
        self,
        account_code: str,
        field_name: str,
        label: str,
        baseline_years: List[Any],
        latest_year: Any,
    ) -> List[AnomalyFlag]:
        """Score the latest year against a historical-only baseline."""
        baseline_ratios: List[tuple] = []  # (year, ratio_pct, raw_value)

        for yd in baseline_years:
            revenue = _safe_decimal(
                getattr(yd, "revenue", None)
                if not isinstance(yd, dict)
                else yd.get("revenue")
            )
            year = (
                getattr(yd, "year", None)
                if not isinstance(yd, dict)
                else yd.get("year")
            )
            value = _extract_account_value(yd, field_name)

            if revenue and revenue > Decimal("0") and value is not None:
                ratio_pct = float((value / revenue) * Decimal("100"))
                baseline_ratios.append((year, ratio_pct, float(value)))

        if len(baseline_ratios) < max(2, self.min_years - 1):
            return []

        latest_revenue = _safe_decimal(
            getattr(latest_year, "revenue", None)
            if not isinstance(latest_year, dict)
            else latest_year.get("revenue")
        )
        latest_year_label = (
            getattr(latest_year, "year", None)
            if not isinstance(latest_year, dict)
            else latest_year.get("year")
        )
        latest_value = _extract_account_value(latest_year, field_name)
        if not latest_revenue or latest_revenue <= Decimal("0") or latest_value is None:
            return []

        latest_ratio_pct = float((latest_value / latest_revenue) * Decimal("100"))

        pct_values = [r[1] for r in baseline_ratios]
        mean_pct = statistics.mean(pct_values)
        std_pct = statistics.stdev(pct_values) if len(pct_values) > 1 else 0.0

        if std_pct == 0.0:
            return []

        z = (latest_ratio_pct - mean_pct) / std_pct
        abs_z = abs(z)
        if abs_z < self.z_threshold:
            return []

        direction = "spike" if z > 0 else "dip"
        confidence = min(0.99, 0.5 + (abs_z - self.z_threshold) * 0.15)
        normalized_value = mean_pct / 100.0 * float(latest_revenue)
        excess = float(latest_value) - normalized_value

        explanation = (
            f"Account {account_code} ({label}) in {latest_year_label}: {latest_ratio_pct:.1f}% of revenue "
            f"vs historical average {mean_pct:.1f}% based on prior years only (Z-score: {z:.1f}). "
            f"This {'increase' if direction == 'spike' else 'decrease'} "
            f"of {abs(latest_ratio_pct - mean_pct):.1f}pp is statistically abnormal "
            f"(>{self.z_threshold:.0f} standard deviations). "
            f"Potential one-off {'cost' if direction == 'spike' else 'saving'} "
            f"of approximately €{abs(excess):,.0f}."
        )

        return [
            AnomalyFlag(
                anomaly_detected=True,
                account=account_code,
                account_label=label,
                year=latest_year_label or 0,
                actual_pct_of_revenue=latest_ratio_pct,
                historical_mean_pct=mean_pct,
                historical_std_pct=std_pct,
                z_score=round(z, 2),
                confidence=round(confidence, 2),
                direction=direction,
                suggested_normalization=round(excess, 2) if excess else None,
                explanation=explanation,
            )
        ]
