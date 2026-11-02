"""
Context Manager

Manages request context and correlation IDs for valuation orchestration.
"""

from typing import Any, Dict, Optional

from src.utils.valuation_logger import ValuationLogger


class ContextManager:
    """
    Manager for request context and correlation IDs.

    Responsibilities:
    - Context propagation
    - Correlation ID management
    - Request context handling
    """

    def __init__(self, logger: Optional[ValuationLogger] = None):
        """
        Initialize context manager.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or ValuationLogger(self.__class__.__name__)
        self.logger.debug("✅ ContextManager initialized")

    def get_correlation_id(self, context: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Extract correlation ID from context.

        Args:
            context: Processing context dictionary

        Returns:
            Correlation ID or None
        """
        if context:
            return context.get("correlation_id")
        return None

    def create_context(self, correlation_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Create processing context.

        Args:
            correlation_id: Optional correlation ID
            **kwargs: Additional context fields

        Returns:
            Context dictionary
        """
        context = {"correlation_id": correlation_id, **kwargs}
        return context

    def merge_context(
        self, base_context: Optional[Dict[str, Any]], additional_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge two context dictionaries.

        Args:
            base_context: Base context
            additional_context: Additional context to merge

        Returns:
            Merged context dictionary
        """
        merged = {}
        if base_context:
            merged.update(base_context)
        if additional_context:
            merged.update(additional_context)
        return merged
