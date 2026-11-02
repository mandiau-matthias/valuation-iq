"""
Report Types and Data Structures

This module defines all data structures, enums, and configuration classes
for the Conversation Report Generator refactoring.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class InsightCategory(str, Enum):
    """Valuation insight categories"""
    STRENGTH = "strength"
    CONCERN = "concern"
    OPPORTUNITY = "opportunity"
    RECOMMENDATION = "recommendation"


class ImpactLevel(str, Enum):
    """Impact level for insights and recommendations"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValuationMethodology(str, Enum):
    """Valuation methodology types"""
    REVENUE_MULTIPLE = "revenue_multiple"
    EBITDA_MULTIPLE = "ebitda_multiple"
    ASSET_BASED = "asset_based"
    INSUFFICIENT_DATA = "insufficient_data"


class ReportSection(str, Enum):
    """Report section types"""
    EXECUTIVE_SUMMARY = "executive_summary"
    KEY_METRICS = "key_metrics"
    INSIGHTS = "insights"
    RECOMMENDATIONS = "recommendations"
    ASSUMPTIONS = "assumptions"
    LIMITATIONS = "limitations"


@dataclass
class ValuationInsight:
    """Individual insight for the valuation report"""
    category: InsightCategory
    title: str
    description: str
    impact: ImpactLevel
    confidence: Decimal  # Decimal('0.0') to Decimal('1.0')
    supporting_data: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ValuationReport:
    """Complete valuation report generated from conversation"""
    company_name: str
    estimated_value: Dict[str, Decimal]  # {"min": 100000, "max": 150000, "most_likely": 125000}
    methodology: str
    confidence_score: Decimal
    executive_summary: str
    key_metrics: Dict[str, Any]
    insights: List[ValuationInsight]
    recommendations: List[str]
    assumptions: List[str]
    limitations: List[str]
    generated_at: datetime
    session_id: str
    conversation_summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportConfiguration:
    """Configuration for report generation"""
    include_executive_summary: bool = True
    include_key_metrics: bool = True
    include_insights: bool = True
    include_recommendations: bool = True
    include_assumptions: bool = True
    include_limitations: bool = True
    confidence_threshold: Decimal = Decimal('0.7')
    max_insights: int = 10
    max_recommendations: int = 5
    template_style: str = "professional"  # "professional", "minimal", "detailed"


@dataclass
class MethodologyDefinition:
    """Definition of a valuation methodology"""
    name: str
    description: str
    multipliers: Dict[str, Dict[str, Decimal]]  # Industry -> {min, max, typical}
    requirements: List[str]  # Required data fields
    confidence_factors: List[str]  # Factors that affect confidence


@dataclass
class ReportSection:
    """Report section configuration"""
    section_type: ReportSection
    title: str
    content: str
    order: int
    required: bool = True
    visible: bool = True


@dataclass
class TemplateConfiguration:
    """HTML template configuration"""
    template_name: str
    css_styles: str
    sections: List[ReportSection]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataExtractionResult:
    """Result of data extraction from conversation"""
    company_name: str
    revenue: Optional[Decimal]
    ebitda: Optional[Decimal]
    industry: str
    business_type: str
    employee_count: str
    key_metrics: Dict[str, Any]
    confidence: Decimal
    completeness_score: Decimal
    missing_fields: List[str] = field(default_factory=list)


@dataclass
class ValuationCalculationResult:
    """Result of valuation calculation"""
    estimated_value: Dict[str, Decimal]
    methodology: str
    confidence_score: Decimal
    assumptions: List[str]
    limitations: List[str]
    calculation_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InsightGenerationResult:
    """Result of deterministic insight generation."""
    insights: List[ValuationInsight]
    executive_summary: str
    recommendations: List[str]
    confidence_factors: List[str]
    ai_model_used: str  # Legacy field; ValuationIQ uses deterministic local context.
    generation_time: Decimal


# Default configurations
DEFAULT_REPORT_CONFIG = ReportConfiguration(
    include_executive_summary=True,
    include_key_metrics=True,
    include_insights=True,
    include_recommendations=True,
    include_assumptions=True,
    include_limitations=True,
    confidence_threshold=Decimal('0.7'),
    max_insights=10,
    max_recommendations=5,
    template_style="professional"
)

# Valuation methodologies
VALUATION_METHODOLOGIES = {
    ValuationMethodology.REVENUE_MULTIPLE: MethodologyDefinition(
        name="Revenue Multiple Method",
        description="Based on industry revenue multiples",
        multipliers={
            "technology": {"min": Decimal('2.5'), "max": Decimal('4.0'), "typical": 3.2},
            "services": {"min": Decimal('2.0'), "max": Decimal('3.5'), "typical": 2.7},
            "manufacturing": {"min": Decimal('1.5'), "max": Decimal('2.5'), "typical": 2.0},
            "retail": {"min": Decimal('1.0'), "max": Decimal('2.0'), "typical": 1.5},
            "healthcare": {"min": Decimal('2.0'), "max": Decimal('3.5'), "typical": 2.8},
            "construction": {"min": Decimal('1.2'), "max": Decimal('2.0'), "typical": 1.6},
            "hospitality": {"min": Decimal('1.0'), "max": Decimal('1.8'), "typical": 1.4}
        },
        requirements=["revenue", "industry"],
        confidence_factors=["revenue_quality", "industry_match", "market_conditions"]
    ),

    ValuationMethodology.EBITDA_MULTIPLE: MethodologyDefinition(
        name="EBITDA Multiple Method",
        description="Based on industry EBITDA multiples",
        multipliers={
            "technology": {"min": Decimal('8.0'), "max": Decimal('15.0'), "typical": 11.0},
            "services": {"min": Decimal('6.0'), "max": Decimal('12.0'), "typical": 9.0},
            "manufacturing": {"min": Decimal('4.0'), "max": Decimal('8.0'), "typical": 6.0},
            "retail": {"min": Decimal('3.0'), "max": Decimal('6.0'), "typical": 4.5},
            "healthcare": {"min": Decimal('6.0'), "max": Decimal('12.0'), "typical": 9.0},
            "construction": {"min": Decimal('3.0'), "max": Decimal('6.0'), "typical": 4.5},
            "hospitality": {"min": Decimal('3.0'), "max": Decimal('5.0'), "typical": 4.0}
        },
        requirements=["revenue", "ebitda", "industry"],
        confidence_factors=["ebitda_quality", "industry_match", "profitability_trends"]
    ),

    ValuationMethodology.ASSET_BASED: MethodologyDefinition(
        name="Asset-Based Method",
        description="Based on the value of company assets minus liabilities",
        multipliers={},
        requirements=["assets", "liabilities"],
        confidence_factors=["asset_quality", "liability_accuracy", "market_conditions"]
    )
}

# Report templates configuration
REPORT_TEMPLATES = {
    "executive_summary": """
    <div class="executive-summary">
        <h2>Executive Summary</h2>
        <p class="company-name">{company_name}</p>
        <div class="valuation-range">
            <span class="estimated-value">€{estimated_value:,.0f}</span>
            <span class="range">(€{min_value:,.0f} - €{max_value:,.0f})</span>
        </div>
        <p class="confidence">Confidence Score: {confidence_score:.0%}</p>
        <p class="methodology">Methodology: {methodology}</p>
        <div class="summary-text">{executive_summary}</div>
    </div>
    """,

    "key_metrics": """
    <div class="key-metrics">
        <h3>Key Business Metrics</h3>
        <div class="metrics-grid">
            {metrics_html}
        </div>
    </div>
    """,

    "insights": """
    <div class="insights-section">
        <h3>Valuation Insights</h3>
        {insights_html}
    </div>
    """,

    "recommendations": """
    <div class="recommendations">
        <h3>Strategic Recommendations</h3>
        <ul class="recommendations-list">
            {recommendations_html}
        </ul>
    </div>
    """,

    "full_report": """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Business Valuation Report - {company_name}</title>
        <style>
            {css_styles}
        </style>
    </head>
    <body>
        <div class="report-container">
            <header class="report-header">
                <h1>Business Valuation Report</h1>
                <p class="company-name">{company_name}</p>
                <p class="generated-date">Generated on {generated_date}</p>
            </header>

            {executive_summary}
            {key_metrics}
            {insights}
            {recommendations}

            <footer class="report-footer">
                <p>This report was generated using deterministic valuation analysis.</p>
                <p>For professional valuation services, please consult with a certified business appraiser.</p>
            </footer>
        </div>
    </body>
    </html>
    """
}

# CSS styles for reports
DEFAULT_CSS_STYLES = """
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
        background-color: #f9f9f9;
    }

    .report-container {
        background-color: white;
        padding: 40px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,Decimal('0.1'));
    }

    .report-header {
        text-align: center;
        border-bottom: 2px solid #007bff;
        padding-bottom: 20px;
        margin-bottom: 30px;
    }

    .company-name {
        font-size: 1.5em;
        font-weight: bold;
        color: #007bff;
        margin: 10px 0;
    }

    .valuation-range {
        font-size: 1.2em;
        margin: 20px 0;
    }

    .estimated-value {
        font-size: 2em;
        font-weight: bold;
        color: #28a745;
    }

    .insight {
        margin: 15px 0;
        padding: 15px;
        border-left: 4px solid #007bff;
        background-color: #f8f9fa;
    }

    .insight-high {
        border-left-color: #dc3545;
    }

    .insight-medium {
        border-left-color: #ffc107;
    }

    .insight-low {
        border-left-color: #28a745;
    }

    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
        margin: 20px 0;
    }

    .metric {
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 5px;
        border: 1px solid #dee2e6;
    }

    .metric-label {
        font-weight: bold;
        display: block;
        margin-bottom: 5px;
    }

    .metric-value {
        font-size: 1.1em;
        color: #007bff;
    }
"""
