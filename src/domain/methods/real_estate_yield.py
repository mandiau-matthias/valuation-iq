"""Canonical governed real-estate income-capitalisation method."""

from decimal import Decimal

from src.api.schemas.stateless_common import RealEstateYieldEvidenceContract
from src.api.schemas.stateless_response_schemas import MethodResult
from src.domain.financial_arithmetic import decimal_number, money

_money = money


def _full_equity(
    enterprise_value: Decimal,
    *,
    evidence: RealEstateYieldEvidenceContract,
) -> Decimal:
    debt: Decimal = decimal_number(evidence.property_debt, "property debt")
    cash: Decimal = decimal_number(evidence.unrestricted_cash, "unrestricted cash")
    nwc: Decimal = decimal_number(evidence.normalized_nwc_adjustment, "NWC adjustment")
    return enterprise_value - debt + cash + nwc


def calculate_real_estate_yield_result(
    *,
    evidence: RealEstateYieldEvidenceContract | None,
    ownership_multiplier: Decimal,
) -> MethodResult:
    """Capitalise governed NOI and apply one exact property EV-to-equity bridge.

    No property type, industry tag, Belgian registry or model default can enter
    this calculation.  The cap-rate distribution and every bridge amount come
    from one Titan-signed evidence contract.
    """

    if evidence is None:
        return MethodResult(
            value=None,
            method_key="real_estate_yield",
            label="Real-estate yield (income capitalisation)",
            available=False,
            unavailable_reason=(
                "Canonical property yield requires a signed, source-bound evidence contract."
            ),
            engine_version="real_estate_yield.v1",
        )
    try:
        ownership_multiplier = decimal_number(ownership_multiplier, "ownership multiplier")
        valid_ownership = Decimal(0) <= ownership_multiplier <= Decimal(1)
    except ValueError:
        valid_ownership = False
    if not valid_ownership:
        return MethodResult(
            value=None,
            method_key="real_estate_yield",
            label="Real-estate yield (income capitalisation)",
            available=False,
            unavailable_reason="Ownership multiplier must fall between zero and one.",
            engine_version="real_estate_yield.v1",
        )

    ev_low_exact = evidence.sustainable_noi / evidence.cap_rate_high
    ev_mid_exact = evidence.sustainable_noi / evidence.cap_rate_mid
    ev_high_exact = evidence.sustainable_noi / evidence.cap_rate_low
    pre_floor_full_equity = {
        "low": _full_equity(ev_low_exact, evidence=evidence),
        "mid": _full_equity(ev_mid_exact, evidence=evidence),
        "high": _full_equity(ev_high_exact, evidence=evidence),
    }
    nav_floor = evidence.governed_nav_equity_floor
    full_equity = {
        key: max(value, nav_floor) if nav_floor is not None else value
        for key, value in pre_floor_full_equity.items()
    }
    nav_floor_applied = {
        key: nav_floor is not None and full_equity[key] != pre_floor_full_equity[key]
        for key in full_equity
    }
    equity = {key: _money(value * ownership_multiplier) for key, value in full_equity.items()}
    enterprise = {
        "low": _money(ev_low_exact),
        "mid": _money(ev_mid_exact),
        "high": _money(ev_high_exact),
    }

    displayed_bridge = (
        enterprise["mid"]
        - _money(evidence.property_debt)
        + _money(evidence.unrestricted_cash)
        + _money(evidence.normalized_nwc_adjustment)
    )
    rounding_adjustment = _money(pre_floor_full_equity["mid"]) - displayed_bridge
    bridge = {
        "application_count": 1,
        "basis": "full_company_enterprise_value_to_full_company_equity_then_ownership",
        "enterprise_value": enterprise["mid"],
        "property_debt": _money(evidence.property_debt),
        "unrestricted_cash": _money(evidence.unrestricted_cash),
        "normalized_nwc_adjustment": _money(evidence.normalized_nwc_adjustment),
        "full_company_equity_before_nav_floor": _money(pre_floor_full_equity["mid"]),
        "governed_nav_equity_floor": (_money(nav_floor) if nav_floor is not None else None),
        "full_company_equity_after_nav_floor": _money(full_equity["mid"]),
        "ownership_multiplier": ownership_multiplier,
        "equity_value": equity["mid"],
        "rounding_adjustment_full_company": rounding_adjustment,
        "exact_components": {
            "enterprise_value": ev_mid_exact,
            "property_debt": evidence.property_debt,
            "unrestricted_cash": evidence.unrestricted_cash,
            "normalized_nwc_adjustment": evidence.normalized_nwc_adjustment,
            "full_company_equity_before_nav_floor": pre_floor_full_equity["mid"],
        },
        "monetary_rounding_policy": "ROUND_HALF_EVEN_0.01",
        "reconciles": displayed_bridge + rounding_adjustment
        == _money(pre_floor_full_equity["mid"]),
    }
    details = {
        "calculation_authority": "valuation_iq",
        "engine_version": "real_estate_yield.v1",
        "value_basis": "enterprise_value_then_single_equity_bridge",
        "currency": evidence.currency,
        "country_code": evidence.country_code,
        "valuation_date": evidence.valuation_date.isoformat(),
        "net_operating_income": _money(evidence.sustainable_noi),
        "net_annual_rent": _money(evidence.sustainable_noi),
        "noi_period_start": evidence.noi_period_start.isoformat(),
        "noi_period_end": evidence.noi_period_end.isoformat(),
        "noi_is_annualized": evidence.noi_is_annualized,
        "occupancy_rate": evidence.occupancy_rate,
        "cap_rate_low": evidence.cap_rate_low,
        "cap_rate_mid": evidence.cap_rate_mid,
        "cap_rate_high": evidence.cap_rate_high,
        "yield_observed_on": evidence.yield_observed_on.isoformat(),
        "yield_published_on": evidence.yield_published_on.isoformat(),
        "yield_sample_size": evidence.sample_size,
        "yield_methodology": evidence.methodology,
        "yield_methodology_version": evidence.methodology_version,
        "enterprise_value_low": enterprise["low"],
        "enterprise_value_mid": enterprise["mid"],
        "enterprise_value_high": enterprise["high"],
        "equity_value_before_nav_floor_low": _money(pre_floor_full_equity["low"]),
        "equity_value_before_nav_floor_mid": _money(pre_floor_full_equity["mid"]),
        "equity_value_before_nav_floor_high": _money(pre_floor_full_equity["high"]),
        "equity_range_low": equity["low"],
        "equity_range_mid": equity["mid"],
        "equity_range_high": equity["high"],
        "nav_floor_level": "full_company_equity",
        "nav_floor_basis": evidence.nav_floor_basis,
        "nav_floor_applied": any(nav_floor_applied.values()),
        "nav_floor_applied_by_leg": nav_floor_applied,
        "ev_to_equity_bridge": bridge,
        "evidence_contract_id": evidence.contract_id,
        "evidence_contract_hash": evidence.content_sha256,
        "evidence_revision_id": evidence.evidence_revision_id,
        "evidence_sources": [source.model_dump(mode="json") for source in evidence.sources],
        "limitations": list(evidence.limitations),
        "range_basis": {
            "schema_version": "valuation_range_basis.v1",
            "kind": "supplied_cap_rate_scenarios",
            "empirical_percentiles": False,
            "statistical_coverage": None,
            "source_contract_id": evidence.contract_id,
        },
    }

    if min(full_equity.values()) < 0:
        return MethodResult(
            value=None,
            equity_value=equity["mid"],
            equity_value_low=equity["low"],
            equity_value_high=equity["high"],
            enterprise_value=enterprise["mid"],
            enterprise_value_low=enterprise["low"],
            enterprise_value_high=enterprise["high"],
            method_key="real_estate_yield",
            label="Real-estate yield (income capitalisation)",
            available=False,
            unavailable_reason=(
                "At least one income-capitalisation equity scenario is negative after the "
                "governed property bridge; a distressed or liquidation premise is required."
            ),
            confidence="low",
            engine_version="real_estate_yield.v1",
            details=details,
        )

    return MethodResult(
        value=equity["mid"],
        value_low=equity["low"],
        value_high=equity["high"],
        equity_value=equity["mid"],
        equity_value_low=equity["low"],
        equity_value_high=equity["high"],
        enterprise_value=enterprise["mid"],
        enterprise_value_low=enterprise["low"],
        enterprise_value_high=enterprise["high"],
        value_basis="equity_value",
        method_key="real_estate_yield",
        label="Real-estate yield (income capitalisation)",
        available=True,
        confidence="high",
        engine_version="real_estate_yield.v1",
        details=details,
    )
