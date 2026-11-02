"""Resolve registry identity fields from top-level values and business context."""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        cleaned = _clean_str(value)
        if cleaned:
            return cleaned
    return None


def _context_get(context: Any, key: str) -> Any:
    if isinstance(context, Mapping):
        return context.get(key)

    getter = getattr(context, "get", None)
    if callable(getter):
        try:
            return getter(key)
        except (TypeError, ValueError):
            pass

    return getattr(context, key, None)


def _context_first_non_empty(context: Any, *keys: str) -> Optional[str]:
    return _first_non_empty(*(_context_get(context, key) for key in keys))


def _parse_postal_city(address: Any) -> tuple[Optional[str], Optional[str]]:
    raw = _clean_str(address)
    if not raw:
        return None, None

    normalized = re.sub(r"\s+", " ", raw).strip(" ,;")
    candidates = [normalized]
    candidates.extend(
        part.strip() for part in reversed(normalized.split(",")) if part and part.strip()
    )

    for candidate in candidates:
        nl_match = re.match(r"^(\d{4})\s*([A-Za-z]{2})(?:\s+(.+))?$", candidate)
        if nl_match:
            postal_code = f"{nl_match.group(1)} {nl_match.group(2).upper()}"
            city = _clean_str(nl_match.group(3))
            return postal_code, city

        four_digit_match = re.match(r"^(\d{4})(?:\s+|[,;-]+)(.+)$", candidate)
        if four_digit_match:
            return four_digit_match.group(1), _clean_str(four_digit_match.group(2))

    return None, None


def resolve_registry_identity(
    *,
    country_code: Any,
    business_context: Any,
    registration_number: Any = None,
    kbo_number: Any = None,
    kvk_number: Any = None,
    vat_number: Any = None,
    legal_form: Any = None,
    postal_code: Any = None,
    city: Any = None,
) -> dict[str, Optional[str]]:
    """Resolve registry identity with selected-company context taking precedence.

    Venus stores selected registry companies in ``business_context`` using a mix
    of legacy KBO aliases and explicit country-specific fields. When a user
    changes the selected company, stale top-level fields can still be present in
    restored/session payloads. Prefer explicit registry context for BE/NL so the
    valuation engine cannot accidentally price the previous company.
    """

    values = {
        "registration_number": _clean_str(registration_number),
        "kbo_number": _clean_str(kbo_number),
        "kvk_number": _clean_str(kvk_number),
        "vat_number": _clean_str(vat_number),
        "legal_form": _clean_str(legal_form),
        "postal_code": _clean_str(postal_code),
        "city": _clean_str(city),
    }
    if business_context is None:
        return values

    context = business_context
    country = _clean_str(country_code)
    country = country.upper() if country else None

    context_registration = _context_first_non_empty(
        context,
        "registration_number",
        "registrationNumber",
        "company_registration_number",
        "companyRegistrationNumber",
        "company_number",
        "companyNumber",
        "enterprise_number",
        "enterpriseNumber",
    )
    context_company_id = _context_first_non_empty(context, "company_id", "companyId")
    context_kbo = _context_first_non_empty(
        context,
        "kbo_number",
        "kboNumber",
        "kbo_registration_number",
        "kboRegistrationNumber",
        "kbo_registration",
        "kboRegistration",
    )
    context_kvk = _context_first_non_empty(
        context,
        "kvk_number",
        "kvkNumber",
        "kvk_registration_number",
        "kvkRegistrationNumber",
        "kvk_registration",
        "kvkRegistration",
    )

    context_identity_applied = False
    if country == "BE":
        be_registration = _first_non_empty(context_kbo, context_registration, context_company_id)
        if be_registration:
            values["registration_number"] = be_registration
            values["kbo_number"] = be_registration
            values["kvk_number"] = None
            context_identity_applied = True
    elif country == "NL":
        nl_registration = _first_non_empty(
            context_kvk,
            context_kbo,
            context_registration,
            context_company_id,
        )
        if nl_registration:
            values["registration_number"] = nl_registration
            values["kvk_number"] = nl_registration
            values["kbo_number"] = None
            context_identity_applied = True
    else:
        generic_registration = _first_non_empty(
            context_registration,
            context_kbo,
            context_kvk,
            context_company_id,
        )
        if generic_registration:
            values["registration_number"] = generic_registration
            context_identity_applied = True

    if context_identity_applied:
        values["legal_form"] = _first_non_empty(
            _context_get(context, "legal_form"),
            _context_get(context, "legalForm"),
            values["legal_form"],
        )
        values["vat_number"] = _first_non_empty(
            _context_get(context, "vat_number"),
            _context_get(context, "vatNumber"),
            _context_get(context, "vat"),
            _context_get(context, "btw_number"),
            _context_get(context, "btwNumber"),
            values["vat_number"],
        )

        parsed_postal_code, parsed_city = _parse_postal_city(
            _context_first_non_empty(
                context,
                "company_address",
                "companyAddress",
                "registered_address",
                "registeredAddress",
                "address",
                "company_location",
                "companyLocation",
                "location",
            )
        )
        values["postal_code"] = _first_non_empty(
            _context_get(context, "postal_code"),
            _context_get(context, "postalCode"),
            _context_get(context, "company_postal_code"),
            _context_get(context, "companyPostalCode"),
            parsed_postal_code,
            values["postal_code"],
        )
        values["city"] = _first_non_empty(
            _context_get(context, "city"),
            _context_get(context, "company_city"),
            _context_get(context, "companyCity"),
            _context_get(context, "municipality"),
            parsed_city,
            values["city"],
        )

    return values


def resolve_business_type_id(
    *,
    business_context: Any,
    business_type_id: Any = None,
) -> Optional[str]:
    """Prefer an explicit context business type over stale restored fields."""

    if business_context is not None:
        context_business_type_id = _context_first_non_empty(
            business_context,
            "business_type_id",
            "businessTypeId",
        )
        if context_business_type_id:
            return context_business_type_id
    return _clean_str(business_type_id)
