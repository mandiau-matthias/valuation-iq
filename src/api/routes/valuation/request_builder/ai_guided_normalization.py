"""Normalization helpers for AI-guided valuation request conversion."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from src.domain.financial_arithmetic import decimal_number

JsonMapping = Mapping[str, object]

_BUSINESS_STRUCTURE_SOLE_TERMS = (
    "sole",
    "trader",
    "self",
    "eenmanszaak",
    "freelancer",
)
_BUSINESS_STRUCTURE_COMPANY_TERMS = (
    "ltd",
    "limited",
    "company",
    "nv",
    "bv",
    "sa",
    "bvba",
)


@dataclass(frozen=True)
class RegistryIdentity:
    registration_number: object
    kbo_number: object
    kvk_number: object
    vat_number: object
    legal_form: object
    postal_code: object
    city: object


@dataclass(frozen=True)
class CountryCodeResolution:
    raw: object
    code: str | None


def first_value(*values: object, default: object = None) -> object:
    for value in values:
        if value:
            return value
    return default


def normalize_country_code(raw: object) -> str | None:
    """Resolve explicit country identity; unknown inputs must remain unknown."""
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip().upper()
    names = {
        "BELGIUM": "BE",
        "BELGIË": "BE",
        "BELGIQUE": "BE",
        "NETHERLANDS": "NL",
        "NEDERLAND": "NL",
        "FRANCE": "FR",
        "UNITED KINGDOM": "GB",
        "UK": "GB",
    }
    if cleaned in names:
        return names[cleaned]
    if re.fullmatch(r"[A-Z]{2}", cleaned):
        return cleaned
    parenthesized = re.fullmatch(r"[^()]+\(([A-Z]{2})\)", cleaned)
    return parenthesized.group(1) if parenthesized else None


def ensure_country_code(value: object) -> str | None:
    return normalize_country_code(value)


def optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def normalize_shares_for_sale(value: object) -> Decimal:
    if value is None:
        return Decimal("100")
    shares = decimal_number(value, "shares_for_sale")
    if not Decimal("0") <= shares <= Decimal("100"):
        raise ValueError("shares_for_sale must be between 0 and 100 percent")
    return shares


def business_type_from_structure(structure: object) -> str | None:
    if not structure:
        return None
    normalized = str(structure).lower()
    if any(term in normalized for term in _BUSINESS_STRUCTURE_SOLE_TERMS):
        return "sole-trader"
    if any(term in normalized for term in _BUSINESS_STRUCTURE_COMPANY_TERMS):
        return "company"
    return None


def is_sole_trader_from_structure(structure: object) -> bool | None:
    if not structure:
        return None
    normalized = str(structure).lower()
    return any(term in normalized for term in _BUSINESS_STRUCTURE_SOLE_TERMS)


def company_name_from_sources(*, company_info: JsonMapping, collected_data: JsonMapping) -> str:
    value = first_value(
        company_info.get("company_name"),
        collected_data.get("company_name"),
        default="Unknown Company",
    )
    return str(value)


def country_code_from_sources(
    *,
    company_info: JsonMapping,
    collected_data: JsonMapping,
) -> CountryCodeResolution:
    raw = first_value(
        company_info.get("country_code"),
        collected_data.get("country_code"),
        company_info.get("country"),
        collected_data.get("country"),
        default=None,
    )
    return CountryCodeResolution(raw=raw, code=ensure_country_code(normalize_country_code(raw)))


def industry_from_sources(*, company_info: JsonMapping, collected_data: JsonMapping) -> str:
    value = first_value(
        company_info.get("industry"),
        collected_data.get("industry"),
        default="professional-services",
    )
    return str(value)


def business_model_from_sources(*, company_info: JsonMapping, collected_data: JsonMapping) -> str:
    value = first_value(
        collected_data.get("business_model"),
        company_info.get("business_model"),
        default="service_based",
    )
    return str(value)


def employee_count_from_sources(
    *, company_info: JsonMapping, collected_data: JsonMapping
) -> int | None:
    return optional_int(
        first_value(
            collected_data.get("number_of_employees"),
            collected_data.get("employee_count"),
            company_info.get("number_of_employees"),
        )
    )


def owner_count_from_sources(*, collected_data: JsonMapping) -> int | None:
    return optional_int(collected_data.get("number_of_owners"))


def business_type_id_from_sources(
    *,
    session_data: JsonMapping,
    company_info: JsonMapping,
    collected_data: JsonMapping,
) -> object:
    return first_value(
        collected_data.get("business_type_id"),
        company_info.get("business_type_id"),
        session_data.get("business_type_id"),
    )


def business_structure_from_sources(
    *,
    company_info: JsonMapping,
    collected_data: JsonMapping,
) -> object:
    return first_value(
        collected_data.get("business_structure"),
        company_info.get("business_structure"),
    )


def business_type_from_sources(
    *,
    business_structure: object,
    company_info: JsonMapping,
    collected_data: JsonMapping,
) -> object:
    return business_type_from_structure(business_structure) or first_value(
        collected_data.get("business_type"),
        company_info.get("business_type"),
    )


def sole_trader_from_sources(
    *,
    business_structure: object,
    collected_data: JsonMapping,
) -> object:
    explicit = collected_data.get("is_sole_trader")
    if explicit is not None:
        return explicit
    return is_sole_trader_from_structure(business_structure)


def business_context_from_sources(
    *,
    session_data: JsonMapping,
    company_info: JsonMapping,
    collected_data: JsonMapping,
) -> dict | None:
    value = first_value(
        collected_data.get("business_context"),
        company_info.get("business_context"),
        session_data.get("business_context"),
    )
    return value if isinstance(value, dict) else None


def registry_identity(
    *,
    collected_data: JsonMapping,
    company_info: JsonMapping,
    session_data: JsonMapping,
) -> RegistryIdentity:
    return RegistryIdentity(
        registration_number=first_value(
            collected_data.get("registration_number"),
            company_info.get("registration_number"),
            session_data.get("registration_number"),
        ),
        kbo_number=first_value(
            collected_data.get("kbo_number"),
            company_info.get("kbo_number"),
            session_data.get("kbo_number"),
        ),
        kvk_number=first_value(
            collected_data.get("kvk_number"),
            company_info.get("kvk_number"),
            session_data.get("kvk_number"),
        ),
        vat_number=first_value(
            collected_data.get("vat_number"),
            company_info.get("vat_number"),
            session_data.get("vat_number"),
        ),
        legal_form=first_value(
            collected_data.get("legal_form"),
            company_info.get("legal_form"),
            session_data.get("legal_form"),
        ),
        postal_code=first_value(
            collected_data.get("postal_code"),
            company_info.get("postal_code"),
            session_data.get("postal_code"),
        ),
        city=first_value(
            collected_data.get("city"),
            company_info.get("city"),
            session_data.get("city"),
        ),
    )
