"""
Progressive HTML Generator

BANK-GRADE: Single Responsibility - Generate HTML for progressive valuation UI

RESPONSIBILITY:
- Generate welcome HTML for instant preview
- Generate progress tracker HTML
- Generate placeholder valuation ranges
- Generate next steps HTML

DOES NOT:
- Calculate valuations (delegated to PhaseCalculator)
- Determine phases (delegated to PhaseDeterminer)
- Validate data (delegated to validators)
- Transform data (delegated to transformers)

SRP Compliance: This class has ONE reason to change - HTML generation requirements
"""

import html
from typing import Dict, Any, List
from decimal import Decimal
from markupsafe import Markup

from src.utils.decimal_helpers import to_decimal, from_decimal
from src.utils.core.formatting_helpers import EURO_SYMBOL
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProgressiveHTMLGenerator:
    """
    BANK-GRADE: Generates HTML fragments for progressive valuation UI.
    
    SINGLE RESPONSIBILITY: HTML generation for progressive valuation interface
    
    This class focuses solely on generating HTML markup for:
    - Welcome messages
    - Progress trackers
    - Placeholder valuation ranges
    - Next step suggestions
    
    Design Pattern: Generator Pattern
    - Separates HTML generation from business logic
    - Enables testing HTML independently
    - Allows template changes without touching business logic
    """
    
    def __init__(self):
        """Initialize HTML generator."""
        logger.info("✅ [PROGRESSIVE-HTML] ProgressiveHTMLGenerator initialized")
    
    def generate_welcome_html(self, company_name: str) -> str:
        """
        Generate welcome HTML for instant preview.
        
        SRP: Only generates HTML, doesn't validate or process data
        
        Args:
            company_name: Company name (will be escaped for XSS prevention)
            
        Returns:
            HTML string with welcome message (marked as safe)
        """
        # Escape user input to prevent XSS attacks
        company_name_escaped = html.escape(company_name)
        
        html_content = f"""
        <div class="welcome-section bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 mb-6">
            <div class="flex items-center mb-4">
                <div class="w-12 h-12 bg-100 rounded-full flex items-center justify-center mr-4">
                    <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                    </svg>
                </div>
                <div>
                    <h2 class="text-2xl font-bold text-gray-900">Building Your Valuation Report</h2>
                    <p class="text-gray-600">I&apos;m analyzing {company_name_escaped} as we chat...</p>
                </div>
            </div>
            <div class="bg-white rounded-lg p-4 border border-blue-200">
                <p class="text-sm text-gray-700">
                    <span class="font-semibold">Real-time Analysis:</span> Your valuation report is being generated progressively as you provide information. 
                    Each piece of data you share helps refine the estimate.
                </p>
            </div>
        </div>
        """
        
        # Mark as safe HTML after ensuring user input is escaped
        return Markup(html_content)
    
    def generate_progress_html(self, collected: int, total: int) -> str:
        """
        Generate progress tracker HTML.
        
        SRP: Only generates HTML for progress display
        
        Args:
            collected: Number of fields collected
            total: Total number of fields
            
        Returns:
            HTML string with progress tracker (marked as safe)
        """
        # Calculate percentage
        percentage = int((collected / total) * 100) if total > 0 else 0
        
        html_content = f"""
        <div class="progress-tracker bg-white rounded-lg p-4 mb-6 border border-gray-200">
            <div class="flex justify-between items-center mb-2">
                <h3 class="text-lg font-semibold text-gray-900">Data Collection Progress</h3>
                <span class="text-sm text-gray-600">{collected}/{total} fields</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2 mb-3">
                <div class="bg-blue-600 h-2 rounded-full transition-all duration-300" style="width: {percentage}%"></div>
            </div>
            <p class="text-sm text-gray-600">
                {percentage}% complete - {total - collected} more questions to go
            </p>
        </div>
        """
        
        # Mark as safe HTML (no user input, server-generated)
        return Markup(html_content)
    
    def generate_placeholder_range(self, data: Dict[str, Any]) -> str:
        """
        Generate placeholder valuation range.
        
        SRP: Only generates display string, doesn't calculate valuations
        
        Args:
            data: Dictionary with revenue data
            
        Returns:
            Formatted range string (e.g., "€500K - €5M")
        """
        # Simple heuristic based on available data
        if 'revenue' in data and data['revenue']:
            try:
                revenue_decimal = to_decimal(data['revenue'])
                
                # Simple 2-5x revenue multiple for placeholder
                low_decimal = revenue_decimal * Decimal('2')
                high_decimal = revenue_decimal * Decimal('5')
                
                low_formatted = from_decimal(low_decimal, precision=0)
                high_formatted = from_decimal(high_decimal, precision=0)
                
                return f"{EURO_SYMBOL}{low_formatted:,.0f} - {EURO_SYMBOL}{high_formatted:,.0f}"
                
            except (ValueError, TypeError, KeyError, AttributeError) as e:
                logger.warning(f"Failed to generate placeholder from revenue: {e}")
        
        # Default range when no revenue available
        return f"{EURO_SYMBOL}500K - {EURO_SYMBOL}5M"
    
    def generate_next_steps(self, data: Dict[str, Any], max_steps: int = 3) -> List[str]:
        """
        Generate next steps based on missing data.
        
        SRP: Only determines which fields are missing for display
        
        Args:
            data: Collected data dictionary
            max_steps: Maximum number of steps to return
            
        Returns:
            List of next step descriptions
        """
        next_steps = []
        
        # Check for missing critical fields
        if 'company_name' not in data or not data.get('company_name'):
            next_steps.append("Company name")
        
        if 'industry' not in data or not data.get('industry'):
            next_steps.append("Industry")
        
        if 'revenue' not in data or not data.get('revenue'):
            next_steps.append("Annual revenue")
        
        if 'ebitda' not in data or not data.get('ebitda'):
            next_steps.append("EBITDA")
        
        if 'growth_rate' not in data or not data.get('growth_rate'):
            next_steps.append("Growth rate")
        
        if 'employees' not in data or not data.get('employees'):
            next_steps.append("Number of employees")
        
        # Return up to max_steps
        return next_steps[:max_steps]
    
    def generate_next_steps_html(self, next_steps: List[str]) -> str:
        """
        Generate HTML for next steps section.
        
        SRP: Only generates HTML display for next steps
        
        Args:
            next_steps: List of next step descriptions
            
        Returns:
            HTML string with next steps (marked as safe)
        """
        if not next_steps:
            return Markup('<div class="text-sm text-gray-600">All required data collected!</div>')
        
        steps_html = ""
        for i, step in enumerate(next_steps, 1):
            # Escape each step for XSS prevention
            step_escaped = html.escape(step)
            steps_html += f"""
            <li class="flex items-center text-sm text-gray-700">
                <span class="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center mr-2 text-blue-600 font-semibold text-xs">
                    {i}
                </span>
                {step_escaped}
            </li>
            """
        
        html_content = f"""
        <div class="next-steps bg-white rounded-lg p-4 border border-gray-200">
            <h3 class="text-lg font-semibold text-gray-900 mb-3">Next Steps</h3>
            <ul class="space-y-2">
                {steps_html}
            </ul>
        </div>
        """
        
        return Markup(html_content)
    
    def generate_confidence_badge(self, confidence_level: str, confidence_score: Decimal) -> str:
        """
        Generate confidence level badge HTML.
        
        SRP: Only generates HTML for confidence display
        
        Args:
            confidence_level: Level string ("low", "medium", "high")
            confidence_score: Numeric confidence score (0-100)
            
        Returns:
            HTML string with confidence badge (marked as safe)
        """
        # Determine badge color
        color_classes = {
            'low': 'bg-yellow-100 text-yellow-800 border-yellow-300',
            'medium': 'bg-blue-100 text-blue-800 border-blue-300',
            'high': 'bg-green-100 text-green-800 border-green-300',
        }
        
        color_class = color_classes.get(confidence_level.lower(), 'bg-gray-100 text-gray-800 border-gray-300')
        
        html_content = f"""
        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border {color_class}">
            <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
            </svg>
            {confidence_level.capitalize()} Confidence ({from_decimal(confidence_score, precision=0):.0f}%)
        </span>
        """
        
        return Markup(html_content)
