"""
Financial Analysis Transformer

Builds the financial analysis section of the valuation report.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.infrastructure.exceptions import DataTransformationError
from src.services.infrastructure.translations import get_translations, normalize_report_locale
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.utils.filing_year_labels import format_year_column_with_filing_role
from src.utils.fiscal_year import get_current_filing_year

from .base_transformer import BaseTransformer

ReportData = Dict[str, Any]
ReportRows = List[ReportData]


class FinancialAnalysisTransformer(BaseTransformer):
    """Transformer for financial analysis section."""

    @staticmethod
    def _annotate_year_display_rows(
        rows: list,
        request: ValuationRequestProtocol,
    ) -> None:
        """Add year_display (Base / Base−n) for appendix tables; mutates rows in place."""
        if not rows:
            return
        numeric_years: list[int] = []
        for r in rows:
            y = r.get("year")
            try:
                numeric_years.append(int(y))
            except (TypeError, ValueError):
                continue
        if not numeric_years:
            return
        base = max(numeric_years)
        raw_loc = str(
            getattr(request, "language", None) or getattr(request, "locale", None) or "en"
        )
        _cc = str(getattr(request, "country_code", None) or "BE").strip().upper() or "BE"
        t = get_translations(normalize_report_locale(raw_loc), country_code=_cc)
        for r in rows:
            y = r.get("year")
            try:
                yi = int(y)
            except (TypeError, ValueError):
                r["year_display"] = str(y) if y is not None else ""
                continue
            r["year_display"] = format_year_column_with_filing_role(yi, base, t)

    def _build_growth_metrics(
        self,
        historical_performance: ReportRows,
        request: ValuationRequestProtocol,
    ) -> ReportData:
        """Revenue CAGR, YoY growth, and historical_growth rows for _growth_metrics.html."""
        if not historical_performance or len(historical_performance) < 2:
            return {"has_historical_data": False}

        parsed: ReportRows = []
        for r in historical_performance:
            y = r.get("year")
            rev = r.get("revenue")
            if y is None or rev is None:
                continue
            try:
                yi = int(y)
                rv = float(rev)
            except (TypeError, ValueError):
                continue
            parsed.append({"year": yi, "revenue": rv})

        if len(parsed) < 2:
            return {"has_historical_data": False}

        parsed.sort(key=lambda x: x["year"])
        y_first, y_last = parsed[0]["year"], parsed[-1]["year"]
        span_years = max(y_last - y_first, 1)
        r_start, r_end = parsed[0]["revenue"], parsed[-1]["revenue"]
        cagr: Optional[float] = None
        if r_start > 0:
            try:
                cagr = (r_end / r_start) ** (1.0 / span_years) - 1.0
            except (ArithmeticError, ValueError, OSError):
                cagr = None

        revenue_growth: Optional[float] = None
        if len(parsed) >= 2:
            rp, rl = parsed[-2]["revenue"], parsed[-1]["revenue"]
            if rp > 0:
                revenue_growth = (rl - rp) / rp

        desc = sorted(parsed, key=lambda x: x["year"], reverse=True)
        base = max(x["year"] for x in desc)
        raw_loc = str(
            getattr(request, "language", None) or getattr(request, "locale", None) or "en"
        )
        _cc = str(getattr(request, "country_code", None) or "BE").strip().upper() or "BE"
        t = get_translations(normalize_report_locale(raw_loc), country_code=_cc)

        historical_growth: ReportRows = []
        for i, row in enumerate(desc):
            y = row["year"]
            rev = row["revenue"]
            growth: Optional[float] = None
            if i + 1 < len(desc) and desc[i + 1]["revenue"] > 0:
                growth = (rev - desc[i + 1]["revenue"]) / desc[i + 1]["revenue"]
            historical_growth.append(
                {
                    "year": y,
                    "year_display": format_year_column_with_filing_role(y, base, t),
                    "revenue": rev,
                    "growth": growth,
                }
            )

        return {
            "has_historical_data": True,
            "cagr_3y": cagr,
            "revenue_growth": revenue_growth,
            "historical_growth": historical_growth,
        }

    def _ebitda_margin_percent(
        self,
        revenue,
        ebitda,
    ):
        if revenue is None or ebitda is None or revenue <= 0:
            return None

        ebitda_margin = self.safe_divide(ebitda, revenue, None)
        if ebitda_margin is None:
            return None
        return ebitda_margin * 100

    def _historical_performance_row(
        self,
        source,
        *,
        year,
        revenue,
        ebitda,
    ) -> ReportData:
        return {
            "year": year,
            "revenue": revenue,
            "ebitda": ebitda,
            "ebitda_margin": self._ebitda_margin_percent(revenue, ebitda),
            "net_income": getattr(source, "net_income", None),
        }

    def _build_historical_year_rows(
        self,
        request: ValuationRequestProtocol,
    ) -> ReportRows:
        rows: ReportRows = []
        if not request.historical_years_data:
            return rows

        for year_data in request.historical_years_data:
            try:
                revenue = getattr(year_data, "revenue", None)
                ebitda = getattr(year_data, "ebitda", None)
                rows.append(
                    self._historical_performance_row(
                        year_data,
                        year=getattr(year_data, "year", None),
                        revenue=revenue,
                        ebitda=ebitda,
                    )
                )
            except (AttributeError, TypeError, ValueError) as e:
                self.logger.warning(
                    "Error processing historical year data",
                    extra={
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "year": getattr(year_data, "year", "Unknown"),
                    },
                    exc_info=False,
                )
                continue
        return rows

    def _current_year_performance_fallback(
        self,
        request: ValuationRequestProtocol,
    ) -> Optional[ReportData]:
        if not request.current_year_data:
            return None

        try:
            current_year_data = request.current_year_data
            revenue = getattr(current_year_data, "revenue", None)
            ebitda = getattr(current_year_data, "ebitda", None)
            if revenue is None and ebitda is None:
                return None

            row = self._historical_performance_row(
                current_year_data,
                year=getattr(current_year_data, "year", 2024),
                revenue=revenue,
                ebitda=ebitda,
            )
            self.logger.info(
                "Used current_year_data as fallback for historical_performance",
                extra={"revenue": revenue, "ebitda": ebitda},
            )
            return row
        except Exception as e:
            self.logger.warning(f"Failed to use current_year_data fallback: {e}")
            return None

    def _legacy_financials_performance_fallback(
        self,
        request: ValuationRequestProtocol,
    ) -> Optional[ReportData]:
        if not hasattr(request, "financials") or not request.financials:
            return None

        try:
            financials = request.financials
            revenue = getattr(financials, "revenue", None)
            ebitda = getattr(financials, "ebitda", None)
            if revenue is None and ebitda is None:
                return None

            year = getattr(financials, "year", None)
            if year is None:
                year = get_current_filing_year()

            row = self._historical_performance_row(
                financials,
                year=year,
                revenue=revenue,
                ebitda=ebitda,
            )
            self.logger.info(
                "Used financials (legacy) as fallback for historical_performance",
                extra={"revenue": revenue, "ebitda": ebitda},
            )
            return row
        except Exception as e:
            self.logger.warning(f"Failed to use financials fallback: {e}")
            return None

    def _build_historical_performance(
        self,
        request: ValuationRequestProtocol,
    ) -> ReportRows:
        historical_performance = self._build_historical_year_rows(request)
        if historical_performance:
            return historical_performance

        current_year_row = self._current_year_performance_fallback(request)
        if current_year_row:
            return [current_year_row]

        legacy_financials_row = self._legacy_financials_performance_fallback(request)
        if legacy_financials_row:
            return [legacy_financials_row]

        return []

    @staticmethod
    def _current_ratio_assessment(current_ratio) -> str:
        return "Good" if current_ratio > 1.5 else "Adequate" if current_ratio > 1.0 else "Low"

    @staticmethod
    def _quick_ratio_assessment(quick_ratio) -> str:
        return "Good" if quick_ratio > 1.0 else "Adequate" if quick_ratio > 0.5 else "Low"

    @staticmethod
    def _debt_assessment(debt_to_equity) -> str:
        return "Low" if debt_to_equity < 0.5 else "Moderate" if debt_to_equity < 1.0 else "High"

    @staticmethod
    def _interest_coverage_assessment(interest_coverage) -> str:
        return (
            "Strong"
            if interest_coverage > 5.0
            else "Adequate" if interest_coverage > 2.0 else "Weak"
        )

    def _append_liquidity_metrics(
        self,
        financial_health: ReportData,
        metrics,
    ) -> None:
        liquidity_metrics = []
        if hasattr(metrics, "current_ratio") and metrics.current_ratio:
            current_ratio_assessment = self._current_ratio_assessment(metrics.current_ratio)
            liquidity_metrics.append(
                {
                    "metric": "Current Ratio",
                    "value": metrics.current_ratio,
                    "assessment": current_ratio_assessment,
                }
            )
            financial_health["current_ratio"] = metrics.current_ratio
            financial_health["current_ratio_assessment"] = current_ratio_assessment

        if hasattr(metrics, "quick_ratio") and metrics.quick_ratio:
            liquidity_metrics.append(
                {
                    "metric": "Quick Ratio",
                    "value": metrics.quick_ratio,
                    "assessment": self._quick_ratio_assessment(metrics.quick_ratio),
                }
            )

        if liquidity_metrics:
            financial_health["liquidity_metrics"] = liquidity_metrics

    def _append_solvency_metrics(
        self,
        financial_health: ReportData,
        metrics,
    ) -> None:
        solvency_metrics = []
        if hasattr(metrics, "debt_to_equity") and metrics.debt_to_equity is not None:
            debt_assessment = self._debt_assessment(metrics.debt_to_equity)
            solvency_metrics.append(
                {
                    "metric": "Debt to Equity",
                    "value": metrics.debt_to_equity,
                    "assessment": debt_assessment,
                }
            )
            financial_health["debt_to_equity"] = metrics.debt_to_equity
            financial_health["debt_assessment"] = debt_assessment

        if hasattr(metrics, "interest_coverage") and metrics.interest_coverage:
            solvency_metrics.append(
                {
                    "metric": "Interest Coverage",
                    "value": metrics.interest_coverage,
                    "assessment": self._interest_coverage_assessment(metrics.interest_coverage),
                }
            )

        if solvency_metrics:
            financial_health["solvency_metrics"] = solvency_metrics

    def _build_financial_health(
        self,
        response: ValuationResponseProtocol,
    ) -> ReportData:
        financial_health: ReportData = {}
        if not response.financial_metrics:
            return financial_health

        metrics = response.financial_metrics
        self._append_liquidity_metrics(financial_health, metrics)
        self._append_solvency_metrics(financial_health, metrics)
        return financial_health

    def _build_key_metrics(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
    ) -> ReportData:
        key_metrics: ReportData = {}
        if not response.multiples_valuation:
            return key_metrics

        ebitda_value = self.get_ebitda_value(response, request)
        if (
            ebitda_value is None
            or not request.current_year_data
            or not request.current_year_data.revenue
        ):
            return key_metrics

        key_metrics["revenue_growth"] = 0
        key_metrics["ebitda_margin"] = self.get_ebitda_margin(response, request)
        key_metrics["industry_revenue_growth"] = None
        key_metrics["industry_ebitda_margin"] = None
        key_metrics["roa"] = None
        key_metrics["industry_roa"] = None
        key_metrics["roe"] = None
        key_metrics["industry_roe"] = None
        return key_metrics

    @staticmethod
    def _risk_is_financial(risk) -> bool:
        risk_text = str(risk).lower()
        return any(
            token in risk_text
            for token in (
                "financial",
                "liquidity",
                "solvency",
                "cash",
                "revenue",
                "profit",
                "margin",
            )
        )

    @staticmethod
    def _has_declining_recent_revenue(historical_years_data) -> bool:
        if not historical_years_data or len(historical_years_data) < 2:
            return False

        years = sorted([yd.year for yd in historical_years_data], reverse=True)
        recent_revenue = next(
            (yd.revenue for yd in historical_years_data if yd.year == years[0]),
            None,
        )
        prior_revenue = next(
            (yd.revenue for yd in historical_years_data if yd.year == years[1]),
            None,
        )
        return (
            recent_revenue is not None
            and prior_revenue is not None
            and recent_revenue < prior_revenue
        )

    def _build_financial_warnings(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
    ) -> list:
        financial_warnings = []
        if hasattr(response, "risk_factors") and response.risk_factors:
            financial_warnings.extend(
                risk for risk in response.risk_factors if self._risk_is_financial(risk)
            )

        if (
            request.current_year_data
            and request.current_year_data.ebitda
            and request.current_year_data.ebitda < 0
        ):
            financial_warnings.append(
                "Negative EBITDA detected: Valuation relies on revenue multiples or asset-based approach."
            )

        if self._has_declining_recent_revenue(request.historical_years_data):
            financial_warnings.append("Declining revenue trend detected in recent period.")

        return financial_warnings

    def _build_result_payload(
        self,
        historical_performance: ReportRows,
        financial_health: ReportData,
        key_metrics: ReportData,
        financial_warnings: list,
        ebitda_normalization: Optional[ReportData],
        user_normalizations: Optional[list],
        request: ValuationRequestProtocol,
    ) -> ReportData:
        result = {
            "historical_performance": historical_performance,
            "financial_health": financial_health if financial_health else None,
            "key_metrics": key_metrics if key_metrics else None,
            "financial_warnings": financial_warnings if financial_warnings else None,
            "ebitda_normalization": ebitda_normalization,
            "user_normalizations": user_normalizations,
        }
        if historical_performance:
            result["growth_metrics"] = self._build_growth_metrics(
                historical_performance,
                request,
            )
        return result

    def transform(
        self, response: ValuationResponseProtocol, request: ValuationRequestProtocol
    ) -> ReportData:
        """
        Build financial analysis section.

        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context

        Returns:
            Dictionary with financial analysis data for template rendering

        Raises:
            MissingDataError: If required data is missing
            DataTransformationError: If transformation fails
        """
        # Validate inputs
        self._validate_inputs(response, request)

        self.logger.debug(
            "Building financial analysis section",
            extra={
                "company_name": response.company_name,
                "valuation_id": response.valuation_id,
                "has_historical_data": bool(request.historical_years_data),
            },
        )
        historical_performance = self._build_historical_performance(request)
        financial_health = self._build_financial_health(response)
        key_metrics = self._build_key_metrics(response, request)
        financial_warnings = self._build_financial_warnings(response, request)
        self._annotate_year_display_rows(historical_performance, request)

        # CRITICAL: Extract EBITDA normalization data from Step 2.5 (if available)
        # Academic requirement: ASA BVS-III, AICPA BVS-VII
        ebitda_normalization = self._extract_ebitda_normalization(response)

        # CRITICAL: Extract user-defined normalizations from request metadata
        user_normalizations = self._extract_user_normalizations(request, response)

        try:
            result = self._build_result_payload(
                historical_performance,
                financial_health,
                key_metrics,
                financial_warnings,
                ebitda_normalization,
                user_normalizations,
                request,
            )
            self.logger.debug(
                "Financial analysis section built successfully",
                extra={
                    "company_name": response.company_name,
                    "historical_years_count": len(historical_performance),
                    "has_financial_health": financial_health is not None,
                },
            )

            return result
        except (AttributeError, TypeError, KeyError, ValueError) as e:
            self.logger.error(
                "Error building financial analysis section",
                extra={
                    "company_name": getattr(response, "company_name", "Unknown"),
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise DataTransformationError(
                f"Failed to build financial analysis: {e}",
                company_name=getattr(response, "company_name", None),
            ) from e

    def _extract_ebitda_normalization(
        self, response: ValuationResponseProtocol
    ) -> Optional[ReportData]:
        """
        Extract EBITDA normalization data from Step 2.5 results.

        Args:
            response: Valuation response

        Returns:
            EBITDA normalization data for template, or None if not available
        """
        # Check if response has detailed_results with step results
        if not hasattr(response, "detailed_results") or not response.detailed_results:
            self.logger.debug(
                "No detailed_results available for EBITDA normalization extraction",
                extra={"component": "financial_analysis_transformer"},
            )
            return None

        step_results = response.detailed_results.get("step_results", {})

        # Look for Step 2.5 (Multiple Calibration)
        # Handle both integer key (2) and float key (2.5) - Python dict keys
        step_2_5 = None
        for key in [2.5, "2.5", 2]:
            if key in step_results:
                step_output = step_results[key]
                # Check if this is the normalization step
                if hasattr(step_output, "result") and "normalized_ebitda" in step_output.result:
                    step_2_5 = step_output.result
                    break

        if not step_2_5:
            self.logger.debug(
                "Step 2.5 Multiple Calibration not found in step_results",
                extra={
                    "available_steps": list(step_results.keys()),
                    "note": "Normalization may not have been executed",
                },
            )
            return None

        # Extract normalization data
        try:
            normalization_data = {
                "reported_ebitda": step_2_5.get("reported_ebitda"),
                "normalized_ebitda": step_2_5.get("normalized_ebitda"),
                "total_adjustments": step_2_5.get("total_adjustments"),
                "adjustment_percentage": step_2_5.get("adjustment_percentage"),
                "adjustments": step_2_5.get("adjustments", []),
                "year": step_2_5.get("year", 2025),
                "confidence": step_2_5.get("confidence_score", "Medium"),
                "rationale": step_2_5.get("rationale"),
                "margin_analysis": step_2_5.get("margin_analysis"),  # NEW: Quality of Earnings data
            }

            self.logger.info(
                "✅ EBITDA normalization data extracted from Step 2.5",
                extra={
                    "reported_ebitda": normalization_data["reported_ebitda"],
                    "normalized_ebitda": normalization_data["normalized_ebitda"],
                    "total_adjustments": normalization_data["total_adjustments"],
                    "num_adjustments": len(normalization_data["adjustments"]),
                },
            )

            return normalization_data

        except (KeyError, AttributeError, TypeError) as e:
            self.logger.warning(
                "Error extracting EBITDA normalization data",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                exc_info=False,
            )
            return None

    def _extract_user_normalizations(
        self, request: ValuationRequestProtocol, response: ValuationResponseProtocol
    ) -> Optional[list]:
        """
        Extract user-defined EBITDA normalizations from request.

        User normalizations are passed in the request when a user has manually
        adjusted EBITDA values. The metadata includes reported EBITDA, adjustments,
        and confidence scores.

        Args:
            request: Valuation request with ebitda_normalization_metadata
            response: Valuation response for context

        Returns:
            List of user normalization objects for template, or None if not available
        """
        user_normalizations = []

        try:
            # Check current year data
            if hasattr(request, "current_year_data") and request.current_year_data:
                current_data = request.current_year_data
                if hasattr(current_data, "ebitda_normalized") and current_data.ebitda_normalized:
                    metadata = getattr(current_data, "ebitda_normalization_metadata", {})
                    if metadata:
                        raw_adjustments = metadata.get("adjustments", [])
                        normalization = {
                            "year": current_data.year,
                            "reported_ebitda": metadata.get("reported_ebitda", current_data.ebitda),
                            "normalized_ebitda": metadata.get(
                                "normalized_ebitda", current_data.ebitda
                            ),
                            "total_adjustments": metadata.get("total_adjustments", 0),
                            "adjustment_count": metadata.get("adjustment_count", 0),
                            "confidence_score": metadata.get("confidence_score", "medium"),
                            "has_custom_adjustments": metadata.get("has_custom_adjustments", False),
                            "adjustments": self._enrich_adjustment_labels(raw_adjustments),
                            "custom_adjustments": metadata.get("custom_adjustments", []),
                            "updated_at": metadata.get("updated_at"),
                        }
                        user_normalizations.append(normalization)

                        self.logger.info(
                            "✅ User normalization detected for current year",
                            extra={
                                "year": normalization["year"],
                                "reported_ebitda": normalization["reported_ebitda"],
                                "normalized_ebitda": normalization["normalized_ebitda"],
                                "total_adjustments": normalization["total_adjustments"],
                            },
                        )

            # Check historical years data
            if hasattr(request, "historical_years_data") and request.historical_years_data:
                for year_data in request.historical_years_data:
                    if hasattr(year_data, "ebitda_normalized") and year_data.ebitda_normalized:
                        metadata = getattr(year_data, "ebitda_normalization_metadata", {})
                        if metadata:
                            raw_adjustments = metadata.get("adjustments", [])
                            normalization = {
                                "year": year_data.year,
                                "reported_ebitda": metadata.get(
                                    "reported_ebitda", year_data.ebitda
                                ),
                                "normalized_ebitda": metadata.get(
                                    "normalized_ebitda", year_data.ebitda
                                ),
                                "total_adjustments": metadata.get("total_adjustments", 0),
                                "adjustment_count": metadata.get("adjustment_count", 0),
                                "confidence_score": metadata.get("confidence_score", "medium"),
                                "has_custom_adjustments": metadata.get(
                                    "has_custom_adjustments", False
                                ),
                                "adjustments": self._enrich_adjustment_labels(raw_adjustments),
                                "custom_adjustments": metadata.get("custom_adjustments", []),
                                "updated_at": metadata.get("updated_at"),
                            }
                            user_normalizations.append(normalization)

                            self.logger.info(
                                "✅ User normalization detected for historical year",
                                extra={
                                    "year": normalization["year"],
                                    "reported_ebitda": normalization["reported_ebitda"],
                                    "normalized_ebitda": normalization["normalized_ebitda"],
                                    "total_adjustments": normalization["total_adjustments"],
                                },
                            )

            if user_normalizations:
                self.logger.info(
                    "✅ User normalizations extracted successfully",
                    extra={
                        "company_name": (
                            response.company_name
                            if hasattr(response, "company_name")
                            else "Unknown"
                        ),
                        "normalization_count": len(user_normalizations),
                        "years": [n["year"] for n in user_normalizations],
                    },
                )
                return user_normalizations
            else:
                self.logger.debug(
                    "No user normalizations found in request",
                    extra={"component": "financial_analysis_transformer"},
                )
                return None

        except (AttributeError, TypeError, KeyError) as e:
            self.logger.warning(
                "Error extracting user normalizations",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                exc_info=False,
            )
            return None

    _CATEGORY_LABELS = {
        "owner_compensation_adjustment": "Owner Compensation",
        "salary": "Owner Compensation",
        "one_time_expenses": "Non-Recurring",
        "non_recurring_revenue": "Non-Recurring Revenue",
        "non_recurring_costs": "Non-Recurring Costs",
        "personal_expenses": "Personal Expenses",
        "family_expenses": "Family Expenses",
        "related_party_transactions": "Related Party",
        "depreciation_adjustment": "Depreciation",
        "tax_optimization_reversal": "Tax Optimization",
        "discretionary_expenses": "Discretionary",
        "unusual_transactions": "Unusual Items",
        "accounting": "Accounting",
        "other_adjustments": "Other",
        "real_estate_carve_out": "Real Estate",
        "custom_adjustment": "Custom",
    }

    def _enrich_adjustment_labels(self, raw_adjustments: list) -> list:
        """Add category_label to each adjustment for the Jinja template."""
        if not isinstance(raw_adjustments, list):
            return []
        enriched = []
        for adj in raw_adjustments:
            if not isinstance(adj, dict):
                continue
            cat = adj.get("category", "")
            enriched.append(
                {
                    **adj,
                    "category_label": self._CATEGORY_LABELS.get(
                        cat, cat.replace("_", " ").title() if cat else "Other"
                    ),
                }
            )
        return enriched
