"""
Template Rendering Service

BANK-GRADE: Single Responsibility - Render templates with data

RESPONSIBILITY:
- Render Jinja2 templates
- Apply template context
- Handle rendering errors
- Validate rendered output

DOES NOT:
- Configure environment (delegated to TemplateConfigurationService)
- Transform data (delegated to TemplateDataTransformer)
- Generate PDFs (delegated to PDFGenerationCoordinator)
- Track versions (delegated to TemplateVersionService)

SRP Compliance: This service has ONE reason to change - rendering requirements
"""

from typing import Dict, Any, Optional
from pathlib import Path

from src.utils.logging import get_logger

try:
    from jinja2 import Environment, Template
    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False
    Environment = None
    Template = None

logger = get_logger(__name__)


class TemplateRenderingError(Exception):
    """Error during template rendering"""
    pass


class TemplateRenderingService:
    """
    BANK-GRADE SRP-COMPLIANT: Renders templates with data.
    
    SINGLE RESPONSIBILITY: Template rendering
    
    This service focuses solely on rendering templates:
    - Loading templates from environment
    - Applying data context
    - Rendering to HTML
    - Error handling
    
    Design Pattern: Service Pattern
    - Separates rendering from configuration
    - Enables testing rendering independently
    - Allows extending with different engines
    """
    
    def __init__(self, environment: Optional[Environment] = None):
        """
        Initialize template rendering service.
        
        SRP: Only rendering, no configuration
        
        Args:
            environment: Jinja2 environment (injected)
        """
        self.logger = logger
        self.env = environment
        
        if not JINJA_AVAILABLE:
            self.logger.warning("⚠️ Jinja2 not available, rendering will fail")
        
        self.logger.debug("✅ [TEMPLATE-RENDER] TemplateRenderingService initialized (SRP-compliant)")
    
    def render_template(
        self,
        template_path: str,
        data: Dict[str, Any],
        validate_output: bool = True
    ) -> str:
        """
        Render template with provided data.
        
        BANK-GRADE: Comprehensive error handling and validation
        
        SRP: Only renders, doesn't configure or transform
        
        Args:
            template_path: Path to template file (relative to templates dir)
            data: Template context data
            validate_output: Whether to validate rendered HTML
            
        Returns:
            Rendered HTML string
            
        Raises:
            TemplateRenderingError: If rendering fails
        """
        if not self.env:
            raise TemplateRenderingError(
                "Template environment not configured. "
                "Inject TemplateConfigurationService environment."
            )
        
        self.logger.info(
            f"🔄 [TEMPLATE-RENDER] Rendering template: {template_path}",
            extra={'template': template_path, 'data_keys': list(data.keys())}
        )
        
        try:
            # Step 1: Load template
            template = self._load_template(template_path)
            
            # Step 2: Render with data
            rendered_html = self._render_with_data(template, data, template_path)
            
            # Step 3: Validate output (optional)
            if validate_output:
                self._validate_rendered_output(rendered_html, template_path)
            
            self.logger.info(
                f"✅ [TEMPLATE-RENDER] Template rendered successfully: {template_path}",
                extra={
                    'template': template_path,
                    'output_length': len(rendered_html)
                }
            )
            
            return rendered_html
            
        except TemplateRenderingError:
            raise
        except Exception as e:
            self.logger.error(
                f"❌ [TEMPLATE-RENDER] Rendering failed: {template_path}",
                exc_info=True
            )
            raise TemplateRenderingError(
                f"Failed to render template {template_path}: {e}"
            ) from e
    
    def _load_template(self, template_path: str) -> Template:
        """
        Load template from environment.
        
        SRP: Only template loading
        
        Args:
            template_path: Path to template
            
        Returns:
            Jinja2 Template instance
            
        Raises:
            TemplateRenderingError: If template not found
        """
        try:
            template = self.env.get_template(template_path)
            return template
        except Exception as e:
            self.logger.error(
                f"❌ [TEMPLATE-RENDER] Template not found: {template_path}",
                exc_info=True
            )
            raise TemplateRenderingError(
                f"Template not found: {template_path}"
            ) from e
    
    def _render_with_data(
        self,
        template: Template,
        data: Dict[str, Any],
        template_path: str
    ) -> str:
        """
        Render template with data context.
        
        SRP: Only rendering
        
        Args:
            template: Jinja2 Template instance
            data: Template context data
            template_path: Template path (for logging)
            
        Returns:
            Rendered HTML string
            
        Raises:
            TemplateRenderingError: If rendering fails
        """
        try:
            rendered_html = template.render(**data)
            return rendered_html
        except Exception as e:
            self.logger.error(
                f"❌ [TEMPLATE-RENDER] Rendering failed for {template_path}",
                exc_info=True,
                extra={'error_type': type(e).__name__}
            )
            raise TemplateRenderingError(
                f"Rendering failed for {template_path}: {e}"
            ) from e
    
    def _validate_rendered_output(
        self,
        rendered_html: str,
        template_path: str
    ) -> None:
        """
        Validate rendered HTML output.
        
        SRP: Only validation
        
        Args:
            rendered_html: Rendered HTML string
            template_path: Template path (for logging)
            
        Raises:
            TemplateRenderingError: If validation fails
        """
        # Basic validation: Check for empty output
        if not rendered_html or not rendered_html.strip():
            raise TemplateRenderingError(
                f"Template {template_path} rendered empty output"
            )
        
        # Check for common rendering issues
        if '{{' in rendered_html or '{%' in rendered_html:
            self.logger.warning(
                f"⚠️ [TEMPLATE-RENDER] Unrendered Jinja2 syntax in output: {template_path}",
                extra={'template': template_path}
            )
            # Not fatal - might be intended in JavaScript
        
        # Check for basic HTML structure
        if '<html' not in rendered_html.lower() and '<!doctype' not in rendered_html.lower():
            self.logger.warning(
                f"⚠️ [TEMPLATE-RENDER] Output missing HTML structure: {template_path}",
                extra={'template': template_path}
            )
    
    def render_string(self, template_string: str, data: Dict[str, Any]) -> str:
        """
        Render template from string (for testing or dynamic templates).
        
        Args:
            template_string: Template string
            data: Template context data
            
        Returns:
            Rendered HTML string
            
        Raises:
            TemplateRenderingError: If rendering fails
        """
        if not self.env:
            raise TemplateRenderingError("Template environment not configured")
        
        try:
            template = self.env.from_string(template_string)
            rendered_html = template.render(**data)
            return rendered_html
        except Exception as e:
            self.logger.error(
                "❌ [TEMPLATE-RENDER] String rendering failed",
                exc_info=True
            )
            raise TemplateRenderingError(
                f"String rendering failed: {e}"
            ) from e
    
    def is_available(self) -> bool:
        """
        Check if rendering is available.
        
        Returns:
            True if environment configured
        """
        return self.env is not None
