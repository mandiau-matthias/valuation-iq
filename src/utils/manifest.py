"""
Calculation Manifest Utilities

Generates lightweight calculation manifests for audit trails and reproducibility.
Manifests capture input data, step results, and output hashes for traceability.

Phase 0: Lightweight manifest (in-memory, logged)
Phase 1: Full manifest (stored in PostgreSQL, signed with HMAC)
"""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


def hash_data(data: Any) -> str:
    """
    Generate SHA256 hash of data for manifest.

    Args:
        data: Data to hash (dict, list, or any JSON-serializable type)

    Returns:
        SHA256 hash as hex string
    """
    # Convert to JSON string with sorted keys for deterministic hashing
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def create_lightweight_manifest(
    valuation_id: str,
    correlation_id: str,
    input_data: Dict[str, Any],
    step_results: Dict[int, Dict[str, Any]],
    output_data: Dict[str, Any],
    code_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create lightweight calculation manifest for audit trail.

    This is Phase 0 implementation - manifest is logged and can be stored
    in memory or passed to logging systems. Full PostgreSQL storage comes in Phase 1.

    Args:
        valuation_id: Unique valuation identifier
        correlation_id: Request correlation ID for tracing
        input_data: Input request data (sanitized)
        step_results: Dictionary of step outputs (step_number -> result)
        output_data: Final output data
        code_version: Git SHA or version tag (optional)

    Returns:
        Manifest dictionary
    """
    # Sanitize input data (remove sensitive fields if needed)
    sanitized_input = _sanitize_input(input_data)

    # Generate hashes
    input_hash = hash_data(sanitized_input)
    output_hash = hash_data(output_data)

    # Create step manifest summary
    step_manifest = []
    for step_num in sorted(step_results.keys()):
        step_result = step_results[step_num]
        step_manifest.append(
            {
                "step_number": step_num,
                "step_name": step_result.get("step_name", f"Step {step_num}"),
                "status": step_result.get("status", "unknown"),
                "has_result": "result" in step_result,
                "has_error": "error" in step_result,
            }
        )

    manifest = {
        "valuation_id": valuation_id,
        "correlation_id": correlation_id,
        "timestamp": datetime.utcnow().isoformat(),
        "input_data_hash": input_hash,
        "output_data_hash": output_hash,
        "step_results": step_manifest,
        "code_version": code_version or "unknown",
        "manifest_version": "1.0",
        "phase": "lightweight",  # Phase 0: lightweight, Phase 1: full with PostgreSQL storage
    }

    return manifest


def _sanitize_input(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize input data for manifest (remove sensitive fields).

    Args:
        input_data: Raw input data

    Returns:
        Sanitized input data
    """
    # Create a copy to avoid modifying original
    sanitized = input_data.copy()

    # Remove or mask sensitive fields (if any)
    # For now, we keep all fields as financial data is not considered PII
    # In Phase 1, we can add field-level encryption for sensitive data

    return sanitized


def log_manifest(manifest: Dict[str, Any]) -> None:
    """
    Log calculation manifest for audit trail.

    Args:
        manifest: Manifest dictionary
    """
    logger.info(
        "📋 Calculation manifest generated",
        extra={
            "valuation_id": manifest["valuation_id"],
            "correlation_id": manifest["correlation_id"],
            "input_hash": manifest["input_data_hash"],
            "output_hash": manifest["output_data_hash"],
            "steps_executed": len(manifest["step_results"]),
            "code_version": manifest["code_version"],
        },
    )

    # Log full manifest at DEBUG level for detailed audit trails
    logger.debug("Full calculation manifest", extra={"manifest": manifest})


def format_manifest_for_storage(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format manifest for storage (Phase 1: PostgreSQL).

    Converts Decimal values to strings and ensures all fields are JSON-serializable.

    Args:
        manifest: Manifest dictionary

    Returns:
        Formatted manifest ready for database storage
    """

    # Convert Decimal to string for JSON serialization
    def convert_decimals(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_decimals(item) for item in obj]
        return obj

    formatted = convert_decimals(manifest)
    return formatted
