"""Stable JSON primitives shared by valuation commitments and response writers."""

from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel


def canonical_wire_value(value: object) -> object:
    if isinstance(value, BaseModel):
        # Preserve Python Decimal/date/enum values until this single canonical
        # serializer handles them. Pydantic's JSON mode may render an equivalent
        # zero as ``0E-8`` while the pre-validation payload renders it as
        # ``0.00000000``; hashing those presentation strings made an otherwise
        # valid run fail its own immutable commitment after model validation.
        return canonical_wire_value(value.model_dump(mode="python"))
    if is_dataclass(value) and not isinstance(value, type):
        # DCF projection rows are dataclasses. Stringifying them loses the
        # field structure in immutable runs and makes reloaded reports fail.
        return {
            field.name: canonical_wire_value(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return canonical_wire_value(value.value)
    if isinstance(value, datetime):
        # Pydantic's JSON mode serializes UTC datetimes with a trailing ``Z``
        # while ``datetime.isoformat()`` emits ``+00:00``. A sealed valuation
        # must keep the same identity before and after schema validation.
        rendered = value.isoformat()
        if rendered.endswith("+00:00"):
            return f"{rendered[:-6]}Z"
        return rendered
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): canonical_wire_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [canonical_wire_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def valuation_wire_object(value: Mapping[str, object] | None) -> dict[str, object] | None:
    """Preserve JSON number types while rendering Decimal facts consistently."""
    if value is None:
        return None
    return {str(key): canonical_wire_value(item) for key, item in value.items()}
