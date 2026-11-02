"""Numeric guard helpers for Step 4 owner concentration."""

from __future__ import annotations

import math
from decimal import Decimal


def is_infinite_number(value: object) -> bool:
    if isinstance(value, float):
        return math.isinf(value)
    if isinstance(value, Decimal):
        return value.is_infinite()
    return False
