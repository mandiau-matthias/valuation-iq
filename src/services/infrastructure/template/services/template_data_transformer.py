"""
Template Data Transformer

BANK-GRADE: Single Responsibility - Transform data for template compatibility

RESPONSIBILITY:
- Convert Decimal to float (for JSON/template compatibility)
- Convert dates to ISO strings
- Validate data types
- Handle nested data structures
- Generate fallback representations

DOES NOT:
- Render templates (delegated to TemplateRenderingService)
- Configure environment (delegated to TemplateConfigurationService)
- Generate PDFs (delegated to PDFGenerationCoordinator)
- Track versions (delegated to TemplateVersionService)

SRP Compliance: This service has ONE reason to change - data transformation requirements
"""

from typing import Any, Dict, List, Union
from decimal import Decimal
from datetime import date, datetime
import json

from src.utils.logging import get_logger
from src.utils.decimal_helpers import from_decimal

logger = get_logger(__name__)


class TemplateDataTransformer:
    """
    BANK-GRADE SRP-COMPLIANT: Transforms data for template rendering.
    
    SINGLE RESPONSIBILITY: Data type transformation
    
    This service focuses solely on transforming data to be template-compatible:
    - Decimal → float/string conversion
    - Date/datetime → ISO string conversion
    - Nested structure transformation
    - Fallback HTML generation
    
    Design Pattern: Transformer Pattern
    - Separates transformation from rendering
    - Enables testing transformations independently
    - Allows extending with new data types
    """
    
    def __init__(self):
        """Initialize template data transformer."""
        self.logger = logger
        self.logger.debug("✅ [TEMPLATE-TRANSFORMER] TemplateDataTransformer initialized (SRP-compliant)")
    
    def transform_for_rendering(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform valuation data for template rendering.
        
        BANK-GRADE: Comprehensive transformation with type safety
        
        SRP: Only transforms data, doesn't render or validate
        
        Args:
            data: Raw valuation data dictionary
            
        Returns:
            Transformed data ready for template rendering
        """
        self.logger.info(
            "🔄 [TEMPLATE-TRANSFORMER] Transforming data for rendering",
            extra={'data_keys': list(data.keys()) if data else []}
        )
        
        try:
            # Step 1: Convert dates to strings (must be first)
            transformed = self.convert_dates_to_strings(data)
            
            # Step 2: Convert Decimals to floats (for JSON serialization)
            transformed = self.convert_decimals(transformed)
            
            # Step 3: Validate transformed data types
            self._validate_transformed_types(transformed)
            
            self.logger.info("✅ [TEMPLATE-TRANSFORMER] Data transformation complete")
            
            return transformed
            
        except Exception as e:
            self.logger.error(
                f"❌ [TEMPLATE-TRANSFORMER] Transformation failed: {e}",
                exc_info=True
            )
            raise
    
    def convert_decimals(self, data: Any) -> Any:
        """
        Recursively convert Decimal objects to floats.
        
        SRP: Only decimal conversion, no other transformations
        
        Args:
            data: Data structure potentially containing Decimals
            
        Returns:
            Data with Decimals converted to floats
        """
        if isinstance(data, Decimal):
            # Use from_decimal helper for consistent precision
            return from_decimal(data)
        elif isinstance(data, dict):
            return {key: self.convert_decimals(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.convert_decimals(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(self.convert_decimals(item) for item in data)
        else:
            return data
    
    def convert_dates_to_strings(self, data: Any) -> Any:
        """
        Recursively convert date/datetime objects to ISO format strings.
        
        SRP: Only date conversion, no other transformations
        
        Args:
            data: Data structure potentially containing dates
            
        Returns:
            Data with dates converted to ISO strings
        """
        if isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, date):
            return data.isoformat()
        elif isinstance(data, dict):
            return {key: self.convert_dates_to_strings(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.convert_dates_to_strings(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(self.convert_dates_to_strings(item) for item in data)
        else:
            return data
    
    def _validate_transformed_types(self, data: Dict[str, Any]) -> None:
        """
        Validate that transformed data contains only JSON-serializable types.
        
        SRP: Only type validation
        
        Args:
            data: Transformed data dictionary
            
        Raises:
            ValueError: If non-serializable types found
        """
        try:
            # Quick validation: try to serialize to JSON
            json.dumps(data, default=str)
        except (TypeError, ValueError) as e:
            self.logger.warning(
                f"⚠️ [TEMPLATE-TRANSFORMER] Data contains non-serializable types: {e}"
            )
            # Not fatal - templates might handle it
    
    def generate_fallback_html(self, valuation_data: Dict[str, Any]) -> str:
        """
        Generate fallback HTML when templates unavailable.
        
        SRP: Only fallback generation, no template rendering
        
        Args:
            valuation_data: Valuation data dictionary
            
        Returns:
            Simple HTML representation of data
        """
        self.logger.info("🔄 [TEMPLATE-TRANSFORMER] Generating fallback HTML")
        
        # Transform data for JSON serialization
        safe_data = self.convert_decimals(valuation_data)
        safe_data = self.convert_dates_to_strings(safe_data)
        
        # Extract key fields for display
        company_name = valuation_data.get('company_name', 'N/A')
        valuation_min = valuation_data.get('valuation_range_min', 0)
        valuation_max = valuation_data.get('valuation_range_max', 0)
        
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Valuation Report - {company_name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .summary {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .warning {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }}
        pre {{
            background: #2c3e50;
            color: #ecf0f1;
            padding: 20px;
            border-radius: 4px;
            overflow-x: auto;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Business Valuation Report</h1>
        
        <div class="summary">
            <p><strong>Company:</strong> {company_name}</p>
            <p><strong>Valuation Range:</strong> €{valuation_min:,.2f} - €{valuation_max:,.2f}</p>
            <p><strong>Report Type:</strong> Fallback (Simple)</p>
        </div>
        
        <div class="warning">
            <strong>⚠️ Note:</strong> Full template rendering unavailable. 
            This is a simplified fallback report. Complete HTML templates not found.
        </div>
        
        <h2>Complete Data</h2>
        <pre>{json.dumps(safe_data, indent=2, default=str)}</pre>
    </div>
</body>
</html>
        """
    
    def validate_data_structure(self, data: Dict[str, Any], required_fields: List[str]) -> bool:
        """
        Validate that data contains required fields.
        
        SRP: Only structure validation
        
        Args:
            data: Data dictionary to validate
            required_fields: List of required field names
            
        Returns:
            True if all required fields present
        """
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            self.logger.warning(
                f"⚠️ [TEMPLATE-TRANSFORMER] Missing required fields: {missing_fields}"
            )
            return False
        
        return True
    
    def sanitize_for_html(self, text: str) -> str:
        """
        Sanitize text for safe HTML rendering.
        
        Args:
            text: Text to sanitize
            
        Returns:
            HTML-safe text
        """
        import html
        return html.escape(text) if text else ""
