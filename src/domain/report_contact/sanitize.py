"""Sanitize report-facing email/phone so QA placeholders never appear in PDF/HTML."""

from __future__ import annotations

import re
from typing import Optional

_LEGAL_FORM_COMPACT = frozenset(
    {
        "bv",
        "nv",
        "bvba",
        "cvba",
        "vof",
        "cv",
        "vzw",
        "commv",
        "esv",
        "eem",
        "ivzw",
        "snc",
        "scs",
        "scomp",
        "gie",
        "sei",
        "beslotenvennootschap",
        "naamlozevennootschap",
    }
)


def _compact_alnum(value: str) -> str:
    return re.sub(r"[\s.\-_'()/]", "", value.lower())


def is_legal_form_label(value: object) -> bool:
    """True when the string is a Belgian/Dutch legal form, not an economic sector."""
    if not value or not isinstance(value, str):
        return False
    t = value.strip()
    if not t:
        return False
    c = _compact_alnum(t)
    if c in _LEGAL_FORM_COMPACT:
        return True
    return bool(len(c) <= 6 and re.match(r"^(bv|nv|vof|cv)$", t.strip(), re.I))


_EMAIL_FORMAT_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_RESERVED_PLACEHOLDER_DOMAINS = frozenset({"test", "localhost"})
_EXAMPLE_DOMAINS = frozenset({"example.com", "example.org", "example.net"})


def _normalized_email(value: object) -> Optional[str]:
    if value is None or not isinstance(value, str):
        return None
    email = value.strip().lower()
    if not email or "@" not in email:
        return None
    return email


def _email_parts(email: str) -> tuple[str, str] | None:
    parts = email.rsplit("@", 1)
    if len(parts) != 2:
        return None
    local, domain = parts
    if not domain:
        return None
    return local, domain


def _is_placeholder_domain(domain: str) -> bool:
    return (
        domain in _RESERVED_PLACEHOLDER_DOMAINS
        or domain.endswith(".test")
        or domain.endswith(".invalid")
        or domain in _EXAMPLE_DOMAINS
        or domain.endswith(".example")
    )


def _is_test_local_address(local: str, domain: str) -> bool:
    return local == "test" and (domain == "test" or domain.startswith("test."))


def _is_test_domain_pattern(domain: str) -> bool:
    return domain.startswith("test.") or "." not in domain


def is_placeholder_report_email(email: object) -> bool:
    e = _normalized_email(email)
    if e is None:
        return False
    # Reject anything that doesn't parse as a real email — covers the
    # comma-separated junk like "test@test,test" that previous patterns let
    # through (Three Towers Capital regression).
    if not _EMAIL_FORMAT_RE.match(e):
        return True
    parts = _email_parts(e)
    if parts is None:
        return False
    local, domain = parts
    return (
        _is_placeholder_domain(domain)
        or _is_test_local_address(local, domain)
        or e in ("test@test", "test@test.com")
        or _is_test_domain_pattern(domain)
    )


def sanitize_report_email(email: object) -> Optional[str]:
    if email is None or not isinstance(email, str):
        return None
    t = email.strip()
    if not t:
        return None
    if is_placeholder_report_email(t):
        return None
    return t


def is_placeholder_report_phone(phone: object) -> bool:
    if phone is None or not isinstance(phone, str):
        return False
    p = phone.strip().lower()
    if not p:
        return False
    if p in ("test", "xxx", "n/a", "-"):
        return True
    digits = re.sub(r"\D", "", p)
    if len(digits) >= 4 and re.fullmatch(r"0+", digits):
        return True
    if digits in ("123456789", "1234567890", "0123456789"):
        return True
    stripped = re.sub(r"[\s.-]", "", p)
    if re.fullmatch(r"x+", stripped, flags=re.I):
        return True
    return False


def sanitize_report_phone(phone: object) -> Optional[str]:
    if phone is None or not isinstance(phone, str):
        return None
    t = phone.strip()
    if not t:
        return None
    if is_placeholder_report_phone(t):
        return None
    return t
