"""
Date Converter

Converts date and datetime objects to ISO format strings for template rendering.
"""

from typing import Any
from datetime import datetime, date


class DateConverter:
    """
    Converts date and datetime objects to ISO format strings.
    
    Prevents JSON serialization errors when logging or validating data.
    """
    
    @staticmethod
    def convert_dates_to_strings(data: Any) -> Any:
        """
        Recursively convert all date and datetime objects to ISO format strings.
        
        This prevents JSON serialization errors when logging or validating data.
        
        Args:
            data: Data structure (dict, list, or primitive) to convert
            
        Returns:
            Data structure with all date/datetime objects converted to ISO strings
        """
        if isinstance(data, dict):
            return {key: DateConverter.convert_dates_to_strings(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [DateConverter.convert_dates_to_strings(item) for item in data]
        elif isinstance(data, (date, datetime)):
            return data.isoformat()
        else:
            return data

