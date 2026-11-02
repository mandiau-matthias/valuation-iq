"""SDE (Seller's Discretionary Earnings) valuation method.

Thin omni-calc adapter. The base-multiple lookup tables live in
``sde_engine.resolve_sde_multiple``; the calibration cascade lives in
``services.reports.sde_channel``. Publishing an SDE method card as market
evidence requires the calling boundary to attach a resolved benchmark
contract or an explicitly accepted disclosed fallback.

The omni-calc SDE method emits a fully channel-coherent ``MethodResult``:
``value`` is the equity computed from ``sde × applied_sde_multiple − net_debt``,
``multiple_used`` is the *applied* SDE multiple after the calibration
cascade, and ``details`` carries the cascade itself plus the SDE bridge so
the report rendering layer never has to re-derive any of this.
"""

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Protocol, SupportsFloat, SupportsIndex

from src.api.schemas.method_details import build_sde_details
from src.api.schemas.stateless_api import MethodResult
from src.domain.financial_arithmetic import FinancialNumber, decimal_number, money
from src.domain.sde_multiple_resolution import resolve_sde_multiple
from src.services.reports.sde_channel import SdeChannelInputs, SdeChannelResult, build_sde_channel

from ._shared import debt_overhang_details, equity_from_ev

Floatable = str | bytes | SupportsFloat | SupportsIndex


class OwnerDependencySignal(Protocol):
    overall_dependency_score: object


@dataclass(frozen=True)
class SdeSalaryInputs:
    owner_salary_estimate: Decimal
    actual_addback: Decimal
    owner_salary_source: str
    sde: Decimal


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (str, bytes, SupportsFloat, SupportsIndex)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _unavailable_sde_result(reason: str) -> MethodResult:
    return MethodResult(
        value=None,
        method_key="sde_multiple",
        label="SDE-multiple",
        available=False,
        unavailable_reason=reason,
    )


def _sde_input_unavailable_reason(*, ebitda: Decimal, revenue: Decimal) -> str | None:
    if not math.isfinite(revenue) or not math.isfinite(ebitda):
        return "SDE vereist geldige numerieke invoer voor omzet en EBITDA."
    if revenue <= 0:
        return "SDE vereist positieve omzet als basis."
    if revenue > 5_000_000:
        return "SDE is bedoeld voor bedrijven met omzet < €5M."
    if ebitda <= 0:
        return "SDE vereist positieve EBITDA als basis."
    return None


def _sde_salary_inputs(
    *,
    ebitda: Decimal,
    revenue: Decimal,
    owner_salary_addback: Optional[Decimal],
) -> SdeSalaryInputs:
    owner_salary_estimate = min(revenue * Decimal(".15"), Decimal(120_000))
    if owner_salary_addback is None or owner_salary_addback < 0:
        raise ValueError("SDE requires accepted owner-compensation evidence")
    actual_addback = owner_salary_addback
    owner_salary_source = "trial_balance"
    return SdeSalaryInputs(
        owner_salary_estimate=owner_salary_estimate,
        actual_addback=actual_addback,
        owner_salary_source=owner_salary_source,
        sde=ebitda + actual_addback,
    )


def _dependency_adjusted_base_multiple(
    *,
    base_multiple: float,
    owner_dependency: OwnerDependencySignal | None,
) -> float:
    # Compatibility seam only. Owner dependency is governed and priced exactly
    # once in the equity-side waterfall, never again inside an SDE multiple.
    del owner_dependency
    return base_multiple


def _business_size_for_revenue(revenue: Decimal, business_size: Optional[str]) -> str:
    if business_size is not None:
        return business_size
    if revenue < 500_000:
        return "micro"
    if revenue < 2_000_000:
        return "small"
    return "lower_middle"


def _sde_channel_inputs(
    *,
    salary_inputs: SdeSalaryInputs,
    sde_base_multiple: float,
    revenue: Decimal,
    total_debt: Decimal,
    cash: Decimal,
    nwc_adjustment: Decimal,
    owner_role: str,
    num_owners: int,
    business_size: str,
    country_code: str,
    industry: Optional[str],
    business_type_id: Optional[str],
) -> SdeChannelInputs:
    return SdeChannelInputs(
        sde_value=Decimal(str(salary_inputs.sde)),
        sde_base_multiple=Decimal(str(sde_base_multiple)),
        revenue=Decimal(str(revenue)),
        total_debt=Decimal(str(total_debt)),
        cash=Decimal(str(cash)),
        nwc_adjustment=Decimal(str(nwc_adjustment)),
        owner_salary_addback=Decimal(str(salary_inputs.actual_addback)),
        owner_salary_estimate=Decimal(str(salary_inputs.owner_salary_estimate)),
        owner_salary_source=salary_inputs.owner_salary_source,
        owner_role=owner_role or "working",
        num_owners=int(num_owners or 1),
        business_size=business_size,
        country_code=country_code or "BE",
        industry=industry or "",
        business_type_id=business_type_id or "",
    )


def _negative_equity_sde_result(
    *,
    equity: Decimal,
    ev: Decimal,
    total_debt: Decimal,
    cash: Decimal,
    ownership_multiplier: Decimal,
    nwc_adjustment: Decimal,
    total_adjustment: float,
    salary_inputs: SdeSalaryInputs,
    applied_multiple: Decimal,
) -> MethodResult:
    return MethodResult(
        value=Decimal(str(round(equity, 2))),
        method_key="sde_multiple",
        label="SDE-multiple",
        available=False,
        unavailable_reason="Na aftrek van schulden resteert er geen positieve aandeelhouderswaarde.",
        details={
            **debt_overhang_details(
                enterprise_value=ev,
                equity_value=equity,
                total_debt=total_debt,
                cash=cash,
                ownership_multiplier=ownership_multiplier,
                nwc_adjustment=nwc_adjustment,
                total_adjustment=total_adjustment,
            ),
            "sde": round(salary_inputs.sde, 2),
            "owner_salary_addback": round(salary_inputs.actual_addback, 2),
            "owner_salary_source": salary_inputs.owner_salary_source,
            "sde_applied_multiple": round(applied_multiple, 4),
        },
    )


def _available_sde_result(
    *,
    equity: Decimal,
    ev: Decimal,
    salary_inputs: SdeSalaryInputs,
    sde_base_multiple: float,
    applied_multiple: Decimal,
    channel: SdeChannelResult,
    ownership_multiplier: Decimal,
) -> MethodResult:
    equity_low = channel.equity_value_low * ownership_multiplier
    equity_high = channel.equity_value_high * ownership_multiplier
    return MethodResult(
        value=Decimal(str(round(equity, 2))),
        value_low=Decimal(str(round(equity_low, 2))),
        value_high=Decimal(str(round(equity_high, 2))),
        equity_value=money(equity),
        equity_value_low=money(equity_low),
        equity_value_high=money(equity_high),
        enterprise_value=money(ev),
        enterprise_value_low=money(channel.enterprise_value_low),
        enterprise_value_high=money(channel.enterprise_value_high),
        method_key="sde_multiple",
        label="SDE-multiple",
        multiple_used=Decimal(str(round(applied_multiple, 4))),
        available=True,
        details=build_sde_details(
            sde=round(salary_inputs.sde, 2),
            owner_salary_addback=round(salary_inputs.actual_addback, 2),
            owner_salary_source=salary_inputs.owner_salary_source,
            owner_salary_estimate=round(salary_inputs.owner_salary_estimate, 2),
            enterprise_value=round(ev, 2),
            enterprise_value_low=round(channel.enterprise_value_low, 2),
            enterprise_value_high=round(channel.enterprise_value_high, 2),
            sde_base_multiple=round(sde_base_multiple, 4),
            sde_applied_multiple=round(applied_multiple, 4),
            sde_multiple_p25=round(channel.sde_multiple_p25, 4),
            sde_multiple_p75=round(channel.sde_multiple_p75, 4),
            equity_range_low=round(equity_low, 2),
            equity_range_high=round(equity_high, 2),
            owner_role=channel.owner_role,
            owner_concentration_tier=channel.owner_concentration_tier,
            owner_concentration_adjustment=channel.owner_concentration_adjustment,
            size_discount_adjustment=channel.size_discount_adjustment,
            liquidity_discount_adjustment=channel.liquidity_discount_adjustment,
            belgian_market_premium=channel.belgian_market_premium,
            sde_calibration_steps=channel.calibration_steps,
            sde_bridge=channel.sde_bridge,
        ),
    )


def calculate_sde_result(
    *,
    ebitda: FinancialNumber,
    revenue: FinancialNumber,
    total_adjustment: float,
    total_debt: FinancialNumber,
    cash: FinancialNumber,
    owner_dependency: OwnerDependencySignal | None,
    ownership_multiplier: FinancialNumber,
    owner_salary_addback: Optional[FinancialNumber] = None,
    nwc_adjustment: FinancialNumber = 0.0,
    business_type_id: Optional[str] = None,
    industry: Optional[str] = None,
    country_code: str = "BE",
    num_owners: int = 1,
    owner_role: str = "working",
    business_size: Optional[str] = None,
) -> MethodResult:
    """SDE valuation for Omni-Calc.

    SDE = EBITDA + owner salary add-back.  The raw table lookup is treated as
    fallback calibration unless an upstream Delphi benchmark contract explicitly
    authorizes publication for the SDE metric.

    ``owner_salary_addback`` must be accepted/evidence-linked input. A
    revenue-percentage heuristic may be useful for a proposed scenario, but it
    is never allowed to enter the priced method result.
    """
    try:
        ebitda = decimal_number(ebitda, "EBITDA")
        revenue = decimal_number(revenue, "revenue")
        total_debt = decimal_number(total_debt, "financial debt")
        cash = decimal_number(cash, "cash")
        nwc_adjustment = decimal_number(nwc_adjustment, "NWC adjustment")
        ownership_multiplier = decimal_number(ownership_multiplier, "ownership")
        if owner_salary_addback is not None:
            owner_salary_addback = decimal_number(owner_salary_addback, "owner compensation")
    except ValueError:
        return _unavailable_sde_result("SDE vereist geldige numerieke financiële invoer.")
    unavailable_reason = _sde_input_unavailable_reason(
        ebitda=ebitda,
        revenue=revenue,
    )
    if unavailable_reason:
        return _unavailable_sde_result(unavailable_reason)
    if (
        owner_salary_addback is None
        or not math.isfinite(owner_salary_addback)
        or owner_salary_addback < 0
    ):
        return _unavailable_sde_result(
            "SDE vereist geaccepteerde, bewijsgekoppelde eigenaarcompensatie; "
            "een omzetheuristiek wordt niet geprijsd."
        )

    salary_inputs = _sde_salary_inputs(
        ebitda=ebitda,
        revenue=revenue,
        owner_salary_addback=owner_salary_addback,
    )
    sde_base_multiple = _dependency_adjusted_base_multiple(
        base_multiple=float(resolve_sde_multiple(revenue, business_type_id, industry)),
        owner_dependency=owner_dependency,
    )
    resolved_business_size = _business_size_for_revenue(revenue, business_size)
    channel = build_sde_channel(
        _sde_channel_inputs(
            salary_inputs=salary_inputs,
            sde_base_multiple=sde_base_multiple,
            revenue=revenue,
            total_debt=total_debt,
            cash=cash,
            nwc_adjustment=nwc_adjustment,
            owner_role=owner_role,
            num_owners=num_owners,
            business_size=resolved_business_size,
            country_code=country_code,
            industry=industry,
            business_type_id=business_type_id,
        )
    )

    applied_multiple = decimal_number(channel.sde_applied_multiple)
    # The SDE channel already embeds owner concentration, size, illiquidity
    # and country calibration in its applied multiple. Applying the generic
    # ``total_adjustment`` again in the EV→equity bridge would duplicate those
    # discounts. Only debt, cash, NWC and the ownership share belong here.
    ev = salary_inputs.sde * applied_multiple
    equity = equity_from_ev(
        ev,
        total_adjustment=0,
        total_debt=total_debt,
        cash=cash,
        nwc_adjustment=nwc_adjustment,
        ownership_multiplier=ownership_multiplier,
    )
    # Reconcile the channel to exact source earnings before the public method boundary.
    channel.enterprise_value = ev
    channel.enterprise_value_low = salary_inputs.sde * decimal_number(channel.sde_multiple_p25)
    channel.enterprise_value_high = salary_inputs.sde * decimal_number(channel.sde_multiple_p75)
    channel.equity_value_low = equity_from_ev(
        channel.enterprise_value_low,
        total_adjustment=0,
        total_debt=total_debt,
        cash=cash,
        nwc_adjustment=nwc_adjustment,
    )
    channel.equity_value_high = equity_from_ev(
        channel.enterprise_value_high,
        total_adjustment=0,
        total_debt=total_debt,
        cash=cash,
        nwc_adjustment=nwc_adjustment,
    )

    if equity <= 0:
        return _negative_equity_sde_result(
            equity=equity,
            ev=ev,
            total_debt=total_debt,
            cash=cash,
            ownership_multiplier=ownership_multiplier,
            nwc_adjustment=nwc_adjustment,
            total_adjustment=0.0,
            salary_inputs=salary_inputs,
            applied_multiple=applied_multiple,
        )

    result = _available_sde_result(
        equity=equity,
        ev=ev,
        salary_inputs=salary_inputs,
        sde_base_multiple=sde_base_multiple,
        applied_multiple=applied_multiple,
        channel=channel,
        ownership_multiplier=ownership_multiplier,
    )

    if result.details is not None:
        result.details["pricing_metric"] = salary_inputs.sde
        result.details["pricing_multiple"] = applied_multiple
        result.details["range_basis"] = {
            "schema_version": "valuation_range_basis.v1",
            "kind": "assumed_multiple_spread",
            "assumed_spread": Decimal(".15"),
            "empirical_percentiles": False,
            "statistical_coverage": None,
        }
        result.details["calibration_evidence_status"] = (
            "heuristic_assumptions_not_empirically_validated"
        )
    return result
