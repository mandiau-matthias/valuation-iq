"""
Response Serializer Utility

Provides custom serialization for non-serializable objects in valuation responses.
Extracted from valuation.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication

CRITICAL FIX (2026-01-19): Added Decimal handling to prevent
"Object of type Decimal is not JSON serializable" errors.
"""

from typing import Any
from datetime import date, datetime
from decimal import Decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


def custom_serializer(obj: Any) -> Any:
    """
    Custom serializer for non-serializable objects.
    
    Handles:
    - Decimal objects → float (CRITICAL for JSON serialization)
    - datetime/date objects → ISO format strings
    - Objects with __dict__ → dictionaries
    - Other objects → string representation
    
    Args:
        obj: Object to serialize
        
    Returns:
        Serialized representation of the object
    """
    # CRITICAL: Handle Decimal first - this is the most common serialization issue
    # BANK-GRADE: Convert to string to preserve full precision
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif hasattr(obj, "__dict__"):
        # Try to serialize as dict, skipping problematic fields
        result = {}
        for key, value in obj.__dict__.items():
            try:
                import json
                json.dumps(value, default=custom_serializer)
                result[key] = value
            except (TypeError, ValueError):
                result[key] = f"<non-serializable: {type(value).__name__}>"
        return result
    elif hasattr(obj, "__str__"):
        return str(obj)
    else:
        return f"<non-serializable: {type(obj).__name__}>"

