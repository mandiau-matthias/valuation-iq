"""Validate the monetary identity in an already authenticated owner-pay decision."""

from collections.abc import Mapping
from decimal import Decimal, DecimalException

from src.utils.decimal_helpers import optional_decimal


def owner_compensation_delta(value: object) -> Decimal | None:
    """Return actual minus replacement pay only when all signed terms reconcile.

    Authentication belongs to the case boundary. Even an authenticated payload
    must distinguish missing or malformed evidence from an explicit zero cost.
    """
    if not isinstance(value, Mapping):
        return None
    role = str(value.get("owner_role") or "").strip().lower()
    if role not in {"working", "passive"}:
        return None
    actual: Decimal | None = optional_decimal(value.get("actual_owner_compensation"))
    replacement: Decimal | None = optional_decimal(value.get("replacement_owner_compensation"))
    signed: Decimal | None = optional_decimal(value.get("signed_amount"))
    if actual is None or replacement is None or signed is None:
        return None
    if actual <= 0 or replacement < 0 or (role == "passive" and replacement != 0):
        return None
    try:
        if (actual - replacement).quantize(Decimal("0.01")) != signed.quantize(Decimal("0.01")):
            return None
    except DecimalException:
        # Finite but unrepresentable magnitudes are not admissible money.
        return None
    return signed
