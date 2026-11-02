"""
PDF Enhancement Service

Transforms basic WeasyPrint output into bank-grade professional PDFs with:
- PDF/A-3 archival compliance
- Enhanced XMP metadata
- Bookmarks/outline generation
- ICC color profile embedding
- Accessibility tag preparation

RESPONSIBILITIES:
- Add professional metadata (XMP)
- Embed ICC color profiles for consistent color reproduction
- Generate bookmarks from document structure
- Set PDF/A conformance markers
- Prepare document for accessibility compliance
"""

import html
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _escape_xml_text(value: Any) -> str:
    """Escape text for safe embedding in XMP/XML metadata."""
    if value is None:
        return ""
    s = str(value).strip()
    return html.escape(s, quote=True)


# Check pikepdf availability
try:
    import pikepdf

    PIKEPDF_AVAILABLE = True
except ImportError:
    PIKEPDF_AVAILABLE = False
    pikepdf = None


class PDFEnhancer:
    """Enhances PDFs with professional archival features."""

    def __init__(self, icc_profile_path: Optional[Path] = None):
        """
        Initialize PDF Enhancer.

        Args:
            icc_profile_path: Optional path to ICC color profile
        """
        self.logger = logger
        self.pikepdf_available = PIKEPDF_AVAILABLE

        if not self.pikepdf_available:
            self.logger.warning("pikepdf not available - PDF enhancement disabled")

        # Set ICC profile path
        if icc_profile_path and icc_profile_path.exists():
            self.icc_profile_path = icc_profile_path
        else:
            # Default profile location
            default_profile = (
                Path(__import__("weasyprint").__file__).parent / "pdf" / "sRGB2014.icc"
            )
            self.icc_profile_path = default_profile if default_profile.exists() else None

        if not self.icc_profile_path:
            self.logger.warning("ICC color profile not found - PDF/A compliance may be affected")

    def enhance_pdf(
        self,
        raw_pdf_bytes: bytes,
        metadata: Dict[str, Any],
        toc_structure: Optional[List[Dict]] = None,
    ) -> bytes:
        """
        Enhance PDF with professional features.

        Args:
            raw_pdf_bytes: Raw PDF from WeasyPrint
            metadata: Enhanced metadata dictionary
            toc_structure: Table of contents structure for bookmarks

        Returns:
            Enhanced PDF bytes
        """
        if not self.pikepdf_available:
            self.logger.warning("PDF enhancement skipped - pikepdf not available")
            return raw_pdf_bytes

        try:
            # Open PDF with pikepdf
            pdf = pikepdf.Pdf.open(BytesIO(raw_pdf_bytes))

            # Step 1: Set document info
            self._set_document_info(pdf, metadata)

            # Step 2: Add XMP metadata
            self._add_xmp_metadata(pdf, metadata)

            # Step 3: Embed ICC color profile (if available)
            if self.icc_profile_path:
                self._embed_color_profile(pdf)

            # Step 4: Generate bookmarks/outline
            if toc_structure:
                self._generate_bookmarks(pdf, toc_structure)

            # Step 5: Set PDF/A conformance markers
            self._set_pdfa_conformance(pdf, level="3B")

            # Step 6: Set language for accessibility
            self._set_language(pdf, str(metadata.get("language") or "en-US"))

            # Return enhanced PDF
            # WeasyPrint supplies a fresh trailer identifier on every render.
            # It is transport noise, but retaining it makes pikepdf's otherwise
            # deterministic ID depend on the random upstream value. Remove it
            # before deterministic serialization so one sealed run produces
            # byte-identical archival artifacts.
            if "/ID" in pdf.trailer:
                del pdf.trailer["/ID"]
            output = BytesIO()
            pdf.save(output, deterministic_id=True)

            self.logger.debug(
                "PDF enhanced successfully",
                extra={
                    "has_bookmarks": bool(toc_structure),
                    "has_icc_profile": bool(self.icc_profile_path),
                    "pdfa_level": "3B",
                },
            )

            return output.getvalue()

        except Exception as e:
            self.logger.error(f"PDF enhancement failed: {e}", exc_info=True)
            raise

    def _set_document_info(self, pdf: "pikepdf.Pdf", metadata: Dict):
        """
        Set traditional PDF document info dictionary.

        Args:
            pdf: PDF document
            metadata: Metadata dictionary
        """
        try:
            with pdf.open_metadata() as meta:
                meta["Title"] = metadata.get("title", "Business Valuation Report")
                meta["Author"] = metadata.get("author", "Upswitch Valuation Services")
                meta["Subject"] = metadata.get("subject", "SME Business Valuation")
                meta["Keywords"] = metadata.get("keywords", "valuation, business, SME")
                meta["Creator"] = "Upswitch Valuation Engine v1.0"
                meta["Producer"] = "WeasyPrint 63.1 + Upswitch PDF Enhancement"

            self.logger.debug("Document info set successfully")

        except Exception as e:
            self.logger.warning(f"Could not set document info: {e}")

    def _add_xmp_metadata(self, pdf: "pikepdf.Pdf", metadata: Dict):
        """
        Add XMP metadata for professional archival.

        Args:
            pdf: PDF document
            metadata: Metadata dictionary
        """
        try:
            # Escape metadata for safe XML embedding (company names may contain &, <, >)
            title = _escape_xml_text(metadata.get("title", "Business Valuation Report"))
            author = _escape_xml_text(metadata.get("author", "Upswitch Valuation Services"))
            subject = _escape_xml_text(metadata.get("subject", "SME Business Valuation"))
            description = _escape_xml_text(
                metadata.get("description", "Professional business valuation report")
            )
            valuation_date = _escape_xml_text(metadata.get("valuation_date", ""))
            company_id = _escape_xml_text(metadata.get("company_id", ""))

            # Basic XMP structure for PDF/A
            artifact_timestamp = _escape_xml_text(
                metadata.get("artifact_timestamp")
                or f"{metadata.get('valuation_date', '')}T00:00:00Z"
            )
            xmp_template = f"""<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:dc="http://purl.org/dc/elements/1.1/"
        xmlns:xmp="http://ns.adobe.com/xap/1.0/"
        xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
        xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/"
        xmlns:upswitch="http://upswitch.io/ns/valuation/1.0/">
      <dc:title>
        <rdf:Alt>
          <rdf:li xml:lang="x-default">{title}</rdf:li>
        </rdf:Alt>
      </dc:title>
      <dc:creator>
        <rdf:Seq>
          <rdf:li>{author}</rdf:li>
        </rdf:Seq>
      </dc:creator>
      <dc:subject>
        <rdf:Bag>
          <rdf:li>{subject}</rdf:li>
        </rdf:Bag>
      </dc:subject>
      <dc:description>
        <rdf:Alt>
          <rdf:li xml:lang="x-default">{description}</rdf:li>
        </rdf:Alt>
      </dc:description>
      <xmp:CreatorTool>Upswitch Valuation Engine v1.0</xmp:CreatorTool>
      <xmp:CreateDate>{artifact_timestamp}</xmp:CreateDate>
      <xmp:ModifyDate>{artifact_timestamp}</xmp:ModifyDate>
      <pdf:Producer>WeasyPrint 63.1 + Upswitch PDF Enhancement</pdf:Producer>
      <pdfaid:part>3</pdfaid:part>
      <pdfaid:conformance>B</pdfaid:conformance>
      <upswitch:ValuationDate>{valuation_date}</upswitch:ValuationDate>
      <upswitch:CompanyID>{company_id}</upswitch:CompanyID>
      <upswitch:ConfidentialityLevel>Strictly Private &amp; Confidential</upswitch:ConfidentialityLevel>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""

            # Attach XMP metadata to PDF
            pdf.Root.Metadata = pdf.make_stream(xmp_template.encode("utf-8"))
            pdf.Root.Metadata[pikepdf.Name.Type] = pikepdf.Name.Metadata
            pdf.Root.Metadata[pikepdf.Name.Subtype] = pikepdf.Name.XML

            self.logger.debug("XMP metadata added successfully")

        except Exception as e:
            self.logger.warning(f"Could not add XMP metadata: {e}")

    def _embed_color_profile(self, pdf: "pikepdf.Pdf"):
        """
        Embed sRGB ICC color profile for PDF/A compliance.

        Args:
            pdf: PDF document
        """
        try:
            if not self.icc_profile_path or not self.icc_profile_path.exists():
                self.logger.debug("ICC profile not available - skipping embedding")
                return

            # Load ICC profile
            with open(self.icc_profile_path, "rb") as f:
                icc_data = f.read()

            # Create ICC stream object
            icc_stream = pdf.make_stream(icc_data)
            icc_stream[pikepdf.Name.N] = 3  # RGB color space (3 components)
            icc_stream[pikepdf.Name.Alternate] = pikepdf.Name.DeviceRGB

            # Add to OutputIntents for PDF/A
            output_intent = pikepdf.Dictionary(
                Type=pikepdf.Name.OutputIntent,
                S=pikepdf.Name.GTS_PDFA1,
                OutputConditionIdentifier="sRGB IEC61966-2.1",
                RegistryName="http://www.color.org",
                Info="sRGB IEC61966-2.1",
                DestOutputProfile=icc_stream,
            )

            if pikepdf.Name.OutputIntents not in pdf.Root:
                pdf.Root.OutputIntents = pdf.make_indirect([output_intent])
            else:
                pdf.Root.OutputIntents.append(output_intent)

            self.logger.debug("ICC color profile embedded successfully")

        except Exception as e:
            self.logger.warning(f"Could not embed ICC profile: {e}")

    def _generate_bookmarks(self, pdf: "pikepdf.Pdf", toc_structure: List[Dict]):
        """
        Generate PDF bookmarks/outline from TOC structure.

        Args:
            pdf: PDF document
            toc_structure: List of TOC items with title, page, level
                Format: [{"title": "Section 1", "page": 2, "level": 1}, ...]
        """
        try:
            with pdf.open_outline() as outline:
                # Create bookmark hierarchy
                parent_stack = [outline.root]
                last_level = 0

                for item in toc_structure:
                    title = item.get("title", "Untitled")
                    page_num = item.get("page", 1) - 1  # 0-indexed
                    level = max(1, int(item.get("level", 1)))

                    # Ensure page number is valid
                    if page_num < 0 or page_num >= len(pdf.pages):
                        continue

                    # Determine parent based on level (ensure parent_stack never empty)
                    if level > last_level:
                        # Child of previous item
                        pass
                    elif level < last_level:
                        # Go up the hierarchy; keep at least outline.root
                        parent_stack = parent_stack[: max(1, level)]

                    # Create bookmark (parent_stack always has outline.root at index 0)
                    current_parent = parent_stack[-1] if parent_stack else outline.root
                    bookmark = current_parent.append_child()
                    bookmark.title = title
                    bookmark.destination = pdf.pages[page_num]

                    # Add to parent stack for potential children
                    if level > len(parent_stack) - 1:
                        parent_stack.append(bookmark)
                    else:
                        parent_stack[level] = bookmark

                    last_level = level

            self.logger.info(
                f"Generated {len(toc_structure)} bookmarks",
                extra={"bookmark_count": len(toc_structure)},
            )

        except Exception as e:
            self.logger.warning(f"Could not generate bookmarks: {e}")

    def _set_pdfa_conformance(self, pdf: "pikepdf.Pdf", level: str = "3B"):
        """
        Set PDF/A conformance level in metadata.

        Args:
            pdf: PDF document
            level: PDF/A level (3B, 3A, 3U)
        """
        try:
            # PDF/A conformance is set via XMP metadata (already done in _add_xmp_metadata)
            # Additional markers can be set here if needed

            # Mark as tagged if going for PDF/A-3a (full accessibility)
            if level.upper() == "3A":
                if pikepdf.Name.MarkInfo not in pdf.Root:
                    pdf.Root.MarkInfo = pikepdf.Dictionary(Marked=True)

            self.logger.debug(f"PDF/A-{level} conformance markers set")

        except Exception as e:
            self.logger.warning(f"Could not set PDF/A conformance: {e}")

    def _set_language(self, pdf: "pikepdf.Pdf", language: str = "en-US"):
        """
        Set document language for accessibility.

        Args:
            pdf: PDF document
            language: Language code (e.g., "en-US")
        """
        try:
            pdf.Root.Lang = language
            self.logger.debug(f"Document language set to {language}")
        except Exception as e:
            self.logger.warning(f"Could not set language: {e}")
