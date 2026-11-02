"""LLM egress anonymization for ValuationIQ.

ValuationIQ should never send exact company identifiers or exact private
financial values to an external model. These helpers preserve broad public
context such as industry, country, ratios, counts, years, and confidence
scores, while replacing exact valuation/revenue/EBITDA/cash/debt figures.
"""

from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal
from typing import Any, Iterable

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[\sA-Z0-9]{10,34}\b", re.IGNORECASE)
_BE_VAT_RE = re.compile(r"\bBE\s?0?\d{9,10}\b", re.IGNORECASE)
_KBO_DOTTED_RE = re.compile(r"\b\d{4}\.\d{3}\.\d{3}\b")
_BUSINESS_ID_RE = re.compile(
    r"\b(?:KBO|BCE|KVK|RCS|VAT|BTW|TVA)\s*[:#]?\s*[A-Z]?\d[\d.\s/-]{5,}\b",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"(?:\+32|0032|\+31|0031|0)(?:[\s./-]?\d){8,12}\b")
_LEGAL_SUFFIX_RE = re.compile(
    r"\b[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ&'’.-]*"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ&'’.-]*){0,5}"
    r"\s+(?:BV|B\.V\.|BVBA|NV|N\.V\.|SRL|SA|S\.A\.|GMBH|LTD|LIMITED|SAS|SARL)\b",
    re.IGNORECASE,
)

_DIGIT_BODY = r"(?:\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
_MAGNITUDE = r"(?:k|K|m|M|bn|BN|mln|mio|mrd|million|billion|miljoen|miljard)"
_CURRENCY_AMOUNT_RE = re.compile(
    rf"(?:€|\$|£|EUR|USD|GBP|CHF)\s*-?{_DIGIT_BODY}\s*(?:{_MAGNITUDE})?\b|"
    rf"\b-?{_DIGIT_BODY}\s*(?:{_MAGNITUDE})?\s*(?:€|\$|£|EUR|USD|GBP|CHF)\b",
    re.IGNORECASE,
)
_MAGNITUDE_AMOUNT_RE = re.compile(rf"\b-?{_DIGIT_BODY}\s*(?:{_MAGNITUDE})\b", re.IGNORECASE)
_LONG_DIGIT_RE = re.compile(r"\b\d{8,}\b")
_LARGE_BARE_NUMBER_RE = re.compile(r"\b\d{5,}(?:[.,]\d+)?\b")
_WS_RE = re.compile(r"\s+")

_PII_KEY_HINTS = frozenset(
    {
        "company_name",
        "business_name",
        "legal_name",
        "client_name",
        "customer_name",
        "owner_name",
        "seller_name",
        "buyer_name",
        "founder_name",
        "contact_name",
        "person_name",
        "accountant_name",
        "advisor_name",
        "email",
        "phone",
        "address",
        "iban",
        "bank_account",
        "tax_id",
        "vat",
        "kbo",
        "bce",
        "kvk",
        "enterprise_number",
        "registration_number",
        "website",
        "website_url",
        "domain",
        "linkedin_url",
    }
)

_SENSITIVE_FINANCIAL_HINTS = (
    "revenue",
    "ebitda",
    "ebit",
    "income",
    "profit",
    "cash",
    "debt",
    "asset",
    "liability",
    "equity",
    "valuation",
    "value",
    "price",
    "amount",
    "arr",
    "mrr",
    "capex",
    "opex",
    "working_capital",
    "estimated_value",
)

_SAFE_NUMERIC_HINTS = (
    "multiple",
    "multiplier",
    "ratio",
    "score",
    "confidence",
    "percent",
    "percentage",
    "year",
    "count",
    "employees",
    "owners",
)


def _path_text(path: Iterable[str]) -> str:
    return ".".join(str(part).lower() for part in path if part is not None)


def _last_key(path: tuple[str, ...]) -> str:
    return str(path[-1]).lower() if path else ""


def _is_pii_key(path: tuple[str, ...]) -> bool:
    key = _last_key(path)
    return key in _PII_KEY_HINTS or any(
        hint in key
        for hint in (
            "email",
            "phone",
            "iban",
            "address",
            "enterprise_number",
            "registration_number",
            "linkedin",
        )
    )


def _is_sensitive_numeric_key(path: tuple[str, ...]) -> bool:
    key = _last_key(path)
    path_value = _path_text(path)
    if any(hint in key for hint in _SAFE_NUMERIC_HINTS):
        return False
    return any(hint in path_value for hint in _SENSITIVE_FINANCIAL_HINTS)


def sanitize_valuation_llm_text(raw: str | None, max_len: int = 80_000) -> str:
    """Redact identifiers and exact amount-like strings before external LLM egress."""
    text = unicodedata.normalize("NFKC", str(raw or ""))
    text = text[: max_len * 2]

    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _URL_RE.sub("[URL]", text)
    text = _BE_VAT_RE.sub("[VAT]", text)
    text = _IBAN_RE.sub("[IBAN]", text)
    text = _KBO_DOTTED_RE.sub("[ENTERPRISE_NUMBER]", text)
    text = _BUSINESS_ID_RE.sub("[BUSINESS_ID]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _LEGAL_SUFFIX_RE.sub("[COMPANY]", text)
    text = _CURRENCY_AMOUNT_RE.sub("[FINANCIAL_VALUE]", text)
    text = _MAGNITUDE_AMOUNT_RE.sub("[FINANCIAL_VALUE]", text)
    text = _LONG_DIGIT_RE.sub("[NUMBER]", text)
    text = _LARGE_BARE_NUMBER_RE.sub("[NUMBER]", text)
    text = _WS_RE.sub(" ", text).strip()
    return text[:max_len]


def sanitize_valuation_llm_value(value: Any, path: tuple[str, ...] = ()) -> Any:
    """Recursively anonymize a value before it is placed in an LLM prompt."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        if _is_pii_key(path) and value.strip():
            return "[REDACTED]"
        return sanitize_valuation_llm_text(value)
    if isinstance(value, dict):
        return {
            sanitize_valuation_llm_text(str(key), max_len=240): sanitize_valuation_llm_value(
                child,
                (*path, str(key)),
            )
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_valuation_llm_value(child, path) for child in value]
    if isinstance(value, (int, float, Decimal)):
        if _is_sensitive_numeric_key(path):
            return "[FINANCIAL_VALUE]"
        if isinstance(value, Decimal):
            return float(value)
        return value
    return value


def dumps_valuation_llm_json(value: Any) -> str:
    """Minified JSON after ValuationIQ LLM egress anonymization."""
    return json.dumps(
        sanitize_valuation_llm_value(value),
        default=lambda obj: sanitize_valuation_llm_text(str(obj)),
        ensure_ascii=False,
        separators=(",", ":"),
    )
