"""Machine-governed public profile for the canonical ValuationIQ engine.

This module is deliberately an input-policy adapter, not a valuation method.
The canonical Omni registry remains the sole calculator.  The adapter verifies
Titan's machine-attested producer and Business Types modeled-prior contracts,
then constrains the normal stateless request to publication-safe inputs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from src.api.routes.valuation.calculators.dcf_country_defaults import (
    INDUSTRY_DEFAULTS,
    resolve_country_defaults,
)
from src.api.schemas.stateless_api import CalculateRequest
from src.domain.discount_rate_calculator import (
    FALLBACK_DEBT_WEIGHT,
    FALLBACK_EQUITY_WEIGHT,
)
from src.domain.method_keys import CANONICAL_METHOD_KEYS
from src.domain.market_defaults import get_default_equity_risk_premium, get_risk_free_rate
from src.utils.percentage_input_contract import with_fraction_inputs

PUBLIC_ADAPTIVE_PROFILE_VERSION = "public_adaptive_profile.v2"
PUBLIC_ADAPTIVE_POLICY_VERSION = "public_adaptive_profile_v2"
LEGACY_PUBLIC_ADAPTIVE_POLICY_VERSION = "public_adaptive_profile_v1"
PUBLIC_MODELED_PRIOR_SCHEMA = "public_modeled_prior_contract.v1"
PUBLIC_PRODUCER_SCHEMA = "public_adaptive_producer_contract.v1"
PUBLIC_MODELED_PRIOR_SCHEMA_V2 = "public_modeled_prior_contract.v2"
PUBLIC_PRODUCER_SCHEMA_V2 = "public_adaptive_producer_contract.v2"
PUBLIC_MINIMUM_HALF_BAND = Decimal("0.30")
PUBLIC_MODELED_DCF_SCHEMA = "public_modeled_dcf_resolution.v1"
PUBLIC_MODELED_DCF_POLICY_VERSION = "valuation_iq_public_dcf_defaults.v4"
SUPPORTED_PUBLIC_MODELED_DCF_POLICY_VERSIONS = frozenset(
    {
        "valuation_iq_public_dcf_defaults.v1",
        "valuation_iq_public_dcf_defaults.v2",
        "valuation_iq_public_dcf_defaults.v3",
        PUBLIC_MODELED_DCF_POLICY_VERSION,
    }
)


class PublicAdaptiveProfileError(ValueError):
    """A public request is not bound tightly enough to calculate."""


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json_bytes(value)).hexdigest()}"


def public_method_registry_hash() -> str:
    return _sha256(list(CANONICAL_METHOD_KEYS))


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicAdaptiveProfileError(f"{field} must be an object")
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicAdaptiveProfileError(f"{field} must be a non-empty string")
    return value.strip()


def _decimal(value: object, *, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PublicAdaptiveProfileError(f"{field} must be a finite decimal") from exc
    if not parsed.is_finite():
        raise PublicAdaptiveProfileError(f"{field} must be a finite decimal")
    return parsed


def _timestamp(value: object, *, field: str) -> datetime:
    raw = _text(value, field=field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublicAdaptiveProfileError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _verify_contract_hash(contract: Mapping[str, Any], *, field: str) -> str:
    claimed = _text(contract.get("contract_hash"), field=f"{field}.contract_hash")
    material = dict(contract)
    material.pop("contract_hash", None)
    expected = _sha256(material)
    if claimed != expected:
        raise PublicAdaptiveProfileError(f"{field}.contract_hash does not match its content")
    return claimed


def _verify_producer_contract(
    request: CalculateRequest,
    contract: Mapping[str, Any],
    *,
    now: datetime,
) -> str:
    schema = contract.get("schema_version")
    if schema not in {PUBLIC_PRODUCER_SCHEMA, PUBLIC_PRODUCER_SCHEMA_V2}:
        raise PublicAdaptiveProfileError("public producer schema is unsupported")
    contract_hash = _verify_contract_hash(contract, field="public_adaptive_producer_contract")
    if contract.get("authority") != "machine_governed_public_producer":
        raise PublicAdaptiveProfileError("public producer authority is unsupported")
    if contract.get("country_code") != request.country_code:
        raise PublicAdaptiveProfileError("public producer country does not match request")
    expected_policy = (
        PUBLIC_ADAPTIVE_POLICY_VERSION
        if schema == PUBLIC_PRODUCER_SCHEMA_V2
        else LEGACY_PUBLIC_ADAPTIVE_POLICY_VERSION
    )
    if contract.get("policy_version") != expected_policy:
        raise PublicAdaptiveProfileError("public producer policy version is unsupported")
    if contract.get("run_schema_version") != "valuation_run.v2":
        raise PublicAdaptiveProfileError("public producer run schema is unsupported")
    if contract.get("max_public_grade") not in {"T2-M", "T3-M"}:
        raise PublicAdaptiveProfileError("public producer graph-grade ceiling is invalid")
    if contract.get("method_registry_hash") != public_method_registry_hash():
        raise PublicAdaptiveProfileError("public producer method registry has drifted")
    for field in ("taxonomy_hash", "benchmark_hash", "evidence_profile_hash"):
        value = _text(contract.get(field), field=f"public_adaptive_producer_contract.{field}")
        if not value.startswith("sha256:") or len(value) != 71:
            raise PublicAdaptiveProfileError(f"public producer {field} is invalid")
    valid_from = _timestamp(contract.get("valid_from"), field="producer.valid_from")
    valid_until = _timestamp(contract.get("valid_until"), field="producer.valid_until")
    if valid_until <= valid_from or now < valid_from or now > valid_until:
        raise PublicAdaptiveProfileError("public producer contract is outside its validity window")
    valuation_case = request.valuation_case
    if valuation_case is None or valuation_case.policy_version != expected_policy:
        raise PublicAdaptiveProfileError("signed valuation case is not bound to the public policy")
    return contract_hash


def _verify_modeled_prior_contract(
    request: CalculateRequest,
    contract: Mapping[str, Any],
) -> tuple[str, Decimal, Decimal, Decimal]:
    schema = contract.get("schema_version")
    if schema not in {PUBLIC_MODELED_PRIOR_SCHEMA, PUBLIC_MODELED_PRIOR_SCHEMA_V2}:
        raise PublicAdaptiveProfileError("public modeled-prior schema is unsupported")
    contract_hash = _verify_contract_hash(contract, field="public_modeled_prior_contract")
    if contract.get("authority") != "business_types_modeled_prior":
        raise PublicAdaptiveProfileError("public modeled-prior authority is unsupported")
    if contract.get("country_code") != request.country_code:
        raise PublicAdaptiveProfileError("modeled-prior country does not match request")
    if contract.get("business_type_id") != request.business_type_calibration.business_type_id:
        raise PublicAdaptiveProfileError("modeled-prior business type does not match calibration")
    if schema == PUBLIC_MODELED_PRIOR_SCHEMA_V2:
        request_mix = list(request.business_type_mix or [])
        contract_mix = contract.get("business_type_mix")
        contract_weights = contract.get("business_type_weights")
        if not request_mix or not isinstance(contract_mix, list) or not contract_mix:
            raise PublicAdaptiveProfileError("public v2 modeled prior requires a business-type mix")
        if _canonical_json_bytes(contract_mix) != _canonical_json_bytes(request_mix):
            raise PublicAdaptiveProfileError(
                "modeled-prior business-type mix does not match request"
            )
        expected_weights = {
            str(segment.get("business_type_id")): segment.get("weight")
            for segment in request_mix
            if isinstance(segment, Mapping)
        }
        if not isinstance(contract_weights, Mapping) or _canonical_json_bytes(
            dict(contract_weights)
        ) != _canonical_json_bytes(expected_weights):
            raise PublicAdaptiveProfileError(
                "modeled-prior business-type weights do not match request"
            )
    metric = contract.get("metric")
    if metric not in {"ev_ebitda", "ev_revenue"}:
        raise PublicAdaptiveProfileError("public modeled prior metric is unsupported")
    allowed_grades = {"T2-M"} if schema == PUBLIC_MODELED_PRIOR_SCHEMA else {"T2-M", "T3-M"}
    if (
        contract.get("confidence") != "low"
        or contract.get("max_public_grade") not in allowed_grades
    ):
        raise PublicAdaptiveProfileError(
            "modeled priors must remain low-confidence and within their public grade ceiling"
        )

    distribution = _mapping(contract.get("distribution"), field="modeled_prior.distribution")
    raw_low = _decimal(distribution.get("p25"), field="modeled_prior.distribution.p25")
    median = _decimal(distribution.get("median"), field="modeled_prior.distribution.median")
    raw_high = _decimal(distribution.get("p75"), field="modeled_prior.distribution.p75")
    if raw_low <= 0 or median <= 0 or raw_high <= 0 or not raw_low <= median <= raw_high:
        raise PublicAdaptiveProfileError(f"modeled-prior {metric} distribution is invalid")
    calibration_median = (
        request.business_type_calibration.ev_ebitda_median
        if metric == "ev_ebitda"
        else request.business_type_calibration.ev_revenue_median
    )
    if calibration_median != median:
        raise PublicAdaptiveProfileError("modeled-prior median does not match Business Types")

    widened_low = min(raw_low, median * (Decimal("1") - PUBLIC_MINIMUM_HALF_BAND))
    widened_high = max(raw_high, median * (Decimal("1") + PUBLIC_MINIMUM_HALF_BAND))
    return contract_hash, widened_low, median, widened_high


def _apply_modeled_prior(
    request: CalculateRequest,
    contract: Mapping[str, Any],
) -> tuple[str, str, dict[str, str]]:
    contract_hash, low, median, high = _verify_modeled_prior_contract(request, contract)
    metric = str(contract["metric"])
    if metric == "ev_ebitda":
        request.business_type_calibration.ev_ebitda_p25 = low
        request.business_type_calibration.ev_ebitda_median = median
        request.business_type_calibration.ev_ebitda_p75 = high
    else:
        request.business_type_calibration.ev_revenue_p25 = low
        request.business_type_calibration.ev_revenue_median = median
        request.business_type_calibration.ev_revenue_p75 = high
    return contract_hash, metric, {"low": str(low), "mid": str(median), "high": str(high)}


def _public_normalizations_are_source_reproducible(request: CalculateRequest) -> bool:
    for adjustment in request.normalizations:
        source = str(adjustment.source or "").strip().lower()
        status = str(adjustment.status or "").strip().lower()
        if (
            source not in {"official_filing", "official_registry", "source_reproducible"}
            or status not in {"accepted", "verified", "applied"}
            or not str(adjustment.evidence_id or "").strip()
        ):
            return False
    return True


def _has_complete_public_equity_bridge(
    metadata: Mapping[str, Any],
    year: int,
) -> bool:
    by_year = metadata.get("public_financial_inputs_by_year")
    year_inputs = (
        by_year.get(str(year))
        if isinstance(by_year, Mapping)
        else metadata.get("public_financial_inputs")
    )
    if not isinstance(year_inputs, list):
        return False
    amounts = {
        str(row.get("metric")): row.get("amount")
        for row in year_inputs
        if isinstance(row, Mapping)
        and row.get("metric") in {"total_debt", "lease_liabilities", "cash"}
    }
    return all(
        amounts.get(metric) is not None for metric in ("total_debt", "lease_liabilities", "cash")
    )


def _has_complete_public_wacc_capital_structure(
    metadata: Mapping[str, Any],
    year: int,
) -> bool:
    """Require source-bound debt and equity before using observed WACC weights.

    A complete EV-to-equity bridge and a complete WACC capital structure are
    different evidence claims. Public Adaptive must not interpret a lone book
    equity value plus the EV-only neutral debt bridge as an observed no-debt
    company. If either WACC leg is absent, the canonical DCF engine owns the
    disclosed 70/30 modeled fallback used by the private/Venus flow.
    """

    by_year = metadata.get("public_financial_inputs_by_year")
    year_inputs = (
        by_year.get(str(year))
        if isinstance(by_year, Mapping)
        else metadata.get("public_financial_inputs")
    )
    if not isinstance(year_inputs, list) or not _has_complete_public_equity_bridge(metadata, year):
        return False
    observed: dict[str, Decimal] = {}
    for row in year_inputs:
        if not (
            isinstance(row, Mapping)
            and row.get("metric") in {"total_debt", "equity"}
            and row.get("amount") is not None
            and row.get("used") is True
        ):
            continue
        try:
            amount = Decimal(str(row.get("amount")))
        except (InvalidOperation, TypeError, ValueError):
            return False
        if not amount.is_finite() or amount < 0:
            return False
        observed[str(row.get("metric"))] = amount
    return set(observed) == {"total_debt", "equity"} and sum(observed.values()) > 0


def _public_wacc_capital_structure(
    metadata: Mapping[str, Any],
    year: int,
) -> tuple[Decimal, Decimal] | None:
    if not _has_complete_public_wacc_capital_structure(metadata, year):
        return None
    by_year = metadata.get("public_financial_inputs_by_year")
    year_inputs = (
        by_year.get(str(year))
        if isinstance(by_year, Mapping)
        else metadata.get("public_financial_inputs")
    )
    amounts = {
        str(row.get("metric")): Decimal(str(row.get("amount")))
        for row in year_inputs
        if isinstance(row, Mapping)
        and row.get("metric") in {"total_debt", "equity"}
        and row.get("amount") is not None
        and row.get("used") is True
    }
    return amounts["total_debt"], amounts["equity"]


def _fraction(value: object) -> Decimal | None:
    """Normalize a percentage/fraction without accepting booleans or NaN."""

    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not parsed.is_finite():
        return None
    if abs(parsed) > 1:
        parsed /= Decimal("100")
    return parsed


def _clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return min(high, max(low, value))


def _public_input_amount(
    metadata: Mapping[str, Any],
    *,
    fiscal_year: int,
    metric: str,
) -> Decimal | None:
    by_year = metadata.get("public_financial_inputs_by_year")
    raw_inputs = (
        by_year.get(str(fiscal_year))
        if isinstance(by_year, Mapping)
        else metadata.get("public_financial_inputs")
    )
    if not isinstance(raw_inputs, list):
        return None
    for raw in raw_inputs:
        row = raw if isinstance(raw, Mapping) else {}
        if row.get("metric") != metric:
            continue
        try:
            amount = Decimal(str(row.get("amount")))
        except (InvalidOperation, TypeError, ValueError):
            return None
        return amount if amount.is_finite() else None
    return None


def _positive_public_actuals(
    metadata: Mapping[str, Any],
    request: CalculateRequest,
    metric: str,
) -> list[tuple[int, Decimal]]:
    rows: list[tuple[int, Decimal]] = []
    seen: set[int] = set()
    for financial_year in [*request.historical_years, request.current_year]:
        if financial_year.year in seen:
            continue
        seen.add(financial_year.year)
        amount = _public_input_amount(
            metadata,
            fiscal_year=financial_year.year,
            metric=metric,
        )
        if amount is not None and amount > 0:
            rows.append((financial_year.year, amount))
    return sorted(rows)


def _historical_revenue_growth(
    metadata: Mapping[str, Any],
    request: CalculateRequest,
) -> tuple[Decimal | None, int]:
    actuals = _positive_public_actuals(metadata, request, "revenue")
    if len(actuals) < 2:
        return None, len(actuals)
    first_year, first_revenue = actuals[0]
    latest_year, latest_revenue = actuals[-1]
    elapsed = latest_year - first_year
    if elapsed <= 0 or first_revenue <= 0 or latest_revenue <= 0:
        return None, len(actuals)
    # Decimal has no portable fractional exponent on older supported Python
    # runtimes. Float is used only to derive a bounded assumption, then sealed
    # back into a decimal string before it can affect the engine.
    cagr = Decimal(str((float(latest_revenue / first_revenue) ** (1 / elapsed)) - 1))
    return _clamp(cagr, Decimal("-0.15"), Decimal("0.25")), len(actuals)


def _resolve_public_modeled_dcf(
    request: CalculateRequest,
    metadata: Mapping[str, Any],
) -> dict[str, object]:
    """Resolve publication-safe DCF defaults inside ValuationIQ.

    Public filings provide actual revenue and/or EBITDA. Forecast drivers are
    explicitly modelled assumptions, never historical evidence. The same DCF
    engine, country pack, Business Types margin and methodology preferences
    used by the private flow remain the numeric authority.
    """

    fiscal_year = request.current_year.year
    filed_revenue = _public_input_amount(
        metadata,
        fiscal_year=fiscal_year,
        metric="revenue",
    )
    filed_ebitda = _public_input_amount(
        metadata,
        fiscal_year=fiscal_year,
        metric="ebitda",
    )
    calibration = request.business_type_calibration
    raw_industry = getattr(request.industry, "value", request.industry)
    industry_key = str(raw_industry or "").strip().lower()
    industry_defaults = INDUSTRY_DEFAULTS.get(industry_key, INDUSTRY_DEFAULTS["other"])
    typical_margin = _fraction(calibration.typical_ebitda_margin)
    margin_default_source = "business_types_typical_margin"
    if typical_margin is None:
        typical_margin = _fraction(industry_defaults.get("ebitda_margin"))
        margin_default_source = "valuation_iq_industry_default"
    if typical_margin is not None:
        typical_margin = _clamp(typical_margin, Decimal("0.01"), Decimal("0.60"))

    reason_codes: list[str] = []
    base_revenue: Decimal | None = filed_revenue if filed_revenue and filed_revenue > 0 else None
    base_ebitda: Decimal | None = filed_ebitda if filed_ebitda and filed_ebitda > 0 else None
    source_metric = "revenue_and_ebitda" if base_revenue and base_ebitda else None
    margin_source = "filed_revenue_and_ebitda" if source_metric else None

    # A reported loss is adverse evidence, not an absent field. Do not replace
    # it with a positive sector margin merely to force a DCF leg.
    if filed_ebitda is not None and filed_ebitda <= 0:
        reason_codes.append("reported_non_positive_ebitda")
    elif base_revenue is not None and base_ebitda is None and typical_margin is not None:
        base_ebitda = base_revenue * typical_margin
        source_metric = "revenue"
        margin_source = margin_default_source
    elif base_ebitda is not None and base_revenue is None and typical_margin is not None:
        base_revenue = base_ebitda / typical_margin
        source_metric = "ebitda"
        margin_source = margin_default_source

    if base_revenue is None or base_revenue <= 0:
        reason_codes.append("positive_revenue_basis_unavailable")
    if base_ebitda is None or base_ebitda <= 0:
        reason_codes.append("positive_ebitda_basis_unavailable")
    if (filed_revenue is None or filed_revenue <= 0) != (filed_ebitda is None or filed_ebitda <= 0):
        if typical_margin is None:
            reason_codes.append("business_types_margin_unavailable")

    # Public callers contribute official company evidence, not macro/WACC
    # numbers. Resolve the same ValuationIQ-owned country and market defaults
    # used by the private DCF stack, then replace Titan's non-numeric delegation
    # placeholder before the DCF method can consume it.
    country_defaults: Mapping[str, Any] | None = None
    try:
        country_defaults = resolve_country_defaults(request.country_code)
    except (KeyError, TypeError, ValueError):
        reason_codes.append("valuation_iq_country_dcf_defaults_unavailable")
    if country_defaults is not None:
        risk_free_rate, risk_free_rate_source = get_risk_free_rate(request.country_code)
        equity_risk_premium = get_default_equity_risk_premium(request.country_code)
        gdp_growth = _fraction(country_defaults.get("gdp_growth"))
        inflation = _fraction(country_defaults.get("inflation"))
        terminal_default = (
            _clamp(gdp_growth, Decimal("0.005"), Decimal("0.04"))
            if gdp_growth is not None
            else None
        )
        request.economic_context = request.economic_context.model_copy(
            update={
                "risk_free_rate": risk_free_rate,
                "risk_free_rate_source": risk_free_rate_source,
                "risk_free_rate_is_override": False,
                "gdp_growth_rate": gdp_growth or Decimal("0"),
                "terminal_growth_rate": terminal_default or Decimal("0"),
                "inflation_rate": inflation,
                "equity_risk_premium": equity_risk_premium,
                "market_risk_premium": None,
                "erp": None,
                "country_code": request.country_code,
                "source": "valuation_iq_public_modeled_defaults.v1",
                "schema_version": None,
                "snapshot_id": None,
                "snapshot_hash": None,
                "snapshot_issuer": None,
                "risk_free_rate_observed_at": None,
                "equity_risk_premium_observed_at": None,
                "growth_rates_observed_at": None,
                "source_references": [],
            }
        )
    economic = request.economic_context.model_dump(mode="json")
    economic_growth = _fraction(
        economic.get("gdp_growth_rate", economic.get("terminal_growth_rate"))
    )
    terminal_growth = _fraction(economic.get("terminal_growth_rate"))
    if economic_growth is None:
        reason_codes.append("economic_growth_unavailable")
    if terminal_growth is None:
        reason_codes.append("terminal_growth_unavailable")

    observed_growth, observed_growth_years = _historical_revenue_growth(metadata, request)
    industry_growth = _fraction(industry_defaults.get("growth"))
    revenue_growth = (
        observed_growth
        if observed_growth is not None
        else industry_growth if industry_growth is not None else economic_growth
    )
    if revenue_growth is not None:
        revenue_growth = _clamp(revenue_growth, Decimal("-0.15"), Decimal("0.25"))
    if terminal_growth is not None:
        terminal_growth = _clamp(terminal_growth, Decimal("0.005"), Decimal("0.04"))
    raw_tax_rate = country_defaults.get("tax_rate") if country_defaults is not None else None
    tax_rate = _fraction(raw_tax_rate)
    if tax_rate is None or tax_rate <= 0:
        reason_codes.append("valuation_iq_country_tax_default_unavailable")

    margin = (
        base_ebitda / base_revenue
        if base_revenue is not None and base_revenue > 0 and base_ebitda is not None
        else None
    )
    if margin is not None:
        margin = _clamp(margin, Decimal("-0.10"), Decimal("0.40"))
    industry_capex_ratio = _fraction(industry_defaults.get("capex_to_revenue"))
    capex_ratio = (
        _clamp(industry_capex_ratio, Decimal("0.01"), Decimal("0.15"))
        if industry_capex_ratio is not None
        else (
            _clamp(
                max(Decimal("0.02"), abs(margin) * Decimal("0.20")),
                Decimal("0.02"),
                Decimal("0.06"),
            )
            if margin is not None
            else None
        )
    )
    da_ratio = (
        _clamp(capex_ratio * Decimal("0.80"), Decimal("0.02"), Decimal("0.05"))
        if capex_ratio is not None
        else None
    )

    available = not reason_codes and all(
        value is not None
        for value in (
            base_revenue,
            base_ebitda,
            revenue_growth,
            margin,
            capex_ratio,
            da_ratio,
            terminal_growth,
        )
    )
    assumptions = {
        "base_revenue": str(base_revenue) if base_revenue is not None else None,
        "base_ebitda": str(base_ebitda) if base_ebitda is not None else None,
        "revenue_growth": str(revenue_growth) if revenue_growth is not None else None,
        "ebitda_margin": str(margin) if margin is not None else None,
        "capex_ratio": str(capex_ratio) if capex_ratio is not None else None,
        "depreciation_amortization_ratio": str(da_ratio) if da_ratio is not None else None,
        "nwc_ratio": "0.015",
        "tax_rate": str(tax_rate) if tax_rate is not None else None,
        "terminal_growth": str(terminal_growth) if terminal_growth is not None else None,
        "projection_years": 5,
        "discounting_convention": "mid_year",
    }
    observed_wacc_capital_structure = _has_complete_public_wacc_capital_structure(
        metadata,
        fiscal_year,
    )
    wacc_policy = {
        "authority": "valuation_iq",
        "rate_model": "country_sector_capm",
        "risk_free_rate_source": "valuation_iq_country_defaults",
        "equity_risk_premium_source": "valuation_iq_country_defaults",
        "beta_source": "valuation_iq_industry_default",
        "size_premium_source": "valuation_iq_revenue_size_band",
        "cost_of_debt_source": "valuation_iq_market_context",
        "tax_rate_source": "valuation_iq_country_defaults",
        "capital_structure_source": (
            "source_bound_balance_sheet"
            if observed_wacc_capital_structure
            else "valuation_iq_public_default_70_30"
        ),
        "capital_structure_fallback": not observed_wacc_capital_structure,
        "equity_weight": (None if observed_wacc_capital_structure else str(FALLBACK_EQUITY_WEIGHT)),
        "debt_weight": (None if observed_wacc_capital_structure else str(FALLBACK_DEBT_WEIGHT)),
    }
    ignored_caller_forecast_years = sorted(
        {int(year.year) for year in request.historical_years if getattr(year, "is_forecast", False)}
    )
    material: dict[str, object] = {
        "schema_version": PUBLIC_MODELED_DCF_SCHEMA,
        "authority": "valuation_iq",
        "policy_version": PUBLIC_MODELED_DCF_POLICY_VERSION,
        "status": "available" if available else "unavailable",
        "country_code": request.country_code,
        "fiscal_year": fiscal_year,
        "business_type_id": calibration.business_type_id,
        "business_type_mix": list(request.business_type_mix or []),
        "industry_default_key": (industry_key if industry_key in INDUSTRY_DEFAULTS else "other"),
        "source_metric": source_metric,
        "margin_source": margin_source,
        "growth_source": (
            "source_bound_historical_cagr"
            if observed_growth is not None
            else (
                "valuation_iq_industry_default"
                if industry_growth is not None
                else "economic_context"
            )
        ),
        "capex_source": (
            "valuation_iq_industry_default"
            if industry_capex_ratio is not None
            else "valuation_iq_margin_derived_default"
        ),
        "historical_revenue_years_used": observed_growth_years,
        "ignored_caller_forecast_years": ignored_caller_forecast_years,
        "economic_context_hash": _sha256(economic),
        "economic_context_authority": "valuation_iq",
        "economic_context_policy": "valuation_iq_public_modeled_defaults.v1",
        "tax_rate_source": "valuation_iq_country_defaults",
        "wacc_policy": wacc_policy,
        "assumptions": assumptions,
        "reason_codes": sorted(set(reason_codes)),
        "confidence": "low",
        "forecast_classification": "modeled_forward_assumptions_not_actuals",
    }
    return {**material, "resolution_hash": _sha256(material)}


def public_modeled_dcf_is_authorized(request: CalculateRequest) -> bool:
    """Return whether this already-profiled request may use modeled DCF.

    This is consumed by the canonical methodology policy to distinguish a
    ValuationIQ-authored low-confidence public assumption set from an unsigned
    caller attempting to bypass the source-dated economic-snapshot gate.
    """

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    if metadata.get("public_adaptive_profile_v2") is not True:
        return False
    profile = metadata.get("public_adaptive_resolution")
    if not isinstance(profile, Mapping):
        return False
    resolution = profile.get("modeled_dcf_resolution")
    if not isinstance(resolution, Mapping):
        return False
    material = dict(resolution)
    claimed = material.pop("resolution_hash", None)
    if (
        resolution.get("schema_version") != PUBLIC_MODELED_DCF_SCHEMA
        or resolution.get("authority") != "valuation_iq"
        or resolution.get("policy_version") not in SUPPORTED_PUBLIC_MODELED_DCF_POLICY_VERSIONS
        or resolution.get("status") != "available"
        or not isinstance(claimed, str)
        or claimed != _sha256(material)
    ):
        return False
    context = request.business_context if isinstance(request.business_context, dict) else {}
    return context.get("public_modeled_dcf_resolution_hash") == claimed


def public_adaptive_weights_are_authorized(request: CalculateRequest) -> bool:
    """Recognize ValuationIQ-authored public Adaptive component weights.

    Generic advisor weights require a signed valuation-case decision. Public
    Adaptive weights are different: ``apply_public_adaptive_profile`` derives
    them inside ValuationIQ after verifying Titan's producer contract and the
    Business Types modeled-prior contracts. Keeping that machine-authored
    blend must not require a fictitious human decision, but a caller-provided
    or subsequently mutated weight map must still fail closed.
    """

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    if metadata.get("public_adaptive_profile_v2") is not True:
        return False
    profile = metadata.get("public_adaptive_resolution")
    if not isinstance(profile, Mapping):
        return False
    if (
        profile.get("schema_version") != PUBLIC_ADAPTIVE_PROFILE_VERSION
        or profile.get("selected_method") != "upswitch_adaptive"
        or request.selected_method != "upswitch_adaptive"
        or request.strict_user_weights is not True
        or request.user_weight_justification
        != "Machine-governed Public Adaptive evidence capability weighting."
        or not isinstance(profile.get("producer_contract_hash"), str)
    ):
        return False
    expected = profile.get("adaptive_component_weights")
    supplied = request.user_weights
    if not isinstance(expected, Mapping) or not isinstance(supplied, Mapping):
        return False
    try:
        expected_weights = {
            str(key): Decimal(str(value)).normalize() for key, value in expected.items()
        }
        supplied_weights = {
            str(key): Decimal(str(value)).normalize() for key, value in supplied.items()
        }
    except (InvalidOperation, TypeError, ValueError):
        return False
    return (
        bool(expected_weights)
        and expected_weights == supplied_weights
        and all(weight.is_finite() and weight > 0 for weight in supplied_weights.values())
        and abs(sum(supplied_weights.values()) - Decimal("1")) <= Decimal("0.000001")
    )


def bind_public_adaptive_runtime_weights(
    request: CalculateRequest,
    *,
    dcf_weight: object,
    multiples_weight: object,
) -> bool:
    """Bind the priced public blend to Adaptive's final runtime weights.

    ``apply_public_adaptive_profile`` establishes the verified method
    capability set and the Business Types preference split before the generic
    methodology selector runs.  The selector then applies ValuationIQ-owned
    readiness and evidence-quality policy (and may exclude a failed DCF leg).
    The weighted synthesis must price *that final Adaptive decision*, not the
    earlier preference split.

    Market weight is distributed only across the already-authorized market
    capabilities and in their original relative proportions.  No new method
    can enter through this binding step.  The resolved map is written back to
    the profile envelope so the existing authorization guard continues to
    fail closed if any later code mutates it.
    """

    if not public_adaptive_weights_are_authorized(request):
        return False

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    profile = metadata.get("public_adaptive_resolution")
    if not isinstance(profile, Mapping):
        return False
    authorized = profile.get("adaptive_component_weights")
    if not isinstance(authorized, Mapping):
        return False

    try:
        resolved_dcf = max(Decimal("0"), Decimal(str(dcf_weight)))
        resolved_multiples = max(Decimal("0"), Decimal(str(multiples_weight)))
        authorized_weights = {
            str(key): max(Decimal("0"), Decimal(str(value))) for key, value in authorized.items()
        }
    except (InvalidOperation, TypeError, ValueError):
        return False
    if not all(
        value.is_finite()
        for value in (resolved_dcf, resolved_multiples, *authorized_weights.values())
    ):
        return False

    total = resolved_dcf + resolved_multiples
    if total <= 0:
        return False
    resolved_dcf /= total
    resolved_multiples /= total

    market_preferences = {
        key: value for key, value in authorized_weights.items() if key != "dcf" and value > 0
    }
    if resolved_dcf > 0 and authorized_weights.get("dcf", Decimal("0")) <= 0:
        return False
    market_total = sum(market_preferences.values(), Decimal("0"))
    if resolved_multiples > 0 and market_total <= 0:
        return False

    runtime_weights: dict[str, float] = {}
    if resolved_dcf > 0:
        runtime_weights["dcf"] = float(resolved_dcf)
    if resolved_multiples > 0:
        for method_key, preference in market_preferences.items():
            runtime_weights[method_key] = float(resolved_multiples * preference / market_total)

    runtime_profile = dict(profile)
    runtime_profile.setdefault(
        "adaptive_component_preferences",
        dict(authorized),
    )
    runtime_profile["adaptive_component_weights"] = runtime_weights
    runtime_profile["adaptive_runtime_weight_policy"] = "business_archetype_readiness_evidence.v1"
    request.user_weights = runtime_weights
    request.metadata = {
        **metadata,
        "public_adaptive_resolution": runtime_profile,
    }
    return public_adaptive_weights_are_authorized(request)


def apply_public_adaptive_profile(request: CalculateRequest) -> CalculateRequest:
    """Verify and apply the public profile before canonical calculation.

    The function mutates the already validated request only to select existing
    engine policy knobs and to widen the supplied benchmark distribution.  It
    never computes a company value; `calculate_all_methods` still owns that.
    """

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    is_v2 = metadata.get("public_adaptive_profile_v2") is True
    is_v1 = metadata.get("public_adaptive_profile_v1") is True
    if not is_v2 and not is_v1:
        return request

    now = datetime.now(timezone.utc)
    producer_contract = _mapping(
        metadata.get("public_adaptive_producer_contract"),
        field="public_adaptive_producer_contract",
    )
    producer_hash = _verify_producer_contract(request, producer_contract, now=now)
    selected_method = request.selected_method or "upswitch_adaptive"
    if is_v2 and selected_method != "upswitch_adaptive":
        raise PublicAdaptiveProfileError("public v2 must enter the canonical Adaptive method")
    if is_v2 and (
        request.allow_untrusted_multiples_fallback
        or metadata.get("allow_untrusted_multiples_fallback") is True
    ):
        raise PublicAdaptiveProfileError("public v2 forbids untrusted multiples fallback")
    if selected_method not in {"upswitch_adaptive", "ebitda_multiple"}:
        raise PublicAdaptiveProfileError("public profile selected method is not authorized")
    if not _public_normalizations_are_source_reproducible(request):
        raise PublicAdaptiveProfileError(
            "public normalizations must be source-reproducible and evidence-bound"
        )
    modeled_forecast_point = bool(
        is_v2 and metadata.get("public_adaptive_modeled_forecast_point") is True
    )
    if modeled_forecast_point and not public_modeled_dcf_is_authorized(request):
        raise PublicAdaptiveProfileError(
            "public modeled forecast point is not bound to the parent DCF resolution"
        )

    resolved: dict[str, object] = {
        "schema_version": (
            PUBLIC_ADAPTIVE_PROFILE_VERSION if is_v2 else "public_adaptive_profile.v1"
        ),
        "producer_contract_hash": producer_hash,
        "selected_method": selected_method,
        "headline_value_basis": "enterprise_value",
        "historical_weighting": "current_year",
        "source_reproducible_normalizations_only": True,
        "private_discount_stack_applied": False,
    }
    resolved_bands: dict[str, dict[str, str]] = {}
    modeled_hashes: dict[str, str] = {}
    adaptive_component_weights: dict[str, float] = {}
    modeled_dcf_resolution: dict[str, object] | None = None
    if is_v2:
        raw_contracts = metadata.get("public_modeled_prior_contracts")
        if not isinstance(raw_contracts, list) or not raw_contracts:
            raise PublicAdaptiveProfileError("public v2 requires modeled-prior contracts")
        for index, raw_contract in enumerate(raw_contracts):
            modeled_contract = _mapping(
                raw_contract,
                field=f"public_modeled_prior_contracts[{index}]",
            )
            modeled_hash, metric, band = _apply_modeled_prior(request, modeled_contract)
            if metric in modeled_hashes:
                raise PublicAdaptiveProfileError("public modeled-prior metric is duplicated")
            modeled_hashes[metric] = modeled_hash
            resolved_bands[metric] = band
        current_revenue = _public_input_amount(
            metadata,
            fiscal_year=request.current_year.year,
            metric="revenue",
        )
        current_ebitda = _public_input_amount(
            metadata,
            fiscal_year=request.current_year.year,
            metric="ebitda",
        )
        available_component_keys = [
            method_key
            for metric, method_key, source_available in (
                (
                    "ev_ebitda",
                    "ebitda_multiple",
                    modeled_forecast_point or (current_ebitda is not None and current_ebitda != 0),
                ),
                (
                    "ev_revenue",
                    "omzet_multiple",
                    modeled_forecast_point or (current_revenue is not None and current_revenue > 0),
                ),
            )
            if metric in modeled_hashes and source_available
        ]
        if modeled_forecast_point:
            existing_profile = _mapping(
                metadata.get("public_adaptive_resolution"),
                field="public_adaptive_resolution",
            )
            modeled_dcf_resolution = dict(
                _mapping(
                    existing_profile.get("modeled_dcf_resolution"),
                    field="public_adaptive_resolution.modeled_dcf_resolution",
                )
            )
        else:
            modeled_dcf_resolution = _resolve_public_modeled_dcf(request, metadata)
        # Delphi may transport an unverified display forecast for other product
        # surfaces. Public Adaptive never prices those caller-authored rows.
        # Drop them before canonical DCF so ValuationIQ regenerates the forward
        # cone solely from the signed modeled-default resolution above.
        request.historical_years = [
            year for year in request.historical_years if not getattr(year, "is_forecast", False)
        ]
        dcf_available = modeled_dcf_resolution.get("status") == "available"
        dcf_preference = (
            request.business_type_calibration.dcf_preference
            if request.business_type_calibration.dcf_preference is not None
            else Decimal("0.5")
        )
        multiples_preference = (
            request.business_type_calibration.multiples_preference
            if request.business_type_calibration.multiples_preference is not None
            else Decimal("0.5")
        )
        dcf_preference = max(Decimal("0"), dcf_preference) if dcf_available else Decimal("0")
        multiples_preference = max(Decimal("0"), multiples_preference)
        if not available_component_keys:
            multiples_preference = Decimal("0")
        total_preference = dcf_preference + multiples_preference
        if total_preference <= 0:
            raise PublicAdaptiveProfileError(
                "public v2 has no eligible Adaptive component after evidence resolution"
            )
        normalized_dcf = dcf_preference / total_preference
        normalized_multiples = multiples_preference / total_preference
        if dcf_available and normalized_dcf > 0:
            adaptive_component_weights["dcf"] = float(normalized_dcf)
        if available_component_keys and normalized_multiples > 0:
            per_market_method = normalized_multiples / Decimal(len(available_component_keys))
            adaptive_component_weights.update(
                {method_key: float(per_market_method) for method_key in available_component_keys}
            )
        resolved.update(
            {
                "modeled_prior_contract_hashes": modeled_hashes,
                "resolved_multiple_bands": resolved_bands,
                "multiple_band_derivation": {
                    "policy_version": "public_modeled_prior_band.v1",
                    "kind": "modeled_sensitivity",
                    "minimum_half_band": str(PUBLIC_MINIMUM_HALF_BAND),
                    "statistical_coverage": None,
                    "source_distributions": {
                        contract["metric"]: dict(contract["distribution"])
                        for contract in raw_contracts
                    },
                },
                "business_type_mix": list(request.business_type_mix or []),
                "business_type_weights": dict(request.business_type_weights or {}),
                "confidence": "low",
                "max_public_grade": producer_contract.get("max_public_grade"),
                "adaptive_component_weights": adaptive_component_weights,
                "modeled_dcf_resolution": modeled_dcf_resolution,
            }
        )
    elif selected_method == "ebitda_multiple":
        modeled_contract = _mapping(
            metadata.get("public_modeled_prior_contract"),
            field="public_modeled_prior_contract",
        )
        modeled_hash, low, median, high = _verify_modeled_prior_contract(request, modeled_contract)
        request.business_type_calibration.ev_ebitda_p25 = low
        request.business_type_calibration.ev_ebitda_median = median
        request.business_type_calibration.ev_ebitda_p75 = high
        resolved.update(
            {
                "modeled_prior_contract_hash": modeled_hash,
                "resolved_multiple_band": {
                    "low": str(low),
                    "mid": str(median),
                    "high": str(high),
                },
                "confidence": "low",
                "max_public_grade": "T2-M",
            }
        )

    # Public values may use only adjustments reproducible from contributed
    # source facts.  The generic private-company discount stack is modelled,
    # not filing evidence, so disable it explicitly for this profile.
    request.risk_analysis_enabled = False
    request.historical_ebitda_weighting_mode = "current_year"
    request.historical_ebitda_weights = None
    request.methodology = "HYBRID" if is_v2 else "MULTIPLES"
    request.include_multiples = True
    # DCF is a canonical Adaptive capability, not a separate public product.
    # ValuationIQ enables it only when the filing and Business Types calibration
    # can materialize a complete, immutable modeled-assumption resolution.
    # Those forecasts remain explicitly modeled and never count as actual years.
    request.include_dcf = bool(
        is_v2
        and modeled_dcf_resolution is not None
        and modeled_dcf_resolution.get("status") == "available"
        and adaptive_component_weights.get("dcf", 0) > 0
    )
    if is_v2:
        if request.include_dcf and modeled_dcf_resolution is not None:
            assumptions = _mapping(
                modeled_dcf_resolution.get("assumptions"),
                field="modeled_dcf_resolution.assumptions",
            )
            base_revenue = _decimal(
                assumptions.get("base_revenue"), field="modeled_dcf.base_revenue"
            )
            base_ebitda = _decimal(assumptions.get("base_ebitda"), field="modeled_dcf.base_ebitda")
            # Revenue-only and EBITDA-only filings need the missing counterpart
            # solely inside the DCF adapter. The original filed lines and their
            # use remain unchanged in the public audit.
            if not modeled_forecast_point:
                request.current_year.revenue = base_revenue
                request.current_year.ebitda = base_ebitda
            request.projection_years = int(assumptions.get("projection_years") or 5)
            modeled_context = with_fraction_inputs(
                request.business_context or {},
                {
                    "dcf_revenue_growth_pct": assumptions.get("revenue_growth"),
                    "dcf_ebitda_margin_pct": assumptions.get("ebitda_margin"),
                    "dcf_capex_pct": assumptions.get("capex_ratio"),
                    "dcf_da_pct": assumptions.get("depreciation_amortization_ratio"),
                    "dcf_nwc_pct": assumptions.get("nwc_ratio"),
                    "dcf_tax_rate_pct": assumptions.get("tax_rate"),
                    "dcf_terminal_growth_pct": assumptions.get("terminal_growth"),
                },
            )
            request.business_context = {
                **modeled_context,
                "dcf_discounting_convention": assumptions.get("discounting_convention"),
                "public_modeled_dcf_resolution_hash": modeled_dcf_resolution.get("resolution_hash"),
            }
        # Drive the canonical weighted-synthesis path with only those method
        # capabilities backed by a verified public modeled-prior contract.
        # `user_weights` is the engine's native custom-weighting contract; this
        # does not introduce another calculator or method registry.
        request.user_weights = adaptive_component_weights
        request.strict_user_weights = True
        request.user_weight_justification = (
            "Machine-governed Public Adaptive evidence capability weighting."
        )
    # A partial or absent debt/cash/lease bridge cannot determine public
    # shareholder equity, but it must not disable an otherwise valid EV method
    # through a debt-overhang gate. Calculate the method on EV with a neutral
    # engine bridge and retain the original partial filed lines in metadata for
    # the audit's explicit `unavailable`/`assumed` disclosure.
    for financial_year in [request.current_year, *request.historical_years]:
        if not _has_complete_public_equity_bridge(metadata, financial_year.year):
            financial_year.total_debt = Decimal("0")
            financial_year.cash = Decimal("0")
        wacc_capital_structure = _public_wacc_capital_structure(
            metadata,
            financial_year.year,
        )
        if wacc_capital_structure is None:
            # Preserve the neutral EV bridge above while making the WACC input
            # incomplete on purpose. The canonical DCF engine will therefore
            # apply and disclose its ValuationIQ-owned 70/30 modeled fallback;
            # a stray unbound book-equity value can never become a false 100/0
            # observed capital structure.
            financial_year.total_equity = None
        else:
            financial_year.total_debt, financial_year.total_equity = wacc_capital_structure
    request.headline_value_basis = "enterprise_value"
    request.selected_method = selected_method
    request.metadata = {
        **metadata,
        "public_adaptive_resolution": resolved,
        "public_adaptive_profile_v2": is_v2,
    }
    return request


__all__ = [
    "PUBLIC_ADAPTIVE_POLICY_VERSION",
    "PUBLIC_ADAPTIVE_PROFILE_VERSION",
    "PUBLIC_MODELED_DCF_POLICY_VERSION",
    "SUPPORTED_PUBLIC_MODELED_DCF_POLICY_VERSIONS",
    "PUBLIC_MODELED_DCF_SCHEMA",
    "PUBLIC_MINIMUM_HALF_BAND",
    "PublicAdaptiveProfileError",
    "apply_public_adaptive_profile",
    "bind_public_adaptive_runtime_weights",
    "public_adaptive_weights_are_authorized",
    "public_modeled_dcf_is_authorized",
    "public_method_registry_hash",
]
