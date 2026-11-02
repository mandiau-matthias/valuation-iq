"""
Valuation Calculation Coordinator

Orchestrates common valuation calculation patterns used across section calculations.
"""

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Mapping, Optional

from src.api.routes.valuation.benchmark_contract_utils import (
    REQUIRED_BENCHMARK_PROVENANCE_FIELDS,
    as_mapping,
    benchmark_contract_data_source,
    extract_resolved_benchmark_contract,
)
from src.domain.multiples.advisor_controls import (
    build_multiple_type_blend,
    infer_sector_multiple_type_weights,
)
from src.services.progressive.calculators.industry_helpers import IndustryHelpers
from src.utils.core.data_extraction_helpers import (
    extract_ebitda_from_collected_data,
    extract_growth_rate_from_collected_data,
    extract_revenue_from_collected_data,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.fiscal_year import get_current_filing_year
from src.utils.logging import get_logger

logger = get_logger(__name__)

NumericInput = str | int | float | Decimal


@dataclass(frozen=True)
class MultiplesFinancialInputs:
    revenue_decimal: Decimal
    has_revenue: bool
    ebitda_decimal: Decimal
    has_ebitda: bool
    revenue: Decimal
    ebitda: Optional[Decimal]

    @property
    def has_positive_ebitda(self) -> bool:
        return self.ebitda is not None and self.ebitda > 0


@dataclass(frozen=True)
class MultiplesResolution:
    ev_revenue_multiple: Optional[NumericInput]
    ev_ebitda_multiple: Optional[NumericInput]
    pe_ratio: NumericInput
    data_source: str
    benchmark_contract: Optional[dict[str, object]]
    blocked_reason: Optional[str] = None


@dataclass(frozen=True)
class MultiplesMetricCandidates:
    ev_revenue_multiple: Optional[NumericInput]
    ev_ebitda_multiple: Optional[NumericInput]
    pe_ratio: Optional[NumericInput]
    data_source: str


class ValuationCalculationCoordinator:
    """
    Coordinates common valuation calculation operations.

    BANK-GRADE: Prioritizes Titan-provided enrichment data (from business_types DB via Delphi)
    over hardcoded fallbacks for maximum valuation accuracy.
    """

    def __init__(self) -> None:
        self.industry_helpers = IndustryHelpers()
        self.logger = logger

    def _allows_untrusted_multiples_fallback(self, collected_data: Dict[str, Any]) -> bool:
        if collected_data.get("allow_untrusted_multiples_fallback") is True:
            return True
        for key in ("metadata", "business_context", "multiples_metadata"):
            container = as_mapping(collected_data.get(key))
            if container.get("allow_untrusted_multiples_fallback") is True:
                return True
        return False

    def _blocked_multiples_data(self, reason: str) -> Dict[str, Any]:
        return {
            "ev_revenue_multiple": None,
            "ev_ebitda_multiple": None,
            "pe_ratio": None,
            "revenue_multiple_value": None,
            "ebitda_multiple_value": None,
            "earnings_multiple_value": None,
            "weighted_multiples_value": None,
            "has_valid_data": False,
            "blocked": True,
            "requires_benchmark_contract": True,
            "publication_allowed": False,
            "data_source": "blocked_no_benchmark_contract",
            "reason": reason,
        }

    def _multiple_type_weights_from_collected_data(
        self, collected_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        candidates = [
            collected_data.get("multiple_type_weights"),
            collected_data.get("multipleTypeWeights"),
        ]
        for key in ("metadata", "business_context", "multiples_metadata"):
            container = as_mapping(collected_data.get(key))
            if container:
                candidates.append(container.get("multiple_type_weights"))
                candidates.append(container.get("multipleTypeWeights"))

        for candidate in candidates:
            if isinstance(candidate, dict):
                return candidate
        return None

    def _metric_median(
        self, benchmark_contract: Dict[str, Any], metric_name: str
    ) -> Optional[float]:
        metrics = as_mapping(benchmark_contract.get("metrics"))
        metric = as_mapping(metrics.get(metric_name))
        value = metric.get("median")
        if value is None:
            return None
        try:
            decimal_value = to_decimal(value)
        except Exception:
            return None
        if decimal_value <= 0:
            return None
        return float(decimal_value)

    def _benchmark_provenance(self, benchmark_contract: Dict[str, Any]) -> Dict[str, Any]:
        return {
            field: benchmark_contract.get(field) for field in REQUIRED_BENCHMARK_PROVENANCE_FIELDS
        }

    def _extract_multiples_financials(
        self, collected_data: Mapping[str, object]
    ) -> MultiplesFinancialInputs:
        revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)
        ebitda_decimal, has_ebitda = extract_ebitda_from_collected_data(collected_data)
        return MultiplesFinancialInputs(
            revenue_decimal=revenue_decimal,
            has_revenue=has_revenue,
            ebitda_decimal=ebitda_decimal,
            has_ebitda=has_ebitda,
            revenue=from_decimal(revenue_decimal),
            ebitda=from_decimal(ebitda_decimal) if has_ebitda else None,
        )

    def _resolve_multiples_inputs(
        self,
        collected_data: Mapping[str, object],
        industry: str,
        business_type_id: Optional[str],
        financials: MultiplesFinancialInputs,
    ) -> MultiplesResolution:
        benchmark_contract = extract_resolved_benchmark_contract(collected_data)
        allow_untrusted_multiples_fallback = self._allows_untrusted_multiples_fallback(
            collected_data
        )

        metrics = self._benchmark_multiple_candidates(benchmark_contract)
        if self._missing_required_multiples(metrics, financials):
            if not allow_untrusted_multiples_fallback:
                return MultiplesResolution(
                    ev_revenue_multiple=metrics.ev_revenue_multiple,
                    ev_ebitda_multiple=metrics.ev_ebitda_multiple,
                    pe_ratio=metrics.pe_ratio or 0.0,
                    data_source=metrics.data_source,
                    benchmark_contract=benchmark_contract,
                    blocked_reason="Resolved benchmark contract missing required valuation metric",
                )
            metrics = self._apply_untrusted_multiples_fallback(
                metrics,
                industry,
                business_type_id,
                financials,
            )

        return MultiplesResolution(
            ev_revenue_multiple=metrics.ev_revenue_multiple,
            ev_ebitda_multiple=metrics.ev_ebitda_multiple,
            pe_ratio=self._derive_pe_ratio(metrics),
            data_source=metrics.data_source,
            benchmark_contract=benchmark_contract,
        )

    def _benchmark_multiple_candidates(
        self, benchmark_contract: Optional[dict[str, object]]
    ) -> MultiplesMetricCandidates:
        if not benchmark_contract:
            return MultiplesMetricCandidates(
                ev_revenue_multiple=None,
                ev_ebitda_multiple=None,
                pe_ratio=None,
                data_source="blocked_no_benchmark_contract",
            )

        ev_revenue_multiple = self._metric_median(benchmark_contract, "ev_revenue")
        ev_ebitda_multiple = self._metric_median(benchmark_contract, "ev_ebitda")
        data_source = "blocked_no_benchmark_contract"
        if ev_revenue_multiple is not None or ev_ebitda_multiple is not None:
            data_source = benchmark_contract_data_source(benchmark_contract)

        return MultiplesMetricCandidates(
            ev_revenue_multiple=ev_revenue_multiple,
            ev_ebitda_multiple=ev_ebitda_multiple,
            pe_ratio=self._metric_median(benchmark_contract, "pe_ratio"),
            data_source=data_source,
        )

    def _missing_required_multiples(
        self,
        metrics: MultiplesMetricCandidates,
        financials: MultiplesFinancialInputs,
    ) -> bool:
        return metrics.ev_revenue_multiple is None or (
            financials.has_positive_ebitda and metrics.ev_ebitda_multiple is None
        )

    def _apply_untrusted_multiples_fallback(
        self,
        metrics: MultiplesMetricCandidates,
        industry: str,
        business_type_id: Optional[str],
        financials: MultiplesFinancialInputs,
    ) -> MultiplesMetricCandidates:
        ev_revenue_multiple = metrics.ev_revenue_multiple
        ev_ebitda_multiple = metrics.ev_ebitda_multiple
        data_source = metrics.data_source

        if ev_revenue_multiple is None:
            ev_revenue_multiple = self.industry_helpers.get_industry_revenue_multiple(
                industry,
                revenue=financials.revenue_decimal,
                business_type=business_type_id,
            )
            data_source = "explicit_untrusted_helper_fallback"

        if ev_ebitda_multiple is None:
            ev_ebitda_multiple = self.industry_helpers.get_industry_ebitda_multiple(
                industry,
                revenue=financials.revenue_decimal,
                business_type=business_type_id,
            )
            data_source = "explicit_untrusted_helper_fallback"

        return MultiplesMetricCandidates(
            ev_revenue_multiple=ev_revenue_multiple,
            ev_ebitda_multiple=ev_ebitda_multiple,
            pe_ratio=metrics.pe_ratio,
            data_source=data_source,
        )

    def _derive_pe_ratio(self, metrics: MultiplesMetricCandidates) -> NumericInput:
        if metrics.pe_ratio is not None:
            return metrics.pe_ratio
        if metrics.ev_ebitda_multiple is not None:
            return to_decimal(metrics.ev_ebitda_multiple) * Decimal("1.2")
        return 0.0

    def _log_benchmark_multiples(
        self,
        resolution: MultiplesResolution,
        business_type_id: Optional[str],
    ) -> None:
        if not resolution.data_source.endswith("_benchmark_contract"):
            return

        self.logger.info(
            "Using resolved benchmark contract multiples for valuation",
            extra={
                "ev_revenue_multiple": resolution.ev_revenue_multiple,
                "ev_ebitda_multiple": resolution.ev_ebitda_multiple,
                "pe_ratio": resolution.pe_ratio,
                "source": resolution.data_source,
                "business_type_id": business_type_id,
                "benchmark_id": (
                    resolution.benchmark_contract.get("benchmark_id")
                    if resolution.benchmark_contract
                    else None
                ),
            },
        )

    def _calculate_multiple_values(
        self,
        financials: MultiplesFinancialInputs,
        resolution: MultiplesResolution,
    ) -> dict[str, Decimal]:
        ev_revenue_multiple_decimal = to_decimal(resolution.ev_revenue_multiple)
        ev_ebitda_multiple_decimal = to_decimal(resolution.ev_ebitda_multiple)
        pe_ratio_decimal = to_decimal(resolution.pe_ratio)

        revenue_multiple_value = from_decimal(
            financials.revenue_decimal * ev_revenue_multiple_decimal
        )
        ebitda_multiple_value = (
            from_decimal(financials.ebitda_decimal * ev_ebitda_multiple_decimal)
            if financials.has_positive_ebitda
            else Decimal("0.00")
        )
        earnings = (
            financials.ebitda_decimal * Decimal("0.7")
            if financials.has_positive_ebitda
            else financials.revenue_decimal * Decimal("0.1")
        )
        earnings_multiple_value = from_decimal(earnings * pe_ratio_decimal)

        return {
            "revenue_multiple_value": revenue_multiple_value,
            "ebitda_multiple_value": ebitda_multiple_value,
            "earnings_multiple_value": earnings_multiple_value,
        }

    def _build_multiple_type_blend(
        self,
        collected_data: Mapping[str, object],
        financials: MultiplesFinancialInputs,
        resolution: MultiplesResolution,
        values: Mapping[str, Decimal],
    ) -> dict[str, object]:
        default_type_weights, default_type_source = infer_sector_multiple_type_weights(
            revenue=financials.revenue_decimal,
            ebitda=financials.ebitda_decimal if financials.has_ebitda else None,
            benchmark_contract=resolution.benchmark_contract,
        )
        return build_multiple_type_blend(
            {
                "ev_revenue": values["revenue_multiple_value"],
                "ev_ebitda": (
                    values["ebitda_multiple_value"] if financials.has_positive_ebitda else None
                ),
                "pe": values["earnings_multiple_value"],
            },
            self._multiple_type_weights_from_collected_data(collected_data),
            default_weights=default_type_weights,
            default_source=default_type_source,
        )

    def _build_multiples_result(
        self,
        financials: MultiplesFinancialInputs,
        resolution: MultiplesResolution,
        values: Mapping[str, Decimal],
        multiple_type_blend: Mapping[str, object],
    ) -> dict[str, object]:
        weighted_multiples_value = from_decimal(
            to_decimal(multiple_type_blend.get("weighted_enterprise_value") or 0)
        )
        is_benchmark_source = resolution.data_source.endswith("_benchmark_contract")

        return {
            "ev_revenue_multiple": resolution.ev_revenue_multiple,
            "ev_ebitda_multiple": resolution.ev_ebitda_multiple,
            "pe_ratio": resolution.pe_ratio,
            "revenue_multiple_value": values["revenue_multiple_value"],
            "ebitda_multiple_value": values["ebitda_multiple_value"],
            "earnings_multiple_value": values["earnings_multiple_value"],
            "weighted_multiples_value": weighted_multiples_value,
            "multiple_type_blend": multiple_type_blend,
            "has_valid_data": True,
            "data_source": resolution.data_source,
            "publication_allowed": is_benchmark_source,
            "benchmark_contract": (resolution.benchmark_contract if is_benchmark_source else None),
            "benchmark_provenance": (
                self._benchmark_provenance(resolution.benchmark_contract)
                if is_benchmark_source and resolution.benchmark_contract
                else None
            ),
        }

    def calculate_revenue_based_valuation(
        self,
        collected_data: Dict[str, Any],
        industry: str,
        business_type_id: Optional[str] = None,
        titan_ev_revenue_multiple: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate revenue-based valuation.

        BANK-GRADE: Prioritizes Titan-provided multiples from business_types DB.

        Priority:
        1. Titan-provided ev_revenue_multiple (from Delphi/business_types DB)
        2. IndustryHelpers with business_type_id (hardcoded fallback)

        Args:
            collected_data: Collected data dictionary
            industry: Industry identifier (may be derived from business_type_id)
            business_type_id: Optional business type ID for business-type-specific multiples
            titan_ev_revenue_multiple: Optional Titan-provided EV/Revenue multiple dict with median/p25/p75

        Returns:
            Dictionary with revenue valuation data
        """
        revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)
        revenue = from_decimal(revenue_decimal)
        revenue_growth = extract_growth_rate_from_collected_data(collected_data)

        if not has_revenue:
            return {
                "revenue": None,
                "revenue_growth": revenue_growth,
                "revenue_multiple": None,
                "revenue_valuation": None,
                "has_valid_data": False,
            }

        benchmark_contract = extract_resolved_benchmark_contract(collected_data)
        allow_untrusted_multiples_fallback = self._allows_untrusted_multiples_fallback(
            collected_data
        )

        # BANK-GRADE: Priority 1 - Use resolved benchmark contract if available.
        # Country-baseline contracts remain publication-safe because they are
        # resolved and fully disclosed, but must not be mislabeled as Delphi.
        revenue_multiple = None
        data_source = "blocked_no_benchmark_contract"

        if benchmark_contract:
            revenue_multiple = self._metric_median(benchmark_contract, "ev_revenue")
            if revenue_multiple is not None:
                data_source = benchmark_contract_data_source(benchmark_contract)
                self.logger.info(
                    "Using resolved benchmark contract EV/Revenue multiple",
                    extra={
                        "multiple": revenue_multiple,
                        "source": data_source,
                        "business_type_id": business_type_id,
                        "benchmark_id": benchmark_contract.get("benchmark_id"),
                    },
                )

        if revenue_multiple is None and not allow_untrusted_multiples_fallback:
            return {
                "revenue": revenue,
                "revenue_growth": revenue_growth,
                "revenue_multiple": None,
                "revenue_valuation": None,
                "has_valid_data": False,
                "blocked": True,
                "requires_benchmark_contract": True,
                "publication_allowed": False,
                "data_source": "blocked_no_benchmark_contract",
            }

        # Explicit disclosed fallback only - never publication-grade.
        if revenue_multiple is None:
            revenue_multiple = self.industry_helpers.get_industry_revenue_multiple(
                industry, revenue=revenue_decimal, business_type=business_type_id
            )
            data_source = "explicit_untrusted_helper_fallback"
            self.logger.debug(
                "Using explicitly disclosed helper revenue multiple",
                extra={"multiple": revenue_multiple, "source": data_source},
            )

        # Calculate valuation
        revenue_valuation = from_decimal(revenue_decimal * to_decimal(revenue_multiple))

        return {
            "revenue": revenue,
            "revenue_growth": revenue_growth,
            "revenue_multiple": revenue_multiple,
            "revenue_valuation": revenue_valuation,
            "has_valid_data": True,
            "data_source": data_source,
            "publication_allowed": data_source.endswith("_benchmark_contract"),
            "benchmark_contract": (
                benchmark_contract if data_source.endswith("_benchmark_contract") else None
            ),
        }

    def calculate_ebitda_based_valuation(
        self,
        collected_data: Dict[str, Any],
        industry: str,
        business_type_id: Optional[str] = None,
        titan_ev_ebitda_multiple: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate EBITDA-based valuation.

        BANK-GRADE: Prioritizes Titan-provided multiples from business_types DB.

        Priority:
        1. Titan-provided ev_ebitda_multiple (from Delphi/business_types DB)
        2. IndustryHelpers with business_type_id (hardcoded fallback)

        Args:
            collected_data: Collected data dictionary
            industry: Industry identifier (may be derived from business_type_id)
            business_type_id: Optional business type ID for business-type-specific multiples
            titan_ev_ebitda_multiple: Optional Titan-provided EV/EBITDA multiple dict with median/p25/p75

        Returns:
            Dictionary with EBITDA valuation data
        """
        revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)
        ebitda_decimal, has_ebitda = extract_ebitda_from_collected_data(collected_data)
        revenue = from_decimal(revenue_decimal)
        ebitda = from_decimal(ebitda_decimal) if has_ebitda else None

        if not has_ebitda or not ebitda or ebitda <= 0:
            return {
                "ebitda": None,
                "ebitda_margin": None,
                "ebitda_multiple": None,
                "ebitda_valuation": None,
                "has_valid_data": False,
            }

        # Calculate EBITDA margin
        ebitda_margin = (ebitda / revenue * 100) if revenue > 0 else 0
        founded_year = collected_data.get("founding_year") or collected_data.get("founded_year")
        historical_data = collected_data.get("historical_years_data")

        benchmark_contract = extract_resolved_benchmark_contract(collected_data)
        allow_untrusted_multiples_fallback = self._allows_untrusted_multiples_fallback(
            collected_data
        )

        # BANK-GRADE: Priority 1 - Use resolved benchmark contract if available.
        ebitda_multiple = None
        data_source = "blocked_no_benchmark_contract"

        if benchmark_contract:
            ebitda_multiple = self._metric_median(benchmark_contract, "ev_ebitda")
            if ebitda_multiple is not None:
                data_source = benchmark_contract_data_source(benchmark_contract)
                self.logger.info(
                    "Using resolved benchmark contract EV/EBITDA multiple",
                    extra={
                        "multiple": ebitda_multiple,
                        "source": data_source,
                        "business_type_id": business_type_id,
                        "benchmark_id": benchmark_contract.get("benchmark_id"),
                    },
                )

        if ebitda_multiple is None and not allow_untrusted_multiples_fallback:
            return {
                "ebitda": ebitda,
                "ebitda_margin": ebitda_margin,
                "ebitda_multiple": None,
                "ebitda_valuation": None,
                "has_valid_data": False,
                "blocked": True,
                "requires_benchmark_contract": True,
                "publication_allowed": False,
                "data_source": "blocked_no_benchmark_contract",
            }

        # Explicit disclosed fallback only - never publication-grade.
        if ebitda_multiple is None:
            ebitda_multiple = self.industry_helpers.get_industry_ebitda_multiple(
                industry,
                revenue=revenue_decimal,
                business_type=business_type_id,
                founded_year=founded_year,
                current_year=get_current_filing_year(),
                historical_data=historical_data if isinstance(historical_data, list) else None,
            )
            data_source = "explicit_untrusted_helper_fallback"
            self.logger.debug(
                "Using explicitly disclosed helper EBITDA multiple",
                extra={"multiple": ebitda_multiple, "source": data_source},
            )

        # Calculate valuation
        ebitda_valuation = from_decimal(ebitda_decimal * to_decimal(ebitda_multiple))

        return {
            "ebitda": ebitda,
            "ebitda_margin": ebitda_margin,
            "ebitda_multiple": ebitda_multiple,
            "ebitda_valuation": ebitda_valuation,
            "has_valid_data": True,
            "data_source": data_source,
            "publication_allowed": data_source.endswith("_benchmark_contract"),
            "benchmark_contract": (
                benchmark_contract if data_source.endswith("_benchmark_contract") else None
            ),
        }

    def calculate_dcf_valuation(
        self,
        collected_data: Dict[str, Any],
        forecast_years: int = 5,
        terminal_growth: float = 2.5,
        risk_free_rate: float = 3.0,
        business_type_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate DCF valuation.

        WORLD-CLASS: Uses business_type_id for business-type-specific WACC calculation.

        Args:
            collected_data: Collected data dictionary
            forecast_years: Number of forecast years
            terminal_growth: Terminal growth rate percentage
            risk_free_rate: Risk-free rate percentage
            business_type_id: Optional business type ID for business-type-specific WACC

        Returns:
            Dictionary with DCF valuation data
        """
        revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)
        growth_rate_decimal = extract_growth_rate_from_collected_data(
            collected_data, default=Decimal("10.0")
        )

        if not has_revenue:
            return {
                "dcf_enterprise_value": None,
                "dcf_equity_value": None,
                "has_valid_data": False,
            }

        # Simplified WACC calculation
        wacc_decimal = Decimal(str(risk_free_rate + 5.0))  # Simplified
        terminal_growth_decimal = Decimal(str(terminal_growth))
        forecast_years_decimal = Decimal(str(forecast_years))

        # Calculate PV of cash flows
        pv_cash_flows_decimal = Decimal("0")
        for year in range(1, forecast_years + 1):
            year_decimal = Decimal(str(year))
            growth_factor_decimal = (
                Decimal("1") + (growth_rate_decimal / Decimal("100"))
            ) ** year_decimal
            discount_factor_decimal = (
                Decimal("1") + (wacc_decimal / Decimal("100"))
            ) ** year_decimal
            year_pv_decimal = (
                revenue_decimal * growth_factor_decimal * Decimal("0.15")
            ) / discount_factor_decimal
            pv_cash_flows_decimal += year_pv_decimal

        # Calculate terminal value
        terminal_growth_factor_decimal = (
            Decimal("1") + (growth_rate_decimal / Decimal("100"))
        ) ** forecast_years_decimal
        terminal_fcf_decimal = revenue_decimal * terminal_growth_factor_decimal * Decimal("0.15")
        terminal_value_numerator_decimal = terminal_fcf_decimal * (
            Decimal("1") + (terminal_growth_decimal / Decimal("100"))
        )
        terminal_value_denominator_decimal = (wacc_decimal - terminal_growth_decimal) / Decimal(
            "100"
        )

        if terminal_value_denominator_decimal > Decimal("0"):
            terminal_value_decimal = (
                terminal_value_numerator_decimal / terminal_value_denominator_decimal
            )
        else:
            terminal_value_decimal = Decimal("0")

        terminal_discount_factor_decimal = (
            Decimal("1") + (wacc_decimal / Decimal("100"))
        ) ** forecast_years_decimal
        terminal_value_pv_decimal = terminal_value_decimal / terminal_discount_factor_decimal

        # Enterprise value
        dcf_enterprise_value_decimal = pv_cash_flows_decimal + terminal_value_pv_decimal

        # Equity value (simplified - assume no net debt)
        total_debt_decimal = to_decimal(collected_data.get("total_debt", 0))
        cash_decimal = to_decimal(collected_data.get("cash", 0))
        net_debt_decimal = total_debt_decimal - cash_decimal
        dcf_equity_value_decimal = dcf_enterprise_value_decimal - net_debt_decimal

        return {
            "dcf_enterprise_value": from_decimal(dcf_enterprise_value_decimal),
            "dcf_equity_value": from_decimal(dcf_equity_value_decimal),
            "wacc": float(wacc_decimal),
            "terminal_growth": terminal_growth,
            "forecast_years": forecast_years,
            "pv_cash_flows": from_decimal(pv_cash_flows_decimal),
            "terminal_value": from_decimal(terminal_value_pv_decimal),
            "net_debt": from_decimal(net_debt_decimal),
            "has_valid_data": True,
        }

    def calculate_multiples_valuation(
        self,
        collected_data: Dict[str, Any],
        industry: str,
        business_type_id: Optional[str] = None,
        titan_ev_ebitda_multiple: Optional[Dict[str, Any]] = None,
        titan_ev_revenue_multiple: Optional[Dict[str, Any]] = None,
        titan_pe_ratio: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate multiples-based valuation.

        BANK-GRADE: Prioritizes Titan-provided multiples from business_types DB.

        Priority:
        1. Titan-provided multiples (from Delphi/business_types DB)
        2. IndustryHelpers with business_type_id (hardcoded fallback)

        Args:
            collected_data: Collected data dictionary
            industry: Industry identifier (may be derived from business_type_id)
            business_type_id: Optional business type ID for business-type-specific multiples
            titan_ev_ebitda_multiple: Optional Titan-provided EV/EBITDA multiple dict
            titan_ev_revenue_multiple: Optional Titan-provided EV/Revenue multiple dict
            titan_pe_ratio: Optional Titan-provided P/E ratio dict

        Returns:
            Dictionary with multiples valuation data
        """
        financials = self._extract_multiples_financials(collected_data)
        if not financials.has_revenue:
            return {
                "ev_revenue_multiple": None,
                "ev_ebitda_multiple": None,
                "revenue_multiple_value": None,
                "ebitda_multiple_value": None,
                "weighted_multiples_value": None,
                "has_valid_data": False,
            }

        resolution = self._resolve_multiples_inputs(
            collected_data,
            industry,
            business_type_id,
            financials,
        )
        if resolution.blocked_reason:
            return self._blocked_multiples_data(resolution.blocked_reason)

        self._log_benchmark_multiples(resolution, business_type_id)
        values = self._calculate_multiple_values(financials, resolution)
        multiple_type_blend = self._build_multiple_type_blend(
            collected_data,
            financials,
            resolution,
            values,
        )
        return self._build_multiples_result(
            financials,
            resolution,
            values,
            multiple_type_blend,
        )
