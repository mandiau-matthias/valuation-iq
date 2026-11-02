"""
Core Template Components

Reusable components for valuation reports and templates.
"""

# Import all components to register them
from .header import HeaderComponent
from .metric_card import MetricCardComponent
from .table import TableComponent
from .chart import ChartComponent
from .summary import SummaryComponent
from .footer import FooterComponent

__all__ = [
    "HeaderComponent",
    "MetricCardComponent", 
    "TableComponent",
    "ChartComponent",
    "SummaryComponent",
    "FooterComponent"
]
