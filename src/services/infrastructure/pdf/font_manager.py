"""
Font Management for PDF/A Compliance

Ensures all fonts are embedded and subset for archival compliance.

RESPONSIBILITIES:
- Verify font embedding in PDFs
- Provide WeasyPrint font configuration
- Ensure PDF/A compliance for fonts
"""

from pathlib import Path
from typing import Dict, List, Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FontManager:
    """Manages font embedding for PDF/A compliance."""
    
    # Deterministic bundled report faces (see ``pdf/font_css.py``). The PDF
    # @font-face block references these from ``src/assets/fonts`` via file://
    # URLs — no host fonts, no CDN.
    REQUIRED_FONTS = [
        "Satoshi",               # Primary sans
        "JetBrains Mono",        # Tabular/monospace figures
        "Noto Sans",             # Deterministic text fallback (Latin+Greek)
        "Noto Sans Symbols 2",   # Monochrome symbol fallback (★ ⚠ ✗)
    ]
    
    def __init__(self, font_directory: Optional[Path] = None):
        """
        Initialize FontManager.
        
        Args:
            font_directory: Optional custom font directory path
        """
        if font_directory:
            self.font_directory = font_directory
        else:
            # Default to assets/fonts if it exists
            default_path = Path(__file__).parent.parent.parent.parent / "assets" / "fonts"
            self.font_directory = default_path if default_path.exists() else None
        
        self.logger = logger
    
    def get_weasyprint_font_config(self) -> Dict:
        """
        Return WeasyPrint font configuration for PDF/A compliance.
        
        PDF/A requirements:
        - All fonts must be embedded
        - Fonts should be subset to reduce file size
        - No external font references allowed
        
        Returns:
            Font configuration dictionary for WeasyPrint
        """
        # For now, rely on system fonts with fallbacks
        # WeasyPrint will automatically embed fonts it uses
        # Future enhancement: Add custom font files
        
        config = {
            "font_family_fallbacks": {
                "Satoshi": ["Noto Sans", "Noto Sans Symbols 2", "sans-serif"],
                "JetBrains Mono": ["Noto Sans", "Noto Sans Symbols 2", "monospace"],
            }
        }
        
        if self.font_directory and self.font_directory.exists():
            self.logger.info(
                "Custom font directory available",
                extra={"font_directory": str(self.font_directory)}
            )
            # Future: Add custom font file references
        else:
            self.logger.debug(
                "Using system fonts with fallbacks for PDF generation"
            )
        
        return config
    
    def verify_font_embedding(self, pdf_bytes: bytes) -> bool:
        """
        Verify all fonts are embedded in PDF.
        
        Args:
            pdf_bytes: PDF content to check
            
        Returns:
            True if all fonts are embedded, False otherwise
        """
        try:
            import pikepdf
            from io import BytesIO
            
            pdf = pikepdf.Pdf.open(BytesIO(pdf_bytes))
            fonts_embedded = True
            non_embedded_fonts = []
            
            # Check all pages for font objects
            for page_num, page in enumerate(pdf.pages, 1):
                if "/Resources" in page and "/Font" in page["/Resources"]:
                    fonts = page["/Resources"]["/Font"]
                    for font_name, font_obj in fonts.items():
                        # Dereference if needed
                        if isinstance(font_obj, pikepdf.Object):
                            font_obj = font_obj.resolve()
                        
                        # Check if font has embedded data
                        has_fontfile = any(
                            key in font_obj for key in [
                                "/FontFile", "/FontFile2", "/FontFile3"
                            ]
                        )
                        
                        if not has_fontfile:
                            fonts_embedded = False
                            non_embedded_fonts.append(str(font_name))
            
            if not fonts_embedded:
                self.logger.warning(
                    "Not all fonts are embedded in PDF",
                    extra={
                        "non_embedded_fonts": non_embedded_fonts,
                        "pdf_a_compliant": False,
                    }
                )
            else:
                self.logger.info("All fonts embedded - PDF/A compliant for fonts")
            
            return fonts_embedded
            
        except ImportError:
            self.logger.error("pikepdf not installed - cannot verify font embedding")
            return False
        except Exception as e:
            self.logger.error(
                f"Error verifying font embedding: {e}",
                exc_info=True
            )
            return False
    
    def get_embedded_fonts_list(self, pdf_bytes: bytes) -> List[str]:
        """
        Get list of all fonts used in PDF.
        
        Args:
            pdf_bytes: PDF content
            
        Returns:
            List of font names
        """
        try:
            import pikepdf
            from io import BytesIO
            
            pdf = pikepdf.Pdf.open(BytesIO(pdf_bytes))
            fonts = set()
            
            for page in pdf.pages:
                if "/Resources" in page and "/Font" in page["/Resources"]:
                    page_fonts = page["/Resources"]["/Font"]
                    for font_name in page_fonts.keys():
                        fonts.add(str(font_name))
            
            return sorted(list(fonts))
            
        except Exception as e:
            self.logger.error(f"Error listing fonts: {e}", exc_info=True)
            return []
