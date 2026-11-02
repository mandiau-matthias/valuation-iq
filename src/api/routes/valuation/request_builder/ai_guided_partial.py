"""Admit conversation facts without manufacturing country, period or earnings."""

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, localcontext

from src.api.schemas.partial_valuation import PartialFinancialInputs, PartialValuationRequest
from src.config.countries import COUNTRY_CURRENCY
from src.domain.financial_arithmetic import decimal_number


def optional_amount(data: Mapping[str, object], key: str) -> Decimal | None:
    observations = data.get("financial_observations")
    if isinstance(observations, Mapping) and observations.get(key) in {
        "missing",
        "placeholder",
        "unknown",
    }:
        return None
    raw = data.get(key)
    if raw is None or raw == "":
        return None
    if isinstance(raw, str) and not re.fullmatch(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", raw
    ):
        raise ValueError(f"{key} must use decimal transport syntax")
    if isinstance(raw, str) and len(raw) > 100:
        raise ValueError(f"{key} exceeds supported decimal length")
    value = decimal_number(raw, key)
    with localcontext() as context:
        context.prec = 50
        if value.copy_abs() >= Decimal("1e18") or value != value.quantize(Decimal(".00000001")):
            raise ValueError(f"{key} exceeds supported financial magnitude or precision")
    return value


def supplied_fiscal_year(data: Mapping[str, object]) -> int | None:
    raw = data.get("fiscal_year", data.get("year"))
    if raw is None or raw == "":
        return None
    if not re.fullmatch(r"\d{4}", str(raw)) or not 2000 <= int(str(raw)) <= 2100:
        raise ValueError("fiscal_year must identify an explicit annual reporting period")
    return int(str(raw))


def supplied_founding_year(data: Mapping[str, object], company: Mapping[str, object]) -> int | None:
    values = [
        source.get(key) for source in (data, company) for key in ("founding_year", "founded_year")
    ]
    years = set()
    for value in values:
        if value is None or value == "":
            continue
        if (
            not re.fullmatch(r"\d{4}", str(value))
            or not 1800 <= int(str(value)) <= date.today().year
        ):
            raise ValueError("founding_year must be an explicit valid year")
        years.add(int(str(value)))
    if len(years) > 1:
        raise ValueError("Conflicting founding years")
    return next(iter(years)) if years else None


def partial_ai_guided_request(
    data: Mapping[str, object],
    company: Mapping[str, object],
    *,
    country: str | None,
    company_name: str,
) -> PartialValuationRequest | None:
    revenue = optional_amount(data, "revenue")
    ebitda = optional_amount(data, "ebitda")
    year = supplied_fiscal_year(data)
    is_forecast = (
        data.get("isForecast") is True
        or data.get("is_forecast") is True
        or data.get("period_kind") == "annual_forecast"
    )
    founding_year = supplied_founding_year(data, company)
    raw_currency = data.get("currency", company.get("currency"))
    currency = str(raw_currency).strip().upper() if raw_currency else None
    if currency is not None and not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be an explicit ISO currency code")
    if (
        country in COUNTRY_CURRENCY
        and COUNTRY_CURRENCY[country] == currency
        and year is not None
        and revenue is not None
        and revenue > 0
        and ebitda is not None
        and founding_year is not None
        and not is_forecast
        and not any(key in data for key in ("references", "fcff_forecast", "fair_value_assets"))
    ):
        return None
    financials = PartialFinancialInputs(
        fiscal_year=year,
        currency=currency,
        revenue=revenue,
        ebitda=ebitda,
        period_kind="annual_forecast" if is_forecast else "annual_actual",
        cash=optional_amount(data, "cash"),
        financial_debt=optional_amount(data, "total_debt"),
        nwc_adjustment=optional_amount(data, "nwc_adjustment"),
        source_reference="AI-guided conversation: explicit reported inputs; no inferred financial facts.",
    )
    request = PartialValuationRequest.model_validate(
        {
            "company_name": company_name,
            "country_code": country,
            "valuation_date": data.get("valuation_date") or date.today(),
            "evidence_revision_id": "ai_guided_pending",
            "financials": financials,
            "references": data.get("references", []),
            "fcff_forecast": data.get("fcff_forecast"),
            "fair_value_assets": data.get("fair_value_assets"),
        }
    )
    digest = hashlib.sha256(
        json.dumps(
            request.model_dump(mode="json", exclude={"evidence_revision_id"}), sort_keys=True
        ).encode()
    ).hexdigest()
    request.evidence_revision_id = f"ai_guided_{digest}"
    return request
