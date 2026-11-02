"""
Validation Coordinator

Provides field-specific validation for triage conversation inputs
including revenue, EBITDA, founding year, employee count, and country code.
"""

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


@dataclass
class ValidationResult:
    validated: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None


_NUMERIC_SUFFIXES = {
    'k': 1_000,
    'thousand': 1_000,
    'm': 1_000_000,
    'million': 1_000_000,
    'b': 1_000_000_000,
    'billion': 1_000_000_000,
}


def _parse_numeric(raw: str) -> Optional[Decimal]:
    cleaned = raw.strip().lstrip('$€£').replace(',', '').replace(' ', '')
    if not cleaned:
        return None

    for suffix, multiplier in _NUMERIC_SUFFIXES.items():
        if cleaned.lower().endswith(suffix):
            num_part = cleaned[:len(cleaned) - len(suffix)].strip()
            if not num_part:
                num_part = '1'
            try:
                return Decimal(num_part) * multiplier
            except (InvalidOperation, ValueError):
                return None

    negative = cleaned.startswith('-')
    if negative:
        cleaned = cleaned[1:]

    try:
        val = Decimal(cleaned)
        return -val if negative else val
    except (InvalidOperation, ValueError):
        return None


class ValidationCoordinator:
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def validate(
        self, input_value: str, context: Any, field_name: Optional[str] = None
    ) -> ValidationResult:
        field_validators = {
            "revenue": self._validate_revenue,
            "ebitda": self._validate_ebitda,
            "founding_year": self._validate_founding_year,
            "number_of_employees": self._validate_employees,
            "country_code": self._validate_country_code,
        }

        if field_name in field_validators:
            return field_validators[field_name](input_value)

        if not input_value or not input_value.strip():
            return ValidationResult(
                validated=False,
                error_code="EMPTY_INPUT",
                error_message="Please provide a valid input.",
            )

        return ValidationResult(validated=True)

    def _validate_revenue(self, raw: str) -> ValidationResult:
        value = _parse_numeric(raw)
        if value is None:
            return ValidationResult(
                validated=False,
                error_code="INVALID_REVENUE_FORMAT",
                error_message="Please enter a valid revenue amount. Example: 100000, $100,000, or 100k.",
            )
        if value <= 0:
            return ValidationResult(
                validated=False,
                error_code="INVALID_REVENUE",
                error_message="Revenue must be a positive number.",
            )
        return ValidationResult(validated=True)

    def _validate_ebitda(self, raw: str) -> ValidationResult:
        value = _parse_numeric(raw)
        if value is None:
            return ValidationResult(
                validated=False,
                error_code="INVALID_EBITDA_FORMAT",
                error_message="Please enter a valid EBITDA amount. Example: 50000, $50,000, or 50k.",
            )
        return ValidationResult(validated=True)

    def _validate_founding_year(self, raw: str) -> ValidationResult:
        cleaned = raw.strip()
        try:
            year = int(cleaned)
        except ValueError:
            return ValidationResult(
                validated=False,
                error_code="INVALID_YEAR_FORMAT",
                error_message="Please enter a valid year. Example: 2015.",
            )
        if year < 1900 or year > 2100:
            return ValidationResult(
                validated=False,
                error_code="INVALID_YEAR_RANGE",
                error_message="Year must be between 1900 and 2100.",
            )
        return ValidationResult(validated=True)

    def _validate_employees(self, raw: str) -> ValidationResult:
        cleaned = raw.strip()
        try:
            count = int(cleaned)
        except ValueError:
            return ValidationResult(
                validated=False,
                error_code="INVALID_EMPLOYEE_COUNT",
                error_message="Please enter a valid number of employees.",
            )
        if count <= 0:
            return ValidationResult(
                validated=False,
                error_code="INVALID_EMPLOYEE_COUNT",
                error_message="Number of employees must be a positive number.",
            )
        return ValidationResult(validated=True)

    def _validate_country_code(self, raw: str) -> ValidationResult:
        cleaned = raw.strip().upper()
        if not cleaned or len(cleaned) != 2 or not cleaned.isalpha():
            return ValidationResult(
                validated=False,
                error_code="INVALID_COUNTRY_CODE",
                error_message="Country code must be a 2-letter code. Example: BE, US, FR.",
            )
        return ValidationResult(validated=True)

    def is_valid_field_value(self, field_name: str, value: Any) -> bool:
        if value is None:
            return False

        if isinstance(value, str):
            if not value.strip():
                return False

        if field_name in ("revenue",):
            if not isinstance(value, (int, float, Decimal)):
                return False
            return value > 0

        if field_name in ("ebitda", "net_income"):
            if not isinstance(value, (int, float, Decimal)):
                return False
            return True

        if field_name in ("founding_year", "founded_year"):
            if not isinstance(value, int):
                return False
            return 1900 <= value <= 2100

        if field_name in ("number_of_employees", "employees"):
            if not isinstance(value, int):
                return False
            return value > 0

        if field_name in ("country_code",):
            if not isinstance(value, str):
                return False
            return len(value) == 2 and value.isalpha()

        return True
