"""
Correlation ID Utilities

Provides correlation ID generation and propagation for request tracing
across all calculation steps. Ensures end-to-end traceability from API
entry point through final valuation result.
"""

import uuid
from typing import Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID for request tracing.

    Returns:
        UUID string formatted as correlation ID
    """
    return str(uuid.uuid4())


def extract_correlation_id(headers: dict) -> Optional[str]:
    """
    Extract correlation ID from request headers.

    Checks multiple header names for compatibility:
    - X-Correlation-ID (standard)
    - X-Request-ID (fallback)
    - Correlation-ID (alternative)

    Args:
        headers: Request headers dictionary

    Returns:
        Correlation ID string or None if not found
    """
    # Try standard header names
    correlation_id = (
        headers.get("X-Correlation-ID")
        or headers.get("X-Request-ID")
        or headers.get("Correlation-ID")
    )

    if correlation_id:
        return str(correlation_id)

    return None


def ensure_correlation_id(headers: dict) -> str:
    """
    Ensure a correlation ID exists, generating one if needed.

    Args:
        headers: Request headers dictionary

    Returns:
        Correlation ID string (existing or newly generated)
    """
    correlation_id = extract_correlation_id(headers)

    if not correlation_id:
        correlation_id = generate_correlation_id()
        logger.debug("Generated new correlation ID", extra={"correlation_id": correlation_id})

    return correlation_id
