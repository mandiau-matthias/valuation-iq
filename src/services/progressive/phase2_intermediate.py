"""Phase-2 progressive valuation calculation policy."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from decimal import Decimal

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import DCFCalculationError

logger = logging.getLogger(__name__)


async def calculate_phase_2_intermediate_for_service(
    service,
    data: dict[str, object],
    result_type: Callable[..., object],
) -> object:
    """
    Calculate progressive Phase 2 using the service's injected dependencies.

    The public dataclass stays in ``progressive_valuation_service`` for API
    compatibility; this helper owns the phase-specific orchestration and returns
    an instance via ``result_type`` to avoid import cycles.
    """
    service.academic_tracker_manager.ensure_tracker(data)
    start_time = time.time()
    logger.info(f"Calculating Phase 2 intermediate for {data.get('company_name', 'Unknown')}")

    try:
        revenue_decimal = to_decimal(data.get("revenue", 0))
        ebitda_decimal = to_decimal(data.get("ebitda", 0))
        growth_rate_decimal = to_decimal(data.get("growth_rate", 0))
        revenue = from_decimal(revenue_decimal)
        ebitda = from_decimal(ebitda_decimal)
        growth_rate = from_decimal(growth_rate_decimal)
        industry = data.get("industry", "unknown")
        benchmark_contract = service._resolved_benchmark_contract(data)
        allow_untrusted_multiples_fallback = service._allows_untrusted_multiples_fallback(data)

        if service.use_mock:
            dcf_data = service.mock_coordinator.calculate_mock_dcf(revenue, ebitda, growth_rate)
            multiples_data = _mock_or_contract_multiples(
                service,
                benchmark_contract=benchmark_contract,
                allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
                revenue_decimal=revenue_decimal,
                ebitda_decimal=ebitda_decimal,
                revenue=revenue,
                ebitda=ebitda,
                industry=industry,
            )
        else:
            dcf_data, multiples_data = await _calculate_real_or_fallback_phase_2(
                service,
                data=data,
                benchmark_contract=benchmark_contract,
                allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
                revenue_decimal=revenue_decimal,
                ebitda_decimal=ebitda_decimal,
                growth_rate_decimal=growth_rate_decimal,
                revenue=revenue,
                ebitda=ebitda,
                growth_rate=growth_rate,
                industry=industry,
            )

        return _build_phase_2_result(
            service=service,
            result_type=result_type,
            dcf_data=dcf_data,
            multiples_data=multiples_data,
            start_time=start_time,
        )

    except DCFCalculationError as e:
        logger.error(f"Phase 2 DCF calculation failed closed: {e}")
        return result_type(
            dcf_data={"methodology": "DCF unavailable", "error": str(e)},
            multiples_data=service._blocked_multiples_data(
                reason="Phase 2 unavailable; refusing fallback industry multiples"
            ),
            combined_value_low=Decimal("0"),
            combined_value_mid=Decimal("0"),
            combined_value_high=Decimal("0"),
            confidence_score=Decimal("0"),
            methodology_weights={"dcf": Decimal("0"), "multiples": Decimal("0")},
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
    except (ValueError, TypeError, AttributeError, KeyError) as e:
        logger.error(
            "Phase 2 calculation failed before valuation-grade inputs could be applied",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return result_type(
            dcf_data={"methodology": "Valuation unavailable", "error": str(e)},
            multiples_data=service._blocked_multiples_data(
                reason="Invalid inputs; resolved benchmark contract required before multiples"
            ),
            combined_value_low=Decimal("0"),
            combined_value_mid=Decimal("0"),
            combined_value_high=Decimal("0"),
            confidence_score=Decimal("0"),
            methodology_weights={"dcf": Decimal("0"), "multiples": Decimal("0")},
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )


def _mock_or_contract_multiples(
    service,
    *,
    benchmark_contract: dict[str, object] | None,
    allow_untrusted_multiples_fallback: bool,
    revenue_decimal: Decimal,
    ebitda_decimal: Decimal,
    revenue: float,
    ebitda: float,
    industry: str,
) -> dict[str, object]:
    if benchmark_contract:
        return service._calculate_contract_multiples_data(
            benchmark_contract=benchmark_contract,
            revenue=revenue_decimal,
            ebitda=ebitda_decimal,
        )
    if allow_untrusted_multiples_fallback:
        multiples_data = service.mock_coordinator.calculate_mock_multiples(
            revenue, ebitda, industry
        )
        multiples_data.update(
            {
                "methodology": "Explicit disclosed mock multiples fallback",
                "publication_allowed": False,
                "benchmark_contract_required": True,
            }
        )
        return multiples_data
    return service._blocked_multiples_data()


async def _calculate_real_or_fallback_phase_2(
    service,
    *,
    data: dict[str, object],
    benchmark_contract: dict[str, object] | None,
    allow_untrusted_multiples_fallback: bool,
    revenue_decimal: Decimal,
    ebitda_decimal: Decimal,
    growth_rate_decimal: Decimal,
    revenue: float,
    ebitda: float,
    growth_rate: float,
    industry: str,
) -> tuple[dict[str, object], dict[str, object]]:
    financial_data_type, market_data_type = _load_valuation_types()
    if financial_data_type is None or market_data_type is None:
        logger.warning("FinancialData/MarketData not available, using mock calculations")
        dcf_data = service.mock_coordinator.calculate_mock_dcf(revenue, ebitda, growth_rate)
        multiples_data = _mock_or_contract_multiples(
            service,
            benchmark_contract=benchmark_contract,
            allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
            revenue_decimal=revenue_decimal,
            ebitda_decimal=ebitda_decimal,
            revenue=revenue,
            ebitda=ebitda,
            industry=industry,
        )
        return dcf_data, multiples_data

    financial_data = _build_financial_data(
        financial_data_type,
        data=data,
        revenue=revenue,
        ebitda=ebitda,
        growth_rate=growth_rate,
    )
    market_data = _build_market_data(market_data_type, data)

    dcf_result = await service.processor.calculate_dcf_valuation(financial_data, market_data)
    dcf_data = {
        "value_low": dcf_result.get("min_value", 0),
        "value_mid": dcf_result.get("value", 0),
        "value_high": dcf_result.get("max_value", 0),
        "discount_rate": dcf_result.get("discount_rate", Decimal("0.10")),
        "terminal_growth": dcf_result.get("terminal_growth_rate", Decimal("0.03")),
        "projected_cash_flows": dcf_result.get("projected_cash_flows", []),
    }

    if benchmark_contract:
        multiples_data = service._calculate_contract_multiples_data(
            benchmark_contract=benchmark_contract,
            revenue=revenue_decimal,
            ebitda=ebitda_decimal,
        )
    elif allow_untrusted_multiples_fallback:
        multiples_data = await _calculate_legacy_multiples_fallback(
            service.processor.calculate_multiples_valuation,
            financial_data,
            market_data,
        )
    else:
        multiples_data = service._blocked_multiples_data()

    return dcf_data, multiples_data


def _load_valuation_types() -> tuple[object, object]:
    try:
        from src.api.routes.valuation.valuation_types import FinancialData, MarketData

        return FinancialData, MarketData
    except ImportError:
        return None, None


def _build_financial_data(
    financial_data_type: Callable[..., object],
    *,
    data: dict[str, object],
    revenue: float,
    ebitda: float,
    growth_rate: float,
) -> object:
    return financial_data_type(
        revenue=revenue,
        ebitda=ebitda,
        net_income=from_decimal(to_decimal(data.get("net_income", 0))),
        total_assets=from_decimal(to_decimal(data.get("total_assets", 0))),
        total_debt=from_decimal(to_decimal(data.get("total_debt", 0))),
        cash=from_decimal(to_decimal(data.get("cash", 0))),
        working_capital=from_decimal(to_decimal(data.get("working_capital", 0))),
        capex=from_decimal(to_decimal(data.get("capex", 0))),
        depreciation=from_decimal(to_decimal(data.get("depreciation", 0))),
        tax_rate=from_decimal(to_decimal(data.get("tax_rate", Decimal("0.25")))),
        growth_rate=growth_rate,
        discount_rate=from_decimal(to_decimal(data.get("discount_rate", Decimal("0.10")))),
        terminal_growth_rate=from_decimal(
            to_decimal(data.get("terminal_growth_rate", Decimal("0.03")))
        ),
        year=int(data.get("year", 2024)),
    )


def _build_market_data(market_data_type: Callable[..., object], data: dict[str, object]) -> object:
    return market_data_type(
        industry_multiple=from_decimal(to_decimal(data.get("industry_multiple", Decimal("2.5")))),
        market_cap=from_decimal(to_decimal(data.get("market_cap", 1000000))),
        enterprise_value=from_decimal(to_decimal(data.get("enterprise_value", 1000000))),
        pe_ratio=from_decimal(to_decimal(data.get("pe_ratio", Decimal("15.0")))),
        ev_ebitda_ratio=from_decimal(to_decimal(data.get("ev_ebitda_ratio", Decimal("8.0")))),
        price_to_sales=from_decimal(to_decimal(data.get("price_to_sales", Decimal("2.0")))),
        price_to_book=from_decimal(to_decimal(data.get("price_to_book", Decimal("3.0")))),
        dividend_yield=from_decimal(to_decimal(data.get("dividend_yield", Decimal("0.02")))),
        beta=from_decimal(to_decimal(data.get("beta", Decimal("1.2")))),
        risk_free_rate=from_decimal(to_decimal(data.get("risk_free_rate", Decimal("0.03")))),
        market_risk_premium=from_decimal(
            to_decimal(data.get("market_risk_premium", Decimal("0.07")))
        ),
    )


async def _calculate_legacy_multiples_fallback(
    calculate_multiples_valuation: Callable[..., object],
    financial_data: object,
    market_data: object,
) -> dict[str, object]:
    multiples_result = await calculate_multiples_valuation(financial_data, market_data)
    return {
        "value_low": multiples_result.get("min_value", 0),
        "value_mid": multiples_result.get("value", 0),
        "value_high": multiples_result.get("max_value", 0),
        "revenue_multiple": multiples_result.get("revenue_multiple"),
        "ebitda_multiple": multiples_result.get("ebitda_multiple"),
        "methodology": "Explicit disclosed legacy multiples fallback",
        "publication_allowed": False,
        "benchmark_contract_required": True,
    }


def _build_phase_2_result(
    *,
    service,
    result_type: Callable[..., object],
    dcf_data: dict[str, object],
    multiples_data: dict[str, object],
    start_time: float,
) -> object:
    multiples_blocked = multiples_data.get("blocked") is True
    if multiples_blocked:
        dcf_weight_decimal = Decimal("1.0")
        multiples_weight_decimal = Decimal("0.0")
    else:
        dcf_weight_decimal = Decimal("0.6")
        multiples_weight_decimal = Decimal("0.4")

    dcf_low_decimal = to_decimal(dcf_data["value_low"])
    dcf_mid_decimal = to_decimal(dcf_data["value_mid"])
    dcf_high_decimal = to_decimal(dcf_data["value_high"])
    multiples_low_decimal = to_decimal(multiples_data["value_low"])
    multiples_mid_decimal = to_decimal(multiples_data["value_mid"])
    multiples_high_decimal = to_decimal(multiples_data["value_high"])

    combined_value_low = from_decimal(
        dcf_low_decimal * dcf_weight_decimal + multiples_low_decimal * multiples_weight_decimal
    )
    combined_value_mid = from_decimal(
        dcf_mid_decimal * dcf_weight_decimal + multiples_mid_decimal * multiples_weight_decimal
    )
    combined_value_high = from_decimal(
        dcf_high_decimal * dcf_weight_decimal + multiples_high_decimal * multiples_weight_decimal
    )

    calculation_time = (time.time() - start_time) * 1000
    logger.info(f"Phase 2 intermediate calculated in {calculation_time:.2f}ms")
    service.academic_validation_service.validate_calculation()

    return result_type(
        dcf_data=dcf_data,
        multiples_data=multiples_data,
        combined_value_low=combined_value_low,
        combined_value_mid=combined_value_mid,
        combined_value_high=combined_value_high,
        confidence_score=Decimal("65.0"),
        methodology_weights={
            "dcf": from_decimal(dcf_weight_decimal),
            "multiples": from_decimal(multiples_weight_decimal),
        },
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
