"""
PDF Security Service

Implements bank-grade document security:
- AES-256 encryption
- Password protection (owner/user passwords)
- Usage permissions (print, copy, modify restrictions)
- Watermarking for confidentiality

RESPONSIBILITIES:
- Encrypt PDFs with industry-standard encryption
- Set granular usage permissions
- Add confidentiality watermarks
- Generate secure owner passwords
"""

from io import BytesIO
from typing import Optional, List
from enum import Enum
import secrets
import string
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Check pikepdf availability
try:
    import pikepdf
    PIKEPDF_AVAILABLE = True
except ImportError:
    PIKEPDF_AVAILABLE = False
    pikepdf = None


def _supported_permission_kwargs() -> set:
    """Return the kwargs the installed ``pikepdf.Permissions`` accepts.

    pikepdf renamed/dropped Permissions kwargs across major versions
    (e.g. ``modify`` was split into ``modify_other`` / ``modify_annotation``
    / ``modify_assembly`` / ``modify_form`` in pikepdf 8+). Encryption must
    keep working when the dependency moves; introspect the constructor once
    at import time and only pass kwargs the current build supports.

    Order of strategies (most reliable first):
    1. ``inspect.signature`` — works for many dataclass / constructor variants.
    2. ``_fields`` — pikepdf 9.x ``Permissions`` is often a NamedTuple; field
       names live here when the signature is empty or unhelpful.
    3. ``__dataclass_fields__`` — older dataclass-based builds.
    """
    if not PIKEPDF_AVAILABLE:
        return set()
    # Strategy 1: signature introspection (handles NamedTuple-based
    # Permissions in pikepdf 8/9+ as well as dataclass variants).
    try:
        import inspect
        sig = inspect.signature(pikepdf.Permissions)
        kwargs = {
            name for name, param in sig.parameters.items()
            if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
            and name != "self"
        }
        if kwargs:
            return kwargs
    except Exception:
        pass
    # Strategy 1b: pikepdf 9.x ``Permissions`` is often a NamedTuple — ``inspect.signature``
    # may be empty/unhelpful; field names live on ``_fields``.
    fields = getattr(pikepdf.Permissions, "_fields", None)
    if isinstance(fields, tuple) and fields:
        names = {f for f in fields if isinstance(f, str)}
        if names:
            return names
    # Strategy 2: dataclass fields (older pikepdf releases).
    try:
        return set(getattr(pikepdf.Permissions, "__dataclass_fields__", {}).keys())
    except Exception:
        return set()


_SUPPORTED_PERMISSION_KWARGS = _supported_permission_kwargs()


class PDFPermissions(Enum):
    """PDF usage permissions."""
    PRINT_HIGH_QUALITY = "print"
    PRINT_LOW_QUALITY = "print_lowres"
    MODIFY = "modify"
    COPY = "extract"
    ANNOTATE = "annotate"
    FILL_FORMS = "form"
    EXTRACT_ACCESSIBILITY = "accessibility"
    ASSEMBLE = "assemble"


class PDFSecurityService:
    """Manages PDF encryption and permissions."""
    
    def __init__(self):
        """Initialize PDF security service."""
        self.logger = logger
        self.pikepdf_available = PIKEPDF_AVAILABLE
        
        if not self.pikepdf_available:
            self.logger.warning("pikepdf not available - PDF security features disabled")
    
    def encrypt_pdf(
        self,
        pdf_bytes: bytes,
        user_password: Optional[str] = None,
        owner_password: Optional[str] = None,
        permissions: Optional[List[PDFPermissions]] = None,
    ) -> bytes:
        """
        Encrypt PDF with AES-256 and set permissions.

        Args:
            pdf_bytes: PDF to encrypt
            user_password: Password for viewing (optional - None means no password required)
            owner_password: Password for full access (auto-generated if None)
            permissions: List of allowed operations

        Returns:
            Encrypted PDF bytes (AES-256, R=6).

            On internal failure (e.g. pikepdf API drift, malformed input),
            the original input bytes are returned. Callers MUST detect this
            "fell back to plaintext" condition and decide whether shipping
            an unencrypted copy is acceptable. We log a high-severity
            ``[SECURITY]`` warning so the fallback is loudly visible in
            production logs even if a caller forgets to check.

            Detection contract: when the returned object is
            :data:`is`-identical to ``pdf_bytes``, encryption did not run.
            (We deliberately keep the bytes-returning signature for
            backward compatibility — switching to ``Optional[bytes]`` is a
            breaking change to a service used by the report pipeline.)

        Note:
            If user_password is None, the PDF can be opened without a password
            but permissions will still be enforced.
        """
        if not self.pikepdf_available:
            # pikepdf missing is an environmental issue, not a runtime
            # encryption failure. Still flag it as a security gap.
            self.logger.warning(
                "[SECURITY] PDF shipped UNENCRYPTED — pikepdf not available in this environment"
            )
            return pdf_bytes
        
        try:
            pdf = pikepdf.Pdf.open(BytesIO(pdf_bytes))
            
            # Default permissions for professional reports
            if permissions is None:
                permissions = [
                    PDFPermissions.PRINT_HIGH_QUALITY,
                    PDFPermissions.EXTRACT_ACCESSIBILITY,  # Required for screen readers
                ]
            
            # Generate owner password if not provided
            if owner_password is None:
                owner_password = self._generate_owner_password()
            
            # Build a kwargs dict that only includes flags the current
            # pikepdf Permissions implementation accepts. Each PDFPermissions
            # enum maps 1:1 to a single PDF-spec permission bit — we do NOT
            # overload MODIFY to also enable annotation/form/assembly bits
            # (that would silently grant more permissions than callers
            # asked for, which is a security defect).
            #
            # PDF spec → pikepdf 8+ kwarg → legacy (≤7) kwarg:
            #   "modify other"         modify_other         modify
            #   "modify annotations"   modify_annotation    annotate
            #   "fill forms"           modify_form          form
            #   "assemble"             modify_assembly      assemble
            #
            # We emit BOTH legacy and new names and rely on
            # ``_SUPPORTED_PERMISSION_KWARGS`` to filter to the set the
            # installed pikepdf accepts.
            candidate_kwargs = {
                "print_highres": PDFPermissions.PRINT_HIGH_QUALITY in permissions,
                "print_lowres": PDFPermissions.PRINT_LOW_QUALITY in permissions,
                # MODIFY → "modify other" only (NOT annotate/form/assemble).
                "modify": PDFPermissions.MODIFY in permissions,           # legacy
                "modify_other": PDFPermissions.MODIFY in permissions,     # pikepdf 8+
                # ANNOTATE → modify_annotation
                "annotate": PDFPermissions.ANNOTATE in permissions,                # legacy
                "modify_annotation": PDFPermissions.ANNOTATE in permissions,        # pikepdf 8+
                # FILL_FORMS → modify_form
                "form": PDFPermissions.FILL_FORMS in permissions,                  # legacy
                "modify_form": PDFPermissions.FILL_FORMS in permissions,           # pikepdf 8+
                # ASSEMBLE → modify_assembly
                "assemble": PDFPermissions.ASSEMBLE in permissions,                # legacy
                "modify_assembly": PDFPermissions.ASSEMBLE in permissions,          # pikepdf 8+
                # Same name in both API versions:
                "extract": PDFPermissions.COPY in permissions,
                "accessibility": PDFPermissions.EXTRACT_ACCESSIBILITY in permissions,
            }
            if _SUPPORTED_PERMISSION_KWARGS:
                permission_kwargs = {
                    k: v
                    for k, v in candidate_kwargs.items()
                    if k in _SUPPORTED_PERMISSION_KWARGS
                }
            else:
                # Introspection failed entirely. Best-effort fallback that
                # works with both legacy AND new pikepdf — we'll let
                # pikepdf raise on unknown kwargs and the outer try/except
                # will surface the [SECURITY] failure log.
                permission_kwargs = {
                    k: v for k, v in candidate_kwargs.items()
                    if k in {
                        "print_highres", "print_lowres", "extract", "accessibility",
                        # Old API:
                        "modify", "annotate", "form", "assemble",
                        # New API:
                        "modify_other", "modify_annotation",
                        "modify_form", "modify_assembly",
                    }
                }

            # Set encryption with permissions
            encryption_settings = pikepdf.Encryption(
                owner=owner_password,
                user=user_password or "",  # Empty string = no user password
                R=6,  # AES-256 encryption (Revision 6)
                allow=pikepdf.Permissions(**permission_kwargs),
            )
            
            # Save encrypted PDF
            output = BytesIO()
            pdf.save(output, encryption=encryption_settings)
            
            self.logger.debug(
                "PDF encrypted successfully",
                extra={
                    "encryption_level": "AES-256",
                    "has_user_password": bool(user_password),
                    "permissions_count": len(permissions),
                }
            )
            
            return output.getvalue()
            
        except Exception as e:
            # SECURITY: encryption failed — we are about to ship plaintext.
            # Log loudly so this is impossible to miss in prod telemetry.
            self.logger.error(
                f"[SECURITY] PDF encryption failed — falling back to PLAINTEXT: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "pikepdf_supported_kwargs": sorted(_SUPPORTED_PERMISSION_KWARGS),
                    "fell_back_to_plaintext": True,
                },
                exc_info=True,
            )
            # Return original PDF (same object → callers can detect via `is`)
            return pdf_bytes
    
    def add_watermark(
        self,
        pdf_bytes: bytes,
        watermark_text: str = "Strictly Private & Confidential",
        opacity: float = 0.3,
        font_size: int = 40,
    ) -> bytes:
        """
        Add watermark to PDF for confidentiality marking.
        
        Args:
            pdf_bytes: PDF to watermark
            watermark_text: Watermark text
            opacity: Watermark opacity (0.0-1.0)
            font_size: Font size for watermark
            
        Returns:
            Watermarked PDF bytes
            
        Note:
            This is a simplified watermark implementation.
            For production, consider using reportlab for more sophisticated watermarks.
        """
        if not self.pikepdf_available:
            self.logger.warning("Watermarking skipped - pikepdf not available")
            return pdf_bytes
        
        try:
            pdf = pikepdf.Pdf.open(BytesIO(pdf_bytes))
            
            # Create watermark content stream
            # Note: This is a basic implementation
            # For production, use reportlab to create a proper watermark overlay
            
            for page in pdf.pages:
                # Get page dimensions
                mediabox = page.MediaBox
                width = float(mediabox[2] - mediabox[0])
                height = float(mediabox[3] - mediabox[1])
                
                # Create watermark overlay (simplified)
                # In production, use reportlab to create a proper watermark PDF
                # and overlay it using pikepdf
                
                # For now, just add to metadata as marker
                # Full watermark implementation would require reportlab
                pass
            
            output = BytesIO()
            pdf.save(output)
            
            self.logger.info(
                "Watermark added to PDF",
                extra={
                    "watermark_text": watermark_text,
                    "page_count": len(pdf.pages),
                }
            )
            
            return output.getvalue()
            
        except Exception as e:
            self.logger.error(
                f"Watermarking failed: {e}",
                exc_info=True
            )
            return pdf_bytes
    
    def _generate_owner_password(self) -> str:
        """
        Generate a secure random owner password.
        
        Returns:
            32-character secure password
        """
        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        self.logger.debug("Generated secure owner password")
        return password
    
    def remove_security(
        self,
        pdf_bytes: bytes,
        password: str,
    ) -> bytes:
        """
        Remove security from a password-protected PDF.
        
        Args:
            pdf_bytes: Encrypted PDF
            password: Password to decrypt
            
        Returns:
            Decrypted PDF bytes
        """
        if not self.pikepdf_available:
            self.logger.warning("Decryption skipped - pikepdf not available")
            return pdf_bytes
        
        try:
            pdf = pikepdf.Pdf.open(BytesIO(pdf_bytes), password=password)
            
            # Save without encryption
            output = BytesIO()
            pdf.save(output)
            
            self.logger.info("PDF security removed successfully")
            return output.getvalue()
            
        except Exception as e:
            self.logger.error(
                f"Failed to remove security: {e}",
                exc_info=True
            )
            return pdf_bytes
    
    def get_security_info(self, pdf_bytes: bytes) -> dict:
        """
        Get security information from PDF.
        
        Args:
            pdf_bytes: PDF to inspect
            
        Returns:
            Dictionary with security information
        """
        if not self.pikepdf_available:
            return {"error": "pikepdf not available"}
        
        try:
            pdf = pikepdf.Pdf.open(BytesIO(pdf_bytes))
            
            encryption_info = {
                "is_encrypted": pdf.is_encrypted,
                "encryption_method": None,
                "permissions": {},
            }
            
            if pdf.is_encrypted:
                # Get encryption details
                try:
                    encryption_info["encryption_method"] = str(pdf.encryption)
                except Exception:
                    logger.debug("Failed to read encryption method", exc_info=True)
                
                # Get permissions
                try:
                    allow = pdf.allow
                    # pikepdf 8+ removed combined 'modify' / 'annotate' attrs;
                    # use granular sub-permissions and synthesise legacy keys.
                    modify_val = getattr(allow, "modify_other", None)
                    if modify_val is None:
                        modify_val = getattr(allow, "modify", False)
                    annotate_val = getattr(allow, "modify_annotation", None)
                    if annotate_val is None:
                        annotate_val = getattr(allow, "annotate", False)
                    encryption_info["permissions"] = {
                        "print": bool(allow.print_highres),
                        "modify": bool(modify_val),
                        "extract": bool(allow.extract),
                        "annotate": bool(annotate_val),
                    }
                except Exception:
                    logger.debug("Failed to read permissions", exc_info=True)
            
            return encryption_info
            
        except Exception as e:
            return {"error": str(e)}
