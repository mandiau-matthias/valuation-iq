"""Fallback HTML rendering for TemplateService."""

import html as html_lib
import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal


def generate_fallback_html(valuation_data: Mapping[str, object]) -> str:
    """Generate safe fallback HTML when rich templates are unavailable."""
    safe_data = _convert_dates_to_strings(_convert_decimal_values(valuation_data))
    json_str = (
        json.dumps(safe_data, indent=2, default=str, ensure_ascii=True)
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("&", r"\u0026")
    )

    safe_company = html_lib.escape(str(valuation_data.get("company_name", "N/A")))
    safe_range_min = html_lib.escape(str(valuation_data.get("valuation_range_min", 0)))
    safe_range_max = html_lib.escape(str(valuation_data.get("valuation_range_max", 0)))

    return f"""
        <html>
        <head><title>Valuation Report</title></head>
        <body>
            <h1>Business Valuation Report</h1>
            <p><strong>Company:</strong> {safe_company}</p>
            <p><strong>Valuation Range:</strong> {safe_range_min} - {safe_range_max}</p>
            <p><em>Full template rendering unavailable</em></p>
            <pre>{json_str}</pre>
        </body>
        </html>
        """


def _convert_decimal_values(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _convert_decimal_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_convert_decimal_values(item) for item in value]
    return value


def _convert_dates_to_strings(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _convert_dates_to_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_convert_dates_to_strings(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value
