"""
KBOSuggestionHandler

Handles KBO (Kruispuntbank van Ondernemingen) suggestion acceptance/rejection.
"""

import logging
from typing import Any, Dict, Optional


class KBOSuggestionHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def handle_suggestion_response(
        self, user_input: str, context: Any
    ) -> Optional[Dict[str, Any]]:
        suggestion = getattr(context, "kbo_suggestion", None)
        if suggestion is None:
            return {"accepted": False, "reason": "no_suggestion"}

        lower = user_input.strip().lower()

        if lower in ("yes", "ja", "oui", "y", "ok", "correct", "that's right"):
            self.logger.info("KBO suggestion accepted")
            return {"accepted": True, "suggestion": suggestion}

        if lower in ("no", "nee", "non", "n", "wrong", "incorrect"):
            self.logger.info("KBO suggestion rejected")
            return {"accepted": False, "reason": "rejected"}

        return {"accepted": False, "reason": "ambiguous", "input": user_input}
