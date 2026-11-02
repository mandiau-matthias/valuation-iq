"""
RejectionDetector

Detects when a user explicitly rejects or corrects a proposed value.
"""

import logging
import re

_REJECTION_PATTERNS = [
    re.compile(r"^no$", re.IGNORECASE),
    re.compile(r"^nee$", re.IGNORECASE),
    re.compile(r"^non$", re.IGNORECASE),
    re.compile(r"\bincorrect\b", re.IGNORECASE),
    re.compile(r"\bwrong\b", re.IGNORECASE),
    re.compile(r"\bnot\s+right\b", re.IGNORECASE),
    re.compile(r"\bnot\s+correct\b", re.IGNORECASE),
    re.compile(r"^that'?s\s+wrong", re.IGNORECASE),
    re.compile(r"^that'?s\s+not\s+right", re.IGNORECASE),
]


class RejectionDetector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def is_rejection(self, user_input: str) -> bool:
        stripped = user_input.strip()
        if not stripped:
            return False

        for pattern in _REJECTION_PATTERNS:
            if pattern.search(stripped):
                return True
        return False

    def get_rejection_message(self, field: str) -> str:
        return (
            f"I understand. Could you please provide the correct value for {field}? "
            f"I want to make sure I get the right {field} for your valuation."
        )
