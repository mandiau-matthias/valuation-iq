"""Report contact sanitization (email/phone) and legal-form detection."""

from .sanitize import (
    is_legal_form_label,
    is_placeholder_report_email,
    is_placeholder_report_phone,
    sanitize_report_email,
    sanitize_report_phone,
)

__all__ = [
    "is_legal_form_label",
    "is_placeholder_report_email",
    "is_placeholder_report_phone",
    "sanitize_report_email",
    "sanitize_report_phone",
]
