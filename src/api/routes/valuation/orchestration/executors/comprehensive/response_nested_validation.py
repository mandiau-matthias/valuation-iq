"""Shared nested-model validation helpers for comprehensive responses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NestedValidationIssue:
    field_name: str
    error: Exception

    @property
    def message(self) -> str:
        return f"{self.field_name}: {str(self.error)}"


def validate_nested_model(
    *,
    field_name: str,
    value: object,
    model_type: type[object],
) -> NestedValidationIssue | None:
    """Validate one optional nested response model without mutating the payload."""
    if not value:
        return None

    try:
        if isinstance(value, dict):
            model_type(**value)
        elif not isinstance(value, model_type):
            model_type.model_validate(value)
    except Exception as exc:
        return NestedValidationIssue(field_name=field_name, error=exc)
    return None
