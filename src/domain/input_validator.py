"""
Input Validation Module for Valuation Engine.

Validates financial inputs for realism and catches unrealistic scenarios
before running expensive valuation calculations.

Validation checks:
1. EBITDA margin realism (catches 100% margins, etc.)
2. Revenue consistency with industry norms
3. Growth rate feasibility
4. Financial metric relationships
5. Data completeness warnings
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from src.domain.models import FinancialData, YearData

# Transparency tracking imports
# TransparencyTracker imported locally to avoid circular imports
from src.domain.transparency import ValidationCheck, ValidationReport
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationWarning:
    """Validation warning with severity level."""

    CRITICAL = "critical"  # Will block valuation
    ERROR = "error"  # Should block valuation
    WARNING = "warning"  # Reduces confidence
    INFO = "info"  # Informational only

    def __init__(self, severity: str, code: str, message: str, field: str = None):
        self.severity = severity
        self.code = code
        self.message = message
        self.field = field

    def __repr__(self):
        return f"<{self.severity.upper()}: {self.message}>"


class FinancialInputValidator:
    """
    Validates financial inputs for realism and completeness.

    This validator catches unrealistic scenarios before running
    valuation calculations, improving accuracy and user experience.
    
    Benchmark Priority:
    1. Titan-provided industry_benchmarks (from Delphi/business_types DB) - HIGHEST
    2. Hardcoded industry-specific benchmarks (fallback)
    3. Generic default benchmarks (last resort)
    """

    # Industry-specific EBITDA margin expectations (FALLBACK - used when Titan doesn't provide benchmarks)
    INDUSTRY_MARGIN_BENCHMARKS = {
        "Technology": {
            "min": -Decimal("0.30"),
            "typical_low": Decimal("0.10"),
            "typical_high": Decimal("0.30"),
            "max": 0.45,
        },
        "Manufacturing": {
            "min": -Decimal("0.20"),
            "typical_low": Decimal("0.08"),
            "typical_high": Decimal("0.15"),
            "max": 0.25,
        },
        "Retail": {
            "min": -Decimal("0.15"),
            "typical_low": Decimal("0.03"),
            "typical_high": Decimal("0.08"),
            "max": 0.15,
        },
        "Healthcare": {
            "min": -Decimal("0.20"),
            "typical_low": Decimal("0.10"),
            "typical_high": Decimal("0.20"),
            "max": 0.35,
        },
        "Services": {
            "min": -Decimal("0.25"),
            "typical_low": Decimal("0.15"),
            "typical_high": Decimal("0.30"),
            "max": 0.40,
        },
        "Default": {
            "min": -Decimal("0.30"),
            "typical_low": Decimal("0.05"),
            "typical_high": Decimal("0.20"),
            "max": 0.40,
        },
    }

    def __init__(
        self,
        financial_data: FinancialData,
        transparency_tracker: Optional["TransparencyTracker"] = None,
        titan_benchmarks: Optional[Dict] = None,
    ):
        """
        Initialize validator with financial data.
        
        Args:
            financial_data: Financial data to validate
            transparency_tracker: Optional transparency tracker
            titan_benchmarks: Optional Titan-provided industry_benchmarks from Delphi/business_types DB
        """
        self.financial_data = financial_data
        self.warnings: List[ValidationWarning] = []
        self.titan_benchmarks = titan_benchmarks
        if transparency_tracker is None:
            from src.services.privacy.compliance.transparency_tracker import TransparencyTracker

            self.transparency = TransparencyTracker()
        else:
            self.transparency = transparency_tracker

    def _actual_historical_years(self) -> List[YearData]:
        """Return non-forecast historical years in chronological order."""
        return sorted(
            (
                year
                for year in self.financial_data.historical_years
                if not getattr(year, "is_forecast", False)
            ),
            key=lambda year: getattr(year, "year", 0),
        )

    def _get_ebitda_margin_benchmarks(self, industry: str) -> Dict:
        """
        Get EBITDA margin benchmarks with priority cascade.
        
        Priority:
        1. Titan-provided industry_benchmarks (from Delphi/business_types DB)
        2. Hardcoded industry-specific benchmarks
        3. Generic default benchmarks
        
        Args:
            industry: Industry name
            
        Returns:
            Dict with min, typical_low, typical_high, max margin benchmarks
        """
        # PRIORITY 1: Titan-provided benchmarks (from Delphi/business_types DB)
        if self.titan_benchmarks:
            # Extract EBITDA margin benchmarks from Titan enrichment
            ebitda_margin = self.titan_benchmarks.get("typical_ebitda_margin") or {}
            
            # Titan provides min, max, median in the typical_ebitda_margin field
            if ebitda_margin and (ebitda_margin.get("min") is not None or ebitda_margin.get("median") is not None):
                titan_min = ebitda_margin.get("min")
                titan_max = ebitda_margin.get("max")
                titan_median = ebitda_margin.get("median")
                
                # NORMALIZE TITAN VALUES: Titan sends percentages (e.g., 15 = 15%)
                # but Python internal logic expects decimals (e.g., 0.15 = 15%)
                # If value > 1.0, it's a percentage - convert to decimal by dividing by 100
                def normalize_margin(value):
                    """Convert percentage (15) to decimal (0.15) if needed."""
                    if value is None:
                        return None
                    val = Decimal(str(value)) if not isinstance(value, Decimal) else value
                    if val > Decimal("1.0"):
                        # Value is in percentage format (e.g., 15 = 15%), convert to decimal
                        return val / Decimal("100")
                    return val
                
                # Build benchmarks from Titan data (normalized to decimal form)
                # Use median as typical_high, and derive typical_low
                if titan_median is not None:
                    typical_high = normalize_margin(titan_median)
                    typical_low = typical_high * Decimal("0.6")  # Estimate typical_low as 60% of median
                else:
                    typical_high = Decimal("0.20")
                    typical_low = Decimal("0.05")
                
                if titan_min is not None:
                    min_margin = normalize_margin(titan_min)
                else:
                    min_margin = typical_low - Decimal("0.10")
                    
                if titan_max is not None:
                    max_margin = normalize_margin(titan_max)
                else:
                    max_margin = typical_high + Decimal("0.15")
                
                logger.info(
                    "✅ Using TITAN-PROVIDED EBITDA margin benchmarks",
                    extra={
                        "source": "titan_enrichment",
                        "min": float(min_margin),
                        "typical_low": float(typical_low),
                        "typical_high": float(typical_high),
                        "max": float(max_margin),
                        "industry": industry,
                    }
                )
                
                return {
                    "min": min_margin,
                    "typical_low": typical_low,
                    "typical_high": typical_high,
                    "max": max_margin,
                    "source": "titan_enrichment",
                }
        
        # PRIORITY 2 & 3: Hardcoded benchmarks with industry fallback
        benchmarks = self.INDUSTRY_MARGIN_BENCHMARKS.get(
            industry, self.INDUSTRY_MARGIN_BENCHMARKS["Default"]
        )
        
        logger.debug(
            "Using hardcoded EBITDA margin benchmarks",
            extra={"source": "hardcoded", "industry": industry}
        )
        
        return {**benchmarks, "source": "hardcoded"}

    def _get_revenue_benchmarks(self) -> Dict:
        """
        Get revenue benchmarks from Titan enrichment or defaults.
        
        Returns:
            Dict with min, max, median revenue benchmarks
        """
        # PRIORITY 1: Titan-provided benchmarks
        if self.titan_benchmarks:
            typical_revenue = self.titan_benchmarks.get("typical_revenue") or {}
            
            if typical_revenue and (typical_revenue.get("min") is not None or typical_revenue.get("median") is not None):
                titan_min = typical_revenue.get("min")
                titan_max = typical_revenue.get("max")
                titan_median = typical_revenue.get("median")
                
                result = {"source": "titan_enrichment"}
                
                if titan_min is not None:
                    result["min"] = Decimal(str(titan_min)) if not isinstance(titan_min, Decimal) else titan_min
                else:
                    result["min"] = Decimal("10000")  # Default fallback
                    
                if titan_max is not None:
                    result["max"] = Decimal(str(titan_max)) if not isinstance(titan_max, Decimal) else titan_max
                    
                if titan_median is not None:
                    result["median"] = Decimal(str(titan_median)) if not isinstance(titan_median, Decimal) else titan_median
                
                logger.info(
                    "✅ Using TITAN-PROVIDED revenue benchmarks",
                    extra={
                        "source": "titan_enrichment",
                        "min": float(result.get("min", 0)),
                        "max": float(result.get("max", 0)) if result.get("max") else None,
                        "median": float(result.get("median", 0)) if result.get("median") else None,
                    }
                )
                
                return result
        
        # PRIORITY 2: Default benchmarks
        return {
            "min": Decimal("10000"),  # €10k minimum
            "source": "hardcoded",
        }

    def _get_employee_benchmarks(self) -> Dict:
        """
        Get employee count benchmarks from Titan enrichment or defaults.
        
        Returns:
            Dict with min, max, median employee count benchmarks
        """
        # PRIORITY 1: Titan-provided benchmarks
        if self.titan_benchmarks:
            typical_employee = self.titan_benchmarks.get("typical_employee_count") or {}
            
            if typical_employee and (typical_employee.get("min") is not None or typical_employee.get("median") is not None):
                result = {"source": "titan_enrichment"}
                
                if typical_employee.get("min") is not None:
                    result["min"] = int(typical_employee["min"])
                if typical_employee.get("max") is not None:
                    result["max"] = int(typical_employee["max"])
                if typical_employee.get("median") is not None:
                    result["median"] = int(typical_employee["median"])
                
                logger.info(
                    "✅ Using TITAN-PROVIDED employee count benchmarks",
                    extra={
                        "source": "titan_enrichment",
                        "min": result.get("min"),
                        "max": result.get("max"),
                        "median": result.get("median"),
                    }
                )
                
                return result
        
        # PRIORITY 2: Default (no specific benchmarks)
        return {"source": "hardcoded"}

    def validate_all(self) -> Tuple[bool, List[ValidationWarning]]:
        """
        Run all validation checks.

        Returns:
            Tuple of (is_valid, warnings_list)
        """
        logger.info("Starting financial input validation", company=self.financial_data.company_name)

        # Run all validation checks
        self._validate_ebitda_margin()
        self._validate_revenue()
        self._validate_growth_rates()
        self._validate_financial_relationships()
        self._validate_data_completeness()

        # Determine if validation passed
        has_critical = any(w.severity == ValidationWarning.CRITICAL for w in self.warnings)
        has_errors = any(w.severity == ValidationWarning.ERROR for w in self.warnings)

        is_valid = not (has_critical or has_errors)

        logger.info(
            "Validation complete",
            is_valid=is_valid,
            warnings=len(self.warnings),
            critical=len([w for w in self.warnings if w.severity == ValidationWarning.CRITICAL]),
            errors=len([w for w in self.warnings if w.severity == ValidationWarning.ERROR]),
        )

        # Track validation report for transparency
        self._track_validation_report(is_valid)

        return is_valid, self.warnings

    def _validate_ebitda_margin(self):
        """Validate EBITDA margin for realism."""
        current = self.financial_data.current_year

        if current.revenue <= 0:
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.CRITICAL,
                    "INVALID_REVENUE",
                    "Revenue must be positive",
                    "revenue",
                )
            )
            return

        margin = current.ebitda / current.revenue

        # Get industry benchmarks - PRIORITY: Titan-provided > Hardcoded > Default
        industry = self.financial_data.industry
        benchmarks = self._get_ebitda_margin_benchmarks(industry)

        # Check for impossible scenarios
        if margin >= 1.0:
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.CRITICAL,
                    "IMPOSSIBLE_EBITDA_MARGIN",
                    f"EBITDA margin of {margin:.1%} is mathematically impossible. "
                    f"EBITDA ({current.ebitda:,.0f}) equals or exceeds revenue ({current.revenue:,.0f}). "
                    f"This suggests either: (1) incorrect data entry, (2) EBITDA includes non-operating income, "
                    f"or (3) revenue is understated. Please verify your financial data.",
                    "ebitda",
                )
            )
        elif margin > 0.80:
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.ERROR,
                    "UNREALISTIC_EBITDA_MARGIN",
                    f"EBITDA margin of {margin:.1%} is extremely unrealistic. "
                    f"Even the most efficient businesses rarely exceed 40-50% EBITDA margins. "
                    f"For {industry}, typical margins are {benchmarks['typical_low']:.1%}-{benchmarks['typical_high']:.1%}. "
                    f"Please verify your EBITDA calculation excludes non-operating items.",
                    "ebitda",
                )
            )
        elif margin > benchmarks["max"]:
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.WARNING,
                    "HIGH_EBITDA_MARGIN",
                    f"EBITDA margin of {margin:.1%} is very high for {industry} industry. "
                    f"Typical range is {benchmarks['typical_low']:.1%}-{benchmarks['typical_high']:.1%}. "
                    f"While possible for exceptional businesses, this will impact valuation confidence.",
                    "ebitda",
                )
            )
        elif margin < benchmarks["min"]:
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.WARNING,
                    "VERY_LOW_EBITDA_MARGIN",
                    f"EBITDA margin of {margin:.1%} indicates significant losses. "
                    f"This is concerning for {industry} and will heavily impact valuation.",
                    "ebitda",
                )
            )

        # Check if EBITDA exceeds revenue (mathematically impossible)
        if current.ebitda > current.revenue:
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.CRITICAL,
                    "EBITDA_EXCEEDS_REVENUE",
                    f"EBITDA (€{current.ebitda:,.0f}) exceeds revenue (€{current.revenue:,.0f}). "
                    f"This is mathematically impossible and indicates a data error.",
                    "ebitda",
                )
            )

    def _validate_revenue(self):
        """Validate revenue figures, using Titan benchmarks when available."""
        current = self.financial_data.current_year

        # Check for negative revenue
        if current.revenue < 0:
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.CRITICAL,
                    "NEGATIVE_REVENUE",
                    "Revenue cannot be negative",
                    "revenue",
                )
            )

        # Use Titan-provided revenue benchmarks if available
        revenue_benchmarks = self._get_revenue_benchmarks()
        min_typical_revenue = revenue_benchmarks.get("min", Decimal("10000"))
        max_typical_revenue = revenue_benchmarks.get("max")
        median_typical_revenue = revenue_benchmarks.get("median")
        benchmark_source = revenue_benchmarks.get("source", "hardcoded")

        # Check for very low revenue (using Titan benchmark or fallback)
        if 0 < current.revenue < min_typical_revenue:
            source_note = " for this business type" if benchmark_source == "titan_enrichment" else ""
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.WARNING,
                    "VERY_LOW_REVENUE",
                    f"Revenue of €{current.revenue:,.0f} is below typical minimum{source_note} "
                    f"(€{min_typical_revenue:,.0f}). Valuations for very early-stage businesses are more speculative.",
                    "revenue",
                )
            )
        
        # Check if revenue is unusually high compared to typical maximum
        if max_typical_revenue and current.revenue > max_typical_revenue * Decimal("2"):
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.INFO,
                    "ABOVE_TYPICAL_REVENUE",
                    f"Revenue of €{current.revenue:,.0f} is well above typical range for this business type "
                    f"(max typical: €{max_typical_revenue:,.0f}). This may indicate a larger enterprise.",
                    "revenue",
                )
            )

        # Check for consistency with historical data
        historical_years = self._actual_historical_years()
        if historical_years:
            last_year = historical_years[-1]
            growth = (current.revenue - last_year.revenue) / last_year.revenue

            if growth > Decimal("5.0"):  # >500% growth
                self.warnings.append(
                    ValidationWarning(
                        ValidationWarning.WARNING,
                        "EXTREME_REVENUE_GROWTH",
                        f"Revenue growth of {growth:.1%} YoY is extremely high. "
                        f"While possible for early-stage businesses, please verify this is accurate.",
                        "revenue",
                    )
                )
            elif growth < Decimal("-0.80"):  # >80% decline
                self.warnings.append(
                    ValidationWarning(
                        ValidationWarning.WARNING,
                        "EXTREME_REVENUE_DECLINE",
                        f"Revenue declined {abs(growth):.1%} YoY. "
                        f"This suggests significant business challenges that will impact valuation.",
                        "revenue",
                    )
                )

    def _validate_growth_rates(self):
        """Validate growth rate consistency."""
        historical_years = self._actual_historical_years()
        if len(historical_years) < 2:
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.INFO,
                    "LIMITED_HISTORICAL_DATA",
                    "Less than 2 years of historical data available. "
                    "Adding historical data improves valuation accuracy by ~20%.",
                    "historical_data",
                )
            )
            return

        # Calculate revenue CAGR
        first_year = historical_years[0]
        last_year = self.financial_data.current_year
        year_span = getattr(last_year, "year", 0) - getattr(first_year, "year", 0)
        years = year_span if year_span > 0 else len(historical_years)

        if first_year.revenue > 0:
            cagr = (last_year.revenue / first_year.revenue) ** (Decimal("1.0") / years) - Decimal(
                "1.0"
            )

            if cagr > Decimal("2.0"):  # >200% CAGR
                self.warnings.append(
                    ValidationWarning(
                        ValidationWarning.WARNING,
                        "EXTREME_CAGR",
                        f"Revenue CAGR of {cagr:.1%} is extremely high. "
                        f"Verify this growth is sustainable and based on actual revenue recognition.",
                        "revenue",
                    )
                )

    def _validate_financial_relationships(self):
        """Validate relationships between financial metrics."""
        current = self.financial_data.current_year

        # Check if net income exists and is consistent with EBITDA
        if current.net_income is not None:
            if current.net_income > current.ebitda + 100:  # Allow small rounding
                self.warnings.append(
                    ValidationWarning(
                        ValidationWarning.ERROR,
                        "NET_INCOME_EXCEEDS_EBITDA",
                        f"Net income (€{current.net_income:,.0f}) exceeds EBITDA (€{current.ebitda:,.0f}). "
                        f"This is unusual as EBITDA should be higher than net income before depreciation, "
                        f"interest, and taxes.",
                        "net_income",
                    )
                )

        # Check if EBIT exists and is consistent
        if current.ebit is not None:
            if current.ebit > current.ebitda + 100:
                self.warnings.append(
                    ValidationWarning(
                        ValidationWarning.ERROR,
                        "EBIT_EXCEEDS_EBITDA",
                        f"EBIT (€{current.ebit:,.0f}) exceeds EBITDA (€{current.ebitda:,.0f}). "
                        f"This is impossible as EBITDA = EBIT + Depreciation + Amortization.",
                        "ebit",
                    )
                )

        # Check for gross profit consistency
        if current.gross_profit is not None:
            if current.gross_profit > current.revenue:
                self.warnings.append(
                    ValidationWarning(
                        ValidationWarning.ERROR,
                        "GROSS_PROFIT_EXCEEDS_REVENUE",
                        "Gross profit cannot exceed revenue",
                        "gross_profit",
                    )
                )

            if current.gross_profit < current.ebitda:
                self.warnings.append(
                    ValidationWarning(
                        ValidationWarning.WARNING,
                        "EBITDA_EXCEEDS_GROSS_PROFIT",
                        f"EBITDA (€{current.ebitda:,.0f}) exceeds gross profit (€{current.gross_profit:,.0f}). "
                        f"This suggests negative operating expenses, which is unusual.",
                        "ebitda",
                    )
                )

    def _validate_data_completeness(self):
        """Check for missing data that would improve valuation accuracy."""
        current = self.financial_data.current_year

        missing_fields = []

        if current.net_income is None:
            missing_fields.append("net_income")

        if current.total_assets is None:
            missing_fields.append("total_assets")

        if current.cash is None:
            missing_fields.append("cash")

        if current.total_debt is None:
            missing_fields.append("total_debt")

        if missing_fields:
            self.warnings.append(
                ValidationWarning(
                    ValidationWarning.INFO,
                    "INCOMPLETE_DATA",
                    f"Missing optional fields: {', '.join(missing_fields)}. "
                    f"Providing complete financial data improves valuation accuracy.",
                    None,
                )
            )

    def get_confidence_penalty(self) -> Decimal:
        """
        Calculate confidence penalty based on validation warnings.

        Returns:
            Decimal between Decimal('0.0') and Decimal('1.0') representing confidence reduction
        """
        penalty = Decimal("0.0")

        for warning in self.warnings:
            if warning.severity == ValidationWarning.CRITICAL:
                penalty += Decimal("0.50")  # Major penalty
            elif warning.severity == ValidationWarning.ERROR:
                penalty += Decimal("0.30")  # Significant penalty
            elif warning.severity == ValidationWarning.WARNING:
                penalty += Decimal("0.10")  # Moderate penalty
            elif warning.severity == ValidationWarning.INFO:
                penalty += Decimal("0.02")  # Minor penalty

        return min(penalty, Decimal("0.80"))  # Cap at 80% penalty

    def _track_validation_report(self, is_valid: bool):
        """
        Track validation report for transparency.

        Converts ValidationWarnings into transparency ValidationChecks.
        """
        # Convert warnings to validation checks
        checks = []
        passed_count = 0
        warning_count = 0
        failed_count = 0

        # Group warnings by validation area
        validation_areas = {
            "EBITDA Margin": [
                "IMPOSSIBLE_EBITDA_MARGIN",
                "UNREALISTIC_EBITDA_MARGIN",
                "HIGH_EBITDA_MARGIN",
                "NEGATIVE_EBITDA_MARGIN",
            ],
            "Revenue": ["INVALID_REVENUE", "LOW_REVENUE", "UNREALISTIC_REVENUE"],
            "Growth Rates": ["EXTREME_GROWTH", "NEGATIVE_GROWTH", "INCONSISTENT_GROWTH"],
            "Financial Relationships": [
                "NEGATIVE_CASH",
                "DEBT_EXCEEDS_ASSETS",
                "MISSING_RELATIONSHIPS",
            ],
            "Data Completeness": ["INCOMPLETE_DATA"],
        }

        # Create check for each area
        for area, codes in validation_areas.items():
            area_warnings = [w for w in self.warnings if w.code in codes]

            if not area_warnings:
                # No warnings in this area - PASSED
                checks.append(
                    ValidationCheck(
                        check_name=f"{area} Check",
                        check_type="data_quality",
                        status="PASSED",
                        message=f"All {area.lower()} checks passed",
                        severity="LOW",
                    )
                )
                passed_count += 1
            else:
                # Has warnings - determine status based on severity
                most_severe = area_warnings[0]
                for w in area_warnings[1:]:
                    if w.severity == ValidationWarning.CRITICAL:
                        most_severe = w
                        break
                    elif (
                        w.severity == ValidationWarning.ERROR
                        and most_severe.severity != ValidationWarning.CRITICAL
                    ):
                        most_severe = w

                if most_severe.severity in [ValidationWarning.CRITICAL, ValidationWarning.ERROR]:
                    status = "FAILED"
                    failed_count += 1
                else:
                    status = "WARNING"
                    warning_count += 1

                checks.append(
                    ValidationCheck(
                        check_name=f"{area} Check",
                        check_type="data_quality",
                        status=status,
                        message=most_severe.message,
                        severity=most_severe.severity.upper(),
                        suggested_action=(
                            f"Review {area.lower()} data and ensure accuracy"
                            if status == "FAILED"
                            else None
                        ),
                    )
                )

        # Calculate overall score
        total_checks = len(checks)
        overall_score = int((passed_count / total_checks) * 100) if total_checks > 0 else 100

        # Create summary
        if is_valid and passed_count == total_checks:
            summary = "✅ All data quality checks passed. High confidence in valuation."
        elif failed_count > 0:
            summary = f"❌ {failed_count} critical issues detected. Please review and correct data."
        elif warning_count > 0:
            summary = f"⚠️ {warning_count} warnings detected. Valuation confidence may be reduced."
        else:
            summary = "✅ Data quality is good."

        # Track validation report
        self.transparency.set_validation_report(
            overall_score=overall_score, checks=checks, summary=summary
        )

    def format_warnings(self) -> str:
        """Format warnings as human-readable text."""
        if not self.warnings:
            return "✓ No validation warnings"

        lines = [f"\nValidation Warnings ({len(self.warnings)}):\n"]

        for warning in self.warnings:
            icon = {
                ValidationWarning.CRITICAL: "🛑",
                ValidationWarning.ERROR: "❌",
                ValidationWarning.WARNING: "⚠️",
                ValidationWarning.INFO: "ℹ️",
            }.get(warning.severity, "•")

            lines.append(f"{icon} [{warning.severity.upper()}] {warning.message}")

        return "\n".join(lines)


def validate_financial_inputs(
    financial_data: FinancialData,
) -> Tuple[bool, List[ValidationWarning]]:
    """
    Convenience function to validate financial inputs.

    Args:
        financial_data: Financial data to validate

    Returns:
        Tuple of (is_valid, warnings_list)
    """
    validator = FinancialInputValidator(financial_data)
    return validator.validate_all()
