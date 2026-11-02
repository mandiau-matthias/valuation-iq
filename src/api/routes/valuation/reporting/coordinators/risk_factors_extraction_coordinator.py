"""
Risk Factors Extraction Coordinator

Handles risk factors extraction logic.
Extracted from summary_generator.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive risk factors extraction
- Detailed logging
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.schemas import ValuationRequest
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RiskFactorsExtractionCoordinator:
    """
    Coordinates risk factors extraction logic.
    
    Responsibilities:
    - Extract risk factors from synthesizer data
    - Extract risk factors from methodology divergence
    - Extract risk factors from financial metrics
    - Extract risk factors from request data
    - Generate fallback risk factors
    - Ensure at least one risk factor is always returned
    """
    
    def __init__(self, logger_instance=None):
        """
        Initialize risk factors extraction coordinator.
        
        Args:
            logger_instance: Logger instance (optional)
        """
        self.logger = logger_instance or logger

    @staticmethod
    def _as_decimal(value: Any) -> Optional[Decimal]:
        if value is None or isinstance(value, bool):
            return None
        try:
            return value if isinstance(value, Decimal) else Decimal(str(value))
        except (ArithmeticError, TypeError, ValueError):
            return None
    
    def extract_risk_factors(self, request: ValuationRequest, results: Dict[str, Any]) -> List[str]:
        """
        Extract risk factors.

        Priority:
        1. Use synthesizer data if available (quantitative, sophisticated)
        2. Calculate from financial metrics and methodology divergence (quantitative)
        3. Fallback to basic logic (quantitative where possible)

        Args:
            request: Valuation request
            results: Valuation results

        Returns:
            List of risk factor descriptions
        """
        try:
            # DEBUG: lifecycle breadcrumb. Dropped the ⚠️ emoji — extracting
            # risk factors is a normal-flow operation, not a warning. The
            # "Extracted N risk factors" exit log carries the summary.
            self.logger.debug("Extracting risk factors")

            # PRIORITY 1: Check for synthesizer data
            synthesizer_risks = self._extract_risks_from_synthesizer(results)
            if synthesizer_risks:
                return synthesizer_risks

            risks = []

            # PRIORITY 2: Calculate from financial metrics and methodology divergence
            financial_metrics = results.get("financial_metrics")
            dcf_valuation = results.get("dcf_valuation")
            multiples_valuation = results.get("multiples_valuation")

            # Methodology divergence
            risks.extend(
                self._extract_risks_from_methodology_divergence(dcf_valuation, multiples_valuation)
            )

            # Financial metrics
            if financial_metrics:
                risks.extend(self._extract_risks_from_financial_metrics(financial_metrics))

            # PRIORITY 3: Deterministic extraction from request data
            if len(risks) == 0:
                self.logger.debug("Using deterministic risk factor extraction")
                risks.extend(self._extract_risks_from_request_data(request))

            # CRITICAL FIX: Ensure at least 1 risk factor is always generated
            if len(risks) == 0:
                risks = self._generate_fallback_risk_factors(request, results)
                self.logger.info(
                    "✅ Generated fallback risk factors", extra={"fallback_risk_count": len(risks)}
                )

            self.logger.info(
                f"✅ Extracted {len(risks)} risk factors",
                extra={
                    "risk_count": len(risks),
                    "source": (
                        "synthesizer"
                        if synthesizer_risks
                        else (
                            "financial_metrics"
                            if financial_metrics
                            else (
                                "fallback"
                                if len(risks) > 0
                                and risks[0].startswith("Small company")
                                or "limited" in risks[0].lower()
                                else "request_data"
                            )
                        )
                    ),
                },
            )

            return risks[:5]  # Return top 5

        except Exception as e:
            self.logger.error(
                f"❌ Risk factor extraction failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return self._generate_fallback_risk_factors(request, results)
    
    def _extract_risks_from_synthesizer(self, results: Dict[str, Any]) -> Optional[List[str]]:
        """
        Extract risk factors from synthesizer data (Priority 1).

        Args:
            results: Valuation results

        Returns:
            List of risk factors if found, None otherwise
        """
        synthesized_valuation = results.get("synthesized_valuation")
        if not synthesized_valuation:
            return None

        # Check if it's an object with risk_factors attribute
        if hasattr(synthesized_valuation, "risk_factors"):
            risks = synthesized_valuation.risk_factors
            if risks and len(risks) > 0:
                self.logger.info(f"✅ Using synthesizer risk factors ({len(risks)} risks)")
                return risks[:5]

        # Check if it's a dict
        if isinstance(synthesized_valuation, dict) and "risk_factors" in synthesized_valuation:
            risks = synthesized_valuation["risk_factors"]
            if risks and len(risks) > 0:
                self.logger.info(
                    f"✅ Using synthesizer risk factors from dict ({len(risks)} risks)"
                )
                return risks[:5]

        return None
    
    def _extract_risks_from_methodology_divergence(
        self, dcf_valuation: Any, multiples_valuation: Any
    ) -> List[str]:
        """
        Extract risk factors from methodology divergence (Priority 2).

        Args:
            dcf_valuation: DCF valuation result
            multiples_valuation: Multiples valuation result

        Returns:
            List of risk factors
        """
        risks = []

        if not dcf_valuation or not multiples_valuation:
            return risks

        # Convert Pydantic models to dicts if needed
        dcf_dict = (
            dcf_valuation.model_dump()
            if hasattr(dcf_valuation, "model_dump")
            else (dcf_valuation if isinstance(dcf_valuation, dict) else {})
        )
        multiples_dict = (
            multiples_valuation.model_dump()
            if hasattr(multiples_valuation, "model_dump")
            else (multiples_valuation if isinstance(multiples_valuation, dict) else {})
        )

        _dcf_eq = dcf_dict.get("equity_value")
        dcf_value = _dcf_eq if _dcf_eq is not None else dcf_dict.get("enterprise_value", 0)
        _mult_eq = multiples_dict.get("equity_value")
        multiples_value = _mult_eq if _mult_eq is not None else multiples_dict.get(
            "enterprise_value", 0
        )

        # Validate values are numeric and positive
        dcf_value_decimal = self._as_decimal(dcf_value)
        multiples_value_decimal = self._as_decimal(multiples_value)
        if (
            dcf_value_decimal is not None
            and multiples_value_decimal is not None
            and dcf_value_decimal > 0
            and multiples_value_decimal > 0
        ):
            try:
                variance = abs(dcf_value_decimal - multiples_value_decimal) / max(
                    dcf_value_decimal, multiples_value_decimal
                )
                if variance > Decimal("0.30"):  # >30% divergence
                    risks.append(
                        f"Methodology divergence: DCF (€{dcf_value_decimal:,.0f}) vs Multiples (€{multiples_value_decimal:,.0f}) "
                        f"indicates valuation uncertainty due to limited comparables or unique business characteristics"
                    )
            except (ZeroDivisionError, ValueError, TypeError):
                pass

        return risks
    
    def _extract_risks_from_financial_metrics(self, financial_metrics: Dict[str, Any]) -> List[str]:
        """
        Extract risk factors from financial metrics (Priority 2).

        Args:
            financial_metrics: Financial metrics dictionary

        Returns:
            List of risk factors
        """
        risks = []

        if not financial_metrics or not isinstance(financial_metrics, dict):
            return risks

        # Profitability concerns (EBITDA margin <5%)
        ebitda_margin = self._as_decimal(financial_metrics.get("ebitda_margin"))
        if ebitda_margin is not None:
            is_percentage = ebitda_margin > Decimal("1.0")
            threshold_decimal = Decimal("0.05")
            threshold_percentage = Decimal("5.0")

            if (is_percentage and 0 <= ebitda_margin < threshold_percentage) or (
                not is_percentage and 0 < ebitda_margin < threshold_decimal
            ):
                risks.append("Low profitability margins limit valuation multiples")

        # Negative growth
        _rev_growth = financial_metrics.get("revenue_growth")
        revenue_growth = _rev_growth if _rev_growth is not None else financial_metrics.get(
            "revenue_cagr_3y"
        )
        revenue_growth_decimal = self._as_decimal(revenue_growth)
        if revenue_growth_decimal is not None and revenue_growth_decimal < 0:
            is_percentage = abs(revenue_growth_decimal) > Decimal("1.0")
            if is_percentage:
                risks.append(f"Declining revenue ({revenue_growth_decimal:.1f}% YoY)")
            else:
                risks.append(f"Declining revenue ({revenue_growth_decimal:.1%} YoY)")

        # High leverage (debt-to-equity >2.0)
        debt_to_equity = self._as_decimal(financial_metrics.get("debt_to_equity"))
        if debt_to_equity is not None and debt_to_equity > Decimal("2.0"):
            risks.append(
                f"High leverage increases financial risk (debt-to-equity: {debt_to_equity:.2f})"
            )

        # Liquidity concerns (current ratio <1.0)
        current_ratio = self._as_decimal(financial_metrics.get("current_ratio"))
        if current_ratio is not None and current_ratio < Decimal("1.0"):
            risks.append(
                f"Current ratio below 1.0 ({current_ratio:.2f}) indicates potential liquidity issues"
            )

        return risks
    
    def _extract_risks_from_request_data(self, request: ValuationRequest) -> List[str]:
        """
        Extract risk factors from request data (Priority 3).

        Args:
            request: Valuation request

        Returns:
            List of risk factors
        """
        risks = []
        ebitda = request.current_year_data.ebitda or 0
        revenue = request.current_year_data.revenue or 0

        # 1. Check owner concentration
        if hasattr(request, "number_of_owners") and hasattr(request, "number_of_employees"):
            owners = request.number_of_owners or 0
            employees = max(request.number_of_employees or 1, 1)
            ratio = owners / employees
            if ratio > 0.50:
                risks.append(
                    f"Owner concentration: {ratio:.0%} owner-to-employee ratio indicates key person dependency risk"
                )

        # 2. Check profitability
        if revenue > 0:
            margin = ebitda / revenue
            if margin < 0.10:
                risks.append(
                    f"Low profitability margins ({margin:.1%}) may impact sustainability and valuation multiples"
                )

        # 3. Check revenue trend
        if request.historical_years_data and len(request.historical_years_data) > 0:
            historical_years = sorted(
                request.historical_years_data,
                key=lambda year: getattr(year, "year", 0),
            )
            prior_revenue = historical_years[-1].revenue
            if prior_revenue > 0:
                growth = (revenue - prior_revenue) / prior_revenue
                if growth < -0.05:
                    risks.append(
                        f"Revenue decline: {growth:.1%} YoY decrease requires investigation"
                    )

        # 4. Check company size
        if revenue < 1_000_000:
            risks.append("Small company size results in higher risk and lower valuation multiples")

        # 5. Limited operating history
        if request.founding_year:
            years = date.today().year - request.founding_year
            if years < 3:
                risks.append(
                    f"Limited operating history ({years} years) increases valuation uncertainty"
                )

        return risks
    
    def _generate_fallback_risk_factors(
        self, request: ValuationRequest, results: Dict[str, Any]
    ) -> List[str]:
        """
        Generate fallback risk factors for MULTIPLES-only valuations or when no specific risks are identified.

        This ensures at least 1 risk factor is always generated to meet validation requirements.

        Priority:
        1. Data quality score from Step 0 (if available)
        2. Confidence score (low confidence = risk)
        3. Missing financial data (null fields indicate risk)
        4. Size-based risks (small companies have higher risk)
        5. Owner dependency (if available)
        6. Operating history
        7. Generic risk for healthy companies

        Args:
            request: Valuation request
            results: Valuation results

        Returns:
            List of at least 1 risk factor description
        """
        from .risk_factors_builders import (
            DataQualityRiskBuilder,
            ConfidenceRiskBuilder,
            MissingDataRiskBuilder,
            SizeRiskBuilder,
            OwnerDependencyRiskBuilder,
            OperatingHistoryRiskBuilder,
            GenericRiskBuilder,
        )

        risks = []

        try:
            # Get current year data for multiple builders
            current_year_data = (
                request.current_year_data
                if hasattr(request, "current_year_data") and request.current_year_data
                else None
            )
            from src.utils.decimal_helpers import to_decimal
            
            revenue_raw = getattr(current_year_data, "revenue", 0) if current_year_data else 0
            revenue = to_decimal(revenue_raw)  # Ensure Decimal
            transparency = results.get("transparency", {})

            # PRIORITY 1: Data quality score
            risks.extend(DataQualityRiskBuilder.build_risks(transparency))

            # PRIORITY 2: Confidence score
            risks.extend(ConfidenceRiskBuilder.build_risks(results))

            # PRIORITY 3: Missing financial data
            risks.extend(MissingDataRiskBuilder.build_risks(current_year_data))

            # PRIORITY 4: Size-based risks
            risks.extend(SizeRiskBuilder.build_risks(revenue))

            # PRIORITY 5: Owner dependency
            risks.extend(OwnerDependencyRiskBuilder.build_risks(request))

            # PRIORITY 6: Operating history
            risks.extend(OperatingHistoryRiskBuilder.build_risks(request))

            # PRIORITY 7: Generic risk (always ensure at least 1)
            if len(risks) == 0:
                risks.extend(GenericRiskBuilder.build_risks(revenue))

            self.logger.info(
                f"✅ Generated {len(risks)} fallback risk factors",
                extra={
                    "risk_count": len(risks),
                    "data_quality_used": bool(risks),
                    "confidence_used": bool(risks),
                    "size_used": revenue > 0,
                },
            )

            return risks[:5]  # Return up to 5

        except Exception as e:
            self.logger.error(
                f"❌ Fallback risk factor generation failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return [
                "Valuation estimates are subject to market conditions and comparable company data availability"
            ]
