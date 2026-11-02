from src.errors.error_types import TemplateRenderError

"""
Valuation Template Service
Jinja2-based template rendering for valuation sections
Privacy-safe: No AI, pure template logic
"""

import logging
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
import os
import time
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = logging.getLogger(__name__)


class ValuationTemplateService:
    """
    Jinja2-based template rendering for valuation sections
    Privacy-safe: No AI, pure template logic
    """

    def __init__(self, template_dir: str = "src/templates"):
        """
        Initialize template service with Jinja2 environment
        
        DEPRECATION WARNING: This service is deprecated.
        Use TemplateService from src.services.infrastructure.template_service instead.
        Migration deadline: 2025-01-15
        """
        # DEPRECATION WARNING
        logger.warning(
            "⚠️ [DEPRECATED] ValuationTemplateService is deprecated and will be removed in v2.0",
            extra={
                "deprecated_service": "ValuationTemplateService",
                "replacement": "TemplateService (src.services.infrastructure.template_service)",
                "migration_deadline": "2025-01-15",
                "severity": "MEDIUM",
                "action_required": "Migrate to new TemplateService",
                "documentation": "See CRITICAL_LOG_AUDIT_REPORT.md for migration guide"
            }
        )
        
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Navigate to the project root and then to templates
        project_root = os.path.join(current_dir, '..', '..', '..')
        template_path = os.path.join(project_root, template_dir)

        # Resolve absolute path and normalize
        template_path = os.path.abspath(template_path)

        # CRITICAL FIX: Verify template directory exists and is a directory
        # Enhanced fallback logic with better path resolution
        if not os.path.exists(template_path):
            logger.error(
                "❌ [TEMPLATE] Template directory not found - trying fallbacks",
                extra={
                    'calculated_path': template_path,
                    'current_dir': current_dir,
                    'project_root': project_root,
                    'template_dir': template_dir,
                    'severity': 'HIGH',
                    'correlation_id': None  # Will be set by caller
                }
            )
            
            # BANK-GRADE: Comprehensive fallback paths (in priority order)
            fallback_paths = [
                os.path.join('/app', template_dir),  # Container path (highest priority)
                os.path.join(os.getcwd(), template_dir),  # CWD relative
                os.path.join('/app', 'src', 'templates'),  # Explicit container src path
                os.path.join(project_root, 'src', 'templates'),  # Explicit src path
            ]
            
            # Try each fallback path
            template_path_found = False
            for fallback_path in fallback_paths:
                if os.path.exists(fallback_path) and os.path.isdir(fallback_path):
                    logger.info(
                        f"✅ [TEMPLATE] Found template directory via fallback: {fallback_path}",
                        extra={
                            'fallback_path': fallback_path,
                            'original_path': template_path,
                            'fallback_success': True
                        }
                    )
                    template_path = fallback_path
                    template_path_found = True
                    break
            
            # If still not found, log critical error and create directory
            if not template_path_found:
                logger.error(
                    "❌ [TEMPLATE] CRITICAL: No valid template path found after all fallbacks",
                    extra={
                        'original_path': template_path,
                        'fallback_paths_tried': fallback_paths,
                        'severity': 'CRITICAL',
                        'action_required': 'Check Docker volume mounts and template directory structure',
                        'documentation': 'See CRITICAL_LOG_AUDIT_REPORT.md'
                    }
                )
                # Create fallback directory structure (will fail gracefully later)
                try:
                    os.makedirs(template_path, exist_ok=True)
                    logger.warning(
                        f"⚠️ [TEMPLATE] Created empty template directory at {template_path} - reports will use fallback HTML",
                        extra={'created_path': template_path, 'fallback_mode': True}
                    )
                except (OSError, PermissionError) as e:
                    logger.error(
                        "❌ [TEMPLATE] Failed to create template directory - system will use fallback HTML generation",
                        extra={
                            'error': str(e),
                            'error_type': type(e).__name__,
                            'fallback_mode': True
                        }
                    )
                    # Continue with invalid path - will fail gracefully in render_section

        # VALIDATION FIX: Verify path is actually a directory, not a file
        if os.path.exists(template_path):
            if not os.path.isdir(template_path):
                logger.error(
                    f"[TEMPLATE] Template path is a file, not a directory: {template_path}",
                    extra={'template_path': template_path}
                )
                # Use parent directory as fallback
                template_path = os.path.dirname(template_path)
                logger.warning(f"[TEMPLATE] Using parent directory: {template_path}")

        self.template_path = template_path

        # Initialize Jinja2 environment with verified path
        self.env = Environment(
            loader=FileSystemLoader(template_path),
            autoescape=True,
            enable_async=True,
        )

        # Add custom Jinja2 filters for currency and number formatting
        self.env.filters['format_currency'] = self._format_currency
        self.env.filters['format_number'] = self._format_number

        # Progressive section templates
        self.templates = {
            'phase_1_preview': 'sections/quick_preview.html',
            'phase_2_dcf_basic': 'sections/dcf_basic.html',
            'phase_2_multiples': 'sections/multiples_basic.html',
            'phase_3_dcf_full': 'sections/dcf_complete.html',
            'phase_3_adjustments': 'sections/adjustments.html',
            'phase_4_owner_factor': 'sections/owner_analysis.html',
            'complete_report': 'base/full_report.html'
        }

        # Verify template files exist
        template_health = self._verify_templates_exist()

        logger.info(
            "✅ [TEMPLATE] ValuationTemplateService initialized (DEPRECATED)",
            extra={
                'template_path': template_path,
                'templates_found': template_health['found_count'],
                'templates_missing': template_health['missing_count'],
                'health_status': template_health['status'],
                'deprecation_warning': 'Use TemplateService from infrastructure instead',
                'migration_deadline': '2025-01-15'
            }
        )

    def _verify_templates_exist(self):
        """
        Verify that critical template files exist
        Logs warnings for missing templates but doesn't fail initialization
        
        Returns:
            Dict with template health status
        """
        # BANK-GRADE: Check for templates in both old and new structures
        critical_templates = [
            # Old structure (deprecated)
            'sections/instant_overview.html',
            'sections/revenue_analysis.html',
            'sections/industry_comparison.html',
            # New structure (current)
            'info_tab/master_info_tab.html',
            'accountant_view/base.html',
            'valuation_report.html',
        ]

        missing_templates = []
        found_templates = []
        
        for template in critical_templates:
            template_full_path = os.path.join(self.template_path, template)
            if not os.path.exists(template_full_path):
                missing_templates.append(template)
                logger.debug(
                    f"[TEMPLATE] Template not found: {template}",
                    extra={
                        'template_path': template,
                        'full_path': template_full_path,
                        'template_dir': self.template_path,
                        'severity': 'LOW'  # Debug level since we have fallbacks
                    }
                )
            else:
                found_templates.append(template)

        # BANK-GRADE: Calculate health status
        total_templates = len(critical_templates)
        found_count = len(found_templates)
        missing_count = len(missing_templates)
        health_percentage = (found_count / total_templates * 100) if total_templates > 0 else 0
        
        if health_percentage >= 90:
            health_status = "HEALTHY"
            log_level = "info"
        elif health_percentage >= 50:
            health_status = "DEGRADED"
            log_level = "warning"
        else:
            health_status = "CRITICAL"
            log_level = "error"

        if missing_count > 0:
            getattr(logger, log_level)(
                f"⚠️ [TEMPLATE] Template health check: {health_status} ({health_percentage:.0f}%)",
                extra={
                    'missing_templates': missing_templates,
                    'found_templates': found_templates,
                    'template_dir': self.template_path,
                    'health_status': health_status,
                    'health_percentage': health_percentage,
                    'found_count': found_count,
                    'missing_count': missing_count,
                    'total_count': total_templates,
                    'fallback_available': True,
                    'user_impact': 'Reports will use fallback HTML generation' if health_percentage < 50 else 'Minor visual differences in reports'
                }
            )
        else:
            logger.info(
                f"✅ [TEMPLATE] All {total_templates} critical templates verified in {self.template_path}",
                extra={
                    'template_dir': self.template_path,
                    'health_status': 'HEALTHY',
                    'templates_count': total_templates
                }
            )
        
        return {
            'status': health_status,
            'found_count': found_count,
            'missing_count': missing_count,
            'total_count': total_templates,
            'health_percentage': health_percentage,
            'missing_templates': missing_templates,
            'found_templates': found_templates
        }

    async def render_partial_section(
        self,
        section_id: str,
        phase: int,
        data: Optional[Dict[str, Any]] = None,
        status: str = 'loading'
    ) -> str:
        """
        Render individual section with state management

        Args:
            section_id: Unique section identifier
            phase: Valuation phase (0-4)
            data: Section data (if status='complete')
            status: 'loading', 'complete', or 'error'
        """
        logger.info(f"[TEMPLATE] Rendering partial section | section={section_id} | phase={phase} | status={status}")

        template_map = {
            'loading': 'progressive/section_loading.html',
            'complete': f'progressive/phase_{phase}_{section_id}.html',
            'error': 'progressive/section_error.html'
        }

        template_path = template_map.get(status, template_map['loading'])

        context = {
            'section_id': section_id,
            'section_name': self._get_section_display_name(section_id),
            'phase': phase,
            'data': data or {},
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            template = self.env.get_template(template_path)
            return await template.render_async(**context)
        except TemplateRenderError as e:
            logger.error(f"[TEMPLATE] Failed to render partial section {section_id}: {e}")
            # Return minimal error HTML
            return f"""
            <div class="section-error bg-red-50 border border-red-200 rounded-lg p-4">
                <div class="flex items-center">
                    <svg class="h-5 w-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                    </svg>
                    <span class="text-red-700">Template rendering failed</span>
                </div>
            </div>
            """

    def _get_section_display_name(self, section_id: str) -> str:
        """Get human-readable section name"""
        section_names = {
            'instant': 'Instant Preview',
            'preview': 'Quick Preview',
            'dcf_basic': 'DCF Analysis',
            'multiples': 'Market Multiples',
            'dcf_full': 'Complete DCF',
            'adjustments': 'Risk Adjustments',
            'owner_factor': 'Owner Analysis',
            'complete': 'Final Valuation'
        }
        return section_names.get(section_id, section_id.replace('_', ' ').title())

    async def render_error_section(
        self,
        section_id: str,
        phase: int,
        error_message: str
    ) -> str:
        """Render error section with specific error message"""
        logger.info(f"[TEMPLATE] Rendering error section | section={section_id} | phase={phase}")

        context = {
            'section_id': section_id,
            'section_name': self._get_section_display_name(section_id),
            'phase': phase,
            'error_message': error_message,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            template = self.env.get_template('progressive/section_error.html')
            return await template.render_async(**context)
        except TemplateRenderError as e:
            logger.error(f"[TEMPLATE] Failed to render error section: {e}")
            return f"""
            <div class="section-error bg-red-50 border border-red-200 rounded-lg p-4">
                <div class="flex items-center">
                    <svg class="h-5 w-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                    </svg>
                    <span class="text-red-700">Section generation failed: {error_message}</span>
                </div>
            </div>
            """

    async def render_section(
        self,
        section_name: str,
        data: Dict[str, Any],
        phase: int = 0
    ) -> str:
        """
        Render individual section template

        This method renders granular section templates for section-by-section streaming.
        Used by StreamingHTMLGenerator for progressive report generation.

        Args:
            section_name: Section template name (e.g., 'instant_overview', 'revenue_analysis')
            data: Section data dictionary matching template variables
            phase: Valuation phase (0-4)

        Returns:
            Rendered HTML string
        """
        logger.info(f"[TEMPLATE] Rendering section | section={section_name} | phase={phase}")

        try:
            # Load section template
            template_path = f"sections/{section_name}.html"

            # CRITICAL FIX: Verify template exists before loading
            template_full_path = os.path.join(self.template_path, template_path)
            if not os.path.exists(template_full_path):
                # PERFORMANCE FIX: Only list directory if it exists, and cache result
                available_files_info = "Unable to list"
                try:
                    sections_dir = os.path.join(self.template_path, 'sections')
                    if os.path.exists(sections_dir) and os.path.isdir(sections_dir):
                        available_files = os.listdir(sections_dir)
                        available_files_info = f"{len(available_files)} files found"
                        logger.debug(
                            f"[TEMPLATE] Available section files: {len(available_files)}",
                            extra={'available_files': available_files[:10]}  # Limit to first 10
                        )
                except (OSError, PermissionError) as e:
                    logger.warning(f"[TEMPLATE] Could not list sections directory: {e}")
                    available_files_info = f"Error: {str(e)}"

                logger.error(
                    f"[TEMPLATE] Template file not found: {template_path}",
                    extra={
                        'section_name': section_name,
                        'template_path': template_path,
                        'full_path': template_full_path,
                        'template_dir': self.template_path,
                        'available_files': available_files_info
                    }
                )
                # Return error HTML instead of crashing
                return await self.render_error_section(section_name, phase, f"Template not found: {template_path}")

            template = self.env.get_template(template_path)

            # Add phase to context
            context = {**data, 'phase': phase}

            # Render template
            html = await template.render_async(**context)

            logger.debug(
                f"[TEMPLATE] Section rendered successfully",
                extra={
                    'section_name': section_name,
                    'html_length': len(html),
                    'phase': phase
                }
            )
            return html

        except TemplateRenderError as e:
            logger.error(
                f"[TEMPLATE] Failed to render section {section_name}",
                extra={
                    'section_name': section_name,
                    'phase': phase,
                    'error': str(e)
                },
                exc_info=True
            )
            # Return error placeholder
            return f"""
            <div class="section-error bg-red-50 border border-red-200 rounded-lg p-4">
                <div class="flex items-center">
                    <svg class="h-5 w-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                    </svg>
                    <span class="text-red-700">Template rendering failed: {section_name}</span>
                </div>
            </div>
            """

    async def render_progressive_section(
        self, 
        phase: str, 
        section: str, 
        data: Dict[str, Any]
    ) -> str:
        """
        Render a single section for progressive display

        Args:
            phase: Phase identifier (phase_1, phase_2, etc.)
            section: Section identifier (preview, dcf_basic, etc.)
            data: Data to render in template

        Returns:
            Rendered HTML string
        """
        try:
            template_name = self.templates.get(f'{phase}_{section}')
            if not template_name:
                logger.error(f"Template not found for {phase}_{section}")
                return self._render_error_section(section, f"Template not found for {phase}_{section}")

            template = self.env.get_template(template_name)

            # Add common data to all templates
            enhanced_data = {
                **data,
                'render_timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'phase': phase,
                'section': section
            }

            html = await template.render_async(**enhanced_data)
            logger.debug(f"Rendered {phase}_{section} template successfully")
            return html

        except TemplateRenderError as e:
            logger.error(f"Template rendering failed for {phase}_{section}: {e}")
            return self._render_error_section(section, str(e))

    async def render_loading_placeholder(self, section: str) -> str:
        """
        Generate loading placeholder for pending sections

        Args:
            section: Section name for placeholder

        Returns:
            HTML string for loading placeholder
        """
        return f'''
        <div class="section-placeholder" data-section="{section}">
            <div class="animate-pulse bg-gray-100 rounded-lg p-6">
                <div class="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div class="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
                <div class="h-4 bg-gray-200 rounded w-2/3"></div>
            </div>
            <div class="text-center mt-4">
                <div class="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800">
                    <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Generating {section.replace('_', ' ').title()}...
                </div>
            </div>
        </div>
        '''

    def _render_error_section(self, section: str, error_message: str) -> str:
        """
        Render error section when template fails

        Args:
            section: Section name
            error_message: Error message to display

        Returns:
            HTML string for error section
        """
        return f'''
        <div class="section-error bg-red-50 border border-red-200 rounded-lg p-4" data-section="{section}">
            <div class="flex items-center">
                <svg class="h-5 w-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                </svg>
                <h3 class="text-sm font-medium text-red-800">Error generating {section.replace('_', ' ').title()}</h3>
            </div>
            <div class="mt-2 text-sm text-red-700">
                <p>{error_message}</p>
            </div>
        </div>
        '''

    async def render_complete_report(self, data: Dict[str, Any]) -> str:
        """
        Render complete valuation report

        Args:
            data: Complete valuation data

        Returns:
            Rendered HTML string for complete report
        """
        try:
            template = self.env.get_template('base/full_report.html')

            # Add metadata
            enhanced_data = {
                **data,
                'render_timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'report_type': 'complete'
            }

            html = await template.render_async(**enhanced_data)
            logger.info("Complete report rendered successfully")
            return html

        except TemplateRenderError as e:
            logger.error(f"Complete report rendering failed: {e}")
            return self._render_error_section('complete_report', str(e))

    def get_available_templates(self) -> Dict[str, str]:
        """
        Get list of available templates

        Returns:
            Dictionary of template names and paths
        """
        return self.templates.copy()

    def _format_currency(self, value: Decimal, currency: str = "EUR") -> str:
        """
        Format currency value with thousand separators

        Args:
            value: Numeric value to format
            currency: Currency code (EUR, USD, etc.)

        Returns:
            Formatted currency string (e.g., "€1,000,000")
        """
        from src.utils.core.formatting_helpers import EURO_SYMBOL
        
        if value is None:
            return f"{EURO_SYMBOL}0"
        try:
            value = to_decimal(value)
            if currency == "EUR":
                return f"{EURO_SYMBOL}{value:,.0f}"
            elif currency == "USD":
                return f"${value:,.0f}"
            else:
                return f"{value:,.0f} {currency}"
        except (ValueError, TypeError):
            return f"{EURO_SYMBOL}0"

    def _format_number(self, value: Decimal, decimals: int = 0) -> str:
        """
        Format number with thousand separators

        Args:
            value: Numeric value to format
            decimals: Number of decimal places

        Returns:
            Formatted number string (e.g., "1,000,000" or "1,000.00")
        """
        if value is None:
            return "0"
        try:
            value = to_decimal(value)
            return f"{value:,.{decimals}f}"
        except (ValueError, TypeError):
            return "0"

    def validate_template_data(self, phase: str, section: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and enhance template data

        Args:
            phase: Phase identifier
            section: Section identifier
            data: Raw data to validate

        Returns:
            Validated and enhanced data
        """
        # Add default values for common fields
        enhanced_data = {
            'company_name': data.get('company_name', 'Unknown Company'),
            'industry': data.get('industry', 'Unknown'),
            'confidence_score': data.get('confidence_score', 0),
            'confidence_level': data.get('confidence_level', 'unknown'),
            'methodology': data.get('methodology', 'Unknown'),
            'timestamp': data.get('timestamp', time.strftime("%Y-%m-%d %H:%M:%S")),
            **data
        }

        # Phase-specific validation
        if phase == 'phase_1':
            # Ensure preview has required fields
            enhanced_data.update({
                'value_low': data.get('value_low', 0),
                'value_mid': data.get('value_mid', 0),
                'value_high': data.get('value_high', 0),
                'multiple_low': data.get('multiple_low', 0),
                'multiple_high': data.get('multiple_high', 0),
                'data_completeness': data.get('data_completeness', 0)
            })

        elif phase == 'phase_2':
            # Ensure intermediate has DCF and multiples data
            enhanced_data.update({
                'dcf_data': data.get('dcf_data', {}),
                'multiples_data': data.get('multiples_data', {}),
                'combined_value_low': data.get('combined_value_low', 0),
                'combined_value_mid': data.get('combined_value_mid', 0),
                'combined_value_high': data.get('combined_value_high', 0)
            })

        elif phase == 'phase_3':
            # Ensure advanced has full DCF and adjustments
            enhanced_data.update({
                'dcf_complete': data.get('dcf_complete', {}),
                'adjustments': data.get('adjustments', {}),
                'final_value_low': data.get('final_value_low', 0),
                'final_value_mid': data.get('final_value_mid', 0),
                'final_value_high': data.get('final_value_high', 0)
            })

        elif phase == 'phase_4':
            # Ensure complete has owner analysis
            enhanced_data.update({
                'owner_analysis': data.get('owner_analysis', {}),
                'final_valuation': data.get('final_valuation', {}),
                'executive_summary': data.get('executive_summary', ''),
                'recommendations': data.get('recommendations', [])
            })

        return enhanced_data

    async def render_section_with_validation(
        self, 
        phase: str, 
        section: str, 
        data: Dict[str, Any]
    ) -> str:
        """
        Render section with data validation

        Args:
            phase: Phase identifier
            section: Section identifier
            data: Raw data to validate and render

        Returns:
            Rendered HTML string
        """
        # Validate and enhance data
        validated_data = self.validate_template_data(phase, section, data)

        # Render with validated data
        return await self.render_progressive_section(phase, section, validated_data)

