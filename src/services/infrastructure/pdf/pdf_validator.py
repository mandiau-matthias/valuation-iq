"""
PDF Validation Service

Validates PDF quality and compliance:
- PDF/A-3 compliance check
- PDF/UA accessibility check
- File integrity verification
- Metadata validation
- Font embedding verification

RESPONSIBILITIES:
- Check PDF/A archival compliance
- Verify accessibility standards (PDF/UA)
- Validate metadata completeness
- Check font embedding
- Verify bookmarks/outline presence
"""

from io import BytesIO
from typing import List, Dict, Any
from dataclasses import dataclass, field
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Check pikepdf availability
try:
    import pikepdf
    PIKEPDF_AVAILABLE = True
except ImportError:
    PIKEPDF_AVAILABLE = False
    pikepdf = None


@dataclass
class PDFValidationResult:
    """Result of PDF validation."""
    is_valid_pdfa: bool = False
    is_valid_pdfua: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    file_size_bytes: int = 0
    page_count: int = 0
    fonts_embedded: bool = False
    has_bookmarks: bool = False
    has_metadata: bool = False
    has_icc_profile: bool = False
    encryption_level: str = "none"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid_pdfa": self.is_valid_pdfa,
            "is_valid_pdfua": self.is_valid_pdfua,
            "errors": self.errors,
            "warnings": self.warnings,
            "file_size_bytes": self.file_size_bytes,
            "file_size_kb": round(self.file_size_bytes / 1024, 2),
            "page_count": self.page_count,
            "fonts_embedded": self.fonts_embedded,
            "has_bookmarks": self.has_bookmarks,
            "has_metadata": self.has_metadata,
            "has_icc_profile": self.has_icc_profile,
            "encryption_level": self.encryption_level,
        }


class PDFValidator:
    """Validates PDF compliance and quality."""
    
    def __init__(self):
        """Initialize PDF validator."""
        self.logger = logger
        self.pikepdf_available = PIKEPDF_AVAILABLE
        
        if not self.pikepdf_available:
            self.logger.warning("pikepdf not available - PDF validation disabled")
    
    def validate_pdf(self, pdf_bytes: bytes) -> PDFValidationResult:
        """
        Comprehensive PDF validation.
        
        Args:
            pdf_bytes: PDF to validate
            
        Returns:
            Validation result
        """
        result = PDFValidationResult()
        
        if not self.pikepdf_available:
            result.errors.append("pikepdf not available for validation")
            return result
        
        try:
            pdf = pikepdf.Pdf.open(BytesIO(pdf_bytes))
            
            # Basic checks
            result.file_size_bytes = len(pdf_bytes)
            result.page_count = len(pdf.pages)
            
            # Font embedding check
            result.fonts_embedded = self._check_fonts_embedded(pdf)
            if not result.fonts_embedded:
                result.errors.append("Not all fonts are embedded")
            
            # Bookmarks check
            result.has_bookmarks = self._check_bookmarks(pdf)
            if not result.has_bookmarks:
                result.warnings.append("No bookmarks/outline found")
            
            # Metadata check
            result.has_metadata = self._check_metadata(pdf)
            if not result.has_metadata:
                result.warnings.append("Metadata incomplete or missing")
            
            # ICC profile check
            result.has_icc_profile = self._check_icc_profile(pdf)
            if not result.has_icc_profile:
                result.warnings.append("ICC color profile not found")
            
            # Encryption check
            result.encryption_level = self._check_encryption(pdf)
            
            # PDF/A compliance check
            result.is_valid_pdfa = self._check_pdfa_compliance(pdf, result)
            if not result.is_valid_pdfa:
                result.errors.append("PDF/A compliance check failed")
            
            # PDF/UA accessibility check
            result.is_valid_pdfua = self._check_pdfua_compliance(pdf, result)
            if not result.is_valid_pdfua:
                result.warnings.append("PDF/UA accessibility not fully compliant")
            
            self.logger.debug(
                "PDF validation completed",
                extra={
                    "pdfa_compliant": result.is_valid_pdfa,
                    "pdfua_compliant": result.is_valid_pdfua,
                    "error_count": len(result.errors),
                    "warning_count": len(result.warnings),
                }
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"PDF validation failed: {e}", exc_info=True)
            result.errors.append(f"Validation error: {str(e)}")
            return result
    
    def _check_fonts_embedded(self, pdf: "pikepdf.Pdf") -> bool:
        """
        Check if all fonts are embedded.
        
        Args:
            pdf: PDF document
            
        Returns:
            True if all fonts embedded
        """
        def has_embedded_font(font_obj: Any) -> bool:
            try:
                descriptor = font_obj.get("/FontDescriptor") if hasattr(font_obj, "get") else None
                if descriptor is not None and any(
                    key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")
                ):
                    return True

                if any(key in font_obj for key in ("/FontFile", "/FontFile2", "/FontFile3")):
                    return True

                descendants = font_obj.get("/DescendantFonts") if hasattr(font_obj, "get") else None
                if descendants:
                    return any(has_embedded_font(descendant) for descendant in descendants)
            except Exception:
                self.logger.debug("Font object inspection failed", exc_info=True)

            return False

        try:
            for page in pdf.pages:
                if "/Resources" not in page:
                    continue
                    
                resources = page["/Resources"]
                if "/Font" not in resources:
                    continue
                
                fonts = resources["/Font"]
                for font_name, font_obj in fonts.items():
                    if not has_embedded_font(font_obj):
                        self.logger.debug(f"Font not embedded: {font_name}")
                        return False
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Font embedding check failed: {e}", exc_info=True)
            return False
    
    def _check_bookmarks(self, pdf: "pikepdf.Pdf") -> bool:
        """
        Check if PDF has bookmarks/outline.
        
        Args:
            pdf: PDF document
            
        Returns:
            True if bookmarks present
        """
        try:
            with pdf.open_outline() as outline:
                return len(outline.root) > 0
        except Exception:
            logger.debug("Bookmark check failed", exc_info=True)
            return False
    
    def _check_metadata(self, pdf: "pikepdf.Pdf") -> bool:
        """
        Check if PDF has proper metadata.
        
        Args:
            pdf: PDF document
            
        Returns:
            True if metadata is present and complete
        """
        try:
            # Check for XMP metadata
            has_xmp = pikepdf.Name.Metadata in pdf.Root
            
            # Check for document info
            has_info = False
            try:
                with pdf.open_metadata() as meta:
                    has_info = bool(meta.get("Title") or meta.get("Author"))
            except Exception:
                logger.debug("Metadata read failed", exc_info=True)
            
            return has_xmp or has_info
            
        except Exception as e:
            self.logger.warning(f"Metadata check failed: {e}")
            return False
    
    def _check_icc_profile(self, pdf: "pikepdf.Pdf") -> bool:
        """
        Check if PDF has ICC color profile embedded.
        
        Args:
            pdf: PDF document
            
        Returns:
            True if ICC profile present
        """
        try:
            if pikepdf.Name.OutputIntents in pdf.Root:
                return len(pdf.Root.OutputIntents) > 0
            return False
        except Exception:
            logger.debug("ICC profile check failed", exc_info=True)
            return False
    
    def _check_encryption(self, pdf: "pikepdf.Pdf") -> str:
        """
        Check encryption level.
        
        Args:
            pdf: PDF document
            
        Returns:
            Encryption level description
        """
        try:
            if not pdf.is_encrypted:
                return "none"
            
            # Try to determine encryption level
            encryption_str = str(pdf.encryption)
            if "AES-256" in encryption_str or "R=6" in encryption_str:
                return "AES-256"
            elif "AES" in encryption_str:
                return "AES-128"
            else:
                return "RC4"
        except Exception:
            logger.debug("Encryption check failed", exc_info=True)
            return "unknown"
    
    def _check_pdfa_compliance(
        self,
        pdf: "pikepdf.Pdf",
        result: PDFValidationResult
    ) -> bool:
        """
        Check PDF/A compliance.
        
        Basic checks:
        - Fonts embedded
        - No encryption (PDF/A doesn't allow encryption with PDF/A-3)
        - ICC color profile embedded
        - XMP metadata present
        
        Args:
            pdf: PDF document
            result: Validation result to check
            
        Returns:
            True if PDF/A compliant
        """
        checks_passed = []
        checks_failed = []
        
        # Fonts must be embedded
        if result.fonts_embedded:
            checks_passed.append("fonts_embedded")
        else:
            checks_failed.append("fonts_not_embedded")
        
        # ICC profile required
        if result.has_icc_profile:
            checks_passed.append("icc_profile")
        else:
            checks_failed.append("no_icc_profile")
        
        # XMP metadata required
        if result.has_metadata:
            checks_passed.append("metadata")
        else:
            checks_failed.append("no_metadata")
        
        # PDF/A forbids encryption. A report may deliberately be encrypted for
        # client delivery, but it must then never be represented as PDF/A.
        if result.encryption_level != "none":
            checks_failed.append("encrypted_pdf_not_pdfa")
        
        # Check for PDF/A identifier in XMP
        try:
            if pikepdf.Name.Metadata in pdf.Root:
                metadata_stream = pdf.Root.Metadata
                metadata_bytes = bytes(metadata_stream.read_bytes())
                metadata_str = metadata_bytes.decode('utf-8', errors='ignore')
                
                if 'pdfaid:part' in metadata_str and 'pdfaid:conformance' in metadata_str:
                    checks_passed.append("pdfa_identifier")
                else:
                    checks_failed.append("no_pdfa_identifier")
        except Exception:
            checks_failed.append("metadata_parse_error")
        
        # PDF/A compliant if critical checks pass
        is_compliant = (
            result.fonts_embedded and
            result.has_metadata and
            "encrypted_pdf_not_pdfa" not in checks_failed
            and len(checks_failed) == 0
        )
        
        self.logger.debug(
            f"PDF/A compliance: {'PASS' if is_compliant else 'FAIL'}",
            extra={
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
            }
        )
        
        return is_compliant
    
    def _check_pdfua_compliance(
        self,
        pdf: "pikepdf.Pdf",
        result: PDFValidationResult
    ) -> bool:
        """
        Check PDF/UA accessibility compliance.
        
        Checks:
        - Tagged PDF
        - Language specified
        - Bookmarks present
        - Metadata present
        
        Args:
            pdf: PDF document
            result: Validation result
            
        Returns:
            True if PDF/UA compliant
        """
        checks_passed = []
        checks_failed = []
        
        # Check if tagged
        try:
            if pikepdf.Name.MarkInfo in pdf.Root:
                mark_info = pdf.Root.MarkInfo
                if mark_info.get(pikepdf.Name.Marked, False):
                    checks_passed.append("tagged")
                else:
                    checks_failed.append("not_tagged")
            else:
                checks_failed.append("no_markinfo")
        except Exception:
            checks_failed.append("markinfo_error")
        
        # Check language
        try:
            if pikepdf.Name.Lang in pdf.Root:
                checks_passed.append("language")
            else:
                checks_failed.append("no_language")
        except Exception:
            checks_failed.append("language_error")
        
        # Bookmarks recommended
        if result.has_bookmarks:
            checks_passed.append("bookmarks")
        else:
            checks_failed.append("no_bookmarks")
        
        # Metadata required
        if result.has_metadata:
            checks_passed.append("metadata")
        else:
            checks_failed.append("no_metadata")
        
        # A language flag and metadata alone do not make a PDF accessible.
        # Tagged structure is a mandatory baseline; bookmarks are helpful but
        # not a substitute for a structural tree.
        is_compliant = all(
            required in checks_passed for required in ("tagged", "language", "metadata")
        )
        
        self.logger.debug(
            f"PDF/UA compliance: {'PASS' if is_compliant else 'FAIL'}",
            extra={
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
            }
        )
        
        return is_compliant
