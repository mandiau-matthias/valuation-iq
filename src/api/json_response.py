"""
Custom JSON Response with Decimal Serialization Support

This module provides a custom JSONResponse class that properly handles
Decimal, datetime, and date types during JSON serialization.

CRITICAL FIX: Addresses "Object of type Decimal is not JSON serializable" errors
that occur when FastAPI/Starlette tries to serialize responses containing
Python Decimal objects.

Usage:
    Prefer this JSONResponse over starlette.responses.JSONResponse when content may include
    Decimal, datetime, or date values so serialization uses DecimalEncoder.

Author: Upswitch Engineering Team
Date: January 2026
Status: Production
"""

from decimal import Decimal
from datetime import date, datetime
import json

from starlette.responses import JSONResponse as StarletteJSONResponse


class DecimalEncoder(json.JSONEncoder):
    """
    JSON encoder that handles Decimal, datetime, and date types.
    
    This encoder converts:
    - Decimal → string (BANK-GRADE: preserves full precision)
    - datetime → ISO format string
    - date → ISO format string
    
    BANK-GRADE: Uses string conversion for Decimals to preserve
    absolute precision. Frontend should use decimal.js or bignumber.js
    to parse and work with these values.
    """
    
    def default(self, obj: object) -> object:
        """
        Encode non-standard types to JSON-serializable values.
        
        Args:
            obj: Object to encode
            
        Returns:
            JSON-serializable representation of the object
        """
        if isinstance(obj, Decimal):
            if obj.is_nan() or obj.is_infinite():
                return None
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        # Let the base class handle other types or raise TypeError
        return super().default(obj)


class JSONResponse(StarletteJSONResponse):
    """
    Custom JSONResponse that handles Decimal serialization.
    
    This class overrides the default Starlette JSONResponse to use
    our DecimalEncoder, ensuring all Decimal values are properly
    converted to floats during JSON serialization.
    
    CRITICAL: Use this class throughout the application instead of
    starlette.responses.JSONResponse to prevent serialization errors.
    """
    
    def render(self, content: object) -> bytes:
        """
        Render the response content as JSON bytes.
        
        Args:
            content: The content to serialize to JSON
            
        Returns:
            UTF-8 encoded JSON bytes
        """
        return json.dumps(
            content,
            cls=DecimalEncoder,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")


# Convenience function for serializing objects with Decimal support
def serialize_with_decimals(obj: object) -> str:
    """
    Serialize an object to JSON string with Decimal support.
    
    Args:
        obj: Object to serialize
        
    Returns:
        JSON string with Decimals converted to floats
    """
    return json.dumps(obj, cls=DecimalEncoder, ensure_ascii=False)
