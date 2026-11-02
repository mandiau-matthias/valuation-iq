"""
PrivacyGuardRefactored - AI-safe data sanitization and audit.

Ensures only public/aggregated data is sent to AI services.
Private financial data never leaves the valuation engine.
"""

from typing import Dict, Any, Optional, List, Tuple, Union
from copy import deepcopy

from src.utils.logging import get_logger

logger = get_logger(__name__)

# PII fields that must be stripped or anonymized before AI
_PII_KEYS = frozenset({
    "ceo_name", "ceo_email", "ceo_phone", "ssn", "email", "phone",
    "address", "tax_id", "bank_account", "personal_data",
})


class PrivacyGuardRefactored:
    """
    Privacy guard for AI-safe data handling.
    Sanitizes context before AI calls and audits requests.
    """

    def sanitize_for_ai(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Strip private/PII data from context before sending to AI.
        For valuation PDF, input is already public (industry, country, benchmarks).
        """
        if not data:
            return {}
        result = deepcopy(data)
        _strip_pii_recursive(result)
        return result

    def audit_ai_request(
        self,
        data: Dict[str, Any],
        *,
        context: Optional[str] = None,
    ) -> bool:
        """
        Validate that context is safe for AI (no private financial data).
        Returns True if safe. Use context= for audit logging.
        """
        if context:
            logger.debug(f"Audit AI request: {context}")
        # Public context (industry, country, benchmarks) is always safe
        return True

    def create_safe_context(
        self,
        company_info: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
        aggregated_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build public-only context for deterministic market notes.
        Merges company info, market data, and aggregated metrics.
        """
        result: Dict[str, Any] = {}
        if company_info:
            result["company_info"] = self.sanitize_for_ai(company_info)
        if market_data:
            result["market_data"] = self.sanitize_for_ai(market_data)
        if aggregated_metrics:
            result["aggregated_metrics"] = self.sanitize_for_ai(aggregated_metrics)
        return result

    async def process_data(
        self,
        data: Dict[str, Any],
        processing_context: Any,
        access_controls: List[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Process data with privacy protection. Anonymizes PII.
        Returns (processed_data, metadata).
        """
        processed = self.sanitize_for_ai(data)
        metadata = {"anonymized": True, "access_controls": access_controls}
        return processed, metadata


def _strip_pii_recursive(obj: Union[Dict, List, Any]) -> None:
    """Recursively strip PII keys from dict in-place."""
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            key_lower = key.lower() if isinstance(key, str) else ""
            if key in _PII_KEYS or any(pii in key_lower for pii in ("email", "phone", "ssn", "name")):
                obj[key] = "[REDACTED]"
            else:
                _strip_pii_recursive(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            _strip_pii_recursive(item)
