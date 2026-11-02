"""
Fallback Content Generator

Generates minimal HTML fallback content when report generation fails.
Maintains UX continuity by always providing some content.

BANK-GRADE DESIGN:
- Minimal but functional HTML
- Includes error message and basic valuation data
- Maintains report structure even with fallback
- Logs fallback usage for monitoring
"""

from typing import Dict, Optional, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)


class FallbackGenerator:
    """
    Generates fallback HTML content when report generation fails.
    
    BANK-GRADE RESPONSIBILITIES:
    - Generate minimal HTML fallback
    - Include error message and basic data
    - Maintain report structure
    - Log fallback usage
    """
    
    @staticmethod
    def generate_accountant_view_fallback(
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        error_message: Optional[str] = None,
    ) -> str:
        """
        Generate fallback HTML for Accountant View.
        
        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            error_message: Optional error message to display
            
        Returns:
            HTML string with fallback content
        """
        company_name = getattr(response, "company_name", "Unknown Company")
        correlation_id = getattr(request, "correlation_id", "unknown")
        valuation_id = getattr(response, "valuation_id", None)
        
        # Extract basic valuation data
        equity_value_mid = getattr(response, "equity_value_mid", None)
        equity_value_low = getattr(response, "equity_value_low", None)
        equity_value_high = getattr(response, "equity_value_high", None)
        
        error_msg = error_message or "Report generation temporarily unavailable"
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Valuation Report - {company_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            padding: 40px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        h1 {{
            color: #1a1a1a;
            margin: 0;
            font-size: 28px;
        }}
        .error-notice {{
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 30px;
        }}
        .error-notice h2 {{
            color: #856404;
            margin-top: 0;
            font-size: 18px;
        }}
        .valuation-summary {{
            background-color: #f8f9fa;
            border-radius: 4px;
            padding: 20px;
            margin-top: 20px;
        }}
        .valuation-summary h3 {{
            margin-top: 0;
            color: #495057;
        }}
        .value {{
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
            margin: 10px 0;
        }}
        .metadata {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            font-size: 12px;
            color: #6c757d;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Valuation Report</h1>
            <p><strong>Company:</strong> {company_name}</p>
        </div>
        
        <div class="error-notice">
            <h2>⚠️ Report Generation Notice</h2>
            <p>{error_msg}</p>
            <p>Please contact support if this issue persists.</p>
        </div>
        
        <div class="valuation-summary">
            <h3>Valuation Summary</h3>
"""
        
        if equity_value_mid:
            html += f'<p><strong>Mid-Point Valuation:</strong> <span class="value">€{equity_value_mid:,.0f}</span></p>'
        
        if equity_value_low and equity_value_high:
            html += f'<p><strong>Valuation Range:</strong> €{equity_value_low:,.0f} - €{equity_value_high:,.0f}</p>'
        
        html += """
        </div>
        
        <div class="metadata">
            <p><strong>Report Generated:</strong> """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            <p><strong>Correlation ID:</strong> """ + correlation_id + """</p>
"""
        
        if valuation_id:
            html += f'<p><strong>Valuation ID:</strong> {valuation_id}</p>'
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        
        return html

    @staticmethod
    def generate_info_tab_fallback(
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        error_message: Optional[str] = None,
    ) -> str:
        company_name = getattr(response, "company_name", "Unknown Company")
        correlation_id = getattr(request, "correlation_id", "unknown")
        equity_value_mid = getattr(response, "equity_value_mid", None)
        equity_value_low = getattr(response, "equity_value_low", None)
        equity_value_high = getattr(response, "equity_value_high", None)

        error_msg = error_message or "Calculation breakdown temporarily unavailable"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Calculation Breakdown - {company_name}</title>
    <style>
        body {{ font-family: sans-serif; padding: 20px; color: #333; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ font-size: 24px; }}
        .notice {{ background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 4px; margin: 20px 0; }}
        .summary {{ background: #f8f9fa; padding: 15px; border-radius: 4px; }}
        .value {{ font-size: 20px; font-weight: bold; color: #007bff; }}
        .meta {{ font-size: 12px; color: #6c757d; margin-top: 20px; border-top: 1px solid #eee; padding-top: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Calculation Breakdown</h1>
        <p><strong>Company:</strong> {company_name}</p>
        <div class="notice"><p>{error_msg}</p></div>
        <div class="summary">
            <h3>Valuation Summary</h3>"""

        if equity_value_mid:
            html += f'\n            <p>Mid-Point: <span class="value">€{equity_value_mid:,.0f}</span></p>'
        if equity_value_low and equity_value_high:
            html += f"\n            <p>Range: €{equity_value_low:,.0f} - €{equity_value_high:,.0f}</p>"

        html += f"""
        </div>
        <div class="meta">
            <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>Correlation ID: {correlation_id}</p>
        </div>
    </div>
</body>
</html>"""

        return html
