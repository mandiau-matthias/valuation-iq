"""
Business Logic Validator

This module provides validation of business logic constraints before expensive
valuation calculations are performed. It ensures data consistency and catches
invalid inputs at the API boundary.

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.api.routes.valuation.business_logic_numeric_bounds import validate_numeric_bounds
from src.api.schemas import ValuationRequest, YearDataInput
from src.utils.decimal_helpers import to_decimal
from src.utils.fiscal_year import get_current_filing_year, get_max_confirmable_year

logger = logging.getLogger(__name__)


class ValidationError(BaseModel):
    """Validation error details"""

    field: str
    message: str
    value: Optional[Any] = None
    constraint: Optional[str] = None


class BusinessLogicValidator:
    """
    Validates business logic constraints on valuation requests.

    This validator ensures that the data passes basic business logic checks
    before expensive calculations are performed. It prevents:

    - Impossible financial relationships (e.g., EBITDA > Revenue)
    - Out-of-bound values (e.g., negative employee counts)
    - Inconsistent data (e.g., historical years in the future)
    - Circular dependencies and contradictions

    All validations are based on accounting principles and business logic,
    not just schema validation.

    Benchmark Priority (when Titan enrichment is available):
    1. Titan-provided industry_benchmarks (from Delphi/business_types DB) - HIGHEST
    2. Generic default benchmarks (fallback)
    """

    def __init__(self, titan_benchmarks: Optional[Dict[str, Any]] = None):
        """
        Initialize the business logic validator.

        Args:
            titan_benchmarks: Optional Titan-provided industry_benchmarks from Delphi/business_types DB.
                             Contains typical_ebitda_margin, typical_revenue, typical_employee_count.
        """
        self.titan_benchmarks = titan_benchmarks
        # Pass-8: structured "must-disclose" integrity warnings produced as a
        # side effect of validation. Callers should drain this list via
        # ``consume_integrity_warnings()`` after each validate() call so the
        # warnings reach ``detailed_results["data_quality_warnings"]``.
        self._pending_integrity_warnings: List[Dict[str, Any]] = []

    def validate(
        self,
        request: ValuationRequest,
        titan_benchmarks: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationError]:
        """
        Validate a valuation request for business logic consistency.

        Args:
            request: Valuation request to validate
            titan_benchmarks: Optional Titan-provided industry_benchmarks for this request.
                             Overrides constructor-provided benchmarks if provided.

        Returns:
            List of validation errors (empty if valid)
        """
        errors, integrity_warnings = self.validate_with_integrity_warnings(
            request,
            titan_benchmarks=titan_benchmarks,
        )
        self._pending_integrity_warnings = list(integrity_warnings)
        return errors

    def validate_with_integrity_warnings(
        self,
        request: ValuationRequest,
        titan_benchmarks: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[ValidationError], List[Dict[str, Any]]]:
        """Validate and return request-scoped integrity warnings without shared-state handoff."""
        effective_titan_benchmarks = (
            titan_benchmarks if titan_benchmarks is not None else self.titan_benchmarks
        )
        integrity_warnings: List[Dict[str, Any]] = []

        errors = []

        # Financial data validations
        errors.extend(self._validate_financial_relationships(request))
        errors.extend(self._validate_ebitda_margin(request))
        errors.extend(self._validate_growth_rates(request))

        # Balance sheet validations
        if request.current_year_data:
            errors.extend(self._validate_balance_sheet(request.current_year_data))

        # Historical data validations
        if request.historical_years_data:
            explicit_current_year = getattr(
                getattr(request, "current_year_data", None), "year", None
            )
            try:
                effective_current_year = min(int(explicit_current_year), get_max_confirmable_year())
            except (TypeError, ValueError):
                effective_current_year = get_current_filing_year()
            errors.extend(
                self._validate_historical_data(
                    request.historical_years_data,
                    effective_current_year,
                )
            )

        # Ownership validations
        errors.extend(self._validate_ownership_data(request))

        # Employee validations
        errors.extend(self._validate_employee_data(request, effective_titan_benchmarks))

        # Numeric bounds validations
        errors.extend(self._validate_numeric_bounds(request))

        # Titan benchmark validations (warnings for deviations from industry norms)
        errors.extend(self._validate_titan_benchmarks(request, effective_titan_benchmarks))

        # Non-blocking integrity scan: flag any year with EBITDA margin ≥ 100%.
        # The current-year hard check above already blocks the request, so this
        # primarily catches historical years (which today pass _validate_historical_data
        # without margin guards). Impossible historical margins still feed the
        # multi-year display and the McKinsey weighting window — silently
        # accepting them is a defensibility leak.
        try:
            self._scan_impossible_margins(request, integrity_warnings)
        except Exception as scan_error:  # pragma: no cover - defensive
            logger.warning(
                "impossible-margin scan failed (non-blocking)",
                extra={"error": str(scan_error), "error_type": type(scan_error).__name__},
            )

        return errors, integrity_warnings

    def _scan_impossible_margins(
        self,
        request: ValuationRequest,
        integrity_warnings: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Append an integrity warning for any year with normalized EBITDA ≥ revenue.

        Pushes onto ``integrity_warnings`` rather than returning a
        ValidationError — historical-year impossibilities are common in legacy
        data (carve-outs, restated periods, entity-composition changes) and we
        do not want a hard 422 to block the entire valuation. The report and
        the EngineCoPilot rail surface the warning instead.

        The McKinsey weighting window is the top 3 most recent years, so we
        flag whether the impossible year sits inside that window — a year that
        feeds the multiple is materially worse than one that doesn't.
        """
        from src.domain.report_integrity import build_impossible_margin_warning

        if integrity_warnings is None:
            integrity_warnings = self._pending_integrity_warnings

        years_for_window: List[Any] = []
        current = getattr(request, "current_year_data", None)
        if current is not None:
            years_for_window.append(current)
        historical = getattr(request, "historical_years_data", None) or []
        years_for_window.extend(historical)

        def _year_of(y: Any) -> int:
            try:
                return int(getattr(y, "year", 0) or 0)
            except (TypeError, ValueError):
                return 0

        sorted_years = sorted(years_for_window, key=_year_of, reverse=True)
        weighted_year_set = {_year_of(y) for y in sorted_years[:3] if _year_of(y) > 0}

        def _check(year_obj: Any) -> None:
            ebitda = getattr(year_obj, "ebitda", None)
            revenue = getattr(year_obj, "revenue", None)
            year = _year_of(year_obj)
            if ebitda is None or revenue is None or year == 0:
                return
            try:
                rev_d = to_decimal(revenue)
                ebitda_d = to_decimal(ebitda)
            except (TypeError, ValueError):
                return
            if rev_d <= 0:
                return
            margin = ebitda_d / rev_d
            if margin < Decimal("1.0"):
                return
            logger.warning(
                f"[IMPOSSIBLE-MARGIN] FY{year} EBITDA margin {float(margin):.1%} ≥ 100%",
                extra={
                    "company_name": getattr(request, "company_name", None),
                    "year": year,
                    "ebitda": float(ebitda_d),
                    "revenue": float(rev_d),
                    "margin_pct": float(margin * 100),
                    "is_weighted_year": year in weighted_year_set,
                },
            )
            integrity_warnings.append(
                build_impossible_margin_warning(
                    year=year,
                    ebitda=float(ebitda_d),
                    revenue=float(rev_d),
                    margin_pct=float(margin * 100),
                    is_weighted=year in weighted_year_set,
                )
            )

        if current is not None:
            _check(current)
        for y in historical:
            _check(y)

    def _validate_financial_relationships(self, request: ValuationRequest) -> List[ValidationError]:
        """
        Validate financial relationships (e.g., EBITDA cannot exceed Revenue).

        Args:
            request: Valuation request

        Returns:
            List of validation errors
        """
        errors = []

        if not request.current_year_data:
            return errors

        current_data = request.current_year_data
        revenue = current_data.revenue
        ebitda = current_data.ebitda
        net_income = getattr(current_data, "net_income", None)

        # EBITDA cannot exceed Revenue
        if revenue is not None and ebitda is not None:
            if ebitda > revenue:
                errors.append(
                    ValidationError(
                        field="current_year_data.ebitda",
                        message=f"EBITDA (€{ebitda:,.0f}) cannot exceed Revenue (€{revenue:,.0f})",
                        value=ebitda,
                        constraint="EBITDA <= Revenue",
                    )
                )

        # Net Income cannot exceed EBITDA (unless EBITDA is negative)
        if ebitda is not None and net_income is not None and ebitda > 0:
            if net_income > ebitda:
                errors.append(
                    ValidationError(
                        field="current_year_data.net_income",
                        message=f"Net Income (€{net_income:,.0f}) cannot exceed EBITDA (€{ebitda:,.0f})",
                        value=net_income,
                        constraint="Net Income <= EBITDA (when EBITDA > 0)",
                    )
                )

        # Revenue must be positive or zero (cannot be negative)
        if revenue is not None and revenue < 0:
            errors.append(
                ValidationError(
                    field="current_year_data.revenue",
                    message=f"Revenue cannot be negative (€{revenue:,.0f})",
                    value=revenue,
                    constraint="Revenue >= 0",
                )
            )

        return errors

    def _validate_ebitda_margin(self, request: ValuationRequest) -> List[ValidationError]:
        """
        Validate EBITDA margin is within realistic bounds.

        Args:
            request: Valuation request

        Returns:
            List of validation errors
        """
        errors = []

        if not request.current_year_data:
            return errors

        current_data = request.current_year_data
        revenue = current_data.revenue
        ebitda = current_data.ebitda

        if revenue is not None and ebitda is not None and revenue > 0:
            margin = ebitda / revenue

            # EBITDA margin must be between -100% and +100%
            # (Anything outside this range is likely a data entry error)
            if margin < -Decimal("1.0") or margin > 1.0:
                errors.append(
                    ValidationError(
                        field="current_year_data.ebitda",
                        message=f"EBITDA margin ({margin * 100:.1f}%) is outside realistic bounds (-100% to +100%). Please verify your financial data.",
                        value=ebitda,
                        constraint="-100% <= EBITDA/Revenue <= +100%",
                    )
                )

        return errors

    def _validate_growth_rates(self, request: ValuationRequest) -> List[ValidationError]:
        """
        Validate growth rates are realistic.

        Args:
            request: Valuation request

        Returns:
            List of validation errors
        """
        errors = []

        # Validate historical growth if we have historical data
        if request.historical_years_data and len(request.historical_years_data) >= 2:
            historical = sorted(request.historical_years_data, key=lambda x: x.year)

            for i in range(1, len(historical)):
                prev_year = historical[i - 1]
                curr_year = historical[i]

                if prev_year.revenue and curr_year.revenue and prev_year.revenue > 0:
                    growth_rate = (curr_year.revenue - prev_year.revenue) / prev_year.revenue

                    # Growth rates outside -90% to +2000% are likely errors
                    # Increased upper bound to 2000% to allow for legitimate startup/early-stage growth
                    # Lower bound at -90% to allow for significant but recoverable declines
                    if growth_rate < -Decimal("0.90") or growth_rate > 20.0:
                        errors.append(
                            ValidationError(
                                field=f"historical_years_data[{i}].revenue",
                                message=f"Revenue growth rate from {prev_year.year} to {curr_year.year} is {growth_rate * 100:.1f}%, which is outside realistic bounds (-90% to +2000%). Please verify your data.",
                                value=curr_year.revenue,
                                constraint="-90% <= Growth Rate <= +2000%",
                            )
                        )

        return errors

    def _validate_balance_sheet(self, year_data: YearDataInput) -> List[ValidationError]:
        """
        Validate balance sheet equation: Assets = Liabilities + Equity.

        Args:
            year_data: Year data to validate

        Returns:
            List of validation errors
        """
        errors = []

        total_assets = getattr(year_data, "total_assets", None)
        total_liabilities = getattr(year_data, "total_liabilities", None)
        total_debt = getattr(year_data, "total_debt", None)
        total_equity = getattr(year_data, "total_equity", None)

        # Allow 1% tolerance for rounding differences (1% or €1,000, whichever is larger).
        def _tolerance() -> Decimal:
            return max(abs(total_assets) * Decimal("0.01"), 1000)

        if total_assets is not None and total_equity is not None:
            if total_liabilities is not None:
                # The full accounting identity is only assertable when we know ALL
                # liabilities. Hermes maps `total_liabilities` EXCLUSIVE of equity
                # (verified on every connected client: liabilities + equity == assets
                # to the euro). Belgian filings and hand-typed forms, however, often
                # mean "totaal passiva" — which already INCLUDES equity and therefore
                # equals total assets. That is a convention, not an imbalance: accept
                # it rather than 422 a correctly filled balance sheet.
                liabilities_is_passiva_total = (
                    abs(total_liabilities - total_assets) <= _tolerance()
                )
                liabilities_and_equity = (
                    total_liabilities
                    if liabilities_is_passiva_total
                    else total_liabilities + total_equity
                )
                difference = abs(total_assets - liabilities_and_equity)

                if difference > _tolerance():
                    errors.append(
                        ValidationError(
                            field="current_year_data.balance_sheet",
                            message=f"Balance sheet does not balance: Assets (€{total_assets:,.0f}) ≠ Liabilities + Equity (€{liabilities_and_equity:,.0f}). Difference: €{difference:,.0f}",
                            value=None,
                            constraint="Assets = Liabilities + Equity (±1% tolerance)",
                        )
                    )
            elif total_debt is not None:
                # Only interest-bearing debt is known. Debt is a SUBSET of liabilities,
                # so `debt + equity` is expected to fall SHORT of assets by exactly the
                # non-financial liabilities — trade payables, accruals, provisions, tax
                # payable. That shortfall is a normal balance sheet, not a defect: a
                # debt-free wholesaler funded by supplier credit is the common case.
                # Only the impossible direction is an error — the funded side cannot
                # exceed what it funds.
                funded = total_debt + total_equity
                excess = funded - total_assets

                if excess > _tolerance():
                    errors.append(
                        ValidationError(
                            field="current_year_data.balance_sheet",
                            message=f"Balance sheet is impossible: interest-bearing debt + equity (€{funded:,.0f}) exceeds total assets (€{total_assets:,.0f}) by €{excess:,.0f}.",
                            value=None,
                            constraint="Debt + Equity <= Assets (±1% tolerance)",
                        )
                    )

        # Debt cannot be negative
        if total_debt is not None and total_debt < 0:
            errors.append(
                ValidationError(
                    field="current_year_data.total_debt",
                    message=f"Total debt cannot be negative (€{total_debt:,.0f})",
                    value=total_debt,
                    constraint="Total Debt >= 0",
                )
            )

        # Assets cannot be negative
        if total_assets is not None and total_assets < 0:
            errors.append(
                ValidationError(
                    field="current_year_data.total_assets",
                    message=f"Total assets cannot be negative (€{total_assets:,.0f})",
                    value=total_assets,
                    constraint="Total Assets >= 0",
                )
            )

        return errors

    def _validate_historical_data(
        self,
        historical_data: List[YearDataInput],
        current_year: int | None = None,
    ) -> List[ValidationError]:
        """
        Validate historical data years are in the past and unique.

        Args:
            historical_data: List of historical year data

        Returns:
            List of validation errors
        """
        errors = []

        current_year = current_year or get_current_filing_year()
        years_seen = set()

        for idx, year_data in enumerate(historical_data):
            year = year_data.year

            # Year must be in the past
            if year >= current_year:
                errors.append(
                    ValidationError(
                        field=f"historical_years_data[{idx}].year",
                        message=f"Historical year {year} cannot be in the present or future (current year: {current_year})",
                        value=year,
                        constraint=f"Year < {current_year}",
                    )
                )

            # Year must be unique
            if year in years_seen:
                errors.append(
                    ValidationError(
                        field=f"historical_years_data[{idx}].year",
                        message=f"Duplicate historical year: {year} appears multiple times",
                        value=year,
                        constraint="Each year must be unique",
                    )
                )

            years_seen.add(year)

        return errors

    def _validate_ownership_data(self, request: ValuationRequest) -> List[ValidationError]:
        """
        Validate ownership-related data.

        Args:
            request: Valuation request

        Returns:
            List of validation errors
        """
        errors = []

        num_owners = getattr(request, "number_of_owners", None)
        num_employees = getattr(request, "number_of_employees", None)

        # Number of owners must be at least 1
        if num_owners is not None and num_owners < 1:
            errors.append(
                ValidationError(
                    field="number_of_owners",
                    message=f"Number of owners must be at least 1 (got {num_owners})",
                    value=num_owners,
                    constraint="Number of Owners >= 1",
                )
            )

        # Owners cannot exceed owners + employees (sanity check)
        if num_owners is not None and num_employees is not None:
            total_people = num_owners + num_employees
            if num_owners > total_people and total_people > 0:
                errors.append(
                    ValidationError(
                        field="number_of_owners",
                        message=f"Number of owners ({num_owners}) cannot exceed total people (owners + employees = {total_people})",
                        value=num_owners,
                        constraint="Owners <= Owners + Employees",
                    )
                )

        return errors

    def _validate_employee_data(
        self,
        request: ValuationRequest,
        titan_benchmarks: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationError]:
        """
        Validate employee-related data using Titan benchmarks when available.

        Args:
            request: Valuation request

        Returns:
            List of validation errors
        """
        errors = []

        num_employees = getattr(request, "number_of_employees", None)

        # Number of employees cannot be negative
        if num_employees is not None and num_employees < 0:
            errors.append(
                ValidationError(
                    field="number_of_employees",
                    message=f"Number of employees cannot be negative (got {num_employees})",
                    value=num_employees,
                    constraint="Number of Employees >= 0",
                )
            )

        # Titan-provided benchmark validation
        if num_employees is not None and num_employees >= 0 and titan_benchmarks:
            typical_employee = titan_benchmarks.get("typical_employee_count") or {}
            benchmark_max = typical_employee.get("max")
            benchmark_median = typical_employee.get("median")

            # Warn if employee count significantly exceeds typical maximum for this business type
            if benchmark_max is not None and num_employees > int(benchmark_max) * 5:
                errors.append(
                    ValidationError(
                        field="number_of_employees",
                        message=f"Employee count ({num_employees:,}) is significantly higher than typical for this business type (max typical: {int(benchmark_max):,}). This may indicate a larger enterprise.",
                        value=num_employees,
                        constraint=f"Typical max employees for business type: {int(benchmark_max):,}",
                    )
                )

            # Info: compare to median
            if benchmark_median is not None and num_employees > int(benchmark_median) * 10:
                # Very different from median - informational only
                pass  # Don't add error, just log could happen here

        return errors

    def _validate_numeric_bounds(self, request: ValuationRequest) -> List[ValidationError]:
        """Validate numeric values are within reasonable bounds to prevent DoS."""
        return validate_numeric_bounds(request, ValidationError)

    def _validate_titan_benchmarks(
        self,
        request: ValuationRequest,
        titan_benchmarks: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationError]:
        """
        Validate request data against Titan-provided industry benchmarks.

        IMPORTANT: These are INFORMATIONAL validations only - they should NOT block valuations.
        Atypical margins and revenues are common in real businesses and should result in
        confidence score adjustments, not validation failures.

        ✅ FIX (2026-01-22): Changed from returning errors to logging warnings only.
        Previously, this method was returning ValidationErrors that caused 422 responses,
        blocking valuations for legitimate businesses with atypical financial profiles.

        The EBITDA-margin comparison is deliberately NOT made here. Step 2 owns
        it: it grades the sector band's provenance and measures the margin on
        the same earnings basis as ``financial_metrics.ebitda_margin``, then
        emits both the graded ``industry_margin_deviation`` and, for a measured
        band only, the must-disclose ``ebitda_benchmark_deviation``. This
        pre-validation pass sees only raw current-year figures and cannot tell a
        measured band from a derived one, so a second comparison here produced a
        rival margin and a Page-1 flag that contradicted Step 2.

        Args:
            request: Valuation request

        Returns:
            Empty list - benchmark deviations are warnings, not errors
        """
        # ✅ FIX: Return empty list - benchmark deviations should NOT cause 422
        # These checks now only log warnings for monitoring, they don't block valuations

        # Skip if no Titan benchmarks available
        if not titan_benchmarks:
            return []

        if not request.current_year_data:
            return []

        current_data = request.current_year_data
        revenue = current_data.revenue

        # =================================================================
        # REVENUE COMPARISON vs Titan industry benchmarks (WARNING ONLY)
        # =================================================================
        if revenue is not None and revenue > 0:
            typical_revenue = titan_benchmarks.get("typical_revenue") or {}

            if typical_revenue:
                benchmark_min = typical_revenue.get("min")
                benchmark_max = typical_revenue.get("max")

                # Log warning if revenue is below typical minimum
                if benchmark_min is not None:
                    min_revenue = to_decimal(benchmark_min)
                    if revenue < min_revenue:
                        logger.info(
                            f"[BENCHMARK-INFO] Revenue below typical minimum: €{revenue:,.0f} < €{min_revenue:,.0f}",
                            extra={
                                "company_name": request.company_name,
                                "revenue": float(revenue),
                                "min_typical": float(min_revenue),
                            },
                        )

                # Log warning if revenue is way above typical maximum
                if benchmark_max is not None:
                    max_revenue = to_decimal(benchmark_max)
                    if revenue > max_revenue * Decimal("3"):
                        logger.info(
                            f"[BENCHMARK-INFO] Revenue significantly above typical: €{revenue:,.0f} > €{max_revenue:,.0f} * 3",
                            extra={
                                "company_name": request.company_name,
                                "revenue": float(revenue),
                                "max_typical": float(max_revenue),
                            },
                        )

        # ✅ FIX: Return empty list - benchmark deviations are informational, not blocking
        return []

    def consume_integrity_warnings(self) -> List[Dict[str, Any]]:
        """Drain integrity warnings produced by the most recent validate() pass.

        The orchestrator should call this after running ``validate`` and push
        the result into ``detailed_results["data_quality_warnings"]`` so the
        benchmark deviation (and any other validator-side integrity flags)
        reach the PDF instead of being swallowed by the log layer.

        Drains-on-read so a misuse pattern of multiple consumes returns an
        empty list rather than duplicating warnings.
        """
        warnings = self._pending_integrity_warnings
        self._pending_integrity_warnings = []
        return warnings

    def is_valid(self, request: ValuationRequest) -> bool:
        """
        Check if a request is valid (no validation errors).

        Args:
            request: Valuation request

        Returns:
            True if valid, False otherwise
        """
        errors = self.validate(request)
        return len(errors) == 0

    def get_error_summary(self, errors: List[ValidationError]) -> Dict[str, Any]:
        """
        Get a summary of validation errors for API response.

        Args:
            errors: List of validation errors

        Returns:
            Error summary dictionary
        """
        return {
            "error": "Business logic validation failed",
            "total_errors": len(errors),
            "errors": [
                {
                    "field": error.field,
                    "message": error.message,
                    "value": error.value,
                    "constraint": error.constraint,
                }
                for error in errors
            ],
            "hint": "Please review your input data for inconsistencies and impossible values",
        }


# ==================== EXPORT ====================

__all__ = ["BusinessLogicValidator", "ValidationError"]
