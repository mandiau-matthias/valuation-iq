"""Shared parser for academic confidence-level configuration values."""

from src.services.academic.models import ConfidenceLevel


def parse_confidence_level(level_str: str) -> ConfidenceLevel:
    """Convert a confidence-level config token to its enum value."""
    level_map = {
        "very_high": ConfidenceLevel.VERY_HIGH,
        "high": ConfidenceLevel.HIGH,
        "medium_high": ConfidenceLevel.MEDIUM_HIGH,
        "medium": ConfidenceLevel.MEDIUM,
        "low": ConfidenceLevel.LOW,
    }
    return level_map.get(level_str, ConfidenceLevel.HIGH)
