from src.errors.error_types import TemplateRenderError

"""
Basic Renderer

Basic HTML rendering functionality for simple templates.
"""

from typing import Dict, Any
import json
from datetime import datetime
from src.utils.logging import get_logger
from src.services.infrastructure.exceptions import TemplateRenderingError

try:
    from jinja2 import Environment
    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False

logger = get_logger(__name__)


class BasicRenderer:
    """
    Basic HTML rendering for simple templates.
    """
    
    def __init__(self, env: Environment, templates_dir):
        """
        Initialize basic renderer.
        
        Args:
            env: Jinja2 Environment instance
            templates_dir: Path to templates directory
        """
        self.env = env
        self.templates_dir = templates_dir
        self.logger = logger
    
    def render_valuation_report(
        self,
        valuation_data: Dict[str, Any],
        template_name: str = "valuation_report.html"
    ) -> str:
        """
        Render valuation report HTML from template.
        
        Args:
            valuation_data: Valuation data dictionary
            template_name: Template filename
            
        Returns:
            Rendered HTML string
        """
        if not JINJA_AVAILABLE:
            self.logger.error("Jinja2 not installed - cannot render template")
            return self._generate_fallback_html(valuation_data)
        
        try:
            template = self.env.get_template(template_name)
            
            # Add generation timestamp
            valuation_data['generation_timestamp'] = datetime.utcnow().isoformat()
            
            html = template.render(**valuation_data)
            
            self.logger.info(f"✅ Rendered template: {template_name}")
            return html
            
        except (KeyError, AttributeError, TypeError) as e:
            self.logger.warning(f"Template data error: {e}")
            return self._generate_fallback_html(valuation_data)
        except TemplateRenderError as e:
            self.logger.error(f"Template rendering failed: {e}", exc_info=True)
            raise TemplateRenderingError(
                f"Failed to render template {template_name}: {e}",
                company_name=valuation_data.get('company_name')
            ) from e
    
    def _generate_fallback_html(self, valuation_data: Dict[str, Any]) -> str:
        """Generate fallback HTML when templates unavailable"""
        return f"""
        <html>
        <head><title>Valuation Report</title></head>
        <body>
            <h1>Business Valuation Report</h1>
            <p><strong>Company:</strong> {valuation_data.get('company_name', 'N/A')}</p>
            <p><strong>Valuation Range:</strong> {valuation_data.get('valuation_range_min', 0)} - {valuation_data.get('valuation_range_max', 0)}</p>
            <p><em>Full template rendering unavailable</em></p>
            <pre>{json.dumps(valuation_data, indent=2)}</pre>
        </body>
        </html>
        """

