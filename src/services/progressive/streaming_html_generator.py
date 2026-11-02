"""
Streaming HTML Generator Service

This service orchestrates section-by-section HTML generation for progressive
valuation reports, similar to Lovable.dev's real-time code generation experience.

Features:
- Section-by-section generation with loading states
- Smooth section replacement (not append-only)
- Progress indicators per section
- Milestone-based triggering (25%, 50%, 75%, 100%)
- Optimized for streaming performance

Author: Upswitch CTO Team
Date: January 27, 2025
Status: Production Ready
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from src.errors.error_types import TemplateRenderError
from src.services.progressive.html_optimizer import StreamingHTMLOptimizer
from src.services.progressive.progressive_valuation_service import ProgressiveValuationService
from src.services.progressive.progressive_valuation_types import ValuationPhase
from src.services.templates.template_service import ValuationTemplateService
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import APIError

logger = logging.getLogger(__name__)


class SectionStatus(str, Enum):
    """Section generation status"""

    PENDING = "pending"
    LOADING = "loading"
    CALCULATING = "calculating"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ReportSection:
    """
    Represents a single section of the valuation report
    """

    id: str
    name: str
    phase: int
    status: SectionStatus
    html: str = ""
    progress: int = 0
    error: Optional[str] = None
    calculation_time: Decimal = Decimal("0.0")
    timestamp: Optional[Decimal] = None


class StreamingHTMLGenerator:
    """
    Orchestrates progressive HTML report generation

    This class manages the entire lifecycle of generating a valuation report
    in real-time, section by section, with smooth animations and loading states.

    Architecture:
    1. Determine data completeness milestone (25%, 50%, 75%, 100%)
    2. Generate loading placeholders for pending sections
    3. Calculate sections in parallel where possible
    4. Stream completed sections with fade-in animations
    5. Update progress indicators in real-time
    """

    def __init__(
        self,
        progressive_service: ProgressiveValuationService,
        template_service: ValuationTemplateService,
        html_optimizer: StreamingHTMLOptimizer,
    ):
        """
        Initialize the streaming HTML generator

        Args:
            progressive_service: Service for phased valuation calculations
            template_service: Service for rendering HTML templates
            html_optimizer: Service for optimizing HTML for streaming
        """
        self.progressive_service = progressive_service
        self.template_service = template_service
        self.html_optimizer = html_optimizer

        # Initialize section calculations helper
        # FIX: ValuationCalculationCoordinator.__init__() takes no arguments (only self)
        from src.services.progressive.section_calculations import ValuationCalculationCoordinator

        self.section_calc = ValuationCalculationCoordinator()

        # Section definitions for each milestone (granular section-by-section)
        self.milestone_sections = {
            25: [  # Phase 1 - First 3 sections
                {"id": "instant-overview", "name": "Instant Overview", "phase": 1},
                {"id": "revenue-analysis", "name": "Revenue Analysis", "phase": 1},
                {"id": "industry-comparison", "name": "Industry Comparison", "phase": 1},
            ],
            50: [  # Phase 2 - Add 2 more sections
                {"id": "instant-overview", "name": "Instant Overview", "phase": 1},
                {"id": "revenue-analysis", "name": "Revenue Analysis", "phase": 1},
                {"id": "industry-comparison", "name": "Industry Comparison", "phase": 1},
                {"id": "ebitda-analysis", "name": "EBITDA Analysis", "phase": 2},
                {"id": "growth-metrics", "name": "Growth Metrics", "phase": 2},
            ],
            75: [  # Phase 3 - Add 3 more sections
                {"id": "instant-overview", "name": "Instant Overview", "phase": 1},
                {"id": "revenue-analysis", "name": "Revenue Analysis", "phase": 1},
                {"id": "industry-comparison", "name": "Industry Comparison", "phase": 1},
                {"id": "ebitda-analysis", "name": "EBITDA Analysis", "phase": 2},
                {"id": "growth-metrics", "name": "Growth Metrics", "phase": 2},
                {"id": "dcf-valuation", "name": "DCF Valuation", "phase": 3},
                {"id": "market-multiples", "name": "Market Multiples", "phase": 3},
                {"id": "risk-assessment", "name": "Risk Assessment", "phase": 3},
            ],
            100: [  # Phase 4 - Add final 2 sections
                {"id": "instant-overview", "name": "Instant Overview", "phase": 1},
                {"id": "revenue-analysis", "name": "Revenue Analysis", "phase": 1},
                {"id": "industry-comparison", "name": "Industry Comparison", "phase": 1},
                {"id": "ebitda-analysis", "name": "EBITDA Analysis", "phase": 2},
                {"id": "growth-metrics", "name": "Growth Metrics", "phase": 2},
                {"id": "dcf-valuation", "name": "DCF Valuation", "phase": 3},
                {"id": "market-multiples", "name": "Market Multiples", "phase": 3},
                {"id": "risk-assessment", "name": "Risk Assessment", "phase": 3},
                {"id": "owner-analysis", "name": "Owner Analysis", "phase": 4},
                {"id": "final-recommendation", "name": "Final Recommendation", "phase": 4},
            ],
        }

    async def generate_progressive_report(
        self, session_id: str, conversation_context: Dict[str, Any], milestone: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate progressive HTML report for a specific milestone

        This is the main entry point for generating a progressive report.
        It yields section events as they're generated.

        Args:
            session_id: Conversation session ID
            conversation_context: Current conversation context with collected data
            milestone: Data completeness milestone (25, 50, 75, 100)

        Yields:
            Dict with section events:
            - type: 'section_loading' | 'section_complete' | 'progress_update' | 'report_complete'
            - section: Section ID
            - phase: Valuation phase
            - html: HTML content
            - progress: Overall progress percentage
            - timestamp: Event timestamp
        """
        start_time = time.time()
        logger.info(
            f"[STREAMING_HTML] Starting progressive report generation",
            extra={
                "session_id": session_id,
                "milestone": milestone,
                "context_keys": list(conversation_context.keys()),
            },
        )

        try:
            # Get sections for this milestone
            sections_to_generate = self.milestone_sections.get(milestone, [])
            if not sections_to_generate:
                logger.warning(
                    f"[STREAMING_HTML] No sections defined for milestone {milestone}",
                    extra={"session_id": session_id},
                )
                return

            total_sections = len(sections_to_generate)
            completed_sections = 0

            # Generate each section
            for section_def in sections_to_generate:
                section_start = time.time()
                section_id = section_def["id"]
                section_name = section_def["name"]
                phase = section_def["phase"]

                logger.info(
                    f"[STREAMING_HTML] Generating section: {section_name}",
                    extra={"session_id": session_id, "section_id": section_id, "phase": phase},
                )

                # Emit loading state
                loading_html = await self._generate_loading_placeholder(
                    section_id, section_name, phase
                )
                yield {
                    "type": "section_loading",
                    "section": section_id,
                    "name": section_name,
                    "phase": phase,
                    "html": loading_html,
                    "progress": int((completed_sections / total_sections) * 100),
                    "session_id": session_id,
                    "timestamp": time.time(),
                }

                # Generate section content
                try:
                    section_html = await self._generate_section(
                        section_id, phase, conversation_context, session_id
                    )

                    # Optimize HTML for streaming
                    optimized_html = self.html_optimizer.optimize_for_streaming(section_html)

                    completed_sections += 1
                    section_time = time.time() - section_start

                    # Emit completed section
                    yield {
                        "type": "section_complete",
                        "section": section_id,
                        "name": section_name,
                        "phase": phase,
                        "html": optimized_html,
                        "progress": int((completed_sections / total_sections) * 100),
                        "calculation_time": section_time,
                        "session_id": session_id,
                        "timestamp": time.time(),
                    }

                    logger.info(
                        f"[STREAMING_HTML] Section complete: {section_name}",
                        extra={
                            "session_id": session_id,
                            "section_id": section_id,
                            "calculation_time": section_time,
                            "html_length": len(optimized_html),
                        },
                    )

                except TemplateRenderError as e:
                    logger.error(
                        f"[STREAMING_HTML] Error generating section: {section_name}",
                        extra={"session_id": session_id, "section_id": section_id, "error": str(e)},
                        exc_info=True,
                    )

                    # Emit error section
                    error_html = await self._generate_error_placeholder(
                        section_id, section_name, str(e)
                    )
                    yield {
                        "type": "section_error",
                        "section": section_id,
                        "name": section_name,
                        "phase": phase,
                        "html": error_html,
                        "error": str(e),
                        "session_id": session_id,
                        "timestamp": time.time(),
                    }

            # Emit report complete event
            total_time = time.time() - start_time
            yield {
                "type": "report_complete",
                "milestone": milestone,
                "total_sections": total_sections,
                "total_time": total_time,
                "session_id": session_id,
                "timestamp": time.time(),
            }

            logger.info(
                f"[STREAMING_HTML] Progressive report complete",
                extra={
                    "session_id": session_id,
                    "milestone": milestone,
                    "total_sections": total_sections,
                    "total_time": total_time,
                },
            )

        except TemplateRenderError as e:
            logger.error(
                f"[STREAMING_HTML] Fatal error in progressive report generation",
                extra={"session_id": session_id, "milestone": milestone},
                exc_info=True,
            )
            raise

    async def _generate_section(
        self, section_id: str, phase: int, conversation_context: Dict[str, Any], session_id: str
    ) -> str:
        """
        Generate HTML for a specific section using granular calculation methods

        Args:
            section_id: Section identifier (e.g., 'instant-overview', 'revenue-analysis')
            phase: Valuation phase (0-4)
            conversation_context: Conversation context with collected data
            session_id: Session identifier

        Returns:
            HTML string for the section
        """
        try:
            # CRITICAL FIX: Use existing methods and create fallback for sections
            # Get industry and business_type from collected_data
            industry = (
                collected_data.get("industry_category")
                or collected_data.get("industry")
                or "general"
            )
            business_type_id = collected_data.get("business_type")

            # Map section IDs to calculation logic
            calc_data = None
            if section_id == "instant-overview" or section_id == "revenue-analysis":
                calc_data = self.section_calc.calculate_revenue_based_valuation(
                    collected_data, industry, business_type_id
                )
            elif section_id == "ebitda-analysis" or section_id == "industry-comparison":
                calc_data = self.section_calc.calculate_ebitda_based_valuation(
                    collected_data, industry, business_type_id
                )
            elif section_id == "dcf-valuation":
                calc_data = self.section_calc.calculate_dcf_valuation(
                    collected_data, business_type_id=business_type_id
                )
            elif section_id == "market-multiples":
                calc_data = self.section_calc.calculate_multiples_valuation(
                    collected_data, industry, business_type_id
                )
            else:
                # Fallback for other sections
                calc_data = {"section_id": section_id, "has_valid_data": False}

            # Skip rendering if no calculation method or no valid data
            if not calc_data or not calc_data.get("has_valid_data", False):
                logger.warning(
                    f"[STREAMING_HTML] No valid data for section: {section_id}",
                    extra={"session_id": session_id, "section_id": section_id},
                )
                return f"<div class='text-gray-500'>Section not available</div>"

            # Use calculated data (already calculated above)
            section_data = calc_data
            logger.debug(
                f"[STREAMING_HTML] Section data calculated",
                extra={
                    "session_id": session_id,
                    "section_id": section_id,
                    "has_data": section_data.get("has_valid_data"),
                },
            )

            # CRITICAL FIX: Data already validated above
            has_valid_data = section_data.get("has_valid_data", True)
            if not has_valid_data:
                logger.info(
                    f"[STREAMING_HTML] Section has no valid data, returning placeholder",
                    extra={"session_id": session_id, "section_id": section_id},
                )
                section_name = section_id.replace("-", " ").title()
                return f"""
                <div class="section-container bg-white rounded-lg shadow-sm p-6 mb-4 border border-gray-200" data-section="{section_id}">
                  <div class="section-header mb-4">
                    <div>
                      <h2 class="text-2xl font-bold text-gray-900">{section_name}</h2>
                    </div>
                  </div>
                  <div class="section-content">
                    <div class="bg-gray-50 rounded-lg p-4 border border-gray-200 text-center">
                      <p class="text-gray-600 mb-2">Complete financial questions to see {section_name.lower()}</p>
                      <p class="text-sm text-gray-500">We need revenue and financial data to calculate this section</p>
                    </div>
                  </div>
                </div>
                """

            # CRITICAL FIX: Filter out UI-only fields that shouldn't be rendered in templates
            # These fields are for internal use only and should not appear in HTML output
            ui_only_fields = [
                "data_completeness",  # Data completeness bars - removed from UI
                "confidence",  # Confidence level bars - removed from UI
                "phase",  # Phase indicators - removed from UI
                "data_collected",  # "X of Y metrics collected" - removed from UI
                "data_total",  # Total metrics count - removed from UI
                "has_valid_data",  # Internal flag - don't pass to template
            ]

            # Create filtered data dict without UI-only fields
            filtered_data = {k: v for k, v in section_data.items() if k not in ui_only_fields}

            # Render section template
            template_name = section_id.replace("-", "_")  # Convert kebab-case to snake_case
            logger.debug(
                f"[STREAMING_HTML] Rendering section template",
                extra={"session_id": session_id, "template_name": template_name},
            )
            # Pass phase=0 to prevent template from rendering phase indicators
            html = await self.template_service.render_section(template_name, filtered_data, 0)

            return html

        except APIError as e:
            logger.error(
                f"[STREAMING_HTML] Error generating section content",
                extra={
                    "session_id": session_id,
                    "section_id": section_id,
                    "phase": phase,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def _generate_loading_placeholder(
        self, section_id: str, section_name: str, phase: int
    ) -> str:
        """
        Generate loading placeholder HTML for a section

        Args:
            section_id: Section identifier
            section_name: Human-readable section name
            phase: Valuation phase

        Returns:
            HTML string with loading animation
        """
        return f"""
        <div class="animate-pulse bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200 bg-[length:200%_100%] rounded-lg p-6 mb-4" data-section="{section_id}">
            <div class="flex items-center gap-3 mb-4">
                <div class="w-8 h-8 bg-blue-400 rounded-full animate-spin border-4 border-blue-200 border-t-blue-600"></div>
                <div>
                    <h3 class="text-lg font-semibold text-gray-700">{section_name}</h3>
                    <p class="text-sm text-gray-500">Calculating...</p>
                </div>
            </div>
            <div class="space-y-3">
                <div class="h-4 bg-gray-400 rounded w-3/4"></div>
                <div class="h-4 bg-gray-400 rounded w-1/2"></div>
                <div class="h-4 bg-gray-400 rounded w-5/6"></div>
            </div>
        </div>
        """

    async def _generate_error_placeholder(
        self, section_id: str, section_name: str, error_message: str
    ) -> str:
        """
        Generate error placeholder HTML for a section

        Args:
            section_id: Section identifier
            section_name: Human-readable section name
            error_message: Error message to display

        Returns:
            HTML string with error message
        """
        return f"""
        <div class="bg-red-50 border border-red-200 rounded-lg p-6 mb-4" data-section="{section_id}">
            <div class="flex items-center gap-3 mb-2">
                <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <h3 class="text-lg font-semibold text-red-900">{section_name}</h3>
            </div>
            <p class="text-sm text-red-700">Unable to generate this section. Please try again.</p>
            <p class="text-xs text-red-600 mt-2 font-mono">{error_message}</p>
        </div>
        """

    def calculate_data_completeness(self, conversation_context: Dict[str, Any]) -> int:
        """
        Calculate data completeness percentage

        Args:
            conversation_context: Conversation context with collected data

        Returns:
            Completeness percentage (0-100)
        """
        collected_data = conversation_context.get("collected_data", {})

        required_fields = [
            "company_name",
            "industry",
            "business_type",
            "revenue",
            "ebitda",
            "growth_rate",
            "country",
            "founding_year",
        ]

        collected_count = sum(
            1 for field in required_fields if collected_data.get(field) is not None
        )

        return int((collected_count / len(required_fields)) * 100)

    def determine_milestone(self, completeness: int) -> Optional[int]:
        """
        Determine which milestone to trigger based on completeness

        Args:
            completeness: Data completeness percentage (0-100)

        Returns:
            Milestone (25, 50, 75, or 100) or None if no milestone reached
        """
        if completeness >= 100:
            return 100
        elif completeness >= 75:
            return 75
        elif completeness >= 50:
            return 50
        elif completeness >= 25:
            return 25
        else:
            return None
