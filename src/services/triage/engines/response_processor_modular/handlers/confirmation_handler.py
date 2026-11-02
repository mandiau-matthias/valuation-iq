"""
ConfirmationHandler

Detects whether a user response is a confirmation of a previously
suggested/clarified value, matching by raw input, numeric proximity,
or case-insensitive string equality.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ConfirmationHandler:
    @staticmethod
    def detect_confirmation(
        user_input: str,
        expected_field: str,
        extracted_value: Any,
        context: Any,
    ) -> Tuple[bool, Optional[Any]]:
        pending_field = getattr(context, "pending_clarification_field", None)
        pending_value = getattr(context, "pending_clarification_value", None)
        pending_raw = getattr(context, "pending_clarification_raw_input", None)

        if pending_field is None or pending_field != expected_field:
            return False, None

        if extracted_value is None:
            return False, None

        stripped_input = user_input.strip() if user_input else ""

        if pending_raw is not None and stripped_input == pending_raw.strip():
            return True, pending_value

        if isinstance(pending_value, Decimal) and isinstance(extracted_value, Decimal):
            try:
                if pending_value == Decimal("0"):
                    if extracted_value == Decimal("0"):
                        return True, pending_value
                else:
                    ratio = abs(extracted_value - pending_value) / abs(pending_value)
                    if ratio < Decimal("0.01"):
                        return True, pending_value
            except (InvalidOperation, ZeroDivisionError):
                pass
            return False, None

        if isinstance(pending_value, str) and isinstance(extracted_value, str):
            if pending_value.strip().lower() == extracted_value.strip().lower():
                return True, pending_value
            if stripped_input.lower() == pending_value.strip().lower():
                return True, pending_value

        return False, None
