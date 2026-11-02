"""SME size classification helpers."""

from decimal import Decimal

from src.services.academic.sme_multiple_catalog import (
    MEDIUM_SME_THRESHOLD,
    MICRO_SME_THRESHOLD,
    SMALL_SME_THRESHOLD,
)


def classify_sme(revenue: Decimal) -> str:
    """Classify company as micro, small, medium, or large by revenue."""
    if revenue < MICRO_SME_THRESHOLD:
        return "micro"
    if revenue < SMALL_SME_THRESHOLD:
        return "small"
    if revenue < MEDIUM_SME_THRESHOLD:
        return "medium"
    return "large"
