"""
Template Initialization Coordinator

Handles template initialization logic.
Extracted from template_service.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive template setup
- Detailed logging
"""

from pathlib import Path
from typing import Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from jinja2 import Environment, TemplateNotFound, TemplateSyntaxError, UndefinedError
    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False
    Environment = None
    TemplateNotFound = Exception
    TemplateSyntaxError = Exception
    UndefinedError = Exception


class TemplateInitializationCoordinator:
    """
    Coordinates template initialization logic.
    
    Responsibilities:
    - Create default templates
    - Preload common templates
    - Setup template environment
    """
    
    def __init__(self, templates_dir: Path, env: Optional[Environment], logger_instance=None):
        """
        Initialize template initialization coordinator.
        
        Args:
            templates_dir: Templates directory path
            env: Jinja2 environment instance
            logger_instance: Logger instance (optional)
        """
        self.logger = logger_instance or logger
        self.templates_dir = templates_dir
        self.env = env
    
    def create_default_templates(self) -> None:
        """
        Create default valuation report template.
        
        Creates a basic HTML template if templates directory doesn't exist.
        """
        default_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Valuation Report - {{ company_name }}</title>
    <style>
        body {
            font-family: 'Helvetica', 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            border-bottom: 3px solid #2563eb;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #1e40af;
            margin: 0;
        }
        .section {
            margin-bottom: 40px;
            page-break-inside: avoid;
        }
        .section h2 {
            color: #1e40af;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 10px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin: 20px 0;
        }
        .metric-card {
            background: #f9fafb;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #2563eb;
        }
        .metric-card h3 {
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #6b7280;
            text-transform: uppercase;
        }
        .metric-card .value {
            font-size: 28px;
            font-weight: bold;
            color: #1e40af;
        }
        .footer {
            margin-top: 60px;
            padding-top: 20px;
            border-top: 2px solid #e5e7eb;
            font-size: 12px;
            color: #6b7280;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        th {
            background: #f9fafb;
            font-weight: bold;
            color: #1e40af;
        }
        .highlight {
            background: #fef3c7;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #f59e0b;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Business Valuation Report</h1>
        <p><strong>Company:</strong> {{ company_name }}</p>
        <p><strong>Industry:</strong> {{ industry }}</p>
        <p><strong>Report Date:</strong> {{ report_date | format_date }}</p>
        <p><strong>Valuation ID:</strong> {{ valuation_id }}</p>
    </div>
    
    <div class="section">
        <h2>Executive Summary</h2>
        <div class="highlight">
            <p><strong>Estimated Valuation Range:</strong></p>
            <p style="font-size: 24px; font-weight: bold; color: #1e40af;">
                {{ valuation_range_min | format_currency }} - {{ valuation_range_max | format_currency }}
            </p>
            <p><strong>Confidence Level:</strong> {{ confidence_level }}</p>
        </div>
    </div>
    
    <div class="section">
        <h2>Key Valuation Metrics</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <h3>Revenue Multiple</h3>
                <div class="value">{{ revenue_multiple | format_percentage }}</div>
            </div>
            <div class="metric-card">
                <h3>EBITDA Multiple</h3>
                <div class="value">{{ ebitda_multiple | format_percentage }}</div>
            </div>
            <div class="metric-card">
                <h3>Industry Average</h3>
                <div class="value">{{ industry_average | format_percentage }}</div>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Valuation Methodology</h2>
        <table>
            <thead>
                <tr>
                    <th>Method</th>
                    <th>Weight</th>
                    <th>Estimated Value</th>
                </tr>
            </thead>
            <tbody>
                {% for method in valuation_methods %}
                <tr>
                    <td>{{ method.name }}</td>
                    <td>{{ method.weight | format_percentage }}</td>
                    <td>{{ method.value | format_currency }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <div class="section">
        <h2>Market Insights</h2>
        <p>{{ market_insights }}</p>
    </div>
    
    <div class="section">
        <h2>Risk Assessment</h2>
        <ul>
            {% for risk in risk_factors %}
            <li>{{ risk }}</li>
            {% endfor %}
        </ul>
    </div>
    
    <div class="footer">
        <p><strong>Disclaimer:</strong> This valuation report is provided for informational purposes only and should not be considered as financial advice. 
        Valuations are estimates based on available data and market conditions at the time of analysis.</p>
        <p><strong>Generated by:</strong> Upswitch Valuation Engine</p>
        <p><strong>Generated at:</strong> {{ generation_timestamp | format_date }}</p>
    </div>
</body>
</html>"""
        
        # Write default template
        template_file = self.templates_dir / "valuation_report.html"
        with open(template_file, 'w') as f:
            f.write(default_template)
        
        self.logger.info(f"✅ Created default template: {template_file}")
    
    def preload_common_templates(self) -> None:
        """
        Pre-load common templates for faster access.
        
        Preloads frequently used templates to improve performance.
        """
        if not self.env:
            return
        
        common_templates = [
            "main_report/master_report.html",
            "main_report_pdf/master_report.html",
            "accountant_view/master_report.html",
            "info_tab/master_info_tab.html"
        ]
        
        for template_path in common_templates:
            try:
                self.env.get_template(template_path)
            except (TemplateNotFound, TemplateSyntaxError, UndefinedError, AttributeError):
                # Template may not exist, skip silently
                pass

