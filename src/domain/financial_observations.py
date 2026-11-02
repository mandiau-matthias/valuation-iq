"""Admission checks for explicit missing/placeholder financial observations."""

from decimal import Decimal
from typing import Mapping


def validate_financial_observation_values(
    observations: Mapping[str, str], values: Mapping[str, object]
) -> None:
    for field, status in observations.items():
        value = values.get(field)
        if status in {"missing", "placeholder"} and isinstance(value, (Decimal, float, int)):
            raise ValueError(
                f"{field} is marked {status} and cannot also be supplied as a monetary observation"
            )
