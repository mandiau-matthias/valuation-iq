"""Compatibility helper surface for the DCF calculator."""

from decimal import Decimal
from typing import Optional

from src.api.schemas import ValuationRequest
from src.domain.dcf_types import WACCComponents

from .dcf_forecast_warnings import build_forecast_assumption_warnings
from .dcf_manual_overrides import apply_manual_dcf_overrides, discount_to_present
from .dcf_policy_context import (
    build_wacc_buildup,
    calculate_terminal_value_split,
    extract_has_audit,
    extract_owner_dependency_score,
)
from .dcf_response_guards import (
    coerce_engine_sensitivity_1d_map,
    fallback_equity_range_band,
    normalize_valuation_range_for_response,
    safe_monte_carlo_decimal,
    safe_monte_carlo_optional_fcf,
    safe_optional_decimal,
    serialize_projection_detail,
)
from .dcf_sensitivity_payload import (
    build_dcf_sensitivity_payload,
    sanitize_sensitivity_matrix_2d,
    sensitivity_matrix_2d_payload_is_finite,
    sensitivity_scenario_values_are_finite,
)
from .dcf_tax_rate_provenance import build_tax_rate_provenance


class DCFCalculatorHelpers:
    """Thin wrappers kept for existing tests and downstream calculator calls."""

    @staticmethod
    def _discount_to_present(
        value: Decimal,
        discount_rate: Decimal,
        period: Decimal,
    ) -> Decimal:
        return discount_to_present(value, discount_rate, period)

    @staticmethod
    def _fallback_equity_range_band(equity_value: Decimal) -> dict[str, Decimal]:
        return fallback_equity_range_band(equity_value)

    @staticmethod
    def _normalize_valuation_range_for_response(
        valuation_range: object,
        equity_mid: Decimal,
        logger: object,
        *,
        correlation_id: object = None,
        company: object = None,
    ) -> dict[str, Decimal]:
        return normalize_valuation_range_for_response(
            valuation_range,
            equity_mid,
            logger,
            correlation_id=correlation_id,
            company=company,
        )

    @staticmethod
    def _safe_monte_carlo_decimal(value: object, fallback: Decimal) -> Decimal:
        return safe_monte_carlo_decimal(value, fallback)

    @staticmethod
    def _safe_optional_decimal(value: object) -> Optional[Decimal]:
        return safe_optional_decimal(value)

    @staticmethod
    def _safe_monte_carlo_optional_fcf(first_projection: object) -> Optional[Decimal]:
        return safe_monte_carlo_optional_fcf(first_projection)

    @staticmethod
    def _coerce_engine_sensitivity_1d_map(raw: object) -> dict[str, Decimal]:
        return coerce_engine_sensitivity_1d_map(raw)

    @staticmethod
    def _serialize_projection_detail(
        dcf_result: object,
    ) -> Optional[list[dict[str, float | int]]]:
        return serialize_projection_detail(dcf_result)

    def _build_wacc_buildup(
        self, wacc_components: Optional[WACCComponents]
    ) -> Optional[dict[str, object]]:
        return build_wacc_buildup(wacc_components)

    def _calculate_terminal_value_split(
        self,
        pv_fcf_projections: list[Decimal],
        pv_terminal_value: Decimal,
    ) -> tuple[Optional[Decimal], Optional[Decimal]]:
        return calculate_terminal_value_split(pv_fcf_projections, pv_terminal_value)

    @staticmethod
    def _build_forecast_assumption_warnings(
        request: object,
    ) -> list[dict[str, object]]:
        return build_forecast_assumption_warnings(request)

    @staticmethod
    def _build_tax_rate_provenance(request: object) -> Optional[dict[str, object]]:
        return build_tax_rate_provenance(request)

    def _apply_manual_dcf_overrides(
        self,
        request: ValuationRequest,
        *,
        enterprise_value: Decimal,
        equity_value: Decimal,
        wacc: Decimal,
        terminal_growth_rate: Decimal,
        terminal_value: Decimal,
        pv_terminal_value: Decimal,
        cash_flow_projections: list[Decimal],
        net_debt: Decimal,
        cash: Decimal,
        mid_year_discounting: bool = True,
    ) -> tuple[
        Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, list[Decimal], str, Decimal | None
    ]:
        return apply_manual_dcf_overrides(
            request,
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            wacc=wacc,
            terminal_growth_rate=terminal_growth_rate,
            terminal_value=terminal_value,
            pv_terminal_value=pv_terminal_value,
            cash_flow_projections=cash_flow_projections,
            net_debt=net_debt,
            cash=cash,
            logger=self.logger,
            mid_year_discounting=mid_year_discounting,
        )

    @staticmethod
    def _sensitivity_scenario_values_are_finite(obj: object) -> bool:
        return sensitivity_scenario_values_are_finite(obj)

    @staticmethod
    def _sensitivity_matrix_2d_payload_is_finite(matrix: dict[str, object]) -> bool:
        return sensitivity_matrix_2d_payload_is_finite(matrix)

    @staticmethod
    def _sanitize_sensitivity_matrix_2d(
        matrix: Optional[dict[str, object]],
    ) -> Optional[dict[str, object]]:
        return sanitize_sensitivity_matrix_2d(matrix)

    def _build_dcf_sensitivity_payload(
        self,
        *,
        fcf_values: list[Decimal],
        wacc: Decimal,
        terminal_growth_rate: Decimal,
        terminal_value: Decimal,
        terminal_value_methodology: str = "gordon_growth",
        terminal_exit_multiple: Decimal | None = None,
        terminal_ebitda: Decimal | None = None,
        mid_year_discounting: bool = True,
    ) -> tuple[dict[object, object], dict[object, object], Optional[dict[str, object]]]:
        return build_dcf_sensitivity_payload(
            fcf_values=fcf_values,
            wacc=wacc,
            terminal_growth_rate=terminal_growth_rate,
            terminal_value=terminal_value,
            terminal_value_methodology=terminal_value_methodology,
            terminal_exit_multiple=terminal_exit_multiple,
            terminal_ebitda=terminal_ebitda,
            mid_year_discounting=mid_year_discounting,
        )

    def _extract_has_audit(self, request: ValuationRequest) -> Optional[bool]:
        return extract_has_audit(request)

    def _extract_owner_dependency_score(self, request: ValuationRequest) -> Optional[Decimal]:
        return extract_owner_dependency_score(request, logger=self.logger)
