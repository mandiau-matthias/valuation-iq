"""
PDF Generator Service for Valuation Reports

Converts HTML reports to professional PDF documents using WeasyPrint.
Designed for world-class report generation with consistent styling and branding.
"""

import logging
import os
import tempfile
from datetime import datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import Optional, Tuple

import_module("src.services.infrastructure.weasyprint_env")
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

logger = logging.getLogger(__name__)


class PDFGeneratorService:
    """
    Generate professional PDF reports from HTML content.

    WHAT: Converts HTML valuation reports to PDF format
    WHY: Provide downloadable, printable reports for clients
    HOW: Uses WeasyPrint HTML-to-PDF engine with custom styling
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize PDF generator.

        Args:
            storage_path: Path for temporary PDF storage (defaults to temp dir)
        """
        self.storage_path = Path(storage_path or tempfile.gettempdir()) / "valuation_pdfs"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Font configuration for WeasyPrint
        self.font_config = FontConfiguration()

        logger.info(f"PDFGeneratorService initialized with storage: {self.storage_path}")

    def generate_pdf_from_html(
        self,
        html_content: str,
        valuation_id: str,
        company_name: str,
        output_filename: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """
        Generate PDF from HTML content.

        Args:
            html_content: Complete HTML report content
            valuation_id: Unique valuation identifier
            company_name: Company name for filename
            output_filename: Optional custom filename (auto-generated if None)

        Returns:
            Tuple of (pdf_file_path, pdf_url, pdf_expires_at)

        Raises:
            Exception: If PDF generation fails
        """
        try:
            # Generate filename
            if not output_filename:
                safe_company_name = self._sanitize_filename(company_name)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"{valuation_id}_{safe_company_name}_{timestamp}.pdf"

            pdf_path = self.storage_path / output_filename

            # Add PDF-specific CSS for better print formatting
            pdf_css = self._get_pdf_css()

            # Wrap HTML in complete document if needed
            if not html_content.strip().startswith("<!DOCTYPE"):
                html_content = self._wrap_html(html_content, company_name)

            logger.info(f"Generating PDF for valuation {valuation_id}")

            # Generate PDF using WeasyPrint
            html = HTML(string=html_content)
            css = CSS(string=pdf_css, font_config=self.font_config)

            html.write_pdf(str(pdf_path), stylesheets=[css], font_config=self.font_config)

            # Get file size for logging
            file_size = pdf_path.stat().st_size / 1024  # KB
            logger.info(f"PDF generated successfully: {pdf_path} ({file_size:.2f} KB)")

            # Generate URL (in production, this would be a GCS/S3 URL)
            # For now, return local file path
            pdf_url = self._generate_pdf_url(valuation_id, output_filename)

            # Calculate expiration (24 hours from now)
            expires_at = (datetime.now() + timedelta(hours=24)).isoformat()

            return str(pdf_path), pdf_url, expires_at

        except Exception as e:
            logger.error(
                f"Failed to generate PDF for valuation {valuation_id}: {str(e)}", exc_info=True
            )
            raise Exception(f"PDF generation failed: {str(e)}")

    def _sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename."""
        # Replace invalid chars with underscore
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")
        # Limit length
        return filename[:50]

    def _wrap_html(self, html_content: str, company_name: str) -> str:
        """
        Wrap HTML fragment in complete document structure.

        Args:
            html_content: HTML content (may be fragment or complete doc)
            company_name: Company name for title

        Returns:
            Complete HTML document
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Valuation Report - {company_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 210mm;
            margin: 0 auto;
            padding: 20mm;
        }}
        @page {{
            size: A4;
            margin: 15mm;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""

    def _get_pdf_css(self) -> str:
        """
        Get CSS optimized for PDF generation.

        Returns:
            CSS string with print-optimized styles
        """
        return """
        @page {
            size: A4;
            margin: 15mm 20mm;
            
            @top-center {
                content: "Upswitch Valuation Report";
                font-size: 10pt;
                color: #666;
            }
            
            @bottom-right {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }
        
        h1 {
            font-size: 24pt;
            margin-top: 0;
            color: #1a1a1a;
            page-break-after: avoid;
        }
        
        h2 {
            font-size: 18pt;
            margin-top: 20pt;
            color: #2c3e50;
            page-break-after: avoid;
        }
        
        h3 {
            font-size: 14pt;
            margin-top: 15pt;
            color: #34495e;
            page-break-after: avoid;
        }
        
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 15pt 0;
            page-break-inside: avoid;
        }
        
        th, td {
            border: 1pt solid #ddd;
            padding: 8pt;
            text-align: left;
        }
        
        th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
        
        .no-break {
            page-break-inside: avoid;
        }
        
        .page-break {
            page-break-before: always;
        }
        
        .highlight {
            background-color: #fff3cd;
            padding: 10pt;
            border-left: 4pt solid #ffc107;
            margin: 15pt 0;
        }
        
        .footer {
            margin-top: 30pt;
            padding-top: 15pt;
            border-top: 1pt solid #ddd;
            font-size: 9pt;
            color: #666;
        }
        """

    def _generate_pdf_url(self, valuation_id: str, filename: str) -> str:
        """
        Generate PDF URL.

        In production, this would:
        1. Upload PDF to GCS/S3
        2. Generate signed URL with expiration
        3. Return public URL

        For now, returns a local path format that Titan can handle.

        Args:
            valuation_id: Valuation ID
            filename: PDF filename

        Returns:
            PDF URL (file path or cloud storage URL)
        """
        # Check for GCS configuration
        gcs_bucket = os.getenv("GCS_VALUATION_BUCKET")
        if gcs_bucket:
            # Production: Return GCS URL
            return (
                f"https://storage.googleapis.com/{gcs_bucket}/valuations/{valuation_id}/{filename}"
            )
        else:
            # Development: Return local file reference
            # Titan API can serve this via /api/v2/valuations/:id/pdf endpoint
            return f"/api/v2/valuations/{valuation_id}/pdf"

    def cleanup_old_pdfs(self, max_age_hours: int = 24):
        """
        Clean up old PDF files to free disk space.

        Args:
            max_age_hours: Maximum age of PDFs to keep (default: 24 hours)
        """
        try:
            cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
            deleted_count = 0

            for pdf_file in self.storage_path.glob("*.pdf"):
                if pdf_file.stat().st_mtime < cutoff_time:
                    pdf_file.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old PDF files")

        except Exception as e:
            logger.warning(f"Failed to cleanup old PDFs: {str(e)}")


# Global singleton instance
_pdf_generator: Optional[PDFGeneratorService] = None


def get_pdf_generator() -> PDFGeneratorService:
    """Get or create global PDF generator instance."""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = PDFGeneratorService()
    return _pdf_generator
